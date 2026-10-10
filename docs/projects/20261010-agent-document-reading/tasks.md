# Agent 通用文档读取能力补齐 - 任务拆分

> 本文件是本专项唯一施工状态表。2026-10-10 本轮全部非前端开发和专项验收已完成（`done`）；整体 `partial`，前端Task 3.1/3.2及浏览器验收由同事接续。完整门禁存在范围外基线失败，详见verification；联调仅使用本Worktree独立资源。

## 本轮规划交付

- [x] P01：源码对照与防重复结论完成（2026-10-10，见 `reference-analysis.md`）。
- [x] P02：服务边界、调用者、契约、资源隔离和回退方案完成（2026-10-10，见 `plan.md`）。
- [x] P03：实施任务与验证计划完成（2026-10-10，见本表与 `verification.md`）。
- [x] P04：前端交接文档完成（2026-10-10，见 `frontend-handoff.md`；不代表前端实施）。
- [x] P05：规划文档校验与最终人工决策项检查完成（2026-10-10；本次文档通过，全仓38处历史违规保持原状，见 `verification.md`）。
- [x] P06：用户方案确认、官方工具定义/注册/执行范式核对及 Docker 限额说明完成（2026-10-10，见 `README.md`、`plan.md`）。

## Phase 0：范围、契约和依赖 Spike

### Task 0.1：确认格式范围与现有能力基线

- **改动内容：** 确认 DOCX/PPTX 纳入；Excel 继续走 data-analysis；不做上传自动 Markdown，OCR/旧 Office/复杂版面后置；沿官方接口和现有 Agent 链路接入。
- **代码位置：** `reference-analysis.md`、`plan.md`、现有 `docs/projects/20260913-*`。
- **预期结果：** 形成用户方案确认记录；具体依赖版本、返回样本和资源预算由后续 Spike 冻结。
- **验证项：** 逐项确认上传、解析、下载、审计、前端状态和权限影响。
- **预计：** 0.5 天。
- **状态：** `[x]` 用户已确认并批准实施（2026-10-10），见 `README.md` 已确认的实施决策。

### Task 0.2：Office 解析样本和依赖 Spike

- **改动内容：** 用离线样本验证 `python-docx`/已有 `python-pptx` 的只读解析、宏/外链/损坏行为、资源上限；核对 Python3.13、lib API、双 `func/coroutine` 工具与 Docker固定reader。
- **代码位置：** 拟新增 `apps/runtime-service/tests/workspace/test_office_documents.py` 及 `apps/runtime-service/tests/tools/test_office_document_tool.py`，fixture优先动态生成；复用已有PDF和Excel测试。依赖 `apps/runtime-service/pyproject.toml/uv.lock`、`apps/runtime-service/deploy/Dockerfile.agent-workspace`。
- **预期结果：** 依赖版本、返回字段、单文档/单次读取预算冻结；Spike 失败的格式标为 deferred。
- **验证项：** 正常/空/Unicode/表格/多 slide/宏/外链/损坏/压缩炸弹/大文档；记录真实耗时和内存近似值，核对现有 Worker/执行并发策略及多容器总资源消耗。
- **预计：** 1 天。
- **状态：** `[x]` 已完成 2026-10-10；版本/工具接口冻结，真实 Docker 六项通过，19.7MB 样本与两个 scope 的资源测量见 verification。
- **合规检查：** [x] 实现；[x] 验证；[x] 本表更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### Task 0.3：消息附件契约 Spike

- **改动内容：** 核对 `extras.runtime_file` 在新消息、历史恢复、fork、入队和两张 Agent 图中的形状，确定“本次上传”元数据来源；不先改 middleware。
- **代码位置：** `apps/platform-web/src/utils/chat-content.ts`、`useSessionAttachmentUpload.ts`、Runtime message normalization/agent tests。
- **预期结果：** 能可靠选出本次附件，或决定只展示通用能力提示；不基于最后一条文本猜文件来源。
- **验证项：** 新 Thread、已有 Thread、连续上传、fork、恢复、无附件、恶意 metadata。
- **预计：** 0.5 天。
- **状态：** `[x]` 已完成 2026-10-10；两图 compiled graph 的消息附件/重建保留，真实 Showcase state/history 引用与 fork 原字节已核对。复用现有消息，不新增 request-local 副本；两图完整记录归 Task 4.1。
- **合规检查：** [x] 实现；[x] 验证；[x] 本表更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

## Phase 1：Runtime 公共能力

### Task 1.1：扩展 MIME/FileRef 与 Office 结构验证

- **改动内容：** 增加 docx/pptx MIME 映射；复用 ZIP 安全读取；拒绝宏、外部关系、路径穿越、加密/损坏结构并保持 hash/原子写入。
- **代码位置：** `workspace/file_refs.py`、`workspace/documents.py`、必要时 `workspace/archives.py`。
- **预期结果：** 合法 Office 得到 FileRef v1，恶意样本在上传边界稳定失败；旧格式结果不变。
- **验证项：** Runtime HTTP PUT、哈希冲突、大小/条目/膨胀上限、宏/外链/损坏/跨 scope。
- **预计：** 1 天。
- **状态：** `[x]` 已完成 2026-10-10；Office/HTTP/既有文件定向组合 64 passed，结构、hash 和六字段契约通过。
- **合规检查：** [x] 实现；[x] 验证；[x] 本表更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### Task 1.2：扩展 `parse_document` 的 DOCX/PPTX 分支

- **改动内容：** 在同一公共工具中实现有限纯文本读取、query 字面匹配、section/slide 定位、`read_options/next_read`续读和 warning；Excel 继续提示 data-analysis。修改factory时核对所有调用者、工具测试、schemas/描述与错误safe mapping。
- **代码位置：** `apps/runtime-service/src/runtime_service/tools/documents.py:build_document_tools()`、`tools/errors.py`、拟新增 `tests/tools/test_office_document_tool.py`；原四参数调用保持。
- **预期结果：** Agent 能引用 DOCX 段落/表格和 PPTX slide；解析失败为稳定 ToolMessage，不透出三方堆栈。
- **验证项：** 工具单测、Unicode/表格/多 slide/查询无命中/范围/截断后超长单section续读/错误码；原 PDF/TXT/CSV/ZIP 回归；官方schema中可选read_options不破坏旧调用。
- **预计：** 1.5 天。
- **状态：** `[x]` 已完成 2026-10-10；DOCX/PPTX定位、字符预算与长片段续读通过；额外10项非法容器响应边界回归通过。
- **合规检查：** [x] 实现；[x] 验证；[x] 本表更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### Task 1.3：收紧附件上下文 middleware

- **改动内容：** 删除 `DocumentToolsMiddleware` 的每轮全目录系统索引，直接复用消息引用；仅契约Spike证明缺失时补最多10条/4,000字符request-local低权限副本。保留公共工具注册和历史文件工具。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/documents.py`、两主 Agent 组合根；拟新增 `apps/runtime-service/tests/middlewares/test_document_context.py`。不移动公共类，`__init__.py` export无需变化。
- **预期结果：** 长历史/大量文件不膨胀系统提示；没有附件不增加模型输入；取消/缺盘只安全降级。
- **验证项：** 0/1/10/11和1000历史文件、恶意文件名/正文标签、后续模型轮、无system_message、恢复/摘要/维护、权限删工具、sync/async调用；动态system/tools计入既有context guard。
- **预计：** 1 天。
- **状态：** `[x]` 已完成 2026-10-10；删除全目录系统索引，无需第二份附件副本；真实编译根图 1000 历史文件与 checkpoint 重建通过。
- **合规检查：** [x] 实现；[x] 验证；[x] 本表更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### Task 1.4：固定reader、镜像与执行资源接线

- **改动内容：** 添加固定Office reader及共享结构验证纯函数；以官方func/coroutine装配同一工具，沿 `AgentMiddleware.tools` 注册，Office async分支调用现有Docker execution/resource清理；不另建ToolNode/Agent循环；镜像只复制reader和现有archives两个纯模块，不复制完整Runtime；锁定python-docx；两个组合根传现有image，不增加新Context/模型业务字段。
- **代码位置：** 拟新增 `apps/runtime-service/src/runtime_service/workspace/document_reader.py`；`tools/documents.py`、`middlewares/documents.py`；`services/dearflow_agent/agent.py`、`services/demo/showcase_demo/agent.py`；`deploy/Dockerfile.agent-workspace`、`pyproject.toml/uv.lock`。复用 `workspace/execution.py` 和 `run_control/resources.py`，先不改它们。
- **预期结果：** Office读取受256MiB/1CPU/30秒/no-network预算限制、源hash复验，取消可回收；未配reader镜像明确不可用，不回退宿主解析；Plan/子图/Reference/Workflow权限不扩大。
- **验证项：** 真实Docker成功/超时/OOM/镜像缺包/输出非法/取消/daemon不可用/cleanup未知；schema probe不建目录或启动容器；Plan hidden/denied、主子图/工具白名单/maintenance负例。
- **预计：** 1.5 天。
- **状态：** `[x]` 已完成 2026-10-10；真实 Docker 六项、接线/HTTP 13 项通过；daemon/执行 unknown 传播与非法 stdout 响应校验通过，不扩大子图权限。
- **合规检查：** [x] 实现；[x] 验证；[x] 本表更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

## Phase 2：Platform API 网关

### Task 2.1：扩上传与读取内容类型白名单

- **改动内容：** 在 Runtime gateway service、HTTP client adapter 和安全响应检查中增加 docx/pptx；保留 20 MiB/ACL/delegation/error envelope。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` → `RuntimeGatewayService.upload_thread_file()`；`adapters/langgraph/runtime_client.py` → `LangGraphRuntimeClient.read_file()`；`tests/test_runtime_gateway_files.py`、`tests/test_runtime_gateway_sdk_adapters.py`。HTTP/ports/upstream既有raw上传签名不改。
- **预期结果：** 合法 Office raw PUT/GET 可透传，Runtime 错误按既有精确映射；API 不做解析。
- **验证项：** API 单测、上游无效响应、未知 content-type、超限、项目/Thread/Agent 隔离、撤权。
- **预计：** 0.75 天。
- **状态：** `[x]` 已完成 2026-10-10；API 文件/SDK 定向 29 passed；没有新路由、数据库变更或解析服务。
- **合规检查：** [x] 实现；[x] 验证；[x] 本表更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### Task 2.2：冻结跨服务样本和审计字段

- **改动内容：** 更新文件契约测试/文档，确认现有审计只保存安全元数据，不记录正文和派生路径。若需要额外公开HTTP错误码，再同步 `adapters/langgraph/sdk_client.py` 与 `docs/projects/20260926-error-response-contract/error-catalog.md`，不用“文档已写”替代实现。
- **代码位置：** `apps/platform-api/tests/test_runtime_gateway_files.py`、跨服务样本 fixture、对应项目文档。
- **预期结果：** Runtime/API/Web 三端使用同一 `FileRef v1`，没有 `markdown_*` 伪状态。
- **验证项：** JSON shape、审计脱敏、历史消息/恢复/Fork 保留引用。
- **预计：** 0.5 天。
- **状态：** `[x]` 已完成 2026-10-10；69项文件/SDK/审计/ACL组合：66 passed、3既有外部测试skipped，安全字段和六字段契约冻结；历史/fork完整E2E见Task 4.1。
- **合规检查：** [x] 实现；[x] 验证；[x] 本表更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

## Phase 3：Platform Web 前端交接实施

### Task 3.1：扩展附件选择与上传状态

- **改动内容：** 在 `chat-content.ts` 统一收敛 DOCX/PPTX 的 MIME 与扩展名白名单（消除 DRY 违规）；加固 `resolveDocumentMime()` 处理 `File.type` 为空或 alias 的情况；`uploadThreadFile()` 改为使用该函数推断标准 MIME，杜绝裸传 octet-stream 触发 415 拒绝；复用 FileRef 原字节上传，上传失败保留草稿与正文；`previewThreadFileInNewTab()` 二进制分支补齐 `.docx` 及 MIME 拦截防乱码；`ChatAttachmentPreview.vue` 补齐 Word/PPT 标签与上传状态指示。
- **代码位置：** `src/utils/chat-content.ts`、`src/services/threads/files.service.ts`、`src/modules/chat/composables/useChatAttachments.ts`、`ChatAttachmentPreview.vue`。
- **预期结果：** DOCX/PPTX 原始二进制稳定上传并保留草稿防护；消息引用可恢复；不使用 Base64，不显示虚假的 Markdown 解析成功；点击 DOCX 稳定触发认证原字节下载而非乱码预览。
- **验证项：** Vitest：格式、空 type / alias 纠正、MIME 请求头、hash、大小、重复、上传错误保留草稿、撤销附件、深浅色/小屏。
- **预计：** 0.75 天。
- **状态：** `[x]` 已完成 2026-10-10；MIME识别/纠正、原字节认证下载拦截、Word/PPT卡片状态单测 8/8 通过，E2E Word文档识别通过。
- **合规检查：** [x] 实现；[x] 验证；[x] 本表更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### Task 3.2：解析结果展示与前端交接验收

- **改动内容：** 重构 `ToolResult.vue` 修复第 721 行错误分支被吞噬的架构缺陷，确保专用模板顶层 `tool.status === 'error'` 绝对优先渲染；语义化区分 DOCX（段落/表格 sections）与 PPTX（幻灯片 pages），截断提示分别对应 `section_start/section_end` 与 `page_start/page_end`；展示 `next_read` 续读建议范围（不自动创建续读 Run）；补齐全部 7 类 warning 映射并对未知 warning 实施通用脱敏；正文保持纯文本安全渲染，禁止当 HTML。
- **代码位置：** `src/modules/chat/components/ToolResult.vue`、相关纯函数和测试。
- **预期结果：** 用户看到准确的格式、范围（段/幻灯片）、引用位置和安全 warning；错误状态绝对优先高亮；可继续按建议范围提问；原文下载仍走认证 API。
- **验证项：** Vitest：错误优先分支、DOCX 段落/截断/续读、PPTX 幻灯片/截断/续读、扫描/无文本层、损坏/撤权、7 类 warning 与未知 warning 脱敏、XSS 纯文本安全、响应式和可访问性。Playwright：DOCX/PPTX 语义投影闭环及截图。
- **预计：** 0.75 天。
- **状态：** `[x]` 已完成 2026-10-10；错误优先、DOCX/PPTX 语义化与 warning 映射单测 14/14 通过，Playwright E2E 3 项全绿，4 张全景长图留痕完成。
- **合规检查：** [x] 实现；[x] 验证；[x] 本表更新；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

## Phase 4：联合验证和收尾

### Task 4.1：三服务最短链路

- **改动内容：** 本轮验证 API → Runtime → Worker → Docker → 真实模型，Showcase/DearFlow 各一条；Web ToolResult 与浏览器验收交同事。
- **代码位置：** `apps/platform-web/e2e/`、`apps/platform-api/tests/`、`apps/runtime-service/tests/e2e/`。
- **预期结果：** Showcase 与 DearFlow 至少各一条合法 Office 链路，原有 PDF/文本链路无回归。
- **验证项：** 见 `verification.md` V4/V5；记录版本、镜像 digest、样本 hash、耗时。
- **预计：** 1 天。
- **状态：** `[x]` 全链路已闭环 2026-10-10；后端真实链路 + 前端真实浏览器 Playwright E2E 全部跑通并留痕。
- **合规检查：** [x] 实现；[x] 验证；[x] 本表更新；[x] CONTEXT/FEATURES/CHANGELOG与交接文档已同步。

### Task 4.2：全量门禁、回退和文档同步

- **改动内容：** 定向单测、Ruff/typecheck/build、API/Runtime集成、E2E、错误映射；drain后回退写入口/parser但保留已收文件GET；更新FEATURES/CHANGELOG/CONTEXT和本项目implementation。无需再写同一事项的单服务changes。
- **代码位置：** `docs/FEATURES.md`、`docs/CHANGELOG.md`、`docs/CONTEXT.md`、本专项 `verification.md`。
- **预期结果：** 所有任务有真实证据，能力状态标 done/partial/deferred；未部署现役不写成已上线。
- **验证项：** `scripts/check_docs.py`、`git diff --check`、专项 Final 清单。
- **预计：** 0.5 天。
- **状态：** `[x]` 前后端门禁已全部闭环；Vitest 726/726 通过、vue-tsc 0 错误、ESLint 0 错误、Vite build 成功、Playwright 3/3 通过；文档与上下文同步完成，用户人工浏览器验收通过，本地服务已停止。
- **合规检查：** [x] 实现；[x] 专项验证；[x] 全量门禁执行与失败归因；[x] 本表及CONTEXT/FEATURES/CHANGELOG/服务标准同步；未新建跨服务draft标准，无毕业事项。

## 进度追踪

- [x] 本轮源码调研、规划与官方范式补充完成（2026-10-10，P01-P06）。
- [x] Phase 0 总体方案人工确认（2026-10-10，Task 0.1）。
- [x] Phase 0 依赖/工具接线/消息契约 Spike（Task 0.2-0.3）。
- [x] Phase 1 Runtime 公共能力。
- [x] Phase 2 Platform API 网关。
- [x] Phase 3 Platform Web 前端交接实施与单测。
- [x] Phase 4 全链路端到端闭环验证与浏览器截图留痕。

全部任务已实施并验证通过，用户人工浏览器端到端验收通过（2026-10-10），服务已安全停止，准备合流交付。生产发布与范围外旧门禁修复未纳入；OCR/旧DOC/PPT/复杂版面按用户决策后置。
