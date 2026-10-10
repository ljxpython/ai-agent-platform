# DeerFlow Agent 迁移重新盘点（2026-09-28）

## 目标

回答上游 Agent 能干什么、当前平台做到了哪里、哪些真正缺开发、哪些只是缺验收。此文是代码审视结果，不是生产认证。接续任务见 [12](12-completion-plan.md)，验收见 [13](13-verification-baseline.md)。

## 方案设计：基线与判定方法

- 参考仓库：相对本仓库的 `../research/deer-flow`；HEAD `cc664451f03140b376611f329ae400c313530bdb`，取样时有 58 个工作区变更。下面描述的是**本地参考工作树**，不保证与公开发行版相同，也不代表所有可选配置均已开启。
- 当前平台：取样末期 HEAD `4f49040a5e9b2f2307bc6418321d32cb300a84ec`；开始读取时有大量已有修改，取样末期工作区已干净，期间由外部发生提交。本轮未执行提交或改动业务源码。
- 旧迁移 provenance（例如 K01）：`44ae750545caff29506906f4b0b1ebf79cb23fa7`。不能把新参考树的所有能力倒算成旧项目漏做。
- 锁文件：DeepAgents `0.7.8`、LangChain `1.3.17`、LangGraph `1.2.11`、GraphHarbor `0.13.0.post37`、langgraph-sdk `0.4.3`。`pyproject.toml` 的范围声明不等于实际安装版本。
- 为避免只记录 HEAD 漏掉本地差异，按相对路径排序，对 `.py/.md/.json` 文件执行 `SHA256(path + NUL + SHA256(bytes))` 累积；排除 `graphify-out` 和 `__pycache__`：参考 harness 666 文件，摘要 `c2619b35d9bf8df9eaa79a9a494ada6c90dcfe8c86b51ca150d4f57b88e3f310`；当前 Dear 业务目录 142 文件，摘要 `6fbcf9447e021a9ba7a023be70bf42b8ee8e0569246831faa408666734ef419c`。这是取样身份，不是完整依赖锁或安全审计。

状态口径：**已有**表示找到装配与调用实现；**部分**表示只覆盖部分行为；**未接入**表示当前 Dear 组合根/业务链路未见对应能力，可能已有可复用底层；**历史待验**来自旧记录，不能当今天仍在失败；**排除/延期**沿用已记录决定，重新纳入须评审。单测通过不等于浏览器、外部供应商或生产拓扑通过。

### 当前结构与真实调用链

| 层 | 当前位置 | 应承担的职责 |
|---|---|---|
| 产品入口 | `apps/platform-web/src/modules/dear-agent/pages/` | Dear 会话入口、Skills、个人记忆、成果页 |
| 共用会话 | `apps/platform-web/src/modules/chat/` | SDK 流、消息、审批、澄清、子任务、历史恢复；DearAgentSession 和 useDearAgentSession 已委托至这里 |
| 控制面 | `apps/platform-api/src/platform_api/modules/agents/`、`runtime_catalog/`、`runtime_policies/` | Agent 定义、模型连接与工具策略 |
| 受控网关 | `apps/platform-api/src/platform_api/modules/runtime_gateway/`、`adapters/langgraph/` | 当前 ACL、委托、幂等、HTTP/SSE、审计，不维护第二份 Run 状态 |
| 通用执行引擎 | 锁定的 GraphHarbor 发布包 | Thread/Run/checkpoint/interrupt/worker/stream 生命周期 |
| 图入口 | `apps/runtime-service/src/runtime_service/graphs/dearflow_agent.py` | 仅导出 `get_agent`；由 langgraph 配置注册 |
| Agent 组合根 | `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py:get_agent` | 验证身份和 Context 哈希、解析模式/模型/权限、装配工具和 Middleware |
| Dear 业务 | 同目录 `tools/`、`middleware/`、`subagents/`、`skills/`、`memory.py`、`skill_governance.py` | 研究、技能、记忆、只读委派、外部副作用回执 |
| 公共 Runtime 能力 | `apps/runtime-service/src/runtime_service/workspace/`、`runtime/`、`http/`、`messaging/` | 作用域工作区、执行、文件、资源绑定和持久消息队列 |
| 应用数据 | `apps/runtime-service/src/runtime_service/db/migrations/` | Runtime 自有业务迁移；不向 GraphHarbor 塞 Skills/媒体业务表 |

执行顺序是 Web → Platform API 授权/受信委托 → GraphHarbor Run/worker → Dear `get_agent` → 模型/工具/工作区 → 同一 Run 流回 Web。Skills/记忆管理走 Web → Platform 网关 → Runtime 业务 HTTP → Runtime 应用数据。已经退役的旧结果服务不参与新设计。

### Agent 能力总表

下表源路径以 `S = ../research/deer-flow/backend/packages/harness/deerflow/` 为前缀，目标以 `R = apps/runtime-service/src/runtime_service/` 为前缀；`D = R/services/dearflow_agent/`。路径与符号是实现入口，不因文件存在就推断运行可用。

| ID | 上游能力：用户可做什么 | 上游依据（相对 S） | 本项目事实/差异 | 接续 |
|---|---|---|---|---|
| A01 | 自然语言理解→工具迭代→最终回答 | `agents/lead_agent/agent.py:build_middlewares`、`factory.py` | 已有，D `agent.py:get_agent` 使用官方 `create_deep_agent`，不迁移上游 factory/config 系统 | T01/T02 |
| A02 | Flash/Standard/Pro/Ultra；规划及思考开关 | `agents/lead_agent/agent.py`，上游 Web 模式入口 | 已有四模式；D `modes.py`：仅 Pro/Ultra planning，仅 Ultra delegation；显式思考参数目前仅支持 DeepSeek V4，其余回退模型默认 | T02/T03 |
| A03 | Todo 拆分及进度；防未完成就结束 | `agents/middlewares/todo_middleware.py` | 官方 Todo 已有；未见上游的未完成拦截/压缩后提醒等价实现；不能把清单显示当完成核验 | T07 |
| A04 | 主动追问/选项/表单、人机互动 | `tools/builtins/clarification_tool.py`、`clarification_middleware.py` | 已有 `request_information` 七字段、`ClarificationBatchGuard`，采用官方 interrupt/resume；不照搬 END+新消息续跑 | T02 |
| A05 | 文件/执行/图片/发布等敏感操作审批 | `agents/interaction_policy.py`、guardrails | 已有工具治理和 APPROVALS；当前 access_policy 决定是否中断，不能笼统宣称所有操作总会弹审批 | T02/T03 |
| A06 | 搜索互联网、抓取网页、落地引用证据 | `community/` 搜索/抓取 providers | 已有 D `tools/search.py`、`research_http.py`；Tavily 缺 key 则不暴露 search/fetch；来源要求进入 prompt，但非通用自动事实核验 | T04/T07 |
| A07 | GitHub 深研、论文/文献检索 | public Skills + 通用检索/脚本 | 已有专用 `github_query`、`arxiv_search`；旧外部限流待重验 | T04 |
| A08 | 读写/搜索文件、执行 Python/SQL/Shell | `sandbox/tools.py`、`sandbox/sandbox_provider.py` | 已有 `DearWorkspaceBackend`、公共 execution；Docker 与受信开发 local 均可选；local cwd 不构成安全沙箱 | T03/T10 |
| A09 | 上传、文档解析、历史附件发现 | `uploads_middleware.py`、`list_uploaded_files_tool.py` | 已有文档工具和附件链路；`DocumentToolsMiddleware` 每次枚举 uploads，未见有界历史附件查询等价机制 | T07 |
| A10 | 看图/视觉理解 | `view_image_tool.py`、`view_image_middleware.py` | 平台有图片传输；Dear 根只装 DocumentToolsMiddleware，未装公共 ImageToolsMiddleware；不能由“可上传/生成图”推断 Dear 能读取工作区图像理解 | T03 |
| A11 | 发布、预览、下载、打包成果 | `present_file_tool.py`、`artifact_registry.py`、workspace | 已有公共 artifact/workspace；HTML 隔离预览、ZIP、表格和图像式 PPTX；音视频不在 MEDIA_MIMES，产物读取仍全量 bytes | T02/T06 |
| A12 | 子 Agent 独立上下文与并行委派 | `subagents/executor.py`、`task_tool.py` | 部分：只读研究角色覆盖 general-purpose，3 并发、task 总限10；不能执行代码、写成果、继续委派；与上游通用/bash worker不同 | T02/T07/T09 |
| A13 | 可管理的子 Agent 定义、角色/模型/工具范围 | `subagents/registry.py`、`config.py` | 当前声明式单研究角色；没有等价管理产品。符合当前最小权限规则，不宜照搬任意通用执行角色 | T09（候选） |
| A14 | 子任务步骤、历史回放、取消、用量归属 | `step_events.py`、`status_contract.py`、`token_collector.py` | 已有 namespace 展示和父 Run 取消；post37/网关已补 checkpoint_ns 回查；独立 child cancel 明确 false、完整父子费用账本未齐 | T02/T09 |
| A15 | 子任务结果引用回执与验收条件核查 | `tool_receipt*.py`、`receipt_verification.py`、`subagents/acceptance_checks.py` | 未见等价装配；当前依靠 prompt 要求核对来源，文件 hash 验证仅覆盖文件，不证明任务完成 | T07 |
| A16 | 摘要压缩、超长工具结果外置 | `summarization_middleware.py`、`tool_output_budget_middleware.py` | 已有官方 DeepAgents 摘要和 StateBackend history/large-results 路由；本轮摘要测试通过，不应再自造压缩器 | T07（补组合边界） |
| A17 | 手动压缩、工作笔记、历史查找、压缩后任务连续性 | `runtime/context_compaction.py`、`agents/task_continuity/`、`durable_context_middleware.py` | 部分：有 checkpoint 和历史文件；未见 task_note/history_search/history_read 或手动压缩产品入口；需要验证官方能力后才补业务缺口 | T07 |
| A18 | 长期记忆检索、写入、自动提取 | `agents/memory/`、`memory_middleware.py` | 已有本人×项目事实、候选采纳、CRUD/导入导出、CAS/epoch/到期、180秒提取；共享线程拒绝。非全局跨项目记忆 | T05 |
| A19 | 多记忆后端、热度/置信度淘汰 | `agents/memory/backends/` | 未迁移 DeerMem/Honcho/Mem0/OpenViking 后端体系；当前 PG 有界词法召回已能满足批准需求，不为对齐名字引入新依赖 | T09（候选） |
| A20 | Skill 渐进加载、内置资源、会话间复用 | `skills/`、`skill_activation_middleware.py` | 已有官方 SkillsMiddleware 和不可变执行快照；19个迁移资源+1个烟测；可读不等于工具获授权 | T04/T05 |
| A21 | `/skill` 强制激活、使用历史快照、技能 allowed-tools/secret 绑定 | `skills/slash.py`、`skill_usage.py`、`skill_tool_policy_middleware.py` | 未见同等业务闭环；现有 execution snapshot 是运行冻结，不等于 UI 显示实际使用 Skill。secret 绑定是新增信任边界 | T08 |
| A22 | Skill 上传、更新、审查、启停、导出/发现 | `skills/installer.py`、`export.py`、`skill_manage_tool.py` | 部分：单份当前内容、ZIP、只读审查、精确 Git commit 导入；无用户版本回滚/导出/市场，后者有明确不做决定 | T05；额外部分T09 |
| A23 | MCP 工具接入、目录延迟检索/路由 | `tools/builtins/tool_search.py`、`mcp_routing_middleware.py` | 部分：D `tools/mcp.py` 仅绑定 streamable_http、声明 allowlist 且 readOnlyHint=true；没有按需 schema promotion | T08 |
| A24 | 远端后台任务查询/取消、通知后续跑 | `background_tasks_tool.py`、MCP task/runtime | 部分：图片/部署 ExternalTaskStorage 记录 submitting/unknown 等；不是通用持久调度，也不提供完整 MCP task 生命周期 | T06/T09 |
| A25 | 一批大量独立任务，后台进度/取消/导出 | `batch_task_tool.py`、`subagents/batch_service.py` | 未接入；3个普通 task 并发不等于 durable batch | T09 |
| A26 | Goal 跨 Run 评估、自主续跑、无进展熔断 | `runtime/goal.py`、`agents/goal_state.py` | 未接入；不能把 Todo 或当前会话消息队列当 Goal | T09（原延期） |
| A27 | 定时 cron/interval/时区任务 | `scheduler/schedules.py`、`persistence/scheduled_tasks/` | 未接入；需授权主体、撤权、去重、错过触发策略，不能在 Web setInterval 执行 | T09（原延期） |
| A28 | Token 成本预算、循环/停滞检测 | `token_budget_middleware.py`、`loop_detection_middleware.py`、`tool_progress_middleware.py` | 部分：截至2026-10-09已补执行预算/软收尾、超时、Token/Cost采集（不等于金额预算）；当前正数env优先。F02只读连续参数/结果保护已实装，三组合根主子、Worker恢复、旧checkpoint回退有证据；默认关闭，前端仍待接续，非通用停滞判官 | T03其余范围；T07/F02接续[15](15-f02-loop-detection.md) |
| A29 | 长度截断/拒绝/空响应修复、模型错误控制 | `model_length_finish_reason_middleware.py`、`safety_finish_reason_middleware.py`、`llm_error_handling_middleware.py`、`terminal_response_middleware.py` | 已有 SDK/模型与超时处理；未见 Dear 等价专项装配，需针对锁版本做故障验证后决定是否添加 | T07 |
| A30 | 注入输入隔离、PII、工具结果清洗、读后写门禁 | `input_sanitization_middleware.py`、`pii_redaction_middleware.py`、`read_before_write_middleware.py` | 已有 scope/审批/包检查/SSRF/路径边界；未见等价通用 Middleware；安全差异列评审，不默认导入上游规则 | T03/T07 |
| A31 | 私有知识检索与消息级知识范围 | `knowledge_scope.py`、`knowledge_scope_middleware.py`、community RAGFlow | Dear 未接入等价知识范围；平台项目/工具绑定不等于资料检索，先盘点已装 MCP 再定是否新增知识产品 | T09 |
| A32 | 项目指令和资料架、归档/回收站 | `projects/context.py`、`documents.py`、`tools.py`、`trash.py` | 平台已有 IAM 项目；并非同义的 Agent 资料架。未接入上述业务；不能直接复用 project_id 就认定完成 | T09 |
| A33 | 显式引用其他会话并分页阅读 | `tools/conversation.py` | 当前会话历史/分叉已有；未见按 Run 授权的跨会话阅读，涉及 ACL 与被读内容留存 | T09 |
| A34 | 浏览器导航/点击/表单/截图/实时画面 | `community/browser_automation/` | 旧专项明确不做；静态网页成果预览不等于浏览器自动化 | T09（排除待重选） |
| A35 | 定制 Agent/SOUL、自身配置修改 | `config/agents_config.py`、`setup_agent_tool.py`、`update_agent_tool.py` | 平台有 Agent 编辑/模型/提示配置；不提供模型自行改权限/配置的同等路径，bootstrap改为个人偏好 | T05/T09 |
| A36 | 调用外部 ACP Agent | `tools/builtins/invoke_acp_agent_tool.py` | 未接入；属于新进程、凭据和执行权限边界，不是普通只读 MCP | T09 |
| A37 | IM、TUI、嵌入式 Python Client、扩展插件 | channels、client、extensions（及独立包） | 原范围仅 Web；不复制上游 Gateway/RunManager/插件宿主。属于可选接入形态，不是19个已迁移 Skill的必备前置 | T09（排除待重选） |
| A38 | 流式消息、思考、标题、历史、分叉、追踪 | runtime/runs、title/token_usage middleware | 已有平台 SDK/GraphHarbor、title_summary、Langfuse；历史专项仍有容量/JWT/边界验收遗留，应继承其证据，不重造 | T02/T10 |

### 23 个 Skill 逐项对照

来源统一是 `../research/deer-flow/skills/public/{上游目录}/SKILL.md`；目标统一是 `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/{目标目录}/`。默认同名，K22显式更名。共同 E2E 要从 Dear 路由执行，核对来源/工具调用/真实产物和刷新恢复，不只读 SKILL.md。

| ID | 上游目录 / 用户任务 | 当前代码及历史证据 | 剩余开发或验收（负责人任务） |
|---|---|---|---|
| K01 | deep-research：多角度联网研究 | 资源、search/fetch、报告证据已有；旧后端通过 | 当前网关＋Dear页面研究→引用→下载（T04） |
| K02 | academic-paper-review：论文评审 | 资源、parse_document、结构化评审已有 | PDF页码、URL失败、方法/局限描述真实验收（T04） |
| K03 | github-deep-research：仓库深研 | 资源+github_query已有；旧匿名403 | 可用只读凭据/配额下重验，不冒认缺工具（T04） |
| K04 | consulting-analysis：咨询报告 | 报告资源已有；图表依赖未全验 | 数据→分析→图表→来源的完整报告（T04） |
| K05 | systematic-literature-review：多论文综述 | 资源+arxiv_search已有；旧429/超时 | 真实检索、去重、abstract_only、BibTeX（T04） |
| K06 | code-documentation：代码/API文档 | 资源及静态ZIP阅读已有 | 代码位置准确、上传包不执行、成果下载（T04） |
| K07 | newsletter-generation：新闻简报 | 正文抓取后端历史通过 | 发布日期与抓取日期区分、多来源正文（T04） |
| K08 | data-analysis：Excel/CSV/SQL | DuckDB/openpyxl/xlrd与脚本已有 | 多表join/聚合、错误列、导出值；不只看文件存在（T04） |
| K09 | chart-visualization：26种图表 | schemas/工具/资源已有；历史25/26，双轴阻塞 | 26种逐项验数据；双轴真实供应商；授权外发（T04） |
| K10 | frontend-design：网页/源码包 | HTML/ZIP产物已有；平台支持隔离预览 | 页面、ZIP hash、主动内容隔离；prompt仍写“只下载”需对齐真实能力（T03/T04） |
| K11 | web-design-guidelines：网页规范审查 | fetch_web_guidelines及版本hash已有 | file:line报告与规范快照；不宣称已跑交互（T04） |
| K12 | image-generation：文生图/参考图编辑 | generate_image/edit_image/回执已有；单图历史通过 | 多参考图真实重验、unknown不重购（T04） |
| K13 | ppt-generation：图像型幻灯片 | python-pptx脚本与验证已有；三页历史通过 | 逐页预览、完整图片、20页上限/缺图；非原生可编辑PPT（T04） |
| K14 | podcast-generation：双人播客 | 未迁入，旧明确延期 | 供应商、语音角色、音频合成和交付全链路（T06，可选批次） |
| K15 | music-generation：音乐/歌词生成 | 未迁入，旧明确延期 | 供应商、计费/轮询/取消/音频交付（T06，可选批次） |
| K16 | video-generation：文生视频/图生视频 | 未迁入，旧明确后续实施 | 持久远端任务＋视频格式/Range/播放（T06，可选批次） |
| K17 | skill-reviewer：技能包审查 | inspect_package/只读审查已有 | 按现行规则验静态检查，不恢复旧发布门禁（T05） |
| K18 | skill-creator：创建/改进/评估技能 | 资源、上传/更新已有；旧文本评估通过 | 现行上传→当前内容→新执行采用→旧执行冻结；不能等同上游完整benchmark优化工具链（T05） |
| K19 | find-skills：发现/引入技能 | 本地目录+精确commit远端导入代码已有 | 真实远端包、拒绝危险路径/内容；不全局安装（T05） |
| K20 | bootstrap：身份/偏好初始化 | 改写为澄清→个人记忆；不原样SOUL自修改 | 本人项目新会话召回、共享禁用；明确行为差异（T05） |
| K21 | surprise-me：组合已可用技能 | 资源/推荐已有；旧组合通过 | 不推荐缺工具/不支持能力；现有VERIFIED仅8项硬编码，需核对展示与能力事实（T03/T05） |
| K22 | vercel-deploy：部署预览/claim | 目标vercel-deploy-claimable；静态ZIP、审批、摘要绑定、幂等已有，默认关闭 | 真实静态发布未验；动态框架构建未实现；若继续限静态，必须明确为部分等价（T06） |
| K23 | claude-to-deerflow：外部客户端桥接 | 未迁入；旧明确延期 | 要么继续排除，要么评审平台SDK桥接的新产品语义；不可声称同等迁移（T09） |

统计仅针对**资源目录**：23项中19项迁入、4项未迁入；本地 runtime-smoke 不占上游名额。`skill_catalog.py:VERIFIED` 仅列8项，是代码标签，不是实时验收台账。`test_dearflow_skills.py` 有20个参数场景（含K12_EDIT/K13_UPLOAD变体），覆盖18个Skill ID，缺K22正式场景及4个未迁移项；这也不等于20项已通过。

### 旧专项与后续专项的冲突处理

| 旧说法 | 当前事实 | 本轮处理 |
|---|---|---|
| README“全部竣工/无阻塞/具备生产交付条件” | 07台账、10的P1—P7、FEATURES保留大量未验项 | 总体恢复partial；前端单测成绩只保留为历史阶段证据 |
| Dear与Chat复制后独立演进 | 20260923重构已共享Chat；源码为薄包装/re-export | 不再按旧08复制；后续改共用Chat并回归两入口 |
| Skill候选→评估→发布/回滚 | 20260919已批准单份当前内容＋执行快照；七类管理接口 | 不把已取消设计算漏做，不恢复旧版本体系 |
| 记忆仍只有旧P6 | 20260920新增无线程管理、队列来源、共享检查，前端已实现 | 接续其R08/V03/浏览器验收，避免重复开发CRUD |
| 子任务历史丢失仍需自建事件表 | 20260928 post37及checkpoint_ns网关已有修复记录 | 复验Dear实际UI，禁止先造第二份子任务状态 |
| 默认v2、post30仍是当前基线 | 当前锁post37，正式技能E2E选择v3；运行配置仍需实测 | 不凭旧总纲推断部署态；T01冻结实际配置 |
| 源参考树等同旧迁移版本 | reference HEAD变化且有本地修改 | 新能力单列候选，不扩大旧授权 |
| 项目实现了动态Web应用部署 | `test_dynamic_webapp.py` 只验证FastAPI队列body前向引用 | 不把同名测试计为K22动态框架支持 |

## 任务拆分

- [x] 盘点参考树Agent/工具/Middleware/Skills及当前三服务落点。
- [x] 复核旧专项和后续Skills/记忆/前端/子任务历史方案的覆盖关系。
- [x] 按“源码实现/历史证据/今日抽测/未来验收”分开记录。
- [x] 将实际欠账、候选增强和已排除能力交给12的任务表。

## 验证要求与记录

2026-09-28：完成静态源码核对、23目录对照、锁版本与工作树摘要；核心抽测28 passed/1 skipped，详细边界见13。上游可选功能没有启动验证；供应商历史失败没有在本轮复现，不能称为现役故障。

## 状态

本轮能力盘点已完成；Agent整体迁移仍partial。未迁移项是否纳入本期、通用安全策略差异以及新增跨服务契约须人工评审，见12。
