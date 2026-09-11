# G1 契约与会话基础（进行中）

> 历史累积记录：早期“待实施/未验证/阻塞”仅代表当时阶段。当前任务状态见 [项目概览](../README.md) 与 01—07 专题；消息及发布的后续结论见 [09](09-message-delivery-completion.md)、[10](10-graphharbor-post27-release.md)。

## 授权与范围

2026-09-10 用户明确要求完成本项目全部需求，无需介入时持续实施。01—07 实施范围已授权，07 仍放在前端主体验收之后；不再把先前文档中的“新增扩展待评审”当作重复审批阻塞。提交、推送、生产发布不在本次执行范围。

## 已改动

- `apps/platform-web/package.json` / `pnpm-lock.yaml`：升级 `@langchain/vue` 至 1.0.35、`@langchain/langgraph-sdk` 至 1.10.2；已核对 Vue 包依赖该 SDK 版本。安装提示既有 vite-plugin-checker/vue-tsc peer 不匹配，后续工程检查处理。
- `apps/platform-web/src/services/agents/types.ts`、`agents.service.ts`：新 Agent DTO 与独立创建/更新白名单，保留空 tools/context 的明确语义，详情按 UUID GET。旧页面尚未迁移，旧 assistants 模块暂待消费者迁出后删除。
- `apps/platform-web/src/stores/workspace.ts`：权限请求 epoch、切换立即清空旧 access、退出使 hydration 失效；新增错误与加载状态。
- `apps/platform-web/src/stores/auth.ts`、`services/http/client.ts`：合并身份 hydration、退出后忽略旧 profile，刷新 token 返回时复核原 refresh token，避免覆盖新登录。
- `apps/platform-web/src/modules/chat/run-actions.ts`：每 Session 的冻结动作与实际 wire body，未知结果仅重试原 key/body；官方 SDK 多 interrupt `responses` 映射到平台 `resume`，拒绝配置覆盖。
- `apps/platform-web/src/services/langgraph/client.ts`：确保 SDK 地址绝对化，合并 Request 原有 headers。旧自动 key 逻辑待全部消费者迁移到新动作入口后移除。
- `apps/platform-web/e2e/support/platform.ts`、`src/modules/chat/sdk-chain.test.ts`：隔离测试项目与真实官方 Vue SDK 链路用例，凭据仅在进程内，错误只记录路由/状态码/错误码。

## 验证记录

- 新 Agent 服务、workspace 竞态、动作幂等、既有认证 fetch：4 个文件、13 项通过。
- 本地 Platform API 旧进程仍加载已退役 `main` 入口；经统一脚本 `restart-one platform-api` 后当前 factory 入口健康检查通过。未改后端源码。
- Runtime 旧进程未加载当前默认 Assistant 发现能力；API/Worker 经统一脚本切到 `langgraph.demo.json` 后目录恢复。GraphHarbor 工作区已有用户未提交改动，未覆盖、未修改其源码。
- 原 Platform API 使用旧 SQLite 数据文件，存在 provider/base_url/protocol/model 为 null 的遗留模型，导致新契约响应验证 500。建立本任务独立临时 SQLite 基线并通过进程环境覆盖启动，保留原数据库及 `.env`。Runtime PostgreSQL 继续使用受信项目隔离。
- 真实 Agent 创建暴露 Runtime schema introspection 缺陷：`reference_agent` / `workflow_demo` 在 GraphHarbor 只传 graph_id 读取 schema 时要求执行 principal。增加只读构造分支；reference 复用 RuntimeConfigMiddleware 阻止无身份执行，workflow 在 prepare 阶段拒绝 probe 执行并声明 RuntimeContext schema。修改及测试均在 Runtime，未加入 GraphHarbor 业务代码。
- Runtime `tests/services/test_schema_introspection.py`、workflow/reference Agent 测试：22 项通过，包含不访问执行模型和不能调用 probe 图。
- 真实 SDK 链路验证进行中；尚未完成 G1、页面重写、渲染、真实浏览器或队列验收。

## 后续

完成 G1 真实发送/审批/恢复/子图/checkpoint 门禁，再推进 G2—G6。进度以实际验证为准，不把新增文件或旧测试通过记作主体重构完成。

## 2026-09-11 续作

- Runtime 只读工厂进一步覆盖 Thread state/history 的 checkpoint 配置。reference 使用与执行相同的 middleware 拓扑；RuntimeConfigMiddleware 的 probe_only 在所有模型/工具边界拒绝执行。workflow 所有节点在只读构造中拒绝执行，避免恢复 checkpoint 绕过 prepare。26 项相关测试通过。
- 真实 SDK 自动把 URL 中的 thread_id 重复放入 configurable，平台不接受。run-actions 校验 ID 一致后移除此冗余字段；标准 Runs checkpoint 写请求也纳入冻结 key/body 与结果未知处理。
- 在 GraphHarbor 源码修复通用事件协议（未发布，未加入业务代码）：protocol_event 添加 type:event，message-start 保留真实消息 ID、展平原生消息 payload 并保留 node/namespace，审批 value 映射为官方 payload；执行器改用 LangGraph 原生 astream_events v3，根 lifecycle 仍由 worker 提交 Run 终态后发出。源码涉及 graph_executor.py / protocol.py，新增 test_vue_protocol_events.py，更新 test_public_runtime.py。原有其他未提交文件保持。
- GraphHarbor 本地源码以进程级 PYTHONPATH 加载：`../graphharbor/libs/langgraph-runtime-pg/src:../graphharbor/libs/langhost/src`（启动使用绝对路径），统一 local-stack restart-one；未修改 site-packages 或依赖锁中的发布版本。
- `sdk-chain.test.ts` 真实官方 Vue SDK 通过：创建 Thread→发送→终态→卸载/重新挂载→相同消息 ID；workflow 审批→新 Run；标准 checkpoint 分支→读取旧 checkpoint。最后一次完整扩展用例约 10.25 秒。SDK hydration 后 Vue 投影异步发布，断言等待投影就绪；未写入 SDK 私有状态。
- 前端新增 approvals.ts：多 ID 映射、无默认批准、类型保持编辑、拒绝额外参数；2 项测试通过。新增 useChatSession.ts / session.service.ts / transcript.ts，尚未接入页面，仍在验证。
- auth/token 与 HTTP/fetch 增加登录代际隔离，旧请求不得刷新或重试到新账号。前端相关 4 文件 10 项测试通过；新增模块类型检查仍在进行。

### 环境与当前限制

- Platform API 验收使用独立 `/tmp/platform-web-refactor-1dkx9td8.sqlite`，重启必须保留 `PLATFORM_API_DATABASE_URL=sqlite+pysqlite:////tmp/platform-web-refactor-1dkx9td8.sqlite`、`PLATFORM_API_PLATFORM_DB_AUTO_CREATE=true`。恢复原启动配置即回原库；旧库未修复/迁移。
- GraphHarbor 测试新建独立 PostgreSQL `graphharbor_web_refactor_20260910`，已执行该库 migrate upgrade；测试的 truncate 仅对此专用库，未指向运行中的 graphharbor_acceptance。Redis 测试 prefix 为 `graphharbor:web-refactor-tests`。
- GraphHarbor public_runtime：17 通过；新增事件测试 2 通过。扩大到 official_sdk_contract + production_contract：53 通过、4 skipped、2 失败。失败为 Python 3.11 fixture 使用 typing.TypedDict（应 typing_extensions）以及既有 auth scope 用例创建 Thread 未拿到 ID；正在处理，不能标全量通过。
- G1 尚缺并行子图、多审批、取消完整证据。页面、13 项渲染矩阵、退役清理、G6、Q0—Q5 仍未完成。普通审批通过不等于多审批验收通过。

### 2026-09-11 Chat 页面接入

- ChatPage 已替换为新 ChatSession，单一 useStream 管消息；加入 Transcript、MessageContent、ToolResult、ApprovalPanel、SubtaskDetail。工具结果按调用 ID 关联，连续正文保留；子任务展开才挂 scoped selectors。Inspector、历史检查点与编辑分支已接入，后两者仍待浏览器验收。
- 首次发送使用 SDK 顶层 graphId：SDK 会覆盖 metadata.graph_id，仅设置 metadata 会导致刷新无法恢复。session.service 回归测试固定此行为，并固定网关 checkpoint_id 查询及 history.before 的公开形状。
- 审批规范化比较排除 SDK 自动增加的 camelCase 别名，以工具名称、参数、允许决策及其余公开信息判断是否变化。真实 SDK 测试同时比较流中审批与 state 审批。
- 草稿在动作 ACK 后清除，用户已编辑的下一条文本保留；Enter 同时检查权限/可发送/审批门禁。附件增加每个 5 MB、最多 8 个、总计 20 MB 边界与销毁后忽略异步读取。
- Chromium 真实浏览器用例 `e2e/chat-refactor.spec.ts` 通过（16.8 秒）：创建一次 Run、ACK 清草稿、下一条草稿保留、刷新相同 Thread、workflow 人工批准后恢复、继续发送门禁、无 pageerror。截图 `/tmp/platform-web-chat-refactor.png`。未使用生产环境；测试项目由用例删除。
- `sdk-chain.test.ts` + `approvals.test.ts`：5 项通过；transcript/run-actions/session service 的上一轮 4 文件 7 项通过。最新 vue-tsc 已通过，后续页面迁移仍需重跑。
- GraphHarbor official_sdk_contract + production_contract + vue_protocol_events：55 通过、4 skipped。修正 Python 3.11 测试 TypedDict 导入；原生产鉴权用例显式配置 Auth hook，保留业务鉴权不属于引擎的边界。该测试文件原有用户改动未覆盖。
- 当前仍未完成：Agent/Model 页面迁移、显式项目路由与导航、旧源码退役、并行多审批/子图与取消验收、13 项矩阵全面验收、G6 和 Q0—Q5。浏览器截图中的子图终态仍需核查；重连时附件草稿保留、参数边界等继续收尾。


### 2026-09-11 控制面与渲染收敛

- 新增项目作用域 Agent 列表/编辑/删除页面及真实 CRUD 浏览器验收；context 仅提交白名单字段，模型使用目录 UUID，工具空数组可持久化。
- 总览改为真实 Agent/Thread 数据，移除旧助手、SQL Agent、Threads 和聊天目标持久化入口；Graphs、Models 均改为显式项目路由。
- 模型页按新目录响应渲染，并加入模型/工具项目策略；去除旧同步、runtime_id、model_id 显示依赖。
- Chat 工作过程按回合折叠；审批按请求指纹保留未变化决策；附件批量去重并支持父级草稿跨 remount 保留。
- 验证：vue-tsc 通过；相关 Vitest 35 passed/1 skipped；Chat 与 Agent CRUD Playwright 真实链路通过。

### 2026-09-11 G6/Q0 启动

- G6 仅有前序局部单元与单审批浏览器证据；并行审批、移动端和全量门禁尚未验收，不能标记通过。
- Q0 尚未执行分进程持久化/崩溃 Spike；代码检查发现 Runtime 原有进程无业务数据库层。新增独立 `runtime_service.messaging.MessageInbox` PostgreSQL 表模型，采用单条消息、稳定 UUID、幂等键和顺序字段，未侵入 GraphHarbor。
- Q1/Q2/Q3/Q4/Q5 尚未完成；队列接口暂未接入，避免把未验证的内存/伪持久实现发布为可靠能力。

### 2026-09-11 验证状态纠正

前序记录与回复中 G6/移动端/Q0 的措辞超出了测试证据。当前 G6、Q0—Q5 均为 partial/待完成，inbox 只有隔离草稿，未挂载到 HTTP 或应用启动；claim/ack 尚无数据库测试，不应作为可靠队列使用。继续先完成前端与引擎协议门禁。

### 2026-09-11 Q1/Q3/Q4 接入

- Runtime 增加受信委托内部入队接口及独立 PostgreSQL inbox；Platform API 增加项目/Thread/Run 状态校验代理；Web Chat 运行中提供排队发送。
- 新增 messages.service 单测通过；三端 Python/TypeScript 编译通过。claim/ack、before_model 注入及双端故障验收仍未完成。
