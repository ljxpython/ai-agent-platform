# 反馈投影公平调度与验收接续

日期：2026-11-14。关联Task1.1/1.2、2.4、4.7；仅Phase，不是Final。

后续状态：本文件的held阻塞已在同日解除，新批次浏览器生命周期、撤权访问和重启验证见[07验收记录](07-browser-batch-lifecycle-and-fixes.md)。以下保留当时调度修复与浏览器阻塞事实，不作为当前浏览器状态。

## 问题、改动与验证

`EvalFlow: eval_platform/feedback_projection.py::tick` 原按固定目录顺序选最多10条，已关联记录每60秒重新检查，而tick每15秒执行。当旧记录超过40条时，前40条持续占满处理名额，尾部新反馈无法开始。

新增 `tests/eval_platform/test_feedback_projection.py::test_due_projections_do_not_starve_behind_periodic_link_checks`，使用50条旧关联和1条新反馈、固定目录顺序，先在原实现真实复现失败：8轮调度只访问40条，新反馈仍pending。改为在curation锁内读取持久化next_at并排序，逐项执行时重新加锁读取状态；每轮10条、总容量1000和既有重试/撤权行为不变，不新增内存游标。

修复后47项投影/批次/审核定向测试通过；最新EvalFlow全套241 passed、2个既有warning，Ruff通过。命令与日志（EvalFlow Worktree）：

```bash
.venv/bin/python -m pytest tests/eval_platform/test_feedback_projection.py tests/eval_platform/test_authorization_batches.py tests/eval_platform/test_curation.py -q
.venv/bin/python -m pytest tests/eval_platform -q
.venv/bin/python -m ruff check eval_platform tests/eval_platform
```

- `.local-stack/phase-projection-fairness.log`
- `.local-stack/phase-flywheel-tests-20261114.log`

此测试证明持久文件调度顺序及每轮限额，不冒充真实进程故障重启、全部运行信号补扫或生产吞吐验收。

## 浏览器与部署事实

接续前EvalFlow后端重启已正常结束并就绪；新调度修复通过测试后再次通过所属local-stack脚本重启后端，端口5011已就绪（PID69574）。浏览器原session `wyzz` / tab `794183476` 的控制检查返回ready=false、mode=held、revision71；sync明确拒绝。没有创建新会话或改控制策略绕过限制。

已保存并实际查看被动截图：Agent Worktree `.local-stack/browser-control-held-20261114.png`。31+16合成草稿仍在输入框，未发送。这只证明阻塞现场，不是审核/回归/撤权业务证据。前轮request-help已超时，本轮不重复同一帮助请求。

本轮末次检查仍为held/revision71；按browser-skill错误退出规则执行 `bsk close --session wyzz`，工具确认session已关闭。后续恢复时先核对保留页面和实际控制权，不复用旧context，也不重放草稿。此处blocked仅指浏览器验收，整体项目仍实施中，四专题其余待办未因此视为完成。

## 尚待验收

### 已补充的裁判正负对照

新增私有脚本 `EvalFlow: .local-stack/probe_calibration_controls.py`，只对明确标记的合成输入/输出调用当前TaskCompletion裁判，不调用Agent、不制造Trace/Run，也不向原生页面发布。这与implementation/05中的真实Agent历史重评分是两类证据，不能合并当成真实Agent检出率。

事前固定4个样本、2个家族、2轮、观察阈值0.7、每样本每轮2请求/整批16请求；无自动重试。Python算式和JSON解析断言给出fixture预期，人工标签仍为空：

| 合成对照 | 两轮结果 | 分数 |
| --- | --- | --- |
| 31+16回答47 | pass / pass | 1.0 / 1.0 |
| 31+16回答46 | fail / fail | 0.0 / 0.0 |
| 请求value为47的JSON，输出合法对象 | pass / pass | 1.0 / 1.0 |
| 同一JSON请求，输出拒绝提供JSON的普通文本 | fail / fail | 0.0 / 0.0 |

实际16请求、输入9,074 Tokens、输出3,201 Tokens，合计12,275。4个唯一样本、8次评分，不计为8个独立场景；阈值、同源偏差、多轮分歧和发布策略仍未批准。

证据：`EvalFlow: .local-stack/judge-controls-d7d0dbf6aa9e4d13b9b80a7970a31f54/` 内的plan、两轮报告、summary、human-labels.pending；汇总 `.local-stack/calibration-controls-result.json`。pending标签expected/reviewer/reviewed_at仍空，未代填人审。

### 剩余条件

原标签页恢复控制后继续新授权批次的聊天、反馈、授权导出、原生审核、冻结发布、回归、撤权及受限资料访问验证。线上质量巡检的资料用途边界已在专题01记录具体方案并请求人工决策；现有synthetic/regression授权不能直接扩大为原会话外发评分。其他缺口仍以四专题任务为准，未自动批准校准阈值、候选、生产路径或循环干预。
