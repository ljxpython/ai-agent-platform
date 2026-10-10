# Changelog

本项目的变更日志遵循 `docs/guides/commit-and-changelog-guidelines.md` 的规范，并采用 Keep a Changelog 的结构。

## [Unreleased]

### Fixed

- 大工具结果随模型窗口更早外置并可分页回读；父子任务复用调用标识时保留各自原文，长会话减少旧文件写入参数占用的上下文；前端平滑消费 ToolMessage 预览并拦截虚拟路径非法跳转，超长单行与哈希自适应换行，结构化证据来源保真展示。
- 非 Docker 或关闭后台新启动时，Agent 隐藏不可用启动工具；仅确认未登记的环境限制提供短任务前台执行建议，已有任务仍可查询，未知结果不建议重跑。
- **修复模型恢复策略下内部接口 500 序列化报错**：修复 platform-api 内部模型配置接口在开启容灾时嵌套策略字典被 FastAPI 强类型校验拦截抛出 ResponseValidationError 500 的缺陷。
- **修复 Agent 配置页等待时间输入框 step 步长限制**：将等待时间秒数输入框原生 step 改为 1，解决输入 600 秒时浏览器校验拦截的问题；优化保存成功就地高亮微反馈。
- 工作区执行环境不可确认或命令结果未知时明确停止当前运行并返回安全原因，避免重复执行；取消时回收本次执行资源。
- 已知工具调用失败时，Agent 可在当前会话继续处理；错误反馈隐藏供应商和环境细节，权限、工作区及未知程序故障仍明确停止。
- 运行错误通过平台JSON/SSE返回时隐藏模型服务的原始错误正文和堆栈，保留执行状态与正常消息内容。
- 修复聊天消息依赖浏览器页面持续消费的问题，提交后的消息由服务端持久队列按序执行。
- **优化 Agent 单次输出 Token 预算与思维链约束**：解绑 DearFlow Agent 硬编码的 4096 兜底限制，用户留空时默认使用模型自身的最大输出上限；系统提示词增加思考链聚焦与工具调用落地约束，避免长篇推理耗尽 Token 导致工具调用缺失或中断。

### Performance

- 切换页面、刷新或关闭浏览器后，已提交的多轮消息仍可在后台继续执行。

- **修复**：多个对话生成时可连续切换，后台排队消息继续执行，避免长连接堵塞权限同步；运行缓存自动过期并降低长历史回放内存。

> 当前默认归档到下一版本：`v0.5.1`

### Added

- **Agent 支持按部署启用模型上下文 PII 脱敏（F05 全链路闭环）**：以稳定占位符替换外发模型的邮箱、凭据、身份证、信用卡和电话；处理失败阻断本次模型请求；前端完成错误消费与输入草稿/附件保留，隐藏误导恢复按钮；Playwright 4 个 E2E 自动化端到端测试与单测全部通过。默认关闭。
- **Agent 重复工具调用循环保护与诊断闭环（全链路）**：后端共享循环检测中间件识别连续重复只读工具调用，第 3 轮预警、第 5 轮安全硬终止拦截；前端实装 Zod DTO 弹性校验、时序状态机（warning/error）、Subagent 冒泡、报错降级兜底及 RunDiagnostics 循环记录独立卡片；默认关闭（环境变量控制），Playwright 端到端全绿通过并沉淀实景截图。
- **Agent 通用文档读取能力（DOCX/PPTX，全链路闭环）**：Runtime/API/Web 三服务全栈实施交付。同一 parse_document 工具支持 DOCX/PPTX 原字节按需读取、section/slide 定位与有界续读；前端补齐 DOCX/PPTX 扩展名与空 MIME 校验、DOCX 原字节认证下载拦截、Word/PPT 专属徽标、仅支持下载无假预览、工作区不可预览文件优雅降级为“该文件类型不支持在线预览，请下载查看”提示；ToolResult 专用模板实现错误优先绝对高亮、段落与幻灯片语义化展示、续读参数建议及 7 类 warnings 中文脱敏映射；Playwright 真实模型 E2E 3 项全绿，全栈人工浏览器实测验收通过。
- Worktree 支持独立本地联调环境：统一分配端口、隔离数据和进程，依赖通过共享缓存复用。
- 新 Worktree 可继承现有环境配置并复用项目、Agent、模型等基础数据，默认本地账号 admin/admin123，无需重新配置；对话历史和定时任务不复制。
- Agent 新增受管后台工作区任务，可先返回任务编号、继续对话，随后在工作区任务面板查询有界日志或申请取消；完成通知独立执行并计量，会话停止包含后台清理摘要。新提交默认关闭，正式启用与全栈联合交付仍需完成引擎回查门禁。
- **Agent Run 终态通知与失败回调（全栈闭环）**：新增通用终态安全投影、可信来源、持久回调收件、历史 completion、私有通知 feed/read 及 cron 来源回填；GraphHarbor post44 提供原子 webhook delivery、HMAC、重试与重放；前端完成 Pinia 全局通知 Store 单例（15s 指数退避轮询与乐观回滚）、顶栏与 ChatPage 双端通知中心、细粒度优先安全白名单错误码映射、任务执行中离开跳转防护二次确认拦截、以及历史 Run 安全终态诊断卡片；Playwright + Chromium 驱动本地隔离三服务与真实模型问答端到端自动化验证全链路通过。
- **Run Token 额度保护治理与前端闭环（全链路）**：支持单 Run 全树累计 Token，80% 接近预警，达限或不可确认时拒绝新增工作；前端实装 Token 额度水位条（Usage Meter 结合）、在途硬停过渡态防抖、刷新后单次静默对账闭环与 1440/768/390 响应式，全链路真实模型端到端验证通过。
- **Agent 先规划后执行治理（全链路闭环）**：支持单次运行启用规划模式，模型动态裁剪工具列表，仅允许只读调研与计划编写；原生抛出计划审批中断；前端实装输入框“+”号菜单展开与规划胶囊徽章、PlanReview 双重视图、Markdown XSS 伪协议安全清洗、待审态主输入框安全锁定与修改建议反馈交互；支持人工批准、提出修改建议（1-2000 字符）与放弃计划；批准后恢复原图流转并受原有工具审批策略保护。
- **Agent 会话停止与状态报告闭环（全链路）**：支持在请求受理时取消已接受的运行与排队任务、查询停止确认回执、持久进度报告与资源清理状态；前端接入会话级停止控制、RunStopReportBanner/Details 状态反馈与报告抽屉、队列刷新、多端隔离与防竞态；刷新或超时后可继续核实。
- **Agent 运行准备幂等、有界重试与诊断展示（全链路）**：暂时性模型失败最多重试一次，已有流式输出与写操作子任务不自动重放；运行诊断接口提供安全的准备结果和尝试次数摘要；Platform Web 实装准备结果与调用尝试专用展示子组件，主 Run 成功时限流重试降级为琥珀色（Amber）防误报，严格空态隐藏与防注入安全过滤，Playwright 全链路 E2E 验证通过。
- **Agent 模型调用稳定性与容灾降级（全链路）**：Agent 支持配置受管备用模型与调用恢复策略（最大尝试次数、单次/总等待时间上限）；主模型遇到断网、服务宕机、不可用或限流等瞬态故障时，底层中间件自动毫秒级捕获并平滑切换到备用模型输出回答；前端聊天界面呈现备用模型微胶囊 Tag，具备取消停止 4000ms 超时保护。
- **Agent 执行预算告警与停机原因展示（全链路）**：支持模型调用数、图步骤数与时间的阈值接近预警（Amber 提示）和软收尾展示，智能体达到限额正常结束时清晰说明停机原因；子任务与子图告警独立展示不污染主会话；Thread 级额度耗尽时自动引导新建会话或在新分支继续。
- **Agent 用量与成本跟踪面板与 open-swe 运行水位仪表（全栈闭环）**：前端轨迹排障视图新增独立“用量与成本”检查器，精准呈现 Run 级别与 Thread 累计的输入/输出/缓存 Tokens、极小非零成本保护（避免误显免费）与 6 项费率计算的 USD 估算金额；实装 open-swe 风格上下文运行水位进度条（Usage Meter）与模型调用流水明细；支持服务端截断告警；模型编辑器支持 6 项费率 Decimal 安全配置与可逆清空保护；彻底切除前端假数据并完成全栈真实大模型自动化闭环。
- Agent 后端支持按 Run/Thread 查询已采集的输入、输出、缓存 Token 与估算成本；模型目录可配置价格，缺失数据明确显示未知，历史价格保持不变。
- **聊天工具调用错误摘要与排版优化**：前端工具卡片支持结构化错误提取与安全中文摘要显示，增加微胶囊 Tag 恢复建议徽章；展开态排版采用格式化只读代码块，彻底消除原始 JSON 字符串糊脸；工具执行失败后智能体可继续自愈输出后续回答，页面刷新与历史回放保持一致。
- **Agent 运行安全诊断面板与多轮追踪（全链路）**：轨迹视图新增独立“运行诊断”检查器，提供模型调用失败安全分类、启动阶段流水毫秒耗时与一键复制执行关联编号；支持多轮对话与历史会话自动选中最新 Run 并自由切换，具备模型 Fallback 成功绿标防误报。
- **Agent 上下文窗口管理工程化（全链路）**：模型目录支持配置真实上下文容量，长会话自动与受控手动整理复用受权模型连接；前端实装容量编辑展示、整理状态微胶囊（含4秒平滑淡出与打断机制）及手动整理菜单守卫，全链路闭环交付。
- **Agent 运行生命周期超时治理与排队死锁根治（全链路）**：Agent 长任务在每次执行尝试时限前获得软收尾提醒，区分整体硬超时与单次模型错误；前端实装超时警示黄色胶囊、双通道停止确认与输入框阻断守护；治本解决 `storageKey` 漂移导致的排队未决死锁与切屏自愈，端到端验收通过。
- **Agent 回答后推荐问题（全链路）**：Agent 每轮回答完成后智能推荐 1~3 个深度追问胶囊，支持一键点击直接发送或草稿冲突平滑处理（追加/替换），具备零视口突跳微型加载骨架、手动收起与思维链防护。
- 定时 Agent 任务后端支持一次性/周期规则、预览、暂停恢复、手动运行和分页历史；执行前权限失效或需要人工审批时明确失败并留痕。
- **定时 Agent 任务前端管理界面**：新增项目级定时任务管理页面，支持现代化卡片网格列表、双栏创建/编辑抽屉、常用周期（每小时/每天/每周/每月）预设联动与服务端排期实时预测、执行历史按需懒加载及立即运行幂等防重。

- **平台用户软删除与生命周期治理**：全局用户管理（`/workspace/users`）及用户详情页支持软删除操作，释放用户名与邮箱，吊销登录凭据并退出项目关联；内置三重安全护栏，严禁删除操作者账号自身、保护系统最后一个超级管理员以及防止产生无管理员孤儿项目。
- **灵感建议胶囊与“小惊喜”创意微动效**：聊天输入框顶部新增常驻/按需灵感胶囊栏（`ComposerSuggestions.vue`），支持一键填充深度写作、敏捷调研、数据洞察及“给我一个小惊喜”；封装五彩物理纸屑微动效（`ConfettiButton.vue`），提供极具情绪价值与仪式感的点击反馈。
- **DearFlow Agent 纯原生创意工坊**：智能体提示词确立单文件自包含、零外部依赖的交互式趣味作品生成规范（原生 Web Audio 动态声效合成 + Canvas/SVG 视觉），并在沙箱工作区中实现 100% 免刷新高保真试玩。

### Changed

- Agent 复用消息中的附件引用，不再每轮将线程全部上传文件注入系统提示，减少长会话上下文占用。
- **LangGraph Run 默认事件流版本统一为 v3**：新建运行和默认恢复请求使用 v3 事件投影，同时保留显式 v2 与历史 v2 Run 兼容。
- **前端 v3 状态投影防洪与版本回退支持**：前端 `useTranscriptMessages` 增加中间 values 帧防洪比对机制，消除长会话频繁深拷贝导致的掉帧；`run-actions` 开放 `version` 白名单参数，支持显式传递 `v2` 进行回滚或调试。
- **长会话断流自愈与历史快照按需懒加载**：将长会话历史快照（Checkpoints History）由全量同步阻塞加载改造为侧边抽屉展开时按需懒加载；会话断流恢复（`recoverExpiredStream`）彻底与巨型快照解耦，仅依赖毫秒级当前状态（`service.state`）实现秒级极速自愈。

### Fixed

- **平台权限误失效提示治理**：区分权限同步暂时不可用与真实撤权，减少切屏、网络抖动和单个会话拒绝造成的整页拦截；认证服务短暂故障不再误清登录状态。

- **多会话切换切回假死死锁、空白消息水合缺失与投递报错误伤**：修复在连续追问后切到其他会话再切回时，前端状态机未及时收敛导致的假死、新输入消息进入待执行队列后死锁发不出、AI 最新落盘回复显示为空白头像、以及后台轮询偶发报错污染本地队列横幅的问题；实现终态流式与动作强制收敛、切回轻量落盘水合、队列自动消费与报错展示隔离。
- **会话交互状态机加固与思维链流式体验优化**：修复切屏或重聚焦唤醒时因瞬态并发刷新偶发误判权限失效被踢出工作区的问题；修复空消息队列下异常弹出“排队补充消息 0”黄色警告横条的问题；修复在触发人工澄清中断时底部仍冲突显示“正在处理当前回合”的问题；增强深度推理模型（DeepSeek 等）的长思维链流式实时感知，彻底解决首轮思考卡顿白屏后突兀弹出的交互问题。
- **长会话 504 超时死锁与错误污染修复**：修复在 100+ 步复杂长会话中，因 LangGraph `/threads/{id}/history` 巨型快照反序列化导致网关超时（504），进而引发前端断流恢复失败并误弹全局红色断线横幅的问题；彻底隔离快照查询错误，保障主会话平稳自愈。
- 修复工作区 HTML 预览中 Tailwind CSS、Google Fonts 及常见现代化前端 CDN 样式完全丢失退化为无样式文本的问题；升级前端沙箱为独立脚本沙箱（零同源凭据）并放宽后端安全 CSP 白名单。
- 修复 Workflow Demo 获取平台模型配置时缺少请求签名的问题；模型引用配置异常时明确报错，保留人工审批恢复后的模型引用更新。

## [v0.5.0] - 2026-09-29

### Added

- **定位升级与企业级架构图解**：全面重构为“基于 LangGraph 生态的企业级 AI Agent 二开平台底座”，发布 3 套完整的 Archify 2K 全景图（系统总览、执行时序、二开扩展点）与交互式网页系统。
- **生产级标杆智能体 `DeerFlow Agent`**：深度融合 `open-swe`、`deepagents` 与 `deer-flow` 核心工程思想，实装全流程多模式动态切换（Research / Coding / Planning）、跨会话长期记忆闭环引擎（Memory Pipeline）、隔离沙箱 Workspace（文件树/产物下载）与真实 PTY 交互式终端。
- **技能矩阵与扩展协议**：全面实装智能体技能包（Skills）机制与标准 MCP（Model Context Protocol）扩展服务接入通道。
- **开源核心致谢置顶**：确立并置顶以 `open-swe`、`deepagents`、`deer-flow` 为核心的架构支柱与技术传承。

### Changed

- **文档与二开体系收敛**：重构 `README.md` 与 `README.en.md`，彻底砍掉内部 AI 工作流水账与过期测试场景描述；建立标准化二开代码扩展速查表。
- **文档路径正规化**：将分散的部署与运维指引统一收敛至 `docs/guides/`，清除所有历史废弃坏链。
- **徽章体系升级**：首页 Header 强化呈现 LangGraph、GraphHarbor、FastAPI、Vue3、MCP、Skills、Memory、HITL 八大核心技术资产。

### Fixed

- **图解截断修复**：消灭早期无头截图中存在的视口截断缺陷，实现 100% 全要素高保真渲染。
- **双语对齐保障**：实现中英文 README 核心技术口径与工程基线的严格同步。

## [v0.4.0] - 2026-07-28

### Added

- 新增正式聊天 v2 运行链路、独立调试工作台和运行级模型、工具、提示词配置入口
- 新增服务端生成的可信身份与项目上下文契约，并将其传递到运行时请求解析链路
- 新增运行时委派、平台认证、聊天状态映射和调试接口的覆盖测试

### Changed

- 将正式聊天收敛到 LangChain 流式运行时状态，统一线程续接、消息展示、工具调用和中断交互
- 将运行时模型、工具和 prompt 配置迁移到受管服务端契约，减少前端手工推导与隐式上下文注入
- 升级前端聊天相关依赖，并将调试能力从正式聊天页面拆分为独立工作台

### Fixed

- 修复运行时委派未配置时聊天请求失败的问题，提供兼容的受管委派路径
- 修复发送消息后页面短暂闪烁以及线程目标恢复、搜索参数和工具结果展示的回归问题

## [v0.3.1] - 2026-07-20

### Added

- 新增 repo-local `lightrag-service`，提供 HTTP 与项目级 MCP 知识链路，并接入默认本地启动、健康检查和停止脚本
- 新增 OpenSpec 项目配置、官方 Codex Skills 与显式 `route-project-change` Skill，为持久 B2/B3 变更提供 proposal、spec、tasks、verification、sync 和 archive 生命周期
- 新增跨平台文档与变更状态检查器，并在 CI 中执行 OpenSpec strict validation 和 Harness 闭环门禁

### Changed

- 将活动 Harness helper host 从 `.omx` 迁移到 `.harness`，保留 `.omx` 作为历史和过渡面
- 收敛 B1/B2/B3 路由、B3 实施前审批、持久验证证据、accepted spec sync 和 archive 规则
- 更新本地 demo 依赖顺序、当前文档入口、前端 leaf playbook 和 Harness 人类使用指南

### Fixed

- 修复本地 demo 启动时知识服务与依赖项未完整拉起的问题
- 修复活动计划、OpenSpec change 和验证证据可能形成重复真相源或绕过完成门禁的问题
- 修复 Graphify、CodeGraph 和本机数据库等生成物可能误入版本控制的问题

## [v0.3.0] - 2026-04-23

### Added

- 新增 `v0.3.0` 发版草案与执行清单，固定“平台正式宿主命名收口版”的发布口径

### Changed

- 将当前正式平台宿主从 `platform-api-v2` / `platform-web-vue` 收口为 `platform-api` / `platform-web`
- 将仓库级 current-standard、默认本地部署 contract、CI、Docker Compose、Nginx upstream、helper scripts 与当前 README/leaf docs 统一到新的正式名称
- 将 `apps/platform-api-v2` / `apps/platform-web-vue` 目录整体迁移到 `apps/platform-api` / `apps/platform-web`，并同步更新前后端 env 前缀、包名、构建路径与当前主链说明
- 将 runtime / interaction-data / runtime-web 等当前文档中的正式链路说明改为 `platform-web -> platform-api -> runtime-service`

### Fixed

- 修复活动面里仍残留旧正式宿主命名导致的 CI、脚本、文档与当前标准口径不一致问题
- 修复本地 demo 脚本、Docker stack 与前端环境变量在新正式命名下的路径/服务名对齐问题
- 修复当前主链文档仍把 `platform-api-v2` / `platform-web-vue` 视作正式宿主的漂移

## [v0.2.0] - 2026-04-22

### Added

- 新增 `apps/runtime-service` 单应用容器化交付面，补齐受管 `Dockerfile`、`docker-compose.runtime-service.yml` 与 deploy 级 env 示例
- 新增整仓 Docker Compose 交付面，覆盖无 Nginx / 带 Nginx 两种部署拓扑、共享 Postgres 初始化脚本与容器地址填写指南
- 新增容器化从零部署指南、容器更新 runbook 与 deploy 总入口文档，形成 operator 视角的 bring-up / recreate / rollback 路径
- 新增 `platform-web-vue` 针对 no-nginx 场景的 API base 回归测试，锁定显式 `localhost:2142` 不再被错误改写为同源 `/api`

### Changed

- 将根目录 README、docs 总入口和部署文档收敛到 Docker 使用路径，补充单应用 runtime、整仓 compose 无 Nginx、整仓 compose 带 Nginx 3 种启动命令
- 将容器化基线中的共享多模态附件解析模型默认值收敛为 `MULTIMODAL_PARSER_MODEL_ID=gpt_5.4-ccr`
- 让 `runtime-service` 的 `test_case_service_v2` 支持从 env fallback 读取私有 knowledge MCP 参数与远端持久化目标配置
- 对 `interaction-data-service`、`platform-web-vue`、`runtime-service` 的 Docker build 上下文做瘦身，补齐 `.dockerignore` 与生产容器入口配置
- 将 `interaction-data-service` 容器的健康检查从 `curl` 改成 Python 内建探活，移除镜像里仅为 healthcheck 引入的系统包依赖

### Fixed

- 修复 no-nginx 容器前端在浏览器端把显式 `http://localhost:2142` 又改写回同源 `/api`，导致登录命中 `3000/api/identity/session` 返回 `404`
- 修复本地 `localhost:3000` 与 `127.0.0.1:3000` 访问口径不一致引发的 CORS 预检失败问题
- 修复 `platform-api-v2-worker` 未同步主服务 upstream 配置，导致 `runtime.models.refresh`、`runtime.tools.refresh` 等异步 operation 在 worker 中报 `LangGraph upstream is unavailable`
- 修复 `runtime-service` 容器未注入 `INTERACTION_DATA_SERVICE_URL`，导致 `test_case_service_v2` 的 `persist_test_case_results` 返回 `skipped_remote_not_configured`
- 修复 `platform-api-v2` 的 operation 统计在 PostgreSQL 下仍使用 SQLite `julianday()` 语法的问题

## [v0.1.2] - 2026-04-21

### Added

- 新增项目级知识工作区主线，补齐 `documents / retrieval / graph / settings` 页面、上传对话框与查询设置能力
- 新增 `platform-api-v2` 项目知识控制面链路，承接项目知识路由、权限、上游代理与相关集成测试
- 新增 `runtime-service` 的 `test_case_service_v2` graph、知识查询守卫、文档持久化与相关技能文档
- 新增仓库级 AI 执行系统 current-standard、使用指南、leaf resolver 与 `.omx/specs` helper artifacts

### Changed

- 收紧 `chat` / `sql-agent` / `testcase` 工作区布局，让目标上下文、输入区、消息区和 compact / focus 模式更聚焦主会话
- 将知识工作区重新对齐到共享前端壳、列表页范式和 metadata-aware 检索路径，减少页面结构漂移与滚动裁切
- 更新 README、部署/开发文档与知识设计文档，统一 AI 任务路由、发布入口和项目知识主线叙事
- 让共享多模态解析默认值支持环境配置，同时保留显式覆盖与运行时覆盖路径

### Fixed

- 修复 testcase 文档详情面板在旧数据形态下无法正常预览与原始下载的问题
- 修复项目知识设置页尾部斜杠请求导致的代理跳转与鉴权丢失问题
- 修复 compact / focus 模式下 chat 全局状态条、跟随滚动与局部布局噪音问题
- 修复若干知识页面滚动裁切、工作区内容溢出与上传元数据校验体验问题

## [v0.1.1] - 2026-04-11

### Added

- 新增 `platform-api-v2` 控制面主线，补齐 runtime gateway、用户平台角色、testcase 管理与多类治理模块
- 新增 `runtime-service` 静态 graph 标准化骨架与 harness 开发范式说明，统一 assistant / deepagent / testcase 等运行时主线
- 新增 `platform-web-vue` 的系统治理、工作区导航、chat / sql-agent / testcase / threads 等演示主线路径补强

### Changed

- 统一 `platform-web-vue` 的品牌口径、侧边栏分组、顶栏下拉层、项目上下文与运行时目录刷新体验
- 将旧 `platform-api` / `platform-web` 主线收口到归档或兼容语境，正式入口切换为 `platform-api-v2` 与 `platform-web-vue`
- 重写根级文档、app docs 与正式架构图，使仓库叙事统一到 `AI Harness` 总哲学与当前正式链路

### Fixed

- 修复 chat 场景中的流式运行时契约对齐问题，稳定会话续接、工具结果展示与阅读跟随体验
- 修复 `platform-web-vue` 中的会话过期跳转、图表工具结果渲染与若干工作区交互收口问题
- 修复文档中仍把历史控制面 / 历史前端宿主当成当前默认实现的漂移问题

## [v0.1.0] - 2026-04-05

### Added

- 新增 `apps/platform-web-vue` 作为新的前端工作台宿主，承接迁移后的正式工作区布局与页面主线
- 新增 `chat / sql-agent / testcase / threads` 主线可演示能力，覆盖 agent 工作台、线程懒加载与文档链路
- 新增 `Resources / Playbook` 作为前端开发范式、页面母版与模板资源沉淀入口
- 新增演示环境、烟测、验收与汇报相关文档，固定 `Agent 工作台可演示版` 发版口径

### Changed

- 统一顶栏系统区交互，包括项目切换、语言切换、公告中心与用户菜单
- 统一列表页母版能力，包括 `DataTable / Pagination / 列设置 / 筛选设置 / ActionMenu / BulkActionsBar`
- 统一 `chat` 与 `sql-agent` 的执行态工作台、消息级操作、上下文抽屉与执行面板交互
- 对 dark mode、移动端与大屏布局做了专项收敛，修正关键页面占满、溢出与视觉一致性问题

### Fixed

- 修复线程页一次性展开所有 thread 内容导致的性能与可读性问题
- 修复 testcase 文档在线预览与原始下载主链路
- 修复 chat 中 retry / edit 后的分支挂载、默认最新分支与历史交互问题
- 修复多处顶栏、下拉、分页、筛选器与 tooltip 的交互一致性问题
