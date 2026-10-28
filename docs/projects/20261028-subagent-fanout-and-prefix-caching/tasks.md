# 任务拆分与执行跟踪

> 范围：Runtime 单服务；所有任务尚未开始。代码改动前先完成 Phase 0 基线。

## Phase 0：基线与前置条件

- [ ] **T0.1 核对上下文治理改动归属**
  - 检查 ToolOutputPruning、ConversationOffloading、工具输出限额相关文件是否在目标分支。
  - 运行现有 subagent、TokenBudget、tool output 和 conversation offloading 测试。
  - 记录实际测试命令、提交版本及未提交文件；未能定位或复测失败时暂停实施。
- [ ] **T0.2 建立串行基线**
  - 使用 verification.md 固定的 deepseek-harness 提交 SHA、原样任务提示词与 5 项答案表；GitHub 工具请求必须显式传该 SHA 作为 ref。
  - 通过 Platform Web 的正式 `dearflow_agent` Run 路径，选择 Pro 和固定模型配置执行 3 次；每次新建 Thread，保持上下文策略一致。此阶段的 Pro 没有 task 工具，作为串行组。
  - 在隔离 Runtime API/Worker 配置 RUNTIME_USAGE_ENABLED=1、RUNTIME_TOKEN_BUDGET_ENABLED=1、RUNTIME_TOKEN_BUDGET_MAX_TOKENS=100000；串行和委派组使用同一额度。
  - 保存每次 Run ID、Thread ID、模型 provider/model、仓库 SHA、prompt hash、完整用量查询、主/子/辅助 Token、缓存 Token、成本、耗时、root custom 整理事件和答案评分。
- [ ] **T0.3 固定验收样例**
  - 直接使用 verification.md 中预登记的 5 条答案与不可变 GitHub 行号链接，不在观察委派组结果后改评分口径。
  - 在开始 Phase 1 前记录模型标识、上下文窗口、有效配置、3 次串行结果与中位数；不得根据委派结果事后放宽门槛。

## Phase 1：受限委派能力

- [ ] **T1.1 为 Pro 开放 task**
  - 修改 dearflow_agent/modes.py，使 Pro 与 Ultra 开放 delegation；Flash 与 Standard 保持关闭。
  - 在 test_agent.py 验证各模式暴露的 task 工具集合。
- [ ] **T1.2 增加受限 code_explorer**
  - 在 dearflow_agent/subagents/ 注册 code_explorer。
  - 只提供 ls、read_file、glob、grep，不提供用户文件写入；固定公开仓库对照还依赖 github_query，只有验证其来源证据写入被限制在 content-addressed sources 路径且带正确 namespace 后才可加入。
  - 明确禁止 execute、write_file、edit_file 和递归委派；共享 backend 不得描述成物理沙箱。
  - 测试子 Agent 的工具 Schema 中不包含禁止工具。
  - 若 github_query 的来源证据写入无法满足上述边界，暂停真实委派对照，先修复隔离或准备经过哈希校验的本地固定快照。
- [ ] **T1.3 补充委派触发和汇报约束**
  - 只有两个以上可并行的研究方向才使用 task；单点问题不委派。
  - 子 Agent 最多返回 5 条带 URL 或 path:line 的结论，并注明置信度和未解决点。
  - 在测试中验证报告不超过当前有效工具输出上限，且超限时不会静默丢失必需证据。

## Phase 2：并发、上下文与预算契约

- [ ] **T2.1 保留现有并发机制**
  - 复用 DelegationConcurrencyMiddleware 的每父图 3 路限制，不新增 asyncio.gather 调度器。
  - 扩展 test_subagents.py：提交 4 个子任务，证明前 3 个可并发启动、第 4 个在有空位前不启动；释放一个槽位后第 4 个继续，峰值活动数始终不超过 3。
- [ ] **T2.2 验证隔离和取消**
  - 断言子任务输入不包含父会话私有内容，子工具原始消息不会进入父 messages，事件归属到不同 namespace。
  - 父任务取消时所有运行中子任务都收到取消；一个子任务失败时其他结果仍可被安全汇总。
- [ ] **T2.3 验证 Run 级 Token 预算**
  - 使用确定性模型：先让父模型调用消耗已知额度并返回 3 个 task 分发，再用屏障让 3 个子模型调用在接近预算边界时同时进入，返回已知 input/output Token。
  - 断言所有 namespace 共用同一 RunTokenBudget 与 RuntimeUsageCallback；并发在途用量已纳入准入或安全预留，Run 总用量不能超过配置上限，额度耗尽后不能再开始模型调用。
  - 若当前实现只能在响应后登记用量、导致在途调用可能超调，先补齐并发预算控制并新增竞态回归测试；未通过前不得开放 Pro 委派。
- [ ] **T2.4 验证结果大小与上下文治理**
  - 验证 task ToolMessage 不超过当前输出上限，子工具长输出不会进入父会话。
  - 运行现有 ToolOutputPruning 与 ConversationOffloading 测试；不得破坏 Checkpoint 原始历史。

## Phase 3：对照验收

- [ ] **T3.1 自动化门禁**
  - 执行 verification.md 列出的 Dear Agent、subagent、TokenBudget、工具输出与上下文整理测试。
  - 对修改文件执行 Ruff 检查。
- [ ] **T3.2 公开仓库真实模型对照**
  - 经用户明确授权后，在隔离本地栈执行 3 次串行基线和 3 次委派运行；两组按 verification.md 固定模型、提示词、上下文和 Run 额度，以中位数比较。记录时间戳，模型部署版本有变化时该对照无效。
  - 若使用关联 Worktree，按 docs/standards/worktree-development.md 执行 local-stack.sh init、deps、doctor、start、status；用 status 返回的实际地址，不假定端口。将预算/用量变量仅配置在该环境的 `.local-stack/runtime.env`。
  - 仅使用固定 SHA 的公开仓库内容；记录 Run ID 和全部指标，不发送平台私有源码。
- [ ] **T3.3 判定与收尾**
  - 按 verification.md 的全部功能和效果门槛判定 done。
  - 若没有真实模型凭据或用户未授权外部调用，保持 partial，不将回放或单元测试记成真实模型验收。
