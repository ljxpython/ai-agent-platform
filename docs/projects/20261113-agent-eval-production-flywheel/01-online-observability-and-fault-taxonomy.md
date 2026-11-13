# 01-线上监控、质量度量与故障归因捕获体系

> 修订：2026-11-13。评审方向已确认；修订稿待实施评审。路径前缀、阶段及授权以 [README](README.md) 为准。

## 目标

1. 在现有 HTTP、运行诊断和预算监控之上，增加 Agent 业务质量信号及可追溯证据。
2. 分开记录异常线索、已确认故障和执行干预，避免合法审批拒绝、用户取消及网络断流被误判。
3. 首期以旁路采集和受预算约束的异步评分建立基线；实际开销、采集完整性和误报通过测量验收。

## 方案设计

### 1. 现状与新增边界

现有接入点：
- `Agent: apps/runtime-service/src/runtime_service/middlewares/execution_budget.py`：预算事件与收尾；同目录 token_budget.py 处理 Token 预算。
- `Agent: apps/runtime-service/src/runtime_service/observability/errors.py`、`Agent: apps/runtime-service/src/runtime_service/tools/errors.py`：运行/工具错误分类。
- `Agent: apps/runtime-service/src/runtime_service/observability/mlflow_tracer.py`：MLflow fail-soft 回调、平台 Trace 与 session/run 元数据。
- `Agent: apps/platform-api/src/platform_api/modules/observability/` 与 `apps/platform-web/src/modules/observability/pages/ObservabilityDashboardPage.vue`：现有诊断与大盘入口。

本期补信号契约、反馈、可靠关联、抽样和告警。保留既有预算和安全策略，不在不存在的 agents/executor.py 内重写调度主循环，不把监控组件变成第二套 Run 状态机。

### 2. 信号、故障与严重度

F1–F5 保留为分析分类，不替代现有底层错误码。候选允许多标签；分类不是自动处置指令。

| 分类 | 可用证据 | 必须区分的情形 |
| --- | --- | --- |
| F1_STEP_EXHAUSTION | 权威预算耗尽事件；无进展调用线索 | 预算耗尽不自动等于死循环；慢响应不等于耗尽 |
| F2_TOOL_MALFORMED | 不存在的工具、参数校验失败 | 上游超时、权限拒绝、服务不可用另记原因，不能统称工具幻觉 |
| F3_WORKFLOW_VIOLATION | 未授权副作用、审批前执行、实际跨项目泄漏证据 | 正确拒绝审批/越权请求是防护有效；被阻止的攻击尝试单独计数 |
| F4_INSTRUCTION_DRIFT | 当前有效约束、完整相关会话与违背证据 | 用户修改了原约束时按最新约束判断；点踩只生成待确认线索 |
| F5_GROUNDING_FAILURE | 实际检索依据、引用解析与输出矛盾证据 | 无检索上下文不能直接计算 Faithfulness；一般事实错误不硬套 RAG 分类 |

每条信号最少记录：`event_id`、`schema_version`、`signal_source`（human/rule/judge）、`signal_type`、原始错误码、候选类别、`confirmation_status`（suspected/confirmed/dismissed）、证据引用、检测器版本、发生/接收时间。严重度依据已证实影响独立确定；确认的未授权副作用按安全事件处理，但本功能不替代原审批/权限强制执行。

运行结果另存 completed/failed/cancelled/timed_out/interrupted/unknown 及原始状态。审批等待、用户拒绝和主动取消按预期场景解释。断流后查询权威 Run/停止回执，不能用客户端连接状态判定执行终态。

### 3. 反馈契约与多标识关联

Web 沿用现有 Vue 聊天组件，提供轻量点踩与可选原因；原因是用户意见，不直接写成 confirmed fault。可撤回/修改反馈；历史版本和操作者可审计。

拟新增反馈入口挂接现有 Thread/Run 授权链。具体 HTTP 路径在 Task 1.0 核对路由规范后冻结，不沿用「任意 trace_id 可写」入口。请求包含客户端幂等 ID、Thread/Run/message ID、rating、可选 reason/comment；tenant/project/actor 由认证上下文解析，不由客户端自由指定。服务端校验对象归属、反馈权限、文本长度和请求频率。

关联记录区分：
- 业务：tenant_id、project_id、thread_id、run_id、message_id；审批恢复可产生多个 Run。
- 排障：platform_trace_id / W3C trace context；不冒充 MLflow Trace ID。
- 评测：mlflow_experiment_id、mlflow_trace_ids、可选 span_id、assessment_ids；一个业务对象允许关联多个 Trace。
- 取证质量：关联状态 pending/linked/unavailable、缺失原因和有限等待期限。

已有 mlflow_tracer.py 将平台 ID 作为 metadata/tag 注入；实际 MLflow ID 由服务端受限查询解析。原生 Assessment 保存 HUMAN/CODE/LLM_JUDGE 来源与理由；tags 仅存检索投影。反馈更新按事件/反馈版本对账，不覆盖其它人的评估。

Trace 未到达、未启用追踪或取消后缺 Trace 时仍可保存业务反馈；如实标 unavailable，不能编造 Trace 或把缺失解释为无违规。链接打开后由目标服务再次授权，URL 中只传标识，不携带访问令牌或原文。

### 4. 可靠采集及旁路失败策略

采用「源侧可靠记录 → 异步投影到 EvalFlow → 回执对账」：
- 源侧只持有反馈、最小信号、关联和导出资格；审核/题库发布真源在 EvalFlow，见专题 02。
- 对反馈，源侧持久化成功后才返回已保存；对运行信号，复用持久运行事实及补扫能力。无持久事实可恢复的事件必须标明采集覆盖限制，不能宣称全部异常可恢复。
- 以 event_id/反馈版本设唯一约束；至少一次投递配合目标幂等键。远端超时先查原 ID，不能新建重复 Assessment。
- 采用有界重试、退避、最大积压和失败暂存/人工重放；记录丢弃、过期、延迟、重试及缺失数。
- 评分、MLflow 或投影故障不能阻塞主 Agent 执行；本地反馈保存失败明确返回失败。安全授权与脱敏失败则拒绝导出，不能按旁路可用性原则放行。
- 禁止每个 span 同步查询业务库/远端服务。存储实现先核对既有能力，缺口才在 `Agent: apps/platform-api/migrations/` 增量迁移，不预置独立消息平台。

### 5. 无进展检测：先观察，再干预

同工具、归一化同参数连续出现三次，只能产生 suspected 线索；跨进程摘要使用稳定指纹，不用 Python 内置 hash() 作为持久去重标识。摘要限制在项目/Run 范围，敏感参数不写入指标或开放日志。

校准样本必须包含合法轮询、重读且结果变化、有界重试、并行工具、审批恢复、重复只读无进展，以及 A→B→A 循环。关联工具类型、输出/状态变化、进展和重试原因，避免全局窗口混入其它子任务。

阶段 1 只打标，不抛异常、不增加模型调用、不发送新的终止指令。已有预算机制继续工作。阶段 4 才评估干预：先冻结误报/漏报接受条件，再按工具/Agent 小范围灰度；需与停止回执、在途副作用及收尾语义兼容。干预开关独立于采集开关，关闭后恢复原执行路径。没有可靠证据或安全停止能力时维持旁路。

### 6. 抽样巡检与统计口径

唯一采样配置：`sample_rate`。部署默认 0（关闭）；经授权启用的初始建议为 0.01，可在 0–0.05 内调整，超过此范围重新评估容量与预算。此处是拟定默认值，未更改任何线上配置。

- 以业务 Run 为单轮抽样单位，以会话/明确窗口为多轮单位；按 tenant/project、Agent 配置与任务类型分层，保留纳入概率、策略版本、时间窗和去重标识。子 span 不重复计样本。
- 全量运行结果统计与抽样质量分开；硬信号全量汇入候选的结果不混入随机质量均值。只评分正常完成请求时，指标命名明确限定该子集。
- 报告 eligible、sampled、scored、error、missing 数量及适用分母；低于冻结的最小样本量显示「样本不足」，不触发均分下降结论。跨层聚合保留权重和分层结果，不只给总体均分。
- TaskCompletion 需要可解释的任务目标与有效输出/工具证据；Faithfulness 仅用于有实际检索上下文的场景；F4 使用完整相关会话。非适用条件在评分前确定，缺本应存在的证据记 error，不能记 not_applicable。
- 原生在线评分优先验证：当前 `EvalFlow: mlflow/genai/scorers/base.py` 的 start()/sampling 配置及服务端作业支持不等于任意 DeepEval scorer 可直接注册执行。选择由 Task 4.0 形成结论；缺口在 eval_platform/ 补齐，不在 Agent API 新建 Celery 裁判服务。
- 复用已校准裁判及现有调用适配；记录模型、提示词、版本与用量。同源模型偏差通过确定性事实和人审控制。生产秘密经服务端安全配置注入，不依赖开发者 home 中的资源文件。

启用前冻结每日请求/Token 上限、并发、单次超时、有限重试、积压上限和样本保留期；预算未知则不启用。推理、裁判、嵌入分别核算，费用不可得记 unknown。暂停巡检不影响业务 Run。

### 7. 大盘、告警与性能

复用 Prometheus/Grafana/Loki 和现有页面。故障、预期拒绝、客户取消、评分错误分别展示；用户反馈率报告分母与未反馈流量，不当作全体满意度。

Prometheus 使用有界类别标签；租户/项目细分通过受控数据查询，不把 message/trace/user ID 变成高基数标签。告警复用已配置 Contact Points，实际通道、版本与模板须验证，不承诺无需配置即可支持所有 IM。通知只含最小摘要和受权链接，不发送原文。

Task 1.0 先测采集关闭时的吞吐、P50/P95/P99、CPU/内存和落库开销，冻结允许增量、最大延迟与可接受丢失条件；相同负载下复测。以证据验收，不承诺延迟增量 0ms、零成本或全故障检出率。

## 任务拆分

所有任务当前为待开始；开发后按完成卡记录具体改动和验证，不以规划文本勾选完成。

- [ ] **Task 1.0 — 信号与测量契约核对（阶段 0）**：核对上述现有模块、Thread/Run 路由及停止回执；冻结信号、标识、授权、采样分母和测量方案。位置：本专题、现有 observability/ 与 runtime_gateway/。输出：契约表及基线/阈值批准记录。验证：V1.1、V1.6 的测试方案可执行。
- [ ] **Task 1.1 — 旁路信号采集与可靠投影（阶段 1）**：依赖 Task 1.0、4.1。复用上述预算/错误/Trace 接口；拟新增 `Agent: apps/platform-api/src/platform_api/modules/evaluation/` 中的最小源事件与投影能力，必要迁移位于现有 migrations/。验证：V1.1、V1.3、V1.6。
- [ ] **Task 1.2 — 消息反馈与 Assessment 关联（阶段 1）**：依赖 Task 1.0、4.1。现有 `Agent: apps/platform-web/src/modules/chat/components/ChatMessageList.vue`、`apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` 为接入点，按实际组件职责拆最小改动；扩展 EvalFlow 接收。验证：V1.2、V1.3。
- [ ] **Task 1.3 — 无进展旁路探针（阶段 1）**：依赖 Task 1.0、1.1。接入实际工具中间件与运行上下文，新增文件按需要落在 runtime_service/middlewares/，不重建执行器。验证：V1.4；输出误报/漏报证据。
- [ ] **Task 1.4 — 异步抽样与预算（阶段 3）**：依赖 Task 4.0、4.1、2.1、4.2。复用验证通过的原生能力或扩展 `EvalFlow: eval_platform/task_worker.py` 与 scorers/，保留任务隔离；不强行将主动回归任务与线上评分共用一个调度锁。验证：V1.5、V1.6。
- [ ] **Task 1.5 — 大盘与告警（阶段 3）**：依赖 Task 1.1、1.4。扩展既有 observability 模块、页面及可观测配置；验证实际告警接收、去重和恢复。验证：V1.5、V1.7。
- [ ] **Task 1.6 — 循环干预校准与灰度（阶段 4，独立审批）**：依赖 Task 1.3 的误报证据及专题 04 安全/回退条件。只实施批准的工具/Agent 范围；无批准保持旁路，不擅自记完成。验证：V1.4、V1.8。

## 验证要求与记录

### 验证要求

| 编号 | 层级与场景 | 验收条件 |
| --- | --- | --- |
| V1.1 | 单元/契约：参数错误、上游超时、拒绝审批、取消、断流、未知终态 | 信号/故障/运行结果独立；合法拒绝不计实际越权；unknown 不伪装成功 |
| V1.2 | API/浏览器：反馈重复提交、修改撤回、跨项目 ID、无 Trace | ACL 生效、幂等可对账；无 Trace 反馈可保存；无令牌/原文进入链接 |
| V1.3 | 集成：Trace 延迟、投影超时、重复事件、进程重启 | 有界恢复，无重复 Assessment；不可恢复缺失被计量；原业务不受远端故障阻断 |
| V1.4 | 受控轨迹：轮询/重读/重试/并行/恢复/交替循环 | 旁路不改变终态，误报漏报有分母；阈值冻结后再评估干预 |
| V1.5 | 抽样与真实裁判：分层样本、无检索、多轮、预算耗尽 | 分母/采样率可核对；不适用与 error 区分；预算生效，禁止无限重试 |
| V1.6 | 性能/故障：同负载开关对比、队列满、存储或 MLflow 不可用 | 达到事前冻结的开销/完整性条件；记录丢失/延迟，关闭后恢复基线 |
| V1.7 | 大盘/通知：故障、恢复、误报撤销、受限项目 | 无高基数泄漏、无越权下钻；实际配置通道收到脱敏通知 |
| V1.8 | 灰度/回退：有在途工具、审批挂起、取消及关闭干预 | 原审批/停止回执不退化；不重复执行副作用；能独立关闭干预 |

### Phase 验证记录

2026-11-13：本次为方案修订，仅静态核对现有接入点；产品测试、性能测量、线上采样与模型调用未执行。后续每个 Task 在此记录真实命令、环境、证据与结果。

### Final 验证记录

未执行。需本专题批准范围及相关联合链路完成后独立验收，不复用规划或 Phase 记录冒充 Final。

## 状态

规划中：评审意见已确认，修订稿待实施评审；Task 1.0–1.6 均未开始。循环干预不属于首期旁路默认行为，后续批准与灰度记录单独保留。
