# 工具调用容错任务拆分

> 实施进度唯一来源。2026-10-06 用户评审批准后开始实施；本轮推进所有非前端事项，前端开发和浏览器联合验收由同事负责。

## P0：本轮规划交付

- [x] P01：读取 CONTEXT、服务规范与相关经验；核对两边真实源码及锁定依赖。
- [x] P02：辨析同事方案，完成三层职责、错误分类、代码落点、实施/验证计划及前端交接。
- [x] P03：实际运行已有容错基线，11 passed / 14 deselected；见 verification.md。
- [x] P03b：锁定版本离线探针复现 stream `tool-error` 携带原异常；已补入 T06 与验证计划。
- [x] P04：已核对源码落点/任务覆盖；8 个本次文档检查通过，6 个专项文档的 15 个本地链接有效；git diff --check 通过；CONTEXT/FEATURES 已同步，只有文档变更。全仓 4 处既有文档问题另记 verification.md。

## G0：实施前人工评审

- [x] G0：批准错误边界与开发范围。
- **需确认内容：** 选择性容错而非全捕获；保留既有授权/中断/取消语义；未知程序异常与工作区基础故障继续传播；本期不新增生产自动重试；第一方 JSON 建议字段/2 KiB 上限；前端同事职责和完整联合验收。
- **代码位置：** 无；审核 plan.md 与 frontend-handoff.md。
- **预期结果：** 人工明确批准后才能开始 T01-T10 的代码/故障注入实施。
- **验证项：** 记录批准人、时间、范围、调整项；不得由 AI 填写“已批准”。
- **批准记录：** 2026-10-06，用户在本会话明确批准：“我已经评审完成，可以开始实施了,任务推进到只剩下前端的相关事项，除非遇到block的事项”。批准现有 plan.md 的范围与错误边界，无方案调整；本轮不执行前端代码、提交或生产发布。

## Phase 1：复现与共享错误出口

### T01：建立逐工具错误出口和失败基线

- [x] T01，Runtime，2026-10-06 完成。
- **改动内容：** 逐项记录第一方工具、MCP、文件系统、task 的错误来源、异常类型/code、是否被 native handler 处理、是否可能已执行、scope/安全语义和本期策略。优先复现实际缺口，保留已有行为证据。
- **代码位置：** 新增 `apps/runtime-service/tests/services/dearflow_agent/test_tool_errors.py`；复用 `test_agent.py`、`test_subagents.py`、`test_research.py` 的 graph/模型/ToolRuntime 模式。错误出口清单写入本专项后续 implementation 记录，不新建生产 Registry。
- **预期结果：** 明确哪些异常需要新策略，哪些已有 safe error/unknown/Command 应原样保留；取得主/子图未处理异常的失败证据。
- **验证项：** 至少覆盖普通执行异常、ToolException native 路径、MCP transport、未知错误与安全错误；证据附真实工具名和代码函数，禁止用虚构异常替代全部真实出口。
- **完成结果：** 核对全部真实出口，取得有效失败基线 `3 failed / 2 passed`，安全/未知错误传播既有项通过；详见 [implementation/01-error-outlets.md](implementation/01-error-outlets.md)。其余资源执行证据随 T05/T09 补齐。
- **合规检查：** [x] 基线测试和出口清单完成；[x] 基线真实执行；[x] 本任务状态更新。服务能力、FEATURES、CHANGELOG 在功能任务收口时统一更新。

### T02：共享分类与安全内容函数

- [x] T02，Runtime，2026-10-06 完成。
- **改动内容：** 新增小型纯函数与 native handler 适配，固定错误码/文案/恢复建议。显式排除 RuntimeErrorBase、控制流、未知异常和未归类 ToolException。工具名从受信 request/builder 注入。
- **代码位置：** 新增 `apps/runtime-service/src/runtime_service/tools/errors.py` → `tool_error_content()`、`on_tool_error()`、`handle_expected_tool_error()`、`tool_error_handler()`；新增 `apps/runtime-service/tests/tools/test_tool_errors.py`。
- **预期结果：** 官方组件与第一方 native handler 共用内容；未知错误返回 None/原异常，内容不含原 exception/request/URL/secret。
- **验证项：** sync/async 官方组件、name/id/status、稳定 JSON、内容上限、无敏感 canary；RuntimeAuthError/ResolutionError 不能因 ValueError 继承被放行；成功 ToolMessage/Command 不变。
- **完成结果：** 共享纯函数、native 适配与官方 sync/async graph 回归通过；安全、未知、控制流显式排除，内容有界且不拼异常原文。见 [实施记录](implementation/02-selective-error-handling.md)。
- **合规检查：** [x] 实现；[x] 定向验证；[x] 任务状态；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### T03：第一方 native 错误归一化

- [x] T03，Runtime，2026-10-07 完成。
- **改动内容：** 按 T01 清单将需要的 `handle_tool_error=True` 换为受信工具名绑定的共享 formatter；已结构化和多模态结果保留。区分证据写入基础故障、配置/权限故障与可修正业务失败，不能新增吞未知异常的 try/except。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/{search,research_http,github,arxiv_search,web_guidelines,media,deployment,memory,skills}.py` 的现有 builder/handler；`apps/runtime-service/src/runtime_service/tools/{documents,images,artifacts,chart}.py` 的已确认失败出口；`apps/runtime-service/src/runtime_service/services/demo/showcase_demo/tools.py:fetch_documentation`。
- **预期结果：** 输入/已知外部失败产生安全消息；native handler 不再绕开批准的分类；现有成功 artifact、媒体任务 unknown/ID、证据路径与调用签名保留。
- **验证项：** 对实际受影响工具的 `.invoke/.ainvoke` 以及 graph 调用分别断言；故障发生后下次模型请求确实包含错误 ToolMessage；未知提交不重复写入/计费，现有相关工具测试通过。
- **完成结果：** native handler 使用受信工具名绑定的共享 formatter，批准错误输出安全 JSON，成功 artifact/Command 和媒体 unknown 回执保留。扩大 Runtime 修正后回归 288 passed / 17 skipped（1550.26 秒），独立最新分类/观测/流回归 40 passed（52.55 秒）；研究工具/技能 56 passed / 3 skipped、HTTP 文件/根映射 25 passed、跨服务边界 1 passed。首次扩大失败及逐项修正保留在 [实施记录](implementation/03-isolated-verification.md)，skip 不计通过。
- **合规检查：** [x] 实现；[x] 定向与扩大回归；[x] 任务状态；[x] 服务文档与功能/变更记录同步。

## Phase 2：生产组合根与资源边界

### T04：主/子 Agent 显式装配

- [x] T04，Runtime，2026-10-06 完成。
- **改动内容：** DearFlow 和 Showcase 的局部 `middleware()` 增加官方 ToolErrorMiddleware；Reference 改用共享函数并保持现有重试。以真实 graph 验证 guards、ToolError、现有 Retry 的实际顺序，不把父 task 兜底当作子图内部容错。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/{dearflow_agent,reference_agent}/agent.py:get_agent()`；`apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py:get_agent()`；对应 `subagents/researcher.py:researcher()`、`subagents.py:build_subagents()` 仅在需要时调整传参。
- **预期结果：** 已知工具错误后主/子模型都能继续；授权/预算拒绝零工具执行；task 致命错误向外传播；故意失败 demo 保持其教学行为。
- **验证项：** 主 Agent、researcher、Showcase 子图、父 task 传播四组 graph 场景；并行成功/失败结果按 ID 和 namespace 配对；保留 Reference 的有界重试测试。
- **完成结果：** DearFlow/Showcase 13 项主子图、并行配对、父 task 致命传播、拒绝零执行和预算回归通过；Reference 11 项原有限重试/官方组件基线通过。见 [实施记录](implementation/02-selective-error-handling.md)。
- **合规检查：** [x] 实现；[x] 定向验证；[x] 任务状态；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### T05：MCP 和 workspace 故障边界

- [x] T05，Runtime，2026-10-06 完成。
- **改动内容：** 区分 MCP 构图失败、协议 error 结果、调用 transport/session 错误与 conversion/未知异常。核对 root/prepare/execute 失败是否按批准策略传播；只对真实复现的吞错缺口修改代码。
- **代码位置：** `services/dearflow_agent/tools/mcp.py:load_mcp_tools()`；`workspace/execution.py:execute_in_workspace()`；`services/dearflow_agent/workspace/backend.py:DearWorkspaceBackend.prepare()/aexecute()`；Showcase backend；必要时 `runtime/errors.py:RuntimeWorkspaceError`。这些路径均相对于 `apps/runtime-service/src/runtime_service/`。
- **预期结果：** 只读连接失败可反馈模型；发现/授权/转换故障不伪装恢复；workspace 不可用停止；单文件错误/非零退出不误判；不切换空工作区、不回退宿主执行。
- **验证项：** 本地受控 MCP server 的 isError/transport/multimodal；临时根目录/Docker 的故障注入；已开始的命令超时保留 unknown 或现有退出结果；没有自动重复副作用。ExceptionGroup 中含安全/控制流/未知异常时不能全组转业务错误。
- **完成结果：** 7 项真实 MCP/Docker 与资源故障验证通过，协议多模态保留；构图拒绝、混合组传播、根目录/CLI 致命故障、非零退出、超时副作用次数均已验。2026-10-07 追加可信根 EACCES/ENOSPC，2 passed / 6 deselected（5.44 秒）；发现写入可重建缺根后明确 create_root 初始化边界，最终 IO/HTTP/图片/文档/成果/终端组 55 passed / 2 skipped（57.81 秒）。媒体/研究/审批/重启组 42 passed / 2 skipped（474.26 秒），原 5 项重启本轮再次通过。不靠 Docker 命令退出码推断，见 [实施记录](implementation/03-isolated-verification.md)。
- **合规检查：** [x] 实现；[x] 定向验证；[x] 任务状态；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### T06：观测与控制流回归

- [x] T06，Runtime，2026-10-06 完成；2026-10-07 HTTP 控制流与回退联合证据已补齐。
- **改动内容：** 审查原 `on_tool_error` 与 error ToolMessage 的 `on_tool_end` 路径，需要时补安全统计；修复已复现的 `StreamToolCallHandler` 原异常流出口，优先用官方等价能力，否则在已有 patch 输出稳定 code/type；回归审批、澄清、取消、预算耗尽和日志失败。
- **代码位置：** `apps/runtime-service/src/runtime_service/observability/langfuse.py`；`apps/runtime-service/src/runtime_service/patches.py:_patch_stream_tool_call_handler()`；`tests/observability/test_graph_tracing.py`、`test_langfuse.py`；拟新增 `apps/runtime-service/tests/test_patches.py`；`tests/services/dearflow_agent/test_tool_errors.py`。
- **预期结果：** 可恢复 error 可查但不被误计为 Run 失败；ToolMessage 与 tool-error 流事件均不泄露原异常；未知错误仍可排查；审批/取消不变成红色工具失败；Exporter 故障不打断主流程。
- **验证项：** caplog/callback 含安全名称/code/现有 trace 标识，异常与转换结果不双计；实际 v3 stream 不带异常 canary，事件 call ID/namespace 保留；HITL approve/edit/reject、澄清和用户取消；重复错误触发原预算终止。
- **完成结果：** 流 patch、native/raised 单次计数、GraphBubbleUp 不记失败、取消和日志故障定向已通过；与主子 graph、审批/澄清一起执行的组合为 91 passed / 2 skipped。旧 live 图片/图表的 skip 不计通过；真实模型 smoke 另有 2 passed。见 [实施记录](implementation/02-selective-error-handling.md)。
- **合规检查：** [x] 实现；[x] 定向验证；[x] 任务状态；[x] 服务 README/knowledge、CONTEXT/FEATURES/CHANGELOG 已同步。

## Phase 3：后端验证与前端同事接入

### T07：API 消息保真与安全回归

- [x] T07，后端，2026-10-06 完成。
- **改动内容：** 在既有测试中覆盖标准 Run SSE、Protocol、state/history 的 error ToolMessage、tool_call_id/name/status、content、artifact 和子图 namespace。默认不增加网关业务代码；发现明确失败才修既有出口。
- **代码位置：** `apps/platform-api/tests/test_runtime_gateway_event_redaction.py`、`test_runtime_gateway_runtime_contract.py`、`test_runtime_gateway_sdk_adapters.py`；实际业务补充位于 `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py:redact_runtime_private_fields()`，HTTP/application 编排不变。
- **预期结果：** 可恢复工具错误不会被 API 改成 HTTP/Run 失败；致命 Run 错误保留终态；既有项目权限、幂等和安全输出规则不变。
- **验证项：** 通道保真；JSON 字符串中的敏感 canary 检查；Runtime 来源拒绝/未知提交安全出口；非错误成功结果不改写。
- **完成结果：** 网关回归 89 项，85 passed / 4 skipped，127.989 秒；两类 SSE、SDK namespace/call 配对、state/history、HTTP/幂等/权限均通过。HTTP canary 又发现原生任务 error 出口，已精确补齐；最新事件脱敏 19 项和 SDK adapter 23 项重跑通过。公开 fatal lifecycle/Thread/任务 error 固定说明，保护 content/artifact/metadata/values/result 中的业务数据；控制流与 Run 状态不改。
- **合规检查：** [x] 实现；[x] 定向与扩大回归；[x] 任务状态；[x] CONTEXT/FEATURES/CHANGELOG 随本轮收口同步。

### T08：前端交接与有限展示接入

- [x] T08，前端，2026-10-07 完成。
- **改动内容：** 在 `transcript.ts` 抽取纯函数 `parseToolErrorSummary`，统一支持第一方 JSON、MCP 文本块数组、非 JSON 纯文本（超 100 字符受控截断加省略号）、stream 兜底（`tool.execution_failed`）以及恢复建议微胶囊 Tag 徽章；改造 `ToolResult.vue` 彻底修复 `tool.error` 为空时不渲染折叠条的 Bug，优化展开态代码块排版与 unknown 对账告警分层；复用至 `SubtaskDetail.vue`。不新增工具重试按钮和状态机。
- **代码位置：** `apps/platform-web/src/modules/chat/transcript.ts`（新增 `parseToolErrorSummary` 纯函数）；`apps/platform-web/src/modules/chat/components/ToolResult.vue`；测试文件 `transcript.test.ts`、`ToolResult.spec.ts`、`SubtaskDetail.spec.ts`。
- **预期结果：** 折叠条稳定展示安全摘要及 Tag 徽章，展开态清晰格式化；MCP 数组与纯文本错误解析无异常；实时、历史与子任务都显示同一失败状态和安全摘要，后续模型答复正常；未知终态不误导重复提交。
- **验证项：** 核心单元测试（`transcript.test.ts`、`ToolResult.spec.ts`、`SubtaskDetail.spec.ts`）全绿（31 passed），`pnpm lint` 0 错误、`pnpm typecheck` 0 错误、`pnpm build` 成功；交接文档 F01-F08。
- **完成结果：** 纯函数抽取与单测 18 passed，组件错误与展开态测试 10 passed，子图内部工具失败传递测试 3 passed；全组 31 passed (31)，耗时 752ms；ESLint 0 error，vue-tsc 0 error，Vite 生产构建成功。详见 [implementation/04-frontend-error-presentation.md](implementation/04-frontend-error-presentation.md)。
- **合规检查：** [x] 代码实现完成；[x] 验证项已执行；[x] tasks.md 状态已更新；[ ] CONTEXT.md（跳过，前端单服务错误展示优化未改变对外服务状态）；[ ] FEATURES.md（跳过）；[ ] CHANGELOG.md（跳过）。

## Phase 4：联合 Final

### T09：真实链路、安全、性能与回退验收

- [x] T09，全链路与前端浏览器联合 Final 全部完成。
- [x] T09-B：Runtime/后端链路、安全、性能和 Runtime 代码回退，2026-10-07 完成。
- [x] T09-F：前端浏览器联合验收 F01-F08、旧 Web 历史兼容与联合 Final，2026-10-07 用户真实完成并通过。
- **改动内容：** 实现仅供隔离测试的故障 fixture，执行跨进程持久化/恢复、受控模型和真实模型、浏览器、权限、安全、未知副作用与回退用例。
- **代码位置：** 新增 `apps/runtime-service/tests/services/dearflow_agent/test_tool_error_integration.py`、`test_tool_error_platform.py`、`test_tool_error_live.py`，`tests/fixtures/tool_error_platform.py` 及 `tests/tools/test_tool_error_performance.py`；前端组件与核心单测文件。
- **预期结果：** verification.md 的 U/G/I/C/E/P/R 全部必需项取得真实证据；缺环境的项明确未验，不能用单进程 fake graph 替代。
- **验证项：** 逐项按 verification.md 执行；真实模型不得跳过后记通过；删除/重置资源仅针对显式授权的隔离测试资源，生产发布不在本任务范围。
- **完成结果：** 非前端 U/G/I/C/P/R 已验；前端 F01-F08 用户在真实全栈环境（Platform Web: 3000、Platform API: 2142、Runtime: 8123）中联合验收通过。覆盖折叠态结构化摘要、微胶囊 Tag 徽章、展开态代码块排版、模型错误后自愈回答、刷新页面与历史回放一致性、子智能体 scoped 错误隔离、取消与审批中断不误判、深色模式与响应式等全部关键路径。全栈服务已平稳停止。
- **合规检查：** [x] 隔离 fixture；[x] 非前端门禁；[x] 失败/重跑及限制留痕；[x] 资源收尾；[x] 前端浏览器与全专项 Final 通过。

### T10：本轮非前端文档收口

- [x] T10，2026-10-07 完成；前端交付后的全专项 Final 更新并入 T09-F。
- **改动内容：** implement-feature 留实际实施/故障证据，verify-change 分开记录非前端 Phase 与全专项 Final partial。同步 README、CONTEXT、FEATURES、CHANGELOG Unreleased 和前端交接。
- **代码位置：** 本专项 tasks.md/verification.md/implementation；Runtime 服务 README 与 knowledge/15 的受影响段落；根功能/状态/变更记录。
- **预期结果：** 完成声明与证据一致；不是因为前端交给同事或测试环境缺失就自动标 done。无本专项对应的跨服务标准草案时，不毕业其他专项标准。
- **验证项：** 全部任务核对、文档检查、diff；有值得沉淀的教训时先向用户提案，确认后才写 docs/lessons。
- **完成结果：** 本轮 T01-T10 及对应浏览器/页面契约/全专项联合验收全部完成。无本专项跨服务标准草案，不改其他专项状态；实际 worktree 为 detached HEAD 424ff90e，无命名分支、提交或部署。

## 进度追踪

- [x] 本轮规划与文档检查完成（P01-P04，含 P03b）。
- [x] G0 人工批准。
- [x] Phase 1 完成。
- [x] Phase 2 完成。
- [x] Phase 3 后端回归完成（T07）。
- [x] Phase 3 前端交付（T08）已完成。
- [x] Phase 4 非前端必需门禁与本轮收口完成（T09-B/T10）。
- [x] Phase 4 Final 必需项全部通过。

本专项全部范围已达到 done：T01-T10 全部闭环，无未解决阻塞，未生产部署。
