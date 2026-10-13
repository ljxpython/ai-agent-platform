# 项目成员知识上传：前端交接与实施规范（修正定稿版）

2026-10-12。针对原交接方案中的 5 项架构与交互缺陷（自然语言驱动不确定性、文件格式一刀切破坏普通聊天、卡片局部轮询内存泄漏、项目详情页缺乏 Tab 规划、后端严格 query 参数校验等）进行了彻底重构与修正。平台 API / Runtime 独立开发与契约验证已完成，本规范作为前端 F01–F03 唯一实施基准。

---

## 一、架构分层与模块边界

遵循单一职责（SRP）与关注点分离原则，严禁在现有巨石组件（如 1143 行的 `ToolResult.vue`）中无节制堆砌业务代码：

| 层级 / 模块 | 路径 | 职责与变更说明 |
| --- | --- | --- |
| **HTTP 服务层** | `services/knowledge/knowledge.service.ts`（新增） | 封装 `/api/projects/{projectId}/knowledge/*` 4 个 GET 接口。**核心要求**：严格清理 query 参数，严禁携带未知 query（如 `_t` 缓存戳、空字符串），避免触发后端的 400 `invalid_knowledge_query` 拦截。 |
| **状态追踪层** | `composables/useKnowledgeJobTracker.ts`（新增） | **全局单例**任务追踪器。集中维护活跃任务状态集合（Map），统一 1 个定时器调度（3–5 秒轮询），监听 `visibilitychange`（切后台暂停、恢复后指数退避），切项目立即清理，组件卸载不影响追踪。 |
| **输入门禁层** | `modules/chat/components/ChatComposer.vue`<br>`modules/chat/composables/useChatActions.ts` | 保持普通附件 16 种格式与 20MB 上限不变；仅对满足 TXT/MD、大小 <= 20MB 且当前环境允许的附件开放【加入项目知识库】勾选项；用户明确勾选后按规范装配意向指令。 |
| **工具回执层** | `modules/chat/components/KnowledgeSubmissionCard.vue`（新增）<br>`modules/chat/components/ToolResult.vue`（路由分发） | 将 `mcp_submit_project_knowledge_document` 与 `mcp_get_project_knowledge_ingest_job` 剥离为专用卡片，消费安全 DTO；订阅全局 Tracker 响应，展示六状态、reused、null job 与 searchable 标签。 |
| **项目面板层** | `modules/projects/pages/ProjectDetailPage.vue`<br>`modules/projects/components/ProjectKnowledgePanel.vue`（新增） | 在项目详情页引入 Tab 结构（`项目成员` / `项目知识库`），避免垂直无限堆叠；知识面板内提供【资料列表】与【任务历史】双视图，带独立分页与切项目竞态防护。 |

---

## 二、三个核心开发项（F01–F03）规范

### F01 明确共享、输入装配与细粒度门禁

#### 1. 普通附件与知识库门禁解耦（禁止破坏现有功能）
- **普通附件上传**：维持原有全部格式支持（PDF、DOCX、XLSX、PPTX、MD、TXT 等 16 种）与原有大小限制，走 `files.service.ts:uploadThreadFile` 生成 `RuntimeFileRef`。
- **知识库入库门禁**（复合条件）：
  - 权限：当前项目用户具备 `project.knowledge.upload`（admin / editor / executor 均具备）。
  - 服务可用性：`capabilities.upload_enabled === true`（若为 false，展示不可用原因 tooltip）。
  - 执行模式：非 `planMode`（规划模式下严禁提交入库）。
  - 智能体类型：当前 Assistant 必须为支持知识库的图（`dearflow_agent` 或 `showcase_demo`）。
  - 文件格式与大小：仅当附件为 `text/markdown` / `text/plain`（即 `.md`、`.txt`）且文件大小 <= `capabilities.max_file_bytes`（当前平台上限 20 MiB）时，才激活入库选项。
  - **交互表现**：附件卡片上展示【共享至项目知识库】复选框/切换项；若文件格式不支持（如 PDF），该复选框置灰并提示：*“当前知识库暂仅支持 TXT/MD 格式，该文件仅作为会话附件供当前聊天解析”*。严禁修改全局文件选择器的 `accept` 属性！

#### 2. 用户意向装配与消息发送
- 用户在附件卡片上勾选【共享至项目知识库】时：
  - 若输入框**为空**：前端自动填入规范意向文本：`请把本条消息的附件加入当前项目知识库`。
  - 若输入框**有自定义内容**（如“分析这篇文档并提取要点”）：前端在消息末尾自动附带明确意向指令：`\n\n【指令】请将本条消息所附的 {fileName} 加入当前项目知识库。`
- **多附件约束**：当前 MCP 入库工具一次仅接受一个 `file_ref`。若用户同时上传多个文件，仅允许勾选一个文件进行知识库共享，或对多文件逐个提示确认，禁止把多个附件同时标记入库导致大模型工具调用混乱。

---

### F02 提交回执、全局状态追踪与卡片呈现

#### 1. 全局轮询管理器（`useKnowledgeJobTracker.ts`）规范
严禁在 `ToolResult.vue` 或独立卡片组件内部私自创建 `setInterval`！所有轮询必须统一交由全局 Tracker 管理：
- **状态维护**：Tracker 维护 `activeJobs: Map<jobId, KnowledgeJob>` 和 `jobSubscribers: Map<jobId, Set<Callback>>`。
- **轮询策略**：
  - 存在处于非终态（`queued` / `parsing` / `indexing` / `publishing`）的任务时，启动单个全局定时器（3–5 秒轮询一次 `/api/projects/{projectId}/knowledge/jobs/{jobId}`）。
  - 达到终态（`ready` / `failed`）后，自动停止该任务的轮询，通知订阅者，并触发当前打开的知识库资料面板刷新。
  - `job_id === null` 的复用回执不发起单任务轮询。
- **页面生命周期与退避**：
  - 监听 `document.visibilityState`：页面切换到后台（hidden）立即暂停定时器；切回前台（visible）立即发起一次补查并恢复调度。
  - 轮询遭遇网络抖动或 5xx 错误时，执行指数退避（5s -> 10s -> 20s，上限 30s）；遭遇 401/403 则立即停止轮询并提示权限失效。
  - 项目切换（`projectId` 变化）或用户退出登录时，立即清空所有活跃任务与定时器。

#### 2. 回执卡组件（`KnowledgeSubmissionCard.vue`）状态映射矩阵
工具执行返回的 ToolMessage 成功时，其 `content`（JSON 文本）与 `artifact.structured_content` 提供安全 DTO。卡片根据状态机精准渲染，禁止显示伪造进度百分比：

| 状态（status） | 标签 / 色调 | 界面文案与行为 | 检索标识（searchable） |
| --- | --- | --- | --- |
| `queued` | 已受理 / 蓝色 | 任务已受理（编号：`job_id`），后台正在排队解析。用户可继续正常聊天。 | `false`（不可检索） |
| `parsing` | 正在解析 / 蓝色 | 正在提取与分块文档内容……（仅展示状态，无长请求） | `false`（不可检索） |
| `indexing` | 建立索引 / 蓝色 | 正在构建向量与知识图谱索引……（严禁伪造百分比进度条） | `false`（不可检索） |
| `publishing` | 正在发布 / 橙色 | 索引已生成，正在发布至当前项目检索视图…… | `false`（不可检索） |
| `ready` | 处理完成 / 绿色 | 资料入库成功！ | `searchable=true`：标绿显示“当前可检索”<br>`searchable=false`：标黄提示“当前版本暂不可检索” |
| `failed` | 处理失败 / 红色 | 显示安全错误原因（根据 `error_code` 映射友好提示）。 | 若 `searchable=true`：额外保留展示“已有历史资料仍可检索” |

**复用场景（`reused === true`）呈现**：
- `reused=true` 且非终态：标签显示“已复用处理中的任务”，展示原 `job_id`，不重复创建后台开销。
- `reused=true` 且 `status=ready` 且 `job_id !== null`：提示“该文档已入库，本次复用已有知识”。
- `reused=true` 且 `job_id === null`（历史迁移数据）：提示“已复用历史入库记录（无关联异步任务编号）”，不展示任务编号，不发起轮询。

---

### F03 项目详情页知识面板（`ProjectDetailPage.vue` 改造）

#### 1. 页面布局重构（引入 Tab 导航）
修改 `modules/projects/pages/ProjectDetailPage.vue`：
- 在顶部项目概览与统计卡片下方，增加 Tab 切换组件：
  - Tab 1: **项目成员**（原有的成员列表与操作保持完全不变）
  - Tab 2: **项目知识库**（挂载新增的 `ProjectKnowledgePanel.vue`）
- 在 `ProjectKnowledgePanel.vue` 内部，按 `read_enabled` 控制面板呈现：
  - 若 `read_enabled === false`：展示空状态或提示“当前项目未启用知识库检索能力”。
  - 若启用，提供两组视图切换或主从分区：
    1. **资料列表（Documents）**：调用 `GET /documents`，展示当前已发布可检索的资料（文件名、MIME 类型、文件大小、发布时间），支持按 20 条分页。
    2. **任务历史（Jobs）**：调用 `GET /jobs`，展示所有入库任务历史（任务 ID、文件名、状态标签、可查性状态、提交时间、失败原因），支持分页与手动单项刷新。

#### 2. 分页、竞态与防御性请求要求
- **本地维护分页状态**：服务端响应仅包含 `{ items: [...], total: number }`，前端组件必须本地严格维护 `limit`（默认 20，范围 1–100）和 `offset`（非负整数）。
- **竞态防御**：
  - 每次切换项目、切换 Tab 或发起刷新时，使用 `AbortController` 立即取消上一轮未完成的请求。
  - 请求响应返回时，严格比对响应所属的 `projectId` 与当前全局激活的 `activeProjectId`，若不一致直接丢弃，严禁把旧项目数据渲染到新项目页面。
- **安全过滤与 XSS 防护**：
  - `file_name` 必须以文本节点或转义形式渲染，严禁使用 `v-html` 渲染文件名，防止文件名包含 XSS 注入。
  - 绝不展示任何服务端内部凭据、HMAC Grant、内部 Thread/Run 标识等私密信息。

---

## 三、HTTP 契约与严格防 400 指南

接口统一前缀 `/api/projects/{project_id}/knowledge`，由 `platformHttpClient` 发送认证请求：

| 方法与路径 | 严格允许的 Query 参数 | 响应 DTO 结构 | 注意事项 |
| --- | --- | --- | --- |
| `GET /capabilities` | **严禁携带任何 Query 参数** | `KnowledgeCapabilities` | 后端 `_query` 严格限制 `allowed = set()`。任何多余参数（包括 `_t` 防缓存戳）都会直接触发 400 报错。 |
| `GET /documents` | 仅允许 `limit`（1–100）与 `offset`（>= 0） | `KnowledgeDocumentPage` | 严禁传递多余 query 或重复 key。 |
| `GET /jobs` | 仅允许 `limit`（1–100）与 `offset`（>= 0） | `KnowledgeJobPage` | 同上。 |
| `GET /jobs/{job_id}` | **严禁携带任何 Query 参数** | `KnowledgeJob` | `job_id` 必须严格符合 `kj_[a-f0-9]{32}` 正则，否则前端拦截不发请求。 |

### 前端 TypeScript DTO 定义
```ts
export type KnowledgeStatus = 'queued' | 'parsing' | 'indexing' | 'publishing' | 'ready' | 'failed';

export interface KnowledgeCapabilities {
  version: 1;
  read_enabled: boolean;
  upload_enabled: boolean;
  supported_mime_types: string[];
  max_file_bytes: number;
  disabled_reason: string | null;
}

export interface KnowledgeDocument {
  document_id: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  status: 'ready';
  searchable: true;
  published_at: string; // ISO8601
}

export interface KnowledgeDocumentPage {
  items: KnowledgeDocument[];
  total: number;
}

export interface KnowledgeJob {
  version: 1;
  job_id: string;
  document_id: string;
  file_name: string;
  status: KnowledgeStatus;
  searchable: boolean;
  error_code: string | null;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeJobPage {
  items: KnowledgeJob[];
  total: number;
}

export interface KnowledgeSubmission {
  version: 1;
  job_id: string | null;
  document_id: string;
  file_name: string;
  status: KnowledgeStatus;
  searchable: boolean;
  error_code: string | null;
  reused: boolean;
  created_at: string;
  updated_at: string;
}
```

---

## 四、安全错误码映射表（UI 展示标准）

当回执或任务处于 `failed` 状态时，`error_code` 必须映射为清晰易懂的友好提示，禁止直接把原始英文 code 丢给用户：

| 错误码（error_code） | 用户界面友好提示 | 建议交互行为 |
| --- | --- | --- |
| `knowledge_upload_disabled`<br>`knowledge_not_configured` | 当前项目尚未启用知识库入库服务。 | 关闭入库勾选，保留正常聊天对话。 |
| `knowledge_upload_denied`<br>`knowledge_authorization_denied` | 您在当前项目中没有上传知识库的权限。 | 提示联系项目管理员开通权限。 |
| `knowledge_unsupported_file_type`<br>`knowledge_unsupported_format` | 格式不支持，当前知识库仅支持 TXT 和 Markdown 文档。 | 引导用户选择合法格式。 |
| `knowledge_file_too_large` | 文件体积超过知识库入库上限（20 MB）。 | 提示压缩或裁剪文件。 |
| `knowledge_queue_full`<br>`knowledge_quota_exceeded` | 知识处理队列已满或项目配额不足，请稍后重试。 | 建议稍后重试。 |
| `knowledge_invalid_file_ref`<br>`knowledge_upload_expired` | 附件引用已失效或上传已过期，请重新上传文件。 | 引导重新选择附件。 |
| `knowledge_submission_unconfirmed` | 提交状态未能即时确认，请前往任务面板查看最新状态。 | 禁止自动重发，提供前往面板按钮。 |
| `knowledge_processing_*`<br>`knowledge_base_changed` | 后台解析与构建索引时出错。 | 提示后台处理异常；若此前有版本可查，提示旧版本仍可检索。 |
| 其他未知错误码 | 暂时无法获取入库状态，请稍后刷新查看。 | 降级处理，隐藏原始堆栈。 |

---

## 五、交付与验收清单（Checklist）

- [ ] **F01 门禁与意向确认**：
  - [ ] 验证普通附件（PDF/DOCX/图片）上传功能完全不受影响，只有符合 TXT/MD 且 <= 20MB 时才展示可勾选的入库入口。
  - [ ] 验证用户在 `planMode`、不支持的 Agent 图、或无 `project.knowledge.upload` 权限时，入库入口被正确隐藏或禁用。
  - [ ] 验证勾选入库后发送的消息，带有明确意向指令，大模型能稳定触发 `mcp_submit_project_knowledge_document`。
- [ ] **F02 回执与追踪管理**：
  - [ ] 验证新增独立的 `KnowledgeSubmissionCard.vue`，正确渲染受理（queued）、解析、索引、发布、完成（ready）与失败（failed）6 态。
  - [ ] 验证 `useKnowledgeJobTracker.ts` 全局调度，无重复定时器；切后台暂停，恢复前台后自动补查。
  - [ ] 验证 `reused=true` 与 `job_id=null` 极端情况下的界面展示与免轮询逻辑。
  - [ ] 验证工具失败（`status=error`）时错误码的友好中文映射。
- [ ] **F03 项目知识面板**：
  - [ ] 验证 `ProjectDetailPage.vue` 增加 Tab 分区，不破坏原有项目成员管理表格。
  - [ ] 验证 GET 4 个接口完全遵守后端 query 严格白名单，不带任何多余 query 参数，无 400 报错。
  - [ ] 验证资料列表与任务列表的分页功能正常。
  - [ ] 验证快速切换项目时，未完成的请求被正确中止，旧项目数据绝不串入新项目。
- [ ] **质量门禁**：
  - [ ] 运行 `pnpm run typecheck`（或 `vue-tsc`）、`pnpm run lint` 必须 0 报错。
  - [ ] 运行相关组件与 composable 单元测试全部通过。
