# Phase 5：另一公开仓库泛化预登记

2026-10-29，在本题模型调用之前冻结题目和评分；当前仅预登记，尚未运行。应用实现须与原题正式组一致，原题门槛通过后执行，不替代原题、不挑成功替补。固定一次Pro委派任务；失败如实记录，不据单例宣称跨任务稳定性。

## 固定输入

- 公开仓库：`HKUDS/nanobot`。
- 提交：`946a44b97a36381aed9ccf50262a1b6d68bb179e`。
- 当前待执行模型：xiaok `kimi-k3`，model ID `bcaf9543-5cc9-40cb-9848-d1fbe90cc086`，配置窗口262144、输出8192；provider实际窗口与部署fingerprint未知。原题最新独立检查和稳定组使用该配置，泛化保持同一实现及配置，不跨模型混算。
- 登记修订说明（首次泛化模型调用前）：最初登记的是xiaok `deepseek-v4.1-flash`（`070cced3-350b-42ec-b678-994dd07b7078`、131072/8192），该泛化尚未执行；现对齐原题Kimi配置。保留原登记历史，原问题、SHA、五项评分与两方向要求不变。原题正式门槛通过后才运行，仍只执行登记的一次，不补成功样本。
- 使用相同费用关闭/Usage开启、窗口headroom、执行调用/时间/循环保护、源码页与交接实现。提交前冻结应用源/环境及问题hash。
- 本地参考副本存在无关未跟踪目录，评分只用`git show <固定SHA>:<path>`读取已提交blob；公开raw的memory文档已与blob逐字核对，不能把工作目录额外文件当证据。

以下问题逐字发送，**不发送下方评分表及证据路径**：

> 请只基于公开仓库 `HKUDS/nanobot` 的提交 `946a44b97a36381aed9ccf50262a1b6d68bb179e`，调研两个互不重叠的问题：1）短期对话、压缩归档和长期记忆如何分层，Consolidator 与 Dream 各自何时运行、读写什么；2）scheduled automation、local trigger 和 heartbeat 的触发、后台依赖及结果投递有什么区别。若 task 工具可用，将两个方向拆开并行处理，最多两个 code_explorer 子任务；否则由主 Agent 顺序完成。所有 GitHub 文件读取都显式传入该提交 SHA。最终用中文表格逐项给出结论、不可变 GitHub `path#Lx-Ly` 证据、置信度和未解决点；不能从证据推出的内容标为未知，不要猜测。

## 独立评分表（不给模型）

| # | 必须保留的语义 | 固定SHA中的证据 |
|---|---|---|
| G1 | 活对话为session.messages；压缩归档为memory/history.jsonl；长期文件SOUL.md/USER.md/memory/MEMORY.md；GitStore记录长期文件变更 | `docs/memory.md#L15-L22` |
| G2 | 上下文压力时Consolidator摘要最旧安全片段并追加history.jsonl；append-only、cursor-based，归档不等于最终长期记忆 | `docs/memory.md#L30-L48` |
| G3 | Dream默认cron、也可手动；读新增归档及当前三份长期文件，单次增量编辑长期文件 | `docs/memory.md#L50-L61` |
| G4 | schedule按时间/间隔/cron、local trigger由本地命令、heartbeat为受保护的系统调度；后台依赖gateway，schedule通常回创建会话并每次报告，heartbeat只把有用/可行动结果送最近活跃目标，gateway启动时默认启用 | `docs/automations.md#L16-L30`、`#L55-L64`、`#L104-L116` |
| G5 | local trigger不自带公网webhook接收器；外部系统需自建接收服务后调用nanobot trigger | `docs/automations.md#L99-L102` |

每项必须结论和支持引用均正确；5/5且无虚构引用才通过本单例。观察窗口覆盖只算引用链证据，不等于语义正确。另核对至少两个真实code_explorer namespace、固定SHA、完整Usage、root自动摘要0、主峰值≤配置窗口50%。输出累计输入/峰值/耗时实数，费用缺价记unknown；不得因单例通过宣称工业级能力已全面验证。

## 待执行

- [ ] 原题正式组通过并确认源/配置未漂移。
- [ ] 正式Web → API → Runtime新Thread运行一次并留终态、子来源、Usage和root事件。
- [ ] 逐项评分、引用窗口及组成审计，记录实际结果；保留失败。
