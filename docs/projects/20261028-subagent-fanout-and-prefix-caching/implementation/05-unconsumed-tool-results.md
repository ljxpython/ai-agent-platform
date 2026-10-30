# 保留尚未消费的并行结果与本轮委派摘要

## 范围与根因

2026-10-29，T0.P，共同前置修复。v3委派首轮的子报告明确出现“目录/README已折叠，未读到正文”，父Agent交回三份子报告后又持续读取同类来源。`prune_messages_for_model()`原来不区分消费时机，只保留最后四个ToolMessage；同一AIMessage并行请求六份来源时，前两份在模型第一次看到前就被替换为占位符。本轮task短摘要在后续读取后也被当作陈旧原始输出折叠。

## 最小修改

- `apps/runtime-service/src/runtime_service/middlewares/tool_output_pruning.py`：从最近AIMessage的tool_call_id集合识别最新批次，保护该批次全部结果；从最后一条HumanMessage之后的task调用识别本轮受限委派报告，继续保留。其余旧工具输出、旧用户回合的task报告仍按既有数量/最小字符策略折叠。
- 不新增状态字段、配置、依赖或第二套摘要服务；同步/异步模型入口及整理计数继续复用同一投影函数。`model_copy`仍只生成模型视图，不改Checkpoint原文。
- task报告的单份大小仍由现有filesystem中间件限制；取消、并发、只读权限和共享Token预算不变。
- 调用点检索覆盖middleware导出、DearFlow主/子图以及ConversationOffloading计数；通用`task`命名来自已注册委派工具，不按工具输出中的自述判定。

## 验证与证据

- 新回归先红：**2 failed、5 deselected**（11.40s），分别复现最新六条批次提前折叠、当前回合task报告丢失。
- 修复后pruning/offloading组合：**43 passed、5 warnings**（11.27s），`.local-stack/phase-batch-pruning-tests.log`。
- 新测试还覆盖消费后的旧批次可正常折叠、旧回合task可折叠、原messages不变；完整Subagent/共享预算/装配组合继续执行，结果另记verification。
- Ruff通过；首次错误调用`uv run ruff`因项目未安装该命令未执行检查，随后使用已有工具环境`uv tool run ruff check`通过，不计失败调用为通过。

## 真实采样边界

v3公共源码一直保持至首轮委派自然终态：Run `c2c27d29-0b5f-4963-9afb-dd63fc80299f`，总977,195 Token、stop_code=token_budget_exhausted、最终仅预算提示。该组与先前v1/v2一样保留为诊断，不混入修复后的效果对照；没有用新成功样本替换旧失败。

同一隔离Redis达到512MiB/noeviction限制并出现event transport unavailable，因此v3捕获的root整理为0只能标为“观察值”，不能证明完整事件未丢。新组采样前只将本环境Redis容量改为1GiB、不删除任何key或数据库；公共配置与该资源改动一起预登记。默认产品与其他环境不改变。
