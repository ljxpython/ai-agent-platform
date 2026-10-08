# Runtime 与 API 预算实现

日期：2026-10-07。G0 已由用户批准；本轮只实施非前端范围。

## Runtime

- `apps/runtime-service/src/runtime_service/middlewares/execution_budget.py`：`ExecutionBudgetMiddleware` 继承官方限制器，保留 counters、after_model 和 end/error。before_model 产生结构化 approaching/reached，end 人工消息附服务端标记；RemainingStepsManager 负责图余量，3 calls/8 supersteps 为当前余量。通知不额外请求模型。
- `middlewares/timeout_wrapup.py`：`TimeoutWrapupMiddleware` 用 invocation 私有 UntrackedValue 保存单调时间，模型边界触发一次软提示；默认关闭，启动/装配拒绝非法阈值。
- DearFlow/Showcase/Reference 的 `agent.py`：替换现有模型限额实例，主子分别声明 scope，保留限额值、工具/HITL/权限策略。子图不装软时间计时器。
- Workflow 的 `agent.py`/`schemas.py`/`workflow.py`：公开 input/output schema 保持原样，内外图分开计预算，内层 primary notice 使用 outer writer。锁定 LangGraph writer 在调用时读取 namespace，需 `copy_context()` 绑定外层节点上下文，直接传函数仍会落到内图 namespace。软计时从内层模型 Agent invocation 起算，不含外图 prepare/route、模型准备及人工等待。

## API

- `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py`：四种精确异常固定 code；字符串/未知异常保持兼容安全泛化。预算通知及 end 标记按白名单校验，计数/clock/latch 不公开。
- `modules/runtime_gateway/presentation/http.py`：补 tasks.error 安全投影；保留 SSE id/seq/namespace 和原生终态。
- `core/runtime_contract.py`/`application/service.py`：私有状态与通知键递归拒绝，覆盖 input/update/command/resume；默认流模式加 custom。
- Runtime `auth/platform.py`：原生网络写入口同步拒绝预算伪造，沿用授权/ACL。
- 真实验收发现普通 create/resume 与 Protocol input.respond 在 `_normalize_payload()` 之前查询 interrupt：已在共享入口统一校验，使非法私有键先返回 400/runtime_private_state，未触发 interrupt 查找。
- 业务 `artifact/result` 的 error 维持正常内容；只在 Runtime 资源错误槽位做执行错误投影，避免误洗结构化业务结果。

## Phase 检查

- T01 官方生命周期/私有 managed schema/Thread 重建：5 passed。
- T02/T04/Reference/Workflow 第一轮定向：50 passed；原 soft prompt 探针读在 wrapper 之前，调整捕获位置后通过。TypedDict 混用标准库与 typing_extensions 的元类冲突已改为同一来源。
- T05/T06：新增投影 unittest 6 passed；既有 SSE unittest 19 passed。旧三失败断言按已批准兼容语义修正，tasks 原文清洗已补。
- T03 主子装配/并行图及 Workflow root writer 定向 **5 passed**；包含两个并行子图、一子完成/一子 end 限额停止和 namespace 唯一性。

## 真实 Worker 与 Final 证据

- `scripts/verify_execution_budget.py` 和 `tests/durable/test_execution_budget.py`：真实 Platform HTTP、GraphHarbor API/ProductionWorker、随机 PG 库/Redis prefix、测试目录及真实模型 smoke。最终 **1 passed，23/23 场景通过**；[安全 JSON](budget-http-evidence.json) 已冻结，仅保存 ID、code、count、namespace 与状态。
- 最后一轮并行子图首次遗漏普通请求 `stream_subgraphs=true`，事件已落 PG 但被回放过滤；脚本补显式订阅并校验 child 调用数 1/4 和 scoped namespace 后复验通过。生产组合根未改变 child=error 策略，父 Run 原生 error 保留。
- 硬 timeout 由 Worker 构造时读取环境变量；验收改变阈值后需重建 Worker。先前测试错误使用已构造 Worker，已修夹具并复验。
- 最后收口修正验证脚本：`complete` 仅在所有场景均为 passed 时为 true，缺真实模型配置保留 blocked；provider 调用统计只存白名单测试别名，人工审批输入映射为 hitl，未知输入映射为 other。
- Runtime **253 passed、5 deselected**；API **81 passed、1 skipped、423 subtests passed**；skip 为既有外部错误契约，未计入通过。非前端 Final 见 verification.md，前端由同事实施。

## 图成本取证

同负载官方限制器/扩展均为 2 model calls / 8 supersteps；独立重复中位数 9.041ms / 9.137ms。早期受机器负载影响出现较高值，未据此定义性能 SLO。

从前次隔离验证库 `runtime_events` 对四个正常样例按 root namespace 读取 checkpoint metadata.step / updates（本轮后续仅收紧脚本证据判定与统计别名，正式图未改动）：

| graph | 最后 root checkpoint step | root updates | root checkpoint 帧数 |
| --- | --- | --- | --- |
| dearflow_agent | 12 | 12 | 14 |
| reference_agent | 7 | 7 | 9 |
| showcase_demo | 13 | 13 | 15 |
| workflow_demo | 3 | 3 | 5 |

以上是软阈值关闭、一次正常模型回答的实际图开销，checkpoint 帧包含输入/初始状态，不能当作模型/工具次数；Workflow root 不包含内层 step。图 8 supersteps/模型 3 calls 仅提供收尾机会，不保证拓扑一定完成总结。
