# Agent 通用文档读取能力补齐 - 整体方案

## 背景

同事提出的 F10 来自 DeerFlow：上传 Office 文档后生成 Markdown，再将 Markdown 注入 Agent。源码核对表明本仓已经有线程上传、FileRef v1、PDF/文本/CSV/ZIP `parse_document`、有界输出、工具错误码、沙箱数据分析和共用 Chat 上传链路。重复建设完整 ingestion 会引入第二份文件事实源。

真正的缺口是：DOCX/PPTX 仍被上传白名单拒绝；现有 `DocumentToolsMiddleware` 每轮列出线程全部上传文件，没有本次消息边界和条数预算；解析结果对 Office 没有统一、可引用的定位字段。方案只补这几个缺口，保持原始文件按需解析。

2026-10-10 用户批准方案并授权完成全部非前端实施。已冻结 `python-docx==1.2.0`、既有 `python-pptx==1.0.2` 和下述读取契约；运行证据见 `verification.md`，前端由同事按 `frontend-handoff.md` 接续。

当前整体状态 `partial`：Runtime/API和本轮非前端专项验收 `done`；前端Task 3.1/3.2与浏览器验收待同事完成。两个后端完整门禁已执行，范围外基线失败/本机超时见验证记录，未宣称全仓全绿或生产发布。

## 目标与非目标

### 目标

1. 让授权的 Showcase/DearFlow 普通运行主 Agent 能按需读取 DOCX/PPTX 的文本结构，并返回安全、有限、可引用的结果；使用文本层读取，不要求模型原生文件能力。
2. 复用消息附件引用，不增加第二份上下文副本，也不把正文或全部历史附件放进每轮 Prompt。
3. 保持原有 PDF/文本/CSV/ZIP/Excel 行为、FileRef v1、上传路径、ACL、Delegation scope、错误 Envelope 和前端上传顺序不变。
4. 让 Platform Web 能区分上传成功、读取成功、截断、扫描/OCR 不可读和解析失败，并将实现边界交给同事。
5. 用离线恶意样本、真实 Runtime Docker、API 网关和最短三服务链路证明安全与回归。

### 非目标

- 不新增 MarkItDown、上传转换任务表、派生 `.md` FileRef、对象存储、OCR 服务、解析缓存或通用文档预览页。
- 不支持旧 `.doc/.ppt`、PDF OCR、复杂版面还原、Office 图片中文字识别、公式计算、Excel Markdown 替代数据分析。
- 不为 Plan Mode、researcher 子 Agent 或 MCP 增加额外 Office 工具授权。
- 不更改前端的 FileRef 上传接口；前端只做展示和 accept 扩展。

## 分层职责与链路

### 前端：交互与状态投影（本期交同事）

`ChatComposer → useChatAttachments → useSessionAttachmentUpload → Platform API file PUT → Runtime FileRef → message extras.runtime_file → Run → ToolResult`

- 接受列表增加 `.docx/.pptx` 和严格 MIME 映射，仍计算 SHA-256、原始二进制上传、消息只放引用。
- 附件卡片显示“已上传”，不要在上传成功时宣称“已解析为 Markdown”。
- `parse_document` 结果展示 `format`、`pages/sections`、`read_range`、`matched_*`、`next_read`、`truncated`、`warnings`；未知字段安全忽略。Office 首版只提供原文下载和读取结果，不提供浏览器 Office 原生预览。
- 上传错误、解析错误、扫描文档 warning 必须留在当前消息，不清空正文或自动重试 Run。

### Platform API：控制面网关与契约边界

Platform API 继续负责 Thread/Project ACL、Delegation 和二进制透传：

- 扩展 `RuntimeGatewayService.upload_thread_file` 的允许 MIME 与响应校验；不在 API 读取 Office 内容，不执行 MarkItDown，不创建转换文件。
- 扩展 SDK/响应内容类型白名单中的 DOCX/PPTX；未知上游类型保持 `runtime_invalid_file_response`。
- 原始文件读写仍走 `workspace-file-upload/read` 最小 scope，审计不记录正文、Base64 或解析全文。
- 若错误机器码新增，登记 `error-catalog.md`，保持 415/422/413 的精确映射。

涉及位置（实施时核对当前符号）：

- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` → `RuntimeGatewayService.upload_thread_file()` / `read_thread_file()`。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` → 文件 PUT/GET 路由现有契约，不新增路由。
- `apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py` → `upload_file()` / `read_file()` 内容类型白名单。
- `apps/platform-api/tests/test_runtime_gateway_files.py` → DOCX/PPTX 成功、拒绝和上游响应边界。

### Runtime Service：文件验证、解析和 Agent 装配

#### 1. 原始文件验证

扩展 `apps/runtime-service/src/runtime_service/workspace/file_refs.py` 的 `MIME_EXT`：

- `application/vnd.openxmlformats-officedocument.wordprocessingml.document` → `docx`。
- `application/vnd.openxmlformats-officedocument.presentationml.presentation` → `pptx`。

`DocumentWorkspace.put()` 仍用内容哈希命名、20 MiB 大小限制、原子写入和 FileRef v1。`validate_document()` 新增 Office 结构验证：DOCX 必须有 `[Content_Types].xml/word/document.xml`，PPTX 必须有 `[Content_Types].xml/ppt/presentation.xml` 及有效 slide 关系；拒绝 VBA、macro-enabled ContentType、OLE/加密包装、XML DTD/entity、缺失引用和危险外部关系。外部 hyperlink 只读取显示文本、丢弃 target，不访问网络；其他外部关系（模板/图片/OLE 等）首版拒绝。这一取舍须人审并以样本证明。

复用 `read_zip()` 的 ZIP 路径/符号链接/重复条目/加密标记/膨胀校验。当前上限为 256 条目、20 MiB 展开总量、单成员 2 MiB、100 倍压缩比；首版保持，不借 Office 放宽。解析 XML 用已有 `defusedxml`；拒绝错误用当前 `invalid_document/invalid_presentation`，不暴露内部 member 路径或异常原文。输入验证不复用 `media.validate_media()` 的图片型成果/最多20页规则，该规则仍独立保留。

#### 2. 公共 `parse_document`

在 `apps/runtime-service/src/runtime_service/tools/documents.py:build_document_tools()` 的同一工具中按 MIME 分支：

- DOCX：使用 `python-docx` 按正文顺序只读段落与表格；每个正文段落/表格算一个 1-based section，空段落仍保留序号，避免不同查询改变编号。使用库提供的 block 迭代 API，不手写 OOXML 转换引擎。header/footer、修订、图像、公式、嵌入文件和复杂合并单元格不保证还原，返回明确 warning，不伪造打印页码。
- PPTX：使用已有 `python-pptx` 只读 slide 的文本框/有限表格和真实 slide 序号；最多读取 20 个 slide/次，不用生成成果的20页上限拒绝整个输入文件。图片型 slide、图表、动画、母版和 notes 不保证读取，缺少文本明确 warning，不将图片生成能力当 OCR。
- 继续以 12,000 字符为返回正文总预算；对截断提供 `next_read` 参数，下一次读取同一 section/slide 的剩余文本。不能只加 `truncated=true` 却让正文后半段永远不可达。
- `query` 维持字面匹配、长度限制；正文预算继续有界，分页/section 范围互斥且可重放。
- Excel 保持当前返回 warning 并交给 `data-analysis` Skill；不把 workbook 变成模型上下文纯文本。
- PDF/文本/CSV/ZIP 的响应字段和现有错误码保持兼容；新字段只对新格式或可选输出出现。

新增依赖 `python-docx==1.2.0`，Python 3.13 已验证并写入 `uv.lock`；既有 `python-pptx==1.0.2`、openpyxl/xlrd/defusedxml/duckdb 继续复用。Workspace 镜像构建时安装同版本 parser，不在 Run 中 pip install；PDF 的既有 PyMuPDF 与截断行为保留。

##### 官方工具范式与本项目接线

2026-10-10 已通过官方 docs/reference MCP 核对：

- [工具定义与执行](https://docs.langchain.com/oss/python/langchain/tools)：简单工具首选 `@tool`，通过类型标注和 docstring 描述模型可见参数；返回字符串或结构化对象，由 Agent 工具执行链生成匹配的 ToolMessage。需要上下文时使用框架注入的 `ToolRuntime`，该参数不进入模型可见 schema。
- [Deep Agents 工具接入](https://docs.langchain.com/oss/python/deepagents/tools)和[自定义 middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)：工具可以传给 `create_deep_agent(tools=...)`，也可以通过 `AgentMiddleware.tools` 在创建 Agent 时注册。本项目已采用后者，继续复用；不同时在两处重复注册 `parse_document`。
- [ToolNode](https://docs.langchain.com/oss/python/langgraph/workflows-agents#toolnode)：自行编排 StateGraph 时显式使用工具节点，配合工具调用路由；当前两张 Agent 图已有完整执行链，本期不另建 ToolNode 或第二套模型/工具循环。
- [StructuredTool.from_function](https://reference.langchain.com/python/langchain-core/langchain_core/tools/structured/StructuredTool/from_function)：官方支持同一工具同时传入 `func` 和 `coroutine`。本期有保留旧同步调用、Office 使用异步隔离执行的实际需要，采用此接口；不另写 BaseTool 基类或通用工具适配器。

接线仍是 `create_deep_agent → 现有工具执行与middleware链 → parse_document → 固定Docker reader → ToolMessage → 模型回答`。生产 Office 分支由 Agent 的异步执行链 await coroutine，不在 model hook、上传处理或前端绕过工具执行链直接读正文。工具返回普通有界 dict，不新增图状态，因此不需要 Command/update 或手工拼接 ToolMessage；`next_read` 只是下一次工具参数建议，不启动自建递归循环。

Workspace、镜像和权限继续由已验证的服务端上下文/组合根绑定，不成为模型可填的工具参数；只有确有新的运行态读取需求时才使用 `ToolRuntime`，不为对齐示例重写已有闭包。错误、预算、审批和取消继续沿已有 middleware/RunControl 执行；控制流异常不吞掉。当前锁版本为 langgraph 1.2.11、langchain 1.3.17、langchain-core 1.6.0、deepagents 0.7.8，实施须验证这些实际版本，不能把线上文档查询当作运行通过。

#### 3. 固定读取进程与取消

新建 `apps/runtime-service/src/runtime_service/workspace/document_reader.py` 作为固定 Office 读取入口：只接受 Runtime 现有 `DocumentWorkspace/ArtifactWorkspace` 验证后的上传/不可变成果引用与有界读取选项，stdout 输出有限 JSON；不接受任意命令、URL、输出文件或插件。库调用放在这里，同步纯函数可独立单测；其中OOXML结构验证函数同时由 `validate_document()` 和隔离reader复用，不复制两份安全校验。该模块只依赖标准库、现有纯模块 `workspace/archives.py` 和parser库，不import HTTP/鉴权/graph/DocumentError（避免循环）；校验用固定ValueError机器码，由外层转DocumentError。入口核对源bytes/hash再读库，防止校验与执行之间文件被改。依赖lazy import，不在模块import时启动解析。

- `apps/runtime-service/deploy/Dockerfile.agent-workspace` 在构建阶段只 `COPY` 现有 `archives.py` 和新 `document_reader.py` 到 `/opt/runtime-reader/runtime_service/workspace/`，安装已冻结的parser依赖；不复制带初始化副作用的`__init__.py`或完整Runtime。namespace目录允许同一 `runtime_service.workspace.archives` import，无第二份ZIP校验。构建context明确为 `apps/runtime-service`。
- `parse_document` 的async分支用现有 `workspace/execution.py:execute_in_workspace()` 调用固定 `PYTHONPATH=/opt/runtime-reader python -m runtime_service.workspace.document_reader`，该import路径只在容器命令内设置，不改变宿主配置。command由固定入口和 `shlex.quote` 后的服务端参数构造，模型不能拼入shell。
- 沿用现有 `protected=True`：uploads/outputs 只读，work 为当前线程工作目录；parser 本身不写 work。Docker 使用现有资源与隔离限制，具体含义见下表；单次解析命令初始30秒硬预算，Spike 可建议调整，但不能超过现有60秒接口上限。
- parser 数据异常返回已知输入码；资源超限/非法 JSON/输出被截断返回固定工具失败。Docker 不可用或清理未确认仍传播现有 `RuntimeWorkspaceError`；控制流取消/interrupt 不降级为普通工具成功。
- 复用 `run_control/resources.py` 的登记和清理，不新建 parser 队列/任务表。单次只有一个 parser 进程，底层 Workspace 未准备、镜像缺包或源文件 hash 改变时明确失败。
- 新 Office 分支必须走异步 handler，避免同步工具在后台线程里 `asyncio.run` 丢失取消控制。优先使用官方 StructuredTool 的 `func/coroutine` 双实现，既有同步 PDF/文本/测试入口保留；Office 的 `.invoke()` 返回明确“不支持同步 Office 读取”，只有 `.ainvoke()` 启动隔离进程。若当前锁版本无法按此装配，先在 Task 0.2 固化失败和所需最小调整，不能退回宿主直接解析。
- 两个组合根分别传入自己的既有 workspace image：DearFlow 使用 `RUNTIME_WORKSPACE_IMAGE`，Showcase 使用 `RUNTIME_SHOWCASE_IMAGE`。公共 factory/middleware 仅新增 keyword-only `execution_image` 参数，现有仅传 root 的调用保持 PDF/文本行为；未配置可用 parser 镜像的 Showcase 不宣传 Office 可读。
- 即使 `RUNTIME_BACKEND=local`，新 Office 读取也要求受限 Docker，不新增宿主 Office 回退。local 只用于既有可信开发流程；前端遇到解析不可用保留原文下载，不伪称通用读取成功。

##### Docker 资源限制的具体含义

限制来自 `workspace/execution.py:docker_workspace_args()` / `execute_in_workspace()`，约束的是每次执行创建的解析容器。目的在于让恶意或异常 Office 文件的解析消耗有边界；LangGraph 负责工具调度，不规定 Docker 或解析库。

| 现有设置 | 含义 |
| --- | --- |
| `--memory=256m` | 单容器内存额度 256 MiB；资源不足会导致执行失败，不能直接套用为整个平台内存上限 |
| `--cpus=1` | 单容器 CPU 时间配额约等于一个核，不是将进程固定绑定在某个核 |
| `--pids-limit=64` | 限制容器任务数，包括进程/线程，防止无界创建 |
| `/tmp` tmpfs 16 MiB | 限制临时目录容量；临时文件也消耗内存，不将其当作额外免费内存 |
| `fsize=8388608` | 单个写出文件最多 8 MiB；这是解析过程写文件的限制，不是上传 20 MiB 限制 |
| 默认命令超时 30 秒；可传 1-60 秒 | 到期终止命令；容器启动、结果收集和清理还有执行器的有界等待，不代表整个 Agent Run 只能运行30秒 |
| `MAX_OUTPUT=128 KiB` | 返回的 stdout/stderr 最多 128 KiB；正文另遵循12,000字符预算。reader结果被截断或不是合法JSON就报失败 |
| `--network=none`、只读root、只读uploads/outputs、降权 | 限制网络和写入权限，属于执行隔离措施，不是资源额度 |

这些是已有执行器的初始值，不是已验证的 Office 生产容量。Phase 0 要用正常/最大/恶意样本测量内存、耗时、失败行为和取消回收；不足时依据实测提出最小调整。每容器限额也不等于总并发容量：多个并行工具/Run 会启动多个容器，必须核对已有 Worker/执行并发策略并完成并发测量。本期不先新建调度平台或无界重试。

#### 4. 现有 Middleware 的最小调整

调整 `apps/runtime-service/src/runtime_service/middlewares/documents.py:DocumentToolsMiddleware`：

- 删除每次模型调用的全目录扫描/系统索引：当前 text block 已包含文件名和虚拟路径，优先直接使用现有消息引用，不重复生成一份提示。
- Task 0.3 核对引用的消息投影。只有某个已证明的执行入口丢失当前引用时才补 request-local 的 HumanMessage 文本副本，最多10条/4,000字符；绝不根据宿主目录猜“本次文件”，也不将文件名/正文提升为 SystemMessage。无 `system_message` 的情况也不能默默丢掉必要引用。
- 不读取正文、不自动转换、不写 checkpoint；正文仍由 `parse_document` 按需读取。
- 主图和子图沿用各自既有工具闭包；不把 Office 读取工具动态塞给 researcher/Plan 子图。若现有 message shape 无法可靠区分本次附件，先做契约 Spike，不使用“猜最后一条 message”作为权限依据。
- 删除扫描后无需另加文件索引缓存、生命周期 state 或新工具。必须验证后续工具轮、历史恢复和摘要后文件来源仍能找回；若出现真实丢失则修共享输入/摘要保留逻辑，不重新注入全部目录。

#### 5. Agent 组合根与能力声明

- `services/dearflow_agent/agent.py`、`services/demo/showcase_demo/agent.py` 继续显式装配公共 middleware 和 `parse_document`，只新增格式能力，不新建 Agent 循环。
- `runtime/capabilities.py`、DearFlow capabilities 与已有前端 graph 能力判断保持 `parse_document` 这个工具名；没有现成格式 capability schema 时不发明格式开关/新 Context 字段。格式支持写在工具描述、测试和功能总览；尚未配好 parser 镜像的图只保证上传与原文下载。
- `PlanModeMiddleware` 的 readonly 工具列表本期不默认加入 `parse_document`；若产品要求规划阶段阅读附件，另立权限决策。

## 冻结契约

### 输入

仍为消息 text block：

```json
{
  "type": "text",
  "text": "[文档附件] 方案.docx\n/workspace/uploads/<sha256>.docx",
  "extras": { "runtime_file": { "version": 1, "path": "/workspace/uploads/<sha256>.docx", "file_name": "方案.docx", "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "size_bytes": 1234, "sha256": "<64 hex>" } }
}
```

`FileRef v1` 六字段不增加 `markdown_*`、`parse_status` 或宿主路径。客户端不能自行伪造“已解析”状态。

### `parse_document` 输出

保留当前公共字段：`version=1`、`file`、`format`、`text`、`chunks`、`truncated`、`warnings`；PDF 继续有 `pages/read_range/matched_pages`。

新增一个可选 tool 参数 `read_options`：DOCX 用 `section_start/section_end`，Office 长片段续读用 `char_offset`；字段为严格整数且非bool，section范围1-based、单次最多20个，char_offset非负且小于选定片段长度。PPTX 沿用 `page_start/page_end` 的slide范围；DOCX拒绝页码参数，非Office拒绝非空read_options。原四参数调用无需修改。

新格式只增：

| 格式 | 定位字段 | 可接受 warning |
| --- | --- | --- |
| DOCX | `sections` 为总section数；`read_range/matched_sections` 为section编号，`chunks[].section/char_offset` | `docx_body_only`、`docx_table_structure_flattened`、`external_relationship_ignored`、`document_no_text`、`no_query_match_in_selected_range` |
| PPTX | `pages` 为总slide数；`read_range/matched_pages` 为slide编号，`chunks[].page/char_offset` | `presentation_text_only`、`slide_N_no_text_layer_ocr_required`、`external_relationship_ignored`、`document_no_text`、`no_query_match_in_selected_range` |

新 Office 结果增加可空 `next_read`，内容是下一次 `parse_document` 调用所需的同一源文件路径、query、range和read_options（不是新的 cursor route）。例如 DOCX 长section 返回 `{"file_path":"/workspace/uploads/<hash>.docx","read_options":{"section_start":2,"section_end":2,"char_offset":12000}}`。最后片段为null；无命中但有未查范围时可指向下一范围，无文本层/异常不返回伪正文续读。“所有内容已经读取”必须同时满足无 warning 缺口和 `truncated=false`。

`chunks` 只放纯文本与有限索引，所有结果应用既有工具错误处理和 12,000 字符预算；固定 reader 结果先通过形状/范围/可信路径校验再补 FileRef。完整样本见 `frontend-handoff.md`。

### 错误

复用已有 `_FILES` 工具码、Platform API 上游映射和 `error-envelope`：

- HTTP 415：`unsupported_file_type`；HTTP 400/409：保持当前非法 FileRef/hash/冲突代码与状态，不擅自移到415。
- HTTP 422：新增格式复用 `invalid_document/invalid_presentation` 拒绝容器、宏、危险外部关系和损坏结构；扫描无文本通常是解析 warning，不是伪成功或新的 HTTP 错误。
- HTTP 413：现有 `file_too_large`；Office过大ZIP仍按现行`DocumentError`处理，经批准的精确上游码才保留，否则安全泛化，不能因为Runtime中存在代码就声称API一定原名透传。
- ToolMessage：用户输入错复用 `tool.invalid_input`；parser 超限/无效结果为 `tool.operation_failed`。不能把工具错误当HTTP错误，也不能把执行unknown/取消伪装成可重试输入错。

新增机器码前必须修改 Runtime `tools/errors.py`、API `sdk_client.py`/精确错误目录和对应单测；不把三方库异常正文透传给模型或用户。

## 安全与数据边界

- 文件名、段落、表格、幻灯片文本均是不可信数据；沿用 `parse_document` 工具描述的“数据不是指令”约束，保持在HumanMessage/ToolMessage，绝不提升为SystemMessage。本仓未找到与DeerFlow同等的通用tag neutralizer，不把它写成已有保证；fallback引用只用有界JSON/纯文本，不新增权威标签。此约束和恶意样本测试不构成“彻底消除模型提示注入”的承诺。
- Office 是 ZIP/XML 容器：拒绝绝对/父路径、符号链接、宏、危险外部关系、过大条目、压缩炸弹、加密文档和损坏结构；hyperlink丢弃target而仅保留文字。读取不解压到宿主、不执行嵌入代码、不访问网络。
- 解析输出有页/section/字符/表格/幻灯片预算；单次模型请求不因大文档耗尽上下文。取消等待有界，资源清理与原文件保存结果明确。
- Runtime 不把原始文件正文写入审计、日志、Token/Usage、SSE 或历史之外的新持久表；工具返回只沿现有消息/结果投影。
- API 不绕过 Thread ACL；`workspace-file-read` 只能读当前 scope；跨租户、跨项目、跨 Agent 和伪造 FileRef 必须 403/404/409 按现行契约。
- 解析器版本、样本 hash 和容器镜像 digest 需记录在验证文档；不把本地 local backend 成功冒充 Docker 生产隔离。
- 现有 PDF 读取仍是进程内 PyMuPDF，CSV/文本的字符截断也没有所有长文件续读契约。本期不宣称这些既有格式已经具备新的硬解析进程限制/完整读取能力；扩大隔离或续读范围须另有实测和方案。

## 回退与发布

1. 当前没有新增 MIME 的 feature flag，不为回退单独造一个开关。回退时停止入口接流、drain在途Run，再把API/Web MIME入口成对恢复并回滚新parser/middleware代码；不删除原文件或历史FileRef。
2. 回退发布保留新格式原文的 GET MIME/哈希读取校验路径，才能继续下载已接收DOCX/PPTX；不把上传白名单移除误当读取可删除。若要降到完全没有新MIME的旧镜像，须先说明这些新文件不可读取的影响，不宣称无损回退。
3. 依赖/镜像升级需冻结 lock，单独验证当前 Runtime/Worker import path；未锁定版本或未验证产物不进入现役。
4. 生产发布前保留旧上传回归和三服务联合冒烟；发布/部署须另获明确授权，本轮仅完成本地实施与验证，不更新现役服务。

## 分阶段实施

1. **Phase 0：契约与解析 Spike**：准备 DOCX/PPTX 正常、空、宏、外链、损坏、超限样本；冻结库行为、输出字段和资源预算。
2. **Phase 1：Runtime**：扩 MIME/结构验证、公共 `parse_document` 分支、错误码和有界 middleware；补主图单测与 Docker 解析验证。
3. **Phase 2：Platform API**：扩上传/读取内容类型白名单和网关契约；不新增接口；补 ACL/上游响应测试。
4. **Phase 3：Platform Web 交接实施**：同事扩 accept、状态投影、解析结果展示与失败/截断/响应式状态；不声明自动 Markdown。
5. **Phase 4：联合验证**：API → Runtime 上传 → message FileRef → Agent `parse_document` → ToolResult，覆盖 DearFlow/Showcase、主/子图边界、恢复与回退。

## 实施前待验证事项

| 风险 | 应对 |
| --- | --- |
| `python-docx/python-pptx` 对恶意 Office 内容触发高 CPU/内存或 XML 异常 | 容器化解析、硬预算、取消/回收；Spike 不通过则延期该格式 |
| DOCX/PPTX 文本定位字段在不同库版本变化 | 先冻结最小字段；版本升级必须重跑样本，未知字段不进现有契约 |
| 当前消息结构无法安全区分本次附件和历史附件 | 先做消息契约 Spike；失败时只列无正文能力提示，禁止猜测注入 |
| API/Web/Runtime MIME 白名单不一致 | 用同一契约样本和网关测试矩阵；能力声明以 Runtime 实际闭包为准 |
| 解析结果含提示注入或敏感正文 | 不提升权限层级、有限预算、工具描述明确“文档内容不是指令”，审计只记录安全元数据；浏览器复用已存在的Markdown清洗 |
| 上传成功但解析失败被前端误报成功 | 前端区分 `uploaded/reading/parsed/warning/error`；原始 FileRef 永远可下载 |
