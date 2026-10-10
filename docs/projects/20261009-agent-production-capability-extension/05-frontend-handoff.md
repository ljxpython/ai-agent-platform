# 前端交接：Agent Run 失败通知与状态监控方案

> **状态：已完成技术评审与修订（2026-10-10）。**
> 本文档为平台前端实施唯一基准，已纠正旧版 DTO 脆断、全局状态管理混乱、去重漏报及路由覆盖风险。
> 接口、持久化与 Runtime 已由后端实现，GraphHarbor 双包已发布 `0.13.0.post44`；本轮前端落地任务为 [tasks.md](tasks.md) P4.1–P4.3。

GraphHarbor 的 webhook 发送与认证是 Server/后端职责，详情见 [官方边界核对](07-langgraph-server-boundary.md)。前端只对接平台受管 DTO，不直接消费原生 webhook 的 kwargs/values/error 正文，也不新增 callback secret 或签名配置。

---

## 1. 产品范围和挂载入口

本期包含两个展示入口，共用同一套底层 completion 事件：

1. **平台顶栏私有运行通知入口（Shell-level Notification Center）**：
   - **挂载位置**：`apps/platform-web/src/components/layout/TopContextBar.vue`，紧邻 `AnnouncementCenter.vue`。
   - **核心职责**：用户在其他页面或新会话中仍可感知自己发起的失败（error/timeout）。浏览器关闭后后端持久保留，下次登录拉取；不做系统推送/邮箱/第三方渠道。
   - **隔离与展示**：标注为“运行通知”，严格按 `actor + project` 隔离，不放入系统全局公告。
2. **历史 Run 的安全失败摘要（Chat History Diagnostics Summary）**：
   - **挂载位置**：`TrajectoryView.vue`（检查器 Inspector / 诊断摘要面板），`ChatSession.vue` 仅传递稳定 props，不承载复杂 completion 状态机。
   - **核心职责**：打开历史非运行态 Run 时惰性拉取 completion，展示脱敏后的安全失败原因及重试/模型切换入口。
   - **边界硬约束**：在线 messages/tools/interrupt/loading/error/lifecycle 继续由官方 SDK controller 持有。completion 仅作为历史辅助摘要和私有 Feed，**绝对禁止修改 turnState、消息列表、checkpoint、选中 Run 或预算计时**。已完成的回答绝不能因查询 completion 偶发 503 被改成 error。

---

## 2. 对接包与前置条件

交付包位于 `frontend-contract/`：
- [OpenAPI 规范](frontend-contract/openapi.json)
- [真实 Worker 响应样例](frontend-contract/real-responses.json)
- [HTTP 状态/错误矩阵](frontend-contract/http-matrix.json)

后端未启用时（`availability: "disabled"`）隐藏顶栏通知入口；未配置能力的历史 Run 返回 `unsupported`。UI 严禁塞模拟假数据冒充接通。开发与单测阶段必须优先使用契约 JSON fixtures 进行穷尽验证。

---

## 3. 请求约定

所有请求严格使用现有 `src/services/http/client.ts::platformHttpClient`，沿用当前 session、`x-project-id` 及 `x-request-id`；响应错误复用 `extractPlatformHttpError`。

| 接口 | 方法与参数 | 用途 |
| --- | --- | --- |
| `/api/langgraph/threads/{thread_id}/runs/{run_id}/completion` | `GET`，带 `x-project-id` | 精确历史 Run 摘要查询 |
| `/api/runtime/run-notifications` | `GET`，`limit=20, unread_only=true`（历史传 `false`），支持 `cursor` | 当前用户、当前项目失败 Feed |
| `/api/runtime/run-notifications/{event_id}/read` | `POST`，正文 `{}` | 当前用户幂等已读回执 |

---

## 4. DTO 与严格 Zod 规范

### 4.1 TypeScript 类型定义

```ts
export type TerminalStatus = "success" | "error" | "timeout" | "interrupted";

export type TerminalReason =
  | "completed"
  | "business_error"
  | "infrastructure_error"
  | "timeout"
  | "hitl_interrupt"
  | "cancel_requested"
  | "rollback"
  | "lease_expired";

export type SafeCompletion = {
  event_id: string;
  graph_id: string;
  status: TerminalStatus;
  reason: TerminalReason;
  reason_code: string | null;
  model_error_code: string | null;
  notification_code: string | null;
  occurred_at: string;
  can_mark_read: boolean;
  read_at: string | null;
};

export type CompletionResponse =
  | {
      version: 1;
      thread_id: string;
      run_id: string;
      availability: "available";
      completion: SafeCompletion;
      request_id: string;
    }
  | {
      version: 1;
      thread_id: string;
      run_id: string;
      availability: "pending" | "unsupported" | "expired";
      completion: null;
      request_id: string;
    };

export type RunNotification = SafeCompletion & {
  thread_id: string;
  run_id: string;
  received_at: string;
};

export type NotificationFeedResponse = {
  version: 1;
  availability: "available" | "disabled";
  items: RunNotification[];
  next_cursor: string | null;
  scan_limit_reached: boolean;
  request_id: string;
};

export type ReadReceiptResponse = {
  version: 1;
  event_id: string;
  read_at: string;
  request_id: string;
};
```

### 4.2 Zod 校验防御原则（防崩盘设计）

1. **`version` 字段防御性补齐**：OpenAPI 中 `version` 未声明在 `required` 中，Zod 必须声明为 `z.literal(1).default(1)`，防止后端序列化缺省引发崩溃。
2. **`status` 宽进严出**：在 DTO 校验层允许合法的四态 `TerminalStatus`，Feed 展示层进行过滤，仅渲染展示 `status === "error" || status === "timeout"` 的项；避免单条脏数据导致整个 Feed 列表解析失败抛错。
3. **安全码字典校验**：严格校验 `reason_code`、`model_error_code` 和 `notification_code` 是否在已冻结白名单内；若为未知结构则按 DTO 格式错误抛出，绝不将未知错误任意 fallback 为“运行失败”。
4. **配对完整性**：`pending | unsupported | expired` 时 `completion` 必须为 `null`；`disabled` 时 `items` 必须为空数组。

---

## 5. 状态管理与有界轮询（Pinia Store 架构）

为防止多个组件重复创建定时器引发轮询风暴，通知状态统一收敛至 **Pinia Store (`useRunNotificationsStore`)**：

- **单例状态维护**：
  - `items`: 响应式 Feed 列表（按 `event_id` 去重）。
  - `unreadCount`: 未读通知计数。
  - `availability`: 当前项目服务可用状态（`available | disabled | unavailable`）。
  - `nextCursor`: 历史分页游标。
  - `isPolling` & `isFetching`: 轮询状态与单飞互斥锁。
- **单飞轮询与指数退避机制**：
  - 严禁使用 `setInterval`。采用 **递归 `setTimeout` + `AbortController` + `isFetching` 单飞锁**。
  - 页面可见（`document.visibilityState === "visible"`）且已登录状态下，默认轮询间隔为 **15 秒**。
  - 当页面隐藏（`hidden`）时，立即暂停定时器；页面重新切回前台（`focus / visibilitychange`）时，执行即时补拉并重置下一次轮询。
  - 网络故障或 503 服务暂不可用时，采用有界指数退避策略（15s -> 30s -> 最长 60s），恢复 200 后自动重置为 15s。
- **分页与快照隔离**：
  - 轮询只刷新最新第一页快照（按 `received_at` 排序），不更新历史浏览游标。
  - 查看历史时使用独立的 `cursor` 向下加载，禁止将新第一页的游标拼接给旧历史列表。
- **乐观更新与失败回滚（Optimistic Read）**：
  - 用户点击“标为已读”时，Store 立即乐观更新对应条目的 `read_at` 并递减 `unreadCount`。
  - 若调用 `POST /read` 失败（如网络中断或 503），自动回滚该条目状态并恢复未读数，同时向用户弹出非阻塞失败提示。

---

## 6. 在线去重与跳转安全防护

### 6.1 去重与前后台抑制（借鉴 open-swe 经验）

- **双重前台抑制条件**：
  只有同时满足以下三个条件时，壳层才对新失败通知**抑制弹窗 Toast**（仅保留通知中心未读点标）：
  1. 当前页面处于前台可见状态：`document.visibilityState === "visible"`。
  2. 用户当前正在查看的会话与失败通知一致：`currentThreadId === notification.thread_id`。
  3. 聊天 SDK 或 SSE 已针对该 `run_id` 呈现了错误状态。
- **后台 Tab 不静音**：若浏览器处于后台标签页（`visibilityState === "hidden"`），即使用户停留在该会话，通知到达时仍需触发系统提示（如更新标题 `(1) 运行失败` 或触发通知），防止用户漏掉耗时任务失败。
- **已通知集合去重**：Store 维护内存 `notifiedRunIds: Set<string>`，在线已弹出的 Run 绝不重复弹窗。

### 6.2 跳转安全防护（禁止打断运行中会话）

- 当用户在通知中心点击某条失败通知的“查看会话”时：
  1. **检查当前会话执行状态**：若当前 `currentThreadId` 对应的 Agent 正在运行中（`isRunning === true`），**严禁直接执行路由跳转（router.push）**！
  2. **拦截与确认弹窗**：弹出确认对话框提示：“当前会话正在执行任务中，切换离开可能中断当前观察，是否确认切换？”或提供“新标签页打开”选项。
  3. **目标对账**：跳转后精准选中目标 `thread_id` 与 `run_id`，若目标已被删除或无权限，按既有 404/403 友好提示，严禁新建空 Thread。

---

## 7. 历史 Completion 查询与竞态控制（useRunCompletion）

在 `apps/platform-web/src/modules/chat/composables/useRunCompletion.ts` 中实现：

- **单飞与代数控制（Generation 防竞态）**：
  - 严格绑定 `actor + project + threadId + runId`。
  - 切换 Thread/Run、项目切换或组件卸载时：立即调用 `abortController.abort()`，递增 `epoch`，清理前次状态。
  - 响应返回时，必须校验 `epoch === currentEpoch && props.runId === targetRunId`，迟到的旧 Run 响应绝不污染新选中的 Run。
- **惰性查询约束**：
  - **严禁在 `isRunning === true` 时发起查询**！运行中的状态完全由 SDK SSE 驱动。
  - 仅在用户选中历史非运行态 Run、或切换到 Trajectory 检查面板时才惰性拉取。
- **Availability 响应处理**：
  - `available`：展示安全原因摘要及重试操作入口。
  - `pending`：延迟 2 秒最多单次重查；若仍为 pending，提供手动刷新按钮，禁止无限重试。
  - `unsupported / expired`：不展示故障 Banner，静默降级。
  - `503 / 网络错误`：保留当前已加载的安全数据，提示“服务暂不可用”，禁止把 Run 判定为 error。

---

## 8. 错误文案与推荐动作（细粒度优先策略）

严格遵循**细粒度优先**降级顺序解析文案：
$$\text{model\_error\_code} \longrightarrow \text{reason\_code} \longrightarrow \text{notification\_code} \longrightarrow \text{status 兜底}$$

| 匹配优先级与错误码 | 呈现短文案 | 推荐操作 |
| --- | --- | --- |
| **1. Model Error Codes** | | |
| `provider_rate_limited` | 模型服务暂时限流 | 稍后重试 |
| `provider_overloaded` | 模型服务繁忙 | 稍后重试 / 切换模型 |
| `provider_timeout` | 模型调用响应超时 | 重新运行 / 切换模型 |
| `context_too_long` | 会话上下文超出模型容量限制 | 建议开启新会话或整理上下文 |
| `provider_auth_failed` | 模型服务认证失败 | 联系管理员检查配置 |
| `provider_access_denied` | 模型服务访问被拒绝 | 联系管理员核对权限 |
| `model_unavailable` / `provider_unavailable` | 模型服务连接暂时中断 | 检查网络或切换模型 |
| **2. Reason Codes** | | |
| `runtime_run_timeout` | 本次运行已超过系统最大时限 | 重新运行 |
| `runtime.model.stream_interrupted` | 模型输出流中断，内容可能不完整 | 查看轨迹，按需重试 |
| `runtime.model.retry_budget_exceeded` | 模型重试次数耗尽，仍未能恢复 | 稍后重新运行 |
| `runtime.workspace.execution_outcome_unknown` | 工具执行结果无法确认 | 查看诊断详情（谨慎重试写操作） |
| `runtime_graph_step_limit_reached` | 运行步数达到系统上限 | 调整提示词或增加步数限制 |
| **3. Notification Codes (兜底)** | | |
| `run_timed_out` | 任务执行超时 | 重新运行 |
| `run_failed` / `runtime_execution_failed` | Agent 未能完成本次执行 | 查看诊断详情或联系管理员 |

*安全合规要求：认证失败不暴露具体 Provider 类型或 Key 细节；重试为显式用户动作，不自动盲目重复执行带副作用的 Tool。*

---

## 9. 模块规划与建议文件列表

| 路径（相对 `apps/platform-web`） | 类型 | 核心职责 |
| --- | --- | --- |
| `src/services/threads/completion.service.ts` | 新增 | 历史 completion HTTP 请求、Zod 严格解析、AbortSignal 与目标核验 |
| `src/services/run-notifications/run-notifications.service.ts` | 新增 | 通知 Feed 与 Read HTTP 请求、严格 Zod DTO 验证 |
| `src/stores/run-notifications.ts` | 新增 | **Pinia Store**：全局通知单例、15s 有界轮询、503 退避、未读数、乐观已读 |
| `src/modules/chat/completion/types.ts` & `presentation.ts` | 新增 | DTO 类型定义、错误码多级降级文案映射纯函数 |
| `src/modules/chat/composables/useRunCompletion.ts` | 新增 | 历史 Run 单飞查询、generation 防竞态、惰性加载 |
| `src/components/layout/RunNotificationCenter.vue` | 新增 | 顶栏下拉通知中心组件（复用 `useTopbarDropdown` 与视觉规范） |
| `src/components/layout/TopContextBar.vue` | 修改 | 在 `AnnouncementCenter` 旁挂载 `<RunNotificationCenter />` |
| `src/modules/chat/components/trajectory/TrajectoryView.vue` | 修改 | 接线历史 completion 失败摘要面板，透传 Run 状态 |
| `src/modules/chat/components/ChatSession.vue` | 修改 | 透传 `threadId/runId/isRunning`，处理跳转确认拦截 |
| `e2e/run-completion.spec.ts` | 新增 | Playwright 验收脚本（三视口截图与基础核心链路） |

---

## 10. 测试分层与验收清单

### 10.1 分层测试策略

1. **Vitest 单元与组件测试（第一防线，100% 覆盖）**：
   - 基于 `frontend-contract/real-responses.json` 与 `http-matrix.json` 覆盖所有 DTO 场景。
   - 测试 Store 的递归轮询、`hidden/visible` 切换、网络错误指数退避。
   - 测试乐观已读回执及其 503 失败回滚。
   - 测试 `useRunCompletion` 的 generation 取消与迟到响应拦截。
2. **Playwright E2E 测试（视觉与端到端防线）**：
   - 验证 1440px (桌面)、768px (平板)、390px (移动端) 三视口下的通知下拉与排版。
   - 验证无权限、空列表、超长文案无重叠溢出。
   - 键盘 Tab 导航与无障碍（A11y）合规。

### 10.2 验收核对表

- [ ] `completion`、`run-notifications`、`read` 三个接口严格通过 Zod DTO 校验。
- [ ] 轮询使用 Pinia Store 全局单例管理，多页面无重复定时器，后台标签页自动休眠。
- [ ] 在线前台失败展示不重复弹 Toast，后台 Tab 失败有明显提示。
- [ ] 错误文案严格按 `model_error_code -> reason_code -> notification_code -> status` 细粒度降级。
- [ ] 运行中的会话点击通知跳转时受阻并弹出确认弹窗。
- [ ] 快速切换 Thread/Run 不发生旧响应污染新界面的竞态。
- [ ] 1440/768/390 三视口布局无遮挡无溢出，产出留存截图。
- [ ] Vitest、typecheck、lint、build 全部通过。
