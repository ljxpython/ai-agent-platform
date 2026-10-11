# 候选知识服务能力与源码对照

## 取样边界

本轮读取三个工作树，未启动它们。后文路径使用以下根标记，避免把开发者本机路径写进可移交文档：

| 标记 | 根目录含义 | HEAD / 取样情况 |
| --- | --- | --- |
| P | 当前 `ai-agent-platform` 仓库 | `116cc26f02911ea3d1318663ed5d740c6f6933c5`；开始时工作树干净 |
| D | 用户指定的 `research/deer-flow` 工作树 | `cc664451f03140b376611f329ae400c313530bdb`；有用户本地修改，只读取样，不等同公开发行版 |
| K | 用户指定的 `research/rag-anything-use` 工作树 | `c7eeb6d647b093b9b577e32a61988bd3e26c30dc`；开始时工作树干净、用户说明尚未部署 |

“已有”指源代码/锁文件存在；外部工程 README 中的历史实测是该工程的记录，**本轮没有复现**。下面把源码事实、缺口与待实测项分开。

## rag-anything-use 够不够

**够做首版小规模文本知识检索的基础，不够直接承担多项目平台的安全服务边界。** 不需要换引擎，也不需要先建平台自己的向量库；先把它已有的封装收成可受管的 MCP 服务。

| 能力 | 代码依据（K 相对路径） | 结论 |
| --- | --- | --- |
| 管理员入库 | `src/cli.py`；`src/knowledge/ingest_service.py:KnowledgeIngestService.ingest_document()` | 已有本地文件 → Docling 解析 → 内容归一化 → RAGAnything 入库 → manifest 状态；MCP 没有入库工具，符合首版管理/执行分离 |
| 知识引擎 | `src/knowledge/rag_engine.py:ProjectRAGEngine`；`src/demo_support.py:build_lightrag()` | 已包装 RAGAnything / LightRAG，无需移植其内部检索/切片算法；没有显式配置新的 SQL/向量服务 |
| 项目目录 | `src/knowledge/project_paths.py:build_knowledge_project_paths()` | 有独立 `manifest/parser/rag_workdir/debug` 目录；是存储组织，尚不是授权隔离 |
| 检索参数 | `src/knowledge/rag_engine.py:query()` / `debug_retrieve()` | `top_k` 与 `chunk_top_k` 确实传入；`hybrid` 等模式由 LightRAG 处理；默认不启用 rerank |
| 检索原始片段 | `debug_retrieve()` | 已有 `aquery_data()` 和 chunks，可作为检索工具的基础；当前 debug 响应含 working_dir/raw_data，不能直接公开 |
| 生成式查询 | `query()` | 先 `aquery_data()`，再 `rag.aquery()`；检索与生成分两次执行。适合 CLI 调试，不适合作为本平台默认工具契约 |
| 来源信息 | `src/knowledge/citations.py:build_query_result_artifacts()` | 返回 document_id/filename/chunk_id/snippet；当前以路径/文件名回映，snippet 截至 280 字符，真实页码未贯通 |
| 文档列表/状态 | `src/knowledge/admin_service.py:KnowledgeAdminService` | 有管理读接口；目前返回整个 record，含内部 source_uri、metadata 和 last_error，网络服务需安全投影 |
| MCP transport | `src/mcp_server.py:build_server_run_settings()` | 源码支持 `stdio/http/sse/streamable-http`。文档推荐 SSE，但接本平台可直接选 HTTP `/mcp`，无需改平台传输栈；仍要实测 |
| MCP 工具 | `src/mcp_server.py` | 已有三个查询/状态工具，但工具名没有 `mcp_` 前缀，没有显式 `readOnlyHint=true`，与本平台 loader 不匹配 |
| 多模态 | `config.py`；`src/demo_support.py:build_raganything()` | 有图片/表格/公式开关，默认关闭；历史文档也把稳态放在关闭增强上，不能宣称已具备稳定多模态知识检索 |
| 自动化测试 | `tests/test_knowledge_smoke.py` / `test_mcp_stdio.py` | 覆盖配置、CLI 参数、来源映射和 stdio 目录/状态。没有当前平台链路、跨项目攻击、并发索引或 HTTP 权限验证 |

### 接入前必须补的实际问题

| 编号 | 发现 | 影响 | 最小处理 |
| --- | --- | --- | --- |
| K01 | `FastMCP(...)` 未配置鉴权；MCP 三工具均接收任意 `project_id` | 知道 ID 即可请求其他项目资料；namespace 字符串不能当权限证明 | HTTP Bearer 凭据绑定一个 tenant/project/namespace；所有网络工具从认证上下文取范围 |
| K02 | 路径函数仅 strip/nonempty 后 `root / project_id` | 绝对路径、`..` 或符号链接可能脱离知识根目录 | 限定单段 ID，resolve 后核验根目录归属；CLI 同样校验，缺范围不回退公共库 |
| K03 | 当前查询工具名与只读注解不符合 P 的门禁 | `allowed_tools` 写旧名字会被目录拒绝；改成新名字而服务未改名仍找不到实际工具 | 收敛一个 `mcp_query_project_knowledge`；明确只读注解，实测 `list_tools` 而非放宽平台门禁 |
| K04 | `query()` 执行两次检索且额外生成答案 | 成本/延迟增加，来源可能不是答案那次实际使用的片段 | MCP 走单次 `aquery_data()`，统一由平台 Agent 回答；CLI 的生成式 query 可以保留 |
| K05 | `ProjectKnowledgeQueryRequest.document_ids` 定义了但没有执行过滤；mode 没有枚举，query 没有上界 | 容易把接口字段误认为文件限权已经实现；无界输入增加开销 | 首版不公开 document_ids/mode；固定 hybrid，限制 query/top_k，拒绝非空未实现过滤 |
| K06 | 来源按 basename 回映、同名文档有歧义；回传内部 `file_path` | 引用可能串文档或暴露宿主路径 | 新入库使用不透明 document_id 作为索引 locator，精确映射 ready 文档；不使用 basename 猜测 |
| K07 | 每次 `_build_services()` 新建 engine；同步 MCP query 内 `asyncio.run()` | `_rag_cache` 不跨请求复用；难以证明并发初始化、取消和跨 event loop 正确 | 查询改 async，服务 lifespan 持有 engine，按范围有界初始化，退出关闭存储；不做跨进程缓存 |
| K08 | `build_lightrag()` 和 `initialize_pipeline_status()` 没有显式项目 workspace | 独立工作目录尚不能证明 LightRAG 共享状态在同进程中隔离 | 按锁版本核实 namespace API，给每个范围明确 workspace，并以双项目并发 canary 验收 |
| K09 | manifest 直接 read-modify-write，没有原子发布或并发保护；每次 ingest 新 UUID | 并发写丢记录，读到半份 JSON，重复入库/部分失败可能留下不一致内容 | 首版离线单写者、查询范围冻结；manifest 临时文件原子替换，失败范围不发布；不建设在线任务系统 |
| K10 | `load_settings()` 无条件要求 TEST_DOCUMENT_PATH/TEST_IMAGE_PATH/VISION 配置；Embedding 只走 Ollama `/api/embed` | 即使文本查询也依赖示例配置；不能把 OpenAI-compatible URL 填成现有 Embedding 服务 | 核实并分开示例必填项和服务必填项；首版沿用现有 Ollama 协议，固定模型/维度，不附带实现新 provider |

K08 的运行时隔离风险未实际复现，必须作为实施前 gate 核实，不能把它写成已发生的数据串库。K01/K02/K04/K05 等是直接可读出的实现缺口。

### 可以明确后置的能力

- 线上知识 CRUD、上传解析队列、增量更新/删除、自动去重和多写者。
- 文档级 ACL、每消息选择知识库/文件、跨项目共享库。
- 页级精准定位、原文下载、点击回答引用打开专用弹窗。
- OCR/扫描件、图片/表格/公式的增强检索，以及批量多模态质量承诺。
- rerank、多向量库后端、自动同步网页/Notion、全局知识搜索。

后置不等于可以削减权限或失败校验。首版有新资料时在新的知识范围离线重建；过期/敏感资料不得继续留在被发布范围内等待“以后加删除”。

## 借鉴 DeerFlow 的哪些设计

| D 文件/符号 | 借鉴的原则 | 本平台的取舍 |
| --- | --- | --- |
| `backend/app/gateway/routers/knowledge.py:list_retrieval_catalog_datasets()` / `list_retrieval_catalog_documents()` | 平台消费外部检索资源，不负责自建索引；目录查询失败不扩大范围 | 首版固定项目范围，目录/选库 UI 不做，因此不用复制这些路由 |
| `backend/packages/harness/deerflow/community/ragflow/tools.py:knowledge_search()` / `knowledge_search_tool` | 外部检索返回片段，让主 Agent 回答；以明确资源范围执行 | 保留现有 MCP 传输，只接外部检索工具，不复制原生 RAGFlow HTTP Adapter |
| `backend/packages/harness/deerflow/community/ragflow/formatting.py:format_retrieval_sources()` | 模型文本与来源快照来自同一次检索；有输出上限；不伪造页码 | 返回现有 UI 可理解的 `sources`，保存检索时 preview/truncated；不复制它的专用引用协议 |
| `backend/packages/harness/deerflow/knowledge_scope.py`；`agents/middlewares/knowledge_scope_middleware.py` | 选择不等于授权；停用必须同时裁剪可见工具并拦截实际调用 | 固定服务端项目绑定＋现有 tool policy，不建消息级 all/selected/disabled 状态机 |
| `backend/packages/harness/deerflow/community/lightrag/client.py:query_data()` | 将 LightRAG 作为检索后端，读取结构化数据 | 候选工程已有同类入口，薄封装即可，无需移植 DeerFlow 框架 |

DeerFlow 的知识文档创建/上传/解析/删除由外部 RAGFlow 承担；线程附件解析不等于长期知识入库。这两条边界在本方案保留。

## 当前平台已有与缺少

| P 文件/符号 | 已有能力 | 本次缺口/处理 |
| --- | --- | --- |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/mcp.py:load_mcp_tools()` | 官方 Adapter、Streamable HTTP、allowlist、只读门禁、传输错误处理 | 当前仅 Dear 主图使用；提取为公共工具模块，给第二个真实消费者 Showcase 显式接线 |
| `services/dearflow_agent/capabilities.py:configured_mcp_names()`（同 Runtime src 根） | 服务端声明名字，拒绝非法或重复名称 | 多项目连接同一 query 名也被全局判重复；目录改为跨连接集合，同连接与实际工具重名仍拒绝 |
| `runtime/resource_bindings.py:resolve_resource_binding()`（同 Runtime src 根） | 校验 tenant/project/thread 与资源字段 | 未核验 connection 自身归属；还需将 binding 与受管连接范围相匹配 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:create_thread()` | 服务端 Thread ID、IAM、ACL 与项目字段注入 | 没有知识资源签发路径；补一份服务端静态项目映射，并生成不含凭据的 binding |
| API `core/runtime_contract.py:PRIVATE_RUNTIME_STATE_KEYS`；`thread_access.py:initial_metadata()` | 多种服务端字段禁止客户端注入 | 当前 private 集合没有 `runtime_resource_bindings`，initial_metadata 也没剥离它；创建入口不能仅凭键名宣称可信 |
| API `adapters/langgraph/sdk_client.py:redact_runtime_private_fields()` | JSON/SSE/history 私有字段投影 | 新 binding 和供应商 payload 仍需核验过滤；不会自动解析所有 JSON 文本来消毒 |
| Runtime `runtime/capabilities.py:graph_tools()` | 图能力/工具目录供策略使用 | Showcase 未声明这些 MCP 名；defaults、catalog、真实 tool list 必须一起更新 |
| Web `apps/platform-web/src/modules/chat/components/ToolResult.vue:evidenceSources` | 已支持 output JSON/text block 的 `sources/evidence`，标题、preview、truncated、无 URL 来源 | 当前 K 的 `citations` 不能直接触发来源卡；后端输出匹配 `sources`，优先零新 UI |
| Web `apps/platform-web/src/modules/dear-agent/components/ToolResult.vue` | 转发共享 Chat ToolResult | 同事只验证两个入口，不维护第二套知识组件 |
| Runtime `tools/documents.py`、Dear `memory.py` | 线程附件读取、个人偏好/事实记忆 | 均不替代跨会话项目知识；不改它们来承载 RAG |

## 部署能力边界

K 的锁文件：Python ≥3.13、RAGAnything 1.2.10、LightRAG 1.4.12、FastMCP 3.2.0、Docling 2.84.0。P 的 Runtime 也要求 Python ≥3.13，当前锁定 `langchain-mcp-adapters` 0.3.2 / MCP 1.26.0。**不是 Python 主版本冲突；仍应独立环境和进程，避免解析与索引依赖污染执行层。**

候选项目没有可直接交付的知识管理 Web 页面、平台 RBAC、线上索引任务/删除生命周期或大规模服务 SLO。本期单独的 HTTP MCP 进程、独立知识目录和已有模型/Embedding 服务已足够。宿主机原生资源优先，不引入 Docker、PgVector、额外 Redis 或 GraphHarbor 变更。

服务能够监听 HTTP 不等于安全可上线。真实配置、凭据、Embedding 部署、样本文档和使用规模尚未核验，最终可用性按 [verification.md](verification.md) 实测判断。
