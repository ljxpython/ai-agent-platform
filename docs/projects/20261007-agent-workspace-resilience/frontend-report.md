# 前端开发交付报告：Workspace 执行失败与诊断

日期：2026-10-07。接收人：platform-web 开发同事。

## 交付状态

用户已批准治理方案。本轮在 `~/.codex/worktrees/agent-production-capabilities/ai-agent-platform` 实施 Runtime/API；基线 `bf47991b7592b19cbda1051c6a674623450318ae`，未改前端、未提交、未部署现役服务。本轮非前端本地与 Docker 范围 done；整体 partial 仅对应前端 T23 移交。原生 PG/Redis + local backend 两条链路已通过，后延的真实 Docker 执行/取消、性能测量及两条 HTTP/API/Worker 重启/回退链路也已补齐；Docker Desktop 已关闭。自动 retry 按批准 G1 分支 B deferred，完整证据与限制见 [verification.md](verification.md)。

前端任务 T23 由同事完成。本报告可独立用于接手；完整字段限制、合成测试输入和 F01-F10 见 [frontend-handoff.md](frontend-handoff.md)。

## 用户行为与后端结果

Runtime 的共享 `execute_in_workspace()` 已覆盖 Dear 主图、Showcase 主图与可执行子图。执行中环境不可确认、输出读取失效或清理不能确认时，稳定 Workspace 异常向外传播，原生 Run 为 `error`，Worker 不重调度整 Run。取消和 HITL 保持原控制流。

Docker exit125 只触发一次固定只读健康探测；探测成功保留命令 exit125，探测失败报告执行结果未知。其他普通非零值仍是工具执行结果，不等于基础设施故障。成功命令不额外探测、不新增 Workspace 观测。

**当前命令只执行一次。** 真实 CPython 测试证明 EAGAIN 可出现在文件副作用完成之后，已按批准 G1 分支 B 后置启动 transient retry。本期不生成 retry exhausted、recovered 或 not_started；实际记录为 attempts=1、retry_wait_ms=0、command_state=unknown。不要在页面补自动重发、自动切工作区或“安全重试”按钮。

## 前端要完成的两项改动

1. 在既有 Run 错误反馈区显示精确固定中文说明，同一 Run 的 live/历史/重连反馈去重；未知异常使用通用说明。
2. 在既有 RunDiagnostics 面板显示可选 Workspace 摘要；保持旧v1、诊断禁用、切Run和授权失效的现有行为。

无需新增页面、路由、权限、运行状态机、执行接口或配置。运行状态仍由原生 SDK/Run GET 决定，诊断只是观测。

## 错误契约

API 在原生执行错误槽位进行安全投影，没有新增 SSE event。字符串保持字符串；对象保留固定 `code/message` 和有限 `type/error`。

| 完整 code | 固定中文说明 |
| --- | --- |
| `runtime.workspace.unavailable` | 工作区暂不可用，本次运行已停止。 |
| `runtime.workspace.execution_unavailable` | 执行环境暂不可用，本次运行已停止。 |
| `runtime.workspace.backend_invalid` | 工作区执行配置不可用。 |
| `runtime.workspace.image_invalid` | 工作区执行配置不可用。 |
| `runtime.workspace.execution_outcome_unknown` | 命令执行结果尚不确定，本次运行已停止，请先核对工作区结果。 |

对象和字符串的逻辑错误值示例（合成fixture）：

```json
{
  "type": "RuntimeWorkspaceError",
  "code": "runtime.workspace.execution_outcome_unknown",
  "message": "命令执行结果尚不确定，本次运行已停止，请先核对工作区结果。"
}
```

```json
"runtime.workspace.execution_outcome_unknown"
```

未知错误：对象 `code=runtime.execution_failed`、`message=Runtime execution failed`；字符串 `runtime.execution_failed`。前端通用中文可沿用既有执行失败说明。旧版通用值仅用于安全降级，不能解释为 Workspace。只检查明确的执行错误槽位和完整值，不递归扫描工具正文/堆栈，不按substring抽码，不直接展示未知message。

入口包括普通 Run SSE、Protocol/v3 lifecycle/tasks、debug task_result、checkpoint/state/history 的 tasks.error。Run GET 和 Thread GET 未必带具体error，可能只有终态或error=null；以SDK错误事件/已授权state中的错误槽位展示原因，不因缺error合成成功或额外提交请求。

网络失败、HTTP Envelope、模型诊断、普通工具错误和 Workspace Run 错误维持各自既有语义。尤其 unknown 不表示命令没开始，也不承诺所有文件已保留。普通消息、工具content、artifact/result的业务正文保持保真。

## 诊断契约

接口与授权保持原样：

```text
GET /api/langgraph/threads/{thread_id}/runs/{run_id}/diagnostics
Authorization: 既有平台登录凭证
x-project-id: 当前项目
```

继续使用 `diagnostics.service.ts` 和 `useRunDiagnostics.ts`。不直连Runtime或Langfuse，不新增轮询。

version仍为1；根DTO新增 **可选** `workspace_executions`，缺失默认 `[]`、最多20条。每层Zod对象strip未知字段，不展示命令、路径、stderr、container、凭据等extra。

| 字段 | 校验与展示 |
| --- | --- |
| `observation_id` | 标识1-128字符，ASCII字母/数字/下划线/点/冒号/短横线 |
| `backend` | 固定docker |
| `phase` | start/execute/cleanup，显示启动/执行/清理 |
| `outcome` | recovered/failed/cancelled，显示固定标签，不能改Run状态 |
| `code` | 上表五个值或null；只用固定说明 |
| `command_state` | not_started/started/unknown；unknown显示结果未知，不推导安全重发 |
| `attempts` | 严格整数1-4，包含首次；显示“尝试N次” |
| `retry_wait_ms` | 有限非负数；0为没有退避等待；用既有formatDuration |
| `duration_ms` | 有限非负数或null；null是未知，不当0 |

`graph_executions[].error_code` 与 `startup.phases[].error_code` 接受 ModelErrorCode 或 WorkspaceErrorCode，`model_errors[].code` 仍为模型专用。当前Schema对graph/startup采用有界字符串，同事只需补固定展示映射，避免放宽model_errors的分类来源。

现有v1其它字段不变。availability为disabled/unavailable时照旧空态；partial显示已有部分记录；truncated延续现有上限提示。空Workspace数组不能解释为没有执行命令，成功路径通常不产生该记录。

## 逐文件任务

| 文件（相对仓库根） | 同事需要做什么 |
| --- | --- |
| `apps/platform-web/src/modules/chat/diagnostics/types.ts` | 新Workspace schema与可选数组默认值；数值/枚举/上限校验，每层strip |
| `apps/platform-web/src/modules/chat/diagnostics/view-model.ts` | 固定阶段/状态/五码文案，复用formatDuration，未知安全降级 |
| `apps/platform-web/src/modules/chat/components/trajectory/RunDiagnostics.vue` | 原面板加紧凑Workspace行；当前Run记录显示阶段、尝试次数、等待与安全原因 |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | 既有错误出口接精确映射，按sessionEpoch/project/thread/run去重；旧Run不覆盖新Run状态 |
| `apps/platform-web/src/modules/chat/composables/useRunDiagnostics.ts` | 回归epoch/abort、迟到响应、切Run、一次延迟刷新；不新建控制器 |
| `apps/platform-web/src/services/threads/diagnostics.service.ts` | 回归x-project-id、响应thread/run一致性；继续原GET |

主工作目录HEAD已推进至 `11ddaa08c4202d71c69e995375e98d1412414c09`，还有同事未提交的前端改动；本worktree仍基于 `bf47991b7592b19cbda1051c6a674623450318ae`。接手应先核对最终合入版本；若已有 `RUNTIME_MODEL_ERROR_MESSAGES/extractRuntimeModelErrorMessage`，在同一模块形成共享精确映射，避免两个重复入口。不要用本worktree旧前端文件覆盖同事工作。

遵循Web playbook、control-plane和visual-baseline；使用现有反馈区/tokens/BaseIcon，长中文换行，浅深主题一致，不抢焦点或强制滚底，固定文字使用文本渲染。

## 已有验证证据与样例

API全仓355 passed、23 skipped、601 subtests passed，定向76 passed、122 subtests passed；Runtime非外部扩大回归708 passed、39 skipped、55 deselected，显式排除外部PG收件箱专项，不称无条件全仓。最新共享执行/诊断定向59 passed、5 deselected，覆盖 ServerVersion 补修。skip/deselected不计通过，范围与复现命令见验证记录。

本地工具恢复/控制流真实链路1 passed（188.12秒）：主/子图、unknown fatal 全出口脱敏、HITL approve/edit/reject/clarification/cancel、三角色重启/checkpoint回放、原文件保留及源码回退后新Run均通过。本地 Workspace 链路1 passed（45.04秒）：Dear/Showcase 实际 local shell 退出7后 Run success、counter=once；根符号链接拒绝返回固定 unavailable，Run error、reason=business_error、retry_count=1，私有路径屏蔽、原文件保留。当前本地正常命令不生成 Docker Workspace 诊断，不能据空数组推导命令未执行。

| 本地场景 | thread_id | run_id | 状态 |
| --- | --- | --- | --- |
| 工具主图恢复 | `b70399be-22fc-45d4-b007-74296cf388dd` | `1a817b71-8f31-4ef8-8fd6-f7c1490b0bf2` | success |
| 工具子图恢复 | `6fbb9bae-ae0b-41a3-88a7-39871d96015f` | `aba10253-88b2-4b25-b7ca-6f31c477fc46` | success |
| Dear local 执行 | `1a39a089-4366-41be-8fe7-b73e15e1f3e4` | `176fd98a-4aa4-4da0-99f1-adda0827531b` | success |
| Showcase local 执行 | `f8423644-a0d8-4734-a2b8-20756207f269` | `917eac00-1e0e-40f8-befd-185b8586d9d3` | success |
| Dear local 根拒绝 | `d6557820-5b24-4d2c-b22f-59619818d586` | `a3290eb4-8277-4b08-a9c4-5ef8f3b350c5` | error |

用户重新启动Docker后，两条实际HTTP/API/Worker链路2 passed（1561.03秒）：Workspace正常非零结果、主/子图unknown、副作用once、不重调度、原生取消、诊断授权；工具恢复及approve/edit/reject/clarification/cancel；三角色重启/checkpoint与HEAD源码回退续接均通过。共享执行器4 passed、Dear/Showcase容器接入2 passed，交替性能/并行重复取消2 passed；最新非integration32 passed。性能数据保留波动，不宣称提升或生产SLO达标。最新运行ID如下，隔离资源已回收，不能在现役服务查询：

| Docker恢复场景 | thread_id | run_id | 原生状态 |
| --- | --- | --- | --- |
| Dear正常工具结果 | `222b027a-0a47-45a2-ad39-d00ec037f54c` | `f3f25836-e125-4ab4-a4b0-2f172fa581d2` | success |
| Dear主图unknown | `a44d339a-bab5-4046-a38d-ddb1a335a0ff` | `e2c5f435-3383-4fd4-9941-9fbe1b52e1d3` | error |
| Showcase主图unknown | `4140f92c-20f8-439c-bcce-fbffb1d638ff` | `92cc7831-8b66-4fa8-a89a-4a0f9732f4ee` | error |
| Showcase子图unknown | `c4b39441-6e88-49cd-96a1-207a3ea20f52` | `d4f94496-6ed8-45e4-86f5-008aa1c6c91b` | error |
| Dear执行取消 | `19971216-114b-439a-b3c2-660d737dc984` | `f4217bd8-0372-4080-a755-b35acd75fc85` | interrupted |
| 工具主图恢复 | `52036af6-b2f2-4185-920b-67f25362a2fa` | `67b74446-f601-4655-be99-3835296beb86` | success |
| 工具子图恢复 | `fd87f1b7-51ff-43aa-a683-30b3ac6d6c25` | `f00f9254-db00-44ff-a3e7-fe682273036e` | success |

历史HTTP/API/Worker/Docker Phase 链路确认三条失败Run副作用once、reason=business_error、retry_count=1仅首次claim；诊断禁用不遮失败；真实共享/撤权、跨项目和错误Run隔离通过。以下为此前历史 Phase 运行ID（不是固定业务资源，也不应写进产品代码）：

| graph/场景 | thread_id | run_id | 原生状态 |
| --- | --- | --- | --- |
| Dear普通非零工具结果 | `507c19b3-e4f7-4a24-ac1c-23e8f7facb1c` | `6bce465b-f3ed-4a75-85a2-25d1fda57e29` | success |
| Dear结果未知 | `f7c848e3-a4c6-4707-825d-df8f686b0321` | `1341f622-6ffc-4e8d-b2eb-82b39351546e` | error |
| Showcase主图结果未知 | `76e5def7-ae1a-442f-a131-4f348ecc7ed9` | `ba6cb875-7a2e-4184-bcdc-b7db73689462` | error |
| Showcase子图结果未知 | `d96d8991-9061-404f-a02b-a2f9fc61fc5c` | `9b5e00c6-6ff1-45fa-9930-236752ddaef3` | error |
| Dear根符号链接拒绝 | `6e3939f2-1843-4398-a5a5-9d99dfb3f32e` | `0e7e5374-e188-47e8-a772-bab253efd527` | error |
| Dear执行取消 | `3c12ec9b-efc2-457b-b454-7de0df4fece9` | `9ac9691d-353a-4ea5-a3f6-ed4cbedc79ba` | interrupted |

这批测试栈已回收，ID用于核对保存的证据，不能在现役服务查询。新联调需要重新运行隔离fixture。

最新Docker验收中Dear失败Run `e2c5f435-3383-4fd4-9941-9fbe1b52e1d3` 的诊断HTTP响应（真实callback记录，经**合成Langfuse transport**查询；不是公网Langfuse验收）：

```json
{
  "version": 1,
  "availability": "partial",
  "unavailable_reason": null,
  "correlation": {
    "execution_request_id": "2a4adcf630d44026ab5a9128ebfa98e3",
    "platform_trace_id": "2a4adcf630d44026ab5a9128ebfa98e3"
  },
  "trace": {"provider":"langfuse","trace_id":"dc7225c031cb6a45ccbdbeda1ba963fd","url":null},
  "graph_executions": [
    {"observation_id":"fixture-9","outcome":"failed","error_code":"runtime.workspace.execution_outcome_unknown","duration_ms":5353.09}
  ],
  "model_errors": [],
  "workspace_executions": [
    {"observation_id":"fixture-8","backend":"docker","phase":"execute","outcome":"failed","code":"runtime.workspace.execution_outcome_unknown","command_state":"unknown","attempts":1,"retry_wait_ms":0.0,"duration_ms":2702.3280849998628}
  ],
  "startup": null,
  "truncated": false,
  "thread_id": "a44d339a-bab5-4046-a38d-ddb1a335a0ff",
  "run_id": "e2c5f435-3383-4fd4-9941-9fbe1b52e1d3",
  "run_status": "error",
  "request_id": "fb416a7ec2234b0e8829a7e94d58e320"
}
```

## 前端验收与交回内容

F01-F10逐项标准见 [验收清单](frontend-handoff.md#前端验收清单)：五码对象/字符串、未知输入/canary、旧v1、数值上限、同Run去重、HITL/取消/断连、r1迟到不污染r2、账号/项目/撤权、三尺寸浅深主题。

同事交回修改版本及文件、F01-F10结果、Vitest/lint/typecheck/build输出、390x844/1024x768/1440x900浅深主题截图，以及真实三服务的live/history/诊断对照。后端自动化不替代浏览器验收。

已有测试文件优先扩 `RunDiagnostics.spec.ts`、`useRunDiagnostics.spec.ts`、`diagnostics.service.spec.ts` 与实际映射模块测试。依项目package.json执行现有Vitest、ESLint、vue-tsc和构建，不自行加入新工具。

发布顺序：先API可选DTO/安全投影，再Runtime，最后Web；新Web兼容旧v1缺字段，旧Web可以忽略新字段。具体部署不在本次授权内。前端无需承担Docker生命周期、执行重试、云provider或外部业务通知。
