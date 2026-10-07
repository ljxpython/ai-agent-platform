# Agent 运行生命周期超时治理 - 前端交接

> 面向承接同事。2026-10-07详细交接版：GraphHarbor post42正式双包已发布，当前worktree已锁定/安装，正式包HTTP与回退证据见 [验证记录](verification.md)。前端源码未修改，F01-F10由同事承接。任务进度以 [T11/T12](tasks.md) 为准。

## 1. 前端要做什么

目标是让用户准确看到上一回合超时、当前仍在执行、等待审批或提交结果未知，并保留已有消息/产物。Run 的计时、硬终止与持久状态由 Runtime Worker 实现；前端消费服务端事实。

现有 `useChatSession.ts` 已将 timeout 视为终态，并有“上一回合执行超时”文案，但 `ChatSession.vue` 只在 sr-only 区引用它，普通用户未必看得到。`stop()` 使用默认停止ACK，再由 `verify(true)` 把非active状态视为结束，最后无条件清 `cancelling`；post42公开interrupted可以早于执行清理，这条流程必须适配。`useFollowUpSuggestions.ts` 目前只看运行结束、最后一条AI消息和用户停止标记，没有区分success与timeout/error；须补成功门禁。`useSessionConnection.ts` 已有SDK重连/410恢复，恢复和队列部分以回归为主。

用产品语言说，同事要处理三件事：超时后页面停止显示“处理中”，已输出内容和产物仍能查看且可以开始下一回合；断网、切会话或刷新后查回原来的运行，不重复发送；点击停止后先显示“正在停止”，确认执行已经结束才显示“已停止”，并与“执行超时”“等待审批”区分。主要工作在现有聊天状态、文案和测试，保持现有布局。

本期没有超时配置表单、倒计时、新页面或 `wrapping_up` RunStatus；没有新增 custom SSE 提醒事件。收尾指令是模型 system prompt，不要求前端显示 prompt。模型在收尾窗口正常给出回答时仍可能 success，但回答可包含未完成事项，UI 不把 success 显示为“业务目标全部完成”。

先读 [前端playbook](../../../apps/platform-web/docs/frontend-development-playbook.md)、[控制面规范](../../../apps/platform-web/docs/control-plane-page-standard.md)、[视觉基线](../../../apps/platform-web/docs/frontend-visual-baseline-standard.md)。第4节给出源码落点，第7节给出实施顺序。完整 `apps/...` 路径以仓库根为基准，表格中的 `src/...` 路径以 `apps/platform-web/` 为基准。

## 2. 时间和状态语义

后端按官方 Worker attempt 计时：每次 Worker 领取开始 H，同一 Run 因数据库故障重试/Worker 接管获得新 attempt H，并从当前 Run checkpoint 继续。排队/退避/停机不累计；浏览器重连不会重新领取或刷新预算。HITL 结束原 Run，审批 resume 创建新 Run/预算。跨 attempt/跨 Run 的累计总限不在本期。

交付回执中的H指一次Worker attempt的硬限，G指硬限前预留的收尾窗口，M指单次模型调用限时；它们由服务端配置，前端不生成、不倒计时。

收尾窗口是硬截止前 G 秒，软提醒不保证模型遵守。跨过软窗口时若没有后续模型请求，可能直接 timeout，没有最终总结。已确认消息、完整 checkpoint 和已提交产物应保留；未完成写入/外部操作结果不能靠 timeout 推断。

| 服务端/客户端事实 | 展示与动作 | 禁止误判 |
| --- | --- | --- |
| Run `pending/running` | 沿用当前等待/执行状态；有执行权限时可停止 | 浏览器计时到期不等于服务端 timeout |
| Run `timeout`，reason `timeout` | 保留“上一回合执行超时”或同义文案；核实目标 Run 后释放其 busy，保留消息/产物 | 不是普通断流，也不是自动重试指令 |
| Run `error`，模型 scope 耗尽 | 执行失败，可显示安全“模型调用超时”信息；整体状态仍是 error | 不改为整体 Run timeout；不依赖字符串包含 TimeoutError 判类别 |
| Run `interrupted`，reason `hitl_interrupt`，state 有 interrupts | 展示等待审批/补充信息，按既有权限处理 | 不因等得久了自动批准或允许普通发送越过审批 |
| Run `interrupted`，reason `cancel_requested` | 停止已受理；在清理尚未确认时保持“正在停止/待核实”，确认后显示已停止 | 不是 HITL；仅 GET status 不证明模型/工具已退出 |
| 目标 Run 的终态事件 `execution_stopped=true`，或平台 cancel JSON body `wait=true` 成功 | 可确认受支持执行已停止；仍保留消息/已提交产物，并核对 run_id | `execution_stopped=false/lease_fenced=true` 只表明旧执行已被禁止继续持久写入，不等于进程或外部任务已退出 |
| SDK lifecycle 的 `completed/failed` 等 event label | 沿用 SDK 适配，再核对 Run JSON status | event label 不能覆盖服务端 timeout/error |
| SSE EOF/AbortError/410/HTTP 请求超时 | 保留上下文，按现有方式查询同一个 Run 并恢复订阅 | 不是任务超时；不创建新 Run 或调用 cancel |
| 发送动作 `unknown` | 保留原动作、幂等键与请求内容，先核实 | 不因旧 Run timeout 自动把未知动作重新发送 |

`reason` 是当前 GraphHarbor 的公开扩展字段，SDK `Run` 类型可能不包含它；必要时使用局部类型扩展与安全解析，不用 `any` 扩散。审批事实同时以现有 state/interrupts 为准，不让迟到事件复活旧审批。

模型/provider 超时由图内已有 retry/fallback 处理；未恢复则 Run 为 error，Worker 不自动重跑整张图。数据库瞬时故障才会使同一 Run 暂回 pending/running 并开始新 attempt；当前 attempt 硬限触发 timeout。前端以最终 Run 状态为准，不凭一次流内异常提前释放 busy 或发起新回合。

## 3. 现有接口与认证

Base URL 由 `getLanggraphApiUrl()` 生成，对应 `/api/langgraph`。复用 `createLanggraphAuthorizedFetch()` 和 `createSessionService()`：`Authorization: Bearer <platform-access-token>`、`x-project-id` 沿现有流程传入，不直连 Runtime、不让浏览器持有 Delegation JWT 或内部预算。

| 操作 | 现有路径与接入方式 |
| --- | --- |
| 提交/审批 | 官方 SDK 的 `POST /api/langgraph/threads/{thread_id}/commands`，经 `run-actions.ts:platformCommand/createRunActions`；保持同一动作的 `Idempotency-Key` |
| 创建/排队/恢复 Run | `POST /api/langgraph/threads/{thread_id}/runs`；`session.service.ts:resume` body 为 `{"command":{"resume":{"<interrupt_id>":"<response>"}}}`，实际 response 沿当前审批契约 |
| 查询目标 Run | `GET /api/langgraph/threads/{thread_id}/runs/{run_id}`；`service.run(threadId, runId)` |
| 会话 Run 列表 | `GET /api/langgraph/threads/{thread_id}/runs`；`service.runs(threadId)`，列表不能随意覆盖已知目标执行 |
| 订阅/恢复 | 原 SDK Protocol 或 `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/stream`；沿用已有游标与 410 恢复，`cancel_on_disconnect=true` 当前被平台拒绝 |
| 受理停止 | `POST /api/langgraph/threads/{thread_id}/runs/{run_id}/cancel`；保留既有 `service.cancel`（SDK `wait=false, action=interrupt`，平台成功为 `200 {"ok":true}`）用于非阻塞受理，不破坏已有测试 |
| 确认停止 | 同一路径，使用既有授权 `read` 新增窄方法 `cancelAndWait`，**JSON body** `{"wait":true,"action":"interrupt"}`；平台 `200 {"ok":true}` 此时才意味着上游已确认停止，失败/网络超时保持待核实 |
| 状态/历史/产物 | 复用 `service.state/history` 与已有工作区/产物服务；恢复先读 state，history 后台/按需加载 |

默认停止成功只说明请求被接收。GraphHarbor post42允许先持久化 `interrupted/cancel_requested`，再异步清理执行；现有 `stop()->verify(true)` 若仅检查这个 status，会过早释放停止状态，需要同事补齐确认流程。在 `session.service.ts` 明确新增窄方法 `cancelAndWait(threadId, runId)`，使用内部授权 `read` 发送 JSON body `{"wait": true, "action": "interrupt"}`，不直连 Runtime、不在组件里写网络请求。

注意接口层次：原生 GraphHarbor `wait=false` 是 HTTP202空body，原生 `wait=true` 成功是200/null，未确认是503；平台SDK适配器保持既有200 ACK，原生503按当前错误标准对外映射502，网络等待超时为504。**平台cancel路由读取JSON body，不转发SDK query的wait/action；不能通过把现有JS SDK的wait参数改为true来完成确认。** 非2xx或EOF不能作为已停止。文案可用“停止结果待确认”，保留同一run_id核实；不声称远端供应商操作已撤销。再次核实必须执行**双通道容错**（先查目标 Run 状态，已终态则直接收敛，避免对已停止 Run 重复 cancel 触发 400/409 报错死锁）。

当前 timeout GET 示例，省略其他既有字段：

```json
{
  "run_id": "b41b8f94-1fc0-4aae-8b70-14a9e97ea1ab",
  "thread_id": "1236e56e-853c-4d4d-90cd-f8a8dd0b22d7",
  "status": "timeout",
  "reason": "timeout",
  "metadata": {}
}
```

本期没有 `metadata.execution_budget` 或其他公开预算字段。客户端不能提交 `__graphharbor_run_budget`、monotonic 值或收尾 system prompt；现有接口已拒绝注入并过滤私有数据。前端无需新增预算类型、计时器或配置项。

`ModelCallTimeoutError` 已实现为 Runtime 内部错误类型，未新增全局 HTTP error code，也未承诺前端一定能读取该 Python 类名。复用已有 `extractPlatformHttpError/formatPlatformHttpErrorMessage`；有安全可识别信息时显示模型调用超时，否则用现有执行失败说明。不能把所有 408/504/provider timeout 翻译为 Run 超时。

验收入口为 `scripts/verify_run_timeout_budget.py`：普通/软收尾/硬超时、模型失败、HITL、真实Worker新attempt、三Thread、SSE、取消竞态、排队/G=0/防注入。测试H=30/G=10，重启接管新H=20/G=5；正式双包为 `graphharbor=graphharbor-runtime=0.13.0.post42`，锁文件已升级，独立PyPI安装环境为 `/tmp/run-budget-pypi-post42-venv`。当前结果见 [verification](verification.md) 新Phase与 [原始证据](evidence/README.md)，10-06旧deadline结果不得复用。浏览器联调应启动此worktree匹配的Runtime/API，现有8123/2142/3000共享服务未被本会话升级，不能把它们自动当作本次联调环境。

后端隔离脚本运行结束会退出临时服务，不是常驻浏览器联调环境。开始F02/F04/F06/F07/F08时，由联调负责人按现有本地启动规范选择独立端口并核对API/Worker都加载post42和当前Runtime源码；低H测试必须同步设置合法G（如H=30/G=10）。不在共享现役环境执行清库脚本或秒级硬限试验。

## 4. 具体改动位置

| 文件 / 符号 | 同事要检查或补充 |
| --- | --- |
| `apps/platform-web/src/services/threads/session.service.ts:createSessionService/read/run/cancel/cancelAndWait/resume` | 必改停止调用：保留既有轻量 `cancel` 不破坏单测，新增显式窄方法 `cancelAndWait`，复用内部授权 `read` 发送 JSON body `{"wait": true, "action": "interrupt"}`，包含 project header 与路径转义，断言错误解析与不直连 Runtime |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts:busy/status/turnState/verify/stop/verifyStop/scheduleBackgroundRunPoll/resumeInterruptedRun` | 必改状态收敛：导出单一事实源 `SessionTurnState` 联合类型消灭布尔地狱；`stop()` 调用 `cancelAndWait`；核实停止执行双通道容错（先查状态，已终态直接收敛，仍 active 才重发 cancelAndWait，防 400/409 死锁）；`resumeInterruptedRun` 严禁恢复 `cancel_requested`；verify/poll 严防迟到结果篡改 |
| `apps/platform-web/src/modules/chat/composables/useSessionConnection.ts:recoverExpiredStream` | 断流/410 后同 Run 查询/rejoin；保持 state 优先，history 不阻塞恢复；重连不调用 run.start |
| `apps/platform-web/src/modules/chat/composables/useSessionInterrupts.ts` | stopped 与 HITL 分开，只有有效 interrupts 可审批；新 resume Run 不读取旧预算 |
| `apps/platform-web/src/modules/chat/run-actions.ts:platformCommand/createRunActions` | `unknown` 原动作与幂等键保留，恢复不篡改 body/预算；确认终态不能等同提交新动作 |
| `apps/platform-web/src/modules/chat/components/ChatSession.vue:turnState/handleStop/handleVerifyStop/send` | 必改展示接入：将 `turnState` 统一下发至状态条、Composer 及滚动浮条；浮动停止按钮和 StatusBar 均接入 `handleStop` 与 `handleVerifyStop`；执行类 send/queue 均接入待核实守卫 |
| `apps/platform-web/src/modules/chat/components/ChatAgentStatusBar.vue:turnState/statusText/statusIcon` | 重构展示门禁（打破原 `v-if="isInterrupted || error"` 限制）：支持 `timeout`（黄警示胶囊）、`stopping`、`stop_unconfirmed`（带【核实停止】按钮）、`interrupted`（HITL 带【查看审批】按钮）、`stopped`；隔离 `cancel_requested` 与审批；适配 390px 移动端不挤爆 |
| `apps/platform-web/src/modules/chat/components/ChatComposer.vue:canSubmitFreshOrQueue/handleKeydown` | 停止进行中与待确认期间，全量禁用发送、Enter 键和队列入口（`canSubmitFreshOrQueue` 顶层一票否决，禁止 `canQueue` 绕过），输入框仅允许纯文本编辑草稿 |
| `apps/platform-web/src/modules/chat/composables/useServerPromptQueue.ts/usePromptQueue.ts` 与 `components/QueuedMessagesBanner.vue` | 沿持久队列专项选当前有效实现；timeout 后保留未消费/未知回执，不在本项目重写 FIFO |
| `apps/platform-web/src/modules/chat/composables/useFollowUpSuggestions.ts:triggerForCompletedTurn` | 必补 success 门禁且时序解耦：消除流结束瞬间 `verify(true)` 尚未完成导致误杀正常推荐的时序漏洞；仅在权威证实目标 Run 为 `success` 终态且未被中断时触发；timeout/error/停止/未知终态严禁按半截 AI 消息触发推荐 |

基线测试入口：`session.service.spec.ts`、`useChatSession.spec.ts`、`ChatAgentStatusBar.spec.ts`、`ChatComposer.spec.ts`、`useSessionConnection.spec.ts`、`useSessionInterrupts.spec.ts`、`useFollowUpSuggestions.spec.ts`、`usePromptQueue.spec.ts`、`QueuedMessagesBanner.spec.ts`、`run-actions.test.ts`、`sdk-stream-recovery.test.ts`、`sdk-chain.test.ts`。后者部分是实际SDK联调测试，不能把没有配置时的skipped当作通过。

设计要求见第7.2节：沿用现有状态条、审批卡、消息展示和BaseIcon，不新增页面或设计体系。新增说明只描述真实状态；未验证保存时避免“所有进度已保存”。

## 5. 同事验收清单

| 编号 | 操作 | 验收条件 |
| --- | --- | --- |
| F01 | 普通短任务与进入软窗口后正常回答 | 无无关提示，普通回答/工具/产物保持；success 不被标成 timeout |
| F02 | 真实 Worker 硬超时，保留一段已输出内容与产物 | GET 为 timeout 后目标 Run busy/处理指示结束；可继续新回合；内容与已提交产物可读；无最终报告也可正确展示 |
| F03 | 模型 scope/provider 超时、数据库 retry/Worker接管、HTTP 504/断流 | 模型未恢复为error、硬限为timeout；DB retry的pending/running保持busy；同Run新attempt继续；网络异常先核实，不自动重发 |
| F04 | deadline临界点点击停止，多次点击；另用清理阻塞/停止确认失败场景 | 复用已知run_id；平台默认ACK与GET interrupted不冒充已停止；等待确认时仍可显示到来的消息；失败后能再次核实；确认后按真实timeout/success/interrupted收敛，不强改已停止 |
| F05 | A/B/C 三个会话并行；A timeout 时切到 B；新 B Run 启动后接收旧终态 | B/C 不受影响；旧 run_id/旧校验结果不覆盖当前执行；切回 A 显示一致状态 |
| F06 | SSE EOF/410/离开页面后恢复，期间服务器已 timeout | 同一个 Run 回查/rejoin，状态与历史恢复；网络日志无额外 run.start，新预算未生成 |
| F07 | HITL 等待超过 H 再人工批准 | 审批卡仍有效，未自动批准；resume 新 Run 正常启动；停止回合不显示为等待审批 |
| F08 | 收尾窗口提交补充消息，制造未消费/ACK 未知 | 各回执状态保留；不误报已消费、不自动作为新请求重发；现有人工恢复草稿/发送动作保持幂等 |
| F09 | 初始 pending 等待超过 H；timeout 后立即启动新回合 | 排队不被前端提前 timeout；新 Run 独立；旧错误/推荐问题/旧预算不附着到新回合；timeout/error/停止后的部分回答不触发推荐请求 |
| F10 | 无公开预算字段、桌面/390px移动、权限刷新 | 使用既有 Run 状态正常工作；文案不遮挡按钮或内容；现有权限/登录、连接恢复与停止行为不回退 |

F02/F04/F06/F07/F08 至少在真实隔离后端上联验，不能仅使用 mock 的 timeout 消息。Playwright 证据包含截图/trace、网络请求计数与 run/thread/request_id，后端提供对应终态与取消/资源证据。

## 6. 命令与交付回执

在 `apps/platform-web/` 执行，以下命令是同事实装后的验证入口，本轮未执行：

```bash
pnpm test:run src/services/threads/session.service.spec.ts \
  src/modules/chat/composables/useChatSession.spec.ts \
  src/modules/chat/composables/useSessionConnection.spec.ts \
  src/modules/chat/composables/useSessionInterrupts.spec.ts \
  src/modules/chat/composables/useFollowUpSuggestions.spec.ts \
  src/modules/chat/composables/usePromptQueue.spec.ts \
  src/modules/chat/components/ChatAgentStatusBar.spec.ts \
  src/modules/chat/components/ChatComposer.spec.ts \
  src/modules/chat/components/QueuedMessagesBanner.spec.ts \
  src/modules/chat/run-actions.test.ts \
  src/modules/chat/sdk-stream-recovery.test.ts
pnpm typecheck
pnpm lint
pnpm build
# 下列文件由同事按既有 e2e 范式补充，当前不存在
PLAYWRIGHT_BASE_URL="http://127.0.0.1:<web-port>" pnpm test:e2e e2e/run-timeout-governance.spec.ts --trace on
```

交付回执填写：代码版本与改动文件、后端正式包版本、H/G/M、F01-F10逐项结果、失败/未执行原因、浏览器截图/trace及后端 run_id 对应证据。同步本项目 T11 与 verification Phase；完整范围联验后再写 Final。前端同事无需接手计时 Worker、依赖发布或 Runtime middleware 实现。

本轮 worktree 为 detached HEAD，基点 `0bc15df1840c83750d821c93fb65600d0d483fa4`，没有开发分支或提交；接手代码时不要把该基点当成包含本轮修改的已提交版本。项目实际入口为 `docs/projects/20261006-agent-run-timeout-governance/README.md`，本交接为同目录 `frontend-handoff.md`。

## 7. 接手即执行的开发稿

### 7.1 先确认边界

前端这次负责把后端已经提供的Run事实投影到聊天页面，区分“停止已受理”和“执行已停止”。这两个阶段可以在一个wait=true请求中完成，不要求额外增加一次默认cancel请求。必须完成：

1. 超时 Run 可见、可回查、可继续发送；已完成消息和已提交产物仍可读。
2. 停止按钮只操作当前目标 `thread_id/run_id`；收到 ACK 或 `interrupted/cancel_requested` 时仍显示停止中，直到确认执行确实结束。
3. timeout、模型调用 error、HITL 等待、用户停止、网络未知分别展示，且不能互相触发自动 retry、自动 resume 或新 Run。
4. 切换会话、刷新、SSE EOF/410、后台轮询和多个操作入口都遵守同一目标 Run 与 epoch 校验。
5. **消灭布尔地狱**：由 `useChatSession.ts` 导出单一事实源的 `SessionTurnState` 强类型联合类型（`idle` | `running` | `stopping` | `stop_unconfirmed` | `stopped` | `timeout` | `awaiting_review` | `error`），禁止各组件散落拼接互相冲突的布尔变量。

现有审批卡、消息队列、断流恢复和权限刷新以回归为主；推荐问题补成功门禁并与 `verify(true)` 完成态时序对齐，其他实现按第4节的明确缺口修改。沿用官方SDK的live投影，仅在固定会话的composable中保存目标Run的停止请求/确认展示状态，不能建立另一个运行表或全局Run状态机。浏览器倒计时、强杀、预算配置、`wrapping_up`、新页面和新SSE事件不在本期。

### 7.2 用户看到的状态

以下文案是建议基线，可按现有语气微调，但同一事实必须在状态条、输入区按钮和 `aria-live` 中一致。状态条 `ChatAgentStatusBar.vue` 必须重构其展示门禁（移除旧有 `v-if="isInterrupted || error"` 限制，改由 `turnState` 或完整 props 驱动），支持超时、停止中和待核实的独立可见性。

| 状态 (`SessionTurnState`) | 用户可见内容 | 可用动作 |
| --- | --- | --- |
| `running` (`pending/running`) | “Agent 正在执行...”和停止按钮 | 停止；输入框不可发送或按既有队列规则处理 |
| `stopping` (停止确认请求进行中) | “正在停止...”并禁用重复停止入口 | 草稿可继续编辑，提交/入队/Enter全量禁用；仍消费到来的有效消息 |
| `stop_unconfirmed` (确认请求失败/断开，或恢复后仅知`cancel_requested`) | “停止结果待确认” | 显示“核实停止”按钮；请求结束后按钮可再次点击；不显示审批，不自动恢复 |
| `stopped` (已确认退出，目标确为`cancel_requested`) | “已停止” | 恢复既有权限允许的发送；保留旧消息、产物和原因；新Run启动后旧状态自动淡出 |
| `timeout` (`status=timeout, reason=timeout`) | “上一回合执行超时，已完成的内容已保留” (黄色警示胶囊) | 可发送新回合；输入框恢复可用；不展示多余操作按钮，不能伪造最终报告 |
| `error` (模型/provider `error`) | 现有安全执行失败文案；有可靠信息时补“模型调用超时” | 按既有错误动作处理；不改成 Run timeout |
| `awaiting_review` (HITL `interrupted` 且有 `interrupts`) | “等待审批”或“等待补充信息” | 沿用审批/补充动作与权限；不自动批准，不把用户停止套成审批 |
| 网络 EOF、410、502、504 或未知提交结果 | “连接/提交结果待确认” | 同一 Run/原动作核实；不新建 Run、不重发 input |

按钮、输入框和顶部状态共享同一composable的派生结果。停止请求待确认（`stopping` / `stop_unconfirmed`）锁死当前会话所有执行类提交动作（Send、Queue、Enter），不阻止编辑草稿、查看产物或切到其他会话。所有“可以发送”都仍受权限、有效审批、unknown提交动作及现有队列规则约束。

视觉沿用现有`pw-panel*`反馈与BaseIcon：等待使用现有加载图标，待核实/超时使用现有警告反馈，error沿用错误反馈。仅在当前回合相关状态显示紧凑一行或自然换行的说明，新的Run启动时旧提示退回历史上下文；不要持续叠加多个横幅。浅/深色、1440px桌面与390px移动均需检查，长文案自然换行，按钮尺寸稳定且不遮挡内容；图标有tooltip/aria-label，`aria-live`只播报状态变化。

### 7.3 停止流程必须这样走

最小实现是保留现有 `service.cancel`（轻量 ACK 调用）不变，在 `session.service.ts` 内部复用授权 `read` 增加窄确认方法 `cancelAndWait`。调用以下接口即可请求取消并等待确认，不必强制先发 wait=false：

`POST /api/langgraph/threads/{thread_id}/runs/{run_id}/cancel`

```json
{"wait": true, "action": "interrupt"}
```

具体时序：

1. 从当前 action 快照或 `run.value` 取目标 `run_id`，同时保存 `thread_id`、项目/用户作用域和当前 verify epoch。
2. 通过既有 edit 权限与 visible/disposed 守卫后，立刻显示停止中（`SessionTurnState = "stopping"`）并调用 `service.cancelAndWait`；请求进行中禁止重复点击。只需沿用现有 guard，不必增加 Promise 池或新依赖。
3. 若保留原 wait=false 路径，其 `200 {"ok":true}` 只算受理，随后仍须确认。无论哪条路径，GET `interrupted/cancel_requested` 或 `execution_stopped=false/lease_fenced=true` 都不能过早清掉停止待确认状态。
4. `cancelAndWait` 成功返回 200，或当前 SDK 确实可消费的目标 Run `execution_stopped=true` 终态事件，才提供退出确认。随后核对目标 Run 的真实 status/reason：若 timeout 或自然 success 抢先结束，展示超时/完成，不强改为“已停止”。
5. 502/503/504、AbortError、EOF 和解析失败结束本次 HTTP 等待，但保留目标与待核实展示（`SessionTurnState = "stop_unconfirmed"`），恢复“核实停止”按钮；**再次点击“核实停止”必须采用双通道容错机制**：
   - 首先调用 `service.run(threadId, runId)` 查询目标 Run 服务端最新真实状态；
   - 若此时服务端返回已是非 active 终态（`status === "interrupted"` 且 `reason === "cancel_requested"`，或者已被超时/完成收敛），**直接就地收敛至终态并清除待核实状态**，彻底避免对已结束的 Run 重复调用 cancel 触发服务端 400 Bad Request / 409 Conflict 报错死锁；
   - 仅当目标 Run 依然处于 `pending` 或 `running` 时，才再次发起 `cancelAndWait` 阻塞等待。
   - `finally` 可以清本次请求 loading，不能清退出未确认事实。401/403 按现有鉴权与作用域撤权处理，不自动重试写操作。
6. 每次异步返回沿用会话身份、thread、run 及 epoch 校验；旧 Run 的迟到确认不能改变新 Run。页面刷新/410 恢复后若发现 `cancel_requested`，应重建该 Run 的待核实展示，不能因本地 loading 丢失就显示已停止或审批。
7. **拦截自动恢复**：`resumeInterruptedRun()` 必须显式增加前置校验 `currentRun.reason !== "cancel_requested"`。对于用户主动取消的 Run，绝对禁止调用 `service.resume` 重新拉活。

平台 cancel 路由读取 JSON body，不转发 SDK query 参数；只把 SDK wait 改为 true 不能完成确认。SDK 是否暴露停止事件字段由同事核对，缺字段时使用 JSON 确认，不改 SDK 内部或手写 SSE 解析器。核实停止不能复用 `retry()` 或 `resumeInterruptedRun()`；前者可能重发 input，后者会创建 resume Run。泛 interrupted 的既有人工继续能力仍保留，只有有效 state interrupts 走审批。

不能只改 `stop()`：`verify()` 当前会在非 active 时清 loading，后台 poll 当前只跟踪 active，`busy` 也可能提前收敛。三处都必须识别仍待确认的目标停止动作；用现有校验/轮询调度承接，不新增第二个轮询器。停止等待期间有效消息与已提交产物仍可更新，禁止仅为消除 spinner 而提前 disconnect 或清空 SDK 状态。

### 7.4 代码落点和顺序

按下面顺序开发，每一步先补最小回归再进入下一步：

| 顺序 | 文件/符号 | 交付内容 |
| --- | --- | --- |
| 1 | `src/services/threads/session.service.ts`、`session.service.spec.ts` | 保持既有 `cancel` 不动；新增窄方法 `cancelAndWait`，复用内部授权 `read` 发送 JSON body `{"wait": true, "action": "interrupt"}`；断言 JSON body、project header、错误状态和不直连 Runtime |
| 2 | `useChatSession.ts`、`useChatSession.spec.ts` | 导出单一事实源 `SessionTurnState` 联合类型消灭布尔地狱；`stop()` 调用 `cancelAndWait`；实现“查状态优先”的双通道核实停止函数（防 400/409 死锁）；`resumeInterruptedRun` 拦截 `cancel_requested`；覆盖 verify/poll/busy/finally 及 A 旧确认晚于 B 新运行 |
| 3 | `ChatAgentStatusBar.vue`、`ChatSession.vue`、`ChatComposer.vue` 及组件 spec | 重构 StatusBar 展示门禁（支持超时黄色胶囊、停止中、待核实、已停止）；Composer 全量封锁 stopping/stop_unconfirmed 期间的 Send、Enter 与 Queue 提交入口；移动端 390px 布局不塌陷 |
| 4 | `useSessionConnection.ts`、`useSessionInterrupts.ts`、`run-actions.ts` | 断流回查同一 Run；停止与 HITL 分离；unknown 原动作、幂等键、body 保持；不引入新状态机 |
| 5 | `useFollowUpSuggestions.ts`、`usePromptQueue.ts`、`QueuedMessagesBanner.vue` 及已有回归 | 补 success 门禁且时序解耦：推荐请求必须延迟至 `verify(true)` 证实目标 Run 为 `success` 终态后触发；消除流结束瞬间误杀正常推荐的竞态；timeout/error/停止不生成推荐 |
| 6 | `e2e/run-timeout-governance.spec.ts` | 使用真实隔离 post42 服务完成 F01-F10 中 F02/F04/F06/F07/F08，补桌面 1440px 和移动 390px；记录请求计数、run/thread/request_id、截图和 trace |

上述缩写文件均对应第4节的完整路径；测试位于同名源码旁。每一步沿用官方SDK controller、`createLanggraphAuthorizedFetch`、`extractPlatformHttpError`和现有组件tokens；字段用局部类型与安全解析。先补七类有效断言：JSON wait body/授权header、ACK或GET interrupted不冒充已停止、核实停止先查状态防400/409、迟到A不影响B、timeout可见且新回合可发、非success不发推荐请求、流结束到verify完成期间不误杀推荐。

### 7.5 验证与联调条件

前端实际锁定的是 JavaScript SDK `@langchain/langgraph-sdk@1.10.2`、`@langchain/vue@1.0.35`；GraphHarbor 正式包为 `graphharbor=graphharbor-runtime=0.13.0.post42`。共享现役服务仍是旧安装，不能作为本专项浏览器证据。联调负责人须使用本 worktree 对应源码和 post42 的独立 API/Worker、PG、Redis、工作区和端口，先核对启动日志中的版本与 `H/G`，再执行真实用例。

验证命令统一见第6节。Playwright已有配置默认只启用Desktop Chrome，移动视口需在新spec中显式设置；真实平台fixture可参考`e2e/support/platform.ts`与`e2e/sse-event-contract-real.spec.ts`。新spec尚不存在，须由同事实现并配置自己的真实环境开关；skipped不计通过。测试应通过正常Chat操作验证页面，不仅在page.evaluate里调用接口。

没有真实隔离服务时，先完成步骤1-5的单测和静态检查，F02/F04/F06/F07/F08记为未执行。低H测试先由联调负责人核对合法`G`，如`H=30,G=10`。页面草稿/用户正文/token不写入公开证据；保留必要的Run/请求ID与状态即可。

### 7.6 交付回执模板

前端同事完成后，在本项目 `tasks.md` 的 T11 和 `verification.md` 的 Phase 区块回填以下内容，再交给联合验收：

```text
代码版本/改动文件：
前端 SDK 版本：
联调 API/Worker/GraphHarbor 版本：
H/G/M 与隔离资源：
F01-F10：逐项通过/失败/未执行及原因
关键证据：截图、Playwright trace、请求计数、run_id/thread_id/request_id
停止确认：ACK、interrupted、execution_stopped、502/504 各自表现
未解决问题与回滚方式：
```

只有 F01-F10 有真实证据后，T11 才能标记完成；随后由后端和前端共同执行 T12 Final。交接文档本身不等于前端开发完成。
