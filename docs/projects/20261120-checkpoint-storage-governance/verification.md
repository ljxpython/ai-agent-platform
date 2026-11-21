# 长会话 Checkpoint 存储治理与 Delta 采用 - 验证计划与记录

项目启动日期：2026-11-20。P01–P07批准的隔离与正式源码交付完成；P08已获授权并完成生产post50/015切换、独立014恢复和关键业务读回。空白Reference首发与P09新增生产验收残余未完成，项目保持partial。原任务为唯一进度，以下历史结果按发生阶段解读。

## 阶段验证（Phase）：启动规划与机制核查

2026-11-20的证据只有源码和内存桩：引擎capture_baseline复制完整历史，prune没有blob DELETE；Dear/Showcase已是Delta50，普通图仍为默认聚合，摘要保留原消息。不能用这些事实证明现役OOM根因或实际数据库容量。

两仓建立独立项目，原项目本轮增补移出、9份原历史文档逐字节还原。规划阶段平台check_docs、两仓diff --check及14份文档/导航的69个本地链接通过；补Worktree规则后71个链接通过。当时未建Worktree、未改产品、未读密钥，属于历史阶段而非当前状态。

## 阶段验证（Phase）：2026-11-21正式接入与消息状态

平台登记wt_3b7f1734875d，资源、双库/角色、Redis、Workspace、安装与进程独立。精确安装GraphHarbor正式post49双包和LangGraph1.2.24/checkpoint4.3.2/postgres3.2.1/SDK0.4.14/DeepAgents0.7.8，CLI与head015一致。GraphHarbor四产物/冷安装42 passed、1 deselected及取消24场景由其独立项目留证，不把内部可选上游ops排除写成通过。

Reference/平台助手的实际compiled messages为Delta50；Dear/Showcase根和编译子Agent为Delta50，教学Workflow仍是普通聚合。追加compiled专项3 passed。两处迁移继续create_agent，没有引入Deep Agent工具或私有reducer。普通单元复验19 passed、1个需PG开关的测试skipped；随后显式启用PG：消息转换和助手审批5 passed，另有并行/空写/清空专项1 passed。既有23项阶段结果与这些套件重叠，不加总。

消息语义覆盖同ID更新/删除、完整工具配对、52次update_state跨快照、历史fork、并行批次、空写和显式清空。原生普通快照→Delta20轮→独立新进程读取一致。平台助手approve/reject/revoked在真实PG分进程恢复，允许动作才有写入。

新schema消息队列21 passed/3 deselected（not live），覆盖工具屏障、授权/拒绝/回调不可用、checkpoint前后进程crash、一次消费和子图不能抢root inbox。原模拟旧schema缺预算触发函数cleanup导致1项失败已修复，最终不跳过计通过。

## 阶段验证（Phase）：容量、故障与恢复

### 容量

引擎六组同机单namespace夹具全部低于用户事先确认的预算。最大边界330B、建立边界p95 20.214ms、WAL1144B、维护RSS99,983,360B，万条历史prune708.201ms；旧版万条16KiB边界真实触发JSONB超256MiB失败。新旧重复次数不同，旧3次、新20次nearest-rank p95，不伪造等样本比较。锁无竞争，维护竞争另有确定性屏障验证。

平台消息200轮800条完整消息逐项相同；普通聚合4,362,489B，Delta周期10/50/200分别1,573,809/1,323,564/1,276,373B。保留周期50，约减少70%，读p95为108.238ms，不能外推普适最优、全部Worker内存或永久历史有界。读状态不是建立Run边界100ms预算。原始数据见[message-capacity.json](implementation/message-capacity.json)。

### 阶段验证（Phase）：与4GB正式评测的容量边界审查

2026-11-21只读核对post50源码及已有记录，用户同意将结论写回。capture_baseline保存Checkpoint头及必要投影，修改前的数据由事务内撤销日志记录，减少全历史基线复制。200轮约70%逻辑字节收益不外推到整机或完整Worker内存；Dear/Showcase原本已使用Delta50。

事件回放是另一条链路：production_worker仍将持久事件payload序列化后交给redis_stream的put/put_batch；Redis保存正文，默认约2000条、滑动TTL3600秒，本地缓存按2000条限长，终态默认延迟120秒释放，均没有对应字节预算。因此本专项通过不表示Run事件缓存已有字节边界，也不表示4GB连续评测已通过。runtime_events本轮仅按既有恢复记录核对行数，不新增内容或长期容量结论。

该次容量审查未重跑测试或操作生产。当时现役切换尚待P08授权与独立014回退验证，后续已获批执行，结果见本文件生产窗口记录。切换后的4GB复测由评测项目Task23按原用例、原指标和原连续序列记录，不纳入本专项已有通过结果。若仍失败，后续缓存治理须保留刷新、重连、慢客户端、审批、取消及历史回放语义，另行评审实施范围。

### HTTP故障、安全与队列

正式引擎下，公开Platform API→Runtime/Worker→PG的工具/模型重试、写审批、安全诊断与错误脱敏首项通过；另一项覆盖准备前后kill、数据库重试、checkpoint恢复、取消、旧新平台源码重载和硬超时，最终1 passed。旧新平台源码均使用post49，不称旧引擎读取015。关键首项的成功保留在reliability-critical结果中，该次另一项失败不被抹去。

先后修正测试夹具：注册不存在图造成3个setup error；合成Tenant slug不匹配导致预算403；2.5秒硬限与收尾预留冲突导致error；reserve=0后图构造先耗尽短硬限，未进入模型。最终15秒硬限、30秒模型限，真实进入provider等待，timeout且1次attempt。没有改生产超时或放宽鉴权。

宽泛旧P6套件曾43 passed/6 failed/4 deselected，涉及旧Token身份、旧head与记忆断言；没有为此扩大存储专项或修改产品门禁。所需队列、审批及故障链已分别验证，不能宣称全仓全绿。

### 所属环境转换和备份恢复

停栈确认014、零Run后备份，015升级→备份恢复014→再015→启动成功，原审批写入1条保留。pg_dump14/PG17不匹配和首次同库--clean外键失败均已记录；确认新undo表和Run为空后只在所属夹具恢复。生产推荐独立新目标、single-transaction、匹配包，不能直接downgrade或覆盖现役新数据。

真实Reference对话后分别重启所属API与Worker，PID均变化，完整values逐项恢复；续聊模型正确复述旧代号，4条消息ID唯一。来源和脱敏结果见[platform-evidence.json](implementation/platform-evidence.json)。引擎另有归属失败回滚014、修复前进和逆序回滚测试。

## 阶段验证（Phase）：真实浏览器与保留政策

Reference和Dear保留浏览器合跑2 passed（约2.1分钟）：真实模型多轮、代号记忆、稳定ID、刷新完整历史、原生编辑fork与旧checkpoint保留；打开/返回/发送续期、后台读取不续期。实际截图已打开核对，JSON已持久化，含token的trace留在私有证据目录。

首轮点击超时由悬浮助手按钮遮挡发送按钮引起；最终使用产品支持的Enter，不用force点击，不把按钮点击和全部loading视觉状态算通过。UI设计不属于本项目，风险明确保留。

所属三服务保留链1 passed（74.094秒），验证服务端idle30天不能由客户端覆盖、旧策略注册、跨项目及未签名回调拒绝、Workspace/ACL回收、文件占用阻止后重试、并发维护和最小墓碑。原403断言和共享临时项目冲突已修正为真实权限语义和自建独立项目。完整原文保持，不启用活跃自动prune。

操作、失败及命令入口见[接入与恢复实证](implementation/01-platform-adoption-and-recovery.md)；脱敏逐例结果见[test-results.json](implementation/test-results.json)。原始XML、日志和截图当时保留在所属.local-stack/evidence；本轮P09已按授权清理，仅永久脱敏结果保留，套件重叠不加总。

## 验收覆盖

| 类别 | 本轮证据与结论 |
|---|---|
| Worktree | 登记、资源与来源已核对；已合本地main，同提交隔离回归14项通过 |
| 产物 | 正式post49、四哈希、CLI、API/Worker与head015一致 |
| 回滚/日志/GC | 引擎真实PG、并发/故障、正式冷安装通过；不从平台旁路操作引擎表 |
| 消息 | 5注册图实际channel清楚，普通两图迁移；ID/删除/清空/工具/update_state/fork/重启通过 |
| 权限/恢复 | 审批允许/拒绝/撤权、队列、取消、崩溃、跨项目/签名负例及备份恢复 |
| 原文/期限 | 页面真实多轮与fork，原文及idle30天保持，无自动活跃裁剪 |
| 容量 | 六组维护预算通过；200轮消息完整且少约70%逻辑字节，读取代价已说明 |
| 未外推范围 | 严格官方等价、全仓既有失败与生产容量未作为通过；现役升级结果见下方独立生产记录 |

## 阶段验证（Phase）：经验沉淀与远端源码交付

2026-11-21用户追加授权三条经验主题和两仓提交推送。平台在原所属Worktree复用“同版本候选不能证明正式包”条目，补实际API/Worker来源验真，新增独立目标恢复、夹具身份/完整时间预算两条；Runtime经验共23条，索引一致。经验提交2e06bb4已随功能代码推送origin/main，原AGENTS修改保留。

GraphHarbor远端原为post39源码，post49依赖的取消、回执、生命周期及迁移011–014此前未提交。核对后以eeb204c完整交付当前正式源码、配套测试和证据，推送origin/main；不是只提交不可独立运行的015增量。重新下载PyPI四产物，SHA256均与原发布记录一致；runtime51个、CLI11个Python文件逐字节相同。初次Python默认CA校验失败，改用已安装certifi的可信CA后成功，未禁用TLS校验。

本轮只新增经验和Git交付记录，没有改已发布产品源码、重复上传包、打tag或切换服务。GraphHarbor的uv lock --check、版本锁步、兼容基线、Ruff检查/90文件格式及mypy46源码通过；mypy仅保留既有未用deepagents配置提示。平台check_docs、经验数量与两仓diff --check通过，既有功能验证按同源码复用，不冒充重跑。

远端实际结果：平台2e06bb4的[CI44787756204](https://github.com/ljxpython/ai-agent-platform/actions/runs/44787756204)四项通过。GraphHarbor eeb204c的[CI44787814603](https://github.com/ljxpython/graphharbor/actions/runs/44787814603)为五项通过、两项失败：Build、Lint及Python3.11/3.12/3.13生产契约通过；live-server E2E为10 failed/3 passed/20 rerun，内部适配入口的checkpoint写入出现run_checkpoint_undo缺失baseline的外键错误；JavaScript SDK契约返回422 Invalid thread metadata update，具体触发原因尚未完全确认。当时两项未修复，未以可选入口或旧失败为由排除；后续修复与post50补验见下文。

本次核查还发现FEATURES的四个旧失效文档链接，已与提交前原文核对，非本轮引入；未扩大修改范围。新文档推送仅更新记录，不代表上述产品失败已消除。

## 整体验收（Final）：2026-11-21原隔离与本地合并验收记录

按用户批准的单一新格式、反向JSON Patch与绝对预算核对P01–P07。正式post49、四产物哈希/来源、通用安全回滚/GC/迁移、平台消息与审批/队列、原文/fork/保留、故障和备份恢复均具备对应证据。六组维护预算复用最终同源码产物的测量，不将重叠测试相加。人工设计和预算批准来自用户，本地验证不冒充独立人审或生产验收。

专项实现提交d460137，先将本地main的4个并行提交合入Worktree，得到代码提交cff8feb3。保留Trace采集与全部并行文档，仅CONTEXT/FEATURES两处文档冲突采用对应项目main最新事实。合并版运行消息/审批/Trace采集33 passed、无skip；重启所属API/Worker后真实浏览器2 passed（约1.2分钟），新截图已实际打开复核。

通过上述功能和必要验收后，本地main由6165026c快进到cff8feb3。随后核对main与Worktree同提交，在原所属隔离环境执行消息语义、全部5图compiled覆盖及Trace回归14 passed（9.09秒）；主工作区check_docs与uv lock --check通过。没有借用主工作区数据库、安装目录或服务跑验证。原AGENTS修改SHA256保持，未提交；主工作区旧规划单独保留于具名stash，完成版文档接替当前说明。

源码Ruff/格式、E2E Prettier、锁文件、两仓diff --check通过；本次19份相关Markdown的89个本地链接/锚点通过。脱敏原始结果见implementation，后续收尾仅更新文档与证据。

**当时结论：批准范围的隔离验收与本地合并通过。** 此后经验沉淀、两仓源码推送完成，但追加远端补验发现引擎两项失败，当时项目回到部分完成；后续修复和本轮补验见下文，上述原验证事实保留，不冒充生产验收。没有新增在线兼容分支或业务引擎耦合；现役安装升级/数据库迁移/服务重启未执行。完整官方逐字段等价、旧套件既有失败、悬浮按钮遮挡、任意大状态和生产容量仍保留各自限制；不宣称数据库或全部Worker内存永久有界。


## 阶段验证（Phase）：2026-11-21 post50追加补验

正式产品源码84e9021远端七项CI通过；四产物独立哈希/62源码、正式Python3.13冷安装41项及三客户端取消24场景见引擎post50证据。平台frozen锁仅将双包post49升为post50，实际安装site-packages/head015；临时浏览器图已逐字节还原，API/Worker实际子进程57256/57810在安装后重启并核对来源。

消息/助手审批分进程恢复6 passed/141.21秒。队列首轮22 passed/1 skipped/1 failed，测试自建threads缺少产品正常读取的deletion_requested_at列；补齐夹具后23 passed/1 skipped/77.21秒，可选真实模型探针未启用。产品生命周期代码没有放宽。

八类确定性真实浏览器8 passed/50.603秒，另外夹具stream/tool chunks、reasoning、usage与子namespace/审批ID自检1 passed/6.52秒。首轮图配置未被所属管理器采用导致8失败；加图身份断言后5过3失败，原因是有效interrupted历史被测试拒绝及5秒建会话预算不足。修正后三项复验通过，再完整八项通过。410响应仅第一帧受控注入，后续真实重连；离线后hydration且commands只发一次，显式v2由真实Run.kwargs核对。

恢复原图并重启后，真实模型Reference两轮记忆/完整历史/刷新/编辑fork与Dear续期浏览器2 passed/54.5秒，两个opt-in均显式启用，不把先前1项跳过算通过。实际截图已打开核对。原文与idle30天不变，悬浮助手遮挡发送按钮仍保留，测试使用Enter。

原安全专项增补官方/正式post50各42场景及8Worker并发，完整安全18项通过；差异没有转写为严格等价，负责人验收仍由原任务维护。生产库只读预检与恢复操作单已准备，但复制业务备份、独立恢复及停写切换未执行。

## 整体验收（Final）：2026-11-21 post50本地交付补验

本轮依据P07/P08的平台隔离交付范围核对正式产物、实际进程、消息/审批/队列、真实模型记忆/fork/期限以及八类确定性浏览器。上述完整必要链路均有真实执行证据；容量与014恢复复用同存储实现已验数据，未将测试数重复加总。

API请求回归30 passed/2 subtests，Spike与流夹具5 passed，前端typecheck和默认生产构建通过，保留Browserslist与大chunk警告；两仓Ruff/格式/锁及平台check_docs通过。

**结论：P07追加缺陷修复与P08本地正式接入通过。** 不将此阶段性结论标成整个项目done：P08的生产副本恢复、现役切换及负责人具体授权独立保留；P09按合并后的实际回收结果补记。脱敏明细见[followup-post50.json](implementation/followup-post50.json)，生产边界见[操作单](production-cutover.md)。


## 阶段验证（Phase）：合并后回归与所属资源回收

平台5d3e2418已从所属Worktree快进合main并推送，随后在同提交隔离安装执行Spike/流夹具5 passed（8.04秒）。GraphHarbor补证0f017d4远端CI44844213427七项通过。平台同提交真实远端CI44844517275的platform-api、code-quality、docs、platform-web四项全部success，不以本地结果替代。

保留脱敏证据后，原生local-stack stop退出11个所属管理/应用进程，destroy准确确认wt_3b7f1734875d。独立PG目录查询确认双库与同名角色均不存在，四端口无监听、登记和.local-stack目录已删除。GraphHarbor仅本项目约266MiB临时目录及平台浏览器报告/dist已删除，未清共享缓存与其他Worktree。原始XML、日志、私有截图不再保留；必要验收摘要和来源哈希已在项目JSON中持久化。

主Redis4721、AGENTS哈希和具名stash保持；现役Platform API/Runtime API/Worker只读核对均active，现役业务库未迁移/清理。源码Worktree和可复用的独立依赖保留，服务已停；清单及删除后读回见[回收证据](implementation/cleanup-post50.json)。P09完成，P08生产授权与实际执行仍独立待办。

## 阶段验证（Phase）：生产副本独立恢复与015转换

2026-11-21用户单独批准完整Runtime备份复制、独立PG17恢复和015转换，未授权现役停写、迁移、重启或切换。开始时本机空闲74,078,601,216字节，超过40GiB门槛；仓库外专属目录0700、归档0600，单集群/单恢复进程，TCP认证拒绝，只用私有Unix socket。

源PG17.11的可重复读只读导出快照涵盖45张表。PG17自定义完整归档150,958,356字节，两端SHA256均为`21bc1b8864fc7842eca8708a0cd3b50688757f01c4afeabcade3a6b863734831`。pg_dump返回0后，导出连接因空闲事务超时在收尾提交时出错，包装进程退出1；保留该失败，仅在完整恢复与同快照验证通过后接受归档，未盲目重传或隐藏退出码。

匹配现役依赖的正式post48环境，以PG17的`pg_restore --no-owner --no-acl --single-transaction --exit-on-error`恢复到独立空库，用时50.602秒。45张表行数、其中44张内容摘要与源快照一致；runtime_events只核对40,131行，未独立计算大表内容摘要。旧版Saver成功读取全部43个根namespace头，没有执行用户graph/reducer、模型或工具。

从该只读已验库创建第二个独立副本，匹配平台frozen锁的正式post50执行`upgrade_head`，2.215秒升级到015。43张未转换表的数量/可用摘要保持；59组反向JSON Patch应用到对应后态后与旧投影逐项相同，59组namespace边界头及7,814条checkpoint/write before-image逐项匹配旧基线差异。新版Saver读取同一43个头，消息计数与pending writes计数保持；非API/Worker真实执行验收，不重复记为平台E2E。

全部演练和清理563.419秒，小于30分钟预算。所属PG17退出、62320端口释放；两个恢复库的data目录、双版安装、约束、临时脚本与原始日志已删除。只保留仓库外完整备份、清单与身份记录，归档在清理后再次验哈希。源读回post48/014、零活动Run、三服务active且无pg_dump连接；原业务库未作迁移或删除。

脱敏原始摘要见[production-recovery-post50.json](implementation/production-recovery-post50.json)。本机演练目标不可作为现役回退地址；操作单新增待批准的服务端空014回退库、最终停写备份、空间门槛和具体窗口。此次物理恢复库约0.67GB，不将与源约10GB的布局差异归因于Checkpoint改造。P08的独立演练子项完成，现役上线及长期容量仍未验收。

## 阶段验证（Phase）：获批生产窗口与关键读回

上述独立演练后，用户明确同意按操作单继续。2026-11-21在sshmy1固定Runtime源码5d3e2418，制作独立发布安装；757个Runtime文件清单、服务账号实际导入、GraphHarbor双包post50、LangGraph1.2.24/checkpoint4.3.2/postgres3.2.1通过。服务器沿用TUNA镜像，规范化来源后frozen锁及产物哈希一致，不称现场直接从PyPI下载。原源码、私有环境、两份锁、图配置及部署脚本共9项哈希保持。未发布前端、未迁移Platform数据库，也未启用活跃prune。

10:25:09.727 CST停写，最终PG17完整备份431,082,245字节、31.990秒，两端SHA256均为`bf791611613e4f0025869184947d2023f10817d35e25595babc33716d45abe34`。新建服务端014回退库，单事务恢复95.456秒，45表行数/44表内容摘要和52个post48头通过；事件大表仅核对120,788行。现役015转换3.076秒、验证4.637秒，43张未转换表一致，91组反向JSON Patch/边界头及10,299条undo逐项匹配，新版读取相同52个头和pending writes。

Runtime API/Worker经systemd drop-in绑定新安装，Platform于10:29:30恢复，首次暂停新请求260.272秒。Reference队列首次实际执行暴露`Message authorization callback is not configured`；零活动Run后只在Runtime两项覆盖配置补齐同一受信平台来源的消息授权URL，10:38:37重启Runtime并复验成功。没有改原始私有env，也没有全局启用缺失的生命周期签名回调。

实际业务结果：

- 三条旧线程state/history读回：两条完全相等；一条仅连续并行tool结果顺序交换，按该组tool_call_id排序后相等，逐条消息ID、完整内容、tool_call_id配对及其他状态均保持。没有将其他差异归一化掩盖。
- Reference真实模型两轮记忆、消息ID唯一、刷新完整历史、原生编辑fork及旧Checkpoint保留通过，最终44.8秒。**首轮经真实API建立，浏览器从第二轮进入；空白Reference首发无请求，未通过。** 延长等待、Enter和键盘激活按钮仍失败，不能仅归因为启动慢或现役Checkpoint升级。
- Dear浏览器查看/返回/发送续期、后台读取不续期及真实模型success通过。
- 真实HTTP操作套件38.1秒：等待Run实际running后排队，同key重试同receipt、消费及消息仅一次；跨项目403，取消interrupted；Workflow当前interrupt ID经整数command ID和原生`input.respond`恢复success。

10:43:10.493关键验证完成并关闭窗口，共1080.765秒，在20分钟门槛内。10:44读回三服务active、NRestarts0、PID为Platform531268/Runtime API537330/Worker537331；Runtime`/ok`与Platform`/_system/probes/ready`均200，零活动Run，暂停后新增内核OOM0。库10,226,308,787字节，可用内存1,344,077,824字节、余盘13,140,541,440字节；短时数据不证明4GB连续评测或长期内存稳定。

保留其他失败：错误探针路径401、SSH隧道使用127.0.0.1 Host命中状态vhost而404，改既有localhost vhost后200；pending Run排队409，改为等待running；审批早期错误入口未实际恢复，字符串command ID返回400，改原生入口和整数ID后通过。均为实际诊断/夹具过程，没有据此增加生产兼容逻辑。

生产验收新增12条删除任务。10条的Thread/Run/checkpoints/writes/blobs/events均0；其中3条inbox只保留回执，payload全部为空。2个空Dear线程仍before_delete，各有1条Thread但无Run/Checkpoint/事件/Workspace绑定；保护原因`legacy_workspace_location_unconfirmed`。1个Dear远端Workspace未purged，只读报告为deleting、eligible=false。Runtime终态签名回调及Platform完成校验缺配置，after_delete仍未完成；切换前已有14条任务，当前26条（before_delete8、after_delete18）。不全局启用后顺带删除原业务，不手改任务或伪造绑定。

追加只读节点诊断：sshmy2该Workspace资源0、accepted操作0，证据kind=deleted_thread；实际旧代码不含已删除会话零宽限逻辑，运行进程使用604800秒宽限。eligible=false由旧策略解释，不是已确认的资源泄漏；本次没有升级节点或缩短保护。2个空Dear的未绑定位置与签名回调缺项仍独立存在。

必要证据留存后，7个临时浏览器文件及其目录、83个本机临时文件（7,628,761字节，含原始日志、来源tar及脚本）已删除。所属隧道PID84167按完整命令核对后停止，59180/59181均无监听；其他隧道和EvalFlow临时文件未动。最终完整备份再次验SHA256、0600及父目录0700；本机只留归档、身份与必要清理证据。服务器备份/014回退库/新旧安装保留，生产受保护残余未假报清空。

**本阶段结论：生产post50/015已切换，独立最终014恢复与上述关键读回通过；整个项目保持partial。** 空白Reference入口、受保护生产验收残余仍是P08/P09未完成项；严格官方协议/负责人验收及4GB连续容量继续由原专项维护。最终完整备份、服务端014回退库和新旧安装保留，已有新写入，禁止直接回退覆盖。脱敏证据见[production-cutover-post50.json](implementation/production-cutover-post50.json)，截图见[Reference分支](implementation/production-reference.png)和[Dear续期](implementation/production-retention.png)。
