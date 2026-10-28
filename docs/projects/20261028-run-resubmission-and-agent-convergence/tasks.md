# 任务拆分与执行跟踪

## 任务清单

- [x] **Phase 1: 前端异常重投漏洞修复**
  - [x] 1.1 审查 `apps/platform-web/src/modules/chat/components/ChatSession.vue` 中的 `send` 降级逻辑
  - [x] 1.2 移除 `session.send` 失败时自动调用 `submitQueuedMessage` 的逻辑，恢复为将原草稿归还用户草稿框并撤销乐观气泡
  - [x] 1.3 运行前端相关单元测试，确保排队功能与发送失败恢复正常

- [x] **Phase 2: Agent 代码库与本地项目调研收敛准则增强**
  - [x] 2.1 审查 `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py`
  - [x] 2.2 增加针对代码库剖析、本地文件探索的自顶向下收敛准则与调用次数上限约束（单轮 5~8 次探索硬约束）
  - [x] 2.3 严禁通过 `execute` 编写脚本对全量文件树进行微观正则/递归遍历，要求即刻落笔并阶段性交付

- [x] **Phase 3: 模型预算耗尽告警的强制收尾感知优化**
  - [x] 3.1 审查 `apps/runtime-service/src/runtime_service/middlewares/execution_budget.py`
  - [x] 3.2 强化 `WRAPUP_INSTRUCTION` 的中文化最高优先级强制刹车指令（严禁在预算告警时调用工具，强制就地总结交付）
  - [x] 3.3 将 `dearflow_agent` 的 `ExecutionBudgetMiddleware` 预警阈值显式提升至 `warning_calls=5`
  - [x] 3.4 运行 `runtime-service` 中间件与 budget 相关自动化测试（76 项测试全绿）

- [x] **Phase 4: 全面验证与回归测试**
  - [x] 4.1 运行 `runtime-service` 中间件与预算测试（`test_execution_budget.py`, `test_timeout_wrapup.py`, `test_loop_detection.py` 全部 76 项通过）
  - [x] 4.2 运行 `platform-web` 核心单测（`useServerPromptQueue.spec.ts`, `useChatSession.spec.ts` 全部 58 项通过）
  - [x] 4.3 产出 `verification.md` 记录
