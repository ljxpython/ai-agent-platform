# 07 实施顺序、任务总表与验收

## 目标

把前六章的讨论拆成可执行阶段，区分确定改动、矩阵和条件性工程。本文只记录真实验证结果；实施 Task 的 Phase 已完成，当前进入独立 Final 验证。

## 方案设计

### 7.1 推荐阶段

```text
Phase 0 方案评审与数据盘点
    ↓
Phase 1 固定角色 / 资源归属 / 平台后端边界
    ↓
Phase 2 运行执行与治理权限拆分
    ↓
Phase 3 前端菜单、页面动作、缓存和失权行为
    ↓
Phase 4 公告、账号、审计和高风险对象收口
    ↓
Phase 5 多身份真实链路、安全回归、回滚演练
    ↓
条件分支：个人对话隔离（自定义角色本期 deferred，另立项目）
```

Phase 1—4 不能随意并行：资源归属决定权限，权限契约决定前端。可先做 E1 公告漏洞复现/修复，但要避免与矩阵冲突。

### 7.2 估算

| 范围 | 估算 | 说明 |
|---|---:|---|
| 基线固定角色治理（02—04、03 前端、测试） | 16–25 人天 | 吸收权限透明化、开户交接和回归保护；不做自定义角色、不改 Runtime Server；个人隔离只落地已证实的平台可行部分 |
| 个人隔离 P1 | +5–10 人天起 | 取决于上游过滤、Thread owner/share ACL；证据不足时标记 blocked/deferred；旧 Thread 清理不计入 ACL 研发人天，单独做数据操作记录 |
| 自定义角色 | 0 人天（本期） | 已确认 deferred；未来另立项目，不纳入本期排期 |
| 采用项目 BYOK 模型连接 | +8–15 人天 | 资源归属、迁移、凭据、去重和页面重构 |

推荐先按约 16–25 人天排期，两个条件分支不计入基线承诺。多人并行只能减少等待，不能跳过 Phase 0 的矩阵冻结。

### 7.3 分阶段发布与回滚

- 先增加权限读取契约与测试基线；确定的授权漏洞修复不以观测期为理由延后。
- 推荐平台前后端协调发布新权限。若需要兼容窗口，必须列出等价映射，不能把 executor 的旧只读身份自动映射成可执行，也不能保留已确认越权路径。
- 角色或权限数据变更必须有存量映射、备份、失败停止和恢复步骤。
- 前端新权限字段缺失时采取安全空态/只读，不能默认全开。
- 回滚代码后，数据库权限/绑定是否向前兼容必须演练；不能只回滚前端。

不修改 Runtime Server 的前提下，回滚需明确撤销哪些新规则；不得恢复已接受的越权缺口或重用过期委托快照。已执行的 Run、已下载内容和已写入审计不会被“回滚”删除。

## 任务导航（不维护第二份进度）

| 交付模块 | 唯一任务位置 | 前置与发布关系 |
|---|---|---|
| 需求基线 | [01 A1](01-current-state-and-reference.md#任务拆分) | 冻结角色/动作/资源/范围 |
| 权限与资源 | [02 B1/B2](02-roles-resources-and-actions.md#任务拆分) | A1；与 C1/C2 同一发布单元 |
| 前端契约/刷新与权限体验 | [03 C1/C2/C3/C4](03-frontend-and-access-contract.md#任务拆分) | B1/B2；不能单独放开运行；C3/C4 吸收复盘中的权限透明化和开户交接 |
| 公告/账号/审计 | [04 E1/E2](04-governance-boundaries.md#任务拆分) | 可在现有 IAM 下先行；后续与新矩阵回归 |
| 个人隔离 | [05 F1/F2](05-personal-conversation-isolation.md#任务拆分) | 先确认产品模型和平台可行性，再安排实现 |
| 自定义角色 | [06 G1/G2](06-custom-roles-and-delegation.md#任务拆分) | 真实岗位需求与委托模型批准后才实施 |

基线人天进一步分解：评审/盘点 2–3，后端授权 4–6，前端契约/页面与权限透明化 5–7，集成/E2E/安全/回滚 4–6，文档交接 1–2，合计约 16–25。含常规修正，不含审批等待、未发现的大型数据质量问题。一个熟悉项目的全栈开发约 3–5 周；完成角色与数据隐私决策后重新估算。

个人私有但无共享的版本预计更接近增量下限；包含共享编辑、管理员 takeover 时应按 10–18 人天重新评估，不能沿用“只加 owner 过滤”的估算。旧 Thread 清理是一次性数据操作，须在评审后给出删除范围、备份和回滚边界。各附加范围存在共用工作，最终总量不应机械相加。

## 任务拆分

### Task H1：发布范围、迁移与人工评审
- **改动内容：** 整理 D01—D36 的确认/待定/本期不做状态；盘点存量 executor、全局模型使用与服务账号 grant；确定上线组合与数据备份回滚。
- **代码位置：** 本目录各章节决策表与 `README.md`；`apps/platform-api/src/platform_api/modules/projects/models.py`、`apps/platform-api/src/platform_api/modules/service_accounts/models.py`、`apps/platform-api/src/platform_api/modules/runtime_catalog/infra/sqlalchemy/models.py`；如需迁移，在评审后确定具体 Alembic 文件。
- **预期结果：** 人工批准范围可复核；条件分支不是隐含实施任务；已有只读 executor 不静默升级。
- **验证项：** 只读统计、角色前后对照、双版本契约与回滚桌面推演；真正迁移时再做隔离库恢复验证。
- **状态：** `[x]` done，2026-09-22。双库全备份恢复、原 20 表数据保持与迁移升降级验证完成；按冻结 ID 清理 13 个旧 Thread 的数据库历史，业务库已升级 0003，本机服务恢复且重启后 ACL 持久化通过。沙箱磁盘目录未擦除；完整回滚须配套代码/数据并关闭业务入口，不得单独 downgrade 放宽隐私。
- **合规检查：**
  - [x] 实施完成（批准来源为用户明确“可以开始实施”及 D20 清理授权）
  - [x] 备份恢复、迁移、数据核对与重启验证已执行
  - [x] 本章任务/Phase 状态已更新
  - [x] CONTEXT 已更新

### Task H2：最终验收与状态核对
- **改动内容：** 全部已批准实现 Task 完成且 Phase 证据齐全后，执行下列 Final 验证；未批准分支记录明确处理决定，不假勾完成。
- **代码位置：** `apps/platform-api/tests/`、`apps/platform-web/src/` 测试、`apps/platform-web/e2e/`、本目录各章验证区。
- **预期结果：** README 汇总、各章任务/Phase 记录和 CONTEXT 状态一致；本章只保留一次跨模块 Final 结论。
- **验证项：** 相关服务全量单元、集成、关键 E2E、安全、适用性能与回滚；实际环境缺失则记录 partial/blocked。
- **状态：** `[x]` done，2026-09-22。本期已确认的平台权限/个人记忆入口范围实现及最终验收完成；结果、失败修复和未覆盖范围见下方 Final。共享/跨项目记忆、自定义角色等明确 deferred，不假勾实施完成。
- **合规检查：**
  - [x] 已批准实施任务完成，范围澄清已记录
  - [x] 全量、集成、安全及真实浏览器验证已执行
  - [x] 章节、README 与本章状态已同步
  - [x] CONTEXT 与 FEATURES 已更新

## 运行中撤权的单独约定

当前身份加载是在请求开始时；“立即”指撤权提交后发起的新请求按最新状态判断，不承诺让已接受的事务或长连接回退。前台权限快照每 60 秒刷新，页面重新激活、项目切换和明确拒绝时立即刷新。现有工具专项约定新 Run/恢复使用新限制，活跃 Run 使用已签名快照；本专项沿用该边界。

需要区分：界面按钮失效、停止新的 HTTP 请求、关闭 SSE、取消 Run、关闭终端。这五件事不是同一动作。若要求紧急处置，可由平台调用已有 cancel/close 并核验结果；断开浏览器流本身不会停止运行。没有证据不能承诺分布式的即时强制撤权。

## 验证要求与记录

### Phase 验证记录

| Task | 日期 | 最小验证 | 结果 |
|---|---|---|---|
| A1 | 2026-09-22 | 用户实施批准与各章范围核对 | done，见 01 |
| B/C/E | 2026-09-22 | F2 前后端 222 项回归、前端 295 passed；刷新/开户/模型/公告/账号用例 | partial，跳过项不计通过；不是当前 F2 的 Final |
| F1 | 2026-09-22 | 真实 Runtime metadata/过滤契约 1 项 | 通过，见 05；整体工作区证据仍须结合 F2 |
| F2 | 2026-09-22 | 网关/ACL 定向 43 项、分叉/运行/ACL 32 项（有重叠）；前端策略/会话 12 项 | Phase 通过，最新改动及剩余入口仍在验证 |
| F2 续 | 2026-09-22 | `RUN_LOCAL_GOVERNANCE_CONTRACT=1 uv run python -m unittest tests.test_thread_acl`，9 项 | 通过，含真实上游列表/count/共享撤销；新建测试对象均清理，非浏览器 E2E |
| H1 迁移 | 2026-09-22 | `RUN_LOCAL_GOVERNANCE_CONTRACT=1 uv run python -m unittest tests.test_thread_acl_migration`，2 项 | 隔离 SQLite / PostgreSQL schema 升降级通过；业务库未迁移 |
| B1/C3 目录治理 | 2026-09-22 | 后端目录/无项目运维 14 项、控制面入口 2 项，类型检查 | 通过；后端上游替身，真实 Runtime 目录与浏览器验收待补 |
| C2/C3/F2 浏览器 | 2026-09-22 | `platform-access-governance.spec.ts` 前两项；真实隔离平台 API + 本机 Runtime | 2 passed（42.6 秒）：管理员接管/结束/删除、移动端运维目录同步及拒绝执行；证据 `/tmp/governance-browser-4.log` |
| C4 开户浏览器 | 2026-09-22 | 同一 spec 的 `--grep "user creation"` | 1 passed（59.0 秒）：真实开户、无项目执行拒绝、模拟单次绑定 503、真实绑定重试、原令牌立即获得执行资格；证据 `/tmp/governance-onboarding.log` |
| E1/E2 治理边界 | 2026-09-22 | 五个后端相关模块 22 项 + 公告/受保护账号浏览器各 1 项 | 通过，见 04 Phase；无关 lint 警告不冒充清零 |
| F2 ACL 性能 | 2026-09-22 | 10001 条本地 ACL、1000 条可见、10 次过滤；SQLite/PG/真实上游共 12 项 | SQL 候选预筛选后中位 389.93 ms、最大 692.54 ms；不含 Runtime HTTP 请求，完整链路性能仍 partial |
| F2 私有子资源 | 2026-09-22 | 真实 API 同项目 peer 的 state/消息/运行/文件/工作区/SSE 拒绝；共享不继承终端/full_access/delete | 1 passed（18.0 秒），`/tmp/governance-child-browser.log` |
| B2/E2/F2 SA 主体 | 2026-09-22 | 修复显示名作为身份导致上游 401；账号 grant/模型引用 12 项；SA grant/shared/revoke 和 viewer 浏览器工具链路 2 项 | 通过，`/tmp/governance-sa-subject.log`、`/tmp/governance-subject-browser.log` |
| C/E/F 治理联测 | 2026-09-22 | 专项 Playwright spec 全部 9 项，真实隔离平台 API + 现有 Runtime | **9 passed（1.3 分钟）**，`/tmp/governance-phase-suite.log`；含故障注入的绑定失败场景，其余动作走真实 API；不包含真实模型审批运行 |
| H1 全库恢复 | 2026-09-22 | PG17 双库备份在新临时数据库恢复；Runtime 13 个 ID/各表计数核对；Platform 0002→0003→0002→0003 | 通过；原有 20 表计数保留，临时库清理；备份目录内 `restoration.json` 为 true，日志 `/tmp/governance-restore.log`、`/tmp/governance-restore-2.log` |
| H1 业务落地 | 2026-09-22 | 停本仓库写入服务→固定 13 个旧 ID 删除→主库升级 0003→恢复服务→新建私有 Thread→重启 API→读取并删除测试 Thread | 通过；旧 13 Thread/35 Run/26938 event 及关联 checkpoints/队列已清理，业务库其余表保留；`cleanup.json`、`/tmp/governance-main-migration.log`、`/tmp/governance-persistence-verify.log` |
| C1/C2 双标签 | 2026-09-22 | 专项双标签成员撤销用例，补齐 window focus 刷新 | 1 passed（26.5 秒）；新请求 403、两页激活后卸载聊天内容；`/tmp/governance-tabs-browser-3.log` |
| C1—C4 联合回归 | 2026-09-22 | 最新 Web 全量单测与 typecheck | 307 passed / 1 skipped，83 个文件通过；类型检查通过；`/tmp/governance-implemented-web-regression.log`、`/tmp/governance-latest-types.log` |
| F1 工作区契约 | 2026-09-22 | 既有 Runtime scope/工作区定向用例 | 6 passed，`/tmp/governance-existing-workspace-contract.log`；未改 Runtime 代码 |
| F2 审批契约 | 2026-09-22 | 真实 IAM/ACL/账本，Runtime 替身；管理员审批返回最小字段 | 1 passed，`/tmp/governance-approval-contract.log`；不包含真实模型运行 |
| F2 列表实际查询 | 2026-09-22 | `RUN_LOCAL_GOVERNANCE_CONTRACT=1 RUN_GOVERNANCE_BENCHMARK=1 uv run python -m unittest tests.test_thread_acl.ThreadAclTest.test_real_runtime_private_share_revoke_list_and_count` | 1 passed（44.060 秒）；201 条可见 Thread，list+count 每轮 6 个真实 HTTP 批次、5 轮中位 371.66 ms、最大 462.55 ms，低于本机验收预算 5 秒；`/tmp/governance-runtime-list-benchmark.log`；全部 202 个测试 Thread 已清理 |
| B2/F2 API 联合回归 | 2026-09-22 | `uv run python -m unittest discover -s tests` | 初次 238 项：224 passed、2 failed、12 skipped；两项工作区服务启动超时。修复测试就绪等待后 `uv run python -m unittest -v tests.test_runtime_gateway_workspace` **4 passed（250.244 秒）**。日志 `/tmp/governance-implemented-api-regression.log`、`/tmp/governance-workspace-recovery.log`；不谎称原整组零失败 |
| B2 真实模型审批 | 2026-09-22 | `RUN_LOCAL_GOVERNANCE_MODEL=1 uv run python -m unittest -v tests.integration.test_governance_model_approval` | **blocked**：两次在创建 Run 时返回上游 500，原因是 GraphHarbor 上下文 issuer/audience 未配齐；两次新建测试 Thread 均在 finally 删除。`/tmp/governance-real-model-approval.log`、`/tmp/governance-real-model-approval-2.log` |

### 当前验收阻塞与复现

**最新状态：已解除。** 用户明确“我同意”批准恢复配置与预检。已恢复本机 `.env` 和 `.env.example` 的 `GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE=graphharbor-worker`，`restart-one runtime-api/runtime-worker` 在停止进程前复用 `validate_runtime`。两服务重启完成；真实模型审批 **1 passed（48.922 秒）**，`/tmp/governance-real-model-approval-3.log`，测试 Thread 已清理。下文保留故障调查历史，不再表示当前阻塞。

重启预检定向测试 1 项（两个 Runtime 入口）通过，shell 语法检查通过。脚本测试组另有既有清理 dry-run 用例因临时目录不是 Git 仓库失败，未影响启动修复；完整说明见 [工具链记录](../../changes/20260922-local-stack-runtime-preflight.md)。不把脚本整组宣称为全通过。

平台实际发起 Run 已到达现有 Runtime 的 `langhost/core_api.py → langgraph_runtime_pg/auth.py:sign_runtime_context()`，抛出：

```text
RuntimeContextError: runtime context issuer and audience must be configured together
```

平台返回 `langgraph_run_request_failed`、`upstream_status_code=500`。这不是平台权限 403，也不是模型供应商失败；尚未进入模型调用。现有 [环境矩阵](../../quickstart/env-matrix.md) 已要求 `GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER` 和 `GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE=graphharbor-worker` 成对配置，API/Worker 使用一致上下文签名配置。当前只记录配置缺口，不修改 Runtime 代码或其本机启动环境，不关闭签名校验绕过。

解除条件：本机 Runtime API/Worker 配齐既有 issuer/audience 后，重新运行上述 opt-in 审批测试；预期真实 `interrupted → approve → success`。该测试只发送合成验收文本，创建和清理专用 Thread，不改项目角色或现有模型。管理员与 owner 的权限差异继续由已锁定的真实 IAM/ACL/账本契约覆盖。

记忆范围已于 2026-09-22 由用户澄清：本期只完成平台权限和项目内个人记忆入口治理，同用户同项目可跨会话使用。项目共享与跨项目记忆的存储/召回均 deferred，未来另行考虑，不再作为本期范围冲突或验收依赖。该决定不解除上面的 Runtime 配置阻塞，也不自动批准记忆专项的其他优化。

### Final 验证计划

#### 2026-09-22 Runtime 配置阻塞补充调查

- audience 表示“运行上下文签名的预期接收方”，既有值为 `graphharbor-worker`；不是域名、模型配置或本次新增业务权限。它与 issuer 配对，由 Runtime API 签发、Worker 验证，防止上下文被不匹配的接收方接受。
- 已安装 GraphHarbor 为 `0.13.0.post30`。用合成身份和测试密钥直接调用已安装的 `sign_runtime_context()` 验证：development 下 issuer/audience 均不设可签发；只设 issuer 报错；两者配齐可签发。未改持久配置、未输出 token 或秘密。生产环境要求配齐，不建议通过删除 issuer 绕过。
- Git 证据：2026-09-06 提交 `abfc442` 的 `.env.example` 已包含两项；2026-09-21 提交 `b5f1ca8` 将超时改为 900 秒时删除了 audience 行、保留 issuer。当前本机 `.env` 同样 issuer 有值、audience 缺失；本地文件无 Git 历史，不能证明其具体删除时间或声称用户以前从未正常运行。
- 启动入口差异：`scripts/local-stack.sh:start()` 经 `validate_stack → validate_runtime → validate_runtime_config.py`，已有 audience 必填预检。`restart-one` 仅加载环境并做进程/HTTP 健康检查，没有同等预检；`status` 也不试创建 Run。因此不能泛称完整 start 缺少校验。前轮恢复服务后的 ready/health 正常不代表 Run 正常，此处修正验证口径。
- 建议恢复本机配置中的 `GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE=graphharbor-worker`，API/Worker 一致加载；恢复示例行，并让单服务重启复用配置预检，防止再次漏检。本轮是解释和只读排查，尚未修改 Runtime 配置、示例或重启服务。

#### 单元测试

- IAM 固定/新权限 all/any、项目 scope、未知权限默认拒绝。
- 项目角色与平台角色组合；executor 执行权限与治理权限分离。
- 公告源/目标 scope、服务账号高权限对象、审计筛选。
- 前端路由 guard、navigation、权限响应、项目切换 epoch、会话过期。

#### 集成测试

- 用户 JWT、服务账号 API Key、停用用户、过期/撤销令牌。
- A/B 两项目：列表、详情、创建、修改、删除、批量、导出和深链。
- 模型全局管理与项目策略；凭据不回显；目录刷新不改变执行授权。
- Platform API→Runtime 现有签名委托契约保持兼容；不改 Runtime Server。

#### 端到端测试

至少覆盖以下身份：platform_super_admin、platform_operator、platform_viewer、project_admin、project_editor、project_executor、无平台角色普通用户、service account。

每个身份至少走：登录 → 项目选择 → 菜单 → 直接 URL → 页面读取 → 一个允许动作 → 一个拒绝动作 → 权限变更 → 重访。对 Chat/Dear Agent 另测消息、Run、审批、文件/成果、终端和 SSE 行为。

另加一条开户体验链路：创建用户 → 可选项目绑定 → 绑定成功/失败结果与重试 → 首次登录 → 无项目/只读/可执行状态说明；验证创建用户权限不能绕过项目成员写权限。

必须明确验证 `platform_operator` 无项目成员资格时不会隐式创建 Thread、发送消息或执行 Run；进入治理/健康入口的行为与业务项目执行分开。

#### 安全测试

- 移除菜单后直接请求仍拒绝。
- 篡改 `user_id`、`project_id`、owner、scope、资源 ID、角色 key 不改变授权主体。
- 源/目标资源跨项目变更、可猜 ID、导出/下载、SSE/流式连接。
- 账号停用、令牌撤销、成员移除和角色降级后的新请求。
- 角色授予不超出委托上限；最后治理者保护。
- 自定义角色相关用例本期不执行，Final 记录为 deferred；不得把固定角色测试冒充动态角色验收。

#### 性能与回滚（按适用）

- 权限计算和项目上下文不产生每个按钮重复请求；记录基线与阈值。
- 权限/角色数据迁移前备份；失败停止；恢复后新请求行为与旧版本一致。
- 若个人隔离/自定义角色 deferred，记录 deferred 而不是跳过冒充通过。

### Final 验证记录

2026-09-22：前置核对通过后独立执行最终回归；B1/B2、C1—C4、E1/E2、F1/F2、H1 均已完成，明确 deferred 项不假勾完成。

| 验证 | 实际结果 | 证据 |
|---|---|---|
| Platform API 全量单元/集成 | **239 项，226 passed、13 skipped，0 失败**，654.427 秒；含文件、终端和隔离 Runtime 重启链路 | `/tmp/governance-final-api.log` |
| Platform Web 全量单测 | **307 passed、1 skipped**，83 个文件通过，255.47 秒 | `/tmp/governance-final-web.log` |
| 最新前端类型检查 | `pnpm typecheck` 退出码 0 | `/tmp/governance-final-types.log` |
| 治理专项真实浏览器/API | 首轮 **9 passed / 1 failed**；失败为双标签用例撤权前等待页面加载仅 5 秒。统一为已有页面的 30 秒加载等待后，失败项 **1 passed（24.0 秒）**，不放宽权限断言；10 个场景均有通过证据 | `/tmp/governance-final-browser.log`、`/tmp/governance-final-tabs-retry.log` |
| 真实模型执行/审批 | 本机真实登录、私有 Thread、Run 中断、approve、模型成功；**1 passed（48.922 秒）**，未使用模型替身，专用 Thread 清理 | `/tmp/governance-real-model-approval-3.log` |
| 安全边界 | 固定身份组合、跨项目/私有子资源拒绝、共享不继承 full_access/terminal、管理员限时接管/结束、SA grant+项目共享+撤权、公告归属、高权限账号保护；真实浏览器及全量授权契约均通过 | 上述 API/browser 记录；按动作与 scope 覆盖，不声称每种身份的所有动作组合都逐一手工点验 |
| 适用性能、迁移与回滚 | 复用本轮无后续业务改动的 Phase 证据：201 条可见对象真实 list+count 最大 462.55 ms；双库完整恢复、隔离迁移升降级及主库重启持久化通过 | `/tmp/governance-runtime-list-benchmark.log`、H1 Phase；未重复破坏性清理 |
| 重启预检修复 | 两个 Runtime 入口的失败预检保护通过；shell 语法与 `git diff --check` 通过 | `scripts.test_local_stack_backend.LocalStackBackendTest.test_runtime_restart_preflight_runs_before_stop` |
| 本机服务/清理 | Runtime API/Worker、Platform API/Web running；ready/health yes；隔离浏览器 API/Vite 已停止，夹具专用 Thread 清理 | `/tmp/governance-final-health.log`、`/tmp/governance-final-fixture.log` |

最终结论：**本期已确认范围 done**。没有提交/推送或生产部署。修复的是既有 Runtime 配置与本地启动预检，未向 Runtime/GraphHarbor 增加业务 ACL。

验证边界与遗留：

- API 的 13 个显式门控跳过项不计通过；本项目相关真实 PG/Runtime/迁移/模型门控另有 Phase/定向证据，不相关的历史清理测试未再次执行。前端跳过项为 `src/modules/chat/sdk-chain.test.ts`，不以它冒充真实链路；真实链路使用本专项 Playwright 与 HTTP 验收。
- 本次运行 `scripts.test_local_stack_backend` 的既有清理 dry-run 测试因临时目录缺 Git 仓库而失败；与本次启动逻辑无关，未修改清理脚本。启动修复定向测试通过，完整失败记录见工具链变更文档，不声称仓库所有脚本测试全绿。
- ACL 列表成本仍随可见 Thread 数量线性增长；本机样本验证不是生产容量或压测承诺。已建立连接/已接受 Run 的撤权边界沿用本章约定。
- 本期仅项目内个人记忆入口与主体治理；项目共享/跨项目记忆、个人记忆专项其他待评审优化、自定义角色、Agent 拨测及公共沙箱均未实施。BYOK 双层模型架构已于 2026-09-22 批准并完成 ADR 与 02/03/04 规范落笔（Phase 1 前端脱敏假警报与对话拦截已落地修复，Phase 2 数据模型与接口演进详见 ADR）。不承诺管理员接管 Thread 就能读 owner 个人记忆。

## 状态

done（2026-09-22，本期已确认范围）。H1/H2 完成；独立 Final API 226 passed/13 skipped，Web 307 passed/1 skipped，10 个浏览器场景及真实模型审批通过；具体失败重试、跳过项、性能上限与本期 deferred 事项见上述记录。
