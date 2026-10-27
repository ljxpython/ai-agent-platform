# 智能体上下文窗口治理与 Token 预算韧性优化 - 任务拆分

## Phase 1: 上下文裁剪策略与工具输出防爆

### Task 1.1: 重构 ConversationOffloading 裁剪保留策略
- **改动内容：** 替换 `ConversationOffloadingMiddleware` 中写死的 `keep=("tokens", 0.10 * self.input_budget)`，实现保留最近 16 条完整消息或 $\ge 40\%$ 输入预算的复合保留逻辑，保护近期工具上下文与用户指令；并在重试裁剪时提供安全截断兜底。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/conversation_offloading.py`
- **预期结果：** 压缩后保留完整的近期工作上下文，不再因为 10% 极小容量导致失忆重读。
- **验证项：** `pytest tests/middlewares/test_conversation_offloading.py` (32 passed)
- **预计：** 0.5 天
- **状态：** `[x]` 已完成

### Task 1.2: 实现单次工具输出 Head+Tail 前置截断防爆
- **改动内容：** 在 `ResultFilesystemMiddleware` 添加安全截断逻辑。对 `TOOLS_EXCLUDED_FROM_EVICTION`（如 `read_file`、`grep` 等大输出工具）执行 Head+Tail 保留（首尾各 50 行），中间插入结构化行号与字符数截断提示，防止单次 `read_file` 打爆上下文。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/filesystem.py`
- **预期结果：** 无论读多大文件或跑多长日志，送入模型的 ToolMessage 严格受控在安全范围。
- **验证项：** `pytest tests/middlewares/test_tool_output_budget.py` (30 passed)
- **预计：** 0.5 天
- **状态：** `[x]` 已完成

## Phase 2: Token 预算耗尽的优雅停机（Graceful Hard-Stop）

### Task 2.1: 改造 TokenBudgetMiddleware 终态控制
- **改动内容：** 在 `TokenBudgetMiddleware` 中实现 `exit_behavior: Literal["end", "error"]`。当累计 Token 达到 `max_tokens`（100% 耗尽）且采用 `end` 模式时，拦截调用、清空模型的 `tool_calls`，将助手消息转换为温和的收尾告示，使 LangGraph 正常流向 `END`，严禁抛出 `TokenBudgetExceededError` 导致红条崩溃。
- **代码位置：**
  - `apps/runtime-service/src/runtime_service/middlewares/token_budget.py`
  - `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`
  - `apps/runtime-service/src/runtime_service/services/reference_agent/agent.py`
- **预期结果：** 预算耗尽时，前端不再出现红色阻断错误，保留当前已产出的文件与思考汇报，正常结束运行。
- **验证项：** `pytest tests/middlewares/test_token_budget.py` (29 passed)
- **预计：** 0.5 天
- **状态：** `[x]` 已完成

## Phase 3: 模型容量配置与前台体验确认

### Task 3.1: 修正模型数据库记录与默认容量策略
- **改动内容：** 检查并更新已录入模型在数据库 `runtime_catalog_models` 中的 `context_window_tokens`（`deepseek-v4.1-flash` 从 64K/32K 校准为官方 **131,072** 128K，`step-5-preview` 从 64K 校准为 **131,072** 128K）。并在 `apps/runtime-service/.env` 与 `.env.example` 中配齐上下文触发水位（0.85）与保留比例（40%）。
- **代码位置：**
  - 数据库 `runtime_catalog_models` 校验与更新脚本
  - `apps/runtime-service/.env`
  - `apps/runtime-service/.env.example`
- **预期结果：** 常见模型恢复真实官方大窗口，不再被压制在 64K 以下；前后台完整支持 128K 预算。
- **验证项：** `SELECT provider, model_name, context_window_tokens FROM runtime_catalog_models` 确认已生效；前端 `vitest run RuntimeModelEditor` 18 项单测全绿。
- **预计：** 0.2 天
- **状态：** `[x]` 已完成

## Phase 4: 全量回归与链路验证

### Task 4.1: 全量测试套件执行与真实场景端到端验证
- **改动内容：** 运行 runtime-service 核心中间件及平台 API 关联测试套件，验证全部通过。
- **验证项：**
  - `test_conversation_offloading.py` (32 passed)
  - `test_tool_output_budget.py` (30 passed)
  - `test_token_budget.py` (29 passed)
  - `apps/platform-api/tests/test_execution_budget_projection.py` (9 passed)
  - `apps/platform-web RuntimeModelEditor.spec.ts` (18 passed)
- **预计：** 0.3 天
- **状态：** `[x]` 已完成

### Task 4.2: 真实页面端到端闭环排障与 Playwright 自动化验证
- **改动内容：** 针对真实页面报错 `ERR_CANCELED` / `runtime.execution_failed` 进行深入排查，定位并修复 `conversation_offloading.py` 中 `int('40%')` 解析异常；编写并执行 Playwright 端到端全自动测试脚本，在真实浏览器中跑完完整用户调研指令，截取多阶段运行证据。
- **代码与脚本位置：**
  - `apps/runtime-service/src/runtime_service/middlewares/conversation_offloading.py`
  - `apps/platform-web/scripts/verify-context-hardening-e2e.mjs`
- **预期结果：** 真实页面无红条、无 `runtime.execution_failed` 报错，Agent 自主进行多轮思考与工具调用链收敛。
- **验证项：** Playwright 自动化测试顺利通过，产出 4 阶段全流程铁证截图。
- **预计：** 0.2 天
- **状态：** `[x]` 已完成

## 进度追踪
- [x] Phase 1 完成（上下文策略与工具防爆）
- [x] Phase 2 完成（优雅收尾）
- [x] Phase 3 完成（模型配置与数据）
- [x] Phase 4 完成（全量回归）
