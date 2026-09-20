# 04 — Runtime：声明、禁用规则与统一执行把关

## 目标

Runtime 对每个 Agent 的工具拥有单一执行决策链；能力上限从代码声明读取，用户禁用快照由 Platform 签名传入，Catalog 不参与执行。Runtime 不维护用户权限表，既检查模型工具调用，也检查能产生同类副作用的直接管理接口。

## 方案设计

### 1. 代码落点

路径相对 `apps/runtime-service/src/runtime_service/`；新增文件/函数均为规划名称。

| 文件 / 函数 | 开发内容 |
|---|---|
| runtime/contracts.py | RuntimeContext 去 tools；RuntimePolicy 去 allowed_tool_names，加入不可变规范化禁用名称集合及 tool_policy_version（传输层 false map），保留模型事实；Resolved 明确 effective 工具与版本 |
| runtime/auth.py / verify_delegation_claims()、verified_delegation_from_user() | 严格新版 claim；移除旧白名单，验证身份/版本/scope/哈希，禁止缺字段默认放行 |
| auth/platform.py / authenticate() | 输出新版可信身份，清理顶层及嵌套白名单；保留 operation 对 Server 资源的限制 |
| runtime/resolver.py / parse_runtime_context()、parse_runtime_policy()、resolve_runtime_config() | 删除 context.tools 与旧允许集权限分支；使用可信声明及签名禁用集合，required 严格、optional 减法；仍为纯函数 |
| runtime/tool_access.py（新增） | 最小共享执行检查：require_tool_access(...)；Agent 集合求交复用已有 resolve_runtime_config(available_tool_names=...)；用于 Agent 与 HTTP，校验 scope/未知名称；不查询用户规则或 Platform DB |
| services/dearflow_agent/capabilities.py | 从现有权限映射收口成 DearFlow 实际工具声明/描述，避免声明、catalog、装配三份名单 |
| runtime/capabilities.py | 改为各已注册 graph 的声明聚合；不把 DearFlow 的表当全局授权表，不 import 会建网络/沙箱的执行根 |
| services/dearflow_agent/agent.py / get_agent() | 从统一声明及 mode/env 求可用集合，再做授权；删除 requested_mcp 从 Context 扩张 defaults；传同一决策到根/子 Agent |
| services/dearflow_agent/tools/mcp.py / load_mcp_tools() | 从受控连接配置/Agent 声明确定候选名称；先过滤授权再连接，返回名称冲突/未知即拒绝 |
| middlewares/runtime_config.py | 移除 tool_permissions 参数及旧校验；模型绑定、模型输出、工具调用共用 effective；internal 例外不覆盖禁用 |
| http/terminal.py / _owner() | 以 Runtime 当前 graph 的 execute 能力规则替换两处旧 claim 检查，保留 scope、开关、所有权、acknowledge_execution |
| http/dear_skills.py / authorize()、各写路由 | 精确映射 upload_skill/update_skill/set_skill_enabled/delete_skill 后检查同一主体规则，再进入 SkillStorage |
| http/dear_governance.py / change_memory() | manage_memory 规则与原 owner/thread 验证同时生效 |
| http/documents.py、http/workspace.py | 明确上传/读取与工具能力的关系；执行写入须满足对应 write_file 规则，读取对应 read_file；fork 保留专有 scope 且核对源读/目标写 |
| webapp.py / tool_catalog()、graph_capability() | 输出声明与图归属，不输出授权承诺；目录读取不装配模型、连接 MCP、创建工作区 |
| runtime/errors.py、observability/langfuse.py | 安全错误与规则/声明版本，受控排除原因，避免重复解析重复日志 |

工具与 HTTP 操作的映射已纳入本轮获批方案。例如禁用 delete_skill 后，不能通过 Skills 管理路由执行同一删除动作；读详情与目录读取仍按相应读 scope。所有批量动作按实际副作用逐项校验。只检查路由前的布尔 write 不足以区分不同写工具。

### 2. 所有 Agent 调用者一次切换

`services/reference_agent/agent.py`、`graphs/mcp_probe.py`、`services/demo/{workflow_demo,failure_demo,deep_agent_demo,showcase_demo,backend_demo,mcp_demo}/agent.py` 均消费旧 Resolver/permission_map，全部改为同一新契约。更新本地测试身份构造，不保留假权限来让测试过关。

复用现有 graph 注册事实源；先查已注册 graph 清单再实现聚合，不能为 Catalog 创建第二套动态注册框架。每个 Agent 只有一份声明，描述可与声明同文件；build_*_tools 的实际名称与声明用定向断言检测漂移。

### 3. 执行细节

- 声明不等于无条件加载：被禁用的 MCP/外部能力不连接，schema 探测不建资源。
- 模式、环境和授权都是减法，必需能力缺失则失败。默认空有效工具集可以对话。
- 子 Agent 先受主体及继承限制，再受子图声明；不得通过 task 转交被禁用动作。
- 审批前后工具调用都校验；full_access 只是审批策略，不能越过禁用规则。
- 手动 Terminal 创建、写入、resize、读取及关闭逐项处理：默认保留现有 execute 门槛；规则收紧后的会话需服务端清理，不能因禁止用户 close 留下可执行进程。
- 模型/存储/沙箱隔离保持；execute 可实现读写和网络，工具名禁用不是动作级沙箱策略。
- 当前 snapshot 恢复工具只是导出的 helper；不能假设它已经覆盖所有 GraphHarbor checkpoint。外部 Worker/SDK 的排队和恢复另列 05 验证。

### 4. 签名事实与执行边界

删除旧 runtime.tool.read/write/execute/delegate 这套从 Catalog 推导的授予；不能改成全量补发来凑校验。保留真实资源权限或 operation scope 的验证。Runtime 只验签及执行最终拒绝集合，不按 role 再算一遍平台用户策略，也不请求平台做每个工具调用的在线鉴权。

tool_overrides 必须存在且为对象，所有值必须 `is False`，不得接受 0/null/字符串；规范化为不可变、排序的名称集合。明确空对象有效，缺失无效；来自 context/config/metadata 的同名字段拒绝。tool_policy_version 和 scope 均在签名内，副作用操作要求具体 graph。旧字段/旧 token 不兼容。

子 Agent 使用父请求签名快照及继承限制，不能因为子图没有单独 token 就默认为全允许。如子图具有独立能力，需要平台在父 graph 的能力清单中可表达其禁用项；首版声明应枚举可委派能力并确保名字无歧义，做不到则该委派方式不开放。

规则版本、Agent 声明版本和 effective 工具进入新配置哈希；诊断日志只出现必要标识，不带令牌或全量规则。更新知识文档 14、19 及相应 runtime standards；这些活文档在实施时直接更新，规划阶段不提前写成已实现。

## 任务拆分

- [x] R1：建立单一声明、false-only claim 校验与最小共享执行检查，不建用户规则求值器。
- [x] R2：更新 contracts/auth/resolver/hash/snapshot 及所有构造器。
- [x] R3：升级全部 Agent/Middleware，收口 MCP/子 Agent/internal 例外。
- [x] R4：Terminal/Skills/Memory/Workspace 的 HTTP 动作映射和共享检查。
- [x] R5：目录投影、可观察性、运行时规范更新。
- [x] R6：正负向单元/集成及 durable、审批恢复测试。

## 验证要求与记录

- [x] false 项不进模型 schema；模型伪造调用、历史待执行调用被拦截，实际副作用 handler 调用次数为零。
- [x] required 禁用/环境不可用失败，optional 禁用正常降级，未知禁用名称和非法布尔不被忽略。
- [x] 同一用户不同项目、同一工具不同 graph 的签名限制不能串用；子 Agent 继承有效禁用。
- [x] 禁用 MCP 不发生网络连接；允许工具不会被未知 schema 扩权。
- [x] direct HTTP 与 Agent 工具效果一致；Terminal 不能依赖已删除字段，跨租户/项目/线程仍拒绝。
- [x] Config/Context hash 与模型绑定事实一致；旧契约拒绝；新版本普通恢复和 HITL 正常。
- [x] 模块导入与 Catalog 读取无模型/MCP/文件系统副作用。

记录：实现与锁定契约、真实 Graph、HTTP 测试完成。运行中任务紧急取消及跨 Worker 联合发布属于 05 的发布验收，不以本地测试代替。

## 状态

done：本轮 Runtime 开发与必要本地验证完成；发布环境验证后置见 05。


终端清理采用最小方案：新建、读取、输入、resize 检查 execute；关闭仅校验原 scope 与所有权，即使 execute 被禁用或终端环境开关关闭仍能关闭自己的会话。活跃进程不会因规则变更自动中断，需要显式关闭；运行时 shutdown 继续清理进程。
