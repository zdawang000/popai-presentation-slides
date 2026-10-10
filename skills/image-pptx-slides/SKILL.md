---
name: image-pptx-slides
description: 使用 PopAI beta 环境的图片模型与 PowerPoint SDK 生成可编辑的 PowerPoint (.pptx) 文件。当用户要求通过图片模型制作可编辑 PPT，或明确指定 image-pptx-slides、beta.01ww.org/agentic-pptx 时使用。支持首轮生成、参考文件上传及 PPTX 下载。
metadata: { "openclaw": { "emoji": "📽️", "requires": { "bins": ["python3"], "env": ["POPAI_ACCESS_TOKEN"] }, "primaryEnv": "POPAI_ACCESS_TOKEN" } }
---

# Image PPTX Slides（内测版）

使用图片模型设计幻灯片，再通过服务端 PowerPoint SDK 构建可编辑的 PPTX。文字等内容以 PowerPoint 元素组织；插画、背景等仍可能保留为图片，不承诺每个视觉元素都能单独编辑。

网页入口：`https://beta.01ww.org/agentic-pptx/<channelId>`。
API 环境固定为 `https://api.01ww.org`。仅支持首轮生成和下载，每次生成都创建新会话。

## 环境准备

需要 Python 3、`requests`，以及有内测权限的 beta 账号 Access Token。

```bash
python3 -m pip install requests
export POPAI_ACCESS_TOKEN="<beta_access_token>"
```

从 beta 账号获取令牌；不要假定生产环境令牌可用于 beta。通过环境变量传入令牌，不把它写入 skill、脚本或输出日志。

脚本为本 skill 目录中的 `generate_ppt.py`。下面的命令在该目录执行；从其他目录调用时使用脚本的绝对路径。

## 首轮生成

将用户的主题、受众、页数、语言和视觉要求合并成一条清晰的 `--query`。保留用户已给出的要求；常规选择可以直接补全，不必为调用接口重复确认。网页链接直接写入 query；本地参考材料通过 `--file` 上传。

```bash
# 生成并提供下载地址
python3 generate_ppt.py --query "为一年级小朋友制作6页中文PPT，介绍加减乘除。句子短，例子直观，采用明亮的儿童插画风格。"

# 生成并下载到本地
python3 generate_ppt.py --query "制作6页中文产品介绍，面向潜在客户。" \
  --output "/absolute/path/产品介绍.pptx"

# 使用参考文件
python3 generate_ppt.py --query "根据附件制作8页中文汇报，突出主要发现。" \
  --file "/absolute/path/报告.pdf" "/absolute/path/数据.xlsx" \
  --output "/absolute/path/汇报.pptx"
```

### 参数及作用

| 参数 | 作用与约束 |
| --- | --- |
| `--query` / `-q` | 首轮生成需求，必须为非空文本。页数、语言、风格和参考网页 URL 都写在这里；这些要求由服务端 agent 处理。与 `--download-url` 互斥。 |
| `--file` / `-f` | 可选，本地参考文件路径，单次最多 5 个，如 PDF、DOCX、PPTX、图片、表格。上传后用于本次生成的内容参考；不将 PPTX 文件自动应用为版式模板。仅用于生成。 |
| `--output` / `-o` | 可选，本地 `.pptx` 保存路径。生成时省略此参数只返回下载地址；提供此参数则等待生成完成后下载。支持创建父目录，输出绝对路径。单独下载时必须提供。 |
| `--download-url` | 从已获得的 PPTX HTTP(S) 地址单独下载，不创建会话、不发起生成，也不需要 `POPAI_ACCESS_TOKEN`。必须同时提供 `--output`，不能与 `--query` 或 `--file` 混用。 |
| `--help` / `-h` | 显示参数帮助，不调用 API。 |

### 执行与完成判定

1. 检查 beta 令牌和参考文件，调用脚本。为长任务预留最多 20 分钟，并根据 stdout 的 JSON 行向用户报告有效进度。
2. 脚本上传材料，调用 `getChannel`（`templateId: "900012"`），随后调用 `/api/v1/chat/send`，读取 SSE。
3. `TOOL_CALLS-pptx`（或 `nodeId: "pptx"`）中的 `media[0].url` 是服务端 SDK 产出的 PPTX；`imgList` 是预览截图。直接使用 PPTX 地址下载，不能将截图重新打包作为可编辑文件交付。
4. 等待 `last: true` 且本次没有错误，再检查是否取得非空 PPTX 地址。只有最终 `pptx_ready` 且 `is_end: true` 才能报告成功；预览、工具调用及自然语言总结都不能单独证明完成。
5. 交付 `pptx_url` 和 beta `web_url`；如指定了 `--output`，同时交付 `local_path`。可补充 `summary`，但完成状态以脚本结果为准。

## 下载

生成时提供 `--output` 即可自动下载。若已取得地址，只需下载，不要重新生成：

```bash
python3 generate_ppt.py --download-url "https://example.com/generated.pptx" \
  --output "/absolute/path/演示文稿.pptx"
```

下载使用文件地址本身，不向文件服务器发送 API 令牌。脚本先保存到临时文件，检查 PPTX ZIP 完整性和必需的 PowerPoint 文件，再替换目标文件。该检查只验证文件结构，不验证渲染效果或所有元素的可编辑性。

生成成功但本地下载失败时，`export_result` 会保留 PPTX 地址；使用 `--download-url` 重试下载即可。

## 输出与异常处理

stdout 每行一个 JSON 对象。常见进度类型为 `channel`、`uploading`、`task`、`search`、`tool_result`、`summary`、`pptx_available` 和 `stream_end`。`pptx_available` 仅表示流中出现文件地址，仍须等待最终成功。

最终生成结果示例：

```json
{
  "type": "pptx_ready",
  "channel_id": "<channelId>",
  "pptx_url": "https://popai-file-boe.s3-accelerate.amazonaws.com/.../presentation.pptx",
  "file_name": "presentation.pptx",
  "preview_images": ["https://.../slide-1.jpeg"],
  "preview_count": 6,
  "summary": "演示文稿已生成。",
  "web_url": "https://beta.01ww.org/agentic-pptx/<channelId>",
  "local_path": "/absolute/path/演示文稿.pptx",
  "is_end": true
}
```

未指定 `--output` 时不包含 `local_path`；单独下载的 `download_ready` 返回 `pptx_url`、`local_path` 和 `is_end: true`。

- `error` 或非零退出码表示失败，不报告完成。
- 流未正常结束、超时或服务端报错时，保留已输出的 `channel_id` 和网页地址供用户查看。不要自动重发生成请求，避免重复生成和计费。
- 若服务端要求补充回答，输出 `needs_input` 并提示用户打开对应 beta 网页处理。本 skill 不发送后续消息。
