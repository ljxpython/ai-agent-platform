# 知识库动态多项目绑定与免重启鉴权体系 - 验证计划和记录

## 验证计划

### 单元测试
- [ ] `test_jwt_token_verifier()` - 验证 RAG 端对合法 JWT、过期 JWT、伪造签名的判定
- [ ] `test_lazy_load_project_paths()` - 验证全新项目首次接入时的物理路径懒加载创建
- [ ] `test_project_record_knowledge_base_id()` - 验证 Platform API 创建项目时自动分配并持久化 knowledge_base_id
- [ ] `test_dynamic_knowledge_token_minting()` - 验证 Platform API 签发 Scoped Token 的正确性
- [ ] `test_runtime_mcp_dynamic_gateway_loading()` - 验证 Runtime Service 在动态 Token 存在时的工具装配

### 集成测试
- [ ] **场景 1：向后兼容性验证**
  - 步骤：使用旧的静态 Token 访问 RAG `/mcp` 端点；
  - 预期：完全兼容，旧项目依然能够正常列出和检索文档。
- [ ] **场景 2：跨项目越权防御验证**
  - 步骤：使用项目 A 的 Token 尝试访问项目 B 的文档或状态；
  - 预期：被 403/404 拦截，绝不发生跨租户数据泄漏。

### 端到端测试
- [ ] **核心验收链路：零重启新建项目与全功能实测**
  1. 启动全栈服务后，通过 Web 页面新建一个名为“动态知识库测试项目”的项目；
  2. 观察控制台，确认无需重启任何后端服务或远端微服务；
  3. 进入该项目，进入知识库面板，确认文档列表空态加载成功；
  4. 上传一份测试文档（如 PDF 或 Markdown），确认上传排队与入库成功；
  5. 在该项目下开启新对话，询问“知识库里有哪些文档？”，确认 Agent 自动调用 `mcp_list_project_knowledge_documents` 并清晰回答；
  6. 登录远端 `sshmy2`，检查 `/home/<user>/rag-data/__default/{新项目ID}/`，确认文件物理落盘且权限正确。

## 验证记录

### 2026-10-14 初始状态
**执行人：** @lijiaxin (老王)
- 方案与任务文档已完成制定，待技术讨论对齐后正式启动 Phase 1 实现。

### 2026-10-14 Phase 1 & 2 & 3.1 实施验证
**执行人：** @lijiaxin (老王)
- **Phase 1 验证：**
  - `research/rag-anything-use/tests/test_knowledge_security.py::test_dynamic_jwt_token_verification_and_ensure_project` 测试通过（7 passed in 1.21s）。
  - JWT HS256 解密、claims 权限提取、篡改 Token 拦截、物理项目动态自动建库均正常。
- **Phase 2 验证：**
  - `apps/platform-api/tests/test_knowledge_mcp_bindings.py` 全量通过（6 passed, 3 subtests passed in 1.75s）。验证了未在静态 mapping 中的新项目动态签发 JWT Scoped Token 并注入 Thread Binding。
  - `apps/runtime-service/tests/runtime/test_resource_bindings.py` 与 `test_mcp_tools.py` 全量通过（7 passed in 6.51s）。验证了 `RuntimeResourceBinding` 携带动态 `auth_token`、`gateway_url` 时正确装配 FastMCP 客户端。
- **Phase 3.1 远端微服务实测：**
  - 代码同步至 `sshmy2` 并平滑重启 `rag-service.service`。
  - 从宿主机使用 Platform-API 逻辑签发的动态 JWT，向 `http://152.136.27.196:8000/sse` 发起真实 MCP 握手，成功获取到 5 个核心知识库工具：
    `['mcp_query_project_knowledge', 'list_project_knowledge_documents', 'get_project_knowledge_document_status', 'mcp_submit_project_knowledge_document', 'mcp_get_project_knowledge_ingest_job']`
  - 远端 SQLite 数据库自动注册项目 `5a5b7239-43e3-40e6-bba3-e64d96057607` 的知识库 `kb_5a5b723943e340e6bba3e64d96057607`。
- **本地全栈运行状态：**
  - `scripts/local-stack.sh restart` 执行完成，`runtime-api`, `runtime-worker`, `platform-api`, `platform-web` 均处于 running 状态。

### 2026-10-14 Phase 3.1 补充修复与验证（工具暴露与 Token 额度）
**执行人：** @lijiaxin (老王)
- **根因排查：**
  1. `configured_mcp_names()` 过去死锁在静态环境变量 `RUNTIME_MCP_CONNECTIONS_JSON`，动态网关模式下返回空元组，导致 `dearflow_agent` 默认把 MCP 工具当成未授权/未暴露。
  2. 远端 FastMCP 工具名缺少 `mcp_` 前缀（`list_project_knowledge_documents`），而 `dearflow_agent` 与提示词严格约定 `mcp_` 前缀。
  3. `.env` 中的 `RUNTIME_TOKEN_BUDGET_MAX_TOKENS` 实际配置为 `100000`（10万），非用户预期的 `1000000`（100万）。
- **实施改动：**
  - 远端 `mcp_server.py` 增加 `mcp_list_project_knowledge_documents` 与 `mcp_get_project_knowledge_document_status` 双向别名工具。
  - 本地 `mcp_config.py` 将动态知识库工具集纳入 `configured_mcp_names()`，确保 `dearflow_agent` 正常申请。
  - 本地 `knowledge_bindings.py` 与 `tools/mcp.py` 严格规范 `/mcp` 路径后缀。
  - `apps/runtime-service/.env` 将 `RUNTIME_TOKEN_BUDGET_MAX_TOKENS` 修正为 `1000000`。
- **验证结果：**
  - `apps/runtime-service` 113 项测试全绿。
  - 真实 Python 探针模拟加载真实远端网关，成功装配 5 个 MCP 工具：
    `['mcp_query_project_knowledge', 'mcp_list_project_knowledge_documents', 'mcp_get_project_knowledge_document_status', 'mcp_submit_project_knowledge_document', 'mcp_get_project_knowledge_ingest_job']`
  - 服务全栈平滑重启成功。

#### 阶段结论
动态工具暴露与 Token 上限均已精准修复到位，具备完整端到端测试条件。
