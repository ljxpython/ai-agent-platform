# Runtime Contract 手工联调清单

这份清单只服务当前这一轮 runtime contract 收口验收：

- 后端只看 `apps/platform-api`
- 前端只看 `apps/platform-web`
- graph runtime 只看 `apps/runtime-service`

目标不是“页面大概能点”，而是把下面几条硬规则做成可逐项验收的联调标准：

- `project_id` 只认 `context.project_id`
- runtime business fields 只进入 `context`
- `config` 只保留执行控制字段
- `config.configurable` 只保留线程 / 平台 / 私有字段
- assistant create / edit 与 chat submit 走同一套 runtime contract

## 1. 联调前置条件

- [ ] 已启动 `apps/runtime-service`
- [ ] 已启动 `apps/platform-api`
- [ ] 已启动 `apps/platform-web`
- [ ] 浏览器能正常登录 `platform-web`
- [ ] 当前账号至少有一个可访问项目
- [ ] 当前项目下至少存在一个可用 graph
- [ ] 浏览器 DevTools 已打开 `Network`
- [ ] Network 面板勾选 `Preserve log`
- [ ] Network 面板过滤关键请求：
  - `assistants`
  - `threads`
  - `runs`
  - `history`
  - `state`

推荐启动方式：

```bash
bash "./scripts/platform-web-demo-up.sh"
bash "./scripts/platform-web-demo-health.sh"
```

如果走本地前端开发模式，至少保证：

```bash
VITE_PLATFORM_API_URL=http://localhost:2142
VITE_PLATFORM_API_RUNTIME_ENABLED=true
```

## 2. 要盯的请求

联调时别只看页面，要盯住这几类请求。

### 2.1 assistant create / edit

- 创建：
  - `POST /api/projects/{project_id}/assistants`
- 编辑：
  - `PATCH /api/assistants/{assistant_id}`

必须重点确认：

- 请求体存在顶层 `context`
- `model_id`、`temperature`、`max_tokens`、`enable_tools`、`tools` 只出现在 `context`
- 顶层 `config` 里不再混入上面这些业务字段
- `config.configurable` 里不再混入上面这些业务字段

### 2.2 chat / debug / resume

- 新线程：
  - `POST /api/langgraph/threads`
  - `POST /api/langgraph/threads/{thread_id}/runs/stream`
- 老线程继续：
  - `POST /api/langgraph/threads/{thread_id}/runs/stream`
- 历史恢复：
  - `POST /api/langgraph/threads/{thread_id}/history`
  - `GET /api/langgraph/threads/{thread_id}/state`
- 取消运行：
  - `POST /api/langgraph/threads/{thread_id}/runs/{run_id}/cancel`

必须重点确认：

- `runs/stream` 请求里存在顶层 `context`
- `context` 中承载运行时业务字段
- `config` 只承载执行控制
- debug 模式只体现为 `interruptBefore`
- continue / resume 不会偷偷重新塞回旧 `config.configurable` 写法

## 3. 用例一：Assistant Create

页面入口：

- `/workspace/assistants/new`

执行步骤：

- [ ] 选择一个 graph
- [ ] 填写 assistant 名称
- [ ] 在运行参数区设置 `model_id`
- [ ] 打开工具开关，并至少选择一个工具
- [ ] 如页面支持，填写 `temperature` / `max_tokens`
- [ ] 点击创建

请求验收：

- [ ] `POST /api/projects/{project_id}/assistants` 返回 `200/201`
- [ ] 请求体顶层出现 `context`
- [ ] `context.model_id` 正确
- [ ] `context.enable_tools` 正确
- [ ] `context.tools` 正确
- [ ] `context.temperature` / `context.max_tokens` 如有填写则正确
- [ ] `config` 中没有 `model_id`
- [ ] `config` 中没有 `enable_tools`
- [ ] `config` 中没有 `tools`
- [ ] `config.configurable` 中没有 `model_id`
- [ ] `config.configurable` 中没有 `enable_tools`
- [ ] `config.configurable` 中没有 `tools`

页面验收：

- [ ] 创建成功后页面跳到 assistant 详情页或展示成功态
- [ ] 页面没有出现 schema / 参数回填错乱

## 4. 用例二：Assistant Edit

页面入口：

- `/workspace/assistants/:assistantId`

执行步骤：

- [ ] 打开一个刚创建好的 assistant
- [ ] 修改 `model_id`
- [ ] 修改工具开关或工具集合
- [ ] 修改 `temperature` 或 `max_tokens`
- [ ] 点击保存

请求验收：

- [ ] `PATCH /api/assistants/{assistant_id}` 返回 `200`
- [ ] 请求体顶层出现 `context`
- [ ] 业务字段只出现在 `context`
- [ ] `config` 与 `config.configurable` 未重新混入业务字段

页面验收：

- [ ] 保存后页面展示与返回数据一致
- [ ] 刷新页面后仍能正确回填当前值

## 5. 用例三：Chat 新线程发送

页面入口：

- `/workspace/chat`
- 或从 assistant 详情页点击“进入 Chat”

执行步骤：

- [ ] 选择刚才创建或更新过的 assistant
- [ ] 打开运行参数弹窗
- [ ] 设置 `model_id`
- [ ] 设置工具开关 / 工具集合
- [ ] 设置 `temperature` / `max_tokens`
- [ ] 发送第一条文本消息

请求验收：

- [ ] 先创建 thread：`POST /api/langgraph/threads`
- [ ] 再发起 run：`POST /api/langgraph/threads/{thread_id}/runs/stream`
- [ ] `runs/stream` 请求里存在顶层 `context`
- [ ] `context.model_id` 正确
- [ ] `context.enable_tools` 正确
- [ ] `context.tools` 正确
- [ ] `context.temperature` / `context.max_tokens` 正确
- [ ] `config` 中未混入上面这些业务字段
- [ ] `metadata` 只承担 thread 初始化信息，不承担运行参数

页面验收：

- [ ] 自动创建 thread
- [ ] 首条消息和回复都能正常出现
- [ ] 线程列表能看到新 thread

## 6. 用例四：Chat 老线程继续

页面入口：

- `/workspace/threads`
- `/workspace/chat`

执行步骤：

- [ ] 打开已有 thread
- [ ] 等待 `history` / `state` 请求完成
- [ ] 发送下一条消息

请求验收：

- [ ] `POST /api/langgraph/threads/{thread_id}/history` 成功
- [ ] `GET /api/langgraph/threads/{thread_id}/state` 成功
- [ ] 新一轮 `runs/stream` 仍带顶层 `context`
- [ ] 没有重新创建新 thread
- [ ] 同一线程继续运行

页面验收：

- [ ] 历史消息顺序正确
- [ ] 新消息追加到当前 thread
- [ ] 不会错误跳到新线程

## 7. 用例五：Debug Continue

页面入口：

- `/workspace/chat`

执行步骤：

- [ ] 在运行参数里打开 `Debug Mode`
- [ ] 发送一条会经过工具或节点的消息
- [ ] 等待运行进入可继续状态
- [ ] 点击继续运行

请求验收：

- [ ] 首次 `runs/stream` 带 `interruptBefore: ['tools']`
- [ ] Continue 时仍走 `POST /api/langgraph/threads/{thread_id}/runs/stream`
- [ ] Continue 请求不把业务字段塞回 `config.configurable`
- [ ] Continue 请求继续携带当前 `context`

页面验收：

- [ ] 页面出现清晰的 debug / interrupt 状态
- [ ] 点击继续后运行恢复
- [ ] 运行恢复后页面没有卡死

## 8. 用例六：Cancel Run

页面入口：

- `/workspace/chat`

执行步骤：

- [ ] 发送一条足够长、能稳定跑几秒的消息
- [ ] 在回复过程中点击取消

请求验收：

- [ ] 触发 `POST /api/langgraph/threads/{thread_id}/runs/{run_id}/cancel`
- [ ] 请求返回 `200/204`

页面验收：

- [ ] 当前流式输出停止
- [ ] 输入框恢复可用
- [ ] 页面不白屏
- [ ] 后续还能继续发送下一条消息

## 9. 可选用例：Resume Interrupt

这个用例只有在目标 graph / agent 明确支持 HITL interrupt 时才做。

执行步骤：

- [ ] 发送一条能触发 HITL interrupt 的消息
- [ ] 页面出现 interrupt 面板
- [ ] 在面板中选择动作并提交

请求验收：

- [ ] 继续走 `POST /api/langgraph/threads/{thread_id}/runs/stream`
- [ ] 请求带 `command.resume`
- [ ] 业务字段仍走 `context`

页面验收：

- [ ] interrupt 面板可操作
- [ ] resume 后运行继续
- [ ] 不会出现“页面恢复了但服务端还卡住”的假恢复

## 10. 失败时先查哪里

### 10.1 请求体结构错了

优先看前端：

- `apps/platform-web/src/services/runtime/runtime-contract.ts`
- `apps/platform-web/src/services/assistants/assistants.service.ts`
- `apps/platform-web/src/modules/chat/composables/platform-chat-stream/actions.ts`

典型症状：

- 业务字段掉进了 `config`
- 业务字段掉进了 `config.configurable`
- `context` 丢失

### 10.2 前端请求体对了，但后端收到后变形

优先看后端：

- `apps/platform-api/app/core/runtime_contract.py`
- `apps/platform-api/app/modules/assistants/application/service.py`
- `apps/platform-api/app/modules/runtime_gateway/application/service.py`
- `apps/platform-api/app/adapters/langgraph/parameter_schema.py`

典型症状：

- 前端发的是对的，后端转发 upstream 后又被改坏
- parameter schema 仍在暗示旧写法

### 10.3 contract 对了，但 graph 行为异常

优先看 runtime：

- `apps/runtime-service/runtime_service/agents/assistant_agent/graph.py`
- 目标 service 的 graph / middleware / tool registry

典型症状：

- 请求体结构正确，但模型、工具或中断行为不符合预期
- debug / resume / cancel 行为和 contract 无关，而是 graph 自身实现问题

## 11. 联调结论记录

每轮联调结束后，按下面格式记结果：

- Assistant Create：通过 / 不通过
- Assistant Edit：通过 / 不通过
- Chat 新线程发送：通过 / 不通过
- Chat 老线程继续：通过 / 不通过
- Debug Continue：通过 / 不通过
- Cancel Run：通过 / 不通过
- Resume Interrupt：通过 / 不通过 / 不适用

最终结论：

- [ ] Runtime Contract 联调通过
- [ ] 还存在前端 contract 问题
- [ ] 还存在后端 normalize / schema 问题
- [ ] 还存在 runtime graph 行为问题
