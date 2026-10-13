# 任务清单

当前范围：全部非前端开发、验证及前端交接。前端业务代码由同事负责。状态：T01–T06与Final已完成（`done`）。

### T01 root调用与整合兼容
- 改动内容：root ToolNode可信namespace、API循环导入、VerifiedDelegation具名构造与迁移身份检查。
- 代码位置：`apps/runtime-service/src/runtime_service/tools/knowledge_upload.py::_identity`、`runtime/auth.py`；`apps/platform-api/src/platform_api/modules/knowledge/authorization.py`。
- 预期结果：实际root调用可受审批执行；子图/错误委托拒绝；Token/后台身份与迁移保持。
- 验证项：最小知识上传/auth/API authorization测试，Alembic head/revision检查。
- 状态：[x] 2026-10-13完成 → [实现](implementation/01-runtime-contract-and-trust.md)
- 验证结果：Runtime相关146项及API19项+3subtests通过；具名构造与循环导入首轮失败已修复。
- 合规检查：[x] 实现、Phase验证、任务更新；CONTEXT/FEATURES/CHANGELOG随本阶段同步。

### T02 来源v2与固定请求
- 改动内容：双版本安全DTO、定位/预算/history一致、服务固定版本与模型参数隐藏。
- 代码位置：`apps/runtime-service/src/runtime_service/tools/knowledge.py`、`tools/mcp.py`、`runtime/mcp_config.py`、`.env.example`。
- 预期结果：可信定位不丢失；v1兼容；模型无法改版本；非法定位安全失败。
- 验证项：投影/F04/loader版本及恶意字段测试。
- 状态：[x] 2026-10-13完成 → [实现](implementation/01-runtime-contract-and-trust.md)
- 验证结果：双版本、安全定位、预算同值、服务固定版本及provider换版本拒绝通过（相关146项）。
- 合规检查：[x] 实现、Phase验证、任务更新；CONTEXT/FEATURES/CHANGELOG随本阶段同步。

### T03 图片可信收据与原件网关
- 改动内容：图片原名称query转发、私有收据、bytes/hash/MIME/长度校验、旧ImageRef兼容与Fork复制。
- 代码位置：Runtime `http/images.py`、`workspace/attachment_receipts.py`；API runtime_gateway HTTP/service/ports/adapter。
- 预期结果：五字段ImageRef保持；知识转换只取受管上传收据，Agent不能写收据。
- 验证项：图片HTTP、API网关及篡改/无收据/名称/MIME/长度/Fork安全测试。
- 状态：[x] 2026-10-13完成 → [实现](implementation/01-runtime-contract-and-trust.md)
- 验证结果：网关名称/元数据、收据、原MIME、隔离及Fork通过（API19项+3subtests、Runtime相关146项）。
- 合规检查：[x] 实现、Phase验证、任务更新；CONTEXT/FEATURES/CHANGELOG随本阶段同步。

### T04 图片知识工具接线
- 改动内容：submit工具FileRef/ImageRef兼容、interceptor内可信转换，原root/Plan/offload/授权/失ACK门禁。
- 代码位置：`apps/runtime-service/src/runtime_service/tools/knowledge_upload.py`、`tools/mcp.py`。
- 预期结果：PNG/JPEG与文档共用异步入库；WebP/生成图/伪造6字段图片拒绝。
- 验证项：工具schema/原bytes staging/伪造/撤权/幂等失ACK及两Agent组装测试。
- 状态：[x] 2026-10-13完成 → [实现](implementation/01-runtime-contract-and-trust.md)
- 验证结果：PNG/JPEG可信转换与伪造/篡改/生成图/WebP/失ACK/撤权测试通过；真实两图联验见T05。
- 合规检查：[x] 实现、Phase验证、任务更新；CONTEXT/FEATURES/CHANGELOG随本阶段同步。

### T05 真实联验与生命周期
- 改动内容：当前平台Worker＋新RAG，文档及图片上传→审批→ready→成员共享查询；权限/Stop/重启/Fork/同hash复用/新旧资料/v1-v2回退验证。
- 代码位置：`apps/runtime-service/tests/e2e/`、专项脱敏证据及runner。
- 预期结果：真实Agent链通过，异步回执有界，旧资料仍可检索，重复入库不增加模型用量。
- 验证项：真实模型与RAG集成；PDF/DOCX/PPTX/PNG/JPEG；跨项目拒绝、撤权、Plan/子图；保留失败诊断。
- 状态：[x] 2026-10-13完成 → [联验与边界](implementation/02-live-gates-and-regression.md)
- 验证结果：真实六格式/两Agent/两成员、20MiB、处理中与ready同hash零新增入库事件、两项目排队/旧读、Fork/API/Worker重启、撤权/Plan/跨项目、v1/上传关闭与v2历史、RAG重启、冻结版本回退/恢复、pending Stop通过。已受理任务关闭新写后的start/activate继续执行且保留当前撤权检查。RAG119项在Ubuntu复跑。
- 合规检查：[x] Phase与公开证据、任务更新；失败诊断与样本/成本边界保留。

### T06 前端交接与验收收口
- 改动内容：前端逐文件需求/契约/fixture/验收话术；活规范、CONTEXT/FEATURES/CHANGELOG；所有相关单测、静态门禁、Token/后台/迁移回归。
- 预期结果：非前端范围done，前端按文档独立接续，明确发布及样本限制。
- 验证项：API/Runtime相关全量回归、真实E2E、安全与回退；交接字段对照实现。
- 状态：[x] 2026-10-13实现、交接与Final完成 → [前端交接](frontend-handoff.md)
### T07 前端开发与真实端到端测试闭环 (F01–F06)
- 改动内容：按照修订版 frontend-handoff.md 完整落地 F01–F06 前端代码。打通 Ubuntu RAG 1024 维多模态反向隧道与 Platform API，完成无 mock 的真实模型 + 真实浏览器 Playwright 闭环。
- 代码位置：`apps/platform-web/src/modules/chat/`、`apps/platform-web/src/modules/projects/`、`apps/platform-web/e2e/knowledge-documents-platform.spec.ts`。
- 预期结果：普通成员上传（PDF+PNG）→ 审批流转（HITL Review 批准）→ 受理排队/就绪 → 另一成员查询召回证据及 Locator → WebP 禁用门禁 → 项目知识库面板渲染。
- 验证项：vue-tsc 0 错误、Vitest 847 passed 全绿、Playwright + Chromium 真实端到端通过、生成 8 张全流程真实截图。
- 状态：[x] 2026-10-13完成 → [验收截图与记录](evidence/screenshots/)
- 验证结果：全套 8 步端到端测试全绿通过（1 passed, 1.7m），截图 01–08 全部落地且细节无误。

### T08 MCP 目录工具放行与防死循环优化
- 改动内容：在 RAG 服务端注册 `mcp_list_project_knowledge_documents` 与 `mcp_get_project_knowledge_document_status` 双向别名，放开 Runtime MCP 5 工具完整装配，微调 Agent 提示词引导目录查询使用 list 工具、内容检索使用 query 工具，彻底杜绝发散盲搜猜词死循环。
- 代码位置：`.local-stack/evidence/knowledge-platform-documents/remote_server.py`、`scripts/connect_ubuntu_rag.py`、`.local-stack/runtime.env`、`apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py`、`showcase_demo/prompts.py`。
- 预期结果：用户询问知识库文档列表时，Agent 单次调用 list 工具精准返回 Markdown 目录表格，无多余 tool calls，0 死循环。
- 验证项：MCP client 5 工具获取验证、真实 Agent 问答端到端执行测试（由 15 次调用/73 步/死循环中断降低为 1 次工具调用/4 步/14 秒成功输出）。
- 状态：[x] 2026-10-13完成
- 验证结果：真实模型实测通过，秒级输出包含 9 篇文档完整 ID 和 ready 状态的表格，用户最终验收通过。

## 进度
- [x] T01–T04实现及Phase测试完成
- [x] T05真实联验完成
- [x] T06前端交接与验收收口完成
- [x] T07前端开发与真实端到端测试闭环 (F01–F06) 完成
- [x] T08 MCP 目录工具放行与防死循环优化完成
- [x] 用户现场验收全流程通过

Final状态：`done`。全链路需求、前端组件、真实模型验证与专项优化全部完成并通过用户最终验收。
