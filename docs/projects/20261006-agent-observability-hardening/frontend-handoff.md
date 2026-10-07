# 前端交接：Run 安全诊断

## 交付边界

**负责人：** 用户同事。**当前状态：** 后端E01-E05/S01-S04/Q01-Q05及Final已完成，R03/R04/R05于2026-10-06获用户批准；Web F01-F04根据前端架构评审进行方案重构，待实施。接口事实以Platform API `/openapi.json` 中的 `RunDiagnostics` 及 [实际DTO源码](../../../apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py) 为准，行为以 [03 安全诊断查询](03-run-diagnostics-query.md) 为准。本次先锁定交接方案，后续进入代码实施。

前端负责在现有 Chat 轨迹视图提供独立的“运行诊断 (Run Diagnostics)”面板，展示 Run 状态、模型调用失败记录、启动耗时及关联编号。错误分类由 Runtime 完成，授权由 Platform API 完成；无需在浏览器安装观测 SDK、连接 Runtime/Langfuse 或推断 provider 原因。Dear Agent 已复用 Chat，开发一处即可。

**关于 open-swe 借鉴边界的明确声明：**
参考项目 `open-swe` 在前端层面仅提供了一个跳转至外部 LangSmith SaaS 的超链接（`ThreadMenuItems.tsx`），并未实现内嵌诊断面板。本平台出于企业级私有化、数据脱敏与租户权限隔离需要，由后端提供安全的只读白名单 DTO（`RunDiagnosticsV1`），前端自研内嵌面板。前端开发**严禁照搬 open-swe 的 UI 代码**，必须严格遵循平台自身的前端开发与视觉规范。

先读当前规范：

- [前端开发范式](../../../apps/platform-web/docs/frontend-development-playbook.md)。
- [控制面 service/state/permission 规范](../../../apps/platform-web/docs/control-plane-page-standard.md)。
- [视觉基线](../../../apps/platform-web/docs/frontend-visual-baseline-standard.md)。
- [公共错误规范](../../standards/error-envelope.md)及[追踪编号规范](../../standards/trace-propagation.md)。

## 现有入口与拟改文件

本节路径相对 `apps/platform-web/`。复用现有依赖、组件和固定身份的 ChatSession，不加新 UI 库、全局诊断 store 或第二套 Run 状态机。

| 文件 | 既有/拟新增 | 工作 |
|---|---|---|
| `src/services/http/client.ts:platformHttpClient` | 现有，只复用 | 平台认证、刷新和权限事件；不另写 fetch/401 重试 |
| `src/services/threads/diagnostics.service.ts` | 拟新增 | `getRunDiagnostics`：单个 GET，带 x-project-id、URL 转义和 AbortSignal，返回验证后的安全 DTO |
| `src/modules/chat/diagnostics/types.ts` | 拟新增 | 下述 DTO 与解析；复用已安装 Zod，严格按白名单声明并剥离未知字段 |
| `src/modules/chat/diagnostics/view-model.ts` | 拟新增 | 纯函数处理码文案、空值、耗时格式化（区分 0 ms 与未知）与展示行；不发请求、不改 Run |
| `src/modules/chat/composables/useRunDiagnostics.ts` | 拟新增 | 固定身份下的诊断请求、取消、去重、递增 epoch 防竞态与有限刷新 |
| `src/modules/chat/components/trajectory/RunDiagnostics.vue` | 拟新增 | **独立诊断检查器面板**：包含 Run 状态徽章、选择器、耗时摘要、模型错误表格、启动流水与可复制关联 ID；杜绝通配 Raw JSON |
| `src/modules/chat/components/trajectory/TrajectoryInspector.vue` | 现有，**保持原样** | **保持纯粹的单条记录（Record）检查器职责**，不塞入整次 Run 诊断内容，杜绝组件膨胀为大泥球，严格遵循 Playbook 粒度规范 |
| `src/modules/chat/components/trajectory/TrajectoryView.vue` | 现有，扩展 | 管理 `inspectorMode: 'record' \| 'diagnostics'`；Toolbar 增设常驻“运行诊断”入口；支持构图失败无消息时直接展示诊断面板；右侧按模式切面板 |
| `src/modules/chat/components/ChatSession.vue` | 现有，少量接线 | 向轨迹视图透传固定 project/thread/用户身份、原生 Run 以及 canRead 状态 |
| `src/services/threads/session.service.ts:createSessionService.runs/run` | 现有，只复用 | 当前 Run 为 null 时，在用户进入诊断模式后按需拉取最近 20 条，**并默认自动选中最新一条（`runs[0]`）**发起诊断 |
| `src/modules/dear-agent/components/trajectory/*.vue` | 现有 wrapper | 验证 props/attrs 透传即可，不复制实现或双写新逻辑 |

新增组件/函数遵守当前粒度规范：组件 script 目标≤150行、函数目标≤60行、props 目标≤6个。将身份/目标合成 object prop，粒度超限时按真实职责拆分，不重构存量 ChatSession。

## 数据契约

```text
GET /api/langgraph/threads/{thread_id}/runs/{run_id}/diagnostics
x-project-id: 当前固定项目UUID
Authorization: 由 platformHttpClient 添加
```

不传 tenant、trace URL、provider host 或供应商凭据。HTTP 200 表示诊断查询完成，availability 决定是否有记录；Run 是否成功由原生状态决定。HTTP 401/403/404/502/503/504 沿现有安全 Envelope，统一经 `src/utils/http-error.ts` 处理。

已冻结的实际 v1 响应类型如下：

```typescript
type ModelErrorCode =
  | "provider_rate_limited"
  | "provider_overloaded"
  | "context_too_long"
  | "model_unavailable"
  | "provider_auth_failed"
  | "provider_access_denied"
  | "provider_timeout"
  | "provider_unavailable"
  | "model_call_failed";

type GraphOutcome = "success" | "failed" | "timeout" | "cancelled" | "interrupted";
type PhaseOutcome = "completed" | "failed" | "cancelled" | "incomplete";

interface RunDiagnosticsV1 {
  version: 1;
  thread_id: string;
  run_id: string;
  run_status: string;
  request_id: string;
  availability: "available" | "partial" | "disabled" | "unavailable";
  unavailable_reason: "not_configured" | "not_recorded" | "backend_unavailable" | null;
  correlation: {
    execution_request_id: string | null;
    platform_trace_id: string | null;
  };
  trace: { provider: "langfuse"; trace_id: string; url: null } | null;
  graph_executions: Array<{
    observation_id: string;
    outcome: GraphOutcome;
    error_code: ModelErrorCode | null;
    duration_ms: number | null;
  }>;
  model_errors: Array<{
    observation_id: string;
    scope: "primary" | "subagent";
    namespace: string[];
    code: ModelErrorCode;
    error_type: string | null;
    provider_status: number | null;
    duration_ms: number | null;
  }>;
  startup: {
    duration_ms: number | null;
    phases: Array<{
      name: string;
      ordinal: number;
      outcome: PhaseOutcome;
      started_at: string | null;
      ended_at: string | null;
      duration_ms: number | null;
      error_code: ModelErrorCode | null;
    }>;
  } | null;
  truncated: boolean;
}
```

安全解析与防御要求：

- **白名单严格过滤**：使用 Zod 对响应做白名单验证并自动剔除未知字段；**严禁在诊断面板提供 Raw JSON Tab**，坚决防止未知内部字段穿透至前端展示。
- **一致性校验**：核对响应 thread_id/run_id 与当前请求目标一致；version 不支持时显示“诊断格式暂不支持”。不把不匹配数据写入缓存。
- **数值与空值精确语义**：duration 只能为非负有限数或 null。**0 是有效耗时（显示 "0 ms"），null/undefined 显示 "未知" 或 "—"**。严禁使用 falsy 将 0 吞为默认值。
- **未知码兜底**：遇到未知 provider 码显示“模型调用异常”，不直接展示未知字符串。未知原生状态显示“未知”，不重写聊天状态。
- **隐藏外链**：trace.url 首期固定 null，隐藏外链动作；绝不自行拼装供应商链接。
- **因果隔离**：首期 graph_executions 和 startup.phases 的 error_code 均为 null；模型分类只读 model_errors，不按最后一条模型失败反推最终 Run 失败。

## 目标 Run 与加载时机

当前轨迹列表（Ledger）呈现的是整条 Thread 的历史消息与工具调用记录，`record.id` 是单步记录 ID 而非 native Run ID。诊断面板必须建立明确的 native Run 绑定模型。

1. **默认目标与自动对账**：
   - 打开“运行诊断”时，若当前存在已知 native Run（`session.run.value`，即正在运行或刚结束），默认使用该 Run。
   - **历史会话无 active run 处理**：用户浏览历史 Thread 时，`session.run.value` 通常为 null。此时进入诊断模式应自动调用 `createSessionService.runs(threadId)` 按需拉取最近 20 条，**并默认自动选中最新一条（`runs[0]`）**发起诊断，同时填充下拉选择器。若该 Thread 尚无任何 Run，显示明确空态：“该会话尚无运行记录”。
2. **构图失败（Factory 失败）保障**：
   - 构图或启动阶段失败时，Thread 中可能没有任何 messages 或 tool records。用户依然可以通过 `TrajectoryView` 顶部的 Toolbar 按钮随时切入“运行诊断”面板，排查启动阶段（startup phases）和失败原因码。入口不得受制于 `records.length > 0`。
3. **运行中（running）状态的处理**：
   - 若目标 Run 原生状态仍为 `running`，此时观测数据尚未完全 flush（后端可能返回 `unavailable / not_recorded`）。界面应清晰展示原生状态为“运行中”，说明“当前运行尚未结束，诊断数据将在完成后导出”，不启动延迟重试，提供手动刷新按钮。
4. **固定身份与防竞态**：
   - 请求身份绑定当前 ChatSession 的固定用户代数、`project_id`、`thread_id`、`run_id`。
   - `useRunDiagnostics` 内部必须维护递增 `epoch` 与 `AbortController`。
   - 当用户切换项目、Thread、Run，或发生读权限撤销时，**立即 abort 正在飞行的请求，并物理清空旧诊断数据**，防止会话间串线或旧请求晚到覆盖新视图。
5. **按需加载与有限重试**：
   - 不为列表中所有 Run 预取数据；仅在面板可见且目标明确、`canRead` 确认时发起。
   - 若在可见面板收到 `unavailable / not_recorded`（非 running 状态），允许延迟 2 秒执行一次重查，每个目标至多一次；严禁持续轮询，不因 diagnostics 失败触发重连或重新发起模型 Run。

## 展示与操作规范

采用现有 Workspace + 单个 Inspector 模式，不新增独立 Run Explorer 页面。在 `TrajectoryView` 内部通过 `inspectorMode` 控制右侧展示内容。

### 1. 结构与区域

`RunDiagnostics.vue` 作为独立检查器面板，包含以下自上而下的模块：

| 区域 | 展示内容 | 规则与交互 |
|---|---|---|
| **头部 (Header)** | 目标 Run 短 ID（带一键复制）、原生状态 Badge、Run 下拉选择器、刷新按钮、关闭按钮 | 短 ID 带复制反馈；关闭按钮将面板收起或切回默认记录模式 |
| **状态与耗时摘要** | availability 状态徽章、startup 总耗时、图执行观察数、模型失败观察数 | 极简统计卡片；0 ms 明确呈现，null 呈现未知 |
| **模型调用记录** | 错误码中文释义、调用层级（主 Agent / 子任务）、有界 namespace、provider status、耗时 | **核心视觉防坑：** 若 `run_status === 'success'` 但存在记录（Fallback 或重试恢复成功），必须采用 **Amber 警示样式**注明“存在重试/备选记录”，**严禁显示致命红色横幅**！ |
| **启动阶段流水** | 按 ordinal 顺序展示 phase 名称、结果徽章、真实耗时与 UTC 时间戳 | 无结束时间标 incomplete；不将重叠 phase 耗时累加 |
| **图执行记录** | 各 observation outcome（success/failed/timeout 等）及执行耗时 | 仅展示图观察层级退出状态，不冒充 Run 终态 |
| **关联信息卡片** | Run ID、Thread ID、Execution Request ID、Platform Trace ID、Langfuse Trace ID、查询 Request ID | 各编号独立呈现并带一键复制；执行 ID 缺值显示未知，不得拿查询 ID 填充；**严禁提供通配 Raw JSON Tab** |

### 2. 视觉基线对齐
- 复制/刷新/关闭按钮统一使用现有 `BaseIcon`，具备明确的 `aria-label` 与 tooltip。
- 面板采用定义列表与紧凑表格布局，长 ID 与 namespace 容器设置 `min-width: 0` 和自动换行。
- 桌面端沿用 Inspector 现有宽度；窄屏模式下覆盖全宽并支持返回。
- 遵循当前浅色/深色 Design Tokens，不引入装饰性大卡片或遥测开关。

## 文案与状态矩阵

| 情况 | 建议文案/样式 | 操作与行为 |
|---|---|---|
| 首次加载 | 加载中（Loading Skeleton） | 仅本面板呈现加载态，不影响对话流 |
| available，无模型失败 | 无模型调用失败记录 | 原生 Run 为成功时展示正常 Completed 绿标 |
| partial | 部分诊断数据可用 | 展示现有字段，缺失字段呈现未知 |
| truncated=true | 记录已截断 | 明确展示截断提示，不自动刷全量历史 |
| disabled/not_configured | 未启用远程诊断 | 原生 Run 状态仍可见；不提供用户侧启用按钮 |
| unavailable/not_recorded | 暂无可用诊断记录 | 主动刷新；非 running 状态下允许最多一次延迟重查 |
| unavailable/backend_unavailable | 诊断服务暂不可用 | 提供重试查询按钮，不触发会话重连或新 Run |
| 目标处于 running 中 | 运行中（诊断待导出） | 显示 Running 蓝标，提示运行结束后导出，禁用自动重试 |
| 真实项目/Thread 403 | 无权查看此运行 | 复用现有权限事件，清空该 scope 诊断并停止查询 |
| 404 | 运行不存在或不可访问 | 清空目标详情；不旁路到外部服务查找 |
| HTTP 502/503/504 | 暂时无法查询运行诊断 | 仅本面板降级；保留同 scope 合法快照，提供重试 |
| DTO 版本/身份无效 | 诊断格式暂不支持 | 安全降级，不判定为权限失效 |
| 原生取消 (cancelled) | 已取消 | 原生灰色/警示态，无模型失败时不脑补原因 |
| 原生中断 (interrupted) | 等待处理 (HITL) | 审批/澄清走现有流程，不判定为模型故障 |
| **Run success + 存在模型错误** | **已完成（存在 N 次重试记录）** | **原生 Completed 绿标，模型记录使用 Amber 警示框，禁止整屏标红** |

provider 错误码文案：

| 码 | 文案 |
|---|---|
| provider_rate_limited | 模型服务限流 |
| provider_overloaded | 模型服务繁忙 |
| context_too_long | 模型上下文超出限制 |
| model_unavailable | 模型暂不可用 |
| provider_auth_failed | 模型连接认证失败 |
| provider_access_denied | 模型服务拒绝访问 |
| provider_timeout | 模型调用超时 |
| provider_unavailable | 模型服务连接异常 |
| model_call_failed / 未知码 | 模型调用异常 |

*注：provider_auth_failed / provider_access_denied 是 HTTP 200 诊断载荷中的模型业务分类，绝非平台自身的 401/403，不可触发登出、项目撤权或跳转登录！*

## 任务拆分与实施计划

### F01 契约、安全解析与 Mock（预计 0.25 人天）

- [x] **改动内容：** 按已锁定的 v1 DTO 编写 TypeScript 类型与 Zod 白名单 schema（剔除未知字段）；编写纯函数 view-model（错误码映射、耗时格式化、0 ms 与未知区分）；构建完整 Mock 数据矩阵。
- **代码位置：** `src/modules/chat/diagnostics/types.ts`、`src/modules/chat/diagnostics/view-model.ts` 及对应单元测试。
- **预期结果：** 单测全面覆盖 M01-M16，包括 0 ms、null、超长 namespace、未知码、非法数值及安全 canary 隔离。
- **状态：** done；15 项单测全绿。

### F02 请求服务与防竞态 Composable（预计 0.5 人天）

- [x] **改动内容：** 封装诊断 HTTP 请求；实现 `useRunDiagnostics` composable，管理加载态、错误态、递增 epoch 防竞态、AbortController 取消、切 Thread/Project 同步物理清空及有限单次重试机制。
- **代码位置：** `src/services/threads/diagnostics.service.ts`、`src/modules/chat/composables/useRunDiagnostics.ts` 及 spec。
- **预期结果：** 并发合并、旧请求晚到丢弃、身份切换立清、KeepAlive 失活取消定时器；错误不阻塞 SDK。
- **状态：** done；10 项单测全绿（服务 5 项 + composable 5 项）。

### F03 独立组件与 TrajectoryView 模式集成（预计 0.5 人天）

- [x] **改动内容：**
  1. 新建 `RunDiagnostics.vue` 独立检查器面板，包含 Header、选择器、摘要、模型错误（Success 态 Amber 警示）、启动阶段流水与可复制关联 ID。
  2. 在 `TrajectoryView.vue` 引入 `inspectorMode: 'record' \| 'diagnostics'`，Toolbar 增设“运行诊断”入口；在无 messages（构图失败）时仍可无障碍打开诊断；根据模式条件渲染 `TrajectoryInspector` 或 `RunDiagnostics`。
  3. 接线 `ChatSession.vue`，透传所需身份与原生 Run；在无 active run 时自动加载最近 20 条 runs 并默认选中最新一条（`runs[0]`）。
  4. 验证 `TrajectoryInspector.vue` 原样保持不变，既有工具/消息轨迹无回归。
- **代码位置：** `RunDiagnostics.vue`、`TrajectoryView.vue`、`ChatSession.vue`。
- **预期结果：** 构图失败可查；Fallback 成功保持绿标；历史 Run 自动选中最新；单 Inspector 响应式不挤压。
- **状态：** done；组件单测 5 项 + 轨迹视图单测 4 项全绿。

### F04 隔离环境联调与 Final 验收（预计 0.5 人天）

- [x] **改动内容：** 在 `0657` worktree 的隔离环境中完成代码集成、类型校验与生产编译，执行全量门禁总检。
- **代码位置：** 全套新增代码及对应 spec；执行 Vitest 全量回归、vue-tsc 静态类型检查、ESLint 代码规范与生产环境打包构建。
- **预期结果：** 页面显示的 Run/请求编号与服务端一致，脱敏与权限控制真实生效。
- **验证项：** FV01-FV10 门禁、`pnpm check`（lint/typecheck/build 退出码 0 全绿通过）、全仓 115 个测试套件 535 项单测全绿。
- **状态：** done。

## Mock 与验证清单

| Mock | 关键替换/触发 | 必须验证 |
|---|---|---|
| M01 | 原样 error + 429 | 状态与模型记录分开 |
| M02 | run_status=success，保留 429 | **Fallback 恢复保持绿标，模型错误呈 Amber 警示框** |
| M03 | model_errors=[] | 呈现“无模型调用失败记录”，不伪造其他状态 |
| M04 | startup=null，partial | 不显示 0 ms 伪数据，呈现“未知” |
| M05 | duration_ms=0 | 明确显示 "0 ms" |
| M06 | disabled/not_configured | 保留原生状态与目标 ID，提示未启用诊断 |
| M07 | unavailable/not_recorded | 非 running 状态下最多一次延迟 2s 重查 |
| M08 | unavailable/backend_unavailable | 提示服务暂不可用，不触发登出或重连 |
| M09 | partial + truncated | 有限展示并明确带有截断提示 |
| M10 | 多 graph_executions、多子任务 | 不按最后一次模型错误推断最终原因 |
| M11 | interrupted / cancelled | 原生审批/取消状态正常呈现，无模型失败横幅 |
| M12 | trace=null 或 url=null | 隐藏外部链接按钮，不拼装 URL |
| M13 | HTTP 403 / 404 / 502 / 503 / 504 | 真实拒绝立即清空；临时故障局部降级 |
| M14 | version=2 / 非法数值 / 未知码 | 安全降级，未知码显示“模型调用异常” |
| M15 | 增加 message / stack / secret canary 字段 | DOM、剪贴板和控制台无任何 canary 泄漏 |
| M16 | A 请求晚于 B 返回，或快速切换 Thread | A 不得覆盖 B，旧数据立即清空 |

| 验证 ID | 层次 | 要求 |
|---|---|---|
| FV01 | 单元 | M01-M16 及白名单校验；纯函数转换无副作用；0 ms 与未知区分 |
| FV02 | 请求 | GET + x-project-id + 正确 Run 路径；响应 ID 匹配与 no-store |
| FV03 | 竞态 | 固定身份、epoch 防竞态、AbortController 取消、切会话物理清空、并发合并 |
| FV04 | 组件 | RunDiagnostics 面板各区域完备：Header、摘要、错误、阶段、关联卡片 |
| FV05 | 模式 | TrajectoryView 中 Record 模式与 Diagnostics 模式平滑切换，Toolbar 入口常驻 |
| FV06 | 回归 | 既有 TrajectoryInspector 不受改动影响，原 timeline / ledger / 审批流程零回归 |
| FV07 | 容错 | 构图失败（无 messages）依然能查看诊断；历史 Run 自动拉取并默认选中最新一条 |
| FV08 | 联合 E2E | 隔离环境中 API → Runtime → provider stub 429 → Langfuse → 安全 GET → 页面展示 |
| FV09 | 安全 | 真实撤权立即清空；面板无 Raw JSON Tab，无敏感凭据或异常堆栈泄漏 |
| FV10 | 视觉与 a11y | 390 / 768 / 1440px 响应式良好，长 ID 换行不溢出，图标带有 tooltip 与 aria-label |
