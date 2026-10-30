# DSH预算对齐与下一步优化

日期：2026-10-29。关联T4.1/T4.2；预算范围已实现并完成Phase验证，整体项目仍进行中，原真实质量门槛未过。

## 授权与范围

用户要求“我们的token预算改一下，改成和dsh一样”，并同意此前故障分析。预算调整复用现有部署开关、DeepAgents摘要和Usage链路，不新增调度器、API/Web字段或依赖，不改变旧样本。源码与私有配置仍只在隔离Worktree；未合并、提交、推送或部署现役环境。

## 具体变化

| 位置 | 变化与原因 |
|---|---|
| `middlewares/conversation_offloading.py` → `_context_limits()`、`resolve_context_governance_settings()` | 复用受信窗口W/输出O；默认触发改为 `floor(min(W*0.8,W-O-B))`，原文保留改为 `floor((W-O)*0.16)`，B默认65,536。新增非负headroom配置；压力非正、token保留不小于触发时拒绝。已有显式覆盖的百分比仍以安全输入预算为分母，避免静默改写旧配置语义 |
| 同文件 → `ConversationOffloadingMiddleware.__init__()` | 将解析后的压力水位提供给剪枝。最终请求guard仍按原来的显式容量/当前模型取值，未把构图模型的profile强行冻结到备模型检查 |
| `dearflow_agent/agent.py` → `middleware()` | 主子图剪枝改用同一个自动整理压力水位；计数继续先看剪枝后视图，摘要/归档保留原始消息。旧结果超过300字符门槛后整段占位的策略尚未修改；300不是保留长度 |
| `.env.example`、Runtime开发标准 | 普通运行不启用累计费用上限；窗口触发/保留留空使用DSH默认，headroom单独说明；保留小窗口和显式配置兼容边界 |
| 隔离 `.local-stack/runtime.env` | `RUNTIME_USAGE_ENABLED=true`、`RUNTIME_TOKEN_BUDGET_ENABLED=false`，trigger/keep清空、headroom65,536。旧MAX_TOKENS值因开关关闭不参与新Run准入；不修改历史账本，不接续旧Run |

参考固定DSH SHA `477b4f420553e8a52c2fbccc464d7561b239c443` 的 `packages/compaction/compaction-basic/src/config.ts:153`。128K窗口/8192输出得到触发57,344（43.75%）、保留19,660；截图49%不是固定预算目标。仍保留平台最终请求安全余量、调用次数/时间/循环保护，因此不能把本次称作整个DSH运行时的等价实现。

## Phase验证

- 新增窗口策略红测：4 failed，确认旧128K触发98,877、旧1M触发800,536与DSH不同；随后实现修正。
- 预算/上下文/主子装配与共享预留：`tests/middlewares/test_conversation_offloading.py`、`test_token_budget.py`、`tests/runtime/test_token_budget.py`、`tests/services/dearflow_agent/test_agent.py`、`test_delegation_budget.py` → **128 passed、5 warnings，28.25s**。
- 工具剪枝、子任务、DearFlow/Showcase上下文组合（`-m 'not integration'`）→ **48 passed、2 skipped、1 deselected、41 warnings，52.67s**。小窗口fixture显式配1024 headroom。一次初始扩大运行发现两个小窗口fixture缺配置，修正；另外误纳入的Showcase Docker执行集成因执行结果不可确认失败，未计通过，未宣称全仓绿灯。
- 供应商溢出回归改用“重试请求实际Token减少”验证，而非消息条数；摘要加归档引用后条数可能相等，配对与错误分类仍验证。
- 关闭累计费用上限的组合测试在两次调用合计**1,200,002 Token**后正常返回并保留Usage，不读取费用预算；显式开启时的拒绝、未知用量、并发预留与恢复回归保持通过。
- 直接调用方补查：隐私与工具输出矩阵56 passed、5 warnings（15.09s）；小窗口fixture显式配置headroom，真实模型历史测试入口同步兼容但未重跑十次供应商摘要。
- 所属隔离Runtime PostgreSQL真实存储验证：两次整理/连接重建/官方wrapper回退与循环保护在自动/手动整理后恢复，2 passed、5 warnings（5.19s）；随机新测试Thread，不清理或覆盖旧基线。
- 合计234项Runtime/真实PG相关测试通过，另有3项Redis启动探针；两个skip不计通过。修改的13个Python文件Ruff通过，`bash -n scripts/local-stack.sh`通过。

### 正式Web → API → Runtime接线

- 使用`playwright-cli`新会话，由页面选择xiaok `deepseek-v4.1-flash`、Pro、8192输出，再点击发送；只读固定公开SHA的单份README，不作完整调研对照，不混入v23。
- Thread：`dd453501-506d-4182-843d-12d19a7c95e3`；Run：`da6a1372-ff6a-4217-b02a-c891c9f298a5`，status=`success`。
- 正式Usage HTTP200，`finalized=true`、`availability=available`、`token_budget=null`；两次主调用均为预期模型ID，2 observed/2 reported、0 missing/0 incomplete。
- 本次输入27,968、输出677、总28,645 Token。该短探针没有触发窗口压力，不能替代自动整理效果、累计百万真实消费或三次质量验收；超过百万继续调用的行为由确定性组合测试证明。
- 冻结清单：Worktree `.local-stack/v24-budget-smoke-manifest.json`，SHA256 `96bda23b9424c59653d5a279d30db928d510980b2b425e5c930e1a0653da4408`；原始返回 `.local-stack/v24-budget-smoke-raw.json`，SHA256 `7173a2213f51939031cf51cd0f7e9266dfd333ff68a71c1383e049c3fce835f0`；截图 `.local-stack/v24-budget-smoke.png`。
- 旧浏览器登录态过期使首次脚本在新建会话前停止；重新登录后才提交上述唯一新Thread/Run，未覆盖历史测试。

### 本地启动阻塞修复

首次启动Redis在加载旧AOF/RDB时返回BusyLoading，原探针立即退出并停止本次进程。修复所属`local-stack.sh`：只对BusyLoading作最多120次、间隔0.5s的有界等待，其他连接错误立即失败；不删除/移动Redis资料，不更改内存策略。实际重启成功，另有3项探针回归验证加载后成功、其他错误不重试、等待上限。见[仓库工具记录](../../../changes/20261029-local-stack-redis-loading-probe.md)。

## 下一步与验证顺序

1. **信息保留**：对照DSH的8192/4096/1024策略，同时审查1200 Token外置、4800字符上限和历史剪枝，避免8192阈值被前置截断遮住；先保证旧结果有实质预览、可回读原文及准确行号；覆盖长文本中段证据、超长单行、并行批次、落盘失败和checkpoint保真。先证明可恢复性，再用新轨迹判断重读是否减少，不把窗口重叠直接当遗忘。 验收至少包括中段证据可定位回读、原文hash一致、最新工具批次和本轮子报告不被误裁剪；不能仅比较Token下降。
2. **收敛与交接**：复用现有末轮撤工具机制，并覆盖显式费用上限预警；复用SDK原生结构化子报告，保留结论、条件、引用、未知项，验证父级整合覆盖。先解决结构化响应工具与末轮撤工具、4800字符上限的冲突；不另建调度器、不靠固定仓库答案补提示词。
3. **冻结对照**：上述行为稳定后，以同模型/原题/公开SHA重新执行完整两臂对照；保留全部旧失败，仍以五项事实齐全验收。分别报告窗口、整理、累计Token、缓存和质量，不用单一占用百分比代替成功率。

取消默认累计费用停机后，累计消耗仍可能增长；现有调用次数/时间限制仍有效。价格、供应商真实窗口元数据与同条件DSH实跑仍未核实，不宣称成本或成功率优于DSH。

## 本次环境收尾

正式Run终态和冻结源码hash核对后已关闭`subagent-budget-v24`浏览器，只停止所属`wt_bf33bcf838fd`应用及Redis；status确认五项均stopped。数据、原始Usage与截图保留，未destroy。
