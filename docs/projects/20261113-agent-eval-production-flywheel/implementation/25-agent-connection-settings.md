# 25｜前端 Agent 连接配置实施与阶段验证

日期：2026-11-18。唯一任务与整体验收要求在[10专题](../10-agent-connection-settings.md)。当前4项done / 1项partial，尚未完成真实双环境整体验收。本记录只保存实施细节和证据，不另建进度清单。

## 用户现在能怎样操作

打开同一个EvalFlow的“评测集”页面，顶部显示当前Agent连接及API地址。EvalFlow原生管理员可以配置或新增连接；普通成员只能选择已登记连接，再用该平台的账号登录。地址从EvalFlow服务器访问，不由浏览器访问。

本机连接`default`保留`http://127.0.0.1:38375`，继续通过原SSH反向隧道访问Mac API2142。浏览器已完成“配置连接→验证并保存→Agent登录→读取旧题库与结果”。服务器连接的界面和服务端能力已实现，但尚未保存真实`server`连接：服务器Agent仍是`0199e264`，缺少评测工作台、目标快照及本次连接描述接口，不能只填URL就宣称接通。

## 代码落点和约束

| 所属 | 修改范围 | 作用 |
|---|---|---|
| EvalFlow远端 | 新增`eval_platform/connections.py`；config/app | 原生管理员管理连接，准确origin白名单，按连接创建原路由与TaskStore；未知连接404，不回退default |
| EvalFlow远端 | authoring_api/workbench_access/workbench_api/browser_login/sso | 登录cookie隔离；来源、签名与实时成员核验绑定连接；SSO影子账号按连接与用户UUID区分 |
| EvalFlow远端 | work_items/work_item_jobs/tasks、结果/诊断、发布/审批/补收、inspection/retention/feedback_projection | 显式传递所属配置；任务快照冻结目标/凭据/任务目录；离线连接不阻断后续连接的维护 |
| EvalFlow前端 | 新增AgentConnectionSettings/agentConnections及测试；AuthoringPage、authoringApi、diagnosisApi、LoginPage及测试 | 配置表单、当前地址、每标签页URL选连接、带连接头的普通/流式/诊断请求、状态切换保护 |
| Agent API | config/delegation/materials/router/workbench、auth_context、`.env.example`及评测测试 | `PLATFORM_API_EVALUATION_CONNECTION_ID`；签名claim、交付/通知和服务认证描述接口绑定连接 |

连接注册表复用默认TaskStore的父目录。`default`保留原`.local-stack/evaluation.json`与`.local-stack/tasks`，没有迁移、复制或重编号旧业务资产。新连接位于`.local-stack/connections/<id>/evaluation.json`、`tasks/`和`results/`。配置文件0600；执行密码和来源密钥不回传浏览器。新连接不继承旧连接秘密。

保存后的连接标识、origin和项目不可修改，不提供删除入口；连接另一平台须新增记录。名称、执行目标和秘密更新须重新验证。任务已冻结的`.config`不会因改名、换凭据、切页面或重载注册表而改变。所有连接仍共享原总运行并发限制和两线程出题池，没有新增调度服务或常驻实例。

原生账号登录只验证EvalFlow自身账号，不再把原生管理员密码转发Agent。SSO按当前连接验签和实时回查，影子账号不取得EvalFlow全局管理员权限，也不自动获得原生实验访问权；查看原生实验/Trace仍需原生权限。已有独立原生账号和reviewer规则保留，不以平台管理员身份推导全局权限。

## 阶段验证（Phase）

### 自动化结果

| 范围 | 实际结果 | 私有日志位置 |
|---|---|---|
| EvalFlow：`tests/eval_platform`、根目录work-item测试、authoring API与退役回归 | 最终广泛回归593 passed；1条上游Starlette弃用警告 | sshmy1 `.local-stack/connection-settings/backend-release.log` |
| 连接专项 | 26项通过，已包含在上述593项内 | sshmy1 `tests/eval_platform/test_connections.py`及上述日志 |
| Agent全部8个`test_evaluation*.py` | 119 passed，12.96s | 本机`.local-stack/deliveries/20261118-eval-independent/api-connections-release.log` |
| EvalFlow前端AuthoringPage/authoringApi/diagnosisApi/agentConnections | 4套39项通过 | Mac EvalFlow `.local-stack/connection-frontend.log` |
| EvalFlow前端AgentConnectionSettings/LoginPage | 2套8项通过 | Mac EvalFlow `.local-stack/connection-form-final.log` |
| 前端类型与构建 | 主/shared类型检查、正常`yarn build`通过 | Mac EvalFlow `.local-stack/connection-build-final.log`及对应终端输出 |
| 静态检查 | Agent全部改动Ruff无诊断；远端新增模块/专项测试Ruff、36个Python文件AST、diff检查及upstream-guard通过 | 本轮终端输出；远端`mlflow/`改动为空 |

新测试覆盖准确origin与危险URL在网络前拒绝、301/302/307/308不跟随、新连接秘密独立、普通成员不能配置、返回值不含秘密、连接不可换origin/项目、未知ID不回退、来源与命令错连接拒绝、同用户UUID/密钥的SSO隔离、按连接cookie、同项目/工作项/请求ID通过真实读路由隔离、同Task UUID隔离、原总并发限制、快照在换凭据/重建注册表/停止后不变、维护遇离线连接仍处理后续连接，以及临时副本备份恢复保持连接及0600权限。涉及网络身份的隔离用受控夹具，不等同两套真实Agent完整E2E。

前端增量lint检查新组件/助手与客户端通过；AuthoringPage原有11条诊断保留，不称全仓lint通过。构建仍报告Browserslist数据陈旧、Node punycode弃用与bundle偏大，未为本需求升级依赖。

### 浏览器与真实HTTP

使用browser-skill的独立`connection-settings` Agent Window，未借用用户标签页。先发布hash静态资源，再发布index/manifest，不使用删除同步，旧hash仍保留。生效入口为远端9128，新脚本`static/js/main.45e26aaa.js`、样式`static/css/main.f5f96c5a.css`。

实际观察如下：

1. 管理员看到当前“本机开发”及38375地址；配置表单中连接标识、origin和项目禁改，两项秘密为空。
2. 点击“验证并保存连接”成功，再使用所属Agent账号登录；列表仍有原7个工作项。打开`MAIN-EVAL-20261118-当前会话`，草稿v3、题库v1和原两条运行均可读，没有触发新的模型请求。
3. 新连接填写未受信的`http://example.invalid`及合成非秘密测试值后，服务端拒绝保存；界面显示错误，两项认证输入清空，连接列表仍只有default。没有保存伪造server或向未知地址转发真实凭据。
4. 无活动任务/出题作业时必要重载`mlflow-eval.service`。默认配置与原两份任务冻结快照字节未变，服务active、health200。浏览器重载后Agent登录态、默认连接、旧草稿及两条历史结果继续可读。
5. 真实HTTP复核：连接摘要不含秘密；default描述200，Agent登录/context200；未知连接404、错连接来源403、缺来源密钥403。经实际Nginx入口读取新index与脚本均200。旧7个工作项、2个Task保留。

HTTP结果保存在sshmy1 `.local-stack/connection-settings/live-release.json`，不含认证信息。浏览器文本与两张截图在Agent私有`.local-stack/deliveries/20261118-eval-independent/browser-connection-*.txt/png`、`browser-after-restart.txt`；这些是本轮合成资料验证，不将旧模型结果说成本轮重新执行成功。

### 失败与修复事实

初期后端扩大测试暴露旧fixture未传所属配置、旧SSO测试依赖平台管理员自动取得原生全局管理权；已补齐配置并改为连接范围内身份测试，没有删测试或跳过失败。前端首次出现Mac大小写文件名碰撞，组件由`AgentConnections.tsx`改为`AgentConnectionSettings.tsx`；表单label与SSO请求fixture同步后通过。worker缩进问题已修并由完整解析及回归覆盖。

真实保存时发现新`GET /api/evaluation/internal/connection`被平台普通JWT中间件挡住。已仅为该method/path加入服务认证通道，仍由`source_access`校验来源密钥与连接；包含真实全局中间件的成功/缺密钥/错连接/错method测试通过。不能将该修复表述为放开匿名业务访问。

末次Agent回归曾误写不存在的`test_evaluation_delegation.py`，pytest未执行；改为实际8个文件后119项通过。新增工作项隔离测试首次缺`share_with_project_reviewers`必填夹具字段，补齐后通过。发布index首次遇到本机构建仍未结束，rsync返回23；待最终构建exit0后重新按资源→metadata顺序发布并验证。

重载后的原生静态探针首次直接访问5000并伪造公网Host，被原有DNS-rebinding校验403拒绝。未放宽Host规则，改从正常Nginx9128入口带原生认证验证成功；业务自定义路由与来源负例同时通过。

## 配置、资源与恢复交接

EvalFlow的`EVALFLOW_AGENT_ALLOWED_ORIGINS`为逗号分隔的准确HTTP(S) origin；未配置时默认38375和2142两个回环候选，并保留现有default origin。前端填写不会扩大该列表。Agent使用`PLATFORM_API_EVALUATION_CONNECTION_ID`与连接id匹配，当前本机保留default，未来服务器应单独配置server。来源密钥对应各平台的`PLATFORM_API_EVALUATION_SOURCE_TOKEN`，不可把EvalFlow原生密码当来源密钥。

实际只更新default私有配置、远端后端与前端产物，备份位于sshmy1 `.local-stack/connection-settings/backup-before-live/`，0600。备份包括旧evaluation.json、index及manifest；旧hash静态资源保留。本机API热重载，远端使用原systemd服务；没有新增实例、迁移、业务库删除、模型测试或共享隧道重建。

恢复连接资料时须一起恢复默认evaluation.json/tasks、connections目录及相关results，保留原部署路径或显式核对快照中的绝对task_root/output_dir，不能只拷贝新evaluation.json。原生MLflow数据库/auth库与制品沿原备份规则配套；本次只做临时副本的连接状态恢复测试，没有生产数据库回退。需要回退代码时按已保存的版本差异和备份审阅执行，不运行清库或全目录覆盖。

既有SSH master仍归原主工作区，远端仅监听回环38375，指向Mac2142；用原私有连接清单与管理流程恢复，先核对端口/隧道归属，禁止重复建立相同转发。保留HTTP无TLS、本机和SSH在线的既有边界。浏览器会话在文档收尾期间因闲置超时自动关闭，随后close返回已结束并确认Agent Window/所属标签页已回收；业务服务保留运行。

## 未完成的整体验收

服务器Agent未升级，也没有登记第二条真实连接。只读核对发现其3个已跟踪修改仍位于Runtime sandbox存储、dearflow workspace及对应测试，另有私有部署文件。本轮未改这些内容，不执行git提交/推送、新建分支或服务器Agent生产升级。

与服务器基线比较，服务器缺失整个`platform_api/modules/evaluation`，不只是本次connection_id字段；主仓还包含API迁移`20261113_0011_evaluation_feedback.py`及Runtime迁移`0011_evaluation_execution.py`。这只证明升级范围涉及API、Runtime与评测表，尚未核对生产实际迁移头，不把“文件缺失”推断为“生产表不存在”。完整差异中的apprise/sqlglot来自其他能力，不能为了开通连接盲目整体升级依赖。服务器开通必须单独审阅部署清单、实际库版本及回退方法，不能复制7个本次API修改文件就上线。

下一步需要用户批准服务器Agent升级及所属项目/账号配置，先确定差异清单、保存既有修改与回退方式，再开通server并完成Task10.4原验收：两环境同时的转换、授权、出题、发布、真实运行/Session/Run/Trace，双标签/在途任务与真实断线恢复，审批/停止/补收/同证据重评。新SSO影子账号的原生实验权限须显式核对，不能通过全局管理员提权绕过。

09原5项done和08原6done/1partial保持不变，08的隔离全栈回退与再升级仍未验证。本专题保持partial；本轮没有把Phase放入Final或自行缩减Final范围。
