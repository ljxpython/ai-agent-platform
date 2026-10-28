# 方案设计：有界调研委派与子智能体上下文隔离

> **当前状态：** 修订稿，待实施评审；本文件只定义 Runtime 单服务改动。
> **参考：** 本地 DeepSeek Harness 仓库仅作设计参考。其 README 标记为 developer preview，性能数字不作为验收依据。

## 1. 问题与现状

用户遇到的“调研过程频繁整理上下文、Token 过载”需要拆成两个问题：工具历史挤占主 Agent 上下文，以及重型任务没有在适合的执行模式下使用隔离子任务。KV Cache 影响重复输入的成本和延迟，不会降低模型上下文窗口占用，不能代替上下文治理。

当前仓库证据：

- 项目 docs/projects/20261028-context-governance-and-tool-resilience/verification.md 记录工具输出截断、历史 ToolMessage 视口折叠和 300 项中间件测试通过；全仓库案例 e5492054 的回放记录为 57 次工具调用、压缩前 129,708 Tokens、折叠后 23,677 Tokens，压缩触发从 6 次变为 0。该项目文档和对应实现仍是当前工作区的未提交改动，需在本项目 Phase 0 确认其分支归属并复测。
- dearflow_agent 已注册 researcher 与 DeepAgents task。modes.py 中 flash、standard、pro 的 delegation 为 false，只有 ultra 为 true；因此默认 standard 和 Pro 任务拿不到 task 工具。现状不是缺少调度引擎，而是重型调研模式没有委派入口。
- DelegationConcurrencyMiddleware 已将每个父图的 task 并发限制为 3；test_subagents.py 已验证两个子任务并行、子上下文不包含父私有输入、父取消会传递到子任务。新实现应扩展这些契约测试，不另写 asyncio.gather 调度器。
- 子 Agent 当前通过同一 workspace backend 读取文件；child_filesystem 只开放 read_file。现有隔离是图命名空间和消息上下文隔离，不是独立文件系统沙箱。
- 用量代码已映射 prompt_cache_hit_tokens / cache_read_input_tokens，前端已有命中率计算。上述部分代码目前有未提交改动，须在 Phase 0 对齐。
- 新方案旧版声称同一类仓库分析会调用 200+ 次工具，但上述 e5492054 验证记录为 57 次。验收前必须固定会话、模型、工具调用定义和 Token 统计口径。

## 2. 目标与边界

### 目标
1. 在 Pro 和 Ultra 模式下，允许模型对至少两个相互独立的研究方向发起 task 委派；Flash 和 Standard 保持单 Agent，避免简单对话默认增加成本。
2. 复用现有 researcher 处理网页调研，新增受限 code_explorer 处理代码阅读；不修改用户文件，系统托管的来源证据写入须限定在已验证的 content-addressed 路径。
3. 主 Agent 只接收每个子任务的短证据摘要；子任务原始工具消息留在各自 namespace。
4. 验证主/子 Agent 用量可按 Run 聚合，并受同一个 Token 预算约束；并发中的模型请求也必须计入额度判断。
5. 在同一公开数据、同一模型和同一上下文配置下，对比串行与委派路径的主上下文 Token、总 Token、成本、整理事件和答案证据质量。

### 非目标
- 不新增 Subagent 调度器，不重写 LangGraph/DeepAgents 工具并发。
- 子 Agent 不开放 execute、write_file、edit_file、部署或任意用户文件写入；不承诺独立文件系统沙箱。
- 不改 Platform API/Web 契约，不加并发树、进度 UI 或 Artifact 卡片。
- 不新增 cache token 采集、不排序所有工具 Schema、不承诺 90% 缓存命中率或固定 tok/s。
- 不把 Unix 命令范例扩写进 SYSTEM_PROMPT；现有代码探索 5~8 次工具调用上限继续生效。

## 3. 方案决策

### 委派模式与触发条件
- 仅 Pro、Ultra 对模型暴露 task；Flash、Standard 不变。
- SYSTEM_PROMPT 补充一条短规则：只有工作可分成至少两个互不依赖的研究问题时才委派；单点事实问题由主 Agent 处理；不重复派发已完成的问题。
- 每个父图最多 3 个子任务同时运行，复用现有信号量。子 Agent 不递归委派。
- 保持现有 Run/Thread 工具调用上限。先证明子调用计入父 Run，再证明并发请求不会因“模型返回后才记账”越过 Run 额度；任一项未通过，Pro 委派不得启用。

### 子 Agent 权限
- researcher 保持现有网页搜索和来源读取权限。
- code_explorer 使用只读工作区工具 ls、read_file、glob、grep；固定公开仓库对照还要求它能用 github_query 读取指定 SHA。该工具唯一允许的副作用是把来源证据写入现有 content-addressed sources 路径并保留 namespace；测试不满足时不得执行真实委派对照，先修复边界或改成可验证的本地固定快照。
- 不开放 execute、write_file、edit_file 或任意用户文件写入。主 Agent 仍是唯一能够修改用户工作区和发布 Artifact 的主体。
- 子任务共享受控 workspace backend，因此文档称“namespace/上下文隔离”，不称“物理沙箱隔离”。

### 汇报与预算
每个子 Agent 最多返回 5 条发现。每条包含结论、证据 URL 或文件路径及行号、置信度和未解决点；不得粘贴完整命令输出。子 Agent 返回值不得超过当前工具输出有效上限（默认 4,800 字符）；测试必须确认没有因截断丢失必需证据。

RuntimeUsageCallback 的 scope、namespace、input/output/cache tokens 和 RunTokenBudget 是用量事实源。当前回调在模型开始时登记未结算调用、收到模型响应后才记入 token；并发子调用可能同时通过开始前检查。因此不能把“共享账本”直接等同于“硬上限”。Phase 2 必须用并发测试验证额度边界；若无法证明并发中的调用已被保守计入，先补齐预算预留/准入控制，再开放 Pro 委派。

真实模型基线和委派组必须使用相同的隔离 Runtime 配置：RUNTIME_USAGE_ENABLED=1、RUNTIME_TOKEN_BUDGET_ENABLED=1、RUNTIME_TOKEN_BUDGET_MAX_TOKENS=100000。预算开关依赖用量采集；任一 arm 的配置缺失或用量不可核验时，该组结果无效，不得把未知用量当作零。

### KV Cache 评估边界
缓存命中率只作为观测值，按 cache_read_tokens / input_tokens 汇总；字段缺失时标记为未采集。固定滑动窗口折叠会改写早期 ToolMessage，因此不能声称完整历史 Append-Only。只有请求 payload 对比证明工具 Schema 顺序或系统提示词存在实际抖动时，才提出对应修复；当前 UTC 日期位于静态系统提示词尾部，不能据此推断静态前缀整体失效。

## 4. 实施阶段

1. **Phase 0：基线与前置条件。** 对齐未提交上下文治理改动；跑现有测试；使用 verification.md 固定的公开仓库提交、任务、解析模型和预算，采集串行基线。
2. **Phase 1：有限委派入口。** 仅 Pro/Ultra 暴露 task；新增受限 code_explorer；补齐委派触发说明和短证据报告约束。
3. **Phase 2：预算与行为契约。** 复用并发限制；验证 Run 聚合用量、并发额度边界、输出上限、子 namespace 隔离、取消和失败处理；发现预算漏洞则先修复再启用。
4. **Phase 3：对照验收。** 运行单元/集成测试和经授权的公开仓库真实模型对照；按 verification.md 的门槛判定 done、partial、blocked 或 deferred。

## 5. 风险与应对

- 并发会增加子 Agent 总输入 Token：同一 Run 预算必须覆盖全部 namespace 和在途模型调用；仅在响应后累计会有额度超调风险，测试未证明边界前不得启用委派。
- 多个子任务可能重复搜索同一材料：任务说明必须划分不重叠范围，父 Agent 合并时保留来源和冲突。
- GitHub 工具只支持公开仓库且会落来源证据：保留公开访问限制、路径校验、哈希校验和 namespace；未能证明隔离写入时不向子 Agent 提供该工具。
- 真实模型结果有随机性：实施前后两组各运行 3 次，比较中位数；只用公开仓库内容，逐次记录时间、模型版本和提交 SHA。
- 当前相关实现未提交：Phase 0 不通过时不进入实现，避免在错误基线上继续叠加。
