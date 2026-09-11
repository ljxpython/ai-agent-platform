# 03 后端契约与接入边界

## 目标

消费已重构后端的公开契约，消除旧字段和隐式兼容。明确 SDK 能力、平台公开接口和 Agent 业务能力的区别；不因前端需要某个面板就假定后端存在对应接口。

## 方案设计

### 1. ID 与领域名称

| 概念 | 前端使用 | 禁止混用 |
| --- | --- | --- |
| Agent 产品记录 | `agent.id` UUID，用于详情/PATCH 和 UI 选择 | 不能直接作为 Runs 的 assistant_id |
| 部署执行目标 | `agent.graph_id`，前端变量 `graphId` | SDK 字段 assistantId / wire assistant_id 只是标准协议名；不新增 agent_key 别名 |
| 模型记录 | 模型目录 `id` UUID | 不能传 model 名称、provider:model、旧 runtime_id |
| 模型策略 | `catalog_id/model_id` 都指模型记录 UUID | 策略保留 model_id 不代表目录也保留它 |
| Thread / Run / checkpoint | 原样使用相应接口 ID | 不用数组下标、Thread ID 或时间戳代替 Run ID |
| interrupt | 当前 state 中稳定 ID | 不是节点名称、动作名称或数组序号 |

已授权 Graph 自动成为项目 Agent，用户只选择 Agent，平台解析配置与 graph_id 后由 SDK 执行，详见 [08](08-visual-and-agent-alignment.md)。同一项目的 Agent/Graph 关系以服务端约束为准，不增加前端“多个别名映射执行图”的模型。Agent 被禁用、目录撤销、模型停用时，刷新并禁止新动作；后端在运行/恢复时再检查当前授权。

### 2. Agent 与目录契约

| 能力 | 方法与路径 | 输入/输出与 UI 行为 |
| --- | --- | --- |
| Agent 列表 | GET `/api/projects/{project_id}/agents` | 按有效 Graph 授权幂等补齐 Agent；使用 limit/offset/query/graph_id；项目为空不请求 |
| Agent 创建 | POST 同上 | 服务端保留接口；Web 不提供手工创建流程，由列表自动对齐取代 |
| Agent 详情 | GET `/api/agents/{id}` | 用记录 UUID 精确读取；不通过首屏模糊搜索还原详情 |
| Agent 更新 | PATCH `/api/agents/{id}` | 只发已编辑的 name/description/status/context；graph_id 不可改；active/disabled |
| Agent 删除 | DELETE `/api/agents/{id}` | 服务端保留接口；Web 移除删除动作，通过 Graph 授权及 Agent 启停控制可用性 |
| 参数 schema | GET `/api/graphs/{graph_id}/assistant-parameter-schema` | 读取 remote-v1 sections；部署不可用呈错误，无本地源码 fallback |
| Model 列表 | GET `/api/runtime/models` | `{count,models}`；每项 id/display_name/provider/base_url/protocol/model/enabled/credential_configured |
| Model 创建/更新 | POST `/api/runtime/models`；PATCH `/api/runtime/models/{model_id}` | provider/display_name/base_url/protocol/model/api_key/enabled；api_key 只写，未修改则省略 |
| Graph/Tool 目录 | GET `/api/runtime/graphs`、`/api/runtime/tools` | 真实目录快照；错误不变成空目录 |
| Graph/Tool 刷新 | POST `/api/runtime/graphs/refresh`、`/api/runtime/tools/refresh` | 等待 `{ok,count,last_synced_at}` 后重读列表；禁重复点击，不轮询 Operation |
| 项目模型/图/工具策略 | 现有 `services/runtime-policies/runtime-policies.service.ts` 对应接口 | 保留授权与默认值治理；模型选项 value 使用 UUID，不另造权限规则 |

Agent 的公开 context 白名单为 `model_id/temperature/max_tokens/top_p/tools`；只提交显式选择字段，`tools: []` 和省略 tools 语义不同，不能被 normalization 吞掉。Agent Context 清空如何用 `{}`/null 表达，按服务端更新测试固定；不让“省略”误变成“无法清空”。

**schema 必须按场景消费：** 当前 `GraphParameterSchemaProvider.build_schema()` 返回 `config` 和 `context` 两个 section，context 可编辑属性只有 model_id/temperature/max_tokens/top_p。Agent 表单只消费 context；Run 高级选项才消费 config.recursion_limit。不要把 config section 原样传给 Agent CRUD。tools 单独来自工具目录与项目授权的明确选择，不从任意 schema 字段推导权限。

未知/不支持的 schema 类型标记不可编辑并显示原因，不默默提交默认 JSON。不能写宿主绝对路径、系统 prompt、可信身份或 runtime_model_ref。

### 3. 认证、项目与错误

- 普通 REST 保留 Axios；SDK 需要原生 fetch，两者共享 token 获取、refresh 去重和退出清理，不强行用 Axios 读取 SSE。
- 请求携带平台认证；需要项目作用域的目录/schema/网关请求固定带 `x-project-id`。service 显式收 projectId，进行中的请求不重新读取另一项目的 store。
- SDK apiUrl 使用 `new URL('/api/langgraph', platformOrigin)` 形成绝对 URL，保留平台代理前缀；浏览器不访问 Runtime 内网地址。
- 用户/项目切换后旧请求、旧订阅失效；服务端始终做最终授权。平台角色与项目 `/access` 分开，前端不把 is_super_admin 当项目万能授权。
- 单次明确 401 可按现有 session 机制尝试刷新；仍失败则重新登录，动作不自动换 key。401/403/404 不能作为网络抖动盲重试。

| 结果 | 产品行为 |
| --- | --- |
| 400/422 | 展示字段或参数错误，保留草稿；不自动清空表单 |
| 401 | 认证恢复或登录；不自动重放旧输入/旧审批 |
| 403 | 明确无权限，刷新当前 access；停止相关读取和操作 |
| 404 | 清理该资源选择，显示已失效；不跳到另一会话假装恢复 |
| 409 | 显示 code 与可理解说明，核实运行/幂等状态；禁止自动换 key 绕过 |
| 超时/断网/部分 5xx | 动作结果未知，保留原 key/payload，先查 Run/state；显式重试同一动作 |
| SSE 断流 | 显示连接问题；不宣称任务取消或已完成 |

### 4. SDK 接入选择与实际限制

首选 **`@langchain/vue useStream` + 官方 HTTP Protocol transport**。保留官方 SDK，用户已允许升级最新稳定版本。不重新编写 SSE 分帧、token reducer、tool-call 拼装或 namespace 分发器。

原审查已查询 LangChain Docs/Reference MCP，并检查 Vue 1.0.29 / LangGraph SDK 1.9.28 本地 `.d.ts`。**以下为旧安装基线，升级后须逐项重查，不能据此认定新版仍有限制：**

- [Vue useStream](https://reference.langchain.com/javascript/langchain-vue/useStream)：返回 refs，提供 messages/toolCalls/values/interrupts 和发现映射。
- [恢复连接](https://docs.langchain.com/oss/javascript/langchain/frontend/join-rejoin)：保留 threadId，disconnect 与服务端 cancel 不同。
- [工具展示](https://docs.langchain.com/oss/javascript/langchain/frontend/tool-calling)：直接消费工具投影。
- 本地 `@langchain/vue/dist/selectors.d.ts` 支持 `useMessages/useToolCalls/useValues` 的 namespace 选择。
- 本地 `StreamSubmitOptions` **没有顶层 context 或每动作 headers 字段**；`streamMode/streamSubgraphs` 也不是此 Vue v2 submit 的正式选项。不能用一个含这些字段的变量绕过 TS 检查后假定生效。
- 本地 `forkFrom` 会变成 `config.configurable.checkpoint_id`；当前网关 config 白名单不接受它，不能直接沿用旧编辑重发路径。
- 本地 multitaskStrategy 类型虽然列出 reject/enqueue 等值，注释明确客户端只实现 rollback 行为；并发最终由后端 reject 裁决，前端必须自己禁止重复提交，不能只相信类型枚举。
- 本地 `stop()` 默认取消；`disconnect()` / `stop({cancel:false})` 才是只断开。

若升级后仍存在上述限制，采用以下限定接入路径；新版已有正式能力时优先用新版公开 API，删除不再需要的适配：

1. 普通发送走官方 `submit`；模型参数在**唯一 transport 边界**映射到目前被支持的 `config.configurable.platform_runtime`，其中 model_id 是 UUID。前端业务层仍使用 `RunContext`。
2. 当前后端 `_promote_protocol_run_start` 会把上述候选值提升为 context，因此该封装不是废弃契约；不在各页面重复生成它。
3. 审批使用 `respond/ respondAll` 时不附 config/metadata/update/goto；本期必须验证 SDK 实际生成的 command 不携带 namespace 或其他平台未允许字段。必要时只在平台 transport 边界做明确字段映射，不能改 SDK 私有状态。
4. 幂等头由 ChatSession 实例的 action snapshot 提供；不放在全局 fetch/defaultHeaders 中，不依赖 SDK 未支持的 per-submit headers。
5. 编辑重发优先使用已公开 **标准 Runs 的顶层 checkpoint_id 字段**，成功后通过同一个 SDK session 重新 hydrate/订阅。阶段 G1 必须用真实网关证明；如果标准路径实际不支持，形成明确后端缺口并阻止本项验收，不能降级为向当前末尾追加。

2026-09-10 使用 package registry 查询的最新稳定版为 **`@langchain/vue 1.0.35`、`@langchain/langgraph-sdk 1.10.2`**；两者声明的 `@langchain/core` peer 为 `^1.1.48`，Vue peer 为 `^3.0.0`。LangGraph SDK 的 react/react-dom peers 为 optional，Vue 工程不因此引入 React。

用户已授权升级；G1 实施时再次查询 registry，核对 Vue 包实际依赖及 core 去重，更新 package.json/lockfile，执行类型、构建及真实发送/审批/重连/子图/checkpoint/幂等测试。必要的小适配仅放 transport 边界，不保留两套执行引擎。当前安装 Vue 1.0.35 / SDK 1.10.2（2026-09-11 再查 registry 仍为最新）；实际网络门禁见 implementation/11-closeout.md。

### 5. Chat HTTP 边界

路径相对 `/api/langgraph`；20 条公开路由完整清单以网关标准为准。

| 场景 | 路径 | 关键约束 |
| --- | --- | --- |
| 创建 Thread | POST `/threads` | 新消息首次发送时创建；metadata.graph_id 指定执行图；项目由平台认证/作用域注入 |
| 会话列表 | POST `/threads/search`、`/threads/count` | 使用实际支持的过滤和分页；不能把当前页过滤结果当总量 |
| 已有 Thread | GET `/threads/{t}`、`/threads/{t}/state` | 当前状态用于 hydrate；直接 GET 判链接有效性 |
| 历史 | POST `/threads/{t}/history` | 按需分页；只读展示，不回灌 live |
| 标准创建/恢复 | POST `/threads/{t}/runs` | 新动作 Idempotency-Key；assistant_id=graph_id；标准 context；config 只公开 recursion_limit |
| Protocol 命令 | POST `/threads/{t}/commands` | id 为整数；run.start/input.respond；HTTP key 与 command.id 分离 |
| Protocol 订阅 | POST `/threads/{t}/stream/events` | SDK 负责 channels/namespaces/depth/since；与标准 stream_mode 参数不可混用 |
| 标准 Run 续接 | GET `/threads/{t}/runs/{r}/stream` | 使用允许的 stream_mode/last_event_id；cancel_on_disconnect=false |
| 核实状态/取消 | GET `/threads/{t}/runs/{r}`、GET `/threads/{t}/runs`、POST `/threads/{t}/runs/{r}/cancel` | cancel ACK 不是终态；当前 Run ID 必须明确 |

标准发送形状（占位符实施时换成真实 ID）：

```json
{
  "assistant_id": "showcase_demo",
  "input": {"messages": [{"role": "user", "content": "检查销售报表"}]},
  "context": {"model_id": "<模型记录UUID>", "temperature": 0.2},
  "config": {"recursion_limit": 25}
}
```

config.recursion_limit 范围 1–1000、缺省 25；真实 graph 可以有更严格限制。默认模型未显式改变时省略 override，让后端按项目→Agent→本次参数决议，不能默认选目录第一项覆盖 Agent 默认值。

多 interrupt 标准恢复只允许：

```json
{
  "assistant_id": "showcase_demo",
  "command": {
    "resume": {
      "<interrupt-A>": {"decisions": [{"type": "approve"}]},
      "<interrupt-B>": {"decisions": [{"type": "reject", "message": "保留现有文件"}]}
    }
  }
}
```

单个 interrupt 可能包含多个 action；decisions 数量/顺序必须对应该 interrupt 的 action_requests。当前平台恢复还按 interrupt 集合保证重复保护，换 HTTP key 不会合法化已处理审批。

### 6. 后端能力缺口与本期范围

| 能力 | 当前依据 | 本期处置 | 完整实现前置 |
| --- | --- | --- | --- |
| 运行中消息注入队列 | 当前 20 路由无 `/threads/{t}/messages`；新 Run 并发 reject | 新增 07 细化三服务扩展；部署验收前保留草稿/停止后发 | [07](07-message-queue-and-middleware.md) 的 Q0 引擎接点验证、消息接口/持久消费/回执及评审 |
| 实时子智能体 | SDK scoped projections；showcase 的 namespace 流测试 | 本期必须真实接通，不能只画 task 工具卡 | G1 验证部署流可携 namespace 和重连回放 |
| 完整文件目录/读取/下载 | Showcase 有 Docker Workspace，但平台无独立 workspace 文件公开 API | 从工具结果/state 展示“本次可见文件”，不声称实时完整文件系统 | 路径/项目/线程授权、目录分页、大小限制、二进制和下载契约 |
| Skills 清单浏览 | Showcase skills 资源与 read_file；无公开管理端点 | 展示本次可见技能读取；不硬编码部署全集 | 只读公开元数据和资源 API；不暴露宿主路径 |
| PTY/交互终端 | 平台无 websocket/PTY 公开路由 | 只展示工具命令输出和 exit_code | 会话授权、PTY 生命周期、背压、重连和输入审核契约 |
| 产物服务 | Operations artifacts 已退役 | 展示公开 tool artifact/消息附件；与退役产品无关 | 若需永久存储/下载，另定义授权、链接有效期和大小策略 |
| 精确全文件 diff | edit_file 输入常是片段 | 显示“拟修改片段”；工具成功后才标已执行 | 要全文件对比需服务端提供前后完整版本或可靠 patch |

全部能力设计与验收层级见 05；队列新增任务与工作量已在 07 单列，完整终端等其他后端缺口仍保留原范围边界。

### 7. 多端消息队列扩展

原本只有后续约束、没有首期实现。本次已扩展为独立的 [07 多端消息入口、持久化队列与 Middleware 注入](07-message-queue-and-middleware.md)，作为消息入队/消费/回执的唯一设计事实源，包含拟新增接口、Runtime 根消费者、存储及引擎门禁、并发/崩溃/终态/审批边界、三服务任务和验证。

用户已要求该扩展最后完成，Q0—Q5 全部放在 G6 前端主体验收后，当前不预建队列接口/抽象。上线前不得请求未部署的接口。普通 Run 的 reject 保持有效，SDK enqueue、当前 Run 消息注入和 HITL resume 三种行为不混用。GraphHarbor 只修复通用引擎缺陷，业务队列与注入代码属于 Runtime；边界见 07 §3。

## 任务拆分

- [x] C1：新增 `services/agents/types.ts`、`agents.service.ts`，明确 CRUD 输入白名单，替换旧 aliases。
- [x] C2：收紧 `services/runtime` 模型类型与目录/策略消费，修复全部 ModelSelect 与 Agent 表单。
- [x] C3：统一 `services/langgraph/client.ts` 的绝对 URL、固定项目 fetch、认证错误，建立每动作幂等记录。
- [x] C4：升级并核对官方 SDK，完成发送、恢复、同名/嵌套 scoped 流、重连、checkpoint 分支及幂等验证；完整断线组合仍按 G6 记录。
- [x] C5：补充契约 fixture，从实际后端响应取公开字段；不继续用旧 Management 类型生成自洽但错误的 mock。

## 验证要求与记录

- [x] 新目录 fixture 不含旧 model_id/is_default，所有调用正常；API key 不返回、不存储。
- [x] Agent POST/PATCH 不含禁用字段，schema 分区使用正确；tools 空数组语义保留。
- [x] 检查实际请求的 project header、command 整数 ID、HTTP key 和 payload。
- [x] SDK 超集参数不穿透平台白名单；审批无 config/context/input/metadata/update/goto。
- [x] 标准 Runs 与 Protocol lifecycle 独立验证，不混淆 JSON 的 success 和事件的 completed。
- [x] SDK scoped selectors 已通过隔离 Runtime 的真实平台事件获取两个同名子图及嵌套消息；测试图不注册生产目录。

2026-09-10 规划阶段记录（非当前状态）：已核对后端 router/service/GraphParameterSchemaProvider、安装版 SDK 类型及官方 MCP 文档。未执行本专题新接入或真实浏览器验收。

## 状态

主要契约、SDK 升级及真实 scoped 子图链路已完成；完整 G6 断线组合仍由 06 统一验收。07 已获批准并实施，无待评审阻塞。

## 2026-09-11 任务对账

本次按当前代码及 [01 实现记录](implementation/01-contracts-and-session-foundation.md)、[09 消息验收](implementation/09-message-delivery-completion.md)、[10 发布验证](implementation/10-graphharbor-post27-release.md) 更新。任务勾选表示该任务范围已完成；下方/上方独立验收清单未勾项仍未完整验证，不能据此宣布整个阶段通过。本次仅核对文档与代码，未重跑业务测试。

证据：Agent CRUD 浏览器验证、目录/Agent 契约用例、`run-actions.test.ts` 和真实 `sdk-chain.test.ts`。post27 修复已发布，SDK 普通消息/终态兼容通过；这不替代最后一项复杂 scoped 子图事件验证。

### 编辑分支的实际兼容边界（2026-09-11）

GraphHarbor post27 Worker 读取顶层 `checkpoint_id`，当前不会把请求中的 `checkpoint` 对象用于执行。Web 从历史中核对 parent checkpoint 后，向标准 Runs 端点提交顶层 `checkpoint_id`，再用官方 SDK hydrate/订阅；只对根 Thread 暴露此动作，不声称子图 checkpoint 对象支持。此次未修改或新发布 GraphHarbor。

旧网络试验只确认原 checkpoint 可读取，不能排除新消息被追加到旧分支。新浏览器验收增加当前分支 human 数量为 1、旧审批消息不在新 state 中、原分支仍可读取的断言；移动真实模型链路已通过。此前使用 checkpoint 对象的版本不应作为可回退产物。
