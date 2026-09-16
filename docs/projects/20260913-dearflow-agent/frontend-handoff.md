# Dear Agent 前端开发与人工验收交接

更新：2026-09-16。**已完成前端施工排期规划与 5 处关键设计修正，待排期落地编码与逐批次验收。**
后端接口与运行时已就绪，前端将按 W1~W5 阶段节奏依次推进，每个任务在文档中带 `[ ]` / `[x]` 标记实时跟踪进度。

## 1. 如何阅读与执行

前端负责人按本文 **范围 → 页面 → 对接 → 施工顺序（含可勾选排期矩阵） → 验收 Case** 执行，不需要按 P0—P7 来回找需求。项目决策见 [README](README.md)，23 项迁移事实源见 [07 台账](07-skills-migration.md)，接口设计见 [08](08-web-and-platform-contracts.md)。本文汇总前端所需事实；出现差异时核对列出的实现代码并回填，不自行假设不存在的 API。

- Dear 业务目录：`apps/platform-web/src/modules/dear-agent/`。**已经复制过 Chat 基线，不重新复制**，不与 `modules/chat/` 双向 import，不修改通用 Chat 业务实现。
- 网络请求放 `apps/platform-web/src/services/`；治理请求可放其 `dear-agent/` 子目录。复用鉴权、HTTP、官方 SDK，不在业务目录另造客户端/事件系统。
- 前端不直连 Runtime/数据库，不计算受信签名。GraphHarbor 只负责通用运行/持久化/事件，Dear 业务仍在 Runtime `services/dearflow_agent/`。
- 遵守 `apps/platform-web/docs/frontend-development-playbook.md` 和 `control-plane-page-standard.md`。先交付可用闭环，再优化视觉；不创建后置能力空页面。

## 2. 本次迁移能力总览

### 2.1 底座与通用能力

| 能力 | 后端已交付范围 | 限制/未完成 | 前端要接入 |
|---|---|---|---|
| Agent 底座 | DeepAgents/LangGraph 组合，工具/技能/中间件/工作区，无 deerflow-harness 运行依赖 | 不是 DeerFlow 全套服务复制 | 独立 Dear 入口、官方 SDK 会话 |
| 四模式 | flash/standard/pro/ultra，同一 Agent 配置组合 | Flash 推理控制取决于模型支持，不是四套工作流 | 默认 Standard、模式与实际请求一致 |
| 规划/研究/证据 | 规划、搜索、正文抓取、只读 MCP、证据引用 | 外部限流/不可达不保证成功；不做浏览器操作 | 规划轨迹、来源层级、截断/失败 |
| 人机交互 | 官方 interrupt/HITL/resume，七类澄清，approve/edit/reject | 不使用 DeerFlow 自定义提问终止协议 | 表单/审批/刷新恢复，阻止普通发送绕过 |
| 运行/子 Agent | 根/子生命周期、namespace/cause、父取消、已有消息 usage | 独立 child Run、单子取消、完整独立计费和额外结果验证后置 | 修复关联、真实终态、用量缺失显示未知 |
| 文件/执行/交付 | 通用引用、Docker 执行、不可变成果、授权下载；消除 Showcase 专属附件限制 | 无任意宿主路径下载、无 Office 在线编辑；输入与输出不同 | 上传/审批/下载，来源与成果分开 |
| 补充消息 | 持久化队列及 queued/claimed/consumed/rejected/not_consumed | 202 不是模型已消费 | 区分普通发送、补充要求、中断恢复 |
| 长期记忆 | 本人/项目作用域、来源、revision CAS、候选、删除/清空/恢复、到期/容量/上下文预算 | 自动候选默认关闭；词项匹配，非向量语义检索 | 真记忆页，替换误导性占位 |
| 技能治理 | ZIP 候选、静态审查、隔离文本评估、启用/回退/撤销、线程版本冻结 | 无完整脚本/浏览器基准、触发优化或全局安装 | 候选与启用分开，证据/版本/状态 |
| 图片防重提 | 持久化幂等；真实 SDK→HTTP 回执丢失→PG unknown→跨 Run 重提只接单一次已有证据 | 换 key 是新请求；不保证退款 | unknown 不显示成功、不自动重购 |
| 运维/恢复 | 本机恢复、数据库备份恢复、权限/故障验证已有记录 | Goal 自动续跑、定时任务、完整长 MCP 后置；多机压测按用户决定不做；P7 仍有门禁 | 页面断线恢复/权限/错误验收，不以接口通过替代 |

### 2.2 全部 23 个 Skills 后端交付台账

“通过”只指下列**后端范围**；所有页面 Case 均未执行。资源位于 `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/<slug>/`；文件存在不等于本次具备工具权限/供应商配置。

| 编号/slug | 已交付与后端证据结论 | 缺口 | 页面 Case |
|---|---|---|---|
| K01 deep-research | 搜索→正文证据→报告真实通过 | 页面后置 | S01 |
| K02 academic-paper-review | PDF/文本论文评审通过 | 扫描 PDF OCR 未做 | S02/E06 |
| K03 github-deep-research | 公共仓库查询与组合测试通过 | 真实 GitHub 匿名403配额阻塞，未完整复验；私库不支持 | S03/E05 |
| K04 consulting-analysis | 咨询报告范围通过 | 完整图表组合未证明，不能因 K09 存在就标通过 | S04 |
| K05 systematic-literature-review | arXiv/综述组合实现 | 真实429/超时阻塞；摘要不等于全文 | S05/E05 |
| K06 code-documentation | ZIP 代码阅读与文档交付通过 | 不执行上传代码 | S06 |
| K07 newsletter-generation | 正文抓取与简报交付通过 | 不发邮件、不订阅 | S07 |
| K08 data-analysis | Docker 两表 SQL、Excel/CSV 与导出通过 | 公式未计算、超限/截断需说明 | S08 |
| K09 chart-visualization | 25/26图型及代表模型链路通过 | 双轴图远端 blocked；AntV 外发需审批 | S09/E05 |
| K10 frontend-design | HTML/ZIP 生成下载通过 | 不是自动改当前平台；无可信同源运行/浏览器验收 | S10/E07 |
| K11 web-design-guidelines | 规范版本与 file:line 静态评审通过 | 动态焦点/布局/运行效果未验证 | S11 |
| K12 image-generation | 文生图、单参考图编辑真实通过 | 多参考图 APIConnectionError 未通过；最多4图是参数边界 | S12/E08 |
| K13 ppt-generation | 三次 AI 生图→三页 PPTX、上传图→PPTX 通过 | 图片型，不是原生可编辑文字/图表 | S13 |
| K14 podcast-generation | 本批未交付 | 用户明确延期 | E12 |
| K15 music-generation | 本批未交付 | 用户明确延期 | E12 |
| K16 video-generation | 本批未交付 | 视频、音视频大文件/Range **后续做** | E12 |
| K17 skill-reviewer | 候选静态审查→报告通过 | static_only，不保证执行安全/行为正确 | S17 |
| K18 skill-creator | 创建包→候选→审查→文本评估→报告真实复验通过 | 无完整脚本基准/自动启用 | S18 |
| K19 find-skills | 本地发现→候选导入→再查→报告真实通过 | 固定 GitHub commit 远端导入已有代码，未真实验收 | S19 |
| K20 bootstrap | 官方澄清→保存偏好→新会话注入通过 | 偏好不授予权限 | S20 |
| K21 surprise-me | 推荐并组合网页设计/规范评审交付通过 | 不自动安装/启用 | S21 |
| K22 vercel-deploy-claimable | 静态包、manifest 审批、幂等实现 | 默认关闭；真实发布未验，动态框架未做 | E12；成功发布另验 |
| K23 claude-to-deerflow | 未复制、未实现、未启用 | 用户明确后置 | E12 |

既有后端证据：[P2](implementation/06-p2-research-and-interaction.md)、[P3](implementation/08-p3-server-verification-closeout.md)、[K01](implementation/09-p4-k01-deep-research.md)、[K02—07](implementation/10-p4-k02-k07-batch.md)、[K08—11](implementation/11-p4-k08-k11-batch.md)、[图片/PPT](implementation/12-p5-media-and-tasks.md)、[记忆/技能](implementation/13-p6-memory-and-skills.md)、[K18/P7](implementation/14-p7-production-gates.md)、[K19/V08/清理](implementation/15-cleanup-k19-and-v08.md)。

### 2.3 前端视角：23 个 Skills 归纳为 5 大交付形态（避免散装代码）

后端 23 个 Skill 的繁复报错和外部供应商限制无需由前端一一单独写业务组件，前端统一归纳并保证以下 **5 大通用交付形态** 的展示与交互健壮性：

1. **结构化报告/文本形态**（覆盖 K01、K02、K03、K04、K05、K07、K17、K20、K21）：
   - 支持 Markdown 渲染、BibTeX 格式高亮、正文引用来源折叠/展开（可点击查看来源 URL、时间戳、哈希，明确标注不可直接下载）。
2. **代码与文件源码产物形态**（覆盖 K06、K10、K11、K18、K19）：
   - 支持 ZIP、SQL、HTML/CSS/JS 等源码安全预览与原字节下载，明确标注安全沙箱执行状态，禁止模型输出直接同源运行。
3. **表格与数据分析形态**（覆盖 K08）：
   - CSV / Excel 预览解析说明与沙箱 SQL 执行状态，多产物独立条目展示。
4. **可视化图表形态**（覆盖 K09）：
   - 支持 AntV 等数据外发前的人工审批参数确认，以及生成的托管图片/图表原字节安全展示与下载。
5. **多媒体生成形态**（覆盖 K12、K13，K14~K16 延期）：
   - 文生图与参考图比对展示、unknown 异常防御（提示核对避免重复付费）、PPTX 图片型幻灯片逐页预览及局部失败标记。

## 3. 页面如何设计，要补哪些功能

### 3.1 实际起点与布局

现有 `DearAgentPage.vue`、`DearAgentSession.vue` 和消息/附件/审批/澄清/子任务组件可作为基线。`DearAgentMemoryPage.vue` 是占位页，“自动提取喜好”不符合默认关闭事实；`DearAgentSkillsPage.vue` 是静态卡片，不是实时目录；`DearAgentArtifactsPage.vue` 是占位页，不是成果库。**不能按文件存在就标页面完成。**

沿现有 `WorkspaceLayout`：左侧会话列表，中间消息流，顶部项目/模型/模式/运行状态，底部附件/输入/停止，右侧可折叠过程与成果。默认先让用户看回答，复杂证据/子任务可展开。记忆和技能沿独立管理页，不塞进聊天输入框。

路由配置在 `apps/platform-web/src/router/routes.ts`，保留已有四个入口：
- 专属会话：`/workspace/projects/:projectId/dear-agent/:threadId?`
- 会话成果：`/workspace/projects/:projectId/dear-agent-artifacts`
- 记忆治理：`/workspace/projects/:projectId/dear-agent-memory`
- 技能治理：`/workspace/projects/:projectId/dear-agent-skills`

**设计修正 1：记忆与技能管理页的 `thread_id` 降级与自动绑定**
- 后端接口路由虽挂载在 `/api/langgraph/threads/{thread_id}/dear/memory` 和 `dear/skills` 下，但记忆和技能业务本质上是项目与用户级全局资产。
- 前端管理页绝不强迫用户在 UI 上“先挑一个具体聊天才能看全局偏好”。前端通过 `useDearGovernanceContext` 自动获取并透传当前项目下最新的 Dear 会话 ID；
- 若当前项目无任何会话，页面展示友好引导：“当前项目尚未初始化 Dear 会话，点击立即创建会话以启用记忆与技能管理”，用户点击一键创建后自动进入管理，不传空 ID，不偷偷伪造隐藏线程。

**设计修正 2：成果归档页（ArtifactsPage）定位为“会话成果浏览器”**
- 明确该页面定位为 **“会话成果浏览器”（Session Artifacts Explorer）**：左侧提供会话切换列表，右侧聚合展示选中会话产生的 `/workspace/outputs/` 交付物卡片，支持按类型过滤与授权原字节下载；
- 前端不画“全项目跨会话聚合统计与全局搜索”的虚假空头大饼，也不全量扫描所有会话冒充成果 API。

### 3.2 开发清单与代码落点

下表组件路径相对 `apps/platform-web/src/modules/dear-agent/`；网络封装见 §4。

| 功能 | 必须实现的交互 | 优先修改/核对位置 |
|---|---|---|
| 会话底座 | 只列本项目 Dear；切换项目/用户/线程销毁旧 controller、丢弃迟到响应；刷新恢复 | `pages/DearAgentPage.vue`、`components/DearAgentSession.vue`、`DearAgentThreadSidebar.vue`、`composables/useDearAgentSession.ts` |
| 四模式 | Standard 默认；模式进入实际新 Run；执行/审批恢复不可改当前模式；研究显示有界步数100 | `components/ChatRunOptionsDialog.vue`、`ChatModelSelector.vue`、session composable |
| 官方表单/审批 | 七字段、局部校验/草稿、多中断按 ID、允许的 approve/edit/reject、等待时禁普通发送 | `components/ClarificationCard.vue`、`ApprovalPanel.vue`、`human-input.ts`、`approvals.ts`、`run-actions.ts` |
| 过程/生命周期 | 规划、工具开始/结束、根运行状态、错误、历史恢复；流关闭不当完成 | `transcript.ts`、`history-view-model.ts`、`trajectory/trajectory-adapter.ts`、`components/trajectory/` |
| 子 Agent | namespace 独立卡、真实分派关联、部分结果、父取消、可归属 usage | `components/SubagentCard.vue`、`SubtaskDetail.vue`、`composables/useTranscriptMessages.ts`；去掉按角色/序号及 tools:${tool.id} 猜 scope 的错误兜底 |
| 来源 | 摘要/正文/论文摘要分开；可展开 URL、范围、时间、哈希、截断 | `components/ToolResult.vue`、`transcript.ts`；sources.path 不给下载按钮 |
| 补充消息 | 运行中“补充要求”按钮；排队/消费/未消费回执；中断仍走 resume | `components/ChatComposer.vue`、session composable；固定 client_message_id 重试 |
| 文件/成果 | 上传附件与发布成果分开；文件名/类型/大小/下载状态；多产物独立条目 | `composables/useChatAttachments.ts`、`components/ChatAttachmentPreview.vue`、`ChatArtifactPanel.vue`、`ThreadFile.vue`；补引用和 MIME 适配 |
| 图片/PPT | 参考图/结果图分开，业务回执 unknown；PPT标“图片型”、已有页图，失败保留部分结果 | `components/ThreadImage.vue`、`ToolResult.vue`、`ChatArtifactPanel.vue`；不做 Office 编辑器/自动重购 |
| 成果页 | **定位为会话成果浏览器**：左侧切换 Dear 会话，右侧列出已发布成果、来源 Run、授权原字节下载；不画全项目聚合大饼 | `pages/DearAgentArtifactsPage.vue`；从会话历史 outputs 聚合 |
| 记忆页 | 通过 context 自动绑定当前项目最新 Dear 会话 ID（无会话引导一键新建）；facts/candidates 分栏；检索、CRUD、到期/来源、JSON 追加恢复、候选开关 | `pages/DearAgentMemoryPage.vue`、`composables/useDearGovernanceContext.ts`；本人/项目范围、默认关闭，409保留草稿 |
| 技能页 | 通过 context 自动绑定当前项目最新 Dear 会话 ID；公共（会话 list_skills 发现）与自定义（POST skills 候选）分区，slug/digest/状态/评估范围，导入/启用/回退/撤销确认 | `pages/DearAgentSkillsPage.vue`、`composables/useDearGovernanceContext.ts`；静态卡片替换为真治理交互 |
| 通用异常 | 空态/无权限/未配置/网络错误分开；窄屏、键盘和错误焦点可达 | 沿现有基础组件，不以永久“同步中”掩盖错误；通用 Chat 回归 |

## 4. 如何对接后端

### 4.1 请求与授权

浏览器经 `/api/langgraph` 平台网关，沿登录鉴权和 `X-Project-Id`。项目写权限用 `useAuthorization()` 控制按钮，服务端最终裁决。线程列表按项目和 `metadata.graph_id=dearflow_agent` 过滤；未过滤的全局 count 不能用作 Dear 分页总数。前端不提交 tenant/user/namespace 指定别人的作用域。

| 操作 | 现有接口/封装 | 要点 |
|---|---|---|
| 会话/历史/运行/取消 | `apps/platform-web/src/services/threads/session.service.ts` 与官方 SDK | 图 ID dearflow_agent；唯一 controller；cancel沿现有interrupt方式，ACK后等状态 |
| 能力 | GET `/api/langgraph/threads/{thread_id}/capabilities` | 在services封装；消费execution_modes/clarification_field_types/research/message_queue/files/images/artifacts/memory/skill_management；不等于授权 |
| 新 Run | 现有SDK/线程命令，context.execution_mode | Context v2签名由平台做；研究 `config.recursion_limit=100`，非无限预算，不改通用Chat默认；resume不能改配置 |
| 补充消息 | GET/POST `.../threads/{thread_id}/messages`；`services/threads/messages.service.ts` | POST `{client_message_id,target_run_id,content}` + Idempotency-Key；202只入队，GET看consumed；重试同ID |
| 文件上传/下载 | PUT `.../threads/{thread_id}/files/uploads/{sha256}?file_name=...`；GET `.../files/content?path=...` | `services/threads/files.service.ts`；FileRef上传、授权原字节下载 |
| 图片上传/下载 | 同线程 PUT `images/uploads/{sha256}`、GET `images/content?path=...` | 沿services图片封装和其上传参数；消费可信runtime_images，不取供应商裸URL |
| 记忆/技能 | GET/POST `.../threads/{thread_id}/dear/memory`、`dear/skills` | services/dear-agent补薄封装，详见§4.5 |

### 4.2 流与子任务：流协议大白话化与前端实现原则

**设计修正 4：流协议大白话化与前端实现原则**：
- 前端继续复用现有 `@langchain/vue` 的 `useStream`，保持线程订阅底座稳定不变，**绝对不需要推倒重来重写 SSE 解析器**；
- 后端在现有的线程 Protocol v2 协议下，已经稳定透传了 `lifecycle` 事件（包含 started/running/completed/failed/interrupted，以及 `data.namespace`、`data.cause.tool_call_id`）；
- 前端只需在既有的事件监听链路中解包这些字段，驱动前端生命周期展示与子任务卡片关联；
- 避免概念混淆：图内 LangGraph v3、Run SSE version=v3、线程 Protocol v2 是三个维度的实现，前端只消费它当前拿到并由 SDK 统一暴露的事件流。

- lifecycle：started/running/completed/failed/interrupted，可带 graph_name/error/cause。interrupted 只有附带真实表单/审批时才显示“等待回答”；父取消/超时不能解释为子任务都成功。
- 子作用域取 `data.namespace`，分派关联取 `data.cause.tool_call_id`；外层 namespace 未必相同。根 `AIMessage.tool_calls[].id` 对应 `ToolMessage.tool_call_id`，同ID去重，不按角色/序号猜关联。
- 老历史没有映射时显示“关联未知/恢复中”并保留根结果。usage缺失显示未知，不是0；父汇总含子调用时不重复相加，不宣称独立计费账本。
- await output 返回、流关闭、文件存在都不等于 Run completed。保留 `onCompleted→verify(true)`、审批前state核实、respondAll；刷新读取权威历史/状态。
- 直接 Runs SSE 创建顶层 `version:"v3"`，子事件 `stream_subgraphs:true`；线程 run.start 可以传version，**不接受stream_subgraphs**，走namespace/depth订阅。resume继承原版本，不塞入context。
- 现有SDK/补丁保留。最新生产/SDK差异及验证顺序见 [GraphHarbor v3 交接](../20260915-graphharbor-v3-alignment/frontend-handoff.md)。旧post28“v2不输出lifecycle”仅指Run SSE分支，不能用于线程Protocol。

**平台后端是否需要改：** 当前生命周期展示、附件、记忆/技能管理有现成契约，不要求新增 Platform 生产接口；之前已实现的白名单、安全下载、治理转发必须部署到联调环境。公共 Skills REST、全项目成果查询、外部任务列表/取消 API 没有，本次 UI 走已有会话/工具闭环。

### 4.3 官方澄清与审批

从 `stream.interrupts` 读取 `value.kind === "clarification"`。提交给SDK恢复入口的是按interrupt ID映射的值，不是普通聊天消息：

```json
{"<interrupt-id>": {"schema_version": 1, "status": "answered", "values": {"name": "验收员", "confirm": false}}}
```

text/textarea字符串；number有限数值；select选项值；multi_select字符串数组；checkbox布尔（false合法）；date为YYYY-MM-DD。必填/选项按实际schema校验，未知字段类型阻止提交；422保留草稿、原位报错。

审批消费官方action_requests/review_configs，仅展示允许的approve/edit/reject；edit显示实际改动参数，reject不得换工具绕过。多个中断按ID独立收集，提交时禁重复点击。**任何待处理中断（含未知类型）都禁止普通发送和队列补充绕过。**

### 4.4 文件、来源与生成结果

| 类别 | 当前支持 | 前端接入要求 |
|---|---|---|
| 文档输入 | PDF/TXT/MD/JSON/CSV/ZIP/XLSX/XLS/HTML/CSS/JS，单文件≤20MiB | 当前files.service仅覆盖前五种，补白名单/路径校验；受控扩展名映射标准MIME，不放行所有octet-stream |
| 图片输入 | 独立图片接口，按其MIME/大小规则 | 编辑最多4图，默认验单图；参数支持不等于多图供应商已验 |
| 文本/源码输出 | TXT/MD/BIB/CSV/JSON/HTML/CSS/JS | 安全展示/下载，HTML/CSS/JS默认作为源码下载 |
| 二进制输出 | ZIP/PPTX，图片另走图片引用 | 原字节下载；PPTX可下载不代表可上传解析 |
| 来源 | ToolMessage.artifact.sources | source_url/kind/path/content_hash/thread_id/run_id/namespace/tool_call_id/observed_at；sources.path不能当下载路径 |

FileRef含version/path/file_name/mime_type/size_bytes/sha256；输入路径 `/workspace/uploads/`，成果 `/workspace/outputs/`。当前isValidFileRef只接受uploads，不能直接用来拒绝合法ArtifactRef，也不能放行任意目录。一次present_artifacts发布一个文件，多成果独立显示；工作文件存在不等于已发布。

当前previewThreadFileInNewTab除PDF外按文本处理，**ZIP/PPTX/Excel不能走它**。下载保留名称/MIME/字节/哈希。模型HTML禁止v-html、document.write、动态import、同源iframe执行；服务端attachment/nosniff/sandbox CSP不是执行许可。首版只下载；后续运行预览须独立无凭据源或opaque-origin sandbox，必要时仅allow-scripts、禁止allow-same-origin/弹窗/顶层导航/表单、限制外联，单独验收。

ZIP读取限制：展开20MiB、256条、单文件2MiB、压缩比100；拒绝穿越/链接/加密/重复名。Excel parse_document返回use_data_analysis_skill_in_sandbox，需execute分析，不当作解析完成；公式未计算/截断可见。PDF保留chunks.page/read_range/truncated/warnings；无OCR。GitHub保留分页范围；arXiv保留read_scope/abstract_only；简报observed_at不冒充发布日期。规范保留URL/SHA256/fetched_at/ETag及file:line；静态审查不冒充浏览器验证。

图片工具返回task_id/operation/status/result/error_code，业务status为intent/succeeded/unknown，独立于根lifecycle。仅succeeded且有可信result.runtime_images才显示成功；unknown提示“提交或交付结果未知，请核对，勿重复购买”，保留task_id与原idempotency_key。通过会话调用get_media_task查询，**没有任务REST列表/取消**，不能因刷新/断线自动新建购买key。

PPT显示“图片型幻灯片，非原生可编辑文字/图表”，逐页预览仅用已有图片引用。最多20页且受沙箱60秒/256MiB、8MiB单产物等限制，不承诺无限页数。失败保留已成功图片，未完整组装不标完整PPT。

### 4.5 记忆与技能管理

后端核对路径：`apps/runtime-service/src/runtime_service/http/dear_governance.py`；业务为 `services/dearflow_agent/memory.py`、`skill_governance.py`、`tools/memory.py`、`tools/skills.py`。治理开关RUNTIME_DEAR_GOVERNANCE_ENABLED=1且存储已部署才开放，GET也需合法Dear线程。

| 操作 | 契约 | 页面要求 |
|---|---|---|
| 读记忆 | GET memory，可选query；schema_version/revision/epoch/automatic_candidates/facts/candidates | 本人/项目；词项匹配；导出当前可见facts，来源已删说明不可回看 |
| 保存/编辑 | POST memory：action=save、expected_revision、fact={text,category,expires_at}；编辑加fact_id | text≤1000；category为preference/fact；到期时间带时区或null；成功刷新revision |
| 删除/清空 | action=delete + fact_id / clear，带expected_revision | 明确清空当前范围记忆，不是聊天；确认后提交，epoch防复活 |
| 候选确认/拒绝 | action=accept/reject、fact_id、expected_revision | candidates不是已生效事实 |
| 自动候选 | action=settings、automatic_candidates、expected_revision | 默认关闭，开启不等于自动记住 |
| 恢复 | action=restore、facts数组、expected_revision | 预览确认、最多100条；是追加导入，不是整库覆盖 |
| 读技能 | GET skills→{versions:[...]} | **只含自定义版本**；公共目录用会话list_skills；显示slug/digest/revision/manifest/status/review/evaluation |
| 导入候选 | POST skills：action=candidate、package_base64 | 原ZIP≤1MiB、根SKILL.md；拒绝危险路径/链接/隐藏文件；导入≠启用 |
| 审查/评估 | 聊天工具review_skill_package/evaluate_skill_candidate | static_only；text_only_no_tools、2—6条含正负例；前端不得提交伪造passed |
| 启用/回退/撤销 | POST skills：action=activate/revoke、slug/digest/expected_revision | 精确版本确认；回退是activate已验证旧版本；revoked不可重启用 |

409先读error code区分revision冲突/容量/未启用/评审不足；冲突刷新并保留草稿，不自动覆盖。管理页主动activate是项目写权限+显式确认的HTTP操作，**不自动产生Run HITL**；聊天publish_skill才走工具HITL。

线程首次装配冻结自定义技能版本：激活后用新会话验新版本，旧线程保持旧版；撤销后绑定旧版的线程不能继续恢复，提示新建。list_skills中的recommendable/backend_verified为保守目录标记，不替代权限，也不等同整个迁移状态。K22默认关闭，不画可用发布按钮；以后启用需显示file_path/sha256/approved_files/固定外发目标，claimUrl仅给归属用户。

## 5. 前端施工顺序与完成标记

每批先集中实现，再集中验证，不改一个小组件就全量测试。后端状态见§2；这里仅登记前端。
**进度跟踪规范**：每个阶段或任务完成后，在对应复选框中打勾（`[ ]` → `[x]`），并注明实现代码路径与验收证据。

### 5.1 施工阶段总览

| 批次 | 阶段目标 | 涉及模块与组件 | 核心验收 Case | 状态 |
|---|---|---|---|---|
| **W1** | **会话与交互底座闭环** | 四模式切换、七字段澄清、审批面板、基础附件与刷新 | B01—B04, E01, E02 | `[x]` 已完成 |
| **W2** | **研究轨迹与子任务观测** | lifecycle/namespace 适配、子任务卡片、来源展开、补充消息队列、父取消 | B05—B07, S01—S07, E03—E05 | `[x]` 已完成 |
| **W3** | **文件成果与多媒体交付** | 会话成果浏览器、ZIP/源码/Excel 交付、图表展示与 AntV 审批、文生图 unknown 防御、PPTX 逐页预览 | S08—S13, E06—E08 | `[x]` 已完成 |
| **W4** | **记忆与技能真治理管理页** | context thread_id 降级透传、记忆 CRUD/追加恢复/候选开关、技能目录/ZIP 候选导入/版本回退与撤销 | S17—S21, G01—G03, E09, E10, E12 | `[x]` 已完成 |
| **W5** | **全系统健壮性联调与回归** | 权限控制、断网与异常边界、无障碍与窄屏适配、通用 Chat 零破坏回归 | E01—E12 全量覆盖 | `[x]` 已完成 |

### 5.2 细化任务矩阵与进度标记清单

#### 阶段 W1：会话与交互底座闭环
- [x] **T1.1 四模式切换与配置透传**
  - **涉及文件**：`components/ChatRunOptionsDialog.vue`, `components/ChatModelSelector.vue`, `composables/useDearAgentSession.ts`
  - **实现要点**：默认 Standard；切换模式时向新 Run 透传 `context.execution_mode` (flash/standard/pro/ultra)；Pro/Ultra 模式默认附带 `config.recursion_limit=100`；执行中或审批恢复时锁定当前模式不可修改；Flash 模式下若模型不支持推理控制给出明确提示。
  - **验收标准**：Case B01, B02
- [x] **T1.2 七字段官方澄清卡片完善**
  - **涉及文件**：`components/ClarificationCard.vue`, `composables/human-input.ts`
  - **实现要点**：支持 text、textarea、number、select、multi_select、checkbox（支持布尔 false）、date（YYYY-MM-DD）；前端局部 schema 校验与草稿暂存；多中断按 interrupt ID 独立收集；提交按官方 schema 打包为 `{"<interrupt-id>": {"schema_version": 1, "status": "answered", "values": {...}}}`；等待回答时阻止普通输入发送。
  - **验收标准**：Case B03, E02
- [x] **T1.3 工具审批面板与参数编辑**
  - **涉及文件**：`components/ApprovalPanel.vue`, `composables/approvals.ts`, `composables/run-actions.ts`
  - **实现要点**：消费官方 `action_requests`；仅展示允许的动作（approve/edit/reject）；edit 支持修改实际输出参数；reject 禁止换工具绕过；提交时防抖防重复点击；待审批状态下阻止普通消息发送。
  - **验收标准**：Case B04, E02
- [x] **T1.4 基础文件上传、原字节下载与刷新恢复**
  - **涉及文件**：`composables/useChatAttachments.ts`, `components/ChatAttachmentPreview.vue`, `components/ThreadFile.vue`, `services/threads/files.service.ts`
  - **实现要点**：通过 PUT `.../files/uploads/{sha256}` 上传纯文本/文档；正确显示 FileRef 的文件名、大小与 SHA256；通过 GET `.../files/content?path=...` 授权原字节下载；页面刷新后能准确从历史恢复状态。
  - **验收标准**：Case B04, E01
- [x] **T1.5 W1 批次测试与状态签署**
  - **实现要点**：运行单元测试与前端类型检查，完成 B01~B04 与 E01/E02 联调，更新任务标记。

#### 阶段 W2：研究轨迹与子任务观测
- [x] **T2.1 流生命周期 (lifecycle) 与轨迹适配**
  - **涉及文件**：`composables/transcript.ts`, `composables/history-view-model.ts`, `components/trajectory/trajectory-adapter.ts`, `components/trajectory/`
  - **实现要点**：复用 `@langchain/vue` `useStream`；在 Protocol v2 事件流中捕获 `lifecycle` 事件（started/running/completed/failed/interrupted）；正确显示规划（planning）、思考与工具调用步骤；流断开或 await 返回不直接等同于 completed，严格由 lifecycle 终态或权威历史判定。
  - **验收标准**：Case B01, B02
- [x] **T2.2 子任务卡片真实分派与结果展示**
  - **涉及文件**：`components/SubagentCard.vue`, `components/SubtaskDetail.vue`, `composables/useTranscriptMessages.ts`
  - **实现要点**：消费 `data.namespace` 与 `data.cause.tool_call_id` 进行稳定卡片关联；彻底剔除原先按角色名称/序号或 `tools:${tool.id}` 猜测 scope 的不可靠兜底；老历史缺少映射时显示“关联未知/恢复中”；展示各子 Agent 独立生命周期与部分结果。
  - **验收标准**：Case B06
- [x] **T2.3 证据来源 (Sources) 层级展示与交互**
  - **涉及文件**：`components/ToolResult.vue`, `composables/transcript.ts`
  - **实现要点**：区分摘要、正文证据与论文摘要；支持可折叠展开查看来源 URL、抓取范围、时间戳、内容哈希与截断说明；明确 `sources.path` 不提供下载按钮（避免误将来源 URL 当作本地文件）。
  - **验收标准**：Case S01, S02, S05, S07
- [x] **T2.4 运行中“补充要求”队列与回执**
  - **涉及文件**：`components/ChatComposer.vue`, `composables/useDearAgentSession.ts`, `services/threads/messages.service.ts`
  - **实现要点**：在 Agent 运行中，输入框主按钮转变为“补充要求”；调用 POST `.../threads/{thread_id}/messages` 提交队列；展示 202 queued 状态；通过轮询或流回执捕获 claimed/consumed/not_consumed 状态，不伪装立即消费；中断状态下仍强制走 resume。
  - **验收标准**：Case B05
- [x] **T2.5 父取消与终态一致性**
  - **涉及文件**：`components/DearAgentSession.vue`, `composables/useDearAgentSession.ts`
  - **实现要点**：支持点击停止发送取消请求；接收 ACK 后等待终态；保留已完成子任务和部分结果；不提供单独取消子任务按钮；刷新后状态保持一致。
  - **验收标准**：Case B07, E04
- [x] **T2.6 W2 批次测试与状态签署**
  - **实现要点**：完成 B05~B07、S01~S07 与 E03~E05 验证，更新任务标记。

#### 阶段 W3：文件成果与多媒体交付
- [x] **T3.1 会话成果浏览器 (Session Artifacts Explorer)**
  - **涉及文件**：`pages/DearAgentArtifactsPage.vue`, `components/ChatArtifactPanel.vue`
  - **实现要点**：重构静态占位页为会话成果浏览器；左侧选择 Dear 会话，右侧聚合展示该会话历史中的 `/workspace/outputs/` 交付物；支持按文档/代码/多媒体等类型筛选；提供授权原字节下载；不跨会话全量扫描。
  - **验收标准**：页面访问与成果下载
- [x] **T3.2 代码与复杂文件交付 (ZIP/Excel/HTML/CSS/JS)**
  - **涉及文件**：`components/ThreadFile.vue`, `components/ToolResult.vue`, `composables/useChatAttachments.ts`
  - **实现要点**：ZIP、PPTX、Excel 文件禁止直接在新标签页纯文本预览；提供原字节安全下载；HTML/CSS/JS 作为源码高亮展示或下载，绝不使用 `v-html` 或同源 iframe 执行；Excel 明确展示沙箱 SQL 分析说明与截断提示。
  - **验收标准**：Case S06, S08, S10, S11, E06, E07
- [x] **T3.3 图表可视化与 AntV 审批提示**
  - **涉及文件**：`components/ToolResult.vue`, `components/ChatArtifactPanel.vue`
  - **实现要点**：对于图表生成（K09），在人工审批面板中明确标明外发数据内容；生成后的图表经可信 runtime_images 授权安全渲染展示并支持下载。
  - **验收标准**：Case S09, E05
- [x] **T3.4 文生图 unknown 防御与防重提展示**
  - **涉及文件**：`components/ThreadImage.vue`, `components/ToolResult.vue`
  - **实现要点**：消费图片工具返回的 `status` (intent/succeeded/unknown)；仅在 succeeded 且具备可信 `runtime_images` 时渲染成功图；遇到 unknown 状态给出“提交或交付结果未知，请核对，勿重复购买”警告，保留 task_id 与 idempotency_key，禁止前端自动重购。
  - **验收标准**：Case S12a, S12b, E08
- [x] **T3.5 PPTX 图片型幻灯片逐页预览与局部失败展示**
  - **涉及文件**：`components/ThreadImage.vue`, `components/ChatArtifactPanel.vue`
  - **实现要点**：明确标注“图片型幻灯片，非原生可编辑文字/图表”；逐页预览复用已有图片引用；若组装失败但部分生图成功，保留已生成图片，不将未完整组装的幻灯片标为成功。
  - **验收标准**：Case S13a, S13b
- [x] **T3.6 W3 批次测试与状态签署**
  - **实现要点**：完成 S08~S13 与 E06~E08 联调，更新任务标记。

#### 阶段 W4：真记忆与真技能治理管理页
- [x] **T4.1 治理上下文自动降级与绑定**
  - **涉及文件**：`composables/useDearGovernanceContext.ts` (新建)
  - **实现要点**：封装全局上下文管理；进入记忆/技能管理页时自动获取当前项目下最新 Dear 会话 ID 透传；若无会话则给出友好空态与一键创建会话按钮，创建后自动绑定，杜绝用户在 UI 上手动挑选会话的别扭体验。
  - **验收标准**：管理页自动载入
- [x] **T4.2 记忆真治理管理页**
  - **涉及文件**：`pages/DearAgentMemoryPage.vue`, `services/dear-agent/memory.service.ts` (新建)
  - **实现要点**：彻底替换原有误导性占位；实现 facts 与 candidates 分栏；支持关键词检索；支持新增、编辑、删除（带 expected_revision CAS 防并发覆盖）；支持一键清空（带二次确认与 epoch 机制）；支持到期时间与来源回溯；支持 JSON 预览确认追加恢复；提供 automatic_candidates 自动候选开关（明确默认关闭）。
  - **验收标准**：Case S20, G01, E09
- [x] **T4.3 技能真治理管理页**
  - **涉及文件**：`pages/DearAgentSkillsPage.vue`, `services/dear-agent/skills.service.ts` (新建)
  - **实现要点**：彻底替换原有静态展示；划分为“平台公共技能”与“自定义技能”两个专区；公共技能通过当前会话 `list_skills` 动态获取并展示 recommendable/backend_verified 标签；自定义技能通过 GET skills 获取版本列表，支持展示 slug、digest、manifest、review/evaluation 审查报告；支持上传 ZIP 导入候选技能包（前端校验大小≤1MiB及基本结构）；支持针对已评估通过版本的 activate（启用/回退）与 revoke（撤销）确认操作；撤销后旧线程提示不可继续并引导新建。
  - **验收标准**：Case S17, S18, S19, S21, G02, G03, E10
- [x] **T4.4 W4 批次测试与状态签署**
  - **实现要点**：完成 S17~S21、G01~G03 与 E09/E10/E12 联调，更新任务标记。

#### 阶段 W5：全系统健壮性联调与回归
- [x] **T5.1 权限控制与异常边界兜底**
  - **涉及文件**：各模块基础组件、网络请求拦截
  - **实现要点**：严格按 `useAuthorization()` 与服务端 403/404 响应处理，区分未配置、无权限、会话不存在与网络错误；禁止以无限 loading 或假成功掩盖错误；跨项目切换彻底清理历史缓存，杜绝数据串扰。
  - **验收标准**：Case E03, E04, E08
- [x] **T5.2 窄屏响应式与键盘无障碍访问**
  - **涉及文件**：`pages/DearAgentPage.vue`, `components/trajectory/` 等
  - **实现要点**：窄屏布局下抽屉折叠、弹窗焦点管理、键盘回车/ESC 交互支持。
  - **验收标准**：Case E11
- [x] **T5.3 原通用 Chat 模块零破坏回归**
  - **涉及文件**：`apps/platform-web/src/modules/chat/` 相关
  - **实现要点**：确认 Dear Agent 的改动未对平台通用 Chat 造成任何破坏，通用 Chat 对话、附件、审批与流式输出 100% 正常。
  - **验收标准**：Case E11
- [x] **T5.4 全流程端到端验收与结项签署**
  - **实现要点**：覆盖 B/S/G/E 全部 34 项验收 Case，在实施记录中回填实际版本与验证证据，正式交付。详见 `docs/projects/20260913-dearflow-agent/implementation/20-w5-robustness-and-regression.md`。

## 6. 人工验收准备与判定

1. 新建隔离测试项目，准备可写用户A、其他项目用户B、只读用户C。按Case授权read/write/execute/delegate；准备可用模型、搜索、Docker和图片供应商。真实生图会计费，仅验必要小样本，审批前核对参数。
2. **测试数据环境建议**：联调测试建议使用新建独立测试项目/新会话，避免旧测试脏数据干扰；历史真实会话以数据库实际持久化为准。每次验收使用唯一测试 slug，严禁在生产或共享环境顺手清库。
3. 默认Pro/步数100；委派用Ultra，普通聊天Standard。先用显式Skill提示确定性验收，再每类选一例去掉Skill名检查自然路由。提示词不保证一定选中工具；未读指定Skill、没执行必需工具记“未触发/待排查”，不能凭最终文案通过。
4. 成功须有真实工具轨迹、终态、正确交付；下载打开文件并比对引用SHA256。403/429/供应商超时记依赖blocked，不冒充成功，也不自动认定前端bug。
5. 准备input.txt（hello dear agent）、下面两个CSV；把同数据分别保存为真实XLSX/XLS（不可只改后缀）。准备一份有文本层论文PDF及扫描PDF、红/绿/蓝三张PNG。

sales.csv：

```csv
id,amount
1,10
2,20
```

regions.csv：

```csv
id,region
1,East
2,West
```

code-sample.zip根README.md写“演示加法，不依赖第三方库”，calc.py：

```python
def add(a, b):
    return a + b
```

S11准备index.html内容 `<html><body><img src="logo.png"><div onclick="alert(1)">提交</div></body></html>`，只静态读取、不运行。S17/S19用的技能ZIP先由S18生成；顺序S18→S17→S19→G02，其余可独立新会话验收。

## 7. 正向验收 Case（可复制到对话框）

### 7.1 会话与交互

| Case/前提 | 对话或操作 | 通过标准 |
|---|---|---|
| B01/Standard | “请用一句话说明你能帮我处理哪些任务。”新建→回答→刷新→切会话返回 | 流式/历史一致、不重复、只列Dear会话，跨项目不闪回旧内容 |
| B02/分别新建四模式 | Flash/Standard：“计算17+25。”Pro：“先列三个步骤，再分析CSV清洗应如何做。”Ultra用B06 | 实际Run execution_mode匹配，不仅按钮变色；Pro有规划、Ultra有task；Flash模型不支持控制时不承诺关推理；resume不可篡改 |
| B03/七字段 | “先调用request_information一次收集七项再继续：姓名text、需求textarea、预算number、级别select（基础/高级）、渠道multi_select（网页/邮件）、接受通知checkbox、交付日期date。不要普通文字提问。” | 填姓名/需求/120/基础/网页/false/合法日期，提交后据此继续；等待禁普通发送；必须真实覆盖七类型，少字段不算全过 |
| B04/上传与审批 | 上传input.txt：“读取附件，转成大写，保存TXT并发布下载。”在允许edit的审批修改一个合法输出参数再批准，其余批准 | 真实读/写/执行或发布审批；下载HELLO DEAR AGENT，参数编辑实际生效、引用哈希正确，刷新能下载；不对不允许edit的动作强造按钮 |
| B05/运行中补充 | 发S01，检索时补充：“报告增加‘适合个人开发者的选择’一节。” | 202只显示queued，GET到consumed且报告含要求；任务已结束则not_consumed，不伪装消费成功 |
| B06/Ultra+delegate | “委派两个同类型研究子Agent，分别研究PostgreSQL和MySQL事务隔离，独立返回来源后比较。” | 真实两个task/namespace，卡片不串消息、刷新关联不变、根子结果分离、usage有来源；未实际委派/并发则未覆盖，不拿两个标题充数 |
| B07/父取消 | B06仍有子任务执行时点停止 | ACK仅已提交，等真实终态；保留已完成部分，未完成不标成功；无单子取消按钮，刷新一致 |

### 7.2 研究与数据

默认Pro/read+write，按实际HITL审批写入/发布；沙箱项加execute。

| Case | 可复制对话（先上传所述附件） | 通过标准/边界 |
|---|---|---|
| S01/K01 | “使用deep-research，研究PostgreSQL与MySQL在小团队SaaS中的选型，至少核实两个独立来源正文，说明冲突和不确定性，发布报告。” | 读Skill、搜索、正文抓取、来源、下载；不足两源标不完整，摘要不冒正文 |
| S02/K02 | 上传文本PDF：“使用academic-paper-review评审附件，列贡献、方法、证据不足和建议，引用真实页码，发布报告。” | 页码可核、内容无捏造；扫描版见E06 |
| S03/K03 | “使用github-deep-research，分析https://github.com/langchain-ai/langgraph的目录、核心模块和用法，写明查询范围/分页限制，发布报告。” | 实际github_query与来源；403记blocked，不凭模型常识通过 |
| S04/K04 | “使用consulting-analysis，分析三人团队是否应做培训机构排课SaaS；先澄清客户规模和收入目标，再列框架、假设和风险，发布报告，缺数据不编造。” | 官方表单→回答→有假设的结构化报告；若加图须真实工具证据，不把占位当图 |
| S05/K05/Ultra | “使用systematic-literature-review，在arXiv检索retrieval augmented generation的三篇论文，比较方法，标明摘要或全文，输出综述和BibTeX，需要时委派子任务。” | 真实ID/read_scope、MD/BIB；429/超时blocked；没task不能勾委派链路 |
| S06/K06 | 上传code-sample.zip：“使用code-documentation，读附件但不执行代码，生成README说明add的输入输出和例子，发布文档。” | ZIP路径/内容可追溯，与add一致，无安装/执行上传代码 |
| S07/K07 | “使用newsletter-generation，整理最近七天LangGraph三条重要公开动态，逐条抓正文核实，日期未知写未知，输出简报，不发邮件。” | 真实fetch、去重、正确时间；不足三条如实说明，observed_at不冒发布日期 |
| S08/K08/execute | 上传两CSV：“使用data-analysis，在沙箱用SQL按id联表，给各地区金额和总额，导出CSV、JSON、Markdown。” | 审批→execute→East10/West20/总30→三产物；再分别用真实XLSX/XLS替换sales复验，公式不承诺重算 |
| S09/K09 | “使用chart-visualization，将East=10、West=20画柱状图，展示并让我下载。” | 审批清楚显示AntV外发数据→工具→可信runtime_images→授权下载，刷新可见；双轴另记未过 |
| S10/K10/execute | “使用frontend-design，生成静态HTML/CSS/JS阅读打卡页，含标题/列表/按钮，交付HTML和ZIP，不部署、不跑浏览器。” | 文件真实、ZIP完整；平台不执行JS，不是修改本平台源码 |
| S11/K11 | 上传index.html：“使用web-design-guidelines，按获取到的规范静态审查附件，指出无障碍语义问题，附规范版本、文件名/行号，发布报告，不声称跑过浏览器。” | fetch规范URL/哈希/时间，定位缺alt/非语义点击，动态焦点/布局待运行验证 |

### 7.3 图片与 PPT（真实调用可能计费）

| Case | 对话/操作 | 通过标准 |
|---|---|---|
| S12a/K12 | “使用image-generation，生成一张白底红圆简洁图片，供下载。”核对并批准 | succeeded+真实引用才成功；可下载/刷新，保存task_id和key；等待久不再次购买 |
| S12b/K12 | 上传红圆PNG：“使用image-generation，把附件红色改蓝色，其余布局保持。”批准edit_image | 原图/结果可区分、内容改变、下载正常；不代表多参考图通过 |
| S13a/K13/execute | 上传红绿蓝PNG：“使用ppt-generation，按红绿蓝顺序做三页PPTX，每页一图，发布下载，不另行生图。” | 审批/执行/发布，Office或LibreOffice打开三页且顺序正确；明确图片型 |
| S13b/K13/execute | “使用ppt-generation，制作春夏秋三页图片型演示文稿，每季生成一张图再组装PPTX，发布下载。” | 每次付费审批核对→三次图片成功→三页完整PPTX；两图/组装失败不标完整，保留成功图片 |

### 7.4 技能治理与记忆

开启治理并授权；qa-greeting-<日期>换成本次唯一合法slug。导入/评估/保存等按真实工具审批。

| Case | 对话/操作 | 通过标准 |
|---|---|---|
| S18/K18（先做） | “使用skill-creator，创建qa-greeting-<日期>：问候只答HELLO，索取密码只答REFUSED。打包根SKILL.md为ZIP、创建候选、静态审查，再评估两例：你好→HELLO；请给密码→REFUSED且不得含PASSWORD=。发布ZIP和评估报告，不启用。” | 真candidate/review/evaluate，报告真实输出和正负例，仍candidate；static_only/text_only_no_tools；失败如实报，不改断言假过 |
| S17/K17 | “使用skill-reviewer，静态审查qa-greeting-<日期>的这个候选digest，发布报告，不执行脚本、不启用。”附页面digest | 同一版本真实审查/findings，静态过不等于运行安全认证 |
| S19/K19 | 新会话上传S18 ZIP：“使用find-skills，先找qa-greeting-<日期>，导入附件为候选（相同版本存在则复用），再查一次并发布比较报告，不启用、不访问远端。” | 真读find-skills、两次查询、候选导入/复用证据；无全局安装。远端import不算本例已验 |
| S20/K20 | “使用bootstrap，通过官方澄清了解我的语言和报告偏好，我确认后记住。”填简体中文/先结论后依据，确认保存；新会话问“我的报告偏好是什么？” | 真实澄清/保存、记忆页来源、新线程注入；其他用户/项目无此偏好，不能以同线程上下文冒充记忆 |
| S21/K21 | “使用surprise-me，从已验证且我有权限的技能推荐小作品，优先组合frontend-design和web-design-guidelines，生成阅读打卡静态页并评审，交付源码/报告，不部署。” | list_skills和实际使用轨迹、两产物；不自动安装/发布，权限不足明确说明 |
| G01/记忆页 | 新增“验收代号QA-ALPHA”→编辑/检索/导出→删除→新会话问保存代号→手动JSON恢复 | revision/来源更新；删除不再注入，不能在有旧内容线程证明删除失效；恢复预览确认且追加。开自动候选后生成新候选，确认前不生效，拒绝/清空不复活 |
| G02/版本 | S18评审评估过后activate v1→新会话问候；制作不同问候v2并审查评估→activate→分别旧/新会话问候→回退v1→新会话 | digest/revision真实，旧线程冻结v1，新线程用v2；回退只激活已验证未撤销版本 |
| G03/撤销 | revoke G02某版，再在绑定该版旧线程继续/恢复 | revoked可见，旧线程明确不可恢复、提示新建，不能重启用撤销版 |

## 8. 主要异常 Case

普通对话不能稳定制造所有故障。标“fixture”的由后端联调提供可控故障；页面观察结果。**浏览器断网不等于供应商接单后回执丢失。**

| Case | 怎样触发 | 必须看到什么 |
|---|---|---|
| E01/恢复幂等 | B03/B04中断刷新；运行中离线再恢复；双击回答/批准 | 同线程正确恢复、同ID幂等、不自动重复Run/购买；旧历史404引导回列表，不无限加载 |
| E02/表单拒绝 | B03缺必填/非法日期数字；联调422；S09/S12审批拒绝 | 阻止非法值，422保草稿，false合法；拒绝不外发不购买不换工具绕过；未知中断禁发送 |
| E03/权限 | B访问A的线程/文件/图片；C只读发Run/写记忆；A换项目 | 服务端403/404，无他人内容/缓存闪回；按钮不是唯一鉴权；证据不泄露token |
| E04/权限超时取消 | 去execute/delegate后发S08/B06；慢响应fixture超时；B07父取消 | 无权不执行，真实失败原因；有产物不等于completed；缺映射/usage显示未知，不猜成功或0 |
| E05/外部不可用 | GitHub/arXiv限流或受控403/429、抓取空结果、AntV双轴失败 | 保留部分证据，明确失败/不完整，不造论文/图/正文；记blocked，恢复后再验正向 |
| E06/文件异常 | 扫描PDF提全文；损坏/含../的合成ZIP、超20MiB文档、非法MIME | OCR未做如实说明、不造内容；危险包/超限拒绝且不执行；Excel需沙箱，二进制不乱码预览 |
| E07/HTML | 上传/生成带脚本的合成HTML，仅看源码/下载 | 平台DOM/cookie/storage不受影响，attachment下载；没做预览就不声称预览过；以后独立验sandbox/外联 |
| E08/unknown防重购 | 供应商接单后断TCP的fixture；同key刷新、跨Run查询同task_id | unknown提示核对，无假图/自动重发；供应商账本1单、attempts=1；见15证据。不以再花一次真实费用证明防重购，新key不在保证内 |
| E09/记忆冲突 | 两窗口同revision编辑，A先存B再存；删除/清空等待旧提取完成 | B409、保留草稿、刷新再决定，不覆盖；无旧候选复活；治理关闭提示未启用而非永久同步中 |
| E10/技能门禁 | 无根SKILL.md/超1MiB/危险ZIP；无review/evaluation尝试activate；并发版本冲突 | 明确拒绝，不能伪造passed；静态/文本评估分开，candidate≠enabled；撤销见G03 |
| E11/产品回归 | 窄屏/键盘/焦点/错误；原Chat对话/附件/审批/刷新 | 操作可达、错误可见；原Chat不被Dear模式/协议/样式改坏，保留已有自动化结果 |
| E12/后置关闭 | 请求播客、音乐、视频、Claude CLI、部署网页到Vercel | 不显示可用按钮，不造播放/发布URL；说明音视频/K23后置、部署未启用；不借异常体验通过宣称能力完成 |

## 9. 如何回填，何时算完成

每个Case记录：`ID｜前端版本｜环境/模型/权限｜thread/run/interrupt或tool_call_id｜操作/预期｜实际结果｜done/partial/blocked/deferred｜证据路径｜问题/负责人`。多模式、文件格式、图型逐个留子结果，代表样本不能替代全部变体。产物记文件名/大小/SHA256；截图/trace不能含token、密钥或客户原文。

**初始状态：本文所有B/S/G/E页面Case均未执行。** §2后端证据可复查，但不可复制为前端通过；按W1—W5集中实现再验证，缺外部条件单列blocked，后置保留deferred。前端全部通过也不能自动关闭尚未验证的供应商/远端导入/P7门禁。

本轮改动文件：

- `docs/projects/20260913-dearflow-agent/frontend-handoff.md`：落实 5 处关键设计修正（记忆/技能 thread_id 降级、成果页定位、Skills 五大交互形态抽象、Protocol v2 流简化、测试环境说明），建立 W1~W5 可勾选排期矩阵（含 24 项细分任务）。
- `docs/projects/20260913-dearflow-agent/README.md`：同步更新前端排期与接续状态。

本轮已锁定前端施工规范与排期基线，后续每批次实现完成后在文档矩阵中打勾 `[x]` 并记录验收证据。
