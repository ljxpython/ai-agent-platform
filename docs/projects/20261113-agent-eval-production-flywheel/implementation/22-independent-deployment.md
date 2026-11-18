# 09 独立部署实施与验证证据

日期：2026-11-18。唯一任务状态在[09专题](../09-independent-deployment.md)，本文仅保存实现说明和实际证据。

交付后说明：用户随后确认需求完成，两端代码已合main并推送；本次隔离服务、Worktree及测试库已删除。本文端口、原Task/Run和`.local-stack/`路径描述开发时现场，现不能据此打开旧环境；日志转存及合并回归见[23交付与清理](23-delivery-and-cleanup.md)。未验项目按用户决定回main继续。

## 环境与授权

Agent：`/Users/lijiaxin/.codex/worktrees/f40b/ai-agent-platform`，基线`7081ae3e3963e12c6bf3e54a7d1e430d7a0ccbad`；独立Web26007/API24138/Runtime24493，专属PG/Redis/依赖。EvalFlow：`sshmy1:/opt/worktrees/evalflow-api-boundary-20261118`，基线`acfc89a`，独立API5011/SQLite/artifacts/venv，现场修改。两端只带入前序评测清理，无他人IAM/Usage改动。

开发传输为本机65156→远端5011、远端46187→本机24138的SSH回环隧道。主环境3000/2142/8123与远端9128未切换。密钥、账号和进程信息只在各自Git忽略的`.local-stack/`，不进入本文。

## 实现位置

- Agent `modules/evaluation/targets.py`：新快照与绑定运行；`core/runtime_contract.py`、`modules/runtime_gateway/application/service.py`：可信metadata、恢复绑定、实时执行权限和幂等。
- Runtime `observability/evaluation_target.py`：服务自身构建与项目资源摘要；dearflow factory执行前校验；原execution_evidence回执追加目标摘要。
- EvalFlow `targets/catalog.py`、`deployment.py`、`run.py`、`targets/agent_platform.py`：HTTP快照、冻结绑定及回执核对，删除正式跨仓源码、环境及venv读取。`network.py`与各HTTP入口：准确origin、认证、禁重定向及环境代理。
- EvalFlow `work_items.py`、`evaluation_assistant.py`、`work_item_jobs.py`、`dataset_registry.py`、`tasks.py`：题库独立资产、失效源隐藏、发布与执行不继承临时源授权、发起者当前权限检查。

平台执行账号与题库实际发起者是两种身份：快照绑定前者的有效工具策略；TaskStore保存后者的真实platform_actor_id，后台每次提交另查其当前成员及执行权限。这里不承诺发起者所有个人工具限制自动继承到专用执行账号。原管理接口权限没有放宽。

## 真实跨机与到期题库

首次成功Task：`07404427-95db-44e5-b8ff-2d54e5301695`，Thread`7252d7c0-817b-4aa2-9d05-7e8fb66dbfd2`，Run`53cf7857-556e-4437-8fee-79263925d65a`，Trace`tr-353a2c6601cfddbedf66af2a7f71841e`。真实输出“独立部署验证”，1份回执，deployment/runtime_package均matches；两项代码评分通过。

当前会话浏览器转换创建工作项`c8bbfe7f-4c1b-5994-b212-4598b0a984bc`，真实AI候选`d1b0924a-aa28-558d-9bfc-1d9cf77becb1`完成。通过正常authoring API采纳后，清除AI误写为缺口的“无阻塞性全局缺口…”说明；未改纯文本题和逐字评分标准。

在专属`wt_136085e6852b_platform`中，按grant ID及work_item_id双重限定，将这一条合成授权`51edcf65-d6ce-5e49-951b-c3d17f0530f6`的expires_at设过去。这是时间过期fixture，并非等待自然24小时。真实取源返回403 `evaluation_export_expired`；题库返回版本正常，`source_materials=[]`、`source_access=unavailable`。正常edit后revision3，正常approve发布独立题库`d-45a3b082425f4c5a83d3341d601d38bd` v1。

到期后运行Task`028ac694-563e-478c-bf84-a7b3a18ea924`最终passed。Thread`d9bf9420-4238-48f3-b070-f98f58dc7eb8`，Run`e79f6bf4-26b6-4df4-bd88-0991c376c20b`，Trace`tr-026bd991228fe7699f39ed0fcfcfdf76`；answer_contains/tool_budget/turn_expectations三项通过。任务私有config中`evaluation_grants=null`、evaluation_actor_id为实际发起人；1份执行回执、Trace完整、双方版本匹配。未配置预算策略的warning保留，不代表性能验收。

历史入口浏览器另建工作项`c760d00b-9548-5464-bcc0-fb5593a542cf`，AI候选`cd01c1e7-5a9c-5876-b50e-acb93f4e7bb8`completed。两入口各只提交一次。browser-skill scope已关闭。EvalFlow远端无UI构建，仅authoring真实API和Agent浏览器已验。

## 失败与修复

- Task`587166aa-b750-4bf4-ab62-ec061d50812b`：evaluator身份清单仍无条件读取已不使用的mcp包。已移除正式清单依赖，本地fixture辅助保留，没有补多余包。
- Task`60e78cac-16c4-485a-8ba5-2d220220e288`：完整target放入普通metadata触发`model_resilience`私有字段校验。改为服务端独立参数验证后注入，客户端私有字段保护保留。
- Task`92160b92-d33c-4130-b0c3-ae2c4282ecec`：供应商quota403。只将本次私有评测config模型改为项目已有连接`070cced3-350b-42ec-b678-994dd07b7078`，不改共享连接。
- 第一次远端地址配置前缀误写，能力只读发现后改为`PLATFORM_API_EVALUATION_*`；错误配置期间未发送桥接写入。第一次候选操作误用`adopt`返回403，正确操作为`edit`携带candidate_job_id；该次拒绝没有写入，未放宽权限。
- 普通执行者快照实测发现调用管理员工具限制列表会403；改为现有`resolve_tool_overrides`读取执行者有效策略，并新增针对性回归，不修改原管理接口权限。
- 材料快照测试一次随机UUID尾段`14421018482`命中既有手机号规则。仅将非ID测试的fixture改为固定a/b/c UUID，复验通过；没有改产品隐私规则，UUID误判风险未在本专题修复。
- 停止脚本最初遗漏`interrupted`这一原生取消终态，断言失败时产品已经停止。修正脚本后按原幂等键只读回查原Run及正式回执，没有重放模型；另一次普通执行者读取管理员工作项被ACL正常拒绝，改为其自己新建题库完成验证，没有放宽权限。
- 超时/审批探针最初的v3断言格式被schema拒绝，修正私有探针脚本后才启动真实Run，没有修改产品schema或评分规则。

## 权限、漂移、幂等与停止

通过正常管理API新增本次专用账号`100c8538-8596-460e-a007-313cfebf12b9`，只授隔离评测项目executor；密码仅保存在本机0600私有文件。该账号自己创建工作项`4f9e37d8-56c5-4c73-ab81-4956c743cdbe`，Task`b242966c-12a5-4d14-a367-04e79ca1315f`真实passed、三项指标通过。随后通过正常DELETE member接口撤其本项目角色；同账号EvalFlow登录仍200，但自己题库的新运行403，目标snapshot及Worker成员权限回查403。没有修改其他用户角色。结果见本机`.local-stack/boundary-results.json`。

取得冻结快照后，用正常PATCH临时改Agent名称，提交返回409 `evaluation_target_changed`；finally恢复原名称，摘要恢复。错项目请求403。相同Idempotency-Key重发返回原Run，列表仅一条：Thread`46429c28-3616-4a73-9405-fdaaebce61d5`、Run`61631194-7bdb-4fee-9cfd-9489f4125c45`。

主动停止ID`076efc9a-fbf2-402d-a873-8e6805ed5cef`正式回执为`phase=stopped`、`execution_stopped=true`、`has_pending_interrupts=false`，回查Run为原生终态`interrupted`。该终态是取消完成，不表示仍待审批。证据在本机`.local-stack/boundary-stop-results.json`；保留报告中的checkpoint/progress unavailable，不推断未收集到的过程。

## 真实超时与审批恢复

远端`.local-stack/timeout-probe.py`以`timeout_seconds=1`及长纯文本合成输入触发真实超时。Thread`73c0ec99-dda6-4ebb-9c61-de2c3703a275`、Run`ece00f15-c9dc-448b-be9e-a54f9777fba9`；Evidence为预期的failed，`errors=["run_timeout_cancel_confirmed"]`，随后回查终态并取得stopped/true正式停止回执。证据在远端`.local-stack/timeout-probe/evidence.json`及`confirmed-stop.json`。不把该预期超时标成质量passed。

远端`.local-stack/approval-probe.py`使用review模式，仅允许`write_file`写`/workspace/work/eval-independent-approval.txt`，准确内容`independent-approved`。一次批准、两次Run，Evidence status=completed且errors为空；文件实际存在且内容一致。

Thread`14013f39-8188-43ba-89a7-03df9cadafa2`；Runs`6410be1f-9a6f-4831-8d1d-f357f7b578f4`、`26af78a1-0a6e-4ac6-96b4-c716dcad6912`的metadata均绑定目标摘要`b39c829c626e50ccf4bf013a6bb15551e4eeebb0070bf0fb7fbaac1b116c3415`。证据在远端`.local-stack/approval-probe/evidence.json`及对应日志。此补充探针验证实际审批、文件和目标恢复，不额外声称已评分或收全Trace。

## 自动回归与静态检查

| 检查 | 已观察结果 | 证据 |
|---|---|---|
| EvalFlow模块及根目录资产/出题相关回归 | 548 passed，1个既有弃用警告 | 远端`.local-stack/pytest-final-09.log` |
| Agent最终扩大API回归 | 163 passed、3 skipped、72 subtests passed；1项既有ACL断言失败 | 本机`.local-stack/api-last-09.log` |
| 原HEAD源码对照 | 同一ACL测试同样失败：预期仅title，实际还含服务端安全ACL投影 | `.local-stack/api-acl-baseline.log`；通过临时目录加载原HEAD源码，无修改运行服务 |
| 新快照有效策略回归 | 7 passed | `test_evaluation_targets.py` |
| Runtime最终相关 | 34 passed，5条已有原生库弃用警告 | 本机`.local-stack/runtime-last-09.log` |
| EvalFlow末次网络/初始化回归 | setup_local禁代理/重定向变更后22 passed；与548项范围重叠不相加 | 远端`.local-stack/pytest-last-network.log` |
| EvalFlow增量Ruff | 本专题新增0条；相关已改文件仍有51条旧诊断 | 远端`.local-stack/ruff-new-final.json`；原文件与before/HEAD以规则及行内容比较 |

Agent API命令（本Worktree根目录）：

```bash
apps/platform-api/.venv/bin/python -m pytest apps/platform-api/tests/test_evaluation_targets.py apps/platform-api/tests/test_evaluation_workbench.py apps/platform-api/tests/test_evaluation_materials.py apps/platform-api/tests/test_evaluation_receiver.py apps/platform-api/tests/test_evaluation_entry_retirement.py apps/platform-api/tests/test_evaluation_assistant_control.py apps/platform-api/tests/test_run_requests.py apps/platform-api/tests/test_runtime_delegation_contract.py apps/platform-api/tests/test_runtime_thread_authorization.py apps/platform-api/tests/test_thread_acl.py -q
```

唯一失败为`ThreadAclTest::test_new_thread_ignores_supplied_identity_and_acl`，预期metadata只有title相关字段，实际还带服务端安全ACL投影；原HEAD源码临时目录对照复现，未改无关ACL实现。`test_evaluation_targets.py`有效策略相关7项通过。材料测试随机fixture误判说明见上文，不将固定fixture等同产品隐私误判修复。

Runtime命令（本Worktree根目录）：

```bash
apps/runtime-service/.venv/bin/python -m pytest apps/runtime-service/tests/observability/test_evaluation_target.py apps/runtime-service/tests/observability/test_execution_evidence.py apps/runtime-service/tests/observability/test_evaluation_environment.py apps/runtime-service/tests/runtime/test_evaluation_maintenance_auth.py -q
```

EvalFlow命令（远端Worktree根目录现场执行）：

```bash
.venv/bin/python -m pytest tests/eval_platform tests/test_authoring_api.py tests/test_work_items.py tests/test_work_item_results.py tests/test_authoring_assistant.py tests/test_work_item_retention.py -q
.venv/bin/python -m pytest tests/eval_platform/test_local_setup.py tests/eval_platform/test_network.py -q
git diff --check
git status --porcelain -- mlflow/
```

本机关键新增文件定点Ruff通过；gateway/Runtime webapp/factory/capabilities范围检查`.local-stack/ruff-last-scope.json`为[]。末次再查targets实现、材料/targets测试及Runtime目标实现4文件，全部通过。远端29个Python文件Ruff按规则和源行内容比较，HEAD原59条、当前51条、新增0条；没有顺手修剩余旧诊断。两端diff检查通过，新文档链接均可解析；FEATURES中4条旧坏链在HEAD已存在，未改无关链接。末次核对保存于两端`.local-stack/closeout-09.json`。

## 整体验收与保留边界

09整体验收在独立双Worktree通过，5项任务状态只在09专题维护。当前/历史入口、跨机运行和回执、到期独立题库、普通执行者撤权、配置漂移、幂等、审批恢复、主动停止和超时均有真实证据。远端同步说明为`docs/projects/20261112-agent-evaluation-system/20261118-independent-deployment.md`，配置见其`docs/guides/agent-evaluation.md`。

开发验收时主API2142与本WT API24138健康200/ok，主Web3000与本WT Web26007为200；Runtime8123/24493健康端点返回401是原认证边界。远端主5000、隔离5011及外部9128当时健康200，上游mlflow/无改动。随后按用户追加授权完成提交/合并/推送并回收隔离资源，详见23记录；浏览器scope已关闭。

未做生产HTTPS、容量/性能、独立盲评或完整EvalFlow UI回归；EvalFlow无UI构建，题库生命周期用真实authoring API验证。08原任务仍5done/2partial，真实多页及全栈回退按用户决定回main继续原范围验收，不能因09通过改成整个历史项目完成。新契约不兼容旧服务，主环境验证前需要共同更新配置和运行进程；原隔离开发隧道已删除。
