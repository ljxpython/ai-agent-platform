# 已取代：第一版可选工具交集方案

本文仅为历史记录，已被 [新版总览](../README.md) 及编号专题取代，不再指导开发。

## 1. 背景与证据范围

[原分析](../../../decisions/20260920-runtime-optional-tool-not-allowed-analysis.md)记录：DearFlow 新增四个技能管理工具后，平台目录仍保存旧工具集合，普通 Chat 抛出 `runtime.optional_tool.not_allowed`；一次管理员刷新后恢复。

本次核查依据 2026-09-20 工作区源码，未访问运行中数据库、未重放故障、未重新执行刷新。原文的工具数量、数据库类型、日志行号及“当前已恢复”属于原现场记录，不能作为本次实测结论。

## 2. 根因：触发因素、放大机制与诊断缺口

### 2.1 实际调用链

```text
Web Context（可不含 tools）
  → Platform RuntimePolicyOverlayService.build_delegation_policy()
    → ready Catalog 工具 + 项目启停策略 → allowed_tool_names / runtime_permissions
      → Gateway 签发 delegation
        → DearFlow get_agent() → resolve_runtime_config()
          → RuntimeConfigMiddleware 再解析 → 模型工具过滤 → 工具执行再次拦截
```

代码证据：

| 位置 | 核查结果 |
|---|---|
| `apps/platform-api/src/platform_api/modules/runtime_policies/application/service.py` / `RuntimePolicyOverlayService.build_delegation_policy()` | 只允许 ready 且项目未禁用的工具；没有项目覆盖策略时默认允许；runtime_permissions 从允许工具的权限声明派生 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` | 将 policy 允许集用于 delegation 签发 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` / `get_agent()` | 先用完整 defaults 解析；之后才应用治理开关、模式及环境可用性过滤 |
| `apps/runtime-service/src/runtime_service/runtime/resolver.py` / `resolve_runtime_config()` | tools=None 使用所有默认 optional；分别校验 Policy 与 Principal，两处可抛出同一个 optional 错误码 |
| `apps/runtime-service/src/runtime_service/middlewares/runtime_config.py` | `_allowed_tools()` 收敛解析结果和本地工具集；模型输入、模型返回工具调用、工具执行均有检查 |
| `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py` / `refresh_tools()` | 通过受鉴权的显式刷新从 Runtime 读取能力，事务更新并标记缺失项删除 |

### 2.2 直接触发：平台目录快照滞后

Runtime 已声明新增工具，平台尚未刷新，故新增名称不在签发的允许集中。按当前 Resolver 规则，任意一个默认工具缺失便失败。这足以解释原现场，但同样错误码也可由 Principal 权限不满足触发，不能仅凭错误码断定“又忘了刷新”。

已检索平台源码及 scripts 中的刷新调用；lifespan 未做 Catalog 刷新，local-stack.sh 未调用 tools/graphs refresh。不能据此排除部署环境在仓库外安排的任务。

### 2.3 设计放大器：默认选择与显式要求共用全量严格语义

现在 optional 的实际含义是“允许调用方选择；调用方不选时默认全部选中，选中后全部必须授权”。旧规范明确要求 fail-closed，代码与该规范一致，因此这是需要评审的语义调整，不应描述为明显写错的一行代码。

这条规则会产生两类故障：

1. 目录滞后：新增一个可选工具，旧 policy 使普通聊天失败。
2. 正常治理：管理员有意禁用一个可选工具，即便目录完全新鲜，默认聊天仍失败。

第二种证明：自动刷新无法根治该问题。DearFlow 在解析后才做运行模式/环境过滤，也意味着本轮原本不会开放的能力仍可能提前阻断整个 Run。

### 2.4 边界纠正：能力与授权分离合理，快照参与默认授权才需重点讨论

Runtime 是实现/能力声明真源，Platform 是项目授权真源，Catalog 是能力投影；不能简单合并成 Runtime 自己授权。应明确能力、授权、运行可用性三者关系。

当前 `ready + 无项目覆盖策略 → 允许` 的规则，使发现新工具同时具有授权效果。自动刷新虽然不会覆盖已有项目禁用记录，却会使全新工具默认进入后续 policy。因此原分析对 A2 的“零破坏性”和“少于 20 行”判断不成立，至少还涉及调用身份、项目上下文、上游顺序与新工具授权规则。

### 2.5 诊断缺口与同步风险

- `_fail()` 与 `RuntimeErrorBase.__init__()` 当前只接受 code、field；原 A1 的第三个 message 参数不能直接使用。
- Runtime 持有最终允许集，无法独立判断不在集合里的工具是“管理员禁用”“Catalog 缺失”还是“目录未 ready”。日志应准确标为 `policy_not_allowed`，具体原因由平台目录/策略对照诊断。
- `_normalize_tool_items()` 将非预期结构变成空列表并过滤非法条目；`refresh_tools()` 随后用所得集合标记缺失工具删除。坏响应可能被当成完整空快照。自动化前必须修复这个边界。
- 旧单测 `test_resolver_enforces_actor_tool_permissions()` 明确要求默认 optional 权限缺失时报错。新语义需要替换该断言，同时保留显式请求和 required 的负向测试。

## 3. 方案选择

| 方案 | 能解决什么 | 无法解决 / 代价 | 建议 |
|---|---|---|---|
| A1 精准诊断 | 缩短定位时间 | 不改善聊天可用性；不能直接把全部策略输出给客户端 | 首批实施 |
| A2 local-stack 启动刷新 | 降低本地启动后的目录漂移 | 不覆盖仅重启 Runtime；有身份与默认授权影响 | 后置，不能当根治 |
| B 平台启动/后台刷新 | 覆盖更多部署方式 | 启动一次仍不覆盖后续升级；需处理多进程、重试、授权与坏响应 | 安全同步契约确认后再选触发方式 |
| C 默认交集、显式严格 | 目录缺失或项目主动禁用可选工具时，保留获准能力 | 改变既有契约；必须覆盖 Principal、模型绑定、执行及观测 | 核心推荐 |
| 继续严格 + 仅强化同步 | 保留旧契约 | 正常禁用仍阻断默认对话，需要逐个 Agent/客户端显式选工具 | 不推荐作为通用 Chat 默认行为 |

**推荐组合：C（完整权限约束）+ A1 + Catalog 刷新安全校验。** 自动同步是后续治理决策，不能用它替代默认工具语义修正。

## 4. 推荐的目标契约（待批准）

### 4.1 默认、显式与必需工具

设 D 为默认可选工具，P 为 policy 允许名称，U 为通过现有 permission_map 检查的工具：

```text
tools 缺省或 null：optional = D ∩ P ∩ U
tools = []：optional = ∅，required 不变
tools = 显式列表：每项必须属于 D、P、U，否则整次拒绝
required：始终严格检查 P 与 U；缺失则拒绝
```

- 保留当前输入类型、重复项、未声明名称及 required/optional 冲突校验，不能用 set 转换掩盖坏输入。
- permission_map 未指定名称时，沿用现有以工具名作为权限值的规则；不增加新的权限系统。
- 使用现有排序约定保证结果确定性。仅默认分支允许收敛；不捕获所有解析异常进行降级。
- 模型无授权、身份错误、Context 哈希不匹配等仍拒绝。
- 默认 optional 全部被排除时，若模型及 required 满足，允许无可选工具对话；这不保证依赖这些工具的任务仍可完成。
- 真正业务必需的工具应声明为 required；本专项不把所有 Agent 的工具重新分类。

### 4.2 装配与执行一致性

复用 `RuntimeConfigMiddleware._allowed_tools()` 作为现有模型/执行边界，不另建权限裁剪层。验证 DearFlow 根 Agent、researcher 子 Agent、Showcase、reference_agent 以及 demo/MCP 调用路径。

实际提供给模型的工具还受环境开关、模式及本地装配集约束。因此 resolved 的授权集合不一定等于实际绑定集合，日志中不得混为“实际可用工具”。对于显式获准但环境不可用的工具，纳入兼容性测试与评审，不顺带引入全新资源可用性契约。

动态 MCP 继续保持先验证显式名称授权、后连接/发现的顺序。默认收敛不能触发未经请求的远程发现。不得新增 internal_tool_names 绕过；已有 internal 例外需单独核对。

默认筛选后的结果进入现有 config_hash/snapshot，Context hash 继续区分 null 与 []。不为诊断字段直接修改严格 snapshot schema；旧快照、恢复运行及重新签发策略必须回归。

### 4.3 诊断边界

- 对外保留稳定错误码及安全提示；普通用户不接收完整 allowlist、permissions、delegation 或内部配置。
- 在受控服务端记录选择来源（default/explicit）、阶段、被排除/拒绝的工具名，以及 `policy_not_allowed` / `principal_permission_missing`。
- 由现有 Agent/Middleware 边界补 request_id、graph_id、policy_version 等关联信息；保持 Resolver 纯函数，不在其中查库、发 HTTP、打印令牌或重复刷屏。
- 优先利用既有异常与运行日志承载信息；若扩展错误结构，保持现有 code/field 调用兼容，检查序列化与事件脱敏。
- 默认收敛必须可观察；产品是否展示“部分能力不可用”见评审事项。静态 prompt/skills 若承诺无条件可用工具，需调整为以当轮工具为准。

### 4.4 Catalog 的安全刷新与触发方式

首批复用现有管理员刷新入口和事务仓储：完整校验返回结构、名称、重复 key 及权限声明后才写入；任一校验失败保持旧快照与同步时间，不把部分响应当完整目录。合法空目录与非法响应必须区分；空目录是否允许清空投影单独明确并测试。

成功刷新保留已有 tool_catalog_id 和项目启停覆盖，不将项目禁用改成启用；名称变更视为新能力，不自动继承旧授权。记录新增/移除差异以便管理员理解影响。

自动化候选优先复用发布后的显式同步步骤与同一服务方法，避免 local-stack、lifespan、Gateway 三处各做一套。自动执行前必须批准：

1. 新发现工具继续默认允许，还是先进入待授权状态；后一项涉及存量兼容与初始化，不在本次规划中偷偷改变。
2. 合法服务身份、项目上下文及鉴权方式；不硬编码管理员密码、不伪造普通用户 actor。
3. 刷新失败保留旧快照并告警；明确发布是否阻断以及恢复重试入口。
4. 多实例并发、Runtime API/Worker 版本一致性；启动同步不能被宣称为运行期间强一致。

首批不做每次 Run 同步，不做“目录为空才刷新”的伪自愈，不新增调度基础设施；无工具变更需求时也不顺带强制刷新 graphs。

## 5. 关键文件与契约影响

| 文件 / 函数 | 计划改动与理由 |
|---|---|
| `apps/runtime-service/src/runtime_service/runtime/resolver.py` / `resolve_runtime_config()` | 区分默认和显式选择；统一现有权限检查语义，保持纯函数 |
| `apps/runtime-service/src/runtime_service/runtime/errors.py` / `RuntimeErrorBase` | 如诊断承载需要，增加兼容的服务端详情；先核对消费者 |
| `apps/runtime-service/src/runtime_service/middlewares/runtime_config.py` / `_resolve()`、`_allowed_tools()`、两个 awrap 方法 | 复用现有过滤/拒绝，补诊断与集成验证；仅在证据要求时修改装配 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` / `get_agent()` | 核对初次解析、环境过滤、MCP 与子 Agent 的一致性 |
| `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py` / `_normalize_tool_items()`、`refresh_tools()` | 失败响应不能被当空目录写入 |
| `apps/platform-api/src/platform_api/modules/runtime_policies/application/service.py` / `build_delegation_policy()` | 验证刷新后保留项目禁用；默认授权语义待评审，不预设改动 |
| `apps/runtime-service/docs/knowledge/14-runtime-contracts-and-resolution-design.md` | 批准后同步更新“禁止默认裁剪”的现行规范 |

HTTP tools 字段类型、delegation 字段、数据库 schema 暂无必改计划；缺省选择的行为语义发生变化。若引入待授权状态或新前端 metadata，需补充具体契约及评审，不能直接扩大实施范围。

## 6. 实施与回滚

1. 评审语义和安全边界，形成明确批准记录。
2. 首批实现默认解析、诊断与对应回归，覆盖所有共享 Resolver 调用者；记录 implementation。
3. 加固受控目录刷新，验证项目策略不被覆盖；自动触发仅在单独决策批准后接入。
4. 执行单元、集成、真实完整链路及回滚验证，按 verify-change 记录四态。

首批不迁移数据库。代码回滚应恢复旧解析语义，并确认 HTTP/JWT/snapshot 仍兼容；旧规则会重新产生默认工具全量拒绝，必须在回滚演练中明确记录。目录刷新是独立数据变化，代码回滚不会恢复目录快照；在隔离环境验证旧 Runtime 再刷新时新增/移除及已有项目禁用的结果，生产恢复不得直接覆盖项目策略。

## 7. 需要详细讨论的决策

1. **默认的含义：** 是否批准“提供当前获准的默认可选能力”？推荐批准；显式请求及 required 保持严格。
2. **权限不足的默认项：** 是否和 Policy 缺失一起排除？推荐是，否则只求 D∩P 仍会在 Principal 检查失败；排除不是授予权限。
3. **新工具授权：** 当前无项目覆盖就默认允许是否符合产品要求？首批先保留管理员受控刷新；不在这个问题未确认前上线自动发现即授权。
4. **降级体验：** 默认排除项先写受控日志，还是同时向用户显示笼统提示？推荐服务端必做；前端提示不暴露内部工具清单，不将正常项目禁用渲染为故障。
5. **同步自动化范围：** 首批是否只做安全刷新，后续再加发布同步？推荐如此；本地启动、平台启动、后台定时不同时铺开。
