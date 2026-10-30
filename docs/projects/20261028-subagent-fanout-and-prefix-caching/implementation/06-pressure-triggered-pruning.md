# 按工作记忆压力触发工具折叠

## 范围与问题

2026-10-29，T0.W。v4已修复最新批次提前折叠，但63次子模型调用仍不断读取来源；子输入峰值仅19,367 Token。只保留最近四条，即使窗口很空也持续丢弃已读证据，迫使模型在完成综合前反复读回。保护最新批次解决“第一次看不到”，没有解决“过早遗忘”。

## 最小修改

- `ToolOutputPruningMiddleware`增加内部`trigger_tokens`参数。低于触发水位时保持完整消息；达到水位后才复用原折叠函数，继续保护最新批次及本轮受限task报告。参数省略时保持原通用调用者行为。
- 压力估算复用已安装LangChain的`count_tokens_approximately`，包含system_message与tools Schema，不新增tokenizer依赖、模型调用或账本字段。
- DearFlow主/子图以既有安全输入预算的40%作为工作记忆水位，在85%摘要阈值之前先折叠工具历史。40%沿用现有保留量级、为估算偏差与下一批结果留空间；不是把dsh截图49%当作触发阈值。水位与真实供应商输入峰值分开记录，不声称精确计数。
- `ConversationOffloadingMiddleware._count_tokens`与最终模型入口传入同一system/tools与折叠实例；原文摘要、归档和Checkpoint不变。手动整理、真实ContextOverflow恢复不改。
- 无上下文治理配置的探测/旧调用者保持既有行为；不改产品Run总额度。

## 验证

- 新水位测试初跑2 failed（缺少trigger_tokens构造参数），不是已通过的行为回归。
- 实现后的pruning/offloading/装配组合68 passed、5 warnings（44.47s）；补充主/子图正式factory接线测试继续执行。
- 新测试覆盖低压力不折叠、system或工具Schema也能触发、原文不变，以及前序最新批次/本轮task保护。

## 诊断样本保留

v4 Run `e012aad9-bbb7-494c-80a4-b6cbda18f81f`由正式Web停止，未启动第二/三轮。status=interrupted、finalized=false、collection_degraded=true。67次已报告调用的已知用量790,458（主67,998、子722,460），不宣称完整账单；最终无报告。118份成功来源（子级111份）已校验哈希、固定ref与原文。原始数据留在`.local-stack/delegation-relaxed-v4-1.json`及audit/sources。

v4中途重启了采集器以避免自动开启下一样本，其基础设施before快照只覆盖后半段，完整v4资源基线另见manifest。Redis总错误回复增加1不自动等同OOM；后续新增按errorstat_OOM单独记录，不把无关协议错误当作内存拒绝。v5在修复与接线回归通过后另行预登记两组，不混入v4诊断。
