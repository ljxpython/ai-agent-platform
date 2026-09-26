# Delegation JWT v2 - 执行方案

> 本期方向、简化生命周期已批准；本文将现有契约和平台侧修正具体化。实现未开始。本方案不升级鉴权架构。

## 1. 范围和实现选择

只改platform-api签发输入校验、两个签发入口的一致性及平台侧测试。Runtime/GraphHarbor所有文件、配置、依赖、数据库不改。生产路径不导入runtime_service包，不建共享schema或新服务。

沿现有create_runtime_delegation_token签发v2；Gateway和Catalog分别调用它，不合并两个业务工厂。双端测试放API测试目录，以独立子进程调用Runtime现有校验器，避免混装依赖。

本期不新增claim/operation、轮换、算法升级、v3、后台刷新或SSE持续重鉴权。追踪专项负责request_id/platform_trace_id来源与传播，本专项验证现有claim兼容性，不重复开发编号机制。

## 2. 源码入口与当前差异

以下路径相对仓库根目录；Runtime路径全部只读：

| 路径/函数 | 职责 |
|---|---|
| apps/platform-api/src/platform_api/core/security/tokens.py::create_runtime_delegation_token / _runtime_names / empty_runtime_context_hash | 唯一委托签发器、名称约束、空context摘要 |
| apps/platform-api/src/platform_api/config.py::Settings | TTL默认60秒，配置范围10—300秒；委托独立secret/issuer/audience/kid |
| apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py::get_runtime_gateway_service / delegation_headers_factory | 初始read与按动作签发；当前已传service account credential_id |
| apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py | 按现有项目/Thread权限校验后使用委托；提交、审批、取消、重连入口 |
| apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py::_runtime_headers | 独立read签发；当前缺credential_id传递，保留用户已有修改 |
| apps/platform-api/src/platform_api/modules/runtime_policies/application/service.py::build_delegation_policy | 已有非空模型集合；无模型时使用platform:no-enabled-model哨兵 |
| apps/platform-api/src/platform_api/modules/identity/actors.py::load_user_actor / load_service_account_actor | 重新加载当前用户、服务账号、凭据状态及项目grant |
| apps/platform-api/src/platform_api/modules/runtime_catalog/presentation/http.py::authorize_runtime_threads | Runtime签名回查Thread ACL，缺凭据的service account拒绝 |
| apps/runtime-service/src/runtime_service/runtime/auth.py::verify_delegation_claims / _parse_scope | JWT/claim/scope验证 |
| apps/runtime-service/src/runtime_service/runtime/resolver.py | principal/policy名称规则、context摘要 |
| apps/runtime-service/src/runtime_service/auth/platform.py::authenticate / deny_image_scope_on_server_resources | HTTP认证、原生资源operation和Thread回查 |
| apps/runtime-service/src/runtime_service/middlewares/runtime_config.py::_resolve / _check_scope | worker执行时的受信快照、context与实际资源检查 |
| apps/runtime-service/src/runtime_service/http/ 及 webapp.py | 自定义资源的operation约束，见第4节 |

2026-09-26静态确认的签发器差异：允许空allowed_model_ids；principal仅检查strip后非空，未完整匹配Runtime名称约束；permissions逐项直接strip，缺类型及名称检查；scope可保留非字符串assistant/thread或归一化后的空字符串；tool_policy_version可为空白，两个policy版本缺100000字符上限。修正均限定签发端，使生成值属于现有Runtime可接受集合。策略构造器已有模型哨兵，不新增模型fallback。

## 3. Claim矩阵与平台修正规则

“名称”指字符串、1—128字符、ASCII可打印、无空白且无首尾空白；复用现有_runtime_names实现检查，单值取单元素列表结果即可，不建校验框架。“文本”指字符串、strip后非空、最多100000字符。

| claim/header | 平台来源/输出 | 现有Runtime校验与本期要求 |
|---|---|---|
| header.alg / typ | 固定HS256 / JWT | 真实authenticate使用默认HS256；typ不作为权限条件。不改算法 |
| header.kid | 配置的非空kid | Runtime不按kid选钥、不匹配kid。有效签名下缺失/不同kid不能宣称必拒绝；无轮换支持 |
| type | runtime_delegation | 必需，精确相等 |
| delegation_version | 整数2 | 必需，严格整数2，布尔值也拒绝 |
| sub | actor.user_id或actor.subject | 必需，名称规则；用户通常为用户UUID，service account为service-account:<UUID>。不接收客户端覆盖 |
| tenant_id / project_id / role | 平台上下文、授权项目、现有角色选择 | 必需，名称规则；role不在本期新增枚举或权限含义 |
| permissions | 现有工厂传[] | 必需数组，可空；签发保留既有strip、去空、去重、排序行为，但先检查容器和元素为字符串，再对输出做名称校验；不新增权限 |
| policy_version | 当前策略版本 | 必需文本；保留签发strip，补长度上限 |
| allowed_model_ids | 策略构造器模型集合 | 必需非空名称数组，唯一且排序；签发器拒绝空数组；保留既有无模型哨兵及运行前拒绝，不用任意模型填充 |
| tool_overrides | 现有工具限制 | 必需dict，最多128键，值只能是False，键符合名称规则，紧凑JSON编码最多4096字节；只收紧不能提权 |
| tool_policy_version | 当前限制版本或既有unscoped标记 | 必需文本；保留合法值，不新增strip语义，只补空白和长度验证 |
| iss / aud | 委托专用配置 | 平台总是发出；真实HTTP authenticate强制issuer/audience匹配。底层helper允许audience=None不代表HTTP关闭校验 |
| iat / nbf / exp | UTC整数秒，iat=nbf，exp=iat+配置TTL | iat/exp必需，nbf若存在校验；沿PyJWT现有行为不加leeway或新的Runtime TTL上限检查 |
| jti | 每次签发uuid4().hex | 平台始终生成；Runtime允许缺省，无jti撤销库/单次使用语义 |
| scope | 见第4节 | 必需；未知key拒绝；tenant/project与顶层一致 |
| context_hash | 保存的运行context摘要；非运行操作用既有空摘要 | 必需sha256:加64位小写hex；生成协议仍runtime-context/v4，不把request_id、JWT或授权字段放进去 |
| request_id / platform_trace_id | 追踪专项的内部上下文；非HTTP可省略 | 已支持的可选字符串，非空、原长度≤256、返回strip值。Runtime未要求32位；平台HTTP目标为32位，不改Runtime |
| credential_id | service account当前凭据UUID | 可选claim；存在时必须为UUID字符串且sub为service-account前缀。平台对所有service account签发要求携带；普通用户禁止带 |
| policy_tenant_id / policy_project_id | 平台不发 | Runtime允许的历史可选字段，存在时须与principal一致；测试覆盖，不主动增加 |
| 其他claim | 不发 | Runtime严格拒绝未知字段，即使声称“可选”也不天然兼容 |

补充输入行为：

- subject/tenant/project/role不strip后替换身份，只校验现值，非法统一ValueError，不暴露AttributeError/TypeError。
- permissions保留旧归一化语义，但字符串本身不能当数组逐字符迭代。
- scope仅允许tenant_id/project_id/assistant_id/thread_id/operation五键；先检查Mapping，None省略，其余必须字符串，沿旧行为strip，strip后不得为空。tenant/project必需且与顶层精确相等；operation按固定23项。无需给Runtime未限制的scope资源字符串另造128上限。
- credential_id先检查字符串再UUID解析；service account缺credential_id在签发端拒绝，用户带credential_id拒绝。账号/凭据归属及激活状态仍由Actor加载和现有回查负责，不在纯签发器查数据库。
- secret至少32 UTF-8字节，保持现有要求。issuer/audience/kid非空配置，不把平台access/refresh的多密钥_decode机制套给委托。

## 4. Operation、scope与资源矩阵（23项）

全部scope含tenant_id/project_id/operation并与顶层一致。表内是目标资源调用约束，不把“JWT结构校验接受”误作“任何端点都授权”。除read、thread-create/reconcile/edit/delete五项外，签发/基础校验均要求assistant_id。

| operation | assistant_id / thread_id | 目标与现有授权边界 |
|---|---|---|
| read | 按资源；读assistant时绑定；Thread初始read允许未绑定 | Thread读取/搜索须具体目标并回查ACL；assistant read只允许绑定ID或其既有uuid5映射；assistant search仅平台operator/super_admin |
| thread-create | assistant可省；绑定预留Thread | 原生threads/create，Thread必须与scope相等；pending owner回查，仅user |
| thread-reconcile | assistant可省；绑定预留Thread | 原生threads/read，pending owner对账，仅user |
| run-create | 实际graph/assistant；绑定Thread | threads/create_run；新提交comment权限，command.resume为approve；worker再验实际资源及context_hash |
| thread-edit | assistant可省；绑定Thread | threads/update；不得携带run_id冒充Thread修改；edit权限 |
| thread-delete | assistant可省；绑定Thread | threads/delete；不得以run_id替代；delete权限 |
| run-cancel | 实际assistant；绑定Thread | threads/update且目标run_id必需；现有edit权限；ACK不代表终态 |
| run-delete | 实际assistant；绑定Thread | threads/delete且目标run_id必需；delete权限 |
| message-enqueue | reference_agent/showcase_demo/dearflow_agent；绑定Thread | webapp.py enqueue_message；目标Run及消息授权沿既有规则 |
| message-read | 实际assistant；绑定Thread | webapp.py list_messages；既有读取还接受message-enqueue，记录现状、不扩权限 |
| image-upload | showcase_demo/dearflow_agent；绑定Thread | http/images.py；精确operation、Thread匹配、write_file限制 |
| image-read | 同上 | http/images.py；read_file限制 |
| workspace-file-upload | 支持workspace的assistant；绑定Thread | http/documents.py；write_file限制 |
| workspace-file-read | 同上 | http/documents.py及现有workspace入口；read_file限制 |
| workspace-fork | 现有fork目标assistant/Thread | http/documents.py::_auth_scope及workspace路由；read_file和write_file限制；沿既有源/目标校验 |
| terminal-read | showcase_demo/dearflow_agent；绑定Thread | http/terminal.py::_owner；execute限制、终端owner隔离 |
| terminal-write | 同上 | 同上；closing沿已有释放例外，不扩大执行权 |
| dear-skills-read | dearflow_agent；thread必须省略 | http/dear_skills.py::authorize；tenant/project/user身份域、具体工具限制 |
| dear-skills-write | 同上 | 同上且功能开关允许；不擅自将service account映射为其他用户 |
| dear-memory-read | dearflow_agent；thread必须省略 | http/dear_memory.py::authorize；平台明确仅user本人；search_memory限制 |
| dear-memory-write | 同上 | 平台仅user本人；manage_memory限制 |
| dear-governance-read | dearflow_agent；绑定Thread | http/dear_governance.py::authorize；平台既有个人记忆/共享Thread限制及search_memory |
| dear-governance-write | 同上 | 同上，manage_memory限制 |

原生资源auth.on只接受read、thread-create/reconcile/edit/delete、run-create/cancel/delete这8类operation；其余15类不能借自定义token访问原生资源。所有操作都保留平台项目权限、Thread ACL及工具策略，不新造role→operation授权表。

JWT scope没有run_id字段。取消/删除目标Run由服务端实际路径/请求和现有Thread关系确定，不能新增run_id claim冒充更细粒度绑定。

### 已知跨端点限制

webapp.py的消息入口在部分路径会将message-read/enqueue委托用于内部GET原生Run，而原生auth.on拒绝这类operation。该静态冲突需在消息子调用测试中复现；不得扩大为read权限、签“双用途”token或关闭校验来凑通过。若当前部署确认受影响，记录为Runtime侧既有阻塞；本专项不改Runtime，JWT平台修正可独立交付，但全operation真实端点验收不能标全部通过。

## 5. 用户与service account

- user：sub取actor.user_id；不带credential_id。当前用户状态/项目成员权限在平台重载；Thread回查继续核对当前用户和ACL。
- service account：sub取既有service-account:<UUID>，credential_id取当前已认证凭据ID。Gateway已有传递，Catalog补齐同样传递；缺失不发token。
- Thread回查通过load_service_account_actor检查账号active、凭据归属/active/到期/revoked_at、当前项目grant。不把仅验证UUID格式当完成权限复核。
- Thread创建/对账的pending owner规则仅user；个人memory平台仅user。skills等其他能力按现有策略，不因本专项额外禁止或扩大service account。
- Runtime自定义端点并非全都重新回查平台权限。保留现有架构：每个新平台请求先鉴权再按动作转发，不承诺已发委托可即时撤销。
- Catalog刷新仍需PLATFORM_CATALOG_REFRESH，graph schema按现有项目读取权限；不为修credential_id放宽角色或跳过策略。

## 6. 已批准生命周期

1. 委托到期不自动取消已接受Run；不重签、不重发已有Run。Run继续受现有业务检查，不保证必然成功。
2. 已建立SSE不增加持续重鉴权或JWT到期定时断流；不承诺撤权立即关闭既有连接。
3. 重连、审批、取消等新HTTP请求加载当前身份/权限，按实际动作签发新委托；无权限直接拒绝，不复用旧请求授权结论。重连只订阅，审批沿原恢复关系，取消ACK仅表示请求接受。
4. 过期JWT用于新的Runtime请求按现有401拒绝。不自动降级匿名，不因401自动重放提交、审批、取消等用户动作。
5. 工厂可在同一HTTP请求内使用当前快照，不缓存到后续请求；本期不加请求内自动续签。慢请求跨TTL导致后续上游调用拒绝时沿现有安全错误返回，不能用放宽过期验证修复。

## 7. 安全失败、兼容和回退

- 平台纯签发器非法输入统一ValueError。HTTP签发边界捕获该类失败，复用现有503 runtime_delegation_not_configured安全响应；scoped闭包也要覆盖，禁止返回异常原文、claim、secret或token。不吞其他业务授权异常/取消。
- Runtime签名/过期/issuer/audience/claim失败为401，资源operation/scope拒绝为403，Thread ACL回查不可用为503，均不放行。平台公开映射沿错误响应专项：Runtime401为502 runtime_delegation_rejected，不让前端误退出用户登录；已登记403保留安全码，未登记为forbidden；503按既有公共转换。
- v2不变：新平台只发当前Runtime已允许字段；本期不新增字段、不把未知字段当兼容扩展。未来claim/operation/语义或算法改变单独评审，不预建v3。
- 新平台+当前锁定Runtime作为必测组合；旧平台+当前Runtime作回退基线。其他旧Runtime未测不能宣布兼容。新增追踪两claim的目标Runtime必须实测已接受。
- 后续发布/回退仅API产物；无DDL、历史回填、依赖升级或Runtime重启要求。回退可能重新暴露旧签发缺陷，但不撤销/重发/重签已接受Run；按既有新请求路径验证。
- 若双端差异必须修改Runtime才能解决，保留拒绝行为并明确阻塞，不在本专项突破边界。权限规则变化也不作为“修一致性”夹带实施。

## 8. 固定修改清单与集成顺序

J1先建立真实双端测试基线 → J2签发输入收口 → J3 Catalog凭据/签发错误出口 → J4动作/身份矩阵 → J5真实生命周期与回退验证 → J6交接。

J2只改tokens.py，不改policy构造器/正常模型算法；J3只改Catalog _runtime_headers凭据传递与Gateway scoped签发ValueError安全出口。J4以测试为主，既有业务权限与动作逻辑保持；发现不兼容依第7节处理。追踪修改同一工厂时按最新工作树整合，禁止覆盖Catalog用户已有改动。

本期无需先实施AI服务规范路由，也无需通读所有项目。最低依赖只涉及错误响应委托失败映射、追踪两claim契约、SSE重连边界；具体测试见verification.md。
