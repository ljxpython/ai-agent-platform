# F04 工具输出预算：复用核查与最小补齐方案

> 2026-10-09，用户已完成人工评审并批准实施。非前端范围已完成实现与必要验证，只剩同事负责的前端回归及其完成后的 Final；整体 partial。
> 本篇细化 [12/T07](12-completion-plan.md) 的上下文与工具结果切片；不新建第二个迁移项目。F04 不代表 T07 或整个 DearFlow 迁移已完成。

## 目标

让大工具结果可恢复、模型输入有界，同时避免重复开发已有外置、存储、预览和摘要机制。本轮实施范围只限F04；前端由同事接续，见[F04前端交接](frontend-handoff-f04.md)。

**结论：补齐效果，复用官方外置而不新增完整 `ToolOutputBudgetMiddleware`。** 工具结果外置、文件载体、head/tail 预览都已有；增量为恢复官方历史大参数压缩、按模型窗口收紧外置阈值，并补组合验证。实施复现父子图同 call ID 覆盖原文后，增加官方 Filesystem 薄扩展：新结果路径包含正文 SHA256；不重写外置、预览或存储算法。DeerFlow 的严格成功覆盖判定继续延期。

## 方案设计

### 1. 证据与比较边界

核查日期、版本、文件摘要、实际命令和探针输出见 [取证记录](evidence/20261009-f04-review.md)。当前平台 HEAD 为 `85d63d87bdf84dabbb963f79e8dd4b2db4432ade`，开始时工作树干净；参考为用户指定的本机 DeerFlow/Open-SWE 工作树，不把它们当公开发行版。

下文使用路径前缀，展开后就是完整代码位置：

- `R` = `apps/runtime-service/src/runtime_service/`。
- `P` = `apps/platform-api/src/platform_api/`。
- `W` = `apps/platform-web/src/`。
- `DF` = `<research-root>/deer-flow/backend/packages/harness/deerflow/`。
- `OS` = `<research-root>/open-swe/agent/`。
- `DA` = 已安装的 `deepagents 0.7.8` 包根；当前 `uv.lock` 同样锁定此版本。

官方资料已查询 LangChain Docs/Reference MCP：[上下文工程](https://docs.langchain.com/oss/python/deepagents/context-engineering)、[FilesystemMiddleware](https://reference.langchain.com/python/deepagents/middleware/filesystem/FilesystemMiddleware)。线上文档可能领先锁版本；下面参数名、阈值和状态行为以本机 0.7.8 源码及实测为准。

### 2. DeerFlow 实际怎么做

| 机制 | 当前本机实现 | 可借鉴的点与限制 |
|---|---|---|
| 执行后预算 | `DF/agents/middlewares/tool_output_budget_middleware.py::ToolOutputBudgetMiddleware.wrap_tool_call/awrap_tool_call` | 返回后检查 `ToolMessage` 或 `Command.update.messages`，超限保存全文并替换正文；替换结果会进入 graph state |
| 阈值与失败降级 | `DF/config/tool_output_config.py::ToolOutputConfig` | 默认 `externalize_min_chars=12000`；预览 head=2000、tail=1000；存储失败 fallback 上限=30000 字符。不是同事描述的 50000/2000/2000 |
| 文件落地 | 同中间件 `_externalize/_externalize_to_sandbox` | 挂载沙箱写 host outputs，远程沙箱直接写虚拟 outputs 并检查存在；解决“host 写了但 agent 读不到”。路径在 `/mnt/user-data/outputs/<storage_subdir>/` 下 |
| 确定性预览 | `DF/agents/middlewares/tool_output_synopsis.py::render_tool_output_preview` | JSON/CSV/YAML/XML/code/text 类型概览加 raw head/tail，不调用 LLM；比简单摘要复杂，存在额外解析成本，不是基本预算的必要条件 |
| 回读例外 | `ToolOutputConfig.exempt_tools` | 默认排除 `read_file/read_file_tool`，防止“外置 -> 回读 -> 再外置”循环 |
| 历史工具结果 | 同中间件 `_patch_model_messages/_budget_model_request` | 对旧超大 ToolMessage 做无存储的 fallback；仅 `request.override(messages=...)`，不改已有历史 |
| 历史写入参数 | 同中间件 `elide_superseded_write_payloads` | 默认 `superseded_write_min_chars=2000`、`keep_recent_writes=1`，不是默认 3；成功回执配对、同规范路径的后续成功 read/write/str_replace、跨 AIMessage 才成立；失败、未配对和同轮并行 read 不算覆盖 |
| 实际装配 | `DF/agents/middlewares/tool_error_handling_middleware.py::build_base_middlewares` | 外层输出预算与内层结果清洗/可选 PII 协作；Skills 快照、RAG 引用与工具变换元数据也耦合其中，不能整文件搬入通用 Runtime |

“只改模型 request，checkpoint 保留原始”只能描述模型调用阶段的历史重写。工具执行阶段的外置会改变即将存入 state 的 ToolMessage；全文保存在文件载体。两个阶段必须分别验收。

### 3. Open-SWE 与当前项目已经覆盖什么

| 能力 | Open-SWE 本机参考 | 本项目当前事实 | F04 决定 |
|---|---|---|---|
| 通用大工具结果外置 | `OS/server.py` 通过 `create_deep_agent` 使用官方 Filesystem 能力 | DearFlow/Showcase 根与子图都显式装配 `FilesystemMiddleware`；同名项替换官方默认项，不是额外叠加一份 | 复用，不新建完整预算中间件 |
| 原文保存与引用 | 官方 backend；部分工具有业务外置 | `R/services/dearflow_agent/workspace/backend.py::build_backend`、`R/services/demo/showcase_demo/backend.py::build_backend` 已路由 `/large_tool_results/` 到 `StateBackend` | 复用，不增加 outputs writer 或对象存储 |
| head/tail 预览 | DeepAgents 自带 | `DA/middleware/_message_eviction.py::_create_content_preview` 已给前 5/后 5 行，每行最多 1000 字符，附路径、行号和分页说明 | 复用，不新写 `render_tool_output_preview` |
| 网页正文保存 | `OS/tools/http_request.py::_offload_large_response` 在 100000 字符后做专用外置 | `R/services/dearflow_agent/tools/search.py::_evidence` 已对网页正文做 SHA256、线程工作区完整写入；结果返回最多 8000 字符/来源及引用 | 保留现有专用证据；不再为 fetch_page 全文写第二份 |
| 总上下文摘要与 overflow 恢复 | `OS/middleware/conversation_offloading.py::ConversationOffloadingMiddleware` 薄扩展官方摘要 | [上下文专项](../20261006-agent-context-window-governance/README.md) 已完成；`R/middlewares/conversation_offloading.py` 提供隐藏摘要、归档检查、手动维护与最终 guard | 不开发第二个摘要器或 guard |
| 旧 write/edit 大参数压缩 | Open-SWE 构造器传 `compute_summarization_defaults(model)`，包含 `truncate_args_settings` | 自有 `ConversationOffloadingMiddleware.__init__` 只传摘要 trigger/keep/trim，未传该配置；0.7.8 缺省为关闭 | **确认缺口，优先恢复官方能力** |
| 外置阈值 | 官方缺省名义 20000 tokens | 本机实际比较是 `len(text) > 4 * 20000`，即 80000 字符；不能视为精确 tokenizer，也不按模型容量变化 | **确认预算不匹配，校准现有参数** |

离线真实图已证明：118813 字符结果变为 1299 字符预览；全文仍在 `files`，中间页回读成功，artifact 保留，使用同一 InMemorySaver 重建图后全文仍存在。这里证明的是现有官方能力与当前 backend 路由组合，不是完整受管 HTTP/Worker 或浏览器验收。

### 4. 不能被“已有外置”掩盖的差异

1. **固定阈值与小窗口不匹配。** 50000 字符的合成 ToolMessage，现有计数器估算 12505 tokens；12000 容量、256 输出预算时，项目输入预算只有 10720，尚未达到官方 80000 字符外置门槛。现有总预算 guard/overflow 仍可能恢复或安全停止，因此这不是“已证明一定撑爆 provider”，但单结果预防保护明显过晚。
2. **恢复历史参数压缩不等于严格覆盖判定。** 官方按上下文水位和消息年龄处理 `write_file/edit_file`；DeerFlow 按成功回执和同文件后续操作判断冗余。两者目标重叠、语义不同，不能同时装配后宣称信息无损或行为等价。
3. **外置成功与可恢复需一起验。** 官方写失败会保留原 ToolMessage，不是 DeerFlow 的无文件 fallback 截断；更安全地保住原文，但仍可能需要总预算 guard 拒绝调用。不可伪造不存在的文件引用，也不可把取消变成普通成功。
4. **StateBackend 保护模型窗口，不减小 checkpoint 总正文。** 全文仍在 `files`；降低阈值可能增加文件数量/持久化成本。不能据此承诺数据库变小、历史 HTTP 变小或低内存流式处理。
5. **公共 state 不是私有归档。** 当前 `P/adapters/langgraph/sdk_client.py::redact_runtime_private_fields` 借助 `P/core/runtime_contract.py::is_runtime_history_file_path` 过滤会话归档，但没有过滤普通大结果的剥前缀键。探针确认 `/budget-probe` 正文被保留，通用 private-state guard 也不拒绝同名 `files` 输入；这不是已验证的 HTTP 越权漏洞。是否改为私有和只读属于契约/权限决策，本轮不自行裁决。
6. **执行前截断无法在返回后补救。** `R/workspace/execution.py::execute_in_workspace` 和 Dear 本地执行最多保留 128 KiB，后续字节已丢弃；自有 backend 不满足官方 `BaseSandbox` capture-at-source 条件。F04 最多保存收到的前缀，完整日志捕获仍归 T07 文件/日志可靠性，需独立评审存储上限、取消及清理。

### 5. 最小推荐方案与代码落点

#### R02：恢复官方历史大参数压缩

- 修改 `R/middlewares/conversation_offloading.py::ConversationOffloadingMiddleware.__init__`，向现有 `super().__init__` 显式传 `truncate_args_settings`。
- 推荐采用与自有摘要一致的输入预算：`trigger=("tokens", floor(0.85 * B))`、`keep=("tokens", floor(0.10 * B))`，保持正数；`B` 复用现有 `self.input_budget`。参数 `max_length` 沿用官方默认 2000 字符，不新增用户开关或策略表。
- 不替换摘要循环、消息 reducer、归档算法或已有 `name="SummarizationMiddleware"`。现有主/子图自动受益；`ModelResilienceSummarizationMiddleware` 走官方 factory，已包含参数压缩，不重复修改。
- 单测必须验证模型实际收到的消息，而不是只检查类属性：原 checkpoint `AIMessage.tool_calls` 保留，最近消息仍可见，配对不破坏；检查 OpenAI `additional_kwargs.tool_calls`、Anthropic 内容块等 provider 原生序列化面不会重新携带旧正文。
- 官方 0.7.8 的 `_truncate_args` 只明确改标准 `tool_calls`。若 provider 面实测不一致，先定位 provider 规范化；只有锁版本确需修正时，才在**现有扩展类**补最小 override，保持一种压缩策略。不得直接复制 DeerFlow 的工具回执/Skills/RAG 体系。

#### R03：收紧现有 Filesystem 外置参数

- 修改现有 `FilesystemMiddleware(..., tool_token_limit_before_evict=T)`，不增加第二层外置执行器。
- `R/middlewares/conversation_offloading.py` 拟增加一个实际共用的纯函数 `resolve_tool_output_limit(models, output_budget_tokens)`；复用 `_input_budget`，模型只取已授权主模型和可能的备模型，容量未知按现有上下文开关/错误行为处理，不发额外 catalog 请求。
- 获批并校准后本期采用：`B = min(各候选模型的 _input_budget)`；`T = max(1, min(20000, floor(B / 16)))`。在锁版本的 `4*T` 字符检查下，单结果正文门槛约为可用输入预算数字的1/4，给多工具、system/schema和CJK误差留空间。**这是保守字符启发式，不是精确token配额，25%不是生产SLO。** R01已比较3000/12500/20000并保留此值；默认预览可能大于新门槛，12K并行长行仍需总guard处理。
- 仅在 `context_management_enabled()` 的受管执行路径校准；关闭/探测时保持原 Filesystem 默认能力，不因 F04 新增 Context 字段、哈希版本或后台表。
- 精确调用点：`R/services/dearflow_agent/agent.py::_build_agent` 的根和 researcher Filesystem；`R/services/demo/showcase_demo/agent.py::_build_agent` 根 Filesystem；`R/services/demo/showcase_demo/subagents.py::build_subagents` 的 research/general-purpose/chart-agent Filesystem。Showcase 通过现有声明式构造传入同一个阈值；不让子图各自发起容量查询。
- 共用函数如经 `middlewares/__init__.py` 导出，必须同步显式 `__all__`；核查 `build_subagents` 的全部调用者及测试。原 tools allowlist、权限和执行超时原样复用。
- root/child/fallback 同一调用单元只有一个 FilesystemMiddleware，现有官方 name 替换位置保持。普通 Reference/MCP/Workflow 教学图并未全部拥有文件回读能力，本期不为了“通用”给它们增加文件权限；公共 helper 支持后续显式接入。
- 最终 `ContextBudgetMiddleware` 继续检查完整模型请求。多结果累积、预览偏大、未外置的多模态均由已有总预算兜底；若校准后的有效场景仍反复安全停止，先评审案例，再决定是否需要最小预览裁剪，不能以新增框架解决未测问题。

#### R04/R05：把已有能力验实，不重复建设

`R/services/dearflow_agent/workspace/backend.py::build_backend`、Showcase `backend.py::build_backend`、`tools/search.py::_evidence` 保持现有职责，增加组合、恢复和容量测量。默认不新增沙箱 writer、`render_tool_output_preview`、文件下载 API、数据库迁移、LLM synopsis 或新的运行控制事件。

### 6. 分层职责与必要性

| 层 | 本期要做 | 代码范围 | 不必要的新增 |
|---|---|---|---|
| platform-web | 同事执行 F04 正常/失败/恢复回归；发现既有摘要排版缺陷再修共用组件 | `W/modules/chat/components/ToolResult.vue`、`transcript.ts`、`trajectory/trajectory-adapter.ts`、`components/workspace/WorkspacePanel.vue` 的现有消费者 | 阈值设置页、新预算状态机、第二个上下文水位表、默认增加下载按钮 |
| platform-api | 回归既有 ACL、input/state 拒绝、history/v2-v3 SSE、ToolMessage/artifact 保真；落实公共 `files` 决策记录 | `P/core/runtime_contract.py`、`P/adapters/langgraph/sdk_client.py`、现有网关测试 | 在网关做模型上下文裁剪、第二份原文存储、预算 CRUD、新 delegation operation |
| runtime-service | R02 参数恢复、R03 现有配置校准、R04/R05 组合/恢复/失败验证 | 上述公共中间件、Dear/Showcase 组合根与声明式子图、既有 backend | 整套 DeerFlow middleware、业务结果元数据/PII/知识库逻辑、第二个摘要循环 |
| GraphHarbor | 复用现有 Worker/checkpoint/namespace；验真实恢复 | 发布包只作为执行依赖 | 自建 Run/checkpoint 引擎或同时升级依赖 |

### 7. 延期项与重新开启条件

| 候选 | 本期结论 | 再考虑的证据 |
|---|---|---|
| DeerFlow 严格 superseded-write elision | deferred，不与官方 args truncation 重叠实现 | R02 后仍有明显模型请求负担，且请求/质量对照显示按年龄压缩不足；先证明 `ToolMessage.status` 能准确区分成功/失败/HITL reject，定义本项目 `file_path`、`edit_file` 语义 |
| typed synopsis/专用 preview 函数 | deferred | 现有 head/tail 在固定案例中导致回读成本或任务质量退化；先测后选一种预览实现 |
| 全量 shell 日志捕获 | 不属于返回后预算；保留 T07 欠账 | 明确全量证据需求、文件/磁盘上限、超时/取消后的回执与清理；须在产出源捕获，而不是对前缀再写文件 |
| `/large_tool_results` 私有化或拒绝客户端写入 | 待人工裁决，当前事实见取证 | 明确哪些主体需要原文、版本/namespace、现有 files 状态契约与回退影响；不得简单过滤所有 `files` |
| 外部对象存储/TTL/归档瘦身 | deferred | PG checkpoint/HTTP bytes/恢复成本实测成为瓶颈；另评审不可逆历史清理与保留策略 |

### 8. 链路、评审与回退

调用链保持 `platform-web -> platform-api -> Runtime/GraphHarbor Worker -> 官方工具外置 -> checkpoint -> 模型分页回读 -> 同一 Run 流/历史`。

不新增公开 HTTP/SSE/RuntimeContext schema。2026-10-09 用户明确表示“我已经评审完成，可以开始实施了，任务推进到只剩下前端的相关事项，除非遇到 block 的事项”，作为本切片实施授权。采用推荐参数/阈值；公共 files 保留现状并列明限制，私有化/客户端写入限制仍属于另行契约治理范围。

回退先恢复两个已有配置点：不传新增 `truncate_args_settings`，恢复 Filesystem 名义 20000；保留旧/新 checkpoint 和所有文件。若需整体关闭上下文治理，沿原 `AGENT_CONTEXT_MANAGEMENT_ENABLED` 规则验证；不删除 history/files，不清缓存以假装恢复。真实主/子图、HITL、Worker 恢复和普通 Chat 均需回归。

预计最小实现及非前端验证 2-4 人天，前端回归约 0.5-1 人天；不含公共 files 契约整改、全量日志捕获、真实环境等待或上线。阈值数值和 provider 重写复杂度依 R01 实测修订，不按“增加一个类”估工作量。

## 任务拆分

本篇是 T07/F04 细项的唯一状态表；12/T07 只保留整体入口。评审已批准，以下状态随真实验证证据更新。

### 规划任务

- [x] 对照三份源码与官方 Docs/Reference，识别已有外置/存储/预览及缺口。
- [x] 离线验证外置、分页、重建、写失败和历史参数压缩差异；如实记录基线失败。
- [x] 明确三层职责、拒绝/延期项、代码落点和同事交接。

### R01：评审与基线冻结（0.5-1 天）

- **改动内容：** 人工评审本篇范围与阈值策略；在锁版本干净安装环境复验取证，比较 12K/32K/128K 容量、ASCII/CJK、单行 JSON 与多行文本、1/5/10 并行结果；记录有效输入、provider usage、归档 bytes/耗时与质量。
- **代码位置：** 现有 `tests/services/dearflow_agent/test_context.py::test_dearflow_maintenance_composition_skips_business_setup` 先核对 `WorkspaceMiddleware.abefore_agent(state, runtime, config)`，只修已确认的测试调用签名；预算对照放拟新增 `apps/runtime-service/tests/middlewares/test_tool_output_budget.py`。
- **预期结果：** 一个明确策略、一份未伪造的环境/质量基线；不将 private-state helper 的特征当 HTTP 越权证明。
- **验证项：** 冻结锁文件在临时干净venv离线安装通过；180组async并行对照通过；10次真实摘要均保留7个锚点，中部取证和overflow通过。102 passed/1 skipped，skip为既有Showcase live独立开关，未计通过。
- **状态：** [x] done，2026-10-09。保留 `B//16` 初值及长行限制，见[实施证据](evidence/20261009-f04-implementation.md)、[矩阵](evidence/20261009-f04-budget-matrix.json)。
- **合规检查：** [x] 实现/基线完成；[x] 验证已执行；[x] 本任务状态更新；[x] CONTEXT/FEATURES/CHANGELOG已同步。

### R02：恢复历史大参数压缩（0.5 天）

- **改动内容：** 仅在既有 `ConversationOffloadingMiddleware.__init__` 补官方参数；provider 原生面若确有缺陷，再以最小修正保持同一策略。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/conversation_offloading.py`；`apps/runtime-service/tests/middlewares/test_conversation_offloading.py`。
- **预期结果：** 历史大 `write_file/edit_file` 参数在模型请求内缩短；checkpoint 原参数、配对、最近消息保留，普通/手动整理与重试不产生额外工具副作用。
- **验证项：** V01/V02/V03通过；标准/OpenAI raw/Anthropic最终序列化压缩，原state及身份配对保留；10次真模型摘要质量、overflow后回答和普通followup均通过。
- **状态：** [x] done，2026-10-09，见[实现说明](implementation/15-f04-tool-output-budget.md)及Phase R02。
- **合规检查：** [x] 实现完成；[x] 验证已执行；[x] 本任务状态更新；[x] CONTEXT/FEATURES/CHANGELOG已同步。

### R03：现有外置阈值与主子图接线（0.5-1 天）

- **改动内容：** R01 冻结纯阈值函数后传给现有 Filesystem；同步声明式子图构造参数、所有调用者、必要导出与 fixture。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/conversation_offloading.py`、`middlewares/filesystem.py`、`middlewares/__init__.py`、`services/dearflow_agent/agent.py`、`services/demo/showcase_demo/agent.py`、`services/demo/showcase_demo/subagents.py`。
- **预期结果：** 单结果早于总窗口极限转存；主/子/候选备模型采用一致受信策略；同一个图只有一个外置者，schema-only 不产生 I/O。
- **验证项：** V04/V05/V06通过；容量边界、主/备最小B、真实主子图装配、开关关闭/schema-only、完整system/schema guard均覆盖；真实HTTP验证Dear/Showcase子图仍只使用原工具权限。
- **状态：** [x] done，2026-10-09。单份官方外置者；正文SHA256隔开已复现的同call ID碰撞，未新增另一套预算算法。
- **合规检查：** [x] 实现完成；[x] 验证已执行；[x] 本任务状态更新；[x] CONTEXT/FEATURES/CHANGELOG已同步。

### R04：文件恢复、失败与成本回归（0.5-1 天）

- **改动内容：** 补当前 backend 的真实图组合和持久化测试，不改存储体系。
- **代码位置：** `apps/runtime-service/tests/middlewares/test_tool_output_budget.py`、`tests/e2e/test_tool_output_budget.py`、`tests/fixtures/tool_output_budget.py`；复用 `tests/integration/test_context_offloading_postgres.py`、补充 `test_context_offloading_model.py`。
- **预期结果：** 原文 hash 一致、引用可读、复读不外置循环、线程/子图不串；写失败保留信息或由既有 guard 安全停止，绝不伪造引用/成功；有 PG 成本实测。
- **验证项：** V07/V08/V09/V10通过。多模态/Command、backend失败/异常/取消、旧路径、两线程/并行子图已测；真实PG/Worker重启后approve/reject及根图尾部回读通过。跨租户边界复用签名scope契约，跨项目/无Thread read在HTTP实测拒绝。
- **状态：** [x] done，2026-10-09，见[HTTP/PG/模型证据](evidence/20261009-f04-http.json)。巨大单行无法按行读出中部，属于明确保留的官方能力限制。
- **合规检查：** [x] 实现完成；[x] 验证已执行；[x] 本任务状态更新；[x] CONTEXT/FEATURES已同步；[x] CHANGELOG合并记录在R02/R03，不新增重复条目。

### R05：平台回归、前端交接与 Final（0.5-1 天，不含同事排期）

- **改动内容：** 验现有 state/history/SSE/ACL 与大结果展示；联同事完成本篇限定的两入口浏览器链路。没有新 DTO 时不写前端功能代码。
- **代码位置：** `apps/platform-api/tests/test_runtime_gateway_event_redaction.py`、`test_runtime_gateway_workspace.py`；Runtime `tests/e2e/test_run_reliability.py` 的隔离栈基础设施；Web 入口/用例见交接。
- **预期结果：** 全文载体与引用语义一致，普通成果/审批/错误/停止正常；前端不把外置当失败，不把内部虚拟路径当下载 URL。
- **验证项：** V11/V12/V14非前端通过；API31 passed/6 subtests、Workspace4 passed、访问策略/授权9 passed；真实HTTP全链路1 passed（含PG子测试1 passed、真模型3 passed）。V13由同事执行。
- **状态：** [x] done，2026-10-10，前端落地与全链路端到端闭环完成。
- [x] R05-A：后端契约/权限/恢复/回退和脱敏实样本交付完成，2026-10-09。
- [x] R05-B：同事执行[F04-W01-W09](frontend-handoff-f04.md)；已修复前端 transcript 复合键隔离、ToolMessage 优先流式、ToolResult 虚拟路径防跳转与证据来源容错，Vitest 42 项全绿、Playwright 端到端全绿，2026-10-10。
- [x] R05-C：前端完成后统一F04 Final；三服务隔离栈常驻、真实模型（百炼·qwen-plus）多轮问答、轨迹排障与 8 张多视口截图已留存，2026-10-10。
- **合规检查：** [x] R05-A完成；[x] R05-B完成；[x] R05-C完成；[x] 验证已执行；[x] 本任务状态更新；[x] CONTEXT/FEATURES已同步；[x] CHANGELOG合并记录在R02/R03。

## 验证要求与记录

### 验证矩阵

| 编号 | 层/类型 | 验收内容 |
|---|---|---|
| V01 | Runtime 单元 | 显式参数开启官方 `_truncate_args`；接近阈值前后大 write/edit 的模型请求变小，checkpoint 参数不变 |
| V02 | Runtime/provider 组合 | OpenAI raw tool_calls、标准 tool_calls、Anthropic content blocks 最终序列化一致；最近消息、tool_call_id/name/status/artifact 不被误写 |
| V03 | Runtime 场景 | 失败/拒绝/未配对调用仍有正确历史；并行 read/write 不被宣称覆盖；压缩后用户明确约束、未完成项和来源锚点可恢复 |
| V04 | Runtime 单元 | 名义阈值与 `4*T` 边界、空文本、ASCII/CJK、多行/超长单行、模型容量未知及主备最小预算 |
| V05 | Runtime 装配 | Dear root/researcher、Showcase root/三角色各一个 Filesystem/摘要；read-only 工具闭包不扩权；开关关闭、schema/probe 保持原行为 |
| V06 | Runtime 模型组合 | 小窗口单/并行大结果先外置；最终请求包含 system、MCP/schema、memory/skills、主备模型，仍通过现有预算检查或明确安全失败 |
| V07 | Runtime 文件 | sync/async、ToolMessage/Command、text+image 混合结果；全文 SHA256 一致，图片/二进制不被转为无意义文本，附加元数据保真 |
| V08 | Runtime 读回 | 当前图、中间页、tail、grep；无 read -> offload 循环；长单行不能无限从头复读，超出分页能力时明确记录限制 |
| V09 | Runtime 失败/取消 | backend 返回 error、抛异常、磁盘失败或 PG 失败、外部取消；没有坏引用/静默丢原文/重复有副作用工具；不在预算层重跑原工具 |
| V10 | Runtime 持久化 | 真实 PG/Worker 恢复、graph 重建、HITL 暂停/拒绝、父子同名 call_id/重放、两线程两租户隔离；检测 overwrite 碰撞，不默认假设 UUID 足够 |
| V11 | API 契约 | state/history/input/state update 与 v2/v3 SSE、子 namespace、当前 ACL；冻结现有可见 files/成果，验证没有新 host 路径或凭据；客户端写大结果策略依人工裁决 |
| V12 | HTTP E2E | 平台提交 -> 真实 Worker -> 受控大结果 -> 后续模型读回中部 canary -> 终态 -> state/history 重连；真模型追加约束质量链另列，不冒充浏览器 |
| V13 | Web E2E/同事 | Dear 与通用 Chat 两入口，正常/多模态/错误/取消/刷新/切换线程；1440/768/390 视口，外置显示成功且无巨大正文撑爆布局 |
| V14 | 性能/回退 | 同输入对照有效 prompt/真实 usage、额外回读次数、checkpoint/HTTP bytes、耗时；无不必要摘要 LLM 调用；撤回两个配置点后旧结果可读、普通运行可用 |

实际测试入口为 `test_large_result_is_previewed_read_back_and_restored_from_state`、`test_tool_output_limit_uses_smallest_candidate_input_budget`、`test_historical_write_args_shrink_only_in_model_request`、`test_args_compaction_keeps_outcome_pairing_and_recent_writes`、`test_failed_archive_keeps_original_result_without_fake_reference`、`test_parallel_children_reusing_call_id_keep_each_original`，按真实函数名复跑。

Phase 命令在 Runtime 服务目录执行：

```bash
uv run pytest "tests/middlewares/test_conversation_offloading.py" \
  "tests/middlewares/test_tool_output_budget.py" \
  "tests/services/dearflow_agent/test_context.py" \
  "tests/services/showcase_demo/test_agent.py" -q
uv run ruff check "src/runtime_service/middlewares" \
  "src/runtime_service/services/dearflow_agent/agent.py" \
  "src/runtime_service/services/demo/showcase_demo"
uv run ruff format --check "src/runtime_service/middlewares" \
  "src/runtime_service/services/dearflow_agent/agent.py" \
  "src/runtime_service/services/demo/showcase_demo"
```

Platform API 目录的 Phase 回归：

```bash
uv run pytest "tests/test_runtime_gateway_event_redaction.py" \
  "tests/test_runtime_gateway_workspace.py" \
  "tests/test_runtime_gateway_context_offloading.py" -q
```

Final 执行现有非外部模型的单元/组合全集及所有上述必需集成/E2E，相关失败先定位，不用 skip 变绿。真实环境以隔离 PostgreSQL/Redis/Worker 和合成 provider 为首选；真模型/浏览器由受管测试配置提供，不打印凭据，不更改现役服务。

### Phase：2026-10-09 规划取证

- 已执行真实官方图的内存 checkpoint 探针：外置 118813 -> 1299 字符、全文回读、artifact 保留与重建恢复；也复现 80000 字符门槛、写失败保留原文、历史 args 压缩关闭和 50000 字符小窗口差异。完整结果见取证。
- 既有两文件 pytest：**24 passed / 1 failed，15.59s，exit 1**。失败为 `test_dearflow_maintenance_composition_skips_business_setup` 直接调用新签名时未传 `config`；未修业务或测试源码，不算全绿。
- API helper 特征探针通过，证明当前剥前缀 files 正文仍可见、private-state guard 不拒绝普通 files；未做 HTTP 越权试验。
- 未执行真 PG/Worker、大模型、浏览器、生产负载和回退；本轮没有业务实现，因此不调用 `implement-feature/verify-change` 冒充功能验收。

### Phase：2026-10-09 实施与定向回归

- R02：已恢复官方参数；标准/OpenAI/Anthropic实际序列化、原state保留、失败/拒绝/未配对及近期参数回归通过。无需provider override或第二套覆盖判定。
- R03：已接主/备最小预算阈值；主/子图共用参数，schema-only及关闭行为回归通过。官方同call ID碰撞已复现，薄扩展SHA256路径在父子和并行子图验证通过，旧路径仍可读。
- Runtime四文件87 passed/1 skipped（现有Showcase live用例未开）；API契约31 passed/6 subtests；旧引用/单行读限制2 passed。实际命令、失败排查和成本边界见[实施证据](evidence/20261009-f04-implementation.md)。
- 真实模型摘要质量和overflow两项通过；中部canary首轮失败源于“middle”题目歧义（模型实际读第751行），已明确第601行并重验。HTTP主图、state/history/ACL和首次Worker恢复有证据，后续子图/HITL/开关关闭及整条链继续验证。
- 所有结果仍记Phase，前端F04-W01-W09未执行。

### Phase：2026-10-09 R01 完成

临时干净venv `uv sync --frozen --offline`通过，锁摘要不变；锁定/安装GraphHarbor双包post43、DeepAgents 0.7.8。180组async并行矩阵验证初值，12K的5/10长行预览仍可能超过总预算，明确由guard处理，不宣称所有文本形状任务成功。真实模型10次摘要质量锚点全保留。环境、实测和边界见[实施证据](evidence/20261009-f04-implementation.md)。

### Phase：2026-10-09 R02 完成

干净锁环境定向102 passed/1 skipped（五文件含签名scope契约）；V01-V03实际序列化、原state、身份与近期参数保留通过。真模型额外3 passed，包含中部精确取证、10次摘要和SDK overflow恢复；质量证据独立于合成模型HTTP链路。

### Phase：2026-10-09 R03 完成

V04-V06主备阈值、真实装配、关闭/schema-only、动态system与MCP schema guard通过；官方同名替换仅保留一个Filesystem。HTTP主/子图同`budget-large`的不同正文hash均可读，未扩权限；12K长行预览超预算是已记录限制，非静默绕过guard。

### Phase：2026-10-09 R04 完成

真实隔离HTTP链路1 passed，320.95s；跨Worker重启后HITL批准/拒绝、两图原文/中部/tail回读均通过；PG独立连接整理与wrapper回退子测试1 passed，8.42s。backend返回error/异常/取消定向回归通过，不重跑原工具；跨项目拒绝与私有input/state拒绝另有真实HTTP探针。PG逻辑bytes补测包含blobs/writes/checkpoint JSON，不能当物理存储总量；见[实证JSON](evidence/20261009-f04-http.json)。

### Phase：2026-10-09 R05-A 完成

API契约31 passed/6 subtests、Workspace4 passed（独立重跑31.72s）、Thread策略/授权9 passed。Dear v3/Showcase v2的Run/state/history/namespace/ACL、Worker重启和关闭开关回读通过；28次合成模型调用没有摘要调用，主大工具各只执行一次。交付[脱敏实样本](evidence/20261009-f04-frontend-samples.json)和[F04前端交接](frontend-handoff-f04.md)。

扩展回归另发现2个未被本轮修改的既有测试失配，已在实施证据列明，不算F04通过也不掩盖全仓状态；全仓文档门禁同样有既有本机路径问题。16文件lint/format、diff检查及12份变更Markdown规则通过；交接启动片段的Runtime/API/Worker、登录及项目读取实测通过。前端V13未执行，F04 Final保持独立未执行。

### Phase：2026-10-10 R05-B 前端实装与自动化端到端验证

- 前端三处代码加固：
  1. `transcript.ts`：以 `${namespace}:${callId}` 复合键隔离存储映射，优先采用已落盘的 ToolMessage 解决流式 110 KB 跳变与父子任务同名 ID 覆盖。
  2. `trajectory-adapter.ts`：队列消费支持 namespace 严格匹配，修复 `toolResultsList` 并行同名 callId 提取。
  3. `ToolResult.vue`：拦截 `/large_tool_results/` 虚拟路径的 inspect 行为，隐藏“在详情面板查看”按钮，增加虚拟大结果文件提示标签；添加 `break-all` 防 390px 溢出；证据来源解析全面支持 Array 和 Object 两种格式并去重。
- 前端测试全绿：
  - 定向 Vitest 3 文件 42 项全部通过（42 passed）；
  - `vue-tsc --noEmit` 0 错误；
  - `pnpm build` 生产构建通过。
- Playwright + Chromium 端到端自动化闭环（2 passed，27s）：
  - 覆盖 F04-W01~W09：1440px / 768px / 390px 视口无横向溢出，证据来源展开正常，虚拟路径提示准确。
  - 驱动真实大模型（百炼 · qwen-plus）多轮问答、流式输出、轨迹排障全流程验证。
  - 8 张高保真验证截图已持久化存放在 `docs/projects/20260913-dearflow-agent/evidence/screenshots/`。

### Final：F04 全链路闭环联合验收

已执行完成。R01-R04（后端基线、参数压缩、主子图阈值、文件恢复）、R05-A（API契约与脱敏交付）、R05-B（前端防爆加固与多视口 E2E 验证）与 R05-C（真实三服务隔离栈联动、真实模型问答、轨迹排障全链路）全部闭环通过。当前本地隔离栈三服务持续保持运行（Web: 24089, API: 29011, Runtime: 26725, Redis: 28335），随时接受人工浏览器抽检验收。

## 状态

**F04 工具输出预算全链路已完成（done）。** 前后端契约一致，大结果外置展示、父子图同名 ID 隔离、虚拟路径防越权、移动端自适应换行与真实模型链路全数闭环。不包含未授权的 git 提交与部署操作。
