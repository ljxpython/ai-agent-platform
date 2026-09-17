# 文件级改动清单与实施顺序

## 目标、范围与状态

把 01—03 的方案落实到代码位置。下表路径均相对仓库根目录；“新增/修改”表示计划，不表示文件已经实现。

用户已同意方案。本轮补充文件级设计，不实现前端，也不新增服务、数据库表或对象存储。第一阶段先交付 Runtime + Platform API，前端最后由前端开发者对接；Terminal 属于第二阶段。

实施更新：Runtime/Platform API 后端项已实现，YAML 跨服务下载已通过。Service 合并为 `thread_workspace`，Ports/Upstream 使用 `workspace_json/workspace_file` 复用鉴权；另新增 `workspace/html_preview.py`。格式测试合并在 `test_workspace_browser.py`，未另建 test_artifact_formats.py。前端项未实施，实际契约见 [05](05-frontend-handoff.md)。

第二阶段更新：Terminal 后端已实施，具体代码与验证见 [06](06-terminal-backend.md)；前端新增文件按 [05](05-frontend-handoff.md) 的 Terminal 表执行。下面“第一阶段不改脚本、不显示 Terminal”的约束仅针对文件阶段，Terminal 阶段已增加 local-stack 开关和前端接入设计。

## 1. Runtime：存储、读取与发布

| 操作 | 代码位置 | 具体职责与改动 |
| --- | --- | --- |
| 新增 | `apps/runtime-service/src/runtime_service/workspace/browser.py` | `WorkspaceBrowser.list_directory/read_file`：实时读取单层目录、普通文件内容；虚拟路径检查、目录分页、类型/大小限制。目录枚举和读取使用文件描述符及禁止跟随符号链接的方式，不执行 Shell 命令。只读，不提供编辑/删除。 |
| 新增 | `apps/runtime-service/src/runtime_service/workspace/schemas.py` | 定义 `WorkspaceEntry`、目录分页响应和 artifact 列表响应等 Pydantic 模型；沿用 `mime_type/size_bytes`，统一 `preview_kind`。HTTP 层引用这些模型，不各写一份 Runtime DTO。 |
| 修改 | `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py` | 继续负责 `ArtifactWorkspace.publish/read`，增加 `list_artifacts`；统一发布和读取扩展名表。发布源允许 `work/generated/charts`，发布目标仍是 `outputs/<sha256>.<ext>`。列表扫描已发布文件，不新增数据库索引；读取继续校验摘要。 |
| 修改 | `apps/runtime-service/src/runtime_service/workspace/documents.py` | 复用已有 UTF-8、JSON、PDF、ZIP、Office 校验；补齐发布所需的校验分派，避免未知文档错误地走纯文本解码。上传与发布的许可范围分开处理。 |
| 修改 | `apps/runtime-service/src/runtime_service/workspace/file_refs.py` | 复核当前格式修复造成的上传 MIME 扩展；不能仅为支持 artifact 发布就顺带开放上传类型。沿用 `FileRef` 和已有大小上限。 |
| 修改 | `apps/runtime-service/src/runtime_service/workspace/media.py` | 保留 PPTX 校验，PNG/JPEG/WebP 复用图片解码校验，补齐 `.jpeg` 和扩展名与真实类型一致性验证。 |
| 复用，必要时小幅提取公共方法 | `apps/runtime-service/src/runtime_service/tools/images.py` | 复用 `ImageWorkspace` 的安全描述符 IO、普通文件检查、读取上限及 `image_type`；目录枚举需要的安全目录打开能力从这里复用，不另造字符串拼接式路径防护。 |
| 复用，不改目录规则 | `apps/runtime-service/src/runtime_service/workspace/scoped.py` | `resolve_thread_workspace` 是 tenant/project/thread/graph 到宿主目录的唯一映射；local 和 Docker 文件浏览读取同一个线程工作区。 |

最小实现不新增 `artifacts/` 目录，不给每个文件建立数据库记录。artifact 列表当前只能可靠提供哈希文件名；原始名称、发布时刻和来源消息不伪造，后续确有展示需求时再增加持久化元数据。

## 2. Runtime：HTTP 与工具装配

| 操作 | 代码位置 | 具体职责与改动 |
| --- | --- | --- |
| 新增 | `apps/runtime-service/src/runtime_service/http/workspace.py` | 注册线程工作区 tree/content/preview 与 artifact 列表内部接口；调用 `WorkspaceBrowser`/`ArtifactWorkspace`，不在路由内复制文件 IO。 |
| 修改 | `apps/runtime-service/src/runtime_service/http/documents.py` | 复用/提取现有 `_auth` 的 delegation、thread scope、workspace 解析逻辑供新路由调用；保留旧 uploads/outputs 下载接口，补齐新 MIME 安全响应。 |
| 修改 | `apps/runtime-service/src/runtime_service/webapp.py` | 注册 workspace router；不新增独立 Web 应用。 |
| 新增共享入口 | `apps/runtime-service/src/runtime_service/tools/artifacts.py` | 将现有 `build_artifact_tool` 的实现迁至公共工具目录，DearFlow 和 Showcase 共用。保留 `present_artifacts(file_path)` 参数和结构化返回兼容性。 |
| 修改为兼容导出 | `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/artifacts.py` | 从公共工具模块导出 `build_artifact_tool`，避免现有调用与测试突然失效；不保留两套发布实现。 |
| 修改 | `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` | 调整公共工具 import；维持原有工具权限、审批与返回行为。 |
| 修改 | `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py` | 将公共 `present_artifacts` 装入工具集合，并接入现有权限/HITL 策略；root 必须来自当前线程上下文。 |
| 修改 | `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/prompts.py` | 明确普通文件留在工作区、正式交付调用发布工具；使用工具返回引用，不臆造下载地址。 |
| 按调用链需要修改 | `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/subagents.py` | 核对生成结果返回主 Agent 的路径；仅当子任务需要自行发布时接入同一工具，不默认给所有子 Agent 增加写工具。 |
| 修改 | `apps/runtime-service/src/runtime_service/services/dearflow_agent/capabilities.py` | 此处才是 `graph_capabilities/tool_permissions` 当前定义位置。为 Showcase 声明 artifact 能力，MIME 从实际发布表派生，补充工作区浏览能力声明；能力声明不替代权限检查。 |
| 复用 | `apps/runtime-service/src/runtime_service/runtime/capabilities.py` | 当前是上述能力函数的导出入口，无须为本需求重构注册体系。 |

第一阶段复用 `workspace-file-read` delegation operation。只有实现时确需新增 operation，才同步修改 Runtime `auth/platform.py`、`runtime/auth.py` 及平台 `core/security/tokens.py` 的白名单；不能只改一端。

工具结果继续使用现有结构化返回与 ToolMessage 传输，不在本期强制新增 `artifact.published` SSE 类型或切换 `content_and_artifact`。前端识别发布工具完成后刷新列表，运行终态再刷新一次，避免遗漏子 Agent 产物。

## 3. Platform API：沿用网关分层

| 操作 | 代码位置 | 具体职责与改动 |
| --- | --- | --- |
| 修改 | `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` | 添加公开 tree/content/preview/artifacts 路由；更新 `_operation` 分类，保持鉴权、审计和错误映射；设置下载与预览安全头。 |
| 修改 | `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | 增加 `list_thread_workspace/read_thread_workspace/preview_thread_workspace/list_thread_artifacts`；先 `_load_thread(..., write=False)` 校验访问和 graph，再签发 delegation，不能直接透传客户端指定的 scope。 |
| 修改 | `apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py` | 在 `RuntimeGatewayUpstreamProtocol` 补齐对应方法；不新增另一套 gateway interface。 |
| 修改 | `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py` | 将上述调用映射到 Runtime 内部路径，复用现有 JSON 与文件 transport。 |
| 修改 | `apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py` | 同步文件 MIME 白名单及 `application/octet-stream` 下载策略，保留响应大小、状态码和资源释放校验。当前 YAML/PNG 发布后下载会被旧白名单拒绝，这里是必须修复的一环。 |

两服务不互相 import 对方 Python 模块；Runtime 负责判型，平台维护显式运输白名单并通过契约测试校验一致性，不为几张表引入新共享包。

### 路由落点

| 用途 | Platform API 公开路径 | Runtime 内部路径 |
| --- | --- | --- |
| 单层目录 | `GET /api/langgraph/threads/{id}/workspace/tree?path=/workspace` | `GET /internal/threads/{id}/workspace/tree` |
| 原文件下载 | `GET /api/langgraph/threads/{id}/workspace/content?path=...` | `GET /internal/threads/{id}/workspace/content` |
| 有界预览 | `GET /api/langgraph/threads/{id}/workspace/preview?path=...` | `GET /internal/threads/{id}/workspace/preview` |
| 发布列表 | `GET /api/langgraph/threads/{id}/artifacts` | `GET /internal/threads/{id}/artifacts` |
| 已有上传/产物下载（兼容保留） | `GET /api/langgraph/threads/{id}/files/content?path=...` | `GET /internal/threads/{id}/files/content` |

artifact 使用返回的 `path` 读取，不新增 `{artifact_id}/content`：现有 artifact_id 是纯内容摘要，同内容不同扩展名不能靠摘要唯一选出文件。选中项和去重键使用 `path`。

## 4. Platform Web：仅设计，后续开发

以下文件本轮不新增、不修改，由前端接入时实施。

| 操作 | 代码位置 | 接入职责 |
| --- | --- | --- |
| 新增 | `apps/platform-web/src/services/threads/workspace.service.ts` | DTO、目录/列表/预览 API；沿用现有请求客户端、鉴权和 `x-project-id`。 |
| 复用/修改 | `apps/platform-web/src/services/threads/files.service.ts` | 复用 `getThreadFileBlob` 和现有下载方式；普通文件下载调用新 workspace content；清理 object URL。 |
| 新增 | `apps/platform-web/src/composables/useThreadWorkspace.ts` | thread/project 绑定的加载、分页、选中、失效刷新；切换线程取消旧请求，避免旧响应覆盖新线程状态。 |
| 新增 | `apps/platform-web/src/components/workspace/WorkspacePanel.vue` | Files/Artifacts 两个页签、选中项和树/预览布局；不预留不可用 Terminal 页签。 |
| 新增 | `apps/platform-web/src/components/workspace/WorkspaceTree.vue` | 按需展开单层目录、分页与局部错误；第一期不承诺全工作区搜索或本轮 diff。 |
| 新增 | `apps/platform-web/src/components/workspace/WorkspacePreview.vue` | 根据服务端 `preview_kind` 显示文本、Markdown、图片、HTML 或下载卡片；复用已有渲染器。 |
| 新增 | `apps/platform-web/src/components/workspace/SandboxedHtmlFrame.vue` | Vue iframe 包装：无 `allow-same-origin`，只加载后端受限预览文档；CSP 随预览文档生效，不能只依赖 Blob HTTP 响应头。 |
| 修改 | `apps/platform-web/src/modules/chat/components/ChatSession.vue` | 挂载共享面板，传入 thread/project，监听工具结果或运行终态刷新。 |
| 修改 | `apps/platform-web/src/modules/chat/components/ChatArtifactPanel.vue` | 已有 artifact 卡片改为选中工作区对应 path，不维护第二套列表数据源。 |
| 修改 | `apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue` | 复用同一工作区面板，不为 Dear Agent 复制实现。 |
| 修改 | `apps/platform-web/src/modules/dear-agent/pages/DearAgentArtifactsPage.vue` | 改用后端 artifact 列表；刷新后仍可通过 path 恢复选中。 |
| 复用 | `apps/platform-web/src/modules/chat/components/ThreadFile.vue`、`apps/platform-web/src/modules/chat/components/ThreadImage.vue` | 保留已有消息附件展示；按接口能力复用，不假设普通文件可直接走原图片专用接口。 |

Open SWE 的 `OutputIframe/SandboxedHtmlFrame/TerminalPanel` 是 React 参考实现，不是本仓库已有组件；其 `DiffFilesView` 展示 Git 变更，不能直接当完整工作区文件树 API。

## 5. 测试放在哪里、何时执行

| 功能块 | 测试代码位置 | 必须覆盖 |
| --- | --- | --- |
| Runtime 工作区（新增） | `apps/runtime-service/tests/test_workspace_browser.py`、`apps/runtime-service/tests/test_workspace_http.py` | 单层目录、分页、大小限制、文件消失、路径穿越、符号链接/替换竞争、跨线程 scope、普通文件与 artifact 读取、HTML 预览策略。 |
| 发布格式（新增/扩展） | 新增 `apps/runtime-service/tests/test_artifact_formats.py`；扩展 `apps/runtime-service/tests/services/dearflow_agent/test_files.py` | YAML 回归、格式矩阵、图片类型不匹配、摘要一致性、重发幂等、未知二进制不发布。 |
| 工具接入（扩展） | `apps/runtime-service/tests/services/showcase_demo/test_agent.py`、`apps/runtime-service/tests/services/dearflow_agent/test_agent.py` | 两个 Agent 使用同一发布工具，权限/审批兼容、线程 root 正确。 |
| 平台工作区（新增） | `apps/platform-api/tests/test_runtime_gateway_workspace.py` | scope/delegation、列表/内容/预览代理、错误映射和安全头。 |
| 运输兼容（扩展） | `apps/platform-api/tests/test_runtime_gateway_files.py`、`apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py`、`apps/platform-api/tests/test_runtime_gateway_http_matrix.py` | 新格式不再被 MIME 白名单误拒绝；旧上传/下载不回归；公开路由覆盖。 |
| 前端（后续新增） | `apps/platform-web/src/services/threads/workspace.service.spec.ts`、`apps/platform-web/src/composables/useThreadWorkspace.spec.ts`、`apps/platform-web/src/components/workspace/WorkspacePreview.spec.ts` | 请求契约、切线程竞态、刷新恢复、预览分派；浏览器 E2E 沿用前端现有测试目录，接入时确定具体用例文件。 |

按三个完整功能块验收：① Runtime 存储/发布/HTTP；② Platform API 及真实两服务 HTTP 联调；③ 前端后续浏览器验证。两服务联调至少完成“写入 YAML → 发布 → 平台列表 → 下载并核对摘要”和“普通 HTML → 平台预览文档”；mock transport 通过不等于真实联调通过。文档修订只检查链接和一致性，不重跑全量测试。

## 6. 不需要改动的位置

- `apps/interaction-data-service/`：本期不引入结果域数据模型或产物表。
- `scripts/local-stack.sh` 与 Showcase `backend.py`：已有 local/Docker 切换继续沿用，文件浏览不再执行一遍 Shell，也不新增第三种 backend。
- 不新增对象存储、异步扫描任务、刷新 POST API 或独立 artifact 事件总线。

## 任务与验证状态

- [x] 对照实际代码补齐文件落点、路由映射、复用边界及测试位置。
- [x] Runtime 完整功能块实施与验证。
- [x] Platform API 实施、前后兼容及两服务联调。
- [ ] 前端后续实施与浏览器验收（本次只交付接入设计）。

本文件是实施清单，不是实现完成证明；各专题继续记录实际完成情况。
