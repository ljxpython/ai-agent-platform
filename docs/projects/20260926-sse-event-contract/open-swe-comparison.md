# open-swe 流式输出对照（2026-09-26）

## 证据范围

只读研究用户指定的本地目录（相对本仓库根目录）`../research/open-swe`；该参考仓库不作为项目运行依赖。
HEAD 为 `ad417d64d91cc349d63d832c7b643637dc1774cf`，但该工作区有大量暂存/未提交改动及未解决冲突，因此下述结论针对本次读取的工作树，不代表该提交或官方发行版。
未修改该目录，未启动其服务，未读取.env或连接生产环境。下述为源码和测试定义审阅，不是运行测试通过证明。

路径缩写：O=`open-swe/ui/src/features/agents/`；P=`apps/platform-web/src/modules/chat/`。最终方案见[plan.md](plan.md)，本页只是借鉴依据。用户后续已确认：线程级保活纳入本期，现有前端展示/交互不变；以下涉及展示差异仅为参考事实，不是改造任务。

## 可借鉴、已具备与需补齐

| 主题 | open-swe 工作树证据 | 当前平台证据 | 决定/建议 |
|---|---|---|---|
| SDK投影→纯展示映射 | O/lib/stream/AgentStreamProvider.tsx:PooledStream；lib/streamMessagesToUi.ts:streamMessagesToUi，读取messages/toolCalls | P/composables/useChatSession.ts:useStream；transcript.ts:buildTranscript | 已有架构，保留；不加自研token累加器/第二套工具执行状态 |
| 工具只出现一次 | streamMessagesToUi以tool_call_id关联ToolMessage和assembled calls | buildTranscript已有callMap/results/shown，并处理审批中断 | 以平台现有特殊语义为基线；补同名工具不同ID、增量参数、晚到结果的用例 |
| 正文/过程分区 | O/components/messages/renderItems.ts:splitWorkAndReply；timeline/AgentTurn.tsx | P/transcript.ts:work/answer；components/ChatMessageList.vue | 已有分区，保持用户当前默认展开/折叠和关注项呈现；不改造 |
| 标准reasoning | O/lib/streamMessagesToUi.ts:reasoningText读取contentBlocks；ReasoningBlock.tsx实时展开/结束折叠 | P/transcript.ts优先contentBlocks，额外兼容旧字段；MessageContent.vue默认一直展开 | 标准块优先已具备；用户已否决结束自动折叠提案，保持当前展示 |
| 稳定流式Markdown | O/components/chat/Markdown.tsx固定动画参数，局部错误降级；lib/provider/useLiveMarkdownMessageId.ts将动画目标稳定2秒 | 平台MarkdownContent.vue + utils/markdown.ts使用markdown-it、html:false；ChatMessageList只给最后一轮流式标记 | 作为稳定性回归参考；不改当前Markdown/动画/降级规则，不引入React/Streamdown |
| 阅读位置保护 | O/components/messages/useTranscriptScroll.ts：手动上滑停止跟随，ResizeObserver，按scrollKey记忆，RAF合帧 | P/scroll-state.ts、ChatSession.vue已有问题32%锚定、RAF和手动跟随控制 | 保留当前滚动体验；验证线程保活不破坏位置/跟随，不主动调整算法 |
| 线程级流托管 | O/lib/stream/streamPool.ts与AgentStreamProvider.tsx保留每个线程的useStream；闲置TTL60秒/最多8个，运行条目不按此上限驱逐 | WorkspaceLayout.vue页面KeepAlive；ChatPage.vue切Thread后增加mountVersion；useChatSession组件作用域；Store只存快照 | 页面保活≠每个Thread的实例保活。隔离探针已确认SDK作用域释放会dispose；方案采用完整会话宿主，不照搬会丢当前UI状态的TTL驱逐；真实连接容量按验证计划执行 |
| 子智能体按namespace隔离 | O/components/subagents/SubagentActivity.tsx使用useToolCalls({namespace}) | P/components/SubtaskDetail.vue已有同类订阅，useTranscriptMessages及SDK patch保护namespace | 保活/重连需验证现有数据隔离；不主动重构子任务卡片展示 |
| 服务端状态兜底 | O/lib/queries.ts:useAgentThread运行中每3秒读取；AgentThreadView.tsx合并thread.status/isLoading | P/composables/useChatSession.ts:verify、scheduleBackgroundRunPoll、busy已有核实链 | 不再加第二套轮询。连接状态、运行事实、UI动画应分开 |

## 不能直接照搬的行为

1. **HTTP错误变成流内错误。** `open-swe/agent/dashboard/threads/proxy.py:stream_thread_events`在生成器内才连接上游；上游>=400时输出`event:error`，detail带解码后的上游正文。路由已返回StreamingResponse，本地权限/content-type虽已预检，上游错误仍可能处于HTTP200流内。平台继续采用错误专项约定：握手失败在响应开始前返回安全HTTP错误；流开始后不能追加HTTP Envelope或泄露原文。
2. **只保留最后一段正文。** `streamMessagesToUi.ts:mergeTextChunks`实际过滤同一聚合回合里此前的text chunk，并不是仅在UI折叠。平台保留已确认中间正文，收进工作过程即可；不能以“简洁”为理由删除。
3. **取消ACK直接写interrupted。** proxy.py的`proxy_dashboard_thread_run_cancel`在取消请求2xx后更新thread metadata；平台保留“取消中→查询真实Run状态”，且审批interrupt与用户取消不是同一语义。
4. **子任务注释与装配不完全一致。** SubagentActivity注释称namespace由streamMessagesToUi填入；本轮检索UI只有types声明和SubagentCard读取`subagentNamespace`，未找到该映射实际赋值。因此只能借鉴scoped订阅模式，不能声称参考仓库子任务链路已经完整可用。
5. **重连注释不是协议保证。** queries.ts注释声称custom fetch影响重连；平台安装的SDK ProtocolSseTransportAdapter明确有独立重连循环。两者不能互相替代证据，更不能据该注释认定平台不支持重连。
6. **不照搬运行条目无限保留。** open-swe的8个上限只限制闲置流；平台还需账号/project隔离、撤权/登出释放、总订阅数观测与压力验证。复用思路，不把参考参数当容量结论。
7. **不导入产品专属通道。** Slack/Linear回帖、conversation_offloading、自定义output_iframe、桌面local/cloud切换依赖它自己的后端。平台现有产物/审批/附件机制继续使用，不为借鉴要求Runtime新发事件。

## 对原SSE方案的修正

- 本轮决策后范围收敛为“实例生命周期、协议恢复、现有展示保护回归”；输出改造提案撤回，仍保留一个专项。
- “SDK单一事实来源”改成精确表述：SDK是实时投影来源，服务器Run/state是执行与快照事实；UI折叠/动画不是执行状态。
- 不自行新增消费游标账本：安装的ThreadStream已有ordering和event_id去重；其lastSeenSeq是接收序号，lastAppliedThroughSeq来自响应meta，两者均不能当作UI提交水位。隔离探针已确认HTTP重连省略initialSince，正常EOF不自动重连；补丁方案见plan第5节。
- 事件兼容性按层处理：未知合法JSON扩展可经现有脱敏继续传输/忽略展示；未知方法不能触发审批/成功/执行动作；损坏外层帧才安全终止。JSON custom载荷里的字符串不是非法非JSON SSE。
- 不删除现有SDK patch、不一律折叠正在流出的reasoning、不回退现有滚动锚定。
- 保留410安全降级、权限停止、重复执行防护和快照/订阅竞态验证；本轮没有发现足够证据证明open-swe解决了平台的410恢复问题。

## 既有项目关系

- [20260912输出标准化](../20260912-chat-streaming-standardization/README.md)：已经明确借鉴open-swe及SDK纯视图映射。本次是差异复核，不重新宣布整套重构。
- [20260924会话缓存/保活](../20260924-chat-session-cache-and-stream-resumption/README.md)：保留已有完成记录；本次单独验证跨Thread实例保留，不能拿页面KeepAlive推导多线程后台订阅已闭环。
- [20260921超时/重试](../20260921-chat-stream-timeout-and-retry-optimization/README.md)：仍为规划中，包含Runtime心跳/超时提案。本专项不承接该Runtime改动，也不直接继承其180秒配置；重试草稿展示/网关实际超时重叠项需按现役代码认领，禁止两份相冲突方案并行实施。

## 本轮资料核对

已查询LangChain docs和reference MCP，获得useStream/toolCalls/subagent scoped消费资料；公共文档仅辅助定位，具体参数与行为以本地锁定SDK1.10.2、Vue1.0.35及patch为准。未执行应用单元、集成、浏览器或真实断网实验。

2026-09-26补充：已执行无真实服务依赖的内存Node探针；已读GraphHarbor post33的protocol_api/core_api，确认state无约定的原子事件游标。完整任务和验收命令已落入本专项标准四文档，本文不再维护另一份候选方案。
