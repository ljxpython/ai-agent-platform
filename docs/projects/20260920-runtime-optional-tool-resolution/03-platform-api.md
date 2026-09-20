# 03 — 平台后端：移除工具授权，保留身份与目录展示

## 目标

所有 execution delegation 与 Run 校验不再读取工具 Catalog/旧项目工具策略。平台从独立禁用记录计算用户权限，Runtime 执行；模型治理和资源入口鉴权保留，目录只影响展示。

## 方案设计

### 1. 按文件实施

以下路径相对 `apps/platform-api/src/platform_api/`。

| 文件 / 函数 | 删除或修改 | 保留/新增 |
|---|---|---|
| modules/runtime_policies/application/service.py / build_delegation_policy() | tools 与 tool_policies 查询、allowed_tool_names、runtime_permissions、工具参与 revision | 模型 policy；按真实用途命名，测试不读工具表 |
| 同文件 list_tool_policies()/upsert_tool_policy() | 删除方法 | model/graph 原有 CRUD |
| modules/runtime_policies/presentation/http.py | 移除 tools GET/PUT | models/graphs 路由 |
| modules/runtime_policies/application/contracts.py、domain/models.py、两层 __init__.py | 移除 RuntimeToolPolicy*、UpsertRuntimeToolPolicyCommand | 非工具契约 |
| modules/runtime_policies/infra/sqlalchemy/models.py、repository.py | 移除 ProjectToolPolicyRecord、list/upsert_tool_policy | 模型/graph policy；旧表退役及新表初始化见 05 |
| core/security/tokens.py / create_runtime_delegation_token() | 移除工具白名单参数 | 新版本、必填 tool_overrides/tool_policy_version、经核实的身份与原 scope/模型/有效期 |
| modules/runtime_gateway/presentation/http.py / delegation_headers_factory() | 移除目录权限拼装 | 按确定的 actor/project/graph 计算拒绝并集并签发；每条 operation 先执行既有授权 |
| modules/runtime_catalog/application/service.py / _runtime_headers() | 同步新的 token 签发，移除 Catalog 自身读取依赖 | 能在空工具目录下获取 Runtime 声明 |
| modules/runtime_gateway/application/service.py / _assert_runtime_options_allowed() | 工具 catalog/policy 预检查整个分支 | 模型检查；_validate_run_options() 拒绝已退役工具字段 |
| core/runtime_contract.py | tools/enable_tools 公开字段、schema、旧字段搬运 | 新 Context schema/hash；不默默吞旧字段 |
| modules/agents/application/service.py / _normalize_agent_context() | 删除 tools 支持 | 模型/采样/模式验证；旧工具字段直接拒绝，不转换已存数据 |
| modules/audit/http_resolution.py | 删除已退役工具策略操作审计映射 | 目录读取/刷新、Agent 与真实业务动作审计 |

### 2. 目录设计

继续复用 `GET /api/runtime/tools` 与管理员 `POST /api/runtime/tools/refresh`，不增加自动同步服务。工具项推荐包含 tool_key、name、description、source、graph_ids；runtime 声明版本作为展示元信息，缓存同步时间保留。同名跨 Agent 项可用 graph_ids 聚合，授权判断始终按 graph+name，不依赖聚合项。

由现有 raw_payload_json 承载新增展示字段，避免为了图归属增加表；修改 runtime_catalog 的 application contracts/domain/infra 映射及 Web 类型。旧 permissions 信息若仅用于授权则删除，对其原有消费逐一清理。

`_normalize_tool_items()/refresh_tools()` 严格校验完整响应再事务更新；坏响应不能归空清除目录。合法空目录可以成为展示快照，明确返回 count=0，不影响运行。保留既有刷新访问控制，无匿名端点或伪造管理员身份。

### 3. 新禁用规则功能（核心新增）

复用现有 runtime_policies 模块组织，新增少量类/方法，不建独立权限服务：

- `infra/sqlalchemy/models.py` 新增 `RuntimeToolRestrictionRecord`（拟），表 `runtime_tool_restrictions`。字段：id、project_id、graph_id、subject_type(project/user)、subject_id、tool_name、reason、created_by、created_at。项目行 subject_id 为 project_id，用户行为 user_id；tenant 从项目关系解析。唯一约束 `(project_id, graph_id, subject_type, subject_id, tool_name)`；不存在即无额外拒绝，不存 true，不引用 Catalog。
- `infra/sqlalchemy/repository.py` 新增 list/add/delete restriction 及按项目+graph+user 查询拒绝并集。以行删除解除某一条来源；另一来源仍生效。查询失败抛错，不签空权限。
- `application/contracts.py` 新增创建/展示 DTO；`application/service.py` 新增规则管理与 `resolve_tool_overrides(actor, project_id, graph_id)`。返回规范化 false map 和作用域内容哈希，禁止查工具 Catalog。
- `presentation/http.py` 新增 `GET/POST /api/projects/{project_id}/runtime-policies/tool-restrictions`、`DELETE .../tool-restrictions/{id}`。POST 接收 graph_id、subject_type、subject_id、tool_name、reason；不接收任意布尔值。管理鉴权复用 PROJECT_RUNTIME_WRITE，读取按已有项目治理权限；新增明确审计事件。
- 创建例外必须校验项目成员、graph 属于部署声明及工具名称；调用 Runtime 声明接口验证，不从可能过期的 Catalog 授权。上游不可达时管理写入失败。规则读取签发不发 Runtime 网络请求。
- 工具重复添加幂等或明确冲突，跨项目 ID 删除拒绝；限制名称长度、每次请求形状和签发总数量/字节，超限显式失败，不能截断禁用集合。具体上限由现有代理 header 预算验收确定。
- 第一版不建角色授权、允许覆盖或规则优先级；项目全员禁用和用户禁用取并集，管理员身份也不隐式绕过。
- 通用只读目录 token 没有 graph 时必须是限定 read operation，携带明确空 map；任何执行或副作用 scope 必须绑定具体 graph 并重新求值。不能把通用 read token 升级为 run-create。

### 4. 身份与业务入口不能弱化

平台仍负责 project/graph/agent/thread 可访问性，以及读写操作与会话归属检查。禁用根据真实 actor.user_id 和项目/graph 计算，不从 role 首项推断。代码核查所有权限字段消费者，固定填充的 project.runtime.write 不能当有效权限来源；只在确认用途后修正，避免无关 IAM 重构。

新的 token 只在完成对应 IAM 检查与 restriction 查询后签发；scope 与 actor/project/graph/thread 绑定。禁用决定由 Platform 制定，Runtime 验签执行，前端传同名字段必须拒绝。模型禁用、模型凭据和模型连接签发继续原有安全边界。

### 5. 数据退役

按用户批准直接退役旧工具策略，不导出或转换旧 false、排序与备注。新 restriction 表空初始化，管理员重新配置。只保留必要 schema revision，不写旧业务迁移脚本，不创建兼容 Agent；切换见 05。

## 任务拆分

- [x] B1：冻结新版签发与 Runtime 鉴权契约，完成 token 三处生产调用者及测试签发器升级。
- [x] B2：拆除 policy/Gateway 执行路径上的工具 Catalog 依赖，保留模型策略。
- [x] B3：退役工具策略 API/service/domain/repository/ORM 与相关审计项。
- [x] B4：统一 Agent Context、run.start、SDK 路径，新旧字段行为明确。
- [x] B5：更新目录展示映射及严格刷新验证。
- [x] B6：新增 restriction 表/CRUD/主体校验/审计/拒绝并集求值，接入每个有副作用 scope 的签发。
- [x] B7：补身份、scope、目录无关性、规则失败拒绝、旧接口退出及新表初始化测试。

## 验证要求与记录

- [x] 将工具目录 repository 调用设为测试失败陷阱：普通 Run 签发和模型策略仍成功。
- [x] 空目录可以刷新；坏响应不更新快照；目录过期不影响运行授权。
- [x] 旧工具策略 GET/PUT 返回路由不存在，不能仍写数据；模型/graph CRUD 正常。
- [x] 错项目/线程/Agent、只读身份写操作、伪造授权请求被拒绝。
- [x] test_runtime_catalog_delegation.py、test_runtime_gateway_runtime_contract.py、test_agent_single_table.py、test_runtime_gateway_http_matrix.py 与相应 IAM 测试通过。
- [x] token 缺新版本/含旧白名单/错误 scope 均被新版 Runtime 拒绝。
- [x] 项目+用户禁用并集、管理员不越过、删除某一来源不解除其他来源；DB 异常不签 `{}`；用户不能改写自己的权限。

记录：后端实现和隔离库 schema 测试完成，已有业务数据库未变更；测试结果见 [06](06-validation-and-delivery.md)。

## 状态

done：后端开发与本轮验证完成；按 01 契约与 05 直接切换。


2026-09-20：规则存储直接复用该模块 application service 的 SQLAlchemy 会话与现有 session_scope；没有为单一查询额外建 repository 抽象。管理读取与写入都要求 PROJECT_RUNTIME_WRITE（当前 admin/editor），executor 拒绝。服务账号只取项目级规则。详细结果见 [06](06-validation-and-delivery.md)。
