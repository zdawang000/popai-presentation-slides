---
name: popai-image-slides
description: Create image-model slides with PopAI, revise an existing image-slides presentation, and export the generated slide images to a final PPTX. Use for image-based or creative slides and PopAI agentic-sota-ppt links.
metadata: { "openclaw": { "emoji": "🖼️", "requires": { "bins": ["python3"], "env": ["POPAI_ACCESS_TOKEN"] }, "primaryEnv": "POPAI_ACCESS_TOKEN" } }
---

# PopAI Image Slides

Create slides with PopAI's image-model workflow at https://www.popai.pro/agentic-sota-ppt. Supply a meaningful topic, audience, language, slide count, and visual preferences when available. The service can research a topic and use uploaded reference files or URLs included in the prompt.

This workflow generates slide images first. After generation finishes, call the site's Download → PowerPoint (.pptx) export API to obtain the final PPTX. An image URL, preview list, summary, or stream-end event is not a PPTX download result. Do not promise editable text/shapes or faithful reproduction of a supplied PowerPoint template; this is an image-based presentation workflow.

## Setup

Use `POPAI_ACCESS_TOKEN` from the environment. If absent, direct the user to https://www.popai.pro/popai-skill to obtain a token and configure it locally. Do not print or save the token in skill files or logs.

The helper requires Python 3 and `requests` (`python3 -m pip install requests` if needed). Resolve `generate_slides.py` relative to this skill's directory, regardless of the current working directory.

## Generate and revise

The helper supports three modes: generate a new presentation, revise an existing presentation, or export an existing presentation without generating new slides. Generation and revision both automatically export the finished slides to PPTX.

### Parameters

| Parameter | Value and default | Purpose and applicable modes |
| --- | --- | --- |
| `--query`, `-q` | Nonempty text; no default | Required for generation and revision. For generation, describe the topic, audience, language, slide count, content requirements, and visual style. For revision, describe the changes to the existing deck. Include reference URLs directly in this text. Cannot be used with `--export-only`. |
| `--file`, `-f` | Local file paths separated by spaces; omitted by default | Optional for generation and revision. Upload up to 5 reference files, such as PDF, DOCX, PPTX, or images. Every path must point to an existing file; quote paths containing spaces. A PPTX file supplies reference content. For revision, these are additional materials for the current request. Cannot be used with `--export-only`. |
| `--channel-id`, `-c` | Existing image-slides channel ID; omitted by default | Omit for new generation so the helper creates a channel. Required for revision and export-only so the helper reuses that channel. Supply the ID itself, not the full URL: it is the final path segment of `https://www.popai.pro/agentic-sota-ppt/CHANNEL_ID`. The channel must be accessible with the configured token and use the image-slides workflow. |
| `--export-only` | Flag with no value; disabled by default | Export the current completed presentation without submitting a generation or revision request. Requires `--channel-id`. Cannot be combined with `--query`, `--file`, or `--aspect-ratio`. Useful when only the PPTX is needed or a previous export failed. |
| `--aspect-ratio` | `16:9` or `4:3`; defaults to `16:9` for new generation | Set the canvas ratio when creating a new presentation. Cannot be used with `--channel-id`. Revision and export use the ratio saved in the existing channel. |
| `--output`, `-o` | Local output file path; omitted by default | Optional in all three modes. After export, download the PPTX to this path, validate its PowerPoint package, and return `local_path`. Use a `.pptx` filename. Relative paths resolve from the process's working directory; missing parent directories are created. A successful download replaces an existing file at that path. Without this option, the helper returns the download URL without saving the file locally. |
| `--help`, `-h` | Flag with no value | Display CLI usage and exit without API calls; no token is required. |

`POPAI_ACCESS_TOKEN` is an environment variable, not a CLI parameter, and is required for all three working modes. Language, slide count, audience, and visual style are specified in `--query`; they have no separate CLI flags.

### Generate a new presentation

Use `--query` without `--channel-id`. Optionally supply reference files, the canvas ratio, and a local output path.

The helper uploads references, creates an image-slides channel, generates slide images, and then calls the PPTX export API. Save the returned `channel_id` for later revisions or exports.

```bash
# Topic only; use the default 16:9 canvas and return the PPTX download URL
python3 generate_slides.py --query "Create 8 Chinese slides about AI industry trends for investors, with a dark technology theme"

# Use references, select a 4:3 canvas, and download the exported file locally
python3 generate_slides.py \
  --query "Create 6 Chinese slides summarizing this report for executives, with a clean blue theme" \
  --file "Annual Report.pdf" chart.png \
  --aspect-ratio 4:3 \
  --output ./report.pptx
```

### Revise a presentation over multiple rounds

Use the same `--channel-id` with a new `--query` for each revision. The helper checks the channel, submits the revision, and exports the updated slides to a new PPTX result. It retains the existing channel and saved canvas ratio.

Add `--file` when a revision needs new source materials. Add `--output` to download that round's exported PPTX. Use the latest returned download link when delivering the revised deck. If the previous turn is unfinished or awaiting user input, resume it online before submitting another revision.

```bash
# First revision: change content and visual style
python3 generate_slides.py --channel-id "CHANNEL_ID" --query "Make slide 3 less dense and change the theme to blue"

# Another revision on the same channel: use new references and save this version
python3 generate_slides.py \
  --channel-id "CHANNEL_ID" \
  --query "Update the financial data using this report and add a conclusion slide" \
  --file new_report.pdf \
  --output ./revised.pptx
```

### Export an existing presentation

Use `--channel-id` with `--export-only`. The helper reads the channel's current images, title, canvas ratio, and latest turn status, then calls the PPTX export API. It does not create a channel or submit a generation/revision request.

The latest turn must be completed, and every slide must have an accessible image URL. Locked pages, unfinished generation, or pending interactive questions prevent export. This mode is also the recovery path after an export failure: reuse the saved channel ID to request the PPTX again.

```bash
# Export the current deck and return its PPTX download URL
python3 generate_slides.py --channel-id "CHANNEL_ID" --export-only

# Export, download, and validate the PPTX locally
python3 generate_slides.py --channel-id "CHANNEL_ID" --export-only --output ./presentation.pptx
```

## Agent workflow

1. Preserve the user's topic, materials, and visual preferences in `--query`. Include reference URLs directly in the query; pass local files with `--file`.
2. Run the helper with a generation budget of up to 20 minutes. Monitor its JSON lines and report useful task/search/image/export progress while it runs. Do not give a fixed completion-time guarantee.
3. Save the `channel_id` and `web_url` from the initial `channel` event for follow-up edits or export recovery.
4. `slides_ready` reports generated page images, with `is_end: false`. Continue through `stream_end` and `exporting`; the helper invokes the PPTX export API automatically.
5. Only `pptx_ready` with a nonempty `pptx_url` and `is_end: true` confirms export success. Present the summary, PPTX download link, and online view/edit link. If `--output` was used, also deliver the validated local file.
6. On an error or interrupted stream, preserve the channel link and explain which stage failed. Do not automatically resend a generation request. For an export failure, use `--export-only` on that channel. If the latest server turn is still unfinished or requires input, resume it online before exporting.

An `ask_user_question` event can be informational while the service waits for its own defaults. If the stream ends with an unresolved interactive question, the helper reports `needs_input` and does not export an older deck as the new result. Relay the question and the online link; do not invent an answer.

## Output

Stdout contains one JSON object per line. Progress events include `channel`, `task`, `search`, `tool_result`, `question`, `summary`, `slides_ready`, `stream_end`, and `exporting`. Errors exit nonzero. Stderr contains diagnostics.

```json
{"type":"channel","channel_id":"CHANNEL_ID","web_url":"https://www.popai.pro/agentic-sota-ppt/CHANNEL_ID"}
{"type":"slides_ready","channel_id":"CHANNEL_ID","preview_images":["https://example.com/slide-1.png"],"preview_count":1,"is_end":false}
{"type":"exporting","channel_id":"CHANNEL_ID"}
{"type":"pptx_ready","is_end":true,"channel_id":"CHANNEL_ID","pptx_url":"https://example.com/presentation.pptx","file_name":"presentation.pptx","preview_images":["https://example.com/slide-1.png"],"preview_count":1,"web_url":"https://www.popai.pro/agentic-sota-ppt/CHANNEL_ID","summary":"Presentation created"}
```

`local_path` is included only when the PPTX was downloaded and its package validated. `fallback_url` is included when the export service supplies it.

## API notes

API origin: `https://api.popai.pro`; headers: `authorization: POPAI_ACCESS_TOKEN` and `app-name: popai-skill`.

- Create: `POST /api/v1/chat/getChannel` with `templateId: "900016"` and `advanceConfig.pptAspectRatio`.
- Generate/revise: `POST /api/v1/chat/send`. Image output uses `TOOL_CALLS-sota` or `nodeId: sota`; read `media.sotaSlides` or `imgList`. Persisted channel images use `pptContext.sotaSlides` or `img_list`.
- Current state: `GET /api/v1/chat/messages?channelId=CHANNEL_ID&pageSize=50` supplies channel title, saved ratio, images, and latest turn status.
- Export: `POST /api/v1/file/export/channel/pptx/v2` with the following payload:

```json
{"channelId":"CHANNEL_ID","fileName":"Presentation title","type":"ppt","pptExportVo":{"imageList":["https://example.com/slide-1.png"],"style":{"width":1280,"height":720}},"sota":true}
```

PowerPoint export uses `type: "ppt"`. For 4:3, the style dimensions are 1280 × 960. The response provides `data.url`, `data.fileName`, and optionally `data.fallbackUrl`. Preserve page order; locked pages or missing image URLs prevent export. These contracts were checked against the public frontend on 2026-10-08; authenticated generation/export requires a separate live check.

Support: customerservice@popai.pro
