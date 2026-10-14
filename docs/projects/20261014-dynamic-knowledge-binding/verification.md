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
  6. 登录远端 `sshmy2`，检查 `/home/ubuntu/rag-data/__default/{新项目ID}/`，确认文件物理落盘且权限正确。

## 验证记录

### 2026-10-14 初始状态
**执行人：** @lijiaxin (老王)
- 方案与任务文档已完成制定，待技术讨论对齐后正式启动 Phase 1 实现。

#### 最终结论
规划就绪，等待执行授权。
