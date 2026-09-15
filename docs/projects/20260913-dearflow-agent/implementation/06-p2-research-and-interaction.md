# P2 研究与交互实施记录

日期：2026-09-14。用户已批准一次完成 P2 后端；不修改前端，前端接入另记交接文档。阶段入口为 [P2 执行包](../phases/P2-研究与交互基础.md)。本记录随切片验证更新，不以代码存在代替完成。

## 切片一：模式与 Context（实施中）

修改 Runtime `runtime/contracts.py`、`runtime/resolver.py`，新增 execution_mode 并纳入 Context/config v2 哈希和快照；不带模式的既有配置继续 v1。Platform `core/runtime_contract.py`、`modules/agents/application/service.py`、`modules/runtime_gateway/application/service.py`、`adapters/langgraph/parameter_schema.py` 同步参数校验、默认值、签发快照及可编辑字段。路径均以各服务 `src/` 为根。

`apps/runtime-service/src/runtime_service/services/dearflow_agent/modes.py` 修正未知模式静默回落、模式预算与推理参数；仅对已明确支持的 DeepSeek V4 参数映射，其余模型保持原参数并记录不支持原因，不谎称 Flash 已关闭思考。模式不增加模型／工具权限。

兼容规则：缺省／null execution_mode 的历史配置按 v1；新 Dear 请求补 standard 后使用 v2，已保存请求快照的 resume 沿用原版本。该规则无需改数据库或回写 checkpoint。双端测试向量与恢复测试通过后再标完成。

## 官方依据

已查询 LangChain Docs 的 DeepAgents customization／context-engineering 和 Reference create_deep_agent。文档版本可能新于锁版本，实际装配以本机 deepagents 0.7.8 源码和组合测试为准。使用官方中间件、工具与 SubAgent，不新建运行循环。

## 验证与状态

- Runtime 工作目录执行 `.venv/bin/python -m pytest -q tests/runtime tests/services/dearflow_agent/test_modes.py`：52 passed in 30.44s。
- Platform 工作目录执行 `.venv/bin/python -m unittest discover -s tests -p test_run_requests.py -q`：20 tests OK。
- Runtime `test_agent.py`＋`test_modes.py`：19 passed in 125.85s，覆盖既有文件审批／权限底座回归。
- Runtime `test_p2_contracts.py`：1 passed in 39.16s。运行同一组七类字段输入于 Runtime 与 Platform，并比对 Context v2 哈希。没有把 Runtime schema 跨服务导入业务代码。

## 切片二：七类澄清字段（双端校验 done）

`apps/runtime-service/src/runtime_service/services/dearflow_agent/schemas.py:ClarificationField/validate_answer` 与 `apps/platform-api/src/platform_api/modules/runtime_gateway/application/clarification.py:_validate` 扩展 textarea、number、multi_select、checkbox、date。checkbox 的 required 表示必须提交布尔值，不代表强制勾选；数字拒绝 bool／非有限值；日期要求 YYYY-MM-DD 且真实存在。保持 v1 envelope，按字段能力协商；老前端必须拒绝不认识的字段，不能自动跳过。

`tools/human_input.py` 更新工具说明，`middleware/clarification.py` 在模型返回边界验证完整请求；畸形 schema 明确失败，不额外建立修正循环、不静默删字段。已有混批拒绝保持。

## 切片三至五（实施与验证中）

研究使用已配置的 Tavily search/extract：`tools/search.py`。Runtime 只向固定供应商 HTTPS 地址请求，不提供宿主任意 URL 抓取。提交及返回 URL 拒绝私网 IP、凭据、非 HTTP(S)、危险端口及本地域名；DNS／站点重定向／最终提取由供应商处理，不宣称本机校验能证明供应商每一跳。本机代理将 dev.to 解析到 198.18.0.77，因此不再用本机代理 DNS 校验远端抓取目标。需要自托管抓取器时另补连接 IP 固定与逐跳验证。来源持久写入只读 sources，ToolMessage.artifact 记录受信线程／调用／内容哈希。

普通 MCP `tools/mcp.py` 使用现有受信 resource binding、官方适配器与服务端 `RUNTIME_MCP_CONNECTIONS_JSON`；每个连接声明 allowed_tools（mcp_ 前缀），仅接明确 readOnlyHint 的工具；写工具在 P2 拒绝，不把只读权限当发布授权。

`subagents/researcher.py` 覆盖官方隐式 general-purpose 角色，只允许研究／读取，禁止再次委派和写入；`middleware/delegation.py` 限制每图最多 3 个并行 task。官方 ToolCallLimitMiddleware 持久 thread_limit=8 限制累计委派；模型和总工具同样设置 thread_limit，重启不会重置。当前是保守的整线程累计上限，不额外建立任务预算账本；达到上限明确结束，不声称预算能精确归属独立 child。

队列直接装配 `middlewares/message_queue.py`；Platform `modules/runtime_gateway/application/service.py:enqueue_thread_message` 和 Runtime `webapp.py:enqueue_message` 增加 Dear 授权图，继续沿用数据库消息与授权对账。

进行中（partial）。后续切片与测试结果在实施时逐项补充。

### 本轮新增验证与修复

- `test_research.py`：9 passed in 99.47s（含 `DEAR_RESEARCH_LIVE_TEST=1` 真实 Tavily）。`test_ultra_uses_restricted_child_and_pro_cannot_delegate`：1 passed in 80.47s。
- `test_mcp_tools.py`：1 passed in 83.12s，官方独立 HTTP MCP 测试服务；使用官方会话上下文、不自建连接池，测试覆盖调用与断连，未单独断言服务端残留会话计数。
- Platform `test_runtime_gateway*.py`：40 tests OK in 35.366s。
- 真实独立 PostgreSQL 队列原回归 20 passed、1 skipped、2 failed；两项失败发生在进程启动前，冷导入实测 46.5 秒，超过测试原 25 秒。`apps/runtime-service/tests/services/test_message_inbox_postgres.py` 把包含冷导入的启动／恢复子进程期限改为 90 秒；两项重跑 2 passed in 214.57s。
- `apps/runtime-service/src/runtime_service/webapp.py` 移除延迟类型注解，修复动态模块加载时 EnqueueMessage 的 Pydantic forward reference 500；正常 import 测试无法覆盖，新增 `test_dynamic_webapp.py` 复现真实动态加载模型校验。
- `services/dearflow_agent/workspace/backend.py:build_backend` 增加官方 large_tool_results 的 checkpoint StateBackend 路由，避免大结果自动外置触发默认工作区写入拒绝；与 conversation_history 一起禁止模型通过文件工具改写。
- 完整平台研究任务首次失败：project `41e4b7c6-b12a-4832-8bf4-54fbfe3f913e`，thread `4237c52f-8e85-4037-a433-72714a57f357`，初始 run `7e5e01ea-79be-4f8c-be6f-65ca34316d39`；入队触发上述 500。保持失败证据，修复后另起独立测试线程，不覆盖原记录。

- `webapp.py` 两处本机自查询 HTTP 客户端设置 trust_env=False，固定本地内部调用不经过环境代理；重试后入队及重复请求均为 202。没有放宽身份／Run 归属校验。
- 后续 thread `58f82bc2-9dae-41f8-b85b-9aa6dd46425b` 入队成功但消费失败，Worker 明确报 `Message authorization callback is not configured`。`scripts/local-stack.sh:start_managed_key` 在已有 Worker 命令中设置本机 Platform 消息授权回调，在 API 命令设置与启动端口一致的 RUNTIME_SELF_URL。未修改 .env 或生产配置。
- `test_context.py`：2 passed in 89.36s。官方摘要保存历史并保留队列私有回执；重建图后官方 thread_limit 继续生效。测试读取原始 checkpoint 私有状态，不将其当公共 state 字段；历史文件通过 CompositeBackend 路由落入 checkpoint。
- `test_p2_contracts.py`＋`test_dynamic_webapp.py`：2 passed in 55.85s，含超大整数拒绝和真实动态模块加载回归。
- 来源写入改为临时文件＋原子硬链接＋哈希校验，避免多个并行研究调用写同一来源出现部分文件。改后来源组合测试 1 passed in 80.33s；provider 错误、响应大小、缺配置、大正文外置测试 1 passed in 63.29s。
- `uvx ruff check --select F` 对本轮 Dear 业务／测试、Runtime Context／webapp、Platform Context／clarification 执行通过。使用临时工具环境，未添加或升级项目依赖；这只是 F 规则检查，不冒称全量类型检查。

## 逐文件排查索引

以下均为仓库相对路径；本轮没有前端代码修改。

| 文件 | 关键符号／原因 | 测试 |
|---|---|---|
| `apps/runtime-service/src/runtime_service/runtime/contracts.py`、`runtime/resolver.py` | RuntimeContext、ResolvedRuntimeConfig、parse_runtime_context、runtime_context_hash、快照恢复；v1/v2 哈希边界 | tests/runtime、test_modes、test_p2_contracts |
| `apps/platform-api/src/platform_api/core/runtime_contract.py` | 运行模式输入校验、字段白名单和参数 schema | test_p2_contracts、网关回归 |
| `apps/platform-api/src/platform_api/modules/agents/application/service.py` | _normalize_agent_context 支持模式默认值 | 网关／Agent 契约回归 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | _runtime_context_snapshot、_inject_project_default_model、enqueue_thread_message；模式签发与队列授权图 | test_run_requests、test_platform |
| `apps/platform-api/src/platform_api/adapters/langgraph/parameter_schema.py` | 模式纳入服务端可编辑参数 | 网关回归 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`、`modes.py`、`prompts.py` | 唯一组合根；有效模式、显式 Todo、中间件、追踪；无新 Agent 循环 | test_agent、test_modes、test_research、test_platform |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/capabilities.py` | 单一权限映射、能力声明、服务端 MCP allowed_tools 目录 | MCP／平台能力查询 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/search.py` | tavily、public_url、_evidence、build_research_tools；固定服务商、总时限30秒、正文1MiB上限、原子证据与截断 | test_research |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/mcp.py` | load_mcp_tools：先授权、再官方 discovery；只读／冲突／绑定检查 | test_mcp_tools |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents/researcher.py`、`middleware/delegation.py` | 一个受限同步研究角色、最多3个并行 task | test_research 的 Ultra 场景 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/schemas.py`、`tools/human_input.py`、`middleware/clarification.py` | 七字段及模型响应边界校验 | test_p2_contracts、test_agent |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/clarification.py` | 网关按当前 interrupt 校验恢复答案，不创建非法 Run | test_p2_contracts、test_run_requests |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py` | 官方摘要和大结果的 StateBackend 路由 | test_context |
| `apps/runtime-service/src/runtime_service/webapp.py` | 动态导入类型修复、队列 scope、内部 HTTP 禁环境代理 | test_dynamic_webapp、队列回归、test_platform |
| `scripts/local-stack.sh` | 本机 API 自查询地址与 Worker 消息授权回调 | bash -n、真实平台部署 |
| `apps/runtime-service/tests/services/test_message_inbox_postgres.py` | 只调整启动等待上限，区分冷导入与真实恢复时限 | 两个故障窗口实际进程恢复 |
| `apps/runtime-service/tests/services/dearflow_agent/test_platform.py` | 新增研究 opt-in：Pro、七字段、队列去重／消费、来源、审批发布和重启 | 完整本机平台 HTTP 门禁 |

新增测试完整目录为 `apps/runtime-service/tests/services/dearflow_agent/`：`test_modes.py`、`test_p2_contracts.py`、`test_research.py`、`test_mcp_tools.py`、`test_context.py`、`test_dynamic_webapp.py`。前端接入仅更新本项目 `frontend-handoff.md`。

### 最终部署排障（持续更新）

- 较广 Dear 回归：36 passed、1 skipped、1 failed；唯一失败为 `test_restart.py` 的 90 秒子进程超时。增加 faulthandler 后证据显示 60 秒仍在导入 `deepagents → langchain_anthropic → anthropic`，未开始恢复业务。该测试进程总期限调整为 240 秒并保留超时栈，业务运行超时不变；待重跑结果。
- thread `cd1a91d0-1982-4dee-8410-4de569061481`／run `3b0388c6-29c8-4ad5-963f-d6888d699798` 失败：消息授权回调 HTTP 502，另有 Redis 控制流超时。`apps/runtime-service/src/runtime_service/middlewares/message_queue.py:abefore_model` 内部授权客户端补 `trust_env=False`，不禁用授权、不放宽权限。尚不能证明所有超时均由环境代理造成。
- `tools/search.py:tavily` 允许供应商可选 `raw_content=null`，仍拒绝非字符串正文；fetch 的实际正文必须非空。`test_research.py:test_provider_errors_and_large_results` 增加可选空字段向量。
- 后续真实平台 thread `733665d1-d94f-4eaa-b33a-fab99ca3b9c0` 已成功七字段中断、Worker 重启后 checkpoint 一致并提交 resume；最终报告发布仍在验证中。
- 冷启动诊断后的重跑：`DEAR_TEST_DATABASE_URI=<独立测试库> DEAR_RESEARCH_LIVE_TEST=1 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_restart.py tests/services/dearflow_agent/test_research.py --tb=short`：**12 passed，429.53s**。含真实 PostgreSQL 跨进程审批恢复、真实 Tavily 搜索／提取、四模式／受限子图、来源及供应商失败；存在第三方 Pydantic／SWIG 警告，非零警告未隐藏。
- 内部授权直连调整后，`RUNTIME_MESSAGE_TEST_DSN=<独立测试库> .venv/bin/python -m pytest -q tests/services/test_message_inbox_postgres.py -k running_tool --tb=short`：**3 passed、1 skipped，44.42s**。覆盖授权成功／撤权／授权服务不可用；跳过的是旧真实模型探针，Dear 平台真模型链路独立验收。
- `apps/platform-api/tests/test_run_requests.py:test_standard_multi_resume_uses_parent_config_and_current_authorization` 增加原 Pro 模式继承及 resume 改 Ultra 被拒绝的断言。Platform `.venv/bin/python -m unittest discover -s tests -p test_run_requests.py -q`：**20 tests OK，22.861s**。
- 本轮最终静态检查：Dear 业务／测试及共享队列 `uvx ruff check --select F` 通过；`python3 scripts/check_docs.py` 与 `git diff --check` 通过。未声称全仓类型检查或生产联合验收。
- thread `733665d1-d94f-4eaa-b33a-fab99ca3b9c0` 最终发布 Run `342bb241-8d25-4938-9bff-934535b43445`：脚本达到 720 秒总期限，832.65 秒后退出失败。后续只读核验已确认产物哈希、真实来源 URL、补充标记和 consumed 回执全部正确，但当时 Run 仍 running，故不把此次记为完整通过。修正 `test_platform.py` 的超时提示，并把包含多轮 HITL 和 Worker 冷重启的测试总期限改为 1200 秒；不改变 Worker 300 秒运行限制。新线程独立重跑。
- `agent.py` 补 `policy_hash`（受信 RuntimePolicy 的确定性 JSON SHA-256）；`modes.py:apply_reasoning` 追踪仅返回本次 thinking／reasoning_effort 控制值，不回显模型原有 extra_body。`test_modes.py` 增加扩展字段不进入追踪的回归。

## 最终结果与复核命令

**功能交付：已实现；阶段验收：partial。** 真实 Pro 平台研究链路已最终成功；连续运行稳定性和外部观测导出未通过，前端本轮后置。不得把本节理解为生产联合验收完成。

- 成功线程 `733665d1-d94f-4eaa-b33a-fab99ca3b9c0` 的最终 Run `342bb241-8d25-4938-9bff-934535b43445` 后续确认为 **success**。原测试客户端因总期限先退出，但服务器仍继续完成。此前同一线程已验证七字段、重复入队、Worker 重启保持 checkpoint、多轮官方审批恢复。新增 `test_platform.py:test_completed_research_delivery` 对保留数据作只读验收：**1 passed、1 deselected，49.83s**，校验终态、空 next、所需工具、下载哈希、来源 URL／线程、报告补充标记、唯一 consumed 回执及消息不重复。该复核不重新创建任务，也不假称重放了重启步骤。
- 后续独立重复运行 project `5756a6da-a7c2-4a2a-b019-c337d3c2fc59`／thread `dcd2ea14-3f93-4c73-81e4-6fa7da15243f`／run `2e836906-afc2-4db8-aef3-36682e51ac39`：**失败，572.81s**。Worker 日志出现 Redis event transport/control key 超时，最终 `graphharbor.run_timeout`；这证明当前本机运行尚不稳定，不证明业务已经连续通过。失败的测试模型已禁用，原记录保留。未改 Redis 配置、关闭鉴权或提高 Worker 300 秒限制来掩盖失败。
- 追踪字段最终修改后 `test_modes.py`：**2 passed，29.53s**；`test_agent.py -k clarification_and_rebuilt`：**1 passed、16 deselected，94.37s**。
- Ruff 联网重跑曾因 PyPI 连接超时失败，使用本机已有缓存 `uvx --offline ruff check --select F ...` 后通过；未安装新核心依赖。

在 `apps/runtime-service/` 执行以下只读复核（需要本机 Platform 2142 及上述测试记录仍保留）：

```bash
DEAR_COMPLETED_RESEARCH=946ff99e-768a-42a3-adc2-33bbe24685f3,733665d1-d94f-4eaa-b33a-fab99ca3b9c0,342bb241-8d25-4938-9bff-934535b43445 \
  .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py -k completed_research --tb=short
```

重新创建完整验收任务（会创建独立测试项目／线程／模型，使用真实模型及 Tavily，并重启本机 Worker）：

```bash
DEAR_PLATFORM_TEST=1 DEAR_PLATFORM_RESEARCH_TEST=1 DEAR_PLATFORM_RESTART_TEST=1 \
  .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py -k creates_and_completes --tb=short -s
```

### 已知边界与接续

1. 先排查本机 Redis／Docker 延迟与 Worker 事件传输，再重跑上述完整验收，不重复实现已通过的 P2 功能。保留 `runtime-worker.log` 中目标 run_id 的事件与异常；不要输出模型正文或凭据。
2. MCP 仅开放已声明的只读工具，连接使用受信 `runtime_resource_bindings` 与服务器 `RUNTIME_MCP_CONNECTIONS_JSON.allowed_tools`；没有新增用户自助绑定接口。运维需先提供现有受信绑定，任意外部 MCP 或写工具不在本次完成范围。
3. 模型／工具预算是整线程保守累计上限，独立 child 取消与用量账本后置；23 个业务 Skills 从 P4 逐项迁移。
4. 前端对接项见 `frontend-handoff.md` 的 P2 小节。本轮没有修改前端代码；工作树中已有前端修改不归入本次后端实现。
