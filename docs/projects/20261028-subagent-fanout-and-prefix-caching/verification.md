# 验证计划与记录

> 当前状态：仅完成方案修订，以下验证尚未执行。测试输出必须在真实运行后填写。

## 1. 验证范围

本项目只改 apps/runtime-service 内部的 Agent 模式、Subagent 工具与预算行为，不改变 Platform API/Web 契约。因此不要求新增 API/Web 单测、前端卡片测试或全链路 UI E2E。效果验收通过 Runtime 现有调用路径执行公开仓库任务；如果运行于关联 Worktree，服务启停和 E2E 必须遵守 docs/standards/worktree-development.md 与 scripts/local-stack.sh。

## 2. 自动化测试

在仓库根目录执行：

- Dear Agent 与 Subagent：cd apps/runtime-service && uv run pytest tests/services/dearflow_agent/test_agent.py tests/services/dearflow_agent/test_subagents.py -q
- Token 预算与上下文治理：cd apps/runtime-service && uv run pytest tests/middlewares/test_token_budget.py tests/middlewares/test_tool_output_budget.py tests/middlewares/test_tool_output_pruning.py tests/middlewares/test_conversation_offloading.py -q
- 静态检查：cd apps/runtime-service && uv run ruff check src/runtime_service/services/dearflow_agent/modes.py src/runtime_service/services/dearflow_agent/agent.py src/runtime_service/services/dearflow_agent/subagents tests/services/dearflow_agent/test_agent.py tests/services/dearflow_agent/test_subagents.py

真实模型对照的运行配置：

- RUNTIME_USAGE_ENABLED=1
- RUNTIME_TOKEN_BUDGET_ENABLED=1
- RUNTIME_TOKEN_BUDGET_MAX_TOKENS=100000

Token budget 开启时必须同时开启用量采集。串行与委派组使用同一模型、同一 100,000 Token Run 上限和相同上下文策略；任一 Run 的 usage 缺失或 invalid 即判该次结果无效。只在隔离测试 Runtime 配置这些变量，不修改主工作区或其他 Worktree 的私有配置。

若在关联 Worktree 执行真实模型对照，先运行 bash "scripts/local-stack.sh" init、deps、doctor、start、status，并使用 status 返回的地址；配置只写入该 Worktree 的 `.local-stack/runtime.env`。测试后只停止本环境服务，不销毁数据。主工作区和其他 Worktree 的服务、数据库、Redis、Workspace 不得复用。

自动化通过条件：

1. Flash、Standard 的 task 工具不可见；Pro、Ultra 的 task 工具可见。
2. code_explorer 仅可见批准的读取工具和受限来源证据记录能力；不存在 execute、write_file、edit_file 或 task，且不得修改用户文件。
3. 并发契约测试提交 4 个子任务：3 个同时活动，第 4 个等待槽位；释放一个槽位后第 4 个启动，峰值活动数为 3。
4. 子任务 namespace 互不相同；父 messages 不包含子 Agent 的原始工具消息或父会话私有输入。
5. 取消父 Run 会取消运行中的所有子任务；单个子任务失败不会导致其他结果被错误伪装为成功。
6. 主、子模型调用 usage 都按 namespace 记录，并共同消耗同一个 Run Token 预算；并发在途调用不得导致额度超调，额度耗尽后模型请求数不再增加。
7. 每个子任务交回的 ToolMessage 不超过有效输出上限；被限制时有明确截断标记，必需的来源信息在合格报告中保留。
8. 现有工具输出截断、ToolOutputPruning 和 ConversationOffloading 测试通过。

## 3. 真实模型对照

### 固定数据与任务

- 仓库：`https://github.com/deepseek-ai/deepseek-harness`，固定提交 `477b4f420553e8a52c2fbccc464d7561b239c443`。该 SHA 来自本地干净 checkout 的 `origin/master`；任务中的每次 `github_query` 必须传相同 `ref`，不可读取默认分支后再声称结果来自该提交。
- 三个互不重叠方向：能力包边界；compaction 触发和生命周期；subagent 能力与提供方边界。
- 两组使用相同的原始提示词、全新 Thread、Pro 模式、模型配置、上下文策略和 100,000 Token Run 上限；唯一被测差异是委派组新增 task 入口和 code_explorer。串行组运行在实施前版本；委派组运行在实施后版本。每组各运行 3 次，按中位数比较；记录执行时间和 provider/model 标识，模型版本发生变化则对照无效。
- 在每次委派 Run 中，至少两个方向必须由不同子任务处理，且至少一个子 namespace 标识为 `code_explorer` 并完成固定 SHA 的 GitHub 读取；没有真实子任务 namespace 的运行不得计入委派组。
- 授权：真实模型验收会向外部模型发送公开仓库内容，且可能产生费用。每次执行前需取得用户对外部/付费模型调用的明确授权；未授权时不执行、不填造结果。

固定提示词（两组逐字相同）：

> 请只基于公开仓库 `deepseek-ai/deepseek-harness` 的提交 `477b4f420553e8a52c2fbccc464d7561b239c443`，调研以下三个互不重叠的问题：1）包目录如何组织 compaction 与 subagent 能力；2）长对话 compaction 的触发、工具结果剪枝和重试流程；3）subagent 的能力边界与提供方形态。如果 task 工具可用，将三个方向拆开并行处理，最多三个子任务；GitHub 源码读取使用 code_explorer。若 task 工具不可用，则由主 Agent 顺序完成。所有 GitHub 文件读取都显式传入该提交 SHA。最终用中文表格逐项给出结论、不可变 GitHub `path#Lx-Ly` 证据、置信度和未解决点；不能从证据推出的内容标为未知，不要猜测。

预登记答案（运行时不给模型）：

| # | 必须核对的事实 | 固定证据 |
|---|---|---|
| 1 | 包目录将 compaction 定义为 Service Definition、基础 Provider 与命令 Consumer 的能力族；subagent 则是提供方注册约定和面向模型的委派工具。 | [`packages/README.zh.md#L51-L53`](https://github.com/deepseek-ai/deepseek-harness/blob/477b4f420553e8a52c2fbccc464d7561b239c443/packages/README.zh.md#L51-L53) |
| 2 | compaction 在 Token 压力上升时摘要较早历史，支持 `/compact`，并可先修剪超大工具输出；该仓库随附基础配置默认启用。 | [`packages/compaction/README.zh.md#L10-L12`](https://github.com/deepseek-ai/deepseek-harness/blob/477b4f420553e8a52c2fbccc464d7561b239c443/packages/compaction/README.zh.md#L10-L12) |
| 3 | `dsh-compaction-basic` 在派生请求前经 `agent/pre-step` 处理压力；`agent/request-error` 仅处理规范上下文溢出；先做可选剪枝再选摘要，只有 replacement generation 前进才重试。 | [`docs/agent-lifecycle.zh.md#L85-L89`](https://github.com/deepseek-ai/deepseek-harness/blob/477b4f420553e8a52c2fbccc464d7561b239c443/docs/agent-lifecycle.zh.md#L85-L89) |
| 4 | subagent 是 agent loop 之外的可选能力；同一注册表可以同时承载多个命名提供方。 | [`docs/subsystems/subagent.zh.md#L5-L7`](https://github.com/deepseek-ai/deepseek-harness/blob/477b4f420553e8a52c2fbccc464d7561b239c443/docs/subsystems/subagent.zh.md#L5-L7) |
| 5 | 子 Agent 可由全新进程内、继承父级已完成历史的进程内、ACP/Codex/Claude Code/另一 Harness 等进程外形态提供；父 Agent 可发现子级。 | [`packages/subagent/README.zh.md#L10-L12`](https://github.com/deepseek-ai/deepseek-harness/blob/477b4f420553e8a52c2fbccc464d7561b239c443/packages/subagent/README.zh.md#L10-L12) |

每项只在结论正确且至少一个引用确实支撑该结论时计为通过；引用必须指向固定 SHA，文件路径和行号准确。5 项全部通过且无虚构引用才满足证据质量门槛。

### 正式调用和取数路径

- 通过 Platform Web 中 `dearflow_agent` 的正式 Run 流程执行；不要用 `DEAR_LIVE_TEST=1` 的 direct graph 测试代替，它不覆盖 Platform Run 身份和 Runtime 用量账本。
- 在隔离 Runtime API/Worker 环境启用 `RUNTIME_USAGE_ENABLED=1`、`RUNTIME_TOKEN_BUDGET_ENABLED=1`、`RUNTIME_TOKEN_BUDGET_MAX_TOKENS=100000`。token budget 依赖用量采集、数据库迁移和受信 native Run 身份；缺少任一条件时停止真实对照。
- 由有该项目 Run Usage 读取权限的身份记录 `thread_id` 与 `run_id`；等待 Run 终态后，通过 `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/usage?limit=100` 读取用量，并按 `calls.next_cursor` 取完所有调用页。必须为 `availability=available`、`finalized=true`，且 `coverage.missing_usage_call_count`、`coverage.incomplete_call_count` 均为 0。确认 `token_budget` 非空、`token_budget.max_tokens=100000`、`token_budget.coverage=complete`、`token_budget.stop_code=null`。单独记录 summary 的 `truncated`；它可能表示价格版本列表被截断，不能代替调用分页完整性判断。
- 主 Agent 和子 Agent 用量按逐调用记录的 `scope`、`namespace` 汇总；预算和 Run 总 Token 使用所有 scope（包含 auxiliary），不得只加 primary/subagent 而漏掉辅助模型。
- `conversation_offloading` 不在 Run diagnostics 聚合中。通过同一 Run 的 SDK custom SSE 帧记录 root namespace（`namespace=[]`）事件；只把 `type=conversation_offloading`、`trigger=automatic`、`status=completed` 计入自动整理次数，同时保留 `started/skipped/failed` 事件。诊断接口不能代替这项实时事件计数。
- 如果在关联 Worktree 执行，按 `docs/standards/worktree-development.md` 与 `scripts/local-stack.sh` 初始化和启动专属栈，配置写入该 Worktree 私有 `.local-stack/runtime.env`，使用 `status` 返回地址；不得复用其他 Worktree 的服务或数据。

### 必须记录

| 指标 | 计算与来源 |
|---|---|
| 主 Agent 输入 Token | 全部 `calls.items[]` 中 `scope=primary` 的 `tokens.input_tokens` 求和；另记录单次 primary 调用最大 `tokens.input_tokens` |
| 子 Agent 输入 Token | `scope=subagent` 的 `tokens.input_tokens` 求和 |
| 总 Token 与成本 | 全部 scope（primary、subagent、auxiliary）的 `tokens.total_tokens` 与 `cost.estimated_cost_usd`；summary 的 `tokens.total_tokens` 和 `cost` 用于交叉核对，不得过滤 scope 漏算 |
| Cache Read 与命中率 | 全部 scope 的 `tokens.cache_read_tokens` 求和；命中率 = cache_read_tokens / `tokens.input_tokens`；任一必要字段缺失则标为未采集 |
| 上下文整理次数 | 同一 Run SDK custom SSE 中 root namespace 的 `conversation_offloading` 事件；统计自动且 completed 次数，并记录其他状态 |
| 上下文错误 | 记录 ContextOverflowError、TokenBudgetExceeded 与其他失败码 |
| 耗时 | 从 Run 开始至终态的墙钟时间 |
| 证据质量 | 逐项核对预登记的 5 条事实是否有正确 URL 或 path:line；记录无证据或错误引用 |

### 通过门槛

1. 3 次委派运行均无 ContextOverflowError 或意外 TokenBudgetExceeded；主 Agent 自动整理事件为 0，任意 primary 模型请求输入不超过解析模型窗口的 50%。
2. 委派组主 Agent 输入 Token 中位数不高于串行组的 75%；未达到 25% 降幅时，不以“降低主上下文”为由交付委派功能。
3. 5 条预登记事实全部有正确证据；不允许出现虚构 URL、文件路径或行号。
4. 每次 Run 所有 scope 的 total_tokens 均不超过 100,000；所有调用均有完整用量记录，不得把缺失计作零。并发自动化测试还必须证明预算没有在途超调；若真实 Run 超额或触发预算停止，该次不通过。
5. 缓存命中率、总成本和耗时如实报告但不设独立百分比门槛；不得将缓存命中解释为上下文窗口节省。
6. 每次委派 Run 至少出现两个不同的 subagent namespace、最多三个，且至少一个 namespace 对应 `code_explorer` 并有固定 SHA 来源证据；自动化并发测试证明峰值活动子任务不超过 3。
7. 自动化测试全绿、真实模型门槛全过，才可判定 done。真实模型测试未执行时最高为 partial；若预算/权限或输出证据失败，先修复并重跑，不能豁免门槛。

## 4. 验证记录

| 日期 | 测试/模型/Run ID | 结果 | 证据 |
|---|---|---|---|
| 待执行 | 方案修订阶段未运行测试或真实模型调用 | 未执行 | 无 |

最终记录需保留 3 次串行和 3 次委派运行的指标、事实核对表、测试命令和四态结论。
