# 验证计划与结果记录

## 1. 验证目标与判定标准

依据项目规范，验证结果需满足四态判定：`done` / `partial` / `blocked` / `deferred`。

本次修复的核心验证指标：
1. **前端异常不自动重发**：当后台执行失败（或返回 `ok === false`）时，前端不再隐式将原 Prompt 发起二次排队执行，而是完好归还用户草稿框并撤销乐观气泡；
2. **提示词收敛性**：`SYSTEM_PROMPT` 具备明确的代码与文件调研预算上限与自顶向下约束（单轮探索限制 5~8 次，禁止写脚本遍历文件树，强制即刻落地产物）；
3. **收尾指令生效**：预算逼近告警阈值提升至 5 次（`warning_calls=5`），中文化最高优先级收尾指令准确注入模型请求中。

---

## 2. 自动化测试结果

### 2.1 后端中间件与预算收尾验证 (`runtime-service`)
```bash
rtk apps/runtime-service/.venv/bin/pytest apps/runtime-service/tests/middlewares/test_execution_budget.py apps/runtime-service/tests/middlewares/test_timeout_wrapup.py apps/runtime-service/tests/middlewares/test_loop_detection.py
```
**执行结果**：
- `test_execution_budget.py`：全部通过
- `test_timeout_wrapup.py`：全部通过
- `test_loop_detection.py`：全部通过
- 汇总统计：**76 passed, 5 warnings in 11.67s**。

### 2.2 前端排队与会话状态机验证 (`platform-web`)
```bash
rtk npm --prefix apps/platform-web run test:run -- src/modules/chat/composables/useServerPromptQueue.spec.ts src/modules/chat/composables/useChatSession.spec.ts
```
**执行结果**：
- `useServerPromptQueue.spec.ts`：7 passed
- `useChatSession.spec.ts`：51 passed
- 汇总统计：**58 passed in 13.87s**。

---

## 3. 四态完成度判定

- **状态判定：`done`**
- **判定说明**：
  1. 前端 `ChatSession.vue` 中引发幽灵自动二次派发 Prompt 的 `submitQueuedMessage` 盲目降级逻辑已彻底移除，草稿恢复机制完全恢复；
  2. `SYSTEM_PROMPT` 中针对 GitHub/代码库/本地架构剖析场景的 Top-Down 约束、单轮 5~8 次探索硬约束、禁止遍历正则扫描约束全部就位；
  3. `WRAPUP_INSTRUCTION` 已全面中文化并提升为高优先级强刹车告警，`warning_calls` 提早至 5 轮；
  4. 跨端自动化单元测试（前端 58 项，后端 76 项）全部绿色通过，改动完全闭环。
