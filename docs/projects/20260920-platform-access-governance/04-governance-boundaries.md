# 04 公告、审计、账号与治理边界修补

## 目标

把已发现的具体授权问题变成可复现、可单独验收的任务。此模块可在保留旧角色模型的条件下先修复，最终仍与新矩阵回归。

## 方案设计

### 4.1 公告修改必须检查原资源

**当前代码：** `apps/platform-api/src/platform_api/modules/announcements/service.py` → `update_announcement()` 先读原记录，然后根据请求计算目标 scope，仅对目标 scope 调用 `_require_manage_access()`。

**待复现场景：** 用户仅为项目 A 的编辑；知道项目 B 某公告 ID；携带 A 的可信项目上下文 PATCH 此公告，同时将 `scope_project_id` 改为 A。当前代码路径只检查目标 A，未先拒绝修改原 B 资源。全局公告改为自己项目也需测试。UUID 难猜不能作为防护。

**推荐：** 先按原公告 scope 授权；若允许改变 scope，再校验目标 scope。最小产品规则是普通编辑不允许迁移公告归属；若管理员确需迁移，则源与目标双授权并审计。创建只校验目标，删除校验原资源。

### 4.2 公告管理列表规则不一致

平台 operator 有 `platform.announcement.write`，创建全局公告可以按此权限放行；`list_admin_announcements()` 却只给超级管理员跨 scope 读取。

例：运维进入公告管理页，页面允许选择全局，但列表请求返回缺项目范围。推荐使用统一权限语义，明确平台公告管理员能管理全局公告还是包括各项目公告；不能把前端筛选器当数据边界。公告 feed 与管理列表分开，普通用户只能看对其可见且处于有效发布期的公告。

#### 公告的使用、发布与归属

“使用”拆成读取 feed、进入管理列表、创建/发布、编辑/删除四类动作：

| 公告范围 | 谁可以读取 | 谁可以创建/发布 | 谁可以编辑/删除 | 归属迁移 |
|---|---|---|---|---|
| 全局公告（`scope_type=global`、`scope_project_id=null`） | 已登录用户的公告 feed | `platform_super_admin`、`platform_operator` | `platform_super_admin`、`platform_operator` 可维护全局运维/系统公告；`platform_viewer` 只读 | 默认禁止，需超级管理员或独立迁移动作 |
| 项目公告（`scope_type=project`、绑定一个 `scope_project_id`） | 该项目成员按 feed 规则读取 | 该项目 `project_admin`/`project_editor` | 原项目具备公告写权限的成员 | 普通编辑禁止；项目间迁移要求源/目标双授权，默认仅超级管理员执行 |

因此，平台运维可以管理全局运维公告，但不能因为拥有 `platform.announcement.write` 就管理所有项目公告。若将来需要集中运营项目公告，新增独立的跨项目公告管理权限，单独授予、单独审计；不能偷偷扩大现有权限含义。管理列表的全局 tab 和项目 tab 只是筛选体验，后端仍按公告原 scope 授权。

### 4.3 平台公共模型、BYOK 项目私有模型与目录刷新

**历史缺陷路径：** `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py` → `update_model()` 曾经仅校验传入项目写权限，再 `get_model_by_id()` 修改全局连接，且模型记录曾无项目归属字段，导致张三仅在 A 项目却可能越权修改 B 项目共享的底座模型连接。

**已确认的 BYOK 治理边界（2026-09-22）：**
1. **平台公共模型（`scope_type='platform'`）**：由 `platform.model.write` 独占管理权限（仅平台运维/超管可创建与修改 Base URL/Key）；项目接口返回时只作为可选池，不暴露敏感配置细节；
2. **项目私有模型（BYOK，`scope_type='project'`）**：归属于特定 `project_id`；由所属项目的 `project.runtime.write` 管理；项目管理员有权自主录入专属 API Key 和 Base URL；跨项目严格 403 物理隔离；
3. **运行时执行代理**：Runtime Gateway 依据模型 scope 自动选择使用平台主 Key 或项目私有 Key 兑换，兼顾集中安全合规与团队自主性。

`_require_refresh_access()` 当前还有项目写权限路径；Graph/工具目录是共享快照，是否允许项目编辑刷新应按全局影响面确认。工具目录不能重新变成工具执行的 allowlist。

### 4.4 高权限服务账号保护

**当前代码：** `apps/platform-api/src/platform_api/modules/service_accounts/service.py` → `update_service_account()` 仅在超级管理员角色标志前后不同时额外要求管理权限；`revoke_service_account_token()` 只检查普通服务账号写权限。

**例：** 普通平台运维不能给服务账号添加超级管理员，但可能可以停用一个已经是超级管理员的账号，或撤销其令牌。是否允许紧急停用需要产品决定；当前与人类超级管理员保护口径不同。

推荐对“目标当前为高权限主体”及“目标将变为高权限主体”都校验高权限管理资格；资料、状态、角色、发 token、撤 token 全覆盖。紧急吊销如果要下放，作为明确能力并审计，不留隐式例外。

本轮确认：`platform_operator` 默认不能停用高权限服务账号或撤销其令牌。若生产应急确实需要，新增独立 emergency revoke 能力，限制为停用/撤销、要求原因和请求号、强制审计，并保留最后一个可恢复的人类超级管理员。

自定义角色会让“高权限”不再只等于一个角色字符串，需要按受保护权限集合判定，见 06。保护最后一个可恢复的人类超级管理员；服务账号不能自动算作管理入口的替代品。

### 4.5 审计的数据范围

当前 `apps/platform-api/src/platform_api/modules/audit/service.py` → `list_events()`：不传 project_id 检查 platform.audit.read；传了检查 project.audit.read。repository 不传 project_id 时没有强制排除项目日志。

例：平台只读者能在全局列表看到某条 B 项目审计，却可能不能按 B 过滤。推荐显式定义：平台审计权限是否允许跨项目治理事件；项目审计只允许本项目。过滤参数只能缩小已授权集合，不能切换成另一套意外更宽/更窄的资格。

跨项目审计不自动允许读取对话正文、文件内容或模型密钥。日志应保存动作、目标、结果、必要变更摘要；凭据、完整消息内容和私人记忆不进入通用审计详情。

本轮确认的最小字段集合：操作者主体、动作、资源类型/ID、项目 scope（如有）、结果、失败原因、时间、request ID、必要的变更前后摘要。平台跨项目审计可以看治理事件和资源元数据；项目审计只能看本项目授权范围。禁止返回消息正文、个人记忆正文、文件内容、模型密钥和 token 原文。

### 4.6 讨论项

| 编号 | 问题 | 推荐起点 | 状态 |
|---|---|---|---|
| D13 | 公告是否允许改变归属 | 普通编辑不允许；确有迁移需求时源/目标双授权；默认仅超级管理员执行 | 已确认原则 |
| D14 | 平台公告运维是否可管理所有项目公告 | 运维可管理全局运维公告；项目公告由项目成员管理；跨项目管理另设独立权限 | 已确认 |
| D15 | 运维可否停用高权限服务账号 | 默认不可以；紧急撤销另授予独立能力并强制审计 | 已确认 |
| D16 | 平台审计能看哪些字段/项目 | 可跨项目看必要治理事件和元数据；不包含私有正文、记忆、文件、密钥/token | 已确认 |

## 任务拆分

### Task E1：公告源/目标授权与列表一致性
- **改动内容：** 复现并修复原资源校验，按已确认的 D13/D14 统一全局/项目公告的读取、发布、编辑、删除和迁移范围。
- **代码位置：** `apps/platform-api/src/platform_api/modules/announcements/service.py` → `list_admin_announcements()`、`update_announcement()`；`apps/platform-web/src/modules/announcements/pages/AnnouncementsPage.vue`。
- **预期结果：** 项目 A 的身份不能把 B/全局公告搬进 A 后修改；允许管理的公告可正确列出。
- **验证项：** `tests.test_announcement_scope_authorization`、`tests.test_security_boundaries` 与公告浏览器链路 → ✅ 通过；真实 API 拒绝跨 scope 修改，运维只见全局公告，编辑表单锁定范围/项目。
- **状态：** `[x]` done，2026-09-22；任务 Phase 完成，仍随项目执行 Final 回归。
- **合规检查：** 代码实现、验证执行、本章状态与 CONTEXT 更新均完成。

### Task E2：高权限目标保护与审计范围
- **改动内容：** 统一服务账号高权限对象保护；按 D15/D16 明确平台/项目审计过滤、治理事件字段和敏感字段边界。
- **代码位置：** `apps/platform-api/src/platform_api/modules/service_accounts/service.py`、`modules/audit/service.py`、`modules/audit/http_resolution.py`；`apps/platform-web/src/modules/service-accounts/pages/ServiceAccountsPage.vue`、`modules/audit/pages/AuditPage.vue`。
- **预期结果：** 普通运维无法通过资料/状态/token 路径影响受保护账号；审计过滤不改变授权语义。
- **验证项：** `tests.test_phase4_observability_and_service_accounts`、`tests.test_service_account_project_grants`、`tests.test_audit_http_resolution` 与高权限账号浏览器链路 → ✅ 通过；运维无法停用或签发受保护账号 Token，列表/详情空态不显示错误入口。
- **状态：** `[x]` done，2026-09-22；高权限账号/token 保护与审计白名单完成任务 Phase 验证。本期不新增紧急授权体系，使用显式超级管理员治理。
- **合规检查：** 代码实现、验证执行、本章状态与 CONTEXT 更新均完成。

模型边界修补统一归 B1，不在本章重复实施。项目管理员恢复、最后管理员保护与用户角色授予沿用已有能力并纳入 Final 回归。

## 验证要求与记录

### Phase 验证记录

E1：`test_announcement_scope_authorization.py` 覆盖真实 HTTP＋隔离数据库的源/目标授权、普通编辑不可迁移、全局列表不泄露项目公告。E2：`test_phase4_observability_and_service_accounts.py` 覆盖高权限账号及 token 操作保护、审计输出脱敏。均包含于 F2 开始前的后端 222 项回归（OK，8 skipped）；详细阶段证据见实施记录。

2026-09-22 最新 E1/E2 最小回归：上述五个 unittest 模块共 **22 项通过**，`/tmp/governance-boundaries-phase.log`；两个页面定向 ESLint **0 errors、1 warning**。真实浏览器公告 **1 passed（21.0 秒）**，`/tmp/governance-announcement-browser-2.log`；高权限账号 **1 passed（18.3 秒）**，`/tmp/governance-sa-browser-2.log`。前者首轮测试公告缺正文导致表单拒绝，补完整 fixture 后通过；后者发现空态发 Token 入口未收口，修复列表及详情后通过。不是绕过断言或隐藏失败。

### Final 验证记录

已完成；最终 API 与治理浏览器用例覆盖新矩阵及公告/账号边界，见 [07](07-implementation-and-verification.md#final-验证记录)。

## 状态

done：E1/E2 实现、Phase 及联合 Final 回归完成，证据见 07；未执行生产发布。
