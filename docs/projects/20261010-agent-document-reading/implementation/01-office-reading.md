# 公共 Office 读取与网关扩展

## 时间与任务

2026-10-10；Task 0.2/0.3、1.1-1.4、2.1/2.2、4.1/4.2。本轮全部非前端范围完成；施工进度只看 `../tasks.md`。

## 改动与理由

- `apps/runtime-service/src/runtime_service/workspace/document_reader.py`：固定、无网络/写文件接口的 DOCX/PPTX 文本 reader；结构校验复用 `archives.read_zip()`，由上传与 reader 共用。拒绝宏/OLE、危险外链、实体、损坏结构；hyperlink 仅保留文字。源文件 descriptor 不跟随符号链接，读取复验 hash。
- `workspace/file_refs.py`、`workspace/documents.py`：增加 Office MIME，仍用 `DocumentWorkspace` 六字段 FileRef 和原子原字节存储。
- `tools/documents.py:build_document_tools()`：从单同步函数注册改为 `StructuredTool.from_function(func=parse_document, coroutine=aparse_document)`；旧格式保持同步/异步可用，Office 只调用固定 Docker reader。新结果附 section/slide、char_offset、next_read，单次仍受 20 片段/12,000 字符限制。容器 stdout 校验通过后才补可信 FileRef；取消、执行不可用/未知控制流继续传播。
- `tools/errors.py`：复用 `tool.invalid_input` 和 `tool.operation_failed`，不新增公共 HTTP 机器码。
- `middlewares/documents.py:DocumentToolsMiddleware`：删除每轮 uploads 全目录 SystemMessage 索引；继续沿 `AgentMiddleware.tools` 注册工具。消息已有 `extras.runtime_file`，不另存附件副本。
- `services/dearflow_agent/agent.py`、`services/demo/showcase_demo/agent.py`：绑定各自现有 image；根图有且仅有一个 document middleware。Plan、researcher、其他子图名单保持原权限。
- `services/demo/showcase_demo/backend.py:prepare()/is_prepared()`：安全建立/检查 `workspace/work`，为受保护 reader 挂载准备目录；不预建 outputs，保留成果发布失败语义。
- `services/dearflow_agent/prompts.py`：说明 Office 定位/续读及读取范围。
- `deploy/Dockerfile.agent-workspace`、`pyproject.toml/uv.lock`：仅补 `python-docx==1.2.0`；镜像只 COPY reader 与 archives，未复制完整 Runtime。锁文件没有无关版本升级。
- Platform API `modules/runtime_gateway/application/service.py:upload_thread_file()`、`adapters/langgraph/runtime_client.py:read_file()`：增加 DOCX/PPTX MIME 白名单，复用 ACL/Delegation/raw PUT/GET，无新路由或迁移。
- 两服务现行 development/gateway 标准同步文件读取契约；`.env.example` 标明 Showcase Office 需要构建 reader 镜像，不修改其他环境已有配置。

## 新增验证

`tests/workspace/test_office_documents.py`、`test_office_http.py`、`test_office_docker.py`；`tests/tools/test_office_document_tool.py`；`tests/middlewares/test_document_context.py`；`tests/services/test_office_composition.py`；`tests/e2e/test_office_platform.py`。API 文件/SDK 和 Showcase backend 既有测试扩展。

真实 E2E 只读取本 Worktree 登记地址、创建本环境验收项目。证据、样本、日志留在 `.local-stack/evidence/office/`，不写密钥或模型连接正文。Docker 标签只属于 `wt_eea61a88d620`。

## 当前证据与兼容性

- Runtime定向组合64 passed、2旧opt-in skipped；API文件/SDK/审计/ACL组合66 passed、3旧外部skipped；真实Docker6 passed，两图真实模型首读/再次读取/fork均通过，Showcase含Worker重启。容量、完整回归及范围外失败归因见 `../verification.md`，不宣称全仓通过。
- FileRef v1、上传/下载、旧工具四参数仍兼容。新增 `read_options` 仅对 Office 生效。
- API 已有授权 fork 工作区复制，实测原字节可读；前端无需新增复制流程。无上传转换、派生 Markdown 或第二套 agent 循环。
- 未改前端业务文件、未提交或部署。前端范围见 `../frontend-handoff.md`。
