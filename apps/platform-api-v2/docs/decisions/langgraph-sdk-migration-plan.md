# LangGraph SDK 迁移评估与执行清单

这份文档只回答一个问题：

> `apps/platform-api-v2` 里的 `runtime_gateway + assistants adapter`，要不要从“自写 HTTP adapter”切回“官方 Python SDK adapter”？

结论先说：

- `platform-api-v2` 的模块边界、权限模型、审计归类、项目作用域控制，这些方向是对的，不能回退。
- 但 `assistants / graphs / threads / runs / crons / history / state` 这类 LangGraph 原生能力，不该继续自己手写 `httpx` adapter。
- 推荐做法是：
  - `platform-api-v2` 继续保持“模块化单体 + 平台治理层”；
  - LangGraph 上游访问改为“优先 SDK，少量 HTTP 保底”；
  - 只保留极少数 SDK 没覆盖、或需要原始 passthrough 的 HTTP 调用。

## 0. 当前进度

第一刀已经落地：

- [x] `apps/platform-api-v2` 已补 `langgraph-sdk` 依赖
- [x] `assistants adapter` 已切到官方 SDK
- [x] `runtime_gateway` 已引入 hybrid upstream
- [x] `graphs + threads` 已从自写 HTTP 改成 SDK 调用
- [x] `runs + crons` 已从自写 HTTP 改成 SDK 调用
- [ ] `info` 继续保留 HTTP

当前验证状态：

- [x] 已补最小自动化测试：
  - `threads.count` 返回形状兼容
  - `runs.stream / join_stream` SSE 编码
  - `runs.cancel_many` ack 语义
  - `crons.count` 返回形状兼容
  - route 层 `cancel` ack 归一化
- [x] 已完成真实 smoke：
  - 登录 `platform-api-v2`
  - 创建项目
  - 创建 assistant（`graph_id=assistant`）
  - 创建 thread
  - 执行 `/threads/{thread_id}/runs/stream`
  - 获取 `/threads/{thread_id}/runs`
  - 获取 `/threads/{thread_id}/runs/{run_id}/join`
  - 执行 `threads/count`
  - 执行 `crons create/search/count/delete`

## 1. 为什么要改

当前 `platform-api-v2` 的问题，不在模块拆分，而在上游接入层重复造轮子：

- 旧 `platform-api` 已经有一套比较成熟的 `langgraph_sdk` 接入方式。
- `platform-api-v2` 又重新写了一套 `httpx` 代理：
  - `app/adapters/langgraph/runtime_client.py`
  - `app/adapters/langgraph/assistants_client.py`
- 这会带来 4 个直接问题：
  - 上游字段支持要手动补，容易漏；
  - 错误语义、流式语义要自己兜，升级成本高；
  - SDK 已有能力又手写一遍，维护价值很低；
  - 后续 LangGraph 能力扩展时，v2 很容易跟不上。

一句话：平台侧应该自己管“权限、审计、项目边界、聚合视图”，不该自己维护一整套 LangGraph 原生 client。

## 2. 当前架构判断

### 2.1 应该保留的部分

- `runtime_gateway` 作为平台运行时网关模块，保留。
- `assistants` 作为平台级 assistant 聚合与项目映射模块，保留。
- `project_id` 注入、thread project scope 校验、assistant project ownership 校验，保留。
- 审计动作、权限码、模块边界、Repository/UoW 结构，保留。

### 2.2 应该替换的部分

- 把 `LangGraphRuntimeClient` 的大部分 JSON/SSE 调用换成 SDK adapter。
- 把 `LangGraphAssistantsClient` 换成 SDK adapter。
- 保留一个极小的 HTTP fallback adapter，只处理 SDK 没暴露的上游能力。

### 2.3 目标形态

建议收敛成下面这层：

1. `presentation/http.py`
   - 负责 HTTP 入参、SSE 输出、ack 归一化
2. `application/service.py`
   - 负责权限、项目边界、注入 project scope、平台语义编排
3. `application/ports.py`
   - 定义 `RuntimeGatewayUpstreamProtocol` / `AssistantsUpstreamProtocol`
4. `adapters/langgraph/sdk_*.py`
   - 用官方 `langgraph_sdk` 实现原生能力
5. `adapters/langgraph/http_fallback.py`
   - 只保留 `info` 或未来 SDK 缺口项

## 3. Endpoint 迁移矩阵

这里说的“改 SDK / 保留 HTTP”，指的是 `platform-api-v2` 内部调用 LangGraph 上游的方式，不是对外 platform endpoint 要改路径。

### 3.1 `runtime_gateway`：改成 SDK 的 endpoint

以下 endpoint 都有明确的旧版 SDK 对应能力，应该切到 SDK adapter：

| Platform endpoint | 目标 | 原因 |
| --- | --- | --- |
| `POST /api/langgraph/graphs/search` | SDK | 旧版已有 `graphs.search` 封装 |
| `POST /api/langgraph/graphs/count` | SDK | 旧版已有 `graphs.count` 封装 |
| `POST /api/langgraph/threads` | SDK | 旧版已有 `threads.create` |
| `POST /api/langgraph/threads/search` | SDK | 旧版已有 `threads.search` |
| `POST /api/langgraph/threads/count` | SDK | 旧版已有 `threads.count` |
| `POST /api/langgraph/threads/prune` | SDK | 旧版已有 `threads.prune` |
| `GET /api/langgraph/threads/{thread_id}` | SDK | 旧版已有 `threads.get` |
| `PATCH /api/langgraph/threads/{thread_id}` | SDK | 旧版已有 `threads.update` |
| `DELETE /api/langgraph/threads/{thread_id}` | SDK | 旧版已有 `threads.delete` |
| `POST /api/langgraph/threads/{thread_id}/copy` | SDK | 旧版已有 `threads.copy` |
| `GET /api/langgraph/threads/{thread_id}/state` | SDK | 旧版已有 `threads.get_state` |
| `POST /api/langgraph/threads/{thread_id}/state` | SDK | 旧版已有 `threads.update_state` |
| `GET /api/langgraph/threads/{thread_id}/state/{checkpoint_id}` | SDK | 旧版已有 checkpoint 读取 |
| `POST /api/langgraph/threads/{thread_id}/history` | SDK | 旧版已有 `threads.get_history` |
| `GET /api/langgraph/threads/{thread_id}/history` | SDK | 只是 query alias，仍可走 SDK |
| `POST /api/langgraph/runs` | SDK | 旧版已有 `runs.create(None, assistant_id, ...)` |
| `POST /api/langgraph/runs/stream` | SDK | 旧版已有 `runs.stream`，平台层只做 SSE 包装 |
| `POST /api/langgraph/runs/wait` | SDK | 旧版已有 `runs.wait` |
| `POST /api/langgraph/runs/batch` | SDK | 旧版已有 `runs.create_batch` |
| `POST /api/langgraph/runs/cancel` | SDK | 旧版已有 `runs.cancel_many` |
| `POST /api/langgraph/runs/crons` | SDK | 旧版已有 `crons.create` |
| `POST /api/langgraph/runs/crons/search` | SDK | 旧版已有 `crons.search` |
| `POST /api/langgraph/runs/crons/count` | SDK | 旧版已有 `crons.count` |
| `PATCH /api/langgraph/runs/crons/{cron_id}` | SDK | 旧版已有 `crons.update` |
| `DELETE /api/langgraph/runs/crons/{cron_id}` | SDK | 旧版已有 `crons.delete` |
| `GET /api/langgraph/threads/{thread_id}/runs` | SDK | 旧版已有 `runs.list` |
| `POST /api/langgraph/threads/{thread_id}/runs` | SDK | 旧版已有 `runs.create(thread_id, ...)` |
| `POST /api/langgraph/threads/{thread_id}/runs/stream` | SDK | 旧版已有 `runs.stream(thread_id, ...)` |
| `POST /api/langgraph/threads/{thread_id}/runs/wait` | SDK | 旧版已有 `runs.wait(thread_id, ...)` |
| `GET /api/langgraph/threads/{thread_id}/runs/{run_id}` | SDK | 旧版已有 `runs.get` |
| `DELETE /api/langgraph/threads/{thread_id}/runs/{run_id}` | SDK | 旧版已有 `runs.delete` |
| `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/join` | SDK | 旧版已有 `runs.join` |
| `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/stream` | SDK | 旧版已有 `runs.join_stream` |
| `POST /api/langgraph/threads/{thread_id}/runs/crons` | SDK | 旧版已有 `crons.create_for_thread` |
| `POST /api/langgraph/threads/{thread_id}/runs/{run_id}/cancel` | SDK | 旧版已有 `runs.cancel` |

### 3.2 `runtime_gateway`：继续保留 HTTP 的 endpoint

当前明确建议继续 HTTP 的，只有这一类：

| Platform endpoint | 目标 | 原因 |
| --- | --- | --- |
| `GET /api/langgraph/info` | HTTP | 旧版就是 HTTP 透传；SDK 没有稳定等价入口 |

补充判断：

- 不要为了“全部统一”硬把 `info` 包成一个假 SDK service。
- 这里更合理的做法，是保留一个很小的 `LangGraphInfoHttpAdapter`。
- 如果未来 LangGraph SDK 官方补齐 `info` 能力，再考虑切换。

### 3.3 `assistants` 模块：哪些平台 endpoint 要改成 SDK upstream

`assistants` 模块对外还是平台自己的 REST 接口，不改路径；这里只改内部 upstream adapter。

| Platform endpoint | 目标 | 原因 |
| --- | --- | --- |
| `POST /api/projects/{project_id}/assistants` | SDK | 对上游实际做 `assistants.create` |
| `PATCH /api/assistants/{assistant_id}` | SDK | 对上游实际做 `assistants.update` |
| `DELETE /api/assistants/{assistant_id}?delete_runtime=true` | SDK | 对上游实际做 `assistants.delete(delete_threads=...)` |
| `POST /api/assistants/{assistant_id}/resync` | SDK | 对上游实际做 `assistants.get` |

### 3.4 `assistants` 模块：继续保留本地/非 SDK 的 endpoint

以下 endpoint 不应该强行改成 LangGraph SDK：

| Platform endpoint | 目标 | 原因 |
| --- | --- | --- |
| `GET /api/projects/{project_id}/assistants` | 保持本地 DB 聚合 | 平台自己的主视图，不应依赖上游搜索 |
| `GET /api/assistants/{assistant_id}` | 保持本地 DB 聚合 | 返回的是平台聚合对象，不是上游原生 assistant |
| `DELETE /api/assistants/{assistant_id}?delete_runtime=false` | 保持本地 DB 删除 | 本来就不打上游 |
| `GET /api/graphs/{graph_id}/assistant-parameter-schema` | 保持本地 schema provider | 这是平台本地分析能力，不是 LangGraph upstream 能力 |

## 4. 迁移执行清单

### 4.1 先做的基础改造

1. 在 `apps/platform-api-v2/pyproject.toml` 增加 `langgraph-sdk` 依赖。
2. 新增 `app/adapters/langgraph/sdk_client.py`
   - 负责创建 request-scoped SDK client
   - 透传：
     - `authorization`
     - `x-tenant-id`
     - `x-project-id`
     - `x-request-id`
   - 兼容 `x-api-key`
3. 在 `runtime_gateway/application` 增加 upstream protocol。
4. 在 `app/adapters/langgraph/` 新增：
   - `runtime_sdk_adapter.py`
   - `assistants_sdk_adapter.py`
   - `info_http_adapter.py`

### 4.2 `runtime_gateway` 的改造顺序

推荐严格按这个顺序做：

1. 先接 `graphs + threads` 的 SDK adapter
   - 风险低
   - 容易验证项目边界
2. 再接 `runs + crons` 的 JSON 类接口
   - `create / wait / batch / cancel / list / get / delete / join`
3. 最后接所有 SSE 类接口
   - `runs/stream`
   - `thread runs/stream`
   - `join_stream`
4. 最后只保留 `info` 的 HTTP adapter

### 4.3 `assistants` 的改造顺序

1. 先把 `LangGraphAssistantsClient` 平替成 SDK adapter
2. 不改 `AssistantsService` 的平台业务逻辑
3. 只替换 upstream port 的具体实现
4. `list/get` 仍以本地聚合为主，不去动查询模型

### 4.4 迁移完成后的代码边界

- `service.py`
  - 仍然负责：
    - 权限
    - project scope
    - ownership 校验
    - 审计语义
- SDK adapter
  - 只负责：
    - 调官方 client
    - 上游参数映射
    - 异常转平台错误
- presentation
  - 只负责：
    - request/response
    - SSE 输出格式
    - ack fallback

## 5. 哪些测试必须补

当前 `platform-api-v2` 最大的问题之一，不是代码风格，而是这块几乎没有成体系自动化测试。SDK 化之前必须先列好测试面。

### 5.1 adapter contract tests

要补：

- `runtime_sdk_adapter`
  - `graphs.search/count`
  - `threads.create/search/count/prune/get/update/delete/copy`
  - `threads.get_state/update_state/get_history`
  - `runs.create/wait/create_batch/get/list/delete/join/cancel/cancel_many`
  - `crons.create/search/count/update/delete/create_for_thread`
- `assistants_sdk_adapter`
  - `create/get/update/delete`

重点验证：

- payload 白名单字段是否与旧方案一致
- query 参数是否正确透传
- `assistant_id` / `thread_id` / `cron_id` 映射是否正确

### 5.2 service boundary tests

要补：

- `project_id` 必须注入 `context.project_id`
- 顶层 `metadata.project_id` 允许作为检索 / 审计冗余
- `config.configurable` 不再承接业务 project scope
- `config.metadata.project_id` 不再作为主链注入口
- thread project scope 校验
- assistant ownership 校验
- thread graph id 回退允许逻辑
- `delete_runtime=false` 时不得访问 LangGraph upstream

### 5.3 stream 行为测试

要补：

- SDK stream 事件能被平台正确转成 SSE
- tuple event / dict event / string event 的编码一致性
- `join_stream` 的 `last_event_id` 透传
- `cancel_on_disconnect` / `stream_mode` 透传
- 上游中断时平台返回的状态码和 detail 可控

### 5.4 error mapping tests

要补：

- 上游超时 -> `504`
- 上游不可达 -> `502`
- 上游 4xx -> 平台保持可解释的错误映射
- 上游返回非 dict / 无效对象 -> `502`
- assistant 不属于项目 -> `403`
- thread 不属于项目 -> `403`
- project 不存在 -> `404`

### 5.5 parity smoke tests

要补一组“旧 HTTP adapter vs 新 SDK adapter”的对比烟测：

- 同一个 LangGraph dev 实例
- 同一个 assistant / thread / run
- 对比：
  - JSON 结构关键字段
  - SSE 是否能正常消费
  - 取消 / join / history / state 是否行为一致

这组测试的价值很大：

- 它不是为了长期保留双实现；
- 它是为了在切换前确认“行为没悄悄变”。

## 6. 风险和处理方式

### 6.1 最大风险

最大的风险不是 SDK 不好用，而是“切一半”：

- 一半 endpoint 走 SDK
- 一半 endpoint 还走散乱的 `httpx`
- 错误语义和流式语义变成两套

这会把后续维护彻底搞乱。

### 6.2 推荐处理方式

推荐策略：

1. 先引入 SDK adapter
2. 先让 `graphs + threads + assistants upstream` 切过去
3. 再切 `runs/crons`
4. 最后清掉大部分 `LangGraphRuntimeClient`
5. 只保留 `info_http_adapter`

### 6.3 不建议的做法

不建议：

- 继续给 `runtime_client.py` 一路打补丁
- 在 service 里同时混用 SDK 和裸 HTTP 细节
- 把 `Request` 一路穿透到 domain 层
- 为了兼容旧实现，把新 adapter 又包装成更复杂的“万能代理”

## 7. 最终结论

最终判断非常明确：

- `platform-api-v2/runtime_gateway + assistants adapter` 可以改成 SDK 版。
- 而且不是“可选优化”，而是下一阶段值得做的基础重构。
- 但要注意：
  - 改的是“LangGraph 上游适配层”
  - 不是推翻 `platform-api-v2` 的模块化单体结构
  - 也不是把平台侧职责再搬回旧 `platform-api`

一句话收口：

> 平台层继续做平台层该做的事；LangGraph 原生资源访问，尽量还给官方 SDK。
