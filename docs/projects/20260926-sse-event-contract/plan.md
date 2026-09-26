# SSE 事件契约与线程持续保活 — 实施方案

> 2026-09-26执行细化稿。用户已确认线程级持续保活纳入本期，并明确禁止改变当前前端展示/交互。本稿补齐技术选择，供人工评审及后续按任务实施；本次只编写文档，不代表批准编码。范围不扩大到Runtime/GraphHarbor。

## 1. 目标、范围与完成标准

只修改platform-web、platform-api、现有SDK补丁及测试。Runtime服务代码、GraphHarbor包/配置/数据库、事件保留策略均不改；参考项目不修改、不成为依赖。保留当前SDK1.10.2、Vue1.0.35；不引入其他状态库、事件总线或新渲染框架。

完成必须同时满足：
1. 当前标签页、同一登录会话及项目内，A运行→B→其他页面→A期间，A的ChatSession、useStream、actions及权限/运行核实逻辑持续存活、持续消费事件。
2. 网络重连只恢复订阅；不自动重发run.start、取消、审批、用户输入。终态后的最终values/checkpoints不被过滤。
3. HTTP握手错误与已开始的流故障分开处理；撤权清理全部本地可读内容；非法帧不泄露原文。
4. 现有正文、思考、工具、子任务、审批、Markdown、动画、滚动和操作保持原样；只改变已确认的生命周期与恢复行为。

保活边界：刷新/关闭标签页、浏览器冻结/休眠、离开工作区、换项目、登出均不承诺继续消费；服务端Run不会因此自动取消。再次进入按授权后快照与现役保留事件恢复，不宣称浏览器具备后台守护进程能力。不同标签页各自持有实例，本期不做跨标签页主从协调。

## 2. 当前事实与确定差异

路径以仓库根目录为起点。SDK安装目录仅作为只读证据，正式改动落在pnpm patch，不直接修改node_modules。

| 事实源 | 已核实行为 | 本期处理 |
|---|---|---|
| apps/platform-web/src/layouts/WorkspaceLayout.vue | KeepAlive保存ChatPage/DearAgentPage；key含sessionEpoch/projectId | 保留页面缓存，增加独立会话宿主；显式清理旧作用域 |
| apps/platform-web/src/modules/chat/pages/ChatPage.vue；modules/dear-agent/pages/DearAgentPage.vue | 切Thread增加mountVersion，loading/target条件可卸载会话；页面级draft/context共享 | 改为选中池条目；模型归属于各条目，不再以mountVersion重建 |
| apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue | 转发ChatSession属性和slots的薄包装 | 保留兼容入口；正式页面转接同一宿主，不另建第二个SDK实例 |
| apps/platform-web/src/modules/chat/composables/useChatSession.ts | useStream组件作用域；dispose清理actions/定时器；verify尝试不存在的joinStream | 生命周期随宿主；去掉无效joinStream分支，显式恢复协议订阅 |
| apps/platform-web/node_modules/@langchain/vue/dist/use-stream.js | onScopeDispose(controller.activate())；返回值无joinStream/hydrate | 不读取私有Symbol，不伪造可调用方法 |
| apps/platform-web/src/modules/chat/run-actions.ts | filterStaleRunSseResponse按completedRunIds及当前Run过滤 | 删除整流Run过滤，防止终态先到导致尾部values丢失 |
| apps/platform-web/node_modules/@langchain/langgraph-sdk/dist/client/stream/index.js | 共享过滤条件并集流，另有wildcard lifecycle/input；已有event_id去重 | 复用；每卡片不额外创建客户端 |
| apps/platform-web/node_modules/@langchain/langgraph-sdk/dist/client/stream/transport/http.js | 网络故障有重试；正常EOF直接关闭；错误可能丢结构；重连省略initialSince | 补EOF/错误分类与明确的手动恢复能力；不在应用再加自动重试循环 |
| apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py | 流握手在返回iterator前；httpx.Timeout(None, connect=...) | 保留，不照搬旧180秒读超时提案 |
| apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py | 已有完整帧脱敏；损坏UTF8/非JSON返回原文；buffer无上限 | 保留脱敏规则，补字节限额及安全失败 |
| apps/runtime-service/.venv/lib/python3.13/site-packages/langhost/protocol_api.py | 先挂实时队列再读取回放；since非零且低于watermark返回410；默认心跳15秒、连接3600秒 | 只读证据，不修改；部署环境实际值需要联调记录 |
| 同包core_api.py::_state_from_snapshot | values/next/checkpoint/metadata/tasks/interrupts，无约定的原子事件水位 | 410不能声称无缝补回全部过程 |

2026-09-26隔离Node探针实测：正常EOF仅请求1次；网络异常重连的body从含since:9变为不含since；StreamController.activate返回的cleanup触发dispose一次。使用注入fetch/ReadableStream，无真实服务连接，无文件写入。两连接稳态及轮换暂时三连接是源码预算，仍须通过任务测试验证，不作为已测容量。

## 3. 协议契约

### 3.1 两套入口不混用

相对/api/langgraph：

| 入口 | 恢复参数 | 本期 |
|---|---|---|
| POST /threads/{t}/stream/events；POST /threads/{t}/commands | JSON body.since | 聊天主线，重点治理 |
| POST /threads/{t}/runs/stream；GET /threads/{t}/runs/{r}/stream | join的last_event_id | 保持现有标准Run流兼容，不改为since |

Protocol允许channels以core/runtime_contract.py::normalize_protocol_v2_event_request为准：checkpoints、values、updates、messages、tools、lifecycle、input、tasks、custom及custom:前缀。namespaces/depth继续原校验。since只接受非负整数；标准Run SSE id不能当作Protocol sequence。

Protocol外层示意（合成契约夹具，不是假称生产抓包）：

```text
id: 41
event: event
data: {"seq":41,"event_id":"e-41","method":"values","params":{"thread_id":"t-1","run_id":"r-1","namespace":[],"data":{"messages":[{"id":"m-1","type":"ai","content":"已完成"}]}}}

: heartbeat

```

业务载荷messages/tools/input/lifecycle以现役SDK测试及实际三段采样为准，不另造一套工具/审批字段。message_id、tool_call_id、event_id、run_id、thread_id、namespace各司其职，不按正文/名称去重；子任务同名不同namespace不合并。

### 3.2 Run与连接状态分离

| 输入 | 执行事实 | 处理 |
|---|---|---|
| pending/running | 运行中 | 消费流；已有verify兜底 |
| tool失败 | 单工具失败 | 不改整轮Run终态 |
| interrupt | 等待人工 | 不自动批准，不标成功 |
| cancel ACK | 取消已请求 | 继续核实指定run_id；不当作interrupted |
| error/timeout/success等真实Run终态 | 服务器事实 | 保留原状态映射；继续收取尾部状态 |
| 网络异常/EOF | 连接变化，结果未知 | 恢复订阅/查询状态，不伪造执行失败或成功 |

不同流的到达顺序不是服务器执行顺序。lifecycle流先收到r1终态、内容流后收到r1的values，两者都必须处理。r1终态不能清掉r2的busy或待确认动作。Run状态回调按thread_id/run_id/action id匹配；数据流本身不以“当前Run”过滤。

verify/onCompleted/stop不得以终态或cancel ACK立即disconnect并截断尾部。保留Thread订阅以接收后续轮次；取消仍只调用原service.cancel一次。终态后通过原history/state读取对齐最终事实，迟到读取需按会话generation及run_id校验，不能覆盖新Run数据。

## 4. 会话所有权与页面接入

### 4.1 唯一实现路线

保留完整ChatSession组件，不拆出第二套消息或工具状态机。新增：
- apps/platform-web/src/modules/chat/components/ChatSessionPool.vue：WorkspaceLayout下唯一稳定宿主。
- apps/platform-web/src/modules/chat/composables/useChatSessionPool.ts：宿主provide/页面inject的轻量注册表及作用域清理。

宿主作为router-view的兄弟节点，不能放进loading/routeAccessAllowed分支。使用Vue Teleport把会话容器放入当前页面的会话插槽位置；非当前条目停放在宿主隐藏容器。条目始终用不变instanceId作key，不用threadId、route.fullPath或mountVersion作key。Teleport只移动已有DOM，不能在目标切换时重新创建ChatSession。隐藏容器不可聚焦、不可占布局；页面离开前同步停放，不能留下已卸载的目标节点。

ChatPage和DearAgentPage保留现有页面布局、侧栏及target/actions插槽内容，只把原会话区域变为注册的挂载点。宿主为选中条目转发该页slots与事件；页面失活时注销view绑定，不释放Thread。适配容器使用原有flex/min-h-0尺寸约束，不新增视觉样式。DearAgentSession不得同时残留一份活跃ChatSession。

### 4.2 数据结构和方法契约

仅内存保存，SDK/AbortController/DOM/VNode不进持久化Pinia。现有useChatSessionStore继续只存快照。

条目字段：
- scope：userId、auth.sessionEpoch、projectId的不可变组合；任一改变先使旧scope失效。
- instanceId：crypto.randomUUID生成；从草稿到正式Thread不变。
- threadId：可空；正式索引为scope + threadId。
- graphId/agentId：创建时固定；同Thread目标不符时报现有目标错误，不重绑另一图。
- draft、attachments、context、recursionLimit：条目独享的refs；保留当前初值及sessionStorage草稿key习惯。
- initialThread、canWrite、title：仅更新该Thread的已验证元数据；后台权限不能引用当前页面B的权限。
- generation、disposed、visible、lastViewedAt：迟到结果隔离与DOM可见性。
- sessionRef：现有openDrawer/openOptions及新增连接恢复入口，均定位此条目。

注册表方法及责任：
1. acquire(resolvedTarget, threadId?, draftKey?)：已存在则返回原条目；未存在才创建。草稿key含scope、页面种类、agentId及本次new动作生成的draftId；不把所有无线程页合成同一条目。
2. attachView(entryId, outlet, slots, callbacks)返回detach：标记唯一可见条目；双页面指向同Thread时复用同一instanceId。detach只解绑view。
3. bindThread(entryId, confirmedThreadId)：平台创建/对账成功后原子登记索引，保留实例和模型；同scope重复Thread绑定报错并核实，不启动第二个Run。
4. remove(entryId, reason)、clearScope(reason)：先generation++/disposed，再移除可见绑定、终止订阅/定时器/监听、清理对应缓存，最后卸载组件。不能发送cancel。
5. dispatch(entryId, generation, event)：数据结果回写所属条目；只有当前view仍绑定该条目才能导航、聚焦、刷新当前页列表或处理fork路径。

created回调必须先bindThread。后台A创建成功不能跳走B、清B草稿或把B附件当作A已提交附件。onAccepted保留“草稿仍等于submittedDraft才清空、只移除submittedAttachments”的现有语义，模型必须为A独享。后台refresh只标记该列表需刷新；页面再激活时合并刷新一次。

页面原resetDraft/restoreDraft不再覆盖所有条目，改为新建/首次acquire时初始化。新对话、选Agent、回历史、fork分别明确选择/创建条目；手动连接重试不改变instanceId。sessionRef跟随当前view，侧栏openDrawer/openOptions不能落到隐藏实例。

### 4.3 可见性、副作用和排队

ChatSession新增visible输入，来自实际页面激活状态且为池选中条目，不仅比较Thread ID。
- 隐藏后继续流消费、运行核实、审批状态同步、权限复核与快照更新。
- 暂停DOM测量、自动滚动、focus、scrollIntoView和可见性相关RAF；保存既有锚点，重新可见后nextTick恢复尺寸，再按原滚动规则工作。不得改scroll-state.ts算法。
- Teleport到body的抽屉/弹窗也需按visible隐藏，保留条目内部状态，不允许后台弹窗盖住当前页。
- 本地尚未发送的promptQueue仅在visible且满足原条件时自动drain；350ms延时回调再次检查visible和generation。切走不会新提交本地待发送项；再次显示沿用现有队列流程。
- 已提交服务端的消息收据/队列照常核实，不重新入队。显式send/approve/cancel只能来自当前可见、仍授权的条目。

### 4.4 保留、容量和权限

本期不使用KeepAlive max=8或60秒TTL自动卸载会话组件：会丢失用户要求保留的折叠/阅读/附件状态，也可能销毁SDK。当前账号/项目作用域内已访问条目保持到作用域清理或明确删除Thread；不驱逐运行中、审批中、动作结果未知条目。

这是明确的内存线性增长取舍，不宣称无限容量。首期容量验证范围：8个并行活跃Thread及30个已访问条目，运行30分钟；同源浏览器部署必须支持HTTP/2或HTTP/3多路复用。HTTP/1.1不能用浏览器自然连接排队冒充保活通过。按现役SDK每条目稳态约2条SSE、单条轮换短暂增加1条估算；实际断言见verification。超过已验证规模不承诺容量SLA，不暗中断掉旧Thread。未来需要回收时另做UI状态序列化专项，不在本期偷改用户体验。

权限：
- 沿用每60秒及激活时访问复核，每条目最多一个在途复核；隐藏标签页调度受浏览器限制，恢复可见立即复核。
- 有效401刷新由现有authorized fetch统一处理一次；仍失败清账号scope。
- 明确403、404或allowed_actions失去read：清此Thread实例、缓存、收据、附件引用和对应草稿存储；旧generation的事件/HTTP结果全部丢弃。
- 网络故障/5xx不能当撤权清内容；保留已授权快照，暂停新的高权限操作，后续操作前重新校验。
- 修正useChatSession.canRead中的hasCachedContent旁路：显式denied后缓存不再授权；不删除尚无撤权证据的内容。
- 换项目、登出、sessionEpoch改变、离开Workspace同步clearScope。Workspace被缓存的旧页面不得重新注册旧scope。Thread删除成功后remove，并保留既有删除授权与确认流程。

## 5. 订阅恢复：只有一套自动重试

### 5.1 普通断线与SDK补丁

继续useStream + service.client + actions.fetch。不新增自定义消息解析器/SDK替身。扩展现有apps/platform-web/patches/@langchain__langgraph-sdk@1.10.2.patch：

1. ProtocolSseTransportAdapter.openEventStream：非主动close的EOF进入原重试分支。重试最多5次，延时1/2/4/8/15秒，抖动±20%；收到响应头不重置预算，连续健康连接30秒才重置，防止空200/立即EOF无限循环。Abort/作用域释放直接结束，等待定时器必须可取消。
2. 使用streamIdleReconnect=45000，任何字节含心跳刷新空闲计时。此为本期客户端设计值，不修改上游心跳。连接45秒无任何字节则恢复；心跳持续但没有token不能当作超时。
3. actions.fetch前的现有授权fetch保留错误专项安全结构；由平台边界在非2xx时抛带status/code/request_id的安全Error，SDK原toError保留Error实例。不得再把原文塞message。
4. 仅网络错误、408/429/500/502/503/504、空响应体/异常EOF可自动重试；其余4xx、410、错误content-type/协议结构错误停止该流。429 Retry-After有效时按秒或HTTP日期解析，等待限制1—60秒；仅stream请求适用，不重复命令。
5. 自动重试在同一logical handle继续产出events，ThreadStream投影不重建。UI仅通过现有status/error入口显示“连接恢复中”或“连接已断开，请重试”，不显示Run失败。
6. 原始subscribe带since仅在首次尝试使用；新的共享过滤并集流及普通重连不注入全局since，遵守当前SDK“重放可保留历史”的契约，event_id由SDK去重。ordering.lastSeenSeq不是UI消费水位；不增加持久化游标账本。

两条物理流可各自按上述规则恢复；不额外加页面setInterval重新fetch SSE。任一不可恢复权限失败需关闭整个条目的流。单Thread连接状态按所有必须流汇总：全部ready才是connected，任一恢复中为reconnecting，任一最终失败为disconnected。

### 5.2 停止重试与手动恢复能力

当前Vue返回值没有joinStream，删除其可选类型断言。为避免重连销毁registry和显示状态，在现有SDK补丁增加以下窄接口，同时修改ESM/CJS产物及类型声明。它们是本期新增，不是假称当前SDK已有。

**Transport层：** 每个openEventStream保留逻辑handle/queue及原filter，内部物理HTTP连接可重新打开。增加suspendEvents()、reconnectEvents()、getConnectionState()、onConnectionChange(listener)四个能力：
- 重试耗尽/不可重试错误进入paused：停止HTTP/定时器，发布含安全status/code的连接状态；不关闭逻辑events queue，不让ThreadStream的#failThreadWithError关闭全部SubscriptionHandle。首次握手尚未成功时ready保持pending，状态由回调通知，手动恢复成功才resolve；真正close/失效scope才reject/结束等待。
- HTTP错误不是Protocol command response，不能reject已发送命令的pending ACK来制造“执行失败”。命令未知结果继续原action对账。
- suspendEvents只暂停物理流，保留logical handles/queues；410可暂停整个Thread两个物理流后查询快照。
- reconnectEvents只恢复当前paused handles；健康流不重复打开；同一次调用共用Promise，等待这些handles重新ready。若恢复再次失败则本次调用reject安全Error，handles仍paused；不是等待首次ready无限挂住。
- 状态包括connecting/connected/reconnecting/paused/closed、每个handle的安全错误；onConnectionChange订阅时立刻回放当前状态，返回unsubscribe。一个handle关闭后从汇总移除，所有必须handle成功才为connected。
- 轮换旧handle close时丢弃其恢复定时器；曾被旧scope关闭的handle绝不复活。首次pending ready若遇close必须settle，SDK关闭流程不能死锁。
- 自动尝试仍只在transport原循环，手动reconnect明确重置五次预算，不另起定时循环。禁止仅修改#failThreadWithError忽略异常却不恢复已关闭队列。

**ThreadStream层：** 公开转发这四个能力至SSE transport，不改变现有消息订阅/投影/去重。非SSE transport调用返回明确“不支持”，不得执行任何run命令。应用继续使用stream.getThread()访问公开接口，不能访问Vue私有Symbol。

**useChatSession层：**
- 新增reconnectStream，通过stream.getThread()操作；尚无Thread时不创建服务器Thread，不发命令。
- 初次Thread创建/绑定及SDK更换Thread时订阅连接状态，卸载时unsubscribe。onConnectionChange驱动已有status/error入口及410单飞恢复；连接错误不设置Run failed。
- 现有重试按钮按来源分流：连接paused调用reconnectStream；原动作unknown继续原actions.retry同一idempotency key/body并先核实执行结果。二者不得混用。
- ensureLiveEventStream不再靠订阅后立即unsubscribe制造旋转；ACK后的激活依赖SDK正常流程。只有paused时恢复。
- 订阅刚建立、先前verify已判终态时也不disconnect，持续保留Thread流。首次state读取失败与SSE握手失败分开：状态请求使用已有service.state/verify重查；不得因为ready pending清空缓存或卡死取消/离开作用域。

测试必须使用真实安装SDK，覆盖首次握手失败→手动恢复、耗尽→手动恢复、订阅扩容期间失败→恢复、待ready时销毁，不接受只mock出上述方法。根/子namespace同一event_id跨恢复各只应用一次。

### 5.3 410安全降级

post33会在非零since小于裁剪水位时返回cursor_expired。当前默认重放路径通常不传非零since，但仍覆盖显式旧游标和未来调用方；不能靠“通常不会发生”删掉处理。

每条目只允许一个recovery Promise，流程：
1. 收到410立即停止自动重试，调用suspendEvents暂停该Thread两类物理SSE；保留已有内容/草稿/视图状态；暂停send/approve及本地queue drain。
2. 读取Thread ACL、Run列表/已知Run及state，确认授权；失败403/404清理，网络失败保留内容并停在可手动重试状态。
3. 经ChatSession现有history/state绑定显示授权后的快照；不把snapshot塞成伪造SSE。新增recoverySnapshot只作为恢复时的数据源，既有历史选择模式保持不变。
4. 通过reconnectEvents重新订阅，不带失效since；SDK保留event_id去重。这只能补当前仍保留的事件，不能证明已裁剪过程完整。
5. 无原子snapshot游标：恢复期间以快照展示已提交内容；增量不能把它降级成更短文本。复用现有checkpoint/消息ID对齐，在收到后续完整root values或Run结束后授权state对齐前保持“历史流已过期，已刷新当前状态；部分过程无法恢复”的原状态提示入口。不按不同快照的文本长度推断先后。
6. 有并发Run时快照只在generation、run_id及请求起止时的当前Run均匹配时应用；不匹配则丢弃并重新核实，不覆盖新输入。状态确认后恢复操作权限；审批提交前继续原interrupt ID/fingerprint校验。
7. 一次恢复仍410/状态不可解析/无权限时停止，不递归清游标重试。用户手动重试可重新进行一次流程。

无缝、全部过程、完全一致的自动恢复不是本期承诺；不改上游以伪造这个保证。普通断线保留已应用数据，但服务端已裁剪的区间也可能无法检测/补回，这是全量保留回放模式的实际边界。

## 6. 网关流式脱敏与资源释放

在runtime_gateway/presentation/http.py扩展_redact_sse_frame、_redact_protocol_event_stream。现有三处调用明确传入口类型protocol/run，避免用Protocol对象约束破坏标准Run数组payload。

处理规则：
- 按原始UTF8字节计算单帧上限8 MiB（8,388,608字节，设计限制，非实测最大值）。按分隔符增量切片，不先拼接一个任意大chunk；多小帧的大chunk不误报。单帧超过上限立即关闭，不输出部分payload。
- 支持LF/CRLF及跨chunk分隔符、UTF8跨chunk、多行data；event/id/retry原义保留。最终没有空行分隔符的data残帧视为不完整，不以正常事件下发。
- 注释心跳不作JSON解析，但也受单帧限额；注释不透传任意上游文本，转为固定“: heartbeat”，不携带内部异常原文。
- Protocol data必须JSON对象，method为字符串、params为对象、namespace为字符串数组；已知消息的字段由现有契约校验，未知合法method/字段递归脱敏后保留，不触发UI执行动作。
- 标准Run的合法JSON对象/数组/标量保留既有形状并脱敏。无data的event:end等终止控制帧保留。不能凭猜测允许[DONE]自由文本；本期三处平台LangGraph流无已确认的该标记，不新增豁免。
- 非JSON data、损坏UTF8、非法Protocol外层、超大帧：不透传原文，不生成伪造Run error、不在HTTP200中追加HTTP Envelope。安全记录原因后关闭上游和下游。
- 关闭后浏览器只能观察EOF/网络异常，按统一重试预算最多重试5次；同一坏帧持续回放则最终停下并显示通用安全连接错误。具体invalid_utf8/invalid_json/invalid_protocol/frame_too_large/truncated_frame只记服务器分类，不声称客户端可从EOF反推原因。
- 日志只含固定reason、现有request_id/trace_id及授权范围内thread_id，不记录payload/token/URL查询秘密。不得修改正常业务正文来做“全字符串秘密检测”；这是结构化敏感字段脱敏，不宣称任意正文自动脱密。
- 上游握手失败发生在StreamingResponse开始前，使用错误专项Envelope及真实HTTP状态。close/finally保留取消屏蔽与资源关闭，客户端Abort、解析失败、超限、正常结束全部验证。

## 7. 现有前端保护清单

用户已否决“普通过程和已结束思考默认折叠，失败摘要和审批保持可见”的展示改造，该建议不再生效。

受保护路径：apps/platform-web/src/modules/chat/transcript.ts、apps/platform-web/src/modules/chat/scroll-state.ts、apps/platform-web/src/modules/chat/components/下的ChatMessageList.vue、MessageContent.vue、ToolResult.vue、SubagentCard.vue、SubtaskDetail.vue，以及apps/platform-web/src/components/platform/MarkdownContent.vue。apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts的既有输出筛选也保留，不借本期重写既有正文规则。

实施前按当时最新工作树采集基线，不能拿本次读取或open-swe外观作目标。正文/过程、思考默认状态、手动折叠、工具/子任务/审批/澄清、Markdown/产物、动画、复制/编辑/fork/retry、问题32%锚定、手动上滑、输入/附件必须逐项验证。ChatSession只允许必要的生命周期、数据绑定和visible副作用约束；不顺带重排模板/CSS/文案或更换渲染器。

## 8. 跨专项依赖、发布与回退

错误响应专项先提供safe error code/status/request_id解析，SSE只消费，不重新实现Envelope；先完成该接口或用已冻结形状的测试double，不让两边同时改client.ts相同边界。追踪专项继续复用现有ID，本期不发明新trace字段。20260924已有页面KeepAlive/SWR作为基础，不能把其joinStream描述继续当作当前SDK已验证能力。

实施顺序：测试基线 → API安全帧 → SDK恢复/动作尾部修复 → 会话宿主 → 综合验证。API/Web分别保持现有上游协议；先API后Web部署，不改Runtime、不做DB迁移、不修改事件保留时间。旧Web遇到网关安全关闭仍不泄漏原文，新Web可连接旧API但缺少本次网关防护，不能据此通过安全验收。

回退单位为本专项Web产物（含锁文件/补丁）与API产物，使用部署前已知版本。回退Web会释放浏览器订阅，不取消Run；用户重新进入读取状态。优先回退Web；API防泄漏修复若需回退应同时评估是否重新放开原文透传，不将安全退化称为无风险。回退演练在隔离环境完成，无自动生产发布/回退授权。

## 9. 决策与交接状态

S01 API/Web范围且Runtime/GraphHarbor不改；S02双入口兼容；S03保留数据、410明确降级；S04服务器执行事实；S05安全帧关闭；S06保留版本并最小扩展补丁；S07展示不变；S08完整实例保活；S09沿用现有创建/对账/交互。

本稿不留“实施时任选架构”的占位项。S07、S08范围为用户已确认；2026-09-26本次交接确认用户在前序文档细化后已同意进入下一专项，方案就绪，业务实现未开始。收到后续明确编码指令才实施；测试失败时按本契约修复；若需要突破Runtime边界、改变UI或丢弃恢复保证，应记录阻塞并回到评审，不能由实施者偷偷改标准。

具体逐文件任务、命令及验收数据见[tasks.md](tasks.md)、[verification.md](verification.md)。参考证据见[open-swe-comparison.md](open-swe-comparison.md)。
