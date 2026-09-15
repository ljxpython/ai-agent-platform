# 功能现状总览

全仓库当前功能清单，按服务分组。每次 `apps/{app}/docs/changes/`、根目录 `docs/changes/` 或
`docs/projects/` 落一笔新记录时，同步在这里新增一行或更新对应行的状态，不需要每次改动都重写整份文档。

状态取值：规划中 / 进行中 / 已完成 / 部分完成（说明缺什么）。

## platform-web

| 功能 | 状态 | 关联文档 |
|---|---|---|
| Dear Agent 专属前端 | 进行中：F1/P1 已完成（专属模块 `src/modules/dear-agent/`、独立路由、澄清表单交互卡片、审批面板与输入锁定已落地并通过 50 套全量回归）；F2—F7 后续推进 | [前端交接与实施](projects/20260913-dearflow-agent/frontend-handoff.md) |
| 正式聊天 v2（LangChain 流式运行时、线程续接、工具调用与中断展示） | 已重写：官方 SDK 会话、按轮渲染、多 ID 审批、历史分支及移动工作区；最终验收见项目记录 | [Chat 重构](projects/20260910-platform-web-refactor/04-chat-session-and-interaction.md) |
| 运行级调试配置 | 已完成：公开 Context/config 白名单、schema 参数校验；不保留旧提示词覆盖 | [接入契约](projects/20260910-platform-web-refactor/03-api-contracts.md) |
| 控制面核心页面（overview/projects/users/agents/me/security/audit） | 已迁移：Agent/模型新契约、统一权限导航、列表四态；全路由浏览器验收见项目记录 | [现状与目标架构](projects/20260910-platform-web-refactor/02-architecture-and-ui.md) |
| 旧 Chat 视觉与统一 Agent 入口 | 部分完成：Agent 归一已交付；旧工作台组件已直接取回；37 项定向测试及三尺寸回归通过；摘要数据与部分专项验收仍待补齐 | [09 还原功能核对](projects/20260910-platform-web-refactor/09-chat-workbench-restoration-audit.md) |
| Platform Web 架构与 Agent Chat 重构 | 01—07 非后置范围已完成；旧展示组件已取回，专项验收边界见 09；双浏览器入队/完整文件与 Skills API/PTY 后置 | [项目概览](projects/20260910-platform-web-refactor/README.md) |
| 运行中补充消息（多端入口、Runtime 队列与 Middleware） | 已实现：根模型注入、持久回执/恢复、权限复核与 Web 重试；网络取消/移动回归通过，双浏览器后置，GraphHarbor post27 发布包复验通过 | [队列与消费设计](projects/20260910-platform-web-refactor/07-message-queue-and-middleware.md) |
| Chat 流式输出标准化与 open-swe 架构对齐 | 已完成：流式管道、打字机光标、平滑滚底、Open SWE 子智能体卡片特化与微型居中未读胶囊已全量交付通过 | [流式标准化](projects/20260912-chat-streaming-standardization/README.md) |
| 任务进度条收起与时间旅行动作标题精准化 | 已完成：任务胶囊可随时 ✕ 收起且折叠为右上角微型恢复徽标彻底消除正文遮挡，时间旅行历史基于当前 Step 动作精准呈现标题 | [任务胶囊与时间旅行优化](../apps/platform-web/docs/changes/20260912-task-pill-dismiss-and-history-preview.md) |
| 历史关键节点过滤、多步长翻页与消息编辑分叉 | 已完成：白名单精准识别业务里程碑并剔除无新动作系统流转帧；支持 +20/+50/+100 快速翻页；编辑消息即时响应与本地内存回溯杜绝卡死 | [关键节点与编辑分叉修复](../apps/platform-web/docs/changes/20260912-history-milestone-filter-and-edit-branch-fix.md) |
| 时间旅行抽屉角色筛选与历史发问分叉 | 已完成：抽屉按用户/Agent/工具多维筛选与统计，可与关键节点组合，秒级定位发问检查点并分叉重新执行 | [时间旅行角色筛选](../apps/platform-web/docs/changes/20260913-history-checkpoint-role-filter.md) |
| 前端对话页面美化与交互体验重构 | 已完成：Hover 浮动工具栏、复制反馈、高质感 Agent 胶囊选择器、Agent Hero 欢迎看板与快捷 Prompt、代码 Diff/终端卡片及输入框光晕微交互已全量交付通过 | [对话页面美化](projects/20260913-chat-ui-aesthetic-optimization/README.md) |
| 对话正文与工具卡片工作区图片自动解析与渲染 | 已完成：聊天正文自动扫描工作区图片路径并派生渲染大图卡片，支持放大与下载；工具卡片中文别名与产物感知增强 | [图片自动渲染](../apps/platform-web/docs/changes/20260913-workspace-image-auto-render.md) |
| DeepSeek Harness 轨迹视图迁移（双视图切换、事件流水账与 Master-Detail 检查器） | 已完成：支持对话/轨迹模式随时切换；按轮次/步数分组呈现思考链、工具入参与返回、错误高亮及 Raw JSON 深度排障；适配层带安全降级 | [轨迹视图迁移](projects/20260914-deepseek-trajectory-migration/README.md) |
| 轨迹排障 DevTools 体验深度对齐（三层甘特时间线、树状贯穿线、紧凑单行表格与 Summary 内联预览） | 已完成：多通道横向甘特条（Input/Model/Tools）、Turn Rail 树状节点与连线、微型彩色徽章、左侧 3px 指示竖条、实时搜索与性能指标底栏 | [轨迹 DevTools 体验对齐](../apps/platform-web/docs/changes/20260914-trajectory-devtools-layout-alignment.md) |
| 前端主对话流极简化与高级感对齐（无界通透主视窗、灰色原子 Think 条、无头像用户气泡与工业指标底栏） | 已完成：去除卡片套娃大框、Think 改为极简灰色单行、去头像气泡、下划线视图 Tab 与性能小字底栏 | [主对话流极简对齐](../apps/platform-web/docs/changes/20260914-chat-ui-minimalist-deepseek-alignment.md) |
| 对话工作台通透无界大视野与布局重构（单层沉浸顶栏、消除底部死留白、自适应平滑滚动与侧栏一键折叠） | 已完成：消灭双 Header 套娃释放 56px 高度、下沉项目与用户切换器、消灭底部大留白、移除会话侧栏分页器并常驻一键折叠 | [通透无界布局重构](../apps/platform-web/docs/changes/20260914-chat-workspace-borderless-layout-redesign.md) |
| 轨迹排障三合一控制器、微交互与工业级指标栏对齐（Duration/Turns/Calls、甘特 Tooltip、概览大字与圆球发送气泡） | 已完成：实装 Duration 真实耗时模式、Turns 批量折叠、Calls 工具隐藏、时间轴色块 hover 黑底白字气泡、顶栏 X 轮 Y 步 Z 工具统揽、完整 LLM/TTFT/tok/s 指标栏及圆球向上箭头微交互 | [控制器与指标栏对齐](../apps/platform-web/docs/changes/20260914-trajectory-controllers-and-metrics-strip-alignment.md) |



## platform-api

| 功能 | 状态 | 关联文档 |
|---|---|---|
| 鉴权、项目治理、审计、catalog | 已完成 | `apps/platform-api/docs/handbook/project-handbook.md` |
| 重构后文档体系重建 | done：10篇活文档、28文件归档与引用修复，配置/契约核对及33项相关测试通过 | [文档工程](projects/20260910-platform-api-docs-rebuild/README.md) |
| 控制面边界与代码简化重构 | 本阶段后端 done：事务/目录、Docker Showcase、真实备份恢复、混合负载及 20 条公开接口矩阵已验收；前端、整套容器部署与完整 Server 等价性 deferred | `docs/projects/20260910-platform-api-refactor/` |
| 运行时网关（受管模型/工具/prompt 契约下发） | 已完成 | `apps/platform-api/docs/standards/runtime-gateway-interface-standard.md` |
| 中转站维度模型管理、对话高级模型选择器 | 已完成：支持端点防重与单项目默认模型互斥 | [模型防重与单默认策略](../apps/platform-api/docs/changes/20260915-model-uniqueness-and-single-default-policy.md) |
| 运行时网关 Checkpoint 分叉白名单与恢复透传 | 已完成：支持 checkpoint_id/checkpoint_ns 校验与提级转发，拦截恶意字段 | [网关分支支持](../apps/platform-api/docs/changes/20260913-gateway-checkpoint-configurable-whitelist.md) |
| 运行时网关执行配置 SDK thread_id 白名单支持 | 已完成：白名单支持 SDK 自动注入的 thread_id 校验与快照保留，彻底解决浏览器端 400 Unsupported execution config 报错 | [网关 thread_id 支持](../apps/platform-api/docs/changes/20260914-gateway-thread-id-configurable-whitelist.md) |

## runtime-service

| 功能 | 状态 | 关联文档 |
|---|---|---|
| DearFlowAgent：Deep Agents 能力迁移与生产化 | 部分完成：P0/P1 后端 done，P2 已有研究闭环；P3 并发／只读隔离／事件关联／usage回归39项通过，受信追踪字段丢失已修复，真实父取消通过；双子任务完整运行超时、外部观测未验，前端只交接，23 Skills与生产联合验收未完成 | [P3 完成项、代码与测试](projects/20260913-dearflow-agent/phases/P3-子%20Agent%20展示与观测.md) |
| Graph 注册、模型参数解析、工具装配 | 已完成 | `apps/runtime-service/docs/standards/*.md` |
| MCP 接入 | 已完成 | `apps/runtime-service/docs/knowledge/19-runtime-tool-capability-mcp-and-side-effect-design.md` |
| 公共图片工具 Middleware、Showcase 图表 MCP 子智能体与平台图片链路 | 部分完成：G0 契约、Runtime 运输层、Platform API 网关与 Platform Web 前端交互及确定性自动化测试全部通过；待配置真实生产环境模型凭据进行线上 Smoke 联调 | [图片与图表能力方案](projects/20260913-showcase-image-chart-capabilities/README.md) |
| Runtime Service 图片编辑（图生图 `edit_image`）与内容安全审核友好提示 | 已完成：支持基于已有图片执行图像编辑/风格转换，接入 HITL 人工审批，结构化捕获并友好提示 `content_policy_violation` | [图片编辑能力](../apps/runtime-service/docs/changes/20260913-image-editing-capability.md) |
| Runtime 鉴权、middleware 层、reference agent | 已完成 | `apps/runtime-service/docs/knowledge/28-runtime-refactor-development-plan.md` |
| Runtime Service 开发文档体系（资料导航、开发范式、介入与验证） | 已完成：正式指南位于 `docs/standards/`，以 Showcase Demo 和 tests 为可执行范式 | `apps/runtime-service/docs/standards/README.md` |
| showcase_demo — 教学智能体（工具调用/HITL/子智能体/Todo/Sandbox/Skills） | 部分完成：post26 平台后端真实联调、审批重启恢复与报表 43.50 已验收；前端后置 | `docs/projects/20260908-showcase-demo/` |

## interaction-data-service

| 功能 | 状态 | 关联文档 |
|---|---|---|
| 结果域落库与查询 | 已完成 | `apps/interaction-data-service/docs/service-design.md` |

## 仓库级 / 工具链

| 功能 | 状态 | 关联文档 |
| 本地栈进程启停 | 已优化：真实进程与端口归属识别、孤儿 worker 深度清理、端口占用自动回收与外部进程安全隔离 | `docs/changes/20260913-local-stack-real-process-management.md` |
| 改动分级 + Skills 自动触发（plan-project/implement-feature/verify-change） | 已完成 | `AGENTS.md` |
| 文档一致性检查（`scripts/check_docs.py`） | 已完成 | `scripts/check_docs.py` |

- Platform API：Agent/Profile ORM 已合并，空库静态基线已通过 SQLite/PostgreSQL 往返验证；完整控制面重构仍为 partial，见 [实现记录](projects/20260910-platform-api-refactor/implementation/08-agent-single-table.md)。

- Agent resync / Operations：后端全链路已退役，20 表及字段收缩和真实 Runtime 验收通过；当前状态见 [11](projects/20260910-platform-api-refactor/implementation/11-backend-closeout.md)。
