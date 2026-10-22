# LightRAG MCP 知识库真实文档状态与图谱资产对齐 - 整体方案

## 背景与问题定性
用户在平台聊天界面询问“知识库中有哪些文档”时，Agent 调用 `mcp_list_project_knowledge_documents` 仅查出 3 份 PDF 文档（带有 `kd_` 前缀的临时伪造哈希 ID），而在远端 LightRAG 原生 WebUI（Knowledge Hub）中，该项目（`__default/11111111-1111-4111-8111-111111111111`）实打实索引了 13 份多模态文档（包含 Markdown、SVG、PNG、JSON、PDF，共 2,450 个实体和 3,890 条关系）。

经老王暴躁且精准的源码审计与远端宿主机实测，确认根因如下：
1. **MCP 假实现**：`<lightrag-repo>/gateway_mcp_server.py` 中的 `mcp_list_project_knowledge_documents` 未接入 LightRAG 底层真实的 `rag.doc_status` 存储，而是粗暴扫描本地 `project_dir / "managed_assets"` 文件夹；
2. **两张皮数据源**：`managed_assets` 文件夹中仅存留了历史测试的 3 个旧 PDF，而真正被切片、构建图谱并持久化在 `kv_store_doc_status.json` 中的 13 份多模态资产完全被 MCP 视而不见；
3. **假 ID 与假状态欺骗**：MCP 用 `uuid.uuid5` 当场伪造 `kd_xxx` 假 ID，并将状态硬编码为 `ready`，导致 Agent 认知严重失真，多模态能力全面丧失；
4. **Scope 静态偷懒反模式**：`gateway_mcp_server.py` 中 `_get_current_scope()` 居然写死为 `resolve_default_or_first_scope()`，未从当前 FastMCP 请求 Header 中按请求解析 Bearer JWT，导致无法实现真正的动态多项目隔离！

## 用户新增核心诉求与解决方案

### 1. 项目专属文档隔离（严格物理隔离，绝不能看到所有文档或跨项目串台）
- **诉求**：在平台下切换项目时，Agent 和用户只能看到“该项目专属”的文档，严禁混杂全局或其它项目文档。
- **技术实现**：
  - 接入请求上下文（Request-Context）：FastMCP 从当前请求中提取 `Authorization: Bearer <jwt_token>`；
  - 动态解码 Scope：提取出当前请求专属的 `tenant_id` 和 `project_id`；
  - 严格物理隔离目录：LightRAG 底层每个项目拥有独立目录 `${storage_root}/${tenant_id}/${project_id}/`，`rag.doc_status` 加载的是该项目独占的 `revisions/rev_1/kv_store_doc_status.json`；
  - 结果：切到项目 A，查出的只有项目 A 的文档；切到项目 B，查出的只有项目 B 的文档，绝不串台。

### 2. 项目名称与 LightRAG 两端一一对应（消灭冷冰冰的 UUID 猜谜）
- **诉求**：当前平台上的项目名称（如“平台默认项目”、“电商客服知识库”）与 LightRAG 端的项目名称一一对应，方便查找与管理。
- **技术实现**：
  - **Token 携带真实名称**：`platform-api` 签发 Scoped JWT 时，将项目的真实名称 `project_name` 存入 JWT claims；
  - **LightRAG 动态元数据持久化**：LightRAG 收到请求验签解出 `project_name` 后，自动同步更新对应物理目录下的 `meta.json`（写入 `"name": project_name`）；
  - **WebUI 友好展示**：LightRAG Web UI 与工作区选择器自动优先读取 `meta.json` 的 `name` 字段，展示形如 `“平台默认项目 (11111111)”`，让两端名称彻底对齐。

## 四层架构影响评估与定界
根据 Karpathy Guidelines（Surgical Changes，最小修改、只动必须动的，绝不过度工程化）：

1. **前端 (platform-web)：【不需要改动，略过】**
   - 前端已支持多项目切换与纯 Markdown 渲染，Agent 拿到什么就渲染什么。
2. **后端 (platform-api)：【微调 JWT 注入 project_name】**
   - 在 `build_knowledge_binding` 中，签发 JWT 时顺便将 `project_name` 传入，提供给 LightRAG 自动对齐名称。
3. **运行时 (runtime-service)：【不需要改动，略过】**
   - 运行时透传 dynamic token，保持无侵入。
4. **知识库服务 (LightRAG)：【核心战场】**
   - 彻底重写 `mcp_list_project_knowledge_documents` 与 `mcp_get_project_knowledge_document_status`，直连项目专属 `rag.doc_status`；
   - 支持请求级 Bearer JWT 动态验签，解出 `project_id` 与 `project_name`；
   - 自动原子持久化 `meta.json`，确保项目名称两端 100% 对齐。
