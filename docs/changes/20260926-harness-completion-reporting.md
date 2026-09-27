# Harness 整单完成与汇报规则

## 背景

用户要求完成一组需求时，Agent 可能在单个 Task 或阶段结束后，以部分进度作为最终答复并停止工作。

## 改动

- `AGENTS.md`：规定先确定范围和验收条件，持续推进至整体 `done`；只有需要用户行动的 `blocked` 才允许提前结束并汇报。
- `.codex/skills/implement-feature/SKILL.md`：明确 Task Completion Card 是进度记录，不是整单完成信号。
- `.codex/skills/verify-change/SKILL.md`：明确 `partial`、`deferred` 不自动结束当前范围的工作。
- `docs/CONTEXT.md`、`docs/FEATURES.md`：同步 Harness 当前规则。

## 试运行修正

SSE 专项试运行仍在可推进任务未完成时以 `partial` 收尾，并提前写了 Final 结论。现要求结束前逐项检查未完成任务；缺少真实环境时先推进隔离验证，只有剩余工作确需用户提供条件或决定才按 `blocked` 汇报。`verify-change` 规定 Task 未完成时证据只写 Phase，不提前生成 Final 结论。
