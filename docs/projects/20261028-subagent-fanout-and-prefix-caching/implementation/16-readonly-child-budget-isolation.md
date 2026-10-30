# 只读子任务额度隔离与末次工具调用拦截

## 改动时间
2026-10-29

## 相关任务
T0.I。

## 原因与实现
v18真实失败证明供应商可能忽略最后一轮的tools=[]/tool_choice=none。`apps/runtime-service/src/runtime_service/middlewares/execution_budget.py` → `ExecutionBudgetMiddleware.after_model()` 在官方计数递增后检查原生tool_calls：达到Run或Thread额度时，error模式立即抛官方异常，end模式替换为明确未完成的停止消息；两者都在工具执行前停止，不发额外模型请求。继承的异步钩子走同一实现。

`apps/runtime-service/src/runtime_service/tools/errors.py` → `on_tool_error()` 仅对已批准readonly_roles的task将ModelCallLimitExceededError转换为既有tool.upstream_unavailable失败反馈，告知子任务不完整、不得重复委派；成功兄弟结果仍可交给父整合。主预算、共享Token停止、鉴权、取消及未知异常不扩大捕获。

## 测试与边界
- `tests/middlewares/test_execution_budget.py`：同步/异步、error/end，供应商无视tool_choice仍原生请求工具，断言工具零执行。
- `tests/services/dearflow_agent/test_subagents.py`：四子、三路并发，一个子额度失败，其余子及父能完成，失败状态不伪装成功。
- `tests/tools/test_tool_errors.py`：只读角色白名单与普通工具/未知角色的分类边界。
- `tests/services/dearflow_agent/test_tool_errors.py`：真实装配子失败后父能收尾；父自己最后一轮继续请求工具仍被阻断，四次总模型请求不增加。不依赖输出中隐藏的计数字段。
- 联合Phase：159 passed、1 skipped、62 warnings（53.15s）；九个本轮文件Ruff通过。真实v18失败与partial用量完整保留；v19效果另验。
