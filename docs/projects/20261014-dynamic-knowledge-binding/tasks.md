# 知识库动态多项目绑定与免重启鉴权体系 - 任务拆分

## Phase 1: 知识库服务升级 (在本地 research/rag-anything-use 验证)

### Task 1.1: 实现基于 HMAC-SHA256 的无状态 Scoped Token 验签
- **改动内容：**
  - 扩展 `KnowledgeTokenVerifier.verify_token`，增加 JWT (HS256) 解密验签分支；
  - 提取 `tenant_id`, `project_id`, `knowledge_base_id`，并校验时间戳有效期。
- **代码位置：** `/Users/lijiaxin/PyCharmMiscProject/research/rag-anything-use/src/knowledge/auth.py`
- **预期结果：** 传入合法签名的 JWT 时，能正确解析出 `KnowledgeScope` 并放行；篡改或过期 Token 被 401 拦截。
- **验证项：** 编写单元测试覆盖静态 Token、动态合法 JWT、篡改 Token、过期 Token 四种场景。
- **状态：** `[ ]` 待开始

### Task 1.2: 支持多项目物理路径与 JobStore 动态懒加载初始化
- **改动内容：**
  - 在 `KnowledgeJobStore` 增加 `ensure_project(knowledge_base_id, tenant_id, project_id)`；
  - 若收到未见过的合法 `knowledge_base_id`，自动在本地 SQLite/磁盘创建对应绑定与目录结构。
- **代码位置：** `/Users/lijiaxin/PyCharmMiscProject/research/rag-anything-use/src/knowledge/jobs.py`
- **预期结果：** 首次带新 project_id 访问时，不报错，自动生成对应目录并就绪。
- **验证项：** 单元测试模拟全新项目首次访问并提交/查询文档。
- **状态：** `[ ]` 待开始

---

## Phase 2: 平台侧动态化改造 (Platform-API & Runtime-Service)

### Task 2.1: Platform-API 数据库模型与 Token 签发器实现
- **改动内容：**
  - 扩展项目表 `ProjectRecord` 增加 `knowledge_base_id` 字段（通过 Alembic 迁移脚本）；
  - 实现 `KnowledgeTokenIssuer`：基于 `PLATFORM_API_KNOWLEDGE_SECRET` 签发 Scoped JWT；
  - 在创建新项目时，自动为该项目分配唯一的 `knowledge_base_id`。
- **代码位置：**
  - `apps/platform-api/src/platform_api/modules/projects/models.py`
  - `apps/platform-api/src/platform_api/modules/knowledge/authorization.py`
- **预期结果：** 新建项目自动持久化 `knowledge_base_id`，并可按需生成合法 JWT。
- **验证项：** 单元测试验证新项目创建及 Token 签发解密。
- **状态：** `[ ]` 待开始

### Task 2.2: Platform-API 控制面与 Thread 绑定动态注入
- **改动内容：**
  - 改造 `knowledge/service.py`：查询文档与状态时，支持从数据库读取项目并动态构造访问客户端，替代静态 `knowledge_mcp_bindings` 字典；
  - 改造 `runtime_gateway/application/knowledge_bindings.py`：在创建 Thread 时，若项目有 `knowledge_base_id`，动态注入带签发 Token 的 MCP binding。
- **代码位置：**
  - `apps/platform-api/src/platform_api/modules/knowledge/service.py`
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/application/knowledge_bindings.py`
- **预期结果：** 新建 Thread 自动具备该项目的动态知识库权限；前端文档列表直接根据数据库渲染。
- **验证项：** `test_knowledge_mcp_bindings.py` 回归与新增动态绑定测试。
- **状态：** `[ ]` 待开始

### Task 2.3: Runtime-Service 动态 MCP 连接与工具装配
- **改动内容：**
  - 在 `tools/mcp.py` 的 `load_mcp_tools` 中，支持读取 binding 中的动态 `auth_token` 与统一的 `RUNTIME_KNOWLEDGE_MCP_GATEWAY_URL`；
  - 优先使用动态凭据直连网关，原静态 `RUNTIME_MCP_CONNECTIONS_JSON` 保留为 fallback。
- **代码位置：** `apps/runtime-service/src/runtime_service/tools/mcp.py`
- **预期结果：** 任意新项目会话启动时，Agent 自动获得 `mcp_list_project_knowledge_documents` 等工具，零重启。
- **验证项：** Runtime 单元测试验证动态 Token 下的 MCP 工具装配。
- **状态：** `[ ]` 待开始

---

## Phase 3: 远端部署与全链路端到端验收

### Task 3.1: 将 RAG 代码同步并部署至远端 Ubuntu (sshmy2)
- **改动内容：**
  - 将本地 `rag-anything-use` 升级代码同步至 `sshmy2`；
  - 更新远端 `/home/ubuntu/PyCharmMiscProject/rag-anything-use/.env` 确保配置了统一的 `KNOWLEDGE_AUTHORIZATION_SECRET`；
  - 平滑重启 `rag-service.service`。
- **代码位置：** 远端 `sshmy2`
- **预期结果：** 远端服务健康运行，同时兼容静态旧 Token 与动态新 JWT。
- **验证项：** 本地用新签发的 JWT 向远端发送 `/mcp` 请求，验证 200 OK。
- **状态：** `[ ]` 待开始

### Task 3.2: 平台端到端全链路验收 (无重启新建项目实测)
- **改动内容：**
  - 启动本地全栈服务（`local-stack.sh start`）；
  - 在 Web 界面或通过 API 创建一个全新的项目；
  - **不进行任何重启或修改 .env**，直接在该项目下开启新对话；
  - 提问“你帮我查询一下知识库里面现在有哪些文档？”；
  - 确认 Agent 成功调用 `mcp_list_project_knowledge_documents`；
  - 上传测试文档，确认远端物理目录正确落盘且不同项目之间严格隔离。
- **验证项：** 全链路端到端测试（见 `verification.md`）。
- **状态：** `[ ]` 待开始

## 进度追踪
- [ ] Phase 1 完成 (RAG 本地核心验证)
- [ ] Phase 2 完成 (平台控制面与运行时动态化)
- [ ] Phase 3 完成 (远端部署与端到端实测)
