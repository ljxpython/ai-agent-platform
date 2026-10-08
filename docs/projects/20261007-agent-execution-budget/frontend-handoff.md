# 前端交接：Agent 执行预算提示

> 前端交接与实施契约。当前工作树已包含 F01-F03 初版草稿实现，但存在响应式订阅断裂、Zod 重复解析性能黑洞、SafetyError 降级误判（Thread 耗尽误给草稿重发）、复读机式重复文案与预警状态下取消按钮丢失等严重缺陷。当前任务是在现有工作树改动基础上进行架构与契约重构纠偏，并完成 F04/T08B 浏览器联合验收。转交入口见[前端交付报告](frontend-delivery-report.md)。

## 要交付的行为

在现有Chat中展示“额度接近上限”“开始收尾”“因限制停止”，并说明请求可能未完成。前端只消费执行事实；不计算预算、不决定停止、不执行通知工具、不创建第二套Run状态机。

无需新页面、Agent配置表单或平台通知中心。现有 ChatSession、AgentStatusBar、子任务详情及草稿/分支动作足够承载本项。

## 当前代码入口与重构责任

| 文件 | 责任与重构要点 |
| --- | --- |
| `apps/platform-web/src/modules/chat/composables/useSessionConnection.ts` | 持有官方`useStream`实例；透出stream，预算投影复用其stream |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | 原生Run核实、提交、恢复、取消；透出当前`run`与`stream`，不另建运行状态 |
| `apps/platform-web/src/modules/chat/budget/types.ts`（已有草稿） | Zod白名单校验通知/安全错误；区分整型与浮点秒数，未知版本安全忽略，保留strip特性 |
| `apps/platform-web/src/modules/chat/budget/view-model.ts`（已有草稿） | `safeExtractBudgetNotice`支持多层嵌套解包；**消除复读机文案**；**安全错误未知scope时严禁赋权adjust_draft重发草稿**；Thread限额分流新建/分支 |
| `apps/platform-web/src/modules/chat/composables/useRunBudget.ts`（已有草稿） | **重构订阅机制**：采用响应式订阅或增量事件处理，杜绝静态target断裂；**落地真实200条LRU有界去重**；杜绝在computed hot path中对全量buffer重复执行Zod解析；规范空runId历史标记过滤 |
| `apps/platform-web/src/modules/chat/components/ChatAgentStatusBar.vue`、`ChatSession.vue` | 状态栏文案解耦；**在running+warning预警态下必须保留取消按钮**；Thread耗尽置灰输入框；草稿回填处理多模态content并规避原生`window.confirm` |
| `apps/platform-web/src/modules/chat/components/SubagentCard.vue`、`SubtaskDetail.vue` | **禁止在卡片三元表达式内违规调用Composable**；子任务卡片头部徽章联动预警/停止；子任务详情顶部展示归属namespace的轻量预算提示 |
| `apps/platform-web/src/modules/chat/run-actions.ts`、`branching.ts`、`composables/useChatActions.ts` | 复用现有草稿与合法分支；区分Run限额（回填草稿）与Thread限额（引导新会话/合法分支） |

遵循 [Frontend Playbook](../../../apps/platform-web/docs/frontend-development-playbook.md) 和 [控制面规范](../../../apps/platform-web/docs/control-plane-page-standard.md)。新增函数优先纯转换，新增composable只管预算投影；不把业务判断继续堆进大组件。

## 通知契约与 Zod 校验规则

```ts
type BudgetCode =
  | "model_call_limit_approaching"
  | "model_call_limit_reached"
  | "graph_step_limit_approaching"
  | "wrapup_started";

type BudgetNotice = {
  version: 1;
  type: "runtime_budget_notice";
  notice_id: string;
  run_id: string;
  scope: "primary" | "subagent";
  budget_scope: "run" | "thread" | "graph";
  code: BudgetCode;
  limit: number | null;
  used: number | null;
  remaining: number | null;
  unit: "model_calls" | "graph_supersteps" | "seconds";
};
```

namespace 来自原始协议外层，不在页面里猜路径。`run_id` 由 Runtime 写入 notice，与官方 controller 核实的当前 Run 匹配；外层 `params.run_id/seq` 不是每个入口都有，不能要求其必填或用浏览器临时 UUID 替代。

### 关键数值与单位约束（严防类型校验误杀）
- **notice_id 格式**：服务端生成稳定格式为 `budget:{run_id}:{namespace_hash}:{scope/dimension}:{code}`（上限 256 字符）。**前端绝不可通过 split 或正则拆解 notice_id 的段数推导字段**，必须仅将其作为唯一 key 去重，所有业务语义均以 notice 内的具体字段为准。
- **调用/步骤类（`unit === "model_calls" | "graph_supersteps"`）**：
  `limit`、`used` 以及非 null 的 `remaining` **必须为非负安全整数**（`z.number().int().nonnegative()`）。
- **时间类（`unit === "seconds"`，即 `wrapup_started`）**：
  `limit` 和 `used` **为非负有限数字（浮点数，如 limit: 0.01, used: 0.907532）**，使用 `z.number().nonnegative().finite()`，**禁止使用 `.int()` 校验**！且此时 `remaining` 固定为 `null`（`z.null()`）。
- **通用保护**：Zod schema 应使用 `discriminatedUnion("unit", ...)` 或 refine 精确区分上述单位；非法数值、未知版本、未知 code 或过长 ID 整条安全忽略（返回 `null`），Zod 必须启用 `.strip()` 剔除未知字段，严禁抛出未捕获异常，严禁把原始未脱敏 payload 打入普通控制台日志。

| code | unit | budget_scope | 数值特性 |
| --- | --- | --- | --- |
| model_call_limit_approaching / model_call_limit_reached | model_calls | run / thread | 整数 |
| graph_step_limit_approaching | graph_supersteps | graph | 整数 |
| wrapup_started | seconds | run | 浮点数，remaining 为 null |

本期工具额度只有硬错误码，没有 tool_calls custom 预警。

例1，模型run额度进入收尾区间：

```json
{"version":1,"type":"runtime_budget_notice","notice_id":"budget:831cda62-2b71-4620-a7b3-36ba7b5c457a:6fb9b9075ec282b22589:run:model_call_limit_approaching","run_id":"831cda62-2b71-4620-a7b3-36ba7b5c457a","scope":"primary","budget_scope":"run","code":"model_call_limit_approaching","limit":10,"used":7,"remaining":3,"unit":"model_calls"}
```

例2，Thread累计额度触限：

```json
{"version":1,"type":"runtime_budget_notice","notice_id":"budget:7e385a40-9e25-4b62-9cd5-24d8a328055c:5aa6d72d794e938dec1c:thread:model_call_limit_reached","run_id":"7e385a40-9e25-4b62-9cd5-24d8a328055c","scope":"primary","budget_scope":"thread","code":"model_call_limit_reached","limit":5,"used":5,"remaining":0,"unit":"model_calls"}
```

例3，独立软时间阈值到达（浮点数与 null 示例）：

```json
{"version":1,"type":"runtime_budget_notice","notice_id":"budget:db20c8c2-bca2-4e39-9688-a21a22002d5a:6fb9b9075ec282b22589:run:wrapup_started","run_id":"db20c8c2-bca2-4e39-9688-a21a22002d5a","scope":"primary","budget_scope":"run","code":"wrapup_started","limit":0.01,"used":0.9075320040001316,"remaining":null,"unit":"seconds"}
```

软时间阈值只是样例，不是新增默认值；默认关闭，实际值由Runtime配置。不得显示“离Run超时还剩N秒”，该middleware没有Worker的权威deadline。

## 官方 SDK 订阅与事件提取

当前Web使用`@langchain/vue==1.0.35`、SDK`1.10.2`。
> ⚠️ **关键架构规约（防响应式断裂与订阅泄漏）**：
> 官方 `@langchain/vue` 中 `useChannel(stream, channels, target)` 的 `target` 参数是**静态对象**（`SelectorTarget`），**不支持**响应式变化（传入 `computed.value` 仅在首次求值时取一次，后续 namespace 响应式变化不会触发重新订阅）。
> 因此，必须使用支持响应式 scope 的 `useChannelEffect(stream, ["custom"], { target: () => targetNs.value, ... })`，或者在父层对 stream custom 事件建立增量监听缓存并按 namespace 派发，**严禁使用静态 target 导致子智能体动态 namespace 订阅断裂**！
> 复用 SDK ref-counted 订阅和 scope 释放，严禁另调 EventSource/fetch 或新建 useStream。

API 普通默认 modes 已包含 `custom`；显式自定 stream modes 时仍需包含它。普通 Run 子图流必须创建时指定 `stream_subgraphs=true`（SDK：`streamSubgraphs: true`），否则既有 GraphHarbor 过滤子图事件。Protocol 使用已有 scoped channel 订阅，包含所需 namespace/depth；不另开连接。`onCustomEvent` 只用于已存在并实测的普通 SDK 入口；本期没有 `custom:budget`，不能调用 `useExtension("budget")` 期待数据。

### 数据解包纯函数 `safeExtractBudgetNotice`
协议传输存在多种真实 payload 嵌套形态，前端必须统一实现纯函数提取并送入 Zod 校验（处理外层 `payload`、`params.data` 或直接 notice）：

```ts
export function safeExtractBudgetNotice(raw: unknown): BudgetNotice | null {
  if (!raw || typeof raw !== "object") return null;

  let candidate: Record<string, unknown> = raw as Record<string, unknown>;

  // 1. 如果外层包含 transport payload 包装 (SSE raw wrapper)
  if ("payload" in candidate && candidate.payload && typeof candidate.payload === "object") {
    candidate = candidate.payload as Record<string, unknown>;
  }

  // 2. 如果包含 protocol params (v3 raw event)
  if ("params" in candidate && candidate.params && typeof candidate.params === "object") {
    const params = candidate.params as Record<string, unknown>;
    if ("data" in params && params.data && typeof params.data === "object") {
      candidate = params.data as Record<string, unknown>;
    }
  } else if ("data" in candidate && candidate.data && typeof candidate.data === "object") {
    candidate = candidate.data as Record<string, unknown>;
  }

  // 3. 校验类型标识
  if (candidate.type !== "runtime_budget_notice") {
    return null;
  }

  const result = BudgetNoticeSchema.safeParse(candidate);
  return result.success ? result.data : null;
}
```

### 跨 Run 隔离、增量处理与真正 200 条 LRU 去重
- **当前 Run 隔离**：SDK 的 custom buffer 跨串行 Run 累计（默认容量 4096），**绝不能取数组最后一项作为当前状态**。`useRunBudget` 必须接收 `currentRunId: ComputedRef<string | null>`，活跃状态投影严格过滤 `notice.run_id === currentRunId.value`。非当前 Run 的事件仅作为历史附注，严禁覆盖当前顶栏。
- **杜绝全量重复扫描性能黑洞**：严禁在 `computed` hot path 内部对 4096 条事件全量反复跑 `safeParse`！必须采用增量事件消费（通过 `useChannelEffect` 或带索引缓存），仅对新增事件做 Zod 解析。
- **真正的 200 条有界 LRU/FIFO 去重**：建立具有真实容量淘汰机制的 Cache/Set（超过 200 条时淘汰最旧的 `notice_id`），防止长会话内存持续膨胀；在 `threadId` 变化、用户登出或明确切换项目时，清空当前预算投影与去重缓存。

## 原生硬错误与历史回退

没有 custom 通知时，当前 Run 的 lifecycle/error 若有精确 type 也能解释硬停止。实际有 error 的 Thread JSON/lifecycle 字段保持原生形状，安全投影形态如下：

```json
{"type":"GraphRecursionError","code":"runtime_graph_step_limit_reached","message":"Graph step limit reached"}
```

| 安全code | 推荐文案 |
| --- | --- |
| runtime_graph_step_limit_reached | 本次执行达到图步骤上限，任务可能尚未完成 |
| runtime_model_call_limit_reached | 模型调用额度已耗尽，任务可能尚未完成 |
| runtime_tool_call_limit_reached | 工具调用额度已耗尽，任务可能尚未完成 |
| runtime_run_timeout | 本次执行已超时；部分工具操作可能需要核对结果 |

不使用异常message里的英语短语猜预算。error是字符串或没有预算code时按现有安全错误提示处理。
> ⚠️ **核心安全契约（未知 Scope 严禁赋权重发）**：
> 当仅有原生 `runtime_model_call_limit_reached` 安全错误，而缺少明确包含 `budget_scope === "run"` 的结构化 notice 时，前端**无法证实**该限额是否为单次 Run 还是 Thread 累计耗尽。根据“不知道是 run 还是 thread 不能替用户决定续跑”原则，**严禁私自将 scope 假设为 run 并提供 `adjust_draft` 动作**！此时必须降级为仅显示停止文案（`actionType: "none"`，禁止重发当前会话），避免误导用户在 Thread 耗尽时盲目重发。
> 历史 `additional_kwargs.runtime_budget_notice` 提取仅当其 `run_id === currentRunId` 时生效；当切换新 Run 时必须即时清空历史投影，防止旧 Run 停机原因闪烁覆盖新 Run 顶栏。

对 Reference/Workflow 现有 `end` 路径，官方生成的人工 AIMessage 带有 `additional_kwargs.runtime_budget_notice`，与 custom reached 同 schema。这是历史回放的辅助标记，去重相同 notice_id；不要隐藏或删除正常模型消息。只有服务端生成的标记应通过网关，前端不能把它写回 input/state/resume。

410时沿现有ACL/Run/state恢复，不自动重发请求。post41原生Run GET只有status/reason等字段，没有error；Thread.error是最新槽位，不能拿它归因某个历史Run。本Run事件仍可重放或有人工消息标记时才显示精确停止原因，全部过期/缺失时只显示原生状态与安全泛化；历史approaching不重新猜。预算投影不能依赖Langfuse可用性，诊断面板继续按原独立契约工作。

Workflow的内层模型不是委派子Agent，其primary通知由Runtime沿外层root writer发布，使用root投影即可显示；委派子Agent沿scoped namespace显示。不能把所有非空namespace都猜成“子Agent失败”，也不能遗漏外层模型工作流的通知。

Workflow 软时间从内层模型 Agent invocation 开始，不包含外图 prepare/route、模型准备或人工等待。DearFlow/Showcase 现有子图使用 `exit_behavior="error"`，未处理限制异常会沿父图传播；真实并行案例父 Run 为 error。只有 child=end 或父图显式处理局部结果的场景才能继续，UI 必须展示真实父终态。

## 状态和文案矩阵（杜绝复读机拼接）

| 原生执行状态/通知 | 规范文案与格式 | 动作与控制约束 |
| --- | --- | --- |
| pending，无通知 | 现有排队态 | 不从排队耗时生成预算预警 |
| running + model approaching | Amber“模型调用额度接近上限”（附注：剩余调用 {n} 次，正在收尾）。**禁止拼接重复标题词条** | **必须保留显式停止/取消按钮**；不自动续跑或禁用合法审批 |
| running + graph approaching | Amber“执行步骤接近上限”（附注：剩余 {n} supersteps，正在收尾） | **必须保留显式停止/取消按钮**；使用superstep单位，不叫剩余工具次数 |
| running + wrapup_started | Amber“运行时间较长，正在收尾” | 不是timeout，不显示伪造倒计时；**保留取消按钮** |
| reached但原生Run仍running/待核实 | “已触发额度限制，正在确认运行结果” | 不提前清busy，不允许并发提交 |
| 原生success + primary reached/end人工消息 | “本次执行因额度限制停止，任务可能尚未完成” | 保留原生success作为传输事实，**打破现有组件隐藏门槛，严禁展示‘任务成功完成’或‘就绪’** |
| 原生success + 只有approaching | 正常完成，预算提示降为历史附注 | 不把预警升级为失败，也不推断任务已完全完成 |
| 原生error + 预算code (run级已证实) | “本次执行因额度限制停止，模型调用额度已耗尽” | run级提供“调整请求”，安全回填草稿供用户精简任务 |
| 原生error + 预算code (thread级已证实) | “本会话累计调用额度已耗尽” | **严禁引导重发当前会话**；提供“新建会话”或“在新分支继续”，输入框置灰禁用 |
| 原生error + 预算code (scope未知) | “因额度限制停止，任务可能尚未完成” | **严禁赋予 adjust_draft**；降级为 actionType="none"，不替用户决定续跑 |
| 原生timeout + runtime_run_timeout | 超时且结果可能待核对 | 不自动重复写工具或重试Run |
| 子图reached，父Run仍running/success | 对应子任务显示停止原因，卡片头部标记告警 | 不提前覆盖父Run状态；后续按原生终态核实 |
| 子图error沿父图传播，父Run真实error | 子任务显示归属原因，主图保留真实失败提示 | 不宣称父图继续；保留已完成子任务和现有消息 |
| 原生interrupt/HITL | 现有审批提示为主，预算为附注 | 继续使用interrupt ID和真实actions，不用resume实现预算续跑 |
| 用户取消 | 原生取消结果及核实状态 | 取消ACK不是终态；预算不能盖过取消或触发总结模型 |
| 网络EOF/重连 | 原有连接恢复态 | 不把连接错误当额度触限 |
| 401/403/明确撤权 | 原有认证/权限处理 | 同scope清预算缓存，不因暂时5xx清所有会话 |
| 旧Run迟到通知/重放 | 只更新旧Run的历史投影 | 不清新Run busy，不闪回旧告警 |

**单个Run主图优先级**：原生取消/权限/审批 > 已证实预算停止（reached / error安全码 / end标记） > 预警与软收尾（approaching / wrapup Amber） > 原生运行/就绪态。到终态后保留停止原因和已产生的消息/成果；子图独立投影。多维预警可简短归并，不堆弹窗或多张重复提示。

## 用户操作约束与动作分流

- **Run 级别限额（已证实 `budget_scope === "run"`）**：
  提供“调整请求”动作，安全提取用户上一条发言内容（兼容纯字符串与多模态数组内容块提取），回填至输入框；若当前输入框已有未发送草稿，**严禁使用粗暴的 `window.confirm`**，必须对接平台统一确认交互；引导用户缩减任务规模重新发送。
- **Thread 级别限额（已证实 `budget_scope === "thread"`）**：
  因服务端 checkpoint 计数器持久且不可逆，**严禁引导用户重发当前会话**！
  操作按钮分流为：**“新建会话”**（创建全新 Thread）或**“在新分支继续”**（调用既有合规分支 Fork 接口）；当前会话输入框发送按钮置灰禁用，并给出“会话累计额度已尽”提示。
- **SafetyError 降级（scope 未知）**：
  **严禁假定为 run 级而向用户提供 `adjust_draft` 重发**！动作固定为 `actionType: "none"`，输入框保持原有终态锁定，由用户明确决定是开新会话还是分叉分支。
- **通用约束**：
  - 新请求使用新幂等key，同动作网络重试保留原key；既有unknown提交结果先对账。
  - 只有当前Run已核实终态、具备comment/相应权限且不是Thread耗尽时，才能启用人工发送下一条请求。
  - 不自动增加recursion_limit、不清Thread计数、不生成临时新Thread绕过累计额度。
  - 审批只resume当前有效interrupt，不携带新的config/context；budget提示不授予任何权限。
  - 不接管未消费队列；原队列收据/取消/unknown状态继续按既有逻辑显示。

## UI 与组件交互规范

1. **`ChatAgentStatusBar.vue` 显隐、文案与控制重构**：
   - 现存组件仅有 `v-if="isInterrupted || error"`，**导致原生 success 停机和运行中 approaching 预警被错误隐藏**。
   - 必须扩展 props 接收 `budget?: BudgetViewModel | null`，显隐条件改为：
     ```html
     v-if="isInterrupted || error || budget"
     ```
   - **控制按钮保留要求**：当 Agent 处于 running 状态且触发 approaching/wrapup 预警时，**必须保留右侧“取消”按钮**，严禁因预警而隐藏控制按钮！
   - **文案解耦**：彻底杜绝复读机拼接！组件采用单一清晰的格式：若为预警态，直接展示 `budget.title + "（" + budget.description + "）"` 或纯说明文案，避免重复词条。
   - 状态栏视觉层级：
     - **预警中（approaching / wrapup_started）**：背景 `bg-amber-50`、边框 `border-amber-200`、文字 `text-amber-800`，图标带动画提示。
     - **限制停止（reached / 预算安全错误码）**：背景 `bg-red-50` 或警告红棕色，明确提示“因额度限制停止，任务可能尚未完成”，并根据 Run/Thread 渲染对应的分流动作按钮。
2. **`SubagentCard.vue` 与 `SubtaskDetail.vue`（子任务展示）**：
   - **生命周期合规**：**严禁在 `SubagentCard.vue` 模板或条件表达式内使用三元运算符调用 Composable**（违反 Vue Composition API 规范）。子任务卡片应基于轻量派发或在稳定顶层订阅。
   - `SubagentCard.vue`：在折叠态头部（Header Badge/Status）联动子任务预算状态。若该子任务 namespace 产生 approaching 预警或 reached 停止，在卡片未展开时即展示微胶囊 Tag，防止用户遗漏子任务异常。
   - `SubtaskDetail.vue`：在展开后的详情顶部，渲染一个轻量级的子任务预算通知横条（SubtaskBudgetNotice），仅作用于当前 namespace。
3. **可访问性与响应式**：
   - 增加 `aria-live="polite"` 支持，仅对首次新通知播报；历史重放/重复帧不重复 announce。
   - 软预警与 fatal 使用不同颜色和独立语义图标，不得仅依赖颜色区分。
   - 360/390px 视口下长文案自适应换行，操作按钮不遮挡输入区与审批按钮；不添加虚假进度条。

## 同事验收清单

| ID | 场景与必须验证的结果 |
| --- | --- |
| H01 | 正常Run不显示预算误报，原Chat路径不变 |
| H02 | 模型approaching/reached逐一显示且去重（真正 200 条 LRU 有界去重，增量解析无卡顿），不扫描消息文本 |
| H03 | 极低recursion没有custom也通过安全错误code显示图上限；scope未知时不提供重发草稿动作 |
| H04 | end路径success仍解释额度停止，保留已有模型/工具消息；文案无复读机重复词条 |
| H05 | thread额度耗尽不出现可用的一键继续或提高配额动作，输入框禁用，提供新建会话/分支引导 |
| H06 | wrapup_started仍显示running且**保留取消按钮**；实际hard timeout由原生状态收敛 |
| H07 | 子图通知归属准确、namespace不串（响应式 target 动态适配）；child=end 时可继续，DearFlow/Showcase child=error 时尊重真实父Run error，不承诺必继续 |
| H08 | 串行r1/r2与迟到r1事件，r2 busy和当前提示不被清掉；新Run启动时不被历史旧Run停机标记闪烁覆盖 |
| H09 | 重连/事件重放去重；custom消费没有第二个controller或独立物理SSE，无重复订阅膨胀 |
| H10 | 刷新、历史Run、410降级；Run GET无error不报错，不能从最新Thread.error归因旧Run；有结构化停止原因才显示 |
| H11 | HITL保持审批ID/动作，取消仍需核实，预算不触发模型补总结 |
| H12 | 暂时网络/5xx保留有效快照；真实撤权、登出、换项目清正确scope |
| H13 | 合法 null 显示未知；非法数值/未知version或code/过长ID整条忽略，normal消息保持；支持多层嵌套 payload 安全解包 |
| H14 | “调整请求”草稿回填处理多模态content、规避原生`window.confirm`、unknown幂等对账、双击不重复发送 |
| H15 | 360/390/768/1440视口无重叠；键盘和屏幕阅读器可用（aria-live="polite"首次有效播报）；重放无重复播报 |
| H16 | `pnpm test:run`与`pnpm check`通过，四正式graph（含Workflow内层primary通知）真实三服务浏览器证据有回执 |

## 后端交接包与回执

Runtime/API 已交付四类通知、四类硬错误、end 人工消息标记、run/thread 耗尽、委派子图 namespace、普通 v2/Protocol/v3 回放和 410 样例。安全文件见 [`implementation/budget-http-evidence.json`](implementation/budget-http-evidence.json)，字段位置和联调入口见[前端交付报告](frontend-delivery-report.md)。Workflow root writer 有真实 compiled graph 组合测试证据，四 graph HTTP 正常请求均通过；浏览器仍需同事验收。

同事回执填写：实现版本 `待填写`、H01-H16结果 `待填写`、浏览器证据位置 `待填写`、SDK订阅数量对照 `待填写`、剩余问题 `待填写`。前端完成不直接等于全项目 done，最终结论见 verification.md 的 Final-B。
