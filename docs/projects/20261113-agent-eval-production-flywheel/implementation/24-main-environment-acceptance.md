# 主环境浏览器全链路验收（2026-11-18）

## 结论与适用范围

Agent 主环境与远端 EvalFlow 的业务主线通过真实浏览器验证：正常对话、两个会话转换入口、真实多页筛选与批量交付、通知跳转、平台登录、AI 候选与修订、采纳和手工保存、刷新恢复、单独发布、显式运行、结果查看及同证据重评。普通执行者交付与管理者单独授权也已验证。

08 的 Task8.3 已满足自身验收要求，更新为 done；Task8.7 仍为 partial，唯一剩余原验收项是 V8.7 的隔离全栈回退与再升级。没有对主环境做数据库降级或应用回退，也没有把此前仅 API 的回退演练当作全栈通过。09 的五项开发、隔离技术验收和交付状态保持 done。本次业务验收不代替生产 HTTPS、性能容量或独立盲评。

唯一进度来源仍是 [08](../08-agent-evaluation-entry-cleanup.md) 与 [09](../09-independent-deployment.md)，本文件只保存证据及边界。

## 实际环境及准备

- Agent main：`5e96b4d1d2d100f11ab687179ccda889a26cd248`；Web3000、API2142、Runtime8123。
- EvalFlow main：`681aa463be04e49e3d496d6bedf9d483649beb6e`；`sshmy1:/opt/mlflow-eval-platform`，内部5000、外部9128。
- 本轮仅用专用评测项目及合成会话；原38375回环 SSH 转发继续连接本机 API。没有共享 Agent 源码、环境文件或虚拟环境。
- EvalFlow 私有配置备份为 `.local-stack/backups/evaluation-before-main-acceptance-20261118130959.json`；按新 schema 只删除旧 `agent_repo` 字段，候选配置校验后原子替换并保持0600。没有修改模型连接或现有账号角色。
- 无活动任务后重载远端 `mlflow-eval` 与本机受管 Runtime API/Worker。本机 Platform API 使用原 reload 进程，没有为了重启而执行数据库迁移。

## 浏览器操作与实际结果

使用 browser-skill 的 `bsk`，scope `eval-main-20261118`、session `bwbl`；独立后台 Agent Window，没有操作用户标签、读取浏览器凭据或用脚本代替页面提交。已在结束时关闭 scope。

### 当前会话、修订、发布与运行

管理员在正常 Chat 中发送纯合成算术问题“8+9，只回复17，不调用工具”，回复17。Thread `1d087107-e578-4766-87e2-552cc6748aff`，普通 Run `b19c4852-34e2-4117-82f1-203193488518` 成功。

菜单只保留“转为评测集”和“从历史会话建评测集”。当前会话提交 `MAIN-EVAL-20261118-当前会话` 后，浏览器网络记录 POST `/api/evaluation/materials/send` 为202；弹窗关闭。通知是“资料已送达”，说明发布和运行另行确认，链接打开远端准确工作项 `51f6292c-e4a3-5ffb-a2c7-1125aa16b336`。

经正常平台登录后，EvalFlow 显示1段2消息。AI 首稿仅为候选，草稿仍v0；点击采纳保存成为v1。通过 Copilot 仅为题号 `MAIN-EVAL-20261118-001` 增加第二轮“再加1”与预期18，查看差异后采纳为v2；手工改为“沿用上一轮结果，再加1，只回复结果数字，不调用工具。”并保存v3。真实刷新后，身份、修订3和手改内容仍在。

单独确认用途并发布题库v1，未启动 Agent；发布后 Runtime Run 总数仍99。数据集 `d-5090f36d961640d8a5c6cb3125aa944e`，发布操作 `8bc13b79-a90c-47fe-a33f-bdad9c818823`。随后只点击一次“运行这个版本”，任务 `2e6b1e82-f8bc-4803-ab21-ad4675a90386` passed，1题2轮。

| 运行证据 | 实际结果 |
|---|---|
| Session | `9b9238a3-6606-458f-8a46-e53677c9d60d` |
| 两条 Run | `625c34a3-8b7e-44a7-a025-13e290070d12`、`4e669d10-d7ed-4052-a8ed-78938303cc74` |
| 两条 Trace | `tr-df3629ba67134986f889eb7bb93980f0`、`tr-00ec37e234901bf39aff8caaed644606` |
| 回答 | 页面17、18；证据原文第一轮为换行加17，按现有评分规范通过 |
| 评分 | turn_expectations=1、tool_budget=1、TaskCompletion=0.7，三项通过 |
| 实际执行身份 | 两条 Worker 回执的 evaluation_target_hash 均为 `78df5fb5409f390b34b14ab908ee09d07581baaa1934f01f2ee398c6ce79bd79`，与冻结目标一致 |
| 完整性 | trace_collection.complete=true、deployment.matches=true、runtime_package.matches=true |

结果页真实展开并查看两轮对话及三个评分。随后点击“用当前发布标准重评（不重跑）”，任务 `873686b4-48fd-439a-8aef-ec72e1a2af06` passed；source_task_id 指向原任务，Session、Run、Trace 与 outputs 均逐项相同。两项代码指标仍1，模型指标变为1；原0.7评分保留，说明模型裁判存在波动，不能当作确定性质量认证。两次任务都有 `budget_policy_not_configured` 警告，没有把预算检查记成通过。

### 历史选择与真实分页

原主项目可见会话不满100，不足以证明多页。通过正常 API 新建101条空合成会话，名称 `MAIN-EVAL-PAGING-20261118-000` 至 `100`，不调用模型，逐条登记ID。

浏览器从历史入口首批加载100条，点击继续后累计110条且ID去重。选择 idle 状态和当地时间2026-11-18 00:00至23:59，首批100、继续后累计103；当天以外会话被排除，页面没有好差评筛选。选择追加页中的本轮会话与上午合成会话 `777dd271-8d41-4cf2-9164-12b06c7ca2f2`，进入统一弹窗并提交 `MAIN-EVAL-20261118-历史分页批量`。

浏览器网络为202，完成通知直达 `ea4cede0-2199-5e3c-808a-b770d94802df`。远端和页面均核对为这两个 Thread、2段4消息；AI作业completed，产生两道待采纳候选，草稿仍v0，没有自动采纳、发布或运行。

### 普通成员交付与管理者授权

使用原获批的专用执行者账号正常浏览器登录，未增加或修改角色。读取其已有合成 Thread `65ff3bc4-a4d4-4f5d-807b-403a097bf572`，提交 `MAIN-EVAL-20261118-普通成员交付`。

提交弹窗明确“等待项目资料负责人确认 AI 用途”，网络返回202。工作项 `ab104965-da61-5063-acee-291127bc47f2` 为awaiting_authorization，1段资料、0个AI作业、空grants。管理员在 EvalFlow 列表打开它，页面禁用生成；单独点击授权后资料可见、生成可用，再点击生成得到结构有效候选。该条目没有自动发布或运行。

### 旧入口与 HTTP 权限负例

普通成员浏览器访问原 Agent 详情 URL，显示“评测操作已移至 EvalFlow”，提供原条目的受控远端链接，没有白屏或自动创建。聊天与导航无旧评测操作。

用正常登录取得的独立短期 API 会话补核负例，结束后注销该 API 会话；没有提取浏览器token。结果：

| 场景 | 实际结果 |
|---|---|
| 执行者试图自动授AI用途 | 403 |
| 执行者试图grant | 403 |
| 错项目签发命令 | 403 |
| 提交同项目另一用户的私有会话 | HTTP200的业务failed，materials空、无item_id，没有导出资料 |
| 恢复早先原request_id | 200/reused=true，仍是 `f23d706f-b9b4-51fa-a032-912abd1fdfb9`，不创建副本 |
| 旧创建入口 | 404 |
| 旧generate代理 | 400/evaluation_action_invalid，明确要求去EvalFlow |
| 错签名到EvalFlow命令入口 | 409“平台已拒绝此资料访问。”，未执行命令 |

脚本最初把退役动作和错签名分别预期为404/401，而实际契约为400/409；另一次漏加载脚本运行环境的.env而未发出远端请求。修正验证脚本后八项通过，没有为匹配断言修改产品错误码或放宽权限。

## 现场发现与修复

### 集中实验未初始化

首次发布停在publishing，错误为“数据集不属于集中评测实验。”。配置指定 `Agent 评测中心`，但当前 PostgreSQL MLflow 中没有该实验，新建的本轮数据集没有任何实验关联。

通过正常 MLflow 客户端创建配置指定的实验ID16；校验本轮数据集名称、work_item_id及无关联状态后，仅通过原生add-experiments接口关联该数据集。没有迁移其他题库、修改已有实验或绕过权限。原发布操作自动恢复，未重新提交、未产生重复数据集。

这是当前环境初始化问题。本轮没有新增自动创建实验逻辑；新部署启用发布前应确认配置指定实验已经存在。记录不能被解读为新部署无需初始化。

### 发布恢复后残留旧后台错误

发布和首次运行已成功，但工作项的background_error仍保留旧实验错误，页面误报。修复位于远端 `eval_platform/work_item_jobs.py::advance`：在取消完成、发布成功及成功读回任务状态时，移除已恢复的后台错误。没有清空历史任务错误或修改评分结果。

补充 `tests/test_work_items.py::test_publication_retry_clears_background_error`，覆盖发布恢复、运行中、完成及取消四种状态，并检查沿用数据集、发布不启动Agent。现场执行：

```bash
.venv/bin/python -m pytest tests/test_work_items.py tests/test_work_item_results.py tests/test_work_item_retention.py -q
```

结果39 passed，2.81秒。Ruff两文件仍13条原有诊断，按实际diff新增行核对为0条；git diff --check通过。执行既有 `bash scripts/local-stack.sh guard` 通过，上游mlflow/零侵入。修复仅3行产品代码及回归测试；验收结束时尚未提交，后经用户明确授权，已在sshmy1提交并推送EvalFlow main（e7ff155）。Mac镜像通过pull同步，没有反向覆盖远端。

无活动评测任务后按既有授权重载服务，内部health200。真实重评经过新成功分支后，background_error消失，页面恢复正常；原运行及新重评结果均保留。

## 资源回收、证据与未覆盖项

101条空分页会话通过正常API逐条核对名称后删除，账本101/101标记deleted。保留本轮业务验收所需的实际合成会话、题库、任务和Trace；没有删除主数据库或原业务资料。结束时远端无queued/running/cancelling/waiting_for_approval任务。

Web、Platform API的 `/_system/health`、Runtime `/ok`、EvalFlow `/health` 最终均200，API database_ready=true。探测API的 `/health` 得到401，是误用受保护路径，随后按真实公开健康路由复核；没有改鉴权。服务重载短窗口中的暂时不可用提示保留为过程事实，后续读写恢复，不记成持续故障。

私有证据在本机 `.local-stack/main-eval-acceptance-20261118/`，含01–40浏览器快照/截图、main-negatives.json、分页创建/回收账本与final-health.json；远端 `.local-stack/deliveries/20261118-eval-independent/` 保存main-error-recovery-tests.txt和main-run-evidence.json。截图38真实展示17/18和三项评分；39显示已恢复页面。文件不含认证密钥，不提交私有配置或原始DOM。

本轮未重新模拟主环境授权到期、撤权/审批/停止/漂移故障，复用09在同一实现上的隔离实证；没有把它们说成主环境新测。来源到期仍用题库的结论来自09专库验证，没有为本次验收修改主环境授权有效期。V8.7隔离全栈回退与再升级仍未完成；生产HTTPS、正式容量/性能、真实CI及独立盲评保持原范围，不因业务主线通过自动完成。

## 文档核对

已将进度写回08唯一任务区（6项done/1项partial），09保持5项done，并同步项目README、两仓CONTEXT及Agent FEATURES/CHANGELOG。任务状态、勾选与摘要已回读一致，两仓git diff --check通过，本轮新增相对链接均可达。全量链接检查另外发现FEATURES中4条原HEAD已存在的失效链接，未扩大本轮范围修复；未把它们计成新增问题或产品失败。没有对应本轮需要毕业的跨服务标准草案。

## 用户确认的经验与Git交付

2026-11-18用户明确同意沉淀经验并提交到代码仓库。评测经验按既有归属写入EvalFlow `docs/lessons/eval-architecture.md` 第8节，并更新其索引；内容为契约配置与运行进程同步、集中实验初始化、后台恢复后的页面及原执行证据核对。Agent经验索引更新引用，不维护第二份。

EvalFlow在sshmy1以 `e7ff1557d928f72165342e9b9db4bd9609c6991f` 提交并推送origin/main；读回远端ref与HEAD一致，Mac镜像以 `git pull --ff-only origin main` 同步。本仓本次文档提交包含原任务、摘要、上下文、功能/变更说明与本记录，实际提交号以本次main日志为准。私有配置、账号、原始DOM、业务资料及临时测试脚本均不纳入提交。

本次仅交付已验代码和文档，不重演模型链路、不新增生产部署或服务重载。08的V8.7及原HTTPS/容量/独立盲评未验边界保持不变；后续服务器部署另行讨论与确认。
