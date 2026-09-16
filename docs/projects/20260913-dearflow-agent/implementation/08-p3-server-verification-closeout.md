# P3 后端收口：通用 Server 修复、真实回放与观测

日期：2026-09-15。用户授权继续实现、发布 GraphHarbor 并更新本地 Worker；前端仍只交接。本记录接续07，更新此前未经证实的性能结论，阶段最终状态见P3执行包。

## 边界

| 所属 | 本轮负责内容 | 不放入此层的内容 |
|---|---|---|
| GraphHarbor | 原生LangGraph v3子图lifecycle不丢失；事件持久化、回放和根Run终态保持既有机制 | Dear Agent、技能、工作区、模型凭据、业务权限、子任务账本 |
| platform-api | 透传显式流版本并校验；修复已有模型更新服务字段与UUID比较错误 | 不在Server修业务模型目录 |
| runtime-service | 升级官方安装包；Dear组合回归、平台真实双子任务／父取消、Langfuse导出验证 | 不修改site-packages、不加执行器、不引入私有事件 |
| platform-web | 仅更新交接文档 | 本轮不实现前端 |

## 为什么先前会超时：证据与纠正

07记录的58—80秒事件滞后和300秒Run超时是真实现象，但不足以确定瓶颈在`MAX(sequence)`。本轮检查证实：

1. 真实PostgreSQL `EXPLAIN` 使用 `Limit → Index Only Scan Backward using ix_runtime_events_thread_seq`，不是全表扫描；先前平方复杂度的说法撤回。
2. **未升级的post27** 已跑完双子Agent、成功结果与checkpoint回读。测试总计12.57秒，最后因禁用测试模型返回500而失败；不能算测试全绿，但证明无需Server性能改动即可完成该运行。
3. 此前“仅游标为0时查历史”的优化会在非零旧游标时产生重复序号。新增数据库回归先失败后恢复通过，该优化已撤回，未进入post28。`record_event`生产代码与原post27相同。
4. 另一条post27运行在单模型调用30秒预算触发`ModelCallTimeoutMiddleware`，经既有Worker重试后error（96.99秒）；这与先前Worker300秒timeout是不同故障。没有通过放宽超时或关闭追踪掩盖问题。

因此只能确认复杂子图增加事件和模型调用数量、对环境波动更敏感；历史长延迟根因尚无可重复的性能归因。本轮不引入未经测量的批处理、异步落库或取消缓存。真实成功、失败与外部观测分别记录，不能宣称Server优化带来数十倍提速。

## 修改文件与函数

### GraphHarbor 仓库（本机 checkout 路径由开发环境配置）

| 路径 | 函数／改动 |
|---|---|
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | `_promote_protocol_run_start`保留version；`launch_runtime_run`在持久提交前统一限制v2/v3，非法版本拒绝，默认不变 |
| `apps/platform-api/src/platform_api/core/runtime_contract.py` | `normalize_protocol_v2_command`的run.start白名单允许version；实际枚举由统一提交边界校验。补命令入口回归时先复现白名单拒绝，再修复 |
| `apps/platform-api/src/platform_api/adapters/langgraph/runs_sdk_adapter.py` | `create`显式version复用现有`request_json`发往原生Run端点；锁定SDK的create不接受version，普通请求仍走SDK。保留授权及幂等头、已有参数白名单 |
| `apps/platform-api/tests/test_run_requests.py`、`apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py` | 验证Run创建及run.start命令版本透传、非法版本不提交、原生HTTP payload与幂等头不丢失 |
| `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/graph_executor.py` | `invoke_graph`只过滤真正根lifecycle；子scope在`params.data.namespace`时保留started/completed及cause；外层协议不私自改写 |
| `libs/langgraph-runtime-pg/tests/test_public_runtime.py` | `test_executor_preserves_subgraph_namespace_and_interrupts`真实子图事件先复现丢失，再验证修复和interrupt兼容 |
| `libs/langgraph-runtime-pg/tests/test_production_contract.py` | `test_record_event_repairs_stale_sequence_counters`覆盖0与非零旧游标，防止“优化”破坏单调序号 |
| `libs/langgraph-runtime-pg/pyproject.toml`、`libs/langhost/pyproject.toml`、`scripts/check_versions.py`、`uv.lock` | 两包锁步post28，无生态依赖升级 |
| `docs/release-notes-0.13.0.post28.md` | 通用边界、验证、发布与纠错记录 |

源码与当前项目安装的post27逐文件比较：本版唯一运行时代码差异为`graph_executor.py`；原工作树已有但已发布的post27内容没有当成本次新修复。

### 当前仓库

| 路径 | 函数／改动 |
|---|---|
| `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py` | `update_model`读取`StoredRuntimeModel.model_name`；同一模型比较UUID对UUID，修复500及随后可能的假重复409 |
| `apps/platform-api/tests/test_model_catalog_and_policy_uniqueness.py` | 创建真实数据库模型后经service禁用，验证名称保持、不能误判自己为重复模型 |
| `apps/runtime-service/pyproject.toml`、`apps/runtime-service/uv.lock` | 从PyPI锁定安装graphharbor及runtime的post28 |
| `apps/runtime-service/tests/services/dearflow_agent/test_subagents.py` | 校验安装包转发真实lifecycle cause；新增opt-in Langfuse只读验收，两子Agent的模型调用沿parentObservationId回溯，用量取实际GENERATION |
| `apps/runtime-service/tests/services/dearflow_agent/test_platform.py` | 成功后经平台网关回放SSE，检查两个子图started/completed及分派调用ID；保留结果、checkpoint和父取消验收 |

## 已完成验证

- 独立创建`graphharbor_p3_perf_20260915`测试库，使用本机已有角色，Redis DB14／专用前缀。解决默认postgres角色不存在的测试配置错误；未修改业务库、未调整角色权限。
- GraphHarbor全量：**151 passed、18 skipped，67.92s**。跳过live-server和已迁到业务层的测试，不计通过。独立production contract：**50 passed、4 skipped，20.38s**。
- GraphHarbor `ruff check .`、CI范围`ruff format --check libs`、mypy36源文件、`uv lock --check`、`scripts/check_versions.py`：通过。全仓库格式检查的5个存量Markdown／acceptance文件提示不归本轮修改，已明确记录。
- Platform模型目录与委托回归：**2＋12项 unittest通过**。重启本地Platform API后，对之前残留测试模型禁用返回200。
- Langfuse真实trace `a694ddc8c577647853970af0541b15d3`，thread `8f5a5986-08d0-4f5d-b018-6de5a4b7525e`：**1 passed、2 deselected，10.39s**。两子Agent均有实际GENERATION用量和父关联；四个受信装配字段可查询。未将非模型CHAIN的0用量当真实子Agent费用。

Langfuse复核命令（Runtime目录，使用已配置的LANGFUSE环境变量）：

```bash
DEAR_SUBAGENT_TRACE_THREAD=8f5a5986-08d0-4f5d-b018-6de5a4b7525e .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_subagents.py -k live_subagent_trace --tb=short -s
```

## 发布与安装

- 已构建并发布PyPI `graphharbor==0.13.0.post28` 和 `graphharbor-runtime==0.13.0.post28`，四份产物的远端SHA256与本机构建一致。
- 发布凭据由用户指定文件读入子进程环境；未输出、写文档或传入命令参数。
- 独立wheel安装CLI校验为post28；当前项目`uv lock`仅更新两个包，`uv sync --frozen`已安装。
- 无数据库迁移、无依赖打补丁、无git提交或推送。重启仅针对已授权的本地Platform API／Runtime API／Worker。

## 官方 v3 调研与接入

官方文档：[LangGraph lifecycle](https://docs.langchain.com/oss/python/langgraph/event-streaming#lifecycle)、[LangChain event streaming](https://docs.langchain.com/oss/python/langchain/event-streaming)。最新文档推荐多数应用使用`stream_events(..., version="v3")`；本项目锁定LangGraph 1.2.11／Deep Agents 0.7.8仍有beta提示，所以保留v2默认，显式v3已贯通。Docs MCP与锁定源码／真实运行交叉核实；Reference未找到对应符号，未据此声称API参考已确认。

| 能力 | v2 | v3 |
|---|---|---|
| 消息、状态与工具结果 | 保留既有流／Run状态查询 | 官方typed envelope，同样保留 |
| lifecycle通道 | 当前Server明确不输出；不能当成事件丢失 | 根及子图生命周期；started／running／completed／failed／interrupted |
| 子任务归属 | 已有debug事实映射与根ToolMessage；未知不能猜测 | `params.data.namespace`与`cause.tool_call_id`；不拿外层namespace替代实际子scope |
| 取消与恢复 | 既有父Run cancel、checkpoint | 生命周期只是事实通知，不增加独立子取消、独立恢复或计费能力 |

平台`POST /api/langgraph/threads/{thread_id}/runs`或`run.start.params`显式传`version: "v3"`；已有GET Run stream按持久Run版本回放。当前平台resume入口禁止覆盖运行配置，本轮没有放宽该安全边界；需要v3跨resume连续体验时，F3应验证新Run实际版本，不能假设自动继承。v3图事件版本、SDK方法参数和HTTP流版本不可混为一谈。

真实Deep Agents子图发出`running`，确定性StateGraph测试发出`started`，两者均为官方事件，生产方不做私有改名。根终态以Worker持久提交后的事实为准；UI不能把流结束或取消ACK当成功。

## post28 安装后的验证

- 平台Run请求：21项unittest通过（含创建及run.start命令v2/v3与非法版本）；SDK适配器13项、Runtime契约14项通过。
- 显式v3真实双子Agent：**1 passed，7.74s**；project `c1acc2c4-e506-43d5-b404-c67a430e9b80`、thread `24a025be-cd42-4675-a3ed-c30d58ea5a01`、run `9bb2f9a4-dff8-447f-af5a-edffa78d4182`。验证两份ALPHA/BETA结果、父输入隔离、checkpoint回读、HTTP生命周期回放、两个不同namespace及分派调用ID、根completed/success。
- 首次v3验收误把启动事件限定为started而失败（8.04s）；只读回放证明实际为running，修正断言后通过，并非生产事件再次丢失。
- 显式v2真实双任务：**1 passed，10.89s**；thread `34ceacfa-8303-4668-9e0f-a61c77b345f4`、run `87e5f49c-331c-4b93-a531-f86b4ef4e506`。根结果与checkpoint通过，回放无lifecycle符合v2契约。
- 未传version的默认兼容路径：**1 passed，10.50s**；thread `c45f5d92-cef4-4824-8c27-eba33042549b`、run `fb816b2e-9f57-4fbe-8b2d-ea752717dcbb`，默认SDK创建、双任务结果、checkpoint、v2回放均通过。测试已改为仅环境变量显式指定时才传version。
- 显式v3创建后的真实父取消：**1 passed，3.36s**；thread `1c415a04-b3be-44c2-b615-23a6c6a52546`、run `ee2a7d6d-f1f7-47d1-9709-58d57c06a440`。发现两个task后取消，查询到interrupted，不以ACK代替终态。
- 最新子图组合及平台默认关闭开关回归：**2 passed、3 skipped，8.22s**。跳过Langfuse和两项真实平台opt-in，不当作成功证据；相应真实测试另列。保留依赖SWIG、Context序列化与v3 beta警告。
- 修改Python文件`ruff --select E9,F`通过；完整规则仍有存量风格诊断，与HEAD逐文件比较仅新增一处import排序，已修复，未顺带格式化历史文件。两仓库`git diff --check`及项目`python3 scripts/check_docs.py`通过。

Runtime目录复验命令：

```bash
DEAR_PLATFORM_TEST=1 DEAR_PLATFORM_SUBAGENT_TEST=1 DEAR_PLATFORM_STREAM_VERSION=v3 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py -k creates_and_completes --tb=short -s
DEAR_PLATFORM_TEST=1 DEAR_PLATFORM_SUBAGENT_TEST=1 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py -k creates_and_completes --tb=short -s
DEAR_PLATFORM_TEST=1 DEAR_PLATFORM_SUBAGENT_TEST=1 DEAR_PLATFORM_CANCEL_CHILDREN=1 DEAR_PLATFORM_STREAM_VERSION=v3 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py -k creates_and_completes --tb=short -s
```

前端F3独立deferred；历史长延迟的根因仍未证实，不因本次成功宣称已完成生产稳定性验收。
