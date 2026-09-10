# 权限标准

权限来源为可信[ActorContext](../../src/platform_api/core/context/models.py)与[IamPolicyEngine](../../src/platform_api/modules/iam/application/policies.py)。认证中间件加载身份，请求体里的user_id/project_id不能作为授权证明。

## 角色与边界

平台角色：`platform_super_admin`、`platform_operator`、`platform_viewer`。项目角色：`project_admin`、`project_editor`、`project_executor`；数据库存admin/editor/executor，通过roles.py转换。

| 项目权限 | admin | editor | executor |
| --- | --- | --- | --- |
| 成员读取、公告读取、Agent读取、Runtime读写 | 是 | 是 | 是 |
| 审计读取、公告写入、Agent写入 | 是 | 是 | 否 |
| 成员写入 | 是 | 否 | 否 |

平台权限以PLATFORM_PERMISSION_MAP为准：super_admin拥有登记的平台权限；operator执行允许的用户资料/状态、目录刷新、公告、配置、服务账号等操作；viewer读取允许的平台资源。角色管理、凭据重置、项目创建/修改/接管、服务账号项目授权由显式权限控制，不能概括成operator能管理所有资源。

项目权限独立判定。平台super_admin也必须拥有项目角色才能访问项目内容；接管是显式治理操作，不是网关隐式绕过。新增权限先登记PermissionCode及映射，未注册权限默认拒绝并返回内部错误。

## 请求流程

1. 验证平台用户token或服务账号token，加载当前身份、状态和角色。
2. 项目请求解析 `x-project-id`；路径携带项目的业务接口按各自契约解析。
3. service调用policy engine，按钮显隐不能代替授权。
4. 网关额外检查Thread项目归属。新启动/resume检查当前Agent、Graph、模型和工具授权，历史Thread不能绕过禁用与撤权。
5. Runtime委托按主体、项目、operation和必要执行上下文限定；业务授权属于Platform/Runtime，GraphHarbor保持通用。

服务账号默认通过 `x-platform-api-key` 接入；账号状态、令牌状态/过期与项目grant均参与身份加载。它不是用户JWT，平台角色不能替代项目grant，密钥不得放query string。

## 命名与验证

产品称Agent，权限枚举仍为 `project.assistant.read/write`，不要自行增加第二组权限。网关使用 `project.runtime.read/write`。

401为未认证，403为权限不足，缺项目scope为400。资源不存在和生命周期错误按用例处理，不能将所有404等同于越权。

[测试目录](../../tests/)中的test_security_boundaries.py、test_iam_project_governance.py、test_service_account_project_grants.py、test_runtime_gateway_http_matrix.py与test_run_requests.py覆盖关键边界。新增接口检查未登录、角色不足、跨项目及当前撤权。当前权限枚举没有Operations权限。
