# 前端交接：通用 Plan Mode 与计划审批

> **契约状态：Runtime/API 已实施并冻结，前端待同事接手。** 下列 DTO、错误码和状态边界来自当前后端代码；JSON 仍是脱敏合成示例，不替代真实联调证据。

## 交接目标与职责

在现有 Chat 增加“先规划”选择、计划预览和人工审阅。用户批准后 Agent 可以在当前原授权下执行；“批准计划”不会关闭逐工具审批，不代表所有工具获得全权。

Runtime 决定规划权限和执行，API 决定当前身份能否审批、版本匹配、幂等和安全投影。前端只提交当前 interrupt 的决定、显示真实状态，不能把 toggle、消息中的“批准”、本地 storage 或历史 plan 作为放权依据。

前端实施和浏览器验收由用户同事承担。本轮未修改前端；后端隔离验证服务已自动回收。当前项目处于“后端完成、前端待接入”的部分完成状态，未部署现役。

## 必须复用的工程入口与架构约定

| 完整路径，相对仓库根 | 改造与接入规范 |
| --- | --- |
| `apps/platform-web/src/modules/chat/composables/useChatRunConfig.ts` | 管理单次新 Run 的 `plan_mode` bool 草稿与发送后自动重置；保持 `execution_mode` 正交；提交后锁定本次运行配置，不污染 `AgentContext` 实体默认属性 |
| `apps/platform-web/src/modules/chat/components/ChatComposer.vue`、`ChatRunOptionsDialog.vue` | 输入框左下角新增功能拓展入口（“+”号/功能菜单），点击可勾选“先规划 (Plan Mode)”；激活后在输入框上方常驻“📋 规划模式已启用”可移除胶囊徽章；`ChatRunOptionsDialog` 同步展示与联动配置 |
| `apps/platform-web/src/types/workspace.ts`、`services/threads/workspace.service.ts` | 增加可选 `plan_mode` capability；采用**两级能力判定（Two-tier Capability Resolution）**：新会话基于当前 Agent/Graph 白名单（`PLAN_GRAPHS`）推导，已有会话通过 `/threads/{thread_id}/capabilities` 权威查询；缺失或 false 隐藏/禁用入口 |
| `apps/platform-web/src/modules/chat/plan-review.ts`，新增纯函数模块 | 严格校验与解析 `agent_plan_review` interrupt 与 `agent_plan` 状态 DTO，生成快照指纹与 response payload，提供 `isPlanReviewInterrupt`、`parsePlanReview`、`buildPlanResponse` |
| `apps/platform-web/src/modules/chat/approvals.ts:parseReviews()` | 排除 `agent_plan_review`，避免与普通工具审批（action_requests）混淆或误报为“不支持审批” |
| `apps/platform-web/src/modules/chat/composables/useSessionInterrupts.ts` | 集中管理 `planReview` 状态；将计划审批并入 `hasPendingInterrupts`，解决输入框锁定与焦点拦截；在 `syncAuthoritativeInterrupts` 中同时核对 plan review 与 state 权威快照 |
| `apps/platform-web/src/modules/chat/run-actions.ts` | 复用原命令通道、Idempotency-Key、body 和 unknown 对账；计划回复严格走已有 `input.respond`，不另建第二套 HTTP 状态机 |
| `apps/platform-web/src/modules/chat/components/PlanReview.vue`，新增组件；`ChatSession.vue` | **实时与历史双重视图（Dual-surface Plan Presentation）**：待审态（`awaiting_review`）在消息流底部审批区渲染完整交互卡片（标题、Markdown、版本哈希、Approve / Request changes / Abandon 动作与反馈输入）；历史态（`approved` / `abandoned`）或规划中（`planning`）在消息流呈现紧凑摘要卡片，并可一键呼出右侧 `Inspector` 抽屉查看 64 KiB 完整正文，支持一键复制 Markdown |
| `apps/platform-web/src/utils/markdown.ts:renderMarkdown()` | 强化协议白名单清洗，强制只允许 `http:`、`https:`、`mailto:`，严格拦截 `javascript:` 与 `data:` 等伪协议以防御 XSS Canary；容器增加局部滚动与防溢出样式，完美支撑 64 KiB 正文 |

### 状态隔离与 Context 载体约定

1. **载体选择**：前端在提交新 Run 时，将 `plan_mode: boolean` 注入到 `config.configurable.platform_runtime.plan_mode`。严格发送布尔值，禁止发送字符串、null 或其他类型。
2. **草稿隔离**：下一次运行的 `draftPlanMode` 属于一次性草稿。当且仅当消息正式开始提交并建立 run action 时，本地草稿自动复位为 `false`；若网络预检未通过或本地校验拦截，草稿予以保留。
3. **正交性保持**：`access_policy`（访问策略）、`execution_mode`（DearFlow 四档模式）、`plan_mode`（独立布尔开关）三者保持正交，严禁将 plan mode 作为第五个 execution mode。
4. **生命周期分离**：下一次运行 toggle 与服务端当前 `agent_plan.active` 是两套独立状态。关闭 toggle 不能解锁尚未批准的计划；当前运行开启规划首步后，不能通过 UI 强行切回普通执行。

## 冻结契约与合成示例

### 支持能力与两级判定策略

为避免新会话无 `threadId` 时调用 `/threads/{threadId}/capabilities` 接口发生死锁，前端采用两级判定：
1. **Tier 1（新会话，`threadId` 为空）**：依据当前选中的 Agent 所属 `graphId` 进行图级能力推导。当前 Runtime 声明支持的图白名单包括：`dearflow_agent`、`reference_agent`、`showcase_demo`、`workflow_demo`。在白名单内即开放“先规划”选项。
2. **Tier 2（已有会话，`threadId` 非空）**：向网关查询 `/api/langgraph/threads/{thread_id}/capabilities` 取得权威值：

```json
{
  "schema_version": 1,
  "graph_id": "reference_agent",
  "workspace": false,
  "plan_mode": true
}
```

能力缺失、为 false 或服务端返回 400 `plan_mode_unsupported` 时，前端隐藏或禁用入口，不自动降级成普通运行。

### 新运行请求

沿用当前 `stream.submit` 管道，在 `config.configurable.platform_runtime` 中携带单次生效的 `plan_mode`：

```json
{
  "config": {
    "recursion_limit": 1000,
    "configurable": {
      "platform_runtime": {
        "execution_mode": "standard",
        "plan_mode": true
      }
    }
  }
}
```

禁止在 resume 请求中携带上述 Context/config，也不得提交内部 `plan_execution_id` 或 `runtime_plan`。


### 当前原生 interrupt

从 SDK 当前 interrupt 读取外层 ID，value 严格识别 type/version：

```json
{
  "id": "interrupt-demo-plan-01",
  "ns": [],
  "value": {
    "version": 1,
    "type": "agent_plan_review",
    "plan_id": "11111111-1111-4111-8111-111111111111",
    "revision": 2,
    "content_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "title": "补充通用审批能力",
    "markdown": "## 目标\n先核对契约，再补充执行门禁。\n\n## 验证\n覆盖越权、恢复与重复提交。",
    "allowed_decisions": ["approve", "request_changes", "abandon"]
  }
}
```

该 hash 只是合成占位值，不与正文计算匹配。客户端不自行重算 hash 来赋予权限，也不重写 plan ID/revision。revision 严格正整数，最大正文 64 KiB UTF-8，未知决定/type/version 不渲染可操作按钮，显示安全不支持态并刷新当前 state。

首期计划审批只由 primary Agent 产生；Workflow 的嵌套 model 也属于 primary 路径，真实 namespace 可能非空，前端应保留 SDK 的 id/ns，不能硬编码为 `ns=[]`。存在其他未解决 interrupt 时按冻结契约和 ID map 处理，不默认为一个全局批准。task 子 Agent 不拥有计划控制工具；已有普通工具审批和 clarification 不能合并成计划决定。

### 人类批准请求

沿既有 `POST /api/langgraph/threads/{thread_id}/commands`，保持当前 `x-project-id` 与授权请求头，通过 run-actions 提交；外层 id 沿当前协议为整数，与 HTTP Idempotency-Key 分别管理：

```json
{
  "id": 101,
  "method": "input.respond",
  "params": {
    "resume": {
      "interrupt-demo-plan-01": {
        "version": 1,
        "type": "agent_plan_response",
        "plan_id": "11111111-1111-4111-8111-111111111111",
        "revision": 2,
        "content_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "decision": "approve"
      }
    }
  }
}
```

附既有 `Idempotency-Key`；一次用户动作持有固定 ID/key/body。服务端回复沿原命令成功格式给恢复后的 run_id/thread_id，Run ID 可以改变。HTTP 成功只表示恢复提交被接受，实际批准/执行从 SDK 和当前 state 对账。

`request_changes` 的同一 response 额外携 `feedback`（去首尾空白后 1-2000 字符）；`abandon` 可附反馈，运行结束且规划限制仍保留。客户端不能提交 `approved_by/approved_at/active/plan_mode/config/context/input`。不支持直接修改 Markdown 正文、行内批注或批准人字段。

### 只读公开状态

在已授权 Thread state 的 `values.agent_plan` 或对应原生 state 槽位取得有限投影：

```json
{
  "version": 1,
  "status": "awaiting_review",
  "active": true,
  "plan_id": "11111111-1111-4111-8111-111111111111",
  "revision": 2,
  "content_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "title": "补充通用审批能力",
  "markdown": "## 目标\n先核对契约，再补充执行门禁。",
  "decision": null
}
```

无计划时 `agent_plan` 可缺失，客户端按可选字段处理；status 为 planning/awaiting_review/approved/abandoned。未保存草稿的 revision=0、content_hash=null、title/markdown 为空字符串；只有保存稿才有正整数 revision 和非空 hash，不能把空草稿渲染成可审批计划。decision 为 approve/request_changes/abandon/null。当前 awaiting_review 必须有当前原生 interrupt 支撑；只有投影没有 interrupt 时仅展示，不能批准。未批准时 `approved_by/approved_at` 省略；批准后 `approved_by` 严格为 `{user_id: string}`，本期没有 display_name，approved_at 是服务端带时区 ISO8601 时间。批准的旧版本只显示“历史已批准”，不能给新执行放权。

DTO 按严格字段/白名单解析；剥离 extra，不保存内部状态、执行标识、签名或原始中断 raw 大对象到 localStorage。后端上线后需用真实同一 Run 的 live/state/history 样例替换/补充 fixture。

## 交互与各状态规范

| 场景 | 展示形式 | 用户动作与控制 |
| --- | --- | --- |
| 未开启且无计划 | 普通 Chat；左下角“+”菜单提供“先规划” | 下一次 Run options 可选先规划；勾选后输入框上方常驻激活胶囊 |
| planning | 规划中状态；消息流内展示规划中状态卡，有草稿时可点击呼出 Inspector 预览；无正文不显示空卡 | 原有 Stop 保持可用；不能提前批准/切执行；输入框处于运行锁定 |
| awaiting_review，当前可审批用户（owner/manager） | **底部审批区大卡片**：展示标题、revision、Markdown 局部滚动视图与版本哈希；**输入框锁定**并提示等待决策 | 批准并执行、请求修改（展开 1-2000 字符反馈输入框）、放弃计划；快捷键 `Ctrl+Enter` 提交修改 |
| awaiting_review，只读或共享用户（read/comment/edit） | 底部审批区展示计划正文，按钮置灰并提示“仅项目管理者/所有者可审批计划” | 不显示放权按钮；输入框锁定保持等待态 |
| 请求修改已接受 | 审批卡片收敛，消息流记录反馈内容；等待 SDK 恢复规划，产生新 revision 后再次唤起审阅 | 保留反馈快照直到新回合明确；新稿到达前不可重复提交 |
| approved | **双重视图**：底部审批区收起；消息流内沉淀紧凑摘要卡片（展示标题、批准人、批准时间，支持一键在 Inspector 展开完整正文与一键复制 Markdown）；执行进度沿现有 Chat 流推进 | 普通工具 HITL（如 `write_file`、`execute`）继续正常拦截；批准不代表 Run success |
| abandoned | 底部审批区收起；消息流内沉淀已放弃卡片；Run 已终止 | 新消息可重新发起规划；不将 `active: false` 违规写回服务端 |
| stopped/timeout/budget/error | 沿原状态展示真实终态与计划历史卡片 | Stop 不等同于 abandon/approve，不自动 resume |
| loading/error/unsupported/旧版本 | 骨架占位或安全错误，正文未完整时不提供放权操作 | 刷新当前 state；禁用批准按钮，保留用户反馈草稿 |

### 计划正文渲染与安全规范（Markdown & XSS 防御）

1. **协议白名单**：正文使用现有 MarkdownIt 渲染，严格清洗链接目标（`href`）。强制仅允许 `http:`、`https:`、`mailto:`，拦截任何 `javascript:`、`data:`、`vbscript:` 等危险伪协议，点击危险链接时安全降级或阻止导航，防御 XSS Canary。
2. **防溢出与大文本局部滚动**：最大正文支持 64 KiB UTF-8。正文容器设置局部滚动上限（如 `max-h-[50vh] overflow-y-auto`），代码块与大表格使用局部横向滚动容器包裹，移动端（390px）自适应换行，严禁撑破外层主聊天面板。
3. **Inspector 抽屉联动**：历史计划卡片与规划中草稿卡片提供 `[查看完整计划]` 按钮，点击后平滑联动当前已有右侧 Inspector 抽屉，在抽屉中以大屏全幅模式展示计划 Markdown，并提供顶部固定复制按钮 `[复制 Markdown]`。

## 提交、并发和自愈处理

1. **指纹校验与动作防抖**：动作前按 `useSessionInterrupts` 模式拉取/复核当前 ID、revision 和 content_hash 指纹；新稿、旧 ID 或 run status 变化后立即可用状态失效。
2. **本地单飞控制**：同一计划同时只允许一个本地提交；触发后按钮进入 loading 态并锁定，未知结果不擅自标为已批准。
3. **网络 timeout/unknown**：保留原 ID/key/body 并按现有 `run-actions` 对账；手动重试复用原请求，不能切换决定复用同一 key。
4. **已接受流转**：跟随返回的新 Run 与官方 SDK 流，重新读取当前 state，不从本地直接推断写死 `approved` 或 `active: false`。
5. **权威同步与 409 自动恢复**：
   - `useSessionInterrupts.ts` 中的权威同步函数升级为 `syncAuthoritativeInterrupts`，同时核对普通 tool reviews、clarifications 和 plan review；
   - 当服务端返回 409（`plan_revision_conflict` / `interrupt_not_active`）时，前端捕获该冲突，立即自动发起 `service.state()` 查询最新真实状态，旧可操作面板平滑收敛为历史只读态，消除多端或旧会话卡死假死。
6. **403 权限拒绝**：按现有身份治理隔离，停止当前审批动作并给出明确权限说明，普通网络故障不误踢登录。
7. **切会话/多会话隔离**：组件、请求、反馈草稿、resolved IDs 按固定 session key（`projectId:threadId`）隔离，迟到响应绝不串染新会话。
8. **历史 checkpoint 与 fork**：历史只读展示，不加入当前可审批列表；分叉重新规划强制重新走计划生命周期，不继承旧批准。


安全错误码已冻结；复用 `utils/http-error.ts`，不从任意 exception 文本猜计划已批准或复原原始敏感消息。

### HTTP 错误处理

| HTTP | code | 前端处理 |
| --- | --- | --- |
| 400 | `invalid_runtime_options` / `runtime_context_conflict` | 校验 bool 与单一载体，不转普通执行重发 |
| 400 | `runtime_private_state` | 请求包含私有字段，修正客户端构造 |
| 400 | `plan_mode_unsupported` | 禁用入口、刷新 capability；不能自动去掉规划选项重发 |
| 400 | `plan_mode_scheduled_forbidden` | 无人值守任务不支持规划 |
| 400 | `plan_response_invalid` | 回复字段/反馈/schema 不合法，保留反馈并刷新当前中断 |
| 403 | `plan_actor_denied` / `thread_action_denied` / `runtime_target_denied` | 按现有权限处理，禁止继续批准 |
| 409 | `plan_revision_conflict` / `interrupt_not_active` | 旧版本或中断已处理，刷新后转只读 |
| 409 | `plan_review_pending` | 新 Run/state 更新不能替代当前审阅，显示当前计划 |
| 409 | `plan_state_update_denied` | 规划或 bootstrap 中 state 不可编辑 |
| 409 | `plan_execution_conflict` | 旧 unknown 请求与当前规划冲突，按原请求对账 |
| 409 | `idempotency_key_conflict` | 原动作 key/body/actor 不一致，不用新 key 重试批准 |

以上为平台本地校验的 Envelope；上游鉴权、网络和安全泛化继续遵循现有错误规范。异常字符串包含额外正文时不保证精确计划 code。

### Runtime 执行错误

可信异常的精确码为 `runtime.plan.tool_denied`、`batch_invalid`、`tool_invalid`、`tools_unavailable`、`state_invalid`、`execution_missing`、`content_invalid`、`response_invalid`、`unsupported`（后八项均带 `runtime.plan.` 前缀）。通过现有 error/task/lifecycle/state 错误槽位显示服务端安全消息；不新增独立终态，也不自动 resume。`Run GET` 无 error 字段时不拿最新 Thread.error 推断旧 Run 失败原因。

## 联调环境与复跑

后端未部署现役；同事使用本 worktree 的 Runtime/API 成对版本和锁文件。Runtime 锁定 GraphHarbor/GraphHarbor Runtime `0.13.0.post43`、LangChain `1.3.17`、DeepAgents `0.7.8`、LangGraph `1.2.11`、LangGraph SDK `0.4.3`，API 锁定 SDK `0.4.2` 并使用自己的 Python 3.14 环境，Runtime 使用 Python 3.13。共享密钥和模型连接走现有受管配置；样例中的模型 UUID 是已退出临时环境的随机 ID，不能当作联调目录的模型。

普通前端开发沿仓库 `scripts/local-stack.sh` 和服务 README 启动，在启动完成后读取实际 API/Web URL；隔离 E2E 自动选择端口，不提供持久联调 URL。前端审批需人类 owner/manager 与当前项目权限；shared read/comment/edit 不可批准，服务账号不能批准计划。

```bash
# 从仓库根运行受控四图 HTTP/Worker 验证（使用本 worktree API Python）
cd apps/runtime-service
TOOL_ERROR_PLATFORM_TEST=1 PLATFORM_API_TEST_PYTHON="$(pwd)/../platform-api/.venv/bin/python" uv run --frozen --no-sync pytest -q -s tests/e2e/test_plan_mode_platform.py::test_plan_http_worker_restarts_and_original_approval

# 修改/再审/批准/放弃，采集同一计划的公开 state/history/SSE/命令响应
TOOL_ERROR_PLATFORM_TEST=1 PLATFORM_API_TEST_PYTHON="$(pwd)/../platform-api/.venv/bin/python" uv run --frozen --no-sync pytest -q -s tests/e2e/test_plan_mode_platform.py::test_plan_http_review_decisions_and_public_handoff

# 真实模型分支，仅从指定本机 .env 读取三个 DeepSeek 连接配置
TOOL_ERROR_PLATFORM_TEST=1 PLAN_MODE_LIVE_TEST=1 PLAN_MODE_MODEL_ENV_FILE="<受管测试配置路径>" PLATFORM_API_TEST_PYTHON="$(pwd)/../platform-api/.venv/bin/python" uv run --frozen --no-sync pytest -q -s tests/e2e/test_plan_mode_platform.py::test_plan_real_model_http_approval_and_revision
```

隔离脚本只使用合成任务和临时 DB/Redis/工作区并在结束时回收。它证明 API/Worker，不能代替同事的 Web/SDK/浏览器链路。请按 F01-F14 回写真实 thread/run/interrupt、截图、命令和结果。

## 已交付的真实公开样例

两份 JSON 都来自实际 HTTP/持久 Worker。它们只保留公开计划相关字段，省略无关消息/metadata/任务结果；SSE 选取原始事件片段，seq 不连续。样例为历史记录，环境已停止，不能拿其中 ID 直接发起审批。

| 文件 | 来源与可验证内容 |
| --- | --- |
| [samples/dearflow-real-model.json](samples/dearflow-real-model.json) | 真实外部模型、合成任务；调研 → 保存/提交 → 计划批准 → 原 write_file HITL → 文件落盘，公开 awaiting_review/approved，最终 Run success |
| [samples/reference-http-contract.json](samples/reference-http-contract.json) | 受控模型 + 真实 HTTP/Worker；5 次命令/5 个快照/2 个 Thread 的 history 与原生 SSE。request_changes 产生 revision 1→2/新 hash/新 interrupt，approve 与 abandon 的完整回复/响应及公开终态 |

DearFlow thread `3568a7d1-fdc2-4bde-bdc2-4b5d462984a6`，最终 Run `08b8bd8e-013f-4571-80bb-1a1250e4e0de`；Reference 修改/批准 thread `52d3e455-0349-458d-a722-808aa60879af`，最终 Run `d9465663-908a-4e62-9a30-5df9704f183c`，放弃 thread `2aca44cf-9c5a-4f36-9b02-03801b549571`。interrupt/plan/hash/批准人/时间见 JSON，不复制内部执行绑定或凭据。

`history[].values.agent_plan.status=awaiting_review` 是当时快照，不代表当前待审批；当前操作必须从最新 SDK interrupt 获取 ID，且批准后可能仍有普通工具 HITL。样例可作为 DTO/纯函数测试 fixture，不能据它标记 Web 联调完成。

## 前端验收清单

| ID | 场景 | 通过标准 |
| --- | --- | --- |
| F01 | supported/unsupported/两级 capability | 两级判定覆盖新会话（按 graphId 白名单判定）与已有会话（按 thread capabilities 判定）；不支持图不显示开关，后端拒绝不转普通运行 |
| F02 | 选项与 session 隔离 | 左下角“+”菜单选择“先规划”后输入框上方出现“📋 规划模式已启用”胶囊；提交后草稿自动复位为 false；不污染全局 AgentContext；与 access_policy / execution_mode 正交 |
| F03 | 当前计划 interrupt 与输入锁定 | 从普通 approvals 排除并独立解析；集中纳入 `useSessionInterrupts` 驱动 `hasPendingInterrupts`；输入框正确锁定与焦点保护；与 clarification / 工具审批并存时分类正确 |
| F04 | Markdown 安全与双重视图 | 长行/代码/表格/中文、严格过滤 `javascript:`/`data:` 伪协议防御 XSS Canary；待审态底部大卡片局部滚动，历史态紧凑卡片可呼出 Inspector 抽屉查看 64 KiB 完整正文与复制 Markdown |
| F05 | 人类批准 | 发送精确 ID/revision/hash；不发送配置；成功后真实新 Run 恢复，原工具 HITL 可再次出现 |
| F06 | 请求修改 | 反馈 1-2000 字符、缺失/超长阻止；新 revision/hash 必须重新审阅 |
| F07 | 放弃/Stop | abandon 请求语义正确；Stop 不批准、不清除限制；Run 终态来自 SDK |
| F08 | 重复点击/多端 | 本地单飞；另一端批准后当前面板失效；冲突不重发另一批准 |
| F09 | timeout/unknown | 原 ID/key/body 不变；没有前端伪已批准或双 Run；反馈不丢失 |
| F10 | 刷新/断流/迟到事件 | 权威同步核对当前 state；409 自动拉取 state 自愈；旧 SSE/历史不复活审批 |
| F11 | owner/manager/shared/撤权 | 读取与批准权限区别；403/撤权不能再操作，不串项目 |
| F12 | 切会话/fork/时间旅行 | 当前与历史隔离，新 Thread 不继承可执行批准，迟到响应不串 |
| F13 | 390/1024/1440，浅/深主题 | 无文本/工具条重叠，正文局部滚动，按钮可触达，键盘与读屏可用 |
| F14 | 回归/旧字段 | 普通 Chat、工具 approval、clarification、预算/停止/用量、history、capability 缺失保持正常 |


单测覆盖纯 DTO/指纹/response 构造、useSessionInterrupts/run-actions 竞态、组件错误与权限态；补对应 `.spec.ts`。必跑 Vitest、vue-tsc、ESLint、Vite build；Playwright 需真实三服务且至少一条真实模型完整审批后执行链路。合成 fixture 的截图只能证明布局，不能标记联调完成。

## 后端交付给同事的条件

- [x] T22/T23 完成：上述 DTO、Context/capability 与安全错误码已冻结；后端仅接受服务端生成的执行链和当前快照。
- [x] 同一计划的真实 plan interrupt、state/history/SSE、approve/修改/放弃响应及 thread/run/interrupt ID，见上方两份 JSON；模型来源明确区分。
- [x] 审批身份 owner/manager、双端与 SDK 版本、成对启动/复跑入口和受管模型渠道已明确。隔离端口随机且环境已退出；持久 URL 由前端联调栈启动后读取，不提供已失效地址。
- [x] Runtime/API 副作用、并发、重启、fork/旧批准、缓存符号链接、性能与禁用封锁恢复已验；Reference/DearFlow 真实模型后端证据见 `verification.md`，浏览器证据仍待同事完成。
- [ ] 同事完成 T30-T33/T41-F/T42-F/T43-F，回写三尺寸/主题截图、测试命令和真实三服务结果。

后端交付条件已满足。前端启动本地联调栈、选择当前项目的受管测试模型并按 F01-F14 执行；隔离样例不包含模型密钥，也不能替代前端真实 SDK/浏览器验收。
