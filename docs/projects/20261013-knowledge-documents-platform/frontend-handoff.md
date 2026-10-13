# 前端交接：知识文档、可信图片与来源 v2

负责人：老王 & 前端团队。平台 API、Runtime 与 Ubuntu RAG 非前端联验已由后端专项完成。当前 worktree 是 `<worktree-root>`，复用现有 F01–F03 前端组件并彻底纠正旧方案漏洞，不另建独立管理后台。完整后端证据见 [verification.md](verification.md)，接口样本见 [fixtures/README.md](fixtures/README.md)。

## 要实现的用户行为

普通项目成员在聊天窗口上传附件，可主动勾选“共享至项目知识库”。经工具审批（若触发）后收到异步受理回执，即可继续正常聊天。后台解析索引成功并发布后在项目内共享，新旧资料累计可检索。默认不共享普通聊天附件。

- **支持格式**：TXT、MD、PDF、DOCX、PPTX、PNG、JPEG 共 7 类；
- **大小门禁（双层严格校验）**：
  - 文档最大上限取服务端 `capabilities.max_file_bytes`（默认 20MiB = 20,971,520 字节）；
  - 图片最大上限强制锁定为本地硬上限 **5MiB（5,242,880 字节）**，绝不被 capabilities 的 20MiB 冲垮；
- **格式限制与排除项**：
  - WebP 仅限普通聊天预览交互，严禁知识入库；
  - Agent 运行时临时生成的图表或输出图片（`/workspace/generated/`、`/workspace/charts/`、`/workspace/outputs/`）无原始本地文件，严禁勾选入库；
  - 音视频本期不开放。

---

## 逐文件开发清单

| 编号 | 涉及文件与入口 | 本次核心补齐与纠错点 | 严格验收标准 |
|---|---|---|---|
| **F01** | `apps/platform-web/src/modules/chat/components/ChatComposer.vue:getKnowledgeGate`<br>`apps/platform-web/src/modules/chat/components/ChatAttachmentPreview.vue` | 1. 彻底移除 TXT/MD 硬编码与“图片不支持”旧逻辑；<br>2. 支持 7 类格式，图片强制硬门禁 5MiB，文档校验 `max_file_bytes`；<br>3. 修复 `ChatAttachmentPreview.vue` 遗漏图片共享入口的问题，图片与文档均提供紧凑复选框；<br>4. capabilities 请求引入防竞态机制（AbortController / 序列号），切项目立即失效旧响应并重置勾选；<br>5. WebP、生成图片、规划模式、权限不足、上传关闭时精准禁用并提示明确原因。 | 7 类格式准确识别；PNG/JPEG 与文档均可正常勾选；超限/WebP/生成图严格禁用；快速切项目能力与勾选状态绝不串台。 |
| **F02** | `src/services/threads/images.service.ts:uploadThreadImage` 及其上传调用方 | 1. PUT 请求增加可选 `file_name` query 参数；<br>2. 文件名必须使用 `encodeURIComponent` 转义或 Axios params 传参，严防中文与特殊字符（空格、#、? 等）破坏路由；<br>3. 剪贴板截图或无名 Blob 严禁传 `undefined`/`null`/空字符串 query；<br>4. 后端返回五字段 `RuntimeImageRef`，前端**严禁自行拼接假 `file_name` 字段**，保持纯正契约。 | 图片上传成功且服务端私有收据记录原名；URL 编码无误；返回五字段通过 `isValidImageRef`；原图显示与下载不回归。 |
| **F03** | `src/utils/chat-content.ts:createRuntimeFileTextBlock/createRuntimeImageTextBlock`<br>`ChatComposer.vue` 发送意向装配 | 1. 上传成功后，将返回引用的完整 JSON 注入模型可见 `text`（文档六字段，图片五字段），保留 `extras`；<br>2. **关键边界**：仅在附件明确勾选 `shareToKnowledge: true` 时，才在 text 末尾追加知识库共享指令文本；普通附件**绝不追加**共享指令，严防模型误提交；<br>3. 严禁前端将图片伪造为六字段 FileRef。 | 模型请求正文包含完整引用 JSON；未勾选附件无入库指令；勾选附件带有标准 prompt 触发 submit；图片五字段与文档六字段结构严谨。 |
| **F04** | `src/modules/chat/components/KnowledgeSubmissionCard.vue`<br>`src/modules/chat/components/ToolResult.vue` | 1. **彻底干掉 `status || 'queued'` 弱智默认值**！无回执或执行中绝不宣称受理；<br>2. 严格四态分流：<br>   - 等待审批（`isAwaitingReview`）：展示“等待审批，尚未受理”，**绝不启动轮询**；<br>   - 执行中（`running` 无回执）：展示“执行中，尚未受理”，**绝不启动轮询**；<br>   - 已受理（`queued` 且具合法 `job_id`）：展示“已受理，等待处理，可以继续聊天”，启动轮询；<br>   - 终态（`ready` / `failed`）：停止轮询，仅当 `searchable=true` 时显示“可检索”；<br>3. 彻底删除“仅支持 TXT/MD”及“超出20MB上限”等过时错误文案，精准展示真实错误。 | 审批中绝无“已受理”假象；无合法 job 不发空轮询；ready/false 明确展示“暂不可查”；旧错误文案全部肃清。 |
| **F05** | `src/modules/chat/components/ToolResult.vue:evidenceSources`<br>来源渲染模板 | 1. **彻底修复致命去重 Bug**：证据去重改用 `source_id` 或 `chunk_id` 唯一标识，**严禁仅按 `title` 去重**，确保同文档多 chunk 不被吃掉；<br>2. 扩展 `EvidenceSourceItem` 类型，支持 v2 可选 `locator: {unit, start, end, block_type}`；<br>3. 格式化渲染：page 显示“第X页”/“第X–Y页”（异常跨页安全兜底）；slide 显示“第X张幻灯片”；unknown 显示“定位未知”；<br>4. 安全渲染：preview 中的 `asset:<opaque-id>` 纯文本显示，严禁渲染成超链接或请求。 | 同文档多来源完整保留；单页/跨页/幻灯片/未知定位精准美观；无页码时不瞎猜；无 XSS 或非法 URL 漏洞。 |
| **F06** | `src/services/knowledge/knowledge.service.ts`<br>`src/composables/useKnowledgeJobTracker.ts`<br>`src/modules/projects/components/ProjectKnowledgePanel.vue` | 1. **Tracker 状态单向流转防倒退**：已进入终态（ready/failed）的任务，严禁被后到的旧 queued 回执覆盖降级；<br>2. 401/403/404 停止该任务轮询，提示权限失效，绝不误报为“RAG 解析失败”；<br>3. 登录登出与切换项目时彻底重置 Tracker 映射与定时器，绝不串任务；<br>4. `ProjectKnowledgePanel.vue` 对齐状态机：`ready` 且 `searchable=false` 时显示琥珀色“已处理（暂不可查）”，仅 `searchable=true` 显示绿色“已就绪”；纠正错误描述中的硬编码数字。 | 跨项目零串台；状态机坚固不倒退；面板与卡片状态完全一致；权限失效优雅降级。 |

---

## 核心 API 契约与严格限制

客户端一律携带用户 Token 与 `x-project-id` 请求头。

| 方法 | 路径 | 关键参数与契约限制 |
|---|---|---|
| `GET` | `/api/projects/{project_id}/knowledge/capabilities` | **严禁任何 Query 参数**，违者直接 400。公开字段为 `read_enabled`。 |
| `GET` | `/api/projects/{project_id}/knowledge/documents` | 仅支持 `limit=1..100`、`offset>=0`。 |
| `GET` | `/api/projects/{project_id}/knowledge/jobs` | 分页读取任务，支持状态过滤（若后端开放）。 |
| `GET` | `/api/projects/{project_id}/knowledge/jobs/{job_id}` | 单任务查询，校验 `job_id` 格式：`kj_[0-9a-f]{32}`。 |
| `PUT` | `/api/langgraph/threads/{thread_id}/files/uploads/{sha256}?file_name=...` | 文档原件上传，`file_name` 必须 `encodeURIComponent`，返回六字段 FileRef。 |
| `PUT` | `/api/langgraph/threads/{thread_id}/images/uploads/{sha256}?file_name=...` | 图片原件上传，PNG/JPEG，`file_name` 可选且需编码，返回五字段 ImageRef。 |

**能力返回标准结构：**
```json
{
  "version": 1,
  "read_enabled": true,
  "upload_enabled": true,
  "supported_mime_types": [
    "text/plain",
    "text/markdown",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "image/png",
    "image/jpeg"
  ],
  "max_file_bytes": 20971520,
  "disabled_reason": null
}
```
*注：图片在前端强制使用 5,242,880（5MiB）本地上限，即使 `max_file_bytes` 为 20MiB。*

---

## 附件正文与模型 Prompt 规范

### 1. 结构化引用规范
- **文档（六字段 FileRef）**：`version, path, file_name, mime_type, size_bytes, sha256`
- **图片（五字段 ImageRef）**：`version, path, mime_type, size_bytes, sha256`

### 2. 模型可见正文装配规则

**（A）用户未勾选“共享至项目知识库”（普通聊天附件）：**
```text
[图片附件] report-chart.png
{"version":1,"path":"/workspace/uploads/abc123...456.png","mime_type":"image/png","size_bytes":45020,"sha256":"abc123...456"}
```
*(仅保留引用元数据，供模型理解附件，绝不注入入库指令)*

**（B）用户明确勾选“共享至项目知识库”：**
```text
[图片附件] report-chart.png
{"version":1,"path":"/workspace/uploads/abc123...456.png","mime_type":"image/png","size_bytes":45020,"sha256":"abc123...456"}
用户明确要求将此附件共享到当前项目知识库；通过 mcp_submit_project_knowledge_document 提交，收到回执后继续对话，不等待解析。
```
*(严格在末尾追加这一行标准意图指令)*

---

## 状态机与轮询生命周期

提交回执字段：`version, job_id, document_id, file_name, status, searchable, error_code, created_at, updated_at, reused`。

| 真实运行状态 | 页面文案展示 | 轮询与 Tracker 行为 |
|---|---|---|
| **工具调用中 / 审批中断 pending** | `执行中，尚未受理` / `等待审批，尚未受理` | **严禁轮询**，无合法 job_id 绝不发请求。 |
| **`queued`** | `已受理，等待处理，可以继续聊天` | 有合法 `job_id` 时启动有界退避轮询。 |
| **`parsing` / `indexing` / `publishing`** | `正在解析` / `正在索引` / `正在发布` | 退避轮询中（页面隐藏时挂起）。 |
| **`ready` 且 `searchable=true`** | `已入库，当前可检索`（绿色） | 停主动轮询，标记为已完成。 |
| **`ready` 且 `searchable=false`** | `已处理，当前版本暂不可查`（琥珀色） | 停主动轮询，提示版本未生效或回退。 |
| **`failed`** | `处理失败`，展示具体安全原因 | 停轮询，提示用户可按需重试。 |
| **`reused=true`** | 复用历史资料，按当前实际 status 展现 | 若 status 为 processing 继续轮询，ready 则停止。 |
| **`job_id=null, status=ready, reused=true`** | 已复用历史资料（秒级就绪） | **严禁轮询 null**。 |
| **401 / 403 / 404** | 会话过期 / 权限不足 / 任务不存在 | 立即停止该任务轮询，提示权限问题，不得宣称 RAG 解析挂掉。 |

---

## 来源 v2 Locator 规范与渲染防护

- **v1 回包**：`{source_id, document_id, chunk_id, title, kind, preview, truncated}`，无 locator。
- **v2 回包**：增加 `sources_version: 2`，每条来源携带 `locator: {unit, start, end, block_type}`。

| locator 数据样例 | 界面展示效果 | 容错兜底逻辑 |
|---|---|---|
| `{"unit":"page", "start":3, "end":3, "block_type":"text"}` | `第 3 页` | 单页展示 |
| `{"unit":"page", "start":3, "end":5, "block_type":"table"}` | `第 3–5 页 · 表格` | 跨页展示，若 `start > end` 或非正数则兜底为单页或未知 |
| `{"unit":"slide", "start":2, "end":2, "block_type":"image"}` | `第 2 张幻灯片` | 幻灯片展示 |
| `{"unit":"unknown", "start":null, "end":null, "block_type":"text"}` | `定位未知` | 不瞎猜页码 |
| **v1 无 locator** | 沿用标题与片段预览 | 向后兼容正常显示 |

**去重与安全规则：**
1. 列表去重 key：`item.source_id || item.chunk_id || item.content_hash || index`，**严禁按 title 粗暴去重**；
2. 文本中的 `asset:<opaque-id>` 纯文本渲染，绝不拼接为可点击链接。

---

## 验证与验收准则（老王硬核交付标准）

1. **类型检查与单元测试**：
   - 运行前端 `vue-tsc --noEmit`，必须 **0 错误 0 告警**；
   - 运行 Vitest 测试套件（`ChatComposer`、`KnowledgeSubmissionCard`、`useKnowledgeJobTracker`、`ToolResult`），全部 **100% 通过**；
2. **端到端自动化测试（Playwright + Chromium，真实模型）**：
   - 在当前 worktree 本地原生环境（Web: 25457, API: 24748, Runtime: 23512, Redis: 24741, MCP: 63311, Embedding: 65417）运行；
   - 使用真实模型（`deepseek-v4.1-flash`），严禁任何 mock 或 route.fulfill 欺骗；
   - 完整闭环覆盖：普通成员上传附件（PDF/PNG/JPEG）→ 勾选共享 → 触发审批/受理 → queued → ready → 另一成员检索召回新旧资料；
   - 边界验证覆盖：未勾选附件不共享、WebP/生成图不可共享、超限拦截、审批中不误报已受理、同 hash 复用、切项目不串任务、切页状态保持；
   - 运行过程保存完整截图与对账证据，供最终验收核查。
