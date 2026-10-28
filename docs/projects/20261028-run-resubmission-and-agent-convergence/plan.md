# 方案设计：运行异常重投与 Agent 代码剖析收敛治理

## 1. 背景与问题定义

在会话 `99bad502-3c33-4a1b-acc0-bd6881ac6811` 中，用户要求 Agent 对 GitHub 仓库 `ljxpython/ai-agent-platform` 进行深度架构与代码资产剖析，暴露了两个严重问题：

1. **前端错误静默自动重投 Bug**：
   - Run 1 在单轮执行中耗尽 50 次模型调用上限挂掉（`ModelCallLimitExceededError`）；
   - 前端 `ChatSession.vue` 的 `session.send` 返回 `false`，降级分支未经任何用户确认，盲目调用 `submitQueuedMessage(content)` 将失败的 Prompt 再次作为队列排队消息（`multitask_strategy: "enqueue"`）二次提交给后端，拉起了 Run 2。用户感知为“模型自己把上一次 Prompt 又重发了一遍并陷入死循环”。
2. **Agent 本地与代码资产剖析死循环**：
   - Agent 缺乏代码与本地文件调研的预算约束与自顶向下（Top-Down）收敛指令；
   - 模型陷入微观强迫症求证（例如为核验 README 中的一句话，频繁通过 `execute` 编写临时 Python 脚本递归匹配数十兆的文件树 JSON），单轮耗费 50 次模型调用和 1100+ 步仍未产出成果。
3. **预算告警与模型收尾脱节**：
   - 现有的 `WRAPUP_INSTRUCTION` 为纯英文，在中文长思考链（Reasoning）中易被模型忽略；模型在最后 3 次告警期仍继续调用工具，导致直接撞上 50 次硬上限抛异常暴毙，前面所有产物白费。

---

## 2. 总体架构设计与改动方案

### 方案 1：前端移除盲目重投降级逻辑（Surgical Fix）
- **修改位置**：[ChatSession.vue](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/platform-web/src/modules/chat/components/ChatSession.vue)
- **改动原则**：
  - `session.send` 失败（`!ok`）时，**绝不自动调用 `submitQueuedMessage` 重新派发**！
  - 只有当网络出现瞬时 409 / 正在排队时，由用户的明确操作控制；对于执行中断、模型超额或失败，恢复草稿（`submittedDraft`）或保持界面状态，允许用户人工审阅或调整后再决定是否重发。

### 方案 2：Agent System Prompt 增加代码与本地文件调研收敛准则
- **修改位置**：[prompts.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py)
- **改动原则**：
  - 对齐现有联网调研约束（3~5 次搜索、2~4 篇精读），增加针对**代码库、本地项目与架构剖析**的收敛约束：
    - 坚持自顶向下（Top-Down）架构抽象原则，严禁微观递归、严禁写脚本对海量文件遍历扫描；
    - 代码/文件探索工具调用严格限制在 5~8 次以内；
    - 一旦掌握顶层拓扑与关键模块职责，必须立即停止顺藤摸瓜，迅速转入产物编写与输出交付。

### 方案 3：强化模型预算逼近时的收尾感知（Graceful Wrapup）
- **修改位置**：[execution_budget.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/middlewares/execution_budget.py)
- **改动原则**：
  - 为 `WRAPUP_INSTRUCTION` 增加中英双语的明确强制收敛指示：“当前执行预算即将耗尽（剩余最后几次调用）。严禁启动新的探索、严禁再调用工具查询次要细节；必须立即利用手头已掌握的资料完成结论整合并输出最终答复。”
  - 确保模型在最后阶段刹车并交付已获得的成果。

---

## 3. 风险与回滚方案
- **平台前端兼容性**：移除自动重投仅影响失败时的非预期重发行为，已有的排队管理（`useServerPromptQueue`）正常排队不受影响；
- **运行时兼容性**：Prompt 增强与 Wrapup 中文化指令为纯增强，不破坏现有的中间件状态机与接口契约；
- **回滚操作**：如需回滚，直接撤销相关文件改动即可。
