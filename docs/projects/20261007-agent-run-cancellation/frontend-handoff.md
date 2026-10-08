# 前端交接：会话停止与状态报告

> **负责人：** 前端开发团队（由老王架构审查与升级）。**交付日期：** 2026-10-08。
> **交付状态：** 后端、Runtime 与 GraphHarbor 引擎源码及 16 条包版/Docker 验收已完成；本文档已修正前版契约缺陷与状态机漏洞，升级为**工业级前端实施标准**。前端方案确定后即刻实施。
> **联调门禁：** 仓库 Runtime 当前锁正式 post41。唯一 post43 候选四产物、冷安装、临时锁接入与 7 条恢复已通过；真实联合验收需配套 API/Runtime/Worker 及迁移 011/0002 环境。前端可先基于 Mock/Fixture 闭环契约与状态机。见 [发布接入清单](release-handoff.md) 与 [验证记录](verification.md)。

事实来源：`apps/platform-api/src/platform_api/modules/runtime_gateway/application/run_control.py` 的 DTO、`presentation/http.py` 的三个路由、`scripts/verify_thread_stop.py` 的真实验收。后端已完成授权、幂等、后台恢复、固定目标、FIFO/inbox 收敛、安全报告和审计。

---

## 1. 核心需求与职责边界

当前 Stop 按钮和入口已存在：`ChatSession.vue::handleStop()` -> `useChatSession.ts::stop()` -> `session.service.ts::cancel()`。本次改动需要将单 Run 取消升级为**会话级（Thread）停止控制流程**，提供精确的状态反馈与确定性报告展示：

1. **会话级原子停止**：运行中点击 Stop，向后端发起停止请求，取消该 Thread 当时已接受的所有运行中及排队待执行 Run（含 inbox 消息）。
2. **状态机全生命周期反馈**：展示提交中（submitting）、停止中（stopping）、已停止（stopped）、无活动任务（no_active_run）、结果未确认（confirmation_unavailable）以及失败拒绝（rejected）。
3. **解耦状态设计，杜绝单布尔值**：彻底废弃单一 `cancelling = ref(false)`。将控制动作（Stop Action）与 SDK Run 执行生命周期解耦，防止新 Run 启动与旧 Stop 发生死锁或状态冲刷。
4. **刷新、切页、多标签与断网恢复**：基于不可变 Scope 与 `localStorage` 持久化未决动作，支持同客户端 unknown 原 key 重试对账与多端拉取同一 stop_request。
5. **队列与草稿安全协同**：停止确认后仅刷新服务端队列（`refresh()`），**严禁前端私自调用 `queue.clear()`**；保留本地 composer 草稿与提交未知的消息。
6. **确定性停止报告展示**：在反馈区（Banner）与抽屉（Inspector）展示报告，严格不进入 AIMessage 流水线，不触发后续推荐问题（suggestions）或自动审批。

> ⚠️ **边界守则**：普通文本“停一下”不作为控制命令解析；独立终端（PTY）和后台 detached 任务不在会话 Stop 控制范围。

---

## 2. 代码落点与模块解耦设计

代码均位于 `apps/platform-web/` 目录下。为保持 Clean Architecture 架构解耦，**严禁将几百行停止逻辑塞死在 `useChatSession.ts` 中**，必须抽取专用领域模块：

| 模块 / 文件 | 类型 | 职责与具体工作 |
|---|---|---|
| `src/services/threads/session.service.ts` | Service | 接入 `stopThread`、`getStopRequest`、`listStopRequests`；严格限制 Headers 与 Body；保留原单 Run `cancel(threadId, runId)` |
| `src/modules/chat/stop/types.ts` | DTO / Zod | 基于 Zod 定义 `StopRequest`、`StopReport` 等 Schema 与类型推导；严格校验成果路径正则与字段白名单 |
| `src/modules/chat/composables/useThreadStopControl.ts` | Composable (核心) | 封装停止状态机、不可变动作快照、`localStorage` 恢复、单飞保护轮询、45s 超时截断、`confirmation_unavailable` 降频与手动重试、Scope/Generation 隔离 |
| `src/modules/chat/composables/useChatSession.ts` | Composable | 接入 `useThreadStopControl`；桥接 `handleStop` 与响应式状态；解耦 `canSend` 与 `status` 计算；确保新 Run 不被旧 Stop 误杀 |
| `src/modules/chat/components/ChatSession.vue` | Component | 挂载反馈条入口与 Inspector 抽屉；桥接快捷键与按钮事件 |
| `src/modules/chat/components/RunStopReportBanner.vue` | Component (新增) | 挂载于 Composer 的 `top-tray` 插槽；展示简要停止状态胶囊、目标计数、查看详情链接、手动核实按钮 |
| `src/modules/chat/components/RunStopReportDetails.vue` | Component (新增) | 挂载于 Inspector 抽屉；详细展示 Checkpoints、工具执行证据（`saved_plan` / `tool_receipt`）、合法成果引用及未确认项 |
| `src/modules/chat/composables/useServerPromptQueue.ts` | Composable | Stop 确认后调用 `refresh()` 拉取服务端最新状态；**禁止调用 `clear()`**；保留本地 unknown 项 |
| `src/utils/http-error.ts` | Util | 复用既有 Platform HTTP Envelope 错误解析与 `request_id` 提示 |

---

## 3. 后端接口契约与严苛校验规则

### 3.1 F01：发起会话停止 (POST)

```http
POST /api/langgraph/threads/{thread_id}/cancel
Authorization: <平台认证>
x-project-id: <项目 ID>
Idempotency-Key: stop:<动作UUID>
Content-Type: application/json

{}
```

- **状态码**：`202 Accepted`（表示请求已持久受理，phase 为 `accepted` 或 `stopping`，也可能直接终态）。
- **权限要求**：`project.runtime.execute` + Thread `edit`。
- **严苛校验（后端已实装，违反必 422）**：
  1. `Idempotency-Key` 必须提供，长度 1~128。
  2. 请求正文**必须严格为纯空对象 `{}`**（后端 `StopBody` 配置了 `extra="forbid"`，带任何多余字段直接 422）。
  3. **严禁携带任何 Query 参数**（后端执行 `_stop_query(request, set())`，哪怕携带防缓存时间戳 `?_t=...` 也会直接触发 422 `invalid_stop_query`）。
- **幂等重试规则**：同一次点击重试必须沿用相同的 `Idempotency-Key`、Body、project_id、thread_id；只有新的停止动作才生成新 UUID key。

### 3.2 F02：按 stop_id 查询详情 (GET)

```http
GET /api/langgraph/threads/{thread_id}/stop-requests/{stop_id}
x-project-id: <项目 ID>
```

- **状态码**：`200 OK`，响应标头带 `Cache-Control: no-store`。
- **权限要求**：`project.runtime.read` + Thread `read`。
- **校验**：**严禁携带任何 Query 参数**；不存在或越权遵循安全隐藏策略（404）。不能因 404 自作主张重新发起一次 POST Stop。

### 3.3 F03：刷新与分页恢复 (GET)

```http
GET /api/langgraph/threads/{thread_id}/stop-requests?limit=20&cursor=<游标>
x-project-id: <项目 ID>
```

- **状态码**：`200 OK`，响应体格式为 `{ items: StopRequest[], next_cursor: string | null }`。
- **🚨 核心契约陷阱（必须严格遵守）**：
  - **后端的请求参数名严格为 `cursor`，而返回体里的分页字段为 `next_cursor`！**
  - 后端白名单严格限定 `{"limit", "cursor"}`。若前端误传 `?next_cursor=...` 或任何未知参数，后端直接抛出 422 `invalid_stop_query`！
  - 若 `cursor` 为 null 或 undefined，**严禁向 URL 拼接 `?cursor=` 空串**，只传 `?limit=20`。
- **使用时机**：初次进入 Thread、多标签页激活或刷新页面时按需拉取最新回执，严禁在渲染每条消息时滥发请求。

---

### 3.4 StopRequest DTO 结构与 Zod 白名单

必须通过 Zod Schema 进行运行时解析，拦截非法数据与路径越权：

```typescript
// 核心状态枚举
export type StopPhase =
  | "accepted"
  | "stopping"
  | "stopped"
  | "no_active_run"
  | "confirmation_unavailable"
  | "rejected";

export type ResourceCleanupStatus =
  | "pending"
  | "confirmed"
  | "unconfirmed"
  | "not_required";

// DTO 数据结构
export interface StopRequest {
  version: 1;
  stop_id: string; // UUID
  thread_id: string; // UUID
  phase: StopPhase;
  requested_at: string; // ISO 8601
  accepted_at: string | null;
  confirmed_at: string | null;
  target_count: number | null; // 非负整数
  execution_stopped: boolean | null;
  resource_cleanup: ResourceCleanupStatus;
  has_pending_interrupts: boolean | null;
  queue: {
    pending_cancelled_count: number | null;
    inbox_consumed_count: number | null;
    inbox_not_consumed_count: number | null;
  };
  report: StopReport | null;
  reason_code:
    | "stop_denied"
    | "stop_confirmation_unavailable"
    | "resource_cleanup_unconfirmed"
    | null;
  request_id: string;
}

export interface StopReport {
  version: 1;
  source: "checkpoint_and_receipts";
  checkpoint_id: string | null;
  checkpoint_at: string | null;
  checkpoints: Array<{
    run_id: string;
    checkpoint_id: string;
    checkpoint_at: string | null;
  }>;
  progress: Array<{
    kind: "saved_plan" | "tool_receipt";
    label: string;
    observed_status: "pending" | "in_progress" | "completed" | "recorded";
    source_run_id: string;
    source_message_id: string | null;
  }>;
  artifacts: Array<{
    artifact_id: string;
    path: string; // 严格匹配 ^/workspace/outputs/[0-9a-f]{64}\.[a-z0-9]{1,8}$
    source_run_id: string;
    source_message_id: string | null;
  }>;
  uncertainties: Array<
    | "checkpoint_unavailable"
    | "progress_unavailable"
    | "external_effect_unknown"
    | "resource_cleanup_unconfirmed"
  >;
  truncated: boolean;
}
```

> **安全解析守则**：成果链接必须匹配正则 `/workspace/outputs/<64位sha256>.<1-8位扩展名>`；前端仅通过现有的平台成果服务进行授权预览或下载，**绝不能直接拼接宿主物理路径或渲染未经校验的原生 URL**。

---

## 4. 状态机全生命周期与并发竞态控制

### 4.1 状态流转图

```text
[用户点击 Stop]
       │
       ▼
  submitting (发送 POST /cancel，携带原 Key，按钮展示 Spinner)
       │
   ┌───┴───────────────────────────────┐
   │ 202 Accepted                      │ 网络中断 / 504 Gateway Timeout
   ▼                                   ▼
accepted / stopping                 unknown (标记未知，保留原 Key)
   │ (启动单飞轮询 GET /stop-requests)   │
   │                                   │ 刷新或重试
   │                                   └───────► 原 Key 重发 POST
   ├───────────────────────────────┐
   │ 后端确认                       │ 达到 45s 硬超时 / 资源清理未确认
   ▼                               ▼
stopped / no_active_run      confirmation_unavailable
   │ (展示成功报告，刷新队列)        │ (展示黄条“运行已停/资源未确认”，
   │                               │  停止自动轮询，提供“重新核实”按钮)
   ▼
[进入终态，清理 localStorage]
```

### 4.2 核心并发与竞态处理准则

1. **解耦 Run Lifecycle 与 Stop Action**：
   - Run 的执行状态（loading、messages、interrupt）继续由官方 LangGraph SDK 持有。
   - `useThreadStopControl` 单独持有当前会话的 `activeStopAction`。
2. **Stopping 期间的发送与输入控制（保守稳妥方案）**：
   - 当 `stopPhase` 处于 `submitting` 或 `stopping` 时，**输入框草稿允许编辑保留，但禁用“发送”和“排队”按钮**，防止并发写入撞击后端的 409 `thread_stopping` 事务屏障。
   - 处于 `stopping` 期间，Stop 按钮处于 disabled + loading 状态，防重复提交。
   - 一旦进入终态（`stopped` / `no_active_run`）或 45s 超时后，发送按钮立即解锁恢复。
3. **新 Run 启动时的竞态隔离（F04 核心验收）**：
   - 停止完成后，用户发送新消息启动了 **New Run**。
   - **New Run 拥有完全独立于旧 Stop 的上下文**：主界面状态栏、停止按钮、SSE 连接必须立即绑定 New Run！
   - 旧的 `stopReport` 自动降级为“历史停止动作反馈”，呈现在反馈区供查阅，**绝对不能把新 Run 误标为 stopped，更不能长期禁用新 Run 的停止按钮**！
4. **`interrupted` 状态的精确区分**：
   - Run 处于 `interrupted` 既可能是审批中断（HITL），也可能是取消动作。**绝对不能把 `interrupted` 直接推导为已停止**，必须以后端 `StopRequest.phase` 为准。
   - 若 `no_active_run` 且 `has_pending_interrupts === true`，界面提示“当前没有运行中的任务，仍有待处理审批”，保留审批面板。
5. **抑制后续推荐问题与消息管线**：
   - 点击 Stop 立即调用 `followUp.markStoppedByUser()`，抑制 `useFollowUpSuggestions`。
   - 停止报告不属于 AIMessage，不进对话历史，不写入 Pinia 消息 store，不产生推荐追问。

---

## 5. 队列、Unknown 提交与草稿协同

1. **服务端队列原子收敛**：
   - 服务端在受理 Stop 请求时已原子固定旧目标快照并取消所有 pending 任务。
   - **前端严禁调用 `useServerPromptQueue.ts` 的 `clear()`**，避免多余请求引发 CAS 冲突或 409。
   - 仅在 Stop 状态确认为 `stopped` / `no_active_run` 时，触发一次 `promptQueue.refresh()`。
2. **未决入队（Unknown Pending）处理**：
   - 若用户此前提交的消息处于 unknown 状态（正在向服务端 enqueue，但未收到 ACK），保留其原 `id/key/body`。
   - 若它在取消边界之后才被服务端成功接受，它属于“新任务”，界面正常显示该排队项，不私自补发二次 Stop。
3. **输入框 Composer 草稿保护**：
   - Stop 操作绝不清空输入框草稿。停止确认后，用户可在此基础上修改并重新提交。

---

## 6. 刷新、切页、多端恢复与轮询策略

### 6.1 持久化存储规范

- **存储介质**：统一使用 `localStorage`（以支持多标签页协同与关页重开恢复）。
- **Key 命名空间**：`pw:thread:stop:${userId}:${sessionEpoch}:${projectId}:${threadId}`。
- **存储数据结构**：
  ```typescript
  interface PersistedStopRecord {
    key: string;         // 原 Idempotency-Key (如 stop:UUID)，重试必备
    threadId: string;
    stopId?: string;     // 收到 202 后回填的 stop_id；有了它刷新后可直接 GET
    requestedAt: number; // 请求发起时间戳
    status: "submitting" | "stopping" | "unknown";
  }
  ```
- **清理与淘汰机制**：
  1. 查询到终态（`stopped`、`no_active_run`、`rejected`）后立即清理。
  2. 初始化加载时，超过 1 小时的未决记录自动清理淘汰。
  3. 用户登出、切换账号（`sessionEpoch` 改变）或切换项目时物理隔离，不跨租户读取。

### 6.2 轮询执行器（Polling Runner）规则

1. **单飞保护（In-Flight Protection）**：
   - 维护 `isPollingInFlight` 标志。上一次 GET 请求尚未返回前，定时器哪怕触发也坚决不重叠发送新请求。
2. **轮询频率与硬超时上限**：
   - `stopping` 期间轮询间隔为 **2 秒**。
   - 设定硬超时上限为 **45 秒**（覆盖 500 pending 目标基准 33 秒）。
   - 若超过 45 秒仍未达到终态，自动切入 `confirmation_unavailable` 态，**终止自动轮询**，界面展示“停止确认超时，请手动核实”，并提供“重新核实”按钮。
3. **`confirmation_unavailable` 降频**：
   - 若后端返回 `confirmation_unavailable`（如 `execution_stopped=true` 但 `resource_cleanup="unconfirmed"`），**立即停止自动高频轮询**，转为手动按钮核实，防止对服务器造成无谓压力。
4. **页面可见性协同**：
   - 页面切入后台（`document.hidden === true`）时暂停定时器轮询；切回前台时立即触发一次单次对账核实。
5. **Thread 切换与 Generation 隔离**：
   - 用户切换 Thread 时，内部 `epoch / generation` 自增，立即 abort 正在飞行的请求并清理轮询定时器，坚决丢弃旧 Thread 的迟到响应，严禁跨 Thread 渲染！

---

## 7. UI 与交互落地规范

遵循 `apps/platform-web/docs/` 下的 frontend playbook、control-plane 与 visual-baseline 规范，不新增全屏页面或花哨区域：

### 7.1 组件划分与挂载落点

1. **简要反馈条：`RunStopReportBanner.vue`**
   - **挂载位置**：`ChatSession.vue` 内 `ChatComposer` 的 `#top-tray` 插槽（紧凑位于输入框上方）。
   - **展示内容**：
     - `submitting` / `stopping`：轻量 Spinner + 稳定尺寸文案（“正在停止...”）。
     - `stopped` / `no_active_run`：绿色/中性徽章，提示“任务已停止”，附带目标数（如“已取消 3 个任务”），提供“查看报告”链接。
     - `confirmation_unavailable`：黄色警告胶囊，提示“运行已停止，资源清理尚未确认”，附带“重新核实”按钮与“查看详情”链接。
     - `rejected`：红色错误提示，展示 Envelope 错误信息与 `request_id`，附带关闭按钮。
2. **详细报告抽屉：`RunStopReportDetails.vue`**
   - **挂载位置**：复用现有的 Inspector 抽屉系统（与 `RunDiagnostics.vue` / `TrajectoryView.vue` 呼应）。
   - **展示内容**：
     - 基础元数据：停止时间、确认时间、目标快照总数、队列清理统计（待取消数、未消费数）。
     - 固定 Checkpoints 列表（最多 20 项）。
     - 保存进度与工具证据列表（`saved_plan` / `tool_receipt`，展示 label、状态与归属 Run）。
     - 授权成果引用（验证通过的 `/workspace/outputs/...`），点击调用现有成果下载/预览服务。
     - 未确认项列表（`uncertainties`），对 `checkpoint_unavailable`、`external_effect_unknown` 等做出明确说明。
     - 截断标记（若 `truncated === true` 提示“部分历史记录已截断，但停止确认覆盖完整目标”）。

### 7.2 交互与无障碍保障

- **按钮稳定性**：Stop 按钮尺寸在普通态与 Spinner 之间保持固定尺寸，防止点击后输入框发生布局跳动（CLS）。
- **无障碍**：状态文案更新区域增加 `aria-live="polite"` 与 `aria-atomic="true"`；提供完整的可访问名称。
- **响应式视口**：
  - `390px`（移动端）：紧凑单列堆叠，文本自动换行，长成果路径安全截断不溢出。
  - `768px`（平板）：自适应中等宽度。
  - `1440px`（桌面端）：与主工作区协调，抽屉侧边展开无遮挡。

---

## 8. 前端专项验收标准 (F01–F10)

| 编号 | 测试场景 | 必须看到的行为与验收标准 |
|---|---|---|
| **F01** | 工具运行中点击 Stop | 发送 `POST /cancel`，Header 携带正确 `x-project-id` 与 `Idempotency-Key`，Body 为 `{}`；收到 202 后界面显示“正在停止”，单飞轮询直至后端确认后才显示“已停止” |
| **F02** | 当前 Run + 2 pending + inbox | 服务端原子处理，已接受旧队列不再执行；本地 composer 草稿不丢失；反馈条正确显示目标数与未消费统计 |
| **F03** | 响应丢失、刷新恢复重试 | 断网或 504 导致 unknown；页面刷新后从 `localStorage` 读取原 key 和未决状态，以原 key 原样重试，后端幂等对账，不触发二次目标扫描 |
| **F04** | Stop 后发送新 Run，再收旧响应 | 用户在停止后发起 New Run；新 Run 保持正常流式执行；后续旧 Stop 的迟到响应只更新历史报告，绝不覆盖新 Run 的执行态，绝不禁用新 Run 的 Stop 按钮 |
| **F05** | 他端停止 / 切换 Thread | 不依赖当前浏览器已知 runId；切 Thread 立即自增 generation 并取消轮询，迟到回执绝不串进新 Thread |
| **F06** | 无活动 Run 且有待审批 | 后端返回 `no_active_run`；界面明确提示“当前没有运行中的任务，仍有待处理审批”；保留原审批卡片，绝不自动 approve/reject |
| **F07** | 403/502/504 错误与拒绝 | 绝不伪装成功；正确展示 Envelope 格式错误与 `request_id`；支持用户在界面重新核实 |
| **F08** | 资源未确认 / 外部结果未知 | 后端返回 `confirmation_unavailable`；界面真实展示黄条提示，无“全部撤销”误导文案，停止自动轮询，支持手动重新核实 |
| **F09** | 报告为空 / 截断 / 脏数据过滤 | 报告通过 Zod Schema 安全解析；截断时展示提示，空态友好；过滤非法成果路径与敏感未知字段 |
| **F10** | 390 / 768 / 1440 响应式与键盘 | 三种视口无横向滚动条或布局错乱；键盘 Tab 可达；`aria-live` 实时发音；Stop 点击无抖动 |

---

## 9. 实施与回交规范

1. **环境与实施路径**：
   - 在当前 worktree `/Users/lijiaxin/.codex/worktrees/5543/ai-agent-platform` 的 `apps/platform-web/` 下进行。
   - 正式依赖未升级前，优先编写纯函数状态机、Zod 校验与 Unit/Fixture 测试（Vitest），确保契约与状态机 100% 闭环。
2. **回交产物要求**：
   - 提交 Vitest 单测报告、`pnpm vue-tsc` 0 错误、`pnpm eslint` 0 错误、`pnpm build` 构建成功输出。
   - 补充 390/768/1440 视口下的 UI 截图与操作录屏/Trace 证据。
   - 将改动文件、任务完成卡和 Phase 验证记录同步写回本专项的 `tasks.md` 与 `verification.md`。
