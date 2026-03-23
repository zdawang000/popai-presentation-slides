---
name: popai-presentations
description: Create presentations (PPT) using PopAI API. Use when asked to create slides, presentations, decks, or PPT content via PopAI. Supports uploading reference files (pptx/pdf/docx/images). Also supports multi-round modifications to an existing PPT.
metadata: { "openclaw": { "emoji": "📊", "requires": { "bins": ["python3"], "env":["POPAI_API_KEY"]},"primaryEnv":"POPAI_API_KEY" } }
---

# PopAI PPT Skill

Create presentations programmatically via PopAI's API. Supports optional file uploads as reference material or templates. After initial generation, you can send follow-up modification instructions using the same channel ID.

## Setup

1. Get API key from https://www.popai.pro
2. Store in environment: `export POPAI_API_KEY=...`

## Scripts
- `generate_ppt.py` - Generate PPT via PopAI API (upload files → create channel → SSE stream → get pptx); also supports multi-round modification via `--channel-id`

## Usage Examples

```bash
# Generate PPT from topic only
python3 generate_ppt.py --query "AI Development Trends Report"

# With reference files (max 5)
python3 generate_ppt.py --query "Tesla Earnings PPT" --file data.pdf chart.png

# With a PPT template file (applied as layout template)
python3 generate_ppt.py --query "Tesla Annual Report" --tpl template.pptx

# With both template and reference files
python3 generate_ppt.py --query "Tesla Annual Report" --tpl template.pptx --file data.pdf chart.png

# Multi-round modification: modify an existing PPT (template cannot be changed)
python3 generate_ppt.py --channel-id "CHANNEL_ID" --query "Add a competitive analysis slide and make the color scheme blue"

# Multi-round modification with additional reference files
python3 generate_ppt.py --channel-id "CHANNEL_ID" --query "Update the financial data with this new report" --file new_data.pdf
```

## Agent Steps

### Initial Generation

1. Get PPT topic from user
2. If user provides local files, pass as `--file` (reference, max 5) and/or `--tpl` (PPT template for layout)
3. Run script (timeout: 600000):
   ```bash
   POPAI_API_KEY="$POPAI_API_KEY" python3 generate_ppt.py --query "TOPIC" [--file FILE1 FILE2 ...] [--tpl TEMPLATE.pptx]
   ```
   Tell user: "Generating your PPT, estimated 5 minutes..."
4. Parse stdout JSON lines, present final results to user:
   - Show `summary` text (from `NODE_END` event) as the generation summary
   - Show `pptx_url` as the download link: "Download PPT: <pptx_url>"
   - Show `web_url` as the site link: "View/Edit online: <web_url>"
5. **Save the `channel_id`** from `web_url` (last path segment of `https://www.popai.pro/agentic-pptx/<channelId>`) for potential follow-up modifications

### Multi-Round Modification

Use when the user wants to revise or improve an already-generated PPT (e.g. "add a slide", "change the title", "use a darker theme").

**Rules:**
- **Required**: `--channel-id` (from previous generation) + `--query` (modification instruction)
- **Optional**: `--file` to supply new reference files for the revision
- **Not supported**: `--tpl` is ignored in modify mode — the original template cannot be changed

1. Confirm the `channel_id` from the previous generation (stored from `web_url`)
2. Get modification instruction from user
3. If user provides additional reference files, pass as `--file`
4. Run script (timeout: 600000):
   ```bash
   POPAI_API_KEY="$POPAI_API_KEY" python3 generate_ppt.py --channel-id "CHANNEL_ID" --query "MODIFICATION_INSTRUCTION" [--file FILE1 ...]
   ```
   Tell user: "Applying your modifications, estimated 3-5 minutes..."
5. Parse and present results the same way as initial generation (new `pptx_url` and `web_url`)

## Output

**Event types (stdout, one JSON per line):**
```json
{"type": "task", "id": "1", "content": "Search for Tesla latest earnings data", "status": "progressing"}
{"type": "search", "action": "Web Searching", "results": [{"title": "...", "url": "...", "snippet": "...", "date": "..."}]}
{"type": "tool_result", "event": "TOOL_CALLS-xxx", "action": "...", "result": "..."}
{"type": "summary", "text": "Tesla earnings PPT has been created..."}
{"type": "stream_end"}
```

**Final result (`is_end: true`):**
```json
{
  "type": "pptx_ready",
  "is_end": true,
  "pptx_url": "https://popai-file-boe.s3-accelerate.amazonaws.com/.../xxx.pptx",
  "file_name": "xxx.pptx",
  "preview_images": ["https://...0.jpeg"],
  "preview_count": 10,
  "web_url": "https://www.popai.pro/agentic-pptx/<channelId>"
}
```

- `pptx_url`: Download link for the .pptx file
- `web_url`: PopAI site link for online viewing and editing
- `summary`: Final summary text from the `NODE_END` event, shown to the user as a generation recap

## Technical Notes

- **Streaming**: SSE stream; `TOOL_CALLS-pptx` event contains final .pptx download URL; `last:true` marks stream end
- **File Upload**: Presigned POST to S3 via `getPresignedPost`, supports any file type
- **Timeout**: Generation takes 3-5 minutes
- **Channel ID**: Extractable from `web_url` — last path segment of `https://www.popai.pro/agentic-pptx/<channelId>`
- **Multi-round**: Calls `send_generate` directly with existing `channel_id`; `tpl_info` is never passed (template is fixed after channel creation)
