# F17 - 评估任务与条件接入任务

## 状态口径

本轮授权范围是源码评估与规划，不包含业务代码。`P01–P04` 属于本轮交付；`M01–M05` 是未来有实际知识 MCP 后的条件任务，当前全部 `deferred`。这些后置项不代表评估未完成，也不表示获得开发批准。

本文件是本专项进度事实源；不创建空的 `implementation/` 来表示进度。

## Phase P：本轮评估

### P01：核实 DeerFlow / Open SWE 与当前实现

- **改动内容：** 对照真实源码，修正工具名称、只读目录、外部索引、线程附件、记忆和 MCP 的能力边界。
- **代码位置：** [plan.md](plan.md) §3–4 中的路径/符号，关键文件摘要见 [verification.md](verification.md)。业务代码只读。
- **预期结果：** 分清已有底座和未接入的项目知识检索，不把参考项目文档转换当成 RAG pipeline。
- **验证项：** 路由方法、工具装配、调用者、依赖/配置、测试与旧退役决定都有依据。
- **状态：** [x] 2026-10-10 源码盘点完成。

### P02：按用户补充条件收敛范围

- **改动内容：** 写出自建方案的成本来源、六项取舍、三层职责和未来条件代码落点。
- **代码位置：** `plan.md` §1、5–9；不新增向量库、CRUD 或检索工具。
- **预期结果：** F17 本期不开发自建知识库；未来优先一个外部 MCP，不维护第二套检索路径。
- **验证项：** 当前没有知识服务的前提明确；原 2–3 周估算不作为排期；治理开发未获 AI 自行批准。
- **状态：** [x] 2026-10-10 条件方案完成，用户确认本期不开发并要求合入结论与交接。

### P03：前端交接

- **改动内容：** 明确当前无需开发；列出后续最小 MCP 接入何时才需要前端适配及验收要求。
- **代码位置：** `frontend-handoff.md`；候选入口为 `apps/platform-web/src/modules/chat/components/ToolResult.vue` 与 `transcript.ts`。
- **预期结果：** 同事不会误建知识库 Tab、上传页或选择器，也不会按尚不存在的接口开工。
- **验证项：** 必读规范、真实契约前置、共享 Chat/Dear 复用、权限与迟到响应、测试要求齐全。
- **状态：** [x] 2026-10-10 交接文档完成；无前端代码任务。

### P04：导航与文档核验

- **改动内容：** 同步 `docs/CONTEXT.md`、`docs/FEATURES.md`、旧 A31/T09 的后续入口，纠正原 `docs/knowledge/deerflow-capability-gap-analysis.md` 的 F17 描述/优先级，检查本次链接/路径及 diff。
- **代码位置：** 上述文档及当前专项；不改服务规范和 CHANGELOG。
- **预期结果：** 下一会话可发现延期决定，不把评估完成当成功能已实现。
- **验证项：** 本次文档检查结果写入 `verification.md`；业务文件无修改，既有项目其他任务不被勾选完成。
- **状态：** [x] 2026-10-10 定向文档与 diff 核验完成；无新增问题，既有全仓失败见 `verification.md`。

## Phase M：有服务后再评估，不自动启动

### M01：实际服务与接线 Spike

- **改动内容：** 检查实际 MCP transport、工具名、只读实现、project 限权、query/results、资料质量和运营负责人；完整检查绑定的签发/撤销路径。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/mcp.py:load_mcp_tools()`；`capabilities.py:configured_mcp_names()`；`runtime/resource_bindings.py:resolve_resource_binding()`；API `modules/runtime_gateway/application/service.py:RuntimeGatewayService.create_thread()`。
- **预期结果：** 给出“配置即可 / 需要哪些最小改动 / 不值得做”的证据和估算；不能把 MCP 支持等同于零开发。
- **验证项：** [verification.md](verification.md) 的 V01、V02、V03；至少两项目 canary 与真实外部查询，核验绑定伪造入口。
- **状态：** [ ] `deferred`，等待真实服务和用户发起；不开 mock-only 项目代替真实场景。

### M02：可信绑定与接入配置，仅补实际缺口

- **改动内容：** 按 M01 结果，在现有网关签发可信资源绑定/拒绝客户端伪造，或仅使用已有被证实的受管路径；连接和 Key 留服务端。
- **代码位置：** API `application/thread_access.py:initial_metadata()`、`application/service.py:create_thread()`；Runtime `runtime/resource_bindings.py`；私有连接配置。数据表/新 endpoint 只有真实需求证明需要后才确定。
- **预期结果：** 当前项目决定访问资源，模型和浏览器不能选择更广权限；旧 Thread、Worker 恢复、当前撤权遵守同一边界。
- **验证项：** V02、V03、V08；覆盖公开 Thread 创建、更新、fork/resume、服务账号、项目切换及旧绑定重放；未涉及路径仍记录适用性。
- **状态：** [ ] `deferred`，M01 完成并人工批准最小范围后才能实施。

### M03：单一 MCP 检索工具及结果复用

- **改动内容：** 装配一个查询工具，不新增原生同义工具；如确需格式适配就在现有入口完成；保留 no-hit/error/取消区别和输出限制。
- **代码位置：** Runtime `services/dearflow_agent/tools/mcp.py:load_mcp_tools()`、`capabilities.py:configured_mcp_names()`、`agent.py:_build_agent()`；API `adapters/langgraph/sdk_client.py:redact_runtime_private_fields()`。
- **预期结果：** 单一索引/检索事实源，模型可读有界资料，历史可回放安全来源；默认 Plan Mode 和子 Agent 权限不被放宽。
- **验证项：** V01、V04–V07；检索请求计数、工具 deny、执行失败与空命中、恶意正文、history/stream、预算/offloading 组合验证。
- **状态：** [ ] `deferred`；若配置即满足，此任务不新增代码。

### M04：前端最小适配，由同事负责

- **改动内容：** 先验证现有 ToolResult 是否已满足展示；仅在实际来源格式缺口时追加小投影/展示，不建设知识管理产品。
- **代码位置：** `apps/platform-web/src/modules/chat/components/ToolResult.vue`、`transcript.ts` 及对应测试；规范和条件见 `frontend-handoff.md`。
- **预期结果：** 普通 Chat/Dear 统一展示真实片段与来源，缺失不伪造，不泄漏凭据/未授权正文。
- **验证项：** V04、V09；正常/空态/失败/恶意来源、刷新回放、身份/项目切换及多视口双主题。
- **状态：** [ ] `deferred`；没有实际展示缺口时略过代码改动，仍做现有页面验收。

### M05：Final 与回退验收

- **改动内容：** 运行最小真实完整链路、权限与故障门禁，验证禁用接入后的普通 Chat，记录供应商/版本/配置和安全证据。
- **代码位置：** `apps/runtime-service/tests/`、`apps/platform-api/tests/`、`apps/platform-web` 浏览器测试；接线先使用 `scripts/local-stack.sh` 的隔离资源。
- **预期结果：** 只报告经过真实服务和当前发布依赖验证的能力，Phase 通过不能代替 Final。
- **验证项：** V01–V09；性能按已批准 SLO 或实测基线记录，不虚构门槛；无删除式回退。
- **状态：** [ ] `deferred`，具体命令/fixture 在 M01 锁定真实契约后制定。

## 进度与收口

- [x] 已有能力、真实缺口与参考方案错误已核实。
- [x] 用户确认的本期不开发决定、后续单一 MCP 方向及前端无任务已记录。
- [x] 本轮 P04 文档核验完成；当前授权的评估范围全部交付。
- [ ] 后续 MCP 接入：`deferred`；当前不开发、不排期、不部署。
