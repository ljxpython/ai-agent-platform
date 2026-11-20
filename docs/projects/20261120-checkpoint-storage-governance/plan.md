# 长会话 Checkpoint 存储治理与 Delta 采用方案

启动日期：2026-11-20。级别：治理改动。用户明确要求独立立项，本项目统一规划长会话存储治理与平台接入；实施进度只维护在 [tasks.md](tasks.md)。GraphHarbor 同名关联项目独立维护通用引擎任务。

## 1. 用户过程与期望结果

用户在平台反复发送消息、运行工具和恢复审批，希望刷新页面后仍能阅读会话、继续执行，并在允许的范围内回滚运行。每一步都需要可恢复的状态，但不应为了保存一个新消息，反复复制这条会话从创建以来的所有 checkpoint 和 writes。

本次治理解决回滚基线重复存储和prune遗留blob，并将Reference Agent、平台助手消息迁移到官方Delta状态。活跃会话保持完整原文和idle30天，不开启自动恢复点裁剪；不能把减少存储开销解释成默认删除聊天记录、评测来源或时间旅行能力。

## 2. 2026-11-20 的事实基线

| 对象 | 已核对事实 | 证据范围 |
|---|---|---|
| 依赖 | 锁文件与本地安装均为 LangGraph 1.2.11、checkpoint 4.2.0、checkpoint-postgres 3.1.2、DeepAgents 0.7.8、GraphHarbor 双包 0.13.0.post48 | 仓库和本地环境，不代表所有已部署进程 |
| Dear Agent / Showcase | `OffloadingState` 继承 `DeepAgentState`，消息 channel 为 `DeltaChannel`，`snapshot_frequency=50` | 状态注解、构图入口和无模型调用的编译检查 |
| Reference Agent / 平台助手 | 普通 `create_agent` 默认消息 channel 为 `BinaryOperatorAggregate`，使用 `add_messages` | 构图入口、依赖源码和无模型调用的编译检查 |
| 回滚基线 | GraphHarbor 的 `capture_baseline()` 在每次 Run 首次 claim 时读取整条 Thread 的 checkpoints/writes，并保存完整投影 | 源码；无数据库内存桩确认历史条目随历史长度重复复制 |
| prune | 当前会保留 Delta 必要祖先，但删除阶段没有回收 `checkpoint_blobs` | 源码；无数据库内存桩确认这条路径没有 blob DELETE |
| 会话到期 | 平台已有 idle 30 天策略，GraphHarbor 已有通用到期和可靠删除循环 | [生命周期项目](../20261030-session-and-runtime-retention-governance/README.md)；本轮没有重验现役调度 |
| 摘要 | 已安装 DeepAgents 摘要通过 `_summarization_event` 改模型视图，保留原始 `messages` | 安装源码；不能把模型输入变短当作状态或数据库已经缩小 |

已确认的是机制，不是本轮生产容量或 OOM 根因。10 月字符串夹具的节省比例、耗时和 Defer 决策保留为历史证据，不能充当当前真实 Agent 的容量结论。

### 当前可定位的源码

- 依赖：[pyproject.toml](../../../apps/runtime-service/pyproject.toml)、[uv.lock](../../../apps/runtime-service/uv.lock)。
- 已有 Delta 状态：[conversation_offloading.py](../../../apps/runtime-service/src/runtime_service/middlewares/conversation_offloading.py) 中的 `OffloadingState`；[Dear Agent](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py)、[Showcase](../../../apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py) 的 `state_schema`。
- 普通 Agent：[Reference Agent](../../../apps/runtime-service/src/runtime_service/services/reference_agent/agent.py)、[平台助手构图入口](../../../apps/runtime-service/src/runtime_service/services/platform_assistant/approval.py)。
- 平台业务期限：[retention.py](../../../apps/platform-api/src/platform_api/modules/runtime_gateway/application/retention.py)。
- GraphHarbor 工作仓库为本仓相邻的 `../graphharbor`，完整引擎方案在[GraphHarbor 存储治理项目](../../../../graphharbor/docs/projects/20261120-checkpoint-storage-governance/plan.md)。不得修改安装目录的 site-packages 来交付修复。

## 3. 两仓与各服务的责任边界

| 所有方 | 本次负责 | 明确禁止 |
|---|---|---|
| GraphHarbor 的 `libs/langgraph-runtime-pg` | 通用 Run 基线/撤销日志、channel 与 namespace 依赖、事务锁和执行代次屏障、blob 可达性、安全 prune/GC、通用维护统计 | 识别具体 Agent、业务工具、模型供应商、平台角色、评测业务或 Workspace 目录；硬编码 30 天等平台政策；自行替换图的 reducer |
| GraphHarbor 的 `libs/langhost` | 复用通用鉴权入口和 CLI/REST，传递获准 Thread 集合及明确操作，报告实际完成/拒绝/失败 | 在 HTTP handler 拼装业务清理 SQL；把平台专有字段加到通用协议或数据库 |
| 本仓 `runtime-service` | 选择 Agent 的消息 schema/reducer、摘要及模型输入策略；受管工具、文件和业务资源；接入正式 GraphHarbor 版本 | 自建第二套 saver/GC；直接跨服务删除引擎表；把业务策略推入 GraphHarbor |
| 本仓 `platform-api` | 用户权限、会话保留与恢复点政策、资料与评测来源的业务保留语义、明确受鉴权的维护动作 | 直接扫描/修改 GraphHarbor 数据库；通过任意客户端配置控制底层删除 |
| 本仓 `platform-web` | 验证用户可见历史、审批、恢复和时间旅行的实际表现；政策变化时明确告知保留范围 | 以本地缓存充当历史事实源；用前端删列表替代持久清理 |

边界是验收条件：GraphHarbor 的核心源码、迁移、SQL、配置和日志标签不得新增使用方业务概念。其独立测试使用确定性通用图；真实业务/模型验证放在本仓。GraphHarbor 不依赖本仓源码、数据库或私有配置才能安装运行。

## 4. 已有授权与待讨论决定

| 项目 | 当前结论 | 实施约束 |
|---|---|---|
| 回滚基线与blob回收 | 用户批准全部实施，并另行确认反向JSON Patch投影与绝对预算 | GraphHarbor正式post49已交付；平台仅接入正式包，不新增业务引擎分支 |
| 旧实现兼容 | 用户明确不要求兼容，采用单一目标实现 | 不新增旧格式双读、旧版本 fallback、长期双写或历史 reducer 分支；不顺带重构无关 v2/v3 代码 |
| 普通Agent迁移Delta | 在用户开始全部实施授权下采用已讨论建议，Reference/平台助手已迁移并验证 | 继续create_agent，仅使用公开DeepAgentState消息语义与周期50，不新增Deep Agent行为；教学Workflow保留普通聚合 |
| 活跃会话历史裁剪 | 本轮保留完整原文、idle30天，不增加活跃自动prune | 未新设恢复点窗口；以后若要求绝对上限，需另定原文、fork和评测来源契约 |
| GraphHarbor 正式发布 | 用户明确授权，为本次验证可直接发布 | 通过源码/候选门禁后，双包锁步使用新的唯一版本；仓库外凭据只注入发布进程，不输出、不复制、不入文档 |
| 平台 Worktree 与 main 交付 | 2026-11-21 用户明确本仓涉及的开发在独立 Worktree 进行，功能全部完成后迁回本地 main | 完成本次批准范围和必要验收后才合并，保留主工作区既有修改；该授权不扩为远端推送、GraphHarbor 仓库 Git 操作或现役部署 |
| 生产与既有数据 | 包发布和本地 main 交付均不等于生产切换或数据销毁授权 | 不因可以发包或合并而重启、迁移现役服务或清空既有库 |

使用方无需再次提供已授权的发布许可。GraphHarbor 凭据位置按其[发布规范](../../../../graphharbor/docs/standards/release-process.md)读取；规划阶段无需读取密钥。

## 5. 总体实施顺序

1. 冻结两仓源码、当前依赖和可重复合成夹具，测量 checkpoint、writes、blob、回滚基线/新日志的逻辑字节、查询条目、WAL、claim/恢复耗时与 Worker 峰值 RSS。
2. 在 GraphHarbor 用必要的运行边界和受影响行撤销日志替代完整历史基线。修复后仍能安全撤销目标 Run、拒绝后继依赖并恢复审批与投影。
3. 在相同写屏障下计算存活引用，保留必要 Delta 祖先/快照和 pending writes，回收无引用 blob；以有界批次完成，不全量加载历史到 Python。
4. 先通过 GraphHarbor 的独立图、数据库、并发和故障验证，再构建并发布双包，从正式源独立安装验证；本仓随后精确锁定已验版本。
5. 普通 Agent 迁移若确认采用，在本仓实现单一 Delta 消息状态，完成消息语义、审批、队列、更新、fork、历史展示和重启验证。
6. 活跃历史政策若确认改变，另按已批准的窗口接入通用维护。政策未定不阻塞基线/孤儿 blob 修复，但不启用自动裁剪。

GraphHarbor 不负责把所有图改为 Delta。即便本仓普通 Agent 迁移，引擎仍须支持使用方明确声明的合法非 Delta channel；这是当前通用能力，不是为旧版本写兼容分支。

### 平台 Worktree 开发与 main 交付

本节为2026-11-21用户明确要求，覆盖本仓所需依赖、产品改动、测试和迁移。已建立独立分支feat/checkpoint-storage-governance及登记wt_3b7f1734875d；实际环境见P02，本地Git交付状态只看P07。

1. 实施前检查主工作区和未提交修改，从 main 建立本项目独立 Worktree/分支，记录起点与实际目录。本项目未提交规划文档按清单带入，不能夹带或覆盖主工作区的无关修改。P02 记录实际环境，禁止直接在 main 开发平台产品代码。
2. 按[Worktree 开发与资源隔离规范](../../standards/worktree-development.md)通过现有 local-stack 工具初始化、安装依赖并检查环境。数据库、Redis、Workspace、端口、进程和安装目录均属于该 Worktree；不复用主工作区或其他 Worktree 的可写资源。跨仓正式包接入仍遵守 P03。
3. 在所属 Worktree 完成本次批准范围的功能、单元/集成/完整链路测试，以及适用的容量、安全与数据恢复验收。范围调整需明确记录，不能把未完成或失败项静默排除，也不能以某个阶段通过代替全部功能完成。
4. P07 确认实现和必要验收全部满足后，再通过 Git 合并迁回本地 main；迁回前核对最新 main、处理冲突并验证，迁回后执行必要回归并记录结果。保留主工作区既有未提交内容，不以目录覆盖代替合并；未满足条件时不提前迁回。资源清理按原隔离规范执行，远端推送和现役部署不包含在本条授权内。

## 6. 普通Agent采用Delta的决定与验证要求

### 为什么建议迁移

平台助手会长期续聊，Reference Agent 也可能被扩展为长会话。频繁变化的消息列表适合增量存储。统一消息 channel 还能让普通 Agent 与现有 Deep Agent 使用相同的存储验证矩阵，减少两套增长特征。

迁移只改变消息持久化方式。两处普通Agent继续create_agent，传公开DeepAgentState复用官方Delta消息reducer与周期50，不增加文件系统、子代理、工具或摘要，不另写消息合并算法。实际compiled graph、状态转换、审批、队列和浏览器证据见verification。

### 必须验证的行为

- ID 在消息首次进入持久化前稳定；同 ID 更新、`RemoveMessage`、清空/覆盖、并行批次及空写入均能精确重建。
- tool call / tool result 的 ID、顺序与配对不变；审批期间新消息不会绕过队列、取消或执行代次保护。
- 普通 `invoke`、流式、`update_state`、中断/恢复、fork、worker 重启与失败重试都得到相同的预期状态。
- `state_schema` 与所有 middleware 合并后的实际 compiled graph 中，`messages` 确实是目标 `DeltaChannel`，不能只检查源码注解。
- 不变更普通 Agent 的模型、工具、授权、提示词、摘要行为或对用户公开的消息内容。

### 周期快照与收益边界

以现有 Deep Agent 的 `snapshot_frequency=50` 作为测量起点，对 10/50/200 三个有限夹具值对照后选择单一实现值；这些是实验输入，不是已批准的服务等级承诺，也不新增用户配置面板。

若状态无限线性增长且保留全部周期快照，累计快照开销约为 `O(N²/K)`，加增量开销 `O(N)`。因此验收不得声称“固定 K 加永久保留必然严格线性”。同样，Delta 不限制当前 `messages`、模型视图、API 投影和浏览器缓存的内存。

## 7. 活跃会话历史怎么保留

必须区分四类内容：用户可阅读的会话原文、模型当前上下文、用于崩溃恢复的 checkpoint、可供时间旅行/回滚的历史恢复点。它们可能引用同一批数据，但不应默认采用同一期限。

**本轮实施决定：** 保留当前30天闲置会话生命周期和完整原文，不开启活跃Thread的keep_latest自动任务。已消除引擎基线复制与无引用blob；恢复点新窗口不在本次批准开发范围。

后续若要限制活跃 Thread 的恢复点，平台必须明确用户仍能看什么、能从哪些点 fork、评测来源是否继续可读；GraphHarbor 只执行使用方显式选择的通用保留/裁剪动作。不能在引擎中实现“用户读过就保留”“评测集引用就豁免”等业务判断。

当前 DeepAgents 摘要保留原消息状态。因此仅保留最新 checkpoint 仍可能保留很大的消息列表。若要求活跃会话内存和原始历史存储也受固定上限约束，需进一步批准原文归档/分页和工作状态压缩的产品契约；本方案不偷偷增加聊天归档服务，也不使用 TTL 冒充解决活跃增长。

## 8. 单一新实现与数据切换

不开发旧 saver、旧 schema、旧 channel 表示的在线兼容路径；目标 LangGraph/checkpoint/DeepAgents/GraphHarbor 组合必须精确冻结，API 与 Worker 同组合运行。官方记录中涉及早于 LangGraph 1.2.13 的 `update_state`/Delta 问题须有最短用例验证，不能只看“版本属于 1.2”。

旧运行代码不需要继续读取新格式。已有数据若需保留，采用一次性维护窗口转换，并核对 messages、命名空间、审批、回滚和文件引用；无法证明无损的条目应停止转换并报告，不能默默丢弃。用户“不考虑兼容性”不等于允许删除现有数据。

切换前排空或持久暂停所属运行，备份并验证可恢复的数据与配置；转换后只运行新格式代码。失败通过恢复演练过的备份/快照或修复后前进恢复处理，不增加运行时旧逻辑 fallback。不得承诺旧包能读取新格式。

## 9. 任务与证据交接

GraphHarbor 的日志、GC、迁移和正式包任务只记在其[独立引擎任务清单](../../../../graphharbor/docs/projects/20261120-checkpoint-storage-governance/tasks.md)；本项目只记录版本接入、Agent 状态、业务保留决定及联合验证，不复制引擎开发进度。

验证矩阵在[verification.md](verification.md)。本项目Phase与Final独立，旧v3浏览器验收留在原项目。维护绝对预算已由用户冻结，具体见文末；隔离迁移窗口及恢复已演练。业务恢复点新窗口未采用，不将永久历史容量上限伪装成已批准承诺。

### 官方资料核对入口

以下为 2026-11-20 核对的官方文档，具体 API 仍以实施时冻结的源码与测试为准：

- `https://docs.langchain.com/oss/python/langgraph/checkpointers`：默认存储、Delta 依赖与安全裁剪。
- `https://docs.langchain.com/oss/python/langgraph/pregel`：Delta reducer、周期快照和格式切换约束。
- `https://www.langchain.com/blog/delta-channels-evolving-agent-runtime`：官方解释周期快照仍有二次增长项，以及常见会话长度下增量项占主导的收益边界。
- `https://docs.langchain.com/oss/python/releases/changelog`：2026-05-12 的 LangGraph 1.2.0 / DeepAgents 0.6.0。
- `https://docs.langchain.com/langsmith/agent-server-changelog`：后续 Delta、`update_state` 与裁剪修复；不是 GraphHarbor 已复现故障的证明。

## 10. 历史资料与项目关系

[10 月 Delta 调研](../20261004-langgraph-v3-delta-evaluation/README.md)和[会话生命周期治理](../20261030-session-and-runtime-retention-governance/README.md)作为事实与历史证据来源。本项目独立维护方案、任务和验收；历史测试数、决定及未完成项不自动计入本项目。

## 2026-11-21 实施决策与验收预算

用户已批准开始实施全部开发项。平台在独立 Worktree 的 `feat/checkpoint-storage-governance` 分支开发，资源登记 `wt_3b7f1734875d`；完整验收后才迁回本地 main。GraphHarbor 仍独立交付通用底座，不新增 Git 或现役部署授权。

用户另行确认投影恢复使用标准 JSON Patch 反向差量，替代原优先从 checkpoint 重建的建议：构图可能执行使用方 I/O，不能放在恢复锁内；跨连接重建也无法读取尚未提交的撤销。反向差量与结果更新同事务保存，与行级撤销同事务恢复，不新增业务 reducer。大范围替换状态时，撤销数据仍可能与实际被替换内容等大，不宣称任意写入都固定大小。

用户已确认固定夹具的绝对门槛：同一隔离机、单 namespace、历史 100/1,000/10,000 条、负载 1 KiB/16 KiB，Run 边界不超过 8 KiB，建立边界 p95 不超过 100 ms，单次建立边界 WAL 不超过 64 KiB，维护进程峰值 RSS 不超过 256 MiB，10,000 条历史 prune 不超过 5 秒；同时检查这些新增维护开销不随旧历史负载线性增加。测量分别标明重复次数、版本、逻辑字节与物理文件；预算不外推整个 Agent 状态或永久历史绝对有界。
