# 平台侧任务清单

唯一进度来源。状态：非前端实施、V02与Final已完成；最终记录和前端多格式/v2/图片真实浏览器接续见[新专项](../20261013-knowledge-documents-platform/tasks.md)。平台独立六项及V02已完成，前端同事已交付F01–F03旧版代码/自测；不以模拟浏览器脚本代替真实入库。RAG G01/K01–K08 与前端由同事负责；下述历史验证保留在[verification.md](verification.md)。

## A01 成员权限与安全项目状态代理

- [x] 新增两知识权限、受管 K client、安全 DTO、四 GET、配置/lifespan、审计。
- **改动内容：** 三项目角色新增独立read/upload权限；四GET重加载当前成员/凭据与active项目，provider网络前后复核；10秒/1MiB上界与严格安全投影。
- **代码位置：** `apps/platform-api/src/platform_api/modules/iam/application/policies.py` → PermissionCode/PROJECT_PERMISSION_MAP；`modules/knowledge/service.py` → require_scope/KnowledgeService.read；`modules/knowledge/router.py`；`adapters/knowledge/client.py` → KnowledgeClient.get；config/lifespan及audit/http_resolution。
- **预期结果：** 普通成员可按权限读资料/任务；不扩大executor的runtime.write，不公开服务凭据。
- **验证项：** `tests/test_knowledge_member_upload.py` 及锁定API集合45 passed/21 subtests；真实HTTPfixture四GET/撤权/安全投影通过。
- **状态：** `[x]` done，2026-10-12；[实施详情](implementation/01-platform-api.md)。
- **合规检查：** [x] 实现；[x] 实测；[x] tasks更新；[x] CONTEXT更新；[x] FEATURES更新；[x] CHANGELOG用户能力留痕。

## A02 read/upload/start/activate 精确授权

- [x] 专用 HMAC 请求和 30 秒 grant、当前主体重建、Thread ACL、项目与凭据复核、候选/base 绑定。
- **改动内容：** read只接受任务用途，upload绑定原文件/Run和comment ACL；后台start/activate复查原主体、Run与候选，不依赖Thread存活。
- **代码位置：** `apps/platform-api/src/platform_api/modules/knowledge/authorization.py` → KnowledgeRead/KnowledgeOperation/parse_operation/authorize_operation；router.authorize与auth_context精确内部入口。
- **预期结果：** 静态Bearer不能授予成员写权限；伪身份、篡改/过期/错用途/错scope拒绝；撤权在排队/发布前生效，写关闭不阻断read。
- **验证项：** `tests/test_knowledge_authorization.py`，HTTP签名/SQL/audit断言与锁定API集合通过；三阶段权限、Thread删除、服务账号撤权均覆盖。
- **状态：** `[x]` done，2026-10-12；RAG `5be564a`消费字段和新签时序已实测对齐，平台校验保持；V02完整验收另行判定。
- **合规检查：** [x] 实现；[x] 实测；[x] tasks更新；[x] CONTEXT更新；[x] FEATURES更新；[x] CHANGELOG共用新增成员知识能力条目。

## R01 可信附件与 MCP interceptor

- [x] 当前 Thread 六字段可信 FileRef、原字节/hash、受管上传、私有 header、幂等重放/回查、输出安全投影。
- **改动内容：** 现有HTTP上传保存workspace外私有回执、fork复制；原bytes/hash/name校验，授权→PUT→再授权→MCP override；同key失ACK只读回查；4KiB安全回执/取消传播。
- **代码位置：** `apps/runtime-service/src/runtime_service/workspace/attachment_receipts.py` → AttachmentReceipts；`http/documents.py`、`http/workspace.py`；`tools/knowledge_upload.py` → _identity/_file/_grant/knowledge_upload_interceptor；`tools/knowledge_jobs.py` → receipt_result/project_job_result。
- **预期结果：** 受理后即返回，用户可继续聊天；伪文件/路径/别名不提权；秘密只进内部headers；未知响应不新建任务；迁移null job仍保留searchable事实。
- **验证项：** `tests/tools/test_knowledge_upload.py`、真实HTTP官方Adapter和附件/fork相关Runtime集合112 passed。非法回查非object先复现失败，补类型校验后通过。
- **状态：** `[x]` done，2026-10-12；[实施详情](implementation/02-runtime-upload.md)。
- **合规检查：** [x] 实现；[x] 实测；[x] tasks更新；[x] CONTEXT更新；[x] FEATURES更新；[x] CHANGELOG共用成员异步共享能力条目。

## R02 两主图、审批与 Plan/deny

- [x] DearFlow/Showcase 共同精确工具、catalog/defaults、HITL 和提示词。
- **改动内容：** 公共loader只允许精确submit写例外；三工具按模式/开关/deny裁剪，两根复用HITL和同一安全interceptor，提示词要求用户明确共享。
- **代码位置：** `apps/runtime-service/src/runtime_service/tools/mcp.py` → _knowledge_schema/load_mcp_tools；`runtime/mcp_config.py` → configured_mcp_names/knowledge_upload_enabled；两图agent.py/prompts.py。
- **预期结果：** Plan/schema/offload/子图/unbound/deny不提权；review/workspace_write批准/拒绝沿现有策略，full_access按既有行为；submit不加入WORKSPACE_WRITE_TOOLS。
- **验证项：** `tests/services/test_knowledge_composition.py` 六模式和三策略approve/reject；loader schema/annotations/mutation测试与interceptor当前权限测试，包含在112 passed中。
- **状态：** `[x]` done，2026-10-12；组合测试的fake工具不作为RAG解析或真实审批后入库证据。
- **合规检查：** [x] 实现；[x] 实测；[x] tasks更新；[x] CONTEXT更新；[x] FEATURES更新；[x] CHANGELOG共用成员知识能力条目。

## O01 配置、运维与交接

- [x] 默认关闭、无 secret 示例、活规范和 local-stack 接线；平台 FEATURES/CONTEXT/CHANGELOG；接口 fixture、前端交接与话术。
- **改动内容：** 两app示例开关默认关闭；所属授权回调自动生成/旧缺项兼容；活规范与部署/前端交接、7份fixture及安全现场证据齐全。
- **代码位置：** 两app `.env.example`、`scripts/local_stack_worktree.py` → CALLBACKS/configs、`scripts/local-stack.sh` → load_runtime_env；API configuration/permission/audit规范、Runtime知识规范与本专项handoff/runbook。
- **预期结果：** 旧query不被新写开关关闭；缺连接安全降级；旧Worktree不回退主环境；前端同事可按实际DTO开发。
- **验证项：** 脚本5 passed、shell syntax、doctor和本环境平台进程重启/ready；真实Worker＋DeepSeek旧query1 passed，现场capability200 disabled且catalog无submit；JSON/文档/私密信息检查见验证记录。
- **状态：** `[x]` done，2026-10-12；未修改RAG/前端业务源码，未开启online写或提交代码。
- **合规检查：** [x] 实现/交接；[x] 实测；[x] tasks更新；[x] CONTEXT更新；[x] FEATURES更新；[x] CHANGELOG更新。

## V01 平台独立集成、安全与回归

- [x] 锁定契约、真实平台 HTTP 与受控 MCP 最短完整链、安全/取消/重放/配置回退验证；相关服务回归与静态检查。
- **改动内容：** API当前SQL/IAM/审计、Runtime官方Adapter及受控HTTPprovider最短整链、恶意响应/私密字段/取消/失ACK/同key/回退覆盖；安全fixture与运行证据。
- **代码位置：** `apps/platform-api/tests/test_knowledge_member_upload.py`、`test_knowledge_authorization.py`；`apps/runtime-service/tests/tools/test_knowledge_upload.py`、`test_knowledge_upload_http.py`；相关既有回归。
- **预期结果：** 平台边界可复验；mock/HTTP协议与真实RAG分开，测试不冒充增量索引或去重计费验收。
- **验证项：** API45 passed/21 subtests、Runtime112 passed、脚本5 passed、真实旧query1 passed；Ruff/compileall/shell与文档自检通过，具体命令见verification。
- **状态：** `[x]` done，2026-10-12；当时未执行Final，2026-10-13已由承接专项完成非前端V02及统一Final，不宣称前端/生产或全仓全绿。
- **合规检查：** [x] 测试实现；[x] 实测；[x] tasks更新；[x] CONTEXT验证状态更新；[x] FEATURES验证状态更新；CHANGELOG测试细节跳过（能力已有用户描述）。

## F01–F03 前端聊天附件入库门禁、回执卡与项目知识面板

- [x] F01–F03 前端全套组件实现、全局 Tracker 轮询、类型检查、Vitest 单元测试与 Playwright 端到端测试闭环。
- **改动内容：**
  - **F01**：在附件预览组件集成“共享至项目知识库”门禁复选框，对非 TXT/MD 文件、`planMode`、无 `project.knowledge.upload` 权限安全禁用；输入框实现意向文本智能装配。
  - **F02**：封装独立回执卡组件 `KnowledgeSubmissionCard.vue`，实现 6 状态机、reused、null job、searchable 映射；实现全局单例轮询管理器 `useKnowledgeJobTracker.ts`，支持后台休眠与前台补查退避。
  - **F03**：改造 `ProjectDetailPage.vue` 为“项目概览与成员”和“项目知识库”双 Tab；实现 `ProjectKnowledgePanel.vue`，支持资料列表与任务历史双视图、分页与刷新。
- **代码位置：**
  - `apps/platform-web/src/services/knowledge/knowledge.service.ts`
  - `apps/platform-web/src/composables/useKnowledgeJobTracker.ts`
  - `apps/platform-web/src/modules/chat/components/KnowledgeSubmissionCard.vue`
  - `apps/platform-web/src/modules/chat/components/ToolResult.vue`
  - `apps/platform-web/src/modules/chat/components/ChatAttachmentPreview.vue`
  - `apps/platform-web/src/modules/chat/components/ChatComposer.vue`
  - `apps/platform-web/src/modules/projects/components/ProjectKnowledgePanel.vue`
  - `apps/platform-web/src/modules/projects/pages/ProjectDetailPage.vue`
- **预期结果：** 0 TypeScript 报错；Playwright 端到端测试与 Vitest 单元测试全部通过；服务正常提供用户验收。
- **验证项：**
  - `vue-tsc --noEmit` 0 报错；
  - Vitest 单元测试：`KnowledgeSubmissionCard.spec.ts`、`useKnowledgeJobTracker.spec.ts`、`ProjectKnowledgePanel.spec.ts` 8 passed；
  - Playwright E2E 测试：`knowledge-member-upload.spec.ts`（包含真实大模型调用）3 passed；
  - 产出并留档 6 张现场截图于 `evidence/screenshots/`。
- **状态：** `[x]` done，2026-10-12。
- **合规检查：** [x] 实现；[x] 实测；[x] tasks更新；[x] 截图查验分析。
- **本轮验证边界：** 上述前端自测为同事交付记录，本轮未复跑浏览器；源码F01/F03包含route.fulfill模拟知识响应，F02仅断言助手消息可见并截图，没有断言submit回执或RAG ready。不得并入V02真实入库验收。

## V02 RAG 真实联合验收

- [x] 真实成员上传、ready、另一成员新旧查询、去重费用、撤权/Stop/重启/回退完成。
- **状态：** 2026-10-13非前端done；当前c30e2149，多格式/图片/v2由[承接专项](../20261013-knowledge-documents-platform/verification.md)统一记录Phase与Final。
- **本轮验收：** 实际executor→两Agent root review→queued→ready→editor新旧MCP；PNG/JPEG可信ImageRef、20MiB文件、跨Run处理中与ready samehash复用且RAG新增入库事件0、两项目排队与旧查询、Fork/API/Worker/RAG重启、撤权/Plan/跨项目、pending/已受理聊天Stop、关闭新写排空在途、v1请求回退/v2历史、冻结generation回退/恢复均有真实证据。候选失败/CAS/原reader lease/实际SIGKILL恢复由本轮Ubuntu119项覆盖。
- **历史证据：** febe70a403/405、5be564a协议与Adapter两组七检查以及失败诊断继续保留；本轮解决跨机iat和平台关闭写阻断在途。不抹旧模型失败，不宣称任意业务解析/生产稳定性已验证。
- **启用门禁：** 前端动态多格式、图片原名/完整JSON、正确回执/v2定位及无mock浏览器仍需接续；默认新上传关闭，正式合入/生产启用不自动执行。本轮样本两项目及20MiB边界不作生产容量保证。

前端新接续入口：[逐文件交接/真实fixture/话术](../20261013-knowledge-documents-platform/frontend-handoff.md)。进度只看任务文档，implementation提供细节。
