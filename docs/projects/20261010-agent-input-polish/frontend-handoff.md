# F11 前端交接（给同事）

> 状态：暂缓（`deferred`），2026-10-10 用户已确认，本交接不安排实施。后端尚未实现；GET/POST、错误码和默认参数是未来备选契约，恢复开发前以获批方案及后端冻结 fixtures 核对。本轮没有前端源码改动。

## 交付目标

给**共享 ChatComposer**增加用户手动发起的纯文本“润色”动作。结果仅写回当前草稿；用户可以编辑、撤销，再自己发送。通用 Chat/Dear 入口共用一次实现，不复制 DeerFlow React 组件、状态或 CSS。

DeerFlow 值得借鉴的是取消、请求世代、条件回写及撤销，而不是 `input.length > 20` 或默认某个模型。按钮不表示 Agent 正在执行任务，不能使用 Run 进度/Stop 状态显示润色。

## 网络契约

必须使用 `platformHttpClient` 与 `x-project-id`，支持 AbortSignal。浏览器不接 Runtime 地址、JWT、模型连接或 Key。

```http
GET /api/langgraph/input-polish/config
x-project-id: <当前项目>
```

```json
{"enabled": false, "max_input_chars": 4000}
```

```http
POST /api/langgraph/input-polish
x-project-id: <当前项目>
Content-Type: application/json
```

```json
{
  "text": "原始草稿，不在前端自行裁切或清洗",
  "graph_id": "当前 graph key，如 showcase_demo",
  "thread_id": null,
  "model_id": null,
  "locale": "zh-CN"
}
```

```json
{"rewritten_text": "新的草稿", "changed": true}
```

注意 ID：`graph_id` 取 `ChatSession.props.graphId`；不能传 Agent 数据库 ID。`thread_id` 取已存在的 `session.threadId`，首条没有则省略/null，不能调用 ensureThread/createThread。`model_id` 取当前选中的 catalog ID，省略时服务器取 Agent/项目默认。`project_id` 不写 body，`context`/`config`/attachments/history/system prompt 也不传。

输入按 Unicode code points 限长，前端计算可用 `Array.from(text).length`，不用 JS `.length` 和 Python `len` 混计 emoji。原始 text 长度 1～配置上限且 trim 非空；长文本提示本动作不可用，不能截断后偷偷提交。普通消息发送不套润色长度上限。响应非空、≤6000、changed 为布尔，且与原始请求逐字差异一致；非法响应按动作失败处理，原文保持。

配置缓存与身份/项目关联，成功值短 TTL 刷新；失败不永久 memoize。配置未知/失败或 disabled 时隐藏润色入口，普通 Chat继续。沿现有权限快照显示，不把请求异常解释成全局撤权。

## UI 与入口条件

- 沿用 ChatComposer 工具区、现有 `BaseIcon`/tooltip/按钮样式。已有 `sparkle` 可用于润色；loading/取消/撤销用项目已装图标或已有组件，不新增图标库，不用 emoji 字符替代按钮。
- `enabled=true`、有可信项目和可执行 Agent时展示；非空且在字符限内、当前可执行、composer可交互且会话 idle 时允许发起。沿代码当前 `project.runtime.execute`（ChatPage的canWrite来自此项），已有Thread再结合comment ACL；不要单用资源修改权限`project.runtime.write`。现有权限规范差异见review G6。没有20字门槛。
- 运行中、队列未清、审批/澄清/计划待审、cancelling/stopping/stop_unconfirmed、只读/撤权时禁用发起，不能绕过已有锁定规则；timeout/error 终态只按当前可编辑/可发送规则处理。
- 模型/额度/运行错误等标签继续表达现有 Run，不新增“润色 Run”。润色失败局部 toast/短反馈，不占整屏。
- 正在润色时按钮显示 loading，并提供取消；文本仍可编辑。用户任何编辑使当前润色失效，取消等待；发送/queue 操作取消润色后仍沿原逻辑处理，不等待模型。
- 结果直接成为可编辑草稿，并显示“撤销润色”动作；不新建预览页/对话框、不自动发送、不改附件/模型/Plan Mode/AccessPolicy。
- changed=false 轻量提示“当前输入无需改写”；不创建 undo，不改输入光标/附件。含代码或思考标记的草稿 V1 原样保留同样属于正常无改写。
- loading/成功/失败不能改变工具按钮宽高或挤掉发送/停止；360/390/768/1440、多主题和focus/compact布局必须可用。
- 图标 `aria-label`/tooltip明确“润色”“取消润色”“撤销润色”；键盘可达，loading 用 `aria-busy`，结果反馈可用 `aria-live=polite`。不增加全局快捷键，保留 IME composition 行为。

## 代码接线

| 文件 | 同事要做的事 |
|---|---|
| 新 `src/modules/chat/input-polish/types.ts` | Request/Response/Config，复用已装 Zod 做接口边界校验 |
| 新 `src/modules/chat/input-polish/api.ts` | `loadInputPolishConfig(projectId, signal)`、`polishInputDraft(projectId, payload, signal)`；POST 不吞错误成默认值 |
| 新 `src/modules/chat/composables/useInputPolish.ts` | 局部状态与草稿动作；不要改官方 SDK controller 或 useChatSession 的 Run 状态 |
| `src/modules/chat/components/ChatSession.vue` | 捕获现有身份/project/graph/thread/model/draft/visible/权限与turn状态，仅提供数据及 `update:draft` 回写 |
| `src/modules/chat/components/ChatComposer.vue` | 工具图标/状态和事件；UI 不自己初始化模型或读全局 Agent配置 |
| 现有 `src/utils/http-error.ts`、`src/services/http/client.ts` | 直接复用，无需为 F11 重写认证/错误体系 |
| 新对应 spec、现有 ChatComposer/Session spec | 请求/状态/ABA/撤销/权限/附件/发送回归 |
| 新 `e2e/input-polish.spec.ts` | 真实三服务联合验收，证据放本 Worktree |

不要把联网、字符串规则、undo和十几个 watch 平铺在 ChatSession。新增 composable只管理草稿润色；API仍在module api；优先用 Composer 现有 toolbar插槽/小对象接入，控制新增 props，不改造既有所有 props。

## 状态、竞态与撤销

最小状态是 `loading`、一个 AbortController、请求 generation、草稿 revision、可选 `{originalText, rewrittenText, appliedRevision, scopeKey}`。不保存多级历史，不新增 localStorage草稿副本。

一次点击的流程：

1. 重新检查允许条件，捕获 originalText 和 `{身份, project, graph, thread或无Thread, model, draftRevision}`；generation递增，single-flight拒绝双击。
2. 发 POST。`draftRevision` 在每次外部文本编辑/替换时单调增加，不能仅用字符串相等判断。
3. 响应返回仅当 controller未abort、generation匹配、scope全相同、draftRevision未改变、页面可见且权限仍有效时应用。
4. 正常 changed=false 不覆盖原稿。changed=true 用现有 `update:draft` 写回并保存原始字符串与应用后的 revision；没有发送/入队/resume副作用。
5. undo仅在scope相同、当前文本仍等于结果、revision仍等于应用revision且未发送时可用；撤销恢复精确原串，包括首尾空白。后续输入、替换、发送或切scope使undo失效。

**ABA 必须测：** 用户在等待时 A→B→A，最终字符串又等于A也不能接收旧响应。撤销同理：结果 R→S→R 后旧undo已过期。revision处理程序性回写时记录实际应用revision，不能把自己的一次写回误判为用户编辑而立即删undo。

以下事件立即abort并递增generation：用户编辑、发普通消息、queue提交、清空、切Thread/Agent/project/账号/model、后台KeepAlive隐藏、document隐藏、unmount、真实撤权。切回前台不自动重试或补偿，用户可再次点击。不要复制 follow-up 的“后台补请求”逻辑到付费草稿操作。

取消与过期响应静默丢弃；`finally`只清理仍属于当前请求的loading/controller，不能让旧请求关掉新请求loading。后端不承诺 HTTP abort 已停止供应商计费。

## 错误处理

| 结果 | 前端动作 |
|---|---|
| changed=false | 原稿保持；无undo；局部轻提示 |
| 404 input_polish_disabled | 刷新/失效该配置，收起入口；不撤销登录或项目权限 |
| 400/422 | 显示边界提示，保留全文；不在客户端强截断 |
| 401 | 走统一client的认证刷新；不增加手动POST重试链 |
| 403 | 统一client通知当前scope复核；本动作不直接登出、不清草稿 |
| 502/503/504、网络/响应schema异常 | 局部“润色失败/超时”，保留原稿可发送；不自动重试 |
| abort或旧generation | 无toast、不写回；只清当前请求状态 |

错误 Envelope 为 `{error:{code,message,details},request_id}`；从 `extractPlatformHttpError` 取，不能读扁平 `response.data.code`。Provider auth错误不等于平台用户401。不得把草稿放URL、埋点、console或analytics错误附加上下文。

## 同事验收清单

- [ ] 请求项目头、graph/model/Thread ID正确；首条无Thread也可润色，不新增Thread。
- [ ] 短中文非空可用；全空白不可用；4000/4001字符与emoji边界匹配后端；普通发送不被4000限制。
- [ ] 成功只改草稿，附件/计划模式/访问策略不变，用户自己发送后才创建Run。
- [ ] 双击只发一个请求；取消、发送、切目标、切账号、后台、卸载后旧响应不落地。
- [ ] A→B→A及R→S→R阻止旧回写/undo；合法undo准确恢复原串。
- [ ] 模型失败/超时/关闭/响应异常不丢字、不触发全屏错误/登出；原文可发送。
- [ ] 运行中/queue/待审批/Stop/只读正确禁用；真实撤权与瞬态配置失败区分。
- [ ] IME、键盘、loading/取消/tooltip与多主题多视口通过；发送/停止按钮仍清晰可达。
- [ ] Vitest、lint、typecheck、build与原Composer/Session回归通过。
- [ ] 真实三服务E2E与后端共同核验零任务副作用、模型一次调用和关闭回退，留下证据。

同事只做前端；专属委托、无Thread授权、模型引用、Prompt、provider取消和费用门禁由后端/Runtime负责。前端交付完成之后仍需要联合 Final，不能提前把整个项目写done。
