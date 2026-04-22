# Platform Web 能力对齐覆盖表

这份文档只回答一件事：`apps/platform-api` 已经暴露出来的正式控制面能力，`apps/platform-web` 到底哪些已经接上，哪些只是部分接上，哪些明确不应该进正式 UI。

目标不是炫技，而是避免后续继续出现“后端有接口，前端不知道谁在用；前端有页面，但没人知道是不是正式口径”的烂账。

## 1. 判定口径

- `已对齐`：正式后端能力已经有正式前端入口或正式业务消费
- `部分对齐`：后端能力已接一部分，但还存在明显治理缺口或嵌入式消费
- `故意不开放`：能力属于 internal / 工具性 / 基础设施口径，不进入正式 UI

## 2. 模块覆盖

| 后端模块 | 代表接口 | 前端状态 | 前端入口 / 消费位置 | 说明 |
| --- | --- | --- | --- | --- |
| `identity` | `session` / `me` / `password/change` | 已对齐 | 登录、资料、安全、鉴权 store | 登录态、刷新、个人资料、改密都已经接通 |
| `users` | `GET/POST/PATCH /api/users*` | 已对齐 | `UsersPage` / `UserCreatePage` / `UserDetailPage` | 用户列表、创建、详情、更新、所属项目都已消费 |
| `projects` | `GET/POST/DELETE /api/projects` | 已对齐 | `ProjectsPage` / `ProjectCreatePage` | 项目列表、创建、删除已接通；后端本身没有项目 metadata 更新接口 |
| `members` | `GET/PUT/DELETE /api/projects/{id}/members*` | 已对齐 | `ProjectMembersPage` / `ProjectDetailPage` | 项目成员查询、加人改角色、移除都已消费 |
| `service_accounts` | `GET/POST/PATCH /api/service-accounts*` | 已对齐 | `ServiceAccountsPage` | 账号列表、创建、编辑、发 token、撤销 token 已接通 |
| `announcements` | feed / list / create / update / delete / read | 已对齐 | `AnnouncementCenter` / `AnnouncementsPage` | 顶部公告中心和治理页都走正式接口 |
| `audit` | `GET /api/audit` | 已对齐 | `AuditPage` / Overview 概览卡 | 正式审计查询页已接通 |
| `assistants` | list / create / detail / update / delete / resync / schema | 已对齐 | `AssistantsPage` / `AssistantCreatePage` / `AssistantDetailPage` | 助手主链已完整接通，schema 接口用于表单编排 |
| `runtime_catalog` | models / tools / graphs + refresh | 已对齐 | `RuntimeModelsPage` / `RuntimeToolsPage` / `GraphsPage` / `RuntimePage` | 目录查询和刷新都已接通；三类 refresh 已统一回流到 operations 链路 |
| `runtime_policies` | models / tools / graphs overlay | 已对齐 | `RuntimePoliciesPage` | 项目级策略查询和编辑都已接通，并已补按钮级权限 gate |
| `operations` | list / detail / stream / bulk / artifact | 已对齐 | `OperationsPage` | 异步治理主链已接通，runtime refresh / assistant resync / testcase export 都统一回流 |
| `testcase` | overview / role / batches / documents / cases / export / preview / download | 部分对齐 | `TestcaseDocumentsPage` / `TestcaseCasesPage` / `TestcaseGeneratePage` | 文档、用例、导出、预览、下载、详情都已接；批次详情仍是嵌入式消费，没有单独一级治理页 |
| `_system` | probes / health / metrics / platform-config | 已对齐 | `SystemGovernancePage` / `PlatformConfigPage` | 平台配置与系统探针已有正式治理入口 |
| `runtime_gateway` public 子集 | thread list/detail/history/state, run stream/cancel | 已对齐 | `ChatPage` / `BaseChatTemplate` / `ThreadsPage` / `SqlAgentPage` | 正式工作台依赖的线程与运行主链已接通；assistant/chat 已统一使用 `context + config` runtime contract，前端不再保留 fake control-plane 抽象 |
| `runtime_gateway` advanced/internal | `info` / runs admin / crons / prune / copy / join* | 故意不开放 | 无正式导航入口 | 这些能力要么属于 internal，要么是 SDK / 运维工具口径，不应该直接进正式 UI |

## 3. 当前剩余缺口

### P0 级

- `testcase batch` 只有嵌入式详情消费，没有独立治理页
- `runtime_gateway` 的 public/internal 边界虽然已经在文档中冻结，但前端侧还需要继续保持“不因为接口存在就随手加入口”的纪律

### P1 级

- `service layer` 虽然已经切到正式命名，但还需要继续保持不新增 `legacy*` / `v2*` 过渡命名
- `TopContextBar` / `UserMenu` / 若干概览页已经在吃正式权限与项目上下文，后续新页必须复用同一套范式，不能回退成页面各自发挥

## 3.1 本轮已收口的前端硬规则

- assistant create / update 与 chat submit 共享同一份 runtime contract helper
- runtime business fields 只进入 `context`
- `config` 只保留执行控制
- `config.configurable` 只保留线程 / 平台 / 私有字段
- `services/platform/control-plane.ts` 已下线，前端不再保留 fake module-aware client / baseURL 抽象

## 4. 前端继续开发时的硬规则

- 如果后端接口属于 `public`，前端必须明确回答“正式入口在哪、权限是什么、审计结果在哪里看”
- 如果后端接口属于 `internal`，前端默认不加正式导航，不做业务承诺
- 页面不因为“接口现成”就直接开入口，必须先过权限、审计、上下文、空态、错态这几关
- `runtime_gateway` 相关新能力优先判断是否应该并入通用 chat 基座，而不是再复制一套工作台

## 5. 建议的后续收口顺序

1. 继续做 `service / client` 层正式命名收口，保持前端只存在一套正式口径
2. 评估 testcase 是否需要独立的 `batch` 治理页
3. 做一轮“页面动作 -> audit action -> operations 归口”复核，避免正式页里还藏着散装异步动作
