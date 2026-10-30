# 基线失败根因与前置修复

日期：2026-10-28；更新：2026-10-29。关联任务：T0.B、T0.G、T0.S、T1.2/T1.3 与 T2.1–T2.4 的离线准备；Pro模式与角色离线门禁已通过，真实模型对照继续。

## 工作区

实现仅位于 `/Users/lijiaxin/.codex/worktrees/subagent-baseline-20261028/ai-agent-platform`，基于 `78aa17177ca597443bd708e741d60312e1d4a600`，尚未提交或合并。项目文档先在主工作区维护，验收整理时同步到实现 Worktree。Pro delegation 已在开启状态通过63项测试；根据用户放宽预算的新指示，为新1M同额度串行组临时设为False，随后恢复True测委派。

## 预算链路

- `runtime/token_budget.py` → `RunTokenBudget.reserve_call/release_call/record_call`：响应后记账改为共享锁下输入估算与最大输出预留，调用结束释放。
- `observability/usage.py` → `RuntimeUsageCallback.reserve_model_call` 与 dispatch guard：所有 scope 共享准入，未知用量拒绝继续；实际账本与内部预留分离。
- `runtime/modeling.py`：显式限制输出预算，支持回调预留。
- Platform API 的 SDK/Usage 投影、Platform Web 的 budget 类型及通知解析：允许尚有剩余额度的准入拒绝，修复原 Usage 502。
- 输入是 4 字符/Token 加 25% 边际的通用估算，不能声称精确 tokenizer 或供应商账单硬封顶。

## GitHub 边界

- `dearflow_agent/tools/github.py` → `build_github_tool`：原 `git/trees/{ref}?recursive=1` 改成逐层目录定位与目录分页。相同固定 SHA 的递归响应实测 4,337,791 bytes/15,778 entries，而根目录只有 14,308 bytes/61 entries；前者在 HTTP 2MiB 上限处已失败，后置 120 项截断无效。
- `file/readme` 保留完整源码哈希证据，模型只接收带真实行号的窗口、不可变 URL、next_line。单行过长明确标为 line_truncated，不把截断内容当完整证据。
- GitHub skill 禁止通过 read_file/execute 读回审计 evidence；新增后段行窗口读取消除这一限制导致的不可达区。
- `tools/errors.py` 注册目录不可用错误，使预期工具错误可安全返回。
- 对应测试在 `skills/test_research_batch.py`；真实只读 GitHub 探测验证根目录、子目录、后段文档与哈希/namespace。

## 固定输入开销

正式 Run `a0a83cac-804c-4caa-94df-aa056ff21dda` 已无目录 HTTP 错误，但三次模型输入为 27,061/28,840/30,934 Token，第三次后额度不足，仍未进入源码事实交付。不能只修目录错误后继续重复消耗同样样本。

离线最终工具绑定观测发现，26 个图表工具 Schema 约 50k 字符。现已复用既有图表技能要求的读取 references 步骤，按需向模型展示相应 Schema；工具注册、参数验证、权限和审批保持原实现。真实首输入 27,061→12,402 Token。此项作为两组共同前置条件，重新采样，不与之前失败样本混算。

2026-10-29 又发现两个独立问题：串行模型持续逐层遍历 src，未及时交付；预算预留拒绝发生在调用回调时，会绕过 `end` 模式原有的响应后判断。前者增加通用的 README/文档优先、最多两轮目录定位与同轮批量读取规则，不向模型提供验收答案；后者在 `TokenBudgetMiddleware.wrap_model_call/awrap_model_call` 只捕获明确预算耗尽，安全交回尚未完成提示，未知用量和其他错误继续传播。35 项预算测试通过。当时两组共同使用此行为、不提高Run额度；用户后续于2026-10-29允许放宽预算，当前新对照额度见plan.md第7节。

## 图级契约

- `test_subagents.py` 使用实际编译的父/子图覆盖四任务三槽、单槽释放、取消、单子失败和超长报告；超长正文留在子 namespace，父报告≤4,800 字符且明确标注截断，尾部证据仍保留。
- `test_delegation_budget.py` 使用父模型与三个屏障子调用，证明共享账本在途预留与实际结算。
- `observability/usage.py` 保留祖先任务实例 ID，只归一末级模型步骤；修复不同子调用被全部压成 `[tools, model]` 的旧缺陷。
- `tests/observability/test_usage.py` 的记忆用量失败源于未等待已异步化的抽取。测试现在显式 `drain_tasks()`，未修改记忆生产代码。

## 当前证据

- 前序预算链路定向验证：Runtime 73、API 37（另 266 subtests）、Web 31 passed。
- 本次源码工具与旧模式测试先失败后修复；`test_research.py` 28 passed、1 skipped。真实 Langfuse/外部搜索 opt-in skip 不计通过。
- GitHub 只读实测三项通过；Ruff 检查 github/test_research/test_research_batch 通过。
- 并发、最终 Schema、取消、单子失败、共享预算及结果边界均已有真实编译图测试；仍缺真实委派对照，不能用确定性测试替代模型效果验收。
