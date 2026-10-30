# 第七次烟测与消息流复核

2026-10-29。T5.7已获用户人工批准并实施，仍处于Phase验证；本记录不代替正式两臂、泛化或Final。

## 第七次完整烟测

Run `fd6eae0e-6e7c-44a9-8be0-3cc8ce8380be`，Thread `66aa1bb4-3170-4e1f-bdbe-32ace15b769e`。正式Web→API→Runtime，xiaok `deepseek-v4.1-flash`，配置窗口131072、输出8192、累计Token限额关闭。正常终态并不等于质量合格。

| 指标 | 实际结果 |
| --- | --- |
| Usage | 40/40完整，私有请求profile可关联，总账对平 |
| 主级 | 5次，输入93578，输出6099，单次峰值24582（18.75%） |
| 子级 | 35次，输入733326，输出29382，峰值42670 |
| 全部Token / 耗时 | 862385 / 约478.23秒 |
| root自动摘要 | 0 |
| 来源 | 66份（子61），固定SHA、hash及Git blob核验通过 |
| 交付 | 16135字符；注册表发现均保留，但additions又重复转述已有发现 |

人工按原五项语义评分：1/2/3通过，4/5失败，合计3/5。第2项接受最终报告跨行表达：Token压力、最老平衡区间压缩及LLM摘要、`/compact`、先剪枝、基础默认启用均有陈述，不要求固定措辞。第4项未说明subagent在agent-loop之外；compaction的同类陈述不能替代。第5项有进程内fresh/fork与已完成历史、进程外形态，但未说明父级发现子级；`list_agents`名称或向直接父回执不能替代发现行为。

缺漏已经出现在子overview，不能再归因为父级静默丢字段。主级派发时把原问题扩成exports/注册/参数审计清单，是本次轨迹中可见的范围偏移；不能据此宣称单一因果已经实验证实。

原始`.local-stack/v27-full-smoke-7-terminal-read.json` SHA256：`969a54da4cde3d5e28100764b3494cf984f7cb21e328ea213731bfd9cdb94376`。同名audit/report/sources/context/citation-windows及start/collect/implementation-hashes证据全部保留，不补成功替身。

引用窗口机械结果为45窗口、48引用，其中一条未覆盖。人工复核：正文真实引用为`packages/compaction/compaction-basic/src/index.ts#L329-L346`，root实际窗口L327–386及L316–375覆盖；理由列的“同文件 #L329-L346”被解析器归给同一行另一README路径。机械失败结果保持原样，人工标记该误归属，不冒充自动全通过。

## 消息流疑似缺失：已排除业务故障

初读采集文件只见158条root消息且没有最终表格，曾怀疑V3流缺失。复核发现原`v27-capture.js`按全网络字节达到30MB后，在内部空catch中静默停止保存；该订阅实际收到约139.53MB，末尾业务事件已超出保存区间。**采集缺失不能当成业务丢消息。**

通过原Thread既有事件接口，按cursor补读原Run末尾，不重新运行模型、不修改checkpoint：

- `.local-stack/v28-smoke-7-root-replay.json`保留原事件，root `messages` seq27266恰有一个最终表格。
- 其AIMessage ID `lc_run--01a1862b-69dc-7690-8fc6-50e2547ecf58-0`与checkpoint一致，16135字符正文逐字相等；seq27303为成功终态。
- 新增正式Worker `invoke_graph()` V3执行适配器测试，与legacy流一并覆盖串行和委派，`v28-stream-reproduction.log`为4 passed。SDK模型副本抑制与节点输出方案无需为此增加发布钩子。
- 该补读证明服务器原事件中存在最终消息；没有把回放冒充本次实时浏览器逐帧捕获。后续烟测使用新采集器核验实时交付。

新私有`v28-capture.js`保留root消息、工具/更新/生命周期/自定义事件，计数但不存子级逐Token及checkpoint/value/debug大帧；来源另由原source capture保存。上限按实际保存字符计，超过时显式标记error，禁止据不完整采集判流成功。新浏览器tab装载，避免旧init拦截器叠加。

## 后续修正及回归边界

- `ResearchSynthesis.additions`的Schema与已有纠错提示明确只接新增证据发现，已有发现通过decisions处理；无新增时留空。最终按原问题整体覆盖检查，不能把引用全有决定当成原问题完整。
- 任务工具及主提示同步：逐字保留对应用户子问题及并列对象，只补必要来源/背景，不另定交付格式或扩大审计清单。子overview的Schema优先保留权威概览开头的定义、架构角色和调用者行为；没有植入DSH事实/评分路径。
- 扩大旧回归`v27-dearflow-phase-regression.log`为20 failed、241 passed、45 skipped；19项旧plain-text夹具未适配，另1项Docker执行环境失败。Docker不启动、不计通过。
- `v28-research-fixtures.log`为2 failed、71 passed、1 skipped；原19项夹具通过后，测试模型覆盖父类bind_tools导致两个图表Schema spy未记录，已修正为保留父类钩子。完整服务专项回归仍在执行，未预填通过。

应用修改仍仅在所属Worktree，保持既有权限/预算/并发/取消契约及所有失败材料。正式六次、nanobot和Final尚未执行。

## 第八次烟测及纠错指令分离

Run `bcf342d2-4b9e-40a8-b092-b6c54f2b668f`，Thread `90f99ecb-941d-4a5c-a3b8-f6e568064353`。6次均为主级，输入117273、输出5554、总122827；峰值28727/131072=21.92%，103.98秒，Usage6/6完整且对平，root自动摘要0。10份来源全部固定SHA/hash通过，5窗口/19引用机械覆盖。4997字符报告原门槛2/5：1/3通过，2漏摘要较早历史，4漏subagent主循环外，5漏父发现。不用未知标注或列表API名补分。模型未调用task，不能作为委派成功样本。

已核验原Run受信策略快照：Pro，tool_overrides为空，没有task禁用；代码Pro delegation为True。仍不能仅据此证明供应商实际收到的每个Schema内容。本次profile有40/41个工具声明。不会通过换模式或变更评分把它记成委派通过。

实时捕获root最终`messages` seq690恰一次，AIMessage ID/正文逐字等于checkpoint，seq727终态。新采集器未触发保存上限；旧Thread残留订阅的中止单列，不混入当前Run。原始SHA256 `6c948403f92c9b3df911b5035741cd4396714b8d3c45f1d644cc5c03492bf46f`，原始/audit/sources/context/citation-windows/源hash均保留。

发现组合中间件正常注入复用了“验证失败、在剩余预算纠错、不要重新研究”的反馈，虽然文字允许补缺口，仍形成错误阶段暗示。修复为`SYNTHESIS_INSTRUCTION`（研究完成后交付，先依原问题研究/委派）与`SYNTHESIS_FEEDBACK`（仅真实校验失败）分离，沿用同一Schema/调用次数，不加审稿或调度。

新增断言正常首个组合请求不含失败/停止研究措辞。`v29-composition-phase-regression.log`：31 passed、1 skipped（35.56秒）。第九次独立原题烟测Run `59765d3f-6b26-4cfd-8895-91649998721a`已发起，等待真实结果；不混入正式组。

回归补记：`v28-dearflow-regression.log`为2 failed、252 passed、45 skipped，两个旧委派描述字符串断言失败，修正后`v28-agent-fixture-recheck.log`24 passed（79.67秒）。`v28-local-tool-boundaries.log`8 passed、1 deselected，唯一Docker integration明确未运行。`v28-budget-privacy-regression.log`先94 passed/1 failed，缺合法收尾夹具；修正后`v28-budget-privacy-recheck.log`96 passed（35.38秒）。扩大容灾组合先10 passed/2 failed/9 skipped，新增角色预期与收尾夹具同步后`v29-composition-privacy-resilience.log`37 passed/9 skipped（37.73秒），两个只读角色均核验隐私和子级容灾。不同集合重叠，不能累加为唯一测试数。Ruff通过；未使用skip替代通过。
