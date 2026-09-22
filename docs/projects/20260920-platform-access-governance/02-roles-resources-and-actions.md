# 02 角色、资源归属与动作权限

## 目标

先说明资源属于谁，再定义谁能做什么。解决 executor 不能执行、运行与治理共用权限，以及全局资源由项目权限管理的问题。

## 方案设计

### 2.1 已确认授权规则

```text
允许 = 当前主体有效
    且满足动作权限
    且满足该动作要求的项目成员 / 平台治理范围
    且目标资源归属、共享关系符合要求
    且资源生命周期、执行限制允许
```

不能写成“只要 platform_super_admin 就无条件通过”。平台元数据治理和项目内容读取继续分开；已有项目接管也不应自动等于未来的私有对话接管。

同范围多角色可以取动作权限并集，但项目 A 的角色不能合并到 B。工具禁用、账号禁用、资源私有边界不会被新增角色抵消。现有项目成员数据库是一项目一用户一个 role；多角色目前只是概念上的组合规则，若实施绑定变化见 06。

### 2.2 资源归属表

| 资源 | 当前事实 | 推荐归属与管理方式 | 例子 |
|---|---|---|---|
| 平台用户、系统配置 | 平台级 | 平台治理权限 | A 项目管理员不能停用全平台用户 |
| 项目名称、归档、接管 | 平台权限控制 | 保留，与项目内部内容分离；是否下放改名另议 | 运维可看项目元数据，不自动查看对话 |
| 项目成员、Agent | 项目级 | 项目成员管理/Agent 编辑权限 | A 的编辑不能修改 B 的 Agent |
| 平台公共模型连接、base_url、公共密钥、全局 enabled | `scope_type='platform'`, `project_id=null` | 平台集中维护，平台运维 (`platform_operator`) 维护；项目仅做选用与项目策略 | A 的编辑不能把平台公共模型地址改成另一个端点 |
| 项目私有模型连接 (BYOK)、私有密钥、私有端点 | `scope_type='project'`, 绑定 `project_id` | 项目级隔离；该项目的项目管理员 (`project_admin`) 或编辑配置与维护自己的 Key/端点 | A 项目自建的 Ollama/私有 Key 不对 B 项目可见，B 无法调用与修改 |
| 模型默认项、项目模型限制 | 项目 policy | 项目治理动作，不能反向授权修改全局密钥 | A 更换默认模型不改变 B 默认模型 |
| Graph/工具 catalog | runtime 共享快照 | 目录可读；刷新属于明确平台治理动作 | 项目执行者可看工具说明，不代表能刷新全局目录 |
| 工具禁用例外 | 项目/graph + 全员或指定用户 | 管理权限独立；保留已有拒绝并集语义 | 增加“执行”角色不能消除用户已有禁用项 |
| Thread、Run、文件、成果 | Thread 按项目隔离 | 项目共享或个人所有权由 05 决定；子资源继承 Thread 范围 | 一份成果下载不能绕过 Thread 授权 |
| Skills、记忆 | 各有当前 Runtime scope 与独立专项 | Skills 继续按真实 scope 管理；本期只保留项目内个人记忆，按当前用户与项目隔离 | 项目管理员、平台运维不因角色名称自动读取个人记忆 |

#### 模型架构升级：支持每项目自带连接 (BYOK)
已于 2026-09-22 批准采纳双层模型架构（详见 [ADR: 平台公共模型与项目私有模型 (BYOK) 双层架构决策](../../decisions/20260922-byok-project-model-architecture.md)）：
- **平台公共模型**：运维配置公共底座与账单，项目按需授权；项目端隐藏运维级脱敏凭据状态，不误报假故障。
- **项目私有模型 (BYOK)**：项目管理员可在所属项目中自主录入私有端点与专属 API Key，实现团队模型自治与账单独立。数据表增加 `scope_type` 与 `project_id` 字段以支持严格租户物理隔离。

### 2.3 六种现有角色的推荐职责

| 角色 | 推荐职责 | 不隐含的能力 |
|---|---|---|
| platform_super_admin | 角色授予、高权限账号治理、平台项目管理、显式恢复/接管 | 自动读取私有对话、自动成为每个项目成员 |
| platform_operator | 被明确允许的用户资料/状态、平台配置、模型运维、目录维护等 | 授予超级管理员、重置所有凭据、跨项目内容读取 |
| platform_viewer | 指定的平台治理数据只读 | 普通用户默认角色、所有项目内容只读 |
| project_admin | 项目成员、Agent、项目策略管理和执行 | 全局模型密钥管理、平台角色授予 |
| project_editor | 配置 Agent、使用已授权能力 | 项目成员管理、项目安全限制修改 |
| project_executor | 使用已配置 Agent，执行允许的对话操作 | 编辑 Agent、模型/策略治理、手动终端或无条件 full_access |

普通平台用户可以没有平台角色，仅通过项目成员身份使用产品。不要为“让普通人登录”自动分配 platform_viewer，因为它能读取平台治理资源。

是否新增 project_viewer 必须单独决定：如果已有 executor 实际用于只读人员，恢复执行能力会扩大存量权限；应先盘点授予意图，再映射，不能直接批量升级。

#### 平台运维的能力边界

`platform_operator` 是控制面运维身份，不是所有项目的业务用户，也不是隐含的超级管理员。当前代码中的平台权限映射允许它读取平台用户、读取项目和审计、刷新目录、读写部分平台配置、发布公告、读写服务账号；不允许角色授予、凭据重置、项目创建/接管、服务账号 grant 写入。模型连接目前没有清晰的独立平台权限，属于需要修补的授权缺口，不能继续借用项目运行写权限。

目标职责按以下边界冻结，具体权限码在实现前再与现有枚举合并：

| 能力域 | 运维默认能力 | 明确不包含 | 说明 |
|---|---|---|---|
| 控制面可用性 | 查看平台状态、受保护的探针/指标、目录刷新、故障定位所需的技术元数据 | 通过探针读取业务对话、私有记忆或用户文件 | 健康拨测必须有独立资源、额度和审计边界 |
| 用户与账号 | 按批准范围查看用户状态，创建账号，修改非敏感资料和状态 | 重置任意凭据、授予平台角色、授予超级管理员 | 当前 `platform.user.write` 过宽时要拆成资料/状态动作 |
| 项目治理 | 查看项目元数据、归档状态和运行健康 | 自动成为项目成员、读取项目 Thread、替项目管理员接管 | 接管是 `platform.project.takeover` 的显式 break-glass 能力，默认只给超级管理员 |
| 模型与目录 | 管理全局模型连接、端点和启停（待建立独立平台动作）；刷新共享 catalog | 修改项目私有策略、借模型管理权限读取项目内容 | 全局密钥只写不读，项目只选择已批准模型 |
| 审计与公告 | 读取平台审计，按职责发布全局公告 | 删除/篡改审计；用公告权限绕过项目授权 | 原记录的 scope 仍需先校验 |
| 服务账号 | 查看和维护普通服务账号状态（高风险对象需保护） | 授予平台超级权限、跨项目 grant、绕过最后治理者保护 | grant 写入继续单独保护 |
| 业务执行 | 无项目成员资格时不能创建 Thread、发消息、Run、终端或读取项目成果 | “运维”角色自动获得所有项目聊天权 | 有业务需要时，显式绑定某项目的项目角色；只影响该项目 |

运维默认首页可进入控制面和健康视图。需要验证某个项目 Agent 时，优先使用受限健康拨测；如果只能调用普通 Chat，则该能力后置，不能用运维身份绕过项目成员授权。

#### 私人沙箱、`full_access` 与项目执行权限

`full_access` 是执行模式和高风险动作集合，不等于项目角色，也不能通过给 executor 加一个粗粒度写权限解决。可以支持“创建者在自己创建的私人沙箱/私人 Thread 中获得 full_access”，但必须同时满足以下条件：

1. 沙箱和 Thread 由平台根据当前认证主体生成 owner，客户端不能提交任意 owner；
2. 沙箱默认是个人私有，不能因为位于某项目就自动对项目成员共享；显式共享后仍按共享动作降级，不能把 `full_access` 传给共享者；
3. `full_access`、终端 create/input/close、文件写入和工具副作用分别记录审计，并受账号状态、Agent/工具限制、额度和过期时间约束；
4. 项目共享 Thread、他人 Thread、管理员查看或接管场景默认不允许 owner 的 `full_access` 继承；需要单独的显式授权；
5. 平台只能在现有 Runtime 契约支持按 Thread/沙箱隔离时实施。若上游无法保证沙箱隔离、取消和资源归属，平台不能宣称“每个人完全独立”，应把该部分标记为 blocked/deferred。

因此本轮结论是：**方向可以成立，但 full_access 只授予私人沙箱的创建者，不能授予整个 executor 角色；实现前必须完成 05 的 Thread/沙箱隔离证据盘点。**

这里还有一个必须单独确认的范围问题：

| 方案 | 沙箱归属 | `platform_operator` 无项目时 | 代价 |
|---|---|---|---|
| A：平台级个人沙箱 | 沙箱属于用户主体，项目只是可选上下文；不读取任何项目资源 | 可以在独立的个人沙箱中执行 `full_access`，但这不是项目聊天资格 | 必须定义平台级额度、费用归属、可用 Agent/工具、数据保留和运维审计 |
| B：项目内个人沙箱（当前推荐） | 每个沙箱必须挂一个项目，Thread 继承项目范围；同一项目内仍按 owner 隔离 | 不能创建或执行；需要业务验证时显式绑定项目角色，或使用受限健康拨测 | 语义最简单，和 D29 一致；运维自测需要额外入口 |

本期推荐先采用 **B**，因为现有运行网关和项目上下文都以 `project_id` 为授权边界；不要为了让运维“能试一下”而偷偷引入平台级执行面。若产品明确需要 A，则应把它作为独立能力评审，新增 `personal_sandbox.create/execute` 一类平台动作，并将额度、数据和审计规则写入 03/04/05，不能仅在前端放开按钮。

#### Skills 与记忆的独立 scope

2026-09-22 用户澄清后，本期只采用**项目内个人记忆**，取代此前“项目共享记忆 + 个人记忆”的本期组合：

- **项目内个人记忆：** 归当前用户所有，按现有 `tenant_id + project_id + user_id` 隔离；只有本人可在当前项目读写和召回。同用户同项目可跨 Thread 使用，不绑定单个 Thread 生命周期。
- **本期不做：** 项目成员共享记忆、跨项目个人记忆、跨项目共享记忆及其存储/召回契约；统一标记 deferred，未来有明确需求再立项，不作为本期依赖或验收阻塞。
- **Skills：** 不因记忆模型改变，继续依据现有系统/项目/用户真实 scope 授权；页面上显示的入口不能扩大 scope。

例如：小李在 A 项目保存“测试报告使用中文”，小李在 A 的另一个会话可以使用；小王在 A 不可使用；小李切换到 B 也不可使用。这是“跨会话”，不是“跨用户”或“跨项目”。Thread 分享、项目管理员身份和 Thread takeover 都不授予读取原 owner 个人记忆的权利。

平台入口根据认证主体和当前项目构造委托，不能信任客户端指定的 owner；管理员不因角色自动读取他人的个人记忆。本期不新增记忆 break-glass 或共享 ACL，也不复制记忆存储。本权限专项只收口入口、主体授权和权限说明；存储/召回的其他优化仍依个人记忆专项单独评审，不在这里扩大 Runtime 改造范围。

参考核对（只读源码，未运行参考仓）：`deer-flow/backend/app/gateway/routers/memory.py:_resolve_memory_user_id()` 从可信身份解析用户；`backend/tests/test_memory_storage_user_isolation.py` 覆盖不同用户的存储/缓存隔离及用户＋Agent 作用域。借鉴个人记忆和跨会话使用的思路；参考仓的用户级摘要/Agent 事实模型不等于本平台的项目 scope，不照搬为项目共享库。

#### 运维身份与项目执行身份的组合

来自 RBAC/UX 复盘的例子：Test 只有 `platform_operator`，可以按平台权限进入治理页面；没有 A 项目成员身份时，不获得 A 的对话读写。若显式加入 A，执行能力由 A 的角色与批准动作矩阵决定，不能把平台角色当作项目资格。

因此修复要分两条：03 解释权限并打通开户/成员关联；本章解决 executor 动作语义。给 Test 添加当前 `project_executor` 并不自动修复发消息问题，必须先完成 D03 的执行/治理拆分，或明确沿用当前角色行为。

开户时同样遵守双层授权：`platform.user.create` 只允许创建账号；现有 `ProjectsService.upsert_member()` 要求目标项目的 `project.member.write`。即使平台超级管理员也不能借“创建向导”悄悄绕过成员授权。需要跨项目开户权限时，应另定义显式授予能力并评审，不能自动接管全部选中项目。

### 2.4 候选动作分组

以下是用于讨论的语义分组；仅已有权限明确标现有，其余名称不是已部署契约。

| 动作组 | 推荐执行者 | 覆盖入口与约束 |
|---|---|---|
| 运行读取（现有 `project.runtime.read`） | 项目读者 | Thread/历史/Run/文件/成果；还需资源关系校验 |
| 普通执行（拟拆分） | admin/editor/executor | 创建 Thread、发送、继续/审批、停止、允许的附件上传；不能附带治理能力 |
| 对话破坏性操作（待细分） | owner 或明确维护者 | 删除对话/Run、状态改写分别评审；不因可运行自动允许删除他人数据 |
| Agent 读取/编辑（现有 `project.assistant.read/write`） | 全体读；admin/editor 写 | 保留现有命名，避免新增同义 agent 权限 |
| 全局模型连接管理（`platform.model.read/write`） | super_admin/operator 可写，platform_viewer 只读 | 新建、端点、凭据、全局停用；独立平台入口，项目仅列可选能力 |
| 项目模型/Graph 策略管理（拟拆分） | project_admin | 默认模型、项目禁用；保留执行时限制检查 |
| 工具限制读取/写入（拟拆分） | project_admin；是否允许只读审计者待定 | 接入现有 `tool-restrictions`，不重建工具协议 |
| 目录刷新（已有 `platform.catalog.refresh`） | 平台指定角色 | 当前 `_require_refresh_access()` 还有项目写权限路径，需要按全局影响面收敛 |
| 手动终端（拟独立） | 明确授权者 | create/input/resize/close 与 list/output 分开评审；代理调用工具不是同一个入口 |
| 执行模式选择（拟独立约束） | 用户仅在获准集合内选择 | Thread 创建和 PATCH 都约束；Agent 默认值和 Run 覆盖不能绕过 |
| Skills 治理、记忆写入 | 按真实作用域单独决定 | 运行权限不能自动变成所有共享资源管理权限 |

“可使用模型”不等于“能读模型连接详情”。对话下拉只需 ID、展示名和必要能力；base_url、内部配置和凭据管理状态按管理权限返回，密钥仍只写不读。

### 2.5 具体调用链改造

1. `apps/platform-api/src/platform_api/modules/iam/application/policies.py`：登记批准的动作、角色映射；未知权限保持拒绝。
2. `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`：替换 `_authorize(write: bool)` 在不同入口的粗分类。标准 Runs、commands、消息队列、终端、状态写入、分支、模式切换都要映射，不能只改 Chat 主入口。
3. `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py`：`create_model()` / `update_model()` 改按全局权限；`_authorize_model_reference()` / `authorize_message()` 改按执行资格复核，不能继续要求配置管理权限。
4. `apps/platform-api/src/platform_api/modules/runtime_policies/application/service.py`：`_require_project_access()` 与工具限制 CRUD 使用明确治理权限；`build_delegation_policy()` / `resolve_tool_overrides()` 的执行语义沿用当前专项。
5. `apps/platform-api/src/platform_api/modules/projects/service.py` → `get_access()`：输出新权限集合；前端 03 同一发布单元对齐。

Runtime 只接收当前协议已支持的执行授权，不接收前端角色名或自定义权限表达式。本期不修改 Runtime Server、GraphHarbor、interaction-data-service；任何发现的协议能力缺失记录为边界阻塞，不自动扩围。

### 2.6 讨论清单

| 编号 | 要决定的问题 | 推荐起点 | 例子/影响 | 状态 |
|---|---|---|---|---|
| D03 | executor 是真正执行者还是只读者 | 执行者；需要只读时另设 `project_viewer` 或等价只读能力 | 不能把历史只读人员静默升级为执行者 | 已确认：executor 可执行 |
| D04 | 模型连接全局还是项目 BYOK | 保持全局，由平台治理角色管理；项目只选择已批准连接 | BYOK 需要归属、迁移、凭据和去重设计，本期不做 | 已确认：全局平台管理 |
| D05 | 编辑能否改项目安全策略 | 默认不能；项目安全/工具限制属于独立治理动作 | 编辑 Agent 与解除禁用职责分离 | 已确认：默认不能 |
| D06 | 谁可操作终端/选择 full_access | 独立对象动作；executor 角色默认没有；项目内私人 Thread owner 可以操作自身沙箱 | 已选 B：必须挂项目，每个 Thread 独立私有；共享者不继承高风险动作 | 已确认；F1 已验证平台可行 |
| D07 | Skills/记忆治理归谁 | Skills 按真实 scope；本期只有当前项目下当前用户的个人记忆 | 同用户同项目可跨会话使用；项目共享与跨项目存储/召回不做，不作为外部依赖；本专项完成平台权限和个人记忆入口治理 | 2026-09-22 用户澄清确认；其他记忆范围 deferred |
| D08 | 删除/审批是否只限对话所有者 | Thread 所有者、项目管理者、平台管理员；三者都受资源 scope、动作权限和审计约束 | 项目共享可读不意味着共享可删；平台管理员不是默认读取私有 Thread，需走 05 的 takeover 规则 | 已确认原则，细节见 05 |
| D29 | 平台运维是否自动获得项目聊天资格，以及运维有哪些能力 | 不自动获得；运维默认只做控制面、审计、目录、全局模型和已有健康状态；有业务需要时显式绑定项目角色 | 运维 + A 项目执行资格仅影响 A，不放开 B；已排除无项目公共沙箱和本期 Agent 拨测 | 已确认，动作映射已落地 |

## 任务拆分

### Task B1：动作权限与全局资源边界
- **改动内容：** 按已确认的 D03—D05、D29 以及 D06/D07 的隔离原则修改 IAM、模型管理、项目策略、目录刷新、沙箱执行和记忆入口授权。
- **代码位置：** 本文 2.5 的 `policies.py`、catalog service、policy service、projects service。
- **预期结果：** executor 可使用已授权能力；项目角色不能管理全局连接；治理动作有独立权限。
- **验证项：** 扩展 `apps/platform-api/tests/test_iam_policy_engine.py`、`test_model_connection_lifecycle.py`、`test_security_boundaries.py`；角色 A/B 与全局模型交叉用例。
- **状态：** `[x]` done，2026-09-22：动作权限、全局模型管理、目录治理和前端入口已实现；IAM/模型/边界用例及多身份真实 HTTP/浏览器 Phase 证据齐全。联合 Final 仍见 07，不表示独立发布。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 角色、模型、目录和越权验证已执行
  - [x] 本章任务与 Phase 状态已更新
  - [x] CONTEXT 已更新

### Task B2：运行入口与后续再授权对齐
- **改动内容：** 将同一动作语义贯穿标准 Runs、commands、模型兑换、排队消息、模式与终端。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`、`apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py`。
- **预期结果：** 不发生入口放行而后续错误拒绝，也不通过替代入口绕过治理限制。
- **验证项：** `apps/platform-api/tests/test_runtime_gateway_http_matrix.py`、`test_runtime_model_reference.py`、`test_run_requests.py`、`test_thread_access_policy.py`；检查未授权请求不调用上游。
- **状态：** `[x]` done，2026-09-22。运行、模型/消息引用、模式及终端再授权已验证；经用户批准恢复既有 audience 配置后，真实 Platform→Runtime→Worker→模型审批链路 `interrupted → approve → success` 通过（48.922 秒），专用 Thread 已清理。共享/跨项目记忆 deferred，不作为验收依赖。
- **合规检查：**
  - [x] 平台实现完成
  - [x] 定向授权契约、工作区及真实模型审批已验证
  - [x] 本章任务及 Phase 记录已更新
  - [x] CONTEXT 已更新

## 验证要求与记录

### Phase 验证记录

B1/B2：模型生命周期、权限与 HTTP 网关已有阶段测试；F2 定向测试组 43 项、分叉/运行组 32 项通过（有重叠），最新修改待再验证。命令及范围见 [实施记录](implementation/01-platform-governance.md)，不作为 Final。

2026-09-22 B1 目录治理补充：`RuntimeCatalogService.refresh_tools()/refresh_graphs()` 使用 `platform.catalog.refresh`，签名保留真实平台角色；项目 ID 只作为现有委托协议的明确范围，不授予成员身份。控制面已有独立同步表单。14 项目录/权限测试通过（`tests.test_thread_acl.ThreadAclTest.test_operator_catalog_refresh_does_not_grant_project_execution tests.test_runtime_catalog_delegation`），覆盖无项目运维同步成功、普通执行者同步拒绝、运维 Thread 创建拒绝。后续专项浏览器 9 项已包含真实 Runtime 目录同步、无项目运维拒绝执行、viewer 模型只读及 editor 安全策略拒绝；见 07。

B2 Phase 补充：`RUN_LOCAL_GOVERNANCE_MODEL=1 uv run python -m unittest -v tests.integration.test_governance_model_approval` 1 passed（48.922 秒），日志 `/tmp/governance-real-model-approval-3.log`。该条属于 Phase，统一 Final 见 07。

### Final 验证记录

已完成，统一结果与边界见 [07 Final](07-implementation-and-verification.md#final-验证记录)。

## 状态

done：B1/B2 及联合 Final 完成，见 07。共享/跨项目记忆由用户确认本期 deferred，不阻塞本期。与 03 同批验收，不表示可以独立上线。
