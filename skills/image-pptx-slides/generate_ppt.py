#!/usr/bin/env python3
"""Generate editable image-model/SDK PowerPoint files on PopAI beta, or download a PPTX."""

import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import quote, urlparse
import zipfile

import requests

API = "https://api.01ww.org"
ORIGIN = "https://beta.01ww.org"
WEB = f"{ORIGIN}/agentic-pptx"
BUCKET = "popai-file-boe"
S3 = f"https://{BUCKET}.s3-accelerate.amazonaws.com/"


def emit(event_type, **values):
    print(json.dumps({"type": event_type, **values}, ensure_ascii=False), flush=True)


def decode(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def http_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in ("https", "http") and bool(parsed.netloc)


def headers(token, accept="application/json"):
    return {"authorization": token, "app-name": "popai-skill",
            "content-type": "application/json", "accept": accept,
            "origin": ORIGIN, "referer": f"{ORIGIN}/"}


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
        json={"md5": md5, "bucket": BUCKET, "prefix": key, "contentType": mime},
        timeout=(15, 60)))
    fields = data.get("fields") if isinstance(data, dict) else None
    if not isinstance(fields, dict) or not fields.get("policy"):
        raise RuntimeError("Presign response has no upload form")
    upload_url = data.get("url") or S3
    if not http_url(upload_url):
        raise RuntimeError("Presign response has no usable upload URL")
    form = {**fields, "key": fields.get("key") or key}
    with path.open("rb") as source:
        response = requests.post(upload_url, data=form,
                                 files={"file": (path.name, source, mime)}, timeout=(15, 180))
    response.raise_for_status()
    # popaiUrl is the public reference URL; the POST destination is not always the object URL.
    file_url = data.get("popaiUrl") or f"{S3}{quote(form['key'], safe='/')}"
    if not http_url(file_url):
        raise RuntimeError("Presign response has no usable reference URL")
    return {"md5": md5, "filename": path.name, "extname": path.suffix.lstrip(".").lower(),
            "url": file_url}


def create_channel(token, query, files):
    # Beta routes 900012 to ImagePptxAgentWorkflowChatEntity, producing SDK-native PPTX.
    payload = {"templateId": "900012", "message": query}
    if files:
        payload.update(docs=[{**info, "pageCount": "1"} for info in files],
                       chatType="PptAgentMultiFile", isUploadToEnhance=True)
    data = api_data(requests.post(f"{API}/api/v1/chat/getChannel", headers=headers(token),
                                  json=payload, timeout=(15, 60)))
    channel_id = data.get("channelId") if isinstance(data, dict) else None
    if not isinstance(channel_id, str) or not channel_id:
        raise RuntimeError("Channel creation returned no channelId")
    return channel_id


def agent_events(item):
    event = decode(item.get("agentEvent"))
    if isinstance(event, dict):
        return [event]
    events = decode(item.get("agentEventList"))
    return [e for e in events if isinstance(e, dict)] if isinstance(events, list) else []


def apply_event(event, state):
    kind = event.get("event") or ""
    message = event.get("message") or {}
    message = message if isinstance(message, dict) else {}
    param = message.get("param") or ""
    if event.get("nodeId") == "ERROR":
        raise RuntimeError(f"Generation error: {param or message.get('action') or 'unknown'}")
    if kind == "NODE_END" and message.get("action") == "✅ Task Stopped":
        raise RuntimeError("Generation was stopped; inspect the beta channel online")
    if "cot" in kind.lower():
        return
    if kind.startswith("TOOL_CALLS-ask_user_question"):
        state["question"] = param
        state["interactive"] = event.get("interactive") is True
        emit("question", content=param, interactive=state["interactive"])
    elif kind == "TOOL_CALLS-pptx" or event.get("nodeId") == "pptx":
        media = decode(event.get("media"))
        entries = media if isinstance(media, list) else [media]
        for entry in entries:
            if isinstance(entry, dict) and http_url(entry.get("url")):
                previews = entry.get("imgList") or []
                previews = [u for u in previews if http_url(u)] if isinstance(previews, list) else []
                state["result"] = {"pptx_url": entry["url"],
                                   "file_name": entry.get("fileName") or "presentation.pptx",
                                   "preview_images": previews, "preview_count": len(previews)}
                state["interactive"] = False
                emit("pptx_available", **state["result"], is_end=False)
    elif kind == "NODE_END":
        if param:
            state["summary"] = param
            emit("summary", text=param)
    elif "update_task_list" in kind:
        tasks = decode(param)
        if isinstance(tasks, list):
            tasks = tasks[0] if tasks else {}
        if isinstance(tasks, dict):
            for task in tasks.get("todos") or []:
                if isinstance(task, dict):
                    emit("task", **{key: task.get(key, "") for key in ("id", "content", "status")})
    elif "web_search" in kind:
        emit("search", action=message.get("action", ""), results=event.get("ragList") or [])
    elif kind.startswith("TOOL_CALLS") and param:
        emit("tool_result", event=kind, action=message.get("action", ""), result=param)


def sse_payloads(response):
    """Read complete SSE records, including multiline data and a final unterminated record."""
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
    state = {"result": None, "summary": "", "interactive": False}
    payload = {"isGetJson": True, "channelId": channel_id, "message": query}
    payload.update({"fileUrls": [f["url"] for f in files]} if files else {"imageUrls": []})
    started = time.monotonic()
    # Never replay this POST automatically: generation can consume credits.
    with requests.post(f"{API}/api/v1/chat/send", headers=headers(token, "text/event-stream"),
                       json=payload, stream=True, timeout=(15, 180)) as response:
        response.raise_for_status()
        if not response.headers.get("content-type", "").lower().startswith("text/event-stream"):
            raise RuntimeError("Generation returned a non-SSE response; check beta authentication/API access")
        for record in sse_payloads(response):
            if time.monotonic() - started > 1200:
                raise RuntimeError("Generation exceeded the 20-minute budget; inspect the beta channel online")
            items = decode(record)
            if items is None:
                raise RuntimeError("Invalid JSON in generation stream")
            ended = False
            for item in items if isinstance(items, list) else [items]:
                if not isinstance(item, dict):
                    continue
                if item.get("error"):
                    raise RuntimeError(f"Generation error {item.get('code')}: {item.get('content', '')}")
                for event in agent_events(item):
                    apply_event(event, state)
                ended = ended or item.get("last") is True
            if ended:
                emit("stream_end")
                if state["interactive"]:
                    emit("needs_input", channel_id=channel_id, question=state.get("question"),
                         web_url=f"{WEB}/{channel_id}", is_end=False)
                    raise RuntimeError("Generation requires user input; continue on the beta webpage")
                if not state["result"]:
                    raise RuntimeError("Stream finished without a PPTX download URL")
                return {**state["result"], "summary": state["summary"]}
    raise RuntimeError("Generation stream closed without last:true; inspect the beta channel before retrying")


def download_pptx(url, output):
    path = Path(output).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # Signed file URLs must not receive the API authorization header.
        with requests.get(url, stream=True, timeout=(15, 180)) as response:
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.",
                                             suffix=".part", delete=False) as target:
                temporary = Path(target.name)
                for chunk in response.iter_content(65536):
                    target.write(chunk)
        with zipfile.ZipFile(temporary) as package:
            if not {"[Content_Types].xml", "ppt/presentation.xml"}.issubset(package.namelist()):
                raise ValueError("Downloaded file is not a PowerPoint package")
            if package.testzip() is not None:
                raise ValueError("Downloaded PPTX package is corrupt")
        temporary.replace(path)
        return str(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--query", "-q", help="Initial presentation requirements")
    mode.add_argument("--download-url", help="Download an existing PPTX URL without generation")
    parser.add_argument("--file", "-f", nargs="+", default=[], help="Local reference files (max 5)")
    parser.add_argument("--output", "-o", help="Download and validate the PPTX at this local .pptx path")
    args = parser.parse_args()
    if args.output and Path(args.output).suffix.lower() != ".pptx":
        parser.error("--output must have the .pptx extension")
    if args.download_url:
        if not http_url(args.download_url) or not args.output or args.file:
            parser.error("--download-url requires an HTTP(S) URL and --output, and excludes --file")
    else:
        if not args.query.strip():
            parser.error("--query must be nonempty")
        if len(args.file) > 5:
            parser.error("Maximum 5 reference files allowed")
        for file_path in args.file:
            if not Path(file_path).is_file():
                parser.error(f"Reference file not found: {file_path}")
        token = os.getenv("POPAI_BETA_ACCESS_TOKEN")
        if not token or not token.strip():
            parser.error("POPAI_BETA_ACCESS_TOKEN environment variable with beta access is required")
    channel_id = None
    try:
        if args.download_url:
            local_path = download_pptx(args.download_url, args.output)
            emit("download_ready", pptx_url=args.download_url, local_path=local_path, is_end=True)
            return 0
        files = []
        for file_path in args.file:
            emit("uploading", file_name=Path(file_path).name)
            files.append(upload_file(token, file_path))
        channel_id = create_channel(token, args.query, files)
        emit("channel", channel_id=channel_id, web_url=f"{WEB}/{channel_id}")
        result = generate(token, channel_id, args.query, files)
        result.update(channel_id=channel_id, web_url=f"{WEB}/{channel_id}")
        if args.output:
            emit("export_result", **result, is_end=False)
            result["local_path"] = download_pptx(result["pptx_url"], args.output)
        emit("pptx_ready", **result, is_end=True)
        return 0
    except Exception as error:
        emit("error", message=str(error), channel_id=channel_id,
             web_url=f"{WEB}/{channel_id}" if channel_id else None, is_end=False)
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
