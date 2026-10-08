# 前端交接：Workspace 执行失败与诊断

## 交接状态与范围

**状态：后端契约已实施，前端由同事接手。** 用户已批准；Runtime/API已完成代码与定向验证。本文demo ID为合成fixture，真实隔离运行与HTTP诊断样例见 [前端报告](frontend-report.md)，最终验证见 [verification.md](verification.md)。

前端只做安全 Run 错误说明和既有 RunDiagnostics 的 Workspace 摘要，不新增页面、执行 API、云 provider 选择、自动重发/重试按钮、独立 Run 状态机或执行配置。

本 worktree 基线为 `bf47991b7592b19cbda1051c6a674623450318ae`；主工作目录 HEAD 已推进至 `11ddaa08c4202d71c69e995375e98d1412414c09`，另有同事未提交的前端改动。接手时核对最终合入版本；若已有 `RUNTIME_MODEL_ERROR_MESSAGES/extractRuntimeModelErrorMessage`，在同一模块统一模型/Workspace 的精确展示映射，避免复制入口。不要用此 worktree 的旧前端文件覆盖同事工作，也不能依赖尚未合入函数。

## 用户可见行为

| 事实 | 应呈现 | 操作边界 |
| --- | --- | --- |
| Workspace 根或执行器不可用，Run error | 当前 Run 一份固定说明，已有消息/文件入口保留 | 不自动换工作区，不重发原输入 |
| 执行结果/清理未知，Run error | “命令执行结果尚不确定，本次运行已停止，请先核对工作区结果。” | 不显示“安全重试”或“全部文件已保留”的未经确认承诺 |
| 工具 error、Run 继续 | 现有失败工具卡 | 工具失败不推导 Run 失败 |
| HITL/澄清、用户取消 | 既有等待/取消展示 | 不误标 Workspace 故障、不自批准 |
| SSE 断连 | 既有连接状态与 SDK 重连/Run 核实 | 连接恢复不重放命令；不伪造 Run error |
| 诊断 disabled/unavailable | 现有诊断空态，安全 Run 提示仍出现 | 不将观测服务状态当执行状态或撤权 |

运行状态以官方 SDK controller 和原生 Run GET 为事实来源。Run GET/Thread GET可能只返回状态或error=null，具体原因从SDK事件或已授权state/history错误槽位读取。`workspace_executions[].outcome` 是某次调用的观测，不是整个 Run 状态。

## 契约 A：原生执行错误槽位

没有新增 SSE event。继续使用现有 API Run SSE、Protocol/v3 lifecycle/tasks、Run/Thread/state/history。下列是 SDK 装配后的逻辑数据形状，不能自行拼接新事件。

### 对象错误

```json
{
  "status": "error",
  "error": {
    "type": "RuntimeWorkspaceError",
    "code": "runtime.workspace.execution_outcome_unknown",
    "message": "命令执行结果尚不确定，本次运行已停止，请先核对工作区结果。"
  }
}
```

### 字符串错误

部分原生流或 checkpoint 的 error 是字符串，保持字符串形状：

```json
{"status":"error","error":"runtime.workspace.execution_outcome_unknown"}
```

前端只按完整白名单值映射，兼容对象的 `code` 和字符串完整值。禁止从原始异常堆栈、错误长文本、工具输出或任意嵌套 key 中搜索 Workspace 码。

| code | 中文说明 |
| --- | --- |
| `runtime.workspace.unavailable` | 工作区暂不可用，本次运行已停止。 |
| `runtime.workspace.execution_unavailable` | 执行环境暂不可用，本次运行已停止。 |
| `runtime.workspace.backend_invalid` | 工作区执行配置不可用。 |
| `runtime.workspace.image_invalid` | 工作区执行配置不可用。 |
| `runtime.workspace.execution_outcome_unknown` | 命令执行结果尚不确定，本次运行已停止，请先核对工作区结果。 |

本期选择批准分支 B；单次命令执行，自动启动 retry deferred，不生成耗尽码，不生成 recovered/not_started。实际 attempts=1、retry_wait_ms=0，command_state=unknown。不合成“4 次尝试”或未开始保证。未知码/旧通用错误采用固定执行失败文案，不展示未知异常 message。

当前交付的 generic fallback 对象 code 与字符串稳定码均为 `runtime.execution_failed`；对象 message 固定为 `Runtime execution failed`。旧版值只作通用失败兼容，不解释为 Workspace。

按 `user/sessionEpoch/project/thread/run` 关联提示，live/Run GET/history 重复出现不产生多份 toast/banner。r1 的终态错误不能覆盖同 Thread 新运行 r2 的 busy/error。沿用现有错误显示区，不合成 AIMessage/ToolMessage，不修改消息顺序和 ID。

## 契约 B：既有 RunDiagnostics v1

接口继续为：

```text
GET /api/langgraph/threads/{thread_id}/runs/{run_id}/diagnostics
```

使用既有认证与 `x-project-id`，不直连 Runtime，不传 retry 参数、provider 凭据或额外身份字段。现有 service 会核对响应 thread/run，composable 有 epoch/abort 和一次延迟刷新，应继续复用。

新增可选 `workspace_executions`，旧 v1 缺失视为 `[]`；不升级 version。graph/startup 的 `error_code` 允许 Workspace 固定码，`model_errors` 仍只表示模型失败。

```json
{
  "version": 1,
  "thread_id": "00000000-0000-4000-8000-000000000001",
  "run_id": "00000000-0000-4000-8000-000000000002",
  "run_status": "error",
  "request_id": "query-demo",
  "availability": "partial",
  "unavailable_reason": null,
  "correlation": {"execution_request_id":"execution-demo","platform_trace_id":"trace-demo"},
  "trace": null,
  "graph_executions": [
    {"observation_id":"graph-demo","outcome":"failed","error_code":"runtime.workspace.execution_outcome_unknown","duration_ms":120.0}
  ],
  "model_errors": [],
  "startup": null,
  "workspace_executions": [
    {
      "observation_id": "workspace-demo",
      "backend": "docker",
      "phase": "execute",
      "outcome": "failed",
      "code": "runtime.workspace.execution_outcome_unknown",
      "command_state": "unknown",
      "attempts": 1,
      "retry_wait_ms": 0.0,
      "duration_ms": 100.0
    }
  ],
  "truncated": false
}
```

| 字段 | 前端校验/展示 |
| --- | --- |
| `workspace_executions` | 可选数组，默认 `[]`，最多 20 条；每层对象 strip 未知字段 |
| `observation_id` | 有界标识，<=128 字符 |
| `backend` | 当前仅 `docker`；不要显示云环境切换入口 |
| `phase` | 固定 start/execute/cleanup，映射“启动/执行/清理” |
| `outcome` | recovered/failed/cancelled；固定说明，不控制 Run 状态 |
| `code` | 白名单码或 null；未知只显示通用说明，不拼原文 |
| `command_state` | not_started/started/unknown，映射“未开始/已开始/结果未知” |
| `attempts` | 严格有限整数 1-4，含首次；显示“尝试 N 次”，不能显示“重试 N 次” |
| `retry_wait_ms` | 有限非负数，0 为实际未等待；复用 formatDuration |
| `duration_ms` | 有限非负数或 null；null 显示未知，不当 0 |

Workspace 列表只记录受影响调用，不是所有命令审计；空列表表示没有可展示记录，不能解释为“没有执行命令”。`truncated=true` 延续既有有限记录提示。RunDiagnostics `availability` 是观测完整度，不能覆盖原生运行状态。

## 逐文件交接

| 文件（相对仓库根） | 建议改动 |
| --- | --- |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | 在既有 Run 错误展示出口调用有限纯映射；如果模型专项已合入，扩它的共享映射，不叠加第二套处理 |
| `apps/platform-web/src/modules/chat/diagnostics/types.ts` | 增 WorkspaceExecution schema 与可选数组默认值；根/嵌套 strip；保持旧 version1 和现有模型字段 |
| `apps/platform-web/src/modules/chat/diagnostics/view-model.ts` | 扩固定阶段/状态/错误标签；复用 formatDuration；未知码安全降级 |
| `apps/platform-web/src/modules/chat/components/trajectory/RunDiagnostics.vue` | 原面板增加紧凑 Workspace 行，呈现阶段、尝试次数、等待及安全原因；outcome 只作观测标签，当前不生成 recovered |
| `apps/platform-web/src/modules/chat/composables/useRunDiagnostics.ts` | 回归迟到响应、epoch/abort、切 run 与一次延迟刷新；无需为 Workspace 增轮询 |
| `apps/platform-web/src/services/threads/diagnostics.service.ts` | 回归项目头与 ID 一致性；复用同一 GET，不增接口 |

优先在现有 diagnostics/view-model 或最终模型错误映射文件增纯函数。仅当主会话与诊断面板有两个真实使用者时，再抽同 module 的共享纯映射文件；不新增全仓错误服务。

继续遵循 Web playbook、control-plane 和 visual-baseline：复用现有反馈区、tokens 与 BaseIcon；长文案换行；不抢焦点、不强制滚底；浅/深主题一致；固定告警文字通过 Vue 文本渲染，不 v-html。

## 前端验收清单

| ID | 场景 | 通过标准 |
| --- | --- | --- |
| F01 | 白名单对象/字符串、重复投影 | 同一中文说明；同 Run 只一份反馈；旧 generic 安全降级 |
| F02 | 未知码/嵌入码/带 canary message | 不按 substring 识别，不公开未知异常正文 |
| F03 | 成功Run、保留的recovered合成兼容fixture | 当前成功路径无额外Workspace记录；fixture的recovered不改变Run状态，本期无真实恢复用例 |
| F04 | unknown/根不可用 | 准确失败说明与原生终态；不重试/换环境/创建假消息，不声称所有数据已保存 |
| F05 | 普通工具失败、HITL、取消、断连 | 不误标 Workspace 故障；原审批/恢复/连接流程不改变 |
| F06 | 旧 v1、缺字段、disabled/unavailable/truncated | schema 和面板正常；诊断失败不能遮住安全 Run 提示 |
| F07 | malformed 数值/枚举/超额/extra | 负数、NaN/Infinity、非法 attempts 等安全拒绝；未知字段剥离 |
| F08 | 切 run/thread、r1 迟到、历史与重连 | 选中 Run 的诊断与错误一致；r1 不覆盖 r2；无重复自动提交 |
| F09 | 切项目/账号、真实撤权、错 ID 响应 | 既有 scope 清理；迟到数据不入新会话；网络/5xx 不清登录 |
| F10 | 390x844、1024x768、1440x900，浅/深主题 | 长文案不挤输入框/工具卡；面板可读、键盘/焦点/读屏提示可用 |

推荐扩现有 `diagnostics/view-model` 对应测试、`components/trajectory/RunDiagnostics.spec.ts`、`composables/useRunDiagnostics.spec.ts`、`services/threads/diagnostics.service.spec.ts`；新增映射的测试跟随实际模块，不为 mock UI 再建运行状态。

在 `apps/platform-web` 执行：

```bash
pnpm test:run src/modules/chat/components/trajectory/RunDiagnostics.spec.ts src/modules/chat/composables/useRunDiagnostics.spec.ts src/services/threads/diagnostics.service.spec.ts
pnpm lint
pnpm typecheck
pnpm build
```

补充实际变更的 schema/纯映射用例。浏览器验收使用真实隔离三服务链路，桌面/移动截图与实际消息/诊断样例需要保留。

## 联调交付物与发布依赖

Runtime/API已交付批准字段、G1分支B、锁定fallback、ordinary/Protocol/v3错误槽位样例、真实Worker失败及同Run的状态/回放/HTTP诊断证据；见 [前端报告](frontend-report.md)。完整Final结果以verification.md为准。

前端同事交付改动版本/文件、F01-F10 结果、静态门禁输出、三尺寸截图及真实链路证据，明确未完成项。API 可选字段和安全投影先就绪，再与 Runtime 联调；旧字段和未知数据始终安全降级。

没有要求前端同事接云 provider、执行重试、通知 Slack/GitHub/Linear 或解决 Docker 生命周期。此类逻辑不得进入页面、Pinia 状态或浏览器配置。
