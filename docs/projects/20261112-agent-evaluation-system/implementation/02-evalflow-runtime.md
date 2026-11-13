# T01–T03、T06 运行链路实现记录（2026-11-13）

## 交付

EvalFlow 独立扩展实现配置、契约、隔离 fixture、Platform API 适配、Trace 关联、历史评分、主动回归、门禁、MLflow 发布与失败重传。Agent 业务服务源码无需改动：现有 API 与 Trace 已提供所需证据，新增评测入口会扩大业务契约，故不实施。

关键代码位于 EvalFlow Worktree 的 `eval_platform/{config,contracts,run,gates,targets,scorers,fixture_server,setup_local,preflight,curate}.py` 与 `tests/eval_platform/test_evaluation.py`。操作手册为 `docs/guides/agent-evaluation.md`。实际运行数据只保存在两个 Worktree 的 `.local-stack/`，不纳入仓库。

## 关键兼容处理

- DeepEval/MLflow 官方桥接只传最后一段 Trace，无法完整表示审批前的工具链；StepEfficiency 依赖未填充的内部 Trace 字典。扩展从完整 Evidence 装配 DeepEval 公共输入，用 G-Eval 评价步骤效率，不修改上游。
- 隔离运行沿用正式 API、独立 Thread/Workspace 和受限合成 MCP；固定知识索引使用百炼真实嵌入。审批只对题库白名单内的文件写操作放行，取消请求带幂等键。
- Run、Trace、case、attempt 显式关联；历史评分不调用 Agent，主动回归才创建新运行。上传失败通过 `publish` 只重传结果。
- MLflow `log_table` 要求列式数据；已修正后端输入并完成真实发布。EvalFlow 页面可打开评测运行，关键界面截图见 `eval-run-r05-published.png`、`eval-assessment-run.png`、`eval-assessment-results.png`。

## 验证

首批隔离/契约测试 23 项通过；最终单元测试、Ruff 与上游 guard 的结果见项目 `verification.md`。真实单轮、多轮、审批、取消、检索均完成，Evidences 与 Run/Trace 精确关联。扩展范围没有业务服务改动，因此没有业务仓库源码回归项。

## 限制

DeepEval G-Eval 步骤效率 v2 与官方原生 StepEfficiency 不具数值可比性；替换指标版本需重新基线。测试只覆盖当前隔离环境和合成数据，不代表生产发布验证。
