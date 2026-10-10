# F11 任务拆分

> 核查与规划已完成；2026-10-10 用户完成 G01，确认暂缓开发（`deferred`），授权提交、合入和推送结论。G02及Phase 2～4全部后置、未排期，不属于本次交付，也未开始实施。不用 implementation/ 文件数量推断完成度。

## Phase 0：核查与规划（本轮）

- [x] P01 核对 DeerFlow/Open-SWE 本地代码及本项目调用者，区分功能缺口与已存在底座。
  - **位置：** `reference-analysis.md`，参考路由/helper/前端及当前 suggestions、catalog、composer。
  - **预期：** 明确“不作为生产必补，P2 候选”及避免重复建设的依据。
  - **验证：** 路径/符号搜索、参考快照哈希；事实不等于生产验收。
- [x] P02 写三层方案、用途授权、失败/成本边界和代码落点。
  - **位置：** `plan.md`、`review.md`。
  - **预期：** 无 Thread 场景不被遗漏，新增安全分支不当作已批准行为。
  - **验证：** 核对现有 `_authorize_model_reference()`、scope 枚举、模型连接与调用端。
- [x] P03 完成前端交接、实施清单与验证计划。
  - **位置：** `frontend-handoff.md`、本文、`verification.md`。
  - **预期：** 同事能明确请求、状态、禁用条件和浏览器验收，不需复制 DeerFlow React 组件。
  - **验证：** 契约字段、Unicode 长度、取消/撤销/KeepAlive/新 Thread 行为一致。
- [x] P04 将规划登记到 FEATURES/CONTEXT，完成文档校验。
  - **位置：** `docs/FEATURES.md`、`docs/CONTEXT.md`。
  - **预期：** 只写规划状态，不声称功能可用，不把 docs 放进 CHANGELOG 功能分组。
  - **验证：** 文档范围 lint/链接、`git diff --check`；证据见 verification。

## Phase 1：人工决定暂缓；实施评审后置

### G01 决定是否启动

- [x] **负责人：** 用户/产品；2026-10-10 用户确认暂缓。
- **内容：** 确认可提供真实匿名草稿样例、反复使用诉求及优先级；选择延期或完整 V1。
- **位置：** `review.md` 的 G1。
- **预期：** 不为功能名对齐自动批准开发；延期则本项目标 deferred，并保留规划。
- **验证：** 人工意见与范围记录；AI 不能勾批准。
- **结果：** 用户采纳 P2 候选、暂缓开发的结论；本项只完成投入决定，不批准 G02 的安全/成本实施方案。

### G02 批准授权、成本和保真边界

- [ ] **负责人：** 用户/架构与产品评审。
- **内容：** 批准 input-polish operation、用途引用和无 Thread 分支；接受 V1 代码/标签草稿原样、旁路成本排除及开启门禁；对既有代码/权限与JWT标准差异作人工裁决。
- **位置：** `review.md` 的 G2～G6；`plan.md`。
- **预期：** 正式实施有确定边界；不以默认关闭替代必须的授权设计。
- **验证：** 明确记录批准者、日期和具体决策；有变更时先改方案再实施。

## Phase 2：API/Runtime（暂缓，未来重新评审后实施）

### B01 公开 DTO、配置与 API 用例

- [ ] **负责人：** Platform API 开发。
- **内容：** GET config/POST，严格输入、现有项目执行权限、Agent/Graph 目标、可选 Thread comment/graph 一致性、当前模型选择，开关默认关闭。
- **位置：** `config.py`、`runtime_gateway/presentation/http.py`、`application/input_polish.py` 与 `RuntimeGatewayService.polish_input()`。
- **预期：** 同一接口覆盖无 Thread/有 Thread，关闭/越权/非法输入不触发 provider，无空 Thread 副作用。
- **验证：** 新 `tests/test_runtime_gateway_input_polish.py` + 当前 Thread/模型/事务测试。
- **预计：** 0.75～1 人天。

### B02 专属 Delegation 与用途模型引用

- [ ] **负责人：** API + Runtime 开发。
- **内容：** 签发/校验 input-polish scope；用途/签名绑定；无 Thread 专属重授权；原用途仍要求 Thread；双端新旧兼容关闭态。
- **位置：** API `core/security/tokens.py`、gateway delegation factory、catalog `model_connection.py`/`service.py`/`presentation/http.py`；Runtime `runtime/auth.py`、`runtime/modeling.py`、`http/input_polish.py:_authorize_scope()`。
- **预期：** F11 token/reference 不能复用于 Run、suggestions 或其他入口；当前撤权在兑换连接时阻断；旧 consumer 行为不放宽。
- **验证：** JWT/用途/nonce/expiry/tenant/project/graph/thread/context mismatch；无 Thread 普通引用拒绝；服务账号撤销；新 operation 按名称集合测试；旧 31 项授权回归。
- **预计：** 1～1.5 人天。

### B03 公共 one-shot 段与 F11 保真实现

- [ ] **负责人：** Runtime 开发。
- **内容：** 提取 suggestions 受管模型准备段，新建通用输入改写服务；各自保留单次无工具调用/失败处理，F11 总预算、CancelledError 传播、类型化最终文本、保护输入/命令/路径/URL与 changed 计算。
- **位置：** 新 `services/oneshot.py`、`services/input_polish.py`；改 `services/suggestions.py`。
- **预期：** suggestions 的 JSON/`[]` 降级和超时边界保留；F11 失败显式返回错误；不引入 create_agent/工具/业务 prompt。
- **验证：** `tests/services/test_oneshot.py`、`test_input_polish.py`、原 `test_suggestions.py`；provider 请求数/超时/取消/不可变保护。
- **预计：** 0.75～1 人天。

### B04 内部路由、adapter、审计/错误/用量边界

- [ ] **负责人：** API + Runtime 开发。
- **内容：** 独立内部 DTO/router、webapp 挂载、gateway port/adapter，错误精确码，安全审计字段，Usage 排除 input_polish，相关 doubles/fixtures 同步。
- **位置：** Runtime 新 `http/input_polish.py`、`webapp.py`、`http/title_summary.py`、`observability/usage.py`；API `application/ports.py`、`runtime_gateway_upstream.py`、`audit/http_resolution.py`、`sdk_client.py:create_runtime_upstream_error()`。
- **预期：** 草稿/结果/原始异常/JWT/Key 不进审计/默认追踪；HTTP 失败与未改写可区分；Run Usage 如实排除旁路。
- **验证：** `tests/http/test_input_polish.py`、API adapter/错误/审计/Usage 回归，纯 HTTP scope 隔离；日志 canary 不出现。
- **预计：** 0.5 人天。

### B05 后端阶段交付与文档同步

- [ ] **负责人：** 后端开发。
- **内容：** 真实 API→Runtime→模型调用；定向 lint/单测/集成，冻结实际 DTO/错误 fixtures；按批准方案更新 JWT/错误/审计/网关/配置文档。
- **位置：** `verification.md` 的 Phase 记录、后续 `implementation/`、相关标准、env-matrix/部署示例。
- **预期：** 可供同事接入的后端 Phase 交付；不标全链路 done。
- **验证：** 集成 I01～I08，旧 suggestions 回归；只使用本 Worktree 资源。

## Phase 3：前端同事交付（暂缓，未排期）

### F01 API/配置与 DTO 解析

- [ ] **负责人：** 前端同事。
- **内容：** 项目头、signal、配置与严格响应校验，局部安全错误；不抄 suggestions 的吞错 `[]`。
- **位置：** 新 `src/modules/chat/input-polish/api.ts`、`types.ts` 及 `api.spec.ts`。
- **预期：** GET 失败隐藏入口，POST 失败留草稿；选中 model catalog ID/graph key 正确，首条不造 Thread。
- **验证：** 请求 schema/头、changed/长度异常、开关关闭、网络超时与身份切换。

### F02 草稿 composable、取消与撤销

- [ ] **负责人：** 前端同事。
- **内容：** single-flight + request generation + draft revision；捕获身份/项目/Agent/Thread/模型；隐藏/卸载/发送/入队/清空/切模型取消；仅未被后续编辑的结果可撤销。
- **位置：** 新 `composables/useInputPolish.ts`、`useInputPolish.spec.ts`。
- **预期：** A→B→A 编辑也不能让旧响应覆盖；取消不改草稿；一键 undo 恢复准确原串。
- **验证：** race/ABA/KeepAlive/out-of-order/undo/changed=false；send/queue/resume 从未被润色调用。

### F03 Composer 与共享 Chat 接线

- [ ] **负责人：** 前端同事。
- **内容：** 现有 icon/tooltip、loading/取消/撤销；权限与 idle 状态禁用；普通发送不依赖配置/模型润色成功，附件和 Plan Mode 保留。
- **位置：** `components/ChatComposer.vue`、`ChatSession.vue`、相关 spec；必要小按钮组件按本地风格。
- **预期：** 通用 Chat/Dear 共用一次接入；不新增页面、不改 Run 控制器、不在 ChatPage 复制逻辑。
- **验证：** disabled/IME/键盘/多视口双主题，Plan pending review 和 Stop 状态不误触发；现有 Composer/Session 回归。

### F04 前端门禁与交付证据

- [ ] **负责人：** 前端同事。
- **内容：** 定向 Vitest、lint、typecheck、build，实际接入点/变化与截图；按后端冻结的交接修订本项目文档。
- **位置：** `frontend-handoff.md`、`verification.md` Phase 记录。
- **预期：** 同事交付能复核，mock 门禁不冒充真实三服务测试。
- **验证：** 前端 F01～F03 单测和 browser mocks 完成；余下联合链路转 Phase 4。

## Phase 4：联合 Final 与开启条件（暂缓，未排期）

### V01 真实三服务与副作用核验

- [ ] **负责人：** 后端 + 前端联合。
- **内容：** 新/旧 Thread润色→检查草稿→撤销/发送，真实模型；检查对话、Run、checkpoint、队列、Workspace 计数和文件 hash。
- **位置：** 新 `apps/platform-web/e2e/input-polish.spec.ts`；隔离 fixtures/证据；`verification.md` Final。
- **预期：** 润色阶段零任务写入；只有后续用户发送创建正常 Run；原审批/取消/queue 行为保留。
- **验证：** E01～E09 与既有关键链回归。

### V02 保真质量、延迟、配额与回退

- [ ] **负责人：** 联合验收 + 部署负责人。
- **内容：** 匿名质量样例人工对照、8 秒超时故障、关闭回退；检查部署入口限频/并发和供应商费用边界是否可执行。
- **位置：** 后续新 `fixtures/polish-quality.json`、验证证据、部署配置（明确获授权时）。
- **预期：** 关键约束零被接受的改写；正常短文本有可见收益；未知配额条件不广泛开启。
- **验证：** Q01～Q03、性能/资源取消/回退门禁；不能以按钮禁用代替直接 HTTP 防护。

### V03 Final 结论与项目状态

- [ ] **负责人：** 联合验收。
- **内容：** 逐项核对本清单、区分前端/后端完成与未具备的开启环境；执行 verify-change 并记录真实四态结论。
- **位置：** `verification.md` Final、README、FEATURES、CONTEXT；feat 才进 CHANGELOG。
- **预期：** 全部约定范围通过才 done；只有缺外部条件才 blocked，未完成不以 Phase 通过收工。
- **验证：** 附命令、日期、配置范围、真实 provider、请求/trace、安全证据和未完成原因。

## 进度追踪

- [x] Phase 0：规划交付完成。
- [x] G01：用户确认暂缓开发，评估与决策完成。
- [ ] G02：未来重新决定投入后，人工批准实施方案；当前后置。
- [ ] Phase 2：API/Runtime 与阶段验证完成。
- [ ] Phase 3：同事前端完成。
- [ ] Phase 4：联合 Final 与受控开启门禁通过。

当前评估与规划交付已完成，功能状态为 `deferred`。G02/Phase 2～4仅作后续参考，不计为本次未完成实施项。
