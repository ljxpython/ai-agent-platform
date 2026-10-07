# Agent 模型调用稳定性 - 前端交接

> 交接对象：Platform Web 开发同事。2026-10-06 实现版：用户已批准完整方案，Platform API/Runtime 代码和隔离 Worker 链路已实现并验证。以下字段来自当前代码，事件来自真实 v3 Worker。未部署现役环境；前端 F01/F02 和浏览器 V02 由同事完成，不能把本文交付记为前端完成。

> 2026-10-07 补充：GraphHarbor post42已发布PyPI并独立取消复验，V01-C默认配置/9项实际子图通过。现役仍post41，未升级；同事联调须使用同版本post42 API/Worker，不能把包发布当作现役上线。

> 交接版本：2026-10-07。本轮追加源码差距、实际平台取消响应、逐步开发任务和停止验收矩阵；本文件是前端开发任务书，进度统一更新 [tasks.md](tasks.md) 的 F01/F02/V02。

## 0. 先理解用户最终会看到什么

本期前端交付三个体验：管理员在 Agent 编辑页设置恢复策略；聊天失败时保留已有内容并说明未完成；用户点击停止后能区分“正在停止”“已停止”“停止尚未确认”。普通聊天用户仍使用现有模型选择和停止入口。

例如主模型 A 暂时不可用，服务端可以在同一个 Run 内改用 B。用户不需要重新发送问题；成功后看到一份答案和实际模型摘要。如果 A 已经输出一半再断开，保留半份答案并提示中断，不拼接 B 的回答。点击停止后也不能只关闭浏览器连接就宣称任务停止。

### 为什么保留前端配置

open-swe 把主备和退避参数放在服务端固定配置中；这足以满足它的部署方式。我们的模型来自项目 Catalog，存在公共模型、本项目 BYOK、权限和不同 Agent 的预算，已经批准由管理 API 保存每个 Agent 的策略。编辑页让有权限的管理员选择这些已治理模型并回读结果，避免每次调整都改部署环境变量。

自动恢复本身可以完全在后端运行；前端配置是本项目已批准的管理入口。按原方案完整实施五个字段，默认关闭。错误和停止确认展示也需要接入；退避抖动、供应商错误分类、Worker heartbeat、Redis、lease 和取消传播不增加前端配置。

| 层级 | 已有/本期责任 | 前端同事需要做什么 |
|---|---|---|
| Platform Web | 编辑配置、消费 SDK 投影、呈现动作结果 | 实施本文 F01/F02 和浏览器 V02 |
| Platform API | 保存策略、检查项目权限、生成受管连接与执行快照、适配网关响应 | 使用现有接口；联调发现契约问题交给后端核实 |
| Runtime Service | 分类错误、重试/主备切换、次数和时间预算、流式保护、成功摘要 | 消费白名单错误与最终消息元数据 |
| GraphHarbor API/Worker | 即时取消、资源清理、持久停止确认；post42 双包已发布 | 在同版本 post42 联调栈验停止体验；不能把包发布当现役升级 |

## 1. 工作范围

只在现有 Agent 编辑页增加受管模型策略，并适配现有 Chat 的模型失败态/实际模型展示。前端不做 provider 调用、重试、切换模型、整 Run 重放，也不新增可靠性页面或第二套 Run 状态机。

必读现有规范：

- `apps/platform-web/docs/frontend-development-playbook.md`
- `apps/platform-web/docs/control-plane-page-standard.md`
- `apps/platform-web/docs/frontend-visual-baseline-standard.md`
- `docs/standards/error-envelope.md` 与 `docs/standards/sse-event.md`

## 2. 现有页面和代码入口

| 路径（相对仓库根） | 同事要做的事 |
|---|---|
| `apps/platform-web/src/services/agents/types.ts` | Agent 新增顶层 `model_resilience` 管理类型；UpdateAgentInput 包含字段 |
| `apps/platform-web/src/services/agents/agents.service.ts` | updateAgent 当前只解构 name/description/status/context，会丢新增字段；同步结构化传递策略，保持 x-project-id |
| `apps/platform-web/src/services/agents/context.ts` | 公开推理字段保持现有五项；不要把策略加入 parseAgentContext 或运行请求 |
| `apps/platform-web/src/modules/agents/pages/AgentEditorPage.vue` | 双栏编辑页追加紧凑策略区，维护独立管理 draft/dirty 状态、保存与回读 |
| `apps/platform-web/src/services/runtime/runtime.service.ts` | 复用 listRuntimeModels(projectId) 获取当前项目 Catalog，不新建请求客户端 |
| `apps/platform-web/src/services/runtime-policies/runtime-policies.service.ts` | 复用 listRuntimeModelPolicies(projectId)，过滤项目禁用公共候选 |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | 按已存在 SDK error/lifecycle 保持 failure 语义，不重新 submit；不把 provider outage 当连接恢复就隐藏 |
| `apps/platform-web/src/services/threads/session.service.ts` | `createSessionService().cancel()` 从默认受理改为等待确认的停止调用，保持 SDK、身份和项目作用域 |
| `apps/platform-web/src/services/runtime-gateway/workspace.service.ts` | 同步既有 `cancelRuntimeRun()` 的等待语义；目前无直接页面调用，不新增入口 |
| `apps/platform-web/src/modules/chat/composables/useSessionConnection.ts` | 核对现有 `useStream()` 的错误/完成回调与恢复路径，保留官方 controller 的结构化投影 |
| `apps/platform-web/src/modules/chat/components/ChatSession.vue` | 复用既有 StateBanner/错误区保留可读失败和 partial 内容；无需新增整页壳 |
| `apps/platform-web/src/modules/chat/composables/useFollowUpSuggestions.ts` | 成功门禁接入真实终态，不能仅因 running 变 false 且末尾存在 AI 文本就触发推荐问题 |
| `apps/platform-web/src/modules/chat/trajectory/trajectory-adapter.ts` | 读取安全 effective-model/attempt 摘要，失败 partial 不误标 completed；对话不增加排障详情墙 |
| `apps/platform-web/src/utils/http-error.ts` | 复用 HTTP 嵌套错误解析；不要覆盖 SDK error 对象或原生 extra |

正式 Agents 由已授权 Graph 自动对齐，页面不增加手工创建/删除入口。Agent 管理 UUID 和运行 graph_id 继续分离。

### 当前代码的具体差距

| Task | 已核对的当前行为 | 要补齐的行为 |
|---|---|---|
| F01 | `types.ts` 没有管理策略，`UpdateAgentInput` 仅 Pick 四项；`updateAgent()` 解构时丢弃新字段 | 增加独立完整管理类型和可空 PATCH 字段，保留原有字段白名单；不要改为整对象透传 |
| F01 | `AgentEditorPage.vue` 的 `fill/load/save` 只维护 Context；schema watcher 只调用 `contextFields(schema)` | 单独消费管理 section，维护策略草稿/基线，dirty 时发送完整对象或 null，成功 `fill(updated)` 回读；以 `schemaEpoch` 严格防冲，禁止迟到的 schema 覆盖用户正在编辑的草稿 |
| F01 | 编辑页备用模型下拉未排除当前主模型，单次与总等待无联动 | 备用模型下拉自动排除/禁用当前选中的主模型，避免提交吃 400；单次等待递增超过总等待时自动联动推高总等待；开启恢复但 N=1 且无备用时轻量提示 |
| F01 | 编辑页当前只按 `model.enabled` 过滤，并未调用模型 policy service | 备用候选增加凭据和项目策略过滤；沿用现有 epoch，策略请求失败时不得当作“全部允许” |
| F02 | 两个 cancel service 均传 `false, "interrupt"`；`stop()` 成功后 verify，finally 清掉 cancelling | 前端采用带 4000ms 超时保护的 `wait=true` 调用；未确认时保留该 Run 的动作结果；修复 `stop()` 逻辑：未确认 Run 即使已公开为 interrupted，依然允许再次点击触发重试确认，不被 `!active` 拦截 |
| F02 | `ChatSession.vue:streamError` 会将部分 upstream 错误归为“恢复连接重试” | 将运行内容失败与网络订阅恢复分开呈现；稳定模型错误保留短文案和 partial |
| F02 | `useFollowUpSuggestions()` 用 running→false 和末尾 AI 文本触发，未接入 Run 终态 | `UseFollowUpSuggestionsOptions` 显式扩展 `runStatus` 与 `hasError`；只有真实成功（`status === 'success'` 且无 error）才允许触发；失败、停止中、未确认和已停止一律静默封杀 |
| F02 | 轨迹 adapter 按 `isRunning=false` 把末尾 AI 正文和 reasoning 统统标 completed | 适配器接收 Run 真实终态与错误标记；未完成内容按 `failed` 或 `interrupted` 呈现；保留已完成工具步骤，不将全段历史标失败，彻底解决精神分裂 |

Chat、Dear Agent 和 Showcase 的共用逻辑在 Chat 模块处理；Dear Agent 的 trajectory adapter 是 re-export，不复制一套实现。新增逻辑只落在实际消费处，不另建通用表单引擎、provider 客户端或全局恢复 store。

## 3. 公开接口

全部走 Platform API，请求带 `x-project-id`；使用现有 Agent service：

| 接口 | 行为 |
|---|---|
| `GET /api/projects/{project_id}/agents` | 每项附顶层 model_resilience 默认/有效值 |
| `GET /api/agents/{agent_id}` | 编辑详情回读，与列表字段一致 |
| `PATCH /api/agents/{agent_id}` | 缺省策略保持；null 重置关闭；完整对象替换 |
| `GET /api/graphs/{graph_id}/assistant-parameter-schema` | 附独立 model_resilience 管理 section、supported/default/ranges；不是 Runtime Context |
| `GET /api/runtime/models` | 复用当前项目 Catalog 数据 |
| `GET /api/projects/{project_id}/runtime-policies/models` | `items[].catalog_id` 对应 Catalog ID，`items[].policy.is_enabled` 为项目开关 |

管理类型：

```ts
type ModelResilienceSettings = {
  enabled: boolean
  fallback_model_id: string | null
  max_attempts: number
  attempt_timeout_seconds: number
  total_timeout_seconds: number
}
```

`Agent.model_resilience` 为完整只读返回值；`UpdateAgentInput` 单独增加 `model_resilience?: ModelResilienceSettings | null`，不能只用 Agent 类型的 Partial/Pick，否则无法正确表达清空。管理 DTO 支持创建字段，但本期仍用既有编辑入口，不额外建设创建页面。

PATCH 示例，主模型推理配置与可靠性设置分开：

```json
{
  "context": {
    "model_id": "<primary-catalog-uuid>",
    "execution_mode": "standard"
  },
  "model_resilience": {
    "enabled": true,
    "fallback_model_id": "<fallback-catalog-uuid>",
    "max_attempts": 3,
    "attempt_timeout_seconds": 600,
    "total_timeout_seconds": 900
  }
}
```

关闭配置提交 `{"model_resilience": null}`。对象完整替换，不发半个对象；无 dirty 改动不发策略字段。旧响应没有字段时 draft 采用关闭默认，但 schema 未说明支持时不开放启用，避免前端默认为已上线。

**严禁**将该对象加入 `context`、`config.configurable.platform_runtime`、`run.start` 请求、排队消息或审批 resume；严禁在浏览器存储 opaque ref、connection、key、provider URL 或内部 `_platform_model_resilience`。

### 字段默认与限制

| 控件/字段 | 默认建议 | 限制与行为 |
|---|---|---|
| 自动恢复 / enabled | 关闭 | 严格开关；不因选了 B 就自动打开 |
| 备用模型 / fallback_model_id | 无 | BaseSelect，空选项为「仅重试当前模型」；Catalog UUID，不接受自由文本 |
| 最大尝试次数 / max_attempts | 3 | 含首次，整数 1~5；数字步进/输入，不写「重试次数」导致误解 |
| 单次等待 / attempt_timeout_seconds | 600 秒 | 有限数值 1~900；数字输入/现有预设，不转字符串上送 |
| 总等待 / total_timeout_seconds | 900 秒 | 有限数值 1~1200，且 >= 单次；以服务返回 schema 为准 |

范围由后端 schema 返回，界面不得硬编码另一组默认值；缺失 schema 时只读/关闭并使用既有加载失败态。预算字段是管理员配置，Chat 输入条不暴露这些控制。

### 管理 section 实际返回

现有参数接口保持 `schema_version="remote-v1"`、`sections` 中的 config/context；API 额外追加以下管理 section。前端按 `key` 读取，只有 `supported=true` 时可启用，不能把新 section 的字段泛化为 Runtime Context。

```json
{
  "key": "model_resilience",
  "type": "object",
  "required": false,
  "supported": true,
  "default": {
    "enabled": false,
    "fallback_model_id": null,
    "max_attempts": 3,
    "attempt_timeout_seconds": 600,
    "total_timeout_seconds": 900
  },
  "properties": {
    "enabled": {"title": "Enabled", "type": "boolean"},
    "fallback_model_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Fallback Model Id"},
    "max_attempts": {"title": "Max Attempts", "type": "integer", "minimum": 1, "maximum": 5},
    "attempt_timeout_seconds": {"title": "Attempt Timeout Seconds", "type": "number", "minimum": 1, "maximum": 900},
    "total_timeout_seconds": {"title": "Total Timeout Seconds", "type": "number", "minimum": 1, "maximum": 1200}
  }
}
```

返回不含 section 的 title，也没有 `fallback_model_id.format=uuid`；UUID 由 DTO validator 校验，前端使用 Catalog 的 ID。原样支持 Pydantic `anyOf`，不要只识别 `type=[string,null]`。首期支持图为 `reference_agent`、`showcase_demo`、`dearflow_agent`、`workflow_demo`，仍以后端 section.supported 为界。

总预算不小于单次预算、完整对象替换与严格数值校验由 DTO/前后端保证；不要从这个 properties 摘要推断允许部分 PATCH。`required=false` 表示 PATCH 字段可缺省，不表示对象内字段可缺省。N/total 只表示一次受管生成 invocation 的预算，原生摘要及压缩后重新进入策略有单独范围，不在 Chat 声称一个节点或整 Run 只会请求 N 次。

管理错误保持既有 HTTP Envelope：格式/字段校验 `422 validation_failed`；不支持图 `400 model_resilience_not_supported`；重复主备 `400 model_resilience_duplicate_model`；候选不可用 `403 runtime_model_denied`。运行前缺 Catalog 主模型为 `400 model_resilience_primary_required`，未配置签名为 `503 model_resilience_unavailable`。这些都不能当作 SSE 内容失败。

## 4. 编辑页状态与权限

- 读取沿用 `project.assistant.read`，保存沿用 `project.assistant.write`，使用 `useAuthorization()` 和当前 projectId；不要用角色名称手写 gate。
- 复用现有双栏和 BaseSelect；新增区域保持紧凑，不再增加卡片套卡片、独立壳、长篇原理文案。右侧预览仅呈配置结果。
- enabled=false 时策略不生效；控件按现有表单规范禁用/收起，保留草稿便于用户开启前配置，保存关闭使用 null 清空。
- 未支持的图显示关闭/只读；不要让表单保存后让 Runtime 静默忽略。
- 候选应满足 Catalog enabled、credential_configured 和当前项目可用策略；平台公共模型与本项目 BYOK 可区分展示，不能显示其他项目私有模型。
- 用 `catalog_id` 对齐 policy，不按模型名/provider 名匹配；已成功取得的 policy 结果缺省项按后端默认允许处理，但请求失败/403 不能伪装成空列表。只读页面仍可展示 Agent 已保存值，策略未核实前不允许启用或更换候选。
- API 拒绝 disabled/不存在/禁止候选时保留草稿和错误，不能自动选列表第一项；无可用 B 仍可选择仅重试主模型。
- **主备模型联动去重**：备用模型下拉选项（`fallbackModelOptions`）自动过滤或禁用当前选中的主模型（`context.model_id`）；若主模型发生变更导致与已选备用模型相同，备用模型自动置空（回退至「仅重试当前模型」），杜绝提交吃后端 `400 model_resilience_duplicate_model`。主模型继承项目默认时以后端最终校验为准。
- **等待时间联动保护**：单次等待（1~900 秒）与总等待（1~1200 秒）在界面做单向推高联动。当用户上调单次等待超过当前总等待时，总等待自动上调对齐；提交前严格检查 `total >= attempt`，不让用户提交死锁数据。
- 配置保存成功后回读服务端规范化值、更新 dirty 基线；修改 Context 不丢 model_resilience，修改策略不丢 Context。
- 项目/身份/Agent 切换使旧请求和 draft 失效；迟到响应按现有 epoch 丢弃。网络失败保留同作用域的已确认信息，不当作撤权。

只读、加载、空候选、schema 不支持、模型已失效、校验错误、保存失败/重试、权限拒绝均应可验收。键盘可操作、数字标签关联、焦点/弹层与 390x844 布局遵循既有组件。

### F01 开发顺序与界面交付

1. 在管理 types/service 接通字段，并先验证 PATCH 的缺省、完整对象、null 三种行为。运行请求的 Context 白名单保持原有五项。
2. 沿现有 load/schema watcher 读取 Agent、管理 section、Catalog 与模型 policy；schema 就绪后取服务端 default/range。独立初始化策略草稿，严格维护 `schemaEpoch`，仅在表单未 dirty 或初次加载时水合默认值，禁止迟到响应覆盖用户输入。
3. 在现有模型参数区域增加紧凑“模型恢复”分组：
   - 自动恢复开关（严格布尔值）；
   - 备用模型 BaseSelect（排除当前主模型，默认「仅重试当前模型」）；
   - 最大尝试次数数字步进（1~5）；若开启且 N=1 且无备用模型，展示轻量辅助文案：“当前配置仅执行 1 次调用，不会触发额外重试”；
   - 单次等待与总等待数字输入（联动校验 `total >= attempt`）。
   - 沿现有双栏布局，右侧 Inspector 显示开关、主备和预算摘要；390px 下使用现有布局的单列折叠。
4. 保存时只补策略 dirty 差异；关闭发送 null，未改动不发送。保存失败保留同作用域草稿，成功以返回 Agent 刷新基线。原有名称、描述、状态和 Context 的差异保存继续有效。
5. 完成只读、加载、schema 不支持、仅重试当前模型、失效候选、主备互斥、校验/网络错误与项目切换测试，再接入 Chat 联调。

界面字段用第 3 节的中文标签，不把 schema 的英文 title 直接呈现。预算统一显示“秒”，提交 JSON number；最大尝试次数包含第一次。开启且 N=1 时不会有第二次备用请求，仍接受合法配置；不要擅自把 N 强制改成 2。图不支持/能力未确认时保持只读，不能自行判断部署已具备能力。

## 5. Chat 错误与结果

### 状态约定

| 场景 | 前端责任 |
|---|---|
| A 在首块前 transient，B 成功 | 继续同一 Run，不新建消息/Run；用户主模型选择不变，轨迹可显示实际成功模型 |
| A/B 用尽次数或预算 | 按原生 error 展示失败；不能标 completed/success，不触发只属于成功的推荐问题 |
| A 已发正文、reasoning 或 tool args 后失败 | 原消息 partial 可读，显示未完成；本期 Runtime 不自动混入 B 输出 |
| 重试等待/推理期间停止 | 复用既有 cancel，先显示停止中；新版 `wait=true`/已验停止投影确认后显示已停止；默认 ACK、提前 Run interrupted 和本地 abort 不算停止确认 |
| 浏览器断 SSE/网络失败 | 只恢复订阅和核实原 Run；不通过 submit 重跑推理 |
| 502/503/504/provider outage | 不撤销登录或项目权限，不清聊天历史 |
| 配置/模型被拒绝 | 显示作用域内可读失败；确有权限拒绝时仍按现有 authoritative check 处理 |

原生 lifecycle 为权威，新增安全 summary/机器码只用于展示。运行失败不能通过扫描故障 AIMessage 文案推断；本次已确认 Runtime 机器码在原生 error.message，使用下述精确白名单适配，不读取不存在的 error.code。

### 实际 v3 失败样例

标准 Run SSE 的 `data` JSON 是下面的原生投影。原生 `error` 位于 `params.data.error`，机器码在 `message`，没有 `error.code`。通过现有 SDK lifecycle 消费，不自己解析网络 chunk 或新增事件流：

```json
{
  "method": "lifecycle",
  "params": {
    "namespace": [],
    "data": {
      "event": "failed",
      "status": "error",
      "graph_name": "reference_agent",
      "reason": "business_error",
      "error": {"type": "RuntimeResolutionError", "message": "runtime.model.retry_exhausted"}
    }
  },
  "seq": 29
}
```

只在 `type=RuntimeResolutionError` 且 `message` 精确属于下表白名单时用对应短文案；其他错误仍走已有安全失败提示。Protocol 的规范化终态与原生 Run JSON 可能命名不同，按 SDK 当前投影核对 `status=error`，不能一律把 completed 当 success。失败 Run JSON 为 error；HTTP 创建/订阅可先成功，不能期待 provider 失败变成 HTTP 503。

取消 ACK 和 Run 提前置 interrupted 都不能证明 Worker 已退出。历史默认失败 7.925 秒及 1 秒 heartbeat 对照保留为基线；post42 默认配置复验 ACK→lease 释放 0.123 秒，ACK/确认/最终均无备用新增，实际子图 9 项通过。前端复用现有停止入口，不增加心跳/取消策略配置。

### 取消停止确认交接（2026-10-07）

| 触发/结果 | 前端显示与动作 |
|---|---|
| 用户点击停止 | 立即显示“停止中”，合并同一 Run 的重复点击；复用现有取消方法和请求作用域 |
| `wait=false` 返回 ACK（GraphHarbor 202，平台按既有 SDK envelope 归一化） | 仅表示受理，保持停止中；不能推断 provider 请求已经退出 |
| 新版 `wait=true` 成功结束，或已联验的同版停止 terminal 投影到达 | 结合权威 Run/lifecycle 确认，显示“已停止”；保留 partial，不标成功、不触发成功推荐问题；普通 Run GET 的 interrupted 不能替代停止依据 |
| 等待超时/GraphHarbor 503/平台 502 或 504/网络断开 | 显示“停止尚未确认”并复用现有状态核实/取消重试；若服务端已受理，取消意图继续有效；网络丢失时受理结果可能未知，不假报成功、不自动新建 Run |
| cancel 与自然完成竞态 | 以服务端单一终态为准；已经完成时正常显示最终结果，不强行覆盖成取消 |
| 切 Thread、切后台、SSE 断开 | 保留 Run 关联和既有会话状态，恢复订阅/回查；本地 abort 只代表客户端断开，不代表服务器执行停止 |

后端适配器 `wait`/`action` 已联合验证，应采用 `wait=true, action=interrupt` 等停止。post42 confirmed body 是 null（SDK 丢弃），按现有 service/SDK envelope 消费，不能要求 body 带额外 cancelled 字段；200 成功必须来自同版新版栈。现役 post41 的 wait 仍可能提前返回，混合 API/Worker 也不具备新版保证；浏览器验收仍由同事完成。前端不查询 lease、不解析 Redis 控制消息、不增加 Run 公开状态枚举。

### 实际平台请求与响应，不能直接照抄 GraphHarbor HTTP 表面

现有前端 SDK 通过 `/api/langgraph` 的授权网关请求，使用同项目的 `x-project-id` 和既有 token refresh。正式停止复用 SDK 已有参数位置：

```ts
await client.runs.cancel(threadId, runId, true, "interrupt")
```

这是给同事的目标调用，本轮未修改 service。浏览器中对应的请求为：

```http
POST /api/langgraph/threads/<thread-id>/runs/<run-id>/cancel
Content-Type: application/json
x-project-id: <project-id>

{"wait": true, "action": "interrupt"}
```

| 场景 | GraphHarbor 同版 post42 | 当前 Platform API 表面 | 前端判定 |
|---|---|---|---|
| `wait=false` 已受理 | 空 body 202 | Python SDK 丢弃 body，`_normalize_ack()` 返回 HTTP 200 `{"ok":true}` | 仅 ACK；平台 200 或 ok 不等于执行停止 |
| `wait=true` 等停止/清理成功 | HTTP 200，body null | HTTP 200 `{"ok":true}`；JS SDK 返回 void | 确认请求 Promise 成功且同版能力已联验，再核对同一 Run 的终态 |
| 停止依据缺失/等待超时 | HTTP 503 | HTTP 502，`langgraph_upstream_request_failed` | 本次取消未确认；不能清登录/权限或显示已停止 |
| 网关上游 HTTP 超时 | 未取得确认响应 | HTTP 504，`langgraph_upstream_timeout` | 未确认，后续仍核对同一 Run |
| 浏览器断网/连接中断 | 受理与确认结果可能未知 | Promise rejected/无响应 | 未确认，不把客户端 abort 当服务端停止 |
| 403/404 或明确校验拒绝 | 既有拒绝语义 | 既有脱敏错误 Envelope | 用原权限/资源错误流程；404 不证明已停止 |

以上映射来自 `runs_sdk_adapter.py:cancel()`、`sdk_client.py:create_runtime_upstream_error()` 与 `runtime_gateway/presentation/http.py:_normalize_ack()`。平台没有公开 Worker 停止证据查询接口，不能新增前端 lease/receipt 请求来补猜测。不要把模型生成的 SSE 失败与取消 HTTP 错误合并成一个机器码体系；502 的“未确认”文案只用于当前取消动作上下文。

### F02 停止动作的具体处理

1. **绑定上下文与点击防重**：点击停止按钮时绑定身份、项目、Thread、目标 Run；立即进入“停止中”，保留当前正文、reasoning 与 tool 调用。同一 Run 的并发点击合并，沿用 Thread `edit` 动作授权。
2. **带 4000ms 前端超时保护的取消调用**：
   - 调用 `service.cancel(threadId, runId)`（底层传 `wait=true, action="interrupt"`）；
   - **前端必须包装有限等待保护（推荐 4000ms `Promise.race`）**：
     - 若在 4000ms 内收到 HTTP 200（新版栈确认停止）：结合权威 Run 终态，置为“已停止”；
     - 若超过 4000ms 仍未返回、或收到 502/504、或网络连接断开：**判定为“停止尚未确认”**，释放本地发送锁，保留该 Run 的“停止尚未确认”提示横条，切勿让前端无限挂起！
3. **解开状态机重试死锁**：
   - 现有 `useChatSession.ts:stop()` 在 `!active(run.value)` 时直接 return。**必须对此进行解耦改造**：维护当前未确认停止的 `unconfirmedStopRunId`，如果当前 Run 处于“停止尚未确认”（即便查询回查将其置为 `interrupted` 导致 `active()` 判定为 false），**依然允许用户点击“重试停止”再次向同一 Run 发起 wait=true 确认请求**，绝不能被 `!active` 分支吞掉！
4. **结果收敛与竞态**：
   - 取消与自然完成竞态时，以服务端单一终态为准；若服务端先产出 natural success 或 error，正常保留真实结果，不强行覆盖成已停止；
   - 停止中与停止尚未确认期间，保留消息复制、查看和滚动，继续回查原 Run，不自动触发下一轮提问，不解除运行安全门禁。
5. **作用域与切屏隔离**：
   - 切 Thread、切项目或切后台时，旧取消响应不得污染新会话；切回时仅恢复订阅与动作核实，本地 abort 只代表断开连接，不代表服务端停止。

### 成功模型摘要与展示平滑

启用策略且生成成功后，最终 AIMessage 可带下述 `response_metadata` 扩展。此处 `attempts` 是该 invocation 的生成请求数，`fallback_used` 表示最终成功模型与请求主模型不同（例如 A/B/A 成功时 `attempts=3`、`fallback_used=false`）：

```json
{
  "platform_model_resilience": {
    "version": 1,
    "requested_model_id": "<primary-catalog-uuid>",
    "effective_model_id": "<fallback-catalog-uuid>",
    "attempts": 2,
    "fallback_used": true
  }
}
```

- **视觉呈现与平滑过渡**：流式生成期间展示请求的主模型名称；终态生成完毕后，若 `fallback_used === true`，在答案底栏或微胶囊 Tag 中平滑展现，例如：`已自动切换至备用模型: {effective_model_name} · 尝试 2 次`。避免流式与完成态无解释突变让用户困惑。
- **Catalog 名称解析与防崩兜底**：使用项目 Catalog 将 `effective_model_id` 转换为模型显示名称；若找不到对应 Catalog 项，降级显示为“备用模型”，**严禁直接暴露裸露的 Catalog UUID**。
- **历史回水（History Hydration）防御**：history 是相同 messages 的 checkpoint 投影，读取 `response_metadata?.platform_model_resilience` 时必须防御性验证 `version === 1` 和有效数字，缺失或非法时静默忽略扩展，不阻断历史渲染。
- 摘要仅在成功生成后追加，失败时使用原生错误与后台诊断日志，不制造成功摘要。

### 机器码与文案建议

| 已实现稳定代码 | 建议短文案 |
|---|---|
| `runtime.model.retry_exhausted` | 模型服务暂不可用，本次运行未完成。 |
| `runtime.model.retry_budget_exceeded` | 模型调用等待超时，本次运行未完成。 |
| `runtime.model.stream_interrupted` | 本次回答中断，已保留部分内容。 |
| `runtime.model.provider_rejected` | 模型配置或额度不可用，请联系项目管理员。 |
| `runtime.model.fallback_incompatible` | 备用模型不支持当前请求，请调整配置。 |

不能显示 provider 原始 body/message、API key、连接地址、ref 或 raw traceback。HTTP request_id 只按现有合法值规则展示。不能承诺每段 partial 都已 checkpoint；刷新后的真实保留内容以原生 state/history 为准。

### F02 错误与成功门禁的开发顺序

1. **结构化错误解析**：通过当前锁定的 `@langchain/langgraph-sdk=1.10.2`、`@langchain/vue=1.0.35` 提取 `stream.error` 原生对象，精确匹配白名单机器码，提供安全短文案映射；禁止直接 `String(error)` 模糊猜测。
2. **推荐问题成功门禁（useFollowUpSuggestions）**：
   - 为 `UseFollowUpSuggestionsOptions` 显式扩展 `runStatus?: MaybeRefOrGetter<string | undefined>` 与 `hasError?: MaybeRefOrGetter<boolean>`；
   - `triggerForCompletedTurn()` 增加硬性拦截：当 `runStatus !== 'success'` 或 `hasError === true` 时立即中断，禁止仅凭 `isRunning` 变为 false 和末尾存在 AI 文本就触发；
   - 彻底杜绝在失败 partial、停止中、未确认和已停止时误触发推荐问题。
3. **轨迹适配器修复（trajectory-adapter）**：
   - 适配器函数接收当前 Run 权威终态（`runStatus`）与错误标记（`hasError`）；
   - 末尾未完成的 assistant 步骤：若 Run 失败标为 `"failed"`，若 Run 停止标为 `"interrupted"`，仅在 Run 真实成功时标为 `"completed"`；
   - 末尾未完成的 reasoning 步骤同步修正，禁止无脑硬编码 `"completed"`；已完成的历史工具调用步骤保持原投影。
4. **接入停止动作与超时保护**：按上述 4000ms 前端超时与 `!active` 解耦改造修改 `useChatSession.ts` 和 `session.service.ts`，打通未确认横条与重试停止。
5. **模型摘要解析与水合验证**：在最终 AIMessage 上挂载安全模型元数据解析，验证刷新、切 Thread 与历史水合下的鲁棒性。

## 6. 最小测试与联调

### 同事自动化测试

- Agent service 实际发送顶层策略，null 清空、缺省保持；既有 updateAgent 解构不漏字段。
- 编辑页严格数字/UUID/预算校验、关闭/支持图/无候选/失效候选、双向保留 Context 与策略。
- 只读 permission、写 permission、项目/Agent 切换、网络失败/迟到响应。
- SDK error 机器码映射、partial 文本/reasoning/tool-call、空 message-start 收敛；没有重复消息/步骤/工具。
- 全失败不触发完成/推荐问题；fallback success 不改变 selector；背景切回/取消/重连不重新 submit。
- 取消默认 ACK 保持停止中；wait 超时不误标已停止；旧版本提前 interrupted、重复点击和自然完成竞态均按上述交接测试。

### 测试落点

| 现有位置 | 本次要补的断言 |
|---|---|
| `src/services/agents/agents.service.spec.ts` | 顶层策略传输、null/缺省、白名单不放行内部或 graph 字段 |
| `src/modules/agents/pages/AgentEditorPage.spec.ts` | schema/default/数字边界、dirty/回读、仅重试 A、备用模型自动排除主模型、单次与总等待联动推高、N=1 辅助提示、候选 policy/权限/epoch 防迟到冲草稿 |
| `src/services/threads/session.service.spec.ts` | SDK cancel 参数为 true/interrupt，4000ms 前端超时保护，项目 header/授权仍生效；SDK void 成功、502/504/拒绝不被吞掉 |
| `src/modules/chat/composables/useChatSession.spec.ts` | 4000ms 超时判定未确认、提前 interrupted 后仍可重试确认（解开 `!active` 死锁）、自然完成竞态、重复点击合并与迟到响应隔离 |
| `src/modules/chat/composables/useSessionConnection.spec.ts`、`src/modules/chat/sdk-chain.test.ts` | 使用现有 SDK controller 的失败/完成/恢复，不因恢复再 submit |
| `src/modules/chat/composables/useFollowUpSuggestions.spec.ts` | `runStatus !== 'success'` 或 `hasError` 时强行阻断；失败 partial、停止中/未确认/已停止及后台切回不请求 suggestions，只有真实成功可触发 |
| `src/modules/chat/trajectory/trajectory-adapter.spec.ts` | 注入 Run 终态：失败 partial 标 failed，停止标 interrupted，不误标 completed；保留工具 ID 和已完成工具；摘要缺失/非法/未知 version 降级展示（不裸露 UUID） |
| `e2e/` + `playwright.config.ts` | 在既有 Playwright 目录补本专项用例，保留三尺寸/深浅模式、身份/项目与 Thread 隔离证据 |

路径均相对 `apps/platform-web`。新增测试不借机改造全仓测试；导出的 `cancelRuntimeRun()` 与 session cancel 一并核对参数，若增加专属 service 测试，放同目录。

### 停止验收矩阵

| 编号 | 场景 | 必须观察到的结果 |
|---|---|---|
| C01 | 同版 post42，provider 长等待中停止 | 立即停止中；true 完成前不显示已停止；之后 partial 可读、实际候选计数不再增加 |
| C02 | backoff/cooldown/真实子图慢清理 | 清理 barrier 未释放前等待，不自动再 submit；确认后子图退出 |
| C03 | 受控 false ACK | 即使平台返回 200/ok，仍只显示受理/停止中，不宣称停止 |
| C04 | 提前 Run interrupted，清理仍未完成 | 不按 GET status 提前确认，不触发 suggestions/完成徽章 |
| C05 | GraphHarbor 503 经网关变 502 | “停止尚未确认”；可核实/重试原 Run，登录、权限和 partial 保留 |
| C06 | 网关 504/前端 4000ms 等待超时/浏览器断线 | 判定为“停止尚未确认”；释放按钮锁，保留未确认横条，恢复订阅只核对原 Run，provider/submission 计数不增加 |
| C07 | 未确认后 interrupted，再点重试停止 | 仍向同一 Run 发 true 请求，不能被 !active 分支吞掉 |
| C08 | 连续点击停止 | 在途确认只有一次；确认重试只能由明确动作或原有核实路径发起 |
| C09 | 取消与自然 success/error/timeout 竞态 | 显示真实结果，不覆盖自然终态；失败/取消不触发成功推荐 |
| C10 | 切 Thread/后台/项目/账号，旧请求迟到 | 原 Run 的结果不污染新作用域；切回不建新 Run、不重复消息/工具 |
| C11 | 只读权限、作用域 403、单 Run 404 | 按原有权限/资源机制处理，拒绝不假报停止；不因局部错误全局退出登录 |
| C12 | post41 或混合 API/Worker | 标记环境不满足新版确认门禁，不能用提前 200/interrupted 判验收通过 |

记录 ACK/确认/退出/释放时间及请求计数的工作由后端受控 provider 和 Worker 证据完成，浏览器不查询数据库或 lease。0.123 秒是既有健康样本，不是 UI 倒计时或生产 SLO；等待超过该样本不能自行判失败或补造停止成功。

### 联调验收用例

1. 配置 A/B，A 首块前 503，B 完整回答：只出现一个有效答案，实际 provider 2 次，工具最多按计划执行一次。
2. A/B 均失败：最多 N 次，Run error，提示可读且无敏感内容，输入和主动继续动作可达。
3. A 已输出 reasoning/正文后断开：partial 保留、明确未完成，无 B 请求、无错误完成徽章。
4. 默认 heartbeat 的新版 GraphHarbor 栈中，backoff/长推理期间调用 `wait=true` 停止，再切 Thread/切回：停止中到已停止确认一致，不新建 Run；核对实际子图退出和后续候选为零。再覆盖默认 ACK、确认超时/断流和自然完成竞态，记录受理/收到/退出/释放时间点。
5. P1/P2 切换、只读访问和后台网络失败：无候选/状态泄漏，不误清权限/登录。
6. tool 审批恢复后故障切换：批准动作、tool ID 和历史一致，不重放副作用。
7. 390x844、1024x768、1440x900 和深浅模式：控件/错误/partial 内容无重叠或溢出，键盘可操作。

```bash
# 在 apps/platform-web 执行
pnpm test:run
pnpm lint
pnpm typecheck
pnpm build
```

浏览器验收保留 screenshot、Run/Thread ID、匿名配置、故障方式和后端请求/工具计数。不能仅凭页面出现一句成功文案判定恢复成功。

## 7. 交接与完成度

### 同事接手清单与责任划分

| 负责人 | 开始/结束条件 |
|---|---|
| 前端同事：F01 | 先交管理 type/service 和编辑页五字段；提交实际 PATCH/回读、权限/候选/项目切换的测试证据 |
| 前端同事：F02 | 再交模型失败/partial、摘要、推荐问题成功门禁、等待停止确认和未确认恢复；同目录测试及静态/构建通过 |
| 后端/Runtime 联调支持 | 提供已更新 Platform API/Runtime 与同版 post42 API/Worker 的隔离环境、当前项目/Agent/Catalog ID、schema supported、受控故障和请求/工具计数；前端无需持有 provider 凭据 |
| 前端同事 + 后端：V02 | 按配置→提交→恢复/失败→停止走真实三服务，完成 E01~E07、C01~C12 和三尺寸/深浅模式浏览器记录 |
| 全栈责任人：V03 | 前端交付与完整平台发布/回退门禁齐全后执行 Final；不能用底座 post42 发布或本文件交付代替 |

前端可先用与本文一致的 fixture 实现/自动化测试；正式取消联调必须等待隔离同版栈可用。环境身份与运行版本由后端提供、记录到证据，不增加页面版本配置或凭浏览器 User-Agent 推断。现役 post41 不满足停止确认门禁；本轮未授权升级/重启。

正式交接已包含批准字段、实际 schema、四个支持图、v3 lifecycle 样例与 [后端 Phase 证据](verification.md)。故障注入脚本为 `apps/runtime-service/tests/integration/test_model_resilience_worker.py`：自动建立临时 PG/Redis/Platform/Runtime API/Worker/provider，结束清理独占进程和临时配置；不提供固定共享账号/密钥，不改现役库。后端可按相同 scenarios 为联合浏览器环境配置受控 provider。

已验收官方 DeepSeek `deepseek-flash` 与 miaomiaoai `deepseek-v4.1-flash` 的文本、工具历史及图片配对；Qwen 文本/工具/图片及 Minimax 文本/工具 smoke 通过。早先 Qwen/Minimax 连接失败来自测试跨事件循环复用缓存 HTTP pool，已修复测试后复验通过；不作为模型不兼容证据。旧代理 `DeepSeek-V4-Flash` 明确只支持文本并对 image_url 返回 400。用户已明确本期不验收 Anthropic 真实 API，前端联调无需等待该配置；Minimax 视觉也不在本次已验范围。项目私有或公共候选都必须先有对应实际模态证据，不能凭 provider 名称自动当视觉模型；不修改现役模型设置。

定时历史耗尽时为 `status=error`、`error_code=scheduled_task_execution_failed`；执行前 B 禁用为 `runtime_model_denied`，provider 计数为零。历史与 Run 失败都不得标成功，手动/once/cron 和服务账号真实链路见 evidence/scheduled.json。

同事接手后在 `tasks.md` 更新 F01/F02/V02，并提供测试、构建和三尺寸/深浅模式浏览器证据。当前前端未实施，整体不能标 done；后端/Runtime 隔离阶段通过不替代浏览器和生产回退门禁。

2026-10-07 用户已同意沉淀取消经验：平台见 [跨服务经验库](../../lessons/cross-service.md)，GraphHarbor 见其仓库 `docs/lessons/runtime-persistence.md`。这里的开发文案和验收继续以本交接及当前契约为准，经验库保存可复用原则。
