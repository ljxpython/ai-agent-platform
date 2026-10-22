# LightRAG MCP 知识库真实文档状态与图谱资产对齐 - 任务拆分

## 任务列表

### 阶段 1：平台端项目名称联动微调
- [x] **Task 1.0: `platform-api` 签发 JWT 时增加 `project_name` 透传**
  - 代码位置：`apps/platform-api/src/platform_api/modules/runtime_gateway/application/knowledge_bindings.py` 及 `authorization.py`
  - 改动内容：在构造 dynamic knowledge token 时，将真实 `project_name`（或项目名称）打包进 JWT payload，方便 LightRAG 自动认亲。
  - 实施状态：已确认 platform-api 会话网关与绑定逻辑已注入 project_name，并在鉴权 Token 中透传。

### 阶段 2：LightRAG 改造与本地验证
- [x] **Task 2.1: 重构 `gateway_mcp_server.py` 的动态请求 Scope 提取**
  - 代码位置：`<lightrag-repo>/gateway_mcp_server.py`
  - 改动内容：使用 FastMCP 官方 `get_http_headers` / `get_http_request` 提取 Bearer Token，动态解出 `tenant_id`、`project_id` 与 `project_name`。彻底根除 Starlette 中间件在 SSE 流式响应下 ContextVar 被提前 reset 的隐蔽缺陷。
  - 同步调用 `mgr.save_project_meta` 确保 `meta.json` 里的项目名称与平台实时对齐。
- [x] **Task 2.2: 重构 `mcp_list_project_knowledge_documents` 与状态工具**
  - 代码位置：`<lightrag-repo>/gateway_mcp_server.py`、`lightrag/kg/json_doc_status_impl.py`、`lightrag/kg/json_kv_impl.py`
  - 改动内容：彻底移除扫描 `managed_assets` 目录的老逻辑；通过 `acquire_read_lease(tenant_id, project_id)` 获取专属 `rag` 实例；直连 `rag.doc_status.get_docs_paginated` 读取真实的文档记录；
  - 核心修复：在 `JsonDocStatusStorage` 与 `JsonKVStorage` 中注入基于 `working_dir` 的 md5 隔离命名空间（`f"{wdir_tag}_{self.namespace}"`），彻底铲除跨项目共享内存导致的数据串台重大 Bug。
- [x] **Task 2.3: 本地单测验证多项目隔离与文档清单**
  - 验证项目 A（默认项目）召回 13 份多模态文档，项目 B（test）返回 0 篇，互不影响。

### 阶段 3：远端 `sshmy2` 生产部署与服务验证
- [x] **Task 3.1: 代码同步至远端服务器 `sshmy2`**
  - 操作：将修改后的 `gateway_mcp_server.py`、`json_doc_status_impl.py`、`json_kv_impl.py` 同步到 `sshmy2:/home/<user>/lightrag-v2-exploration/LightRAG/`。
- [x] **Task 3.2: 重启远端 `rag-service.service` 并校验服务健康**
  - 操作：执行 `systemctl restart rag-service.service`，检查日志确认服务 active 且 8 个 MCP 工具全部注册。

### 阶段 4：全链路端到端联合验收
- [x] **Task 4.1: 远端多项目专属文档隔离与名称对齐验证**
  - 操作：分别携带不同项目 Token 调用 `mcp_list_project_knowledge_documents`，确认项目之间文档严格隔离；确认远端 `meta.json` 中项目名称已实时同步对齐。
- [x] **Task 4.2: 平台 Web 界面对话真实大模型验证**
  - 操作：使用 Playwright + Chromium 自动化端到端测试闭环工具进行真实大模型（deepseek-v4.1-flash）全链路测试，截取 4 张关键证据截图，验证通过（Exit Code 0）。
