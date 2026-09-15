# Dear Agent 前端交接与开发指南

本阶段**严禁修改现有通用 Chat 业务组件（`apps/platform-web/src/modules/chat/`）**。Dear Agent 专属业务目录固定为 `apps/platform-web/src/modules/dear-agent/`，从现有 Chat 业务代码复制基线并独立演进；网络请求统一由 `apps/platform-web/src/services/` 承接，严禁在业务目录内重复造公共请求与 SDK 基础设施。

## 路由与页面规格

- **路由路径**：`/workspace/projects/:projectId/dear-agent/:threadId?`
- **路由名称**：`workspace-dear-agent`
- **布局承载**：沿用平台通用 `WorkspaceLayout`
- **权限控制**：继承项目读取权限；发起 Run、修改或删除操作前通过 `useAuthorization()` 检查项目写权限。
- **会话过滤**：会话列表服务端按 `graph_id === "dearflow_agent"` 严格过滤，按项目隔离，URL 参数与真实会话身份服务端校验绑定。

## P1 必做核心清单

1. **页面底座与会话列表**：
   - 建立 `DearAgentPage.vue`，组合会话列表（Sidebar）、消息流主区域与单一 SDK stream controller。
   - 切换项目/用户/会话时必须重置并销毁旧会话，丢弃迟到响应，杜绝双 controller 内存与状态泄漏。
2. **接入运行时 Gateway**：
   - 对接平台网关及 LangGraph 官方流：支持 Dear Graph（`dearflow_agent`）的启动（Run）、SSE 流式事件监听和恢复（Resume）。
3. **文件流转与产物交付**：
   - 接入工作区文件上传，生成合法 `FileRef`；
   - 接入交付成果（`ArtifactRef`，P1 先行打通 TXT 及纯文本）的受权安全预览与下载，杜绝裸物理路径访问。
4. **官方澄清中断渲染（Clarification HITL）**：
   - 监听官方 `stream.interrupts` 中 `value.kind === "clarification"` 的中断数据（由后端 `request_information` 工具触发）。
   - P1 支持动态渲染 `text`（单行/多行文本）和 `select`（单选）表单组件。
   - 提交严格遵循恢复契约：`{"<interrupt-id>": {"schema_version": 1, "status": "answered", "values": {...}}}`。
   - 表单带客户端即时校验，后端 422 格式错误时原位回显，不丢失草稿。
5. **工具人机审批卡片（Action Review HITL）**：
   - 承接官方 `action_requests` 中断，渲染工具审批卡片，支持 `approve` / `edit` / `reject`；
   - 正确展示工具执行中、执行成功与失败错误态。
6. **全局中断交互保护（重要约束）**：
   - 在存在任何挂起中断（`hasPendingInterrupts` 为 true，含审批、澄清和未知中断）期间，**底部输入框必须禁用常规发送**，禁止用户以普通聊天消息绕过中断恢复。

## P2 后端接入交接（2026-09-14，本轮不实施前端）

1. 模式：通过既有运行 Context 提交 `execution_mode=flash|standard|pro|ultra`，默认 Standard。新 Dear 请求使用 Context v2 签名，前端不计算签名。模式不能在审批恢复时更改；不支持推理控制的模型保持默认并在追踪中记录原因，不声称所有 Flash 都关闭思考。
2. 能力：继续查询线程 capabilities；`execution_modes`、`clarification_field_types`、`research`、`message_queue` 来自后端。能力声明不替代模型／工具授权；缺 Tavily 配置时 research=false。
3. 澄清：v1 envelope 内新增 textarea、number、multi_select、checkbox、date。multi_select 值为字符串数组、checkbox 为布尔值（false 也是有效回答）、date 为 YYYY-MM-DD。沿用官方 interrupt ID 映射和恢复入口；未知字段禁止提交，422 保留草稿。
4. 来源：研究工具标准 ToolMessage.artifact 内 `version=1,sources=[...]`，包含 `source_url,kind,path,content_hash,tool_call_id,thread_id,run_id,namespace,observed_at`。search_snippet 与 page_text 分开展示；模型可见结果包含 preview/truncated。仅外链打开公开 URL；sources 路径暂供 Agent read_file，不能自行拼成文件下载路由。最终 TXT 沿用 ArtifactRef 下载。
5. 补充消息：既有 `POST /api/langgraph/threads/{thread_id}/messages`，请求 `client_message_id,target_run_id,content`，携带 Idempotency-Key；GET 同路径查询回执。202 表示入队，consumed 才表示消费，断线不重发新 ID。待澄清／审批时仍走 resume，不能用队列绕过。
6. Ultra 只有普通同步研究子 Agent，沿用子图事件；没有新增单子任务取消或独立用量接口。P3 再处理展示缺陷。

后端逐文件／测试定位见 [06 实施记录](implementation/06-p2-research-and-interaction.md)。上述为接入契约，不表示浏览器链路已经验收；完整后端部署结果以 P2 执行包实时状态为准。

## 后续演进阶段

### P2 前端实施清单（待接入验收，不代表代码全部缺失）

本轮仅补文档，不实施前端。当前目录已有独立 Session、轨迹、文件面板及澄清组件；先核对已有实现，再补差异，不重新复制 Chat。以下路径除特别注明外均相对 `apps/platform-web/src/modules/dear-agent/`。

| 顺序／功能 | 具体工作与接口 | 优先检查的现有代码 | 完成标准／状态 |
|---|---|---|---|
| 1. 能力与执行模式 | 从线程 capabilities 读取四模式、research、message_queue 和字段类型；新 Run 的 context 提交 execution_mode；恢复沿用原值 | `composables/useDearAgentSession.ts`、`components/ChatRunOptionsDialog.vue`；请求复用 `apps/platform-web/src/services/threads/session.service.ts` | 切换模式实际进入请求，运行／待审批期间不能篡改当前 Run 模式；待验收 |
| 2. 七类澄清表单 | 在既有 text/select 上核对并补 textarea/number/multi_select/checkbox/date；按 interrupt ID 恢复 | `human-input.ts`、`components/ClarificationCard.vue`、`run-actions.ts` | false 合法、日期／有限数值／多选有效；422 保留输入；未知字段阻止提交；待验收 |
| 3. 研究过程与来源 | 复用已有工具轨迹展示 search_web/fetch_page；读取 ToolMessage.artifact.sources，区分摘要与网页正文，展示来源 URL 和截断状态 | `transcript.ts`、`components/ToolResult.vue`、`trajectory/trajectory-adapter.ts` | 来源按真实 thread/run/namespace/tool_call_id 关联，不能把模型文字当受信来源；待验收 |
| 4. 运行中补充消息 | 运行中使用队列 POST，固定 client_message_id/target_run_id；GET 读取回执；有 interrupt 时仍走 resume | `components/ChatComposer.vue`、`composables/useDearAgentSession.ts`；`apps/platform-web/src/services/threads/messages.service.ts` | queued 与 consumed 分开；重试同 ID；not_consumed／拒绝／断线有明确反馈；待验收 |
| 5. 报告与下载 | 复用 P1 ArtifactRef 和受权下载；区分工作文件、已发布成果以及发布失败 | `components/ChatArtifactPanel.vue`、`components/ThreadFile.vue`；`apps/platform-web/src/services/threads/files.service.ts` | 下载实际发布文件；sources.path 不自行拼为下载地址；待验收 |
| 6. 中断、错误与恢复 | 复用唯一 Session/controller；刷新恢复审批／澄清／队列状态，显示 timeout/error，不因流关闭判成功 | `composables/useDearAgentSession.ts`、`history-view-model.ts`、`approvals.ts` | 原 Chat 不受影响，断流不自动重复发起研究任务；待验收 |

首个前端验收场景：选择 Pro → 七字段澄清 → 研究中补充要求 → 来源展示 → 文件审批 → 下载报告 → 刷新复核。报告包含真实引用与补充要求，回执精确等于 consumed。第二个场景验证服务超时与重连，不能把本机 Redis 超时包装成成功。

四模式和七字段的后端接口已交付；前端实现状态需由前端负责人逐项验证。当前 P2 整阶段仍 partial，原因见 [P2 执行包](phases/P2-研究与交互基础.md)。欢迎区和装饰性布局不作为这次接入前置；不新增浏览器操作、MCP 管理、记忆或 Skills 编辑界面。

### P3 前端接入范围

用户确认本轮只做后端，F3 实现和浏览器验收 deferred。后端测试及限制见 [07 实施记录](implementation/07-p3-subagents-and-observability.md)。不增加新的子任务 REST API。

对接时按以下事实处理：

- 根消息中的 `AIMessage.tool_calls[].id` 对应返回 `ToolMessage.tool_call_id`。同角色不能用 name 匹配。
- 原生 LangGraph v3：`lifecycle.params.data.cause.tool_call_id` 关联分派；真实 scope 是 `params.data.namespace`，外层 `params.namespace` 可能为空。
- 当前 GraphHarbor 0.13.0.post27 会过滤上述外层 namespace 为空的 lifecycle。保留的 `debug` 事件中，`data.type=task`、`data.payload.name=tools`，`data.payload.input[]` 是调用列表；其中 `id` 是模型调用 ID，`data.payload.id` 是执行任务 ID。只有拿到该事实后才能将 `tools:<执行任务 ID>` 与收到的子图 namespace 匹配；禁止拼 `tools:<模型调用 ID>`。组合证据见 `apps/runtime-service/tests/services/dearflow_agent/test_subagents.py`。这不是已实现的前端适配。
- 先核对当前 SDK 是否向消费者暴露 debug 关联；未暴露、缺事件或历史中缺映射时，显示“关联未知／恢复中”，保留根 task 结果，不按顺序或名称串接。完整 discovery 需依赖包修复后再验收，不复制一套事件系统。
- 子消息的 `usage_metadata.input_tokens/output_tokens/total_tokens` 是该次模型消息用量。缺失显示未知，不显示0；不得与包含子调用的父总量重复相加，也不能据此宣称拥有独立子任务计费账本。
- 父取消沿用既有 Run cancel，ACK 只是已接受；等待 Run `interrupted` 等真实终态。已有成功 ToolMessage 可保留，仍未返回的任务不能标成功；父超时不能被解释成子任务全部成功。

F3 需完成：稳定映射、根/子 transcript 分离、缺 discovery 降级、刷新恢复、父取消反馈与有来源的 usage 展示。浏览器至少验两个同角色并发、断流刷新、未知关联、父取消及部分结果；不添加单子任务取消按钮。

P3 围绕现有 `components/SubagentCard.vue`、`components/SubtaskDetail.vue`、`composables/useTranscriptMessages.ts`、`transcript.ts` 和轨迹适配器修复任务关联、状态及历史恢复；具体顺序与测试见 [P3 执行包](phases/P3-子%20Agent%20展示与观测.md)。当前卡片存在按角色名匹配及 `tools:${tool.id}` 推测 namespace 的兜底，实施时需以官方真实数据验证并去除错误关联，不把本次阅读当作缺陷修复完成。

不加“取消这个子 Agent”按钮，不估算独立子任务费用；只有已有回调／消息提供可归属的 usage 才展示，否则显示未知。父 Run 取消继续使用已有入口。后端验证可以先做，前端代码仍需另行安排，不能把后端通过标成 F3 完成。

- **P2**：四模式切换、七字段澄清、来源、补充消息、文件交付和恢复，按上表核对；欢迎区按需后续适配。
- **P3**：普通子 Agent 进度卡片（SubagentCard）、namespace 关联、取消状态反馈与用量展示。
- **P4 ~ P6**：技能（Skills）只读与管理面板、记忆（Memory）管理面板、多媒体/PPT/长任务状态跟踪。
- **P7**：生产级全链路验收、多租户/项目权限隔离、异常断线与主题/移动端无死角覆盖。

## 质量与架构红线

1. **绝对隔离**：`modules/dear-agent/` 与 `modules/chat/` 之间严禁双向 `import`。
2. **基础设施共用**：通用鉴权、Token 管理、API 类型和 HTTP 请求走 `src/services/`，不得在专属模块内部自建 Axios 客户端。
3. **老功能零回归故障**：Dear Agent 落地后，原通用 Chat（`/workspace/projects/:projectId/chat`）的所有既有测试必须保持 100% 绿灯通过。
4. **验收必须覆盖**：
   - 浏览器刷新无缝恢复正在进行的会话与中断；
   - 重复点击与恢复操作幂等；
   - 跨租户/跨项目越权彻底阻断；
   - 澄清表单非法输入的局部错误定位与重填；
   - 输出产物真实文件内容哈希校验一致。
