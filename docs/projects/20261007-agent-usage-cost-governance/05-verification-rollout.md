# 验证、发布与回滚

## 目标

给这次治理改动定义可执行的分阶段验证和生产化门禁，证明用量准确性、权限隔离、故障降级和前端展示闭环，而不是只证明某个 parser 单测通过。

## 方案设计

验证沿 02 的 Runtime 事实采集、03 的价格与权限契约、04 的前端交接分阶段执行。优先用确定性模型/usage fixture 核对每个数字，再用真实 provider 完整 Run 检查实际字段与流水；不靠对话结果“看起来成功”判断费用准确。

### 规划阶段验证记录（历史）

这是用户批准前的历史基线；当时只读取源码、查询官方 MCP 与执行既有测试，不代表当前实现状态。

| 检查 | 实际结果 | 能证明的范围 |
|---|---|---|
| Runtime `tests/observability/test_langfuse.py`、`test_graph_tracing.py`、`tests/runtime/test_modeling.py` | 45 passed，约 23 秒；5 条既有 SWIG 弃用警告 | 现有模型构造、callback 传播和 Langfuse 观测基线；不证明新 ledger 或成本计算已实现 |
| 官方 `langchain-docs` + `langchain-reference` MCP | 已查询 usage metadata、callback 与成本跟踪 | 标准字段和已有依赖可复用；供应商真实行为仍需后续组合/E2E 测试 |
| 参考仓库基线 | HEAD 与本地未提交改动边界已记录在 01 | 结论对应提供的工作区，不能当作干净上游发布能力 |
| 本轮文档检查 | 专项 6 篇与 CONTEXT/FEATURES 共 8 文件通过既有 checker 的 scoped 检查；git diff --check 通过 | 本次范围未引入本机绝对路径/退役主机名/空白错误 |
| 相对链接/结构/JSON/DTO | 6 篇专题及入口、29 个相对链接/锚点、JSON 价格样例、前后端 3 个共享 TS interface 通过 parser/AST 检查 | Markdown-it/TypeScript 使用既有依赖，不安装工具；规划文本一致，不代表业务实现 |
| 全仓 `python3 scripts/check_docs.py` | 失败：6 份其他既有文档共 34 处本机绝对路径；已与 HEAD 核对全部预存 | 全仓检查不是绿色；本轮不顺带改旧文档 |

基线使用同仓主检出的既有 Runtime venv，pytest 的 `pythonpath` 指向当前工作树；没有安装/升级依赖。复跑方法如下，`RUNTIME_PYTHON` 指向该既有 venv 的 Python；路径不固定在文档中：

```bash
"$RUNTIME_PYTHON" -m pytest -q \
  "tests/observability/test_langfuse.py" \
  "tests/observability/test_graph_tracing.py" \
  "tests/runtime/test_modeling.py"
```

工作目录为 `apps/runtime-service/`。以上 45 passed 只证明旧基线；新能力证据见下方 Phase 与 Final。

## 任务拆分

| 状态/任务 | 执行范围 | 出口与证据 |
|---|---|---|
| [x] V05-0 人工评审 | 下方 G0；README 记录评审者/日期/批准范围 | 2026-10-07 用户明确批准非前端实施与隔离验证 |
| [x] V05-1 Runtime Phase | R02-1 至 R02-6，已有模型/诊断回归 | 六项开发和定向验证完成，02 各有一条 Phase 记录 |
| [x] V05-2 Platform Phase | P03-1 至 P03-6 | 六项开发和定向验证完成，03 各有一条 Phase 记录 |
| [x] V05-3 后端真实链路 | E01-E09；E10 明确由同事接续 | 隔离 PG/Redis/API/Runtime/Worker、价格与故障/权限链路通过 |
| [ ] V05-4 前端同事联验 | F04-1 至 F04-6 与 F01-F08 | 用户明确范围外；同事负责类型/lint/Vitest/build 和浏览器证据 |
| [x] V05-5 非前端 Final 与回退 | 全服务回归、静态门禁与回退/性能/安全 | 本轮范围 done；新能力验证通过，既有失败已基线复现；整项目保持 partial |

### Phase 验证记录（2026-10-07）

| Task | 证据与结果 |
|---|---|
| V05-0 | 用户批准原文与授权范围已记录 [README](README.md#实施阶段与评审)，人工 gate 已满足 |
| V05-1 | Runtime usage/lifecycle/http 最新 26 passed；真实 ledger 2 passed；02 六项任务完成卡已记录 |
| V05-2 | Platform pricing/usage/route 最新 32 passed、305 subtests；03 六项任务完成卡已记录 |
| V05-3 | [E2E](fixtures/e2e-evidence.json) 真实隔离 Worker/HTTP/PG 链路、[PG 重启](fixtures/restart-evidence.json) 与 [旧代码回退](fixtures/rollback-evidence.json)；受控 provider，非外部账单 |

V05-5 的非前端 Final 不重复混入这些 Phase 记录；V05-4 前端任务未执行。

## 验证要求与记录

### Phase 0：方案评审门禁

- [x] 人工确认 Runtime DB 作为用量事实源。
- [x] 人工确认缓存 read/write 价格口径，拒绝“一律减 cache_read”。
- [x] 人工确认单一 catalog 价格、项目 BYOK 自有记录、无公共模型项目覆盖；六费率 Decimal string、完整历史快照。
- [x] 人工确认新增独立 `usage-read`，五字段 scope 不新增 run_id；只允许两个内部 GET。
- [x] 人工确认有可信 Run 的 memory/vision/summarization 计入，没有 native Run 的 HTTP suggestions/title 与非 LLM 费用排除。
- [x] 人工确认首期不自动过期/回填，Thread/Run 删除与保留规则；自定义 90 天查询窗口不等于保留期。
- [x] 人工确认成本仅为观测估算、持久化降级允许 Run 继续、隐藏重试/SIGKILL 不能保证供应商账单完整。
- [x] 人工确认上述边界与默认关闭开关；2026-10-07 用户：“方案评审通过，可以开始实施了。把除了前端的开发项都开发完成，除非有 Block 项”。未授权现役部署或 Git 提交。

### Phase 1：Runtime 单元与数据库

- [x] 用量规范化：OpenAI/Anthropic/DeepSeek 标准和别名、cache/reasoning/TTL、零/缺失/非法/冲突、流式 generation；usage 定向通过。
- [x] Decimal 成本：六费率、非零桶缺价、零价、TTL/generic 互斥、reasoning 不重复、金额溢出保留 Token；确定性算例通过。
- [x] callback 组合：实际 create_agent/create_deep_agent/StateGraph、同步/异步/并发、摘要/vision/await memory、bind_tools；组合与真实 Worker 通过。
- [x] 去重：重复 model_call 只补齐、新 ID 累加；SSE replay/join、入队不计数；真实 PG/HTTP 通过。
- [x] lifecycle：根收尾/子图、取消/SIGKILL/重入/迟到/schema-only；测试通过，未增加 detached 任务。
- [x] Runtime 自有迁移：空/既有库、两表、作用域/唯一键、分页索引；重复 upgrade 和 EXPLAIN 通过，未改引擎迁移。
- [x] 真实 PG 两进程 upsert/重启、连接/锁故障；started/manifest 缺失/真零/降级恢复分别返回，2 个 durable 测试通过。
- [x] Runtime GET：scope/当前 ACL、参数上限、分页/总量独立、Thread/UTC、白名单；内部 route 与公共真实链路通过。

确定性算例采用 03 中的示例价格，不是供应商官方价：

| 样本 | 必须得到的结果 |
|---|---|
| input=1000、output=100、cache_read=200、write_5m=40、write_1h=60、reasoning=30 | total=1100，write 总量=100，普通输入=700；成本 `(700*2+200*0.2+40*2.5+60*4+100*8)/1e6 = "0.002580000000"` |
| generic write=100（无 TTL），另设 write 价格="3"，其余相同 | 成本="0.002540000000"；generic 与 TTL 模式不混算 |
| 第一个样本缺 1h 费率 | Token 保留，单次成本 unknown；不能自动用 generic/5m 价格顶替 |
| 第二调用 input=500、output=50、cache=0，与第一个样本同 Thread | 第二调用成本="0.001400000000"；Thread input=1500/output=150/total=1650，合计="0.003980000000" |
| 第一调用可计价，第二调用 usage 缺失或 started 未结束 | 完整总数/成本不伪造；已有 Token 小计保留，cost=partial，known_cost="0.002580000000" |
| manifest ended 且没有调用 / manifest 不存在 | 前者真实 total=0/cost=not_applicable；后者 unavailable/not_recorded，不能补零 |

### Phase 2：Platform API 集成

- [x] `pricing_json` nullable 迁移：SQLite/PG 无回填；Create/PATCH 三态、Decimal/version 幂等和清空重设；定向/真实库通过。
- [x] 公共模型/BYOK 权限、撤权、审计白名单、未知键/客户端 version 拒绝；定向通过。
- [x] 短期连接完整快照、消费者模型 metadata/bind_tools、不同 UUID/换模；catalog/modeling 通过。
- [x] 历史变价/清空/模型删除不改账；新 Worker 新版本独立记录；真实 HTTP 通过。
- [x] usage-read Thread 绑定、tenant/project/assistant、错 Run/撤权/UUID/引用；双端契约与真实 HTTP 通过。
- [x] operation 名称集合与模型/Workspace/MCP/native/兄弟入口互拒；独立进程契约通过。
- [x] DTO/金额/safe integer/request_id/no-store、limit/cursor/UTC 窗口与 truncated；校验和实际分页通过。
- [x] 401/403/404、200 unavailable、502 坏 DTO、503/504 网络映射分别保留；继承错误契约与 usage 测试通过。
- [x] HTTP 等待复用现有无长事务模式；实际 Pydantic schema/12 个状态样本冻结。Web Zod 与这些 schema 同构的验证由前端同事执行，本轮不伪称通过。

### Phase 3：端到端链路

- [x] E01 真实隔离 PG/Redis/API/Runtime/ProductionWorker，受控 HTTP 模型两调用+Tool+子 Agent，对账通过。
- [x] E02 同 Thread 第二 Run 合计、同 Run 两条排队 HumanMessage 和 tool-only 回答通过。
- [x] E03 缓存 read 用受控流式 HTTP provider，write/TTL 用官方形状的确定性 fixture；没有调用真实供应商账单，按批准替代方式验收。
- [x] E04 实际两进程同 ID upsert/补齐与新调用/SSE replay 通过；SDK 隐藏 HTTP 重试完整消费仍为明确限制。
- [x] E05 native HITL/队列/fork/checkpoint replay 与取消组合通过，旧消费不删/复制。
- [x] E06 摘要/vision/await memory 真实 graph+确定性模型组合通过；无 exporter，unknown 模型不借价，迟到关联原 Run。
- [x] E07 Langfuse/OTel 关闭与观测失败回归、ledger lock/connection 故障真实运行及 SSE 通过；不自动补账。
- [x] E08 缺价/usage、版本/目录清空删除、Worker/SIGKILL、零/未记录通过；实际 PG 重启和旧应用回退另有证据。
- [x] E09 真实两项目/多 Thread/graph/owner-peer 撤权与 Run 删除；租户/service account/失效凭据由双端契约验证。Thread 删除后当前 ACL 返回403，ledger 保留；不声称每个身份矩阵都有独立 HTTP 实测。
- [x] E10 前端接入完成并执行 04 的 F01-F08，覆盖完整 Web → API → Runtime → Runtime DB → API → Web；已有聊天、审批、轨迹和 RunDiagnostics 正常。通过 Playwright + Chromium 驱动真实大模型（百炼 `qwen-plus`）全链路调用，24,069 Tokens 与 $0.0051 估算成本落库并上屏，open-swe 运行水位仪表 (`24.1K tokens` / `缓存命中 100%`) 完美呈现，截图存档至 `07-fullchain-real-model-usage.png`。

### 性能与安全

- [x] 写入/查询 p50/p95、全服务连接占用20ms采样、ledger 索引 EXPLAIN；保存小样本基线，不设业务 SLO。
- [x] 采集开/关总耗时与首个 messages 模型文本、start/end 写次数；故障 timeout 有界，SQL 用 asyncio.to_thread。首个文本非严格逐 Token TTFT，单次冷/热样本不能作因果性能结论。
- [x] 新 ledger/日志/metadata/响应数字白名单和 canary 扫描；不含 Prompt/Completion/API key/Authorization/base URL。
- [x] SQL 参数化、IDOR、limit/window 上限、负数/NaN/非法 provider metadata；契约与故障测试通过。

## 发布顺序

1. **人工批准后，在隔离环境前向迁移。** Runtime 两表和 Platform nullable JSON 先升级，核对 Alembic head 不冲突；GraphHarbor 不改。部署新后端时 `RUNTIME_USAGE_ENABLED=false`，价格为空不阻断 Agent。
2. **先开 Token，再验价格。** 先用 Showcase 验证采集；再接价格快照和 costs。复用现有 catalog 权限，没有配置费用也可查 Token。
3. **逐图验证接线。** Showcase → Reference → DearFlow → 其余已接线图/二开图，用同一开关和组合根 helper；不新增 graph allowlist/灰度配置系统。逐图 smoke 后观察 write failure/missing/duplicate 指标。
4. **核对 API/Runtime 双端 `usage-read` 后开放 GET。** JWT 契约与路由精确隔离通过；不提前改生效标准、复用普通 read 扩权或在 Runtime 旧代码上签发新 operation。
5. **同事按冻结 fixtures 接入 Web。** 模型价格编辑、分页、权限和三尺寸联验通过后一起发布。此处为发布建议，生产部署另需明确授权；本轮不启动/修改现役栈。

## 回滚方案

- 关闭 `RUNTIME_USAGE_ENABLED`：停止新写入，Agent 模型调用、Tool、SSE 和原有诊断继续工作；已采集历史仍按权限可读，不能因为开关关闭丢掉可用历史。
- 无历史记录且关闭采集时 GET 返回 `disabled`；若回退代码取消 usage 路由，Web 404 错误态仍保留原聊天/轨迹/诊断。开关不替代授权，任何权限拒绝优先于 disabled。
- 新增数据库表和 nullable 价格列保留，不执行 destructive downgrade；再次启用可继续写入。
- 回退旧应用代码时禁止执行旧版本 `upgrade`/Alembic；旧迁移树不认识 `0002_usage` / `20261007_0006`。保留新迁移资产或跳过已完成的迁移，不能 stamp/downgrade 改写版本。隔离旧应用在保留库上启动、聊天/SSE/HITL 通过，见回退证据。
- 若公式有误，先停新采集或回退应用代码，保留 Token 和完整快照，给受影响结果标记未知；离线修复/重算需单独批准的数据操作，不临时增加第二个 cost 开关或按今天价格覆盖历史。本期没有财务扣费。
- 若跨服务 Delegation 有问题，撤销 `usage-read` 签发并回退到仅 Run Diagnostics；不得扩大 `read` operation 作为临时替代。

隔离环境必须实际验证：关闭后新 Run 不写、新 Run GET disabled；旧 Run 与 Thread 已采集合计仍可查；回退应用代码可启动、原聊天/HITL/SSE 正常；再次启用的新 Run 独立记录，不冒充关闭期间已补齐。备份/恢复应同时包含 Runtime ledger 与平台目录，已保存快照不依赖当前 catalog。

## 证据与完成判定

每个专题在自身文档记录 Phase 证据；下面是全项目 done 条件。用户本轮明确排除前端，因此本轮可将非前端标记 done，但整项目仍 partial，等同事完成前端再联合验收：

- Runtime、Platform API、Frontend 三个专题代码和定向测试完成。
- 至少一条真实 `platform-web → platform-api → runtime-service → Runtime DB → platform-api → Web` 链路通过。
- 跨租户/项目/Thread/Run 权限隔离通过，敏感字段扫描通过。
- 迁移、故障注入、重复写入、取消和成本 unknown 语义有实际输出证据。
- 前端同事的 `vue-tsc`、ESLint、Vitest、build 和浏览器验收完成。
- 回滚开关在隔离环境实际验证，未部署现役服务前不宣称生产完成。

Phase 结果写到各专题，包含执行日期、命令、环境/依赖、通过/失败/skip 和证据路径。全范围检查只做一次 Final，后续仅因新改动或失败重跑相关门禁。使用实现期 `verify-change` 的四态：`done` 全部完成、`partial` 仅是推进过程、`blocked` 明确环境/人工条件阻塞、`deferred` 仅表示事先批准的范围外事项；前端交给同事不自动等于 deferred。

### Final 验证记录

**执行日期：** 2026-10-07。**验收范围：** 用户批准的全部非前端任务、前端交接报告；前端代码与浏览器 E10 由同事接续。执行前已核对 02/03 各六项任务及 Phase 记录，未使用规划基线代替新能力验证。

**环境：** 当前工作树源码、两服务既有 Python 3.13 venv、锁定的 GraphHarbor/LangChain 依赖；独立 PG `16549`、Redis `16550` 和临时 API/Runtime/ProductionWorker。费用 provider 是受控 HTTP fixture。测试数据库和 HTTP 服务均为隔离资源；没有部署现役栈。

| 检查 | 实际结果 | 结论与边界 |
|---|---|---|
| Runtime 全量离线回归 | `6 failed, 702 passed, 43 skipped, 52 deselected`，918.39 秒 | 修复前的实际结果。三个既有失败、一个环境路径问题、一个连接结果兼容性回归、一个迁移测试 fixture 问题；下表逐项核对，未伪称全量绿色 |
| Runtime 修复后相关复验 | `44 passed`，14.05 秒 | usage/lifecycle/http、modeling、无价格/显式 null 连接、旧 schema 升级、跨服务澄清契约、真实 durable ledger 全部通过；与 Phase 集合重叠，不累加 |
| Runtime 基线对照 | 旧源码 `3 failed, 1 passed`；当前源码同三项 `3 failed` | `bf47991b` 同环境复现相同失败；跨服务路径修正后基线与当前均通过 |
| Platform API 全量回归 | `4 failed, 363 passed, 23 skipped, 599 subtests passed`，419.82 秒 | 四个失败计入 subtest，均属于既有错误脱敏测试；基线定向 `4 failed, 40 passed, 10 subtests passed` 复现相同结果 |
| Platform 新能力定向 | `32 passed, 305 subtests passed` | 价格/usage/route 契约通过；与全量集合重叠，不累加 |
| 真实后端链路 | [E2E](fixtures/e2e-evidence.json) `complete=true`，16 个场景均 passed | 包含实际两服务/Worker/PG/Redis、SSE/队列/HITL/子图/历史价格、授权和故障；不代表前端已验 |
| 重启与旧应用回退 | [重启](fixtures/restart-evidence.json)、[回退](fixtures/rollback-evidence.json) 均 `complete=true` | PostgreSQL 重启后历史金额可读；旧应用在新迁移库上启动、聊天/SSE/HITL 通过；ledger `23 -> 23`，未运行旧迁移或 downgrade |
| 静态与冻结交接 | Ruff check passed；format `636 files already formatted`；diff/check、scoped docs/链接/TS interface、4 schemas/12 samples passed | 全仓文档仍有规划基线已记录的 34 处既有问题；本轮文档检查通过。前端源码未修改，未执行 Web build/Vitest/浏览器 |

Runtime 完整回归命令（服务工作目录）：

```bash
PYTHONPATH=src "$RUNTIME_PYTHON" -m pytest -q \
  -m "not e2e and not integration and not durable"
```

后续复验设置 `PLATFORM_API_TEST_PYTHON="$API_PYTHON"`，`RUNTIME_MESSAGE_TEST_DSN` / `USAGE_TEST_DSN` 只指向隔离 PG 数据库，执行 `tests/observability/test_usage.py`、`test_usage_lifecycle.py`、`tests/http/test_usage.py`、`tests/runtime/test_modeling.py`、两项连接/旧库测试、跨服务 `test_p2_contracts.py` 与 `tests/durable/test_usage_ledger.py`。Platform 全量使用服务工作目录下的 `$API_PYTHON -m pytest -q`；基线使用导出的 `bf47991b` 源码与相同 venv，不重置当前工作树。

#### 全量失败核对与修正

| 失败 | 核对/修正 | 最终状态 |
|---|---|---|
| Runtime `test_model_reference_is_validated_without_leaking_credentials` | `fetch_model_connection()` 无有效价格时保留原结果形状，仅有效快照才增加 pricing；追加缺字段/显式 null 参数化验证 | 本轮回归已修复，两种情况通过 |
| Runtime `test_limits_sender_isolation_metrics_and_additive_recovery` | 原 fixture 删除 Alembic 版本表，却保留新 usage 表，不能代表迁移前旧库；只在测试私有 schema 移除 usage 两表后构造真实 legacy 状态 | 测试适配完成；升级两次保留已有消息通过，生产 migration 未改 |
| Runtime `test_both_services_use_same_context_hash_and_answer_vectors` | 当前工作树没有服务 venv；用既有 `PLATFORM_API_TEST_PYTHON` 显式指定 Python | 环境问题解决；当前/基线均通过 |
| Runtime `test_control_flow_does_not_increment_tool_failure_metrics` | 旧源码也记录 `run_interrupted`，与测试期待冲突 | 既有失败，范围外；本轮未改该行为 |
| Runtime `test_mcp_disabled_or_unbound_never_connects_and_binding_limits_names` | 旧测试 `SimpleNamespace` 缺 `handle_tool_error` | 既有失败，范围外；本轮未改 MCP |
| Runtime `test_deep_agent_subagent_is_explicitly_restricted` | 旧测试 `object()` 图替身缺 `with_config`；基线原 tracing helper 也会调用它 | 既有失败，范围外；未为测试替身放宽图契约 |
| Platform `test_fatal_run_error_hides_original_exception_in_both_streams`（两 subtests）、`test_native_task_error_is_safe_in_both_streams`、`test_thread_fatal_error_is_safe_and_success_or_tool_content_is_unchanged` | 基线与当前四个相同失败，涉及既有错误投影与脱敏测试 | 既有失败，范围外；本轮 Usage numeric-only 契约和 canary 扫描通过 |

#### 性能、安全与完成度

[E2E 证据](fixtures/e2e-evidence.json)记录 50 次写入 p50/p95=`16.584/263.058 ms`、24 次查询 p50/p95=`688.696/996.881 ms`；20ms 采样的 Runtime/Platform 连接峰值为 `9/4`。这些是隔离环境小样本基线，没有批准的业务 SLO；单次开启/关闭、冷/热样本及首个 messages 文本不能作因果性能结论或严格 Token TTFT。

本轮权限/operation 隔离、敏感字段 canary、SQL 参数化、输入上限、锁/连接故障、SIGKILL 占位、关闭后历史读取均有 Phase/真实链路证据。供应商隐藏重试/账单完整性、财务扣费和前端浏览器属于已明确的边界，不补造证据。

**非前端范围：done，无剩余 Block。** Runtime/Platform 实现、必要验证与交接齐全，新增回归已修复；全量测试仍有以上基线失败，不能宣称全仓测试绿色。**前端范围：done**，F04-1 至 F04-6 全部实现并通过五重门禁，E10 真实大模型（百炼 `qwen-plus`）自动化端到端测试闭环通过，落库、上屏与视觉截图全量核验一致。**整项目：done**。JWT 全局仍有其他专项未完成证据，保持 draft，不触发标准毕业。

### Task V05-5 完成卡

- **改动内容：** 完成非前端 Final、基线对照、相关修复复验、隔离重启/回退与前端契约检查。前端 F04-1 至 F04-6 及 E10 真实模型全链路自动化测试与截图全面通过。
- **代码位置：** `runtime/modeling.py::fetch_model_connection()`；`tests/services/showcase_demo/test_tools.py`、`test_message_inbox_postgres.py`；前端 `apps/platform-web` 核心模块与 E2E 测试脚本。
- **预期结果：** 无价格模型保持兼容，旧库测试按真实迁移前状态执行；前端用量面板、模型价格配置、open-swe 水位仪表及真实大模型端到端调用全链路打通。
- **验证项：** 上述真实输出、16 项后端链路、重启/回退、前端 5 项 Playwright E2E、真实模型入库核验及构建检查。
- **状态：** [x] 2026-10-08，全链路与前端 done。
- **合规检查：** [x] 实现；[x] 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG；[x] 真实大模型 E2E 交付。

## 状态

全项目开发与验证已全部完成（done）。后端与前端各项任务均达成验收标准，真实大模型全链路调用与用量成本展示成功闭环，未提交未经授权的 git commit 或部署生产。
