# 09代码交付、既有功能保留与隔离资源回收

日期：2026-11-18。用户确认本需求开发完成，授权停止本次服务、提交并推送Worktree、合入主工作区、清理Worktree和测试数据库；未验项目回到main后继续验证。唯一任务状态仍在[09专题](../09-independent-deployment.md)，08未验条件不改成已通过。

## Git交付与主分支保护

Agent主工作区为`/Users/<name>/PyCharmMiscProject/ai-agent-platform`。交付前main为`b067fc1dd5c6e09c8cf7ae4ddd2603612f62d16a`，已含前序评测清理、后续聊天、用量看板和超级管理员权限改动；Worktree起点为`7081ae3e`。没有用Worktree目录覆盖主目录。

Agent实现提交`2f13a76e`先推到`origin/feat/evalflow-independent-deployment-20261118`，在Worktree三方合入最新main形成`9972a0b50cb498e3435e04192e44b9ae9d720d55`，回归后再次推送分支，再将主工作区main快进到该提交并推送origin/main。分支远端保留作交付记录，本地分支和Worktree已回收。

main独有的36个应用文件逐字节核对保留。合并结果相对原main只有13个本次API/Runtime/测试与服务规范文件变化，前端、IAM及用量看板没有被旧Worktree反向覆盖。对应精确路径与结果在主工作区私有`main-preservation-check.json`。

EvalFlow在`sshmy1:/opt/mlflow-eval-platform`现场交付。原main为`acfc89a`，主目录尚有前序08已批准但未提交的清理代码；先限定11个源码/测试/文档路径提交为`4fec81b578f3f04eda301b7e75c99b9a46372d7c`保留现场。未跟踪的旧环境备份移至主目录私有`.local-stack/backups/`，未加入Git。

EvalFlow Worktree实现提交`2e93ff502335e01d846ea375e0ff8fc68455c846`先推同名远端分支，再合入上述main，形成`9fd76d4dbc31f7fb751219f11841d611a74442da`。远端现场回归通过后，主目录main快进到该提交并推送origin/main。原多Worker登录修复、Copilot、诊断专家和web目录保留，上游`mlflow/`零变更。

冲突按具体段落处理：两端文档保留09已验证的新状态及既有无关功能记录；EvalFlow命令入口保留现有签名/调用者准入，采用09的准确远端origin校验。Agent自动合并漏掉新接口所需的`get_runtime_gateway_service` import，已补回并通过提交钩子和API回归，没有放宽权限。

首次Agent提交钩子还发现前序测试模块重复导入setup fixture；复用main已有conftest注册并移除重复导入。Ruff/Prettier自动格式化本次相关文件后重新提交，未跳过钩子。失败与自动修正均保留在执行记录中。

## 合并回归

以下在已合入最新main的Worktree代码上运行，未重新启动模型服务或伪称主环境E2E通过：

| 检查 | 结果 | 私有证据文件 |
|---|---|---|
| Agent API与IAM相关11个文件 | 173 passed、3 skipped、84 subtests passed；同一项既有ACL断言失败 | `agent-merge-api.log` |
| Runtime目标/证据/环境/维护权限4个文件 | 34 passed，5条已有原生库弃用警告 | `agent-merge-runtime.log` |
| 前端入口、路由、侧栏、历史/分支及用量看板 | 9套47 passed | `agent-merge-web.log` |
| 前端vue-tsc | exit 0 | `agent-merge-types.log` |
| EvalFlow评测模块与根目录资产/出题回归 | 548 passed，1条既有Starlette WSGI弃用警告 | 远端`evalflow-merge-regression.log` |

API唯一失败仍为`ThreadAclTest::test_new_thread_ignores_supplied_identity_and_acl`：旧测试期望只有title相关metadata，实际还带服务端安全ACL投影。原HEAD隔离对照已复现，未修改无关ACL实现。用量看板测试有既有loading prop类型警告，测试通过不等同该警告已修复。各组与先前测试重叠，不累计为唯一样本总数。

API命令在22记录所列10文件基础上追加`apps/platform-api/tests/test_iam_policy_engine.py`；Runtime和EvalFlow复用22记录中的完整命令。前端执行：

```bash
pnpm --dir apps/platform-web exec vitest run src/modules/evaluation/EvaluationMovedPage.spec.ts src/modules/evaluation/components/PickSessionMaterials.spec.ts src/modules/evaluation/useEvaluationCapabilities.spec.ts src/modules/chat/components/ThreadActionsMenu.spec.ts src/modules/chat/components/ChatThreadSidebar.spec.ts src/router/routes.spec.ts src/modules/usage/pages/UsageDashboardPage.spec.ts src/modules/chat/history-view-model.test.ts src/modules/chat/branching.test.ts
pnpm --dir apps/platform-web exec vue-tsc --noEmit
```

真实模型跨机证据来自22记录中的隔离开发版；合并后的版本完成上述自动化回归，尚未在主环境完整运行。没有以Git合并代替服务升级或生产验收。

## 服务、数据库和Worktree清理

停止Agent隔离栈`wt_136085e6852b`的Web/API/Runtime API/Worker及专属Redis；核对Web26007/API24138/Runtime24493/Redis25217均释放。远端先核对PID、进程命令和真实目录归属，再SIGTERM停止隔离EvalFlow5011；未启动的前端预留9138也为空。

仅取消本次本机65156→远端5011、远端46187→本机24138的两条SSH转发。SSH动态反向端口在控制通道登记的原始端口是0，按实际46187取消会报告未登记；改用原`0:127.0.0.1:24138`规格后取消成功，并远端回查46187已释放。原主环境38375→2142转发仍存在，未关闭共享SSH master。

Agent执行原生销毁命令：

```bash
bash "scripts/local-stack.sh" destroy --confirm "wt_136085e6852b"
```

销毁后只读查询PostgreSQL确认`wt_136085e6852b_platform`、`wt_136085e6852b_runtime`两个数据库及同名角色均不存在；专属Redis数据、Workspace、私有状态及资源登记删除。没有删除主业务数据库或共享PostgreSQL服务器。

EvalFlow根据登记root和SQLite文件头精确核对后，删除隔离`data/mlflow.db`及`.local-stack/auth.db`两个库及其可能存在的WAL/SHM/journal。没有保留本次测试数据库副本。确认无进程保留Worktree目录、端口已释放、源码已提交并合入main后，移除两端Worktree及本地分支；EvalFlow再通过`local_stack_worktree.py clean`移除所属失效登记。主服务数据与artifacts未清理。

## 证据位置与后续main验证

测试日志、原HEAD对照、权限/停止摘要、清理清单和结果，保存在两端主工作区各自私有`.local-stack/deliveries/20261118-eval-independent/`，不进入Git。关键结果为`agent-cleanup-result.json`、`evalflow-cleanup-result.json`，后者位于远端。旧Worktree内日志路径只表示原验证位置，现已不可访问；题库、Task、Run和Trace的合成数据库记录随授权清理删除，不再宣称可以打开原Task复验。

用户要求本次未验内容回到main继续：08真实多页与全栈回退仍在原任务区维护；完整EvalFlow UI、生产HTTPS、容量/独立盲评保持未验，不因需求开发交付完成改写历史验收。主环境验证前应共同升级两端私有配置与运行进程，删除正式EvalFlow配置的旧agent_repo，核对认证、地址、来源回调和Trace目标。本轮没有主动重启生产systemd、修改主数据库或发布前端产物。
