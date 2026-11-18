# AI 网关预算控制与财务熔断任务进度

> **进度唯一来源：** 在原任务中更新状态、勾选、证据和剩余工作；README 仅作摘要。
> **2026-11-18：** 用户已追加 Worktree 后端实施授权，前端交同事开发。保留 Task 1–5 编号和原验收范围，未授权提交或发布。
> **环境：** `ai-agent-platform-gateway-budget` / `feat/gateway-budget-and-governance` / `wt_1c4f0f7fb905`；测试只连接所属数据库。

## Task 1：预算策略、权限与受信控制面契约

管理员需要为当前租户或某个项目设置 USD 日 / 周 / 月预算，并明确保存后何时生效。Platform API 负责规则、权限和审计，Runtime 使用受信规则执行，不接受浏览器伪造的 tenant、费用或预算绕过参数。

**状态：** 已完成（done）。责任服务：platform-api；runtime-service 配合冻结契约。

**任务清单：**
- [x] 在 runtime_policies 增加策略实体、持久化和增量迁移；校验正金额、12 位精度、周期、作用域与项目关系。
- [x] 实现策略增删改查、tenant 范围查询、现有项目管理权限和审计；GLOBAL 不等于跨租户授权。
- [x] 定义 tenant 策略集单调版本、策略版本、窗口定义版本、生效时间与删除标记；编辑金额 / 动作不重置累计或事件。
- [x] 冻结 Runtime 每调用解析策略、预算状态查询及错误契约；金额采用字符串，未知 / 恢复中状态不能冒充完整零余额。
- [x] 验证内部调用认证方向、签名与重放防护；区分策略已保存和 Runtime 窗口就绪，落实变更后的同步与失败重试。
- [x] 补齐 CRUD、精度、越权、跨租户、版本乱序和旧 Worker 不兼容时不能启用 REJECT 的测试。

**验收条件：** 见 [P1](verification.md#p1控制面与受信契约)。成功保存有可追溯版本；普通成员不能修改预算，项目用户不能读取其他项目或无权访问的租户聚合费用。接口失败不能返回“没有策略”。

**涉及位置：** `apps/platform-api/src/platform_api/modules/runtime_policies/`、该服务迁移与测试目录；Runtime 认证和 HTTP 契约测试。内部预算路由及前端金额/状态契约已冻结，见 frontend-handoff.md。

**开发与验证进度：** 策略、迁移、CRUD、即时权限、版本、签名与同步重试均已实现；控制面专项30项通过，覆盖非法金额/布尔周期、越权/跨租户、未知状态、签名与重放、HTTP Envelope以及通知ACK丢失。Runtime真实数据库门禁和双向HTTP联调证明不兼容Worker不能领取。保存/查询pending与applied分开，不把窗口未知补零。证据见 verification.md 及 implementation/01-backend-validation.md。

## Task 2：Runtime 权威账本、周期窗口与持久预算事件

用户需要重启后仍看到可信的已用金额；同一笔调用被重试结算不能重复收费，跨午夜晚到的费用也不能记错周期。本任务在 Runtime PostgreSQL 内派生预算，不再实现 Redis 浮点计数或从 Trace 回填的网关 Tracker。

**状态：** 已完成（done）。责任服务：runtime-service。

### Task 2.1：精确金额、窗口与幂等事务

- [x] 定义预算窗口、逐调用计入记录和唯一约束；沿用完整调用主键、Decimal 和 `numeric(28,12)`。
- [x] 实现 UTC 日 / 周日 / 月初左闭右开窗口；按调用开始时间归属，旧窗口不被滚动覆盖。
- [x] 把账本 upsert、差额计入所有命中窗口、数据质量和 outbox 写入同一事务；GLOBAL 与 PROJECT 不得部分提交。
- [x] 所有费用写入和窗口初始化先取得同一租户事务锁，锁后读取已提交事实；锁不得覆盖模型网络调用。
- [x] 对重复结算、缺失 / 部分转可信、失败 / 取消有费用和实际重试尝试分别测试；不把整个 Run 总费用再次累计。

**独立验收：** 多 Worker / 多数据库连接并发后，窗口金额等于按唯一调用事实算出的 Decimal 总和；同一事实重放增量为零，补齐仅加差额，任何事务故障都不能只更新账本或某一层预算。对应 P2。

### Task 2.2：新策略回填、迟到结算与恢复

- [x] 新策略 / 新窗口定义回填当前自然周期已纳管调用，保留调用价格快照；旧调用后续结算也能更新新登记窗口。
- [x] 用与实时写入相同的事务栅栏和幂等记录处理初始化；覆盖事务先启动、后提交等竞争，不使用自增 ID 假定提交顺序。
- [x] 保留周期和定义历史；跨午夜迟到补记旧周期，额度 / 动作变更不清零，周期变更不混算版本。
- [x] 区分正常在途、缺价格 / 用量、失联未闭合和重建中状态；REJECT 不在账务未核实期间按零放行。
- [x] 重启后核对并按需重建；检查 Thread 删除与 Trace 清理不能减少有效预算或破坏重建事实，故障期无法恢复的数据继续标未知。

**独立验收：** 回填与实时结算交错、重放及重启后金额无重无漏；迟到费用留在开始周期。无法核实的窗口保持不可核实，不能仅因数据库恢复连接就标记完整。对应 P2、P3。

### Task 2.3：首次超额事件与可重放 outbox

- [x] 在结算 / 策略应用事务内，为 ALERT 和 REJECT 生成首次超额事件，业务唯一键绑定 tenant、策略、窗口定义、起止和事件类型。
- [x] 固定事件 ID 与触发时快照，保存待投递、重试和失败状态；调额、改动作、再次越线不重建同窗口首次事件。
- [x] 测试提交前 / 后进程退出与并发越线；事件与费用一起提交或一起回滚。外部发送由 Task 3 负责。

**独立验收：** 一个窗口只有一条持久首次超额事件；事件重放不重复计费，重启不丢待投递任务。只证明数据库事件唯一，不宣称外部通知 Exactly Once。对应 P2、P5。

**涉及位置：** `apps/runtime-service/src/runtime_service/observability/usage.py`、`db/repositories/usage.py`、Runtime 迁移、持久化测试目录；新增预算模块沿现有服务分层放置。

**开发与验证进度：** Runtime专项34项通过，覆盖UTC边界、四连接精确小数、两个项目/两个tenant、双作用域五处事务故障、重放/可信补记、原价格快照、晚提交回填、历史定义、采集缺口与窗口重建。真实API/Worker重启后2.5 USD保留，失联未结调用阻止REJECT，可信零费用夹具补记后恢复；删除Thread后金额不减。Trace不是记账来源，保留链路已做源码核对，未执行外部Trace服务清理。实际供应商403费用保持未知，未清账。

## Task 3：每次模型调用准入、错误投影与可靠通知

预算应能在同一长 Run 的中途阻止下一笔模型费用，同时保留已完成结果和停止操作。本任务把 Task 1 的受信策略、Task 2 的账务事务接入真实调用路径，并把持久超额事件送达通知渠道。

**状态：** 部分完成（partial）。责任服务：runtime-service、platform-api。

### Task 3.1：真实调用边界与策略新鲜度

- [x] 逐条核对主 Agent、子 Agent、已纳管摘要等辅助调用、异步恢复、重试 / 备用模型及 SDK 隐式尝试，形成调用路径与入口对照。
- [x] 在实际发送模型请求前执行可中断准入；逐调用解析最新受信策略，不冻结整 Run，不允许晚到旧版本覆盖新版本。
- [x] 放行前持久化开始标记和价格快照；结束 / 失败 / 取消后确认结算结果，受 REJECT 约束的后续调用不能绕过未确认账务。
- [x] 落实 ALERT 降级、REJECT 账务不可核实即拒绝、查询失败不等于空策略；已确认无策略时保持现有行为。
- [x] 验证所有命中 REJECT 同时生效；保留正常在途并发和允许超支的语义，不增加金额预占。

- [ ] 取得可用供应商额度后，补真实主/备模型和异步恢复的组合链；既有Resilience多轮工具KeyError已在无预算callback条件重现，尚未处理，不算该组合通过。

**独立验收：** 同一 Run 的第一笔调用耗尽预算后，第二笔不再到达模型；真实供应商适配器的重试 / 回退不能绕过拒绝。策略变更影响后续调用，历史查询与停止不受预算阻断。对应 P4。

### Task 3.2：网关提前拒绝与 HTTP / SSE 安全表达

- [x] 新 Run 入口复用 Runtime 权威检查作提前拒绝；不能以此替代每调用准入，也不修改 completion 的费用职责。
- [x] 超额在握手前返回 429；账务不可核实返回受控 503。使用现有 Envelope、request_id、安全字段和 Retry-After 过滤。
- [x] 流建立后停止下一次模型调用，通过安全投影的错误 / 预算事件表达，持久化可回读原因；按需登记错误码并补白名单契约测试。
- [x] 验证不自造 Run 终态、不自动重试预算拒绝、不切换模型绕过；错误不暴露其他项目和租户费用。

**独立验收：** 同时覆盖握手前 HTTP 拒绝和流内停止；前端重连 / 历史回读仍可获知安全原因，停止和结果读取继续可用。对应 P4。

### Task 3.3：跨服务幂等接收与通知重试

- [x] Runtime outbox 通过受信内部接口发送事件，超时 / 失败重试，ACK 后才标记已交付。
- [x] Platform API 按事件 ID 幂等持久化通知及外部投递任务后 ACK；复用现有通知渠道，补持久去重与重试，不能只调用一次后写日志。
- [x] 站内信同事件只保留一份；外部渠道携带可用事件 ID，记录发送结果、失败和重试。
- [x] 覆盖发送前退出、接收后未 ACK、发送成功未记录 ACK、Worker 重启和重复投递；ALERT 与 REJECT 行为一致。

**独立验收：** 持久事件可恢复投递，站内无重复，外部至少一次重试及可能重复的边界可追溯；不承诺所有外部接收端只显示一次。对应 P5。

**涉及位置：** Runtime 模型调用封装、usage 接线、认证 / HTTP 与执行错误；Platform API `modules/runtime_gateway/`、`modules/notifications/`、适配器及契约测试。新增代码位置以调用路径核对结果为准。

**开发与验证进度：** 已实现全部后端接线，真实可控OpenAI HTTP经过平台认证、Runtime API和Worker，证明0.6+0.5后429、原幂等请求恢复、ALERT继续、流内停止、历史原因、调额恢复与通知去重。辅助调用/嵌套路径、同步/异步和重试不切备模型已有实际LangChain测试；事件重投及外部成功但ACK提交失败的至少一次语义有测试。3.2/3.3本地技术验证已完成；3.1真实供应商/主备组合仍部分完成。首选maomaoai/deepseek-v4.1-flash实际403额度不足，账户维护者补额度后由后端补验。原生Resilience多轮工具路由另有基线KeyError风险，证据及边界见implementation记录。

## Task 4：用量中心 Budgets 治理看板与聊天终态适配

管理员需要查看已用预算、自然周期、执行动作并就地维护策略；账务恢复或不可核实时，界面必须明确标识状态，严禁冒充健康零余额；普通用户在智能体运行触发预算耗尽时，界面应展示清晰的停止胶囊与指引，且严禁触发 Zod 校验崩溃。

**状态：** 已完成（done）。责任服务：platform-web。

**任务清单：**
- [x] 提供经过老王深度审查纠偏的 [frontend-handoff.md](frontend-handoff.md)，冻结三态进度条矩阵、高精度定点计算、URL Query replace 规范、Zod 白名单扩充与完整验收清单；[backend-runbook.md](backend-runbook.md) 提供隔离联调环境与回退约束。
- [x] 沿现有用量中心导航增加 Budgets Tab 与 URL query `replace` 双向驱动，修复图表下钻至 Logs 路由联动，加入请求序列锁隔离项目切换竞态。
- [x] 封装策略/状态类型与 API 客户端；金额严格保留 12 位十进制字符串提交与展示，实现三态视觉呈现矩阵（complete 三色进度条、reconciling 脉冲骨架、unverifiable 置灰/报警斜纹）。
- [x] 封装 `calculateBudgetRatio` 定点高精度计算纯函数，解决 BigInt 截断与 Number 浮点溢出；表单输入组件采用纯文本加正则守卫，严禁走 `v-model.number`。
- [x] 实现策略列表（GatewayBudgetsTab）、弹窗维护（CreateBudgetPolicyModal）与删除确认；弹窗作用域自适应锁定（项目用量页自动固定为当前项目 PROJECT 策略，平台用量页根据超管权限守卫 GLOBAL 策略）。
- [x] 补充聊天模块契约防爆：在 `apps/platform-web/src/modules/chat/completion/` 扩充 `REASON_CODES` 白名单（加入 `runtime.gateway_budget.exhausted` 与 `runtime.gateway_budget.unverifiable`），并在 `presentation.ts` 映射中文友好提示胶囊，防止流式消息与历史拉取时 Zod 崩溃。
- [x] 加固 `useChatSession.ts` 与错误展示：握手前 429 报错时安全保留草稿且禁止 `submitQueuedMessage` 重投，流内拦截时进入安全终止态并保留已有产物。
- [x] 补齐组件与 Composable 单元测试，执行 `pnpm typecheck`（vue-tsc）、`pnpm lint` 与生产构建，记录真实命令和结果。

**验收条件：** 见 P6。页面、表单、三态进度条与错误语义与修订版方案一致；代码检查与生产构建 0 报错通过。

**涉及位置：**
- 用量中心：`apps/platform-web/src/modules/usage/pages/UsageDashboardPage.vue`、`components/GatewayBudgetsTab.vue`、`components/CreateBudgetPolicyModal.vue`、`components/DeleteBudgetPolicyModal.vue`、`composables/useGatewayBudgets.ts`、`types.ts`、`services/usage/usage.service.ts`
- 聊天模块：`apps/platform-web/src/modules/chat/completion/types.ts`、`completion/presentation.ts`、`composables/useChatSession.ts`

**开发与验证进度：** 前端全栈能力已完整实施并闭环验证：
1. 聊天模块契约防爆：`presentation.spec.ts` 5 项测试全绿，覆盖 429 与流内终止 reason_code 校验与友好呈现；
2. 用量中心高精度计算与防竞态 Composable：`useGatewayBudgets.spec.ts` 8 项测试全绿，覆盖 0%、50%、80%、110% 截断及 12 位小数精准换算；
3. 用量大盘 Tab 切换与路由联动：`UsageDashboardPage.spec.ts` 3 项测试全绿，验证 budgets Tab 激活、路由 replace 与下钻同步；
4. 全量用量模块回归：`pnpm vitest run src/modules/usage/ src/modules/chat/completion/presentation.spec.ts` 7 个文件 47 项测试 100% 通过（耗时 5.76s）；
5. 静态检查：`pnpm typecheck`（`vue-tsc --noEmit`）0 errors，`pnpm lint` 0 errors；
6. 生产打包：`pnpm build`（`vue-tsc --noEmit && vite build`）构建通过（耗时 25.06s），dist 产物无损坏。真实证据已登记至 verification.md P6。

## Task 5：联合链路、故障恢复、安全与回退验收

管理员需要确认预算从配置到逐调用阻断、窗口恢复和通知都实际生效，且升级 / 回退不会让保护失效。本任务验证完整三服务链路，不把本地单测或阶段测试等同整体验收。

**状态：** 部分完成（partial）。责任服务：三个服务联合；治理验收由人工确认。

**任务清单：**
- [x] 按 P1–P6 执行单测、真实 PostgreSQL 多连接集成、契约、前端检查及 browser-skill 真实浏览器端到端测试；实际测试路径与命令在落地后登记。
- [ ] 执行 F1–F8 完整链路及故障 / 安全场景，保留真实认证、调用计数、账本差额、错误和通知证据。
- [ ] 执行 F9 完整链路性能对照，测策略解析、事务锁、调用写入与回填；依据事先确认的基线 / 阈值判断，不能沿用未测量的 ≤2ms 承诺。
- [ ] 执行 F10 前向迁移、重复升级、混合版本保护、兼容回退与再升级；保留历史，预算不可绕过。
- [ ] 将阶段验证和整体验收分区记录，失败 / 未覆盖项写回对应任务；完成原验收范围后再提交人工整体验收结论。

**验收条件：** [整体验收 F1–F10](verification.md#3-整体验收final) 均有证据和结论，必要人工门禁满足。未执行项不能勾选通过，不用缩小范围代替完成。

**开发与验证进度：**
1. 阶段验证 P1–P6 全部达成；
2. browser-skill 真实浏览器全链路端到端自动化验收 100% 通过（7 个 Case 全绿，232 秒无剪辑全程录屏、13 张关键步骤截图，交付报告见 [gateway-budget-e2e-report.html](gateway-budget-e2e-report.html)）；
3. 双库迁移及重复升级、旧Worker门禁、真实服务重启、金额重建和通知重投已验；本地热点/真实签名解析及认证查询性能已测，包含原250ms锁超时失败和修复复测；
4. 剩余项：仍需首选供应商 maomaoai 配额补齐后补验真实主备组合；人工确认性能阈值及治理/生产回退验收。因项目涉及底层 Worker 粘性安全栅栏，合并到 main 分支需经人工确认。
