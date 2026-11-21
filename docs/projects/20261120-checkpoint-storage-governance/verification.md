# 长会话 Checkpoint 存储治理与 Delta 采用 - 验证计划与记录

项目启动日期：2026-11-20。P01–P07批准的隔离与正式源码交付范围已完成，追加缺陷经post50远端/正式源及平台补验解决；项目当前partial，剩P08生产独立恢复/切换与P09合并后回收。原任务为唯一进度，以下历史失败保留。

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

操作、失败及命令入口见[接入与恢复实证](implementation/01-platform-adoption-and-recovery.md)；脱敏逐例结果见[test-results.json](implementation/test-results.json)。原始XML、日志和截图保留在所属.local-stack/evidence，套件重叠不加总。

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
| 未外推范围 | 严格官方等价、全仓既有失败、生产容量和现役升级未作为通过 |

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
