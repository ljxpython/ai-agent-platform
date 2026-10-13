# 权限标准

权限来源为可信[ActorContext](../../src/platform_api/core/context/models.py)与[IamPolicyEngine](../../src/platform_api/modules/iam/application/policies.py)。认证中间件加载身份，请求体里的user_id/project_id不能作为授权证明。

## 角色与边界

平台角色：`platform_super_admin`、`platform_operator`、`platform_viewer`。项目角色：`project_admin`、`project_editor`、`project_executor`；数据库存admin/editor/executor，通过roles.py转换。

| 项目权限 | admin | editor | executor |
| --- | --- | --- | --- |
| 成员读取、公告读取、Agent读取、Runtime读取/执行 | 是 | 是 | 是 |
| 知识读取、知识上传（project.knowledge.read/upload） | 是 | 是 | 是 |
| 审计读取、公告写入、Agent写入 | 是 | 是 | 否 |
| 成员写入、Runtime管理写入（project.runtime.write） | 是 | 否 | 否 |

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

### 已采集 Agent 用量查询（2026-10-11 方案批准）

`platform.usage.read` 映射 `platform_super_admin/platform_operator`，只读当前 tenant 有效项目的数字统计与安全目录标签；`platform_viewer` 不授予。`project.usage.read` 映射 `project_admin/project_editor`，服务账号需当前有效凭据与对应项目 grant；`project_executor` 不新增此权限。

项目聚合以路径项目为准，平台查询显式集合最多200；SQL前后重新加载身份/授权/有效项目。聚合保留有效项目中已删除 Thread 曾发生的消费，不授予私有 Thread/文件/模型凭据访问。Runs候选页单次最多200，按现有当前Thread ACL/ready状态过滤，manager接管保留审计；公开游标认证加密且绑定身份/筛选，有效15分钟。Run删除过滤依现有成功删除审计，直接引擎删除/审计丢失不能由此证明。

三个 GET、参数和真实验证见 [Token 看板接口](../../../../docs/projects/20261011-token-usage-dashboard/03-platform-api-and-security.md)。接口已实现供小规模联调，容量 B01 尚未通过，不能据此开放正式发布。

产品称Agent，权限枚举仍为 `project.assistant.read/write`，不要自行增加第二组权限。网关使用 `project.runtime.read/execute/write`；runtime.write不等于启动Agent。上表按现有代码区分执行与管理，不扩大executor权限。

知识面板的四GET要求当前 `project.knowledge.read` 与active项目；MCP任务读取额外核对原Run及Thread read ACL。明确共享上传要求 `project.knowledge.upload`、Thread comment ACL、精确工具/Run与非Plan/offload来源；后台start/activate重新检查原主体、服务账号credential、成员与项目，不依赖Thread继续存活。服务端scope/token不能代替成员授权，前端capability不能代替当前权限。细节与已锁定授权测试见[成员上传专项](../../../../docs/projects/20261012-project-member-knowledge-upload/README.md)。

401为未认证，403为权限不足，缺项目scope为400。资源不存在和生命周期错误按用例处理，不能将所有404等同于越权。

[测试目录](../../tests/)中的test_security_boundaries.py、test_iam_project_governance.py、test_service_account_project_grants.py、test_runtime_gateway_http_matrix.py与test_run_requests.py覆盖关键边界。新增接口检查未登录、角色不足、跨项目及当前撤权。当前权限枚举没有Operations权限。
