---
name: image-pptx-slides
description: 使用 PopAI beta 的图片模型与 PowerPoint SDK 创建和修改可编辑 PPTX。用户要求通过图片模型制作 PPT，或指定 image-pptx-slides、image-pptx-skill、beta.01ww.org/ai-powerpoint 或 agentic-pptx 时使用。支持本地文件上传、同一会话多轮修改、回答澄清问题及通过页面 Download 对应接口导出最终 PPTX。
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
- 下载最终文件：运行 `--download --channel-id <channelId> --output /absolute/path/file.pptx`，调用顶部 Download 对应的导出接口，不使用 SSE 原始文件地址。新建或修改时也可传 `--output` 自动导出。

保留用户的主题、受众、页数、语言、内容与视觉要求。后续修改应明确涉及哪些页、要改什么；不为了修改而新建会话。优先使用当前对话已经记录的 `channel_id` 或用户给出的会话 URL；有多个候选且不能判断时再询问。

## 新建与文件上传

```bash
python3 generate_ppt.py --query "制作6页中文产品介绍，面向潜在客户。"

python3 generate_ppt.py --query "根据附件制作8页中文汇报，突出主要发现。" \
  --files "/absolute/path/说明.md" "/absolute/path/数据.xlsx"
```

本地材料必须通过 `--files` 上传，query 中的本地路径或文件名不能让服务端读取文件。上传入口不限制扩展名，可传 PDF、DOCX、PPTX、图片、表格、音视频、Markdown 和代码文件；实际解析能力取决于服务端，不把上传成功当作内容已正确理解。脚本单次允许 1–5 个文件，支持混合格式和重复 `--files` 参数，含空格的路径须加引号。

文件上传后作为本轮 `fileUrls` 提交。说明每个附件的用途（内容来源、风格参考、Logo 等）；不要把作为参考上传的 PPTX 自动声称为已应用的母版模板。用户明确要求应用模板时，确认服务端返回的实际结果。

需要联网搜集的信息可写入 query 并附参考网页，交由 PopAI 的 `deep_research` 处理；这不能替代缺失的本地材料。

## 多轮修改与追加材料

```bash
python3 generate_ppt.py --channel-id "<channelId>" \
  --query "将第3页改成左右对比布局，保留数据；统一全稿标题字号。"

python3 generate_ppt.py --channel-id "<channelId>" \
  --query "根据新附件更新第5页数据，并补充一页结论。" \
  --files "/absolute/path/最新数据.xlsx"
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

最终 PPTX 必须经过页面顶部 Download 对应的后端导出流程，不能直接下载 SSE 中的 `raw_pptx_url` 作为成品。优先由本 skill 脚本完成，不需要先打开浏览器。

```bash
# 下载已有会话，不创建会话或发送生成消息
python3 generate_ppt.py --download --channel-id "<channelId>" \
  --output "/absolute/path/演示文稿.pptx"

# 生成或修改完成后自动导出
python3 generate_ppt.py --channel-id "<channelId>" \
  --query "更新第3页数据" --output "/absolute/path/修订版.pptx"
```

脚本使用 beta 令牌调用 `POST https://api.01ww.org/api/v1/ppt/editor/download?channelId=<channelId>`，读取响应 `data.url`，再下载该文件；文件下载请求不携带 API 令牌。这是编辑器顶部 Download 对应的接口，会尝试保存当前编辑、嵌入字体并返回导出地址。不要猜测其他导出接口，也不要绕过账号权限或使用原始文件作为失败回退。

下载先写临时文件，HTTP 下载完成后保存到 output。不检查文件完整性或字体嵌入记录，字体处理由服务端导出流程负责。

| 状态 | 含义与处理 |
| --- | --- |
| `download_ready` 且 `is_end: true` | 已通过导出接口完成下载；交付 `local_path` 和 `web_url`。 |
| `export_required` | 生成已结束但未指定 output；再运行 download 模式完成交付。 |
| `turn_complete` | 请求结束但未产出文件；可为讨论或回答确认，不能声称文件已生成。 |
| `needs_input` | 需要用户回答，继续原会话。 |
| `error` 或非零退出码 | 失败；保留会话信息。导出失败只重试 download，不重发生成消息。 |

中间的 `raw_pptx_available` 不代表生成或下载完成。须等待流的 `last: true` 且没有错误，然后经过导出接口。`imgList` 是预览，不能将截图打包成可编辑文件交付。保留 `channel_id` 供多轮修改使用。

只有接口确实无法完成且需要诊断时才打开会话页面，尝试顶部 Download（Version history 旁，不是嵌入编辑器 File 菜单）。遇到认证或权限问题，报告具体错误并请求所需登录或令牌修复，不以直链下载代替。

`--query/-q` 和 `--download` 互斥。download 模式必须同时提供 `--channel-id` 和 `.pptx` 后缀的 `--output/-o`，不能传 files。query 模式可用 `--files/-f` 添加本轮附件，可选 output 自动导出；澄清或无文件回复不会触发导出。`--download-url` 不支持，避免绕过字体处理。`--help` 不访问 API。
