# F17 - 规划核验与未来接入门禁

## 本轮验证范围

仅核实源码、依赖/配置、测试定义、历史决策和规划文档。没有运行 Agent、知识服务、单元/集成/E2E，没有修改数据库或启动本地服务。当前 Worktree 未发现 Runtime `.venv` 或本地栈登记；文档检查仅使用系统 Python 标准库，不借用其他 Worktree 的依赖。

以下源码事实不等于功能测试结果，未来门禁不能勾为通过。

## 2026-10-10 源码核验记录

| 核验项 | 实际结果 |
| --- | --- |
| DeerFlow 知识目录 | `knowledge.py` 仅两个 GET；读取 RAGFlow datasets/documents，无知识文档写入 endpoint |
| DeerFlow 工具/范围/引用 | `knowledge_search_tool` 经 HTTP 读取外部索引；知识范围含 all/selected/disabled；文本与 bounded artifact 对应 |
| DeerFlow README | 明确要求在 RAGFlow 创建/上传/解析/删除文档；没有 DeerFlow 知识管理页 |
| DeerFlow 备选 | 配置包含 LightRAG 数据检索备选；没有依据认定自行实现 PgVector pipeline |
| Open SWE 搜索 | 对 `agent/`、pyproject 和 README 的知识/RAG/向量关键词搜索未发现 F17 同类实现；`server.py` 存在 MCP 与 Notion 接入 |
| 当前 Runtime 搜索 | 未发现 `knowledge_search/search_knowledge/ragflow/lightrag` 生产工具；个人记忆为词法召回；附件解析为线程资源 |
| 当前 MCP 底座 | `load_mcp_tools()`、声明校验和资源解析已存在；仅能据此认定有底座，不认定任何知识服务已连接 |
| 当前测试定义 | `test_mcp_tools.py` 含真实本地 fake MCP 的装配、只读拒绝、错 Thread、断连等断言；本轮未执行，且不证明知识数据质量 |
| 绑定签发 | 测试构造绑定；未找到 Platform 调用 `thread_resource_metadata()` 的项目 MCP 签发路径，未来必须核验公开 metadata 入口 |
| 旧产品决定 | API 重构明确退役知识库与测试用例；新评估不恢复旧实现 |
| 用户补充与范围确认 | 当前无企业知识服务；大改动不做，后续倾向 MCP；2026-10-10 用户明确要求合入“不开发”结论及前端交接，本期开发范围已关闭 |

### 关键证据摘要

外部仓库路径按 `plan.md` 的 D/S/H 定义。HEAD 不涵盖本地修改，以下 SHA256 用于再次确认关键取样文件：

| 文件 | SHA256 |
| --- | --- |
| `D/backend/app/gateway/routers/knowledge.py` | `55c643f255b6acc30665c8e0bbde05fc105f0dda5984cec73378c01b4deb16f1` |
| `H/community/ragflow/tools.py` | `385bdf44305c9be7c312cf80fe35d02d63579a3df54782bd22a1d5acab1f9bfc` |
| `H/knowledge_scope.py` | `771d3aaa719dfb1b909c175a2819e1159b740daf46ef4d0d9637ddc919f4c95d` |
| `S/agent/server.py` | `2e18fb2817e10bb722eb60cf6e43b193b4089bce5c8de0bc32f2439d368903cd` |
| 当前 `services/dearflow_agent/tools/mcp.py` | `c03b3de36bb82aef467e58a67a5aa8c86dc4f952626ce393eddcfa2d40dec5fa` |

官方 MCP 文档查询确认 ToolMessage artifact 可保存检索元信息、工具可使用受注入的 ToolRuntime 上下文。当前官方示例已出现不同 Adapter API，不能照抄到本项目锁版本；本轮没有增加 LangChain/DeepAgents 代码或升级依赖。

- [官方 tools / access context](https://docs.langchain.com/oss/python/langchain/tools#access-context)
- [官方 ToolMessage artifact](https://reference.langchain.com/python/langchain-core/langchain_core/messages/tool/ToolMessage)
- [官方 MCP structured content](https://docs.langchain.com/oss/python/langchain/mcp/tools#structured-content)

### 本轮文档检查

- [x] 本次文件语法、链接和文档规则定向核验。
- [x] `git diff --check`。
- [x] 全仓 `python3 scripts/check_docs.py` 与既有失败范围核对（全仓本身未通过）。
- [x] 确认变更仅为本专项文档、功能/上下文索引、原 F17 和旧 A31/T09 入口。

| 检查 | 真实结果 |
| --- | --- |
| 定向文档检查与 HEAD 基线对照 | 收口复核：10 个变更 Markdown、229 个本地链接、496 个表格行（含分隔行），无新增路径/链接/表格问题；保留的 5 个问题均在 HEAD 已存在 |
| 明确 app 路径检查 | 新专项列出的 22 个明确 app 路径均存在；计划测试文件只在正文标为未来可能新增，不当成现有文件 |
| `git diff --check` | 退出码 0 |
| 全仓 `python3 scripts/check_docs.py` | 退出码 1；38 处既有个人绝对路径，未增加新错误，未顺带清理其他专项 |
| 额外本地链接核验 | `docs/FEATURES.md` 的 4 个失效链接已在 HEAD 复现；原 F17 调研的 1 个个人路径也为既有问题，均未改动原有内容 |
| 变更范围 | 仅 10 个 Markdown 文件；业务源码、配置、数据库、依赖与前端无变更 |

上述定向检查不是完整 Markdown lint，也没有执行业务测试。未来 V01–V09 仍全部未验。

## 未来验证计划：有实际 MCP 后才执行

| ID | 层与场景 | 最低验收标准 |
| --- | --- | --- |
| V01 | Runtime 兼容与装配 | 实际 streamable HTTP 工具名/声明可加载；真实编译图只暴露获授权的查询工具；重名、写工具、missing tool 被拒绝；同一知识源没有第二原生工具 |
| V02 | 绑定签发和项目隔离 | 两租户/两项目植入不同 canary；公开创建/更新 metadata、模型参数和旧绑定不能换 resource 或 namespace；不只检查字段相等；越权请求不访问外部目标资料 |
| V03 | 当前权限与恢复 | 提交后撤权、项目/主体切换、服务账号 grant 撤销、Worker 重建、fork/resume 分别验证；历史绑定不能绕过当前权限；检查 Thread 分享是否扩大资料读者 |
| V04 | 结果与引用 | 成功片段含真实来源；刷新、历史与 stream 返回一致；页码不发明；若有 artifact，用当前发布 Adapter 验形状；非法/缺失来源不得标记已核实 |
| V05 | 输出限制与不可信正文 | provider 超大正文、恶意 Markdown/URL/提示词注入、缺字段；片段/来源/裁剪一致、输出有界；工具权限与 HITL 不被改变；全文、Key、内网地址不进入错误/日志 |
| V06 | 失败与取消 | no-hit 与 upstream timeout/error 不混同；错误复用现有安全处理；取消向上游传播或清楚标识无法确认；未知错误不被包装为成功检索 |
| V07 | 与现有能力组合 | tool deny、Plan Mode 默认不接 MCP、上下文摘要/大结果外置、Token/调用次数预算生效；根图支持不冒充子图支持；没有新增自动入库/记忆写入副作用 |
| V08 | 运维、关闭与回退 | 服务重启恢复、凭据替换、禁用工具/绑定后普通 Chat 不受影响；checkpoint 不被删除；记录真实延迟/并发/费用与输出上限，SLO 如需设定先由需求确认 |
| V09 | 浏览器完整链路 | platform-web → platform-api → Runtime Worker → 实际知识 MCP → 可读来源/片段 → 刷新回放；双项目 canary 不串；当前错误/来源/权限反馈真实 |

### 单元 / 组合测试落点

如发生代码变更，优先扩展现有测试；以下新增名称是计划名称，不表示文件已存在：

- Runtime：`apps/runtime-service/tests/runtime/test_resource_bindings.py`、`tests/services/dearflow_agent/test_mcp_tools.py`、`tests/runtime/test_tool_governance.py`；新增逻辑需覆盖可信 resource 选择、结果限制和真实 ToolMessage 序列化。
- Platform API：`apps/platform-api/tests/test_runtime_gateway_http_matrix.py` 及网关/鉴权测试；如新增签发规则，可新增 `test_runtime_gateway_mcp_binding.py`，覆盖客户端伪造与撤权。
- Platform Web：只有展示变化才扩展 `apps/platform-web/src/modules/chat/components/ToolResult.spec.ts`、`transcript.test.ts`；类型检查、lint 和 build 按现有脚本执行。

现有 fake MCP 测试可以证明工具协议/错误路径，不能替代实际知识服务的效果或项目隔离验证。

### 检索效果核验

服务就绪后先准备一组真实授权文档、可回答/无答案/跨项目/过期资料问题，人工标出预期来源。对比“当前附件/普通回答”和“知识 MCP”两条路径的来源命中、事实正确性、无依据回答、时延和费用。用真实变化决定是否接入；不预设必然更准确，也不凭 Embedding 相似度认定答案可信。

PDF 文本/OCR、Markdown、URL 的入库正确性首先由外部服务验收；本平台再验证检索结果的来源和作用域，不能把实际服务不支持的格式承诺给前端。

### 环境和命令约束

未来先读 `docs/standards/worktree-development.md`，通过 `scripts/local-stack.sh init/deps/doctor/start/status` 建立本 Worktree 资源。测试地址从登记读取；外部知识服务的测试 corpus/账号也要隔离。没有真实服务不运行“全链路通过”示例，具体命令与 fixture 在 M01 后冻结。

## Phase / Final 记录

- **本轮规划：** `done`，源码评估、范围取舍、前端交接与定向文档核验完成；全仓既有文档问题如上记录。
- **未来 Phase：** 未开始。
- **未来 Final：** 未执行。
- **F17 功能状态：** 用户确认本期不开发，功能 `deferred`，不是已实现，也不是等待用户立即补环境的 `blocked`。

本期没有标准草案毕业、生产验收或业务发布动作。后续如实施，再调用 implement-feature / verify-change 记录真实结果。
