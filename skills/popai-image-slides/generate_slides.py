#!/usr/bin/env python3
"""Generate PopAI image slides, then export them through the site's PPTX API."""

import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import sys
import time
import zipfile

import requests

API = "https://api.popai.pro"
WEB = "https://www.popai.pro/agentic-sota-ppt"
S3 = "https://popai-file.s3-accelerate.amazonaws.com/"
STYLES = {"16:9": {"width": 1280, "height": 720},
          "4:3": {"width": 1280, "height": 960}}


def emit(event_type, **values):
    print(json.dumps({"type": event_type, **values}, ensure_ascii=False), flush=True)


def decode(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def headers(token, accept="application/json"):
    return {"authorization": token, "app-name": "popai-skill",
            "content-type": "application/json", "accept": accept,
            "origin": "https://www.popai.pro", "referer": "https://www.popai.pro/"}


def api_data(response):
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError("API response is not an object")
    if body.get("code") not in (None, 200, "200"):
        raise RuntimeError(f"API error {body.get('code')}: {body.get('message', '')}")
    return body.get("data")


def upload_file(token, file_path):
    path = Path(file_path)
    digest = hashlib.md5()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8192), b""):
            digest.update(chunk)
    md5 = digest.hexdigest()
    key = f"f/{md5}/{path.name}"
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = api_data(requests.post(
        f"{API}/py/api/v1/chat/getPresignedPost", headers=headers(token),
        json={"md5": md5, "bucket": "popai-file", "prefix": key, "contentType": mime},
        timeout=(15, 60)))
    fields = data.get("fields") if isinstance(data, dict) else None
    if not isinstance(fields, dict) or not fields.get("policy"):
        raise RuntimeError("Presign response has no upload form")
    upload_url = data.get("url") or S3
    form = {**fields, "key": fields.get("key") or key, "Content-Type": mime}
    with path.open("rb") as source:
        response = requests.post(upload_url, data=form,
                                 files={"file": (path.name, source, mime)}, timeout=(15, 180))
    response.raise_for_status()
    return {"md5": md5, "filename": path.name, "extname": path.suffix.lstrip(".").lower(),
            "url": f"{upload_url.rstrip('/')}/{form['key']}"}


def create_channel(token, query, files, ratio):
    payload = {"templateId": "900016", "message": query,
               "advanceConfig": {"pptAspectRatio": ratio}}
    if files:
        payload.update(docs=[{**info, "pageCount": "1"} for info in files],
                       chatType="PptAgentMultiFile", isUploadToEnhance=True, fromPpt=True)
    data = api_data(requests.post(f"{API}/api/v1/chat/getChannel", headers=headers(token),
                                  json=payload, timeout=(15, 60)))
    channel_id = data.get("channelId") if isinstance(data, dict) else None
    if not channel_id:
        raise RuntimeError("Channel creation returned no channelId")
    return channel_id


def slides_from(container):
    container = decode(container)
    if isinstance(container, list):
        for entry in reversed(container):
            found = slides_from(entry)
            if found:
                return found
        return []
    if isinstance(container, dict):
        for key in ("sotaSlides", "imgList", "img_list"):
            value = decode(container.get(key))
            if isinstance(value, list) and value:
                return value
    return []


def image_urls(slides):
    urls = []
    for index, slide in enumerate(slides, 1):
        if isinstance(slide, dict) and slide.get("status") == "locked":
            raise RuntimeError(f"Slide {index} is locked; complete access online before exporting")
        url = slide if isinstance(slide, str) else None
        if isinstance(slide, dict):
            url = slide.get("url") or slide.get("imageUrl")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise RuntimeError(f"Slide {index} has no usable image URL")
        urls.append(url)
    if not urls:
        raise RuntimeError("No generated slide images available for export")
    return urls


def agent_events(item):
    event = decode(item.get("agentEvent"))
    if isinstance(event, dict):
        return [event]
    events = decode(item.get("agentEventList"))
    return [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []


def apply_event(event, state, report=True, historical=False):
    kind = event.get("event") or ""
    message = event.get("message") or {}
    message = message if isinstance(message, dict) else {}
    param = message.get("param") or ""
    if "cot" in kind.lower():
        return
    if event.get("nodeId") == "ERROR":
        detail = param or message.get("action") or "unknown"
        if historical:
            # A completed failed turn does not invalidate the saved slide deck
            # or prevent a new instruction from being sent to this channel.
            state["latest_turn_error"] = detail
            return
        raise RuntimeError(f"Generation error: {detail}")
    if kind.startswith("TOOL_CALLS-ask_user_question"):
        state["question"] = param
        state["interactive"] = event.get("interactive") is True
        if report:
            emit("question", content=param, interactive=state["interactive"])
    elif kind == "TOOL_CALLS-sota" or event.get("nodeId") == "sota":
        slides = slides_from(event.get("media"))
        if slides:
            state["slides"] = slides
            state["interactive"] = False
            if report:
                # Progress media may contain pages that are still being generated.
                urls = [s if isinstance(s, str) else s.get("url") or s.get("imageUrl")
                        for s in slides if isinstance(s, (str, dict))]
                urls = [url for url in urls if isinstance(url, str) and url]
                emit("slides_ready", channel_id=state["channel_id"],
                     preview_images=urls, preview_count=len(urls), is_end=False)
    elif kind == "NODE_END":
        if param:
            state["summary"] = param
            if report:
                emit("summary", text=param)
    elif report and "update_task_list" in kind:
        tasks = decode(param)
        if isinstance(tasks, list):
            tasks = tasks[0] if tasks else {}
        if isinstance(tasks, dict):
            for task in tasks.get("todos") or []:
                if isinstance(task, dict):
                    emit("task", **{key: task.get(key, "") for key in ("id", "content", "status")})
    elif report and "web_search" in kind:
        emit("search", action=message.get("action", ""), results=event.get("ragList") or [])
    elif report and kind.startswith("TOOL_CALLS") and param:
        emit("tool_result", event=kind, action=message.get("action", ""), result=param)


def sse_payloads(response):
    """Read full SSE records, including multiline data and a final unterminated record."""
    data = []
    for raw in response.iter_lines():
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        if not line:
            if data:
                yield "\n".join(data)
                data = []
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data:
        yield "\n".join(data)


def generate(token, channel_id, query, files):
    state = {"channel_id": channel_id, "slides": [], "summary": "", "interactive": False}
    payload = {"isGetJson": True, "channelId": channel_id, "message": query}
    payload.update({"fileUrls": [f["url"] for f in files]} if files else {"imageUrls": []})
    started = time.monotonic()
    # Never replay this POST automatically: generation can consume credits.
    with requests.post(f"{API}/api/v1/chat/send", headers=headers(token, "text/event-stream"),
                       json=payload, stream=True, timeout=(15, 180)) as response:
        response.raise_for_status()
        if not response.headers.get("content-type", "").lower().startswith("text/event-stream"):
            raise RuntimeError("Generation returned a non-SSE response; check authentication/API access")
        for record in sse_payloads(response):
            if time.monotonic() - started > 1200:
                raise RuntimeError("Generation exceeded the 20-minute budget; inspect the channel online")
            items = decode(record)
            if items is None:
                raise RuntimeError("Invalid JSON in generation stream")
            for item in items if isinstance(items, list) else [items]:
                if not isinstance(item, dict):
                    continue
                if item.get("error"):
                    raise RuntimeError(f"Generation error {item.get('code')}: {item.get('content', '')}")
                for event in agent_events(item):
                    apply_event(event, state)
                if item.get("last") is True:
                    emit("stream_end")
                    if state["interactive"]:
                        emit("needs_input", channel_id=channel_id, question=state.get("question"),
                             web_url=f"{WEB}/{channel_id}", is_end=False)
                        raise RuntimeError("Generation requires user input; resume the channel online")
                    return state
    raise RuntimeError("Generation stream closed without last:true; inspect the channel before retrying")


def current_channel(token, channel_id):
    data = api_data(requests.get(f"{API}/api/v1/chat/messages", headers=headers(token),
                                 params={"channelId": channel_id, "pageSize": 50}, timeout=(15, 60)))
    if not isinstance(data, dict) or not isinstance(data.get("channel"), dict):
        raise RuntimeError("Messages response has no channel state")
    channel = data["channel"]
    if str(channel.get("promptTemplateId")) != "900016":
        raise RuntimeError("This channel is not an image-slides (900016) channel")
    state = {"channel_id": channel_id, "slides": slides_from(channel.get("pptContext")),
             "summary": "", "interactive": False}
    messages = data.get("message") or []
    latest = next((m for m in reversed(messages)
                   if isinstance(m, dict) and m.get("roleEnum") == "AI"), None)
    if latest:
        if latest.get("isFinish") is not True:
            raise RuntimeError("Latest generation is unfinished; resume or wait in the online channel")
        from_message = {"channel_id": channel_id, "slides": [], "summary": "", "interactive": False}
        for event in agent_events(latest):
            apply_event(event, from_message, report=False, historical=True)
        if from_message["interactive"]:
            raise RuntimeError("Latest generation requires user input; resume the channel online")
        if not state["slides"]:
            state["slides"] = from_message["slides"]
        if from_message.get("latest_turn_error"):
            state["latest_turn_error"] = from_message["latest_turn_error"]
        else:
            state["summary"] = from_message["summary"]
    ext = decode(channel.get("ext")) or {}
    config = (ext.get("advanceConfig") or {}) if isinstance(ext, dict) else {}
    ratio = config.get("pptAspectRatio", "16:9")
    if ratio not in STYLES:
        raise RuntimeError(f"Unsupported saved canvas ratio: {ratio}")
    state.update(title=channel.get("channelName") or "Presentation", aspect_ratio=ratio)
    return state


def export_pptx(token, channel_id, title, urls, ratio):
    payload = {"channelId": channel_id, "fileName": title, "type": "ppt",
               "pptExportVo": {"imageList": urls, "style": STYLES[ratio]}, "sota": True}
    data = api_data(requests.post(f"{API}/api/v1/file/export/channel/pptx/v2",
                                  headers=headers(token), json=payload, timeout=(15, 180)))
    url = data.get("url") if isinstance(data, dict) else None
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise RuntimeError("PPTX export returned no download URL; retry with --export-only")
    return {"pptx_url": url, "file_name": data.get("fileName") or f"{title}.pptx",
            **({"fallback_url": data["fallbackUrl"]} if data.get("fallbackUrl") else {})}


def download_pptx(result, output):
    path = Path(output).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    for url in (result["pptx_url"], result.get("fallback_url")):
        if not url:
            continue
        try:
            # Signed file URLs do not receive the API authorization header.
            with requests.get(url, stream=True, timeout=(15, 180)) as response:
                response.raise_for_status()
                with temporary.open("wb") as target:
                    for chunk in response.iter_content(65536):
                        target.write(chunk)
            with zipfile.ZipFile(temporary) as package:
                if not {"[Content_Types].xml", "ppt/presentation.xml"}.issubset(package.namelist()):
                    raise ValueError("Downloaded file is not a PowerPoint package")
                if package.testzip() is not None:
                    raise ValueError("Downloaded PPTX package is corrupt")
            temporary.replace(path)
            return str(path)
        except (requests.RequestException, OSError, ValueError, zipfile.BadZipFile):
            temporary.unlink(missing_ok=True)
    raise RuntimeError("PPTX download/validation failed; the export URL is retained in the export_result event")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", "-q", help="Presentation topic or revision instruction")
    parser.add_argument("--file", "-f", nargs="*", default=[], help="Local reference files (max 5)")
    parser.add_argument("--channel-id", "-c", help="Existing image-slides channel ID")
    parser.add_argument("--export-only", action="store_true", help="Export a completed channel without generation")
    parser.add_argument("--aspect-ratio", choices=STYLES, help="New deck canvas ratio (default: 16:9)")
    parser.add_argument("--output", "-o", help="Download and validate the PPTX at this local path")
    args = parser.parse_args()
    if args.export_only:
        if not args.channel_id or args.query or args.file or args.aspect_ratio:
            parser.error("--export-only requires --channel-id and excludes --query, --file, --aspect-ratio")
    elif not args.query or not args.query.strip():
        parser.error("--query is required for generation or revision")
    if args.channel_id and args.aspect_ratio:
        parser.error("--aspect-ratio applies only to new channels")
    if len(args.file) > 5:
        parser.error("Maximum 5 reference files allowed")
    for file_path in args.file:
        if not Path(file_path).is_file():
            parser.error(f"Reference file not found: {file_path}")
    token = os.getenv("POPAI_ACCESS_TOKEN")
    if not token:
        parser.error("POPAI_ACCESS_TOKEN environment variable is required")
    channel_id = args.channel_id
    try:
        # Check channel ownership/type/completion before uploading references or revising.
        saved = current_channel(token, channel_id) if channel_id else None
        files = [upload_file(token, f) for f in args.file]
        if not channel_id:
            channel_id = create_channel(token, args.query, files, args.aspect_ratio or "16:9")
        emit("channel", channel_id=channel_id, web_url=f"{WEB}/{channel_id}")
        if saved and saved.get("latest_turn_error"):
            emit("history_warning", channel_id=channel_id,
                 message="The last completed turn was marked failed. Continuing from the saved deck; this does not confirm that the failed turn's requested changes were applied.",
                 previous_error=saved["latest_turn_error"])
        generated = None if args.export_only else generate(token, channel_id, args.query, files)
        # Read authoritative state after the stream, including the saved title and ratio.
        saved = saved if args.export_only else current_channel(token, channel_id)
        slides = generated["slides"] if generated and generated["slides"] else saved["slides"]
        urls = image_urls(slides)
        emit("exporting", channel_id=channel_id)
        result = export_pptx(token, channel_id, saved["title"], urls, saved["aspect_ratio"])
        result.update(channel_id=channel_id, web_url=f"{WEB}/{channel_id}",
                      preview_images=urls, preview_count=len(urls),
                      summary=(generated["summary"] if generated else "") or saved["summary"])
        if saved.get("latest_turn_error"):
            result["latest_turn_error"] = saved["latest_turn_error"]
        if args.output:
            # Preserve the usable export link even if downloading the local file fails.
            emit("export_result", **result, is_end=False)
            result["local_path"] = download_pptx(result, args.output)
        emit("pptx_ready", **result, is_end=True)
        return 0
    except Exception as error:
        emit("error", message=str(error), channel_id=channel_id,
             web_url=f"{WEB}/{channel_id}" if channel_id else None, is_end=False)
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
