# 收尾协议与完整短报告

## 改动时间
2026-10-29

## 相关任务
T0.F；真实质量仍由T3.2验收。

## 证据与根因
v7主上下文峰值25.1%、自动整理0，但最后子模型轮因tools为空而未向供应商发送tool_choice，返回DSML调用正文。父级重派形成4个子任务。最终主响应finish_reason=length，4096输出额度含1835 reasoning Token，第三部分截断。失败原始证据保留，不能以success代替质量验收。

## 最小修复
- `apps/runtime-service/src/runtime_service/middlewares/execution_budget.py`：`disable_tool_calls()`保留工具Schema并显式禁止调用；OpenAI-compatible传`none`，Anthropic传`{type: none}`。`ExecutionBudgetMiddleware._delivery_request()`在最后模型轮使用该原生协议，预警和已有计数保持不变。
- `apps/runtime-service/src/runtime_service/middlewares/model_resilience.py`：`_observed_request()`在每次实际模型候选切换后重新规范化none参数，避免跨协议容灾把none当成工具名。
- `dearflow_agent/prompts.py`：委派只重述原问题和来源限制，不扩成审计清单，最多3个含重试；短报告先覆盖全部原问题，总计最多6行，约1800字。
- `subagents/code_explorer.py`：子报告目标从3600字符收敛至1800，先覆盖所分配问题再补细节。既有工具输出硬上限与权限不变。
- 未引入DSML解析器，不执行模型正文中的调用标记；不注入目标文件、答案或评分点。

## 测试
- `tests/middlewares/test_execution_budget.py`：同步/异步最后轮参数；真实OpenAI/Anthropic SDK经MockTransport核对请求字段及保留Schema。
- `tests/runtime/test_model_resilience_protocols.py`：OpenAI-compatible、Anthropic、DeepSeek四组容灾切换均保留禁止调用语义。
- 新回归先红6 failed/4 passed；修复及装配/组合70 passed、5 warnings（47.33s），Ruff通过。一次测试错误地把httpx客户端传给ChatAnthropic未知构造参数，已改用其既有默认HTTP工厂注入后通过；不涉及生产逻辑。
- 安装版LangChain factory在tools为空时改用model.bind，省略request.tool_choice；ChatAnthropic.bind_tools对字符串none按工具名处理。这两点均以本Worktree锁定依赖源码与SDK请求测试确认。
- v8公共源码22份，预登记manifest SHA256 `c5113dabafcf0f6e0ba3b5e102d1a902900a7ae9e1e26eee2e324aedc0078307`。真实供应商依从性、三次质量和完整对照仍待实测。
