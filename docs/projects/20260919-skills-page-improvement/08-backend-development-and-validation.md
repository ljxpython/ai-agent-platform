# 后端开发、接口与验证详细规划

状态：**最高 / done（后端范围）**。用户已明确授权开发；下文保留批准的文件级规划，实际契约以 [07](07-frontend-handoff.md)、实现记录和第9节验证为准。

已决定：UUID CAS、默认启用/更新保持状态、删除不存在 404、全部公共目录、50 条当前技能、独立 Alembic。
恢复引用已落在官方私有 graph state，使用原生 task_id 幂等化；不修改 GraphHarbor。
前端实施/浏览器验收及根级部署自动接入 **延后**，不计为已交付。

## 1. 已批准范围与完成定义

**已决定：** 单份当前技能；无候选发布和强制文本评估门槛；导入/更新校验后原子生效；运行内内容稳定、下次运行取当前内容；tenant/project/user 隔离、管理不依赖 thread；公共目录动态下发；公共和自定义的文件树及文本只读详情；PostgreSQL 与统一应用迁移/连接；只实施 platform-api、runtime-service，前端只交接。

首期不建设多版本 UI、历史回滚、项目共享、在线编辑、导出或技能市场。**启用/停用、删除用户自定义技能纳入本期**；公共内置技能全部可见且保持只读，不把“全可见”扩大成可覆盖/删除内置文件。新增自定义技能继续拒绝与内置 slug 冲突。

后端完成须具备：真实接口链路、数据迁移、权限与文件安全、运行时读取及工具同步、后端验证证据、可执行前端交接。前端未接入时不得标记完整页面交付完成。用户已随后明确授权实施，前期讨论限制已结束。

## 2. 调用链和复用点

目标管理链：浏览器 → platform-api（登录身份、项目权限、审计、委托）→ Runtime 内部技能路由 → 技能目录/存储 → PostgreSQL 或内置包资源。

目标执行链：受信任运行身份 → 读取本 scope 当前技能 → `prepare_custom_skills()` 内容快照 → `workspace.skills_root` → `/skills/` 只读后端及 Docker 只读挂载 → 主 Agent/子 Agent。

已核对的复用点：

- `RuntimeGatewayService._prepare_project_scope()` 可校验项目存在及读写权限，不必创建占位会话。
- `SkillStorage` 已含范围锁与存取；`inspect_package()` 已有路径、大小和文本检查，可改造复用。
- `prepare_custom_skills()` 已按内容创建独立目录并指定 `skills_root`，旧实例不必切换到新目录；其指纹现按公共与自定义实际文件内容计算，避免无关元数据制造重复快照。
- `/skills/` 的 `ReadOnlySkillsBackend` 与 `execute_in_workspace(..., skills=...)` 都接入 `skills_root`，必须同时验证；不能只验证 Python 文件读取。
- `get_agent()` 已移除 `freeze(scope, thread_id)`，由 ExecutionSkillsMiddleware 读取当前集合并持久化执行快照；非执行 schema 探测不连接技能数据库。

## 3. 开发文件与职责清单

下面路径均相对仓库根，已按职责实现。测试优先整合现有文件，实际落点见第9节。

### 3.1 Runtime 技能、HTTP 和执行

| 文件 | 开发内容 | 验收重点 |
|---|---|---|
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py` | 复用包检查；一份当前技能；原子 create/update、enable/disable/delete、CAS、列表/内容读取；退出 candidate/activate/freeze 业务链 | 更新/停用/删除竞争安全，删除重建不接受旧并发 token |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_catalog.py`（已实现） | 提取公共枚举/元信息、文件 manifest 与受限读取；全部内置技能列出，HTTP 和工具共享 | 不保留隐藏名单；全可见不跳过文件路径安全 |
| `apps/runtime-service/src/runtime_service/http/dear_skills.py`（已实现） | 独立于 thread 的技能列表/详情/文件/写入路由，严格请求模型与委托检查 | 不接受客户端任意 scope、只读 token 不能写 |
| `apps/runtime-service/src/runtime_service/http/dear_governance.py` | 保留记忆契约；核对旧技能调用方后退役不再需要的技能分支，不做候选动作适配层 | 不误删 `/memory` 和其授权；退役清单交接前端 |
| `apps/runtime-service/src/runtime_service/webapp.py` | 注册新技能 router；保留现有其他 router | 路由无冲突，探活/记忆等不受影响 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` | `freeze()` 改为当前技能装配；同步工具名、权限、审批与运行恢复策略 | 同会话后续运行获得更新；当前运行读取不变 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py` | 复用内容快照、稳定指纹与只读映射；明确空自定义集、公共包变化、损坏快照行为 | 文件工具、execute、子 Agent 都读取同一份内容 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/skills.py` | 列表使用共享目录；直接导入/显式更新替代 candidate/publish；删除强制评估；保留只读审查且无发布门槛；启停/删除工具复用存取规则和 HITL | 页面、远端导入和对话写入使用相同校验/冲突规则 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/capabilities.py` | 清理旧工具权限；提供无需 thread 的技能能力信息来源 | 工具清单与实际注册一致；能力字段不替代授权 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/skills/skill-creator/SKILL.md` 及 `provenance.json` | 改掉 candidate→review→evaluate→publish 指令，更新本地适配说明 | Agent 不被旧指令引导调用已退役工具 |

联动检查 `prompts.py`、`subagents/researcher.py`、`skills/find-skills/`、`skills/skill-reviewer/` 和相关测试/文档中的旧工具引用，仅修改实际依赖处。GraphHarbor/LangGraph/DeepAgents 的执行恢复 API 如需使用，实施前按仓库约定核对官方 MCP 文档，不凭猜测新增 lifecycle hook。

### 3.2 平台网关与两端鉴权

| 文件 | 开发内容 | 验收重点 |
|---|---|---|
| `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` | 新技能路由；复用 `x-project-id`；请求验证/大小限制；委托 factory 支持不带 thread 的技能操作；按真实授权签发 | 不用虚假 thread；不只依赖前端 canWrite |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | 技能方法使用 `_prepare_project_scope()`，核对 Dear Agent 在项目内允许访问，再签发技能资源委托；记忆保持原路径 | 跨项目/禁用 Agent/无权限均拒绝 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py` | 增加技能上游端口声明，避免复用 thread 必填签名硬塞空字符串 | port、实现与测试桩签名一致 |
| `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py` | 技能路由、参数/错误透传，编码文件 path；不把文件正文丢到日志 | 400/403/404/409 等语义可传至前端 |
| `apps/platform-api/src/platform_api/core/security/tokens.py` | 新增专用技能读/写 operation 白名单 | 新操作不扩大旧 token 权限 |
| `apps/runtime-service/src/runtime_service/runtime/auth.py` | 同步 operation 枚举和受信任 scope 校验 | 签发与验证一致 |
| `apps/runtime-service/src/runtime_service/auth/platform.py` | 技能 token 加入原生 Server 资源拒绝规则 | 管理 token 不能创建 run、读线程或进入终端 |

已新增 `dear-skills-read` / `dear-skills-write`；旧 `dear-governance-*` 保留给记忆，不因技能退役删除共用 operation。名称已定，独立authorize校验无thread技能scope，旧memory的thread检查保留。

继续复用 `project.runtime.read/write` 与现有角色策略，不新增权限模型。当前委托 factory 有固定声明读/写 permission 的代码，技能入口须先完成真实权限检查，并避免新技能 token 虚报写权限；不顺带重构全部委托体系。审计沿用 `apps/platform-api/src/platform_api/entrypoints/http/middleware/audit_log.py`，核对新增路径是否正确归类；记录动作/scope/slug/结果，不记录包正文、凭据或完整文件内容。

### 3.3 数据库与交付资源

| 文件/目录 | 拟议工作 |
|---|---|
| `apps/runtime-service/src/runtime_service/db/__init__.py` | 抽出现有重复 DSN 归一/连接逻辑，不提前加 ORM 或通用 Repository |
| `apps/runtime-service/src/runtime_service/db/migrations/`（最高） | 应用迁移版本、独立版本记录；SQL/迁移资源可随 wheel 发布 |
| `apps/runtime-service/src/runtime_service/db/__main__.py`（最高） | 一个应用迁移入口；不在 HTTP 请求或 Agent 装配时建表 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/governance_storage.py` | 通用连接转用 db；scope 锁保留业务语义；退出散落建表入口或保留明确的过渡提示 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/{memory.py,external_task_storage.py}` | 仅接入共用连接/迁移，记忆与外部任务语义不变 |
| `apps/runtime-service/src/runtime_service/messaging/{inbox.py,__main__.py}` | 收件箱建表/加列纳入应用迁移；消费/幂等语义不变 |
| `apps/runtime-service/pyproject.toml`、`uv.lock` | 声明 Alembic 直接依赖；调整包资源；不升级核心运行依赖 |
| `apps/runtime-service/deploy/`、`README.md`、`docs/standards/` | 根据选定入口维护服务内部署顺序、应用迁移规范与验证步骤 |

`scripts/local-stack.sh` 和仓库根 `deploy/` 不在用户已定的两个服务代码范围内。需要接入它们才能完成统一启动覆盖时，应明确提出最小范围扩展；在此之前只能交付服务内命令和接入说明，不能宣称默认部署已自动执行所有迁移。

Q7 已取消存量兼容设计，但没有明确将根级部署文件纳入代码范围；这里保留范围说明，不能把“不兼容旧数据”解释为任意改部署范围。

### 3.4 Q1 核实：Server 扩展与应用能力的边界

**已决定：技能目录、上传、启停、删除、扫描、技能持久化及其迁移均为 runtime-service 自有能力，不向 GraphHarbor 添加技能业务能力。**

本轮通过 langchain-docs / langchain-reference MCP 核对：

- [Agent Server](https://docs.langchain.com/langsmith/agent-server) 与 [SDK 核心资源](https://reference.langchain.com/python/langgraph-sdk/client)：核心覆盖 assistants、threads、runs、cron、store；核对资料中未发现与本方案等价的内置技能 CRUD/应用表迁移注册契约。
- [自定义路由](https://docs.langchain.com/langsmith/custom-routes)：应用可提供自有 app/routes。由 Server 承载应用路由不意味着业务功能变成 Server 自带能力。
- [Deep Agents Skills](https://docs.langchain.com/oss/python/deepagents/skills#read-only-skills) 与 [SkillsMiddleware](https://reference.langchain.com/python/deepagents/middleware/skills/SkillsMiddleware)：技能加载/渐进读取在 Agent SDK 层，官方说明应用或管理流程可更新技能 backend。不能因为 SDK、Fleet 或 Managed Deep Agents 有技能产品功能，就归入通用 Agent Server 的核心契约。

本地安装版本 `graphharbor==0.13.0.post30`：包入口是 `langhost.cli:cli`；`langhost/cli.py::migrate_command()` 调用 `langgraph_runtime_pg.migrate`，后者将 `MIGRATIONS_DIR` 固定为自身包内 migrations。已检查的 CLI/runner 没有应用技能迁移注册入口；支持版本表 schema 不等于支持应用迁移链。仅做源码读取，未运行 migrate。

**具体落地方案已实施并验证；状态：最高。** Runtime 自有 Alembic 链，放在 `src/runtime_service/db/migrations/`，通过 `python -m runtime_service.db upgrade` 执行，使用独立 `runtime_app_alembic_version` 记录；将 Alembic 声明为本服务直接依赖，不依赖 GraphHarbor 的传递依赖。业务查询继续 psycopg，不迁入 ORM。GraphHarbor 与应用迁移由部署按顺序调用，不修改 GraphHarbor migration runner。

## 4. 已实现接口（详细成功/错误契约见07）

沿用平台 `/api/langgraph` 前缀、登录鉴权与 `x-project-id`。Runtime 使用内部前缀，由委托 token 携带 tenant/project/user，正文不接受这些身份字段。建议使用独立技能路由，不再复用 `/threads/{thread}/dear/{resource}`。

| 平台接口 | Runtime 对应接口 | 用途 |
|---|---|---|
| `GET /api/langgraph/dear/skills` | `GET /internal/dear/skills` | 公共与当前用户自定义列表、管理能力与限制 |
| `GET /api/langgraph/dear/skills/{source}/{slug}` | 同后缀 `/internal/dear/skills/{source}/{slug}` | 技能元信息＋manifest 文件树数据 |
| `GET /api/langgraph/dear/skills/{source}/{slug}/content?path=...&revision=...` | 同后缀内部路由 | 单文件受限文本；校验详情对应内容未改变 |
| `POST /api/langgraph/dear/skills/custom` | `POST /internal/dear/skills/custom` | 创建：只接受新名称 |
| `PUT /api/langgraph/dear/skills/custom/{slug}` | `PUT /internal/dear/skills/custom/{slug}` | 显式更新：根 SKILL.md 名称须匹配路径，携带 expected_revision |
| `PATCH /api/langgraph/dear/skills/custom/{slug}` | `PATCH /internal/dear/skills/custom/{slug}` | 启用/停用：`{enabled, expected_revision}` |
| `DELETE /api/langgraph/dear/skills/custom/{slug}?expected_revision=...` | 同后缀内部路由 | 删除当前自定义技能，校验并发 token，成功建议 204 |

`source` 只允许 `public/custom`。首期继续 ZIP＋base64。创建体 `{package_base64}`；更新体 `{package_base64, expected_revision}`。公共技能全部可列出/查看，不按内部用途或验收状态过滤；文件读取仍限定在目标技能目录。自定义所有写操作校验 scope，内置技能没有修改/启停/删除接口。

推荐元信息：`source/slug/name/description/revision/updated_at`、自定义 `enabled`；已有 `backend_verified/recommendable` 只作事实提示，不控制可见性或管理按钮。`revision` 是不透明并发 token，不支持用户历史版本读取。**因本期增加删除后同名重建，建议自定义每次变更新发随机 UUID token**，避免计数重置后旧请求误更新/删除重建的技能；内容 hash 单独保留用于快照。公共 revision 可用包内容 hash。字段已按此实现。

列表建议 `{items, capabilities, limits}`。`capabilities` 至少含 `can_read/can_write` 和 `custom_management_enabled`，写权限由平台按登录人真实权限计算；无需先查 thread capabilities。`limits` 明确上传压缩/解压大小、单文件与条目数。列表不返回正文；详情返回 `manifest:[{path,size,readable}]`，前端按路径构树；内容返回 `{path,content,revision}`，按 UTF-8 文本展示。业务状态不再返回 candidate/review/evaluation；扫描通过不等于端到端能力已验收。

沿用当前自定义包上限作为首期建议：压缩与解压各 1 MiB、单文件 256 KiB、100 条目、现有扩展名白名单。公共文件文本读取上限也定为256KiB，超过时明确 `readable=false/reason`，不静默截断。

建议错误：400 包/路径非法；401 未认证；403 无权限；404 不存在或不可见；409 同名冲突/修订冲突/功能关闭；413 超限；422 请求字段错误。扫描阻断建议 400＋`skill_security_blocked`，不落库。重复创建同名返回 409，引导显式更新；更新应先校验 expected_revision，即使上传内容相同也不绕过冲突检查。错误封装沿用平台现有 envelope，07 在定稿时提供真实示例。

## 5. 已实现数据模型与迁移

已新增 `dear_skills` 当前表：主键 `(tenant_id,project_id,user_id,slug)`，JSONB `document` 保存 revision、enabled、描述/文件/内容hash/来源及updated_at。不保留 candidate/active/revoked。数据库行/范围锁与条件更新保证 CAS、内容替换、启停/删除在同一事务完成。

建议按当前 scope 的技能数维持 50 条配额，替换现有“50 个版本”的限制；更新不占额外条数，实际配额已定为50条。规范化后的文件内容计算 hash，不用 ZIP 打包时间戳变化判定内容更新。

**Q7 已决定：不做旧技能数据兼容转换。** 删除原先 active 复制、candidate/inactive/revoked 映射、旧绑定接管、双写和旧版本无损回切方案。新技能能力按新模型初始化，不自动导入旧版本；需要的技能由新接口重新上传。

应用 schema 迁移仍要有版本管理、失败回滚和重复执行保障；“不兼容旧技能数据”不意味着不管理 schema，也不意味着清空记忆、外部任务、inbox 或 GraphHarbor 数据。对保留能力的已有表只做结构检查/明确接管，不承诺兼容任意历史形态；结构不符则报错，不默默 stamp。旧技能表退役、实际清理命令留在实施清单，尚未执行任何 DROP/DELETE，本次文档决策不是清库操作。

发布切换需处理旧程序和在途执行：新版本运行恢复遵守第 6 节，但不承诺恢复旧版本留下且缺少快照标识的工作；上线前排空或结束这些运行，不能暗中用当前技能替代。这里不建设历史数据恢复产品。

### 5.1 启用、停用、删除的具体语义（实现建议）

- 上传成功默认启用；更新已停用技能时维持停用状态，避免替换内容自动重新启用。启用/停用均需 scope 权限与 CAS，保留内容和详情；管理列表含停用项，新执行只装配 enabled 项。
- 删除移除当前技能记录，后续列表/详情不可见；再次上传同名视为全新技能，旧 revision 不得匹配。已实现真实删除当前记录，不新增软删除/回收站/历史恢复体系。
- 已开始或已中断待恢复的逻辑执行沿用原快照，因此停用/删除只影响之后的新执行。不能顺手删除仍被运行引用的快照；“删除技能”不是“立即取消现有运行”或“抹掉所有历史副本”。
- 前端删除前明确确认，后端/对话工具均要求写权限；对话启停/删除沿用 HITL。相关执行如需立即停止，使用既有取消运行能力。
- 上述作用对象是用户自己的自定义技能；公共全可见不增加公共写权限。接口已定稿：删除成功204，不存在404，详见07。

## 6. 运行快照与恢复边界

普通新运行：一次读取当前技能集并构建只读快照，整个运行复用；同会话下一次用户输入运行重新读取。主 Agent、子 Agent、文件工具、shell 都必须使用同一个 skills_root。

**Q6 已决定：继续被中断的工作、同一逻辑执行的重启/retry 沿用原快照；新用户输入开启新执行时读取当前启用技能。** 不能仅以新 HTTP 请求或新的 transport run_id 判定新工作。已使用官方 execution_info.task_id 标识首次装配节点，快照引用由 runtime-service 的私有graph state承载并由既有checkpoint持久化；不向 GraphHarbor 新增技能字段、技能表或技能专用 hook，也不预建第二套 run 数据库。

复用快照需把内置公共资源标识纳入 key，防止服务升级后复用混合旧公共技能。空自定义集不应误沿用此前 workspace 对象中的旧路径。损坏/缺失快照应重建相同内容或明确拒绝，不能退回当前内容伪装成功。快照清理不得删除活跃/待恢复运行引用的目录；首期沿现有持久工作区生命周期保留，不新增自动清理服务。

## 7. 开发顺序与验证计划

实施任务已完成；实际验证结果见第9节。分批避免先退役旧接口再补契约；按 README 先执行 P1/P2，P3/P4 各自满足阶段条件。

- [x] **最高 · P0：** 在已批准范围内核实并定稿实际契约、旧调用方切换及恢复落点；不重复请求迁移选型批准。
- [x] **最高 · P1：** 完成当前技能存取、公共目录与数据库迁移/连接收口。
- [x] **最高 · P2：** 完成两服务 HTTP、委托与权限链路。
- [x] **最高 · P3：** 完成运行快照、工具、权限清单和内置指令适配。
- [x] **最高 · P4：** 完成调用方核对及旧契约退役、关联能力回归与应用迁移验证。
- [x] **最高 · P5：** 交付实际契约、后端验证证据及前端接入/验收清单。

| 阶段 | 开发交付 | 依赖与出门条件 | 状态 |
|---|---|---|---|
| P0 定稿 | 核实接口与恢复工程细节、旧前端切换安排 | 已批准方向不重审；P3/P4 前完成对应阶段核对 | **最高 / done** |
| P1 数据与目录 | 当前技能存取/启停/删除、全量公共目录、连接与应用迁移 | 新模型初始化、保留表边界及并发/隔离验证通过 | **最高 / done** |
| P2 HTTP 与委托 | Runtime 路由、网关端口/上游、项目授权、token 防越权 | 无会话的真实两服务读写链路和错误透传通过 | **最高 / done** |
| P3 执行与工具 | 当前技能快照装配、恢复、工具/权限/内置指令同步 | 运行更新隔离、恢复和对话导入验证通过 | **最高 / done** |
| P4 退役与回归 | 不再需要的旧技能接口下线；保留记忆；服务内部署接入 | 调用方及交接清单完整；记忆/外部任务/inbox 回归通过 | **最高 / done** |
| P5 交接 | 固化 07 的实际契约/样例/证据与限制 | 后端完成状态与前端待接入状态分别记录 | **最高 / done** |

### 测试落点与断言

| 编号 | 类型/文件 | 必须验证 | 状态 / 证据 |
|---|---|---|---|
| V01 | `apps/runtime-service/tests/services/dearflow_agent/test_p6_governance.py` | 保留全部记忆断言；旧冻结测试替换为当前记录、原子替换、CAS、scope 隔离；不能整文件删除 | **最高 / done**；见第9节 |
| V02 | `apps/runtime-service/tests/services/dearflow_agent/test_p6_governance.py`（已实现） | 公共目录与工具共享；可见/推荐分离；根 SKILL.md 和辅助文本、缺失/二进制/超限、symlink/穿越/编码路径 | **最高 / done**；见第9节 |
| V03 | `apps/runtime-service/tests/services/dearflow_agent/test_p6_governance.py`（已实现） | 创建/读取/更新；伪造身份拒绝；错误 operation/assistant/scope、read token 写入、旧 thread token 滥用 | **最高 / done**；见第9节 |
| V04 | `apps/runtime-service/tests/services/dearflow_agent/test_p6_governance.py`（已实现） | 两并发更新仅一成功；损坏/超限/扫描警告旧内容不变；并发创建、容量、重试与重启持久性 | **最高 / done**；见第9节 |
| V05 | `apps/platform-api/tests/test_runtime_gateway_skills.py`（已实现） | 登录/项目/Agent 授权、无会话请求、真实 can_write、路由/端口/响应字段和错误映射 | **最高 / done**；见第9节 |
| V06 | `apps/platform-api/tests/test_runtime_delegation.py`；`apps/runtime-service/tests/runtime/test_auth.py`、`test_platform_auth.py` | 双端新 operation 一致；技能 token 不可访问原生 runs/threads/workspace/terminal 或记忆 | **最高 / done**；见第9节 |
| V07 | `apps/runtime-service/tests/services/dearflow_agent/test_p6_governance.py` 快照测试及 `test_restart.py` | 同会话运行 1 使用 A，更新为 B 后运行 1 延迟读取仍 A，运行 2 使用 B；子 Agent/execute 同步；中断、重启、恢复按定稿规则 | **最高 / done**；见第9节 |
| V08 | `apps/runtime-service/tests/services/dearflow_agent/test_p6_governance.py`（已实现） | 新 schema 初始化、保留表结构核对、二次执行、迁移并发锁/失败重试、包内资源；不迁入旧技能版本，不修改 GraphHarbor 版本记录 | **最高 / done**；见第9节 |
| V09 | `apps/platform-api/tests/test_runtime_gateway_skills.py` | 真实 platform-api→Runtime→隔离 PostgreSQL：无会话导入→目录→正文→更新→冲突→越权拒绝，不使用 mock 替代此链路 | **最高 / done**；见第9节 |
| V10 | `apps/runtime-service/tests/services/dearflow_agent/test_skill_restart.py` | 创建会话并真实运行/文件工具读取，更新后同会话新运行读取新内容；模型结果仅作辅助，核心以实际文件/内容标识断言 | **最高 / done**；见第9节 |
| V11 | 现有 `test_p5_media.py`、`test_message_inbox_postgres.py`、记忆测试、平台旧 HTTP 矩阵 | 连接收口不破坏外部任务幂等/租约、记忆 CAS、inbox 消费；旧技能路径符合退役策略 | **最高 / done**；见第9节 |
| V12 | 部署产物与迁移失败演练 | wheel/镜像包含应用迁移资源，迁移失败阻止发布；事务失败回滚；不要求回切旧技能数据模型 | **最高 / done**；见第9节 |
| V13 | V03/V04/V05/V07 的启停/删除用例 | disabled 管理可见但不装配；重新启用；更新不改变停用状态；更新/启停/删除并发 CAS；删除后重建拒绝旧 token；跨 scope 拒绝；公共写操作拒绝 | **最高 / done**；见第9节 |
| V14 | 全量公共目录及运行隔离 | 实际所有有效内置 SKILL.md 都可列出/读取，包括 bootstrap/runtime-smoke；推荐标识不隐藏条目；运行 A 中停用/删除后 A 与其恢复仍读旧快照，新的 B 不再装配 | **最高 / done**；见第9节 |

以现有 pytest 为主，不引入新测试框架；Runtime PostgreSQL 测试必须显式配置隔离测试 DSN，不使用测试文件里的开发库默认值。集成测试带真实环境前置条件，缺配置如实记未执行，不把 skip 算通过。

实际命令、日期、隔离环境及结果见第9节；Runtime用pytest，平台沿用unittest，没有额外安装测试或类型检查框架。

前端测试由接手方按 07 执行；浏览器链路未验时项目保持“后端完成、前端待适配/验证”。性能只需在当前配额上验证列表不携带正文、读取有界、复用快照不重复复制；除非发现瓶颈，不另开通用性能工程。

## 8. Q1—Q7 最新决定与剩余细节

| 议题 | 推荐方案 | 状态及影响 |
|---|---|---|
| Q1 迁移工具与目录 | 技能业务及应用迁移归 runtime-service，不扩展 GraphHarbor 技能能力；核实证据见 3.4 | 已决定归属及具体方案：自有 Alembic、包内目录、独立版本表和入口；代码与验证均已完成 |
| Q2 旧接口切换 | 考虑调用方；不需要的旧接口直接下掉，不建设无用兼容层 | 已决定原则；前端当前仍调用旧接口，需明确接入切换安排，不能标成无调用 |
| Q3 扫描与对话工具 | 保留包校验、正则阻断、只读审查；去掉强制评估；首期不新增 AI 扫描服务；远端导入走同一规则 | 已决定；HITL、工具权限与沙箱继续有效 |
| Q4 停用/删除 | 增加用户自定义技能启用/停用和删除 | 已决定能力；CAS、默认启用与仅影响新执行等细节见 5.1 建议 |
| Q5 公共可见集合 | 全部内置技能可见，不设额外用途/验收可见性过滤 | 已决定；安全路径检查、身份授权不是可见性名单，不移除 |
| Q6 运行恢复 | 新输入使用当前启用内容；恢复同一逻辑执行沿用原快照 | 已决定语义；应用层私有graph state＋持久workspace引用已实现并验证 |
| Q7 存量迁移与部署范围 | 不做旧技能数据兼容转换/双写/历史模型回切 | 已决定不兼容；根级部署脚本范围未明确扩展，实际清理也未执行 |

迁移工具/目录/入口已批准，不再列为待决。后端实施已完成；旧前端切换、API最终schema和恢复落点已固化到07及实现记录。根级部署自动接入与前端实施标“延后”，能力/存量兼容等排除项标“不做”，总表见 README。本轮已实施旧技能接口退役；未清理实际库中的旧技能表或业务数据。

## 9. 2026-09-19 实际验证记录

执行人：Codex。**后端范围最高 / done；前端与浏览器 deferred。** 用户已人工批准并授权开发。
以下是实际执行记录，重复运行有覆盖交集，不把数字相加冒充独立用例总数。

### 环境与证据

- Runtime Python 3.13、PostgreSQL 17.11、本机 Docker 28.0.4 与既有 `runtime-agent-workspace:p5` 镜像。
- 测试显式传入 `RUNTIME_MESSAGE_TEST_DSN`，在本机 PostgreSQL `postgres` 数据库新建随机隔离 schema；测试后仅清理自己的 schema，没有改动开发业务表。
- 平台 HTTP 测试启动真实 loopback 平台与 Runtime 服务并连接隔离 PostgreSQL；用户身份/项目目录采用锁定 fixtures，授权拒绝另有真实 policy 路径测试，不宣称做过生产登录或浏览器验证。
- 运行恢复测试使用真实 PostgreSQL checkpointer、跨进程重建图、真实 Docker 文件工具；模型为确定性工具调用 fixture，不访问付费模型，不把模型描述当文件证据。

| 执行组 | 实际结果 | 覆盖 |
|---|---|---|
| Runtime：test_skill_restart（三种变更）＋test_p5_media（DEAR_P5_DOCKER=1）＋test_p6_governance＋test_agent＋test_auth＋test_platform_auth | **56 passed**，257.76s | 更新/停用/删除、中断与进程重启、下一输入、容器执行、记忆/外部任务和权限 |
| Runtime：补充后的 test_p6_governance | **14 passed**，56.14s | 并发创建/更新、50条容量、公共名字冲突、非法包原内容不变、公共文本边界、迁移幂等与失败回滚 |
| Runtime：恢复＋技能＋inbox 回归 | **35 passed, 1 skipped**，94.43s | inbox消费/幂等/租约及旧表接管；skip 为既有付费模型探针，不计通过 |
| Runtime：子 Agent 只读文件工具恢复＋迁移专项 | **3 passed, 15 deselected**，23.45s | 父任务中断后更新，重建图的子 Agent 仍读取原快照；迁移幂等与失败回滚 |
| 平台：test_runtime_gateway_skills | **2 passed**，55.05s | 所有技能路由匿名/外部用户拒绝；两服务 HTTP CRUD/冲突/隔离/能力/Runtime进程重启 |
| 平台：test_runtime_delegation | **12 tests OK** | 新 operation 签发与白名单 |
| 平台：test_runtime_gateway_http_matrix | **1 matrix OK**，10.78s | 原网关接口授权和路由清单，记忆接口保留 |
| 平台：test_runtime_gateway_sdk_adapters | **15 tests OK** | 上游路径、状态/错误映射与已有资源回归 |
| wheel 构建及安装资源检查 | **通过** | 新迁移 Python 资源包含；旧散落 SQL 不再打包 |
| 从 wheel 解包产物执行 `python -m runtime_service.db upgrade` 两次 | **通过** | 隔离 schema 初始化及重复运行；独立版本表等于 0001_application |
| 两份服务 Compose 迁移依赖检查 | **通过** | 两条命令按顺序运行，API/Worker 等待迁移成功 |
| 改动 Python 语法编译 / `git diff --check` | **通过** | 已检查33个变更Python文件；无项目统一ruff/mypy配置，不虚报类型检查通过 |

最终边界补测：ZIP目录路径拒绝、容量、公共文本、迁移等 **5 passed, 9 deselected**（28.25s）。

### 复现命令

先显式设置隔离测试连接 `RUNTIME_MESSAGE_TEST_DSN`；不要使用生产连接。测试自身按随机 schema 隔离。
在 `apps/runtime-service`：

```bash
DEAR_P5_DOCKER=1 .venv/bin/python -m pytest tests/services/dearflow_agent/test_skill_restart.py tests/services/dearflow_agent/test_p5_media.py tests/services/dearflow_agent/test_p6_governance.py tests/services/dearflow_agent/test_agent.py tests/runtime/test_auth.py tests/runtime/test_platform_auth.py -q --tb=short
.venv/bin/python -m pytest tests/services/test_message_inbox_postgres.py -q --tb=short
uv build --wheel --out-dir /tmp/runtime-skills-wheel
```

在 `apps/platform-api`（该服务既有环境用 unittest，未安装新测试框架）：

```bash
.venv/bin/python -m unittest discover -s tests -p "test_runtime_gateway_skills.py" -q
.venv/bin/python -m unittest discover -s tests -p "test_runtime_delegation.py" -q
.venv/bin/python -m unittest discover -s tests -p "test_runtime_gateway_http_matrix.py" -q
.venv/bin/python -m unittest discover -s tests -p "test_runtime_gateway_sdk_adapters.py" -q
```

### V01—V14 实际落点

| 编号 | 完成依据 |
|---|---|
| V01 | test_p6_governance 保留记忆回归及当前技能 CAS/scope/recreate |
| V02 | test_skill_http_catalog_and_writes 全目录逐项读取；test_public_catalog_text_boundaries |
| V03 | Runtime真实签名HTTP：无token、错误operation、read写入、跨project、额外身份字段拒绝 |
| V04 | test_skill_capacity_create_race_and_rejected_updates；并发update仅一成功，50条上限仍可更新 |
| V05 | 平台新七类路由、真实拒绝路径、无thread、can_write与Agent授权；两服务HTTP |
| V06 | 双端operation测试，技能token原生Server拒绝；HTTP operation隔离 |
| V07 | 三种变更的跨进程恢复＋子Agent文件工具原快照；真实容器执行 |
| V08 | migration并发/重复/保留memory/不建旧技能表/独立version表；失败回滚与修正后重试 |
| V09 | test_real_http_crud_restart_and_permissions：真实两服务网络＋PostgreSQL，含Runtime重启 |
| V10 | 新输入→真实图→中断→技能更新→进程重启恢复→实际脚本读A→同会话新输入读B；没有浏览器或付费模型验收声明 |
| V11 | 记忆、P5外部任务、inbox、平台旧HTTP矩阵与SDK适配回归 |
| V12 | wheel包含迁移且CLI可运行；迁移失败事务回滚；Compose依赖门禁。生产镜像发布未执行 |
| V13 | enabled/CAS/删除重建/隔离；更新停用项保持状态；并发修改统一scope锁 |
| V14 | 全量公共目录；更新/停用/删除均不改变恢复内容；新执行读取当前集合 |

### 已修复的问题与边界

1. Docker未启动/重启中曾返回125，用户重启后真实容器与跨进程恢复验证通过；失败结果未记为通过。
2. 原inbox测试在已迁移schema上人为删列再期望每次initialize修复；调整为真实旧库场景（无应用版本表）后接管通过。Alembic不承担已stamp库任意结构破坏后的自动修复。
3. 直接图测试提供run_id时收件箱需要checkpointer；子进程测试显式接入同一个真实PostgresSaver，未改业务逻辑规避测试。
4. 公共frontmatter名字可能与目录名不同，上传检查同时保护二者，防止同名覆盖模型可见技能。
5. migration目录被旧.gitignore全局忽略，已增加精确Python资源例外；不包含__pycache__。

**延后 / deferred：** 前端代码、浏览器完整用户链路、根级部署自动接入与生产发布；未跑的既有付费模型探针。
**不做：** 旧技能数据转换/双写/历史回滚、公共写接口、用户多版本、GraphHarbor技能扩展。
没有承诺删除会清理在途快照；持久工作区是恢复前置条件。容量以50条当前技能及每包1MiB约束，未另做通用压力测试。
