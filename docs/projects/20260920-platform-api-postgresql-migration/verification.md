# Platform API PostgreSQL 迁移专项 - 验证计划和记录

**最新结论：done（2026-09-20）。** 真实本地切换及本轮验收通过；早期规划/隔离阶段记录保留，最终边界和复测结论见文末。

## 验证原则

隔离测试使用专用库；用户于 2026-09-20 明确授权真实切换与验收后，本地业务库允许受控验收写入。记录代码版本、PG 版本、源快照摘要、脱敏目标、迁移 revision、命令、退出码和结果；秘密及原始业务备份不提交仓库。skip 不计通过，旧专项记录只作参考。

## 单元与质量检查

在 `apps/platform-api` 执行现有测试：

```bash
uv run --frozen python -m unittest discover -s tests -p 'test_*.py'
```

- [ ] `tests/test_iam_migration.py` 的基线与 metadata 一致性；SQLite 测试保留，不能替代 PG 集成。
- [ ] `tests/test_transaction_boundaries.py`、`tests/test_run_requests.py`、`tests/test_resource_lifecycle.py`：事务回滚、幂等与资源关闭。
- [ ] 拟新增 `tests/test_sqlite_to_postgres_migration.py`：布尔、JSON、NULL、时间偏移/无时区处理、外键关系、非空目标、错源/错目标、部分导入失败回滚及重复运行保护。
- [ ] 改动 Python 文件沿用仓库现行 lint/类型检查配置；Shell 使用 `bash -n` 检查，文档运行 `python3 scripts/check_docs.py`，变更运行 `git diff --check`（后两项在仓库根目录执行）。

## 真实 PostgreSQL 集成

- [ ] 空库 `alembic upgrade head` 两次成功，revision 正确，20 张业务表的字段、索引、约束与 metadata 一致。降级/再升级仅限可销毁的空白隔离库。
- [ ] 用当前模型构造覆盖全部表的 SQLite 数据，完成复制；逐表行数和归一摘要一致，外键与唯一约束无异常，`alembic_version` 保持 PG 迁移产生的值。
- [ ] 模拟中途插入失败，目标本次事务回滚，源库摘要不变；非空目标拒绝，无隐式清理。
- [ ] PG 不可达、密码错误、库不存在、权限不足、落后 revision 时启动给出准确且脱敏的错误；迁移失败不启动 API，不创建 SQLite 文件。
- [ ] 新卷和已有卷分别运行隔离 Compose 场景；应用实际连接预期 PG 库且重启后数据持久，不能只检查配置字符串。
- [ ] 迁移后普通用户/管理员登录刷新、token 撤销、服务账号项目授权、公告已读、项目策略和模型凭据解密保持一致。

## 端到端关键链路

复用 `apps/platform-api/tests/integration/test_runtime_graphharbor_http.py` 和 `scripts/platform_showcase_acceptance.py`，按 `apps/platform-api/docs/handbook/runbook.md` 配置专用环境；补浏览器验收，不把 mock 或健康探针视为业务完成。

| 场景 | 操作 | 验收点 |
|---|---|---|
| 身份与治理 | 浏览器登录、查看/编辑项目和 Agent、刷新 token、查看审计，重启 API 后重读 | 数据在控制面 PG，角色与租户隔离正确 |
| 历史数据 | 迁移后打开原项目、Agent、thread/run，验证历史请求 | ID、授权和关联不变；历史审计可读 |
| 执行与幂等 | Web → API → Runtime 创建对话、流式执行、工具调用；相同幂等键重试 | 原 Run 不重复执行，PG 请求/审计持久化，Runtime 执行事实正确 |
| 中断生命周期 | 触发审批、恢复、取消及已启用的分叉能力 | 授权与请求关联保持，不误重放旧任务 |
| 结果域 | 在启用 interaction-data-service 的隔离环境执行一条产物落库与查询链路 | 结果可查，控制面关联有效；未配置则明确记录未验 |

以上全部为待验证项，逐项留证；测试写入与正式业务开放时间分开记录。

## 安全、清理与性能

- [ ] 专用业务角色能完成所需操作，不能访问 Runtime 库业务表；日志、预览和验证报告不泄露连接密码/token/密钥。
- [ ] 清理脚本预览前后数据库与备份不变；未确认不执行；受控执行只影响批准的流水表，其他 18 张业务表和源库/备份摘要不变。
- [ ] 外键依赖、连接失败、拒绝执行时明确失败；不因 `CASCADE` 或测试库名前缀扩大删除范围；运行中的幂等数据不可清理。
- [ ] 复用 `scripts/platform_backend_closeout.py` 的混合负载思路，在相同数据和请求组合下对比 SQLite 与 PG，记录吞吐、P95、错误、连接峰值和审计落库数。
- **待评审性能门槛：** 建议至少 2 个 API worker、10 个并发客户端持续 5 分钟，平台 CRUD/审计/幂等混合负载；排除预期拒绝响应后非预期数据库错误为 0、重复执行为 0、业务写入无丢失，PG P95 不高于同环境基线 1.2 倍。目标是专项回归，不是生产容量认证；评审可按实际负载调整，调整必须留记录。

## 备份与恢复

- [ ] 在停写窗口生成可恢复 SQLite 备份，校验 WAL 数据没有遗漏；保存对应 Runtime/适用结果域快照及密钥依赖。
- [ ] 新写入开放前模拟验收失败，恢复旧配置和一致状态，验证登录、历史读取及执行关联。
- [ ] PG 开放写入后加入唯一测试记录再模拟故障，停止写入并备份 PG；验证流程拒绝直接回指旧 SQLite，PG 恢复到新库后该记录及关联仍存在。
- [ ] `pg_restore --exit-on-error` 恢复到新库，逐表校验、历史读回成功；Worker/Redis 待处理项复核后再恢复执行，不盲重放。
- [ ] 记录实测停写、迁移和恢复耗时，满足评审确定的窗口；备份保留期内清理脚本不得删除恢复材料。

## 验证记录

### 2026-09-20 规划阶段

- 已完成：ADR、数据库手册、依赖、迁移基线、测试入口、本地启动及清理脚本的静态核查。
- 未执行：源库数据盘点、进程现场确认、建库、数据导入、服务重启、业务/性能/恢复测试；当前仅建立专项。
- 文档检查结果：本次 6 份新增/更新文档通过 `scripts/check_docs.py` 的逐文件检查，专项相对链接目标全部存在；`git diff --check` 通过。全仓 `python3 scripts/check_docs.py` 退出码 1，发现 10 处既有本机绝对路径（原始 ADR 3 处、其他专项 7 处），本轮未修改这些文件。
- **结论：** 规划中，待人工评审；不作功能验收通过或迁移完成声明。

### 2026-09-20 实施验证

执行者：Codex。人工评审：用户已批准方案，见 README。测试环境：独立 Docker PostgreSQL 16 容器，宿主机回环端口 55439；独立 Platform API 容器端口 55440，使用专用非超级用户角色。未修改真实本地服务的数据库配置。

| 验证项 | 实际命令 / 操作 | 结果 |
|---|---|---|
| 迁移专项测试 | app 目录：设置专用 `PLATFORM_MIGRATION_TEST_URL` 后 `uv run --frozen python -m unittest discover -s tests -p 'test_sqlite_to_postgres_migration.py' -q` | 3 项通过，包括真实 PG 全表复制、失败回滚与非空目标保护 |
| 本地启动脚本 | 根目录：`python3 -m unittest discover -s scripts -p 'test_local_stack_backend.py' -v` | 4 项通过，包括迁移失败阻断、清理预览保留源库和备份 |
| 全量单元/契约回归 | app 目录：`PLATFORM_RUNTIME_INTEGRATION=0 uv run --frozen python -m unittest discover -s tests -p 'test_*.py' -q` | 198 项：192 通过、5 跳过、1 错误；不是全量通过 |
| 失败复跑 | app 目录：`uv run --frozen python -m unittest discover -s tests -p 'test_model_connection_lifecycle.py' -q` | 7 项：6 通过、1 同样错误 |
| 新库与角色 | 建库脚本 `--platform-only`，重复执行；特殊字符密码连接 | 成功，不覆盖已有角色；单引号、百分号、@、反斜线密码可用 |
| 容器构建/配置 | `docker build -t platform-api:postgresql-migration-check apps/platform-api`；三份 Compose 分别 `config --quiet` | 通过 |
| 真实 HTTP 与重启 | 独立 API：ready、POST /api/identity/session、POST /api/projects、GET /api/projects；重启容器再登录/列表读取 | 通过，项目 ID 保留，数据库就绪；首次/重复 Alembic 启动正常 |
| PG 恢复 | 在隔离容器内 pg_dump custom → 新库 pg_restore --exit-on-error --no-owner --no-acl | 通过，20 表归一摘要一致；仅证明控制面恢复，不代表跨库/队列恢复 |
| 代码质量 | Ruff 检查新增 Python、迁移配置和改动的脚本测试；compileall；Shell bash -n | 通过 |
| 文档质量 | `python3 scripts/check_docs.py`、`git diff --check` | 通过，原 10 处绝对路径已修复 |

源库只读盘点：20 张业务表和当前字段集一致，SQLite integrity 为 ok，foreign_key_check 无孤儿。盘点时 projects=108、agents=127、users=1、refresh_tokens=323，audit_logs/run_requests 均为 0；这是读取时点数据，正式停写前必须复核。

失败详情：`test_service_account_revoked_token_is_not_reusable` 在首次兑换时得到 `ForbiddenError: Project role missing`。对应测试、权限策略和 Catalog 业务实现本轮没有修改；独立复跑同样失败。本轮不放松鉴权来使测试变绿。

排障说明：合成数据测试最初缺 Numeric 分支，已补齐并重新通过；HTTP 验收最初误用不存在的项目详情 GET，改用现有列表契约后通过。重启过程中短暂未就绪不记为通过，最终重新登录和读取完成后才确认持久化。

**最终结论：partial。** 本轮请求的绝对路径修复及三部分正式规范已完成；迁移工具与隔离 PG/容器/恢复证据已交付。实际本地停写切换、真实历史授权/密钥验收、完整浏览器与结果域链路、全栈 Compose、2 worker/10 并发/5 分钟性能对比、跨服务恢复尚未完成。全量回归存在上述独立失败，不能合并为“全面验收通过”。

收尾：最新构建镜像内 `database.py check` 成功确认专用角色与 head。本轮创建的 `platform-api-pg-migration-check-20260920`、`platform-pg-migration-check-20260920` 已停止，容器数据和恢复文件保留；未清理现有业务库、备份或其他容器。


### 2026-09-20 真实切换与验收（最新记录）

用户明确授权立即真实切换。本轮已切换原本地服务至 PostgreSQL 17.11 的 `platform_api` 数据库及专用非超级用户角色。20 张业务表复制前后归一摘要一致，7 组模型密钥可解密，原 SQLite 及原配置保留。源 Runtime runs 为 0，不能声称验收读取了源库中不存在的历史 Run；以下历史来自切换后真实生成的新会话。

| 项目 | 结果及边界 |
|---|---|
| 全量回归 | 198 项，193 通过、5 环境门控 skip，570.130 秒；修复陈旧 executor 权限测试，未放松业务鉴权 |
| 真实 PG 集成 | 3 项全部通过，43.303 秒；覆盖全表类型、复制、事务失败回滚、非空目标拒绝、清理遇反向外键整体失败且保留数据 |
| 真实 Runtime HTTP | 显式配置网关集成环境后 5 项通过，4.206 秒；补跑原先其中 3 个门控 skip |
| Skills PG/HTTP | 原门控测试已尝试执行，服务未在测试启动轮询期限内 ready；尚未计通过 |
| 本地启动脚本 | 4 项通过，1.669 秒；迁移失败阻断与清理预览保全 |
| 浏览器管理页 | 16 路由 × 桌面/手机真实请求，无 5xx、无 pageerror；另 1 项 mock 四态 UI 检查通过，单独标注不作为真实后端证据 |
| 浏览器聊天 | 修复审批定位器及消息父检查点问题后 2 项全部通过，2.3 分钟；覆盖发送一次、草稿、刷新、审批恢复、编辑分支、旧历史保留及刷新分支 |
| 分支回归 | branching.test.ts 的 4 项通过，包含多个路由节点重复消息时选择首次出现前的检查点 |
| 工具与幂等 | 真实 workflow 调用 read_reference，工具结果存在；同 key 重试同 run，不同内容同 key 返回 409；5 个 history 检查点 |
| 角色及故障 | 独立角色非 superuser/createdb，不能读取 Runtime 表；错误密码/不存在的库/不可达/无 CONNECT 权限/未迁移库均退出 1，输出不含密码 |
| 本地认证边界 | Homebrew PG 本地 trust；错误密码验证使用隔离 PG16 的密码认证，不把本机随机密码配置视为已启用密码认证 |
| 双库恢复 | 停写后控制面 21 表（含 Alembic）及 Runtime 24 表 dump/restore 到两个新库，逐表计数和 SHA256 全相等；新项目和新 run 及 parent 关联保留 |
| 恢复 HTTP | 恢复副本及重启的原服务均真实登录并读回 success run、工具结果和 5 个 history；副本 jobs=0，不重放任务 |
| 恢复耗时 | 控制面 dump+restore+核对约 4.48 秒，Runtime 约 8.42 秒；完整停止/备份恢复/重启窗口 363.46 秒，含 Worker 停止等待与 Runtime 冷启动，不等同秒级回滚 |
| Redis/工作区 | 开始前 pending/running=0；保留原 Redis，没有恢复旧队列。配置的工作区根目录本次清单为 0 文件，不能据此宣称验证了有产物的工作区恢复 |
| 首轮性能 | 各 300 秒、2 worker/10 客户端；SQLite P95 870.21ms/21.96 req/s，PG 1065.31ms/19.54 req/s，比值 1.224 超 1.2；均 0 错误，PG 2864 项目全部持久化、5880 审计、连接峰值 12。并行 Docker 构建干扰，保留失败记录，按原门槛复测 |

私有材料：`apps/platform-api/.data/backups/20260919T174506Z-postgresql-cutover/`。脱敏证据放在本专项 evidence/。已有新写入，禁止将原配置文件直接覆盖回去并回指旧 SQLite；恢复必须使用当前 PG 快照。

排障留痕：恢复副本最初的 config 位于备份目录，GraphHarbor 阻止跨 base directory 的源码路径；改为 Runtime 根目录的临时配置后删除。第二次鉴权失败来自 dotenv 对委托密钥引用的求值顺序；副本显式复用原 Platform 委托密钥后，双端 HTTP 核验通过。均为演练启动配置问题，未修改业务数据或鉴权策略。


性能复测（镜像构建完成后，原门槛未变）：`scripts/platform_database_load.py --seconds 300`，全新空 PG 测试库和同一停写 SQLite 快照。SQLite 13515 请求、44.99 req/s、P95 318.53ms；PG 14166 请求、47.14 req/s、P95 291.18ms，P95 比值 **0.914 ≤ 1.2**。两组均 0 错误；PG 6908 个 HTTP 创建项目全量持久化、14168 条审计、连接峰值 12。真实幂等/取消另以功能调用验证，本负载不包含模型执行，不作为生产容量认证。首轮超标结果保留。

脱敏证据： [切换](evidence/cutover.json)、[双库恢复](evidence/recovery.json)、[恢复 HTTP](evidence/recovery-http.json)、[性能复测汇总](evidence/load-quiet-summary.json)、[SQLite 明细](evidence/load-quiet-sqlite.json)、[PG 明细](evidence/load-quiet-postgresql.json)。

切换后两次取消并重新提交均产生不同 run，终态 interrupted；[取消证据](evidence/cancel.json)。旧 SQLite 仅在副本中完成登录和项目读取，源备份摘要未变；不将此副本测试表述为真实环境已回退。

Skills PG/HTTP 复测：就绪等待改为 120 秒实际时钟上限后，2 项测试全部通过（50.753 秒），包含真实 HTTP CRUD、版本冲突、权限隔离与重启持久化。全量测试原先 5 个门控 skip 已分别在真实 PG、Runtime HTTP、Skills HTTP 专项中补跑，不再留未执行门控项；保留原全量命令的 193 pass / 5 skip 原始统计。


容器收尾：完整 Compose 的四服务及 PG/Redis 已在线验证，最终 `up -d --no-build` 退出 0。当前源码 Runtime 网关 info/创建线程成功；Web HTTP 200；结果域文档使用同一项目 ID 实际写入，API 与结果域重启后项目和文档内容均保留。[容器证据](evidence/compose.json)。初次缓存 Runtime 源码过旧导致 401，更新验收镜像为当前源码后通过；详细镜像来源见实施记录。容器启动完成前的连接重置、演练重启打断 Compose 的等待均保留日志，不记为成功。

结果域适用性：当前已注册 Runtime 源码没有 interaction-data-service 调用，所以验证结果域自身真实 HTTP/PG 持久化，不声称存在自动产物链路。工作区无文件、源服务账号/公告/Runtime runs 为空；没有虚构这些历史数据的恢复证据。真实写入后不允许直接恢复旧 SQLite 配置。

质量检查：改动 Python 的 Ruff、编译检查，分支/聊天文件 ESLint、全量前端 vue-tsc --noEmit、Shell 语法、两份全栈 Compose 配置校验、全仓文档检查及 diff 空白检查通过。除原 10 处绝对路径外，检查期间其他并行专项新出现的本机路径也改为仓库/参考源码相对标识。

**最终结论：done。** 本轮授权的真实本地 SQLite → PostgreSQL 切换与验收完成。198 项回归原统计为 193 pass / 5 skip；5 项已分别在真实 PG、网关 HTTP 和 Skills HTTP 中补跑通过。浏览器管理与聊天通过，性能复测 P95 比值 0.914，双库全表恢复一致且两端真实 HTTP 读回成功。生产环境发布、生产容量认证及不存在的结果域自动链路不在此结论内。

收尾只停止本轮隔离容器与专用浏览器会话，不删除数据库、卷或备份；真实本地 Runtime API/Worker、Platform API、Web 保持运行并连接 PG。未执行 Git 提交或推送。

## 2026-09-20 项目清理补充验收（done）

用户明确授权只保留 test；按现有软删除语义执行，未变更授权契约。
- 真实 PG 临时表测试 1 项通过：预览、非法 UUID、缺失/已删除保留对象拒绝、同名隔离、幂等及事务回滚。
- Runtime 测试项目异常退出清理回归 1 项通过；未重跑付费模型长链路，本次只调整测试资源回收。
- 真实 HTTP：两个项目 Graph 目录相同、Agent UUID 不同；执行后列表仅 test、原 4 个 Agent 未变、已删除项目访问拒绝。
- 实库核对：活动项目 98 → 1，已删除 21 → 118；171 个 Agent、119 个成员、4 个 Graph、7 个模型、23 条请求保留。
- 清理后重复 dry-run 待处理项目为 0；默认文件 dry-run、bash -n、Python Ruff、两页 ESLint 和 git diff --check 通过。
- pg_dump 最新备份已保存；事务回滚测试通过。本轮未额外做全库恢复，先前迁移恢复证据不冒充本次新快照恢复证据。
- 本地 runtime-api / runtime-worker / platform-api / platform-web 正常运行。
- 证据：[project-cleanup.json](evidence/project-cleanup.json)；范围及保留项见 [实施记录](implementation/03-project-cleanup.md)。

## 2026-09-20 历史数据清理补充

用户明确批准历史清理。实现见 [历史清理记录](implementation/04-history-cleanup.md)。
- PG 临时表回归 2 项通过；覆盖保护目标、有效令牌保留、运行中阻断、事务回滚。
- 本地停写后实际执行：127 失效令牌、23 请求、1033 审计、10 会话/23 运行及关联历史已清理；6 个完整名称指定的测试库删除。
- 控制面/Runtime 新备份分别恢复到隔离临时库，原有数据计数通过；恢复测试库已删除。
- 服务重启后真实 HTTP：仅 test 项目、4 个 Agent、空会话列表。四进程 running，Runtime/API ready。
- 二次 dry-run：失效令牌、请求、Runtime 历史均 0；5 条审计为启动和验收新产生记录，保留。
- Ruff、格式、bash -n、diff 检查通过。未重新执行模型推理/性能测试，本轮不改业务执行代码。

- Redis 历史流 875 个（151592 条消息）完整导出后清理，当前 Runtime 命名空间剩余历史流 0；54 个其他测试命名空间键保留，不做 FLUSHDB。
- 结论：done。用户批准范围执行及恢复验证完成。脱敏证据：[history-cleanup.json](evidence/history-cleanup.json)。
