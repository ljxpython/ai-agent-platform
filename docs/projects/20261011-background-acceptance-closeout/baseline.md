# 事实核查与合并基线

> 初次规划核查日期：2026-10-11。第 1–5 节保留实施前事实；实际合并与当前产物见第 6 节，不把历史核查状态当成当前进度。

## 1. 来源与证据归属

| 来源 | 核查事实 | 可复用范围 |
|---|---|---|
| `f5a8/ai-agent-platform` | HEAD `bd476ae6`；核查开始时工作树干净；Runtime pyproject/服务锁为 post44，部署 Dockerfile 仍固定 post20；无后台任务/接受回执主体 | 主分支较新功能的合并参考与本轮规划存放点；不是后续服务验收基线 |
| `99f7/ai-agent-platform` | HEAD `ef9f08ba`，存在暂存和未暂存改动；后台任务、A/B 与 U01–U03 均已落地；锁/部署断言已为 post45 | 既有实现、原专项任务/Phase、前端成果；需确保工作区增量完整进入主分支 |
| GraphHarbor | `docs/projects/20261010-run-acceptance-receipts/{README,tasks,verification}.md` 为 done、13/13；正式 post45 双包和发布后联合验收完成 | B01 解除、协议和正式包来源证据；不能替代平台合并后的 Final |

核查的GraphHarbor源码库为用户提供的 `~/PyCharmMiscProject/graphharbor`；证据在上述项目的 `implementation/`。后续验收由K01记录实际CLI/正式安装来源，复用隔离runner时传明确的可执行路径；不新增仓库定位配置或复制私有环境。

正式产物入口：[graphharbor](https://pypi.org/project/graphharbor/0.13.0.post45/) / [graphharbor-runtime](https://pypi.org/project/graphharbor-runtime/0.13.0.post45/)。引擎证据含正式 wheel/sdist 各 5 组进程验收、使用方 Platform 132 passed/116 subtests、Runtime 115 passed、真实 PG repository 21 passed 与迁移 1 passed；各报告的 skipped/deselected 不算通过。

正式源 lost-ACK 联合场景分别为 notify/Stop/撤权：每场景源+完成共 2 Run、1 ledger，完成模型调用 1/0/0。这里引用历史事实，本轮没有重跑。前端 F01–F11、A/B 的阶段与人工验收也保留来源状态，F12 未完成。

## 2. 合并不能只看来源 HEAD

核查时 `99f7` 的下列相关内容仍有工作区改动；实施 K01 必须比较最终主分支的实际文件，不能仅判断 `ef9f08ba` 是否进入历史：

- Platform 新增 `migrations/versions/20261010_0007_run_acceptance.py`，以及 `modules/runtime_gateway/application/service.py` 的接受接线。
- Runtime `background_tasks/{capabilities,service,repository}.py`、`pyproject.toml`、`uv.lock`、`deploy/Dockerfile` 等正式依赖与 A/B 增量。
- Web `useBackgroundTasks.ts`、对应 spec、`ChatSession.vue`、`transcript.ts` 与测试；部分文件同时有暂存与未暂存增量。
- 原后台专项的 tasks/verification/engine-handoff 与 A/B 交接、实施和证据。

此列表不是完整补丁清单。K01 用来源实际 diff 和合并结果建立受影响文件清单，只保留源码/文档/脱敏证据，不带入 `.venv`、`node_modules`、`.local-stack` 或私有 `.env`。本轮不代用户执行提交、暂存或合并。

## 3. 已发现的迁移分支

| 数据库迁移体系 | 当前分支 | 处理提案 |
|---|---|---|
| Platform API | `20261009_0007`（终态通知，来自较新平台）与 `20261010_0007`（接受回执，来自 99f7）均以 `20261007_0006` 为父 | 保留两份 revision，新增无数据操作的 merge revision；不要修改已经使用的 revision/down_revision |
| Runtime 应用 | `0003_token_budget` 与 `0003_background_tasks` 均以 `0002_run_control` 为父 | 保留两分支，新增 merge revision；同时保留 Usage、Stop 与后台表 |
| GraphHarbor 引擎 | post45 正式 head 为 `013_run_acceptance_receipts` | 从正式包执行迁移；平台不得另建或修改引擎表 |

合并节点只汇合迁移图，不删字段、重建表或改旧记录。需从空库、各分支已迁库和汇合库验证唯一 head、重复升级及回执保留；K02 负责。若主分支合并阶段已正确解决，不再新增第二份 merge revision。

建议文件名（实施前核对无冲突）：

- `apps/platform-api/migrations/versions/20261011_0008_merge_completion_acceptance.py`，父节点元组为 `("20261009_0007", "20261010_0007")`。
- `apps/runtime-service/src/runtime_service/db/migrations/versions/0004_merge_background_token_budget.py`，父节点元组为 `("0003_background_tasks", "0003_token_budget")`。

主分支实际 head 和新增 revision ID 在 K01/K02 冻结，不在本轮创建迁移代码或更改数据库。

## 4. 需要逐块保留的接线

| 合并热点 | 必须同时存在 |
|---|---|
| Platform `RuntimeGatewayService.launch_runtime_run()` | 接受回执的最终 bytes/key/digest/binding 与终态通知 origin_ref/callback_context；Plan/模型/Token 配置与原幂等逻辑 |
| `RunRequestRecord` / `StoredRunRequest` / `RunRequestsRepository` | 接受回执六个 nullable 字段与已有 origin_ref、执行快照及稳定 run_id；两套能力互不覆盖 |
| Runtime 两组合根、middleware、webapp | 后台三工具/A+B/完成 guard 与 Token/loop/工具输出预算、文档读取和终态 projector；根/子图权限边界保持 |
| Web transcript/ChatSession/Workspace | 后台系统胶囊与任务探针、较新大工具输出/循环/用量/Plan 展示和全局终态通知；两类通知不混为同一功能 |
| 依赖与镜像 | 正式 post45 双包、当前已批准业务依赖和 Workspace reader；从统一 frozen 锁构建，不整体覆盖较新 lock 丢失功能依赖 |

以上是合并检查，不要求在本专项重做所有较新功能。若只丢失个别接线，以最小补丁恢复，并回归该调用链。

## 5. 规范差异与边界

来源当前代码还有三项需要接续修补；主分支若已修正则直接复验，不重复修改：

1. `apps/platform-web/src/components/workspace/BackgroundTaskItem.vue` 将 `delivery.state=accepted` 渲染为“已送达通知”；它只证明续接接受，需改为“续接已接受”，并为delivery=unknown单独呈现“续接待确认”。
2. Runtime `background_tasks/repository.py::list_tasks()` 的最新Run查询只要求 `delivery_run_id IS NOT NULL`，Web `useBackgroundTasks.ts::checkDiscoveredRuns()` 也不检查delivery.state；Stop后suppressed迟到run_id仍可能成为自动接续候选。提案：列表最新候选只含accepted且未抑制任务，Task详情仍保留原run_id供固定清理；Web同样过滤并清除Stop后待转交的候选。
3. Web `useChatSession.ts::acceptDiscoveredRun()` / `flushPendingDiscoveredRuns()` 仅检查原Run active和stream.isLoading，未显式检查当前真实interrupt；异步Run列表返回前也未重核固定Thread和当前busy/HITL。需沿已有SDK状态加入待审批避让和scope/异步竞态校验，避免覆盖用户新Run或待审Run。

这里只确认代码缺少上述条件，没有执行浏览器复现，行为风险在V16–V18验证。候选过滤是现有Stop/HITL契约的补齐，不删除持久接受回执或原Run证据。

`99f7` 的 `docs/standards/delegation-jwt.md` / 健康表仍写 34 项 operation 和 B01 阻塞，但双端代码已增加 `run-acceptance-read`；该差异应在 K08 按引擎 U02 已批准语义补文档及集合断言，不另行扩大授权。若最终合并代码与批准的固定目标语义不符，先标记差异等待人工裁决，不自行放宽权限。

官方 MCP 已查询：LangSmith enqueue 文档和 Python `langgraph_sdk.RunsClient.create` 说明原生后台 Run 创建；LangGraph interrupt 文档要求重执行的副作用幂等。此次查询没有提供 GraphHarbor 固定 key 接受回执、永久墓碑和持久否定的官方保证，因此仍明确它是引擎扩展，沿现有 adapter 消费。

- [官方 enqueue 文档](https://docs.langchain.com/langsmith/enqueue-concurrent)
- [SDK create 参考](https://reference.langchain.com/python/langgraph-sdk/_async/runs/RunsClient/create)
- [interrupt 幂等要求](https://docs.langchain.com/oss/python/langgraph/interrupts#side-effects-called-before-interrupt-must-be-idempotent)

本轮未核实合并后的主分支、现役镜像、已安装依赖或新环境资源；后续 K01 实测填入，不能沿用来源状态冒充结果。

## 6. 已冻结的实施基线

用户确认合并后，来源 `d412d54c` 经 `74ac8c83` 已进入集成分支 `feat/langgraph-v3-delta-evaluation` 的 `2b94585b`。从该提交创建 detached Worktree：`~/.codex/worktrees/b01-closeout/ai-agent-platform`。本轮增量未提交，f5a8/99f7 不能替代当前验收代码。

独立环境 `wt_43727db9404e`；两应用各独立安装，Runtime 双包正式 post45/SDK0.4.3、API SDK0.4.2。当前实际 head：Platform `20261011_0009`，Runtime `0004_background_token_budget`，引擎 `013_run_acceptance_receipts`。`0008` 是首次汇合后的阶段 head，随后因历史 SQLite 类型与元数据差异新增 `0009`；旧节点和持久事实保留。

最终 Runtime 冷镜像 `sha256:3b7a07136c46d7d151218571f45a40016dbd1044938ae976aff2aadc7a992601`，API/Worker 同摘要。业务接线、迁移与执行域修补分别见 [01](implementation/01-baseline-and-migrations.md)、[02](implementation/02-completion-context-and-merge-repairs.md)、[03](implementation/03-schema-and-local-stack-isolation.md)；Phase/Final 结果见 [verification.md](verification.md)。前端差异为零，K09/K10 由同事完成。
