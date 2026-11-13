# T08、T10 Badcase 审核与复用演练（2026-11-13）

## Badcase 闭环

从评测报告收集候选，保留来源并去重；审核者补齐预期、审核状态与说明后发布新数据集目录。C04 候选经过独立证据核对并发布扩展版本，真实运行通过；v1 哈希保持不变。M01 裁判分歧仅作为候选，未直接变成黄金标准。

## 操作指南与演练

EvalFlow 的 `docs/guides/agent-evaluation.md` 已覆盖隔离准备、preflight、Agent 接入边界、题库/指标扩展、真实运行、历史重评分、基线比较、报告重传和 Badcase 审核。按指南完成 C04 收集、审核、发布、真实执行，全程没有修改 runner 核心代码。

首期不配置真实 CI。无密钥单测、Ruff、local-stack guard 和真实模型 CLI 可在本地执行；未来接入可信 CI 时再配置 runner secrets 与范围策略。

## 本次经验提案

- `eval_platform`、`tests/eval_platform` 的 root `conftest.py` 污染问题通过限定 pytest `--confcutdir` 避免；建议补入 EvalFlow 评测开发指南的测试命令说明。
- 审批恢复接口不能追加 metadata，必须在启动前建立 Thread 绑定；建议补入 EvalFlow 评测指南的接入检查项。
- 真实 holdout 一旦用于诊断评分器，就应标记为已暴露，并在后续周期重新冻结新 holdout；建议写入 EvalFlow 的评测流程经验。

以上为经验提案，按仓库规则需用户确认后再写入 `docs/lessons/`。
