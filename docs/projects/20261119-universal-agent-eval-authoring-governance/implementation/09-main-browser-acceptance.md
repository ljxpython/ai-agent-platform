# 合并版浏览器验收与报告（Task14）

日期：2026-11-20。当前为阶段证据；唯一任务进度在原tasks.md。长来源、独立发布、客观错误检出、固定交互和同证据重评已核对，两仓产品及阶段文档已推送。历史终态修复已在页面生效，但裁判超时后的第三次评分结果及收尾健康待远端恢复核对；报告41/41媒体实际播放／加载通过，不能据此宣布Final通过。

## 合并与版本

Agent正常合并提交dbc656a9；EvalFlow远端正常合并69d0584。EvalFlow原有7d3cb7f和0a5b89b并行修复均为合并版祖先，未覆盖产品目录；Agent主仓AGENTS.md原有改动逐字节保留且未提交。Runtime所属Worktree已同步main，API／Runtime及Web使用登记环境wt_644e8a066eac，Web27968／API25075／Runtime26631。最新产品为Agent fd99405b／EvalFlow 8914aeb。EvalFlow所属5011经9138访问；本轮未主动重启正式生产，后续19:08全局OOM曾触发其自动重启，见环境记录。

Mac前端构建同步到所属远端的生成目录mlflow/server/js/build，不改上游跟踪源码。HTTP页面实际返回main.bf3f6555.js，asset-manifest SHA256为983521c386d184edbe156d5ca9ae564aa70af3d0ae7f6e88a5355b81877506f1。

## 合并版回归

- EvalFlow原57套后端清单重新执行：756 passed，27 warnings，25.79秒。
- Runtime工具流式专项：7 passed，2 warnings，5.95秒。
- 前端4套41 passed；类型检查通过。默认build因既有全局lint失败；DISABLE_ESLINT_PLUGIN=true后的编译通过，两者不混称。
- 来源修复关联回归：157 passed、2 skipped、499 subtests passed；另2项工作区缺文件错误文案断言失败。临时使用HEAD原源码及相同身份夹具重跑，两项仍以相同“File not found”与“Workspace file unavailable”差异失败，修复源码已按哈希恢复。不是本次新增失败，不改无关错误文案。

## 来源长会话转换问题

浏览器打开六轮会话77761538-99f1-4da8-b0bf-ceb9d2e8cd17并点击转为评测集。POST在17:48:29返回202，约60秒后的Runtime读取401，通知明确显示转换未完成。页面直接读取同一会话为200。

调用核查发现：后台复用get_runtime_gateway_service产生的网关。大部分state/history已逐次签发，但_load_thread、list_thread_runs及get_thread_execution_evidence的原生Run读取仍使用初始委托。补测试令旧upstream凭据过期、只有重新签发的upstream可读，原源码先失败，最小修复后通过；同时确认无权用户在签发前拒绝。复用_thread_upstream，不增JWT claim／operation，不延长有效期，不放宽Runtime校验。图片／文件测试补核对先read、再用途委托；真实双服务测试延续原锁定身份夹具。

## 客观用例首次尝试与漂移保护

浏览器新建b7978d95-81c1-41fc-b90f-e3076fbecb6b，材料通过产品粘贴文本资料逐一添加六表；原生文件选择自动化被CDP拒绝，未称上传通过。完整配置导入已冻结的objective-case，保存修订2，三规则分别是completion、artifact_correct、protected_unchanged，没有模型裁判或动态模拟。主动授权发布题库v1，页面显示已发布尚未运行，然后显式点击运行。

任务ab32aebe-d8d8-486d-a987-7b7299d5b2fb、Session9d366044-3bf3-4762-88c0-8f8982e3dc24已真实运行。此时为修复来源问题修改API源码，工具write_file恢复前被target_configuration_changed阻断；停止回执no_active_run／not_required。该次不是业务通过证据，原失败保留；修复合入、重启并冻结产品源码后另发完整验收。全屏Trace窗口、退出和原始错误展示实际可用。

## 媒体与交付形式

用户选择桌面独立验收目录，HTML按C01–C07组织前置条件、操作步骤、预期、实际、版本、MP4和关键截图。18段原始MP4合计4541.3秒、348,301,585字节，23张现场截图，编码及SHA清单已生成；HTML不依赖外网服务，移动时需整体保留媒体目录。

01–16段正常停止为complete／user_stopped；第17段600秒达到duration_limit，为complete但未覆盖最终结果；第18段473.881秒、2029帧，因session_ended为partial，包含89错误回看和47启动，未覆盖最终结果。09段892帧、11段85帧、12段4帧、13段937帧、14段5帧、17段33帧丢失，其余0；分段间存在空档。第17段实时状态帧数未更新曾被误读为停滞，停止后核对实际1814帧，已纠正，不把实时计数当视频失效证据。首次临时HTTP预览器不支持Range，随后改用现有Starlette静态文件服务，只绑定OS分配回环端口；没有安装依赖或更改产品服务。

后台自动播放最初被Chromium省电策略暂停，不能把该错误当文件损坏。用户明确允许临时置前专用验收窗口后，报告按钮逐段实际播放并观察currentTime大于0.03秒、逐图检查naturalWidth，18视频和23截图共41/41通过；浏览器DOM结果与报告截图均已保存并回读，专用窗口随即关闭。未改变浏览器设置或绕过权限。本地file导航被CDP拒绝，实际验证采用回环HTTP，不声称file方式已由浏览器验过。

## 六表冻结版本结果与长会话分页修复

ce091a93冻结版本任务df3e5461-f414-4ba4-b68e-e882f5317379在18:20:12结束，耗时426.771秒，Session b5a00218-1132-442e-b955-34fb5674f40b，1输入/1输出、5 Run/5完整Trace、17工具、4受限审批。六个上传回执与原文SHA一致。completion和protected_unchanged均1.0；artifact_correct为0，因为order_audit.csv的O012/O013/O019/O020漏填excluded。另外三文件与冻结参考逐值一致；完整表26行，地区3行、超时4行，主要统计16单/5066.50元/四类8、2、4、2/超时金额871.49/25.00%/到期13单/30.77%正确。独立读取实际CSV发现相同四处差异，未放宽阈值。页面结果、失败文件定位已录屏，原漂移失败保留。

修复鉴权后第二次来源转换main验收-六轮来源修复复验-20261120越过401，但history读取仍报LangGraph upstream timed out。原每页100个checkpoint重复携带累计状态，18:14:34发出后约39秒才收到200响应头，后续仍超时。最小调整为每页10、200页，保留2000上限与原冻结/重建/材料完整性语义；未放大超时或JWT有效期。23、2000、2001个历史点的回归先红后绿，关联75 passed及181 subtests passed。首次从仓库根执行测试出现tests包导入错误，改为服务目录后正常，不算产品失败。后续小分页和来源容量修复后已完整送达，详见下节；早期超时保持为历史失败。

## 来源容量与固定交互补证

长来源小分页实际完成66页及19份执行证据读取，250KB资料限制随后拒绝，录像11/截图13保留。测量当前128条消息按交付字段为515,619字节，19份manifest为52,212字节，模型可见对话正文23,862字符。仅为服务端snapshot将隐私检查容量传为1MB，原文不裁剪；手填250KB、签名请求1MB和模型150,000字符继续独立约束。5项新增测试旧实现先红，相关49项绿；首次连续字母长行导致既有隐私正则慢扫描，中止后以分行长文重验，未修正或声称该性能边界通过。

2a519071固定交互新任务9548e720通过，scope回应及计划批准真实发生，3 Run/3 Trace、三规则1.0、裁判调用0；视频12及截图14保存。

## 完整来源、候选校验及独立发布

fd99405b实测送达572,218字节／128消息／6条用户输入／19 Run，history_complete及runs_complete为true、changed_during_capture为false；逐消息ID及内容hash与来源当前状态一致。来源environment为initial_state_unavailable，19个manifest没有附件初态，具体原因未确认；不伪造可重跑环境、文件断言或“附件已恢复”。

真实AI作业deea6d5e首响应结构ValidationError、第二响应完成，生成2题，其中第1题仅保留前4轮。操作员初次AI复核漏审，采纳为修订1后被发布既有全轮次保护拒绝，operations为空。fe41f19在normalize_proposal复用bind_source提前检查，覆盖AI候选、采纳及编辑；新增7项旧版6失败，相关69项通过，Ruff既有29／新增0。

页面修订1保存明确拒绝且版本不变。操作员从完整原文补入第5/6轮，只把第1题指标关注范围限定为前4轮；第2题和全部阈值不变。页面保存修订2后独立发布题库d-29af713efdbf472c9a69340651a6bc3b v1，hash为0cf7f8f4af58756457b57e7bcc4e73dacdd8391c2e61917d6b6a570de1a4ed1e。发布没有自动创建评测任务，随后才显式启动历史评分。录像15/16和截图19–22保留失败与修订过程。

## 历史审批续跑终态修复

任务9b83ecc4的5项语义指标均通过：第1题BusinessFacts为0.9、ConversationalGEval为1.0；第2题三项均1.0。但整体error，因为原source_evidence要求每条Run都success，把13条已续跑的审批interrupted也判source_execution_incomplete。保留该error，不改题目或旧Evidence。

8914aeb仅对状态全部属于success/interrupted的历史按created_at可靠排序，最新时点所有Run为success才认为已完成；未决中断、error/cancelled、未知状态、缺坏时间或并列时点仍有中断保持拒绝。11项回归包含升倒序、时区和并列时间；原实现先红，扩大188 passed、6 warnings、5.29秒，Ruff27项既有／新增0。首次扩大命令误写不存在套件而未收集，随后纠正通过，不计成产品测试失败。

所属5011在无活动任务后停止并重载，PID3325573；产品70份Python文件hash冻结为8914aeb。页面从同一已发布v1新建历史评分89f218b5，不用复用旧Evidence的重评操作，未重跑Agent。该任务两题执行证据均completed、source_execution_incomplete已消失，证明终态修复在实际链路生效；但5个语义指标均为scorer_exception/error，至少一次裁判调用有APITimeoutError、68.139秒及未知用量，整体仍error。脱敏结果保存在HTML目录evidence/historical-infrastructure-error.json。不能以终态修复成功替代完整评分通过，也不能仅凭同期OOM断言所有裁判超时均由OOM引起。

恢复所属5011后，页面从同一v1显式创建第三次历史评分47bfe21f-b18a-4ea7-941f-d8977e33033c；原题目、阈值和dataset hash保持，未重跑Agent。启动后用正常鉴权API核对来源仍原19个Run，13条历史interrupted、6条success，集合与首轮来源一致。最后确认该任务running、0/2；19:48后SSH及本地9138再次不可达，最终结果仍待核对，不能凭等待时长推断通过。原六轮0.7／0.8结果保持。

## 固定交互与同证据重评

2a519071冻结版本任务9548e720真实完成scope澄清及绑定计划批准，3 Run／3完整Trace、4工具、两次自动响应，三规则均1.0，裁判与模拟调用0。执行45.753秒、墙钟83.990秒，页面配置和结果已录屏。

页面对df3e5461执行“用当前发布标准重评（不重跑）”，生成b8a783b8，仍按原规则1/0/1正常failed、无error。Session、Run、Trace、输入、输出、上传、审批和逐轮快照8组证据相同；正常接口确认仍是原5个Run。原六轮2ff899ef及c80efddf的0.7／0.8失败未改写。

## 环境中断与生产边界

19:08:12宿主机发生全局OOM，journal记录某Node进程触发分配、正式EvalFlow的Python被选为终止对象；这些记录不能单独证明全部资源根因。systemd于19:08:33自动重启为PID3320689，NRestarts=1，随后5000健康200。此前生产PID不变的核对只适用于当时，不作为收尾结论。Loki还有独立cgroup OOM记录，本轮未改其资源或重启其他服务。

19:38:02再次全局OOM，journal确认PID3325620的本轮验收进程域Python被终止，随后所属后端PID3325573不存在；旧评分Worker3327564曾仍在。仅用所属scripts/local-stack.sh恢复5011为PID3332712。实际宿主机约3729MiB内存、4095MiB swap，恢复时快照used3408／available321MiB、swap used3271MiB；不是早期文档估计的约8GiB。未调整Loki或其他服务资源，没有声称完整定位资源根因。

SSH曾连续banner exchange超时，9138转发断开；恢复后只重建本轮9138／37211双向转发，没有调整SSH、内核或生产配置。19:48后SSH及9128/9138再次不可达，独立TCP探针也超时；ping三包正常仅证明ICMP可达，不等于业务健康。最终服务和远端源码冻结核对仍须等连通后完成；不把已通过单测当作环境恢复。

## 当前Git与证据边界

Agent产品fd99405b及阶段文档311af2e、EvalFlow8914aeb已合各自main并推送，Mac EvalFlow主仓及镜像Worktree已同步产品；7d3cb7f及0a5b89b并行功能保留。Agent冻结673份产品文件在本地收尾再次核对无变化；EvalFlow远端70份产品文件的最终复核仍待连通，原AGENTS.md未提交改动SHA保持。最终文档按本次结果更新，不将文档提交当产品重新验收，也不销毁当前验收Worktree、数据库或用户stash。
