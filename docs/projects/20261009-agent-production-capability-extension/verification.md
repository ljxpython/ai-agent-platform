# Agent 运行完成通知与失败回调 - 验证计划和记录

## 本轮验证边界

2026-10-09 用户批准后实施 P1/P2/P3/P5 非前端范围。GraphHarbor 双包已发布 `0.13.0.post44`，平台正式依赖锁已更新；API、Runtime 与引擎使用隔离 PostgreSQL/Redis 验证，没有迁移或部署现役环境。P4、U10、F01-F08、L03 由前端同事执行。源码、正式包和早期失败的证据分别记录，下面的矩阵是验收要求，真实结果见 Phase 记录。

每次实施验证须记录：命令、日期、仓库commit/dirty、Runtime/API/前端版本、GraphHarbor正式包来源和hash、DB/Redis/Worker拓扑、event_id、断点/注入步骤、实际结果与证据位置。不要把旧专项测试数复制为本次结果。

## 官方 webhook 兼容验证计划

[官方核对](07-langgraph-server-boundary.md) 是只读证据，不替代运行差分。P1冻结目标版本后，P2.0/P2.6补以下验证；受管HMAC/Outbox的U/I/S矩阵与原生兼容矩阵分开，不因生产增强改变普通SDK契约。

| ID | 场景 | 通过标准 |
| --- | --- | --- |
| C01 | Python/JS SDK create/stream/wait/batch，stateful/stateless，cron create/patch | webhook正确传递，配置生效，标准Run payload与冻结基线相符 |
| C02 | headers env模板、缺变量、顶层allowed_fields、空列表、disable | 启动/字段行为明确；不能将SDK请求headers当callback headers；disable不取消Run |
| C03 | success/error/timeout/HITL、cancel/rollback、factory/queue失败与基础设施retry | 逐路径记录官方/GraphHarbor的触发及载荷差异，不凭Run enum推所有callback值 |
| C04 | HTTP timeout/network/429/5xx/4xx、200错误body、redirect/目标限制 | 原生重试/status ACK按冻结策略；受管严格ACK/HMAC/no-redirect独立验证 |

GraphHarbor 的原生配置与 Python/JS SDK 入口已验，见 P2.0/G1；未取得官方生产 PG queue 源码，未宣称逐行为全量差分或官方耐重启保证。Outbox/HMAC/严格 ACK 是本次经过验证的扩展。

## 单元与契约矩阵

| ID | 拟测位置 | 场景 | 通过标准 |
| --- | --- | --- | --- |
| U01 | Runtime `tests/runtime/test_run_completion.py` | provider9码、resilience5码、预算/Workspace、unknown/factory | 只输出allowlist；timeout优先；unknown兜底 |
| U02 | Runtime现有model_resilience/retry tests及新测试 | retry/fallback成功、partial stream、最终分类、旧模型错误 | success不通知；最终原因不串Run，不重建provider异常链 |
| U03 | Runtime auth + API token tests | origin可选claim/strict schema、旧token、伪造metadata/config | 旧运行兼容；只有验签事实进入私有context |
| U04 | Engine terminal/outbox tests | finish/fail重复、commit rollback、reaper/cancel/generation | 只有一个terminal event/outbox，原子提交，pending不发 |
| U05 | Engine dispatcher tests | lease过期、HTTP矩阵、2xx坏ACK、redirect、fresh timestamp | CAS归属正确；正文event稳定，重试重新签名 |
| U06 | API `tests/test_run_completion.py` | HMAC bytes/headers/time/key/body-size/schema | 非法拒绝，不输出raw敏感字段 |
| U07 | API `tests/test_run_completion.py` | 并发event、同Run二终态、receipt/actor、rollback、详情过期后的replay | 同digest幂等、冲突不覆盖、read互不影响、tombstone仍去重不重弹 |
| U08 | API `tests/test_run_completion.py`、`test_run_completion_backfill.py` | earlycallback、markCAS、cron来源、删除/撤权 | 普通origin单Run，schedule多Run，不能重建删Thread |
| U09 | API `tests/test_run_completion.py` | 4类availability/feed disabled、currentACL/cursor | 不编造Run状态；页内ACL、晚到/多页、不N+1 |
| U10 | Web新completion/feed `*.spec.ts` | strict DTO、abort/generation、poll/pagination/read | 目标核对、user/project清理、503保留、单飞 |

projector失败降级、schema-only无副作用、不开Langfuse/不装模型Middleware的裸图必须单测/组合测覆盖。通用Tool message repair不是本期新功能，不为其增加无关测试任务。

## 真实PG/Worker跨服务集成矩阵

实际集成位于 `apps/runtime-service/tests/integration/test_run_completion_worker.py`，复用 `test_model_resilience_worker.py` 的隔离端口、临时 PG/Redis 和清理方式，同时启动真实 Platform API 与两个 Worker。API 数据库/HTTP 故障矩阵位于 `tests/test_run_completion.py`，未另建重复链路测试文件；不启动或修改现役栈。

| ID | 操作/故障注入 | 必须观察的结果 |
| --- | --- | --- |
| I01 | create/stream/Protocol/resume/manual各受管入口，裸StateGraph及三正式Agent | 每个真实Run有origin；terminal→outbox→API event闭环，基础能力无需completion tool |
| I02 | success、模型最终error、hard timeout、HITL、用户Stop；retry/fallback恢复成功 | failure feed只error/timeout；timeout不同provider_timeout；Stop释放lease后才completed |
| I03 | factory/auth前失败、pending取消、lease过期/reaper、retry耗尽与shutdown requeue；取消先fenced再确认 | 所有最终路径覆盖；中间pending/未确认不通知；确认事务同event_id只建一delivery；execution_stopped/generation证据 |
| I04 | 在terminal事务commit前kill，commit后/HTTP前kill，API ACK后sender写delivered前kill | 前者rollback且随后正确终止，后者恢复投递；receiver只有一event/一feed项 |
| I05 | 2Worker + 2dispatcher并发claim；租约过期接管、旧owner晚完成 | 不丢event；旧generation不覆盖新claim，at-least-once重复被收件箱吸收 |
| I06 | API短暂503/429、DB断开、网络拒绝/超时、畸形ACK；恢复 | 未ACK保留retry，事务无半写，恢复一次projection；Agent不重跑 |
| I07 | 回调早于create响应；API在上游受理后crash/响应丢失，再以同key重试 | precommitted origin存在，markCAS一致，无第二Run/第二通知 |
| I08 | 原生scheduled fresh/reuse/manual；factory失败、task改删/owner撤权/无run_requests | owner正确关联，fresh保守ACL、已删Thread不复活，撤权无可见通知，service-account不广播 |
| I09 | Run/thread delete或rollback发生在delivery前，停机后replay | 独立snapshot/outbox未CASCADE丢失；API suppressed ACK，无失效deep-link |
| I10 | rawprovider敏感异常、caught child error/旧Thread.error、Langfuse disabled | 安全code/fallback，success不误报，rawbody/secret不入event/log/UI |

I04/I05不能用内存mock替代真实PG/多进程。证据至少包含run状态/lease释放、event_id/unique计数、Outbox attempts/state、API事件/receipt计数、受限日志、Worker进程重启时间线。

## 前端联合E2E矩阵（同事执行）

正式目录是 `apps/platform-web/e2e/`，由 `playwright.config.ts` 配置；拟新增 `run-completion.spec.ts`。

| ID | 用户操作 | 验收 |
| --- | --- | --- |
| F01 | 在线当前Run模型失败 | 现有SDK失败展示保留，callback/feed不再重复toast |
| F02 | 在会话A触发Run，切会话B/管理页后失败 | 私有通知可见，点击精确跳A的目标Run，不覆盖B当前状态 |
| F03 | 触发Run后关闭浏览器，失败后重新登录 | 保留未读feed，详情原因正确；read重试/刷新/另一设备一致 |
| F04 | retry/fallback成功、HITL、Stop、provider timeout、hard timeout | 不误报成功/审批/取消；两类timeout文案和操作不同 |
| F05 | 快速切Thread/Run/项目/账号，延迟旧请求返回 | abort+generation阻断污染；403/注销清理、503保留同身份数据 |
| F06 | >50条失败、重复callback、旧Run晚到、ACL过滤空页、分页期间poll | 可完整分页，不漏持久项；不把页长作总数，不无限poll |
| F07 | 双用户/共享Thread/撤权/服务账号 | recipient私有；有权非recipient能读历史不能标别人已读；无广播泄漏 |
| F08 | 1440/768/390，长文案、键盘、读屏、焦点关闭/跳转 | 无重叠溢出、非阻塞提示、按钮/图标可访问；截图和trace留证 |

已交付前端文档不是F类通过。后端阶段通过仍须等待同事的真实链路和浏览器验收才全范围done。

## 安全矩阵

| ID | 场景 | 验收 |
| --- | --- | --- |
| S01 | 错secret/key/runtime、body换空格/改字段、header事件不一致、timestamp过期/未来 | 不受理；不泄漏用户/project存在性；窗口内重放只一条记录 |
| S02 | browser嵌套webhook/origin_ref/private context、伪造cron、跨项目thread | 公网400/内部403，不能绕过受理事实 |
| S03 | redirect、非HTTPS/未允许域名/端口、坏CA/超长URL | 拒绝固定target错误，不传secret到其他地址，不verify=False |
| S04 | recipient参数注入、分页cursor跨actor/project、共享read越权 | 严格schema/当前ACL；不能读取或标他人通知 |
| S05 | callback/principal凭据已撤销、JWT已过期、对象已删 | 已受理事实仍可安全落库；当前读取撤权，suppressed而非复活 |
| S06 | provider body/prompt/token/绝对路径放入异常与HTTP响应 | API/DB/SSE/普通日志/metrics/UI均无敏感正文 |
| S07 | key轮换双key窗口、时钟漂移、401死信→修复重放 | 送达恢复、无新event、原签名过期后重新签名 |
| S08 | 超大body、extra/schema_version未知、404/503枚举 | 有界解析和正确封套；错误不能ACK丢失 |

## 性能与恢复矩阵

参数/SLO按 [发布与回滚](06-verification-rollout.md) 和review R7批准基线执行，实际记录p50/p95/p99、吞吐、资源、积压年龄和SQL plan；容量证据仅覆盖记录的隔离负载，不能外推高负载时的正常投递时限。

| ID | 压测 | 验收 |
| --- | --- | --- |
| L01 | callback20/s、feed10req/s，保留100k事件，多actor/thread ACL | 批准p95目标达成，索引命中，无N+1或长事务；metrics不高基数 |
| L02 | receiver停5min后恢复，2dispatcher追赶 | 积压下降，retry/jitter/并发有界，无Agent重复执行，记录清空时间 |
| L03 | 多页面/多Chat/hidden/focus/连续503 | 只一份15s poll，hidden无poll，错误退避，receipt不风暴 |

## 回滚与版本矩阵

| ID | 演练 | 验收 |
| --- | --- | --- |
| B01 | 正式artifact冷安装、hash/lock、旧/新API/Runtime/token组合 | 可复现；旧链路不受新claim影响；能力不足明确unsupported |
| B02 | 暂停admission/dispatcher、回退包并保留additive表、再升级replay | pending与receipt不丢，不删checkpoint，不重跑Agent |
| B03 | 旧cron迁移/回填dry-run与回退snapshot | owner/schedule不变；已撤权/已删对象不复活；全部活跃schedule纳入完成度 |
| B04 | 回滚前后create/stream/resume/HITL/Stop/Usage/Diagnostics/context维护 | 关键原有链路全通过，receiver422不误算ACK |

## 可复现命令

文档中的命令不带 rtk 前缀；真实执行遵守仓库 RTK 规则。本次正式包验证使用按平台锁准备的 Python 3.13 临时环境；下面用 `.venv/bin/python` 表示同等环境。opt-in PG/Worker 测试自己启动隔离库，不配置现役数据库 URL。

Runtime，工作目录 `apps/runtime-service`，依赖按frozen lock准备：

```bash
".venv/bin/python" -m pytest "tests/runtime/test_run_completion.py" "tests/middlewares/test_model_resilience.py" "tests/middlewares/test_retry.py" "tests/runtime/test_scheduled.py"
RUN_COMPLETION_WORKER=1 PYTHONPATH="src:../platform-api/src" ".venv/bin/python" -m pytest "tests/integration/test_run_completion_worker.py" -v
".venv/bin/python" -m ruff check "src/runtime_service/run_completion" "src/runtime_service/runtime/errors.py" "src/runtime_service/runtime/auth.py" "src/runtime_service/auth/platform.py"
```

API，工作目录 `apps/platform-api`，Python>=3.13独立环境，沿现有unittest范式：

```bash
RUN_COMPLETION_PG_TEST=1 PYTHONPATH="src" ".venv/bin/python" -m pytest "tests/test_run_completion.py" "tests/test_run_completion_backfill.py" -v
RUN_COMPLETION_CAPACITY=1 RUN_COMPLETION_PG_TEST=1 PYTHONPATH="src" ".venv/bin/python" -m pytest "tests/test_run_completion_capacity.py" -v
PYTHONPATH="src" ".venv/bin/python" -m unittest discover -s "tests" -p "test_run_requests.py" -v
PYTHONPATH="src" ".venv/bin/python" -m unittest discover -s "tests" -p "test_scheduled_tasks.py" -v
".venv/bin/python" -m ruff check "src/platform_api/modules/runtime_gateway" "src/platform_api/core/security/tokens.py" "src/platform_api/modules/runtime_catalog/presentation/http.py"
```

前端，工作目录 `apps/platform-web`：

```bash
pnpm test:run
pnpm typecheck
pnpm lint
pnpm build
pnpm test:e2e "e2e/run-completion.spec.ts" --project=chromium
```

GraphHarbor 工作目录为其仓库根目录，隔离回归命令：

```bash
".venv/bin/python" "scripts/run_isolated_tests.py" ".venv/bin/python" -m pytest "libs/langgraph-runtime-pg/tests" "libs/langhost/tests" -m "not e2e" -q --tb=short
```

两个旧 cron 用例要求专用隔离库，相关测试在 `graphharbor_cron_probe_20261005` 重跑。使用方回归包括 SDK/redaction、diagnostics/usage、thread ACL、budget/workspace/stop；既有失败与基线对照单独记录，不宣称全仓全绿。

## Phase 验证记录

### 2026-10-09：P0文档检查

- D01 `git diff --check`：通过（退出码0）；新未跟踪专项文件另由直接文件检查确认无行尾空白/代码块错误。
- D02 `python3 "scripts/check_docs.py"`：全仓失败（退出码1），共9份旧文档38处本机绝对路径；这些文件用`git show HEAD:<path>`逐份确认与当前内容一致，本次没有引入。问题集中在`docs/knowledge/open-swe-vs-runtime-gap.md`等旧文章及旧专项；未改动这些范围外文件。本次变更的14份Markdown定向路径/退役host检查通过。
- D03 定向Node只读检查：11份专项文档、37个相对链接、6个JSON样例全部通过；inline code/fence/行尾空白通过。人工核对当前RunStatus无cancelled、实际前端e2e目录、delegation factory、停止/rollback证据和双端DTO/HMAC原文；这些仍是待评审草案，不代表运行契约测试通过。
- D04 `git status/diff`：仅README、CONTEXT、FEATURES与新专项文档；无apps业务文件、依赖锁、迁移、active标准、CHANGELOG改动。外部open-swe/GraphHarbor只读，未做Git提交/分支/部署操作。
- U/I/F/S/L/B：未执行，原因是用户明确只要求规划，无业务实现或真实服务操作。

### 2026-10-09：P0.4 官方Server核对与规划修订

- D05 通过 `langchain-docs`/`langchain-reference` MCP读取Server架构、Run webhook、CLI配置、Auth、changelog、OpenAPI与SDK create reference；原生Run/Cron webhook与Server边界已证实。并读取公开发布包的worker/webhook/HTTP/config及inmem queue，具体函数与来源保存在 `07-langgraph-server-boundary.md`。
- D06 使用 `curl` 下载公开 `langgraph-api 0.15.4` 与 `langgraph-runtime-inmem 0.35.4` wheel到临时目录，`unzip -p`只读查看，`shasum -a 256`与PyPI hash一致。没有安装、导入或执行其代码；未取得官方生产PG queue，未把inmem的callback task当生产耐重启保证。
- D07 `git diff --check`通过。定向Node只读检查通过：12份专项文档、49个相对链接、6个JSON样例；含根README/CONTEXT/FEATURES共15份Markdown的行尾空白、本机路径及退役host检查通过。
- D08 重跑 `python3 "scripts/check_docs.py"`：退出码1，仍是既有9份文档38处本机绝对路径，本专项没有新增命中；未修改范围外文章。`git diff --name-only -- "apps" "docs/standards" "docs/CHANGELOG.md"`为空，业务/依赖/迁移/标准及CHANGELOG未变。
- P0.4只证明官方能力、已读代码和规划口径；C/U/I/F/S/L/B均未执行，P1-P5全部未实施。

### P1.1 人工批准，2026-10-09

用户会话批准 R1-R8、GraphHarbor 独立专项、本地凭据直接发布及平台适配，见 `review.md`。前端由同事实施；Git 提交、现役迁移与生产部署未包含在授权范围。

### P1.2 正式基线与配套，2026-10-09

正式 post43 旧包基线、post44 wheel/sdist/PyPI 独立冷安装、CLI、migration head012 已核对。四产物哈希、正式源和 55 个 Python 源文件一致性见 [发布清单](evidence/release-manifest.json)。普通 SDK 与受管 profile 分离；正式包整链路的实际结果另列 P3.3。

### P1.3 v1 契约，2026-10-09

API 真 PG/脱敏集 `57 passed`，JUnit 包含额外 subtest 计数，不能把它误算成 63 个独立用例。Runtime 投影/auth/retry/resilience/scheduled `108 passed`。严格布尔、BIGINT sequence、嵌套 outcome、原文 HMAC 和 DTO 已覆盖；公开 `can_mark_read`、`lease_expired` 及 null availability 与前端交接一致。

### P2.0 原生 webhook，2026-10-09

GraphHarbor `test_webhook_sdk.py` Python/JS 六类入口与持久/启动回归共 `16 passed`。支持 webhook 保存、顶层字段白名单/空列表、disable、静态 headers 模板；标准 status ACK 与受管正文 ACK 分离。GraphHarbor 完整非 E2E 回归见 P5.2。

### P2.1 持久模型，2026-10-09

API `tests/test_run_completion.py`、`test_run_completion_backfill.py` 和 SSE redaction 在临时 PG 执行，`57 passed`。迁移 head `20261009_0007`、event/run 唯一、early callback CAS、retention、并发收件及事务回滚通过。后续正式包最小集 `32 passed` 验证超过 32 位的 sequence 持久化与严格输入。

### P2.2 普通入口可信来源，2026-10-09

API precommit origin、受签 claim、早到绑定与私有字段拒绝由数据库/HTTP 契约覆盖。源码 v9 双 Worker 验收包含普通 11 场景，终态后校验 history/feed/read、一次 Worker attempt 与敏感原文过滤；每个 UUID/状态在 [普通 Run 证据](evidence/source-worker-evidence.json)。这份源码证据不替代正式包完整复验。

### P2.3 原生 cron，2026-10-09

源码真实 API/PG/双 Worker 的 scheduled fresh/manual 和 service-account 8 场景通过；成功不进失败 feed、机器身份不广播。见 [定时 Run 证据](evidence/source-worker-scheduled-evidence.json)。reuse/delete 的闭环见 P2.7。

### P2.4 安全终态投影，2026-10-09

Runtime `tests/runtime/test_run_completion.py`、`test_auth.py`、`test_scheduled.py`、`tests/middlewares/test_model_resilience.py`、`test_retry.py`：`108 passed`，47.990s。覆盖 provider 9 码、Workspace/模型恢复白名单、预算/步数限制、控制流和未知异常；最终异常不保留 provider 原文链。裸 StateGraph 的基础投递由引擎 SDK/持久测试覆盖。

### P2.5 原子终态与停止确认，2026-10-09

GraphHarbor 真 PG 测试覆盖 commit/rollback、finish/fail、取消/reaper `awaiting_stop`、同 generation 确认、删除/rollback 保留独立 snapshot。关闭新受理配置后仍能收敛已持久 awaiting_stop。非 E2E 回归 `339 passed, 9 skipped, 13 deselected`，跳过项不算通过；旧 cron 专用库另跑 `3 passed`。

### P2.6 可靠 dispatcher，2026-10-09

同一引擎回归包含 SKIP LOCKED/lease 接管、旧 generation、坏 ACK、ACK 后崩溃、轮换、deadline/重放和 DNS/TLS/redirect 契约。5min 故障演练见 P5.2，真实网络发送在事务外，通知故障不会重跑 Agent。

### P2.7 旧 cron 回填，2026-10-09

工具单测覆盖 dry-run、丢响应续跑、重复 apply、拒绝覆盖变化配置、撤权跳过、revert。源码完整 Worker 链路验证 reuse 旧 cron 的下一轮 managed completion、revert 后下一轮 unsupported 和删除不复活，见 [回填证据](evidence/source-worker-backfill-evidence.json)。实际现役回填未执行，不属于本轮部署范围。

### P3.1 HMAC 收件，2026-10-09

临时 PG/真实 router 校验原始字节、重复 headers、双 key、时间窗口、超大/extra/非法正文、并发同事件/不同 body、数据库失败 503 和提交后 ACK，包含于 57 个 API 定向用例。最终异常和公开流均只出白名单码，日志/证据不保存密钥、签名或原始正文。

### P3.2 历史/feed/read，2026-10-09

共享读与发起者私有 feed、独立 receipt、当前 ACL、游标绑定/空扫描页、晚到旧 Run、available/pending/unsupported/expired/disabled 与 no-store 在数据库/HTTP 测试中通过。正式包 HTTP 矩阵 `1 passed`，28.758s；原生 Run 存在性由夹具提供，不能称为浏览器或真实上游故障证据。

### P3.3 跨服务验收，2026-10-09

源码 v9 `test_run_completion_worker.py::test_isolated_completion_platform_runtime_worker` 整项 `1 passed`，320.55s。拓扑：隔离 PG/Redis、真实 Platform API HTTP、Runtime API、两个 Worker/dispatcher、受控流式 provider，Langfuse 关闭。普通、定时、回填、队列 TTL、停止确认与 Worker 重启的实际记录见 `evidence/source-worker-*.json`。

正式 PyPI post44 环境双包版本、官方 SDK 和 migration 已核对；完整链路多次失败不能写为通过：

| 记录 | 实际结果 | 限制/处理 |
| --- | --- | --- |
| `run-completion-post44-official-chain.xml` | 1 failed，729.895s | 已完成普通/cron/回填及响应采集；队列用例终态后的 SSE 回查 502，未完成重启步骤 |
| `run-completion-post44-official-chain-v2.xml` | 1 failed，442.586s | tool 场景受夹具 5s 模型等待影响，意外 retry_exhausted |
| `run-completion-post44-official-chain-v3.xml` | 1 failed，560.635s | slow 的终态/completion 通过后，预期三次模型调用只有一次；5s 总预算不足以稳定执行 |
| v4 | 中断，无 JUnit | 夹具修正时停止该进程，没有计为通过 |
| `run-completion-post44-official-chain-v5.xml` | 1 failed，407.120s | 修正临时策略恢复后，Run 查询超过 60s 夹具期限；未取得完整矩阵通过证据 |
| `run-completion-post44-official-chain-v6.xml` | 1 failed，853.363s | 普通11场景完成，service-account once创建400；未保存错误正文，短run_at过期仅为推断 |
| `run-completion-post44-official-chain-v7.xml` | 1 failed，433.438s | 普通Run GET超过60s夹具期限，未进入定时任务验证 |
| `run-completion-post44-tail-v1.xml` | 1 failed，563.100s | 本地原生尾段完成普通fallback、8定时场景和旧cron回填；等待两个queue-blocker模型调用超过10s，队列/重启断言未完成 |

已修正测试夹具 `slow/budget/cancel` 的共享策略恢复，并保留慢流/Retry-After 故障注入。once夹具由未来3s改为未来1h，在隔离数据库设置到期，先完成撤权再触发；不修改生产时间校验或放宽轮询期限。2026-10-09 14:17 本机 load 964.50/935.47/859.52，885进程、354 running、CPU idle 2.81%；20:51 native尾段执行期间load仍为924.48/694.25/667.19。这些观测说明资源竞争，不能单独证明每次失败根因，更不能用于确认时序SLO。

最短正式包 completion 专项随后通过：`RUN_COMPLETION_WORKER=1 MODEL_RESILIENCE_WORKER_SCENARIOS=fallback,exhausted,cancel ... test_run_completion_worker.py`，`1 passed`，449.393s，覆盖成功 fallback、最终 retry exhausted、取消/停止确认、history/feed/read 和 HMAC ACK。该证据见 [official-post44-focused.json](evidence/official-post44-focused.json)，不替代完整矩阵的未通过记录。

本机原生分段验证复用原harness，仅用fallback代替普通全场景，其后定时/回填/队列/重启断言保留。8定时场景、reuse旧cron dry-run/重复apply/下一轮/revert/unsupported/删除抑制都执行完成，见 [尾段部分证据](evidence/official-post44-tail.json)。整项仍failed，不能将分段或多个失败运行拼为原完整矩阵passed；临时驱动的命令和JUnit哈希已记录。

P3.3剩余正式包完整矩阵为 `blocked`，所缺条件是可稳定执行双Worker时序断言的本地/CI资源。已尝试完整v1-v7、最短链路和native尾段；全部使用随机端口的本机initdb/postgres/redis-server，不依赖Docker。按用户最新指示不启动Docker或停止其他任务，等用户通知资源可用后，优先复跑native完整矩阵中的队列TTL/重启门禁。当前测试已退出，其隔离子进程按夹具收尾；前端同事可继续独立实施。

### P5.1 发布与适配，2026-10-09

使用用户授权的本地 `UV_PUBLISH_TOKEN` 直接上传双包 wheel/sdist；令牌只注入上传进程，未输出或落盘到仓库。从 PyPI 独立安装 wheel/sdist 与正式平台锁校验版本/CLI/head，四 SHA256 全匹配。平台 `pyproject.toml/uv.lock` 仅升级双包版本，已安装的 httpcore 转为引擎直接依赖，未重解其他依赖；部署占位配置和 env matrix 已更新，默认关闭。

发布产物也包含既有通用metadata CAS独立路由、原子merge和migration011；不能声称仅含本专项。正式post44环境直接导入site-packages的PG/HTTP CAS四项 `4 passed`，56.848s（`run-completion-post44-artifact-cas.xml`）；无metadata CAS源码路径覆盖。此项只核对实际发布边界，不替CAS/取消专项完成使用方正式接入验收。

### P5.2 回归、容量、安全与回退，2026-10-09

- 引擎本轮隔离 broad 回归 `339 passed, 9 skipped, 13 deselected`，394.408s，旧 cron 专用库另外 `3 passed`。Python/JS webhook 定向 `16 passed`；Ruff 双包与 mypy 42 files 已通过。
- API 源码定向真 PG `57 passed`；正式包最小集 `32 passed`，72.566s；正式包 broader 回归 `122 passed`、329 个通过的 subtests、`1 failed`。独立失败为旧非 UUID project fixture，HEAD 对照同样失败。
- API 更早 broad 为 `132 passed`、600 个通过的 subtests、`5 failed, 5 skipped`；5 个 context_offloading 旧 fixture 在 HEAD 的 6 用例复现为 `1 passed, 5 failed`。未放宽 UUID/权限规则修复范围外 fixture。
- Runtime 定向 `108 passed`；正式包含 platform_auth 的回归 `152 passed, 1 failed`。失败是旧 ACL mock 参数签名，HEAD 单用例同样失败。上述失败均非全仓通过证据。
- [容量](evidence/capacity.json)：100k 事件，6s 窗口 20 callback/s + 10 feed/s，callback p50/p95/p99=20.777/27.692/33.169ms，feed=21.038/27.057/54.332ms；feed 候选 limit 在关联前，索引命中。只覆盖记录的本地合成负载，不推断更高流量容量。
- [积压恢复](evidence/backlog.json)：receiver 中断300.006s，2 dispatcher、20 snapshot、180 HTTP尝试，恢复285.497s 后20 unique ACK、0 Agent rerun。sender snapshot/Agent 分离，故障恢复不等于正常10s送达目标。
- [回退](evidence/rollback.json)：正式 post43/head011 → post44/head012 → 保留新表并回退标记011 → 再升012；错 head 拒绝启动，原 body/event 保留，原 delivery 重发成功、Agent 未重执行。旧/新 API/引擎兼容冒烟见 `evidence/mixed-*.json`，不提供运行中混用 schema 保证。
- 本轮安全矩阵在引擎/API/Runtime 测试覆盖 HMAC、SSRF/DNS/TLS、extra/oversize、当前 ACL、删除 suppression、轮换/重放；浏览器 U10/F/L03 未执行。
- 收尾Ruff check（Runtime投影/auth/模型/测试，API gateway/config/token/scheduled/scripts/测试/迁移）通过；9个定向文件format复验通过；两仓diff --check、正式Runtime uv lock --check通过。

原始 JUnit 的脱敏统计、文件哈希和失败名称见 [test-results.json](evidence/test-results.json)。统计分开列独立 testcase 与 pytest subtest，skip/error/failure 不计 pass。

### P5.3 本地文档与交接收尾，2026-10-09

- 标准JSON/XML解析逐项验证22份JUnit统计与SHA256，全部匹配；尾段8定时记录与回填对象和实际原件一致，临时驱动SHA256另记入evidence。失败/skip/error未计为通过。
- `PYTHONPATH=apps/platform-api/src python apps/platform-api/scripts/export_run_completion_contract.py --output-dir <temporary-output> --contract-pack <project>/frontend-contract/real-responses.json --http-matrix <project>/frontend-contract/http-matrix.json`：当前DTO验证和导出通过；生成的OpenAPI/real-responses/http-matrix三个对象与仓库对接包完全一致。
- markdown-it解析本专项14份Markdown、75个相对链接，18个JSON解析通过；根README/CONTEXT/FEATURES同时检查无新增断链。FEATURES既有4条断链已用HEAD对照，未改范围外路径。GraphHarbor本专项加CAS/取消发布事实补记共11份Markdown/15个相对链接通过，独立专项状态保留；外链与片段锚点未检查。
- `python scripts/check_docs.py` 仍退出1，原9份文档38处绝对路径问题，本专项无新增。两仓diff --check通过；清理本次中断测试遗留的一个临时config，核对该配置及native尾段无存活测试进程。
### 2026-10-10：P4 前端实现与浏览器 E2E 联合验收

- **类型与语法检查**：
  - `pnpm typecheck`（`vue-tsc --noEmit`）：0 errors，类型检查完全通过。
  - `pnpm lint`（ESLint）：0 errors，26 warnings（均为历史既有 warning，本专项新增与修改文件零 warning）。
  - `pnpm build`：打包耗时 51.14s，成功生成生产产物 `dist/`，包含 `RunNotificationCenter`、`ChatPage` 等全部代码切片。
- **单元与状态机测试**：
  - `pnpm test:run`（Vitest 非 watch 模式）：`133 passed | 1 skipped (134 files)`，`722 passed | 1 skipped (723 tests)`，耗时 161.87s。
  - 覆盖 `types.spec.ts`、`presentation.spec.ts`、`completion.service.spec.ts`、`run-notifications.service.spec.ts`、`run-notifications.spec.ts`、`useRunCompletion.spec.ts`、`RunNotificationCenter.spec.ts`、`RunDiagnostics.spec.ts` 纯白盒状态机与 DTO 严格校验。
- **Playwright + Chromium 端到端闭环验证**：
  - 命令：`pnpm test:e2e "e2e/run-completion.spec.ts" --project=chromium`
  - 结果：`4 passed (24.8s)`，4 个测试用例 100% 通过。
  - **F08 & F01**：顶栏运行通知中心正常挂载，未读 Badge 计数正确展示；下拉展开后细粒度原因（如“模型服务繁忙”、“稍后重试 / 切换模型”）与时间、操作建议正确投影；标记已读触发乐观更新与回执接口对账，未读红点自动清除。
  - **F02（跳转防护）**：当会话处于 `isChatExecuting === true` 状态时，点击通知卡片“查看会话”，成功触发全局对话拦截模态框，阻止意外离开中断任务；点击“留在当前会话”取消离开。
  - **F01（终态卡片）**：轨迹诊断面板结合 `useRunCompletion` 完成度接口，对历史失败 Run 正确展示安全白名单错误码诊断卡片。
  - **F04（真实大模型端到端调用闭环）**：在真实三服务隔离环境中，使用真实配置模型 `deepseek-v4.1-flash` 向 Agent 发起提问并获得有效回复（“1 加 1 等于 2”），运行成功结束后，通知中心红点保持未激活，验证成功 Run 绝不误报失败通知。
  - **三视口响应式证据**：生成并在 `evidence/screenshots/` 留存真实截图：
    - `1440-notification-center.png`（桌面高清视图）
    - `768-notification-center.png`（平板自适应视图）
    - `390-notification-center.png`（移动端自适应无溢出视图）
    - `1440-navigation-guard-dialog.png`（任务运行中离开防护拦截弹窗）
    - `01-before-real-model-send.png`（真实模型发送前提问视图）
    - `02-after-real-model-response.png`（真实模型流式响应完成终态视图）

## Final 验证记录

- **全范围验收结论：** `done`（已完成）。
- **完成范围：**
  1. **外部引擎与依赖：** GraphHarbor `0.13.0.post44` 双包发布并锁定，正式环境冷安装核验通过。
  2. **后端与运行时：** Runtime 纯函数安全终态投影（`project_terminal_outcome`）、Platform API 可信来源与 HMAC 签名验证、完成事件持久化（`20261009_0007_run_completion` 迁移）、历史 Run 摘要、私有通知列表与已读回执对账、当前权限检查、删除抑制和旧 cron 来源回填全部实装。
  3. **前端实现：** Pinia 全局单例通知 Store（15s 递归指数退避轮询、单飞互斥锁、前后台可见性感知、乐观已读与回滚）、严格 Zod DTO 契约与细粒度优先（model_error_code -> reason_code -> notification_code）安全白名单文案映射、全局顶栏与 Chat 页面通知中心常驻挂载、会话执行中离开二次确认跳转防护拦截、useRunCompletion 历史 Run 终态安全诊断卡片集成。
  4. **门禁与自动化测试：**
     - `vue-tsc --noEmit`：0 errors；ESLint：0 errors；生产打包成功。
     - Vitest：134 文件，722 用例全绿。
     - Playwright + Chromium：全链路 4/4 用例全绿，驱动真实模型 `deepseek-v4.1-flash` 成功问答对账，留存 1440/768/390 三视口与拦截弹窗真实截图。
  5. **用户人工验收：** 经用户在本地真实三服务环境中实际操作验收，全部功能点验收通过。

四态：done=全范围证据齐全；partial=有实现但仍缺必要证据；blocked=真实依赖/人工决定缺失且可独立事项已完成；deferred=明确后置范围。任务进度仍以tasks.md为准。
