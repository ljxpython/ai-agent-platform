# 子概览与有界证据组合接入

2026-10-29，用户明确批准28号修订后实施。对应T5.7；应用源码只在`/Users/lijiaxin/.codex/worktrees/subagent-baseline-20261028/ai-agent-platform/`修改，本文不代替tasks.md进度与正式语义验收。

## 实现

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents/report.py`：`ResearchReport`改为必需`overview`及最多4条补充，保持紧凑JSON4800字符总限额；两个子角色及既有纠错消息同步。overview继续使用结论、条件、来源、置信度、未解点，不加入原题答案字段。
- `.../middleware/synthesis.py`：主级ToolStrategy预注册`ResearchSynthesis`，按实际只读调研工具/研究委派启用；普通聊天、计划/维护以及已进入其他工作流程继续沿用原输出。串行使用相同Schema的additions；没有单独模型、调度器或调用额度。
- `ResearchSynthesisMiddleware.before_agent()/before_model()`：私有图状态按真实Run重置，SDK恢复同Run保留；仅匹配本Run实际task调用及成功、合法的`ResearchReport`。当前Run发现以task调用ID和发现序号派生引用；历史、失败报告不能进入注册表。私有状态不传给子图。
- `validate_decisions()/render_synthesis()`：每条当前发现必须恰好有一次include/disputed/excluded决定，后两者必填理由；拒绝漏条、重复和陌生引用。程序保留原结论/条件/来源/置信度/未解点以及报告总未解点，争议/排除有明确列；转义HTML、表格分隔符和换行。unknown不升级。组合输出总JSON限18000字符、最多50条决定/15条主级补充，不修改8192模型输出配置。
- 注册表在模型视图只提供一次，原task消息临时替换为注册表指针，checkpoint保留原报告；即使旧工具视图已剪枝，父级仍能看到全部有界发现。没有把任意来源全文复制进注册表。
- `ResearchSynthesisStreamMiddleware`位于模型选择之后：模型副本加`nostream`，原响应在模型节点返回前转换成唯一Markdown AIMessage。成功响应不保存原Schema工具交换；失败Schema交换完整省略，改为有界SystemMessage反馈，避免向页面发送原始JSON，同时不留下失配工具消息。纠错仍由SDK循环使用原剩余预算，最终缺合法响应明确失败；Schema与执行工具混合批次不执行其副作用。
- `.../agent.py`：只在主图装配上述两层钩子，保留Token、调用/超时、工具权限和并发中间件。已标记的显式Token额度停止沿用原终态，不被组合校验覆盖。

未加来源原句绑定：本修订允许优先交付overview和有界组合，子报告4800上限保持。Schema证明交接/组合字段保留，不能证明来源或子概览语义准确。

## 已执行的Phase验证

日志均在所属Worktree`.local-stack/`：

| 证据 | 结果与范围 |
| --- | --- |
| `v27-synthesis-regression-initial.log` | 首轮13 failed、58 passed、1 skipped，保留。既有测试末尾plain-text夹具需同步新契约；另发现限额结束后缺少组合校验及内部纠错消息被误判其他流程，已修复；测试模型副本的序列游标与外部取消用真实任务取消验证 |
| `v27-synthesis-regression-2.log` | 71 passed、1 skipped，154.47s；子/主装配、并发/失败/取消、Usage/显式Token预留、报告、权限/错误处理 |
| `v27-synthesis-boundaries.log` | 35 passed，66.03s；字段保留、HTML/表格转义、缺条/重复/陌生引用、unknown、末轮Schema唯一工具、单一messages流与checkpoint一致、串行、预算内纠错/耗尽失败、外部取消、跨Run清空、普通聊天/计划/维护、混合批次无副作用、SDK真实子图私有状态及未授权工具/其他Schema拒绝 |
| Ruff | 上述源码与直接改动测试全部通过 |

回退只撤本轮源码/夹具接线，保留既有Run/Usage/来源及失败日志；无迁移和生产部署。真实Platform烟测、正式六次、nanobot与Final仍需继续执行，不以此认定研究质量完成。
