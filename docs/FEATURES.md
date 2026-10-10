# 功能现状总览

全仓库当前功能清单，按服务分组。每次 `apps/{app}/docs/changes/`、根目录 `docs/changes/` 或
`docs/projects/` 落一笔新记录时，同步在这里新增一行或更新对应行的状态，不需要每次改动都重写整份文档。

状态取值：规划中 / 进行中 / 已完成 / 部分完成（说明缺什么）。

## platform-web

| 功能 | 状态 | 关联文档 |
| Agent 运行准备与有界重试诊断摘要展示 | 已完成：实装运行准备（RunPreparationsSection）与受管重试（RunRetriesSection）独立子组件，支持 strict attempts/role 正则校验、主 Run 成功时琥珀色 Amber 警示降级、空态完全隐藏、敏感字段剥离，49 项单测与 Playwright 全链路 E2E 验证全绿 | [前端交接](projects/20261007-agent-production-capabilities/frontend-handoff.md) |
| Agent Run/Thread 用量与成本展示 | 已完成：实装独立解耦面板 RunUsage 与 useRunUsage 防竞态状态机、open-swe 水位进度条 (Usage Meter)、服务端截断告警卡片、模型费率安全编辑（Decimal 精度、自动补零、可逆清空保护）以及假数据彻底切除。Playwright + Chromium 端到端 5 项全绿（含真实百炼 qwen-plus 全链路调用闭环与 24,069 Tokens / $0.0051 落库上屏）并生成 7 张高清渲染截图，全仓 120 套件 583 项单测、typecheck、lint 和生产打包 100% 通过 | [前端交接](projects/20261007-agent-usage-cost-governance/04-frontend-handoff.md) |
| Agent 执行预算告警与限制原因展示 | 已完成：Zod 契约投影、安全解包、useRunBudget 有界 LRU 去重与 Run/namespace 隔离、ChatAgentStatusBar Amber/Success 停机展示（保留取消、文案解耦、A11y）、子任务微横条与徽章、Thread 耗尽禁用；571 单测、类型检查与 ESLint 全绿 | [项目入口](projects/20261007-agent-execution-budget/README.md) · [实施记录](projects/20261007-agent-execution-budget/implementation/02-frontend-budget-implementation.md) |
| Agent 模型调用稳定性与容灾降级界面 | 已完成：实装 AgentEditorPage 模型恢复策略配置（主备去重、等待时间联动推高、schemaEpoch 防草稿覆盖、step=1 步长修复与保存成功就地高亮微反馈）；接通 4000ms 前端超时保护与 wait=true 取消确认；useChatSession 映射 5 大稳定机器码，trajectory-adapter 真实终态修正与备用模型微胶囊渲染；全量单测 559 passed，三服务端到端故障注入实测通过，用户在浏览器端人工验收通过 | [项目概览](projects/20261006-agent-model-resilience/README.md) · [前端交接](projects/20261006-agent-model-resilience/frontend-handoff.md) |
| Agent 会话级停止控制与状态报告展示 | 已完成：实装三接口接入、Zod DTO 校验、useThreadStopControl 状态机解耦、45s 超时降级与单飞保护、RunStopReportBanner 顶部提示条与 RunStopReportDetails 抽屉报告，Vitest 553 项全绿，Playwright+Chromium 真实模型全链路自动化闭环通过（1440/768/390 截图已存档） | [前端交接](projects/20261007-agent-run-cancellation/frontend-handoff.md) |
| Agent 运行诊断面板（Run Diagnostics） | 已完成：实装独立解耦面板 RunDiagnostics、Zod 白名单契约、防竞态 useRunDiagnostics、TrajectoryView 常驻入口与模式切换、ChatSession 历史 Run 自动拉取与无缝切换，全仓 115 套件 535 项单测全绿，浏览器联合验收通过 | [前端交接](projects/20261006-agent-observability-hardening/frontend-handoff.md) |
| Agent 上下文整理反馈与手动动作 | 已完成：单模型容量编辑与查看（F01）、整理微胶囊与 4 秒淡出/输入打断机制（F02）、手动整理菜单与守卫隔离（F03）；63 项单测、vue-tsc 0 错误与生产打包全通过；用户在真实平台页面完成端到端人工实测联合验收，全链路闭环通过 | [项目概览](projects/20261006-agent-context-window-governance/README.md) · [前端交接](projects/20261006-agent-context-window-governance/frontend-handoff.md) |
| 定时 Agent 任务页面 | 已完成：实装现代化卡片网格列表、双栏创建/编辑抽屉、DeerFlow 预设体系、历史记录抽屉与权限守卫，481 套单测、类型检查与生产打包全绿 | [前端交接](projects/20261005-scheduled-agent-tasks/frontend-handoff.md) |
| 工具卡片错误结构化摘要提取与微胶囊 Tag 徽章展示 | 已完成：纯函数 parseToolErrorSummary 抽取，统一支持第一方 JSON、MCP 文本块数组与纯文本截断，微胶囊 Tag 徽章（recoveryHint）与展开态格式化排版实装，根治 tool.error 为空时不显红条 bug，31 项单测、类型检查与打包全绿 | [实现记录](projects/20261006-agent-tool-error-resilience/implementation/04-frontend-error-presentation.md) |
| Chat 顶栏选择 Agent 历史会话队列联动过滤与 Pad 侧栏体验治理 | 已完成：修正 currentSelectedAgent 优先级倒挂、拔除 graph_id 过滤劫持恢复 agent_id 精准匹配、优化 Pad 侧边栏折叠交互，210项单测全绿 | [变更记录](../apps/platform-web/docs/changes/20261004-chat-agent-history-filter-fix.md) |
| Chat 对话体验优化（视口倒滚/流式跟随/消息秒蒸发）与切屏权限失效自爆根治 | 已完成：视口防倒滚精准锚定、rAF 60fps 原生流式跟随、切除 computed 副作用根治消息闪退、加固 SWR 权限驻留与具名事件解绑彻底根除切屏报错，212项单测全绿 | [变更记录](../apps/platform-web/docs/changes/20261004-chat-viewport-smooth-follow-fix.md) |
| 多会话切换切回假死死锁、空白消息水合缺失与投递报错隔离 | 已完成：切回终态收敛、落盘轻量水合、队列自动消费与报错展示隔离全链路闭环，422项单测全绿 | [变更记录](../apps/platform-web/docs/changes/20261004-chat-session-switch-healing-and-receipt-isolation.md) |
| 模型思考内容展示与 OpenAI 兼容字段保留 | 部分完成：Qwen/DeepSeek 真实模型、LangGraph 消息流和浏览器 Think 展示通过；正式平台模型目录聊天链路待验 | [排查与验证](projects/20260923-model-reasoning-output/README.md) |
| 对话流式超时容错与 Transcript 解析优化 | 规划中：解决长推理超时截断与前端幽灵步骤假折叠问题 | [项目概览](projects/20260921-chat-stream-timeout-and-retry-optimization/README.md) |
| 平台权限状态与刷新容错 | 本地 done：临时网络故障保留权限快照和登录；局部拒绝隔离；真实撤权、冷启动重试与 Runtime ACL 连接复用验证通过；未生产部署 | [专项与验证](projects/20261005-platform-access-refresh-governance/README.md) |
| 全平台菜单、页面与角色权限治理 | 人工验收中：技术实现与自动化 Final done；固定角色、平台/对象授权、撤权、P1 隔离、治理边界及项目内个人记忆入口完成；共享/跨项目记忆等 deferred | [分章方案与进度](projects/20260920-platform-access-governance/README.md) · [人工验收用例](projects/20260920-platform-access-governance/08-manual-acceptance.md) |
| Agent 回复新对话分支 | 进行中：Platform API 受控分叉和 Runtime 隔离验证实施中；前端已完成对接设计、待接入 | [项目规划](projects/20260917-agent-conversation-fork/README.md) |
| Agent 会话访问策略（逐项审批 / 工作区免审批 / 全权负责） | 部分完成：前后端与 Runtime 均已实现三档策略（review/workspace_write/full_access）、输入框左右布局对齐与草稿态同步；待全栈启动后跑最终 E2E 验收 | [方案](projects/20260917-agent-session-access-policy/README.md) |
| Dear Agent 专属前端 | 进行中：F1/P1 已完成（专属模块 `src/modules/dear-agent/`、独立路由、澄清表单交互卡片、审批面板与输入锁定、历史僵尸澄清过滤与实例隔离已落地并通过 50 套全量回归）；F2—F7 后续推进 | [前端交接与实施](projects/20260913-dearflow-agent/frontend-handoff.md) · [澄清复活修复](apps/platform-web/docs/changes/20260923-fix-zombie-clarification-on-thread-switch.md) |
| Dear Agent 独立成果页闭环 | 已完成：后端与前端核心对接全链路完成。前端实现独立 useArtifacts、右侧滑出抽屉（Drawer）、download 拦截、Axios Blob 错误解包，27 项单元测试及生产构建打包验证通过 | [分层规划](projects/20260920-dear-agent-artifacts-alignment/README.md) · [前端交接](projects/20260920-dear-agent-artifacts-alignment/04-frontend-handoff.md) |
| Dear Agent Skills 页面改进与治理简化 | 前后端最高/已完成：无会话技能目录与详情、用户上传/更新/启停/删除、执行快照恢复、独立Alembic；前端组件重构、详情抽屉与单测全量通过，待浏览器联合演练 | [进度总览](projects/20260919-skills-page-improvement/README.md) |
| 正式聊天 v2（LangChain 流式运行时、线程续接、工具调用与中断展示） | 已重写：官方 SDK 会话、按轮渲染、多 ID 审批、历史分支及移动工作区；最终验收见项目记录 | [Chat 重构](projects/20260910-platform-web-refactor/04-chat-session-and-interaction.md) |
| 运行级调试配置 | 已完成：公开 Context/config 白名单、schema 参数校验；不保留旧提示词覆盖 | [接入契约](projects/20260910-platform-web-refactor/03-api-contracts.md) |
| 控制面核心页面（overview/projects/users/agents/me/security/audit） | 已迁移：Agent/模型新契约、统一权限导航、列表四态；全路由浏览器验收见项目记录 | [现状与目标架构](projects/20260910-platform-web-refactor/02-architecture-and-ui.md) |
| 旧 Chat 视觉与统一 Agent 入口 | 部分完成：Agent 归一已交付；旧工作台组件已直接取回；37 项定向测试及三尺寸回归通过；摘要数据与部分专项验收仍待补齐 | [09 还原功能核对](projects/20260910-platform-web-refactor/09-chat-workbench-restoration-audit.md) |
| Platform Web 架构与 Agent Chat 重构 | 01—07 非后置范围已完成；旧展示组件已取回，专项验收边界见 09；双浏览器入队/完整文件与 Skills API/PTY 后置 | [项目概览](projects/20260910-platform-web-refactor/README.md) |
| 运行中补充消息（多端入口、Runtime 队列与 Middleware） | 已实现：根模型注入、持久回执/恢复、权限复核与 Web 重试；消息内部原生Run回查委托源码修复及本机PostgreSQL测试通过，现役跨服务链路未验证；前端排队守卫和横幅状态修复已落地，双浏览器后置 | [队列与消费设计](projects/20260910-platform-web-refactor/07-message-queue-and-middleware.md) · [内部Run回查修复](projects/20260927-message-run-read-delegation/README.md) |
| Chat 流式输出标准化与 open-swe 架构对齐 | 已完成：流式管道、打字机光标、平滑滚底、Open SWE 子智能体卡片特化与微型居中未读胶囊已全量交付通过 | [流式标准化](projects/20260912-chat-streaming-standardization/README.md) |
| 聊天任务进度底部悬浮托盘（Composer Top Tray）与时间旅行动作标题精准化 | 已完成：任务进度下沉至底部输入框顶沿阶梯托盘（SVG 环形进度圈 + 完成态降噪 + 向上展开清单），彻底根治正文/深色代码块滚动穿模遮挡；时间旅行历史基于当前 Step 动作精准呈现标题 | [任务进度底部托盘重构](../apps/platform-web/docs/changes/20260924-composer-task-tray-redesign.md) · [时间旅行优化](../apps/platform-web/docs/changes/20260912-task-pill-dismiss-and-history-preview.md) |
| 历史关键节点过滤、多步长翻页与消息编辑分叉 | 已完成：白名单精准识别业务里程碑并剔除无新动作系统流转帧；支持 +20/+50/+100 快速翻页；编辑消息即时响应与本地内存回溯杜绝卡死 | [关键节点与编辑分叉修复](../apps/platform-web/docs/changes/20260912-history-milestone-filter-and-edit-branch-fix.md) |
| 时间旅行抽屉角色筛选与历史发问分叉 | 已完成：抽屉按用户/Agent/工具多维筛选与统计，可与关键节点组合，秒级定位发问检查点并分叉重新执行 | [时间旅行角色筛选](../apps/platform-web/docs/changes/20260913-history-checkpoint-role-filter.md) |
| 前端对话页面美化与交互体验重构 | 已完成：Hover 浮动工具栏、复制反馈、高质感 Agent 胶囊选择器、Agent Hero 欢迎看板与快捷 Prompt、代码 Diff/终端卡片及输入框光晕微交互已全量交付通过 | [对话页面美化](projects/20260913-chat-ui-aesthetic-optimization/README.md) |
| 对话正文与工具卡片工作区图片自动解析与渲染 | 已完成：聊天正文自动扫描工作区图片路径并派生渲染大图卡片，支持放大与下载；工具卡片中文别名与产物感知增强 | [图片自动渲染](../apps/platform-web/docs/changes/20260913-workspace-image-auto-render.md) |
| 产物图片全链路渲染缺陷修复与代码保护原地切块 | 已完成：支持 outputs 产物白名单、原地切块、Markdown 反引号代码/超链接保护防止路径误触拆块，并对齐 Dear Agent 模块 | [产物图片渲染修复](../apps/platform-web/docs/changes/20260918-fix-artifact-image-rendering.md) |
| DeepSeek Harness 轨迹视图迁移（双视图切换、事件流水账与 Master-Detail 检查器） | 已完成：支持对话/轨迹模式随时切换；按轮次/步数分组呈现思考链、工具入参与返回、错误高亮及 Raw JSON 深度排障；适配层带安全降级 | [轨迹视图迁移](projects/20260914-deepseek-trajectory-migration/README.md) |
| 轨迹排障 DevTools 体验深度对齐（三层甘特时间线、树状贯穿线、紧凑单行表格与 Summary 内联预览） | 已完成：多通道横向甘特条（Input/Model/Tools）、Turn Rail 树状节点与连线、微型彩色徽章、左侧 3px 指示竖条、实时搜索与性能指标底栏 | [轨迹 DevTools 体验对齐](../apps/platform-web/docs/changes/20260914-trajectory-devtools-layout-alignment.md) |
| 前端主对话流极简化与高级感对齐（无界通透主视窗、灰色原子 Think 条、无头像用户气泡与工业指标底栏） | 已完成：去除卡片套娃大框、Think 改为极简灰色单行、去头像气泡、下划线视图 Tab 与性能小字底栏 | [主对话流极简对齐](../apps/platform-web/docs/changes/20260914-chat-ui-minimalist-deepseek-alignment.md) |
| 对话工作台通透无界大视野与布局重构（单层沉浸顶栏、消除底部死留白、自适应平滑滚动与侧栏一键折叠） | 已完成：消灭双 Header 套娃释放 56px 高度、下沉项目与用户切换器、消灭底部大留白、移除会话侧栏分页器并常驻一键折叠 | [通透无界布局重构](../apps/platform-web/docs/changes/20260914-chat-workspace-borderless-layout-redesign.md) |
| 轨迹排障三合一控制器、微交互与工业级指标栏对齐（Duration/Turns/Calls、甘特 Tooltip、概览大字与圆球发送气泡） | 已完成：实装 Duration 真实耗时模式、Turns 批量折叠、Calls 工具隐藏、时间轴色块 hover 黑底白字气泡、顶栏 X 轮 Y 步 Z 工具统揽、完整 LLM/TTFT/tok/s 指标栏及圆球向上箭头微交互 | [控制器与指标栏对齐](../apps/platform-web/docs/changes/20260914-trajectory-controllers-and-metrics-strip-alignment.md) |
| Showcase / DearFlow 沙箱工作区、文件树、安全HTML/Markdown预览与多终端会话 | 已完成：借鉴 open-swe 架构，弹性拖拽宽度与全屏最大化、单层懒加载文件树、HTML/Markdown/Code统一预览、xterm多终端会话保活、终端划词一键入Chat及全链路Agent终态静默刷新已全量交付通过 | [工作区前端实现](projects/20260917-showcase-artifact-workspace/implementation/04-platform-web-workspace.md) |
| 工作区全量文件打包下载（.zip） | 已完成：后端标准库流式 Zip 打包、网关安全透传及前端一键下载与 loading/toast 提示全量交付通过 | [工作区全量打包下载](projects/20260918-workspace-archive-download/README.md) |
| 对话历史按智能体过滤与极简微型分页器优化（首页/末页直达 + 跳页输入） | 已完成：选择特定 Agent 时列表仅展示该 Agent 的历史会话并实时联动，支持总数呈现、«/» 极端直达与数字直接跳页 | [会话按 Agent 过滤与分页优化](../apps/platform-web/docs/changes/20260918-chat-agent-history-filter-and-pagination.md) |
| Agent 与工具界面优化及权限治理（创建 Agent、详情高级化、工具卡片化与权限收紧） | 已完成：新增 Agent 创建全流程与 `/agents/new` 路由；修复 execution_mode 下拉渲染 bug 与布局；升级工具卡片与同步；收紧 PROJECT_RUNTIME_WRITE 排除 EXECUTOR | [项目概览](projects/20260918-agent-tool-ui-overhaul/README.md) |
| 会话标题识别与消息预览优化（手动重命名、消除(无内容)、模板词清洗、最新预览同步与 LLM ✨ 魔法棒智能标题提炼） | 已完成：Phase 1 手动重命名/预览修复/模板词清洗与 Phase 2 基于 DeepSeek create_agent 10字标题 ✨ 魔法棒手动提炼全链路已全量交付通过 | [会话标题与预览优化](projects/20260918-thread-title-and-preview-enhancement/README.md) |
| 新建用户一页流与多项目分配 | 已完成：彻底重构为一页流，支持动态添加/移除多个所属项目并独立指定角色，补充确认密码一致性校验与防自动填充 | [变更记录](../apps/platform-web/docs/changes/20260922-user-create-single-form-multi-project.md) |
| 会话顶栏人机工程排布优化与专注模式沉浸感美化 | 已完成：毛玻璃浮岛胶囊与呼吸指示灯、支持ESC快捷退出、消除重复详情入口收敛至更多操作、项目切换器与最右侧用户账号分区分明 | [变更记录](../apps/platform-web/docs/changes/20260922-chat-topbar-and-focus-mode-ux-refinement.md) |
| 排队补充消息体验深度美化与超时终态自愈 | 已完成：优雅气泡卡片、正文预览、呼吸感状态、未消费一键作为新消息发送/恢复草稿；终态自动断开僵尸流彻底解决假死 | [变更记录](../apps/platform-web/docs/changes/20260922-queued-messages-ux-and-run-timeout-self-healing.md) |
| 敏感工具审批中断状态优化与回合处理指示条精准化 | 已完成：工具触发中断时保持执行/等待审批态，杜绝误报“已中止”；助手回答完毕流结束时瞬时隐藏“处理当前回合”指示条，杜绝延迟逗留 | [变更记录](../apps/platform-web/docs/changes/20260923-tool-interrupt-status-and-live-step-refinement.md) |
| 消息出队与即时提交会话执行态感知优化 | 已完成：综合 isSessionRunning 状态机覆盖出队、提交与乐观消息，0ms 呈现“组织答复”与进度指示条，出队动效与禁用保护 | [变更记录](../apps/platform-web/docs/changes/20260923-queued-message-draining-execution-state.md) |
| 工具卡片区分「正在生成参数」与「执行中」状态及实时字数反馈 | 已完成：基于末尾 AIMessage finish_reason 精准区分 LLM 流式构造长参数与工具真实执行阶段，实时展示 `正在生成参数 · 已生成 X.Xk 字符` 及 `write_file` 流式正文预览 | [变更记录](../apps/platform-web/docs/changes/20260923-tool-streaming-input-vs-execution-state.md) |
| 仿 GPT 聊天界面回合锚定与流式防抖滚动体验 | 已完成：首次提问即时收起欢迎区并置顶展开流式输出；后续提问锚定在视口偏中间位置（32%高度）配合动态收缩底部留白垫片实现零抖动流式生长；支持自由上下滑动与统一底部悬浮回到最新胶囊 | [变更记录](../apps/platform-web/docs/changes/20260924-gpt-style-turn-anchoring-and-scroll-ux.md) |
| 前端对话会话 SWR 缓存与流式长效保活治理 | 部分完成：已有页面KeepAlive、SWR缓存；跨Thread实例保活、SDK恢复、真实普通链路及1/4条短容量已验；8条容量受HTTP/1.1浏览器origin连接槽限制，Final blocked | [原项目记录](projects/20260924-chat-session-cache-and-stream-resumption/README.md) · [SSE专项](projects/20260926-sse-event-contract/README.md) |
| 工作区 HTML 现代化高保真安全预览 | 已完成：SandboxedHtmlFrame 升级为 sandbox="allow-scripts" 且 Origin 锁定为 null，更新安全沙箱徽章文案，单测通过 | [沙箱渲染支持](projects/20261002-workspace-html-sandbox-preview/README.md) |
| 对话输入灵感胶囊栏与微物理撒花小惊喜（ConfettiButton & ComposerSuggestions） | 已完成：实装基于 canvas-confetti 的五彩粒子喷射按钮与动态灵感胶囊栏，支持快捷填入小惊喜、写作、调研、分析等指令模板，与 ChatComposer 双向联动；单测与打包全通过 | [小惊喜迁移专项](projects/20261002-dearflow-surprise-me-feature/README.md) |
| Chat 灵感胶囊栏生命周期与单次会话收起优化 | 已完成：灵感建议胶囊栏仅在空白新会话首次输入前展示，一旦在当前会话点击使用或产生对话后彻底收起，新建空白会话重置展示；单测、类型检查与打包全通过 | [变更记录](../apps/platform-web/docs/changes/20261005-chat-composer-suggestions-lifecycle.md) |
| Agent 回答后推荐问题 | 已完成：全链路前后端闭环。前端实装带 x-project-id 与单例缓存 API、思维链与多模态清洗纯函数、生命周期状态机（KeepAlive 补偿、Stop 抑制、竞态防护）、FollowUpSuggestions 紧凑展示组件与草稿冲突确认弹窗，27 项单测、vue-tsc 与打包全绿 | [项目文档](projects/20261005-agent-followup-suggestions/README.md) · [前端交接](projects/20261005-agent-followup-suggestions/04-platform-web-handoff.md) |
| 长会话断流恢复解耦与历史快照按需懒加载治理 | 已完成：剥离 recoverExpiredStream 对 3.4MB 巨型 history 的阻塞强依赖，改为 state 毫秒级极速自愈 + history 后台静默预热软降级；加固 ChatSession 抽屉懒加载守卫并隔离全局横幅报错；单测全通与打包通过 | [历史懒加载治理专项](projects/20261002-chat-history-lazy-loading-and-timeout-resilience/README.md) |
| Chat 前端对话 Clean Architecture 架构治理与中断/时序缺陷修复 | 已完成：对标谷歌开发范式，拆解上帝组件（ChatSession 净减 923 行），根治手动中断 400 报错与消息队列出队跳顶/并排时序倒挂；102 个测试套件、441 项单测全绿、vue-tsc 0 错误、生产打包通过 | [Chat 干净架构重构](projects/20261004-chat-frontend-clean-architecture-refactor/README.md) |
| 平台用户管理软删除操作与自杀保护交互 | 已完成：操作菜单与详情页实装软删除操作、二次确认弹窗、防自杀禁用与状态筛选；单测及生产构建全绿 | [软删除治理](projects/20261003-platform-user-soft-delete/README.md) |
| Agent 会话停止与状态报告交互 | 已完成：前端 Stop 按钮接入会话级停止控制、幂等重试、状态自愈、报告横幅与抽屉展示、全链路 Playwright E2E 与人工验收通过 | [取消专项](projects/20261007-agent-run-cancellation/README.md) · [前端交接](projects/20261007-agent-run-cancellation/frontend-handoff.md) |

## platform-api

| 功能 | 状态 | 关联文档 |
|---|---|---|
| 模型价格快照与授权用量查询 | 全链路已完成：可空六费率/版本与历史快照、usage-read、Run/Thread GET、安全投影和当前 ACL；隔离链路/Final 完成，未部署现役 | [方案与任务](projects/20261007-agent-usage-cost-governance/03-platform-cost-contract.md) |
| Agent 预算通知与安全错误出口 | 全链路 done：四精确预算安全码、custom/end 标记白名单、tasks.error 清洗、input/update/command/resume 防伪已实装；81 passed/423 subtests，1 skipped；真实 Worker 链路通过，前端联合 F01-F04 全绿，未部署 | [验证](projects/20261007-agent-execution-budget/verification.md) |
| Agent 模型调用稳定性与受管备模型网关 | 已完成：配置持久化、主备候选授权与项目隔离、受管连接与策略快照签名、修复 FastAPI 500 强类型校验异常，全入口受管组装与公开脱敏；定向单测 17 passed，三服务全链路故障注入联验通过，用户人工实测验收合格 | [项目概览](projects/20261006-agent-model-resilience/README.md) · [整体方案](projects/20261006-agent-model-resilience/plan.md) |
| 模型容量治理与上下文维护网关 | 后端已完成：容量 CRUD/受信连接、Context v5、手动维护全入口校验/幂等/ACL、公开脱敏与真实 HTTP/回滚验证通过；前端入口待交接，未部署 | [整体方案](projects/20261006-agent-context-window-governance/plan.md) |
| 会话停止与回执查询 API | 源码及隔离验证完成：cancel/detail/list、当前执行/读取授权、安全 DTO、精确委托/HMAC 和阶段审计；正式 Runtime 配套接入 blocked，未部署现役 | [取消专项](projects/20261007-agent-run-cancellation/README.md) |
| 定时 Agent 任务 API | 后端 done：CRUD、预览、once、pause/resume/manual、私有历史分页与执行拒绝审计；发布包隔离链路通过，未部署现役平台 | [专项](projects/20261005-scheduled-agent-tasks/README.md) |
| 平台用户软删除与生命周期治理 | 已完成：实现 DELETE /api/users/{user_id}，内置防自杀、最后超管保护、唯一项目管理员防孤儿项目三重护栏，释放原始用户名与凭据吊销 | [软删除治理](projects/20261003-platform-user-soft-delete/README.md) |
| 鉴权、项目治理、审计、catalog | 已完成 | `apps/platform-api/docs/handbook/project-handbook.md` |
| 控制面 SQLite → PostgreSQL 迁移 | 已完成：本地 PG 真实切换，20 表一致；浏览器、容器重启、性能复测及双库恢复读回通过 | [迁移专项](projects/20260920-platform-api-postgresql-migration/README.md) · [运维规范](guides/database-operations.md) |
| 重构后文档体系重建 | done：10篇活文档、28文件归档与引用修复，配置/契约核对及33项相关测试通过 | [文档工程](projects/20260910-platform-api-docs-rebuild/README.md) |
| 控制面边界与代码简化重构 | 本阶段后端 done：事务/目录、Docker Showcase、真实备份恢复、混合负载及 20 条公开接口矩阵已验收；前端、整套容器部署与完整 Server 等价性 deferred | `docs/projects/20260910-platform-api-refactor/` |
| 运行时网关（受管模型/工具/prompt 契约下发） | 已完成 | `apps/platform-api/docs/standards/runtime-gateway-interface-standard.md` |
| Agent 回答后推荐问题网关 | 部分完成：配置查询、Thread ACL/模型策略校验、`suggestions-generate` delegation、Runtime best-effort 降级已实现；前端接入与真实 E2E 待完成 | [项目文档](projects/20261005-agent-followup-suggestions/README.md) |
| 中转站维度模型管理、对话高级模型选择器 | 已完成：支持端点防重与单项目默认模型互斥 | [模型防重与单默认策略](../apps/platform-api/docs/changes/20260915-model-uniqueness-and-single-default-policy.md) |
| 运行时网关 Checkpoint 分叉白名单与恢复透传 | 已完成：支持 checkpoint_id/checkpoint_ns 校验与提级转发，拦截恶意字段 | [网关分支支持](../apps/platform-api/docs/changes/20260913-gateway-checkpoint-configurable-whitelist.md) |
| 运行时网关执行配置 SDK thread_id 白名单支持 | 已完成：白名单支持 SDK 自动注入的 thread_id 校验与快照保留，彻底解决浏览器端 400 Unsupported execution config 报错 | [网关 thread_id 支持](../apps/platform-api/docs/changes/20260914-gateway-thread-id-configurable-whitelist.md) |

## runtime-service

| Agent 模型上下文 PII 脱敏（F05） | 已完成：全链路闭环，默认关闭，唯一五检测器/Thread HMAC、四图请求副本/摘要/旁路、失效阻断与策略防注入已验；前端完成 useChatSession 错误消费与草稿保留重构，隐藏误导恢复按钮；Playwright 4 个 E2E 自动化端到端测试与单测全部绿灯通过，未部署现役 | [实施与取舍](projects/20261009-agent-pii-redaction/README.md) · [前端交接](projects/20261009-agent-pii-redaction/frontend-handoff.md) |
| 通用运行准备幂等与有界重试 | 已完成：全链路闭环，两 Agent workspace latch、资源安全修复、单一重试负责人/最多 2 次尝试、部分流保护及安全诊断；Platform Web 准备与重试专用子组件、主 Run 成功琥珀色降级；单测、本机故障恢复及 Playwright 全链路 E2E 验证通过，自主唤醒后置，未部署现役 | [方案与任务](projects/20261007-agent-production-capabilities/README.md) · [前端交接](projects/20261007-agent-production-capabilities/frontend-handoff.md) |
| 通用 Agent Token/Cost 采集与持久化 | 全链路已完成：主/子图、摘要和可信旁路 callback、自有 Run/call ledger、缓存 TTL 与 Decimal 估算；真实隔离 PG/Worker/重启/回退与包含真实百炼大模型的 5 项 Playwright 端到端全部闭环，未部署现役 | [方案与任务](projects/20261007-agent-usage-cost-governance/02-runtime-usage.md) |
| 通用 Agent 执行预算预警与软收尾 | 全链路 done：官方模型限额薄扩展、managed 图余量、幂等提示、四正式 graph 主/子接线和可选 invocation 软计时完成；253 passed，23 真实 Worker 场景通过；原 hard limits/end/error 不变，前端联合 F01-F04 全绿，未部署 | [项目入口](projects/20261007-agent-execution-budget/README.md) · [验证](projects/20261007-agent-execution-budget/verification.md) |
| Agent 模型调用稳定性与中间件容灾降级 | 已完成：显式 transient 错误分类、Retry-After 冷却、ModelResilienceMiddleware 有界重试与自动故障转移（fallback）、单次与总预算控制、流式安全、四组合根与子图装配；单测 43 passed，故障注入死端口实测毫秒级平滑降级至备用模型并流式完成全生命周期，用户人工实测验收合格 | [项目概览](projects/20261006-agent-model-resilience/README.md) · [实现记录](projects/20261006-agent-model-resilience/implementation/01-managed-model-resilience.md) |
| 持久会话停止、inbox 收敛与证据报告 | 源码/唯一post43包版16场景与真实Docker完成，B01解除；固定目标、恢复、inbox及报告通过，B02正式发布指令/正式源锁接入待完成 | [取消专项](projects/20261007-agent-run-cancellation/README.md) |
| Agent 工具调用容错与生产接线 | 已完成：全链路闭环，Runtime/API 选择性错误分类、主子图接线、安全消息与流出口脱敏完成；Platform Web 纯函数摘要、微胶囊 Tag 徽章与格式化代码排版实装，31 项单测全绿，三服务全栈浏览器联合验收 F01-F08 全部通过，未生产部署 | [方案与任务](projects/20261006-agent-tool-error-resilience/README.md) · [前端交接](projects/20261006-agent-tool-error-resilience/frontend-handoff.md) |
| Agent 上下文窗口管理工程化 | 已完成：全链路交付闭环；模型容量配置与展示、预算 guard、隐藏摘要流、根/子图装配、维护副作用隔离、前端整理微胶囊及平滑淡出打断、受控手动整理；隔离真 PG、真实模型质量集及全栈单测/类型/构建全绿，用户人工实测验收通过 | [项目入口](projects/20261006-agent-context-window-governance/README.md) |
| Agent Workspace 执行容错与安全失败报告 | 非前端 done：Runtime/API 共享失败保护、结果未知停止、安全投影与v1诊断，本地/Docker真实Worker不重调度、权限/控制流及重启/回退已验；真实容器并行取消/清理与性能测量补齐，Docker Desktop已关闭。前端交同事，启动retry按批准G1分支B deferred，未部署现役 | [方案与任务](projects/20261007-agent-workspace-resilience/README.md) · [前端报告](projects/20261007-agent-workspace-resilience/frontend-report.md) |
| 定时 Run 执行前聚合授权与无人值守策略 | 后端 done：身份/凭据/项目/Agent/模型/Thread 失效拒绝，审批转失败，原生预览与历史；原post41验收保留，当前依赖锁定post42，未重启现役栈 | [验证](projects/20261005-scheduled-agent-tasks/verification.md) |
| 工作区 HTML 预览 CSP 策略升级与白名单扩充 | 已完成：放行公认安全 CDN（Tailwind CDN / Google Fonts / cdnjs / unpkg / jsdelivr / SVG），严格限制 connect-src https: 阻断内网探测，43 项单测全绿 | [沙箱渲染支持](projects/20261002-workspace-html-sandbox-preview/README.md) |
| DearFlow Agent 接入 Jina Reader 网页深度提取与双通道容灾 | 已完成：Jina Reader API（r.jina.ai）高质量 Markdown 提取上线，首选 Jina、超时/异常自动平滑降级 Tavily Extract，严守 public_url 防御与 SHA256 证据落盘 | [Jina Reader 集成](projects/20261002-dearflow-jina-reader-integration/README.md) |
| DearFlow Agent 单文件交互式创意编程与惊喜作品规范 | 已完成：确立纯原生零外部依赖、Web Audio 音效合成、Canvas/SVG 交互的单文件 HTML 规范，通过 present_artifacts 发布并在 SandboxedHtmlFrame 免刷新实时试玩 | [小惊喜迁移专项](projects/20261002-dearflow-surprise-me-feature/README.md) |
| 数据库访问边界收敛与类型补全 | 已完成：Scope 与 Memory/Skills SQL 抽取；43 项定向通过，全仓两项范围外失败见验证记录 | [精简方案](projects/20260930-runtime-database-repository-refactor/README.md) |
| Runtime 与 GraphHarbor 业务边界解耦 | 部分完成：授权/身份、模型与业务 trace、workspace 及旧 SQL scope 的候选实现已验证；真实 HTTP Thread ACL 与治理浏览器 10 项通过，完整业务链路、文件正向操作与维护切换待验 | [跨仓库协作入口](projects/20260925-runtime-business-boundary-decoupling/README.md) |
| 智能体 execute 与交互终端统一后端 | 已实现：`RUNTIME_BACKEND=local` 供受信任本地开发使用，Showcase、Dear Agent 与终端不依赖 Docker；独立 Runtime 默认 Docker，保留执行审批 | [项目记录](projects/20260923-dear-agent-local-execute/README.md) |
| Runtime 工具治理收敛与平台禁用例外 | 后端/Runtime 开发及本轮验证完成；前端由用户接入，联合发布待执行：Runtime 执行、平台管理禁用例外、Catalog 仅展示，旧功能不兼容 | [专项方案](projects/20260920-runtime-optional-tool-resolution/README.md) |
| Showcase / DearFlow 沙箱文件树与产物预览下载 | 第一阶段后端已完成：文件树、普通文件/产物预览下载、格式扩展与审批；兼容 `/workspace/outputs/` 下 SHA256 命名与普通可读文件名成果识别及动态哈希计算；两服务 HTTP、重启读取与双浏览器静态 HTML 隔离通过 | [实现版接入契约](projects/20260917-showcase-artifact-workspace/05-frontend-handoff.md) · [可读文件名兼容](../apps/runtime-service/docs/changes/20260923-artifact-readable-filenames-support.md) |
| Showcase / DearFlow 人工交互 Terminal | 后端 done：local/Docker PTY、六类鉴权 HTTP、字节重放、输入幂等、配额/过期/清理、审计；前端 deferred，对接设计已交付；local 是宿主开发模式，多 Runtime 进程须粘性路由 | [Terminal 实施与验证](projects/20260917-showcase-artifact-workspace/06-terminal-backend.md) |
| GraphHarbor官方v3对齐与平台迁移 | 后端完成：post30已发布／接入，生命周期／并行中断／恢复版本／步数限制修复，真实研究、文件、子任务、父取消及观测已验；前端交接完成，浏览器与默认切换后置，默认仍v2 | [完成项与代码证据](projects/20260915-graphharbor-v3-alignment/README.md) |
| DearFlowAgent：Deep Agents 能力迁移与生产化 | partial：2026-09-28重审确认主Agent/四模式/研究/文件/审批/只读子Agent及19个上游Skill资源已有；4项未迁入；逐Skill页面、部分供应商和生产Final仍未闭环。当前Skills采用单份内容＋执行快照，Dear复用Chat，记忆接续独立专项；核心抽测28 passed/1 skipped；14效果审计另复现7个可靠性缺口，不能认定同名能力效果等价；新增治理实施范围待评审 | [能力与缺口](projects/20260913-dearflow-agent/11-20260928-capability-reassessment.md) · [效果与可靠性](projects/20260913-dearflow-agent/14-effect-parity-and-reliability.md) · [补齐任务](projects/20260913-dearflow-agent/12-completion-plan.md) · [验证基线](projects/20260913-dearflow-agent/13-verification-baseline.md) |
| Graph 注册、模型参数解析、工具装配 | 已完成 | `apps/runtime-service/docs/standards/*.md` |
| Agent 运行生命周期超时治理 | 已完成：正式 post42 接入、12 组 HTTP 及匹配回退通过；前端 T11 超时治理实装（胶囊展示/停止双通道防死锁）与 T12 端到端用户联调验收通过（含排队提交死锁根除与切换自愈）；服务已安全停止 | [项目记录](projects/20261006-agent-run-timeout-governance/README.md) · [前端交接](projects/20261006-agent-run-timeout-governance/frontend-handoff.md) |
| Agent 回答后推荐问题 one-shot capability | 部分完成：独立 suggestions endpoint、JWT scope 隔离、无工具模型调用、输出清洗和超时/provider 降级已完成；真实模型与三服务 E2E 待验证 | [项目文档](projects/20261005-agent-followup-suggestions/README.md) |
| MCP 接入 | 已完成 | `apps/runtime-service/docs/knowledge/19-runtime-tool-capability-mcp-and-side-effect-design.md` |
| 公共图片工具 Middleware、Showcase 图表 MCP 子智能体与平台图片链路 | 部分完成：G0 契约、Runtime 运输层、Platform API 网关与 Platform Web 前端交互及确定性自动化测试全部通过；待配置真实生产环境模型凭据进行线上 Smoke 联调 | [图片与图表能力方案](projects/20260913-showcase-image-chart-capabilities/README.md) |
| Runtime Service 图片编辑（图生图 `edit_image`）与内容安全审核友好提示 | 已完成：支持基于已有图片执行图像编辑/风格转换，接入 HITL 人工审批，结构化捕获并友好提示 `content_policy_violation` | [图片编辑能力](../apps/runtime-service/docs/changes/20260913-image-editing-capability.md) |
| 图像识别分析工具（`analyze_image`）支持 DeepSeek 官方识图与安全错误摘要 | 已完成：支持 DeepSeek 官方多模态识图（`deepseek-flash`）与通用 `VISION_*` 配置；provider/HTTP 失败对外使用稳定安全摘要，底层敏感正文不进入公开工具消息 | [变更记录](../apps/runtime-service/docs/changes/20261003-vision-deepseek-support.md) · [容错专项](projects/20261006-agent-tool-error-resilience/README.md) |
| Runtime 鉴权、middleware 层、reference agent | 已完成 | `apps/runtime-service/docs/knowledge/28-runtime-refactor-development-plan.md` |
| Runtime Service 开发文档体系（资料导航、开发范式、介入与验证） | 已完成：正式指南位于 `docs/standards/`，以 Showcase Demo 和 tests 为可执行范式 | `apps/runtime-service/docs/standards/README.md` |
| showcase_demo — 教学智能体（工具调用/HITL/子智能体/Todo/Sandbox/Skills） | 部分完成：Docker 正式执行与 LocalShellBackend 本地开发模式均支持；前端后置 | `docs/projects/20260908-showcase-demo/`、`docs/projects/20260917-showcase-local-sandbox/` |

## 仓库级 / 工具链

| 功能 | 状态 | 关联文档 |
|---|---|---|
| Worktree 本地联调资源隔离 | 已完成：首次随机登记端口并稳定复用，独立配置/数据/进程，共享依赖缓存及 E2E 地址接线；继承 app 配置、默认 admin/admin123、首次只读复制基础数据并重加密模型凭据，排除历史/令牌/定时任务；三栈、真实 Worker/Workspace、浏览器登录和重启验收通过 | [规范](standards/worktree-development.md) · [专项](projects/20261010-worktree-local-stack/README.md) |
| Agent通用运行取消与中断闭环 | 已完成：全链路闭环。后端会话停止、回执详情/分页、幂等重试、恢复与审计已闭环；前端完成会话级停止控制、RunStopReportBanner/Details 状态反馈与报告抽屉、队列刷新、多端隔离与防竞态；Playwright E2E/响应式与单元测试全绿 | [方案与任务](projects/20261007-agent-run-cancellation/README.md) · [前端交接](projects/20261007-agent-run-cancellation/frontend-handoff.md) |
| 跨服务规范治理专项群 | 四专项仅验收新Web+新API+当前锁定Runtime/GraphHarbor，不设置旧版兼容或混用测试；错误响应与追踪本期Final已完成，SSE/JWT按各专项状态推进；AI路由按仓库级文档小改动处理 | [总入口](projects/20260922-cross-service-governance/README.md) |
| Agent 通用 Token/Cost 跟踪治理 | 非前端 done：开发/Final/隔离真实链路与冻结契约已交付；既有全量失败已记录，前端同事接续，整项目 partial，未生产部署 | [项目入口](projects/20261007-agent-usage-cost-governance/README.md) |
| Agent 可观测性与追踪补齐 | 已完成：全链路闭环。Runtime/Platform API 完成模型错误分类、安全诊断、启动阶段计时与只读投影；Platform Web 完成独立面板 RunDiagnostics、Zod 白名单、防竞态 useRunDiagnostics、TrajectoryView 常驻入口与多轮 Run 自由切换；单测全绿，浏览器联合验收通过，未部署现役 | [项目入口](projects/20261006-agent-observability-hardening/README.md) · [前端交接](projects/20261006-agent-observability-hardening/frontend-handoff.md) |
| 平台错误响应统一 | 已完成：API公共安全出口、精确上游映射、Web无损解析、Thread对账、真实提交→Run→审计→Langfuse、memory409、SSE编号、peer ACL、workspace正向文件及现役浏览器403均已验；`reference_agent` 的 `runtime.tool.not_allowed` 属既有工具授权基线差异 | [错误响应专项](projects/20260926-error-response-contract/README.md) · [当前标准](standards/error-envelope.md) |
| SSE事件契约治理 | 部分完成：S1—S10已完成，API分帧/安全关闭、Web SDK恢复、410单飞、Workspace线程池、真实普通SDK链路、1/4条短容量及390px视觉检查通过；8条容量受HTTP/1.1浏览器origin连接槽限制，h2/h3和30分钟Final blocked | [SSE专项](projects/20260926-sse-event-contract/README.md) |
| 跨服务追踪传播治理 | 已完成本期验收：T1—T8、V01—V15、R1—R6，API编号/委托/审计精确查询/SSE关闭及真实Run→Langfuse反查均有证据；PG/SQLite性能留实测数据，不设SLO | [追踪专项](projects/20260926-trace-context-propagation/README.md) |
| Delegation JWT契约治理 | 部分完成：J1—J6平台任务、v2双端25项矩阵（含cron-read/write）、签发安全失败及R01—R04真实生命周期有证据；消息内部Run回查由后续专项修复源码，本机测试通过，现役链路未验证；GraphHarbor不改 | [JWT专项](projects/20260926-delegation-jwt-contract/README.md) · [回查修复](projects/20260927-message-run-read-delegation/README.md) |
| AI服务规范路由 | 不再独立立项：后续按仓库级文档小改动补按需阅读规则；本轮未修改AGENTS | [AI路由专项](projects/20260926-ai-service-routing/README.md) |
| 代码规范自动化门禁 | 部分完成：pre-commit 与 CI 变更文件检查已接入；Python 历史格式基线待单独清理 | [项目记录](projects/20260925-code-quality-automation/README.md) |
| 前端代码格式化与 Git Hook 工具链治理 | 已完成：引入 eslint-config-prettier 解耦 ESLint 质量检查与 Prettier 视觉排版，优化 pre-commit 执行链并提供 VSCode 保存即格式化配置 | [变更记录](changes/20260928-code-formatting-toolchain-optimization.md) |
| Python 格式基线清理 | 规划中：约 731 条 Ruff 诊断、297 个文件格式差异待分批清理，本次不实施 | [项目规划](projects/20260925-python-format-baseline-cleanup/README.md) |
| 旧 Testcase 结果服务退役 | 已完成（本机范围）：仓库与本机 Docker 独占资源已清理，备份恢复、浏览器聊天及成果生成/预览/下载通过 | [退役记录](projects/20260924-interaction-data-service-retirement/README.md) |
| 非 Docker 新机开发环境交接 | 文档已收口：通用模板与私有账号映射分开，建库/SCRAM/反向验收连续步骤，补齐运维回执；目标机实际部署待执行 | [部署手册](quickstart/deployment-guide.md) · [运维交接](quickstart/operator-handoff.md) · [收口记录](changes/20260921-native-deployment-operator-handoff.md) |
| 本地 PostgreSQL 密码认证 | 本地已完成：SCRAM、18 项认证检查、9 项兼容检查、重连和回退通过；云端交接更新因 SSH 超时待补 | [认证记录](projects/20260920-local-postgres-password/README.md) |
| 本地项目清理 | 已支持：按 UUID 保留项目；显式历史清理先备份，支持失效令牌、会话/审计及指定测试库；测试退出回收项目 | [运维规范](guides/database-operations.md#本地项目清理) |
| 本地栈进程启停 | 已优化：进程/端口归属隔离；Runtime 单服务重启在停进程前预检，恢复 audience 配置后真实审批通过 | [重启预检修复](changes/20260922-local-stack-runtime-preflight.md) · `docs/changes/20260913-local-stack-real-process-management.md` |
| 改动分级 + Skills 自动触发（plan-project/implement-feature/verify-change） | 已完成；整单任务持续推进至 done 或需用户行动的 blocked，阶段进度写入任务文档且不作为最终交付 | [Harness 完成与汇报规则](changes/20260926-harness-completion-reporting.md) |
| 文档一致性检查（`scripts/check_docs.py`） | 已完成 | `scripts/check_docs.py` |

- Platform API：Agent/Profile ORM 已合并，空库静态基线已通过 SQLite/PostgreSQL 往返验证；完整控制面重构仍为 partial，见 [实现记录](projects/20260910-platform-api-refactor/implementation/08-agent-single-table.md)。

- Agent resync / Operations：后端全链路已退役，20 表及字段收缩和真实 Runtime 验收通过；当前状态见 [11](projects/20260910-platform-api-refactor/implementation/11-backend-closeout.md)。

| Dear Agent P6 记忆与技能治理 | 记忆与外部任务原有验收保留；技能已由当前记录和执行快照替代旧版本治理，见Skills改进项目；前端待接入 | [P6执行包](projects/20260913-dearflow-agent/phases/P6-记忆与技能治理.md) |
| Dear Agent 个人记忆管理与跨会话闭环 | partial：无线程管理、本人队列多源、受信共享检查、180秒提取与召回降级已通过真实HTTP/隔离PG及独立MAOMAO模型测试；完整平台run/SSE、部署和前端联验未完成。前端由同事开发 | [记忆专项与前端交接](projects/20260920-dear-agent-memory/README.md) |

| 多会话流连接与运行缓存治理 | post39 已发布并升级本地 Runtime；后台 SSE 暂停、队列继续执行，三会话切换与权限浏览器验收通过 | [专项](projects/20261005-chat-stream-resource-governance/README.md) |

| Chat 服务端持久消息队列 | 规划完成，治理方案待评审；当前仍由页面消费 localStorage 队列，不支持关闭浏览器后自动提交后续消息 | [专项](projects/20261005-durable-chat-prompt-queue/README.md) |
| 排队提交未决死锁与会话切换自愈 | 已完成；修复 storageKey 漂移遗留幽灵锁，补充历史 Runs 双重自愈与【放弃并恢复草稿】逃生通道 | [变更](apps/platform-web/docs/changes/20261007-prompt-queue-unconfirmed-deadlock-and-switch-healing.md) |
