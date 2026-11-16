# 平台内置助手方案

## 1. 目标与已确认决定

普通平台用户在当前页面打开助手，可以咨询用法、交流想法，也可以提交错误信息。助手根据用户权限读取实际数据，完成分析和指导；研发用户另可读取获准源码。用户面对同一个助手，无需先选择专家类型。

2026-11-16 用户明确确认以下方向：

1. 所有平台用户可用，数据权限分层；“助手能力较广”不等于所有用户获得同样的数据范围。
2. 第一版采用单 Agent 加工具，覆盖智能排障、使用指导、资料检索、聊天和创意交流。
3. 后端和Agent的组件复用由本次开发者决定，可以直接引用或复制适合的装配骨架。前端组件和页面组织由前端同事决定，本次只交付后端、Agent和可执行的前端交接文档。
4. 助手可以读数据库、日志和代码。数据库默认仅有读取权限；单独暴露且授权的写入/修改/删除工具也必须先由用户在前端选择“执行/不执行”，不能自行执行。正常读取不要求确认。
5. 使用指导优先用文档，源码仅向获准研发开放。
6. 要梳理越权查询、资源关联与信息使用记录，不通过每次读取弹确认来替代系统权限。
7. 技术方案采用create_agent，不采用DeepAgents，不为助手创建执行沙箱；数据库、日志和资料均通过工具读取。保留持久历史与会话内记忆，第一版不新增跨会话长期个人记忆。

**改动级别：治理改动。** 整体涉及三服务、新的数据读取入口及日志访问边界。2026-11-16用户进一步明确本次开发交付为后端、Agent及前端交接，前端代码由同事实施。本次具体实现与本地资源范围已按追加决定落实，详见第9节及backend-operations.md；不把本地实施授权推定为生产访问授权。

**交付分工：** 本次负责Platform API、Runtime/Agent、后端联调和测试、前端交接文档；前端同事负责页面实现与组件选择。后端交付验收和全栈联合验收分别记录，不能等前端完成才确认已满足自身标准的后端任务，也不能用后端验收代替浏览器验收。交接完成要求见[frontend-handoff.md](frontend-handoff.md)。

**实施授权（2026-11-16追加）：** 用户要求先提交当前版本到源代码仓库，再持续开发直至后端、Agent及前端交接完成。本轮据此开始开发、隔离环境验证及功能分支交付；已批准的单Agent、只读/写审批、分层授权和日志治理方向不重复确认。未指定的真实生产资源不自动接入，生产部署未授权。

本方案替代前轮口头建议中“仅固定业务查询”的限制：第一版保留授权范围内的灵活只读查询能力，包括必要的结构发现、过滤、关联和聚合。不会以“没有失败 Run ID”为由拒绝所有调查。

## 2. 业务流程

### 2.1 从错误现场排障

用户从错误弹窗打开助手，预览诊断摘要后发送，也可以手动粘贴现有诊断包。上下文包含页面路径、发生时间、可获得的错误码/请求编号/运行编号及部署版本。缺失字段标明未知，不要求用户先手动收集全部信息。

Platform API 根据当前身份确认目标项目、Thread/Run 或请求的可见性，再返回结构化诊断。助手按需要查关联日志、配置摘要和数据库记录，组织为“判断—证据—处理建议—未知项”。同一次调查可以继续追问，不强制多轮点击批准。

发生在创建 Run 之前的错误或纯前端错误，使用已授权的项目、页面、时间范围及请求信息取证。获准运维/研发可以按环境、服务、时间和错误特征进行较宽范围的读取，不仅支持按 Trace ID 查询。仍不能把用户提供的项目 ID、Trace ID 或日志文字当成授权。

助手使用自己的 Thread/Run；被诊断的 Thread/Run 是目标资源，记录在单独的调查上下文中。不向失败业务会话注入排障消息，不因打开助手而重跑原任务。

### 2.2 使用指导

先检索与部署版本匹配的产品文档和操作手册，给出步骤、来源和当前用户可访问的页面入口。资料缺失、过期或版本不匹配时明确说明，不编造菜单、权限或功能。

需要解释实现或定位代码缺陷时，仅为具有源码权限的研发用户检索获准仓库快照。代码来源需要仓库标识、revision、相对路径和行号；文档需要来源、版本/更新时间和章节定位。

### 2.3 聊天、资料和创意交流

普通聊天和创意讨论直接使用模型；需要实际平台数据或外部事实时才调用对应工具。设想与实际系统状态分开表达，工具失败不伪装成已查证。公开资料检索不默认携带内部日志、SQL结果或私有源码。

保留现有会话历史，不在本项目默认新增跨会话个人画像或长期记忆。助手自身或主运行链路不可用时，前端保留本地错误解释、诊断复制与人工处理入口，不递归调用助手排查助手。

## 3. 架构与执行方式

| 层次 | 职责 | 主要接入位置 |
|---|---|---|
| Platform Web | 全局入口、抽屉、消息流、上下文预览、来源与操作入口 | apps/platform-web/src/layouts/WorkspaceLayout.vue；modules/chat；新增 modules/platform-assistant |
| Platform API | 当前身份与资源授权、数据源绑定、查询接入、脱敏、查询审计 | apps/platform-api/src/platform_api/modules/runtime_gateway；modules/observability；modules/audit；新增 modules/platform_assistant |
| Runtime Service | 受管执行、模型、工具调用、取消/预算/恢复、追踪 | apps/runtime-service/src/runtime_service/runtime；middlewares；graphs |
| 助手 Agent | 理解意图、选择工具、补充询问、组织证据和答复 | 新增 services/platform_assistant |
| 数据源 | 平台数据库、运行事实、日志、产品资料和代码快照 | 各自已有存储/服务；只通过获准连接读取 |

主链沿用 Web → Platform API → Runtime/GraphHarbor。Agent 工具通过受信的业务查询入口读取资源；内部调用携带服务端绑定的用户、项目、助手运行和用途，不给模型传管理凭据，也不让模型自行声明权限。已采用固定路径 /api/platform-assistant/internal/read，HMAC绑定platform-assistant用途、规范JSON和30秒时间窗；服务端重新加载身份并核对助手Thread/Run与当前启用状态。没有增加Delegation operation或Context字段。

单 Agent 从reference_agent的create_agent组合方式起步，复用必要中间件；不用create_deep_agent，不创建本助手的Docker/远端执行沙箱，不挂载shell或任意代码执行工具。SQL由数据库工具执行，源码由只读检索服务提供，聊天状态由现有持久化底座保存，这些能力不要求Agent拥有执行沙箱。现有Runtime服务自身的部署方式保持不变；后续若新增用户代码执行，须另行设计隔离能力。

第一版不默认引入子Agent、独立服务、消息队列或通用SQL平台。若真实任务证明长日志/代码分析需要上下文隔离，再独立规划排障子Agent；本期无需先写调度框架。

用户已明确允许无项目用户创建个人助手项目。bootstrap不带项目时幂等创建/复用仅本人加入的个人项目，带项目则沿当前成员授权；个人项目仅执行platform_assistant，不自动授予业务项目数据权限。

### 3.1 会话记忆与历史对话

历史对话、会话内上下文和跨会话长期记忆分别处理：

| 能力 | 本期决定 | 实现与验证 |
|---|---|---|
| 历史对话 | 必须有 | 沿用平台Thread/Run/消息与历史接口，可列出、重开、续聊及按既有规则删除；身份、项目和Agent绑定 |
| 会话内记忆 | 必须有 | create_agent的messages/state由GraphHarbor管理的持久checkpoint承载；同一Thread接续，服务重启后可恢复 |
| 跨会话长期记忆 | 第一版不新增 | 新Thread不自动召回其他会话或个人画像；用户显式提供的获准历史引用另按权限读取 |
| 产品文档与数据库结构知识 | 按需查询 | 属于版本化资料，不是用户长期记忆；本期不缓存结构，每次按当前数据源授权查询 |

复用现有生产持久化，不为本Agent另建InMemorySaver或一套聊天数据库。受管运行的checkpointer由既有底座提供；独立测试才使用相应测试saver，不把进程内测试当重启恢复证据。历史记录受模型上下文窗口和既有Token预算约束；本期未另实现自动摘要或跨会话召回，原始记录遵守既有保留与ACL。

同一用户不同项目、不同用户以及新Thread之间不能混入旧上下文。批准状态也需要持久化；恢复时重新核对当前权限，不能把过往“执行”选择当永久授权。

## 4. 组件复用与复制边界

以下是源码核对到的复用候选，存在文件不代表已经通过本项目适配测试。表内前端组件仅提供给前端同事参考，不规定其选型、文件结构或改造方式；后端与Agent部分由本次开发者负责决策。接口、权限、审批和会话行为属于共同契约。

| 能力 | 已有位置（相对仓库根） | 本项目用法 |
|---|---|---|
| 抽屉与页面壳层 | apps/platform-web/src/components/base/BaseDrawer.vue；apps/platform-web/src/layouts/WorkspaceLayout.vue | 直接复用，补助手入口和面板挂载 |
| 输入、消息和来源展示 | apps/platform-web/src/modules/chat/components/ChatComposer.vue；ChatMessageList.vue；Transcript.vue | 优先直接引用，使用已有 compact 等能力；业务差异确需时复制小块展示/装配代码 |
| 会话运行与生命周期 | apps/platform-web/src/modules/chat/composables/useChatSession.ts；useChatSessionPool.ts | 复用同一 SDK controller、会话池和取消机制，不复制第二套运行状态机 |
| 错误上下文 | apps/platform-web/src/services/observability/diagnostic-packet.ts；error-buffer.ts；modules/chat/components/DiagnosticDetailModal.vue | 复用诊断数据和脱敏逻辑，补面向助手的结构化输入；粘贴 Markdown 仍支持 |
| 运行诊断 | apps/platform-web/src/services/threads/diagnostics.service.ts；apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py；service.py 的 get_thread_run_diagnostics | 复用诊断 schema、Thread/Run 校验和安全投影 |
| 日志解析 | apps/platform-api/src/platform_api/modules/observability/service.py | 保留查询解析能力；新旧入口授权、查询范围与脱敏需治理后接入 |
| 普通 Agent 组合根 | apps/runtime-service/src/runtime_service/services/reference_agent/agent.py | 允许复制装配骨架，替换名称/Prompt/工具；保留探测与执行隔离、身份解析及必要恢复行为 |
| 预算、隐私、错误与追踪 | apps/runtime-service/src/runtime_service/middlewares/；observability/；runtime/ | 引用共享实现；按本助手场景装配，不照搬 reference 的固定工具数或全部高级能力 |
| 知识检索与 MCP | apps/runtime-service/src/runtime_service/tools/mcp.py；tools/knowledge.py | 本期选择显式发布manifest的有界文档检索；未接入项目知识MCP，不增加新RAG链路 |
| 联网检索 | apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/search.py | 已提取最小共享tools/research.py，助手和DearFlow复用Tavily传输，不依赖另一Service私有helper |
| 查询审计 | apps/platform-api/src/platform_api/modules/audit/；entrypoints/http/middleware/audit_log.py | 扩展已有动作和安全字段，不另建平行审计系统 |

复用顺序：现有公共组件直接引用 → 复制适用的业务组合根/小块代码后适配 → 两个真实使用点确需时做最小共享提取。复制必须保留原实现的错误处理、授权和取消语义，移除原业务专有名称/工具，补当前调用点测试。不会为“先统一架构”重构整个聊天或 DearFlow 模块。

## 5. 数据权限：能力较广，范围随人

下表是产品访问层级，不是新建 IAM 角色枚举。实施时映射现有角色与显式资源授权；研发身份不能仅凭自称或任意角色字符串判断。

| 使用者 | 数据库 | 日志与运行 | 文档 | 源码 |
|---|---|---|---|---|
| 所有登录用户 | 自己有权访问的项目/资源数据，获准查询时可在受限数据集上由Agent生成只读SQL | 可访问资源的诊断与允许展示的日志 | 获准平台帮助与项目资料 | 默认不提供 |
| 获准项目管理/支持人员 | 项目授权范围内更广的读取、过滤和聚合 | 项目允许范围的调查；私有Thread沿既有规则 | 相同权限范围的资料 | 单独授权后才可读 |
| 获准平台运维/研发 | 经登记的数据源/环境范围内的只读分析 | 可按获准环境/服务/时间调查，跨项目需明确范围 | 获准运维/研发文档 | 指定仓库和版本的只读检索 |

平台角色不自动获得所有项目私有内容；现行权限标准要求项目授权与必要接管。具体账号/角色、表/视图/字段、项目行范围、日志环境和代码仓库在 T02 建立清单。配置冻结后，获准范围内的正常读工具自动执行；只有扩大范围或引入写工具时处理相应授权。

读取结果的隐藏字段、证据详情、引用链接和历史会话也必须遵守访问范围。切换项目/账号不能沿用前一个作用域缓存；撤权后禁止继续取数和打开受限来源，历史已物化内容按当前会话可见性/保留策略处理，不能承诺收回用户已经看到的信息。

### 5.1 数据库只读查询

支持两类读取：已有业务查询直接复用；允许数据库查询的用户通过受控只读SQL工具读取各自获准的数据集。Agent可发现允许的表/字段并编写过滤/关联/聚合查询，普通用户也不必被限制为固定问答，研发/运维则按授权拥有更广的数据范围。

**Agent自己生成SQL，开发者不为每个问题预写查询。** 执行过程为：查看允许的表清单→按需读取字段、主外键及业务说明→模型生成SQL→工具校验并用只读连接执行→将有界结果或可修正错误反馈模型→回答并引用查询证据。只在需要时查询schema，不每轮把全库结构塞入Prompt；重要业务含义可补简短数据字典，不能假定模型仅凭列名知道业务语义。

**开源选型：优先复用langchain-community的SQLDatabase和SQLDatabaseToolkit。** 本仓pyproject已声明langchain-community，uv.lock锁定0.4.2；langchain锁定1.3.17。本轮核对了上游SQLDatabaseToolkit实现，包含列出表、读取schema、执行SQL、模型检查SQL四类工具；已通过锁定版本工具适配测试及真实模型生成SQL链路。Toolkit示例里的旧create_react_agent不是本项目采用的入口，仍使用create_agent。

我们负责平台适配，而不是重写SQL Agent：把表/字段发现接到获准数据源，用后端只读执行器承接sql_db_query语义，加入当前用户范围、结果大小、超时和审计。query checker是模型辅助检查，不能替代权限或只读约束。不要将未经适配的Toolkit直接接到应用写连接；include_tables只约束工具可发现范围，不独自承担SQL权限控制。schema默认不附带业务样例行，确需样例时也走同一授权和脱敏路径。

- 使用独立只读数据源凭据/连接池，不能复用应用写账户、迁移账户、表所有者或管理账户。数据源与凭据由平台绑定，模型只见资源标识。
- 数据库权限、只读事务与查询校验共同执行边界；验证写入 CTE、多语句、DDL、过程/有副作用函数、文件/外部访问及角色切换不能绕过只读约束。仅检查 SELECT 开头不作为合格实现。
- 项目/行/列访问在数据库或可信查询服务强制实施，不能依赖模型主动加 WHERE，也不能查询全库后仅靠 Prompt 不展示。普通用户的动态SQL只见获准的受限数据集，研发/运维可访问更广数据集；具体视图/行策略按真实数据源冻结。
- 工程默认门槛在容量验证前固定：查询2秒、锁500ms、连接3秒、每进程4并发、100行/64KB结果；结构目录和字段分批读取。当前不是动态配置或生产SLA，正式容量目标由部署负责人评审。
- 只读规则约束助手调查业务数据。平台自身的审计落库、Thread/checkpoint 持久化属于独立系统职责，使用独立连接和代码路径；不能把它们误认为助手获得业务写权限。

第一版不凭空增加未指定的业务写动作，但本次需要完成写工具人工审批的后端机制与契约测试。任何显式发布、项目启用且用户有权限的写工具，仍必须逐次取得用户“执行”的明确选择，细节见5.4。只读SQL工具不升级为通用写SQL，用户点击批准也不能使它执行UPDATE/DELETE。

### 5.2 日志读取与现有缺口

规划时发现旧日志路由认证放行、且只按Trace文本匹配。现已移除放行，新旧入口共用当前项目和结构化Trace授权；保留原URL和解析字段，新增partial/coverage。此描述是本分支实现，不代表现役生产已部署。

目标是复用解析并补齐调用者和资源授权，覆盖现有诊断页面与新助手，避免只加固新工具却保留旧入口绕过。普通资源查询由服务端核实资源→Trace/请求→日志范围；平台调查使用明确的服务/环境授权。不允许知道 ID 就读取任意人的记录。

按用户已批准的权限分层和日志治理范围保留URL，增加登录/项目校验，不新建IAM角色。唯一旧页面调用者及前端迁移步骤已列入交接；明确日志调查者使用配置授权名单，所有读取仍须当前项目成员。

### 5.3 文档、代码和外部信息

产品文档绑定部署版本；源码检索绑定获准仓库快照/revision，提供相对路径与行号，不直接开放生产宿主机任意路径。凭据文件、私钥和配置密文不属于默认源码读取范围。

检索到的网页、日志、代码和用户粘贴内容是资料，不是提升权限或调用写工具的指令。送入模型前沿现有隐私机制投影与脱敏；内部资料能否发送给具体模型提供方，需要按已批准的数据处理范围绑定。联网搜索只发送必要的公开问题，不把内部排障包转发给搜索引擎。

### 5.4 写操作必须由用户决定

复用HumanInTheLoopMiddleware及现有interrupt/resume契约，对每个有副作用的业务工具强制允许approve/reject两种决策。前端显示“执行/不执行”；正常读工具不进入审批。即使会话现有access_policy为full_access，平台助手的业务写工具也不得跳过此要求。

后端在调用工具前持久化待审动作，返回具体工具、目标、参数与影响说明。用户选择执行后，只恢复对应interrupt及原参数；恢复时重新核对身份/项目/资源和工具权限。权限不足不能靠批准补齐。参数或目标发生变化必须形成新的待审动作，不能借已有批准改做其他操作。

“不执行”返回reject并结束该动作；没有选择、关闭页面、断网、超时、服务重启均不自动批准。前端不需要强迫用户填写拒绝理由，可发送固定的“用户选择不执行”以兼容现有helper。重复点击和重放沿幂等控制；写入结果未知时先对账，不能自动重做。用户拒绝后不能换个工具静默执行同一操作。

后端用独立测试写工具验证批准/拒绝/恢复/撤权/重放，不将测试工具发布到正式目录。未来具体业务写工具必须有自己的幂等与执行回执；本轮没有获批业务写动作时，不假装验证了真实业务写入。前端审批交互由同事开发，所需状态和报文在交接文档明确。

## 6. 工具与跨层数据

已实现工具如下，HTTP、字段与示例以frontend-handoff.md为准：

| 工具 | 行为 |
|---|---|
| list_databases / sql_db_schema / sql_db_query | 全部获准数据源发现、分批结构、动态只读SQL |
| read_run_diagnostics | 目标Thread/Run校验、运行诊断和安全模型配置摘要 |
| read_run_logs / search_project_logs | 已验证关联查询/明确授权的无Run项目调查 |
| search_documents / search_source | 版本化文档、研发源码清单与行号 |
| search_public_web | 只使用本轮用户提供的公开关键词，复用Tavily |

前端输入包含用户消息与可选页面/诊断上下文。身份和授权 scope 始终由服务端产生；客户端 ID 仅用于定位待校验资源。保留平台 Trace、模型追踪 Trace、请求 ID 和 Run ID 的类型区别，不把不同系统的 ID 相互替代。

内部资料工具统一携带 evidence_id、operation、observed_at、scope、audit_recorded及data；可用性、截断、版本在各data中。公开搜索返回sources和authorization_evidence_id，关联搜索授权及会话工具结果。助手最终答复引用真实 evidence_id；引用无结果、超时或工具调用成功都不等于根因已确认。普通回复先复用消息与 Markdown 来源展示；只有确需结构卡片才扩展已有受管事件，不提前创建第二套 SSE 协议。

## 7. 越权、关联与使用记录梳理

需要区分“谁能读”“这是不是本次问题的证据”“读出的信息被怎样使用”，三项分别验证：

| 事项 | 服务端事实 | 需记录/验证 |
|---|---|---|
| 用户与目标 | 当前用户、tenant/project、角色/资源授权版本 | 拒绝越权、伪造ID、撤权和跨环境连接；模型不能声明身份 |
| 助手与调查对象 | 助手Thread/Run、目标Thread/Run/请求、数据源 | 查询既能关联目标，也支持明确授权的非Run调查；缺关联不能冒充已定位 |
| 查询结果 | 查询动作、允许范围、时间、结果状态、条数、截断 | success/empty/denied/unavailable/partial分别说明 |
| 答案证据 | evidence_id、来源版本/时间、答案引用 | 可追溯取证与引用；不承诺还原模型内部每一项影响 |
| 数据去向 | 模型提供方、必要工具及公开检索用途 | 原始秘密不进入Prompt、审计、公开链接或检索词 |
| 撤权与留存 | 当前读取权限、会话ACL、结果/日志保留策略 | 不靠旧缓存恢复读取；资料过期明确不可用 |

扩展现有审计：actor、scope、助手运行、目标资源、数据源标识、工具/查询类型、查询摘要或脱敏指纹、结果状态、时间、耗时、条数及关联 evidence_id。不默认写完整 SQL 字面值、整份结果、日志正文或源码；限制条件/参数只保留必要且脱敏的定位信息。业务查询权限不自动授予查看审计的权限。

现有普通 HTTP 审计为独立短事务、写入失败不覆盖业务响应，不能承诺零丢失。T08 需验证内部工具实际取数也有记录，避免只有外层聊天 POST 被审计；审计失败必须有可观测提示，是否需要更强交付保证在 T02 明确，不默认新建 outbox。

## 8. 代码组织与影响范围

本次新增代码位置：
- apps/platform-api/src/platform_api/modules/platform_assistant/：按现有模块规范放置查询入口、service、schemas和数据源适配；按实际代码规模拆分。
- apps/runtime-service/src/runtime_service/graphs/platform_assistant.py
- apps/runtime-service/src/runtime_service/services/platform_assistant/agent.py、prompts.py、tools.py、approval.py、capabilities.py；运维与结构说明统一放在本项目backend-operations.md。

前端目录、组件选型和文件划分由前端同事决定，本次只提供交接文档。后端必须同步诊断网关、日志接口、IAM策略与审计动作（按需要）、Runtime图配置/能力目录/工具装配及包资源；前端的壳层、错误弹窗、会话绑定、日志调用和审批消费者列入交接影响清单。测试覆盖后端调用者、夹具和图注册断言，浏览器验收由前端同事接续。未选用附件、Workspace写入或Plan Mode时不默认声明支持；工具写审批不依赖开启Plan Mode。

受影响规范：权限/审计标准、Runtime网关、错误Envelope、Trace传播；如确有新增委托/SSE字段再更新对应草案。本次同步权限/审计/网关及Trace说明；未新增SSE类型或Delegation字段，原草案未满足其原门槛，不提前毕业。

## 9. 批准记录与落实范围

用户已批准产品方向、后端/Agent/交接分工、动态只读查询、日志治理、写工具逐次审批及功能分支Git交付。2026-11-16另明确允许个人助手项目，数据库“全部放开，都可以读”；按此前仍有效的数据权限分层落实为全部已接入且获准数据源，不采用管理员身份绕过。

具体交付配置见backend-operations.md：本次PostgreSQL专用只读账号和项目视图；个人项目幂等；源码/无Run日志用显式用户授权且须当前项目成员；旧日志保留URL并鉴权；固定资料manifest；受管模型及共享公开检索。普通审计沿既有fail-soft，资料授权回执失败则不返回内容。真实模型和搜索只使用本地合成资料/公开关键词，没有外发生产业务资料。

已固定的工程限制与本地测量见verification。生产连接、字段/行视图、文档发布内容、外部模型数据处理范围及生产容量由环境/数据负责人配置和评审；这些不是未完成的接线代码，也不是本轮已操作过的生产资产。用户人工交付验收和前端浏览器验收仍分别保留，开发者不代为批准。

## 10. 验证与回退

详细验收在verification.md，任务与进度只维护在tasks.md。必须覆盖四类业务、数据库真实只读、越权/撤权/缓存隔离、旧日志入口、文档与源码版本、数据外发边界、取消/故障和查询审计。

新增必验：历史与同Thread续聊、跨进程恢复、跨用户/项目隔离、读工具无审批、写工具批准前零副作用、批准/拒绝/重放/撤权、无沙箱资源创建。本次后端交付使用真实API→Runtime→工具链并模拟前端客户端；前端同事另完成页面、浏览器与联合验收，二者分别下结论。

回退关闭助手入口、图可用性和新工具挂载，终止所属调查任务，保留既有聊天/诊断页面可用。已修复的日志权限不随助手回退重新放开；只读连接凭据可撤销，已授权的系统审计按既有留存规则处理。已新增20261116_0012授权回执迁移，本地升级通过；downgrade保留表以防旧历史失去权限依据。关闭与恢复操作见backend-operations，生产不自动执行。

## 11. 框架依据与版本核对

2026-11-16先查询LangChain docs/reference MCP，再核对上游源码。参考[SQL Agent指南](https://docs.langchain.com/oss/python/langchain/sql-agent)、[短期记忆](https://docs.langchain.com/oss/python/langchain/short-term-memory)、[长期记忆](https://docs.langchain.com/oss/python/langchain/long-term-memory)、[人工介入](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)和[SQLDatabaseToolkit源码](https://github.com/langchain-ai/langchain-community/blob/main/libs/community/langchain_community/agent_toolkits/sql/toolkit.py)。

官方最新页面可能超前于仓库锁定版本。只采用本仓已有且经验证的batched action_requests/review_configs、interrupt ID映射及approve/reject语义，不直接引入最新per_call/resume协议。SQL适配签名、无样例行、有界返回及真实只读执行均已在锁定依赖验证；具体记录见verification，官方资料核对与应用验证分别留痕。
