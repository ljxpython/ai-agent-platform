# 为有界研究保留实际交付轮次

## 2026-10-29 / T0.D

v5首轮`b741e7ed-102b-42ef-8706-0158d9d02696`已终态：969,120 Token，primary 4次/63,639 Token，subagent 45次/905,481 Token。主输入峰值16,801/131,072=12.8%，root自动整理观测0次。三个真实code_explorer namespace读取99份来源，全部来源102份的固定ref与哈希通过。完整账本对平、finalized=true；最终只有55字符预算提示，任务失败，不计为有效交付。Redis自采样登记起OOM增量0；原采集器在终态前被停止以防自动启动后续样本，补采文件明确区分终态快照与预登记快照。

## 根因与最小改动

- 父级把三个问题扩成了package.json/exports/依赖、源码常量、各provider权限等审计清单；只有一个子任务给出长报告且被既有输出保护落盘，另两个消耗共享预算后未交付。
- `ExecutionBudgetMiddleware`先前仅追加收尾提示，没有把最后一次调用留给报告，模型可继续选工具直至上限。复用已有Run/Thread计数，在最后一次允许的模型请求上清空tools/tool_choice并追加既有收尾提示；早期预警继续允许工作，不修改Token账本、权限、工具注册和持久消息。
- `dearflow_agent/agent.py`子模型上限24→8、预警提前2次，父级上限不变。代码探索角色声明有界交付、最多5条及3600字符目标；父提示词约束只拆原问题，不扩成源码审计。字符目标仍是模型指令，超长报告由既有工具输出保护处理，不能声称完全硬保证。

## 文件与检查

源码仅在隔离Worktree；涉及`middlewares/execution_budget.py`、`dearflow_agent/agent.py`、`prompts.py`、`subagents/code_explorer.py`，以及`test_execution_budget.py`、`test_agent.py`。

新增同步/异步、Run/Thread最后一轮工具关闭与提前一轮工具保留测试；装配断言确认两种委派模式下所有子角色上限8、预警2。先红6 failed/4 passed（12.97s），原因分别为最后一轮仍带工具、子上限仍为24。修复组合97 passed/1 skipped/1 failed，残留失败是此前T0.L加入github_query循环检测后旧组合白名单断言未同步；同步后预算/装配复测53 passed、5 warnings（47.70s）。修改文件Ruff通过；完整关联门禁及v6真实效果继续验证，不把v5混作成功样本。

未更改原始用户提示词、固定SHA、模型、单次输出、1M测试兜底和五项证据门槛；没有向模型提供答案或目标文档行号。
