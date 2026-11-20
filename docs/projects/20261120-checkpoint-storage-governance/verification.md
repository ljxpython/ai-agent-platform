# 长会话 Checkpoint 存储治理与 Delta 采用 - 验证计划与记录

项目启动日期：2026-11-20。批准的功能、正式包、容量与隔离恢复已验证；本地main交付及合并后回归进行中。唯一任务进度见[tasks.md](tasks.md)，原项目未完成项不转记为本项目通过。

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
| Worktree | 登记、资源断言、独立安装、实际PID与源码来源已核对；本地main迁回待完成 |
| 产物 | 正式post49、四哈希、CLI、API/Worker与head015一致 |
| 回滚/日志/GC | 引擎真实PG、并发/故障、正式冷安装通过；不从平台旁路操作引擎表 |
| 消息 | 5注册图实际channel清楚，普通两图迁移；ID/删除/清空/工具/update_state/fork/重启通过 |
| 权限/恢复 | 审批允许/拒绝/撤权、队列、取消、崩溃、跨项目/签名负例及备份恢复 |
| 原文/期限 | 页面真实多轮与fork，原文及idle30天保持，无自动活跃裁剪 |
| 容量 | 六组维护预算通过；200轮消息完整且少约70%逻辑字节，读取代价已说明 |
| 未外推范围 | 严格官方等价、全仓既有失败、生产容量和现役升级未作为通过 |

## 整体验收（Final）：功能证据齐备，本地交付待完成

2026-11-21按用户批准的单一新格式、反向JSON Patch和绝对预算核对P01–P06，各自要求具备证据；P07功能与必要链路已通过。人工批准来自用户，不将本地自测冒充独立人审。

尚需将本专项Git合回已前进的本地main、保留主工作区既有修改，并执行合并后必要回归。完成前项目保持partial。Git提交/合并仅限平台本地，不推远端、不执行GraphHarbor Git、不迁移或重启现役生产。旧官方等价性与10月v3专项仍保持独立状态。
