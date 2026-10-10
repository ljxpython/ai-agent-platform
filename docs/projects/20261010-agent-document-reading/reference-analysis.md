# F10 源码对照与辩证分析

> 2026-10-10 调研基线快照。“已有”只表示调研时找到源码与接线；后续用户批准的实际实施与运行证据见 `implementation/`、`verification.md`，不要把本表当最新功能状态。

## 取样边界

参考仓是用户指定的本机工作副本，通常位于 `~/PyCharmMiscProject/research/deer-flow` 与 `~/PyCharmMiscProject/research/open-swe`。下文参考路径均相对各自仓根，不把个人宿主路径写入运行契约。

| 仓库 | 读取时 HEAD | 注意 |
| --- | --- | --- |
| ai-agent-platform | `2f08c5462571cd0244a7181e5d0d1388341b79c4` | 开始调研时工作树干净 |
| deer-flow | `cc664451f03140b376611f329ae400c313530bdb` | 本文四个核心上传/转换/middleware 文件没有工作树修改；不代表整个仓库干净 |
| open-swe | `ad417d64d91cc349d63d832c7b643637dc1774cf` | `agent/utils/multimodal.py` 已修改、`agent/sandboxes/state.py` 已暂存新增、`pyproject.toml` 未合并；不能将工作副本视为上游发行版 |

Open-SWE 本次取样文件 SHA256：`agent/utils/multimodal.py` 为 `0f98bcefc92e1fc73c365a810cf7f8aa2e2ead1be5392dd5ad84905570a7053a`；`agent/sandboxes/state.py` 为 `ad5e51cd10e7ada98637c60eee3fd02223368fdd4c50ddc532574ee9252e1756`。

## DeerFlow 实际设计

| 层与文件 | 源码行为 | 可借鉴与限制 |
| --- | --- | --- |
| Gateway `backend/app/gateway/routers/uploads.py:upload_files` | multipart 批量上传；调用共享 ingestion；默认每批 10 文件、单文件 50 MiB、总量 100 MiB，配置可覆盖 | 上传入口与处理生命周期分开；限额不是本平台必须沿用的标准 |
| 同文件 `_auto_convert_documents_enabled` | `uploads.auto_convert_documents` 缺失时为 false，需要显式开启宿主转换 | “用户上传后必自动转”不符合当前默认行为 |
| `backend/app/gateway/upload_ingestion.py:ThreadUploadIngestionService` | staging、名称占位、无覆盖提交、可选转换、沙箱同步、清理和 lease 释放；转换成功增加 markdown_* 字段，普通转换失败可保留原文件 | 借鉴原始输入独立于派生结果、取消清理、避免半成品；本平台已有 hash 命名和原子写入，不复制名称治理系统 |
| Harness `backend/packages/harness/deerflow/utils/file_conversion.py` | `CONVERTIBLE_EXTENSIONS` 为 PDF/PPT/PPTX/XLS/XLSX/DOC/DOCX；PDF 可先 pymupdf4llm 再 MarkItDown，其他经 MarkItDown；返回伴随 .md 或 None | 不是全格式自动转换；HTML/CSV 没在该自动转换集合中。库可识别格式不等于上传流程已支持 |
| Harness `backend/packages/harness/deerflow/agents/middlewares/uploads_middleware.py` | 读取本次 HumanMessage 的 `additional_kwargs.files`；最多列 10 个文件；附路径、目录或少量预览；历史文件按需发现 | **没有每轮注入全部 .md 正文**。当前消息优先、目录限长值得借鉴；不能照搬其消息字段和路径 |
| Harness `tools/builtins/list_uploaded_files_tool.py` | 提供历史上传查询入口 | 本平台根图已有 `ls/glob`；先复用现有发现工具，不新增同义工具 |
| Web `frontend/src/core/uploads/api.ts`、`hooks.ts`、`core/threads/hooks.ts` | 上传请求、limits/list/delete 状态、提交时携带 files 元数据 | 浏览器负责交互和引用传递，不执行 Office 转换 |

额外限制：转换 helper 的 `asyncio.to_thread` 只把大文件解析移出事件循环，不能杀掉运行中的线程，也不是 CPU/内存或宿主文件隔离。当前 helper 中小于等于 1 MiB 的转换直接同步执行；文件大小也不能保证复杂文档解析便宜。不能将这段代码直接视为本平台生产隔离方案。

## 本仓已有什么

路径均相对本仓根。下表不仅检查文件存在，还核对其消费者。

| 能力 | 文件/符号 | 实际覆盖 |
| --- | --- | --- |
| 上传与下载网关 | `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py:upload_thread_file/read_thread_file`；`application/service.py:RuntimeGatewayService.upload_thread_file` | raw PUT、项目/Thread ACL、受信 `workspace-file-upload/read` 委托、20 MiB 单文件限制 |
| Runtime 文件入口 | `apps/runtime-service/src/runtime_service/http/documents.py:upload_thread_file/read_thread_file` | 流式大小校验、作用域绑定、后台文件写入；不做全文转换 |
| 不可变原始文件 | `apps/runtime-service/src/runtime_service/workspace/documents.py:DocumentWorkspace`；`workspace/file_refs.py:FileRef/validate_file_ref` | sha256 文件名、内容哈希、精确六字段 v1、descriptor IO、临时文件和无覆盖提交 |
| 公共文档工具 | `apps/runtime-service/src/runtime_service/tools/documents.py:build_document_tools.parse_document` | PDF 文本层、UTF-8 文本/Markdown/HTML/CSS/JS、JSON、CSV、静态 ZIP；PDF 每次最多 20 页，正文最多 12,000 字符；扫描页有 OCR warning |
| Excel 输入与分析 | 同工具 Excel 分支；`services/dearflow_agent/skills/data-analysis/scripts/analyze.py` | parse_document 只返回 `use_data_analysis_skill_in_sandbox`，不返回 Excel 内容；DearFlow 经 execute/Skill 用 DuckDB/openpyxl/xlrd 处理。这是已有不同方案，不是转换缺失就不会分析 |
| 附件提示与工具注册 | `apps/runtime-service/src/runtime_service/middlewares/documents.py:DocumentToolsMiddleware` | 每次 awrap_model_call 列出 uploads 全部普通文件和大小；不注入正文，但也不限制数量，不区分本次/历史附件 |
| 真实组合根 | `services/dearflow_agent/agent.py:get_agent` 与 `services/demo/showcase_demo/agent.py:get_agent` | 两个根图装配同一公共 middleware；DearFlow researcher 不具备 parse_document；Plan Mode 只读名单也没有该工具 |
| 共用前端链路 | `apps/platform-web/src/modules/chat/composables/useSessionAttachmentUpload.ts`；`src/services/threads/files.service.ts`；`src/utils/chat-content.ts` | 计算 hash、先上传后提交、消息用 `extras.runtime_file`；文档不转 Base64、不发全文；Dear 页面委托共用 Chat |
| 现有结果展示 | `apps/platform-web/src/modules/chat/components/ToolResult.vue` | parse_document 专用展示、页码、截断与 warning；非 PDF 定位需要扩展 |
| 已安装 Office/安全依赖 | `apps/runtime-service/pyproject.toml`、`deploy/Dockerfile.agent-workspace` | openpyxl/xlrd/defusedxml/python-pptx 已有；没有 markitdown/python-docx。python-pptx 当前用于生成，不是上传读取接线 |

上传输入的 DOCX/PPTX 同时被 Runtime `MIME_EXT`、API `allowed_mimes` 和 Web 的 MIME/扩展集合排除。PPTX 仅存在于发布成果 MIME/校验；不能把输出能力倒算成输入能力。

现有 Web 检查每条消息最多 8 个附件、总量 30 MiB，文档 20 MiB、图片 5 MiB。后端单文件端点的 20 MiB 是服务端硬限制；本轮未找到等价的消息级 8 个/30 MiB 后端附件配额，不能说这些前端校验已经构成服务端总量保护。

## Open-SWE 与重复建设判断

本机 Open-SWE 的相关取样显示：`agent/utils/multimodal.py` 负责外部图片 URL 读取、鉴权、防 SSRF、图片大小和 vision block；`agent/sandboxes/state.py` 处理沙箱 Backend。对 Agent/UI 的格式与转换调用搜索未发现与本文 F10 等价的通用文档转换管线，但这不是对其他分支或全部集成的“完全没有”证明。

**本次防重复的依据是本平台现有的公共文件、工具、middleware 和共用 Chat，而不是“借鉴过 Open-SWE，所以一切都已覆盖”。** 功能上已有 PDF/文本读取，不必为了统一到另一种技术实现重新转换；Word/PPT 输入缺口则不能因已经借鉴过某仓库而忽略。

原迁移项目已经记录 [A09](../20260913-dearflow-agent/11-20260928-capability-reassessment.md) 与 [T07](../20260913-dearflow-agent/12-completion-plan.md) 的有界附件发现问题；本专项只细化该切片，不维护第二份旧项目完成率。

## 对同事五项建议的取舍

| 建议 | 判断 | 推荐处理 |
| --- | --- | --- |
| 引入 `markitdown[all,xlsx]>=0.0.1a2` | 不采纳为默认前提 | PDF、Excel、PPTX 的相关库已有；全量 extras 和浮动预发布下限不等于必要依赖。DOCX 使用专用库，版本由样本 Spike 冻结 |
| 在 runtime 上传处理层调用转换 | 责任层方向正确，时机不合适 | API 管授权，Runtime 管读取；上传只校验并保存，普通 Run 需要时调用既有工具，避免延迟和失败绑到上传 |
| 转换 .md 存到线程 uploads | 本期不做 | FileRef 哈希属于原始字节；新文本需独立哈希、绑定、清理和状态，还会重复进入文件索引。尚无必须持久转换产物的用例 |
| 实现 UploadsMiddleware，每次注入内容 | 不做第二个 middleware，不注入全文 | 改现有 DocumentToolsMiddleware 为本次消息引用优先、有界、无正文；内容由工具按需返回 |
| 前端显示“已解析为 Markdown” | 修正状态语义 | PUT 成功只代表已上传；真实 parse_document 成功才表示读到了当前片段；扫描/截断/不支持须区分 |

## 值得做与暂时不做

优先收益是把已有 Agent 能力做实：控制动态附件索引、保留权限交集和 PDF 引用；在同一个公共工具上补现代 DOCX/PPTX 的有限读取。它不需要新业务属性、外部服务、转换任务表或新的 Run 状态。

全文缓存/伴随 Markdown 的可能价值是重复读取大型长文和保留结构。只有后续测量显示重复解析成本明显、或者用户确实需要下载转换文本，才评审缓存/导出；不能为当前简单缺口先建设全套 ingestion 生命周期。OCR、图像理解、表格计算和排版还原仍是分别验收的能力。

## API 依据与未验证项

已查询 `langchain-docs` 与 `langchain-reference` MCP，参考[自定义 middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)、[AgentMiddleware.awrap_model_call](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware/awrap_model_call)和 [StructuredTool.from_function](https://reference.langchain.com/python/langchain-core/langchain_core/tools/structured/StructuredTool/from_function)。官方接口允许覆盖模型请求、同一工具配置 `func/coroutine`；middleware 的先后顺序及异步 hook 不代表内部同步 IO 自动离开事件循环。

用户确认方案后再次通过官方 MCP 核对[工具定义与执行](https://docs.langchain.com/oss/python/langchain/tools)、[Deep Agents 工具](https://docs.langchain.com/oss/python/deepagents/tools)和 [ToolNode](https://docs.langchain.com/oss/python/langgraph/workflows-agents#toolnode)。简单工具首选 `@tool`；已有Agent通过tools参数或middleware.tools注册和执行，自编StateGraph才显式装配ToolNode。本仓已有 `DocumentToolsMiddleware.tools → create_deep_agent` 接线，继续复用。同一工具的同步/异步双实现有官方StructuredTool支持；Docker限额则是本仓应用层选择，不能写成LangGraph标准。详细决策和当前锁版本见 `plan.md`。

后续必须用本仓 frozen 版本验证 `request.messages/state`、`request.override`、工具 allowlist 过滤、动态 system 预算计算和取消传播。未运行参考仓，未安装 MarkItDown，未验证转换质量、性能、Docker 或真实模型；不能根据文档、库名或已存在测试源码报告通过。
