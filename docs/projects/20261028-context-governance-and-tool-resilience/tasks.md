# 任务拆分：智能体上下文防爆治理与工业级工具截断/子任务架构升级

> 状态标记：`[ ]` 待开始 / `[/]` 进行中 / `[x]` 已完成

## Phase 1: 工具结果溢出落盘机制（Spill-to-Disk）
- [x] **T1.1** 在 `runtime-service` 中设计工具响应拦截与溢出落盘组件，在 `conversation_offloading.py` 中引入 `AGENT_TOOL_TOKEN_LIMIT_BEFORE_EVICT`（默认 1200 Tokens）。
- [x] **T1.2** 适配工作区/沙箱存储路径：复用 `/large_tool_results/{digest}/{tool_call_id}`，自动将超限输出持久化落盘，回传指针。
- [x] **T1.3** 升级 `filesystem.py` 的 `_guard_message` 与 `truncate_tool_output_text`，支持 `AGENT_TOOL_OUTPUT_MAX_CHARS`（默认 4800 字符），全量覆盖 `execute` 等重度工具。
- [x] **T1.4** 编写单元测试（`test_tool_output_budget.py` 新增 3 项测试），验证环境变量生效与全工具拦截行为，65 项测试全部通过。

### Task Completion Card: Phase 1 完成
- **改动内容：** 实施工具输出限额与落盘机制，引入 `AGENT_TOOL_TOKEN_LIMIT_BEFORE_EVICT`（1200 Tokens）和 `AGENT_TOOL_OUTPUT_MAX_CHARS`（4800 字符），全量加固 `execute`、`github_query` 等重度工具的截断与落盘。
- **代码位置：**
  - `apps/runtime-service/src/runtime_service/middlewares/conversation_offloading.py` → `resolve_tool_output_limit()`
  - `apps/runtime-service/src/runtime_service/middlewares/filesystem.py` → `ResultFilesystemMiddleware._guard_message()`, `truncate_tool_output_text()`
  - `apps/runtime-service/.env`, `apps/runtime-service/.env.example`
- **预期结果：** 单次工具调用输出严格限制在约 4800 字符以内，超限自动落盘到沙箱文件并返回指针与首尾切片，杜绝单轮几十次工具调用累积打爆 128K 窗口。
- **验证项：** `pytest apps/runtime-service/tests/middlewares/test_conversation_offloading.py apps/runtime-service/tests/middlewares/test_tool_output_budget.py -q` → ✅ 65/65 通过
- **状态：** `[x]` 已完成 2026-10-28 → 见 [01-tool-output-spill-and-truncation.md](implementation/01-tool-output-spill-and-truncation.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] implementation 记录已归档

## Phase 2: 历史工具结果动态虚拟折叠（Ephemeral Tool Pruning）
- [x] **T2.1** 在请求构造管道中实现大模型视口层面的工具结果虚拟置换（`ToolOutputPruningMiddleware`，保持数据库 Checkpoint 不变，仅在发往大模型前通过 `request.override` 折叠）。
- [x] **T2.2** 制定折叠窗口策略（保留最近 4 次工具调用完整输出，更早的已消化工具输出折叠为精简占位符，支持多模态与文件指针提取）。
- [x] **T2.3** 单元测试覆盖：多轮长工具调用场景下的 Prompt 瘦身率、多模态保留、异步拦截等测试全量跑通（300 项中间件单测全绿）。

### Task Completion Card: Phase 2 完成
- **改动内容：** 实现大模型推理视口工具结果动态虚拟折叠中间件 `ToolOutputPruningMiddleware`，在组装发往大模型的 Prompt 时将较早轮次已消化的 ToolMessage 替换为精简占位符，保持数据库持久化 Checkpoint 原始数据 100% 完整。
- **代码位置：**
  - `apps/runtime-service/src/runtime_service/middlewares/tool_output_pruning.py` → `ToolOutputPruningMiddleware`, `prune_messages_for_model()`
  - `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` → 挂载中间件
  - `apps/runtime-service/tests/middlewares/test_tool_output_pruning.py` → 专项测试
  - `apps/runtime-service/.env`, `apps/runtime-service/.env.example`
- **预期结果：** 在拥有 50+ 次工具调用的重型任务中，发给大模型的有效 Prompt 体积压降 90% 以上，彻底杜绝历史工具消息累加撑爆 128K 窗口，消灭上下文恶性压缩。
- **验证项：** `pytest apps/runtime-service/tests/middlewares/ -q` → ✅ 300/300 全部通过
- **状态：** `[x]` 已完成 2026-10-28 → 见 [02-ephemeral-tool-pruning.md](implementation/02-ephemeral-tool-pruning.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] implementation 记录已归档

## Phase 3: 策略调优与重度调研/全库分析链路复验
- [x] **T3.1** 校验 `AGENT_CONTEXT_TRIGGER_POLICY` 与 `AGENT_CONTEXT_KEEP_POLICY` 在工具落盘后的适应性表现，确定 1200 Token 驱逐与 4800 字符截断基线。
- [x] **T3.2** 针对 `6f09c502`（灵巧手调研）和 `e5492054`（全仓库剖析）两大真实场景进行全链路压力复测，回放测算压降 58% ~ 82%，彻底消除恶性压缩。
- [x] **T3.3** 固化验证数据与指标对比，完成工程验收，判定为 `done`。

### Task Completion Card: Phase 3 完成
- **改动内容：** 提取两大真实生产问题会话（109 条消息与 83 条消息）进行底层回放复验，验证多轮连续工具调用场景下的 Prompt 瘦身压降幅度及零压缩触发状态。
- **验证项：** `python scratch/verify_replay_pruning.py` → ✅ 全部回放复测通过，灵巧手场景 Token 压降 60.56%（由 10.5 万降至 4.1 万），全库代码分析场景 Token 压降 81.75%（由 12.9 万降至 2.3 万），均牢牢处于安全水位，压缩触发从 6 次降至 0 次。
- **状态：** `[x]` 已完成 2026-10-28 → 见 [verification.md](verification.md)
- **合规检查：**
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] verification.md 已出具四态判定（done）
