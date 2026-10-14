# 知识库动态多项目绑定与免重启鉴权体系 - 任务拆分

## Phase 1: 知识库服务升级 (在本地 research/rag-anything-use 验证)

### Task 1.1: 实现基于 HMAC-SHA256 的无状态 Scoped Token 验签
- **改动内容：**
  - 扩展 `KnowledgeTokenVerifier.verify_token`，增加 JWT (HS256) 解密验签分支；
  - 提取 `tenant_id`, `project_id`, `knowledge_base_id`，并校验时间戳有效期。
- **代码位置：** `/Users/lijiaxin/PyCharmMiscProject/research/rag-anything-use/src/knowledge/auth.py`
- **预期结果：** 传入合法签名的 JWT 时，能正确解析出 `KnowledgeScope` 并放行；篡改或过期 Token 被 401 拦截。
- **验证项：** 编写单元测试覆盖静态 Token、动态合法 JWT、篡改 Token、过期 Token 四种场景。
- **状态：** `[x]` 已完成 (2026-10-14) 见 test_knowledge_security.py::test_dynamic_jwt_token_verification_and_ensure_project

### Task 1.2: 支持多项目物理路径与 JobStore 动态懒加载初始化
- **改动内容：**
  - 在 `KnowledgeJobStore` 增加 `ensure_project(knowledge_base_id, tenant_id, project_id)`；
  - 若收到未见过的合法 `knowledge_base_id`，自动在本地 SQLite/磁盘创建对应绑定与目录结构。
- **代码位置：** `/Users/lijiaxin/PyCharmMiscProject/research/rag-anything-use/src/knowledge/jobs.py`
- **预期结果：** 首次带新 project_id 访问时，不报错，自动生成对应目录并就绪。
- **验证项：** 单元测试模拟全新项目首次访问并提交/查询文档。
- **状态：** `[x]` 已完成 (2026-10-14)

---

## Phase 2: 平台侧动态化改造 (Platform-API & Runtime-Service)

### Task 2.1: Platform-API 数据库模型与 Token 签发器实现
- **改动内容：**
  - 在 `ProjectRecord` 确立基于 UUID 的确定性 `kb_{hex}` 物理命名空间，避免不必要的破坏性迁移；
  - 实现 `mint_knowledge_jwt`：基于 `PLATFORM_API_KNOWLEDGE_SECRET` 签发 Scoped HS256 JWT；
  - Settings 增加 `knowledge_gateway_base_url`。
- **代码位置：**
  - `apps/platform-api/src/platform_api/modules/knowledge/authorization.py`
  - `apps/platform-api/src/platform_api/config.py`
- **预期结果：** 任意项目天然确定唯一 `knowledge_base_id`，并可按需生成合法 JWT。
- **验证项：** 单元测试验证新项目 Token 签发与解密。
- **状态：** `[x]` 已完成 (2026-10-14) 见 test_knowledge_mcp_bindings.py::test_dynamic_jwt_binding_when_unconfigured_in_static_mapping

### Task 2.2: Platform-API 控制面与 Thread 绑定动态注入
- **改动内容：**
  - 改造 `knowledge/service.py`：查询文档与状态时，若未配置静态 mapping，支持从数据库读取项目并动态构造 KnowledgeConnection；
  - 改造 `runtime_gateway/application/knowledge_bindings.py`：在创建 Thread 时，若开启知识库密钥，动态注入带签发 Token 的 MCP binding；
  - 改造 `RuntimeGatewayService` 贯通密钥与网关地址。
- **代码位置：**
  - `apps/platform-api/src/platform_api/modules/knowledge/service.py`
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/application/knowledge_bindings.py`
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
- **预期结果：** 新建 Thread 自动具备该项目的动态知识库权限；前端文档列表直接动态渲染。
- **验证项：** `test_knowledge_mcp_bindings.py` 全量通过 (6 passed)。
- **状态：** `[x]` 已完成 (2026-10-14)

### Task 2.3: Runtime-Service 动态 MCP 连接与工具装配
- **改动内容：**
  - 扩展 `RuntimeResourceBinding` 数据类与校验器，支持 `auth_token`、`knowledge_base_id`、`gateway_url` 可选字段；
  - 在 `tools/mcp.py` 的 `load_mcp_tools` 中，支持从 binding 中读取动态 `auth_token` 与统一的 `RUNTIME_KNOWLEDGE_MCP_GATEWAY_URL`；
  - 优先使用动态凭据直连网关，原静态 `RUNTIME_MCP_CONNECTIONS_JSON` 保留为 fallback。
- **代码位置：**
  - `apps/runtime-service/src/runtime_service/runtime/resource_bindings.py`
  - `apps/runtime-service/src/runtime_service/tools/mcp.py`
- **预期结果：** 任意新项目会话启动时，Agent 自动获得 `mcp_list_project_knowledge_documents` 等工具，零重启。
- **验证项：** `test_resource_bindings.py` (6 passed) 与 `test_mcp_tools.py` 全绿。
- **状态：** `[x]` 已完成 (2026-10-14)

---

## Phase 3: 远端部署与全链路端到端验收

### Task 3.1: 将 RAG 代码同步并部署至远端 Ubuntu (sshmy2)
- **改动内容：**
  - 将本地 `rag-anything-use` 升级代码同步至 `sshmy2`；
  - 更新远端 `/home/ubuntu/PyCharmMiscProject/rag-anything-use/.env` 确保配置了统一的 `KNOWLEDGE_AUTHORIZATION_SECRET`；
  - 平滑重启 `rag-service.service`；
  - 补齐 `mcp_list_project_knowledge_documents` 与 `mcp_get_project_knowledge_document_status` 前缀别名；
  - 在 `mcp_config.py` 中将动态知识库工具纳入 `configured_mcp_names()`，解决动态网关工具未暴露的问题；
  - 修正 `.env` 中的 `RUNTIME_TOKEN_BUDGET_MAX_TOKENS` 为 1000000 并规范网关 URL 后缀 `/mcp`。
- **代码位置：** 远端 `sshmy2` 及本地 runtime-service / platform-api
- **预期结果：** 远端服务健康运行，动态工具成功暴露至 dearflow_agent，Token 预算正确放宽至 100 万。
- **验证项：** 真实 Python 加载探针验证 5 个 MCP 工具完整装配，113 项单测全绿。
- **状态：** `[x]` 已完成 (2026-10-14) 实测动态 Token 探测成功返回 5 个 MCP 工具并自动建库。

### Task 3.2: 平台端到端全链路验收 (无重启新建项目实测)
- **改动内容：**
  - 启动本地全栈服务（`local-stack.sh start`）；
  - 在 Web 界面开启新对话；
  - 提问“你帮我查询一下知识库里面现在有哪些文档？”；
  - 确认 Agent 成功调用 `mcp_list_project_knowledge_documents`；
  - 上传测试文档，确认远端物理目录正确落盘且不同项目之间严格隔离。
- **验证项：** 全链路端到端测试（见 `verification.md`）。
- **状态：** `[-]` 本地全栈就绪，等待用户在 Web 界面发起新对话进行端到端体验验收

## 进度追踪
- [x] Phase 1 完成 (RAG 本地核心验证)
- [x] Phase 2 完成 (平台控制面与运行时动态化)
- [x] Phase 3.1 完成 (远端部署、MCP 前缀工具别名与 Token 预算修正)
- [ ] Phase 3.2 待验收 (Web 端开启新对话验证)
