# Platform API V2 权限标准

这份文档把 `platform-api-v2` 的权限模型钉死，后面谁再把“项目 admin 当全局 admin”这种骚操作写回来，谁就该先回来看这份文档。

## 1. 权限目标

权限系统必须同时满足 4 个目标：

- 平台级和项目级权限严格分离
- 权限判定可测试、可复用、可审计
- API handler 不直接堆硬编码角色判断
- 后续接入组织、SSO、service account 时不用推翻重来

## 2. 资源分层

### 2.1 平台级资源

典型资源：

- 用户
- 全局审计
- 平台配置
- 全局 catalog refresh
- 运维类 operation

这类资源只能由平台级角色控制。

### 2.2 项目级资源

典型资源：

- project
- project member
- assistant project policy
- testcase project data
- project audit
- runtime gateway project scope

这类资源只能由项目级角色控制。

### 2.3 铁律

- 项目级角色永远不能隐式提升成平台级角色
- 平台角色也不能跳过项目归属校验直接操作项目资源
- handler 不允许自己拼 `if role == "admin"` 这种散装逻辑

## 3. Actor 模型

后续所有权限判定统一基于 `ActorContext`：

- `user_id`
- `subject`
- `platform_roles`
- `project_roles`

来源规则：

- 身份信息由 `identity` 模块解析
- 项目归属由 `projects` 模块或请求上下文提供
- policy engine 只消费 `ActorContext`，不依赖 FastAPI `Request`

## 4. 默认角色基线

### 4.1 平台角色

- `platform_super_admin`
- `platform_operator`
- `platform_viewer`

### 4.2 项目角色

- `project_admin`
- `project_editor`
- `project_executor`

## 5. 权限编码规范

权限码统一使用：

`{scope}.{resource}.{verb}`

示例：

- `platform.user.read`
- `platform.user.write`
- `platform.audit.read`
- `platform.operation.read`
- `platform.operation.write`
- `platform.config.read`
- `platform.catalog.refresh`
- `project.member.read`
- `project.member.write`
- `project.operation.read`
- `project.operation.write`
- `project.runtime.read`
- `project.runtime.write`
- `project.testcase.read`

禁止直接拿角色字符串作为“权限”。

## 6. 判定流程

统一流程：

1. 先确认 actor 是否已认证
2. 判断权限码属于平台级还是项目级
3. 如果是项目级，必须先拿到当前 `project_id`
4. 用 policy engine 给出 allow/deny
5. deny 时抛显式错误码，并落审计

## 7. 代码落点

当前统一落点：

- `app/modules/iam/domain/roles.py`
- `app/modules/iam/application/policies.py`

要求：

- 角色枚举在 `domain`
- 权限码与判定策略在 `application`
- handler 只调用 `policy.require(...)`

## 8. 测试矩阵

权限测试至少覆盖：

- 未登录访问平台接口
- 项目 admin 访问平台用户管理
- 平台 operator 访问项目成员写接口
- project_editor 访问项目写接口
- project_executor 访问只读项目接口
- 缺 `project_id` 时访问项目权限接口

## 9. 未来扩展口径

后面即使接入这些能力，也不能改坏当前模型：

- tenant / organization scope
- service account
- API key
- OIDC / SSO claim mapping
- policy cache

允许扩展 scope，但不允许把 scope 混成一锅。
