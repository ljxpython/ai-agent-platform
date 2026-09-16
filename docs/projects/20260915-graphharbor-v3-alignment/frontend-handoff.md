# 前端交接：GraphHarbor post30 生命周期接入

2026-09-15：**交接已完成，前端代码与浏览器验收 deferred。** 本轮没有修改前端实现。后续从本文执行，不需要重新拼接后端调查记录；后端证据见 [03实施记录](implementation/03-backend-closeout.md)，Dear业务范围仍见 [原前端交接](../20260913-dearflow-agent/frontend-handoff.md)。

## 已提供的后端能力与边界

- GraphHarbor／graphharbor-runtime 已发布并安装 0.13.0.post30，包含post29生命周期对齐及recursion_limit传递修复。生命周期提供 started/running/completed/failed/interrupted，graph_name/error/cause 仅在真实存在时携带。根终态由事务提交产生。
- 区分三层：图内 v3、Run SSE 的 version=v3、线程 Protocol v2。官方0.13.0 Run SSE即使传v3仍为旧格式；GraphHarbor typed Run SSE是扩展。现有Vue useStream使用线程命令／订阅，不要将线程协议改名或全局塞入version。
- 平台create与stream入口支持显式v3；join沿用已创建Run版本；resume继承已授权checkpoint来源Run的公开kwargs.version，幂等重试也继承。版本不属于Agent context，前端不自报恢复源配置。
- Run SSE需要子图时显式请求 `stream_subgraphs=true`；false时根lifecycle可能位于外层根scope，仍会按data.namespace排除子事件。线程订阅使用自己的namespace/depth过滤，不照搬这个参数。
- 保持鉴权、项目隔离、审批前状态核实和重复请求幂等；取消ACK仅说明请求已接收，须确认运行终态。独立子任务取消与独立计费账本不在本轮范围。

## 消费者清点与修改位置（E4清点完成）

以下路径相对 `apps/platform-web/`。业务适配在Dear独立目录，网络请求继续在services，不复制或改造共享Chat来实现Dear专属功能。

| 消费者／文件 | 后续具体工作 | 本轮状态 |
|---|---|---|
| `src/modules/dear-agent/composables/useDearAgentSession.ts` | 核对useStream的subgraphs、interrupts、错误与终态；保留onCompleted后的verify(true)、审批前state核实、respondAll及父取消后核实 | 接入代码 deferred |
| Dear的 `transcript.ts`、`composables/useTranscriptMessages.ts`、`trajectory/trajectory-adapter.ts` | 使用SDK投影绑定消息／工具／scope；未知usage保持未知，避免重复累加 | deferred |
| Dear的 `components/SubagentCard.vue`、`components/SubtaskDetail.vue` | 按真实scope和cause显示两个同名任务；仅在证实存在时移除名称／调用ID拼接namespace的兜底 | deferred |
| `src/services/langgraph/client.ts`、`src/services/threads/session.service.ts` | 承担SDK／HTTP、鉴权和项目header；核实实际入口支持后再传版本，不改全局默认 | 保持原路径 |
| `src/modules/chat/composables/useChatSession.ts`、`src/modules/chat/pages/ChatPage.vue` | 共享Chat单独回归，新建、历史、审批和停止均应正常；Dear通过不等于Chat自动切换 | 默认迁移 deferred |
| `src/modules/overview/pages/OverviewPage.vue`、Dear／Chat页面中的createSessionService | 会话列表、计数、状态读取；无创建流版本开关需求，验证读取不退化 | 保持原路径 |
| `src/services/runtime-gateway/workspace.service.ts` | 使用createLanggraphClient的运行／会话操作逐入口确认；未验收不改默认 | 默认迁移 deferred |
| Python／其他HTTP消费者 | platform-api的create、stream、run.start已统一版本校验；join不覆盖历史版本；未指定仍v2，没有公开wait入口，无须新增 | 后端契约已验，客户端逐入口迁移后置 |

## 实施顺序与验收

### 已确认的切换决策与平台后端改动结论

用户已确认：**先适配Dear Agent，验收通过后切换Dear已验证入口；共享Chat与其他消费者保持现状。** 本次更新只细化交接，不实施前端、不立即切默认。

**按现有线程Protocol入口实施，不需要额外修改platform-api或runtime-service生产代码。** post30和平台已有版本校验、子图事件、恢复与权限链路足够支撑此次适配；不要新增“Dear专属v3接口”、数据库版本字段或Server全局默认开关。前端联调如发现真实缺陷，再按所属服务边界最小修复并补证据，不能提前为假设需求改后端。

| 平台后端核对点 | 已有实现（路径相对仓库根） | 本次是否修改 |
|---|---|---|
| 创建与流式创建选择版本 | `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:launch_runtime_run`、`stream_thread_run`；显式v2/v3校验，缺省保留v2 | 否 |
| SDK线程run.start | 同文件 `_promote_protocol_run_start`、`send_thread_command`；`apps/platform-api/src/platform_api/core/runtime_contract.py:normalize_protocol_v2_command`接收version并进入统一创建流程 | 否；不要将version放入Agent context |
| Python SDK create缺少version参数 | `apps/platform-api/src/platform_api/adapters/langgraph/runs_sdk_adapter.py`已有显式version的HTTP补偿路径 | 否 |
| resume与重复提交 | `send_thread_command`从已授权checkpoint来源Run的kwargs.version继承，保持审批／模型权限与幂等保护 | 否；浏览器不覆盖恢复版本 |
| 生命周期／子图／回放／执行限制 | 独立GraphHarbor post30已发布，`apps/runtime-service/pyproject.toml`与`uv.lock`已安装锁定 | 否；业务展示逻辑不能放GraphHarbor |

**入口参数不能混用：** 当前平台线程 `run.start`允许version，但不允许stream_subgraphs；后者用于直接Runs请求，不要因为内部提升函数列出了该字段就认为线程命令公开支持。Dear继续用线程订阅的namespace/depth与SDK子图投影，无需为了子卡片扩展线程命令白名单。

### Dear实际适配步骤（按此顺序实施）

以下路径相对 `apps/platform-web/`；先完成最小真实页面链路，再扩大场景。

| 顺序 | 具体改动与接入 | 完成标准 |
|---|---|---|
| 1. 记录现有真实请求 | 从 `src/modules/dear-agent/composables/useDearAgentSession.ts` 的useStream、submit、respondAll，追到 `src/modules/dear-agent/run-actions.ts:platformCommand` 和 `src/services/threads/session.service.ts`；核对浏览器实际commands/events请求和SDK锁版本 | 确认仍走线程Protocol，不将“接入v3能力”误做成更换整个通信通道 |
| 2. 接入根状态 | 在Dear会话composable消费当前SDK公开生命周期／错误投影，保留verify(true)最终核实；started/running显示执行中，completed结合持久终态确认完成，failed展示错误，interrupted结合实际interrupt区分待回答／审批与停止 | 失败、断流和取消ACK不会显示成功；不得根据interrupted虚构审批表单 |
| 3. 接入子任务 | 在Dear trajectory适配与子卡片中使用真实子scope作为身份，cause关联task调用；graph_name仅为显示名称；子消息／工具归属对应子图，根终态和子终态分别展示 | 两个同名子任务可区分，子失败被父捕获时父仍可成功；不拼名称猜namespace |
| 4. 对齐内容与用量 | `useTranscriptMessages.ts`／`transcript.ts`沿SDK消息、工具及内容块投影显示；按工具真实ID处理重复handle；显示已有usage并保留未知值 | 无重复文本、重复工具或重复usage；不新增独立子任务计费、取消接口 |
| 5. 对齐恢复 | 保留 `run-actions.ts` 的动作回执、幂等重试和SDK批量回答转平台resume映射；审批前核实当前state，刷新后恢复待处理interrupt及已有消息 | 两个并行中断可分别回答；重复点击不新建重复执行；恢复沿用来源版本／权限 |
| 6. Dear定向启用与回退 | 优先保留线程Protocol，仅启用已验证的生命周期／子图消费。若另一个直接Runs入口确实要用typed Run SSE，才在该入口顶层传version=v3、需要子事件时传stream_subgraphs=true；网络参数由services承接 | 不在共享SDK构造器全局注入版本；不新增一套SSE解析器；共享Chat保持原行为 |

步骤6不是要求线程入口必须强制设置version=v3。线程Protocol本身提供生命周期；如后续确有同时保存typed Run SSE回放的需求，再在Dear创建命令params中显式传version，并通过当前SDK／services公共扩展点实现，不能假设useStream.submit接受未声明参数。

**回退区分两种情况：** 若只改变Dear线程投影展示，回退Dear这部分适配代码，线程协议名称不变；若某直接Runs入口改了创建版本，则只让后续新Run重新选择v2。在途Run与历史事件保留原版本，resume仍交给后端继承。无需建设新的配置中心或双执行引擎。

### 验收后如何标记完成

完成下面D1—D3后，将实际修改文件、SDK版本／patch、浏览器trace、thread/run标识回填本项目V11；再勾选E1的Dear入口交付。交付说明应写清“Dear线程Protocol生命周期／子图适配完成”或“某Runs入口typed v3默认启用”，不能笼统写“全平台已切v3”。其他消费者E4-b保持deferred，除非另有独立验收和授权。

1. **D1：锁定实际前端依赖。** 当前SDK1.10.2、Vue1.0.35，`package.json`和`pnpm-lock.yaml`存在 `patches/@langchain__langgraph-sdk@1.10.2.patch`。Server验收用SDK1.9.28，不能据此删除当前patch或宣称浏览器已通过。先运行现有SDK链路测试与类型检查，记录必要改动最小集合。
2. **D2：适配Dear并做浏览器链路。** 新Run→两个同名任务→消息与工具结果→根终态；失败必须显示失败；子异常被父捕获时允许父成功；澄清与审批（含两个并行中断）分别恢复；父停止后确认interrupted且不误展示审批；运行中断网／刷新／跨Run订阅恢复无重复文本或工具；旧v2历史可读。保留截图或Playwright trace、thread/run标识，回填V11。
3. **D3：共享入口回归。** 运行Chat既有测试及浏览器新建／恢复／停止，overview与workspace读取回归。只有确实需要修改公共services才改，不复制网络层，也不重建SDK事件聚合器。
4. **E1/E4实际切换：** 上述通过后仅切已验收入口，记录入口、版本、日期与变更集合；其他消费者保持原路径。回退仅让新Run选择v2，在途v3保持原版本完成／回放，不修改历史数据。

## 已实测的客户端陷阱

- SDK1.9.28的 `await thread.output` 在根失败时也可能resolve，不能据此显示成功。结合根lifecycle.failed/interrupted及当前持久Run核实；断流、取消ACK也不代表成功。
- 线程Protocol的根error已适配字符串；GraphHarbor扩展Run SSE仍可保留结构化 `{type,message}` 错误。使用对应SDK／入口契约，不对所有通道统一调用error.toLowerCase或直接渲染对象。
- SDK投影中断ID是 `interrupts[].interruptId`；命令使用 `interrupt_id` 和该项namespace。优先沿用现有respondAll，不手写新HITL协议。官方HITL源Run持久status可能为success，GraphHarbor保留interrupted，不能仅凭status判断是否有待审批项。
- 双端SDK1.9.28对同一个工具ID产出两个handle，原始tools只有一对。回归当前1.10.2与patch的行为，界面按真实工具ID展示，不能删除Server事件来掩盖客户端重复投影。
- lifecycle外层namespace与data.namespace用途不同，以SDK子图投影／真实cause关联，禁止通过同名Agent名称猜测唯一身份。
- v3比v2 values流携带更多数据：本轮样本每次26条／19688字节，对照4条／311字节；不是带宽优化。先观察实际页面渲染和事件量，不预建新缓存或节流框架。

## 完成标记

- [x] 后端可交付契约、消费者清单、具体文件、SDK差异和验收步骤已写清。
- [ ] D1—D3前端实现与浏览器验收：按用户要求后置。
- [ ] E1／E4客户端默认切换：依赖浏览器验收，不能用后端成功代替。
