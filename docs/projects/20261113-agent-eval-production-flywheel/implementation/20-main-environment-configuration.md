# 主工作区评测配置与真实验证

2026-11-16，关联07 Task 7.5。只修改本地主环境私有配置和使用说明，没有改业务代码、提交Git或部署应用。后续经用户明确授权，仅调整既有sshmy2沙箱的源IP准入并重启Node。

## 为什么需要补齐

隔离验收环境已按用户要求回收；合并代码不会把被忽略的 `.env`、测试账号和数据库复制到主工作区。主环境缺少`EVALFLOW_WORKBENCH_ENABLED`，因此页面明确显示“评测工作台尚未启用”，不是题库被删或前端缓存问题。

用户要求配置并补充环境变量注释，又明确批准主环境启用原生页面登录与授权批次隔离、新建独立后台服务及普通验收账号；保留现有实验和数据，不恢复旧`flywheel-reviewer`。本轮没有合并两个平台的用户或角色。

## 已完成的配置

| 位置 | 配置内容与用途 |
|---|---|
| Agent `apps/platform-api/.env` | `PLATFORM_API_EVALUATION_*`：会话反馈、工作台、获准项目与模型目录ID、EvalFlow后端5001及前端9128、后台接收账号、共享回源密钥；旧合成导出及真实巡检仍关闭 |
| Agent `apps/runtime-service/.env` | `RUNTIME_EVALUATION_EVIDENCE_ENABLED=1`；本机MLflow写入身份和密码，与EvalFlow后台配置一致；保留原`docker/remote`执行后端及Node绑定 |
| EvalFlow `.env` | 工作台、固定端口、原状态/任务配置路径、平台回源URL和密钥；`basic`原生页面登录、授权批次隔离、原生账号库路径、后台SDK认证和签名密钥 |
| EvalFlow `.local-stack/auth.ini` | 专用本地SQLite账号库，`NO_PERMISSIONS`默认拒绝，不自动开放默认工作空间；业务存储仍是原PostgreSQL，没有替换 |
| EvalFlow `.local-stack/access-policy.json` | 旧任务页仅给普通账号现评测项目/集中实验的30天只读策略；不是向全部实验授予读取，也不替代评测集逐次授权 |
| EvalFlow `.local-stack/local-accounts.txt` | 普通原生账号`local-reviewer`及随机密码的查看位置；后台`evalflow-service`用于内部调用，不用于日常页面登录 |

三个`.env`均逐项添加中文用途、服务端/浏览器地址区别和重启说明。原文件备份在各仓库忽略的`.local-stack/config-backups/20261116/`；配置、凭据和账号库权限600，未在输出或文档中保存密钥。原Runtime已有`AGENT_CONTEXT_MANAGEMENT_ENABLED`重复定义，本轮未新增或调整它。

复用“Agent 评测项目”`352e1fdd-10c3-44a5-820c-27ca2d7a7424`、现有Agent和`Evaluation xiaok DeepSeek`模型；没有新建项目或更改模型策略。AI建题/裁判资源仍由既有`evaluation.json`的`resource_file`读取`~/.my_best/.env`，不混同原生网关的`OPENAI_*`配置。

## 真实验证结果

- 平台API、Runtime API/Worker、EvalFlow后端通过所属`local-stack.sh`重启；前端继续使用3000/9128，API为2142/8123/5001。
- 15项真实HTTP检查通过：工作台未登录401、平台账号登录/上下文/跨平台列表200、跨源403；原生未登录401且无认证挑战弹窗、错误密码401、普通账号登录/会话200、集中实验10读取200、其他实验0读取403、退出200及退出后401；平台工作台开启而巡检关闭；错误服务密钥403。结果在EvalFlow`.local-stack/main-workbench-config-checks.json`。
- 普通原生账号只显式获得旧集中实验10的READ，非管理员；启用登录前的12个实验全部仍存在。后续新建授权批次实验12，普通账号读取该实验和其Dataset均403，保留平台管理的资料边界。
- browser-skill在Agent Window完成两种页面登录、评测集列表/新建、保存资料、授权AI、真实xiaok DeepSeek生成（1次模型请求）、确认发布一题为v1、点击真实运行。新增自检用例是纯虚构算式，不使用真实业务数据；本轮不录屏。
- 本地样本：`主环境配置自检-20261116`，工作项`bab3dd70-df7a-4749-b04b-a6678fc1eb82`，Dataset`d-5e677143c1104e4c9534fe8c7e5d2a98`，实验12。发布成功与运行成功分别记录。
- 最小运行`408d5cde-9b74-4d5c-994b-8cee49d52e5d`失败：被测Agent在远程Workspace prepare阶段报`runtime.workspace.execution_outcome_unknown`，尚未产生模型回答。已有1个Run/1条Trace及执行证据；Trace收集complete，证明新后台认证没有阻断写入，不表示Agent执行成功。证据保留在EvalFlow`.local-stack/results/408d5cde9b744d5c994b8cee49d52e5d/config_selfcheck_add_001/evidence.json`。
- 初步排查时HTTPS报`UNEXPECTED_EOF_WHILE_READING`，本机路由走`utun4`，曾怀疑VPN/代理路径；该推测已被后续服务器防火墙日志收敛为明确的源IP准入阻塞。本机TCP连接返回成功不能证明请求穿过了服务器防火墙。未改系统路由、VPN、云/宿主防火墙、远端服务或执行后端，未重放未知结果操作。
- 后续只读排查确认：当前软件为Clash Verge，但尚未修改其配置。SSH服务器看到当前出口为111.227.13.240，而UFW的19111白名单及Node执行域wt_f58309b22539的allowed_ips均仅有旧出口66.90.99.210、120.245.112.51、120.245.112.0/24及49.233.222.54，没有当前出口；两端CA指纹一致。至少存在明确的源IP准入不匹配，不能继续把原因笼统归为代理。已请用户批准仅追加当前IP的/32白名单及安全重启，确认前未变更远端。只读检查没有活跃沙箱容器，240条资源均为removed；3条旧accepted操作分别来自10月13日和11月6日，未改记录或重放。
- 2026-11-16根因补证：服务器日志有13条来自111.227.13.240、目标端口19111的`UFW BLOCK`，发生于北京时间08:38:04至08:39:48，直接证明本次请求被防火墙拦截。Node从2026-11-06 19:02:35起持续运行，未发生服务自动重启；两端Token及客户端证书身份匹配，客户端证书有效至2027-01-10，本轮沙箱配置与修改前备份一致。脱敏证据在Agent仓`.local-stack/main-sandbox-access-diagnosis-20261116.json`。
- 历史核对：上一项目`20261112-agent-evaluation-system/tasks.md`的A04及`implementation/13-primary-project-setup.md`在2026-11-13已记录主环境新出口未准入。不能将旧隔离环境验收通过等同于主环境远程沙箱成功，也不能归因于本次电脑重启或本轮配置。出口具体何时、因何变化尚无证据。用户无需自行配置代理或SSH；下一步待明确批准精准追加当前IP的/32准入，核对空闲并备份后短暂重启已有Node，再验证完整运行；不部署新代码。
- 最初API核对脚本误按顶层`access_token`读取登录响应，修正为实际`tokens.access_token`后上述15项通过；没有为验证脚本改应用接口。

截图均在EvalFlow`.local-stack/`：`main-authoring-new-20261116.png`、`main-native-login-20261116.png`、`main-published-sandbox-block-20261116.png`。它们是本地主环境证据，不替代旧项目的独立盲测/性能/生产验证。

## 下一步与边界

配置、登录、AI建题、题库发布和最小真实运行均已完成，Task 7.5现为done。下面的恢复记录是本次新证据，不覆盖上面的初次失败事实；旧A04完整评测范围没有随本次单题检查自动完成。

无业务代码变化，未重复运行历史全量单元/构建；真实CI、独立盲测、性能、自动抽样和生产仍按既有决定暂缓。没有删除主数据、迁移现有实验、恢复旧Worktree或重置平台账号。

## 2026-11-16 · 按批准恢复远端准入并完成运行

用户明确选择放行111.227.13.0/24（最后一段可变化，共256个地址），代替先前建议的单IP /32。此授权仅涉及sshmy2沙箱19111端口和执行域wt_f58309b22539，不扩大到其他端口或调用方。

- 修改前核对：无活跃沙箱容器，240条资源均removed；仅3条已核实的历史accepted操作，没有新增未决操作，未删除或重放这些记录。
- 备份：远端 `/etc/runtime-sandbox/backups/access-20261116T005825Z/` 保存原callers.json、UFW用户规则及规则状态，目录700、文件600。只向原caller的allowed_ips追加批准的CIDR，并增加19111/tcp对应UFW规则；和备份逐项比较确认其他caller字段、Token摘要及证书身份未改变。
- 只重启 `runtime-sandbox-node.service`，没有重启整机、其他服务或部署新代码。服务active，原Runtime客户端公网mTLS readiness返回ready=true；携带错误Token的只读请求返回sandbox_caller_denied。网段边界检查确认当前111.227.13.240被覆盖，新增规则不覆盖111.227.14.1；未从该外部地址实际发起连接。
- browser-skill从已发布v1点击“运行已发布版本”，新任务 `62ebfb9e-4722-4226-941d-51eb81406f7e` 最终passed，1/1题完成。Agent可见回答为3、工具调用0；原始输出有前导换行，按现有代码检查规则通过，并非原始字节逐字相同。turn_expectations、tool_budget及三项语义评分均为1，3次真实裁判请求完成。原题虽要求仅代码指标，但当前发布版仍带有三项语义指标；本轮没有为制造通过而修改已发布题目或评分标准。
- 本次执行Session `d2b6f8c0-308f-4dc4-a711-97d432cf6b0e`，Runtime Run `4a40e757-a10a-4fdc-a159-be2d8c6bdb55`，Trace `tr-3ee50699f5e663ee9adb17baa68d63a7`；收集complete、无缺失。MLflow评测Run `35babc06ea30489ca0d10efbeb2e178d`。浏览器已展开本次结果、原生会话和裁判过程，答案及5项pass可见。
- 证据均在EvalFlow主目录 `.local-stack/`：`main-sandbox-restoration-checks-20261116.json`、`main-sandbox-restored-20261116.png`、`results/62ebfb9e47224226941d51eb81406f7e/config_selfcheck_add_001/evidence.json`。全页截图因页面动态更新的严格观察校验被拒，未绕过；改存实际结果视口截图并检查画面。初次失败任务和Trace保留。

本次证明主环境配置及一条最小真实评测链路恢复，没有重跑上一项目20/5题、全部复杂场景或性能/CI/独立盲测。门禁仍提示budget_policy_not_configured，未声称预算治理通过；循环观察coverage unavailable，自动停止循环仍属原暂缓范围。当前网段之外的出口变化仍需重新确认准入，不应自动开放更大网段。
