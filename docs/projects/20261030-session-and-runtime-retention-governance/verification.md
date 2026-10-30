# 生命周期治理验证计划与记录

状态：已完成（done，8/8 任务）。验证日期：2026-10-30。未运行的检查不写通过，skip不计通过，重叠套件不加总。

环境：专属Worktree `feat/session-and-runtime-retention-governance`，登记 `wt_5642ffa8be9a`；平台/运行库均为本登记同名role的隔离数据库。GraphHarbor双包正式 `0.13.0.post48`，所属API/Worker已重启。未操作主工作区或现役数据。

## 验证计划

- GraphHarbor 双包独立 PostgreSQL/Redis：策略、并发、安全删除、故障重启、鉴权、CLI、发布四产物、PyPI 冷安装。
- Platform/Runtime/Web 最短相关单元测试、契约与静态检查。
- 专属栈 `wt_5642ffa8be9a`：主动查看/发送续期；后台读取不续期；到期/手动删除；Workspace 无额外七天等待；未结任务、远端失联与重启重试；迟到回调、去重/受理凭证。
- dry-run 只读、有限批次、并发维护与跨租户/环境保护。
- 新增迁移和停维护回退；不测试生产删除。

## Phase 验证记录

### P01 2026-10-30
用户人工批准方案边界。已核实锁定 GraphHarbor post45 的 TTL 扫描为空实现；仅配置官方 checkpointer.ttl 无法生效。现有 GraphHarbor 工作目录包含历史未提交改动，本次保留并建立源码基线摘要。

### P02 2026-10-30

- GraphHarbor G02–G07完成：源码392 passed/22 skipped、独立Cron3 passed、候选wheel23/sdist19 passed；正式四产物SHA256一致，无缓存冷安装与13项HTTP/CLI/恢复探针通过。
- Runtime `pyproject.toml`、`uv.lock` 锁定正式post48，经所属local-stack同步依赖并重启API/Worker/Platform API；真实三服务使用发布包通过。
- [引擎验证](/Users/lijiaxin/PyCharmMiscProject/graphharbor/docs/projects/20261030-thread-retention-lifecycle/verification.md) 保留完整命令与证据。旧post45不能接管014，未伪称可直接降旧版。

### P03 2026-10-30

- 平台ACL/fork/policy/title相关测试55 passed、3 skipped、22 subtests；两端JWT操作AST集合均38项且相等。
- API10文件初次147 passed、4 skipped、132 subtests、5 failed，失败均为fixture导入内部异常别名及契约例外分类遗漏。fixture改用公共 `runtime_service.errors.RuntimeAuthError`，OPERATIONS与原生例外分类加入两个retention操作；委托契约重跑5 passed、67 subtests、23.86秒，退出0。
- Web `useThreadActivity.spec.ts`、`ChatPage.spec.ts`、`DearAgentPage.spec.ts` 合计8 passed。`pnpm --dir apps/platform-web lint` 为0 errors/40 warnings；vue-tsc及build通过（1041 modules，23.55秒）。
- 新会话强制30天、后台不续期、主动查看/返回/发送续期、越权拒绝和存量登记不覆盖策略/活动，在P07真实栈及浏览器另验。

### P04 2026-10-30

- 生命周期最短 `tests/services/test_thread_lifecycle.py` 15 passed，覆盖本地文件占用、受控远端失联/恢复、可信路径和未结事项；远端不是实际离线节点。
- Runtime最终相关10文件命令（在`apps/runtime-service`运行，测试DSN仅注入下述变量）：

```bash
uv run pytest -q tests/runtime/test_platform_auth.py tests/runtime/test_resource_bindings.py tests/services/test_message_inbox_postgres.py tests/services/test_thread_lifecycle.py tests/services/test_resource_reconnect.py tests/test_terminal.py tests/test_terminal_http.py tests/test_thread_workspace_isolation.py tests/workspace/test_background_execution.py tests/workspace/test_remote_workspace_receipts.py
```

- 实际119 passed、11 skipped、5 warnings、50.31秒，退出0。只从所属`.local-stack/runtime.env`提取`DATABASE_URI`赋给`RUNTIME_MESSAGE_TEST_DSN`，从混合单测环境移除`DATABASE_URI`；不打印DSN。
- 前两次整体注入runtime.env：116 passed、11 skipped、3 failed，固定scope与不同tmp路径触发生产Workspace防错绑。临时terminal fixture修改已撤销，修正测试环境后通过；未绕过绑定校验。

### P05 2026-10-30

- completion/delegation/requests相关套件83 passed、1 skipped、110 subtests；真实PG completion35 passed，覆盖详情/去重窗口、充分终态请求清理、迟到回调、HMAC/ACL及并发互斥。
- PG命令入口：在`apps/platform-api`运行`uv run pytest -q tests/test_run_completion.py`，设置`RUN_COMPLETION_PG_TEST=1`及`RUN_COMPLETION_TEST_DATABASE_URL`为所属平台库，fixture仅使用独立schema并核验本地地址、wt_*_platform库及同名role。未用生产/主库。
- 既有pending/unknown/HITL、未清请求/origin/event配套保留，超窗口合法回调duplicate ack而不复活已删会话；未单凭created_at删除受理凭据。

### P06 2026-10-30

- Runtime维护/资源/inbox/terminal相关验证包含在P04的119 passed/11 skipped，未重复加总。默认report、limit/budget边界、owner存活、互斥及completed墓碑满24小时清终态行均覆盖。
- `uv run --project apps/platform-api pytest -q scripts/tests/test_local_stack_completion.py` 2 passed：所属回调密钥配对及跨环境拒绝。
- 一套`ai-agent-retention@.timer`映射platform/runtime两份service；账户aiplatform、路径`/opt/ai-agent-platform`，使用各app自己的`.env/.venv`。静态核验见Final；本机没有安装/运行Linux systemd。

### P07 2026-10-30

真实专属栈命令：

```bash
RUN_RETENTION_STACK_TEST=1 uv run --project apps/runtime-service pytest -q apps/runtime-service/tests/e2e/test_session_retention_stack.py
RUN_RETENTION_STACK_TEST=1 pnpm --dir apps/platform-web test:e2e e2e/session-retention.spec.ts --workers=1
```

- 三服务1 passed，13检查，57.41秒：存量登记预览只读/给足30天/保留已有策略活动、新会话覆盖客户端、后台不续期、查看续期、跨项目和未签名拒绝、手动与TTL删Workspace/ACL、CLI只读、文件占用阻塞重试、并发唯一任务、完成墓碑最小化。
- 浏览器1 passed，20.4秒：查看、KeepAlive返回、发送续期，后台读取不续期，真实模型回复成功。2次显式活动报告；证据`.local-stack/evidence/retention-browser.json`与`.png`。
- 三服务证据`.local-stack/evidence/retention-stack.json`，10轮维护耗时秒：3.047、3.460、3.168、3.039、8.211、3.016、9.084、3.457、8.765、2.892。这是隔离链路样本，不是生产容量压测。
- 正式包重启/hook重试/停维护保留任务/旧包拒绝/恢复匹配post48由GraphHarbor真实进程探针补充，不把fixture的远端恢复写成真实远端验收。

### P08 2026-10-30

- 任务卡、逐项Phase、实现记录、方案/功能/变更、发布/维护手册及CONTEXT已按当前范围对齐；Final另执行状态、链接、差异和产物核验。
- `delegation-jwt.md`更新38操作及两个精确retention例外、last_verified；原专项独立门禁尚未解除，继续draft。GraphHarbor REST契约既有active状态/日期同步，不将其他专项冒充本次验收完成。
- 不新增无关功能或写入lessons；经验沉淀建议随最终交付提出，用户确认后才落笔。未执行Git提交、推送、生产部署或既有业务数据销毁。

## Final 验证记录

### 2026-10-30 最终验收

前置状态核验通过后进入Final：8项任务勾选、8张完成卡、8条Phase与README/plan/CONTEXT均对齐“任务全部完成，待最终核验”。完整相关回归、真实集成及E2E已执行，Final复核其证据并独立检查发布产物、配置和文档；未把阶段记录当成新测试重复计数，未重复运行已通过的昂贵套件。

| 范围 | 实际结果 |
|---|---|
| Runtime相关完整回归 | 10文件119 passed/11 skipped/5 warnings/50.31秒；最短生命周期15 passed为重叠证据，不加总。环境误注入导致的初次3失败已按P04修正 |
| API相关回归与PG | completion/delegation/requests83 passed/1 skipped/110subtests；ACL/fork/policy/title55 passed/3 skipped/22subtests；真实PG completion35 passed。契约fixture/classification初次5失败修正后，委托5 passed/67subtests；不将这些重叠套件相加 |
| Web门禁 | 3文件8 passed；ESLint0 errors/40 warnings；vue-tsc与生产build通过，1041 modules/23.55秒 |
| 真实集成与E2E | 三服务1 passed/13检查/57.41秒；真实模型浏览器1 passed/5检查/20.4秒；读取/返回/发送、后台不续期、TTL/手动删除Workspace、占用重试、并发、安全边界均有实际证据，见P07 |
| 性能边界 | 10轮隔离维护2.892–9.084秒；验证有限批次/预算/互斥，未据此宣称生产容量 |
| 发布与恢复 | 正式post48四产物hash、60源码与wheel一致，平台实际安装双包同为post48；正式13项真实进程探针通过。旧post45拒绝接管014；停维护保留任务、恢复匹配post48续跑通过 |
| 最终Python门禁 | 本次39个新增/修改Python文件Ruff check通过；format初次37通过/2文件需格式化，仅格式化本次local-stack回调及其新测试，随后两文件check/format均通过。对应 `uv run --project apps/platform-api pytest -q scripts/tests/test_local_stack_completion.py` 再跑2 passed、1 subtest、0.15秒 |
| 安全契约与模板 | AST确认两端各38项operation且集合相等；ConfigParser断言timer小时/随机300秒/持久化，platform/runtime实例映射、aiplatform账户、各app `.env/.venv`、执行入口和120秒超时均正确。输出 `.local-stack/evidence/retention-final-static.json` |
| 运行栈 | `bash scripts/local-stack.sh status`：登记wt_5642ffa8be9a，Runtime API/Worker、Platform API/Web、Redis均running，runtime-ready/platform-api均yes；仅本环境 |
| 文档与差异 | 两仓 `git diff --check` 通过；本仓12份相关Markdown的新增本地链接/锚点无断链。广扫发现4条HEAD既有断链，未修改无关历史内容，详情 `.local-stack/evidence/retention-final-docs.json` |

### 状态一致性与标准检查

- [x] README、plan、tasks、verification与CONTEXT均为done，8/8任务、8张完成卡、8条Phase一致。
- [x] FEATURES、CHANGELOG、实现记录与逐表维护手册同步；平台主工作区保持只读，本分支仍为`feat/session-and-runtime-retention-governance`。
- [x] `delegation-jwt.md`的38项操作和精确retention例外已核对，last_verified为2026-10-30；原专项消息内部Run现役链路等门禁未解除，保持draft，不能因本项目done将整份标准毕业。
- [x] GraphHarbor REST标准保持active并同步本增量；经验建议随交付提出，等待用户确认才写lessons。

### 最终结论

**done**：本次已批准的平台业务策略、GraphHarbor通用TTL/可靠删除、Runtime资源与Workspace回收、关联数据保留维护、本地正式发布及专属栈验收均完成，无当前范围内未完成任务。

未执行Git提交/推送、生产部署、Linux systemd安装启停或生产容量压测。远端失联/恢复仅受控fixture；不宣称真实离线节点验收。旧post45不能接管014，已删除数据和文件不承诺可恢复；暂停平台timer本身不能关闭GraphHarbor Worker TTL。
