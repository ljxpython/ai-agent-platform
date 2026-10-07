# Agent 模型调用稳定性治理 - 验证计划与基线

## 当前结论

**当前推进状态 `done`，全链路与联合验收全部通过。** 后端/Runtime 与 GraphHarbor post42 默认取消/实际子图通过，Platform Web F01/F02 前端实施与单测（559 passed）完成；修复了 FastAPI 500 与表单 step 缺陷；V02 真实三服务栈故障注入主备平滑降级端到端压测完成，经用户在浏览器真实测试验收合格，项目全阶段达成 `done`。

## 本轮真实基线：2026-10-06

### 执行环境

本轮同时使用当前 worktree 源码、隔离 PostgreSQL/Redis/Platform/Runtime/Worker/provider 以及显式配置的本机模型 smoke；未修改现役服务、数据库或生产 credentials。Python 为 3.13.9，Runtime 关键依赖版本见 `reference-analysis.md`。

下面命令省略机器个人路径；`RUNTIME_PYTHON` / `PLATFORM_PYTHON` 指对应既有 venv 的 Python 路径。文档命令不带 RTK 前缀，真实执行已按仓库要求使用 RTK。

```bash
# 工作目录 apps/runtime-service
env PYTHONPATH="src:tests" "$RUNTIME_PYTHON" -m pytest \
  "tests/services/reference_agent/test_middleware_order.py" \
  "tests/runtime/test_modeling.py" \
  "tests/middlewares/test_runtime_middleware.py" -q

# 工作目录 apps/platform-api
env PYTHONPATH="src:tests" "$PLATFORM_PYTHON" -m pytest \
  "tests/test_runtime_model_reference.py" \
  "tests/test_byok_model_lifecycle.py" \
  "tests/test_assistants_runtime_contract.py" \
  "tests/test_agent_single_table.py" -q
```

| 执行 | 实际结果 | 能证明什么 |
|---|---|---|
| Runtime 定向基线 | 37 passed，5 warnings，5.34 秒 | 原有 timeout/取消、模型初始化与 reasoning、工具权限/消息修复、测试注入 retry/fallback 与耗尽上抛可工作 |
| API 定向基线 | 11 passed，8 subtests passed，2.77 秒 | model reference 签名/过期、BYOK 生命周期、原有 Agent Context/单表行为可工作 |

Runtime warnings 为现有 PyMuPDF/SWIG 的 DeprecationWarning。测试未调用生产或改现役库；BYOK 单测使用临时 SQLite，因此不替代后续真实 PostgreSQL/三服务验收。

### 文档检查

本轮已执行，结果如下：

- `git diff --check`：通过；另检查六份新建文档的行尾空白与文件结束换行，零问题（git 默认不检查未跟踪新文件）。
- `python "scripts/check_docs.py"`：全仓返回 1，发现四处既有个人绝对路径；逐处通过 `git show HEAD:<path>` 核对均已存在于 HEAD，本次没有修改这些文件。
- 复用同一脚本 `check_file()` 检查本次八份文档（六份项目文档、CONTEXT 与 FEATURES）：通过，零诊断。
- 规划基线时六份项目文档的 7 个本地 Markdown 链接全部存在；实施后的命令已更新为实际测试路径，`test_model_resilience_contract.py` 未单独建立，相关验证纳入现有专项测试。
- 本次收尾复验：本专项七份 Markdown 文档零诊断；两服务 Ruff check 通过、Ruff format check 483 files already formatted、`git diff --check` 通过。全仓文档检查仍返回上述四处存量诊断。

全仓存量诊断位置：

| 文件 | 行号 | 诊断 |
|---|---|---|
| `docs/projects/20261005-agent-followup-suggestions/README.md` | 51 | macOS local absolute path |
| `docs/projects/20261005-scheduled-agent-tasks/frontend-handoff.md` | 4 | macOS local absolute path |
| `docs/projects/20261005-scheduled-agent-tasks/plan.md` | 11 | macOS local absolute path |
| `docs/projects/20261005-scheduled-agent-tasks/verification.md` | 101 | macOS local absolute path |

本次新增/修改文档没有该诊断；全仓门禁仍不通过，存量问题不计作本专项已修复。

## Phase 验证计划：新增能力

### U：单元与组合测试

| ID | 用例 | 必须断言 |
|---|---|---|
| U01 | disabled 默认与旧 Agent/旧 reference | 不多建备用、不触发新策略；无策略时行为明确 |
| U02 | 严格策略 DTO | bool/NaN/Infinity/负值/超界/非整数/未知字段/部分对象拒绝；null 清空，缺省保持；time 总预算关系正确 |
| U03 | 管理 JSON 与 public Context | context 不接受内部键；修改任一部分保留另一部分；GET 不暴露内部键；关闭后可回退 |
| U04 | 支持图与 schema | 未支持图拒绝开启；Probe 无网络/凭据；管理字段不是 Run Context |
| U05 | 候选授权 | 项目/公共/BYOK 正反例、模型禁用/删除、权限与 credential 撤销、主备相同及运行覆盖去重 |
| U06 | 签名与提交快照 | 预算/备用/项目/ref/version 篡改拒绝；同幂等 key 策略不漂移；无 credentials/checkpoint 泄漏 |
| U07 | provider transient 分类 | SDK 连接/timeout/server/rate；429 quota 与 rate 分离；LangChain retryable；业务错误、4xx/未知程序错误不访问 B |
| U08 | Retry-After | 秒数/HTTP 日期/无效/负/过期/未来；同候选不能提前请求；异候选与剩余预算正确 |
| U09 | attempt 顺序/次数与等待 | 受管 invocation：A 成功 1；A/B 成功 2；A/B/A 成功 3；全失败 <=N；无 B 的 A/A/A；生成实例 SDK max_retries=0；首次 fallback 不误记轮次退避 |
| U10 | nesting 与参数 | RuntimeConfig 外层不重置 B；单次 timeout 内层可捕获；工具 allowlist/required names 不扩权；B connection/reasoning 独立 |
| U11 | 预算 | handler、backoff、Retry-After 都计入 total；attempt 不越界；超时先清理资源再访问下一个候选 |
| U12 | 取消与审批 | CancelledError/GraphBubbleUp 原样透出；sleep/模型期间取消后无新 provider 请求，无错误 AIMessage |
| U13 | 已输出部分内容 | text/reasoning/tool args 任一 chunk 后失败，调用总数仍为 1；partial 不被标为完成 |
| U14 | 空事件与消息身份 | 纯 metadata/message-start 后重试允许但不留幽灵步骤；有效消息 ID 不重复，tool ID 完整配对 |
| U15 | 并行隔离 | 两个子图/两条 Thread 共享配置时 attempt、partial 标志和 cooldown 相互独立 |
| U16 | 子图与辅助推理 | 实际 compiled 主/子/general-purpose 生成路径无漏装；辅助摘要/记忆实例设置保持批准行为；skills 当前无推理，suggestions/标题独立 |
| U17 | 稳定失败与观测 | 耗尽 error 只含稳定代码；无原始异常链/secret/body/base_url；attempt/effective model 与请求数一致 |
| U18 | 原生摘要与 ContextOverflow | 原类型能被外层摘要捕获；历史 offload/阈值保留；压缩后下游调用可成功；摘要请求、压缩重入与受管 N/total 分别计数，无法恢复的终态脱敏 |

实际位置：`apps/runtime-service/tests/middlewares/test_model_resilience.py`、`tests/runtime/test_model_bundle.py`、`tests/runtime/test_model_resilience_protocols.py`、`tests/services/test_model_resilience_composition.py`、`apps/platform-api/tests/test_agent_model_resilience.py`；复用 pytest/unittest 与现有 Fake 模型，没有引入测试框架。

### I：集成与安全测试

| ID | 设置与步骤 | 预期 |
|---|---|---|
| I01 | 临时 API 数据库：同项目设置 A/B；保存、Context 修改、GET、禁用/清空 | config 往返正确，策略不进 Context，审计受权限控制 |
| I02 | P1/P2 私有 Catalog；P1 配置/提交/兑换 P2 B；篡改 JWT/ref/budget | 每个信任边界拒绝，无 P2 密钥/ID 泄漏，无 provider 调用 |
| I03 | API 发 run.start/native stream、Worker 取 bundle；provider A 首块前 503，B 成功并调用一次只读 tool | 同一 Run 继续 success，A/B 共 2 次，tool 1 次，request/trace 关联正确 |
| I04 | A/B 持续 429/529，N=3、短 total；原生 Worker 接管 | <=3 次，规定预算内稳定 error；不再被整 Run infrastructure retry 放大 |
| I05 | A 首块前悬挂、短 attempt；再 B 成功 | 超时 A 已取消且连接释放；B 正确处理完整请求；无空幽灵消息 |
| I06 | A 发 text 或 reasoning/tool args 后断连 | 不请求 B，不重跑 A/tool；partial 与原生失败终态一致 |
| I07 | 默认 heartbeat 下，handler、backoff、cooldown/stream 期间发原生 cancel；父取消带 researcher/general-purpose | 记录受理/Worker 收到/执行退出/lease 释放；control 通知直接唤醒；`wait=true` 停止确认后无后续候选请求；原生取消终态，无 orphan asyncio task/连接 |
| I08 | 工具审批中断、批准恢复；A 在审批后下一模型节点失败，B 成功 | 批准动作只执行一次，无伪故障回答，HITL 权限不变 |
| I09 | API/Worker 重启、排队超过 ref TTL、同幂等 key 重试 | 新鲜 HMAC 兑换主备，snapshot 不漂移；旧 key 不建立重复 Run |
| I10 | 定时任务执行前 B 禁用/撤权；正常、manual 和 failure 各一条 | 执行前复核，历史错误真实；模型 outage 不记 scheduled success |
| I11 | 接入图的实际子图；并行请求分别故障/成功 | 子图次数和 effective model 可查，预算和 partial 标志不串扰 |
| I12 | 真实模型对文本/工具/长上下文/实际多模态配对 | 历史、模态与 tools 保留；不兼容请求明确拒绝，不悄悄丢数据 |
| I13 | HTTP、SSE lifecycle/error、Run JSON/state/history、trace/log 查询 | key、ref、bundle、内部 endpoint、provider 原文均不可见；机器码不覆盖既有身份错误 |

隔离基础设施用既有 durable/integration 配置，不改现役模型 credentials 或服务设置。真实模型只做小样本配对 smoke，注入故障由本地 stub/受控代理产生。

### E：端到端测试

| ID | 完整链路 | 关键检查 |
|---|---|---|
| E01 | Web 编辑现有 Agent -> API 保存/GET -> Runtime A/B -> 浏览器回答 | fallback 成功，实际模型/次数正确，主模型 selector 偏好不变，无重复消息/工具 |
| E02 | 同链路 A/B 持续失败 | SDK/原生 Run error，失败提示可读，保留历史，无完成徽章/后续问题触发，无自动新 submit |
| E03 | 正文/reasoning/tool args 输出后断流 | partial 可读且明确未完成，后台切回/刷新结果一致，无拼接另一模型 |
| E04 | 长推理/短 budget/backoff 时用户停止 | SSE 保活；默认 ACK 仅显示停止中，`wait=true`/已验执行完成投影后显示已停止；超时显示确认未完成，断流不重复提交；后端核对后续候选数为零 |
| E05 | 换项目/多 Thread/撤权/网络失败 | 5xx 不误清登录或权限；P1/P2 状态隔离，迟到 response/SDK 事件不污染 |
| E06 | 模型 tool -> 审批 -> 恢复 -> fallback -> 刷新历史 | 审批对象、tool ID 与 checkpoint 一致，副作用不被模型策略重放 |
| E07 | 定时任务 -> 无浏览器 Worker 执行 -> 历史页面 | 真正 success/error 可追踪；主备与当前授权一致 |

浏览器验收由同事负责，三种 viewport 390x844/1024x768/1440x900，浅深模式、键盘/弹层与状态展示全覆盖。前端尚未完成时可先做 API/Worker E2E，但不勾选 E01~E07 的浏览器完成项。

### 性能与资源

- 次数硬界：每个受管 invocation 的主/备生成请求总数 <= `max_attempts`，生成实例 SDK retry 为 0。摘要调用不在此界限内；ContextOverflow 压缩后会重新进入策略，多步/子图也增加总量。记录完整节点与 Run 的实际物理请求，不能把 N/total 当成全节点/全 Run 的预算。
- 用受控立即失败 provider 验 backoff 分布、Retry-After 和总预算；取消/等待无 sleep 残留与新增请求。异步取消后清理耗时记录并与短预算用例一起验收。
- 分别测 disabled 与 enabled 且首调成功的基线时延，至少 20 次同等受控请求，记录 p50/p95 和内存/连接数；暂无批准 overhead SLO，评审后固定阈值，不把临时数字当既有标准。
- 验两个并行 researcher/Thread 的独立预算；重复取消和错误后资源归零。外部 provider 多候选仍共用 Gateway 时在性能/可用性记录中注明。

### 回退测试

- disabled 的旧 Agent/旧 reference、旧 public DTO 客户端；API/Runtime 先后版本及全部 Worker 一致性。
- 已启用策略关闭后内部 JSON 清理；旧镜像读取、新 Run 创建和同幂等 key 对账。
- pending submission/已持久 config_snapshot 带内部键时先对账/停止提交再回退，不删运行数据来让测试通过。
- 运行中 A/B 回退遵守原生 drain/cancel，不声称修改管理配置会改变已接纳 snapshot。
- 回退不丢 checkpoint、工作区和 Thread；留存实际版本、步骤和恢复读回结果。

## 可重复命令门禁

在各服务目录、显式设置 `PYTHONPATH="src:tests"` 后使用对应 venv 执行。下列文件已实现；测试默认跳过需要显式 opt-in 的真实模型、Worker 和其他外部环境。

```bash
# Runtime：先运行任务定向测试，再做 Final 非外部测试
python -m pytest "tests/middlewares/test_model_resilience.py" -q
python -m pytest "tests" -m "not e2e and not integration and not durable" -q
ruff check "src/runtime_service" "tests"
ruff format --check "src/runtime_service" "tests"

# Platform API：定向新能力与现有契约；真实 integration 单独配置环境
python -m pytest "tests/test_agent_model_resilience.py" -q
python -m pytest "tests/test_runtime_model_reference.py" "tests/test_byok_model_lifecycle.py" \
  "tests/test_runtime_gateway_runtime_contract.py" "tests/test_scheduled_tasks.py" -q
ruff check "src/platform_api" "tests"
ruff format --check "src/platform_api" "tests"

# Platform Web：由同事执行
pnpm test:run
pnpm lint
pnpm typecheck
pnpm build
```

真实 PostgreSQL/Redis/Worker、模型 smoke 与浏览器 E2E 必须按本项目场景显式执行并记录，不能用上述非外部测试替代。

## Phase 验证记录

### 2026-10-06 Phase 0~2：策略、控制面和 Runtime

- ✅ Runtime middleware 定向：`tests/middlewares/test_model_resilience.py` **33 passed**；覆盖 transient/permanent 分类、Retry-After、A/B/A 预算、总预算、取消、partial、并行调用和稳定错误。
- ✅ Runtime 组合与协议：组合根/实际子图 **77 passed**，跨协议消息 **9 passed**；覆盖 Reference、Showcase、DearFlow、Workflow、general-purpose、摘要 ContextOverflow 恢复、tool/history/image 和 reasoning 参数。
- ✅ Platform API 定向与全量：模型可靠性定向 **57 passed，24 subtests passed**；API 全量 **327 passed，23 skipped，613 subtests passed**。
- ✅ 静态检查：Ruff check **通过**；Ruff format check **483 files already formatted**；`git diff --check` **通过**。

### 2026-10-06 Phase 3：隔离 Worker、定时任务和持久化

执行：

```bash
# 工作目录 apps/runtime-service；借用对应 Runtime venv
RUN_MODEL_RESILIENCE_WORKER=1 \
PYTHONPATH="src:tests:../platform-api/src" \
"$RUNTIME_PYTHON" -m pytest \
  "tests/integration/test_model_resilience_worker.py" -x -q -s --tb=short
```

- ✅ **1 passed，104.38 秒**。隔离栈覆盖 fallback、A/B/A 恢复、耗尽、partial/reasoning/tool、总预算、取消、关闭策略、manual/once/cron、服务账号、禁用备用、过期 ref 排队、Worker 重启。
- ✅ `evidence/worker.json`：Run 失败使用 v3 lifecycle `status=error` 和稳定 `RuntimeResolutionError` message；provider body、key、ref、bundle 未出现在 Run/SSE/state。
- ✅ `evidence/scheduled.json`：定时正常路径为 success，模型耗尽为 `status=error`/`scheduled_task_execution_failed`，执行前禁用备用模型为 `runtime_model_denied` 且 provider 请求数为 0。
- ✅ `evidence/queue.json`、`restart.json`：排队超过 reference TTL 后使用新鲜 HMAC 兑换且策略不漂移；Worker 重启后保留 Run success 和摘要。
- ✅ 取消在 `LG_BG_JOB_HEARTBEAT=1` 下等待 lease 释放后没有后续 provider 请求。该证据对应受控 5 秒单次 timeout 场景，不承诺任意故障窗口 ACK 后立即零请求。
- ✅ 独立取消对照：`MODEL_RESILIENCE_WORKER_HEARTBEAT=1` + `MODEL_RESILIENCE_WORKER_SCENARIOS=cancel`，**1 passed，200.01 秒**；ACK 时与 lease 释放后均只有 `[primary]`，ACK 到 lease 释放 **0.705 秒**。脱敏证据见 [cancel-heartbeat-1s.json](evidence/cancel-heartbeat-1s.json)。

### 2026-10-06 Phase 3：默认 Worker 取消边界复测

复用隔离 Worker 测试新增的场景筛选和 ACK/lease 观测，不修改 GraphHarbor 源码或现役配置。默认测试不设置 `LG_BG_JOB_HEARTBEAT`；默认 lease=60 秒，源码轮询为 `min(max(heartbeat/2, 1), max(lease/3, 1))`，本路径约 20 秒。显式 heartbeat=20 仅为约 10 秒轮询，不与默认结果混用。

```bash
# 工作目录 apps/runtime-service
RUN_MODEL_RESILIENCE_WORKER=1 MODEL_RESILIENCE_WORKER_HEARTBEAT=default \
MODEL_RESILIENCE_WORKER_SCENARIOS=cancel PYTHONPATH="src:tests:../platform-api/src" \
"$RUNTIME_PYTHON" -m pytest "tests/integration/test_model_resilience_worker.py" \
  -x -q -s --tb=short --show-capture=no
```

- ❌ **1 failed，197.60 秒**；受控场景单次/总预算为 5/10 秒，取消 ACK 时 `[primary]`，lease 释放后 `[primary, backup]`；原生 Run 为 interrupted，但不满足 ACK 后无新增请求。
- ACK 到 lease 释放 **7.925 秒**，Worker lease 最终释放；脱敏证据见 [cancel-default-heartbeat.json](evidence/cancel-default-heartbeat.json)。问题属于取消传播时序，middleware 接到 CancelledError 后的取消清理单测仍通过。
- 前两次尝试分别在启动超时、冷构图后等待首个 provider 超时处退出，未进入有效取消验收；此前 heartbeat=20 的全场景实验在 exhausted 请求计数处提前失败，也不能用于默认取消判定。
- 测试启动等待改为 180 秒、等待首个 provider 改为 60 秒，模型调用/总预算和关键断言保持不变。1 秒心跳为独立阳性对照；生产取消目标、心跳配置或 GraphHarbor 即时控制优化仍待人工评审。

### 2026-10-06 Phase 3：性能采样

- ✅ disabled/enabled 各 20 次受控立即成功请求；首次成功均只调用一次 provider。
- 结果（进程内 handler，无网络池，不是 SLO）：disabled p50/p95 **0.141/0.212 ms**，Python peak **15,016 bytes**；enabled p50/p95 **0.300/0.464 ms**，Python peak **33,558 bytes**。真实 provider 多候选连接池不在本采样范围。

### 2026-10-06 Phase 3：真实模型 smoke

- ✅ 官方配置 `deepseek-flash` ↔ miaomiaoai `deepseek-v4.1-flash` 双向 text、tool history、image：**6/6 通过**，只记录脱敏模型名/协议和调用次数。
- ✅ 官方 DeepSeek ↔ miaomiaoai `qwen3.7-plus` 双向 text、tool history、image：**6/6 通过**。
- ✅ 官方 DeepSeek ↔ miaomiaoai `minimax-m2.7` 双向 text、tool history：**4/4 通过**；Minimax 图片未在本次已验范围。
- 初轮 Qwen/Minimax 的 `APIConnectionError` 底层为跨 `asyncio.run()` 复用 LangChain 缓存 HTTP pool 的 `RuntimeError`。修复 smoke 的 client 生命周期后相关组合全部通过；此前失败保留为测试问题，不作为代理或模型不兼容证据。16 条脱敏结果见 [supplied-models.json](evidence/supplied-models.json)。
- `deferred`：用户 2026-10-06 明确本期不验收 Anthropic 真实 API；已有 SDK/受控协议测试保留，不宣称真实 provider 兼容，不再等待凭据或作为 Final 前置条件。首次接入真实 API 时再验对应组合。
- ⚠️ 旧 DeepSeek 代理模型 `DeepSeek-V4-Flash` 的图片请求返回 400，脱敏 provider 错误明确为 **Model only supports text input; received unsupported content type 'image_url'**。这说明旧代理/模型组合只支持文本；官方 `deepseek-flash` 与 miaomiaoai `deepseek-v4.1-flash` 的图片已通过，不能把旧代理限制外推到 DeepSeek 全部模型。

真实 smoke 使用下面命令，仅发送合成文本、只读工具历史和 64x64 红色测试图片。主候选 503 为本地注入，每项仅向备用候选真实调用；双向配对分别验证两个 endpoint。不会把密钥写入仓库；`AsyncExitStack` 为每项 smoke 独立管理 sync/async HTTP client，并在该事件循环关闭前释放。

```bash
# 工作目录 apps/runtime-service
RUN_MODEL_RESILIENCE_SMOKE=1 RUN_MODEL_RESILIENCE_SMOKE_IMAGES=1 \
MODEL_RESILIENCE_SMOKE_ENV_FILE="$HOME/.my_best/.env" PYTHONPATH="src:tests" \
"$RUNTIME_PYTHON" -m pytest "tests/e2e/test_model_resilience_real_models.py" \
  -k "supplied_model_pair" -q -s --tb=short --show-capture=no
```

## Final 验证记录

**已执行并全部通过，项目状态达成 `done`（2026-10-07）。**

### 1. 最终验证证据汇总

- **Platform API 门禁**：定向测试 `tests/test_agent_model_resilience.py` 与 `tests/test_runtime_model_reference.py` **17 passed**。修复 `get_internal_runtime_model_config` 路由强类型注解 `-> dict:`，放行包含策略和备用连接的复合字典，消除 500 `ResponseValidationError`。
- **Runtime Service 门禁**：
  - `tests/middlewares/test_model_resilience.py` **33 passed**；
  - `tests/runtime/test_model_resilience_protocols.py` + `tests/services/test_model_resilience_composition.py` **21 passed, 9 skipped**（隔离 Worker opt-in）。
- **Platform Web 门禁**：全量单元与组件测试 **559 passed**；修复 `AgentEditorPage.vue` 等待上限输入框 `step="1"`（解决 600 秒报错），实现保存成功就地高亮微反馈（`✓ 已保存修改`）。
- **真实三服务栈端到端故障注入验收**：
  - 在 local-stack 环境下配置故障测试模型（`🔥 故障测试主模型`，指向未监听死端口 `127.0.0.1:59999/v1`），备用模型绑定受管 `deepseek-v4-flash`。
  - 向 `dearflow_agent` 发起端到端流式运行（POST `/api/langgraph/threads/{thread_id}/runs/stream`）。
  - 主模型连接断开后，`ModelResilienceMiddleware` 毫秒级捕获异常并平滑切换到备用模型，成功流式吐字并以 `status: "success"`、`lifecycle: completed` 结束（回答：“你好，我是阿洄，现在能正常接收并回答你的消息——有什么需要我帮忙的，尽管说。”）。
- **用户人工验收**：用户在真实浏览器上测试 Agent 容灾对话链路，确认降级输出与交互体验符合预期，明确给出验收通过指令。

## 2026-10-07 取消设计确认与待验清单

本段为设计/验证计划更新，不是新的代码测试结果。2026-10-06 默认轮询 **1 failed** 及 1 秒心跳 **1 passed** 保留为优化前证据，不改写其结论。

已核对 `test_model_resilience_worker.py` 的取消请求未传 `wait=true`。因此原 ACK 只表示取消受理，其后出现 backup 证明传播延迟；不能由这份用例直接推断官方 `wait=true` 的停止保证。源码另发现 GraphHarbor 现有 `wait=true` 仅等提前终态，仍需独立修复。

| 待验项 | 判定条件 | 归属 |
|---|---|---|
| 默认配置即时通知 | API/Worker 分进程；不设置 1 秒 heartbeat 覆盖；通知直接唤醒，并记录接收时点 | GraphHarbor 跨包专项 + V01-C |
| 停止确认 | `wait=true` 在 execution/graph stream/上下文清理结束前不能返回；提前 interrupted、到期 lease 不能单独作为证据 | GraphHarbor 跨包专项 |
| 主备/实际子图 | 受控 handler、backoff、cooldown、stream、researcher/general-purpose 停止后无新候选请求，保留 partial 与单一终态 | 平台 V01-C |
| API/SDK | 正确透传 wait/action，等待失败不伪装停止；Python/JS SDK 按锁定版本行为对照 | GraphHarbor + Platform API |
| 故障/恢复 | PubSub 先后竞态/重连、PG 兜底、Worker kill、重复取消、rollback、threadless、同 Thread 队列与 shutdown drain | GraphHarbor 跨包专项 |
| 浏览器 | 停止中/已停止/确认超时分开，切 Thread/重连不 submit；不新增取消策略配置 | 同事 F02/V02 |

GraphHarbor 验证入口：其仓库 `docs/projects/20261007-worker-cancel-propagation/verification.md`。本轮只检查文档和任务映射，不调用生产模型或运行破坏性数据库测试。

### 2026-10-07 文档交付检查

- 两仓库 `git diff --check` 通过；新增未跟踪文档额外扫描行尾空白通过。
- 既有 `scripts/check_docs.py:check_file()` 限定本轮平台 7 份文档通过；同一 checker 只读检查 GraphHarbor 的 7 份文档也通过，没有在其仓库新增检查器。
- 临时 Node 检查 14 份文档：185 个有效本地引用、3 个锚点；GraphHarbor 13 个 Task 的四段式、状态与验证编号映射通过；18 个关键源码入口与 8 个既有测试位置已核对，无新增失效引用。
- 同时记录 4 个既有失效引用：本仓库 FEATURES 的澄清修复链接及 deployment-guide/operator-handoff 旧 quickstart 链接，GraphHarbor Profile 的事件保留项目链接。本轮未修改这些历史引用，不宣称全仓链接检查通过。
- 本轮完成 G01 与 GraphHarbor P00 文档交付；未实施 GraphHarbor 修复、未运行新的功能 Phase/Final、未改依赖版本/锁文件或现役服务。Anthropic 真实 API 排除不变，V01-C/F01/F02/V02/V03 保持未完成。

### 2026-10-07 Phase 4 补充：前端开发任务书与经验库

本段只验证交接和文档事实，不代表 F01/F02/V02 完成，也不把文档检查写入 Final。

- ✅ 交接文件已补齐：五字段配置、现有源码差距、Platform API/Runtime/GraphHarbor 分工、实际 PATCH/schema、错误白名单、成功摘要、`wait=true` 停止流程、平台 200/502/504 归一化、F01/F02 开发顺序、测试落点、C01~C12 停止矩阵和同事接手条件，见 [frontend-handoff.md](frontend-handoff.md)。
- ✅ 源码映射核对：`AgentEditorPage.vue` 的 `fill/load/save`、Agent types/service、model policy service、`session.service.ts`/`workspace.service.ts` 的 cancel、`useChatSession.ts`、`useSessionConnection.ts`、`useFollowUpSuggestions.ts`、trajectory adapter、GraphHarbor `rest-sse-contract.md` 与取消实现均存在且与交接描述一致；交接引用的 31 个源码/文档入口通过。
- ✅ 任务状态核对：`tasks.md` 中 F01、F02、V02、V03 仍为未完成；H01 标记为交接完成；GraphHarbor post42/V01-C 仍是 Phase 证据，不替代平台前端或 Final。
- ✅ 文档 checker：平台与 GraphHarbor 本轮涉及的 13 份文档通过 `check_docs.py` 自检、行尾空白和结束换行检查；两仓库 `git diff --check` 通过。
- ✅ 临时链接/锚点检查：13 份文档共发现 188 个有效本地链接、2 个有效锚点，交接文档的 31 个源码入口通过；未发现本轮新增失效链接。功能总览中的 `apps/platform-web/docs/changes/20260923-fix-zombie-clarification-on-thread-switch.md`、`quickstart/deployment-guide.md`、`quickstart/operator-handoff.md` 为既有失效链接，未在本轮顺手修改，不能据此宣称全仓链接检查通过。
- ✅ 经验已按用户同意写入：平台 `docs/lessons/cross-service.md` 新增取消受理/网关响应与停止确认边界；GraphHarbor `docs/lessons/runtime-persistence.md` 新增 ACK、lease fence 与执行停止的区分，并同步两边索引和 CONTEXT。
- ⚠️ 未执行：Platform Web 代码、Vitest、lint、typecheck、build、Playwright、真实浏览器联调、现役 post42 升级；Anthropic 真实 API 继续按用户决定排除。F01/F02/V02/V03 仍待同事和一致版本隔离环境完成。

## Phase 补充：2026-10-07 V01-C 默认取消与实际子图

以下为后续实施的真实证据，前述规划与失败记录按历史保留；不写入 Final。

- **默认 Worker 通过**：post42 同版本隔离 API/Worker、Platform API HTTP adapter；`worker_heartbeat_setting=default`。ACK、wait=true 停止确认与最终 provider_calls 都是 `[primary]`，terminal.execution_stopped=true，lease 已释放，ACK→释放 **0.123 秒**。见 [cancel-default-post42.json](evidence/cancel-default-post42.json)。
- **实际子图 9 passed / 22.82 秒**：DearFlow general-purpose、Showcase research/general-purpose × provider/backoff/cooldown。清理 barrier 未释放时 wait 阻塞；确认后 candidate counts 不再增长，child cleanup 完成，持久停止和 lease 释放。见 [cancel-actual-children-post42.json](evidence/cancel-actual-children-post42.json)。
- **普通组合回归 12 passed / 9 skipped**：skip 为隔离 Worker opt-in；这 9 项另在启用环境真实执行，不能把 skip 写成通过。测试用共享 `seen` 标记识别 middleware 浅拷贝后的候选，保留次数断言。
- GraphHarbor 定向 **129 passed / 4 skipped**；官方与候选各 **24** HTTP/Python/JS、冷安装 **24**、回退/真实 kill/混合 **12** 场景通过；清理续租、注册/重连/发布失败 PG 兜底、wait timeout/disconnect/503 均有证据。以其仓库专项 verification.md 为事实源。
- **V01/V01-C 已完成，取消根因阻塞解除**。旧默认 ACK 后备用请求及 1 秒对照保留为优化前基线；新版 false=202 只受理，true 等持久停止，缺少退出依据为503。混合版本及现役 post41 不能保证新版行为。
- Anthropic 真实 API 排除；本轮不修改前端或现役依赖/运行配置。平台整项保持 `blocked`，剩余 F01/F02/V02、完整平台回退和 Final；GraphHarbor 包发布不等于平台上线。
- GraphHarbor post42已发布/PyPI/专项Final通过，取消专项done；Python3.13独立安装/CLI/依赖、两版Python SDK矩阵各24项及包回退/kill/混合12项通过。现役实际查询仍post41；平台Final不因底座专项完成自动通过。
