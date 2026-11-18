# 26｜连接配置代码交付与相关服务升级

日期：2026-11-18。用户明确要求先提交代码到远端仓库，再升级相关服务。承接[10专题Task10.4](../10-agent-connection-settings.md)，本记录只保存交付/部署证据，不另建任务清单。原开发验证见[25记录](25-agent-connection-settings.md)。

## 批准范围与升级顺序

先提交两仓连接功能与测试，再停止服务器Agent写入、备份、迁移和升级；随后登记server连接并执行有界合成验证。私有env、配置密钥、会话、数据库与构建产物不提交。不增加常驻实例，复用原EvalFlow和38375反向隧道。

## 代码交付与既有改动保护

| 仓库 | 已提交并推送的代码 | 内容 |
|---|---|---|
| Agent main | `9a88b7939d938f996db148dc76a09cc902ed47a4` | 连接契约、签名/交付/通知、描述接口、测试及文档，20文件 |
| EvalFlow main | `7b8d08d2601e687866a8356bd90bc2b535f57acd` | 连接注册表、按连接身份与资产、前端及测试，53文件 |
| EvalFlow main | `c065db094c1fdc8ef5a8ac76cef366bae729b37d` | 部署实测发现的冻结连接题库目录修复与2项回归 |

Agent首次提交被Ruff格式化钩子中断，8个Python文件经钩子格式化后重新暂存，提交通过。EvalFlow后端在sshmy1提交/推送，Mac镜像pull；Mac原12个前端修改先备份、定向stash，随后逐个SHA256核对与已提交源文件一致，没有apply重复补丁。私有备份在Mac `.local-stack/deliveries/20261118-eval-independent/evalflow-mac-before-sync/`。

服务器Agent原基线`0199e264`。以下3处既有未提交修改先保存patch及AST，再与main逐文件比对，确认主分支已包含全部语义，定向stash后ff-only更新，再次AST一致：

- `apps/runtime-service/src/runtime_service/sandbox_node/storage.py`
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py`
- `apps/runtime-service/tests/services/dearflow_agent/test_agent.py`

原`/workspace/outputs/`可写修复及路径保护保留。服务器原`.config/`、`apps/platform-web/.env.production`、`scripts/backup_database.sh`、`scripts/run_production_service.sh`未跟踪私有文件均保留，没有目录覆盖。服务器缺整个评测模块，使用兼容整版升级，未拼凑个别文件。

服务器GitHub 22连接挂起后，仅终止本轮确认的Git/SSH进程；通过本机Git bundle传输并核验精确提交，再ff-only更新。后续GitHub 443已验证可用，使用原受信`github.com`主机键校验，不关闭校验、不修改主机信任。文档后续同步使用443通道。

## 停写、备份与数据库迁移

停写前服务器27个历史Thread均idle；27个历史Run为24 success、2 error、1 interrupted，无pending/running/queued/retrying或cron。历史interrupted记录保留。停止API、Runtime API和Worker后执行备份与迁移，没有取消旧运行或删除业务记录。

远端备份目录：`/opt/ai-agent-platform/.local-stack/deliveries/20261118-connection-upgrade/`，目录0700、敏感文件0600：

- `files/`：私有env、部署/备份脚本及`.config/`；另存四个systemd unit内容、`server-before.patch`与`patch-ast.json`。
- `platform_api.dump`：17,624,318字节；`graphharbor_acceptance.dump`：17,506,883字节。两个自定义格式备份均通过`pg_restore --list`，未实际还原生产库。
- `api-migration.log`、`runtime-app-migration.log`保存真实迁移输出；旧前端index另存`agent-web-index-before.html`。没有运行会清理旧备份的脚本。

| 数据域 | 升级前 | 升级后 |
|---|---|---|
| Platform API | `20261030_0010` | `20261117_0014`，经过评测0011、助手证据0012、通知0013/0014 |
| Runtime应用 | `0010_terminal_cleanup_binding` | `0011_evaluation_execution` |
| GraphHarbor引擎 | `014_thread_retention` | 保持014 |

0013执行前通知表不存在，没有删除旧通知。GraphHarbor及graphharbor-runtime均保持`0.13.0.post48`，未升级引擎核心包。Runtime原docker/remote沙箱选择未改。

服务器API缺少当前版本已声明的apprise/sqlglot。用59个原已安装包的精确版本作约束预检，只补装锁文件中的`apprise==2.2.0`、`markdown==3.11.3`、`oauthlib==4.0.1`、`requests-oauthlib==2.0.0`、`sqlglot==28.10.1`。原包版本保持，没有全量更新依赖。

**恢复边界：** 本轮验证了备份可列出及升级后服务/数据可读，没有实际执行全栈降级再升级。若需恢复，先停止新增写入并另存升级后资料，在隔离库验证两个dump、旧代码/私有配置及对应前端index后再决定生产恢复窗口；不能只回退代码而让旧程序读取新结构，也不能直接覆盖正在写入的数据库。08的V8.7仍未通过。

## 私有配置与服务发布

服务器API设置`PLATFORM_API_EVALUATION_CONNECTION_ID=server`，复用现有`test`项目`17bc3aa1-5248-4237-874f-ffdcaa327ce5`，开启获准工作台/资料交付，接收方为EvalFlow内部5000、网页9128。独立source token未输出；执行账号复用现有admin，未新建服务器用户/项目或改变旧角色。原dev项目不变。

Runtime启用评测证据及现有MLflow认证，保留tracking URI `http://127.0.0.1:5000`和实验`ai-agent-platform-traces`。私密账号信息只写入服务env。server经正式连接管理API验证保存到`.local-stack/connections/server/evaluation.json`，使用独立tasks/results；集中实验17通过正常MLflow接口创建。default保留原目录、项目与实验。

| 连接 | EvalFlow后端访问地址 | 实际环境 |
|---|---|---|
| default／本机开发 | `http://127.0.0.1:38375` | 原SSH隧道回Mac API2142，环境`primary` |
| server／服务器 | `http://127.0.0.1:2142` | sshmy1 Agent API，环境`sshmy1-server` |

服务器Agent前端在Mac用公开配置构建，`VITE_PLATFORM_API_URL=/`、EvalFlow网页9128、原实验6保持。vue-tsc与Vite构建通过后发布至`/www/wwwroot/agent-platform`，先增量复制资产、最后原子替换index，保留旧hash。HTTP200且index与新产物一致，SHA256为`649ca5198497fe1010faca85e30699565e431255e144b0a1226a770fb4a05f9f`。没有在服务器重度打包。

EvalFlow沿用前一阶段已发布前端：`main.45e26aaa.js`、`main.f5f96c5a.css`。后续目录修复仅改后端，在无活动任务时重载`mlflow-eval`。既有四个systemd unit及私有启动脚本不替换。

**实际故障与恢复：** 使用dotenv原子更新两个env后，文件属主变成root；0600使服务账号`aiplatform`无法读取，造成短暂重启循环。已恢复两个env属主为`aiplatform`、权限0600后重启。最终四服务`active/running`、`NRestarts=0`，API健康200且`database_ready=true`、EvalFlow健康200。最终只读探针保存在备份目录`final-health.json`。先前单凭systemd active的检查不能当作完整就绪证据。

## 升级后回归与真实双环境验证

### 自动回归

- 服务器Agent API：8个`test_evaluation*.py`，**119 passed / 4.65s**。日志在上述备份目录`api-evaluation-regression.log`。
- 服务器Runtime：evaluation目标、环境、执行证据、维护权限及原dearflow outputs修复，**57 passed / 14.56s**。日志`runtime-regression.log`。
- EvalFlow目录修复：**33项关联回归**通过；扩大范围为`tests/eval_platform`、根目录work_item_results/work_item_retention/work_items、authoring_api、legacy_entry_retirement及copilot_lifecycle，**606 passed / 21.40s**，1条既有Starlette警告。日志`.local-stack/connection-settings/backend-upgrade-fixed.log`。不与先前593项相加。
- 新测试Ruff通过；`run.py`对照修复前保留2条E501及1条E306原诊断，新增行无诊断。diff检查通过，`mlflow/`零侵入。前端原6套47项、类型/构建证据沿用25；本轮Agent生产构建再次通过，既有Browserslist和大chunk警告保留。

### 登录、连接与浏览器

远端`.local-stack/connection-settings/dual-live.json`：两个连接各自登录、context、来源描述均200，错连接头均403；server保存200，default配置及旧冻结任务字节不变，响应不返回密码/source token。

browser-skill自建scope `eval-upgrade-20261118`验证：原生管理员登录、server平台登录、配置读回、秘密不回显；两个标签同时分别保持default旧列表与server工作项，互不显示对方资料；default旧v3及历史结果仍可读，server passed详情及Session/评分/工具0可见。服务器Agent80页面仍显示原工作区、旧会话和管理导航，Runtime在线。重载窗口曾显示暂不可用，就绪后reload恢复。scope已关闭，业务服务与原隧道保留。

Mac私有证据目录`.local-stack/deliveries/20261118-eval-independent/`保存`browser-upgrade-default.txt`、`browser-upgrade-server.txt`、`server-upgrade-result.png`。

### 两环境发布与真实运行

两边各发布一题合成算术题：计算2+3，只输出数字、不调用工具；使用明确v3格式与预期5。completion、turn_expectations、tool_budget三项均通过，各1 Session/1 Run/1 Trace，工具调用0，错误为空。

| 连接 | Task与结果 | Session | Run | Trace |
|---|---|---|---|---|
| server | `5cb26974-9c0b-508c-9419-823a813bdcbb` passed | `880c5724-e7c2-4572-b775-504163624688` | `54f1f2ab-01aa-451c-942a-aabe2a46f3f8` | `tr-fbc2c7c576a6faa187a4ffc93500ccef` |
| default | `8c839c48-0559-50f8-934d-872bd83ed884` passed | `b406da09-a2ae-439a-803a-b60da16f2c6d` | `5fbead9f-be31-4989-a873-d4d5cdad6b27` | `tr-7c92527d25729f206caf034eb3ae8927` |

server题库`d-ac2941a0413a41a4b597fea002246cd4` v1；default题库`d-ea4cc582dc764b118abb60ba2aecb873` v1。目标环境分别`sshmy1-server`/`primary`，项目分别服务器test/本机Agent评测项目，与冻结配置一致。服务器Runtime库确认新增1条执行证据。日志`.local-stack/connection-settings/upgrade-lifecycle-fixed.log`，脚本`upgrade_lifecycle.py`。

**保留的首次失败：** server旧Task `fd1a009e-9973-5ea2-ae0b-0bcaf32e73c9`因`run.authorize_dataset`硬编码默认tasks目录而在执行Agent前失败。`c065db0`使用冻结`config.task_root`校验，新增两项先失败后通过的测试，同时验证不能回退到默认目录同ID题库；旧失败未改写，新请求通过。真实运行提示`budget_policy_not_configured`，不宣称已通过预算/性能门禁。

### 历史会话、转换、幂等与AI候选

两平台正常账号各自查询历史列表200，并找到自己的新执行会话。仅将本轮合成Session通过`/api/evaluation/materials/send`（sync、auto_generate=true）转换，均200 delivered；原request重放返回`reused=true`，没有重复采集旧业务资料。server通知携带`?connection=server`。

- server转换工作项`8d38a460-1dcb-5eef-9031-b3eba7a61666`，AI请求`e41b6245-48cc-5eff-b9de-48ef1072a719` completed，已有候选。
- default转换工作项`b266f3f1-c971-530a-8694-e6f2e96f38e3`，首个AI请求`747a267f-2989-5f48-8d7f-fc797fb43f42`在3次结构修复后仍给出非法case_id/schema，终态error、没有写入候选。补充明确v3单题口径，以新请求`49d1c6a3-96c4-5519-ab06-3fbc38241ad2`重试后completed并生成候选；不重放未知写、不改旧终态。

远端证据：`.local-stack/connection-settings/dual-conversion.json`、`dual-conversion.log`、`default-generation-retry.json`及`default-generation-retry.log`。首次模型失败属于本轮事实，没有为此修改产品代码或删除失败记录。

## 当前结论与未验范围

用户本轮要求的两仓代码交付与相关服务升级已完成，服务健康，服务器原修复与私有部署文件保留。以上为升级后的阶段补验；10专题仍4done/1partial，09仍done，08仍6done/1partial。

收尾文档核对仍为5项任务、8个已勾选/2个待验，摘要与任务一致，diff检查通过。全文件相对链接检查发现FEATURES原有4处失效引用，与HEAD基线相同，本轮未顺手更改；本次新增引用均存在。

本轮发布/运行使用手工确认的一题，尚未把两边转换后的AI候选继续采纳、发布并运行成同一条完整链。双环境普通成员、真实断隧道/在途切换/撤权、审批/停止/重启、补收与同证据重评等组合仍未全验；08全栈回退与再升级未执行。保留原验收，不以分段成功替代整体Final。

公网仍为HTTP，无TLS；default依赖Mac API与原SSH隧道持续在线，server直连不借道Mac。模型生成仍可能结构校验失败，需要补充明确口径后以新请求恢复。没有删除业务数据库、备份或失败记录。
