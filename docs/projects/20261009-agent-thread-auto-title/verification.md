# F07 验证计划与记录

> 2026-10-09 R1-R5已批准并实施；下面分别保留规划基线、实施Phase与尚未执行的前端联合Final。候选证据不能替代正式发布。

## 验收原则

- 不出现第二个标题事实源/生成器，不更改 Agent 消息、Run 终态、审批或 Stop 行为。
- 现有手动改名/AI 提炼仍可用；新增授权拒绝语义经评审与前端同步。
- 自动功能的成功、失败、撤权、并发、落库未知和回退均有证据；CAS 只接受真实 PostgreSQL/HTTP 验证。
- 前端交接完成不替代同事实现和浏览器联验；外部 wheel/源码验证不替代正式双包接入。

## 单元与契约测试位置

| 位置 | 验证范围 |
|---|---|
| `apps/runtime-service/tests/utils/test_title_summarizer.py` | 保留已有 10 字清洗；多个文本块/role alias、工具/system/提醒排除、think-only、正文为空不读 reasoning、超长输出与规则 fallback |
| `apps/runtime-service/tests/http/test_title_summary.py` | 从既有无 token positive fixture 改为真实精确委托 fixture；缺 token/错误 operation/thread/project/assistant/hash、非法 schema/输入大小、授权错误不降级 |
| `apps/runtime-service/tests/services/test_thread_titles.py` | 注入受管模型、模型引用拒绝、连接/阻塞构造总deadline、provider error、取消传播、一次/no tools/no graph Run、不继承主流回调、附件只走本地 |
| `apps/runtime-service/tests/runtime/test_auth.py`、`tests/runtime/test_platform_auth.py` | title operation 合法范围与原生资源拒绝；其它 operation 不能请求 title |
| `apps/platform-api/tests/test_thread_metadata_update.py` | 手动兼容、输入限制、source/seed/pending、rename/preview、生成前后 ACL、fallback 不覆盖、真实当前 title 返回 |
| `apps/platform-api/tests/test_runtime_gateway_http_matrix.py`、`test_runtime_delegation_contract.py`、`test_runtime_model_reference.py` | 标题路由 DTO、read/title-generate/thread-edit 分离、模型与项目隔离；按 operation 集合断言 |
| `apps/platform-api/tests/test_thread_fork.py` | fork 不复制自动 eligibility，旧显式标题保持 |
| `apps/runtime-service/tests/integration/test_thread_title_flow.py` | 复用隔离native服务harness，启动真实API/Runtime/Worker/PG/Redis；成功/改名/并发/撤销/未知写回查与真实受管模型 |
| Web service/composable/Page tests | 交接 F01-F09；success 与最终正文到达顺序、visible catch-up、scoped epoch、manual 优先、错误 DTO/未知写结果 |

现有用例的 mock 只证明逻辑，不证明真实 scope、Server 自定义路由认证或数据库并发。

## 集成与安全门禁

- [x] 精确HTTP/真实签名契约：无Bearer、过期/篡改、项目/Thread/Graph/hash/operation拒绝。网络链路验证合法token与无token/错Graph；其余拒绝在signed ASGI/跨解释器矩阵验证，不声称每一项都经真实网络。
- [x] title token无原生Thread/Run/Workspace/MCP权限；read/suggestions/usage不能代用。网络Thread/Run/MCP拒绝与跨解释器通用原生拒绝证据组合。
- [x] 项目受管/BYOK来源、模型禁用、ACL拒绝、连接引用绑定与生成后复核；安全响应不含密钥/seed/provider原错误。真实中途gate/model及平台ACL撤销见T07A。
- [x] PG多session屏障竞争、rename两种顺序/同名清seed与无关键原子merge；真实HTTP两请求仅一个CAS applied。没有另起两个API进程，跨实例保证来自数据库SQL与两个独立session证据。
- [x] CAS实际提交后模拟响应丢失503，GET查持久title/pending，再请求不生成。
- [x] 空材料/多轮/非success/活跃Run/interrupt/stop/维护/fork/旧Thread定向拒绝；真实主state/SSE无辅助副作用。
- [x] 超时、取消、provider失败/空正文、附件only定向；真实provider失败不自动重试。
- [x] metadata唯一事实源；主state/SSE前后逐值相等，无新Graph channel/标题表/辅助nativeRun。
- [ ] CAS 正式版本、双包、来源/哈希/契约与 cold install 真实记录；本地 source/post 同名候选不冒充正式。

## E2E、性能基线与回退

- [x] **非浏览器完整链：** 新Thread -> 平台Run -> Runtime真实受管模型回复 -> 自动请求 -> CAS -> GET刷新，主state/SSE保持。列表展示/浏览器由T06/T07B补验。
- [ ] **第二入口：** Dear Agent 相同链路与手动改名/手动 AI 提炼回归。
- [x] **后端故障链：** title超时/未知提交/生成中改名与gate/model撤销；Stop/HITL的服务端资格拒绝。真实浏览器Stop/HITL交互仍待前端。
- [ ] **浏览器验收：** 前端 F01-F10，Playwright 在 1440/768/390 视口截图；正文/工具/思维链流中没有幽灵标题消息。
- [x] **辅助耗时/次数：** fixture成功HTTP0.887s，真实qwen-plus1.293s；8场景agent7/title8，两个竞争请求可各调用模型，CAS只存一个结果。8s为Runtime连接/构造/调用deadline，不是全HTTP SLA；真实title usage未另采账，沿获批排除范围，不宣称免费。
- [x] **关闭auto验证：** 新请求disabled，生成中关闭也不写；人工rename/手动模式回归。候选官方旧包缺CAS已核对，不能退回普通PATCH；API/Runtime须匹配新正式引擎，正式发布/版本回退演练单列B01，未部署现役。

## 本轮基线记录（2026-10-09）

执行范围：本地隔离的既有定向单元/组件测试；无真实供应商调用、无数据库迁移、无生产 API。

| cwd | 实际执行命令（文档不含 rtk） | 结果 |
|---|---|---|
| `apps/runtime-service` | `./.venv/bin/python -m pytest tests/utils/test_title_summarizer.py tests/http/test_title_summary.py -q` | 13 passed；16.58s；6 个既有 dependency deprecation warnings |
| `apps/platform-api` | `./.venv/bin/python -m unittest discover -s tests -p test_thread_metadata_update.py -v` | 6 passed；0.139s；模型/Thread upstream mock |
| `apps/platform-web` | `pnpm exec vitest run src/utils/thread-title.spec.ts src/services/threads/session.service.spec.ts src/modules/chat/components/ChatThreadSidebar.spec.ts src/modules/dear-agent/components/DearAgentThreadSidebar.spec.ts` | 4 文件、36 passed；7.44s；既有 pnpm patchedDependencies 提示 |

**解释：** 本轮 55 项通过证明现有规则命名、手动提炼 helper、元数据编排、service 和侧栏已有实现与测试；不证明自动标题或生产安全能力。Runtime HTTP positive 用例没有携 Bearer，只有 app mount 层证据；真实 GraphHarbor 外层 auth 本轮没有联验。

文档链接、docs checker 与 diff 校验在规划收尾记录，不将它们写为功能 Final。

## Phase 验证记录

### T01 精确委托与契约（2026-10-09）

- API：`PYTHONPATH=src:tests .venv/bin/python -m unittest tests.test_automatic_thread_title tests.test_thread_metadata_update tests.test_thread_fork tests.test_runtime_delegation_contract tests.test_runtime_model_reference tests.test_runtime_gateway_http_matrix -q`，38 passed，337.445s。
- 最新将title-generate加入既有跨解释器OPERATIONS矩阵：`PYTHONPATH=src:tests .venv/bin/python -m unittest tests.test_runtime_delegation_contract -q`，5 passed，25.150s；覆盖真实签发/解析、缺Thread/Graph绑定、原生资源拒绝与其他operation回归。
- Runtime signed HTTP 矩阵：无 Bearer、过期/项目不匹配、错误 operation/Thread/Graph、schema、当前 ACL 撤销与原生资源拒绝通过；最初 Runtime title 定向共 16 passed，33.08s。
- 以上有 HTTP ASGI/真实签名与跨解释器证据，完整网络服务证据继续由 T07 记录。

### T03 材料与附件（2026-10-09）

- Runtime：`PYTHONPATH=src .venv/bin/python -m pytest tests/services/test_thread_titles.py -q --tb=short`，5 passed，24.37s。
- 合法附件不调用模型；跨 Thread、不匹配 size、未知工作区均 skipped；正文缺失不读取 reasoning。
- 初跑新增附件用例暴露 `RuntimeWorkspaceError` 被归为provider_failure，已修正为materials_missing并重跑通过。最新Runtime标题helper/service/HTTP17项通过（55.31s）；新增阻塞构造deadline后service6项通过（3.41s）。

### T02 受管一次调用（2026-10-09）

- `PYTHONPATH=src .venv/bin/python -m pytest tests/services/test_thread_titles.py -q --tb=short`：6 passed，3.41s。一次ainvoke、max_retries=0、disable_streaming、callbacks=[]、nostream、引用/哈希拒绝、超时、取消、附件、空正文覆盖。
- 同步模型构造移入 `asyncio.to_thread`，受deadline覆盖；阻塞构造timeout后不得调用ainvoke。已开始的同步构造线程不能强杀，但不执行模型请求，未承诺8s内线程必退出。
- 真实qwen-plus模型通过平台目录创建项目BYOK配置，再复用主Run与标题同一个受管连接；成功HTTP1.293s、最终标题6字，CAS/刷新通过。
- DeepSeek初测主Run60s等待失败，扩大仅测试主Run等待后主Run成功，但title降级未通过applied断言。8s直接辅助探测为TimeoutError；后续使用现有百炼凭据完成真实成功门禁，不将供应商超时抹掉或扩大标题deadline。

### T04 引擎源码与候选（2026-10-09）

- 引擎命令：`PYTHONPATH=libs/langhost/src:libs/langgraph-runtime-pg/src .venv/bin/python -m pytest libs/langhost/tests/test_thread_metadata_cas.py -q --tb=short`：4 passed，最新36.35s。PG两个独立session并发屏障、两种rename顺序/同名、8个无关键并发merge、missing/null/filter、HTTP422/404/409、ttl-only和minimal204。
- 构建：`uv build --offline --package graphharbor-runtime --out-dir /tmp/f07-title-candidate-20261009/v2/runtime` 和 `uv build --offline --package graphharbor --out-dir /tmp/f07-title-candidate-20261009/v2/cli`，wheel/sdist均成功。在线hatchling下载曾timeout，offline缓存完成，非block。
- 冷安装：新 `/tmp/f07-title-candidate-20261009/venv-v2` 先安装Runtime冻结导出的136依赖，再只替换本地v2双包wheel；direct_url及模块来源确认在该venv，未加载引擎源码PYTHONPATH。实际链路使用同v2双包的 `/tmp/f07-title-candidate-20261009/venv`，其余依赖按同冻结文件安装。

| v2产物 | SHA256 |
|---|---|
| CLI wheel | ae4ae5564558a488c47e80c7498fe109c50f0684e4a5c57a7222d069378e8660 |
| Runtime wheel | 22b87a8afa4abedc3f5bcc3b3d88d3fc1460c6e8094c036c547bae72f28aafde |
| CLI sdist | 41553f24a3bc3fd9f30173d76208e0fa80e1c7ff40fd66561cef9922aa0a7258 |
| Runtime sdist | db9c94bdd29585d617a2e0209950afad26d7a7f3d2b6584d97f7013d42b39573 |
| Runtime uv.lock | 780e842efbdbd9da297f05d6d37f9b1c9fec93400c48bd575b565f8a50ca8ba3 |
| 冻结locked.txt | f3dfb6977f07c96ecc38947970d66a70f7a9bd233364f4e45b30c058ec8ff949 |

- PyPI正式post43双包下载digest核对：CLI `8fcb0910829355df2582e5e88881c527e442ff5dc94a92de85b760d9e2911670`；runtime `96c16ccff6314855d5d65a38b8c8633ee3791deeb907f841810c87e334659b65`。官方CLI含cancel-active，不含metadata/cas；官方runtime无thread_metadata.py。正式新唯一版本发布/正式源接入为B01，候选不等于正式。

### T05 自动编排（2026-10-09）

- API最新：`PYTHONPATH=src:tests .venv/bin/python -m unittest tests.test_automatic_thread_title tests.test_thread_metadata_update tests.test_thread_fork -q`：27 passed，8.035s，包含preview迟到返回保持上游实际新title。
- 首轮/多轮、工具中间态/reasoning、非success/维护/活跃Run/interrupt、同名改名、私有注入、gate、ACL/model与材料/checkpoint变化、CAS冲突/404/未知返回及manual兼容。
- HTTP/Worker/PG/Redis8场景与真实受管模型通过，完整证据见T07A。

### T07A 非前端链路与收尾（2026-10-09）

实际命令（cwd `apps/runtime-service`，`PYTHONPATH`使用两服务src，不含GraphHarbor源码）：

```bash
RUN_THREAD_TITLE_FLOW=1 TITLE_REAL_MODEL=1 TITLE_REAL_PROVIDER=bailian \
  /tmp/f07-title-candidate-20261009/venv/bin/python -m pytest \
  tests/integration/test_thread_title_flow.py -q -s --tb=short \
  --basetemp=/tmp/f07-title-http-v3-real-20261009
```

- 2 passed，91.14s：fixture8场景 + 真实qwen-plus成功场景。产物 `/tmp/f07-title-http-v3-real-20261009/test_isolated_thread_title_htt0/title-evidence.json`（fixture）、`test_isolated_thread_title_htt1/title-evidence.json`（real）；诊断只存outcome/reason/耗时，不存正文或凭据。
- fixture：成功刷新/state/SSE逐值不变、title合法token原生拒绝、同名manual优先、provider失败保留规则且无retry、双请求仅一个CAS applied、gate/model生成中撤销不写、CAS实际提交丢响应503与GET对账/不再生成。主agent7次/title8次。
- 初次5场景fixture通过保留在 `/tmp/f07-title-http-all-20261009/test_isolated_thread_title_htt0/title-evidence.json`。v2重跑有竞态等待10s失败、real降级；v3另一次native启动180s超时。后续有界屏障与阻塞构造deadline修复后，上述完整链路重跑通过。
- 新增平台ACL真实撤销扩验的首次fixture错误使用UUID查询字符串主键，供应商屏障未释放导致退出timeout；修正主键并使屏障等待有界后，最新 `RUN_THREAD_TITLE_FLOW=1 ... -k fixture --basetemp=/tmp/f07-title-http-v5-acl-20261009`：1 passed、1 deselected，79.28s。9场景通过，agent8/title9；实际平台ACL生成中撤销返回403，恢复测试ACL后GET确认规则title与pending未变化。证据 `test_isolated_thread_title_htt0/title-evidence.json`。
- Runtime扩展定向：`PYTHONPATH=src .venv/bin/python -m pytest tests/utils/test_title_summarizer.py tests/services/test_thread_titles.py tests/http/test_title_summary.py tests/runtime/test_auth.py tests/runtime/test_platform_auth.py -q --tb=short -k "not test_thread_auth_rechecks_signed_platform_acl"`：76 passed、1 deselected，7.99s（另次8.25s，同一范围无需叠加计数）。
- Ruff check：API12个本次文件、Runtime8个本次文件、GraphHarbor共享helper/HTTP/ops/server/test通过；format定向检查通过。两仓git diff --check通过。服务venv未装Ruff，使用已存在的GraphHarbor工具环境，不增加依赖。
- 全仓 `python scripts/check_docs.py` 报37处既有绝对路径（open-swe-vs-runtime-gap及其他旧专项），均非本次F07文件；复用 `scripts.check_docs.check_file()` 定向检查专项、旧标题项目和受影响活规范16文件，0 errors。
- 使用已安装的 `markdown-it` 解析本地链接：平台16份、引擎10份文档，共128个本地链接目标，0 missing；仅核对目标存在，不验证外链或片段锚点。两仓diff --check通过。委托矩阵当前30项，加独立Cron共32项，方案/活规范/交接明确创建时gate关闭无seed、之后不回填。
- 失败ACL扩验遗留的一份 `.model-resilience-worker-*.json` 已确认无进程使用并清理；未删除其他测试配置。

### 既有基线失败与边界

- Runtime `test_thread_auth_rechecks_signed_platform_acl` fixture只接受timeout/trust_env，`auth/acl_client.py::post_acl` 的HEAD已有 `verify=False` 导致断言失败；本专项未改此文件，未顺手修改TLS策略或凑绿。
- API `test_runtime_gateway_runtime_contract.py`：19 passed、1 error。`test_run_launch_attaches_opaque_model_reference_from_platform_runtime_context` 传非UUID `project-1`，HEAD已有模型恢复快照/模型许可校验解析UUID；`_attach_runtime_model_reference()` 本轮未改。保留基线，不声称全仓全绿。
- 未执行前端接线/Playwright/浏览器Final，不发布包、不改现役、不提交Git。正式源安装/版本回退演练随B01，自动默认关闭；manual AI新版同样依赖CAS。

## Final 验证

**未执行；全项目partial。** 非前端源码/候选完成，前端T06/T07B与正式发布B01仍待完成。每个后端任务证据记Phase；使用verify-change记录真实结果，不提前宣称联合Final或现役可用。
