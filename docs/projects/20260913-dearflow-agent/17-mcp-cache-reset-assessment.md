# F15：MCP 工具刷新与缓存热重置评估

## 目标

判断同事提出的 F15 是否解决当前项目的真实缺口，避免为同一目标再建设一套 MCP 管理系统。

**已确认决策（2026-10-10）：不开发原案中的 reset API 和连接池。** 用户已采纳评估结论，并要求将结论合入项目分支。当前普通 MCP 接入没有跨 Run 工具缓存或持久连接池，每次执行构图重新发现工具，工具调用使用官方适配器的临时 session。DeerFlow 的 reset 是其缓存架构的配套动作，不是所有生产 Agent 都必须具备的独立能力。

可选的最小后续工作是**固化刷新语义和补充回归证据**，不增加生产接口。如果真正要求“修改部署连接配置而不重启 API/Worker”，应单独评审配置热更新；清缓存不能实现这个目标。

- **本轮范围：** 只做源码对照、取舍、任务与验证规划、前端交接；不改业务代码或测试代码，不启动服务。
- **入口与模板：** 沿用 [项目总纲](README.md) 的多专题模板及 2026-09-13 启动日期，不新建重复项目。本文是 F15 的任务与状态来源，前端按 [18 交接](18-mcp-cache-reset-frontend-handoff.md) 阅读。
- **分级：** 本轮是文档规划。推荐的测试/说明补齐不改变服务契约；原案若落地为跨进程、跨租户的管理动作，属于治理改动，须人工评审。当前没有该项实施批准。
- **总体状态：** 已完成（评估关闭）；用户已确认原案不开发，评估与交接文档作为决策记录保留。后续候选未排期，不属于本次交付。不改变整个 DearFlow 项目的 `partial` 状态。

## 方案设计

### 1. 证据基线

核对日期：2026-10-10。下文当前项目路径相对本仓库根目录，上游路径相对各自参考仓库。

| 来源 | 路径/版本 | 证据边界 |
| --- | --- | --- |
| 当前平台 | HEAD `2f08c5462571cd0244a7181e5d0d1388341b79c4` | 开始核对时工作树干净；已读 CONTEXT、服务入口、Runtime 范式、相关经验和现有项目 |
| DeerFlow | `/Users/lijiaxin/PyCharmMiscProject/research/deer-flow`，HEAD `cc664451f03140b376611f329ae400c313530bdb` | MCP harness、reset router 和本次检查的前端 MCP 文件无 HEAD 差异；不据此声称整个参考仓库干净 |
| Open-SWE | `/Users/lijiaxin/PyCharmMiscProject/research/open-swe`，HEAD `ad417d64d91cc349d63d832c7b643637dc1774cf` | 已分别检查 HEAD 的 `agent/integrations/*_mcp.py` 与本机新增的 `agent/mcp/runtime.py`；后者及 server/TTL cache 存在本地改动，不能冒称上游已发布实现 |
| 官方适配器 | `apps/runtime-service/uv.lock` 锁定 `langchain-mcp-adapters==0.3.2` | 只读核对 uv 缓存中该版本的 `client.py`、`tools.py` 和版本元数据；没有借用其他工作区的运行环境 |
| 官方文档 | 已查询 `langchain-docs`、`langchain-reference` MCP | Docs 的[迁移对照](https://docs.langchain.com/oss/python/migrate/langchain-mcp-adapters#client-methods)说明旧 API 与 session 语义；Reference 搜索返回 [session](https://reference.langchain.com/python/langchain-mcp-adapters/client/MultiServerMCPClient/session)，但详细符号查询未命中。具体行为以锁定版本源码为依据，不在本轮迁移到新 API |

本 Worktree 尚无 Runtime `.venv`，本轮没有安装依赖、运行功能测试或访问真实供应商。已存在的测试说明覆盖意图，不代表本轮重新通过。`docs/quickstart/` 当前不存在，入门信息使用根 README 和服务文档入口。

### 2. DeerFlow 实际怎么做

| 层/文件/符号 | 实际职责 | 可借鉴与限制 |
| --- | --- | --- |
| Gateway：`backend/app/gateway/routers/mcp.py::reset_mcp_tools_cache_endpoint` | `POST /api/mcp/cache/reset`；先 `require_admin_user`，再 reset，返回 `success/message` | 明确是当前 Gateway 进程的全局动作，影响该进程内所有线程和用户；不是跨实例广播 |
| 同 router：`update_mcp_configuration`、`create_mcp_servers` 等 | 保存配置、重载配置，并自动 reset | 正常配置修改本身就有失效接线，手动 reset 是补充入口，不应要求每次保存后再手动点击 |
| Harness：`backend/packages/harness/deerflow/mcp/cache.py::get_cached_mcp_tools` | 进程级工具缓存，首次使用时初始化；检查配置路径及 `(mtime, size, sha256)` 签名，再比较有效 MCP 配置切片 | 缓存是性能策略；仅 skills/middleware 变化不必重建 MCP。远端 schema 变化而本地配置不变时，手动 reset 才有额外价值 |
| 同文件：`reset_mcp_tools_cache`、`_reset_mcp_tools_cache_state` | 锁内替换 pool、清空工具状态、递增 generation，阻止旧初始化结果回填；锁外关闭旧 pool | 值得借鉴的是初始化/reset 竞态保护；不是简单 `dict.clear()` |
| Harness：`backend/packages/harness/deerflow/mcp/session_pool.py::get_session_pool/reset_session_pool/MCPSessionPool.close_all_sync` | 维护并替换进程级 pool，在创建 session 的原任务/事件循环上清理 | 同一正在运行的事件循环只收到清理信号，返回时不保证远端 session 全部关闭；清理异常会被记录，reset 响应不证明新工具已加载成功 |
| Harness：`backend/packages/harness/deerflow/mcp/tools.py::get_mcp_tools` | 官方适配器发现工具，仅为 stdio 工具包装持久 session；HTTP/SSE 工具保留临时 session | 同事的“清空 MCP client 连接池”描述过于笼统；当前 DeerFlow 并不把所有传输都池化 |
| Web：`frontend/src/core/mcp/{api,hooks}.ts`、`frontend/src/components/workspace/capabilities/mcp-plugin-manager.tsx` | 配置 CRUD/启停、加载和错误展示；修改后刷新前端 `mcpConfig/capabilities` 查询 | 在已检查的前端源码中未找到 reset API 调用。浏览器查询缓存失效与服务端 session reset 是两件事 |

DeerFlow 当前将 Agent runtime 嵌入 Gateway。清理 Gateway 进程内状态可以触及该进程的执行资源。我们的 Runtime API 与 Worker 分离，不能直接把这套拓扑假设搬过来。

其配置文件消失时可能保留上次有效工具的 fail-soft 策略，也不能原样用于我们受信资源、权限或凭据失效的场景；是否保留旧配置需要独立安全决策。

### 3. 当前项目与 Open-SWE 的覆盖情况

#### 当前平台

| 能力 | 当前文件/符号 | 判断 |
| --- | --- | --- |
| 真实执行时装配 MCP | `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py::_build_agent` | 先解析/验证受信 Context 与策略，再在 `factory.mcp_tools` 阶段调用 loader；schema 探测和手动上下文整理不走普通 MCP 装配 |
| 每次装配重新发现工具 | `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/mcp.py::load_mcp_tools` | 每次读取进程环境，创建局部 `MultiServerMCPClient`，调用 `get_tools()`；未保存进程级 tools/client/pool |
| 资源与权限边界 | 同 loader；`apps/runtime-service/src/runtime_service/runtime/resource_bindings.py::resolve_resource_binding` | 资源绑定本身校验 tenant/project/thread，不包含 user_id；用户身份/线程权限沿既有委托与 ACL 链处理。按 resource_id 取服务端配置，`allowed_tools` 与已授权请求取交集，检查重名、缺失及只读声明，不暴露未知工具 |
| session 生命周期 | 锁定适配器 `client.MultiServerMCPClient.get_tools`、`tools.load_mcp_tools/convert_mcp_tool_to_langchain_tool` | discovery 使用临时 session，退出后关闭；返回工具仅持有本次连接配置与 schema，每次调用再进入临时 session。没有可供 API 统一关闭的常驻 pool |
| 工具能力声明 | `apps/runtime-service/src/runtime_service/services/dearflow_agent/capabilities.py::configured_mcp_names`；`apps/runtime-service/src/runtime_service/runtime/capabilities.py::graph_tools/tool_catalog` | 从部署 `allowed_tools` 生成声明，能力目录不连接远端 MCP、不授予权限；它不是远端 schema 缓存 |
| 平台工具目录刷新 | `apps/platform-api/src/platform_api/modules/runtime_catalog/presentation/http.py::refresh_runtime_tools`；`apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py::RuntimeCatalogService.refresh_tools` | 已有 `POST /api/runtime/tools/refresh`，受 `platform.catalog.refresh` 控制，通过受信委托 GET Runtime 声明，再同步平台数据库目录 |
| 前端刷新入口 | `apps/platform-web/src/services/runtime/runtime.service.ts::refreshRuntimeTools`；`apps/platform-web/src/modules/control-plane/pages/ControlPlanePage.vue::refreshCatalog` | 已有“同步工具目录”，支持权限、项目上下文、busy 和成功/失败展示；不必再加一套刷新入口 |
| Demo / 恢复探针 | `apps/runtime-service/src/runtime_service/services/demo/mcp_demo/loader.py::load_mcp_tools`；`apps/runtime-service/src/runtime_service/graphs/mcp_probe.py::mcp_probe` | 同样使用官方适配器局部加载；教学/探针实现不是第二套生产 MCP Manager，不需要为了 F15 合并这些私有模块 |
| AntV 图表 MCP | `apps/runtime-service/src/runtime_service/tools/chart.py::build_chart_tools`、`apps/runtime-service/src/runtime_service/tools/chart-schemas.json` | 锁定 npm 包和仓库 schema 快照，工具调用使用临时 stdio session；更新快照/包属于代码发布，reset 不能更新仓库资源 |
| 初始化性能证据入口 | `apps/runtime-service/src/runtime_service/observability/startup.py::StartupDiagnostics` | 已记录 `factory.mcp_tools` 耗时，可以先用现有诊断评估握手成本，不另造监控框架 |

现有设计文档 [Runtime MCP 范式](../../../apps/runtime-service/docs/knowledge/19-runtime-tool-capability-mcp-and-side-effect-design.md)明确首期不做跨 Run 工具或连接缓存，与本次源码核对一致。

#### Open-SWE

- **HEAD 中的实现：** `agent/integrations/{notion,datadog,corridor}_mcp.py` 都使用局部 `MultiServerMCPClient.get_tools()`。Notion 还在实际调用时重新解析凭据和工具。可借鉴服务端凭据与生命周期边界，不移植 Notion/Datadog/Corridor 业务、GitHub 参与者授权或它的降级策略。
- **本机新增设计：** `agent/mcp/runtime.py::_load_tools` 将远端定义缓存 600 秒，key 包含 source namespace、连接名和 revision；`_wrap_tool` 调用前重新解析连接并检查作用域、enabled、URL/transport 和 allowlist。它说明“有缓存时按版本隔离”比无范围的全局 reset 更适合受管连接，但当前平台未采用该缓存。
- **去重结论：** 不是“借鉴过 Open-SWE，所以 F15 已实现”，而是当前平台采用临时 session 和新构图 discovery，已经消除了 F15 针对的旧缓存问题。已检查的 Open-SWE MCP 路径也没有同名 reset 接口；不以此推断未核查的全部历史版本。

### 4. 必须拆开的刷新场景

| 变化 | 当前如何生效 | 是否需要 F15 |
| --- | --- | --- |
| 同一个已绑定远端 Server 修改已允许工具的 schema/description | 下一次执行构图重新 `tools/list`；正在执行的图仍持有旧 schema，远端不兼容变更可能使旧调用失败 | 不需要清缓存；补“下一次构图取新 schema”的回归证据 |
| 远端新增一个工具名 | 不会自动授权。必须先进入服务端允许声明，并满足平台/角色/模式策略和资源绑定 | reset 不能绕过授权，也不能作为授权入口 |
| 修改部署 `.env` 的 MCP URL/headers/allowed_tools | 文件变化不会替换已运行 API/Worker 的 `os.environ`；当前按部署流程使 Runtime API、全部 Worker 配置一致 | reset 无效。无重启生效是配置热更新需求，当前未实现 |
| 在同一进程内由测试更新环境变量 | 下一次 loader 会取新值；已构造的工具保留原配置副本 | 仅能证明 loader 重新读取，不能声称 `.env` 已支持生产热更新 |
| 平台管理页上的工具列表陈旧 | 复用 `/api/runtime/tools/refresh` 同步 Runtime 当前声明 | 已有目录刷新。不会重载环境、发现远端 schema、重建正在执行的图或扩大权限 |
| MCP session 断开后再次调用 | 官方适配器重新创建 session；服务不可用仍按现有失败语义处理 | 不需要清池；不把再次建连等同自动成功或无条件重试 |
| 更新固定 AntV npm 包或 `chart-schemas.json` | 通过匹配代码、包版与 schema 的发布生效 | 不属于可失效内存缓存 |

新构图的工具列表是该次图实例的快照。**不承诺正在执行的 Run 被热替换，也不把重新建连等同 schema/凭据立即更新。** 热撤权、密钥轮换时如何处置已经开始的调用属于另一项治理语义，不能用关闭所有连接来代替。

### 5. 对原方案逐项取舍与三层职责

| 原方案 | 已确认取舍 | 理由 |
| --- | --- | --- |
| Runtime 新增 `POST /api/mcp/cache/reset` | 跳过 | 当前没有待清理的共享状态；公开控制面入口也应归 Platform API，而非浏览器直连 Runtime |
| 实现 MCP client 连接池失效机制 | 跳过 | 先新建池再失效增加握手复用、隔离、竞态和清理问题，不能作为当前能力补齐 |
| 配置修改后不重启服务 | 不认定已完成；另行评审 | 需要可更新且可信的配置事实源、版本、生效边界及所有 Worker 的一致性，而非清工具列表 |
| “半天的小改动” | 只适用于有限测试/文档补齐 | 加一个空 reset 路由容易，但无法兑现配置热更新；真实池化或热更新不可按这两行代码估算 |

| 层 | 本轮/推荐后续职责 | 代码开发范围 |
| --- | --- | --- |
| platform-web | 同事接收 18 交接；保留现有目录同步。需要补证据时只补当前入口回归 | **无必需产品代码。** 不新增 reset 按钮、MCP 配置页、Chat 状态或重建 Run 动作 |
| platform-api | 保持目录同步、权限、委托、审计和数据库目录归属 | **无必需产品代码。** 不新增 reset 代理、JWT operation、DTO 或迁移 |
| runtime-service | 保持组合根/私有 loader、官方临时 session、受信绑定和工具筛选；补刷新语义测试/说明 | **无必需生产代码。** 不新增 cache manager、pool、全局单例或路由 |
| GraphHarbor/部署 | 引擎保持 Run/Worker 职责；现阶段连接配置随部署更新 | 无 MCP 业务逻辑、依赖升级或引擎补丁 |

### 6. 可以补什么，在哪里补

以下是后续候选，**本轮没有实施**。测试先验证现有行为；只有出现可复现失败，才在原 loader/组合根修根因并重新核定范围。

| 位置 | 后续最小补充 | 调用方/配置/导出影响 |
| --- | --- | --- |
| `apps/runtime-service/tests/runtime/test_tool_governance.py` | 两次 loader 调用使用相同绑定、不同工具定义，断言第二次 schema 更新、第一批对象不被改写；增加 schema 探测不调用 MCP 的显式断言 | 沿用 principal/resource binding fixture；不改生产签名/exports |
| `apps/runtime-service/tests/services/dearflow_agent/test_mcp_tools.py` | 复用真实本地 HTTP MCP fixture，提供可切换工具定义和 session 观测；验证同一 Runtime 进程重新 discovery，不重启 Runtime | fixture 的新增控制只用于测试，不新增生产 HTTP 路由；计数必须来自 session 生命周期，不能用 TCP 连接数冒充 |
| `apps/runtime-service/tests/services/dearflow_agent/test_agent.py` | 在现有 `test_schema_probe_has_no_model_or_workspace_io` 中对 `load_mcp_tools` 设置禁止调用的 spy | 将“schema 无 MCP I/O”从间接覆盖变成明确契约；已有构图调用者保持不变 |
| `apps/runtime-service/README.md`；`apps/runtime-service/docs/knowledge/19-runtime-tool-capability-mcp-and-side-effect-design.md` | 说明远端 schema、部署连接配置、平台目录三种生效路径，以及 API/Worker 配置一致性 | 复用现有 `RUNTIME_MCP_CONNECTIONS_JSON`，不新增 env/config 文件、watcher 或双源优先级 |
| `apps/platform-api/tests/test_runtime_catalog_delegation.py` | 运行已有委托、无效快照/空目录回归；只有缺覆盖时再加断言 | 不改 `RuntimeCatalogService`、路由、持久化模型或错误/SSE 契约 |
| `apps/platform-web/src/modules/control-plane/pages/ControlPlanePage.spec.ts` | 同事可补“同步工具目录”的成功、失败和权限回归；当前测试主要覆盖 Graph 按钮 | 继续调用 `refreshRuntimeTools`；不新增网络 service 或页面 |

推荐测试/说明补齐估计 **0.5–1 人天**，真实联调取决于隔离环境就绪情况。这是工程估算，不是原案热更新交付承诺。即使不接受此测试切片，也不应开发无对象可清的 reset。

### 7. 何时重新打开需求

仅在出现以下证据时重新评审，不提前实现扩展框架：

1. 已有 `factory.mcp_tools` 实测证明 discovery 成本显著影响已批准的性能目标，或者明确需要跨调用持久的 stdio 状态。再讨论缓存/池是否必要；当前没有该性能证据。
2. 运维明确需要无重启修改连接或轮换凭据。重新定义可信配置来源、作用域、版本、API/Worker 生效时点、在途执行与失败回退，不把“cache reset”当成配置读取器。
3. 未来已经引入缓存且确实出现远端 schema 陈旧。失效必须按受管资源及版本定位；公开入口经 Platform API 权限/审计，Runtime 只接内部可信操作。还要验证多 Worker/多实例覆盖，不能向一个 API 进程发请求就宣布全局完成。

届时需要明确 scope、清理回执、旧初始化回填、取消与在途调用、凭据隔离、超时、失败可观测及回退。这里不提前定义未获批准的 URL/JWT/DB schema，也不复制 DeerFlow 的业务配置、个人 MCP 系统或进程单例。

## 任务拆分

### P：本次规划交付

| 任务 | 内容/验收条件 | 状态 |
| --- | --- | --- |
| F15-P01 | 对照三仓源码和锁定适配器；区分 Open-SWE HEAD 与本地改动，确认真实缓存对象 | [x] 2026-10-10 完成源码核对，见 §1–3 |
| F15-P02 | 明确远端 schema、部署配置、平台目录生效边界和三层取舍 | [x] 2026-10-10 完成规划，见 §4–5 |
| F15-P03 | 形成改动位置、验证计划与独立前端交接，登记总纲/FEATURES/CONTEXT | [x] 2026-10-10 本轮文档交付；文档检查见下方记录 |
| F15-P04 | 记录用户最终取舍并关闭评估 | [x] 2026-10-10 用户确认不开发 F15 原案，要求合入项目分支 |

### R：未排期参考项，不属于本次交付

- [ ] **F15-R01：刷新契约回归。** 在 §6 Runtime 测试位置补两次 discovery/schema 快照及探测无 MCP I/O；预期现有生产实现直接通过，不创建共享状态。最小检查见 U01/U02。
- [ ] **F15-R02：本地 MCP 生命周期证据。** 扩展现有 HTTP fixture，测新 schema、工具调用退出与取消清理；预期客户端临时 session 生命周期可观测。验证见 I01/I02，不拿 mock 或 TCP 计数代替真实 session。
- [ ] **F15-R03：说明与现有目录回归。** 按 §6 更新 Runtime 说明，复跑 API 原有目录测试；不新增跨服务契约，验证 U03/U04。
- [ ] **F15-R04：后续切片收尾。** R01–R03 实施后汇总真实结果和遗留问题，更新专题状态；任何未通过项不标完成。没有产品行为变化时不强制浏览器全链路，若修复扩展到运行路径/跨服务契约则追加 E01 和对应治理门禁。
- [ ] **F15-F01：前端条件任务。** 仅当同事接受“现有工具目录入口回归补齐”时，按 18 交接增加测试；无新增页面、按钮、配置表单。本任务不阻塞本轮规划交付。

原案的 reset API 和 pool **已决定不开发**；配置热更新是独立需求，未排期。R/F 候选均未开始，也不因本文落笔自动获得实施授权，不计为本次评估的未完成任务。

## 验证要求与记录

### 后续验证要求

| ID | 类型/位置 | 操作与预期 |
| --- | --- | --- |
| U01 | 拟增 Runtime 单测 | 相同 resource binding 连续加载 schema v1/v2；两次独立 discovery，第二次用 v2，第一批对象不被改写，未知/未允许工具不进入输出 |
| U02 | 现有 + 补明确断言 | 无绑定/禁用工具不触达 MCP；schema probe 与手动上下文整理不触达 MCP。复用 `test_mcp_disabled_or_unbound_never_connects_and_binding_limits_names`、schema probe 与 `test_dearflow_maintenance_composition_skips_business_setup` |
| U03 | 现有 Runtime 边界 | `test_real_mcp_binding_permissions_disconnect_and_close`、`test_mcp_reconnect_uses_server_connection_registry`、`test_mcp_reconnect_fails_closed_when_connection_is_unavailable`；保持 scope、冲突、只读、断线与错误块行为 |
| U04 | 现有 API 目录契约 | `test_refresh_passes_delegation_to_upstream`、`test_tool_refresh_rejects_bad_snapshot_and_accepts_empty`；Runtime 返回坏快照不破坏上次有效平台目录，合法空目录可同步；权限/委托仍有效 |
| I01 | 拟增本地真实 MCP | MCP Server 不变更连接地址，仅切换已允许工具 schema；同一客户端执行环境的下一次构图取新定义，不调用 reset；旧对象快照仍可辨识 |
| I02 | 拟增本地真实 MCP | 观测 discovery 和多次工具调用的 session 创建/退出；正常、异常和取消后在有界等待内完成清理，取消不能转换为成功。独立记录远端 session 证据，不声称 HTTP socket 复用等于 MCP session 复用 |
| E01 | 条件链路验收 | 如后续确实改动运行路径或契约：隔离 Platform API → Runtime API/Worker → 本地 MCP，在同 Thread 的下一 Run 验证 schema 更新、不同 scope 不串资源、目录刷新不触发 MCP；前端展示按同事交接接续 |

本轮仅文档检查，以上功能验证均未执行。未来执行须按 [Worktree 规范](../../standards/worktree-development.md) 初始化隔离资源、本工作区独立依赖；不回退主库/主 `.venv`，不使用固定主栈端口。不需要真实模型或付费供应商才能验证 discovery/session 语义。

完成 R 切片时可运行以下定向命令；路径从仓库根起算，前提是隔离依赖已准备，命令不是本轮执行记录：

```bash
uv run --frozen --project "apps/runtime-service" pytest -q "apps/runtime-service/tests/runtime/test_tool_governance.py" "apps/runtime-service/tests/services/dearflow_agent/test_mcp_tools.py" "apps/runtime-service/tests/services/test_resource_reconnect.py"
uv run --frozen --project "apps/platform-api" pytest -q "apps/platform-api/tests/test_runtime_catalog_delegation.py"
```

Schema/maintenance 定向测试按 U02 再执行；若改生产代码，还需对应 lint/类型检查。只做测试/文档不新增 DB/数据模型，安全和回退检查聚焦授权不扩大、生产文件不变、无数据删除；不凭空设置性能达标值。

### Phase：2026-10-10 规划核对

- 已执行：三仓 HEAD/相关状态读取；当前 MCP 调用方、声明、目录刷新、测试源码及 DeerFlow reset/cache/pool 的只读检查；官方 MCP 查询；锁定 0.3.2 适配器源码核对。
- 文档验证：`git diff --check` 通过；首次本地链接/代码路径检查发现 1 处相对路径层级错误，已修正；重检全部通过。2 篇新增文档的尾随空白、冲突标记与代码围栏检查通过。收尾时还核对了资源绑定的实际字段并修正表述。
- 未执行：U/I/E 功能测试、浏览器、性能、生产部署验证。本工作区无 Runtime `.venv`；规划阶段不为此安装/启动完整服务。
- 结论：静态证据支持“当前无跨 Run MCP cache/pool，原案无需新增”；`.env` 热更新未覆盖，不能把替代路径称为原案全部已实现。

### Final：实施验收

**不适用：2026-10-10 用户确认不开发 F15 原案，评估关闭。** 本轮只有文档检查，没有新增能力或功能验收结果。未来另行接受并实施后续候选时，再按真实证据逐项登记；本次评估完成不代表现役环境或整个 DearFlow 项目验收完成。

## 状态

**已完成（评估关闭）：2026-10-10 用户确认不开发 F15 原案；源码评估、取舍记录和前端交接已完成。** R01–R04/F01 是未排期的参考项，不属于本次交付。配置热更新和缓存/池化只有满足 §7 条件后才重新规划。
