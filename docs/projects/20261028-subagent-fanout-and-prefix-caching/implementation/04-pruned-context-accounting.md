# 整理压力与实际模型视图对齐

## 日期与范围

2026-10-29，T0.C。v2诊断发现的共同前置修复，两组均使用，不归功于委派。

## 原因

DeepAgents SummarizationMiddleware先计算历史压力，DearFlow的ToolOutputPruningMiddleware随后才折叠旧工具结果。原始历史已超过阈值时，即使最终模型视图很小，也会先调用摘要并通知前端“整理上下文”。单纯提前传入折叠历史会让摘要/归档只看到占位符，不能这样修。

## 最小修改

- `apps/runtime-service/src/runtime_service/middlewares/tool_output_pruning.py`：从原请求投影提取`filter_messages()`，保留开关、保留数量和最小字符策略。
- `apps/runtime-service/src/runtime_service/middlewares/conversation_offloading.py`：可接收实际使用的折叠中间件实例，仅计数时投影；原文仍由官方cutoff/配对/摘要/归档逻辑处理。手动整理与ContextOverflow恢复不改；没有注入折叠策略的调用者保持原计数。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`：每个主/子图共享同一折叠实例供整理计数、最终输入保护及实际模型视图使用。
- 隐藏摘要模型补`runtime_usage_purpose=summarization`，保留原model metadata；此前它在model节点内发起，账本可能误标primary。旧样本不回填猜测值，不能据此作精准主/辅助对照。

## 验证

- 先红：新三场景测试1 failed、2 passed，失败项正是开启折叠时仍自动整理。
- 修复后的上下文整理、折叠、Usage、DearFlow装配、PII组合：**105 passed、5 warnings（57.20s）**，日志`.local-stack/phase-pruned-count-tests.log`。
- 新断言覆盖折叠视图避免误触发、关闭折叠仍整理、手动仍整理、归档包含原始证据且没有折叠占位、原messages不变、隐藏摘要真实回调为auxiliary/summarization。
- 既有测试继续覆盖供应商精确overflow码、一次恢复、摘要/落盘失败、取消、工具配对、并行子图与PII。
- 修改文件Ruff及`git diff --check`通过。

## 真实采样版本

v2第一轮工具限额失败、第二轮诊断中断均保留，第三轮未启动。该组不作为完成的三次对照。v3在2026-10-29预登记：原提示词、固定SHA、xiaok模型、131072窗口、4096输出、1M兜底及全局100工具限制不变；公共15文件哈希保存在`.local-stack/relaxed-v3-manifest.json`。三次串行后恢复Pro委派并采集三次，不能与旧版本混算。
