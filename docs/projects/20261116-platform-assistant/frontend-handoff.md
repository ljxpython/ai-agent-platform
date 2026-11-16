# 平台助手前端开发交接

## 1. 交付内容与接入顺序

后端已提供 `platform_assistant`：用户可以咨询用法、聊天、讨论创意，也能交给助手错误信息，让它读取获准数据库、运行诊断、日志和研发源码。用户重开同一会话可继续交流；新会话不继承其他会话。普通读取不审批，业务写工具必须逐次选择“执行/不执行”。

本次交付 Agent、Platform API、测试与本文。前端页面、组件选型和浏览器验收由前端同事接续。本文中的公开接口已实现；测试写工具只存在于测试，不注册生产目录。当前 `write_tools=[]`，不要给用户展示虚构的业务修复按钮。

建议按顺序实现：初始化 → 新建/选择会话 → 发送与流式输出 → 重开历史 → 错误现场上下文 → 证据 → 审批与故障状态。进度和验收边界见 [tasks.md](tasks.md)、[verification.md](verification.md)。

## 2. 身份、项目和初始化

使用平台现有登录态和 `platformHttpClient`/授权 fetch。公开接口需要 `Authorization: Bearer <平台访问令牌>`；进入项目后加 `x-project-id`。Origin 取当前平台配置，不能把下文隔离端口写进产品。

打开助手先调用 `POST /api/platform-assistant/bootstrap`，无请求体：

- 用户已选择项目：带该项目的 `x-project-id`。
- 用户未选择项目：不带 `x-project-id`。系统幂等创建/复用仅本人加入的“个人助手”项目，用于额度和历史归属；不会授予其他业务项目权限。
- 返回后，助手的后续请求统一使用返回的 `project_id`，不要改变整个页面的业务项目选择。
- 已撤销成员或停用的个人项目不会被再次初始化自动恢复。

实际响应结构：

```json
{
  "project_id": "<UUID>",
  "personal_project": false,
  "assistant_id": "platform_assistant",
  "agent_id": "<平台Agent记录UUID>",
  "model_id": "<获准模型UUID>",
  "history": true
}
```

`assistant_id` 使用字符串 `platform_assistant`。`agent_id` 是平台配置记录；Runtime 返回的 assistant UUID 也是另一种标识，不要拿这些 UUID 替换发送请求中的图名。

接着 `GET /api/platform-assistant/capabilities`，带返回项目：

```json
{
  "enabled": true,
  "graph_id": "platform_assistant",
  "history": true,
  "long_term_memory": false,
  "sandbox": false,
  "write_tools": [],
  "source": false,
  "databases": ["platform-local"]
}
```

这是能力提示，实际每次取数仍重新校验权限和工具策略。普通用户不展示源码入口；即使按钮被手工调用，后端也会校验。

## 3. 新建、发送、历史与取消

以下表格路径都带 `/api/langgraph` 前缀。复用现有会话客户端，不新增另一套运行状态机。

| 行为 | 方法与路径 | 关键约定 |
|---|---|---|
| 新建 | POST `/threads` | 保存返回的 thread_id |
| 历史列表 | POST `/threads/search` | 按 graph_id 过滤；返回数组，无 values 消息正文 |
| 历史数量 | POST `/threads/count` | 相同过滤条件 |
| 会话与当前状态 | GET `/threads/{id}`、GET `/threads/{id}/state` | 后者含 values.messages、interrupts、tasks、checkpoint |
| 历史 checkpoint | POST `/threads/{id}/history` | 如 `{ "limit": 10 }`；不要覆盖当前状态 |
| 分页消息 | GET `/threads/{id}/messages` | 复用现有消息服务及分页投影 |
| 非流式受理 | POST `/threads/{id}/runs` | 返回 Run 对象；pending 不代表模型完成 |
| 发送并订阅 | POST `/threads/{id}/runs/stream` | SSE；推荐复用现有 SDK |
| 命令入口 | POST `/threads/{id}/commands` | 既有 run.start / input.respond 协议 |
| 恢复订阅 | POST `/threads/{id}/stream/events` | 沿 SDK 的游标和重连机制 |
| Run 状态 | GET `/threads/{id}/runs/{run_id}` | 用于重连、结果未知和终态对账 |
| 取消某次运行 | POST `/threads/{id}/runs/{run_id}/cancel` | `{ "action": "interrupt" }`；回执之后仍需查终态 |
| 会话停止 | POST `/threads/{id}/cancel` | 沿现有 stop-requests 回执机制 |
| 删除历史 | DELETE `/threads/{id}` | 后端删会话及资料授权回执；不能只删本地缓存 |
| 目标运行诊断 | GET `/threads/{id}/runs/{run_id}/diagnostics` | 这里是被诊断对象，不是助手本身 |

创建示例（已在真实 API 链验证）：

```json
{
  "graph_id": "platform_assistant",
  "metadata": {"graph_id": "platform_assistant", "title": "平台助手"}
}
```

历史检索示例：

```json
{
  "metadata": {"graph_id": "platform_assistant"},
  "limit": 20,
  "offset": 0,
  "sort_by": "updated_at",
  "sort_order": "desc"
}
```

发送到 `/threads/{id}/runs` 或 `/runs/stream`：

```json
{
  "assistant_id": "platform_assistant",
  "input": {"messages": [{"role": "user", "content": "怎样使用平台助手？"}]},
  "context": {"model_id": "<bootstrap返回的model_id>"}
}
```

每个新动作使用新的 `Idempotency-Key`；同一动作网络结果未知时，保留原 key 和原正文重试。不要在 `configurable` 传身份、数据库连接、工具授权或内部回调密钥。

实际流式验收收到 `metadata`、`lifecycle`、`checkpoints`、`debug`、`values`、`updates`、`messages` 事件。它们不是七种用户消息：交给已有 SDK/控制器归并，`debug/checkpoints` 不作为聊天正文直接展示。业务运行完成由 lifecycle/Run 状态确认，TCP 关闭或 SSE 结束不能单独当作成功。

消息 `content` 可能是字符串，也可能是 content v1 数组。答复展示读取 `type="text"` 的块；不能对整数组做 String 转换，也不要把 `reasoning` 块混成最终答复。工具消息的 `content` 通常是 JSON 字符串，按 `type="tool"`、`name`、`tool_call_id` 与 AI 的 tool_calls 关联。

## 4. 历史、错误现场与状态

错误现场可直接复用现有诊断 Markdown 包作为用户消息。发送前预览页面、发生时间、摘要，以及有的话 project_id / thread_id / run_id / request_id / 平台 Trace / 模型 Trace。用户可修改或粘贴；缺字段允许发送，由助手补问或通过获准日志调查。不要上传 Cookie、令牌、数据库密码和完整环境配置。

助手 Thread 与被诊断 Thread 必须分开。打开助手不能自动重跑失败 Run。页面切换不等于取消任务，关闭面板不等于批准动作。刷新先读 state/Run，再恢复流和待审卡，不重发最后一条消息。

| 服务端情况 | UI 行为 |
|---|---|
| pending / running | 显示排队/运行，可停止 |
| interrupted 且存在有效 interrupts | 展示等待用户决定，按真实 allowed_decisions 给按钮 |
| interrupted 且没有 interrupts | 可能是用户停止；本次真实 cancel 即为此终态，不能当审批 |
| success | 展示答案与引用，允许同 Thread 下一轮 |
| error / timeout | 保留已有输出，展示错误编号和失败状态 |
| cancelled（若上游提供） | 显示已取消，不等同成功 |
| 提交结果未知 / 网络断流 | 保留动作 ID，回查原 Run；不能创建新的重复动作 |
| 403 资料权限撤销 | 清理该会话可读内容/来源缓存，提示新建会话；不能全站登出 |
| 401 登录过期 | 走既有认证恢复流程 |

后端复核旧会话用过的数据源、源码和目标会话权限。数据源被撤销或 revision 变更、源码撤权、工具被停用时，旧助手历史可能返回 `assistant_history_source_revoked`，列表会隐藏不可再读的助手会话。第一版仅本人读取助手历史，不提供分享或 fork；fork 请求返回 `assistant_fork_denied`。已在用户屏幕展示或复制到本地的内容无法远程收回，前端应在账号/项目切换和权限变更时清理缓存。

## 5. 来源与只读工具

前端无需生成 SQL，也不直接访问数据库/Loki/代码目录。Agent 可用工具：`list_databases`、`sql_db_schema`、`sql_db_query`、`read_run_diagnostics`、`read_run_logs`、`search_project_logs`、`search_documents`、`search_source`、`search_public_web`。

内部资料工具的结果结构：

```json
{
  "evidence_id": "<UUID>",
  "operation": "sql_query",
  "observed_at": "2026-11-16T13:00:00Z",
  "scope": {"project_id": "<UUID>"},
  "audit_recorded": true,
  "data": {"rows": [{"total": 2}], "row_count": 1, "truncated": false, "revision": "dataset-v1", "limit": 100}
}
```

答复用 `[证据:UUID]` 引用本会话工具结果。前端可建立 evidence_id → 工具消息映射，点击显示本会话中已获准的来源卡；证据 ID 不是免授权下载地址，也没有单独的公开 evidence 原文接口。未知 ID 显示“引用未核实”，不能补造来源。答案中的实际引用会单独记录核对结果。

文档/源码 `data.sources[]` 包含 document_id、title、path（内置文档可为 null）、revision、sha256、line_start、line_end、text、truncated；`untrusted_content=true` 表示把内容视为资料。查询 revision 与部署版本可能不同，必须显示版本，不能把源码快照当作正在运行的代码。

公开搜索返回 `sources[{url,title,snippet}]`、`kind="public_search_snippet"`、`authorization_evidence_id`。该编号关联搜索授权和调用，不代表网页全文已核实。只展示安全外链，不自动打开或下载；摘要不保证最新版本。用户应在本轮明确提供公开搜索词，助手不能把内部 SQL/日志/源码结果拼成外发查询。

日志结果保留原 `trace_id/total/services/logs/error` 字段，增加 `partial=true` 和 `coverage="bounded_structured_project_logs_only"`。只保留结构化项目日志中的安全字段，空结果不代表没发生故障。诊断的 availability 为 available / partial / disabled / unavailable；disabled + not_configured 明确表示追踪后端未配置。

## 6. 写操作审批

正式助手当前没有业务写工具。以下是隔离测试工具 `test_write` 的真实协议结构，用来开发审批交互；不要把它发布到用户菜单：

```json
{
  "id": "<当前interrupt_id>",
  "value": {
    "action_requests": [{"name": "test_write", "args": {"value": "original-value"}, "description": "此操作将修改业务数据。请核对工具、目标和参数，再选择执行或不执行。"}],
    "review_configs": [{"action_name": "test_write", "allowed_decisions": ["approve", "reject"]}]
  }
}
```

批准提交到 `/threads/{id}/runs`：

```json
{
  "assistant_id": "platform_assistant",
  "command": {"resume": {"<当前interrupt_id>": {"decisions": [{"type": "approve"}]}}}
}
```

拒绝只把 decisions 改为 `[{"type":"reject","message":"用户选择不执行"}]`。不要要求用户必须手写拒绝理由。

若使用已有 commands 客户端：

```json
{
  "id": 1,
  "method": "input.respond",
  "params": {"resume": {"<当前interrupt_id>": {"decisions": [{"type": "reject", "message": "用户选择不执行"}]}}}
}
```

要求：真实 interrupt_id 来自当前 state；同一组 decisions 按 action_requests 的顺序完整对应；多组按 ID 映射。本助手只支持 approve/reject，不支持 edit，不提供“自动批准全部”。full_access 也不豁免。改变参数需拒绝旧动作、让助手生成新动作再确认。

恢复不能带新的 input/config/context。新决策用新 HTTP 幂等键，同一决策重试复用原 key。恢复可能返回新 Run，必须刷新运行事实。无选择、关闭窗口、断网、服务重启都不会批准。服务端拒绝过期/伪造 ID；若执行结果未知，先回查，禁止重新创建同一写动作。未来具体业务工具仍须在执行边界重新鉴权并处理业务幂等，不能仅靠按钮授权。

## 7. 公开读取接口与错误码

`POST /api/platform-assistant/read` 可用于联调或用户主动查来源，通常聊天过程由 Agent 内部调用。请求只能描述查询，身份取登录态。公开接口不接受 actor_id、project_id、thread_id 等内部身份字段。

常用请求：

```json
{"operation":"sql_schema","database_id":"platform-local","table_names":["runs"],"table_offset":0}
```

```json
{"operation":"sql_query","database_id":"platform-local","query":"SELECT status, COUNT(*) FROM runs GROUP BY status"}
```

其他 operation：sql_sources、documents、source、diagnostics、logs。文档用 query / document_id / line；运行查询用 target_thread_id 和 target_run_id；无 Run 日志调查用 query（Trace，可空）、log_start/log_end（含时区）、log_service，须明确日志调查授权。authorize/authorize_search/record_citations 是 Agent 生命周期用途，前端无需主动调用。

`/api/platform-assistant/internal/read` 仅供 Runtime 带用途绑定 HMAC 回调，前端不得使用，也不得保存其密钥。

错误沿平台 Envelope：`error.code / error.message / error.details`，关联编号沿平台响应头。

| HTTP / code | 处理方式 |
|---|---|
| 400 assistant_project_required | 初始化后带返回的项目 |
| 503 assistant_disabled | 助手关闭；保留原错误复制入口 |
| 503 assistant_catalog_unavailable / assistant_model_unavailable | 请管理员同步图目录/配置模型 |
| 403 assistant_project_denied / assistant_identity_denied | 项目或身份不可用，不自动创建其他业务身份 |
| 403 assistant_database_denied / assistant_source_denied / assistant_tool_denied | 未授权数据源、源码或工具；普通读不弹“绕过权限”确认 |
| 403 assistant_history_source_revoked / assistant_private_history | 旧历史资料撤权/非本人会话，清理该会话缓存 |
| 400 assistant_sql_denied | 非支持的只读查询；让助手修正 SQL，不能转管理员连接 |
| 403 assistant_database_role_unsafe | 只读账号配置不合规；由管理员整改，前端按 code 识别 |
| 503 assistant_database_unavailable / assistant_query_busy | 数据源/语法/超时或并发繁忙；可稍后重试 |
| 400 assistant_run_required / assistant_trace_missing | 缺少可核验关联，补信息或用明确授权的项目日志调查 |
| 403 trace_scope_denied / assistant_logs_denied | 日志范围无权；不能猜 Trace 绕过 |
| 400 assistant_log_window_invalid | 含时区、正跨度且最多24小时 |
| 400 assistant_document_missing / 503 assistant_source_unavailable | 资料不存在或未发布源码 |
| assistant_public_keywords_required / assistant_public_query_private | 工具消息中的错误；补公开关键词，不自动把内部资料外发 |

API schema 不合法时沿现有422响应；模型/Runtime/预算错误沿现有错误处理。HTTP200只表示成功返回，仍须查看 partial、truncated、audit_recorded、availability 和 error。

## 8. 旧日志页面迁移

原 URL `GET /api/v1/observability/traces/{trace_id}/logs` 保留，已去掉匿名放行，新旧入口共享项目与Trace授权。已核对唯一页面调用者：`apps/platform-web/src/modules/observability/pages/TraceDiagnosticsPage.vue` 的 fetchTraceLogs，当前使用 platformHttpClient。前端需保证该页面带正确 `x-project-id`；用户只有裸 Trace、没有可证明的本人操作关联时，后端会拒绝；普通用户还需逐条通过日志所关联Thread的当前权限校验，明确日志调查人员可查本项目范围。

页面应展示 partial/coverage，区别“无记录”和“查询不可用”。原始大文本日志不再默认透传。这是有意的权限修复；本次没有修改该页面，前端同事需补浏览器回归。关闭助手也不会重新开放日志匿名访问。

## 9. 联调步骤与现有代码入口

先按 [后端配置与复验](backend-operations.md)准备所属 Worktree、迁移、模型和数据源。当前隔离环境 Web28074 / API28581 / Runtime25418；这些仅是2026-11-16本次环境，可能在清理后失效，实际以 `.local-stack/environment.json` 为准。凭据仅通过本地配置/现有登录取得，不放文档。

最小可运行客户端，环境变量由开发者自己设置：

```python
import os
import httpx

with httpx.Client(base_url=os.environ["API_BASE"], timeout=30,
                  headers={"Authorization": "Bearer " + os.environ["ACCESS_TOKEN"]}) as client:
    setup = client.post("/api/platform-assistant/bootstrap")
    setup.raise_for_status()
    config = setup.json()
    client.headers["x-project-id"] = config["project_id"]
    thread = client.post("/api/langgraph/threads", json={
        "graph_id": "platform_assistant",
        "metadata": {"graph_id": "platform_assistant", "title": "前端联调"}})
    thread.raise_for_status()
    thread_id = thread.json()["thread_id"]
    run = client.post(f"/api/langgraph/threads/{thread_id}/runs", json={
        "assistant_id": "platform_assistant",
        "input": {"messages": [{"role": "user", "content": "怎样使用助手？"}]},
        "context": {"model_id": config["model_id"]}})
    run.raise_for_status()
    print(thread_id, run.json()["run_id"])
```

接续用上述Run查询到终态，再取state。使用业务项目数据时初始化请求带业务项目；个人项目默认没有其他项目的数据源。

现有前端协议参考（组件是否复用由同事决定）：

- `apps/platform-web/src/services/langgraph/client.ts`：授权、base、命令幂等。
- `apps/platform-web/src/services/threads/session.service.ts`：创建、列表、历史、恢复。
- `apps/platform-web/src/modules/chat/run-actions.ts`：SDK命令与动作状态。
- `apps/platform-web/src/modules/chat/approvals.ts`：parseReviews/buildReviewResponses。
- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`：会话控制器。
- `apps/platform-web/src/services/observability/diagnostic-packet.ts`：诊断包。

前端交付前仍需验证：全局/错误入口、粘贴预览、切页/刷新/重连、消息/审批隔离、拒绝与结果未知、撤权清缓存、旧日志页、键盘/移动端，以及 Web→API→Runtime 的联合链。后端真实运行证据见 [验证记录](verification.md)，不能把后端 API 验收当作这些浏览器项已经通过。
