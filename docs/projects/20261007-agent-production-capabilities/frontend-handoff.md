# 前端交接：运行准备与重试摘要

## 交接状态与职责

**状态：** 2026-10-07 后端契约已冻结，Runtime/Platform API 非前端实现及本机验证完成，T10 待前端同事实施。本次没有修改 `apps/platform-web` 源码，也没有部署现役服务。联调使用本工作树的新后端；现役版本是否返回新字段需以部署版本为准。

前端由用户同事完成 T10。本期只扩展现有 Chat 的 Run Diagnostics 面板，保持普通 Chat/DeerFlow 复用入口。前端不计算 fingerprint、不写 prepare state、不重启 Run、不自动重发消息或审批、不在浏览器决定可重试错误，不新增 retry 配置页。

后端/Runtime 提供模型/task/prepare 的实际执行结果和脱敏 DTO；GraphHarbor/官方 SDK 仍持有运行生命周期。诊断不是实时运行状态源，查询失败/延迟/无记录不等于 Agent 失败。

已接线 DearFlow、Showcase 的 workspace 与模型/只读 task；Reference 复用原有机制，其他 Agent 按组合根显式选择。当前前端 Zod 的 strip 会安全丢弃新字段，旧页面兼容新后端，但需要完成下面的类型与展示工作后才能看见新摘要。

## 接口

保持现有接口：

```http
GET /api/langgraph/threads/{thread_id}/runs/{run_id}/diagnostics
x-project-id: {当前项目 ID}
Authorization: {现有平台认证}
```

沿用 `getRunDiagnostics()`、已有权限语义、`Cache-Control: no-store`，不直连 Runtime/Langfuse。响应 `run_id`/`thread_id` 必须匹配当前目标。`request_id` 是本次查询；`correlation.execution_request_id` 是原执行，不能混为一条调用。

OpenAPI 入口为 Platform API 的 `GET /openapi.json`，响应模型仍是 `components.schemas.RunDiagnostics`，新增子模型为 `PreparationSummary`、`RetrySummary`。事实来源为 [后端 DTO](../../../apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py) 与本机抓取的 `/tmp/agent-reliability-8365-native5/test_http_retry_task_partial_s0/diagnostics-openapi.json`。该抓取确认两数组不在 required 中，各自 `maxItems=20`，`attempts` 为 integer、minimum=1、maximum=2。

不新增 SSE retry/prepare 控制事件。HTTP 查询新增安全摘要，原工具消息和 SDK 的 namespace、tool_call_id、interrupt、lifecycle 继续照常消费。

## v1 冻结增量契约

原 `RunDiagnosticsV1` 字段全部保留，新增可选 `preparations`、`retries`，未返回时规范化为空数组。两组数组均最多 20 项。`version` 仍是 1；不能为了一个兼容字段把当前所有旧响应拒绝为 v2。

### Zod Schema 防御性设计规则（关键对齐）
1. **根数组兼容与安全剥离**：
   - `preparations: z.array(preparationSummarySchema).max(20).optional().default([])`
   - `retries: z.array(retrySummarySchema).max(20).optional().default([])`
   - 两数组允许缺失或 `[]`，不接受显式 `null`；使用 Zod 默认 `.strip()` 剔除未知字段，防止敏感字段（如 canary）穿透至 DOM。
2. **strict 校验与严禁 Coercion**：
   - `attempts` 必须是 strict integer，范围限定在 1-2：`z.number().int().min(1).max(2)`。**严禁使用 `z.coerce.number()`**。
   - 彻底拦截越界 attempts（如 0、3、负数）、`NaN`、`Infinity`，确保非法数据直接走降级处理。
3. **白名单正则与安全防注入**：
   - `observation_id`：必须校验 Identifier 正则 `^[A-Za-z0-9_:.-]+$`，1-128 字符。
   - `role`：必须校验安全正则 `^[A-Za-z0-9_:.-]+$`，1-64 字符，防止 LLM 提示注入或非法长文本直接渲染。
4. **子项 Nullable 字段默认值**：
   - 子项所有 nullable 字段（如 `error_code`、`role`、`duration_ms`）在 Zod 中统一声明为 `.nullable().optional().default(null)`。
   - 杜绝后端在序列化缺省字段时导致前端解析抛出 `invalid_diagnostics_dto`。

### preparations 项

| 字段 | 冻结类型/限制 | 含义 |
| --- | --- | --- |
| `observation_id` | 现有 Identifier，1-128 字符 | 观测 ID，作为稳定列表 key；不按数组索引去重 |
| `scope` | `primary` / `subagent` | 发生于主图或子图 |
| `namespace` | 现有 Identifier 数组，最多 8 项 | 现有图命名空间；允许空数组表示根图 |
| `component` | `workspace` | 首期只公开已接入的 workspace 准备，未来新枚举先变更契约 |
| `outcome` | `prepared` / `reused` / `repaired` / `failed` | 首次准备、复用已完成记录、补缺资源、准备失败 |
| `duration_ms` | 非负有限数或 null | hook 总耗时；0 是有效值，null 是未采集 |
| `error_code` | null / `prepare_failed` / `resource_unavailable` | 公开固定摘要；不暴露内部 path、hash、token 或原异常 |

`reused` 只证明这一步复用了准备记录，不证明整次 Run、模型连接或授权成功。失败是当前步骤失败，最终状态继续看原生 Run。

### retries 项

| 字段 | 冻结类型/限制 | 含义 |
| --- | --- | --- |
| `observation_id` | 同上 | 安全观测 ID |
| `scope` | `primary` / `subagent` | 重试 owner 所在图；父图重试 task 的 scope 是 primary，不是它调用的子图 |
| `namespace` | 同上 | 重试 owner 的现有 namespace |
| `unit` | `model` / `task` | 重试的是模型请求还是整个只读 task |
| `role` | null 或当前 graph 代码声明的角色名，最大 64 字符 | 仅 task 对应；不能展示 LLM 随意传入的任意 role 字符串 |
| `attempts` | strict integer，1-2 | 总调用次数，包含首次；2 表示一次自动重试 |
| `outcome` | `success` / `exhausted` / `failed` / `cancelled` / `interrupted` | 该调用单元结果，不是父 Run 终态 |
| `code` | 既有 ModelErrorCode 或 null | 被安全分类的最后失败原因；成功恢复也可保留前次错误 code |
| `duration_ms` | 非负有限数或 null | 整个重试单元用时，包含退避；不是单次 provider latency |

`exhausted` 表示匹配的瞬时错误达到尝试上限；`failed` 包括不可重试错误、未分类错误和已输出部分流后禁止重放的失败，此时 attempts 可以是 1 或 2。没有数据不能表示“尝试 0 次”；只读 task 返回安全错误后父模型仍可能选择别的路径并最终 success。

`retries` 包含受管调用的汇总，`attempts=1/outcome=success` 也会出现，并不表示发生过自动重试。父 task 与子 model 的记录描述不同层级，不能累加 attempts 当成实际 provider 请求总数。子模型由父 task 负责重试时，每条子 model 记录仍是 attempts=1。

`code` 复用现有九个 `MODEL_ERROR_CODES`：`provider_rate_limited`、`provider_overloaded`、`context_too_long`、`model_unavailable`、`provider_auth_failed`、`provider_access_denied`、`provider_timeout`、`provider_unavailable`、`model_call_failed`。后端最多自动重试一次；前端无需按这些 code 再决定是否发起重试。

### 响应样例

下面是实际 Platform API HTTP 响应，取自上述目录的 `reliability-evidence.json` 中 `prompt=retry`，未修改字段或耗时。场景是合成 provider 第一次 429、第二次成功；观测查询使用真实 Langfuse SDK 和受控本地 HTTP 端点，并非生产 Langfuse。随机测试端口已随 fixture 关闭，样例 ID 用于对照证据，不作为持续可查询目标。

```json
{
  "version": 1,
  "availability": "available",
  "unavailable_reason": null,
  "correlation": {
    "execution_request_id": "6af86d7c0f544a35bbfd2ed3221ebbcb",
    "platform_trace_id": "6af86d7c0f544a35bbfd2ed3221ebbcb"
  },
  "trace": {
    "provider": "langfuse",
    "trace_id": "dd7a757046ea946b051f36b1e559aa2d",
    "url": null
  },
  "graph_executions": [
    {
      "observation_id": "1c7e2d05c48d476a8c0ca637e2cf7eea",
      "outcome": "success",
      "error_code": null,
      "duration_ms": 2660.08
    }
  ],
  "model_errors": [],
  "startup": {
    "duration_ms": 1599.605907,
    "phases": [
      {
        "name": "factory.memory_policy",
        "ordinal": 0,
        "outcome": "completed",
        "started_at": "2026-10-07T10:57:15.774157Z",
        "ended_at": "2026-10-07T10:57:15.774183Z",
        "duration_ms": 0.030169,
        "error_code": null
      },
      {
        "name": "factory.context_resolution",
        "ordinal": 1,
        "outcome": "completed",
        "started_at": "2026-10-07T10:57:15.774249Z",
        "ended_at": "2026-10-07T10:57:15.774346Z",
        "duration_ms": 0.100055,
        "error_code": null
      },
      {
        "name": "factory.mcp_tools",
        "ordinal": 2,
        "outcome": "completed",
        "started_at": "2026-10-07T10:57:15.774637Z",
        "ended_at": "2026-10-07T10:57:15.774649Z",
        "duration_ms": 0.015102,
        "error_code": null
      },
      {
        "name": "factory.model_connection",
        "ordinal": 3,
        "outcome": "completed",
        "started_at": "2026-10-07T10:57:15.774657Z",
        "ended_at": "2026-10-07T10:57:15.843946Z",
        "duration_ms": 69.296719,
        "error_code": null
      },
      {
        "name": "factory.model_build",
        "ordinal": 4,
        "outcome": "completed",
        "started_at": "2026-10-07T10:57:15.843966Z",
        "ended_at": "2026-10-07T10:57:16.519709Z",
        "duration_ms": 675.749428,
        "error_code": null
      },
      {
        "name": "factory.workspace",
        "ordinal": 5,
        "outcome": "completed",
        "started_at": "2026-10-07T10:57:16.519737Z",
        "ended_at": "2026-10-07T10:57:16.520163Z",
        "duration_ms": 0.430182,
        "error_code": null
      },
      {
        "name": "factory.agent_compile",
        "ordinal": 6,
        "outcome": "completed",
        "started_at": "2026-10-07T10:57:16.660721Z",
        "ended_at": "2026-10-07T10:57:17.343948Z",
        "duration_ms": 683.229909,
        "error_code": null
      }
    ]
  },
  "preparations": [
    {
      "observation_id": "b5a281b4e9954c6dad46d35b4d9119ac",
      "scope": "primary",
      "namespace": [
        "ProbeWorkspace_workspace.before_agent:3f05860b-b143-712f-cec4-1bc9e42431ca"
      ],
      "component": "workspace",
      "outcome": "prepared",
      "duration_ms": 2.641,
      "error_code": null
    }
  ],
  "retries": [
    {
      "observation_id": "3a85de2d55884942bab0bbf1760bd3ad",
      "scope": "primary",
      "namespace": [
        "model:9301043c-61ff-f881-7ea1-75e7ff76a764"
      ],
      "unit": "model",
      "role": null,
      "attempts": 2,
      "outcome": "success",
      "code": "provider_rate_limited",
      "duration_ms": 986.68
    }
  ],
  "truncated": false,
  "thread_id": "90515b9e-2dba-4363-b22e-289992ac46b4",
  "run_id": "20e9b065-588f-449e-ba86-3b6d4c3d7e38",
  "run_status": "success",
  "request_id": "46029ef7eadd468abb756f13e277127e"
}
```

本次成功响应的 `model_errors=[]`，但重试汇总仍保留前次 `provider_rate_limited`，不要依赖单一数组推断“是否出过错”。原 `graph_executions`/`startup` 数据继续展示。

同一批实际 HTTP 证据还有以下联调样本；完整响应及计数保留在 `reliability-evidence.json`，前端可据此构造测试 fixture：

| prompt | 实际 Run ID / 状态 | 要展示的调用单元 |
| --- | --- | --- |
| `exhausted` | `bc04c533-1900-45f9-a19d-4a2246d8aa55` / error | model attempts=2，exhausted，provider_rate_limited |
| `denied` | `425ebeec-b396-48bf-9341-b7dbaca021ee` / error | model attempts=1，failed，provider_access_denied |
| `partial` | `de892aeb-843b-4527-a4ad-bc69b4326be1` / error | model attempts=1，failed，model_call_failed；没有重放部分流 |
| `child` | `8eb602a7-9c0d-4faa-bc9f-7ff22ce4f74e` / success | task/general-purpose attempts=2，exhausted；两条子 model 各 attempts=1/failed |
| `parallel` | `8a6d4dce-bb34-4b5c-b364-bc947d038625` / success | 一条 task attempts=1/failed，另一条 attempts=2/success；namespace 不同 |
| `write-retry` | `be360a9e-5b5a-464c-bdc5-bb989c16d51a` / success | 审批 resume 后 model attempts=2/success，文件只写 1 次；preparations=[] 合法 |

## UI 与文件位置

### 架构分层与组件粒度规范（对标 Playbook）
现有 `RunDiagnostics.vue` 已有 504 行代码，已达单文件组件复杂度警戒线。**严禁直接往主面板内追加长模板！** 必须严格遵循单一职责原则拆分专职展示子组件，主面板仅负责组装和空态控制。

| 文件 | 架构职责与改动要求 |
| --- | --- |
| `apps/platform-web/src/modules/chat/diagnostics/types.ts` | 严格定义 `preparationSummarySchema`、`retrySummarySchema` 及根 schema 扩展；防注入正则、strict integer、子项 default(null) 及根级 default([])；沿用 safeParseRunDiagnostics |
| `apps/platform-web/src/modules/chat/diagnostics/view-model.ts` | 增加纯标签与视觉判定函数：<br>• `formatAttempts(attempts)`：1 显示“单次调用”，2 显示“重试 1 次”；<br>• `getPreparationOutcomeBadge(outcome)`：prepared=已准备(emerald)、reused=已复用(blue)、repaired=已补齐(amber)、failed=准备失败(red)；<br>• `getRetryOutcomeLabel(outcome)`：success=成功、exhausted=重试耗尽、failed=失败、cancelled=已取消、interrupted=已中断；<br>• `getRetrySeverity(outcome, runStatus)`：**核心视觉防坑**，若主 Run 为 success，则失败项降级为 `warning` (Amber 琥珀色)，严禁整屏标红！ |
| `apps/platform-web/src/modules/chat/components/trajectory/RunPreparationsSection.vue` | **新增专职子组件**：呈现准备结果（工作区准备/复用/补齐/失败）、耗时、namespace 截短显示；空数组时不渲染 |
| `apps/platform-web/src/modules/chat/components/trajectory/RunRetriesSection.vue` | **新增专职子组件**：呈现受管调用与重试尝试；列表标题定为「调用尝试与重试」；展示 unit、role、attempts、错误码及耗时；空数组时不渲染 |
| `apps/platform-web/src/modules/chat/components/trajectory/RunDiagnostics.vue` | 主面板精简重构：引入上述子组件，根据数据长度进行条件渲染，自身代码增量控制在 30 行以内 |
| `apps/platform-web/src/modules/chat/composables/useRunDiagnostics.ts` | 维持既有取消、target/epoch 检查、同一目标 not_recorded 最多一次延迟重查；新字段不需要独立请求/轮询 |
| `apps/platform-web/src/services/threads/diagnostics.service.ts` | 现有 API/目标核验直接复用，无需修改请求逻辑 |
| 对应 Spec 单元测试 | 包含 `view-model.spec.ts`、`RunDiagnostics.spec.ts`、新增子组件 spec、`useRunDiagnostics.spec.ts`、`diagnostics.service.spec.ts` |

首期不改 `TrajectoryTimeline.vue`/`TrajectoryInspector.vue` 的记录模型，不从摘要重新构造工具树或 model turns。它们的普通轨迹、子图历史配对和状态要做回归；只有现有轨迹天然携带完整 attempt 身份时才另评审时间线标记。

### 呈现与视觉防坑规则：

- **标题与语义明确**：重试区域标题定为 **「调用尝试与重试」**（而非误导性的“重试列表”），因为受管调用包含 `attempts=1/outcome=success`（正常单次成功），文案清晰区分“单次调用”与“重试 1 次”。
- **严格空态隐藏**：
  - `preparations.length === 0` 时隐藏运行准备区域；
  - `retries.length === 0` 时隐藏调用尝试区域；
  - 两数组都为空时（如旧版后端响应或无任何准备/重试记录），整个新增区域完全隐藏，保留既有 availability/truncated 状态。**绝对禁止显示“无重试说明运行完全正常”等冗余占位卡片**。
- **终态不误报（琥珀色降级）**：
  - 若 `run_status=success` 且存在失败/耗尽的重试调用（如 F03 首次限流重试成功，或 F04 子任务失败后父 Run 备选成功），主 Run 仍显示已完成，尝试记录使用 Amber 警示样式，**严禁整屏标红误报**。
- 原生 running/pending/interrupted/cancelled/timeout/error 由现有 SDK/Run 响应决定；model/task 的 outcome 不驱动 loading 或 Stop 按钮。
- 历史诊断缺数据、Langfuse disabled/backend_unavailable 使用已有反馈，查询按钮仅重查 GET，不重新发起 Run。
- 角色名是 graph 局部定义，不根据 `general-purpose` 这一名字显示写入权限/读写标识。后端已筛选的 task retry 表明允许重试，无需前端推断角色授权。
- 0 ms 与未知分开；不显示内部 fingerprint、config hash、堆栈、provider body、api_key、model ref、完整本地路径。未知字段不进入 DOM。
- 使用现有 BaseIcon、tokens 和紧凑列表；新增工具按钮有 aria-label/title，键盘可达；窄屏长 ID/role 换行或省略，不产生横向溢出。

## 失败与并发

| 条件 | 前端行为 |
| --- | --- |
| 查询 403 | 清空当前目标诊断并使用现有权限反馈，不影响无关项目 |
| 502/503/504、网络失败 | 已有数据可保留；可手动重查，不清登录/权限，不重发 Run |
| provider_auth_failed 作为 HTTP 200 DTO code | 显示模型连接认证失败，不处理为平台登录失效 |
| 切 Thread/Run/project 时旧响应迟到 | 原请求取消/epoch 丢弃；新页面不显示旧 prepares/retries |
| unavailable/not_recorded | 沿用现有同目标最多 1 次、2s 后 GET 重查；不新增 retry timer |
| 用户 Stop、等待审批、审批恢复 | 现有流程原样；resume 新 Run 选中规则保持，不把查询“重试”变为批准/提交 |
| SDK 流重连 | 仅恢复订阅；不因 prepare/模型失败观测重新 POST |

## 前端验收清单

由同事填写执行日期/浏览器、结果、截图或日志路径；下列均尚未执行。

| ID | 场景 | 预期 | 结果/证据 |
| --- | --- | --- | --- |
| F01 | 旧 v1 无新增字段，旧 Runtime 回退响应 | 校验通过，新区域隐藏，原诊断保持 | 待执行 |
| F02 | workspace prepared/reused/repaired/failed | 标签和耗时正确，失败不自动启动 Run，未知记录不冒充成功 | 待执行 |
| F03 | 第一次 429，第二次成功，Run success | 显示重试 1 次/限流摘要，主 Run 已完成，无红色终态误报 | 待执行 |
| F04 | 只读 task 两次失败后父 Agent 选择替代并成功 | task 错误仍保留，父 Run 已完成；消息/tool_call_id 不重复合并 | 待执行 |
| F05 | primary 模型重试耗尽/未知错误 | 原生 Run error；显示安全摘要，页面不自动重发 | 待执行 |
| F06 | 退避时 Stop，或 task 内 HITL 中断/恢复 | Stop 能取消；审批出现一次，恢复不重复批准/发送 | 待执行 |
| F07 | 快速切换项目/Thread/Run，旧查询迟到，历史与子图 | 当前目标隔离；无需重新建立诊断状态机 | 待执行 |
| F08 | 观测 disabled/not_recorded/timeout/partial/truncated，403 与 5xx | 保持原降级/有限查询/权限行为，不清登录 | 待执行 |
| F09 | secret canary、越界 attempts/负数/NaN/Infinity/超长/未知键 | schema/平台拒绝或 strip；canary 不进 DOM/console/截图 | 待执行 |
| F10 | 1440x900 / 390x844，浅/深色，键盘/长 role，刷新与多 Run 选择 | 无遮挡/横向溢出/点击错位；屏幕阅读名称正确 | 待执行 |

测试命令在 `apps/platform-web` 下执行（按当前已装依赖，不升级 SDK）：

```bash
pnpm test:run src/modules/chat/diagnostics/view-model.spec.ts src/modules/chat/components/trajectory/RunDiagnostics.spec.ts src/modules/chat/components/trajectory/RunPreparationsSection.spec.ts src/modules/chat/components/trajectory/RunRetriesSection.spec.ts src/modules/chat/composables/useRunDiagnostics.spec.ts src/services/threads/diagnostics.service.spec.ts
pnpm typecheck
pnpm lint
pnpm build
```

联合浏览器用例需要隔离三服务 + 后端故障场景；mock UI 测试不能替代。前端同事提供 F01-F10 实际证据后，回填 `tasks.md` T10 和 `verification.md` 的 Phase 前端区块。非前端通过不代表整单 Final 完成。

## 交接门禁

- [x] G0 已确认两数组字段/枚举、尝试上限和无 SSE 新事件。
- [x] T09 已提供实际 API 响应、OpenAPI 和安全字段验证记录。
- [x] 非前端 T01-T09/T11/T12 验证和交接完成；未部署现役，旧前端可继续工作。
- [ ] 同事认领 T10，确认文件/样例可直接使用。
- [ ] F01-F10、定向单测、typecheck/lint/build 完成。
- [ ] 与后端一起完成至少一条真实 Run + 三服务浏览器短链，以及停止/审批/历史关键链。

自主唤醒页面、通用 retry 开关、Agent 管理页参数不是本次同事任务；后续若有批准的产品契约，再单独交接。
