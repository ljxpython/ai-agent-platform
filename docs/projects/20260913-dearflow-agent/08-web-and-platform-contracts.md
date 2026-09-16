# 08 Dear Agent 专属前端、Chat 基线复制与跨服务契约

## 目标

在 `platform-web` 内建设 Dear Agent 专属前端模块。将现有 Chat 首发所需展示与交互代码作为基线快照复制到专属目录，形成独立可用入口，再逐阶段适配业务布局、执行过程和成果管理，最终交付平台内的生产级 Agent 展示。使用官方 LangChain／LangGraph 交互语义，消除 Showcase 特判。所有公开请求经过 Platform API 授权，Runtime 只接受受信委托；不另建 Web 应用、事件总线或运行状态机。

## 工作上下文

- **总入口：** [项目总纲与交接规则](README.md)。独立开发本章时先读总纲，不以聊天历史代替依赖证据。
- **实施阶段：** P0—P7 全程参与，前端明细 F0—F7；P1 就交独立入口。
- **必读前置：** [01 第一轮实施包](01-architecture-and-boundaries.md)、[10 切片导航](10-delivery-and-production-verification.md)；按当前功能查 02 模式、04 文件、05 子任务、06 记忆、07 Skills、09 外部任务。
- **输入 → 输出／对接：** Runtime 实现能力＋Platform 当前授权＋官方 SDK → Dear Agent 专属 UI；本章 C01—C09 管跨章节契约落点，F 表管前端交付。
- **当前切片／最近证据：** P1 最小后端契约与平台 HTTP 文件／恢复链路通过，见 [05](implementation/05-p0-p1-deployment-verification.md)。历史前端实现单列，本轮未改或重验。
- **下一任务：** P2 扩展模式／表单／队列契约；前端对接前提前告知，浏览器验收另行安排。
- **结束回填：** 更新本章任务／验证／状态及此处游标，按总纲登记最近 implementation 记录、契约变化和下一精确任务；部分切片通过不勾选整章完成。

## 方案设计

### 1. 现状缺口与参考定位

| 能力 | DeerFlow 参考（相对参考仓库根） | 当前工程与改造点 |
|---|---|---|
| 运行模式提交 | `frontend/src/core/threads/hooks.ts` | Dear Agent 专属 `ExecutionModePicker.vue`＋现有 `apps/platform-web/src/modules/chat/composables/useChatSession.ts`；按 02 提交版本化 Context，目录见 §6 |
| 线程文件与产物 | `backend/app/gateway/routers/` 下文件／上传路由；`backend/packages/harness/deerflow/tools/builtins/present_file_tool.py` | Runtime `http/images.py` 硬编码 showcase assistant、`http/documents.py` 使用 Showcase 根目录；按 04 统一 scope resolver |
| 子任务进度与取消 | `backend/packages/harness/deerflow/subagents/step_events.py`、`tools/builtins/task_tool.py` | 当前 Web `SubagentCard.vue`、`SubtaskDetail.vue`；保留官方 namespace／tool call 关联，独立 Run 另订阅 |
| 人工输入／审批 | `backend/packages/harness/deerflow/agents/middlewares/clarification_middleware.py` | 现有 `ApprovalPanel.vue`、`approvals.ts`、`run-actions.ts`；统一 interrupt ID 和标准 resume |
| 技能与记忆管理 | `backend/app/gateway/routers/skills.py`、`memory.py` | 在 Dear Agent 专属目录中实现管理面板，组合现有 Inspector 基础；Runtime 业务归属见 06／07，不复制 DeerFlow 管理 API |

现有 Runtime `/internal/capabilities/tools` 从 Showcase 导入权限描述；消息队列 HTTP 仅允许指定 graph；Platform 及 Web 也有附件／队列能力特判。应统一从受信 Graph 能力快照判断，不能每加一个 Agent 再加一组字符串分支。

### 2. 能力描述：静态事实与运行授权分开

拟新增 `apps/runtime-service/src/runtime_service/runtime/capabilities.py`，只定义不可变数据结构与纯校验。各 Graph 在现有注册装配处显式声明；不扫描插件、不探测 MCP、不构图触发模型或执行资源。

拟定 `GraphCapabilities` 最小字段：

| 字段 | 含义与约束 |
|---|---|
| `schema_version` | 能力描述版本，未知版本拒绝消费或明确降级 |
| `graph_id`、`internal_worker` | 受信注册身份；内部 worker 禁止普通用户直接新建 Run |
| `execution_modes` | Graph 实际支持的枚举，默认模式明确；不是任意 provider 参数 |
| `attachments` | 每种 MIME／扩展的上传、解析、预览及大小限制，声明不等于所有租户获准 |
| `artifacts` | 可交付种类与预览方式，不允许动态插入任意前端组件 |
| `message_queue`、`subagents` | 是否支持补充消息；普通／独立子任务能力及取消差异 |
| `skills`、`memory` | 是否提供该管理入口；具体已启用版本与 owner 在授权请求中获取 |

复用 catalog 同步，将能力快照接入 `RuntimeGraphCatalogItem`、对应 ORM 与 application service。快照内容代表实现能力，公开响应还要与当前用户／项目授权取交集。缓存带 revision／digest，撤销权限在执行时再次校验，不依赖 Web 隐藏按钮。

公共工具权限仍来自实现声明。图片等内部工具也必须进入该声明和实际工具执行边界，修复“用户 tools 配置排除后 internal 工具仍可调用”的缺口；不把技能描述当授权源。

### 3. 契约变更清单

以下是拟定业务契约，不宣称路由已经存在。普通 Thread／Run／流／cancel 继续走现有 `/api/langgraph` SDK 网关。新增资源路由按现有网关路径风格落地，最终 OpenAPI 名称在 P0／P2 冻结；不要求前端绕过网关直连 Runtime。

| 请求意图 | 输入／输出重点 | 授权与幂等 |
|---|---|---|
| 获取 Graph 能力 | graph、能力版本、有效模式／格式／功能 | catalog 项目权限；内部 worker 不公开成可选 Agent |
| 新建普通 Run | `context.execution_mode` 与现有 Context；有效模式回显 | 双端 Context v2 哈希，模型／工具交集；run 请求重试沿现有幂等契约 |
| 上传／读输入文件 | thread、SHA-256、MIME、字节数 → 04 的 FileRef | 创建线程后上传；受信 thread/graph 绑定；重复同摘要同内容复用、不同内容拒绝 |
| 列出／读输出产物 | thread、产物 ID／版本 → ArtifactRef；下载支持 Range | 只能读该线程已发布产物；不可提交任意宿主路径或外部 URL |
| 列出／控制独立子任务 | parent thread/run、task ID → child 官方状态或操作回执 | 05 的父子归属校验、operation 专属委托；取消 ACK 只表示已请求 |
| 补充运行中消息 | 原 message ID／内容与回执 | 复用既有队列；ACK=queued，checkpoint 证实后才 consumed；子任务不广播消费 |
| 查看／修改／删除记忆 | scope、事实、revision；来源与更新结果 | 当前用户／项目范围，revision 冲突返回 409；清空与晚到提取协调 |
| 上传／审查／启用技能版本 | 包引用、revision、哈希、审查／验证报告 | 候选不可执行；发布动作 HITL；批准绑定精确哈希，内容变化重新审批 |
| 外部长任务状态／控制 | 业务 task ID、远端已核实事实、产物引用 | 09 的持久记录＋授权；客户端不能给远端句柄和 callback URL 来替换任务 |

不得把公开“启用技能”的修改授权与一次聊天工具批准混为一谈：用户必须既有相应项目权限，又对该次副作用给出所需确认。

### 4. Token、scope 与兼容性

- 继续使用 `apps/platform-api/src/platform_api/core/security/tokens.py` 的受信委托。新增 operation 先列资源边界：读取文件、发布技能、读／取消 child、读／改记忆不能共用一个任意操作 scope。
- scope 从当前 Platform 主体、项目、服务端 graph/thread 绑定生成；Runtime 对每次 HTTP／工具执行重新核实，用户和模型不可自报 owner。
- 独立子 Run 的启动／读取／取消分别签发正确委托；长任务不能永久复用到期 token，后续由受控服务流程重新检查授权后签发。系统 worker 只获所需操作，不能替用户自动同意审批。
- Context v2 的规范化字段、默认值、tools 顺序、模式枚举由两端固定测试向量保证一致；全量搜索签发、校验、空哈希和恢复调用者。未知版本／被篡改上下文拒绝，不保留能绕过校验的兼容兜底。
- FileRef 与 ArtifactRef 不混用：上传是输入，产物是经核验的不可变输出版本。旧 Showcase 引用继续用其原 scope 版本解析，新 Agent 使用含 graph 的 scope；不批量移动历史文件。
- catalog 结构涉及持久表变化时使用当前 Platform 迁移流程；Runtime 私有表独立迁移。先加字段／后写入／再开放能力，失败时关闭新能力，不自动启动 DDL。

### 5. 事件与页面语义

| 展示内容 | 唯一事实来源 | Web 行为 |
|---|---|---|
| 根回答、工具调用和 Todo | 官方 messages／updates | 现有 `@langchain/vue useStream` 与 transcript 组件；无第二套消息缓冲或状态 reducer |
| 普通子 Agent | 官方子图 discovery、namespace、tool_call_id | `SubagentCard.vue` 按 `(parent_run_id, namespace, tool_call_id)` 关联；去掉同名 fallback，展开才按需订阅 |
| 独立子任务 | 受信父子映射＋child 官方 Thread／Run | 单独 SDK 订阅与详情；根 transcript 不混入 child 的模型消息 |
| 等待人工处理 | 官方 interrupt 集合 | `ApprovalPanel.vue` 区分动作批准与缺失信息；按 ID 恢复，重复／过期处理有明确反馈 |
| 文件交付 | 工具 artifact 中经过核验的 ArtifactRef | `ChatArtifactPanel.vue` 按格式预览／下载；正文裸路径不能自动获得文件读取权限 |
| 取消与断线 | 官方当前 Run 状态及重连结果 | 显示“取消中／重新连接／结果未知”，确认终态后再完成；HTTP 超时不等价于远端失败 |
| 用量 | 去重后的实际 usage 与调用记录 | 可展开根／子任务归属，缺失显示未知，不用估算冒充账单 |

不搬 DeerFlow 自定义 `task_started/task_running/...` SSE。确有官方事件不含的业务产物／远端任务信息时，只发送小型版本化业务 payload 供展示，持久事实仍可查询；不能让瞬时事件成为唯一状态源。

### 6. 专属前端目录与路由

产品显示名统一为 **Dear Agent**；后端服务目录／Graph 继续使用 `dearflow_agent`。这是同一产品的显示名和技术标识，不是两套 Agent。

| 完整目标路径 | 归属与创建时机 |
|---|---|
| `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue`（拟新增） | P1 页面组合根：项目／目标／URL／线程列表与会话挂载；不直接发 HTTP |
| `apps/platform-web/src/modules/dear-agent/components/DearAgentWorkspace.vue`（按需新增） | P2 专属工作区：上下文／会话导航、对话主区、单一 Inspector；复用全站 WorkspaceLayout 与 token |
| `apps/platform-web/src/modules/dear-agent/components/DearAgentWelcome.vue`（拟新增） | P2 能力导向欢迎区与任务示例，示例只来自已启用能力 |
| `apps/platform-web/src/modules/dear-agent/components/ExecutionModePicker.vue`（拟新增） | P2 有效模式选择；P2 开放 Ultra（普通同步子 Agent） |
| `apps/platform-web/src/modules/dear-agent/components/ClarificationCard.vue`、`apps/platform-web/src/modules/dear-agent/human-input.ts`（拟新增） | P1 文本／单选提问卡片及纯输入校验，P2 扩展多字段七种类型；状态来自官方 interrupt，schema 见 02 §6 |
| `apps/platform-web/src/modules/dear-agent/components/TaskPanel.vue`（拟新增） | P3 普通子任务、证据与已有用量投影；独立控制后置；P5 追加外部任务，复用官方详情组件 |
| `apps/platform-web/src/modules/dear-agent/components/ArtifactsPanel.vue`（拟新增） | P4 专属成果组织；底层文本／图片／文件卡片继续复用，P5 加媒体 |
| `apps/platform-web/src/modules/dear-agent/components/SkillsPanel.vue`（拟新增） | P4 只读可用技能／已选版本；P6 候选审查、验证、启用与回退 |
| `apps/platform-web/src/modules/dear-agent/components/MemoryPanel.vue`（拟新增） | P6 当前项目／用户偏好、来源、编辑／删除与冲突反馈 |
| `apps/platform-web/src/modules/dear-agent/composables/useDearAgentWorkspace.ts`（按需新增） | 页面复杂度确有需要才提取目标／能力／面板状态；不复制 `useChatSession`、Run 状态或 SDK 客户端 |
| `apps/platform-web/src/services/dear-agent/dear-agent.service.ts`、`types.ts`（拟新增） | 按前端规范承接专属能力／技能／记忆／任务 HTTP 契约；只增加既有 services 未覆盖的请求，不再包装一遍全部 Thread API |
| `apps/platform-web/src/services/threads/`、`services/agents/`、`services/langgraph/`（现有） | 继续负责通用线程、Agent、鉴权与官方 SDK；公共文件／任务行为优先复用真实调用点 |
| `apps/platform-web/src/router/routes.ts`（现有） | P1 路由与导航 metadata；统一权限守卫，不做另一套导航 registry |
| `apps/platform-web/src/modules/dear-agent/**/*.spec.ts`、`apps/platform-web/e2e/dearflow-agent.spec.ts`（拟新增） | 各阶段随能力增加的组件／会话与真实链路测试，E2E 沿用已有命名规划 |

以上为职责地图，按阶段创建文件，不在 P1 建空面板／空 composable。前端业务放专属模块，网络请求仍按当前规范放 `src/services/`，不能为了“一个目录”把裸 HTTP 塞进页面。测试和类型遵守相邻模块现有习惯。

拟定路由：`/workspace/projects/:projectId/dear-agent/:threadId?`，名称 `workspace-dear-agent`，沿用 `WorkspaceLayout`。`meta.requiredPermissions` 使用现有项目读权限，发起运行／编辑／删除等动作通过 `useAuthorization()` 再检查对应写权限；平台未配置 DearFlowAgent 时显示配置缺失与有权限的操作入口，不自动建立 Agent 或授予权限。

由 Platform Agent 目录选择 graph 为 `dearflow_agent` 的授权配置；一个项目存在多个配置时显式选择 `agentId`，不得硬编码某条数据库 ID。已有线程以受信 thread→graph／Agent 绑定为准，URL 参数不能切换它的运行身份。专属列表在服务端过滤目标 graph，按需过滤 agentId；当前 `createSessionService.list` 是项目级列表，需要核对并补官方搜索／网关白名单，不能只过滤当前 20 条后错误计算分页。

项目／登录身份／Agent／线程切换时销毁旧会话并重新挂载，沿用 session epoch 丢弃迟到响应。草稿按用户／项目／Agent／线程隔离；新建线程后更新 Dear Agent 自己的 URL。通用 Chat 路由继续有效，不自动重定向所有旧聊天，不迁移／复制其线程数据。

### 7. Chat 基线复制与专属界面演进

**已确认决策：** 为避免两个产品的布局、交互和状态展示互相牵制，将首发必需的 Chat 业务代码复制到 `apps/platform-web/src/modules/dear-agent/`。复制是一次基线快照，完成后分别维护；不持续挂载原 `ChatSession`，不要求原 Chat 为 Dear Agent 增加 slots 或产品开关。这一决策替代此前“共享 Chat 组件、逐步增加组合接口”的方案。

#### 7.1 复制范围与共用边界

以下源文件均位于 `apps/platform-web/src/modules/chat/`。F0 根据真实 import 链冻结清单；只复制首发闭环所需文件，不整目录搬运。

| 源代码／能力 | 目标与处理 | 继续共用的边界 |
|---|---|---|
| `pages/ChatPage.vue`、`components/ChatSession.vue` | 作为 `pages/DearAgentPage.vue`、`components/DearAgentSession.vue` 的基线；替换专属 URL、授权目标、欢迎区和面板装配 | 全站 WorkspaceLayout、路由守卫与权限规则 |
| `components/ChatThreadSidebar.vue`、消息渲染、输入框、工具结果组件 | 首发需要的组件复制到本模块 `components/`；内部引用全部指向本模块 | 基础 UI、图标、样式 token、公共下载工具 |
| 附件、`ApprovalPanel.vue`、`SubagentCard.vue`、`SubtaskDetail.vue` | 复制 UI 和交互逻辑；澄清卡片新增于本模块；关联／状态缺陷在副本中修复 | 文件 HTTP、官方 interrupt／resume、namespace 协议不另造 |
| `composables/useChatSession.ts`、`useChatAttachments.ts`、实际需要的 transcript composables | 将产品会话编排复制为本模块 composables，主会话建议命名 `useDearAgentSession.ts`；删除无关产品分支 | `src/services/` 的现有请求与官方 SDK 客户端、鉴权、项目上下文 |
| `transcript.ts`、业务类型及相邻测试 | 复制必需的纯展示转换、状态投影和有效行为测试；按 Dear Agent 路由及能力调整断言 | 公共 API 类型继续从 services 引用，不复制协议 DTO |

目标结构按实际文件创建：`pages/`、`components/`、`composables/`、`transcript.ts`；专属类型与纯校验按相邻规范放置。`types.ts`、`index.ts` 只有实际消费者需要时才创建，不建空导出或未来面板。

网络请求统一保留在 `apps/platform-web/src/services/`。复制后的 composable 可以调用 services 的动作和官方流封装，不在 `modules/dear-agent/` 中复制 SDK 客户端、裸 HTTP、鉴权刷新或错误拦截器。新增业务请求只补 `src/services/dear-agent/`，通用 Thread／Run 请求沿用原 services。

**隔离约束：** Dear Agent 的业务组件、composable、类型、测试不得 import `modules/chat/`；Chat 同样不得反向依赖 Dear Agent。两者可以依赖公共模块，公共模块不得反向 import 任一产品模块。复制的是代码，不是线程数据、草稿数据或服务实例；草稿与 URL 仍按本章 §6 隔离。

#### 7.2 各阶段施工与交接

1. **F0/P0：冻结基线。** 阅读前端规范，记录来源文件、目标文件、实际依赖、复制时的源码版本或内容摘要，以及排除项。清单写入本项目当次 implementation 记录，不另建长期同步系统。确认哪些调用继续由 services 承接。
2. **F1/P1：完成最小副本闭环。** 复制页面／会话／消息／输入／附件／审批／子图详情所需实现和测试，替换内部 import、专属路由及目标限制。接通当前阶段的澄清卡片。每个挂载会话只有一个官方 stream controller，沿用销毁和 session epoch 机制；不在父页面重复开流。
3. **F2/P2：专属适配。** 在副本内实现欢迎区、模式选择、完整提问表单、能力提示和面板布局；不为此修改 Chat props／slots 或增加 `isDearAgent` 分支。
4. **F3—F6：增量业务。** 子任务、成果、Skills、记忆及外部任务在本模块迭代；共享服务的契约变更仍要验证所有消费者，产品组件变更只通过明确的修复同步影响另一边。
5. **F7/P7：生产验收。** Dear Agent 有独立组件测试和 E2E；确认无跨产品 import、重复客户端或双 controller，验证共享基础服务的回归及两套入口可同时正常使用。

#### 7.3 缺陷修复与同步规则

复制后允许 UI 代码有重复，这是换取产品独立演进的明确取舍，不立即再抽回共享 Chat 层。原 Chat 的改动不会自动合并到 Dear Agent。

- Dear Agent 专属交互缺陷只修本模块。发现副本继承的 Chat 缺陷，核对原实现是否仍存在；仍存在且属于本次范围时，分别修复并记录两边验证结果。
- 网络、鉴权、API 类型和基础 UI 的问题在现有公共位置修复，并验证 Chat 与 Dear Agent；不在两个副本分别补协议补丁。
- 安全、数据丢失和协议兼容修复必须检查另一消费者是否受影响；适用时同步修复，不靠人工记忆。implementation 记录列出“影响另一模块／同步位置／验证证据／不适用原因”。
- 不自动批量同步目录，不复制 SDK，不创建通用 renderer 注册系统。只有两边出现稳定且真实相同的需求时，另行评估提取公共能力。

#### 7.4 验收与完成定义

- F1 的新建／续接、消息、附件、审批、澄清 resume、子任务详情、停止与断线恢复，均从 Dear Agent 路由验证；不能仅因复制完成就标验收通过。
- 静态检查两个模块无互相 import；复制后的专属测试不通过 mock 原 Chat 组件绕过实际副本。
- Dear Agent 展示变更不要求调整原 Chat 接口；共享请求服务变更要有两个入口的回归证据。
- 同一页面无重复流／重复请求，离开页面取消订阅，切换用户／项目／线程时丢弃迟到响应；复制不产生第二套 Run 状态事实源。

### 8. 前端分阶段交付与验收

本表是前端 F 任务的唯一明细；10 只映射阶段并汇总门禁。每行交付必须包含 loading／empty／error／forbidden、键盘操作和响应式表现。

| 任务／阶段 | 用户可使用的内容 | 必需对接与前置 | 必须通过的验收 |
|---|---|---|---|
| F0／P0 | 尚不开放产品；确认路由、Chat 复用边界和契约样例 | 01 的 S0—S4；当前 ChatPage／ChatSession／session service；08 W01—W07 | 形成接口／文件落点记录；验证只有一个根 controller；目录不含空业务壳 |
| F1／P1 | 独立 Dear Agent 导航与页面；新建／续接会话，基础上传、官方审批、文本／单选澄清、文件下载 | 02/C04-b；04 工作区；W01 最小能力、W03 文件、W05 基础交互、W07 目标列表；提问区域最小 slot 本阶段即交付 | 专属 URL 刷新可用；TXT→澄清 resume→受限处理→审批→下载；两类中断不混用，无双 controller，通用 Chat 回归 |
| F2／P2 | 专属欢迎区／布局、Flash／Standard／Pro、全部七种字段表单、有效模型／格式提示、引用、补充消息 | 02/C04-c 与 Context v2；03 搜索／证据；W01 扩展能力、W02 模式、W05 队列／表单 | 字段校验／错误恢复／多字段回答正确；Ultra 未就绪不开放；引用可定位、queued 不误标 consumed |
| F3／P3 | Ultra、任务计划、普通子任务列表／详情、父 Run 取消反馈、结果证据、已有用量；本轮 deferred，只交接 | 05 普通子图与 W04；v2默认、显式v3 lifecycle透传和真实回放已验。data.namespace／cause关联、resume及历史兼容限制见 frontend-handoff.md 与08实施记录 | 同角色两个任务不串线，父取消保留已完成结果，刷新还原，取消中／未知／部分完成准确显示；不提供单子任务取消 |
| F4／P4 | K01—K11 对应研究／表格／图表／网页成果；技能只读目录与运行选中版本；成果 Inspector | 07 顺序验收＋03 EvidenceRef＋04 格式矩阵；SkillsPanel 仅只读，写入留 P6 | 每 K 在 Dear Agent 页面真实交付后才启用；PDF／表格／图片／网页隔离预览或真实下载；来源与产物关联正确 |
| F5／P5 | 当前K12图片、K13 PPT页图／下载；K14/K15延期；K16视频及音视频大文件后续实施（deferred） | 图片回执＋官方HITL＋PPTX文件代理 | 交接done、页面deferred；具体字段／路由见[前端交接F5](frontend-handoff.md)，音视频Range不冒称可用 |
| F6／P6 | K17—K23 技能审查／评估／发布／回退、记忆查看修改／删除、引导偏好、组合任务和审批发布 | 06 记忆；07 管理底座；W06 管理接口；D5 改写范围获批 | 候选不自动执行，发布绑定 hash；版本冲突有反馈；记忆不串用户项目／删除不复活；K22 外发经审批、K23 按批准口径验收 |
| F7／P7 | 完整 Dear Agent 专属前端与可复现生产展示场景 | 所有必要能力真实验证，V01—V12 | 独立入口完整链路、深浅色／移动／键盘／断线／撤权、与通用 Chat 并存回归、发布关闭与回滚演练 |

F4—F6 的每个 Skill 先复用消息／工具卡片／文件预览已有表达，只在无法清楚表达任务状态或结果时增加专属组件，不为 23 个 Skill 各造一页。开发中的固定响应样例只用于测试，正式入口不能用 mock 成功冒充后端交付。

生产展示最少覆盖：研究＋引用报告、表格分析＋图表文件、并发子任务＋单取消、一次媒体长任务恢复、技能审查发布＋偏好修正。展示数据与账号使用隔离演示项目，但服务代码必须与生产路径相同，不在 Showcase 初始化假数据或特殊绕权。

### 9. 契约接续登记

跨章节引用以下稳定 C 编号。此表只记录所有者、消费关系和冻结阶段；字段／错误细节仍以对应设计和最终代码 schema 为准，不维护第二套 OpenAPI。每项实施记录须补最终路由、请求／响应样例、权限、版本、源码／测试链接和验收状态。

| 契约 | 事实所有者 → 消费方 | 设计来源／冻结与交付阶段 | 当前状态 |
|---|---|---|---|
| C01 目标、路由、线程列表／绑定 | Platform Agent 目录＋Runtime Thread → Dear Agent 页面 | 本章 §6；P0 冻结、P1 交付；W07／F1 | P1 后端注册／创建／绑定通过；页面筛选分页另验，见 05 |
| C02 Graph 有效能力 | Runtime 静态声明＋Platform 授权 → 前端 | 本章 §2；P1 先交付文件／Standard 最小描述，P2 扩展；W01 | P2 保持 schema_version=1，增加 execution_modes、clarification_field_types、research、message_queue；代码 capabilities.py，前端交接见 frontend-handoff.md |
| C03 运行 Context／模式 | Platform 签发＋Runtime 校验 → 官方 SDK | 02；P0 确认兼容策略、P2 v2，P1 用当前批准版本；W02 | P2 双端 v2 哈希与模式恢复不可变测试通过；旧无模式继续 v1，新 Dear 默认 standard；真实部署门禁见 P2 执行包 |
| C04 文件／产物 | Runtime workspace → Platform 文件代理 → 前端 | 04；P0 冻结基础引用、P1 基础文件、P4／P5 扩格式；W03 | P1 TXT通过；P4增加ZIP输入、MD/BibTeX输出，P5增加图片型PPTX输出；现有URL／字段不变；见[10批次](implementation/10-p4-k02-k07-batch.md)，前端仅交接 |
| C05 流／审批／提问／消息队列 | 官方引擎／既有 Runtime 队列 → SDK／Chat 复用层 | 02 §6／05／本章 §11；P1 文本／单选与工具审批，P2 完整表单／队列，P3 子图；W05 | P2 后端七字段及 queued/consumed 接入完成；保持官方 interrupt ID/resume，不新增终止协议；前端七字段／来源／队列后置，部署证据见 06 |
| C06 child 展示归属／基础用量 | 普通子图 namespace＋调用 ID → Platform → TaskPanel | 05；P1/P2 复用与修复；独立控制和独立用量 deferred | 待开始 |
| C07 技能版本／发布 | Runtime 技能存储＋Platform 授权 → SkillsPanel | 07；P4 只读，P6 管理／发布；W06 | 待开始 |
| C08 记忆／偏好 | Runtime 唯一事实存储＋Platform 授权 → MemoryPanel | 06；P0 存储风险验证、P6 CRUD 与提取；W06 | 待开始 |
| C09 外部任务／交付 | Runtime 私有图片回执＋官方工具结果 → 专属前端 | 09；P5图片切片 | task_id/status/result/error_code；查询走get_media_task工具，无新增REST；远端任务／outbox／自动续接deferred |

任何一章变更这些契约，必须同时检查表中生产者和消费者并回填本表链接，不能仅改一端后把章节标 done。内部 worker graph 不属于 C01 可选产品列表；`agentId`、`graphId`、`threadId` 的绑定必须服务端验证。

### 10. 错误与副作用反馈

沿用当前标准错误 envelope，不单独定义 DearFlow 错误壳。新增明确业务 code：无效模式／上下文版本、资源 scope 不匹配、技能版本冲突、外部任务提交未知等。HTTP 状态保持语义：401 未认证、403 未授权；防枚举策略下资源不可见使用统一 404；409 revision／幂等冲突；413 过大；415 不支持格式；422 内容／参数无效；429 配额；502／504 下游失败／超时。

502／504 不自动推导“副作用没发生”。发生过提交的请求返回可查询的业务 ID 和未知状态；Web 不诱导用户反复点击重做。错误、审计、trace 不记录 token、claim URL、完整用户文件内容。

### 11. C05 提问与审批的详细实施

#### 11.1 当前能力与实际缺口

`apps/platform-web/src/modules/chat/approvals.ts:parseReviews` 将每个 interrupt 当成工具审批解析，当前只接受 approve／edit／reject。`useChatSession.ts:approve` 会重读状态、比对 fingerprint，构造 responses，调用 `stream.respondAll`；这条传输和幂等基础可复用，不能新写一套 resume 客户端。

DeerFlow 的问题卡片来自 ToolMessage.artifact，本方案的待回答问题来自官方 `stream.interrupts` 中的 `value.kind="clarification"`。历史工具消息只用来回看已回答问题，不能因为消息里出现一个问题就激活可提交卡片。详细请求／回答 v1 唯一来源为 [02 §6](02-agent-composition-and-modes.md)。

#### 11.2 前端组件、状态与动作分工

| 文件／符号 | 实施改动 |
|---|---|
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | 保留单一 SDK controller；暴露全部 pending interrupts 与 `hasPendingInterrupts`；原 approve 和新澄清提交共用私有 `resumePending(responses, expected)`，重读状态、核实 ID／fingerprint／scope、调用现有官方 respond API 并核实结果 |
| `apps/platform-web/src/modules/chat/approvals.ts` | `parseReviews` 只处理确实为官方 action_requests 的中断；保留 buildReviewResponses 的 action 数量／顺序／allowed decisions 校验。不能把过滤后的 reviews.length 当成所有中断数量 |
| `apps/platform-web/src/modules/chat/components/ChatSession.vue` | P1 增加最小待输入区域 slot，传只读 interrupt 与受控提交动作；现有 ApprovalPanel 继续处理工具审批。未知中断有只读提示和取消／重连入口，不能丢弃 |
| `apps/platform-web/src/modules/dear-agent/human-input.ts`（拟新增） | `parseClarification`／`validateClarificationAnswer`／`buildClarificationResponse` 纯函数，识别版本和字段，生成标准 resume 的值；不创建网络客户端 |
| `apps/platform-web/src/modules/dear-agent/components/ClarificationCard.vue`（拟新增） | 问题／背景／字段／必填／局部错误／提交反馈；复用现有表单和按钮；由 DearAgentPage／Workspace 插入共享会话 slot |
| `apps/platform-web/src/modules/chat/run-actions.ts` | 沿用现有 send／resume／fork 的动作快照与 SDK 批次归一；增加非 decisions 值的回归测试，不为 clarification 增设发送通道 |

提问卡片的草稿仅为 UI 状态，键包含用户／项目／thread／namespace／interrupt ID 和请求 fingerprint；请求内容变化或身份切换立即失效。不得让模型提供的 field name 直接污染普通对象原型。提交期间禁重复，未知／失败保留草稿；只有确认该回答已消费或进入明确后续状态才显示已提交完成。HTTP ACK 本身不证明后续任务成功。

`hasPendingInterrupts` 覆盖审批、澄清和未知类型，统一控制普通发送、运行中消息入队及“正在等待用户”的文案；不能因为 parseReviews 过滤了澄清就允许 send 覆盖正在等待的计算。用户在输入框直接打出答案也不能当新 human 消息自动绕过恢复：需要明确选择对应问题并通过同一表单校验提交。

P1 slot 只为真实提问消费者引入；P2 再扩欢迎／选项／Inspector 插槽，修正此前“所有扩展点都等 P2”的阶段依赖。共享 Chat 模块不导入 Dear 私有卡片，卡片不再调用 `useChatSession`。

#### 11.3 两类回答如何经过同一官方 resume

工具审批仍为：

```json
{"<官方审批interrupt-id>": {"decisions": [{"type": "approve"}]}}
```

澄清回答为：

```json
{"<官方提问interrupt-id>": {"schema_version": 1, "status": "answered", "values": {"period": "quarter", "language": "中文"}}}
```

两者都作为官方 `Command.resume` 的 ID 映射；客户端继续通过当前 SDK `respondAll`／经验证的单 interrupt respond 接口，现有 `run-actions.ts` 将 SDK batch 归一为 Platform `input.respond`。不发送 DeerFlow `human_input_response` 消息，不新建 `/dear-agent/answer` 执行端点，不在同一请求里附加新 messages／mode／model／tools。

一个工具审批 interrupt 可能包含多个 action，它的 decisions 仍必须全部匹配；多个独立 interrupt 可以按用户实际完成的项目提交合法子集，不能自动批准未填部分。实际 SDK 对部分恢复与子 namespace 的行为在 P0／P3 验证。独立 child 用 child 自己的受信会话提交，不混入根 thread ID map。

#### 11.4 Platform 预校验与恢复幂等

现有 `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` 的 `input.respond` 已检查当前 interrupt ID、原 Run interrupted 状态、Agent 归属和原请求快照，然后新建携带 `command.resume` 的 Run。继续复用该路径和 RunRequestsRepository，不另建等待回答表。

需要补齐的步骤：

1. 在首次接受 resume、创建幂等记录之前，从受信 state 的当前 interrupt 读取请求内容。对 `kind=clarification` 的已支持版本，按字段声明验证答案；未知版本拒绝提交。schema 不采信客户端重复传来的 question／fields。
2. 前端负责即时错误，Platform 做通用交互契约预校验（类型、必填、枚举、额外字段、预算），Runtime 工具做最终业务校验。Platform 不导入 Runtime 服务私有 Python 模块；拟在 `modules/runtime_gateway/application/human_input.py` 放小型通用验证函数，两端用相同 JSON 测试向量验证一致性。它只验证公开输入契约，不承担 Agent 业务决策。
3. 格式错误返回 422 与字段定位，保持原中断可回答，不能先消费 resume 再要求用户修正同一个已用幂等键。用户无权限、ID 过期／来源不符、内容版本变化分别沿现有 403／409 语义处理。
4. 相同恢复目标和相同答案重试返回原操作；相同目标不同答案冲突，不能静默复用旧回答。网络超时先查原动作／Run 状态再重试，禁止换 ID 重发。
5. **需要先验证的现有缺口：** 当前 key 按排序后的 interrupt IDs 构成，不能未经证明就认为同一节点中的再次 interrupt 一定生成全新 ID。P0 必须测试连续提问、无效回答和重放；本方案避免靠工具内无界重复 interrupt 处理表单错误。
6. 若锁版本确实出现同 ID 不同待恢复 checkpoint，恢复幂等应绑定受信 originating Run／checkpoint＋interrupt 集合，并保留稳定请求 digest。为区分重试与新一轮，必要时给现有命令增加受限的预期 checkpoint 字段，服务端核实后使用；这属于 C05 契约修订，必须同步官方 SDK 包装、白名单、两端测试及旧操作排空／兼容策略。未验证前不预建新协议或声称已解决。

仅靠前端 fingerprint 比较不足以防止绕过页面直接请求；服务器必须依据当前持久状态校验。模型参数／工具权限仍由原配置快照恢复，答案中的同名字段不能覆盖它们。敏感答案不进入普通审计日志或默认长期记忆。

#### 11.5 可执行验收清单

| 用例 | 必须观察到的事实 | 拟验证位置 |
|---|---|---|
| 文本／单选回答 | 官方中断可见，同 thread resume 后工具拿到准确值，没有新 human 消息冒充恢复 | Runtime `test_human_input.py`、Web `human-input.spec.ts`、专属 E2E |
| 七种字段及多字段 | required／选项／number／date／boolean／额外字段校验一致，422 后原问题仍可提交 | 两端固定 JSON 样例、`ClarificationCard.spec.ts`、Platform `test_runtime_gateway_human_input.py` |
| 提问与执行混批 | 在回答之前和混批修正期间，execute／付费调用计数为零 | Runtime `test_clarification_batch_guard.py`，包含 invalid_tool_calls |
| 工具审批并存 | approve／edit／reject 原语义不变，澄清不出现批准按钮，未知类型不放开普通发送 | `approvals.test.ts`、`ApprovalPanel.spec.ts`、`useChatSession.spec.ts` |
| 双窗口／未知提交 | 相同答案去重、不同答案 409、ACK 丢失查回同一 Run；不重复副作用 | Platform 网关＋真实引擎 integration／durable |
| 重启／取消／撤权 | 恢复 pending 问题；取消／撤权后旧回答不能继续任务 | Runtime durable＋Dear Agent E2E |
| 根／子任务 | 两个同角色 child 的问题、答案、审批及费用不串 | 05 生命周期测试＋SubtaskDetail 回归 |
| 旧版本／未知字段 | 明确不支持或按批准升级路径恢复，不能剔除字段后伪称表单完整 | UI／Platform／Runtime 契约矩阵 |

新测试完整目录分别为 `apps/platform-web/src/modules/dear-agent/`、`apps/platform-web/src/modules/chat/`、`apps/platform-api/tests/`、`apps/runtime-service/tests/services/dearflow_agent/`，持久测试位于 `apps/runtime-service/tests/durable/test_dearflow_human_input.py`；路径按所属用例选择，不生成一套重复测试框架。

## 任务拆分

- [ ] W01：统一能力声明与 catalog 快照，拟修改 `apps/runtime-service/src/runtime_service/webapp.py`、`runtime/capabilities.py`；Platform `modules/runtime_catalog/domain/models.py`、`infra/sqlalchemy/models.py`、`application/service.py`。替换每处 graph 特判并保留旧 Graph 回归。
- [ ] W02：Context v2 双端与 Web 模式；目标见 02。拟补 `apps/platform-api/tests/test_runtime_gateway_runtime_contract.py` 与 Runtime resolver 测试向量。
- [ ] W03：解除文件 Showcase 耦合，新增 `apps/runtime-service/src/runtime_service/http/artifacts.py`（拟新增），扩展现有图片／文档路由；Platform `modules/runtime_gateway/presentation/http.py`／`application/service.py` 及已有 files/images 网关测试。
- [ ] W04：按 05 接入子任务归属、operation 委托及官方 SDK 控制，完善 `SubagentCard.spec.ts`、`SubtaskDetail.spec.ts`；同角色并发和单取消必须真实联调。
- [ ] W05：按 §11 完成官方审批／澄清的共同恢复、Platform 预校验与幂等核对，完善 `useChatSession.spec.ts`、`ApprovalPanel.spec.ts`／`approvals.test.ts`／`run-actions.test.ts`；队列沿 P2 交付，所有 pending 中断期间不广播注入消息。
- [ ] W06：P4 先交付已启用技能只读目录／版本；P6 再交付技能与记忆 HTTP 薄入口、授权审计、专属面板和版本冲突反馈；业务实现分别在 06／07，不在 HTTP 重写规则。
- [ ] W07：Dear Agent 目标解析与线程服务端筛选／分页，复用 `services/agents/agents.service.ts`、`services/threads/session.service.ts` 和官方 SDK；补网关搜索白名单／归属测试，未知绑定不猜测。
- [ ] F0：P0 完成 §6—§9 的前端复用／契约检查记录。
- [ ] F1：P1 完成独立页面与真实基础链路，新增 `DearAgentPage.spec.ts` 和既定 E2E 文件。
- [ ] F2：P2 完成最小 Chat 扩展点、专属工作区／欢迎区／模式／引用／队列。
- [ ] F3 deferred：用户确认本轮只做后端，前端保留交接；需接普通子图关联／父取消／usage，补已有 Chat 回归。实际字段及缺 discovery 降级见 [前端交接](frontend-handoff.md)，不将后端测试计为浏览器验收。
- [ ] F4：P4 随 K01—K11 逐个验收成果区和只读技能目录。
- [ ] F5：K12/K13交接done，页面deferred；K14/K15延期；K16视频和音视频大文件／Range后续实施（deferred），见frontend-handoff。
- [ ] F6：P6 完成技能／记忆管理及 K17—K23 专属交互。
- [ ] F7：P7 完成专属前端收口、展示用例、并存回归和生产验收。

## 验证要求与记录

- [ ] Dear Agent 独立路由完整链路：选择授权 Agent 配置 → 设置模式 → 上传文档 → 官方提问／审批 → 工具／子任务 → 文件预览和下载 → 刷新恢复。
- [ ] 新目录拥有专属产品 UI；通用 Chat 不反向依赖 `modules/dear-agent/`，共享会话不含 Dear 专属条件分支；同一根会话只创建一个 controller。
- [ ] 目标 graph／Agent 的服务端线程筛选、分页、深链接与新建 URL 正确；当前项目／身份切换丢弃旧请求，通用 Chat 并存回归通过。
- [ ] 所有公开请求的未登录、跨项目、角色受限、过期委托、撤权、内部 worker 直连与伪造引用负例。
- [ ] 两个同角色任务消息与审批不串；单取消仅影响目标任务，子 Run 超时后 UI 不误显示成功。
- [ ] 重复上传／重复 resume／重复提交、断网重连、旧线程／旧文件兼容；Context v2 两端哈希一致。
- [ ] 上传／产物大文件流与 Range、HTML 隔离、移动与键盘操作；新增面板四态完整。
- 2026-09-13：完成现状定位和拟定契约；没有执行接口、前端或端到端测试。
- 2026-09-14：按用户确认的独立前端方向修订目录、Chat 复用路径、F0—F7 与 C01—C09；仅静态核对现有源码，尚未实现或执行前端测试。
- 2026-09-14：补充 C05 提问表单、统一恢复、Platform 回答预校验、连续中断幂等风险及测试矩阵；P1 提前交付最小提问 slot，P2 完整表单，P3 子任务；功能未实施。

## 状态

### P1 当前落点更新

- `GET /api/langgraph/threads/{thread_id}/capabilities` 已接入线程／目标授权、签名委托与 Runtime 内部能力接口，响应走现有脱敏逻辑。
- `input.respond` 在创建恢复 Run 前校验 text/select 澄清回答；失败为 422／`invalid_clarification_answer`，不消耗回答、不创建恢复 Run。
- Dear Run 使用 `durability=sync`。产物读取仍走既有 `files/content` 路由，支持 outputs；缺失文件 404、错误哈希 409。
- 代码路径、测试类型和未覆盖部署边界见 [04 实施记录](implementation/04-p0-p1-foundation-closeout.md)。本轮没有前端改动，原规划中的完整前端联调不因此勾选完成。

部分完成：P1 最小后端契约和精确路由已冻结，真实平台文件及 Worker 重启链路通过，见 [05 契约与部署证据](implementation/05-p0-p1-deployment-verification.md)。前端浏览器联调、C06—C09 正式业务及后续扩展不据此标为通过。

2026-09-15 K08—K11增量：Excel两类输入、HTML/CSS/JS源码、CSV/JSON/ZIP产物、Dear图片授权下载，以及文件attachment／nosniff／sandbox响应已接入。验证边界与代码位置见[11批次记录](implementation/11-p4-k08-k11-batch.md)，前端只交接，隔离预览未实现。

## P6 契约实施增量（2026-09-15）

C07/C08/W06新增Dear私有治理HTTP：公开`GET/POST /api/langgraph/threads/{thread_id}/dear/{memory|skills}`，平台验证项目读写与Dear线程，使用`dear-governance-read/write`委托Runtime内部同名资源。GraphHarbor不参与业务CRUD。写入必须expected_revision，冲突409；严格拒绝额外字段和客户端review/evaluation裁决。当前技能HTTP仅返回自定义版本，公共目录通过Agent的list_skills工具查看。

后端代码与集中测试见[13](implementation/13-p6-memory-and-skills.md)，F6字段/审批/错误展示已[交接](frontend-handoff.md#p6-增量交接2026-09-15后端验证结果见13记录)，页面验收deferred。K23后置，不实现平台操作桥接。
