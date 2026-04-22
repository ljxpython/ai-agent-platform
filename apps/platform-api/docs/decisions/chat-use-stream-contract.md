# Chat 使用 `@langchain/vue` 的接口约束

这份文档只服务一个目的：

> 当前端 chat 基座切到 `@langchain/vue/useStream` 后，`apps/platform-api` 的 `runtime_gateway` 必须保持哪些协议边界不变？

结论：

- 可以切，而且 `platform-api` 当前的 `/api/langgraph` 网关已经足够接入官方 `Client + useStream`。
- 但必须守住“LangGraph 原生语义尽量原样透传，平台只负责项目边界、权限、审计、认证头注入”的原则。
- 不允许为了局部页面方便，再把 runtime gateway 包成一层与 LangGraph 原生语义不兼容的私有协议。

## 1. 前端接入方式

前端 chat 会继续使用：

- `@langchain/langgraph-sdk`
- `@langchain/vue`
- `createLanggraphClient()`

接入路径保持：

- base url: `/api/langgraph`

必带头：

- `Authorization: Bearer <token>`
- `x-project-id: <project_id>`

这意味着 `runtime_gateway` 必须继续允许官方 `Client` 直接访问，不再要求前端先转成另一套平台私有 payload。

## 2. 必须保持兼容的接口

以下能力是 `@langchain/vue/useStream` 和官方 `Client` 直接依赖的：

- `POST /api/langgraph/threads`
- `GET /api/langgraph/threads/{thread_id}`
- `PATCH /api/langgraph/threads/{thread_id}`
- `DELETE /api/langgraph/threads/{thread_id}`
- `GET /api/langgraph/threads/{thread_id}/state`
- `POST /api/langgraph/threads/{thread_id}/state`
- `GET /api/langgraph/threads/{thread_id}/history`
- `POST /api/langgraph/threads/{thread_id}/history`
- `POST /api/langgraph/threads/{thread_id}/runs`
- `POST /api/langgraph/threads/{thread_id}/runs/stream`
- `GET /api/langgraph/threads/{thread_id}/runs/{run_id}`
- `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/join`
- `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/stream`
- `POST /api/langgraph/threads/{thread_id}/runs/{run_id}/cancel`

这些接口的语义应尽量与 LangGraph 原生保持一致：

- thread / run / checkpoint / branch 字段名称不要随意改名
- SSE event name 不要私自重写成平台自定义事件
- messages / values / tasks / custom / metadata 这些流事件不要被二次包装

## 3. 平台层允许做的增强

平台层可以继续做这些事：

- 校验 `x-project-id`
- 注入审计上下文
- 做权限校验
- 将上游 401/403/404/5xx 归一成平台错误口径
- 为 thread / assistant / graph 做项目作用域隔离

但不能做这些事：

- 改写 LangGraph 原生消息结构
- 把 stream 事件重写成另一种私有结构
- 去掉原生 branch / checkpoint / interrupt 元数据
- 让前端 chat 再额外调用一套“平台专属 stream 协议”

## 4. 前端仍然需要的非 stream 能力

即使 chat 内核切到 `useStream`，前端仍然会继续调用平台的辅助能力：

- thread 列表分页 / 搜索 / 状态筛选
- runtime model catalog
- runtime tool catalog
- assistant / graph 展示名补齐

这些属于平台工作台壳，不属于 `useStream` 的职责。

## 5. 关于停止运行

需要明确一点：

- `useStream.stop()` 只能视为“停止前端当前流订阅”
- 平台前端仍然应该保留一次显式 `runs.cancel()`

因此 `platform-api` 必须继续稳定提供：

- `POST /api/langgraph/threads/{thread_id}/runs/{run_id}/cancel`

不要因为前端切到 `@langchain/vue` 就把 cancel 语义偷掉。

## 6. 版本冻结要求

当前迁移要求前后端共同遵守下面的冻结口径：

1. `platform-web` 升级 `@langchain/langgraph-sdk` 时，`platform-api` 不得再输出旧版私有字段
2. runtime gateway 如需兼容差异，优先在 adapter 层做，而不是要求前端在 chat 里写双协议兼容分支
3. 如果未来继续升级 `@langchain/vue` / `@langchain/langgraph-sdk`，先做 smoke，再改 chat 基座

## 7. 最终标准

`platform-api` 对 chat 的标准支持方式已经冻结为：

- 路径标准：`/api/langgraph`
- 认证标准：`Authorization`
- 项目上下文标准：`x-project-id`
- 上游语义标准：尽量保持 LangGraph 原生 thread/run/stream 语义
- 平台职责标准：权限、审计、项目隔离、错误归一

这意味着后续前端 chat 基座可以继续沿着官方 `useStream` 演进，而不用再为平台私有协议反复返工。

## 8. Runtime Contract 冻结口径

当前 `platform-api` 对 runtime payload 的最终口径再补一条硬规则：

- `context`
  - 只承载运行时业务字段
  - 例如 `project_id`、`model_id`、`system_prompt`、`temperature`、`max_tokens`、`top_p`、`enable_tools`、`tools`
- `config`
  - 只承载执行控制字段
  - 例如 `recursion_limit`、`run_name`、`max_concurrency`
- `config.configurable`
  - 只承载线程 / 平台 / 私有字段
  - 例如 `thread_id`、`checkpoint_id`、`assistant_id`、`graph_id`、`langgraph_auth_*`

平台侧禁止再做这些旧写法：

- 把 `project_id` 注入到 run payload 的 `metadata`
- 把 `model_id / temperature / enable_tools / tools` 塞进 `config` 或 `config.configurable`
- 把 `user_id / tenant_id / role / permissions` 当成前端可写字段透传

对 thread 资源本身的项目隔离，仍然允许通过 thread metadata 记录 `project_id`，因为那属于平台线程作用域，不属于 runtime business contract。
