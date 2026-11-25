# 任务清单：平台助手按 Thread 检索运行与脱敏活动摘要

状态约定：待开始 / 进行中 / 已完成（done） / 部分完成（partial） / 等待条件（blocked） / 已暂缓（deferred）。

### Task 1：Platform API 契约扩展与 Thread 前缀/Run 列表查询

用户只提供 `thread_id` 或其前 8 位时，平台助手需要先安全解析目标会话并拿到 `run_id` 列表，才能衔接后续诊断和日志检索；同时保证多条命中可歧义提示、无权会话绝不泄露。

**状态：** 已完成（done）。
**完成标准：** `ReadRequest` 支持 `"thread_runs"` 与 `"thread_activity"`；完整 UUID 与 8–35 位短前缀解析、跨项目 ACL 过滤、Run 列表白名单投影及 `evidence.py` 撤权保护均实现并通过单元测试。
**涉及位置：**
- `apps/platform-api/src/platform_api/modules/platform_assistant/contracts.py`
- `apps/platform-api/src/platform_api/modules/platform_assistant/service.py`
- `apps/platform-api/src/platform_api/modules/platform_assistant/diagnostics.py`
- `apps/platform-api/src/platform_api/modules/platform_assistant/evidence.py`

- [x] 在 `contracts.py` 扩展 `ReadRequest.operation` 支持 `"thread_runs"` 与 `"thread_activity"`
- [x] 实现受目标项目 ACL 约束的 Thread 前缀解析与 `thread_runs` 安全投影（含 `not_found` / `ambiguous` / `matched`）
- [x] 在 `service.py` 与 `evidence.py` 接入工具策略映射及历史撤权保护

**开发与验证进度：** 已实施完成。新增 `resolve_thread_target` 与 `summarize_runs`，覆盖完整 UUID、8–35 位短前缀唯一/多条/无权分支及跨项目成员撤权拦截；`tests/test_platform_assistant.py` 相关用例通过（详见 [verification.md](verification.md)）。
**下一步：** 无（本地开发与验证已完成；生产部署按用户窗口另行确认）。

---

### Task 2：Platform API 脱敏对话活动摘要投影

用户希望平台助手根据 `thread_id` 回答“之前几轮对话都干了什么”，需要服务端在不泄露出对话原文和工具参数/结果正文的前提下，投影出按轮次组织的结构化工具调用与状态摘要。

**状态：** 已完成（done）。
**完成标准：** `thread_activity` 操作可结合 `list_thread_runs` 与 `get_thread_state`（有界超时）生成结构化轮次活动摘要，严格剔除消息正文、工具入参和返回原文，并通过敏感字段屏蔽断言。
**涉及位置：**
- `apps/platform-api/src/platform_api/modules/platform_assistant/diagnostics.py`
- `apps/platform-api/src/platform_api/modules/platform_assistant/service.py`

- [x] 实现 `read_thread_activity` 状态读取与脱敏摘要投影（含 200 条消息上限及 `truncated` 标记）
- [x] 覆盖空状态、超时降级、多轮工具调用成功/失败状态关联及敏感文本不泄露校验

**开发与验证进度：** 已实施完成。在 `diagnostics.py` 抽取共享 `_interrupt_flags`，新增 `activity_summary` 与 `read_thread_activity_state`，仅输出轮次号、`ai_messages` 计数、`tool_name`（经 `identifier` 过滤）、`status` 与中断布尔标识，消息正文与工具参数/输出全量剥离，并通过隐私字段零泄露断言（详见 [verification.md](verification.md)）。
**下一步：** 无。

---

### Task 3：Runtime Service 新工具、校验与提示词接入

Runtime 侧平台助手需要注册 `list_thread_runs` 与 `read_thread_activity` 工具，并教会模型在只拿到 `thread_id`（或前 8 位）时主动串联查询，同时对非法入参抛出 `ToolException` 避免崩溃。

**状态：** 已完成（done）。
**完成标准：** `platform_assistant` 的 `TOOL_NAMES`、`tools.py` 与 `SYSTEM_PROMPT` 同步完成更新，参数校验仅放行合法 36 位 UUID 或 8–35 位十六进制前缀，异常入参抛 `ToolException`；Runtime 单元测试与图执行测试通过。
**涉及位置：**
- `apps/runtime-service/src/runtime_service/services/platform_assistant/capabilities.py`
- `apps/runtime-service/src/runtime_service/services/platform_assistant/tools.py`
- `apps/runtime-service/src/runtime_service/services/platform_assistant/prompts.py`

- [x] 在 `capabilities.py` 与 `tools.py` 新增 `list_thread_runs` 与 `read_thread_activity` 工具及参数校验
- [x] 更新 `prompts.py` 的排障指引与脱敏回答约束

**开发与验证进度：** 已实施完成。新增 `_thread_locator`、`list_thread_runs`、`read_thread_activity` 并同步注册 `TOOL_NAMES` 与 `SYSTEM_PROMPT`；`tests/test_platform_assistant.py` 含真实 `create_platform_agent` 图工具调用验证全通过（详见 [verification.md](verification.md)）。
**下一步：** 无。

---

### Task 4：跨服务契约联调验证与文档收口

完成跨 `platform-api` 与 `runtime-service` 的自动化测试与最短联动契约验证，确保文档链接校验通过，并同步更新项目与仓库状态快照。

**状态：** 已完成（done）。
**完成标准：** Platform API 助手测试、Runtime Service 助手测试、跨模块 HMAC 内部回调联调测试及 `python scripts/check_docs.py` 全部通过；任务与项目状态更新至最新事实。
**涉及位置：**
- `apps/platform-api/tests/test_platform_assistant.py`
- `apps/runtime-service/tests/test_platform_assistant.py`
- `docs/projects/20261125-platform-assistant-thread-lookup/verification.md`
- `docs/CONTEXT.md`、`docs/FEATURES.md`、`docs/CHANGELOG.md`

- [x] 补齐 `platform-api` 与 `runtime-service` 单元及跨服务回调契约测试
- [x] 执行验证并记录完整证据到 `verification.md`
- [x] 同步 `docs/CONTEXT.md`、`docs/FEATURES.md`、`docs/CHANGELOG.md` 并通过 `scripts/check_docs.py`

**开发与验证进度：** 已完成本地全部单元回归、跨进程真实 TCP HTTP HMAC 签名回调联调以及仓库文档一致性校验（详见 [verification.md](verification.md)）；生产环境部署待用户确认。
**下一步：** 由用户确认是否打包部署至 `sshmy1`。
