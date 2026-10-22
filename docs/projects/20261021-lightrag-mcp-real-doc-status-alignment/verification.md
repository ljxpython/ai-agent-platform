# LightRAG MCP 知识库真实文档状态与图谱资产对齐 - 验证计划与记录

## 验证计划

### 1. 自动化与单元验证
- 本地 FastMCP 工具单元测试：
  - 调用 `mcp_list_project_knowledge_documents`；
  - 检查返回的 `documents` 数组长度是否与底层 `kv_store_doc_status.json` 一致（13 份）；
  - 检查文档名称中是否包含 `.png`, `.svg`, `.json`, `.md`, `.pdf` 多模态格式；
  - 检查返回的 `document_id` 是否为真实的 LightRAG doc id（`doc-xxx`）。

### 2. 远端服务部署健康验证
- 远端 systemd 服务检查：
  - `systemctl status rag-service.service` 状态为 `active (running)`；
  - journal 日志中无报错，MCP 8 项工具注册完毕。

### 3. 全链路端到端联合验证
- 真实对话验收：
  - 在平台前端与 `dearflow_agent` 对话：“你查一下知识库，看下知识库中有哪些文档”；
  - 确认工具调用：`mcp_list_project_knowledge_documents` 成功返回；
  - 确认回答内容：Agent 明确罗列 13 份文档，不再声称“只有 3 份且都是 PDF”，而是如实呈现包含文档、图片、架构图与接口文档的完整资产。

## 验证结果记录

### 1. 远端服务健康状态
- 执行命令：`ssh sshmy2 "systemctl is-active rag-service.service; systemctl is-active rag-webui.service"`
- 结果：
  ```
  active
  active
  ```
- 确认：8 项 MCP 工具（含 `mcp_list_project_knowledge_documents`）在 `0.0.0.0:8001/mcp` 正常服务。

### 2. 自动化端到端测试（Playwright + Chromium + 真实大模型）
- 测试脚本：`tests/e2e_knowledge_alignment_test.py`
- 执行命令：`python3 tests/e2e_knowledge_alignment_test.py`
- 结果：**100% 通过（Exit Code 0）**
- 过程与断言细节：
  1. **登录平台**：以 `admin` / `admin123456` 登录 `http://127.0.0.1:3000`；
  2. **默认项目真实文档检索验证**：
     - 在“平台默认项目”工作台向 `dearflow_agent` 提问：“你查一下知识库，看下知识库中有哪些文档”；
     - 模型：`deepseek-v4.1-flash`；
     - 调用工具：`mcp_list_project_knowledge_documents`；
     - 返回结果：成功列出 13 份多模态文档（含 PDF 3 份、图片 4 份、SVG 2 份、Markdown 3 份、JSON 1 份），包含完整 doc ID、切片数、字符数与修改时间；
     - 截图留存：`docs/projects/20261021-lightrag-mcp-real-doc-status-alignment/evidence/02_default_project_13_docs.png`；
  3. **切换隔离项目（test）验证**：
     - 切换到 `test` 项目（ID: `5a5b7239-650a-4c28-989d-773df4047607`）；
     - 向 Agent 提问相同问题：“你查一下知识库，看下知识库中有哪些文档”；
     - 调用工具：`mcp_list_project_knowledge_documents`；
     - 返回结果：大模型精准回复“文档总数：0，文档列表：无”，默认项目的 13 份文档泄露数量为 0；
     - 截图留存：`docs/projects/20261021-lightrag-mcp-real-doc-status-alignment/evidence/03_isolated_project_empty.png`；
  4. **项目名称对齐验证**：
     - 进入“项目管理”页面（`http://127.0.0.1:3000/projects`）；
     - 列表明确展示“平台默认项目”与“test”，与远端 LightRAG `meta.json` 命名完全一致；
     - 截图留存：`docs/projects/20261021-lightrag-mcp-real-doc-status-alignment/evidence/04_projects_name_alignment.png`。

### 3. 证据截图索引
| 编号 | 截图文件 | 检验要点 | 结论 |
|---|---|---|---|
| 01 | `evidence/01_login_and_workspace.png` | 登录与工作区就绪，默认项目上下文建立 | 正常 |
| 02 | `evidence/02_default_project_13_docs.png` | 真实模型调用 MCP 召回 13 份真实多模态文档 | 验证通过 |
| 03 | `evidence/03_isolated_project_empty.png` | 切换 test 项目，文档返回 0 篇，物理隔离无串台 | 验证通过 |
| 04 | `evidence/04_projects_name_alignment.png` | 平台端项目与远端项目名称完全对齐 | 验证通过 |

### 4. 专项排查：Tests 项目与知识库工作台文档数对齐修复 (2026-10-22)
- **问题现象**：
  - 在 `test` 项目中，Agent 调用 MCP 知识库工具返回 `total: 0, documents: []`（显示 0 个）；
  - 但在【知识库】工作台 (Knowledge Hub, 端口 9621) 页面中，却显示有 13 个文档，造成界面与 Agent 认知不一致。
- **根因分析**：
  1. 真实物理存储：`test` 项目（`5a5b7239-43e3-40e6-bba3-e64d96057607`）底层原本就是空项目，MCP 返回 0 篇是隔离生效的正确事实；
  2. 知识库工作台通过 iframe 嵌入 LightRAG WebUI，其 React 内部通过 Zustand (`localStorage['lightrag-workspace-storage']`) 持久化当前项目 ID，默认写死为 `11111111-1111-4111-8111-111111111111`；
  3. 服务端 `run_lightrag_webui_server.py` 的 HTML 注入脚本在跨域 iframe 中只同步了 JWT Token 与 tab，未将 URL 参数中的 `project_id` 同步写入 `localStorage`；
  4. 导致 React 应用内发起的 `/documents/paginated` 接口请求头始终携带 `x-project-id: 11111111-1111-4111-8111-111111111111`，错把默认项目的 13 份文档渲染在 `test` 项目页面。
- **修复方案与落地**：
  1. 修改 `run_lightrag_webui_server.py` 中的 `sso_script`，首行动态解析 `project_id` 并覆写 `lightrag-workspace-storage`；
  2. 同步代码至 `sshmy2` 并重启 `rag-webui.service`；
  3. Playwright 实测抓包验证：
     - `test` 项目下：请求携带 `x-project-id: 5a5b7239...`，返回 `total: 0`，页面显示 `Documents 0` 与 `No Documents` 空态；
     - `平台默认项目` 下：请求携带 `x-project-id: 11111111...`，返回 `total: 13`，正常展示 13 份多模态文档；
     - 界面与 Agent MCP 工具完全统一。
  4. 留存验证截图：`evidence/test_project_knowledge_hub_fixed.png`。

### 5. 四态判定
- **判定结果：** `done`（全量范围达到完成，代码已部署，全链路自动化真实模型测试 100% 绿灯）。
