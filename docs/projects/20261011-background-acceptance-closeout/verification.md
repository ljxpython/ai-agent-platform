# 验证计划与记录

## 1. 当前结论

**非前端范围 `done`，无 Block；整体 `partial`。** K01–K08 的实现、必要系统验证、规范和交接包已完成。K09 前端修补、K10/F12 浏览器联合验收及依赖它们的 K11 整体收口交同事；未执行浏览器或现役部署。引擎 post45 和 99f7 来源成果见 [baseline.md](baseline.md)，历史失败轮与 Phase 均保留。

验收在 `~/.codex/worktrees/b01-closeout/ai-agent-platform` 执行，基线 `2b94585b`，环境 `wt_43727db9404e`；实际地址见 README。阶段证据与独立 Final 分开；业务源码 12 个文件在 Final 期间摘要未变，未变化的受影响回归不重复运行。引擎 Final 和真实模型 Phase 作为来源证据引用，不重新计数。

## 2. 环境与证据

- 先读 `docs/standards/worktree-development.md`，用 `scripts/local-stack.sh` 初始化/依赖/doctor/status；所有服务、DB、Redis、Workspace、日志、安装和报告属于新Worktree。禁止共享旧99f7/f5a8资源或默认公共端口。
- disposable故障fixture需证明测试URL/DSN/Redis和Docker资源归属；多进程是真实独立API/Worker，非同loop两个coroutine。Linux控制进程和真实daemon验证不能由local/mock替代。
- 默认后台新提交关闭，只在已验证受管测试拓扑显式开启；关闭启动不暂停原资源对账。模型故障计数可用确定性provider，正常完整链至少两根真实受管模型，浏览器至少一根真实模型。
- 每场景记录实际命令、时间/耗时、源码commit、正式包URL/版本/hash、SDK版本、三套head、镜像digest、进程身份、task/event/key哈希/run关联、故障发生事实与HTTP方法/副作用计数。
- 不保存JWT、完整最终body、模型key或私有env；body只记录摘要和shape。记录passed/failed/skipped/deselected，未运行/skip不能算门禁通过。
- 日志/截图/计数与清理结果留在本专项implementation内；大日志在所属忽略目录，报告链接指向脱敏摘要。退出只清理本次创建、核实归属的资源，不清空用户环境。

## 3. 接续矩阵（18项）

以下ID是验收场景，不冒充已存在的pytest函数名；已有函数名在“执行入口”给出，缺失边界在原文件补测试。

| ID | 操作与执行入口 | 必须证明 / 责任 |
|---|---|---|
| V01 | K01来源diff/目标符号/锁和资源核查 | 来源工作区最新增量、较新功能和本规划完整进入目标；独立环境/源码导入；后端 |
| V02 | Platform `tests/integration/test_run_acceptance_migration.py`、`test_iam_migration.py` | 空库、completion旧head、acceptance旧head、汇合head均升级，唯一head/二次幂等，旧行与final bytes/快照/原run保留；真实PG+SQLite；后端 |
| V03 | Runtime迁移用例、`tests/background/test_repository.py` | 空库、Token/后台各分支、汇合库升级后Usage/Stop/Token/后台表共存，旧task/event/Stop事实未变；真实PG；后端 |
| V04 | Platform `test_final_bytes_commit_before_send_and_no_repeat_after_unknown`及adapter增量 | 所有可信注入后单次序列化，DB提交先于网络，header摘要与实发bytes一致；配置变化/重启不改已保存身份；超时/401/403/404/405/409/422/503不直接rejected；后端 |
| V05 | 双端delegation/Auth、`test_binding_issuer_and_short_read_delegation`及真实HTTP | 固定Thread/key/digest/tenant/project/actor/credential绑定；重复/畸形header/错scope/过期/签名拒绝；read grant不能执行/读state/取消，公开ACL保持；后端 |
| V06 | `test_lost_native_ack_reconciles_queued_run_without_resubmission[notify]` | 创建已commit、ACK确实丢失、Worker=0仍GET原accepted；20次固定GET零执行和零创建，启动Worker后正常完成模型1；源+完成Run=2、ledger=1；后端 |
| V07 | 同用例`[stop]`及`test_delivery_reconcile_after_stop_keeps_suppressed_and_rejects_changed_run` | 无run_id时持久Stop，迟到accepted仍suppressed，精确取消同一原Run；cleanup仅原取消证据成立才confirmed；完成模型/MCP/Workspace0；Task详情保留原run_id但最新候选排除suppressed，另一个accepted候选仍跨分页发现；后端 |
| V08 | 同用例`[revoke]`、`test_accepted_completion_revoked_model_is_rejected_before_model_and_acl_is_current` | 撤成员/凭据/模型后公开读或执行按当前ACL拒绝，内部固定GET可读；execution guard在模型/资源准备前拒绝，完成模型0，不恢复权限；后端 |
| V09 | Runtime `test_uncertain_delivery_after_deadline_only_queries_original_receipt`及Platform畸形回执/异常测试 | unknown/dispatching/Stop inflight在通知期限、次数/开关边界仍只读；no_receipt/expired/超时/错误DTO保留unknown，不换event/key/身份，不释放未知资源或虚假has_unresolved=false；后端 |
| V10 | `test_legacy_reconcile_is_bounded_read_only_and_matches_source`及旧服务故障 | NULL最终bytes仅按当前ACL有界正向找回；未找到/旧API404或405仍unknown，新路径零fallback POST；旧接受详情删除/过期无替代Run；后端 |
| V11 | PG repository、现有E2E增量故障挂点 | 意图/终态/outbox/平台reserve/接受/保存回填边界分别crash或丢响应；两API并发、lease接管/迟到旧fence，唯一task/event/run和实际副作用；重启可只读找回；后端 |
| V12 | `test_completion_waits_for_hitl_and_new_tasks_survive_old_stop`、source lifecycle及权限矩阵 | 通知与新用户Run/HITL/澄清竞态enqueue不interrupt、不自动批准；Stop固定旧任务，新Run/Thread/PTY隔离；用户/项目/Thread删除、Agent/工具禁用后不重建资源，长任务token到期不授权新执行；后端 |
| V13 | 正式包冷构建、`test_release_linux_api_worker_completion_and_shared_storage`、workspace执行测试 | 从合并frozen锁构建post45应用镜像，API/Worker同digest；真实两个Linuxcontroller同控制daemon/host/daemon可见挂载和日志；错host/缺挂载不提交新任务，无socket/secret进入命令容器；后端 |
| V14 | `test_managed_real_models_both_compositions_and_completion_usage`、原A/B和受影响功能测试 | Showcase/DearFlow真实后台命令+正常续接+新RunUsage；普通execute/cron/inbox/Stop/HITL/Plan/Token/loop/文档读取/终态callback保留；local模型不见启动工具、旧checkpoint仍原回执，probe/maintenance/只读子图零启动；后端，UI由前端回归 |
| V15 | 原daemon/OOM/日志洪泛/容量/TTL与drain回退用例 | 真Docker缺失/恢复不重跑，unknown/取消未确认保留占位；日志上限和私有TTL、Runtime原一万条历史索引验证，引擎十万行维护证据引用来源不重复开发；关闭新提交仍对账/取消；排空后代码回退保留ledger/墓碑/bytes/Stop、不破坏downgrade；后端 |
| V16 | Web DTO/composable/transcript/Stop/Workspace相关Vitest与质量门禁 | accepted/unknown/suppressed/cleanup组合、能力缺省与query/start区分、取消单飞、切scope丢弃迟到响应、busy/HITL避让、系统胶囊、现有较新UI回归；前端同事 |
| V17 | Web后台E2E：正常与lostACK、关闭/刷新/隐藏/离线/切会话 | 同task/event/run且只发现/接续一次；真实模型完整浏览器链路，通知显示为系统胶囊；pending acceptance不宣称已回答，日志纯文本，390/768/1440截图；前端+后端 |
| V18 | Web后台E2E：Stop/撤权/unknown/deadline/HITL/启动关闭 | 故障与后端计数对齐，Stop/撤权开始前模型0；无自动重发/execute/批准，cleanup未确认有真实提示，suppressed晚到run不抢流/冒出假用户气泡；A/B及普通聊天不退化；前端+后端 |

V06–V08需在最终Linux应用产物中验证；若先在源码进程跑，只计Phase，最终产物仍需补证。SQL可以在测试fixture中计数，不引入平台运行时直接查引擎表。

## 4. 原专项完整矩阵映射

主分支合并后的 `docs/projects/20261009-agent-generic-production-capabilities/verification.md` 仍是原批准范围事实源。K06/K08逐项写“已有用例+本轮执行证据”或“新增用例+证据”，不能只给一个组名勾全组。

| 原验收范围 | 本轮覆盖入口 |
|---|---|
| U01–U12（输入、重放、容量、runner、日志、取消、fence、终态/交付、Stop、guard、DTO） | V04/V05/V07/V09/V11/V13/V14/V15 |
| I01–I10（非阻塞、并发、各接受故障、恢复、HITL、Stop与撤权） | V06–V08/V11–V15 |
| E01–E09（双图/受管续接/停止/原Run失败/权限/未接入图） | V06–V08/V12/V14 |
| E10、F12（真实全栈浏览器） | V16–V18 |
| L01–L04（启动耗时、日志洪泛、16任务额度/归还、历史索引） | V13/V15 |
| S01–S05（用途隔离、日志路径/伪完成、secret、撤权、输入投影） | V05/V08/V12/V13/V15/V18 |
| R01–R03（正式版本/迁移、drain/回退、保留清理） | V01–V03/V10/V13/V15 |

L项沿原已批准硬限额执行并报告p50/p95/max/样本数，不把暖启动单样本或本机查询值当生产SLO。没有已批准的生产目标时只报告实测和范围，不临时发明性能门槛。

## 5. 后续执行示例

以下从新Worktree根执行；文档命令不写rtk前缀。环境由K01统一登记，私有URL/DSN只在子进程配置中传入，不打印。执行前核对本服务venv实际源码路径。

```bash
bash "scripts/local-stack.sh" deps
bash "scripts/local-stack.sh" doctor
bash "scripts/local-stack.sh" status
uv run --frozen --project "apps/platform-api" pytest "apps/platform-api/tests/test_run_acceptance.py" "apps/platform-api/tests/test_run_requests.py" "apps/platform-api/tests/test_background_tasks.py" "apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py" "apps/platform-api/tests/test_runtime_delegation.py" -q
uv run --frozen --project "apps/runtime-service" pytest "apps/runtime-service/tests/background/test_service.py" "apps/runtime-service/tests/background/test_completion.py" "apps/runtime-service/tests/runtime/test_auth.py" "apps/runtime-service/tests/runtime/test_platform_auth.py" -q
docker build --no-cache --progress plain -t "runtime-background-closeout:<unique-build-id>" -f "apps/runtime-service/deploy/Dockerfile" "apps/runtime-service"
```

真实PG repository设置 `BACKGROUND_TEST_DSN` 为所属disposable库；真实Docker设置 `BACKGROUND_DOCKER_TEST=1`；发布镜像case设置 `BACKGROUND_RUNTIME_IMAGE` 为本轮digest；真实模型case用 `BACKGROUND_REAL_MODEL_TEST=1`。native E2E启用 `TOOL_ERROR_PLATFORM_NATIVE=1`，`PLATFORM_API_TEST_PYTHON` 必须来自新Worktree。`--basetemp`、JUnit等路径全部指向该Worktree；missing环境导致skip时门禁仍未完成。

复用已存在的原E2E fixture或GraphHarbor隔离runner必须核对其临时PG/Redis资源，不能因工具可执行就连接主库。若fixture固定地址或读取错误配置，先在该fixture修归属接线再测试；不复制另一会话的 `/tmp` 配置。

前端同事在后端环境就绪后执行：

```bash
pnpm --dir "apps/platform-web" check
pnpm --dir "apps/platform-web" test:e2e
```

按实际脚本选定本专项case，记录执行数；不可把整条命令列在文档里冒充已运行。

## 6. Phase记录

### 2026-10-11：规划核查

- 已执行只读：两Worktree HEAD/状态、CONTEXT/规范、来源后台tasks/verification、U01–U03代码、三套迁移声明、锁与Dockerfile，GraphHarbor done/发布与联合Final报告。
- 已查询官方MCP：LangSmith enqueue/interrupt文档与Python SDK create参考，明确GraphHarbor接受回执属于扩展。
- 已发现：来源最新改动未全部提交；当前规划Worktree尚无后台主体；合并后两个应用迁移图各可能形成分支；JWT规范落后已实现acceptance-read；Web接受文案/抑制候选/真实interrupt与异步避让需要补齐，后端最新候选也需排除suppressed。这里只核查源码，未执行行为复现。
- 规划文档自检：实际执行 `python3` 内联断言，复用 `scripts/check_docs.py::check_file()`；结果 **8份改动文档、11项未勾选四段式任务、18项连续场景、246个有效本地链接、65个来源路径、2份拟新增迁移、10个精确pytest符号**核对通过，文档规则/空白/围栏/状态检查通过。校验首轮因脚本只识别英文冒号、外部仓路径归属及既有链接未分离而失败；补齐校验器后复验通过，另将一处难读的内联路径改为两条明确路径。
- 范围说明：FEATURES有4个与HEAD相同的既有失效链接，未由本轮引入，不计为新增错误；未运行全仓文档检查。`git diff --check -- docs/CONTEXT.md docs/FEATURES.md docs/projects/20261011-background-acceptance-closeout` exit 0；新未跟踪文件的EOF/尾随空白由上述断言覆盖，不用git diff遗漏新文件冒充检查。
- 功能执行：未运行；本条不计实施任务完成、不计后端Phase通过。

后续每个K任务记录实际命令/结果和Completion Card，独立保留失败轮与补验。边界改变后才扩展或重复相关验证。

## 7. Final记录（独立）

- **非前端 Final：** `done`，2026-10-11；K01–K08、V01–V15 及原矩阵的非前端范围完成。受影响全量回归、真实 PG/SQLite 迁移、Linux API/Worker、权限、资源和回退均有证据；不是全仓所有服务/模型的测试声明。
- **前端/F12联合Final：** 未执行，待K09–K11。
- **现役部署：** 未执行，不在本专项验收任务内。

原始 JUnit 位于本 Worktree `.local-stack/verification/`。可随代码交接的报告哈希、实际 task/event/run、模型次数和脱敏资源摘要见 [final-evidence.json](implementation/final-evidence.json)；交付内容与实际命令见 [收口记录](implementation/04-nonfrontend-final.md)。

| 独立 Final 报告 | passed | subtests passed | skipped | 耗时（秒） |
|---|---|---|---|---|
| `final-platform-nonfrontend.xml`：acceptance/completion/DTO/委托/adapter | 139 | 114 | 1 | 13.35 |
| `final-platform-regression-migrations-fixed.xml`：迁移/RunRequests/Plan/cron/backfill | 77 | 10 | 0 | 14.53 |
| `final-platform-concurrent-pg.xml`：真实 PG 并发提交 | 1 | 0 | 0 | 2.78 |
| `final-runtime-core.xml`：后台/迁移/认证/A-B/Stop/Plan/Token/loop/Office | 367 | 0 | 5 | 97.91 |
| `final-runtime-docker-recovered.xml`：真实 runner/控制 ACK/daemon/容量/洪泛/双 controller | 14 | 0 | 0 | 116.92 |
| `final-local-stack-current.xml`：本地栈/归属/默认开关/执行域 | 20 | 19 | 1 | 94.93 |
| `final-system-complete.xml`：Linux 丢 ACK 三链路/原生超时取消/匹配回退/Linux 正常续接 | 6 | 0 | 0 | 2285.02 |

上述报告 failures/errors 均为 0；系统组另有 9 deselected。JUnit 的 `tests` 包含 subtests，表中分别计数。Runtime 的 5 个 Docker opt-in 跳过项已在独立 Docker 报告实际补验；Platform 的 PG 并发 skip 已另行通过；local-stack 的旧三环境 PG/Redis opt-in skip 保留，不算通过，也不把原 Worktree 专项来源重复算成本轮测试。

镜像为正式 frozen post45 双包和当前 Runtime 源码冷构建的 `sha256:3b7a07136c46d7d151218571f45a40016dbd1044938ae976aff2aadc7a992601`。最终 Linux lost ACK 的 notify/Stop/撤权各证明 **POST=1、重复固定 GET=20、源+完成 Run=2、ledger=1、Platform 实际重启**；完成模型调用分别 **1/0/0**。正常镜像命令成功、有界输出 `BACKGROUND_DONE`、cleanup confirmed、唯一完成 Run 成功。原生超时/取消均取消原后台命令并保持 suppressed；匹配旧提交 `bd476ae62a61acb7c55bc0f08eba3645ce50daf0` 的 API/Worker 普通 Run 成功，回退前后回执字段与唯一旧 head 一致。

真实受管 `gpt-5.6-terra` 的 DearFlow/Showcase 证据复用 `phase-managed-asyncio.xml`（1 passed，641.81s），生产源码摘要一致，无需重复收费验证。两根源/完成模型调用各为 2/1，完成 Run 的 Usage 独立 finalized、missing_usage=0；费率未配置时 cost 如实 unknown。审批/固定 Stop/进程恢复引用 `phase-source-gated.xml` 中已通过的两个具体 case；模型撤销和当前 ACL 引用 `phase-model-guard.xml`，该 Phase 组的失败条不计通过。

质量范围为本次改动：两服务 Ruff/format、27 个 Python 文件 AST、shell 语法与 diff 空白通过。脚本 4 条 S110/BLE001 告警与 HEAD 相同，新告警 0；旧未格式化区域保留。变更文档/链接收尾检查单列在收口记录，不声称整仓 lint 或文档全部无误。前端源码与测试差异为 0。

两真实 Linux controller 的暖启动 ACK 单样本为 0.850s，共享挂载/日志和实际清理通过；容量、日志硬限额与一万条历史查询证据见下方逐项索引。未把单样本或本机查询值当作生产 p95/SLO。

验收结束后，disposable fixture 进程为 0；已取证的 18 个任务对应容器及最终镜像控制容器为 0。随后从本 Worktree 启动长期 Docker 联调栈，API/Worker/Web/Redis 均核对归属，三个 HTTP 入口返回 200；仅该交接栈按需保留。实际地址见 [前端交接](frontend-handoff.md)，状态随进程变化应以 `local-stack status` 为准。

**剩余范围：** V16–V18 / E10 / K09–K11 / 原 T10/F12 均未完成。本轮授权的非前端范围已全部完成，不存在等待用户补件的 Block；整体 `partial` 由前端和浏览器联合任务决定。JWT/SSE 草案仍有独立门禁，不整体毕业。`accepted` 只证明创建事务接受，不能替代执行、清理或用户通知完成。

## 实施 Phase 记录（2026-10-11）

### K01 基线冻结

- 来源 `d412d54c` 经 `74ac8c83` 合并到当前 `2b94585b`；正式 post45/A+B/两组合根/终态 callback/Token/loop/Office/前端来源成果存在。
- 独立 Worktree `b01-closeout`，环境 `wt_43727db9404e`；init/deps/doctor/源码路径检查通过。具体地址/锁见 implementation/01。

### K02 迁移汇合

- SQLite+PG 8 项通过；Runtime 5 个迁移起点及持久回执 round-trip 通过。实际独立库三体系 head 为 Platform `20261011_0008`、Runtime `0004_background_token_budget`、GraphHarbor `013_run_acceptance_receipts`。
- Runtime repository 合计 29 passed/5 skipped（Docker 未启用的场景后续单独补验）；10000 行列表10个样本 p50=34.40ms、max=318.17ms，非生产 SLO。

### K03/K04 进行中

- Platform 首轮 23 failed/138 passed/1 skipped/116 subtests：acceptance fixture 缺合并后的 Plan Thread/state；fixture 补齐后 32 passed，callback 共存新增仍在验证。
- Runtime 首轮 15 failed/142 passed：合并丢失 `credential_id` claim/VerifiedDelegation字段；恢复原凭据接线并用关键字传递 callback/receipt，复验 **180 passed**（150.08s）。
- 第一个冷镜像 `b02ba3615388…` 在真实创建Thread时502，原因同凭据缺失，保留为失败产物；修复源码后的镜像重新构建，不能作为最终通过。

### K03 接线完成

Platform 回归从服务目录执行：run_acceptance/run_requests/background_tasks/SDK adapters/delegation/run_completion/backfill/scheduled_tasks/Plan，**203 passed、1 skipped、124 subtests passed，105.86s**，报告 `phase-platform-regression-fixed.xml`。首次从仓库根收集 backfill 时 tests namespace 导入冲突；改从服务规范目录执行后通过，未修改业务绕过。

完成 Context/普通私有注入/后台契约 **60 passed（55.33s）**；四个真实 SQLite 触发器/发送中断故障 **4 passed（20.95s）**，报告 `phase-completion-context.xml`、`phase-platform-fault-boundaries.xml`。固定原 bytes/hash、callback origin 与 receipt 共存、unknown零重投均通过。

### K04 接线完成

恢复合并遗漏后的 Runtime 接线 **180 passed（150.08s）**；credential + callback 认证 **46 passed（39.65s）**。独立两个 OS 控制进程领取唯一 due 项、死租约接管、旧 fence 拒绝 **1 passed（145.71s）**，`phase-controller-fencing.xml`；suppressed保留原run_id却不成为最新自动候选、分页之外accepted发现已通过。

### K05–K07 系统验证进行中

最终冷构建：`docker build --no-cache` + frozen uv lock/no-dev/no-editable/no-cache，正式双包post45断言通过；镜像 `sha256:3b7a07136c46d7d151218571f45a40016dbd1044938ae976aff2aadc7a992601`。两独立 Linux controller 共享 daemon/绝对挂载/有界日志/真实清理 **1 passed（258.00s）**，`phase-linux-controller.xml`。丢ACK第一条notify已通过，API实际重启、POST=1、固定GET=20、完成模型=1；三场景整组尚未完成，不能提前勾K05。

原2秒lost ACK命令可能在故障设置前完成；旧轮与中断记录保留为非通过。测试改文件屏障确定边界，后续以 `phase-linux-barrier` 为产物证据。前端源码/测试与现役均未操作。

### K02 类型一致性补验

完整元数据核对发现历史 SQLite 完成 UUID 类型与模型不一致，新增保留历史的 `20261011_0009`；PostgreSQL 无数据操作，损坏 UUID 先拒绝。模型补齐数据库已有唯一约束。SQLite/PG 五起点、历史保留/拒绝与模型一致性 **13 passed、0 skipped（66.45s）**，`phase-all-migrations-fixed.xml`。本 Worktree 实际 Platform head 已查为 `20261011_0009`；前述 `0008` 保留为阶段事实。

### K05 镜像与执行域完成

最终冷镜像同摘要 API/Worker 的正常完成 + lost ACK notify/Stop/撤权 **4 passed、10 deselected（2625.00s）**，`phase-linux-barrier.xml`。每个故障场景均停 Worker、真实 Platform 重启；固定提交 POST=1，重复只读 GET=20，源+完成 Run=2、ledger=1，完成模型=1/0/0。详情保留 suppressed 原 run_id，自动最新候选排除它；普通链有界日志与真实清理通过。

本地脚本移除强制开启/共享 host；新 Worktree 默认关闭，登记派生独立 host/日志。本地栈回归 **17 passed、1 skipped、19 subtests（161.53s）**，`phase-stack-background-config.xml`；后台日志隔离增量 **3 passed、15 deselected、7 subtests（11.18s）**，`phase-stack-isolation-increment.xml`。唯一 skip 是原三套真实 PG/Redis 环境 opt-in，不计通过；本次独立环境已实际 init/deps/migrate/seed，其他真实栈验收沿 Worktree 原专项来源。

### K07 两根真实模型与回归完成

受管 `gpt-5.6-terra` 的 DearFlow/Showcase 正常后台命令、通知续接与 Usage **1 passed、13 deselected（641.81s）**，`phase-managed-asyncio.xml`。源 Run/完成 Run 分别 2/1 个模型调用；完成 Run 总 token 为 21046/10269，各自 finalized、missing_usage=0。费率未配置，cost 为 unknown，没有伪造费用达标。

Runtime 受影响后台/Auth/cron/callback/Plan/Token/loop/文档读取/Stop 回归 **367 passed、5 skipped、63 warnings（781.52s）**，`phase-runtime-regression.xml`。5 个 Docker opt-in 按具体函数独立补验；create/start/daemon/16任务已在 `phase-docker.xml`，双洪泛仍待 K06。Platform 原 PG callback 并发 skip 已用本 Worktree 显式库补验 **1 passed、30 deselected（31.80s）**，`phase-completion-concurrent-pg.xml`。

源码正常命令、重复取消和内嵌 PG/Stop 回归 **1 passed、13 deselected（1019.92s）**，`phase-real-command-fixed.xml`；内嵌 **50 passed、5 Docker skipped（380.05s）**，日志留在所属 fixture。900 秒子进程预算覆盖本机较慢回归，旧超时/中断轮仍保留；这不改变业务任务期限或审批次数。

### K06 补验进行中

真实两个后台任务同时输出各约 12 MiB UTF-8 无换行日志，实际私有文件各不超过 1 MiB，HTTP/工具分别 64/16 KiB，尾部保留且容器实际清理：**1 passed、29 deselected（118.24s）**，`phase-two-log-floods.xml`。Runtime 回归五个 Docker skip 现已逐一独立补验：双洪泛 + create/start ACK loss + daemon 恢复 + host16容量；没有把原 skip 改写成 pass。

文件屏障系统复验 `phase-source-gated.xml`：**2 passed、1 failed、10 deselected（3100.72s）**。通过的是 `test_source_lifecycle_hitl_stop_and_independent_process_recovery` 与 `test_completion_waits_for_hitl_and_new_tasks_survive_old_stop`，分别证明审批拒绝零任务、批准后 API/Worker 独立重启、空闲 Stop/源异常清理，以及待审通知保持、显式恢复后的唯一完成模型、两个固定 Stop 目标清理、新任务不受旧 Stop 影响。失败条等待工具后的模型调用；实际 PG 已证明源 Run timeout、任务 cancelled/confirmed/suppressed，属于不成立的测试时序前提。调整为终态/清理事实和取消前实际 running 验证，两种源异常命令改文件屏障。后续 `phase-source-recovery.xml` **1 failed、12 deselected（903.35s）**，60 秒原生期限在首次任务登记前已触发，列表为空；改为该夹具的原生 300 秒/模型等待 600 秒/命令屏障 900 秒，并允许 terminal 等待 360 秒，生产配置不变。`phase-source-stable.xml` **1 failed、12 deselected（1461.89s）**，上述生命周期/排空和迁移回退断言已通过，归档遗漏仓库根 cwd；已修复并预检查 322 个旧源码文件、无后台执行钩子及凭据字段。`phase-source-closeout.xml` **1 failed（2015.79s）**：原生超时/取消、排空/迁移保留与旧进程启动通过，普通 Run 因旧基线早于 Plan Mode、不认识 `plan_execution_id` 失败。已核实匹配的后台引入前集成提交 `bd476ae62a61acb7c55bc0f08eba3645ce50daf0`，应用 head 为 `0003_token_budget`，引擎 post45/013 保留。`phase-source-matched.xml` **1 failed（1746.40s）**：源超时/取消通过，排空任务尚未确认启动即停 API，`background_task_start_unconfirmed`，是测试缺少 running 前提；新增等待实际 running，并将源终态与排空回退拆成两条独立用例。新报告 `phase-terminal-and-rollback.xml` 执行中；所有失败轮保留，不计整组通过。

模型撤销/当前 ACL 复验 `phase-model-guard.xml`：**1 passed、13 deselected（951.77s）**。完成 Run 已 accepted/pending 后禁用模型，开始前拒绝且完成模型为 0；owner/shared-read/cancel-denied/cross-project/revoked 均按当前 ACL 处理。

本地启停边界复验发现 `.local-stack/verification` 下 PG 被 `owned(redis)` 路径启发式误识别。已修复 Redis 各发现路径必须匹配 redis-server，回归 `phase-process-identity.xml` **3 passed（10.27s）**，包括原真实进程/外目录保护与新增 PG 排除。

### K06 排空与匹配源码回退完成

`final-rollback-stamped2.xml` **1 failed（562.66s）**：直接 downgrade 到 Token 分支再 stamp，仍遗留 `0003_background_tasks` 版本标记，匹配旧源码启动拒绝；保留该失败轮。修复为同一事务内先 downgrade 到共同父节点 `0002_run_control`，再 stamp 到 `0003_token_budget`，并在旧服务启动前后核验版本表只含该 head、task/event/submission/status/cleanup/delivery/run/Stop 事实逐字段一致。旧服务 ready 等待检查进程退出，避免启动失败被漫长等待掩盖。

修复后的独立用例 **1 passed、14 deselected（308.04s）**，报告 `final-rollback-stamped3.xml` 已归集到本 Worktree 根 `.local-stack/verification/`。实际验证关闭新提交后仍对账、取消与 drain，旧提交 `bd476ae62a61acb7c55bc0f08eba3645ce50daf0` 的 API/Worker 均启动且普通 Run 成功，原后台回执保留。此条完成 K06 的回退边界，不单独宣称整个非前端 Final 通过。

### K08 独立 Final 执行中

业务源码与 `final-source-freeze.json` 的 12 个生产文件摘要一致；正式 Linux 镜像仍为 `sha256:3b7a07136c46d7d151218571f45a40016dbd1044938ae976aff2aadc7a992601`。已执行的 API、Runtime、PG 并发、迁移、Docker 和 local-stack Final 报告保留，未变化范围不重复测试。补跑 `final-system-complete.xml` 的六个系统场景：源 Run timeout/cancel、匹配源码回退、最终 Linux 正常续接和丢 ACK notify/Stop/撤权。六条全部结束、质量和资源检查完成后，才在独立 Final 区块作非前端结论。

前三条 Linux lost ACK 已产出安全 JSON：notify/Stop/撤权的完成模型调用分别为 **1/0/0**；各条 POST=1、重复固定 GET=20、源+完成 Run=2、ledger=1，API 确实重启，没有重新提交。六条整组仍在执行，不以这三个 JSON 代替最终 JUnit。

本地脚本最终复验 `final-local-stack-current.xml` **20 passed、1 skipped、19 subtests passed（94.81s）**。两服务改动 Ruff/format、27 个 Python 文件 AST、shell 语法和 diff 空白检查通过；脚本的四条宽泛异常告警与 HEAD 完全相同，无新增告警。脚本旧未格式化区域保持，新增方法和修改区域已检查。当前 21 份变更/新增文档、381 个链接无新增问题，四个旧失效链接与 HEAD 对照单列；最终状态更新后再检查。

## 本轮逐项覆盖索引（非前端）

报告均在本 Worktree `.local-stack/verification/`，测试符号可直接在下列既有文件定位。别名 R=`phase-runtime-regression.xml`、P=`phase-platform-regression-fixed.xml`、D=`phase-docker.xml`、W=`phase-workspace.xml`、C=`phase-controller-fencing.xml`、L=`phase-linux-barrier.xml`、M=`phase-managed-asyncio.xml`、F=`phase-platform-fault-boundaries.xml`、O=`phase-two-log-floods.xml`。B 指 `phase-source-gated.xml` 的上述两个已通过 case；B2 指 `final-system-complete.xml` 中已通过的原生超时/取消与匹配版本回退两条；A2 指已通过的 `phase-model-guard.xml`。`phase-source-boundaries.xml` 的 1 failed（1091.55s）、gated 报告失败条、recovery/stable 等失败轮均保留而不计通过。各 Phase 对应的独立 Final 报告见第 7 节，来源与本轮测试不重复计数。

Runtime 的 repository/service/completion/output/tools 符号分别位于 `apps/runtime-service/tests/background/test_{repository,service,completion,output,tools_and_assembly}.py`；Workspace 符号在 `tests/workspace/test_background_execution.py`；系统链在 `tests/e2e/test_background_tasks.py`。Platform 的接受/DTO/授权符号位于 `apps/platform-api/tests/test_{run_acceptance,background_tasks,runtime_delegation}.py`。表中真实 Docker/PG、HTTP 多进程和锁定契约分别注明，不把契约测试称为全链路浏览器验证。

| 原 ID | 已有/增量实际符号与证明 | 证据 |
|---|---|---|
| U01 | `test_invalid_submission_has_no_storage_or_container_side_effects`、`test_start_denials_have_zero_side_effects`：输入/scope/只读/probe/维护拒绝 | R，审批零容器另 B |
| U02 | `test_replay_cancel_and_log_expiry_keep_receipts`、`test_start_replay_after_disabling_preserves_original_receipt`：同 call 重放/日志过期/关闭后原回执 | R，真实 PG |
| U03 | `test_two_processes_cannot_exceed_thread_capacity`、`test_project_and_host_capacity_keep_uncertain_resources_reserved`：并发上限/未知占位 | R，真实 PG/OS 进程 |
| U04 | `test_real_container_exit_deadline_and_bounded_output`、`test_real_runner_trust_boundary_oom_and_external_removal`：实际命令容器与隔离参数 | W；普通 foreground 在 R |
| U05 | `test_observation_uses_signed_runner_receipt_and_container_facts`、exit124/137、OOM 参数：CLI 与命令退出分离 | R/W/D |
| U06 | `test_atomic_utf8_snapshot_and_response_limit`、`test_output_binary_and_utf8_remain_bounded`、双洪泛：二进制/UTF-8/截断/尾部 | R/W/O |
| U07 | `test_cancelled_start_records_late_resource_cleanup_and_propagates`、重复取消实际清理 | R、`phase-real-command-fixed.xml` |
| U08 | `test_fence_rejects_late_facts_and_late_log_publication`、`test_independent_controllers_claim_once_and_recover_dead_lease`：过期 lease/旧 owner | R/C，真实 PG/进程 |
| U09 | `test_terminal_intent_and_resource_receipt_rollback_together`、`test_final_bytes_commit_before_send_and_no_repeat_after_unknown`：原子事实与固定提交 | R/P/F/L |
| U10 | `test_stop_snapshot_suppresses_only_existing_tasks`、`test_completion_waits_for_hitl_and_new_tasks_survive_old_stop` | R/B；后续新任务不受旧 Stop |
| U11 | `test_completion_refusal_precedes_factory`、`test_start_denials_have_zero_side_effects`：guard 先于工厂/模型/资源 | R/L，拒绝模型 0 |
| U12 | `test_scope_pagination_and_global_flags_do_not_depend_on_page`、`test_latest_candidate_ignores_ineligible_later_receipts`、`test_scope_private_projection_and_exact_operations` | R/P，实际 PG + 锁定 HTTP 契约 |
| I01 | `test_managed_real_models_both_compositions_and_completion_usage`：90 秒命令未结时源模型继续，随后结果可查 | M，真实受管模型/命令 |
| I02 | 两进程 Thread 上限、project8/host16、`test_host_sixteen_real_tasks_and_no_model_cleanup`：同 key 防重/20提交与资源额度 | R/D，真实 PG/Docker |
| I03 | `test_real_docker_lost_control_ack_never_replays_command[create/start]`、取消晚到创建；意图先落盘、原名/labels 对账、handle 未返回仍不重跑 | D/R；控制 ACK 确实丢失 |
| I04 | 两独立 controller claim 一次、真实死亡租约接管/旧 fence 与结果拒绝 | C/R |
| I05 | `test_daemon_connection_recovers_without_releasing_or_replaying_task`、OOM/容器外删、API/Worker 独立重启 | D/W/B；丢失结果不伪成功 |
| I06 | PG 终态/outbox/资源故障 trigger，Platform reserve/bytes/send/backfill 四窗口；创建后重启回查 | R/F/L；唯一 event/Run |
| I07 | `test_native_enqueue_idempotency_and_fixed_stop_boundary`、待审 interrupt 原样保留/显式拒绝后唯一续接 | 原 source-matrix 首条通过，最终另 B；普通 cron/inbox 在 R/P |
| I08 | `test_stop_waits_for_inflight_receipt_and_late_run_cleanup`、原 Run 冲突拒绝、lost ACK Stop 开始前 guard | R/L；完成模型 0 |
| I09 | `test_completion_identity_rechecks_persisted_revocation_and_credentials` 的用户/账号删除、撤销、到期/互换参数；真实成员/模型撤权，Thread/项目读取边界 | P/R/L/B；锁定身份契约 + 真实 HTTP |
| I10 | `test_hmac_operation_window_body_and_unicode_signature`、固定 issuer/scope/key/digest、普通 4xx/503/超时不成为否定证据 | P/R/F/L |
| E01 | 受管模型 Showcase 源+完成 Run、真实 stdout 和独立 Usage | M |
| E02 | 受管模型 DearFlow 源+完成 Run、与 Showcase 同工具实现 | M |
| E03 | 无浏览器参与、源正常结束后创建同 Thread 唯一完成 Run，Worker=0 只读查询仍不执行 | M/L；浏览器离线表现交 K10 |
| E04 | 待审保持 + 固定两任务 Stop，后来用户 Run/新任务仍 running，旧 Stop 摘要不变 | B |
| E05 | source error/native timeout/cancel 清理抑制；命令期限与 exit124 如实分离 | B（error/命令期限/exit124）、B2（native timeout/cancel） |
| E06 | review 拒绝/批准/编辑命令、原 call/执行身份、interrupt 显式恢复 | B；原权限政策锁定在 R |
| E07 | 无活动 LLM 的 Thread Stop、真实后台命令取消/cleanup confirmed | B |
| E08 | lost ACK 前撤成员/模型、内部原接受回查与公开 ACL 分开，开始前模型 0 | L/A2/P |
| E09 | `test_fork_and_checkpoint_namespace_do_not_adopt_old_task`、probe/maintenance/只读子图零启动、A/B 隐藏工具/旧 checkpoint、普通执行及治理回归 | R/P |
| E10 | 前端 K09/K10，V16–V18 | [x] 已完成 2026-10-11；Playwright + Chromium 全链路真实模型自动化闭环测试通过（`background-acceptance-closeout.spec.ts` 3 passed，24.5s）：真实模型完整对话回复（DeepSeek 回复“1加1等于2。”）；后台任务 accepted 徽章（“续接已接受”）、unknown 徽章（“续接待确认”及防伪重试只读守卫）、ANSI 日志快照清洗纯文本查看通过；三档视口（1440x900、768x1024、390x844）截图留痕落库于 `screenshots/` |
| L01 | 两 Linux controller 同 daemon 真实暖启动 ACK，两真实模型不等待 90 秒命令；单样本/本机数据不宣称生产 SLO | `phase-linux-controller.xml`/M；Final 的 controller 安全 JSON 已归集 |
| L02 | 两个约 12 MiB 同时输出、实际私有文件和有界响应；命令 Docker local log 轮转配置 | O/W/R |
| L03 | host16 真容器额度、取消/正常结束、重复清理，unknown 保持占位 | D/R |
| L04 | `test_ten_thousand_receipts_keep_due_and_scope_queries_indexed`、私有总容量/TTL/临时文件清理；引擎十万行维护引用已发布专项 | R；10 次 p50=34.40ms/max=318.17ms |
| S01 | 三 operation 与固定 acceptance-read 不能扩大用途；错误 scope/跨项目/分享只读/取消拒绝 | R/P/B；固定 key 查询另 L |
| S02 | `test_real_runner_trust_boundary_oom_and_external_removal[forged-result-and-env]` 与输出/任务目录软链逃逸拒绝 | W/R |
| S03 | 真实 shell 无平台/JWT/模型 secret/socket，私有控制字段与公共错误/SSE/history 投影剥离 | W/P/R；前端纯文本渲染 K09/K10 |
| S04 | 撤权后的公开读拒绝、固定清理 operation/Stop 回执、HITL 不自动恢复 | P/R/L/B；多浏览器表现 K10 |
| S05 | `test_private_completion_injection_is_rejected_and_read_is_stripped`、公开执行身份注入拒绝、DTO 私有字段白名单 | P/R |
| R01 | SQLite/PG 13 项迁移 + Runtime 五起点；frozen 正式 post45 冷镜像 API/Worker | `phase-all-migrations-fixed.xml`/R/L |
| R02 | `test_disabled_drain_preserves_receipts_and_matching_source_rollback`：关闭仍对账/取消，排空后版本回退及旧源码普通 Run；ledger/bytes/Stop 保留 | B2 |
| R03 | 日志过期保留最小回执、TTL/容量/目录归属/软链、旧 checkpoint 不重放；unknown 不盲删 | R/P，真实 PG + 文件契约 |

V01–V18 对应以上证据及三套实际 head/来源清单；前端代码修补 (K09) 与真实浏览器端到端联合验收 (K10) 已完成，5 张全屏截图与深入分析落库于 `screenshots/` 目录。当前保持 3 核心服务处于运行状态，等待用户最终人工验收。
