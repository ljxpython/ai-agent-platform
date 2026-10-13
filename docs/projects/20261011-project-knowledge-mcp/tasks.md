# 项目知识 MCP - 任务与完成卡

**当前总体：非前端与通用多格式验收完成，业务题集质量B02仍blocked，前端接续。** PDF/Office环境B01于2026-10-13由Ubuntu真实平台链解除，最新Final见[承接任务](../20261013-knowledge-documents-platform/tasks.md)。下述2026-10-11交付记录保留历史；平台尚未合并主干，本轮不自动提交/发布。

## 已完成任务（16项）

### P01：三仓盘点

- **改动内容：** 阅读平台/知识工程/DeerFlow，核实现有调用者、权限与来源契约。
- **代码位置：** provider-assessment.md；只读源码。
- **预期结果：** 区分已有能力、缺口和未实测。
- **验证项：** 源码/锁/符号/官方Adapter依据核验 → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；CHANGELOG此文档任务跳过。

### P02：设计与授权

- **改动内容：** 固定项目只读MCP、离线发布、公共接线与最小三层职责。
- **代码位置：** plan.md / README.md。
- **预期结果：** 不扩成在线知识管理产品。
- **验证项：** 用户明确批准方案、本地源码实施与启动 → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；CHANGELOG此文档任务跳过。

### P03：前端分工与验证设计

- **改动内容：** 确定ToolResult/transcript复用与V01–V12矩阵。
- **代码位置：** frontend-handoff.md / verification.md。
- **预期结果：** 前端由同事接续，后端交真实fixture。
- **验证项：** 组件消费位置与验收矩阵核验 → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；CHANGELOG此文档任务跳过。

### P04：导航与状态

- **改动内容：** 同步原F17评估、专项与现状行。
- **代码位置：** docs/CONTEXT.md / docs/FEATURES.md / 原评估README。
- **预期结果：** 实现/Block/前端归属一致。
- **验证项：** 定向链接、代码位置、文档规范与diff；全仓旧问题另列 → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；CHANGELOG此文档任务跳过。

### G0：真实服务Gate

- **改动内容：** 独立uv环境；FastMCP3.2、LightRAG1.4.12、Ollama768、DeepSeek与HTTP。
- **代码位置：** K pyproject.toml / uv.lock / src/demo_support.py / src/mcp_server.py。
- **预期结果：** 两scope/cache/workspace独立，文本模式可启动。
- **验证项：** 两项目HTTP与实际ToolResult/ToolError；Torch阻塞归V1B → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；[x] CHANGELOG用户能力行同步。

### S1：认证、scope与路径

- **改动内容：** Bearer固定scope、单段namespace与resolve/symlink约束、所有读工具安全DTO。
- **代码位置：** K src/knowledge/auth.py:KnowledgeTokenVerifier/resolve_knowledge_scope()；project_paths.py:build_knowledge_project_paths()；admin_service.py。
- **预期结果：** 未授权/额外scope/逃逸在索引调用前拒绝。
- **验证项：** 安全/HTTP/stdio、401、严格输入、跨scope状态not_found → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；[x] CHANGELOG用户能力行同步。

### S2：单次检索与来源

- **改动内容：** query只检索、ready opaque locator、安全有界sources、error/no_hit区分。
- **代码位置：** K rag_engine.py:retrieve() / citations.py:build_retrieval_sources() / schemas.py / mcp_server.py:create_server()。
- **预期结果：** aquery_data=1、aquery=0；8条/800字符/12KiB。
- **验证项：** 计数断言、同名/未知locator、无命中/失败/取消、真实两scope → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；[x] CHANGELOG用户能力行同步。

### S3：生命周期与离线发布

- **改动内容：** cache/明确workspace、初始化60秒/关闭30秒、失败清理、manifest原子写、读写锁和immutable publish；md/txt直接入库。
- **代码位置：** K rag_engine.py:get_lightrag()/close()；publication.py；ingest_service.py；document_registry.py:_save()；cli.py:_execute()；demo_support.py:build_llm_model_func()。
- **预期结果：** 部分/失败索引不发布，重启数据保留；关闭thinking保证抽取正文。
- **验证项：** 生命周期/取消/损坏manifest/部分索引；真实读锁、失败publish、新版本/旧版本恢复、MCP/Embedding重启。PDF归V1B → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；[x] CHANGELOG用户能力行同步。

### A1：平台可信绑定

- **改动内容：** 默认空配置校验，新Thread内部绑定，fork重签，合并其他受管资源。
- **代码位置：** P apps/platform-api/src/platform_api/config.py；modules/runtime_gateway/application/knowledge_bindings.py:build_knowledge_binding()；service.py:create_thread()；presentation/http.py。
- **预期结果：** 浏览器不选resource，旧Thread不迁移。
- **验证项：** 新绑定5项、fork/ACL/两真实项目新Thread → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；[x] CHANGELOG用户能力行同步。

### A2：公开边界与当前权限

- **改动内容：** 递归拒绝binding/引擎metadata，Thread/state/history/SSE投影；修原服务账号credential遗漏。
- **代码位置：** P API core/runtime_contract.py、application/thread_access.py、adapters/langgraph/sdk_client.py；Runtime runtime/auth.py。
- **预期结果：** 撤权后新Run/读取403、provider0；客户端不能自签scope。
- **验证项：** 真实Thread/Protocol/Run/state/patch矩阵、SSE/history、两种撤权与91项鉴权回归 → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；[x] CHANGELOG用户能力行同步。

### R1：公共MCP loader

- **改动内容：** Dear生产loader迁公共、纯配置独立；discovery前scope核对、同名集合、只读/allowlist/错误/取消保留。
- **代码位置：** P apps/runtime-service/src/runtime_service/tools/mcp.py:load_mcp_tools() / runtime/mcp_config.py；旧调用者及测试。
- **预期结果：** 每Thread只取授权连接，已有MCP配置须补scope。
- **验证项：** 原HTTPecho/只读/冲突/断网、错scope零discovery、官方Adapter → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；[x] CHANGELOG用户能力行同步。

### R2：安全来源与F04

- **改动内容：** 官方interceptor先校验/裁剪；更小预算缩完整字段、同步content/artifact。
- **代码位置：** P Runtime tools/knowledge.py:project_knowledge_result()/fit_knowledge_message()；middlewares/filesystem.py。
- **预期结果：** 无raw metadata，错误不变no_hit，极小预算合法JSON失败。
- **验证项：** 恶意/错类型/大结果/取消、官方HTTPfixture、F04组合 → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；[x] CHANGELOG用户能力行同步。

### R3：两主图与门禁

- **改动内容：** Dear/Showcase显式接线，catalog/defaults/实际列表一致，资料只作数据。
- **代码位置：** P Runtime两图 agent.py/prompts.py；runtime/capabilities.py。
- **预期结果：** schema/offload/未绑定/deny/Plan不联网，子图不自动获权。
- **验证项：** 12项组合根（强制非法call拒绝）、Plan/子图回归、四条真实Worker → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；[x] CHANGELOG用户能力行同步。

### L1：资源登记与迁移

- **改动内容：** 两份无DDL双head merge；知识MCP/Embedding纳入worktree登记与所属进程启停。
- **代码位置：** P两服务merge revision；scripts/local-stack.sh / local_stack_worktree.py / local_stack_processes.py / scripts/tests/test_local_stack_knowledge.py。
- **预期结果：** 独立本机PG/Redis/local，不抢他环境端口、不停他进程。
- **验证项：** 真实隔离PG upgrade、4项登记/冲突/归属测试、bash语法、真实knowledge-restart/持久性及command故障清理2场景 → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；[x] CHANGELOG用户能力行同步。

### F1A：前端交接（本轮）

- **改动内容：** 4份真实Worker和6份官方Adapter受控HTTPfixture、步骤/验收/转发话术。
- **代码位置：** fixtures/ / frontend-handoff.md / frontend-message.md。
- **预期结果：** 同事按实际契约复用共享UI。
- **验证项：** 样本来源、content/artifact一致、无服务端配置/Key/path、实际接口位置 → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；CHANGELOG此文档任务跳过。

### V1A：本机非前端文本链验收

- **改动内容：** 隔离/撤权/停用/Stop/fork/重启/历史、无答案/注入、性能/发布回退。
- **代码位置：** P tests/e2e/test_knowledge_platform.py；K tests；verification.md与私有证据。
- **预期结果：** 所有本机可做关键链有证据；不把旧基线/缺环境说全绿。
- **验证项：** K24项、API59项、Runtime74项、四条真实模型链+7项关键场景、30题合成质量、持久性/回退 → 通过；限定范围和证据见verification。
- **状态：** [x] 完成2026-10-11，详见implementation/01-knowledge-mcp.md。
- **合规检查：** [x] 实现/产物完成；[x] 验证已执行；[x] tasks同步；[x] CONTEXT/FEATURES按专项同步；[x] CHANGELOG用户能力行同步。

## 剩余任务与具体请求

### V1B：真实PDF/Office与业务语料质量门禁

- **状态：** [ ] blocked，仅B02代表性业务题集部分未完成；PDF/Office通用解析检索于2026-10-13由承接专项完成。
- **需求：** 兼容环境frozen安装documents，真实文本PDF离线入库/发布/检索；代表性10–20份业务资料与至少30题标注问答（含无答案/恶意指令），核对召回、引用、答案依据和性能。
- **B01已解除：** Intel macOS/Python3.13锁定Torch2.11缺wheel的原记录保留；2026-10-13改用已授权Ubuntu独立1024库完成PDF/Office/图片真实解析检索，见[验证](../20261013-knowledge-documents-platform/verification.md)。未降锁/Python、未使用Docker。
- **B02证据/替代：** 当前3份合成md（另有版本样本），20/20有答案命中不能代替业务质量；已做真实无答案不编造与注入样本检查。
- **需要用户提供（业务质量阶段）：** 代表性资料路径、标注问题/预期来源；兼容Ubuntu环境已具备，不再重复请求。条件到位后继续业务质量门禁。

### F1B：同事前端实施与浏览器验收

- **状态：** [ ] 同事接续，本轮明确排除前端开发。
- **需求：** 先以fixture验共享组件，必要时最小适配；F01–F10浏览器、多主题/三视口/历史/撤权。
- **交付：** 必要diff或“无需代码”证据、测试/Thread/Run/截图关联。

## 收口判定

16项本轮可执行任务已完成。V1B是真实Block，F1B已有交接；专项不标全栈done、不做草案毕业、不声明合并/生产门禁通过。全仓既有失败另列verification，不顺手重构其他业务。
