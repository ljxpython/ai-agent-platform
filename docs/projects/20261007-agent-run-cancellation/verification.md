# Agent 运行取消与中断 - 验证记录

> **状态：blocked，2026-10-07。** 非前端源码、唯一post43包版隔离证据和真实Docker完成，B01解除；B02正式发布指令/正式源锁接入及前端联合Final待完成。现役部署另行指定。只记Phase，不把候选记成正式发布。

## 验证环境

- 使用平台 worktree HEAD `bf47991b` 加本次未提交改动，GraphHarbor HEAD `f9bb32e` 加配套改动；外部工作树还有其他专项，未覆盖或回退。
- 所有写测试使用 GraphHarbor `scripts/run_isolated_tests.py` 的临时原生 PostgreSQL/Redis，自动创建/销毁，合成身份、模型和密钥；无现役数据、无付费模型调用。
- 正式 Runtime 环境：Python 3.13，GraphHarbor 双包 post41/head010、SDK 0.4.3；锁未修改。配套源码测试覆盖 head011。
- 首轮同名post42候选只作历史Phase证据；本轮唯一post43四产物、Python3.13.9、LangGraph1.2.11、SDK0.4.3，wheel/sdist哈希见[packages.json](evidence/packages.json)。临时复制Runtime锁接入仅改双包，新环境冷安装140包；仓库正式锁仍post41，未写临时来源。
- 用户已启动Docker；daemon28.0.4，测试用现有p5镜像。真实后端/PPTX3项和两种包版取消通过，结束后仍仅原有3个运行容器；未修改系统配置或现役服务。

## Phase 验证记录

### Task 0.1：源码与参考核对

已核对三服务、SDK、open-swe Slack/Web/API cancel、Middleware 与 GraphHarbor Worker。官方 LangChain cancel/RunControl/LocalShellBackend 依据见 open-swe-comparison.md。结论：现有 Stop/单 Run cancel 已有，interrupt 不保证工具自然完成。

### Task 0.2：方案与交接

人工批准后按实际 DTO/路由更新 handoff，空 body/key、六 phase、nullable 计数、20 checkpoint/30 progress/20 artifact、502存储错误与明确恢复规则完整。前端未修改。

### Task 0.3：验证计划

覆盖固定目标、重启/未知、权限/撤权、FIFO/inbox、HITL、资源、外部unknown、安全报告、迁移/回退与容量。未执行项均有外部条件，不用 skip 当 pass。

### Task 0.4：人工批准

用户明确“方案评审通过，可以开始实施了。把除了前端的开发项都开发完成，除非有 Block 项”；已记录 review.md R01–R10。

### Task 1.1：依赖基线

正式双包 post41、SDK0.4.3、迁移010已核实；候选双包构建 wheel/sdist、冷安装79包、import `langhost.cancellation` 与 RunCancellationRow/head011、CLI version 均通过。新正式版本缺失，锁/现役未升级。

### Task 1.2：固定目标、竞争、容量

- GraphHarbor 新固定回执 + Worker/public runtime 集：48 passed。
- 新目标容量/竞争集：26 passed，含151目标分页/重试/新Run、20次claim/submit竞争、lease fence与1/10/100/500目标。
- 实测非SLO：1目标82.42ms/19条SQL；10目标917.23ms/118条；100目标8072.56ms/1108条；500目标33243.04ms/5524条。SQL含取回执分页，不含seed；当前逐Run取消有线性成本。
- 真实 Runtime 500目标后台恢复通过：超过单HTTP10秒预算仍恢复同stop_id，完整500 targets确认，报告truncated不影响停止事实。

### Task 1.3：退出与身份

Worker cancel/production/public runtime 48项通过；主图/子图重新构建 server_info 的 assistant_id/graph_id 传播验证通过。lease消失但无持久退出证明时confirmation_unavailable，不误报成功。真实模型等待/长工具/两类并行双子Agent退出、无lease与持久终态确认通过。

### Task 1.4：候选迁移与回退（正式门禁 blocked）

[scripts/verify_stop_migrations.py](../../../scripts/verify_stop_migrations.py) 在冷安装候选包环境7项通过，见 [migrations.json](evidence/migrations.json)：

1. 候选包真实HTTP取消，退出回执存在。
2. Runtime downgrade0001保留Stop/inbox证据。
3. 再upgrade0002幂等，原事实一致。
4. pg_dump custom与独立库pg_restore，Run/Stop/引擎回执/inbox快照相同。
5. 引擎downgrade010删除新增取消表，Run仍interrupted且无lease；先保留备份，不在现役直接downgrade。
6. 旧正式post41包读取旧取消意图，并完成旧单Run cancel。
7. 再upgrade011成功。

正式唯一新版本未发布/未授权部署；候选测试不等于发布门禁通过。源码回退优先保留加性表，已提交取消不反向恢复pending；需要恢复报告时用备份和新引擎回执，不能删除Run。

本轮post43在原SDK0.4.3/原Runtime依赖锁的独立环境重跑7条恢复全部通过。双包源码/精确依赖/版本门禁及uv.lock已更新post43；全包73文件Ruff check/format、mypy39源文件、uv lock/check_versions通过。PyPI正式post42与候选wheel源码对照仅5处新增/变更，未混入其他未发布源码；正式上传未执行。

完整引擎初跑296 passed/8 skipped/4 failed：两项迁移head旧断言、两项Cron隔离库配置不符。同步head011及取消表存在性，Cron使用独立库/专用Redis前缀重跑，主回归297 passed/8 skipped，Cron3 passed。Python3.12初跑123 passed/4 skipped/1 failed、Python3.13初跑149 passed/4 skipped/1 failed：跨实例订阅的合法recheck通知与测试首消息断言竞态，修测试为有界等待interrupt并finally关闭资源，不改运行时。修正后3.12契约集124 passed/4 skipped、3.13冷安装wheel契约与固定取消集150 passed/4 skipped。Python3.11独立wheel导入和CLI/head011通过；sdist独立安装通过。完整四产物及接入步骤见[release-handoff.md](release-handoff.md)。

### Task 2.1：持久受理与恢复

Runtime Stop最终定向25 passed（`tests/services/test_run_control.py`）。验证scoped key、安全facts、租约续租/过期/fencing、confirmation_unavailable重试和存储503安全错误。真实accepted后Runtime重启恢复同动作与500目标等待超时恢复通过。

### Task 2.2：inbox

60次真实PG竞争：enqueue/claim/checkpoint各20次通过；新Run不受旧屏障影响。checkpoint先消费时准备inbox集合允许为空，consumed不改写。Stop真实1running/2pending/2inbox，计数3/2/2、旧pending不执行、未消费user_stopped通过。
既有Stop+inbox集33 passed/1 skipped；加媒体集47 passed/2 skipped，唯一新测试过严断言修正后最新Stop25项通过。skip为opt-in真实Server与Docker，不记通过。

### Task 2.3：资源（真实 Docker done，B01解除）

- Docker mock正常取消、重复取消、rm失败/超时/spawn失败，cleanup confirmed/unconfirmed与取消传播通过。
- local同步线程重复取消等待、命令失败unconfirmed通过；真实local sleep30约等有限执行结束后确认cleanup，不强杀Python线程。
- 模型HTTP等待、Showcase/DearFlow各双并行子Agent真实退出通过。
- 媒体取消/供应商接受但丢响应保留unknown且不重复购买通过（既有media PG/合成provider检查）。
- 部署HTTP被取消，PG unknown/attempts=1，相同key重试不再提交通过；供应商为本机MockTransport，没有真实外部发布。
- 本轮真实Docker后端/PPTX3项通过；包版HTTP中Showcase/DearFlow均等PG active资源、命令开始文件及daemon running容器后取消；回执stopped/cleanup_confirmed，无lease，inspect确认容器移除，8秒后无延迟文件写入。容器ID与镜像ID保存在acceptance.json的docker字段，未删除工作区或影响其他容器。

本轮夹具初跑9场景通过后Docker探针失败，原因是用数据库Tenant UUID推导workspace，而平台执行身份使用DEFAULT_TENANT_ID。修正夹具回传真实运行tenant，沿已有hashed_thread_root推导，之后post43包版16场景全部通过。不是放宽生产权限或用PG登记代替实际运行；先前失败记录保留，本段为修正后的证据。

### Task 2.4：报告

25项定向中包含checkpoint固定Run、不继承旧ToolMessage、有界计划/工具/成果、JWT/凭据/宿主路径脱敏、in-flight工具external_effect_unknown、schema与503。真实四图/noactive/HITL/500目标报告通过。纯确定性报告，无模型、无新图、无消息注入。最新in-flight补充是独立有界单测，不将较早HTTP证据冒充补充后全图重测。

### Task 3.1：公开HTTP与投影

Stop API8 passed；相关6文件回归66 passed/376 subtests passed/1 failed。公开字段剔除、ownership、empty body/key、query、UUID、no-store、request_id、安全错误已验证。最初改变公开503被既有契约测试拒绝，已恢复Runtime503→公开502并保留stop_storage_unavailable，定向11 passed/116 subtests passed。

剩余失败位于未改动的 `tests/test_runtime_gateway_sdk_adapters.py::RuntimeGatewaySdkAdaptersTest.test_thread_fatal_error_is_safe_and_success_or_tool_content_is_unchanged`，旧断言期待runtime.execution_failed，HEAD实际已有runtime_execution_failed+安全message。前轮已HEAD复现，未顺手改测试或fatal语义；不能宣称相关全仓全绿。

### Task 3.2：委托与授权

跨进程operation集合按名称核验（含3个新scope），JWT过期/claim/scope/context/native资源与custom隔离通过。新增HMAC有效签名、过期/未来timestamp、Thread/credential正文篡改、签名篡改/缺失拒绝通过。普通用户/服务账号固定取消ID与Thread回执隔离通过；普通read之外的run-cancellation-read不能读Run/state或新取消。
真实Thread只读分享拒绝新Stop、移除成员拒绝公开GET；已有引擎accepted意图继续后台收敛通过。当前项目没有viewer角色；只读由Thread ACL模拟，未修改角色制度。

### Task 3.3：审计与关联

audit resolver回归通过；Runtime持久audit_pending、稳定phase UUID防重复，真实撤权后confirmed入库且pending清空通过。requested/read HTTP与后台阶段区分，GET不写confirmed；只存安全ID/phase/count/request/trace，不存正文或token。

### Task 4.1：前端动作与多端状态机（Phase done，2026-10-08）

- **契约与DTO校验：**
  - `src/modules/chat/stop/types.ts` 基于 Zod 实现 `StopRequest`、`StopReport`、`StopRequestList` 严格白名单校验；成果路径严格正则校验 `^/workspace/outputs/[0-9a-f]{64}\.[a-z0-9]{1,8}$`。
  - `src/services/threads/session.service.ts` 接入 `stopThread`（POST 空正文 `{}`，携带 `x-project-id` 与 `Idempotency-Key`）、`getStopRequest`、`listStopRequests`（请求 Query 严格为 `cursor`，返回为 `next_cursor`）。
  - 单元测试 `session.service.spec.ts`：10 passed。
- **状态机与生命周期：**
  - `src/modules/chat/composables/useThreadStopControl.ts` 实现 45s 硬超时降级、单飞保护防重复提交、Scope/Generation 隔离（`threadId`/`projectId`/`sessionEpoch` 变化立即重置并废弃旧响应）、`localStorage` 幂等未决恢复（格式 `pw:thread:stop:${userId}:${sessionEpoch}:${projectId}:${threadId}`）、`confirmation_unavailable` 降频轮询。
  - `src/modules/chat/composables/useChatSession.ts` 废除单一布尔值 `cancelling`，将停止动作状态与 Run 生命周期彻底解耦；解耦 `canSend` 与 `status` 计算，支持 `onStopConfirmed` 触发 `promptQueue.refresh()`。
  - 单元测试：`useThreadStopControl.spec.ts` 4 passed，`useChatSession.spec.ts` 28 passed。

### Task 4.2：前端报告、队列与端到端闭环（Phase done，2026-10-08）

- **UI 组件实现与挂载：**
  - 新建 `src/modules/chat/components/RunStopReportBanner.vue`：挂载于 Composer `top-tray` 插槽，展示简要状态、目标计数、查看详情与重新核实入口。
  - 新建 `src/modules/chat/components/RunStopReportDetails.vue`：基于 `BaseDrawer` 展示 Checkpoints、工具证据、授权成果引用与不确定性告警（报告不走 AIMessage 管线，不触发推荐问题或自动审批）。
  - `ChatSession.vue` 挂载组件并接入队列刷新协同 `onStopConfirmed: () => { void promptQueue?.refresh(); }`。
- **前端门禁验证：**
  - `vue-tsc --noEmit`：0 errors。
  - `eslint "src/**/*.{ts,tsx,vue}"`：0 errors。
  - `vite build`：打包构建成功（14.21s，0 errors）。
  - Vitest 全量套件：115 passed，553 tests passed。
- **Playwright + Chromium 真实模型自动化全链路闭环验证：**
  - 测试脚本：`apps/platform-web/e2e/chat-session-stop.spec.ts`（耗时 10.57s，1 passed，0 failed）。
  - 真实环境闭环：本地启动 Runtime API (8123)、Runtime Worker、Platform API (2142)、Platform Web (3000)，连接真实模型 `百炼 · qwen-plus`。
  - 过程闭环证据：
    1. 发起真实模型长文生成，在生成进行中点击“停止生成”；
    2. 捕获 POST `/cancel` 网络请求：Body 为严格空对象 `{}`，Header 携带 `x-project-id` 与 `Idempotency-Key`，响应 202 Accepted；
    3. 单飞保护生效：按钮立即切为 `停止中...` 且 disabled，禁止重复提交；
    4. 轮询 `GET /stop-requests/{id}`，直到返回 `phase: stopped`；
    5. Banner 呈现 `✓ 已停止（取消 1 个任务）`，并附带 `查看报告` 入口；
    6. 点击 `查看报告`，右侧 `BaseDrawer` 展开展示 `会话停止状态与证据报告`，详细展示执行状态、Checkpoints、工具证据及不确定性警示；
    7. 验证响应式适配并保存 1440px / 768px / 390px 截图；
    8. 验证通过键盘 Escape 优雅关闭抽屉，输入框恢复可编辑状态，草稿正常保留，不阻塞新消息输入与发送。
  - 截图归档目录：`docs/projects/20261007-agent-run-cancellation/evidence/screenshots/`
    - `e2e-stop-phase1-stopping.png`：停止中状态与单飞保护
    - `e2e-stop-phase2-stopped.png`：已停止横幅与任务计数
    - `e2e-stop-phase3-drawer.png`：1440px 桌面端停止报告抽屉详情展开
    - `e2e-stop-viewport-768.png`：768px 平板视口响应式
    - `e2e-stop-viewport-390.png`：390px 移动端视口响应式
    - `e2e-stop-phase5-resumed.png`：会话恢复与下一轮可输入状态

### Task 5.1：非前端真实 HTTP（整体联合 blocked）

`scripts/verify_thread_stop.py` 共15个可执行场景通过，见 [acceptance.json](evidence/acceptance.json) 的脱敏回执；运行过程记录request_id/stop_id/固定Run/checkpoint/count/phase。四图使用实际组合根与合成模型，不是mock Runtime router。
首轮源码/local的15场景原件为`/tmp/agent-stop-acceptance-5543.json`；当前仓库acceptance.json为下段16场景。

首轮15场景为源码/local证据。当前acceptance.json已更新为唯一post43、SDK0.4.3、实际四图16场景完整包版证据，新增DearFlow execute并将两种execute验证为真实Docker开始/取消/清理/延迟副作用；PYTHONPATH仅含平台业务源码，没有GraphHarbor源码路径。Runtime Stop/inbox同候选环境47 passed/1 skipped；API复跑66 passed/376 subtests passed/1条相同既有失败。

覆盖：pending重启/原key重试、500目标后台恢复、Reference慢工具/模型、Workflow、DearFlow、Showcase/DearFlow双子Agent、local execute、FIFO/inbox、旧Stop不伤新Run、未知提交/列表分页/无active/输入拒绝、HITL保留、当前interrupt ID显式resume、接受后撤权与审计。
HITL夹具先携新配置被400拒绝、再用非ID映射被409拒绝，均按现有审批规则修正，实际显式resume成功且interrupt清空。没有放宽安全规则。

### Task 5.2：静态门禁与文档

最新收口检查：平台35个Python路径Ruff check/format check/compileall通过；GraphHarbor本专项6文件Ruff check/format check/compileall通过（新增回执路由一处换行已修正）；两仓git diff --check通过。源码与候选/正式来源区别、服务活标准、CONTEXT/FEATURES/CHANGELOG、详细实现记录和前端报告已同步，正式锁和前端代码未修改。

定向检查33份项目/活标准/经验文档：287个相对链接、9份JSON或JSON代码块、21个闭合代码块和13个完成任务的Phase对应均通过；本次新增行无宿主绝对路径/retired-host，README/plan/tasks/verification/CONTEXT状态一致。查到3条FEATURES旧断链，均用HEAD确认已存在，未顺手修改。此前全仓docs检查的旧绝对路径/retired-host问题也保留，不宣称全仓文档门禁全绿。安全/契约规范保留现有draft，不提前毕业。

用户已确认两条Runtime经验并写入lessons，索引2→4。B01已解除，剩余B02正式发布指令/正式源接入与同事前端；候选及非前端证据未当作整体done。本轮格式/迁移断言/订阅通知测试问题已修正并补验，不重复修无关API文案基线。

最后一个twine检查进程已完成，post43四产物均PASSED；SHA256复核与packages.json一致，PyPI双包最新仍post42且post43无文件。GraphHarbor的CONTEXT/FEATURES/CHANGELOG、Thread取消任务/验证与REST契约已同步唯一post43及真实Docker证据，首轮同名post42仅保留为历史Phase。正式上传仍未执行，仓库Runtime锁保持正式post41。

续跑收口：check_versions、compatibility baseline和uv lock --check通过；30份两仓文档、291个相对链接、21个闭合代码块和9份JSON无新增错误，3条FEATURES基线断链仍与HEAD一致。两仓diff --check通过。发布指令待回复，不执行上传、git提交或现役部署。

本轮原件：`/tmp/agent-stop-post43-acceptance-5543.json`、`/tmp/agent-stop-post43-migrations-5543.json`、`/tmp/agent-stop-docker-5543.xml`、`/tmp/agent-stop-post43-runtime-5543.xml`、`/tmp/agent-stop-post43-api-5543.xml`、`/tmp/thread-stop-post43-engine-final-5543.xml`、`/tmp/thread-stop-post43-cron-final-5543.xml`、`/tmp/thread-stop-post43-python312-final-5543.xml`、`/tmp/thread-stop-post43-python313-final-5543.xml`。脱敏回执/产物记录已入evidence，临时日志与原件不承诺长期保留。

## 可复跑命令

从平台仓库根执行，变量填写隔离环境解释器与外部GraphHarbor源码路径；不要复制真实密钥、不要使用现役DSN。

```bash
export PYTHONPATH="$PWD/apps/runtime-service/src:$PWD/apps/platform-api/src:$GRAPH_HARBOR_ROOT/libs/langhost/src:$GRAPH_HARBOR_ROOT/libs/langgraph-runtime-pg/src"
LANGFUSE_ENABLED=false OTEL_SDK_DISABLED=true \
PLATFORM_API_TEST_PYTHON="$PLATFORM_API_PYTHON" STOP_PROBE_OUTPUT="/tmp/agent-stop-acceptance.json" \
"$GRAPH_HARBOR_PYTHON" "$GRAPH_HARBOR_ROOT/scripts/run_isolated_tests.py" \
"$RUNTIME_PYTHON" scripts/verify_thread_stop.py

# 候选冷安装环境中必须已安装双wheel；runtime业务代码经PYTHONPATH提供
PYTHONPATH="$PWD/apps/runtime-service/src" STOP_ROLLBACK_PYTHON="$OLD_RUNTIME_PYTHON" \
STOP_MIGRATION_OUTPUT="/tmp/agent-stop-migrations.json" \
"$GRAPH_HARBOR_PYTHON" "$GRAPH_HARBOR_ROOT/scripts/run_isolated_tests.py" \
"$CANDIDATE_PYTHON" scripts/verify_stop_migrations.py
```

Runtime定向：隔离运行器内设 `RUNTIME_MESSAGE_TEST_DSN="$POSTGRES_URI"`，执行 `pytest apps/runtime-service/tests/services/test_run_control.py -q`。不得使用test文件既有默认现役地址；本轮误带占位DSN时认证失败，无数据操作，已改回隔离运行器。

API相关：在apps/platform-api下以src为PYTHONPATH执行 `pytest tests/test_run_control.py tests/test_runtime_gateway_http_matrix.py tests/test_runtime_gateway_runtime_contract.py tests/test_runtime_gateway_sdk_adapters.py tests/test_audit_http_resolution.py tests/test_runtime_delegation_contract.py -q`；指定 `RUNTIME_CONTRACT_PYTHON` 以避免跨进程契约静默skip。

GraphHarbor：隔离运行器内执行 `pytest libs/langgraph-runtime-pg/tests/test_thread_cancellation.py -q -s`；worker/public/queue定向按该库现有脚本和tests执行。命令包含路径须替换为所在仓库，shell实际执行使用用户rtk约定，文档命令不带rtk。

## 剩余条件与四态

| 范围 | 状态 | 条件 |
|---|---|---|
| 非前端源码/公开契约/固定目标/后台恢复 | done（隔离证据） | 已完成，不等于正式部署 |
| 候选冷安装/备份/迁移/旧包回退 | done（候选证据） | 不是正式包发布 |
| Docker资源边界 | done，B01解除 | 两种实际命令开始/容器移除/持久清理回执/无延迟写入，另有后端/PPTX3项 |
| 正式配套/锁接入 | blocked B02 | 唯一post43发布准备完成，等待明确PyPI上传指令，再正式源安装/锁接入复验；现役部署另行指定 |
| 前端与浏览器 | done（真实全链路证据） | 契约校验、状态机解耦、Banner与Drawer完成；Vitest (553 passed)、vue-tsc (0 error)、ESLint (0 error)、Vite build (通过)、Playwright+Chromium 真实模型全链路端到端自动化测试通过，1440/768/390截图已归档 |
| 可选LLM润色 | deferred | 用户批准首期不做 |
| 500目标性能 | 实测已记录 | 逐Run线性成本，未批准SLO，不宣称秒级 |

## Final 验证记录

**未开始。** Task2.3已done/B01解除；Task1.4与4/5仍需B02正式源复验及同事前端。README/plan/tasks/verification/CONTEXT统一blocked，候选Phase不是全项目Final，draft标准此时不毕业。
