# 01 — 职责、根因与目标契约

## 目标

将工具能力与执行决定收敛到 Runtime，Platform Catalog 只作展示投影。一次性替换旧契约，不保留旧工具白名单、双读双写或兼容开关。用户已批准方案，并明确不维护旧项目、转换旧业务数据或兼容旧执行状态。

## 方案设计

### 1. 根因与改造前证据

原现场是 Runtime 新增技能工具、Platform 目录落后，默认对话被全量 optional 校验阻断。但当前问题不止一处校验：

- `runtime/resolver.py:resolve_runtime_config()` 同时检查 allowed_tool_names 和 Principal permissions。
- Platform `RuntimePolicyOverlayService.build_delegation_policy()` 从 Catalog 派生 allowed_tool_names 和 runtime_permissions；`RuntimeGatewayService._assert_runtime_options_allowed()` 还另做一次工具预校验。
- Runtime `http/terminal.py:_owner()` 直接读取旧白名单和 runtime.tool.execute。
- Web `AgentEditorPage.vue` 保存 context.tools；`RuntimeModelsPage.vue` 维护项目工具策略。
- Catalog 返回的是 DearFlow 的全局权限映射，不能准确表达“某个 Agent 声明哪些工具”。
- 签发代码使用 project_roles[0]，且固定添加 project.runtime.read/write，不能直接据此实现精确的角色授权。

因此改动级别是治理改动。原先 C+A1 的补丁方向已被本方案取代。

### 2. 三层职责

| 层 | 应负责 | 本专项移除 |
|---|---|---|
| platform-web | 展示目录；管理员配置禁用例外；运行交互、审批和安全提示 | 普通 Agent 工具选择、客户端授权计算与权限事实提交 |
| platform-api | 用户/项目/Agent/线程鉴权，禁用规则管理/审计/求值，签发可信权限快照，模型治理，目录缓存 | 从 Catalog 算允许集、依赖 catalog_id 的旧工具策略、白名单预检查 |
| runtime-service | Agent 静态声明、验证签名禁用结果、模式/环境收敛、模型/执行/HTTP 统一检查、资源隔离 | 用户规则管理、对平台 Catalog/工具白名单的执行依赖 |
| interaction-data-service | 结果域原有职责 | 无计划业务改动，仅必要链路回归 |

“平台只展示”仅针对工具；不删除平台身份认证、项目访问权、Agent/graph 访问限制和模型权限。

### 3. false 规则的含义与来源

经用户进一步澄清，采用：Platform 管理用户权限规则，Runtime 执行权限决定。平台从独立于 Catalog 的禁用记录计算 `tool_overrides: {"delete_skill": false, "execute": false}`，放入签名 delegation。浏览器不能为普通 Run 提交此字段，Runtime 不存用户规则。

- Agent 声明集合内，未出现禁用规则表示默认可用；不代表所有已注册工具默认可用。
- 只允许布尔 false 作为例外；true 无需配置，非布尔值必须报配置错误。
- 第一版支持项目+graph 的全员禁用与指定用户禁用，拒绝并集；不做角色规则/允许覆盖/复杂优先级。已有角色控制谁能管理规则、谁能访问 Agent。
- 新表只存禁用记录，使用项目、graph_id、主体类型（project/user）、主体 ID 和 tool_name；不引用 catalog_id。项目记录覆盖该项目全部用户，用户记录只能进一步减少。
- 创建/修改规则时由平台服务端校验主体归属和 Runtime 实时声明，不能相信前端目录；Runtime 不可达则拒绝此次管理写入，不阻断其他正常 Run。
- Runtime 收到未知工具/错误 graph 的禁用快照应明确拒绝，不静默忽略拼错；声明升级移除/改名时要同时盘点限制规则。
- token 必填 tool_overrides，`{}` 表示成功求值后无禁用；规则查询/签发失败、字段缺失均拒绝，不能回退空对象。
- 第一版不凭空规定哪个业务角色禁用什么。新规则从空集合开始，由管理员明确配置，不转换旧 false 数据。
- 新部署在已有 Agent 中增加工具，会使该工具默认向可访问该 Agent 的主体开放；能力增量需要代码评审，Catalog 刷新不再有授权效果。

“Catalog 仅展示”与“Platform 管用户权限”并不矛盾：前者是目录投影，后者是独立的拒绝例外。平台无需逐条给 Agent 所有工具授权，也不再因工具未同步而阻断运行。前端管理界面只提交规则变更命令，真正求值、校验、签发都在平台后端。

### 4. 集合与失败语义

设 S 为当前 Agent 声明工具，A 为当前装配/模式/环境可用工具，D 为 Platform 按可信身份求值并签名的禁用项：

`effective = (S ∩ A) - D`

- 模型只看见 effective；实际工具调用必须属于 effective，未知/伪造调用直接拒绝。
- Required 工具不在 effective 时，Agent 初始化明确失败；Optional 被禁用则移除，剩余工具或纯对话可运行。
- 公开 Context 不再支持 tools / enable_tools；旧字段返回明确 400。删除显式工具选择整条路径，调试脚本也升级。
- 动态 MCP 的可选工具集合改由 Runtime Agent 代码/受控连接配置声明，不能从 context.tools 动态扩张 defaults；先判断主体可用名称，再连接发现并校验名称冲突。
- 子 Agent 可拥有其代码声明的专用工具，但必须使用同一可信身份、对子图应用同一规则来源；父级业务限制必须传播到子图，不能换子 Agent 名绕过项目/用户禁用。
- 内部工具例外不得通过 internal_tool_names 的无条件并集覆盖禁用；逐项判断真正框架内部操作与用户可调用工具。
- tools 被禁用不表示同类业务动作绝对不可达：execute、网络、MCP 可能形成替代路径。若需求是禁止删除/写入整个资源域，必须在存储/沙箱/凭据边界执行，不靠工具名列表保证。

### 5. 新鉴权/执行契约

| 字段 | 新约定 |
|---|---|
| delegation schema | 新必填版本标识，如 delegation_version=2；只接受新版 |
| sub/tenant_id/project_id | 保留可信身份 |
| role / permissions | 保留真实身份事实及现有必需资源权限；工具禁用按 user/project 求值，不为本专项新增角色授权引擎。核查 role 首项选择和固定权限的实际消费者，不把其当禁用规则来源 |
| permissions | 仅保留确有来源与用途的项目/资源权限；停止固定声明权限及从工具目录推导 runtime.tool.*；无消费者的字段移除 |
| scope | 保留绑定 graph/assistant、thread、operation；通用读 scope 不能执行工具 |
| allowed_model_ids / policy_version | 保留模型治理；不从工具目录参与计算 |
| allowed_tool_names / runtime_permissions | 删除；不双读、不改名为另一份允许列表 |
| tool_overrides | 必填对象，值只允许严格 false；空对象表示成功求值无禁用；由平台签名，客户端不可覆盖 |
| tool_policy_version | 必填：按作用域和规范化禁用集合生成内容哈希；与模型 policy_version 区分 |
| Context hash | 新单版本 schema，移除 tools；两服务同步实现，旧 Context 拒绝 |
| Resolved/snapshot | 记录实际生效工具、声明/规则版本及哈希；旧执行快照不继续执行 |

平台的禁用策略版本及 Runtime Agent 声明版本进入执行事实，供审计/恢复判断；不把内部规则全文放入普通 Web 响应。公开错误保留安全 code，受控日志记录 graph/request/run、规则版本、排除项及原因。平台在 graph/actor 确定后的 delegation_headers_factory 按本次作用域求值，不能复用一个跨 graph 的权限快照。

### 6. 实时性与边界

第一版规则可由管理员在线修改；新 Run、恢复/审批续跑、新 HTTP 操作重新签发当前策略。已经运行的 Run 使用其签名快照，不承诺即时撤销；紧急禁用需取消相关活跃任务并关闭终端，单靠 JWT TTL 不能终止已接受的长任务。资源操作仍验证 tenant/project/user/thread 与所有权，access_policy/HITL 不能将 false 重新变成 true。

## 任务拆分

- [x] 核查并记录旧三层职责及隐藏依赖。
- [x] 用户澄清权限管理归 Platform、执行把关归 Runtime，取消 Runtime 管用户规则的建议。
- [x] 用户批准拒绝并集、生效边界及新 token/context/snapshot 单版本方向。
- [x] required、optional、规则冲突、MCP、子 Agent、HTTP 统一语义已实现并通过定向测试。
- [ ] deferred：管理员上线后配置实际业务禁用例外；本轮仅在隔离测试库创建规则，不替用户制定业务权限。

## 验证要求与记录

- [x] Catalog 缺失/过期/清空时，签发与正常运行不依赖工具目录。
- [x] 不可信 Context/config/metadata 无法传入、删改或覆盖授权事实。
- [x] false 从模型列表到执行/相关 HTTP 操作都生效，required 禁用报错。
- [x] 旧 token/Context/snapshot 明确拒绝，没有兼容回退。

记录：实现与证据见 [06 验证](06-validation-and-delivery.md) 和 [实施记录](implementation/01-backend-runtime.md)。

## 状态

done（本轮契约与后端实现）；实际业务规则配置后置，旧项目维护与兼容不在范围。
