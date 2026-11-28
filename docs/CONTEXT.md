# 项目当前状态 - AI 上下文

## 当前交付：EvalFlow双机开发与运维规则（2026-11-21）

Task24当前批准范围已完成（done）。EvalFlow的AGENTS、项目Skills、指南及运维入口已按实际双机分工同步，e33b501已合main推送，两台服务器检出与Mac镜像一致。后端继续在sshmy1独立Worktree开发，正式应用/评测及任务产物在sshmy2，Agent/Runtime/PG/Redis和原9128入口留sshmy1；前端重度构建只在Mac。旧整仓镜像发布脚本启动即返回2，make deploy-status只读检查双机与公网，正式发布按EvalFlow仓docs/DEPLOYMENT.md在获准窗口执行。10项回归与合并后实际入口读回通过，服务PID/NRestarts和6份受保护配置摘要保持；未发布应用或改数据、预算。Agent只交付原项目文档与当前摘要，不合并失败资源候选，不覆盖Checkpoint post50/015或用户AGENTS。唯一进度与边界见[Task24](projects/20261119-universal-agent-eval-authoring-governance/tasks.md#task-24同步双机迁移后的开发规则与运维入口)。

## 当前交付：EvalFlow双机连续正式评测（2026-11-21）

Task23当前批准的双机迁移、单并发连续容量及合并后联合读回已完成（done），两仓文档同步交付。无需追加内存：EvalFlow启动前约2GiB可用预算包含应用、评测和系统余量。五条正式任务均完成评分，Agent业务低分保留，完整结果及边界见[唯一Task23](projects/20261119-universal-agent-eval-authoring-governance/tasks.md#task-23在4gb主机上完成正式自动评测)。EvalFlow产品813dc61已合main并在正式目录对齐，Agent本次只同步文档，Checkpoint post50/015新写入及用户AGENTS改动保持。

## 当前交付：正式 Agent 已加载采集去重（2026-11-21）

用户批准的Task22正式部署与独立生产读回已完成。Agent应用基线0a2f93ca，Platform API / Runtime API / Worker于00:57:22重载，PID178977/178973/178975、NRestarts0；EvalFlow PID134216保持。普通聊天两轮补传CSV、两次read_file及19.75/22.00通过；两份Trace共73 Span/778,425字节，64内部CHAIN输入输出引用，根、LLM/TOOL原文和一次上游504事件保持。API与实际Worker包指纹237f40e3一致；独立主机22项/业务16项通过，四份旧资产hash及三条旧任务读取、十份配置/锁文件保持，无新增OOM或活动Run。首轮swap增长，后续60秒稳定，不称长期容量通过。正式EvalFlow新任务555ae0cd因不足1GiB可用内存被保护拒绝，未执行Agent、不放宽门槛。依赖、数据库、前端及并行Checkpoint规划保持。唯一进度见[Task22](projects/20261119-universal-agent-eval-authoring-governance/tasks.md#task-22正式部署并验证-agent-采集去重)。

## 当前追加：复杂评测OOM修复已批准（2026-11-20）

有界Trace、事实复用、按需正文与Runtime去重已完成批准范围的实现和合并后联合Final，Task14–21均done，后续Task22已完成正式采集加载。原19 Trace/837 Span及四规则保持，86158adc两题五项语义按原阈值pass；新六轮302 Span/6,049,147字节，必要事实和文件保持，逐轮及会话业务failed如实保留。Loki原两小时无非预期OOM/新增stream超限，最低可用650,804KiB，swap未持续积累；应用回退/再升级通过。Agent32646240、EvalFlow d0cb23d已合main推送，正式EvalFlow与Agent新采集均已加载。桌面报告9案例/26视频/32截图，58/58实际媒体核对通过，所属临时验收栈及转发已停。长期容量、8MiB单归档限制及既有lint/录像缺口见原verification。

用户于2026-11-21批准沉淀OOM经验：Runtime内部CHAIN采集去重写入本仓经验库；有界取证、软内存阈值与Loki标签治理写入关联EvalFlow经验库，索引已更新。该知识提交仅文档；随后Task22的正式加载与生产验收单独留证。

> **最后更新：** 2026-11-28（专题 07 `eval_copilot` AI 出题专家闭环完成，未提交 Git）。一阶段及二阶段（[专题 06](projects/20261128-independent-eval-platform/06-metric-reliability-and-migration-gap-audit.md) `Task 6.1–6.4`）与架构文档 [docs/architecture/08-evaluation-platform/](architecture/08-evaluation-platform/README.md) 已推 `origin/main`（`62063827`）；本次完成 [专题 07（Task 7.1–7.5）](projects/20261128-independent-eval-platform/07-eval-copilot-skills-and-authoring-agent.md) 全部落地——为 `eval_copilot` 实装 4 份领域 Skill、多文件上传读取、7 项 HMAC 控制面内部桥、同源 Schema/防呆与 `turns[].role` 强校验、`HumanInTheLoopMiddleware` 分级审批（新建 `<5` 免弹窗、覆写/`>=5`/试跑必审）、同线程 `cancel_own_trial_run` 免二次确认停表、反作弊红线与前端实时试跑胶囊/中断状态兜底，并通过本地 `RUNTIME_BACKEND=local` 全栈真实 `/browser` E2E 全链路验收及三端单测（已同步将 `chickener` DeepSeek 设为出题专家默认模型）。剩余边界：`v3-golden` 其余 7 题（含 RAG 与 PlanReview）、远端 Docker 沙箱与定时巡检 Cron 待补。
> **AI 读取规则：** 每次新会话开始前主动读此文件；改动完成后更新对应行。
> **维护规则（渐进式快照）：**
> - 「最近改动」只保留最新一条完整描述；新条目写入时将上一条折叠进「本月归并」
> - 「本月归并」每月一行（月份 + 核心事项，50 字内）；超过 2 个月的月份直接删除，历史在 `docs/projects/` 和 `docs/changes/` 里
> - 各服务状态表和活跃项目始终保留当前有效信息，过期条目直接删除

## 当前增补：长会话Checkpoint存储治理（2026-11-21）

[独立项目P01–P09](projects/20261120-checkpoint-storage-governance/tasks.md)部分完成（partial）：P01–P07隔离/源码交付完成，P08获批生产窗口已完成post50/015切换、最终备份和服务端014恢复；空白Reference首发仍未提交请求。P09原隔离栈/独立演练资源清理完成，生产验收残余被生命周期保护。GraphHarbor只交付通用journal-v1边界与引用安全GC，无平台业务。反向JSON Patch和六组预算均由用户批准。

正式post50四哈希/62源码、正式安装41项与取消24场景通过，产品源码84e9021远端CI44840687787七项success。原外键/线程PATCH422/跨topic事件误去重已修复，旧失败保留。平台5d3e2418已合main推送、合并后5项回归和CI44844517275四项通过；原wt_3b7f1734875d双库/角色/四端口/登记已回收，源码Worktree保留。

| 服务 | 本阶段当前状态 |
|---|---|
| runtime-service | `sshmy1` 生产已部署最新 MLflow 诊断写/读（紧凑 3576B 标签快路径 + 空 `TraceData` 回退 + Root 结束短时 flush）、独立 `INFO` 诊断日志流、上下文关联补齐及按 Thread 检索/非法 UUID 容错；API `4055313`/Worker `4055314`、`NRestarts=0`、`8123/ok` `200`；`tests/observability/` 186 passed（`tools/images.py` 本地脱敏日志未合入 release） |
| platform-api / platform-web | `sshmy1` Platform `4043344`、`NRestarts=0`、健康 `200`：已部署 `read_checkpoint` 有界 `before` 游标分页（消除 `run_mismatch`）、`require_scope` 默认租户 `"__default"` 对齐、`thread_runs`/`thread_activity` 及开启平台助手、Loki 与 `admin` 日志权限；回归 123 passed / 6 subtests passed。`platform-web` 已于 2026-11-25 部署至 `/www/wwwroot/agent-platform`（非 HTTPS 剪贴板降级与完整 `run_id` 复制按钮），外网首页 200 |

六组最大边界330B/WAL1144B/建立边界p95 20.214ms/维护RSS99,983,360B/万条prune708.201ms；200轮周期50消息逻辑字节少约70%，状态读取p95 108.238ms不属于建边界预算。不承诺永久状态有界，也未证明现役OOM根因。隔离014备份恢复/再015已验，生产恢复须独立目标。

用户同意记录与4GB评测的审查边界：post50减少Checkpoint基线复制，但Redis及进程内Run事件缓存仍保存正文、按条数限长，没有对应字节预算；逻辑字节收益不能外推Worker或整机内存。Task23此前单机连续容量未通过，后续双机单并发容量已独立实测通过，结论不由Checkpoint存储收益推导；该审查本身没有授权新增缓存治理。

2026-11-21已按用户批准停止sshmy2四应用并迁入EvalFlow，Agent/Runtime/PG/Redis留sshmy1，原9128/5000入口保持。含新增结果的实际回退、五条正式任务、615秒稳定窗口及合并后联合读回通过。三条附件四规则1.0，客观及原六轮缺产物正常failed，无执行/裁判error；15 Trace/566 Span和真实文件完整。两台采样最低786.14/1276.38MiB，末窗口Swap稳定、PSI avg10为0、OOM新增0，之后第五条继续passed。启动前2GiB已含应用1GiB、scope512MiB和系统512MiB，无需先扩8GB。EvalFlow产品813dc61已合main推送，正式PID817813/NRestarts0保持。Nano仍enabled，未验证多并发、长期或并行重型RAG；原Nginx身份注入与default503保持。唯一Task23当前批准范围已完成，文档同步交付。

生产副本演练已获用户单独批准并完成：完整备份两端哈希、45表行数/44表内容摘要及43个post48 checkpoint头一致；第二副本015转换核对59组反向投影/边界头、7,814条undo及相同43个post50头。含清理563.419秒；导出连接收尾空闲事务超时导致包装退出1，只有完整恢复/同快照验证通过后接受，见[证据](projects/20261120-checkpoint-storage-governance/implementation/production-recovery-post50.json)。新演练PG/双库/安装/日志已清理，完整归档在仓库外0700目录以0600保留。

后续获批生产窗口10:25:09–10:43:10 CST完成，关键验证1080.765秒，首次暂停新请求260.272秒。最终完整备份431,082,245字节两端哈希一致；服务端graphharbor_ckpt014_20261121单事务恢复95.456秒，45表行数/44摘要及52个头通过；015转换3.076秒，91组反向投影/边界头与10,299条undo逐项一致。旧三线程仅一条并行tool顺序变化，内容/ID/配对保持。[生产证据](projects/20261120-checkpoint-storage-governance/implementation/production-cutover-post50.json)保留来源、窗口及失败。

最后生产读回post50/015、零活动Run、三服务active、无新增内核OOM；库约10.23GB、可用内存1.34GB、余盘13.14GB，仅为短时值，不跑压力。现役业务库graphharbor_acceptance、完整备份、服务端014回退库及新旧安装保留；已有新写入，禁止直接回退覆盖。P09新增12个验收删除任务中10个核心数据已删、3条inbox正文均空，2个空Dear线程和1个远端Workspace仍受保护。终态签名/Platform校验配置缺失，全局补齐会继续原14个删除任务，须先确认业务范围；当前26任务为before_delete8/after_delete18。下一步定位空白Reference首发并处理获准的生命周期残余。用户AGENTS、原stash、共享Redis和其他项目资源保持。

## 当前增补：复杂评测集一次启动自动执行（2026-11-20）

用户批准将固定交互自动执行方案写回原项目并进入Worktree开发。沿用MLflow、DeepEval及现有断言/结果页，补材料轮次、结构化信息补充/计划审阅、受限审批、逐轮产物证据与真实正负例验收。后端使用sshmy1关联Worktree，登记后端5011/前端预留9138；主仓39d4656及原有未提交文件保留。宿主机可用内存偏低，串行验证，前端重度构建只在Mac进行。

用户同意的收敛已实施：默认完整输入加客观验收，固定交互按需，动态模拟不扩建。新用例仅规则指标的制作／契约／编辑／发布及执行已验证。客观任务842be548一次提供六表，1输入／1输出、4 Run／4 Trace、16次工具调用、219.083秒，四文件正确、三规则1.0、裁判与模拟调用均0。与原六轮分开发布和统计，不改历史指标或标准。

Task8–13开发及验证done：固定澄清、计划审阅、分轮附件及受限审批保持。真实HTTP79e1f510与页面ee7a8040通过。运行时4行空名称兼容修复，关联56项／专项7项通过；环境wt_644e8a066eac、Web27968/API25075/Runtime26631。原六轮2ff899ef完成6输入／6输出、19 Run、75工具调用及13审批，四文件和原件保护通过；新同证据重评c80efddf取得19份完整Trace，四规则1.0、会话0.7低于0.8，整体failed且无裁判error。裁判按需组织必要事实、对完全相同重复项显式引用来源，沿用已有结构化非思考模式；旧error不覆盖。57项独立Final通过，实际工作台和跟踪服务原生结果可读；开发5011原生相对链接与5000跟踪库不同，手册已注明。后端753 passed／3项HEAD既有认证失败；前端40项／类型检查及关闭既有lint插件后的编译通过，默认构建失败保留。Redis2GiB／noeviction、新增OOM0，所属API／Runtime及5000／5011健康200。远端主仓0a5b89b／生产PID3167539为并行工作当前状态，本轮未覆盖或重载。Task14后续已完成两仓正常合main、OOM治理和9案例报告，58/58媒体核对通过。历史89f218b5裁判error与47bfe21f无评分保留，86158adc完成原标准重评；19:08/19:38整机OOM和19:48 SSH中断为历史。当前正式EvalFlow已加载d0cb23d，Agent三服务已由Task22重载新采集代码并完成生产读回，所属验收栈已停。唯一进度见[原项目任务](projects/20261119-universal-agent-eval-authoring-governance/tasks.md)。

## 前期已完成工程交付：通用 Agent 评测集转化与出题治理（2026-11-19）

用户已确认两步推进及职责边界修订：第一步清理通用提示词与 Schema 描述污染，补非退款/真实退款正例回归；第二步在 EvalFlow 解耦通用出题、已有回答评分和按需新运行。能力信息为可选出题参考，不要求来源 Agent 在线、具备完整工具清单或已支持重新执行；文件类和纯文本类素材均应能独立成库。详见[项目入口](projects/20261119-universal-agent-eval-authoring-governance/README.md)。

| 服务 | 当前状态（2026-11-19） |
|---|---|
| eval_platform (mlflow-eval-platform) | Task1–7工程交付done；合并产品9373c1e保留既有功能，689项及真实模型全链路Final、21 Span和十题AI质量10/10证据保留。所属开发服务/Worktree/10个SQLite库已回收，共享生产库保留。Task6正式服务15:46:59重载，新PID2308114、5000/9128健康200，源码属主仓、三份配置与十份工作项哈希不变；server旧资产可读。Task7已补六轮表格排查和六个可直接上传CSV，独立复算通过，用户实际操作结果待填写；default回源503、9128代理默认身份边界保留 |
| platform-api / runtime-service | 现有交付、evaluation-target/v1、绑定及Worker回执接口足够，本轮未改产品代码。用户批准后将Platform预算一行revision0→2并原生签名同步，Runtime=2、synced_revision=2、last_error=null，空策略保持；新任务passed，1 Session/1 Run/1 Trace及目标一致，生产进程未变 |

实施准备及Task1–7工程交付done，唯一进度见项目tasks.md。合并版原资产/旧版、管理员200与后端匿名401、历史评分来源无重跑已验；新任务bbd5de5b passed，1 Session/1 Run/1 Trace、21 Span完整，ConversationalGEval=1.0。委托AI复核非独立人审，原12批及失败保留，不外推任意Agent。369份原证据归档，5011/9138与45011均已停，其他Worktree和Mac原有演示脚本保持。Task6仅正式EvalFlow重启，Agent三服务身份不变；server旧题／结果及开考弹窗已核对。Task7新增真实CSV上传、补传、口径变更、四文件产出和读回复核的六轮操作全文，V1/V2/V3材料独立复算通过；本轮未调用模型或代跑用户验收，见[逐步手册](projects/20261119-universal-agent-eval-authoring-governance/manual-acceptance.md)。9128既有Nginx无凭据注入默认身份，不能称公网匿名拒绝；default回源503，未改配置恢复。未重跑完整浏览器链、独立盲评或大规模压测，“历史单测倒灌”因果仍未核实。

2026-11-13 Git交付：用户追加授权将EvalFlow主环境适配及中文/品牌修复提交并推送远端；本仓同步对应的项目状态与验收文档，无Agent服务代码改动。生产部署未授权，A04沙箱准入阻塞保留；最终提交与远端状态以Git记录为准。

## 当前增补：AI网关预算治理独立Worktree（2026-11-18）

用户授权建立 `../ai-agent-platform-gateway-budget`、分支 `feat/gateway-budget-and-governance` 并完成前后端核心功能。环境 `wt_1c4f0f7fb905`，回环Web/API/Runtime端口24824/26911/24254，双库/Redis/Workspace独立。代码已合并至 main 分支，生产部署未执行。

| 服务 | 本Worktree当前状态（2026-11-18） |
|---|---|
| platform-api | 预算策略/权限/受信同步、429/503及幂等通知实现；专项30通过，真实认证可控HTTP与重启恢复通过。扩大回归1项HEAD既有投影失败保留 |
| runtime-service | 精确调用账本、回填/未知/恢复、逐调用guard、outbox及粘性Worker栅栏实现；真实PG专项34通过，重启/重建保留2.5USD。扩大回归1项HEAD既有Token失败及Resilience工具循环风险保留 |
| platform-web | 全栈能力已落地：聊天模块防爆与友好提示（5项单测全绿）、定点高精度计算 Composable（8项单测全绿）、三态进度条、作用域自适应弹窗及用量大盘 Tab 双向路由联动（3项单测全绿）；用量全量47项单测 100% 通过，vue-tsc 类型检查 0 错误，生产构建打包成功 |

项目仍partial：真实maomaoai请求403额度不足，真实主备/异步恢复组合、已确认阈值下完整性能、版本包全栈回退和人工联合Final待补。Worker栅栏覆盖整个Runtime执行域，空策略能力同步也会激活；关开关不能撤销，回退须保留保护或暂停执行域。当前任务、全部证据与运行边界见[项目入口](projects/20261118-gateway-budget-and-governance/README.md)。

## 当前增补：同一 EvalFlow 的前端 Agent 连接配置（2026-11-18）

用户已批准并实施前端Agent连接配置；[10专题](projects/20261113-agent-eval-production-flywheel/10-agent-connection-settings.md)现4done/1partial。原生管理员保存受信连接，各标签页按URL选择，登录/来源/签名/后台任务及私有资料按连接绑定；origin与项目保存后固定。default沿原目录和38375隧道，旧题库ID、版本与运行保留。SSO影子账号不自动取得EvalFlow全局管理员或原生实验权限。

Agent代码9a88b793、EvalFlow连接功能7b8d08d及目录修复c065db0已提交推送。服务器Agent已升级，3处原Runtime修复经AST确认主分支已包含、私有部署文件保留；API迁移至0014、Runtime应用至0011，引擎014与post48双包保持，升级前两业务库和配置已备份。服务器API119、Runtime57、EvalFlow扩大回归606项通过；原前端47项/类型构建证据保留，Agent生产构建再次通过并增量发布。四后台服务active/running、NRestarts=0，API与EvalFlow健康200。

default沿原38375隧道、server直连2142均接通：各自登录/转换/幂等/AI候选通过，独立确认的一题均发布运行passed，各1 Session/1 Run/1 Trace，目标一致；浏览器双标签隔离与旧资产读取已验。server首次题库目录错误已修、env属主造成的重启循环已恢复；default首次AI结构失败保留，明确口径新请求生成成功。新AI候选采纳到运行的完整链、普通成员双环境及真实故障组合未全验，10仍4done/1partial。未增加实例、重建隧道或删业务库，09/08结论保持。详见[26升级记录](projects/20261113-agent-eval-production-flywheel/implementation/26-connection-delivery-and-upgrade.md)。

## 已完成：评测独立部署与代码交付（2026-11-18）

用户已确认本需求完成并授权交付。[09专题](projects/20261113-agent-eval-production-flywheel/09-independent-deployment.md)5项done：目标快照/绑定运行API替代跨仓源码、.env及虚拟环境依赖；来源到期题库仍可读/编辑/发布/执行，继续取源及新运行分别检查当前权限。隔离跨机、双入口、撤权、漂移、幂等、审批恢复和停止已验；本轮main进一步完成真实浏览器业务主线，不等同生产全面验收。

Agent代码`9972a0b5`与远端EvalFlow代码`9fd76d4`已合各自main并推送origin；Worktree分支先独立推远端再合并。主分支既有聊天、IAM、用量看板及远端多Worker登录等功能保留，没有目录覆盖。合并回归：远端548、Runtime34、前端9套47及类型检查通过；API173通过/3跳过/84子断言，原HEAD同样失败的1项ACL断言保留。详见[23交付与清理](projects/20261113-agent-eval-production-flywheel/implementation/23-delivery-and-cleanup.md)。

本次隔离服务、两条专属SSH转发、两个Worktree及登记均已回收；Agent专属2个PG库/角色、Redis/Workspace和EvalFlow2个SQLite库已删除，主业务数据和原38375回调转发保留。原26007/24138/24493/25217/5011及65156/46187地址已停用。日志转存两端主目录私有`.local-stack/deliveries/20261118-eval-independent/`，不保留测试数据库副本。

本轮main已删除EvalFlow私有配置旧agent_repo，核对回调并在无活动任务后重载Runtime API/Worker和远端mlflow-eval。browser-skill完成正常聊天、双入口、分页100→110/筛选后103、双会话批量、普通成员交付/管理者授权、AI修订/采纳/手改/刷新、发布、显式两轮运行及同证据重评；1 Session/2 Run/2 Trace与目标一致，8项HTTP正负例通过。101条空分页夹具已回收，浏览器scope已关闭，服务健康并保留运行。08为6done/1partial，仅V8.7隔离全栈回退与再升级未验。

首次发布因集中实验缺失失败，按原生接口创建配置指定实验16并仅关联本轮数据集后原操作恢复。远端3行修复清除恢复后的旧background_error，39项相关回归通过，新增行Ruff无诊断/guard通过；修复、测试与初始化/恢复经验已提交并推送EvalFlow main（e7ff155），Mac镜像已pull同步。本轮未改Agent产品代码或构建前端。到期/撤权/审批/停止/漂移沿用09隔离证据；全量比较/诊断UI、生产HTTPS、容量/独立盲评未重验。详见[24主环境证据](projects/20261113-agent-eval-production-flywheel/implementation/24-main-environment-acceptance.md)。

## 08现场历史：Agent评测入口清理与远端联调（2026-11-18，后续代码已合main）

[08唯一任务进度](projects/20261113-agent-eval-production-flywheel/08-agent-evaluation-entry-cleanup.md)现为6项done/1项partial；以下保留早期现场事实。Agent仅保留当前/历史会话转评测集及历史批量转换；12个旧前端文件、旧公开写入口、旧Runtime评测助手及远端两处旧助手派发已清理。删除前旧项/旧图Run盘点为0；保留历史数据库、共享授权、来源ACL、签名、用途、脱敏、幂等、通知和执行维护。真实当前/历史/双会话批量交付、请求恢复和普通执行者权限通过；新通知仅表示“资料已送达”，不误报AI完成。真实出题、采纳/手改及独立发布成功；早期批量AI首稿结构失败保留，本轮新批量候选已成功。Web51、API188及末次60、Runtime91及目录15、远端585及末次22项分别通过，范围重叠不加总。

当前Agent3000/API2142/Runtime8123连接远端EvalFlow http://49.233.222.54:9128（内部5000），精确放行已获批origin与出口111.227.13.240；回调通过远端回环38375的SSH反向隧道接本机API。配置已备份，保留签名与实时权限；HTTP无TLS，依赖出口IP稳定、本机API和隧道在线。按批准补齐远端缺失依赖，原有包仅click8.5.0→8.3.3；新增一个仅属该项目的执行者测试账号，凭据只在本机私有文件。未删除业务数据、模型或迁移，未执行Git提交/推送，未改其他用户权限。

**08当时剩余与后续：** 当时远端运行因agent_repo为Mac路径、缺所属Runtime源码而被验真阻止，操作已cancelled，该轮没有成功评测Run。09已修复并隔离验证跨机运行、审批和到期题库，代码交付main；本轮main多页及运行已通过，仅全栈回退仍待原验收。用户重申题库独立、来源授权到期后仍可用；此前将早期到期封闭套用于题库并列为政策待决是判断错误。08仅API的回退/再升级及历史摘要一致不能替代全栈恢复。[早期阶段证据](projects/20261113-agent-eval-production-flywheel/implementation/21-agent-evaluation-entry-cleanup.md)。

## EvalFlow Copilot联调补丁（2026-11-17）

EvalFlow全链路专项在本仓仅追加通知同origin判定、旧评测工作项pending候选及EvalFlow审阅入口，获准成员capabilities返回authoring_url。相关API23/通知8项、类型与指定文件lint/ruff通过；本仓其他既有改动不属于该专项。真实浏览器已完成会话出题、咨询/局部修改、差异/部分采纳、手改/旧基线保护、刷新/取消、发布运行及结果回归主线；03只采纳新增题为v5、单独发布题库v2，最新运行37f9052e-4d2c-48d4-bfae-40c0272525e4为passed，Session/2Run/2Trace与代码评分已核对。旧01格式failed、模型503和首个03的Runtime包指纹error保留；确认本地无未结Run后，仅用既有脚本重载本地Runtime API/Worker，未改被测Agent配置、模型或标准。临时推理资源只接入本地EvalFlow私有0600且Git忽略文件，Key未入源码/证据。12项本地done，生产发布未授权，整体partial；双账号/断网/20题模型容量等边界未实测。dsfe浏览器工具会话已关闭，主服务保留；没有提交、推送或生产部署。详见相邻EvalFlow仓docs/projects/20261117-evaluation-copilot-full-lifecycle/README.md及implementation/87-browser-local-closeout.md。

## 当前批准范围与完成状态（2026-11-16）

**追加主环境配置（07 Task 7.5）：done。** 三个私有.env已补齐逐项中文注释并重启；平台工作台、原生页面登录、默认拒绝及授权批次隔离完成，普通原生账号信息仅在EvalFlow私有.local-stack/local-accounts.txt。15项登录/权限HTTP检查及browser-skill建题、真实AI生成和发布通过。用户明确批准sshmy2沙箱19111端口和当前caller放行111.227.13.0/24；核对空闲、备份并只重启Node后，mTLS readiness通过，错误Token仍拒绝。新任务62ebfb9e-4722-4226-941d-51eb81406f7e最终passed，1/1题、5项评分通过，Session/1Run/1Trace收集完整、裁判过程可见。旧失败保留，未改执行后端、部署代码或重跑旧A04完整评测；主服务3000/2142/8123、9128/5001保持运行。详见项目implementation/20-main-environment-configuration.md。

**用户已确认验收通过；代码交付和测试资源清理完成。** 06共16/16、07共4/4 done；原01–04为22 done / 3 deferred，05的旧流程由06承接。需求与进度以Agent主工作区`docs/projects/20261113-agent-eval-production-flywheel/README.md`及各专题为准。

- 两个`feat/agent-eval-production-flywheel`分支已提交推送；Agent合并`ccbf7111`、EvalFlow合并`3ab1ae8cd`已推送origin/main。原GenAI导航及指南先独立提交保存；主工作区旧后端补丁留在桌面交付记录，用户已批准采用已验收的严格鉴权和真实错误响应。
- Agent前端29、API115、Runtime97通过；EvalFlow前端190、后端487通过；两端类型与最终构建通过。主环境Python3.11补齐锁定Flask-WTF/WTForms；完整锁安装需要Python3.12+，未升级主环境Python。Node24未复验。
- Agent平台提供获准Session/环境并执行被测Agent；EvalFlow负责AI出题、题库/版本管理、运行、完整Session/Trace和裁判诊断。正式评测集菜单与页面登录已完成；平台账号与原生MLflow账号仍独立，既有权限不变，原生登录会话仅适用于单worker。
- 344c两个Worktree、Git与资源登记已删除；所属6个端口释放。2个专属PostgreSQL库/角色、EvalFlow内部30个SQLite及备份/恢复副本已删除。主环境和其他项目数据库未清理；不再从旧9138/28808链接验收。
- 桌面`评测演示/打开演示.html`保留原业务录像与07操作录像、可放大截图；`交付记录-20261116/`保存合并复验日志、旧后端补丁和清理核对结果。测试数据库不另备份。正式样本历史事实保留在项目文档，不能把录像中的本地链接当作仍在线。
- 真实四轮退款题首轮提前计算及AI裁判局限仍保留；用户功能验收通过不等于Agent每题全对，也不等于独立盲测结论。正式性能、真实CI、独立盲测、缺网关说明的真实自动抽样、自动停止循环、Grafana/通知和生产仍按原决定暂缓；本轮未生产部署。

详细交付、失败过程与证据见Agent项目`implementation/19-accepted-merge-and-cleanup.md`。新测试需重新建立隔离环境和资料；主环境现有配置/任务仍在其原`.local-stack/`，没有复制测试数据进入主环境。

## 评测集与具名配置扩展

2026-11-13：D01–D06本地done。专用执行项目、集中MLflow实验、原生版本化评测集与任务绑定已实现；同一dearflow_agent的温度0/0.3具名配置真实比较通过。64项后端、25项前端及4次真实模型运行8个用例通过，构建通过（关闭既有全局ESLint插件）；详见Agent仓项目verification.md扩展Final及EvalFlow implementation/27-dataset-profiles.md。已合入main；两个feature分支已推送。主仓复验后端64/前端39项、主/shared类型检查与Ruff通过；两个Worktree、专属PG库/角色和EvalFlow SQLite已清理，7个端口释放，其他数据库/Worktree未变。生产未部署。新增配置身份/审批恢复/题库冻结经验已确认沉淀至EvalFlow经验库。

## 最近改动

2026-11-25 | **平台助手 MLflow 运行诊断双通支持、Checkpoint 分页匹配与 Worker 诊断日志修复（本地已完成，未部署生产）**：`runtime-service` 在开启 `TRACING_PROVIDER=mlflow` 时实现启动前事件缓冲补挂与全量结构化诊断事件 SpanEvent 写入（`run_inline=True` 消除异步回调竞态），并在 `query_run_diagnostics` 适配按 `project-{project_id}`/默认实验检索 MLflow Trace 投影（历史旧 Trace 诚实降级为 `partial`，新 Run 返回完整 `available`）；为 `log_diagnostic` 补齐无 root handler 下的独立 `INFO` 流输出，并为 `log_context_metric` 与模型剖面注入受控标量关联字段。`platform-api` 将 `read_checkpoint` 从单一 `limit=1` 升级为首页 `limit=1` 快速探测 + `before` 游标分页扫寻目标 `run_id`，消除多轮会话查早期轮次的 `run_mismatch` 误报。Runtime 137 passed、API 122 passed（含 6 子测试）及跨进程 HTTP + JWT HMAC + SQLite MLflow + 日志过滤端到端验证通过。

## 近期评测基础

2026-11-13 | **Agent 自动化评测首期交付**：EvalFlow 扩展完成历史评分/主动回归、20题、真实模型基线、门禁与Badcase审核；三次开发集运行保留 KnowledgeRetention 分歧，holdout曾用于裁判诊断。真实CI、生产发布和全新盲测集后置，详见项目 Final 记录。

## 本月归并

2026-11-25 | 平台助手上线 `sshmy1`（Loki/非HTTPS复制/Thread检索与摘要），并完成跨服务联调验证。
2026-11-18 | 完成 AI 网关使用看板（Vue 3+ECharts）重构及 EvalFlow 独立部署与连接配置合入推送。
2026-11-17 | 完成跨项目排障、转评测集异步闭环与密钥脱敏误判治理，消除弹窗超时与 403 阻断。
2026-11-16 | 平台助手全栈验收交付，主环境评测配置与沙箱准入恢复并跑通。
2026-11-16 | 评测飞轮验收交付完成，双仓已推送，344c资源回收；原暂缓与生产范围不变。

2026-11-10 | 纯白系统架构拓扑交互图交付，README 彻底清理历史脱节残留并对齐生产现状。

2026-11-09 | MLflow / EvalFlow 原生链路追踪与会话评测适配全栈上线与生产发布。
2026-11-08 | 工作区总览、项目详情与成员管理工业级重构与信息密度治理全栈交付。
2026-11-08 | 知识库文档列表 502 校验死锁根治、前端文档状态动态呈现与全域模型计价补齐回填工程。
2026-11-07 | 历史会话侧边栏三段式工业级重构、会话批量删除与顶栏 Tooltip 交互优化；产物下载拦截与空闲会话断流误报防范。
2026-11-06 | 会话删除前置条件死锁与前端列表回显缺陷根治闭环：终态报错任务放行解除死锁，乐观注销杜绝幽灵会话。

2026-10 | 会话保留收尾；委派简化验收合并与隔离资源清理；运行重投、工具输出和代码剖析预算治理

2026-10-27 | **Markdown 渲染器放行 blob: 安全协议白名单与图表紧凑卡片排版治理**：彻底根治用户在产物库中预览深度调研报告时，由于 `markdown.ts` 中 `sanitizeUrl` 协议白名单过严导致 `WorkspacePreview.vue` 转换的 `blob:http://...` 动态 Object URL 被暴力清洗重写为 `#`（`<img src="#">` 表现为全屏破图图标）的致命缺陷；同时重构 Markdown 图像展示规范，彻底消除 2280px 超采样图表无约束膨胀导致的“广告牌”视觉灾难，建立 680px 宽度/460px 高度上限、居中对齐、微圆角轻阴影卡片边框与深浅模式自适应标准。Vitest 单测 6/6 全绿，vue-tsc 0 报错，Playwright 真实浏览器端到端高清截图验证通过。
2026-10-27 | **智能体联网调研预算约束（Research Budget）与边际收敛刹车治理**：彻底根治深度调研场景下由于技能煽动无限递归搜索导致单会话调用 250+ 次工具、耗时 34 分钟超时死循环的过犹不及缺陷。重构 `deep-research` 技能与全局系统提示词，确立严格调研预算（常规 3~5 次搜索、2~4 篇精读全文）、边际效用递减（前 3~5 轮已覆盖 80% 核心事实）及摘要优先评估原则，彻底废除顺藤摸瓜无限追溯与全量全文泛览反模式。全量 30 项技能单测全部跑绿。
2026-10-27 | **前端历史会话回放防误触（Replay Immunity）与上下文整理状态机收敛**：彻底根治用户打开已结束历史会话时，底层 SSE 协议万帧历史事件全量回放（Replay）导致前端盲目展示“正在整理上下文...”甚至永久悬挂的问题。建立终态与活跃 Run 严格双重校验机制，并在会话验证收尾与取消确认时强制复位过渡态，确保静态历史会话展现干净稳定。单测 51/51 项、TypeScript 类型检查及 Playwright 双会话端到端真实验证全部 100% 绿灯。
2026-10-27 | **会话取消（Stop）后乐观消息幽灵消除、时序防倒挂与 Loading 精准挂载治理**：彻底根除用户在发送消息并点击取消后再次提问导致的界面错乱（旧消息倒挂到末尾、被取消回合盲目渲染“Agent 正在组织答复...”）；修复 `message-alignment.ts` 中首轮空会话 baseline=0 时乐观消息被误追加在流式输出后的倒挂 Bug；加固 `ChatMessageList.vue` 的 `showPendingPlaceholder` 严禁在中断/已停止态渲染；在 `ChatSession.vue` 的取消、重连与新发送流程中彻底重置乐观消息与历史错误横幅。单测与类型检查全部 100% 绿灯。
2026-10-27 | **智能体上下文窗口治理与 Token 预算韧性优化全栈闭环**：彻底终结智能体运行中频繁触发整理上下文微胶囊、残暴 10% 裁剪导致记忆断层并陷入“失忆重读文件再次撑爆”死循环、以及单次运行耗尽 100 万 Token 抛错红条猝死的问题；实现四层防御：1) 上下文保留策略由 10% 提升为复合保留 $\ge 40\%$ 输入预算或最近 16 条完整消息；2) 在 `ResultFilesystemMiddleware` 实现 Head+Tail 物理截断（首尾各 50 行），根治 `read_file`/`grep` 瞬爆上下文；3) 改造 `TokenBudgetMiddleware` 实现 `exit_behavior="end"` 优雅停机，耗尽时清空后续 tool_calls 并温和收尾，绝不崩溃；4) 批量校准数据库存量模型窗口（`deepseek-v4.1-flash` 由 64K/32K 校准为官方真实 128K 131,072，`step-5-preview` 同步校准为 128K），配齐触发水位与保留环境变量；全量核心单测全部绿灯。
2026-10-27 | **DeerFlow Skills 全量迁移对齐、触发验证与缺陷治理工程**：系统性梳理参考项目 deer-flow 23 项 Skills 与本平台 20 项 Skills 的迁移对齐度；建立全景清单与触发指南；4 个 Phase（学术文献、数据图表、前端规范、多模态元技能）全量真实实测与测试套件 100% 跑通；彻底根治 GITHUB_TOKEN 403 限流、Docker RPC 元组退化、多处硬编码 trust_env=False 导致本地代理被屏蔽、_evidence 空指针防护、以及 skill_catalog 遗漏官方推荐等关键缺陷；明确收口音视频未开放边界；39 项单测全部通过。
2026-10-26 | **全域架构文档全景同步与技术资产演进工程**：系统性抹平 10 月份 52 项已交付成果与 `docs/architecture/` 之间的 8 大技术断层；升级宏观拓扑图与选型原则，扩充通信大动脉为 6 条干线（新增知识中台单向通道与双轨监控抓取通道）；全面重构可观测性文档（落实 W3C traceparent 与 Loki TSDB 毫秒日志穿透）；新增原生知识中台与单向免隧道自治架构规范；全面重写 DearFlow 记忆系统（异步解耦、双池 MMR 重排与软淘汰）；新增 Token 看板百万聚合读模型专篇与 186MB 轻量可观测、异步记忆 MMR、弹性 MCP 容错三大硬核 concepts 专篇；新增 4 篇端到端场景时序（Plan Mode、Trace-to-Logs 穿透、知识检索、模型容灾）；刷新全局 README 知识地图，自动化相对链接 100% 绿灯校验。
2026-10-23 | **工业级链路可视化升级与 Langfuse 多租户精准路由闭环**：彻底解决 Langfuse 404 跨租户路由报错，实现基于项目级精准搜索与 filter 参数的三级自适应 URL 构造器（全面支持 `VITE_LANGFUSE_PROJECT_ID` 等环境变量配置）；阻断平台代理查询 Loki 自身的自回声日志污染；重构工业级排障大屏（四联指标概览卡片、耗时瀑布流甘特条、毫秒级纯前端即时搜索与双视角 Tab 对比切换），适配平台标准深浅色主题；全量单测、TypeScript 0 错误、生产构建及 Playwright 自动化验证 100% 绿灯。
2026-10-22 | **分布式全链路追踪与日志关联可观测性工程全栈交付**：对标大厂分布式排障体验（字节诊断、阿里 ARMS），在 Platform API 与 Runtime Service 全面落实 W3C `traceparent`（`00-{trace_id}-{span_id}-01`）跨微服务协议透传与结构化日志 `service`、`trace_id`、`span_id` 打标；基于 Grafana Loki (TSDB) + Promtail 建立超轻量微服务日志中心；在生产主机 sshmy1 实装部署，Prometheus + Grafana + Loki + Promtail 四容器常驻总内存仅 **186.47 MiB**（CPU < 1%）；在前端实装可观测诊断中心与 Explore 联动，根据单一 `trace_id` 一键穿透展示跨服务毫秒级对齐日志流，并结合 Derived Fields 提供直达 Langfuse 链路树的高亮外链；全量测试与 TypeScript 检查 100% 绿灯。
2026-10-22 | **工业级可观测性与指标大盘全栈落地与前端方案 B 内嵌**：建立 Langfuse + Prometheus 双轨制架构；彻底重构 Platform API 内存锁计数器，引入标准 prometheus-client 并提供防内存泄漏的路径归一化；在 API (2142) 与 Runtime (8123) 暴露标准 /metrics 接口；生产主机 sshmy1 成功部署 Prometheus (19.59MB) 与 Grafana (50.5MB)，常驻内存总增量仅 70.09MB，双抓取 Targets 100% UP；实装前端方案 B 内嵌大盘（`ObservabilityDashboardPage.vue`，Kiosk 沉浸式无边框、深浅色主题双向联动、全屏与独立窗口跳转、系统探测快速直达），远端 Grafana 容器安全配置 `GF_SECURITY_ALLOW_EMBEDDING=true` 与免密只读已平滑热生效，前端全量 906 项单测及构建 100% 绿灯。

## 活跃项目

- [平台助手 MLflow 诊断、Checkpoint 分页匹配与日志链路修复](projects/20261125-platform-assistant-mlflow-diagnostics/README.md)：已完成（done，本地开发与跨服务联调验收范围）；Task 1–5 均已通过（`runtime-service` 137 passed、`platform-api` 122 passed / 6 subtests passed、真实跨进程 HTTP + JWT HMAC + SQLite MLflow + 多轮 history + 日志脱敏过滤端到端验证通过），未部署生产。
- [平台助手按 Thread 检索运行与脱敏活动摘要](projects/20261125-platform-assistant-thread-lookup/README.md)：已完成（done，已部署 `sshmy1` 并实测 `70f0ab34` 返回 200）。
- [DearFlow Agent 前缀缓存实验与动态上下文评估](projects/20261123-dearflow-prompt-cache-governance/README.md)：已完成（done，当前批准的本地范围）；Task 0–10已结束，用户已确认实验与文章、批准经验沉淀/合并/清理。产品提交41c8d500已合本地main，188项回归通过；原97次Xiaok、16次官方及新增23次多轮脱敏证据和失败保持，B八轮诊断全量/后续读取87.93%/96.24%，完整八轮同质量A/B收益仍未知，原首正文变慢反例保留。环境wt_9b100adcf0ef两个数据库/角色、私有请求/SSE、Workspace/Redis及登记已销毁，其他63库/20角色/4套环境和原17份公开证据哈希保持；清理后从main三份数据CLI及共同前四轮摘要复算一致，源码来源核对通过。两条Runtime经验已写入，私有完整请求不再保留；未推送、未部署。唯一进度见原项目tasks.md。
- [AI网关预算控制与财务熔断治理](projects/20261118-gateway-budget-and-governance/README.md)：`部分完成（partial）`；Task 1/2/4 完成（done），Task 3 核心链路接线与本地 HTTP/Worker、通知恢复已验，全链路 browser-skill 端到端验收通过；代码已合并进 main 分支，Task 5 待外部供应商配额补齐后完成人工整体验收。
- [AI 网关使用看板与综合可观测重构](projects/20261117-gateway-observability-usage/README.md)：`已完成（done）`（2026-11-18 全栈实施与验证完成，5 项任务 100% 验收通过）；对标 mlflow-eval-platform 重构网关黄金三要素（吞吐、延迟分布、错误率）、单请求 Token 均值与 Prompt Cache 效能，落地图表到 Logs 毫秒级下钻穿透。

- [会话转评测集后台异步任务与通知闭环](projects/20261117-evaluation-materials-async-task/README.md)：`done`（2026-11-17 全栈闭环与端到端验证通过）；将大体量业务会话转评测集的同步阻塞请求重构为基于 BackgroundTasks 的异步任务，弹窗秒级关闭 + 全局 Toast 提示，完成后通过平台通知中心（🔔）推送直达链接，彻底根治前端 30 秒超时与弹窗卡死问题。

- [平台内置助手](projects/20261116-platform-assistant/README.md)：T01–T25批准开发与本地技术验收`done`。原指南/连续浏览器链保持原范围；追加Run绑定持久失败、缺Trace时可信执行请求/Run日志关联、每轮可读资料摘要与误判回归。最终相关API96、Runtime24、证据抽屉5项及类型/指定静态检查通过；真实模型四轮/11个工具结果经答案复核。原旧Run只读定位技能准备失败，根因仍未知，固定旧日志为empty。主环境无未结Run后已重载Runtime API/Worker，API自动重载且未迁移；未改模型凭据或业务库。原API既有ACL断言失败保留；当前追踪未配置、历史采集未知，生产Loki/容量及本轮新增状态真实浏览器复验未覆盖，没有本轮Git交付或生产部署。详见项目tasks/verification及implementation/04。

- [Agent生产评测飞轮](projects/20261113-agent-eval-production-flywheel/README.md)：10连接配置4done/1partial，两仓代码已推送、相关服务已升级；双环境会话转换/AI候选及独立题库真实运行分段通过，双标签/旧资产已验，新候选完整链与故障组合待补。09交付5done，08为6done/1partial、V8.7全栈回退仍未验。原隔离资源已回收，主服务与隧道保留。
- [Agent 自动化评测体系](projects/20261112-agent-evaluation-system/README.md)：done，已合main并清理测试Worktree/专属数据库；EvalFlow执行器、20题、真实基线、门禁、Badcase审核与页面验证通过。Agent仍有KnowledgeRetention质量失败；真实CI、生产发布、新盲测集后置。
- [MLflow 链路追踪与会话评测适配](projects/20261108-mlflow-tracing-adaptation/README.md)：`done`；全栈完成 MLflow / EvalFlow 平台平滑接入，支持动态环境变量热切换（langfuse/mlflow/both/none）。落地三大场景：1) 前端安全防御守护（none 模式下追踪 UI 彻底消失零报错）；2) Project 维度项目物理隔离（动态自动创建 `project-{project_id}` 独立实验）；3) 超级链接原生直达线程 ID（直接进入 `#/experiments/{id}/chat-sessions/{sessionId}` 全景对话卡片）。单测 153 项全绿、Vue-tsc 0 报错、browser-skill 真实浏览器端到端实测验证通过。
- [Runtime Agent 开发指南与入口纠偏](projects/20261108-runtime-development-harness-governance/README.md)：done（文档范围，2026-11-08 用户人工验收通过）；52 篇全文审查完成，经验已沉淀；文档提交 5ea9ea8c、整合提交 2b434585 已推送并合入 main，主干原有功能保留，f335 Worktree 已清理，无所属服务/测试数据库。CI 不在本期，产品测试未重跑。
- [工作区总览工业级重构与信息密度治理](projects/20261108-workspace-overview-refactor/README.md)：`done`；针对工作区总览废话文案、空洞留白与狗皮膏药治理入口立项工业级重构全栈交付，4 联指标看板、紧凑 Header、主辅双栏高能工作流已落地，单测全绿。
- [会话快照水合与媒体外置治理](projects/20261107-session-hydration-and-artifact-offloading/README.md)：`partial`；仅覆盖新会话及其刷新/重连，不做存量或旧逻辑兼容；Runtime 图片引用化、模型临时展开、Web 首屏快照优先和按需预览已完成。真实 xiaok DeepSeek + Playwright Chromium 通过；GraphHarbor 保持通用边界且未修改。30 样本性能、远端 Workspace 和完整竞态/故障注入待补。
- [前端 Markdown 产物链接拦截下载与空闲会话长连接断开误报治理](projects/20261106-chat-artifact-download-and-stream-resilience/README.md)：`done`（已全量通过代码审查、单元测试、构建与部署）；针对 Agent 生成产物链接被 Markdown 误洗为 `#` 导致新开空白标签页、以及会话池切换切回已完成会话时空闲 SSE 流重连被拒导致 `Event stream closed.` 误报两大缺陷立项治理。
- [智能体会话与运行时数据生命周期治理](projects/20261030-session-and-runtime-retention-governance/README.md)：`done`（8/8任务、8条Phase与Final核验通过）；30天闲置/查看发送续期、正式post48通用TTL、Workspace随会话回收、关联事实分级保留及有界维护均已实现；提交`5635e621`已推送并快进合并`main`，专属服务和测试资源已清理，生产服务未部署。systemd仅静态核验，远端失联为受控fixture。
- [有界调研委派与子智能体上下文隔离](projects/20261028-subagent-fanout-and-prefix-caching/README.md)：`done`，2026-10-30用户人工验收通过；功能分支已推送并快进合并main，服务停止、所属Worktree/测试库已清理。收尾记录随main推送，历史失败与质量/费用局限保留；未部署共享服务。
- [修复运行异常重投与 Agent 代码剖析死循环收敛治理](projects/20261028-run-resubmission-and-agent-convergence/README.md)：`done`；彻底修复前端在回合失败时私自调用 submitQueuedMessage 自动重投 Prompt 的 Bug；在 SYSTEM_PROMPT 确立代码库/本地架构剖析自顶向下原则、单轮 5~8 次探索硬约束、禁止遍历脚本正则扫描；将 ExecutionBudgetMiddleware 预警阈值提升至 warning_calls=5 并强化中文化最高优先级收尾指令；前端 58 项单测、后端 76 项测试全绿。
- [智能体上下文防爆治理与工业级工具截断/子任务架构升级](projects/20261028-context-governance-and-tool-resilience/README.md)：`done`；对标 Antigravity / Cursor / Manus 工业级架构，从源头解决灵巧手调研与全库代码剖析等重度长任务中工具无脑倾倒巨量输出（单次 188KB/6.4万 Token）、单上下文硬抗 60+ 次工具调用导致的上下文反复爆炸与 6 次恶性循环压缩问题。实装溢出落盘（Spill-to-Disk）与历史工具视口虚拟折叠（Ephemeral Pruning），生产真实大长会话回放 Token 暴降 58% ~ 82%，压缩触发归零，300 项中间件单测 100% 绿灯。
- [智能体上下文窗口治理与 Token 预算韧性优化](projects/20261027-agent-context-budget-hardening/README.md)：`done`；彻底解决频繁触发整理上下文、10% 残暴裁剪引发失忆死循环、以及单次运行耗尽 100 万 Token 抛错红条猝死缺陷；四层防御（40% 复合保留、Head+Tail 工具防爆截断、Token 耗尽优雅停机、存量模型校准为官方真实 128K 窗口）全栈落地闭环，测试全绿。
- [DeerFlow Skills 全量迁移对齐、触发验证与缺陷治理工程](projects/20261027-deerflow-skills-audit-and-verification/README.md)：`done`；系统性梳理参考项目 deer-flow 23 项 Skills 与本平台 20 项 Skills 的迁移对齐度，建立全景对照与触发指南，分 4 个 Phase 逐类验证并修复潜在执行缺陷。全部实测跑通，测试全绿。
- [GitHub 调研工具与远程沙箱证据元组契约韧性治理](projects/20261026-github-tool-and-remote-evidence-resilience/README.md)：`done`；针对 GitHub 匿名调用 403 限流击穿引入 GITHUB_TOKEN 鉴权支持（借鉴 deer-flow），实测限流额度提升至 5000/hr；同时彻底修复 Remote Sandbox RPC 证据回传将元组退化为 List 导致 LangChain 强校验失败抛出 `runtime.execution_failed` 的致命缺陷。53 项单测全绿。
- [全域架构文档全景同步与技术资产演进工程](projects/20261025-architecture-docs-synchronization/README.md)：`done`；系统性抹平 10 月份 52 项已交付成果与 `docs/architecture/` 之间的 8 大技术断层，4 个 Phase 全部交付闭环并通过六维合规验证，0 坏链。
- [分布式全链路追踪与日志关联可观测性工程](projects/20261022-trace-to-logs-distributed-observability/README.md)：`done`；对标大厂分布式排障体验，基于 W3C traceparent 协议 + Grafana Loki/Promtail 超轻量日志中心（实测四容器常驻总内存仅 186.47MB），实现根据单一 trace_id 在一屏内同时展现微服务调用拓扑瀑布图与各服务毫秒级对齐的详细上下文日志，前端一键穿透与 Derived Fields 跳转全面实装，生产主机 sshmy1 验证通过。
- [工业级可观测性与指标大盘架构工程](projects/20261022-industrial-observability-architecture/README.md)：`done`；建立 Langfuse + Prometheus 双轨制工业级可观测体系，彻底淘汰内存锁计数器，向外暴露标准 `/metrics` 接口，生产主机 `sshmy1` 实装 Prometheus + Grafana 双容器（总内存常驻仅 70.09MB，双 Targets 100% UP），实装方案 B 前端无缝内嵌工业指标大盘（Kiosk 沉浸、深浅主题联动、全屏与全量 906 单测全绿）。
- [LightRAG MCP 知识库真实文档状态与图谱资产对齐](projects/20261021-lightrag-mcp-real-doc-status-alignment/README.md)：`done`；彻底消除假数据与跨租户内存串台，13 份多模态文档与真实状态完全透出，项目名称一一对齐，远端已部署，Playwright 真实模型测试通过。
- [LightRAG 工业级知识中台全量能力复刻与无缝集成](projects/20261019-full-lightrag-studio-integration/README.md)：`done`；彻底根治登录框弹窗，完整复刻 Graph Studio 2.0、Chat Studio 与 Knowledge Hub 三大工业级能力，测试与构建 100% 绿灯。
- [知识中台原生化重构 - 路线 C](projects/20261019-native-knowledge-studio/README.md)：`done`；彻底移除详情页冗余面板，废除 iframe 外挂，实装原生智能问答与 Canvas 力导向图谱工坊，测试与构建 100% 绿灯。
- [项目详情与知识中台交互收敛](projects/20261019-project-detail-knowledge-streamline/README.md)：`done`；项目详情页彻底纯净化，专注于基础信息与成员管理，测试构建全绿。
- [前端可观测性与端到端排障链路增强](projects/20261019-frontend-observability-and-diagnostic-tracing/README.md)：`done`；有界内存错误缓冲区 (Cap=10)、全局 ErrorBoundary 拒绝白屏、Axios/SSE 全链路 Request ID 对齐、DiagnosticDetailModal 就地排障模态窗、open-swe 风格 Actionable 建议字典与后端分类器、Langfuse 分布式链路追踪（Open Trace 直达外链）、轨迹错误节点兜底注入全栈落地并通过 Playwright 自动化 E2E 验收（4 张实景截图固化）。
- [Native Systemd 生产级架构加固与运维治理](projects/20261016-native-systemd-production-hardening/README.md)：`done`；非 root 专用受限账号 aiplatform 与内核级沙箱落地、Platform API 2 Worker 并发与 2G 内存熔断、Nginx 生产安全头与 600s 流式反代超时调优、PostgreSQL 每日凌晨自动 gzip 压缩轮转备份（留存 7 天）与 Journald 2G 封顶全部闭环并通过生产实测（HTTPS 证书依用户确认 deferred 暂缓）。
- [记忆系统架构升级 (Agent Memory System Upgrade)](projects/20261015-agent-memory-system-upgrade/README.md)：`done`；吸收 DeerFlow 记忆系统核心工程与算法优势，实现异步后台提取解耦（主请求耗时降至 < 5ms）、Prescreen 成本门禁、中文混合分词+IDF+双池 MMR 多样性检索、近重复合并与平滑淘汰；保留权威 PostgreSQL 存储、CAS 乐观锁与人工审核制；跨服务契约（Runtime stats 透传、API 校验、Web 健康进度条）全栈交付；Runtime 33 项单测、API 契约测试、Web 5 项单测及 vue-tsc 类型检查全部 100% 通过。
- [弹性 MCP 工具装配与运行时解耦保护](projects/20261015-resilient-mcp-loading/README.md)：`done`；对标 OpenSWE 生产级容错机制进行去业务化移植，实现 MCP 服务与工具的装配期故障隔离（10s 超时控制与全局异常捕获降级）与运行期优雅降级，彻底废除“缺工具即自杀”的反模式强校验；单测套件 170 项全绿；Playwright + Chromium 真实大模型端到端自动化验收 100% 绿灯，彻底消灭 `runtime.execution_failed`。
- [Docker 对话级沙箱生命周期管理与原生流式传输改造](projects/20261015-docker-sandbox-lifecycle-and-streaming/README.md)：`done`；纯 Docker 低开销对话沙箱架构落地；彻底拔除 Base64 JSON 传输大文件与全内存缓冲反模式；实装前端路径锁、下载Toast、Smart Zip智能归档（ZIP_STORED）与独立流式连接池；远端云主机 sshmy2 完成生产部署与验证；打包 9.4MB 大文件耗时从 21.5s 压降至 0.36s（下降 98.3%）；Playwright + Chromium 自动化端到端测试 100% 绿灯。
- [知识库免隧道自治与单向架构治理](projects/20261014-knowledge-zero-tunnel-auth/README.md)：`done`；彻底移除 SSH 反向隧道，实装本地自治自验；远端收敛为纯单向入站服务（仅需 22/8000 端口）；Playwright + Chromium 自动化端到端测试 100% 绿灯。
- [Agent 显式挂载多 MCP 与极简治理](projects/20261014-agent-explicit-mcp-mounting/README.md)：`done`；基于 LangChain 官方 `MultiServerMCPClient` 原生多 Server 纳管能力，贯彻 KISS 极简原则；实现 Agent 维度的显式按需挂载与多 Server 隔离，杜绝全量工具混调导致的大模型幻觉与 Token 浪费。全量单测 100% 通过。
- [知识库动态多项目绑定与免重启鉴权](projects/20261014-dynamic-knowledge-binding/README.md)：`in_progress`（Phase 1、Phase 2 及远端 Phase 3.1 实施验证完毕，本地全栈已就绪）；彻底淘汰静态 .env 手工配置与服务重启，建立基于 Platform-API 数据库持久化、Scoped HMAC/JWT 动态凭据签发、以及 RAG 远端知识库无状态即时验签与物理隔离的多租户免重启生产架构。待 Web 端开启新对话进行端到端体验验收。
- [知识文档/图片平台接线](projects/20261013-knowledge-documents-platform/README.md)：`done`（2026-10-13 用户验收通过）；T01–T08全部完成；前端F01–F06与无mock浏览器闭环、8步Playwright自动化测试全绿、MCP防死循环优化落地；所属服务已停止。
- [项目成员知识上传平台接线](projects/20261012-project-member-knowledge-upload/README.md)：`done`；由20261013专项统一验收；RAG真实联合链、审批/排队/去重/回退均通过。
- [项目知识检索 MCP 接入](projects/20261011-project-knowledge-mcp/README.md)：`done`；通用MCP与别名工具目录接入完成，多模态/文本库隔离。
- [Runtime 单节点远端 Docker 沙箱](projects/20261012-runtime-remote-docker-sandbox/README.md)：done（2026-10-13 用户本期验收）；T00–T15 本期收口，B01/B02 解除；正式整机重启/后续独立 Final、真实编辑和留存夹具/interrupt 排查 [deferred](projects/20261012-runtime-remote-docker-sandbox/follow-ups.md)。五服务已停。
- [后台任务接受回执接入与联合收口](projects/20261011-background-acceptance-closeout/README.md)：`done`；全栈闭环完成，前端修补、Playwright 真实模型自动化测试与三视口全景留痕通过，用户人工验收通过，已合并入主干。
- [平台/项目Token看板](projects/20261011-token-usage-dashboard/README.md)：`done`；全栈端到端实现、B01容量优化、W01–W04前端交付、无头抽屉复用、布局防抖消除、503容量饱和适配全部完成；Playwright真实模型端到端自动化联合复验通过（24.1s，全套截图已留痕）；用户人工浏览器实测验收通过，本地服务已安全停止。
- [Agent 通用后台非阻塞任务能力](projects/20261009-agent-generic-production-capabilities/README.md)：`done`；接受回执接入与联合收口闭环，所有剩余门禁已回填并通过。新提交默认关闭，现役未部署。
- [F07 自动对话标题复用与补齐](projects/20261009-agent-thread-auto-title/README.md)：`done`；T01-T05 后端/Runtime/CAS、T06 前端接线、T07A 非前端验证、T07B 真实大模型 Playwright 联合闭环均已 100% 完成（首轮提炼“量子力学本质”+改名“老王科研保密项目”+二轮防竞态覆盖，全套 7 张实景截图落地）；用户实操人工验收通过，本地服务安全停止。
- [F05 Agent 模型上下文 PII 脱敏](projects/20261009-agent-pii-redaction/README.md)：`done`；全栈闭环完成，后端算法网关、前端错误消费草稿保留、Playwright 自动化测试闭环及全链路 E01-E03 验收 100% 通过。未部署现役。
- [F10 Agent通用文档读取能力补齐](projects/20261010-agent-document-reading/README.md)：`done`；全链路闭环，Runtime/API/Web 三服务全栈交付。同一 parse_document 补 DOCX/PPTX、定位/有界续读和 Docker reader，移除全 uploads 系统索引，FileRef/raw 接口保留。python-docx1.2.0 与专属镜像冻结；前端 MIME 纠正、原字节认证下载拦截、错误优先绝对高亮、DOCX 段落/表格与 PPTX 幻灯片语义化投影全部实装；Vitest 726 项全绿、vue-tsc 0 错误、ESLint 0 错误、生产构建成功；Playwright + Chromium 真实大模型（DeepSeek-V4-Flash）自动化端到端测试 3 项全绿，4 张全景截图已留痕。用户人工浏览器实测验收通过，本地专属服务已安全停止。未部署现役。
- [Agent 运行完成通知与失败回调](projects/20261009-agent-production-capability-extension/README.md)：`done`。GraphHarbor/Runtime/API非前端实现、post44发布和交接完成；正式最短通过，native定时/回填部分证据已固化；前端 P4.1-P4.3 全部交付并通过 Vitest 与真实模型 Playwright E2E 闭环验收。用户人工实测验收合格，安全合并入主干。
- [F11 通用输入润色](projects/20261010-agent-input-polish/README.md)：评估与规划完成，用户确认暂缓（`deferred`），P2 候选、功能未实施。suggestions 复用、无 Thread 用途授权与旁路成本方案保留，未来重新投入时需人工批准；同事前端交接未排期。
- [Agent 通用 Plan Mode 与计划审批治理](projects/20261008-agent-plan-mode-governance/README.md)：`done`；三服务（Runtime/API/Web）全链路实施与自动化验收全部完成。后端双重门禁、原生审批、快照幂等与安全脱敏闭环；前端开关/徽章、待审卡片、输入框锁定、XSS 防御与状态自愈实装；静态代码门禁全部通过；Playwright + Chromium 真实大模型（DeepSeek-V4-Flash）自动化端到端测试 100% 绿灯；7 张全景截图与 Thread/Run/interrupt 对账无误。未部署现役。
- [Worktree 本地栈资源隔离](projects/20261010-worktree-local-stack/README.md)：done；T01-T07全部验收，默认admin/admin123456、继承各app配置并自动对齐miaomiaoai deepseek-v4.1-flash默认模型策略，主库基础数据复用完成。源库只读，历史/令牌/定时任务排除；24项回归及真实三栈通过，资源回收；存量37条文档路径后置。
- [Agent Workspace 执行容错与安全失败报告](projects/20261007-agent-workspace-resilience/README.md)：`done`（非前端本地与 Docker 范围全部闭环，全栈代码与测试已合并进入主干；前端交接与报告已固化）；后端五精确安全码、结果未知停止、取消回收与诊断记录已融合闭环。未部署现役。
- [Agent通用运行取消与中断能力](projects/20261007-agent-run-cancellation/README.md)：`done`（全链路闭环）；后端三接口、持久Stop/恢复、inbox屏障与确定性报告完成；前端Stop控制器状态机、Banner、Drawer与真实模型Playwright E2E自动化闭环完成（F01–F10闭环，截图已留痕，用户实测验收合格）；B01解除；B02等待正式PyPI发布指令/正式源锁接入。
- [Agent 运行准备幂等与有界重试](projects/20261007-agent-production-capabilities/README.md)：done；公共 prepare latch、目录修复、有界重试与诊断接口已实现，前端双专职子组件实装，49 项单测与 Playwright + Chromium 全链路自动化 E2E 闭环全部通过。未部署现役。
- [Agent 通用 Token/Cost 跟踪与运行用量治理](projects/20261007-agent-usage-cost-governance/README.md)：done；Runtime + Platform API + Platform Web 全栈闭环，16 项隔离真实后端链路与包含真实大模型调用的 5 项 Playwright 自动化端到端测试全部通过，五重质量门禁全绿。未部署现役服务。
- [Agent 执行预算、步骤限制告警与软收尾](projects/20261007-agent-execution-budget/README.md)：done（全链路闭环）；Runtime 253 项回归、API 81 项回归与 23 场景真实 Worker 验证齐全；前端 F01-F04 实装并完成 116 套件 571 项单测、vue-tsc 0 错误、ESLint 0 错误。端到端自动化验收与人工实测完成。
- [Agent 运行生命周期超时治理](projects/20261006-agent-run-timeout-governance/README.md)：done；已完成正式post42接入、12组HTTP、匹配回退、前端T11超时治理与停止时序实装，以及T12用户真实浏览器端端到端联调验收（含排队死锁自愈）。本地服务已安全停止。
- [Agent 模型调用稳定性治理](projects/20261006-agent-model-resilience/README.md)：`done`；全链路闭环，Platform API、Runtime Service 与 Platform Web 全栈交付。后端模型恢复策略/受管备模型/分类重试/契约签名与网关快照、前端编辑页配置/真实失败态/推荐问题门禁/停止确认超时保护/备用模型微胶囊 Tag 全量实装；单测门禁全绿，故障注入主备降级实测通过，用户人工浏览器实测验收通过。
- [Agent 上下文窗口管理工程化](projects/20261006-agent-context-window-governance/README.md)：`done`；Platform API、Runtime Service 与 Platform Web 全栈交付闭环，模型容量配置/展示、整理状态微胶囊及平滑淡出、受控手动整理动作与全套单测/类型/构建门禁全绿，用户人工实测验收通过。
- [Agent 工具调用容错与生产接线补齐](projects/20261006-agent-tool-error-resilience/README.md)：done；全链路闭环，Runtime/API 共享选择性分类、主子图接线、安全消息与执行中缺根保护完成；Platform Web 纯函数摘要、微胶囊 Tag 徽章与格式化排版实装；核心单测全绿，浏览器联合验收 F01-F08 全部通过。未生产部署。
- [Agent 可观测性与追踪补齐](projects/20261006-agent-observability-hardening/README.md)：done（本地隔离环境全链路闭环）；Runtime/API 诊断与安全投影完成；Platform Web 独立解耦面板 RunDiagnostics、模式切换、防竞态 Composable 与全量门禁总检全绿（vue-tsc 0 errors、ESLint 0 errors、打包全绿、535 项单测全绿）。未部署现役服务。
- [Agent 回答后推荐问题](projects/20261005-agent-followup-suggestions/README.md)：done（本地全链路代码与门禁已完成）；Platform API + Runtime Service + Platform Web 全栈闭环，单测、静态类型、Lint 与生产构建全绿；真实三服务 E2E 与远端人工标准评审待具备环境后执行。
- [定时 Agent 任务](projects/20261005-scheduled-agent-tasks/README.md)：全链路 done；后端 CRUD/once/manual/预览/分页和执行前拒绝审计完成，发布包隔离链路通过；前端定时任务模块实装，对标 playbook 与 control-plane 规范，全仓 107 套件 481 单测、vue-tsc 与生产打包全绿。未部署现役或远端平台。
- [Chat 持久消息队列](projects/20261005-durable-chat-prompt-queue/README.md)：进行中，用户已批准治理方案；已核对 localStorage 消费根因、审批/FIFO/取消缺口，开始实施。现有平台修复已推送 `b85e00f`。
- [多会话流连接与运行缓存治理](projects/20261005-chat-stream-resource-governance/README.md)：done；多会话与真实撤权浏览器、最终构建验证通过；GraphHarbor post39 双包已发布，本地 Runtime 已升级重启；Redis 从峰值 18.01 GiB 降至约 0.57 GiB。
- [平台权限状态与刷新治理](projects/20261005-platform-access-refresh-governance/README.md)：本地 done；临时故障保留页面/登录，真实撤权仍生效；单测、故障注入与真实安全链路通过。未生产部署。
- [Chat 前端对话架构治理与 Clean Architecture 重构](projects/20261004-chat-frontend-clean-architecture-refactor/README.md)：done；对标谷歌范式完成 5 层解耦。剥离模型参数、视口跟随、分支动作与传输自愈；ChatSession 降至 1959 行，useChatSession 压降至 1198 行，消息流水线纯函数化；前端 429 项单测、vue-tsc 0 错误、生产构建全绿。
- [LangGraph v3 默认消费与 DeltaChannel 评估](projects/20261004-langgraph-v3-delta-evaluation/README.md)：已完成（done，原评估范围）；八类浏览器、API30项/2subtests、Spike/流夹具5项及前端typecheck/build补齐；原Defer历史与后续Adopt分开，生产未部署；节点 timeout/error_handler/RunControl 暂不实施。
- [Chat 会话状态机加固与流式体验优化](projects/20261004-chat-session-state-and-stream-hardening/README.md)：done；彻底解决切屏失焦权限刷新误踢、空队列误弹排队 0 黄条、中断等待澄清时底部悬挂正在处理矛盾提示、以及 DeepSeek 思维链首轮流式卡顿假死四大顽疾；前端 22 项单测全绿、静态类型检查与生产打包全绿。

## 历史飞轮 Worktree 服务状态（344c，已回收，非当前连接）

| 服务 | 最后更新 | 本轮能力与验证 |
|---|---|---|
| AI协作与文档 | 2026-11-15 | 06全部16项done，含业务会话直接转换；原25项22完成/3暂缓。手册主线、16图5视频齐备，用户验收表留空 |
| platform-api | 2026-11-16 | 原业务能力保留；主环境工作台/反馈及获准项目/模型、回源密钥与EvalFlow接收方已配置，重启后能力/登录/命令验证通过 |
| platform-web | 2026-11-15 | 当前/批量“转为评测集”、管理者用途确认与自动首版；组件2项及四轮真实会话浏览器链路通过 |
| runtime-service | 2026-11-16 | 主环境已启用获准评测执行证据及本机MLflow认证，API/Worker已重启；新自检一题真实运行通过，1Run/1Trace收集齐全；按批准恢复远端/24准入，未切换后端 |
| EvalFlow | 2026-11-16 | 原07四项已验收；追加7.5主配置done。9128/5001运行，新增本地登录/默认拒绝/批次隔离已获用户批准；建题、AI、发布及一题真实运行通过，结果/Session/Trace可查 |

原隔离端口：Agent Web28808/API25087/Runtime26645/Redis26450，EvalFlow Web9138/API5011，服务已停止、端口已释放，专属数据库及Worktree已回收。自动化浏览器自建会话已结束。05真实隔离恢复证据继续有效（67张PG表、9843文件、Redis10键、18个旧会话读取403）；未启动模型Worker的恢复服务已停止，不等于生产灾备。

## 当前各服务状态（主工作区）

| 服务 | 最后改动日期 | 关键约束/注意 |
|---|---|---|
| EvalFlow（关联仓库） | 2026-11-21 | 正式应用在sshmy2，后端开发在sshmy1独立Worktree，Mac负责前端重度构建；Agent/Runtime/PG/Redis及公网9128留sshmy1。Task23双机单并发容量与Task24规则同步已完成，当前Git e33b501；make deploy-status只读检查，旧发布脚本已退役。PID817813/NRestarts0保持，本轮未重载；HTTP、9128默认身份注入和default回源503边界保持。 |
| runtime-service | 2026-11-23 | DearFlow 临时日期/记忆及 DeepSeek system 序列化已合本地main（41c8d500），188项相关回归通过，用户确认的实验/文章/经验与测试环境清理已完成；原公开数据和负结果保持，完整八轮同质量A/B收益与实扣仍未知；清理后main离线复算及其他环境保护核对通过，未推送或部署（见[缓存项目](projects/20261123-dearflow-prompt-cache-governance/README.md)）。服务器已升级至 `9a88b793`；GraphHarbor post48 正式接管，014 Retention 与 Workspace 回收 Schema 迁移完成。生产服务运行正常，端口 8123 探针通过。2026-11-17平台助手：单create_agent/无执行沙箱，六篇当前指南及原持久历史/强制写审批保留；追加每轮可读资料刷新、失败阶段/未知根因与本轮引用规则。补强24项及真实模型四轮通过；最终提示/工具已在无未结Run后重载本地Runtime API/Worker，未改模型或生产。EvalFlow题库v2既有运行包指纹一致并passed的联调结论保留。 2026-11-18：08旧评测图、实现及专属注册已删除，执行证据与dearflow_agent维护权限保留。91项通过/1项Docker不可用跳过，追加目录基线15项通过；API/Worker已重载，目录5图/83工具，无旧助手；管理员浏览器及执行者HTTP合成聊天成功。  09独立目标声明/Worker绑定已交付main；先前main两轮运行2Run/2Trace及同证据重评证据保留。10升级：服务器API/Worker已重启、应用迁移0011，引擎014/post48保持；原3处outputs修复语义保留，57项回归及server真实评测通过。 |
| platform-api | 2026-11-18 | 升级知识库 DocumentId 正则放宽与多状态 Schema；补齐全量模型定价与历史 151 条调用快照重算；端口 2142 探针全量通过。2026-11-17平台助手：原只读SQL/指南/当前目标ACL/查询审计保留；新增Run绑定checkpoint安全摘要、Trace/执行请求/Run受控日志关联及可读能力说明。最终相关96项通过；本地固定三个日志源已接入，旧Run状态连续读回准确、对应旧窗口日志0条如实标empty。8秒状态查询上限低于工具15秒；API自动重载、未迁移，原扩大回归1项既有ACL断言失败保留，生产权限未改。 2026-11-18：08旧公开入口及桥接已裁剪，保留EvalFlow身份、签名、来源、用途及执行维护；准确远端origin和禁止重定向已覆盖，通知改为资料送达。188项及末次60项通过，已重载；真实执行者交付/权限、管理员授撤权及幂等通过，08当时远端运行受源码验真阻塞；09已补跨机实现。  09目标API及可信绑定已交付main，保留已有IAM/用量/助手；本轮main转换202、原请求恢复及8项权限/退役HTTP核对通过，健康200且database_ready=true。 10连接升级：服务器已部署9a88b793、API迁移0014，全评测119项通过；server连接直连本机2142，转换/幂等/真实执行已验，default隧道与旧资产保留，完整故障组合未验。 |
| platform-web | 2026-11-18 | 知识库文档列表动态状态徽章呈现与接口类型契约对齐；生产产物已更新部署至 `/www/wwwroot/agent-platform`，Nginx 端口 80 访问与线上探针全量正常。2026-11-17平台助手：原全局抽屉/错误现场/指南/项目竞态及403缓存修复保留；追加持久失败阶段、审批摘要、日志来源/关联与空/不可用状态，相关抽屉5项及vue-tsc/Prettier通过。原68项及连续浏览器链保持原范围，本轮新增状态未真实浏览器复验；Vite主服务未重启，助手未生产发布。 2026-11-18：08旧工作台/回答反馈/巡检入口已删除，旧URL为受控迁移页；保留当前/历史/批量转换、能力与执行权限，移除好差评筛选。9套51项、正常构建及增量ESLint通过；本轮main真实聊天、双入口、分页100→110/筛选103、双会话批量与通知、成员交付/管理者授权及旧URL迁移已验。09交付未改Agent前端；10连接交付后在Mac按服务器公开配置重新构建，增量部署80入口，浏览器原工作区/旧会话/导航读取通过。08仅剩隔离全栈回退与再升级。 |
| AI Harness（AGENTS.md + Skills + 文档） | 2026-11-13 | Agent生产评测飞轮本轮批准范围已在双Worktree完成，22 done / 3 deferred，联合Final通过；未提交、合并或生产部署，主工作区服务未变更。Agent 自动化评测首期与D01–D06已合main，测试资源已回收；详见项目记录。既有运行规则： 知识授权回调纳入本环境生成，旧Worktree缺/空新增回调从本登记API派生，显式跨环境拒绝；全场景本地原生PG/Redis优先及禁止滥用Docker硬约束实装；Worktree 开发/联调前必读 worktree-development 规范；统一登记隔离资源，共享依赖缓存但独立安装，默认本地账号 admin/admin123456、默认模型对齐 miaomiaoai deepseek-v4.1-flash、配置继承与首次只读基础数据初始化已验收；知识MCP/独立Ollama新增登记/所属启停，4项自检及真实重启通过。7个既有Worktree已同步31个本地栈工具/规范文件；未来新Worktree需从包含该基线的提交创建。Worktree依赖/真实Worker隔离、模型配置重加密、源历史与新审计区分及多会话发布协作经验已写入[ai-workflow](lessons/ai-workflow.md)；回调/迁移回退/Docker日志/执行目录经验已写入[runtime-service](lessons/runtime-service.md)。 |

F07实施与验证入口以tasks.md/verification.md为准；正式post43和同名本地CAS候选来源/哈希不同，不能只凭版本名认定正式能力。

2026-11-16扩展更新：A01–A03完成；A04 partial，获批111.227.13.0/24准入已恢复，Task7.5单题真实运行通过；旧A04完整评测未重跑。Agent Web3000/API2142/Runtime8123、EvalFlow Web9128/API5001与fixture运行中；项目Agent评测项目、实验10与20/5题集合已持久化。75后端/9前端测试和模型/嵌入/DeepEval探针通过，原test配置未改。原首期/M01验收保留原范围，任务以tasks.md为准。
