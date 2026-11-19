# 用户委托 AI 复核、成功新运行与联合验收

> 本文保留Task1–4开发阶段事实；后续合并、验收和清理以[交付记录](05-delivery-and-cleanup.md)为准。原Worktree私有证据已归档至 sshmy1:/opt/mlflow-eval-platform/.local-stack/deliveries/20261119-universal-authoring/pre-merge-evidence/，下述相对日志路径以此为根。

2026-11-19，适用本项目Task1–4原开发批准范围。用户明确同意生产预算状态最小修复，并要求由 AI 完成业务审核与采纳。AI 据此执行完整业务、来源、安全及发布检查，记录委托身份；没有将其改称独立真人审核。唯一任务状态见 [tasks.md](../tasks.md)，本文只保存证据和边界。

## 授权后的业务复核与发布

文本题完整提供“周一至周五09:00至18:00、周末休息”的规则，独立预期由该规则推导，不照抄旧助手回答。文件题完整内联 YAML，按 `replicas=0` 解释无 Pod，保留不修改文件及不得断言镜像故障的标准。它是内联文件内容的历史评分题，不是实际上传文件或来源 Agent 实际推理。

AI 检查原候选采纳审计及发布操作，确认文本修订1无需重写。文件修订2的 `max_tool_calls=20` 无素材依据且未配工具预算指标，故只删除该字段；另更新 proposal 的 changes 说明，经正常 `edit` 和 `approve` 命令形成修订3/题库v2。检查证明其余 case 完全一致，发布没有创建 task，旧版 hash 未变。

| 资产 | 核对的修订 / hash | 独立发布 |
|---|---|---|
| 文本原采纳题 | 修订1，`1f0bc085b00c6d3f3c11a169bb1c06bdad92b84e4480f802788eb6fb91ca3a68` | `d-25b57ad773254b1fb13c814e22ef3db5`，v1 |
| 文件复核题 | 修订3，`5da86ea0a9c069d860d2c740dc3fb81717b2bc34020bb06354612ce0ccbf7ae0` | `d-83a38e60ea614139a359ddece2de3f6d`，v2；操作 `ea26dcc7-3a70-43e9-8e62-84ff4107bd38` |
| 文本显式运行题 | 修订3，`9438e720e3a8ef91f06f392d9f29d8e2b1aa2fa37245c8b9a6412646cd221bbe` | `d-f601cc557b884c1f8b74f6b25adefd41`，v3；业务标准保留，切换 isolated 并加入工具证据指标 |

第12批固定十题也由用户委托 AI 逐项复核，首稿结构及业务10/10、最终10/10；没有候选修复样本。原模型输出、全部12批失败及原复核记录保持冻结，追加 `user-delegated-quality-review.json` 记录本次授权与结论。详细题目见[复核材料](03-human-review-materials.md)。

## 预算状态修复及成功新运行

用户批准后，备份两端预算状态行，仅将 Platform 租户 `__default` 一行 revision0→2，再由原生 BudgetService 走签名接口同步。Final 只读再查：Platform revision/synced_revision=2/2、last_error=null；Runtime revision=2，策略仍为空。预算规则、历史用量、费用与 Runtime 账本未手工修改，未关闭守卫或重启服务。修复过程与首版导入失败见[预算记录](02-production-budget-precondition.md)。

通过真实认证 ASGI 平台入口、实际 HTTP Agent API/Runtime/EvalFlow 和真实模型，正常显式新建任务；不是浏览器或全程 HTTP 平台入口验收。

| 证据 | 实际结果 |
|---|---|
| 新任务 | `a9ca7536-0828-43d5-985d-461bada1a7ee`，operation completed，task passed，gate.exit_code=0，errors/failures为空 |
| Session | `cf4f647f-b068-4ce5-a26e-d73524ef2cad` |
| Runtime Run | `3cfdab07-a2c1-4e09-b376-8432aaa232bf`，正常平台接口回读 status=success |
| Trace | `tr-db5ebd2afe90d74305979827993739c0`，正常受控 session 接口回读 state=OK，21 Span可读 |
| 收集清单 | expected/received Run完全一致，missing=[]，complete=true、query_complete=true |
| 目标绑定 | evaluation-target/v1 的 spec、agent/resource/config hash、两服务包清单一致；Trace的项目、graph、model、Run、Session及Runtime包hash对应同一目标 |

实际回答：“不能。规则规定服务时间为周一至周五 09:00—18:00，周末休息；周日属于周末，因此无法获得人工服务。”

BusinessFacts、EvidenceBoundary、RecommendationGrounding 各0.8；ConversationalGEval、ToolCorrectness 各1.0，均达到原阈值。回答未额外引导工作日联系，评分原因保留该不足，没有把通过写成满分。工具项1.0仅对应本题无需调用且实际无工具调用的证据，不证明其他工具能力。未配置预算策略的 `budget_policy_not_configured` 警告准确保留，不是再次同步失败。

原预算失败任务 `1b3f422b-4860-4d76-9fa6-5c31191a6af0` 没有回答/Trace的事实不变；此次新任务没有覆盖它。

## 联合整体验收（Final）

2026-11-19 12:57（Asia/Shanghai）另执行 `verify_joint_final_v2.py`，重新认证后正常读取两类资产、历史混合评分、成功Runtime Run与受控Trace；没有再次启动模型或修改业务资产。结果 `joint-final-summary.json` 为 passed。

- 两类候选采纳审计存在，复核版本及发布 hash 一致；原文件修订2、文本修订1和全部旧操作可读。文件新版仅删除无依据次数上限，发布未产生任务。
- 两个来源线程的 Run 列表仍为空，历史评分及出题没有重跑来源。历史任务 `f4793b4a-9bb3-4f95-b07c-4eddd7c9071f` 四项文本各1.0、工具缺证据error、整体error仍可读，没有掩盖缺失。
- 新任务回答、Session/Run/Trace和目标绑定通过上述正常接口回读核对，预算版本及同步状态持久正常。
- 18份源码/测试/脚本哈希与 `final-static-checks.json` 一致，第12批冻结源码也一致。复用同版本 **687 passed、21 warnings、23.18s** 回归证据，本轮数据修复及资产复核阶段未修改产品源码，不机械重跑整套测试。另执行 `git diff --check` 通过，上游 `mlflow/` 仍无改动。
- 回读应用包/私有配置回退证据：16份题库及Run文件hash保持，配置逐字节恢复；没有数据库迁移或数据库回滚。所属进程测试、不可达目标及安全/权限回归复用相同源码的阶段证据，不冒充本轮重新执行。
- 四项生产服务的 MainPID、NRestarts、ActiveState 与预算修复前快照完全一致；5000/5011健康均200。生产EvalFlow仍 MainPID=2115014、NRestarts=0；未生产重启或部署。

全部当前范围必要条件满足，Task 1–4及实施准备完成。文档回写后再核对任务、README、CONTEXT和两仓摘要一致；对应证据在私有 `e2e/final-document-checks.json`。

## 保留的临时脚本失败与边界

业务复核首版把“期望副本数”作为连续字面断言，而真实标准为“期望Pod副本数”，在任何edit/publish前失败；正常再读确认文件仍修订2后，v2修正断言再执行。联合验收首版混用了命令名approve与持久操作intent=publish，只读筛选断言失败；核对原操作结构后，v2按真实intent通过。两次原脚本与日志保留，这些是检查脚本问题，没有改产品或伪造资产以满足断言。

私有证据根目录：`sshmy1:/opt/worktrees/evalflow-universal-authoring-20261119/.local-stack/universal-authoring/`。本轮关键文件在 `e2e/`：`budget-repair-summary.json`、`ai-delegated-review-summary.json`、`file-ai-reviewed-published.json`、`new-run-v3-summary.json`、`final-text-read.json`、`final-file-read.json`、`final-runtime-run-read.json`、`final-session-trace-read.json`、`final-services.json`、`joint-final-summary.json`。不将凭据、配置或原始Trace入仓。

本次开发Final时尚未执行Git提交、推送、合并或生产部署，后续交付见05记录；未执行浏览器完整验收、独立真人/盲评、大规模压测或任意新图执行接入。未来Git交付需整合生产主仓外部提交 `10d400a` 的权限修复并对整合版本回归。没有对应本项目待毕业的标准草案，不修改无关标准状态。十题单模型冒烟不代表普遍稳定性，出题更高输出/超时上限可能增加等待与开销，供应商未返回该批费用。
