# 平台权限治理实施记录

## 范围与批准

2026-09-22，按用户“可以开始实施了，把本次的需求按规划都开发完成”的批准实施。仅修改 platform-api / platform-web；未修改 Runtime、GraphHarbor 或结果服务，未执行历史数据删除、用户数据库迁移、Git 提交或发布。

## 固定角色与治理入口（B1、C1—C4、E1—E2）

- `apps/platform-api/src/platform_api/modules/iam/application/policies.py`：新增 `platform.model.read/write`、`project.runtime.execute`；`project.runtime.write` 仅项目管理员。身份 profile 返回后端计算的 `permissions`。
- `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py`：全局模型连接由平台角色管理，项目列表不显示连接地址/凭据状态；新增无项目的 `/api/runtime/platform-models`。目录刷新只接受平台刷新权限。
- `apps/platform-web/src/modules/runtime/pages/RuntimeModelsPage.vue` 与 `router/routes.ts`：复用组件提供 `/workspace/models` 平台入口，项目侧只选用模型和配置项目策略。
- `apps/platform-web/src/layouts/WorkspaceLayout.vue`：前台每 60 秒刷新身份和项目 access；激活、403 立即刷新；失败清除旧权限。放在 Layout 而非 TopContextBar，确保沉浸聊天也生效。写请求遇 403 不自动重试。
- `apps/platform-web/src/modules/users/pages/UserCreatePage.vue`：创建成功后独立可选绑定项目；绑定失败保留用户、清空密码，可单独重试。项目列表加载全部分页。
- `apps/platform-api/src/platform_api/modules/announcements/service.py`：更新核查源/目标授权，普通 PATCH 禁止变更归属；全局与项目管理列表分开。
- `apps/platform-api/src/platform_api/modules/service_accounts/service.py`：高权限账号保护同时覆盖编辑、停用、创建和撤销 token。
- `apps/platform-api/src/platform_api/modules/audit/{service.py,http_resolution.py}`：允许平台审计跨项目筛选；不记录原始 query，历史 metadata 输出使用白名单。

## Thread 授权事实源（F2）

`apps/platform-api/src/platform_api/modules/runtime_gateway/application/thread_access.py` 和 `infra/sqlalchemy/models.py` 新增平台 `thread_access` 表，维护 owner、项目、个人/项目共享动作、临时接管。迁移为 `apps/platform-api/migrations/versions/20260922_0003_thread_access.py`，尚未对用户数据库执行。

上游 `Threads.patch` 使用读取后合并 metadata，没有 ACL 的 CAS/行锁保障。将可变授权存在该 metadata 中，会有撤销后被并发旧写恢复的风险。因此 ACL 保存在 Platform DB，事务内锁定记录后更新并写审计；Runtime 仅保留普通项目、graph、标题和执行模式，不接收业务共享/接管数据。

`RuntimeGatewayService` 的改动：

- `_load_thread()` 先核查平台 ACL，再读取上游；read/comment/edit/share/delete/approve/terminal/full_access 分开。管理者默认无私人内容读取资格。
- `create_thread()` 服务端生成新 ID，禁止客户端复用已有 ID；剥离 owner、share、sandbox/workspace 等输入。`fork_thread()` 复用新建链路，新对象属于当前创建者。
- `search_threads()/count_threads()` 用平台授权 ID 集合查询上游，每批最多 100 个，统一过滤后排序、分页、计数。复杂度为项目 ACL 扫描＋可见历史读取，不能当作大规模性能已验收；需要压测证据。
- 标题/preview/执行模式 PATCH 只写改变的字段，不把合并后的平台 ACL 回写上游。
- `PUT /threads/{id}/shares` 支持个人或项目共享、撤销；项目共享只授予 read/comment/edit；普通成员不可获得 delete/approve。委托共享不可超过自己的动作集合。
- `POST /threads/{id}/takeover` 要求管理员身份、分类、至少 10 字原因、工单和 1—60 分钟期限（默认 15）。接管只增加 read；读取前同步审计；过期自动拒绝。
- 模型引用带平台签名的 Thread ID/动作；兑换和排队消息消费重新加载当前主体、项目权限及 Thread ACL，防止旧引用绕过撤销。
- 前端 Chat/Dear Agent 开始消费 `allowed_actions`，逐步拆开删除、编辑、发送、审批和 full_access；界面闭环仍在验证。

## Skills / 记忆真实边界（B2）

只读核对 `apps/runtime-service/src/runtime_service/http/dear_skills.py`、`http/dear_governance.py` 及 `services/dearflow_agent/memory.py`：现有自定义 Skills、个人记忆实际按 `(tenant_id, project_id, user_id)` 隔离，由已签名主体确定 user_id。平台入口允许有执行权限的用户管理自己的内容，不再误用仅管理员具有的项目策略写权限。

当前上游没有项目共享记忆的读写/召回契约；不得伪造一个 user_id 代表项目，也不能以 Thread 共享冒充共享记忆。该存储/召回能力仍由记忆专项承接，本专项只修平台入口；当前项目共享记忆不能标为完成。

## Phase 验证证据（非 Final）

- F2 开始前：后端 `uv run python -m unittest discover -s tests`，222 项，OK，8 项 skipped；前端 295 passed / 1 skipped，typecheck/build 通过。该结果不代表随后 ACL 修改已经全量通过。
- F1：`RUN_LOCAL_GOVERNANCE_CONTRACT=1 uv run python -m unittest tests.integration.test_thread_metadata_filter`，真实本机上游 1 项通过；仅创建并删除本测试两个 Thread。
- F2 首轮回归暴露旧 fixture 缺 ACL 及新增路由 inventory 未同步；不放松生产鉴权，改用隔离 SQLite 测试库建立真实 ACL。
- F2 定向 43 项通过：`tests.test_thread_acl`、`tests.test_thread_access_policy`、`tests.test_model_connection_lifecycle`、`tests.test_runtime_gateway_http_matrix`、files/images/workspace、normalization、metadata。日志 `/tmp/governance-f2-targeted.log`。
- F2 分叉/运行/ACL 32 项通过：`tests.test_thread_fork tests.test_run_requests tests.test_thread_acl`。日志 `/tmp/governance-fork-run.log`。
- 最新前端 ACL 改动仍在修复测试 fixture；最终前后端回归、迁移回滚、多身份浏览器 E2E、旧数据清理尚未完成。

任务完成度以各编号章节为准；以上测试是阶段证据，不是整体交付结论。

## 2026-09-22 续实施：接管、撤销与真实上游链路

- `thread_access.allowed()`：限时接管的 read 在项目共享分支之前判断，无项目平台管理员可按接管授权读取；结束授权后立即拒绝。接管不补项目成员、不增加 comment/terminal/full_access。
- `RuntimeGatewayService._load_thread()`：无项目管理员读取项目共享对象时同样记录接管读取审计。`create_thread()`：ACL 注册失败则删除本次新建上游对象；补偿失败记录对象 ID 和异常，原失败继续上抛，不返回可用对象。
- `ThreadAccessControl.vue`：已离开项目的旧共享目标仍可选中撤销，禁止重新授予；共享数据读取失败时禁止保存旧值；提交时重查当前组件动作资格。
- 两套 `use*Session.ts`：持续前台每 60 秒、激活、403、共享/接管更新事件刷新对象权限；合并同时到达的刷新，避免刷新自身 403 递归。失权断流、清空消息回执/待发送缓存、停止回执请求；两套 Session 组件隐藏正文和工作区，显示可见解释及重新检查按钮。原请求重试按 resume→approve、send/fork→comment 检查。
- `tests/test_thread_acl.py` 增加项目共享对象接管/结束、跨项目拒绝、不同管理员不能结束他人的接管、新建失败补偿，以及可选真实 Runtime 联调。

阶段证据：

1. `uv run python -m unittest tests.test_thread_acl tests.test_thread_fork tests.test_runtime_gateway_http_matrix`：12 项通过（新增真实联调用例之前）。
2. `RUN_LOCAL_GOVERNANCE_CONTRACT=1 uv run python -m unittest tests.test_thread_acl`：修正夹具后 9 项通过，包含真实 Platform ACL → 网关 → Runtime/GraphHarbor 的私有列表、count、共享、撤销；日志 `/tmp/governance-acl-real-2.log`。没有调用模型执行。
3. 真实联调首轮失败不能隐去：测试库的非 UUID `private` 夹具被传入真实 search，修正为先移除该合成测试记录；首次清理时上游 checkpoint 数据库连接断开导致 HTTP 500。再次运行正常；遗留测试 Thread `2ccf8a35-ab75-40ef-908c-6666a880348e` 已单独通过 Runtime API 删除，并确认测试项目无剩余 Thread。未改 Runtime 代码，未删除历史业务数据。
4. 前端共享组件、Chat 会话和两套页面定向 16 项通过，日志 `/tmp/governance-refresh-pages.log`；类型检查通过。随后增加 Dear Agent 同等撤销测试，结果以 03 最新记录为准。
5. 前序全量 API 228 项、8 skipped 及隔离迁移 2 项通过属于 Phase 证据；不覆盖之后所有增量，不作为 Final。迁移测试只用临时 SQLite 与 PostgreSQL 临时 schema，不是业务库迁移完成。

仍需解决：真实浏览器多身份/移动端、存量清理及整体 Final 未完成。项目共享记忆无既有上游存储/召回契约，仍按记忆专项边界标注。独立对象治理入口见下节最新实施。

## 2026-09-22 续实施：无项目运维目录同步

- `RuntimeCatalogService.refresh_tools()/refresh_graphs()` 改用平台目录刷新权限；仍校验指定项目存在，签名用真实平台角色和既有 read scope，不伪造项目角色。普通项目执行者不能刷新；平台运维不能借此创建 Thread。项目 schema/普通读取保留项目成员检查。
- `ControlPlanePage.vue` 复用工作区已有的项目治理列表作为同步表单选项，明确选择现有项目，不修改当前业务工作区。复用 `refreshRuntimeGraphs/refreshRuntimeTools` 服务。无项目成员关系的运维可以操作；平台只读者不展示动作；平台完全没有项目时提示联系管理员创建。
- 当前 Runtime 协议仍要求 project scope 和模型策略，因此保留现有项目作为协议范围；这不是自动加入项目或授权业务执行。新页面仅是共享目录同步，不是 Agent 健康拨测。
- `uv run python -m unittest tests.test_thread_acl.ThreadAclTest.test_operator_catalog_refresh_does_not_grant_project_execution tests.test_runtime_catalog_delegation`：14 项通过，日志 `/tmp/governance-catalog-scope.log`。真实平台临时 DB/IAM，验证签名平台角色、空执行 permissions、目录刷新与 Thread 创建拒绝；上游响应为测试替身，不能声称本组做了真实 Runtime 目录同步。
- `pnpm exec vitest run src/modules/control-plane/pages/ControlPlanePage.spec.ts`：2 项通过，日志 `/tmp/governance-catalog-ui.log`。对象刷新/共享最后一轮 12 项通过，日志 `/tmp/governance-refresh-final-phase.log`。`vue-tsc --noEmit` 通过；新共享组件、两套 Session 模板和控制面模板 lint 格式修正后无输出、退出成功。

## 2026-09-22 续实施：独立会话治理入口

- 新增 `ThreadGovernancePage.vue`，复用 `ThreadAccessControl`、`MessageContent` 和 `ApprovalPanel`。平台入口 `/workspace/thread-governance` 只要求 `platform.super_admin.manage`；项目入口 `/workspace/projects/:projectId/thread-governance` 要求项目治理权限，导航沿用路由权限裁剪。
- 使用工单中的项目/Thread ID 定位，不提供默认跨项目私有列表。无项目平台管理员可明确申请限时接管、读取、审批、结束接管和确认删除，无须进入业务聊天页，也不增加项目成员身份。
- 删除不依赖读取正文，必须二次确认。审批通过 `session.service.resume()` 调既有 `/threads/{id}/runs` resume 分支，只传审批决策，不允许覆盖模型/input/config；提交前重新比对每项审批的指纹。
- 60 秒/激活/拒绝时刷新，失败清空内容；目标变化和授权更新递增 epoch，旧响应不能恢复已撤销的私有内容。接管开始/结束仍使用现有审计接口。
- 首轮 `ThreadGovernancePage` + session service + routes + guards：17 项通过，日志 `/tmp/governance-admin-tests.log`。随后治理页 4 项通过（含审批内容变化拒绝），日志 `/tmp/governance-admin-page-final.log`；类型检查首次发现 `ChatCheckpoint` 缺 interrupts，已复用实际 `state()` 返回类型修正，Vite 的 TypeScript/vue-tsc 检查均为 0 errors。
- 两套会话增加授权变更 epoch，旧读取响应不能恢复撤销前的权限；连续刷新和迟到响应定向 12 项通过，日志 `/tmp/governance-session-epoch-2.log`。

## 2026-09-22 真实浏览器 Phase 验证

新增 `apps/platform-api/tests/fixtures/governance_server.py`：显式 `RUN_LOCAL_GOVERNANCE_E2E=1` 开启，API 仅监听本机 12142，Platform 使用临时 SQLite 和独立 JWT 密钥；真实 Runtime 仍为现有本机服务。创建专用 owner/peer/manager/superadmin/operator/viewer 身份、项目；退出清理该测试项目的 Thread。测试不使用业务账号密码、不调用模型、不修改 Runtime 代码。

新增 `apps/platform-web/e2e/platform-access-governance.spec.ts`：独立 Vite 13000 代理到 12142。复现命令：

```bash
# platform-api 目录
RUN_LOCAL_GOVERNANCE_E2E=1 uv run python tests/fixtures/governance_server.py
# platform-web 目录，另一个终端
VITE_DEV_PORT=13000 VITE_DEV_PROXY_TARGET=http://127.0.0.1:12142 pnpm exec vite --host 127.0.0.1
# platform-web 目录，另一个终端
RUN_LOCAL_GOVERNANCE_E2E=1 PLAYWRIGHT_HTML_OPEN=never PLAYWRIGHT_BASE_URL=http://127.0.0.1:13000 pnpm exec playwright test e2e/platform-access-governance.spec.ts --workers=1 --reporter=line
```

最终本组结果：**2 passed，42.6 秒**，日志 `/tmp/governance-browser-4.log`，截图 `/tmp/governance-admin-desktop.png`、`/tmp/governance-operator-mobile.png`。

- 真实 HTTP 身份与网关：owner 创建；peer 默认拒绝、read 共享后可读但不可编辑、撤销后立即拒绝；无项目 superadmin 默认不可读。
- 桌面浏览器：超级管理员从独立治理入口定位 Thread；原因/工单申请接管；可见会话标题；立即结束后标题清除并且 API 拒绝；无需读取即可二次确认删除。
- 390×844 移动浏览器：运维登录落治理页；无需项目成员身份同步真实上游 Graph 目录（本机返回 4 项）；私有会话治理 URL 被拒绝，创建 Thread API 返回 403。页面说明可见，不依赖 tooltip。
- 首轮环境缺当前版本 Chromium，下载后继续；第二轮定位器误用占位文案而非无障碍名称，修正；第三轮跨页导航等待不足，采用与登录相同 30 秒等待。失败均保留日志，不计通过。
- 测试 API/Vite 已停止；查询确认测试项目剩余 Thread 为 0，临时 Platform DB 已随服务退出清理。没有清理历史业务 Thread。
- 同轮 `RUN_LOCAL_GOVERNANCE_CONTRACT=1 uv run python -m unittest tests.test_thread_acl tests.test_thread_acl_migration`：12 项通过，包含真实上游私有 ACL 与临时 PostgreSQL schema 升降级，日志 `/tmp/governance-acl-phase-final.log`。

以上为 Phase 链路证据，不替代完整身份矩阵、真实审批执行、性能、历史清理和整体 Final。

## 2026-09-22 续实施：开户链路与 ACL 性能

- 隔离浏览器 fixture 新增显式拥有项目 admin 的 provisioner；保留无项目 superadmin 身份，避免测试悄悄扩大超级管理员业务权限。
- `platform-access-governance.spec.ts` 新增开户→无成员身份执行 403→注入一次绑定 503→真实绑定重试→原令牌新请求可创建 Thread→删除测试 Thread。1 passed，59.0 秒，`/tmp/governance-onboarding.log`；密码输入在创建完成后移除。绑定失败为网络故障注入，创建、重试和授权检查均走真实 API。
- `e2e/support/platform.ts` 的超级管理员测试模型读取改为 `/api/runtime/platform-models`，项目可选模型接口不再暴露 credential_configured。
- `thread_access.visible_records()` 原先载入项目全部 ACL；1 万条隔离 SQLite 记录、10 次过滤中位 3513.57 ms、最大 5019.37 ms（`/tmp/governance-acl-benchmark.log`）。现下推 owner/项目共享/当前用户 share/takeover 候选谓词到 SQL，仍由 `allowed()` 检查成员身份、具体动作和到期。
- 同样 10001 条 ACL、1000 条可见记录，改后中位 389.93 ms、最大 692.54 ms；`RUN_LOCAL_GOVERNANCE_CONTRACT=1 RUN_GOVERNANCE_BENCHMARK=1 uv run python -m unittest tests.test_thread_acl` 共 12 项通过（`/tmp/governance-acl-filter-sql.log`），包含真实 PostgreSQL 临时 schema 的 JSON 候选查询、过期接管拒绝和真实 Runtime 共享撤销。基准不含上游 HTTP 批量查询，也不是生产 SLO；本机有其他负载。项目 JSON 扫描与上游批量请求仍是已知上限。
- `AnnouncementsPage.vue` 修正编辑归属不可变的前端禁用条件：锁定编辑表单范围，而不是锁定列表筛选项目；后端不可迁移检查继续生效。
- 质量检查：`pnpm build`（含 vue-tsc）通过，`/tmp/governance-build-current.log`；`pnpm lint` 为 0 errors、670 warnings，`/tmp/governance-lint-current.log`。这是阶段检查，不能标为完整 Final。
- 数据只读盘点：平台库 revision 为 `20260920_0002`；project_members 125 个 admin、1 个 executor；service account project grants 为 0。按已批准 D03，executor 的语义变为执行者，不能把存量数量忽略。Runtime 的 runtime_events 约 3115 MB，解释了全库备份耗时；备份未完成恢复验证前不删除历史数据。

## 2026-09-22 续验收：公告、账号、共享与角色

- 公告浏览器 `--grep "announcement editing"`：1 passed（21.0 秒），日志 `/tmp/governance-announcement-browser-2.log`。首轮 fixture 未提供正文，被前端正确拒绝；补完整测试输入后通过。验证全局列表不含项目内容、普通编辑不能更换归属、运维跨项目写入 API 403。
- 高权限账号浏览器 `--grep "high-privilege"`：1 passed（18.3 秒），`/tmp/governance-sa-browser-2.log`。首轮暴露列表/详情 EmptyState 的发 Token 入口仍可点击，虽然函数及 API 会拒绝；现两个空态均复用 `canManageAccount()` 控制入口，不增加另一套权限判断。
- E1/E2 五个后端模块合计 22 项通过（62.865 秒），`/tmp/governance-boundaries-phase.log`。
- 私有 Thread 子资源真实 HTTP 链路：1 passed（18.0 秒），`/tmp/governance-child-browser.log`。同项目 peer 无法读取 state/runs/messages/capabilities/工作区/文件/图片/记忆或打开 SSE；授予 read/comment/edit 后能读，但 full_access、终端创建与删除仍 403。
- SA 项目共享真实链路发现：账号名称作为委托 subject 时，合法显示名含空格会被现有 Runtime 身份规范拒绝（401）。根因在平台主体映射，修改 `ServiceAccountsService.authenticate_api_key()` 和 `RuntimeCatalogService` 的引用兑换主体重建为 `service-account:{account.id}`；不借用自然人 ID、不改 Runtime、不引入个人密钥 ACL。审计 `actor_subject` 也随之使用稳定 ID，展示名称仍从服务账号资料读取。
- 修复后 `tests.test_service_account_project_grants tests.test_model_connection_lifecycle` 共 12 项通过（34.559 秒），`/tmp/governance-sa-subject.log`。浏览器工具真实 API 验证“无 grant 拒绝→有 grant 但私有拒绝→项目共享允许→移除 grant 即时拒绝→撤 Token 401”，另覆盖平台 viewer 全局模型只读，两项 **2 passed（26.0 秒）**，`/tmp/governance-subject-browser.log`。
- 项目 editor 的浏览器直接治理 URL 拒绝、execute 权限存在而 runtime.write 不存在、安全策略写入 403、私有 Thread 创建/删除通过；该轮合计 1 passed/1 failed（失败的 viewer 标题定位已在后一轮修正），不能把整轮记录成全通过，日志 `/tmp/governance-role-browser.log`。
- 两库全备份完成：`apps/platform-api/.data/backups/20260921T190322Z-p1-governance/`；Runtime dump 约 2043 MB，Platform dump 约 331 KB。原始 `manifest.json` 固定 13 个旧 Thread ID、更新时间和历史表计数。恢复校验仅针对新建 `platform_migration_test_governance_*` 临时数据库，恢复日志 `/tmp/governance-restore.log`；校验完成前仍不清历史或迁移业务库。

## 2026-09-22 数据落地与恢复结果

- Runtime 全库恢复成功：13 个 Thread ID 和 11 张历史表计数与备份清单一致。首轮随后因平台账号无 CREATEDB 权限停止，未放宽账号权限；改由同机维护账号创建以平台账号为 owner 的独立临时库。Platform 恢复后 0002→0003→0002→0003 成功，原 20 表计数不变，临时库均已删除。`restoration.json` 为 `restoration_verified: true`；日志 `/tmp/governance-restore-2.log`。
- 先只读预览，确认 13 个旧 ID/updated_at 未变且没有新 ACL 保护；停止本仓库 Platform API、Runtime API/Worker。清理在一个数据库事务中锁定历史表及 crons，重新拒绝活跃运行/定时任务/外部任务，按固定 ID 删除，不用 TRUNCATE/CASCADE。
- 删除结果：threads 13、runs 35、runtime_events 26938、runtime_message_inbox 1、checkpoint_writes 1126、checkpoint_blobs 232、checkpoints 639；其余关联历史表 0。2026-09-22 03:43（北京时间）提交。`cleanup-preview.json`、`cleanup.json` 与维护脚本副本保存于上述备份目录。业务审计、项目、账号、模型等平台表保留；沙箱磁盘目录未擦除。
- 主平台库 `database.py upgrade` 升级到 `20260922_0003`。随后恢复 Runtime API、Worker、Platform API；前端保持原进程。`local-stack.sh status` 四个服务 running，Runtime ready / Platform health 为 yes。
- 真实 PostgreSQL 持久化：使用已有管理账号的项目新建一个专用私有 Thread，确认 owner/full_access；重启 Platform API 后同一会话 owner/visibility 保留，随后删除该测试 Thread。日志 `/tmp/governance-persistence-create.log`、`/tmp/governance-persistence-restart.log`、`/tmp/governance-persistence-verify.log`。
- 回滚界限：恢复是到独立临时库，不覆盖业务库；以后若回滚线上组合，必须先停业务入口并配套数据/代码恢复。单独 downgrade 删除 ACL 再启旧共享逻辑会破坏私有边界，不属于安全回滚。
- 专项 Playwright 9 项合并运行 **9 passed（1.3 分钟）**，`/tmp/governance-phase-suite.log`；不将其称为完整 Final。
- 管理员审批最短契约链：真实 IAM/ACL/请求账本 + Runtime 替身，owner 首次 Run、peer 审批拒绝、无项目超级管理员审批仅返回 thread_id/run_id，仍不能读私有正文；1 passed，`/tmp/governance-approval-contract.log`。不冒充真实模型审批运行。
- 只读核对既有 Runtime 隔离契约后，执行原有 `test_thread_workspace_isolation.py` / `test_scoped_and_refs.py`：**6 passed、5 warnings**，`/tmp/governance-existing-workspace-contract.log`。本轮 Runtime 代码零修改。

## 2026-09-22 验收补齐与回归修复

### 最终收口（同日，取代下文历史阻塞状态）

用户批准恢复 audience 后，本机配置/示例已恢复，Runtime API/Worker 单独重启前增加既有配置预检；真实审批 1 passed（48.922 秒），日志 `/tmp/governance-real-model-approval-3.log`。Runtime/GraphHarbor 业务逻辑未修改。

独立 Final：API 239 项中 226 passed / 13 skipped（654.427 秒）；Web 307 passed / 1 skipped（255.47 秒）；类型检查通过。专项浏览器首轮 9 passed / 1 failed，双标签用例在撤权前页面加载超过 5 秒，采用其他页面已有的 30 秒等待后定向 1 passed（24.0 秒）。完整原始结果及跳过项/工具链无关失败保留在 07，不改写为首轮全绿。隔离 fixture/Vite 已停止，原四服务 running、ready/health yes；测试对象已清理，无重复历史删除/迁移，无 Git 提交。

用户明确 D07 仅项目内个人记忆；共享/跨项目记忆 deferred，不再作为本期依赖。项目按此已批准范围标记 done，所有章节和 CONTEXT/FEATURES 同步；共享记忆、其他记忆专项待评审优化与生产部署均未冒充交付。

- `WorkspaceLayout.vue` 原先只有 visibility/timer/403 刷新，补齐 `window.focus` 注册与卸载；双标签先等聊天页面实际加载，再撤项目成员并逐页激活。浏览器 **1 passed（26.5 秒）**，`/tmp/governance-tabs-browser-3.log`；对应组件单测通过。
- 最新前端联合回归 **83 文件、307 passed / 1 skipped**，224.64 秒；最新 typecheck 退出码 0。日志 `/tmp/governance-implemented-web-regression.log`、`/tmp/governance-latest-types.log`。跳过项不计通过，Phase 联合回归不改写成 Final。
- `tests/test_thread_acl.py` 的真实上游测试增加显式性能开关：创建 201 条 owner 可见 Thread 和 1 条 peer 私有 Thread，验证跨三个 100-ID 批次的分页/计数及 peer 隔离。五轮 list+count 中位 **371.66 ms**、最大 **462.55 ms**，每轮含六次真实 Runtime HTTP 请求，低于本机 5 秒验收预算。1 项通过、总耗时 44.060 秒，finally 删除本次全部 202 个 Thread。日志 `/tmp/governance-runtime-list-benchmark.log`。这不是生产容量 SLA；可见 Thread 越多仍线性增长。
- 后端全量初次 **238 项：224 passed、2 failed、12 skipped**，437.868 秒。两个失败为 `test_runtime_gateway_workspace` 的临时 Runtime 就绪超时，尚未进入业务断言。单独复现同样失败；导入诊断显示 30 秒时仍在 Anthropic/Pydantic SDK 初始化，随后正常完成，无运行时异常。平台测试改用单调时钟 120 秒启动上限，保留提前发现子进程退出、附带失败日志；不修改 Runtime 源码。原始失败日志 `/tmp/governance-implemented-api-regression.log`、`/tmp/governance-workspace-failure-check.log`，修复验证 `/tmp/governance-workspace-recovery.log`。
- 记忆范围复核：README 原已明确存储、作用域、召回归个人记忆专项，本期只负责平台入口与主体授权。项目共享记忆尚未实现；此前向用户提出的本期扩围问题没有收到确认，不解释为获准改 Runtime，也不把共享存储记成已交付。
- 工作区修复验证：`uv run python -m unittest -v tests.test_runtime_gateway_workspace` **4 passed（250.244 秒）**，包括真实本地 HTTP、文件、终端、Runtime 重启后持久化；`/tmp/governance-workspace-recovery.log`。这是失败项定向复测，不改写初次全量结果。
- 新增 opt-in `tests/integration/test_governance_model_approval.py`，目标为本机真实平台登录→专用私有 Thread→workflow_demo 中断→审批→模型完成；仅发送合成文本，finally 清理专用 Thread。两次均在创建 Run 时返回 500，未触达模型。实际 Runtime 栈为 `langhost/core_api.py → langgraph_runtime_pg/auth.py:sign_runtime_context()`，报 issuer/audience 必须成对；只读检查确认本机 `.env` issuer 存在、audience 缺失（未输出秘密）。日志 `/tmp/governance-real-model-approval.log`、`/tmp/governance-real-model-approval-2.log`。不改 Runtime 代码/启动环境，不以替身审批测试覆盖该失败。
- 收尾 `local-stack.sh status`：原四个服务均 running，Runtime ready 与 Platform health 为 yes；健康检查成功不能替代 Run 创建验收。Runtime/interaction-data-service 工作树无本轮改动，`git diff --check` 通过。未重复执行历史清理/迁移，未提交代码。
