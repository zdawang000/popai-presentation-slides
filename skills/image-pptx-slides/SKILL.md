---
name: image-pptx-slides
description: 使用 PopAI beta 的图片模型与 PowerPoint SDK 创建和修改可编辑 PPTX。用户要求通过图片模型制作 PPT，或指定 image-pptx-slides、image-pptx-skill、beta.01ww.org/ai-powerpoint 或 agentic-pptx 时使用。支持本地文件上传、同一会话多轮修改、回答澄清问题及 PPTX 下载。
metadata: { "openclaw": { "emoji": "📽️", "requires": { "bins": ["python3"], "env": ["POPAI_BETA_ACCESS_TOKEN"] }, "primaryEnv": "POPAI_BETA_ACCESS_TOKEN" } }
---

# Image PPTX Slides

通过 PopAI 图片模型设计幻灯片，再由服务端 PowerPoint SDK 构建可编辑 PPTX。文字等内容以 PowerPoint 元素组织；插画和背景仍可能是图片，不承诺每个视觉元素都能单独编辑。

- beta 首页：`https://beta.01ww.org/ai-powerpoint`
- 已有会话：`https://beta.01ww.org/agentic-pptx/<channelId>`
- API：`https://api.01ww.org`，新建会话使用 `templateId: "900021"`。

## 环境与入口

使用本目录的 `generate_ppt.py`；从其他目录调用时传脚本绝对路径。需要 Python 3、`requests` 和有 beta 权限的 `POPAI_BETA_ACCESS_TOKEN` 环境变量。缺少依赖时安装 `requests`。令牌仅从该变量读取，不回退到生产令牌，不写入脚本、skill 或日志。

根据任务选择：

- 新建 PPT：`--query`，省略 `--channel-id`。
- 修改已有 PPT、继续讨论或回答问题：`--channel-id` 加 `--query`，复用原会话。
- 本轮新增材料：同时传 `--files`；新建和后续轮次均支持。
- 只下载已有文件：`--download-url` 加 `--output`，不需要令牌。

保留用户的主题、受众、页数、语言、内容与视觉要求。后续修改应明确涉及哪些页、要改什么；不为了修改而新建会话。优先使用当前对话已经记录的 `channel_id` 或用户给出的会话 URL；有多个候选且不能判断时再询问。

## 新建与文件上传

```bash
python3 generate_ppt.py --query "制作6页中文产品介绍，面向潜在客户。" \
  --output "/absolute/path/产品介绍.pptx"

python3 generate_ppt.py --query "根据附件制作8页中文汇报，突出主要发现。" \
  --files "/absolute/path/说明.md" "/absolute/path/数据.xlsx" \
  --output "/absolute/path/汇报.pptx"
```

本地材料必须通过 `--files` 上传，query 中的本地路径或文件名不能让服务端读取文件。上传入口不限制扩展名，可传 PDF、DOCX、PPTX、图片、表格、音视频、Markdown 和代码文件；实际解析能力取决于服务端，不把上传成功当作内容已正确理解。脚本单次允许 1–5 个文件，支持混合格式和重复 `--files` 参数，含空格的路径须加引号。

文件上传后作为本轮 `fileUrls` 提交。说明每个附件的用途（内容来源、风格参考、Logo 等）；不要把作为参考上传的 PPTX 自动声称为已应用的母版模板。用户明确要求应用模板时，确认服务端返回的实际结果。

需要联网搜集的信息可写入 query 并附参考网页，交由 PopAI 的 `deep_research` 处理；这不能替代缺失的本地材料。

## 多轮修改与追加材料

```bash
python3 generate_ppt.py --channel-id "<channelId>" \
  --query "将第3页改成左右对比布局，保留数据；统一全稿标题字号。" \
  --output "/absolute/path/汇报-修订.pptx"

python3 generate_ppt.py --channel-id "<channelId>" \
  --query "根据新附件更新第5页数据，并补充一页结论。" \
  --files "/absolute/path/最新数据.xlsx" \
  --output "/absolute/path/汇报-更新.pptx"
```

指定 `--channel-id` 会直接调用 `/api/v1/chat/send`，不会再调用 `getChannel`。历史消息与工作中的 PPTX 由服务端会话维护；不必反复上传已提交材料。每次只附本轮新增或替换的文件，并在 query 中说明替换关系。

正常情况下，等上一轮完成再发下一轮；澄清回答是例外。每轮重新收集 PPTX 地址，不能将上一轮地址当作本轮修改结果。

## 澄清问题与连接管理

通过可返回进程会话 ID 的执行工具运行长任务，读取 JSON 行进度。脚本流处理预算为 20 分钟；持续跟踪进程并向用户报告有意义的变化。

当出现 `question` 且 `interactive: true`：

1. 读取 `content` 中的问题、选项和倒计时（若有）。答案已在用户要求中时直接据此回答，否则向用户提问。
2. 保持原生成进程及 SSE 连接运行，不要为了等待用户主动结束它。
3. 收到回答后，用第二个进程在同一 channel 提交：

   ```bash
   python3 generate_ppt.py --channel-id "<channelId>" \
     --query "面向投资人，中文，10页，采用简洁商务风。"
   ```

4. 回答请求可能仅返回 `turn_complete`；这表示该请求结束，不代表 PPT 已生成。继续读取原进程，文件可能从原连接返回。
5. 服务端可能在等待超时后自行继续。不要将超时解释为用户已回答；若原轮次已完成，用户迟到的回答应作为同一会话的后续修改处理。

若流正常结束但仍明确等待回答，脚本返回 `needs_input`，保留会话并在用户回答后续聊。若原连接意外中断，则先检查会话状态（可打开 beta 网页），不要自动重发整条生成请求。无法确认原任务状态时说明不确定性，避免重复生成或计费。

## 完成、下载与交付

stdout 每行一个 JSON 对象。`channel` 提供会话 ID 和链接；`uploading`、`task`、`search`、`tool_result`、`summary`、`question` 是进度。不要向用户逐条转发工具内部细节。

| 最终状态 | 含义与处理 |
| --- | --- |
| `pptx_ready` 且 `is_end: true` | 本轮正常结束并取得 PPTX 地址；指定 output 时也已完成本地下载和结构检查。 |
| `turn_complete` 且 `pptx_ready: false` | 本次请求正常结束但没有产出文件；可为讨论或回答确认，不能声称生成或修改成功。若用户要求文件，检查原连接或会话状态。 |
| `needs_input` | 需要用户回答，继续原会话，不当作生成失败或完成。 |
| `error` 或非零退出码 | 失败；保留 channel 和已有文件地址用于检查或重试下载。 |

`TOOL_CALLS-pptx`（或 `nodeId: "pptx"`）中的 `media[].url` 是 SDK 产出的文件，`imgList` 是预览。中间的 `pptx_available` 不代表成功：必须等待 `last: true` 且没有错误。不能将预览截图打包成 PPTX 交付为可编辑文件。

成功后交付本轮 `pptx_url`、`web_url`，以及存在时的 `local_path`，并保留 `channel_id` 供后续修改。没有 `--output` 时仅返回远程地址。用户要求本地文件时必须指定 output；文件保存在当前任务允许的交付目录。

```bash
python3 generate_ppt.py --download-url "https://example.com/generated.pptx" \
  --output "/absolute/path/演示文稿.pptx"
```

下载不会向文件服务器发送 API 令牌。脚本先下载临时文件，验证 ZIP 完整性及 PowerPoint 必需文件，再替换目标文件。这仅验证结构，不证明渲染效果或所有元素的可编辑性。生成成功但下载失败时，从 `export_result` 取地址单独重试下载，不重新生成。

`--query/-q` 必须非空；`--files/-f` 是本轮本地文件路径；`--output/-o` 必须以 `.pptx` 结尾。`--download-url` 与 query、channel-id、files 互斥且必须指定 output。`--help` 不访问 API。
