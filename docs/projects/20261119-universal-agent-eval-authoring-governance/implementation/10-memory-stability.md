# 复杂评测内存稳定性：实施与证据

关联Task15–21，日期2026-11-20。唯一进度在原tasks.md，本文保存技术证据，不代替Final。

## 日志阶段

正式配置与仓库基线一致；配置三文件备份在观测目录backups/20261120-oom，原日志卷observability_loki-data保持。

Loki、Promtail原程序校验及compose校验通过。21:56仅重建Loki并停止/恢复原Promtail，保留采集位置；首次ready为503恢复等待，随后ready、EvalFlow health和Platform API _system/health通过。独立48MiB上限采样任务记录可用内存、swap、cgroup、重启、streams及ready，每60秒一次。

候选配置：Loki 256MiB内存、128MiB swap，WAL恢复上限64MB、chunk空闲五分钟回收。移除journal/file两条采集链trace_id索引标签；正文保留，平台现有正文检索与Grafana正文提取路径不变。仍待旧/新日志查询、恢复和至少两小时观察。

备份SHA256：compose 709248c244353f64b8d72b7b6a4bc79cabd74176620bfa0286ab426398a6fddc；loki ff74356ef1ea03550f58798597f4fe914712feaf315ab18df05bc963ab388e93；promtail 9721d6fa53f9d39ee15f4c76f28506e0116c759b2b15c3c86c01f52bfe45ebe0。

22:06:45最终候选另设Go内存目标192MiB及chunk缓存16MiB，观察窗口从该次重建重新计时。应用SHA256：compose 46936075476c676f4872cbe4ce8e9200dbe958f69cdf3d7cd4446d1b446bf839；loki ce50b7c2ea2d101e7fadef905fc8ffbe90bf7079358436c02a6346dcdcef3187；promtail e773519e3030e29e10f6b07b14a25fddc8bfa3cef497e464fb0246e886d6e1ab。

回退使用备份三份配置与原volume，校验后仅重载日志服务；不清理旧日志。读取和评分修复完成前5011保持停止，不用重负载复现整机OOM。

## 旧六轮只读阶段验证

使用正式进程环境中的服务身份和只读数据库事务，不输出凭据。原19份Trace、837个Span全部分批读取，原工具事件73条、审批13次、循环观察、完整性与原报告字节一致，9项检查通过。原296.223MiB内容保留，提取事实JSON为1,561,049字节，耗时41.2187秒，进程峰值266,256KiB。此次通过只读SQL适配器调用同一有界读取代码，不等同新HTTP接口已部署；后续需补当前metadata分页、真实HTTP、规则分数、cgroup峰值和整机余量。

相关126项回归通过，覆盖SQL分页、原始节点、同长度变更、撤权、缺失、文件/归档、旧原生大对象拒绝以及任务生命周期。文件或归档单对象超过8MiB时明确报错，未实现任意大归档的流式拆分。

## 资源故障注入

22:31首次32MiB探针被systemd拒绝：MemoryOOMGroup不是现场可用的赋值。未启动负载。改用OOMPolicy=kill后，独立资源组申请64MiB内存，被该资源组上限终止；Result=oom-kill，MemoryPeak=33,554,432字节。主机和正式服务继续运行。任务对该结果返回resource_limit_exceeded，保留证据并将Agent清理状态标为未确认，不能声称被评测Agent已停止。

核对正式unit时发现仓库模板缺少现场已有app-name、serve-artifacts和产物目录参数；本轮候选保留这些参数，只改变Worker数和资源边界。候选通过测试不等同正式配置已加载。

## 正式读取、评分与软阈值修正

现场扩大789 passed／27 warnings，后端4563f06正常合并为6052416并加载。原生tree200、24,683字节、32/157 Span、0.982秒；匿名401，旧全量入口413。第二轮原19 Trace／837 Span与四规则核对通过，cgroup峰值267,051,008字节、swap0、OOM0，最低可用776,640KiB；事实1,561,049字节，原report字节保持。证据native-http-phase.json、original-evidence-phase2.json及backend-regression.log均在所属私有oom目录。

正式服务768MiB软阈值低于约823MiB常驻量，出现mem_cgroup_handle_over_high、PSI约76%及health五秒超时；未发生OOM也会丧失可用性。23:02备份drop-in后受控改为MemoryHigh1024MiB，MemoryMax1152MiB、SwapMax128MiB保持；MainPID94457、NRestarts0不变，health恢复，PSI随后降为0。备份在production-backup/soft-threshold-before.conf。不得把软阈值再次降至常驻量以下。

任务上限候选640→512MiB、MemoryHigh384MiB、禁swap；启动余量仍512MiB，扣除本scope已分配内存避免重复预留。d36d7a9d因HTTP软阈值问题取证error，f6529b39因余量不足拒绝，原结果保留。86158adc正常创建、CLI立即退出释放导入内存后启动，23:08:54–23:13:10完成两题，五项语义结果按原阈值pass，原19 Run不变。scope峰值252,399,616字节、swap0、OOM0，主机最低713,516KiB可用；详细joint-rescore5-summary.json及joint-rescore5-resource.json保持。47bfe21f退出无评分，未补造结果。

## Runtime采集基准

真实MLflow回调的合成大状态实验：43 Span与拓扑不变、根/LLM/TOOL事实hash一致、原state未改；采集48,987,451→1,813,916字节，RSS峰值581,783,552→314,974,208字节。脚本与两份结果在所属task14的oom-runtime-*。该结果不代替真实模型联调。

## 新六轮实际执行与原文显示缺口

重载所属Runtime API/Worker后，e0d36c3c完整执行六轮，6份上传分两批到达，423.847秒完成，8 Run/8 Trace、302 Span共6,049,147字节，单Span最大317,933字节。265个CHAIN中257个为内部状态引用，8个根、16个LLM及21个TOOL均保留输入输出。四份交付和原件保护规则通过；第五轮未写交付，最后一轮才生成，逐轮11/12而指标0、会话0.6低于0.8，整体failed。一次ls返回path_not_found，完整性检查保守标记tool_execution_unknown/tool_attempt_not_resolved；不将21个工具Span写成21次成功。20条成功事件、2审批，完整原始Span仍可定位。无取证/裁判error；scope峰值248,877,056字节、swap/OOM0、最低可用727,920KiB。新旧执行工具次数不同，不以总字节差替代受控基准。

旧单轮正式页面曾出现明细接口200但正文仍是evalflow.payload占位（后续真实复验已修复）。原生查看器搜索树以节点ID及Trace元信息缓存，补正文时两者均未变；在ExecutionSession按需入口复制Trace元信息以刷新缓存。7项异步/取消/错误页面回归、类型检查、Prettier及关闭既有全局lint插件后的构建通过，真实页面复验已通过，详下文最终阶段补证。直接调用Jest未载入项目CRACO配置导致零测试，纠正为项目test命令后7 passed；错误日志保留，不计测试通过。

## 日志恢复阶段

23:37:23–23:37:44按相同参数受控重启platform-loki，ready恢复耗时16.034秒。容器及挂载保持；旧trace 8f5a2b77784d4fc4995f880b7602be31与新trace 3040122993074269a17107ee91194fef正文在重启前后完全一致。新stream只有job/service；旧stream历史trace_id标签保留，不能称历史索引已全部移除。Promtail运行时unit映射兼容service/api/worker，配置检查后只重启Promtail，runtime-service真实metrics日志已入库。未制造新的业务写入来伪造Trace。两小时参数观察从22:06:45计，配置未变的恢复重启单独标明，尚待窗口结束。

## 最终阶段补证（2026-11-21）

两小时窗口22:06:45至00:07:30、122次采样，最低可用650,804KiB，Loki OOM/stream超限0；swap峰39,518,208字节、末次0，宿主机swap占用净下降。初始503与22:41一次探针超时不隐藏。稳定性原始文件stability-final.json；仅预期32MiB资源组探针被OOM终止。

d0cb23d已合main推送并23:45:09正式加载，PID134216/NRestarts0，1024/1152/128MiB资源保持。e21ad8e缓存修复后，正式旧单轮与所属原六轮最大Trace的根/工具正文真实显示。补收200/129,680字节/50.874秒，仍原19 Run与旧评分error；86158adc由CLI创建未挂接工作项，不用旧错误页冒称新评分页面通过。新增录像23–26及截图28–32保留；25/26明显丢帧，分段空档与捕获限额如实披露。

所属临时384MiB服务从8914aeb8c回退后再升级当前版本，两次health及实验25读取均200，配置与原报告hash不变，正式身份未变。隔离恢复三份日志配置后Compose/Loki/Promtail原生校验通过；未在生产重施已知不够的旧内存值。证据application-rollback.json、configuration-rollback.json。首次归档目录断言与系统Python缺psutil均在停止服务前失败，改用项目原虚拟环境后完成，未计作通过。

桌面报告已扩充9案例/26录像/32关键截图，browser-skill实际播放/加载58/58通过，视频均观察到播放进度。新增25/26明显丢帧、18 partial及各时长上限保持披露；完整后台新六轮与两小时窗口未录制连续录像。检查用专用窗口已关闭，原报告不依赖外部资源。

## 合并后联合验收与环境收尾

Agent实现7bf7475c先推所属分支，再正常合main为32646240并推送；主仓原AGENTS、README及Checkpoint规划的CONTEXT/FEATURES与4份新文档均保留为原未提交工作，没有代为提交。原文件副本与逐项核对在所属私有main-before-oom-merge目录。冻结的6份Runtime/测试/日志配置与main逐字节一致，合并后Runtime11项通过。

EvalFlow d0cb23d正式源码的81份后端与3332份前端跟踪文件和已验Worktree逐字节一致，合并后资源、有界读取及会话证据18项通过，上游mlflow产品源码无修改。00:20:19独立Final另行读取任务、正常认证下原生Run、report SHA、原19 Run、五项语义评分、稳定性和回退证据，20项通过；不是把阶段测试改名Final。00:26再次确认正式API2142、Runtime8123、EvalFlow5000/9128及Loki均200，四个systemd服务active/running，EvalFlow PID134216/NRestarts0。

原生历史评分Run为ab41c28e545148c2b5ae6740b7ff5415，新六轮Run为c262ca99fb3048bab9e259876dd19976，均FINISHED；业务passed/failed分别保持。最初目录diff误含ignored编译产物，改为Git跟踪清单比对；Mac本地别名的错误探针另存oom-local-alias-probe-attempt.json，正式sshmy1健康证据为oom-formal-agent-final-health.json。两次错误检查均未当作产品故障或通过证据。

所属临时5011、回退/再升级与采样单元、Mac所属Agent验收栈和本轮SSH转发已按身份停止，其他转发、正式服务、私有状态、业务数据库及日志卷保留。正式EvalFlow已加载修复；正式Agent没有重载Runtime采集去重，合main不代表正式部署。最终任务状态和剩余边界以原tasks/verification为准。
