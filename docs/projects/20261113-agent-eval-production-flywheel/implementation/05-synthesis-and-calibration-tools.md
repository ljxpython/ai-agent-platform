# 有界合成候选与裁判校准工具

日期：2026-11-14。关联 Task 3.1、3.4、4.2、4.3。仍为 Phase，未完成人工审核或阈值批准。

## 实现

- EvalFlow `eval_platform/synthesize.py` 复用已有 `XiaokJudge` / `JudgeBudget`，不引入合成框架或移植 LightRAG。只接受1–5道 synthetic/v2/dev种子，每题最多4个候选、最多8轮；单题1次请求、整批5次请求，无隐式重试。
- 模型仅生成用户话术。fixture、断言、指标、审批决策和家族保持继承；结构不符、fixture引用丢失、重复/原文直接拒绝。结构通过不代表语义等价，改变数字、否定或权限仍必须由人审拒绝/修订。
- 候选始终 `pending`、审核人 `pending-human-review`；manifest保留种子hash、请求模型、提示词版本、家族数、用量、结构拒绝和错误。失败保留已生成内容与已消耗预算，停止后续请求，不用追加生成凑足题数。
- `curate.publish_reviewed()` 复用现有发布流程，支持明确的 approved/rejected及理由；拒绝项保留在manifest而不进入题库。漏审、全拒绝、生成题未填写审核人、重复题、家族跨split或v2发布关闭均不能发布。CLI发布也遵守v2开关，修复仅原生registry入口受开关控制的遗漏。
- `eval_platform/calibration.py` 从语义报告生成空人工标注模板；比较时要求完整人审字段和原执行证据hash。冻结评分器版本、阈值、比较键及评测器身份，分开统计重复试验数和唯一case数，保留error分母、TP/FP/TN/FN与逐题分歧。输出始终等待人工政策评审，不验证独立人审身份、不自动批准阈值。
- `run.evaluator_identity()` 将评测器包SHA256、六项已安装依赖版本、裁判入口指纹纳入比较键和manifest；启动后或运行中包变化按完整性错误处理。包范围较保守，包括整个eval_platform，不宣称无关改动仍可直接比较。旧报告继续可读，但没有新身份不能作为本轮校准的可比基线。

## 可复现命令

均在所属 EvalFlow Worktree 使用其已安装环境，配置/输出使用私有本地路径。

```bash
.venv/bin/python -m eval_platform.synthesize --config "<private-config.json>" --seeds "<synthetic-dev-seeds.jsonl>" --output "<new-candidate-directory>"
.venv/bin/python -m eval_platform.curate publish --input "<human-reviewed-candidates.json>" --output "<new-version-directory>"
.venv/bin/python -m eval_platform.calibration template --reports "<report.json>" --output "<new-human-labels.json>"
.venv/bin/python -m eval_platform.calibration compare --reports "<trial-1-report.json>" "<trial-2-report.json>" --labels "<completed-human-labels.json>" --output "<new-calibration-report.json>"
```

## Phase 实测

1. 合成工具/旧发布/registry组合：52 passed。真实5种子试验输出20候选，3家族，5请求、3,643输入+5,540输出=9,183 Tokens。全部待审，没有执行/发布候选。固定本地种子是开发者构造，不冒充独立人审或盲测。
2. 原执行 `f8f86ccec5b045a49c9201603e4f19dc` 的三条安全dev证据，在事前固定两轮、TaskCompletion观察阈值0.7、每题4/整批12请求预算下做historical评分；不重放Agent。报告 `4ff67a8bed2c47a586c35cea446ded76`、`dc4fd826c0014ab49909c21fdfcb5b10` 比较键相同，六次TaskCompletion结果均1.0/pass，共12裁判请求、12,907 Tokens。
3. 上述两轮只有3个唯一成功样本，不足以测量错误检出率或证明阈值合格；没有人工标签，未运行真实人机一致率计算。`calibration-human-labels.pending.json`保持空标签；不能用模型全pass替代人审。
4. 校准/评测器身份/部署定向15 passed，随后补了身份不一致负例；最新EvalFlow全套 **240 passed**、Ruff通过，日志 `.local-stack/phase-flywheel-tests-latest.log`。全部为本地Phase，不替代前端E2E或真实CI。

私有产物：EvalFlow `.local-stack/synthesis-development-20261114/{candidates.json,manifest.json,review.md}`、`calibration-trial-plan.json`、`calibration-trials-result.json`、`calibration-human-labels.pending.json`。未把凭据、私有配置或模型原始推理写入项目文档。

## 尚缺

- 合成候选逐条人工接受/拒绝、家族覆盖/新检出缺陷统计和原生新版本发布验证。
- 包含真实已知失败的校准样本、人工标签、各语义指标覆盖及事前批准的波动/阈值；两次成功样本重评分只是路径验证。
- 新授权批次 browser-skill 全链路仍受held阻塞；独立盲测/可信CI条件暂无。在线抽样、大盘告警和完整恢复仍按专题待办推进，生产路径保持关闭。
