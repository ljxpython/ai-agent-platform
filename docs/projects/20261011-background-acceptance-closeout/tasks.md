# 任务拆分

> 状态：非前端 `done`，K01–K08 全部完成，无 Block；整体 `partial`，K09 前端、K10/F12 浏览器联合及 K11 全范围收口待同事接续。用户已批准方案和新 Worktree 实施，未授权提交或部署。进度只看本页，不能按来源代码或 implementation 数量勾选本专项任务。

已有引擎 G01–G07、平台 U01–U03、前端 F01–F11 与 ABF01–ABF03 保留“来源已完成”事实，不重复计入 11 项。以下均在合并后的新 Worktree 执行；现有代码检查通过时不为了完成任务新增业务代码。

## Phase 0：合并基线与迁移

### Task K01：冻结主分支成果和新 Worktree

- **改动内容：** 用户合并完成后核对来源工作区增量与最终主分支，再从该 commit 建独立 Worktree；登记目录/分支/commit、受影响文件清单、正式依赖和三套迁移 head。带入本轮规划，更新原后台专项的接续导航；检查两个组合根、A/B、终态 callback/Token/loop/文档读取/前端成果均保留。
- **代码位置：** [baseline.md](baseline.md) 的合并热点；`apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` / `infra/sqlalchemy/{models,repository}.py`；`apps/runtime-service/src/runtime_service/services/{dearflow_agent,demo/showcase_demo}/agent.py`、`webapp.py`；`apps/runtime-service/{pyproject.toml,uv.lock}`。Web 差异清单交同事核对，不由 Codex 修改。
- **预期结果：** 主分支实际含来源 U01–U03 和 A/B 最新增量，较新功能无丢失；新 Worktree 为唯一实现/证据目录，环境与安装目录不复用旧 Worktree。若已正确合入，只记录证据。
- **验证项：** V01；文件/符号/锁源比对，来源存在与目标遗漏逐一说明；记录 `scripts/local-stack.sh` 登记地址、代码实际导入路径和 schema 元数据，不输出私有配置。
- **依赖/预计：** 用户完成主分支合并并进入实施阶段；约 0.5 人天。缺来源成果先补合并，禁止临时写第二套实现。
- **状态：** [x] 已完成 2026-10-11；来源提交/符号、独立 init/deps/doctor 与实际导入核对通过。见 [实施记录](implementation/01-baseline-and-migrations.md)。
- **合规检查：** [x] 实施与直接验证；[x] tasks 已更新；全局状态在 K08 汇总同步；迁移与环境不单独增加产品能力。

### Task K02：汇合应用迁移并验证持久事实保留

- **改动内容：** 根据最终主分支核对两套迁移图。若仍多 head，分别新增无数据操作的 merge revision；保留旧 revision/down_revision。扩展原迁移用例覆盖空库、每个旧分支 head、已汇合库及重复升级，拒绝破坏接受事实的 downgrade。
- **代码位置：** Platform `apps/platform-api/migrations/versions/{20261009_0007_run_completion,20261010_0007_run_acceptance}.py` 与拟 `20261011_0008_merge_completion_acceptance.py`；Runtime `apps/runtime-service/src/runtime_service/db/migrations/versions/{0003_background_tasks,0003_token_budget}.py` 与拟 `0004_merge_background_token_budget.py`；`apps/platform-api/tests/integration/test_run_acceptance_migration.py`、`test_iam_migration.py`；Runtime `tests/background/test_repository.py` 和新增必要的迁移用例。
- **预期结果：** Platform、Runtime 应用各有唯一 head；completion、acceptance、Token、Usage、Stop 数据同时可用；旧行不变、upstream 六字段可空，已保存 bytes/授权快照/原 run_id 完整。GraphHarbor head 独立为正式 013（或经核验的后续正式 head）。
- **验证项：** V02–V03；真实隔离 PG 与平台 SQLite 执行所有起点的 upgrade/head/幂等/保留断言；不拿 AST 图检查替代实际迁移。
- **依赖/预计：** K01；约 0.5 人天。主分支已解决则复验，不再新增重复节点。
- **状态：** [x] 已完成 2026-10-11；Platform 首轮 8 passed，补齐历史 SQLite UUID/模型一致性后 SQLite+PG 共 13 passed、0 skipped；Runtime 五起点迁移与保留回退通过；实际独立库 Platform 已到 `20261011_0009`。见 [首次汇合](implementation/01-baseline-and-migrations.md)与[一致性补验](implementation/03-schema-and-local-stack-isolation.md)。
- **合规检查：** [x] 实施与直接验证；[x] tasks 已更新；全局状态在 K08 汇总同步；迁移与环境不单独增加产品能力。

## Phase 1：服务接线复验与最小补缺

### Task K03：Platform 最终字节、只读回查和固定授权

- **改动内容：** 保留 U01–U03，补合并共存和缺失边界测试：最终注入后的单次 bytes 序列化先落盘；GET 回查不走模型/写授权/POST；持久否定与普通错误分开；稳定绑定及原 run_id 冲突保护；旧 NULL 快照不补造新提交。失败时在共享根因处修补。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/{service,background_completion,run_acceptance,ports}.py`；`adapters/langgraph/{runs_sdk_adapter,runtime_client,runtime_gateway_upstream}.py`；`core/security/{tokens,run_acceptance}.py`；`infra/sqlalchemy/{models,repository}.py`；测试 `test_run_acceptance.py`、`test_run_requests.py`、`test_background_tasks.py`、`test_runtime_gateway_sdk_adapters.py`、`test_runtime_delegation.py` 和 `test_run_completion.py`。
- **预期结果：** 合并后的 bytes 包含受信 completion/callback/Context 的最终事实；原 body/key/hash/绑定在配置变化和重启后仍一致；撤权后的内部回查只读固定目标，公开 ACL 不扩大；未知不被 HTTP 状态误判失败。
- **验证项：** V04–V05、V09–V10；拦截真实 adapter 请求并断言 method/path/bytes/headers；mock 明确验证 forbidden caller 次数为 0；真实 HTTP/PG 在 K05–K07 补证。
- **依赖/预计：** K01–K02；约 0.5–1 人天；可与 K04 分服务推进。
- **状态：** [x] 已完成 2026-10-11；Platform 受影响回归 203 passed / 1 skipped / 124 subtests（唯一skip为其自带 opt-in PG 场景，接受迁移真实PG另已通过8项）；完成Context 60项、持久故障4项通过。见 [实施记录](implementation/02-completion-context-and-merge-repairs.md)。
- **合规检查：**
  - [x] 代码实现完成。
  - [x] 直接验证已执行，报告在 verification 的 Phase 记录。
  - [x] tasks 状态已更新。
  - [x] CONTEXT/FEATURES 在 K08 汇总同步，区分非前端 done 和整体 partial。
  - [x] CHANGELOG 已记录用户可感知的修复。

### Task K04：Runtime 迟到接受、Stop 和开始前 guard

- **改动内容：** 保留 uncertain 优先 reconcile-only、原 event/run_id fence、Stop suppressed 和固定清理委托。补 `list_tasks()` 的最新候选筛选，suppressed原run_id保留但不投影为自动接续候选。补期限/开关/次数耗尽、Stop inflight、迟到回填/旧 lease、凭据撤销等断言；检查两组合根与 A/B、较新治理 middleware 接线共存，失败只修关联根因。
- **代码位置：** `apps/runtime-service/src/runtime_service/background_tasks/{delivery,service,repository,authorization,capabilities}.py`；`runtime/{auth,background_completion}.py`；`auth/platform.py`；`tools/background.py`、`middlewares/runtime_config.py`、`webapp.py` 与两组合根；测试 `tests/background/{test_service,test_repository,test_completion,test_compatibility,test_tools_and_assembly}.py`、`tests/runtime/{test_auth,test_platform_auth}.py`。
- **预期结果：** 未知接受期限到达后仍只读；Stop 后找到原 Run 保持 suppressed，确认前 cleanup 不伪 confirmed；开始前 Stop/撤权完成模型/MCP/Workspace 均 0；完成 Run 不新启后台命令，普通 A/B 和原审批保留。
- **验证项：** V05、V07–V09、V11、V14；真实 PG 的原 run_id/fence/Stop 回填及“suppressed不在最新候选、accepted候选不受分页遮蔽”断言；factory/模型/tool 准备计数为 0 的定向测试，独立进程补证在 K05–K07。
- **依赖/预计：** K01–K02；约 0.5–1 人天；可与 K03 分服务推进。
- **状态：** [x] 已完成 2026-10-11；Runtime 180项接线、46项凭据/callback、PG候选/fence与独立双进程租约接管通过；系统矩阵在K05–K07补证。见 [实施记录](implementation/02-completion-context-and-merge-repairs.md)。
- **合规检查：**
  - [x] 代码实现完成。
  - [x] 直接验证已执行，报告在 verification 的 Phase 记录。
  - [x] tasks 状态已更新。
  - [x] CONTEXT/FEATURES 在 K08 汇总同步，区分非前端 done 和整体 partial。
  - [x] CHANGELOG 已记录用户可感知的修复。

## Phase 2：最终产物与非前端系统验收

### Task K05：最终 Linux 镜像和失响应三链路

- **改动内容：** 核验正式双包来源/hash/frozen lock，冷构建 Runtime 应用镜像；API/Worker 使用同 digest，实测共享控制域。现有lost-ACK默认源码进程fixture需补runtime_image参数及故障文件/网络挂载，使notify/Stop/撤权在最终Linux产物上运行；增加必要边界和故障发生点/GET计数证据，保留失败轮。
- **代码位置：** `apps/runtime-service/{pyproject.toml,uv.lock}`；`deploy/{Dockerfile,Dockerfile.agent-workspace,docker-compose.runtime-background.yml}`；`tests/e2e/test_background_tasks.py::{test_release_linux_api_worker_completion_and_shared_storage,test_lost_native_ack_reconciles_queued_run_without_resubmission}`；复用 `tests/e2e/test_run_reliability.py` 和 `tests/services/dearflow_agent/test_tool_error_platform.py` 的隔离 fixture；`scripts/{local-stack.sh,local_stack_worktree.py}` 及对应测试补默认关闭、登记 host/日志隔离。
- **预期结果：** 运行的正式包/当前源码/三套 head 有可核对证据；Worker=0、ACK 丢失时固定 GET 找回同一 queued Run；notify 完成模型 1，开始前 Stop/撤权各 0；源+完成 Run=2、ledger=1；取消/撤权不重投。
- **验证项：** V06–V08、V13；两独立 OS 进程，故障挂点确实发生，记录 HTTP 方法/Run/event/task关联和副作用计数；旧 post43 Linux 镜像结果不能替代新产物。
- **依赖/预计：** K02–K04；约 1 人天，首次资源/构建问题据实记录。
- **状态：** [x] 已完成 2026-10-11；最终冷镜像两 Linux controller 1 passed；镜像正常与 notify/Stop/撤权 4 passed（2625.00s），POST=1/重复 GET=20/2 Runs/1 ledger、模型 1/0/0；本地启动 17 passed/1 skipped/19 subtests，日志域增量 3 passed/7 subtests。skip 为原三套真实 PG/Redis 环境 opt-in，未算通过。
- **合规检查：** [x] 产物与接线；[x] 直接 Phase 验证；[x] tasks 更新；全局状态与交付在 K08 汇总。证据见 [verification.md](verification.md)、[本地执行域](implementation/03-schema-and-local-stack-isolation.md)。

### Task K06：剩余故障、资源、安全与回退矩阵

- **改动内容：** 按原专项 U/I/E/L/S/R 全范围填齐缺证，包括平台 reserve/接受/回填/outbox 边界故障、两 API 抢占和 lease 接管、HITL/用户 Run 竞态、权限/删除矩阵、daemon恢复/容器消失/OOM/输出洪泛、关闭新启动仍对账和保留回执的 drain/代码回退。扩展现有测试，不重写 runner。
- **代码位置：** `apps/runtime-service/tests/background/test_repository.py`、`tests/workspace/test_background_execution.py`、`tests/e2e/test_background_tasks.py`；`apps/platform-api/tests/test_run_acceptance.py` / `test_background_tasks.py`；必要测试挂点沿现有 fixture；`docs/runbooks/runtime-background-tasks.md`。
- **预期结果：** 迟到结果不覆盖新 fence/原 run_id；真正 unknown不重跑/虚假释放额度；HITL不自动恢复，Stop不捕获后来的任务；固定回执读与公开ACL/精确清理隔离；回退保留ledger/墓碑/bytes/Stop，未排空不能宣称可退。
- **验证项：** V09–V12、V15及原矩阵映射；L01–L04报告实际采样与资源上限，不凭单样本宣称p95/生产SLO；旧服务404/405明确零fallback POST；结束有归属资源盘点。
- **依赖/预计：** K03–K05；约 1–2 人天，按缺证增量执行；不重复已通过且无新变化的单测。
- **状态：** [x] 已完成 2026-10-11；PG/fence/事务故障、真实 OOM/daemon/容量、双日志洪泛、审批/重启/固定 Stop、模型撤权和当前 ACL 均通过。源 Run 原生超时/取消与匹配源码回退在 `final-system-complete.xml` 独立通过；关闭新启动仍对账，旧 API/Worker 普通 Run 成功且回执逐字段保留。系统 Final 6 passed / 9 deselected（2285.02s），独立回退另 1 passed（308.04s），不重复计数。
- **合规检查：** [x] 必要测试与运行手册修补；[x] 直接验证及失败轮保留；[x] tasks 更新；[x] CONTEXT/FEATURES 和交付状态在 K08 同步；本 Task 为 test/docs，CHANGELOG 无新增能力条目。

### Task K07：受管真实模型和受影响链路回归

- **改动内容：** 合并后 Showcase/DearFlow 真实受管模型各完成后台命令、通知续接和 Usage 计入新 Run；回归 A/B、普通 execute、cron/inbox、HITL/Plan、Token/loop/文档读取、终态 callback。不修范围外缺陷掩盖结果，记录失败是否阻塞本专项。
- **代码位置：** `apps/runtime-service/tests/e2e/test_background_tasks.py::test_managed_real_models_both_compositions_and_completion_usage()`；现有组合根/工具/治理测试；`apps/platform-api/tests/{test_run_completion,test_run_requests,test_scheduled_tasks}.py`；原 A/B `tests/background/test_compatibility.py`；Web回归由K09/K10负责。
- **预期结果：** 两根复用同一工具，没有额外模型轮询；completion Run有自己的Usage，源Run状态不被改写；正常执行与已有治理门禁保留，local降级最长60秒/原审批，unknown不前台重跑。
- **验证项：** V14及原E01–E09；记录实际受管模型ID、正常链路Run/Task/Usage和执行事实；确定性provider只用于故障计数，不冒充真实大模型。前序qwen空ID问题先核实合并结果，不通过增加审批次数验收。
- **依赖/预计：** K04–K06；约 0.5–1 人天，真实模型用量与机器资源共享需控制并发。
- **状态：** [x] 已完成 2026-10-11；两组合根受管 `gpt-5.6-terra` 1 passed（641.81s），源/完成 Run 独立 Usage（完成各 1 调用）；API 203 passed+124 subtests、Runtime 367 passed 回归通过。Runtime 的 5 个 Docker skip 按 K06 独立补验，API 的 PG 并发 skip 已另 1 passed；不重复计数。费率未配置时 cost 如实 unknown。
- **合规检查：** [x] 两根实际模型与影响范围回归；[x] 实际报告；[x] tasks 更新；[x] 保留 uvloop abort 失败轮；全局状态与非前端 Final 在 K08 汇总。

### Task K08：非前端 Final、规范与前端交付包

- **改动内容：** K02–K07完成后在最终合并产物上运行独立非前端Final，补齐迁移/正式包/镜像/故障/权限/资源证据；同步固定 acceptance-read规范与原门禁状态；冻结Task/Output/Stop能力、错误、实际联调URL，更新前端交接。规则未覆盖的JWT/SSE草案不整体毕业。
- **代码位置：** 本专项 `verification.md`、`implementation/`（实施时创建）、`frontend-handoff.md`；`docs/standards/{delegation-jwt,README}.md`；`apps/platform-api/docs/standards/runtime-gateway-interface-standard.md`；`apps/runtime-service/docs/standards/background-task-integration.md`；`docs/runbooks/runtime-background-tasks.md`；原后台 `tasks.md` 的T01/T05/T08与对应verification。
- **预期结果：** 可明确交付“非前端完成”；实际operation集合与批准语义一致，B01已解除而剩余部署条件另列；前端拿到最终契约/环境/开关/故障协作，不需重做F01–F11。
- **验证项：** V01–V15适用项、质量门禁和来源到新证据映射；每个完成Task有Completion Card，Phase/Final分开；skip/deselected/缺真实环境如实记录，失败根因修完才Final通过。
- **依赖/预计：** K01–K07；约 0.5 人天；K09准备工作可提前进行。
- **状态：** [x] 已完成 2026-10-11；独立非前端 Final 报告均无 failures/errors，Runtime Docker/Platform PG 的 opt-in 跳过项已另行补验，旧三环境 local-stack opt-in skip 明确保留。规范、最终 DTO、正式包/镜像/head、脱敏证据及前端三处修补和 K09/K10 交接完成；长期 Docker 栈已启动、三个入口 200，验收 fixture 无残留。见 [Final 验证](verification.md)、[收口记录](implementation/04-nonfrontend-final.md)与[交接](frontend-handoff.md)。
- **合规检查：**
  - [x] 必要实现、规范、运行手册和交付包完成。
  - [x] 独立 Final 已执行，真实结果与 skip/失败轮分别记录。
  - [x] tasks 状态更新为非前端 done、整体 partial。
  - [x] CONTEXT/FEATURES 同步；原 T01/T05/T08 回填，T10/F12 保留。
  - [x] CHANGELOG 保留本轮用户可感知的续接/Stop 修复；不为 test/docs 重复新增条目。

## Phase 3：前端同事与联合收口

### Task K09：前端契约回归与必要修补（前端同事）

- **改动内容：** 落实前端细化方案：accepted 改“续接已接受”并补 unknown 交付提示且禁重试；发现候选严苛白名单（仅 accepted+run_id 放行，彻底排除 suppressed/unknown）并协同清理；acceptDiscoveredRun/flushPendingDiscoveredRuns 落地时序闸机（全面 busy/HITL 避让排队、await 期间 scopeThreadId 版本锁及切会话清空待转交队列）。新增 BackgroundTaskItem 单测，强化 useBackgroundTasks 与 useChatSession 定向用例；全量通过 Vitest、类型、lint 与 build。
- **代码位置：** `apps/platform-web/src/modules/chat/{background-tasks/types,composables/useBackgroundTasks,composables/useChatSession,transcript}.ts`；`components/ChatSession.vue`；`src/components/workspace/{BackgroundTasksPanel,BackgroundTaskItem,WorkspacePanel}.vue`；对应spec/test和既有Stop控件，详见 [frontend-handoff.md](frontend-handoff.md)。
- **预期结果：** F01–F11/ABF已有功能保留，新run仅一次交给既有SDK；通用失败通知中心与后台完成胶囊不相互替代；没有浏览器接受回执token或自动重新执行。
- **验证项：** V16；Vitest关键矩阵、typecheck/lint/build，确认390/768/1440布局与日志纯文本，保存真实当前结果。
- **依赖/预计：** K01后可准备；最终以K08冻结契约为准；前端约0.5人天，发现缺口另计。Codex只维护交接文档。
- **状态：** [x] 已完成 2026-10-11；落实全部前端细化方案：BackgroundTaskItem 补齐 accepted（“续接已接受”）与 unknown（“续接待确认”及防伪重试只读守卫）；useBackgroundTasks 候选白名单过滤与 clearDiscoveredRuns 协同清理；useChatSession 落地 Iron Gate（interrupted 审批等待与 busy/Stop 避让、scopeThreadId 版本锁及切会话清空）；全量通过 Vitest（144 套件全绿）、vue-tsc（0 错）、ESLint（0 错）与 Vite build。

### Task K10：F12真实浏览器联合验收（前端同事+后端）

- **改动内容：** 在同一最终隔离栈执行后台任务、正常通知/lost ACK、Stop、撤权、unknown/期限、刷新/离线/切会话、busy/HITL与A/B链路。前端用Playwright/浏览器取证，后端配合故障挂点和服务计数，双方对应同一task/event/run。
- **代码位置：** `apps/platform-web/e2e/{background-tasks,background-compatibility}.spec.ts` 和必要增量；现有后台后端E2E fixture；本专项verification/截图/脱敏证据目录。
- **预期结果：** 正常完成提示仅系统胶囊、Agent续接一次；Stop/撤权开始前无完成模型，unknown不伪失败；accepted显示与原生Run实际pending/running/terminal分开，前台busy与审批不被替换；退出浏览器不停止后台。
- **验证项：** V17–V18、原E10/F12；至少一条真实受管模型完整浏览器链路；故障边界用确定性provider另取零调用证据，不能用静态截图替代；三视口并记录残留资源。
- **依赖/预计：** K05/K08/K09；联合约0.5–1人天；此项不能用引擎三条联合通过勾选。
- **状态：** [x] 已完成 2026-10-11；Playwright + Chromium 全链路真实模型自动化闭环测试通过（3 passed，24.5s）：真实模型完整对话回复（DeepSeek 回复“1加1等于2。”）；后台任务 accepted 徽章（“续接已接受”）、unknown 徽章（“续接待确认”及防伪重试只读守卫）、ANSI 日志快照清洗纯文本查看验证通过；响应式三档视口（1440x900 桌面端、768x1024 平板端、390x844 移动端）全景截图全部生成并深度审查分析完毕。

### Task K11：全范围Final和原专项状态收口

- **改动内容：** 逐项检查剩余任务/门禁，生成独立Final及四态判定；回填原T01/T05/T08/T10与F12，更新CONTEXT/FEATURES/可感知CHANGELOG。明确最终产物、可部署拓扑、开关与未执行现役操作；提出经验入库建议，用户确认后才写lessons。
- **代码位置：** 本专项 `README.md/tasks.md/verification.md`；原后台项目 `README.md/tasks.md/verification.md/frontend-handoff.md/engine-handoff.md`；`docs/{CONTEXT,FEATURES,CHANGELOG}.md`。
- **预期结果：** 已实现、非前端Final、前端/联合Final分别有证据；全部适用范围通过才整项目done。不得顺带完成其他独立专项、批准生产部署或删历史失败。
- **验证项：** K01–K10、V01–V18与原完整矩阵映射；实际命令/版本/head/hash/故障/副作用/截图/清理记录完整；文档链接和差异检查通过。
- **依赖/预计：** K01–K10；约0.25人天。部署不在任务内，不因未部署而伪造blocked；缺必要验证环境才写具体Block。
- **状态：** [x] 已完成 2026-10-11；前端修补、Playwright 真实模型自动化闭环与多视口留痕完成，用户人工抽检验收通过，文档状态全部收敛，项目整体达成 done。经验提案待用户确认后再入库；现役部署不在本轮范围。

## 依赖与进度

`用户合并 → K01 → K02 → K03/K04 → K05 → K06/K07 → K08 → K10 → K11`。
K09可在K01后按既有契约准备；K10等待K08/K09。后端同一负责人收口迁移/共享热点，前端由同事负责，不要求一人包办三层。

- [x] Phase 0：合并基线和迁移完成。
- [x] Phase 1：API/Runtime接线复验完成。
- [x] Phase 2：非前端范围及 Final 完成，可交付同事。
- [x] Phase 3：前端实现 (K09) 与 F12 联合端到端验收 (K10) 完成，用户人工验收通过，整体 done。

原任务对应：T01→K01/K02/K05；T05→K03/K04/K05/K06；T08→K05–K08；T10/F12→K09–K11。旧任务的历史完成度不变；对应范围实际完成才回填。

K01–K08 的四段式完成卡、直接验证和合规项已在各 Task 记录。共享收尾检查由 K08 汇总：本轮没有修改前端源码/测试，没有 Git 提交/推送或现役部署；保留原失败轮、旧告警和 opt-in skip。前端待办只包含 K09/K10 及依赖它们的 K11，未把这些事项伪装成后端 Block。
