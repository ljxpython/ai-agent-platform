# 07 Platform Web：图片上传、展示与审批体验

## 目标与状态

- **状态：** 规划中，等待人工评审；本文件不代表已实施。
- **目标：** 在 Showcase 对话中完成图片上传识别、文生图审批与展示、图表子 Agent 产物展示；其他 Agent 行为不变。
- **关键约束：** 浏览器不再把新图片附件 Base64 塞进消息；先上传线程 workspace，再发送 `ImageRef v1` 轻量引用。

## 1. 需要修改的文件

| 文件 | 改动 |
|---|---|
| `apps/platform-web/src/utils/chat-content.ts` | 生成/解析标准 text block 的 `extras.runtime_image`，保留非图片与旧历史兼容 |
| `apps/platform-web/src/modules/chat/composables/useChatAttachments.ts` | 图片校验、内容 hash、待上传状态、错误保留；Showcase 拒绝 GIF |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | 在线程创建后上传，在 send/queue/fork 三入口复用同一预处理 |
| `apps/platform-web/src/modules/chat/ChatSession.vue` | 连接上传状态、草稿保留和 Run 启动条件 |
| `apps/platform-web/src/modules/chat/transcript.ts` | 从消息 extras 和两种 artifact 层级归一提取 `ImageRef` |
| `apps/platform-web/src/modules/chat/components/MessageContent.vue` | 渲染用户上传和 Agent 生成图片 |
| `apps/platform-web/src/modules/chat/components/ToolResult.vue` | 展示普通工具 `artifact.runtime_images` |
| `apps/platform-web/src/modules/chat/components/SubagentCard.vue` | 展示 MCP `artifact.structured_content.runtime_images`，兼容父 task 路径 |
| `apps/platform-web/src/modules/chat/components/ApprovalPanel.vue` | 为文生图 interrupt 增加明确中文文案，不改服务端 decisions |
| `apps/platform-web/src/services/threads/images.service.ts` | 封装线程图片 PUT/GET；沿用现有认证 HTTP client |
| `apps/platform-web/src/modules/chat/components/ThreadImage.vue` | 认证下载、Blob URL 生命周期、预览/下载/错误状态 |

路径若与当前组件实际目录略有差异，以现有 import 归属为准；禁止为了对齐本文移动现有组件。

## 2. 浏览器侧类型

前端只定义一个与 04 对齐的 `RuntimeImageRef`，不再定义上传版、消息版和 artifact 版三套结构：

```ts
type RuntimeImageRef = {
  version: 1
  path: string
  mime_type: 'image/png' | 'image/jpeg' | 'image/webp'
  size_bytes: number
  sha256: string
}
```

解析函数必须校验版本、目录、MIME、大小和 64 位 hash。无效 artifact 作为普通工具文本展示，不发起图片请求。

## 3. 附件状态与上传流程

附件最少需要 `local File`、预览 URL、状态 `pending | hashing | uploading | uploaded | failed`、可选 `ImageRef` 和错误信息。状态放在现有附件模型中，不引入全局 store。

### 新线程发送

1. 用户点击发送后冻结本次提交的附件快照，输入框继续由现有发送状态管理。
2. 按当前 `useChatSession.send()` 逻辑先创建线程，拿到真实 `thread_id`。
3. 在浏览器用 `crypto.subtle.digest('SHA-256', file.arrayBuffer())` 计算内容 hash。
4. 调用 `PUT /runtime/threads/{thread_id}/images/uploads/{sha256}`，正文直接传 `File/Blob`，保留原 MIME。
5. 收到 `ImageRef v1` 后，将图片编码为标准 text block：可读文字放 `text`，引用放 `extras.runtime_image`。
6. 全部图片上传成功后才创建 Run；任一上传失败则不启动 Run，保留输入文本和全部附件，允许用户重试或删除失败项。

上传失败后已经成功落盘的内容无需回滚：文件名按 hash 幂等，下一次提交复用相同 PUT 即可。不要增加“上传会话”或清理 API。

### 已有线程与三个入口

抽取一个局部 `prepareMessageAttachments(threadId, content, attachments)`，供以下入口调用：

- 正常 `send()`；
- 运行中 `queueMessage()`；
- 快照分叉 `fork()` 后的新消息。

注意：平台已于 2026-09-12 统一为原生流式 `stream.submit(input, { threadId, forkFrom: checkpointId, ... })`，`fork` 是在**同一线程**内基于历史 checkpoint 分叉执行，不生成新 thread id。因此快照分叉补图时，附件同样上传到当前 `threadId` 的 workspace 下；原历史中已有的 `/workspace/...` 文件在当前线程工作区依然有效，无需跨线程复制。纯文本和非图片附件继续走现有逻辑。

### 文件限制

- 沿用现有单文件 5 MiB、最多 8 个、合计 20 MiB 的 UI 限制，并与服务端上限取更小值。
- Showcase 新链路支持 JPEG、PNG、WEBP。
- GIF 在 Showcase 提交前明确提示“不支持动态 GIF，请转换为 PNG/JPEG/WEBP”；不修改其他 Agent 既有附件策略。
- 客户端 MIME/扩展名检查只为即时反馈，Platform API 与 Runtime 必须再次校验。

## 4. 消息内容

新图片消息采用 LangChain 标准 text block 和 `extras.runtime_image`：

```json
{
  "type": "text",
  "text": "[图片附件] 示例.png\n/workspace/uploads/<sha256>.png",
  "extras": {
    "runtime_image": {
      "version": 1,
      "path": "/workspace/uploads/<sha256>.png",
      "mime_type": "image/png",
      "size_bytes": 12345,
      "sha256": "<sha256>"
    }
  }
}
```

路径文本用于不理解 extras 的客户端降级展示，不作为可信图片源。新消息不得含 Data URL 或 Base64。旧 checkpoint 中已有 Data URL 的消息继续按当前逻辑只读显示，不执行批量迁移。

## 5. 认证图片组件

`ThreadImage.vue` 接受 `threadId`、`RuntimeImageRef` 和可选 alt 文本：

1. 通过 `images.service.ts` 和现有认证 client 请求 GET，响应类型为 Blob。
2. 用 `URL.createObjectURL(blob)` 赋给 `<img>`，禁止把 `/workspace/...` 直接放进 `src`。
3. ref 变化、线程切换、组件卸载和重试前调用 `URL.revokeObjectURL`。
4. 固定预览区域的宽高约束，提供加载 skeleton，避免加载后撑动消息布局。
5. 成功时支持点击预览和下载；下载文件名从可信 `path` basename 派生，不采用响应中的任意文件名。
6. 403 显示“无权访问此图片”，404 显示“图片已不存在”，网络失败显示重试按钮；错误时仍显示 alt/路径摘要。

第一版不实现缩略图接口、Range、浏览器持久缓存或全局 Blob 缓存。单个组件实例持有一个 Blob URL 已足够。

## 6. 产物解析与展示

`transcript.ts` 提供一个归一提取函数，按以下来源收集且用 `path + sha256` 去重：

1. 消息 block 的 `extras.runtime_image`；
2. 普通工具结果 `artifact.runtime_images`；
3. MCP 结果 `artifact.structured_content.runtime_images`。

普通图片工具在 `ToolResult.vue` 中展示。图表 MCP 在 `SubagentCard.vue` 中展示；实时 task/subgraph 有 artifact 时直接解析，刷新恢复后若子图详情缺失，使用正则表达式 `/\/workspace\/charts\/[a-f0-9]{32}\.(png|jpg|webp)/` 严格匹配父 `task` 工具返回文本，识别同一产物并构建弱引用展示。不能假设刷新后 LangGraph 仍返回完整子图事件。

AntV 原始文本 URL 只作为调试文字；有 `runtime_images` 时必须优先使用受认证的线程图片，不让浏览器直接访问外域 URL。

## 7. 文生图审批

复用现有真实 interrupt/approval 协议。`ApprovalPanel.vue` 只增加按工具名匹配的中文展示：

- 标题：“生成图片需要确认”；
- 摘要展示 prompt、尺寸等服务端已提供且可安全展示的参数；
- 说明批准后会调用外部图片模型并写入当前线程 workspace。

按钮集合和提交值严格来自服务端 `allowed_decisions`。前端不得自行增加“始终允许”、绕过审批或缓存本次批准。拒绝后按现有 interrupt 恢复链路继续，界面显示拒绝结果且不出现图片。

## 8. 实施任务

- [ ] **W1 类型与 service：** 定义 `RuntimeImageRef` 校验器；实现 raw PUT 和 Blob GET，测试请求体不是 JSON/Base64。
- [ ] **W2 附件预处理：** 加入 hash、上传状态和 Showcase GIF 拒绝；保持现有大小/数量限制。
- [ ] **W3 会话接入：** 将 `prepareMessageAttachments` 接入 send/queue/fork；新线程严格按“创建 -> 上传 -> Run”。
- [ ] **W4 消息契约：** 生成 `extras.runtime_image`；验证 SDK 请求内无 Base64，旧历史仍可显示。
- [ ] **W5 图片展示：** 实现 `ThreadImage`、Blob URL 释放、预览、下载和错误状态。
- [ ] **W6 工具与子 Agent：** 解析两个 artifact 层级，支持父 task 恢复路径和去重。
- [ ] **W7 审批与回归：** 增加文生图文案；运行组件测试、lint、类型检查及 08 的 Playwright 场景。

依赖顺序：`W1 -> W2 -> W3 -> W4`；`W5` 可在 W1 后实施；`W6` 依赖 Runtime artifact 契约；`W7` 最后收口。

## 9. 组件与流程验收

| 场景 | 预期 |
|---|---|
| 新线程带 PNG 发送 | 先创建线程、再 PUT、最后 Run；消息只有轻量引用 |
| 上传失败 | 不启动 Run，文本和附件仍可编辑、重试 |
| 运行中补图 | PUT 完成后入队，队列 payload 小于限制且无 Base64 |
| 快照分叉补图 | 流式 forkFrom 时附件正常上传至当前线程工作区，提交后在分叉 run 中正常识别 |
| GIF 提交 Showcase | 本地阻止并给转换提示；其他 Agent 不受影响 |
| 图片识别 | 不出现审批；回复能引用上传图片内容 |
| 文生图批准/拒绝 | 每次均出现服务端审批；批准显示图片，拒绝不调用模型 |
| 图表子 Agent | 卡片内显示 workspace 图表；刷新后仍可从父 task 恢复 |
| 切换线程/卸载 | 所有已创建 Blob URL 被 revoke，无旧图串线 |
| 403/404/网络失败 | 分别显示明确状态，允许适当重试，不泄露内部响应 |

完成条件：W1—W7 完成，前端单测、类型检查、lint 通过，并完成 08 所列桌面与移动端真实浏览器 E2E。
