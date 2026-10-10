# LangGraph Server 能力边界与 completion 实现核对

> 2026-10-09 官方资料与发布包只读核对。本文件保留上游能力边界；GraphHarbor post44 的本期实现与验证见 [引擎交接](03-engine-terminal-delivery.md) 和 [验证记录](verification.md)，不把平台业务策略倒灌到引擎。

## 结论

GraphHarbor 对标的是完整的 LangGraph Server，官方现在称为 LangSmith Agent Server。其职责包括 HTTP/SDK 协议、资源管理、持久化、队列、运行控制、通用鉴权和服务端扩展。Run completion webhook 属于 Server 能力，应在 GraphHarbor 的正式生产路径补齐，而不是要求每个 Agent 增加通知 Tool。

本平台的 Runtime Service 是部署在 Server 上的应用：注册图、装配模型和工具、提供应用认证与错误分类。Platform API 决定项目授权、收件用户和通知文案；Web 展示结果。Server 可以保存身份并执行应用提供的授权规则；不应硬编码本平台的角色、成员表、provider 分类或 Slack/GitHub/Linear 业务。

现有规划中的可靠 Outbox 可以由 GraphHarbor 实现，但不能说它是官方 webhook 已证实的内部设计。正文 HMAC、严格 ACK、可信 origin 和 terminal projector 同样是本项目待评审的增强，不是官方 webhook 的必需接入参数。

## 官方来源与版本

通过 `langchain-docs` MCP 的 search/filesystem 工具，以及 `langchain-reference` MCP 的 search/get_symbol 工具核对：

| 来源 | 本次确认内容 |
| --- | --- |
| [Agent Server](https://docs.langchain.com/langsmith/agent-server) | 部署组件、PG/Redis 分工、queue/lease、graph 加载和执行生命周期 |
| [Server 概览](https://docs.langchain.com/langsmith/agent-server-overview) | assistants/threads/runs/crons、鉴权、MCP/A2A 和扩展的公开边界 |
| [Run webhook](https://docs.langchain.com/langsmith/use-webhooks) | 完成后 POST、回调载荷、认证头、URL 限制与禁用 |
| [CLI 配置](https://docs.langchain.com/langsmith/cli) | `langgraph.json` 的 `webhooks` 和 `http.disable_webhooks` |
| [Server OpenAPI](https://docs.langchain.com/langsmith/server-api-ref) | MCP 挂载的 `agent-server-openapi.json`，核对 Run/Cron 请求及状态枚举 |
| [SDK RunsClient.create](https://reference.langchain.com/python/langgraph-sdk/_async/runs/RunsClient/create) | `webhook` 是可选 URL；SDK 的 `headers` 是发往 Server 的请求头，不能当成 callback 认证头 |
| [Auth](https://docs.langchain.com/langsmith/auth) | Server 的认证/资源授权扩展点、身份上下文与应用策略边界 |
| [Server changelog](https://docs.langchain.com/langsmith/agent-server-changelog) | v0.5.36 配置/headers，v0.7.11 载荷字段控制，v0.7.46 结构化 error |

为回答“如何实现”，另只读下载公开 PyPI wheel，不安装到本仓、不执行其代码：

| 官方产物 | SHA256 | 已读实现 |
| --- | --- | --- |
| [langgraph-api 0.15.4](https://pypi.org/project/langgraph-api/0.15.4/) | `23e8af464a652ee220ac97642f12ff909915cf6b901f0c3208e9e30202012436` | `langgraph_api/worker.py`、`webhook.py`、`http.py`、`config/schemas.py`、`config/__init__.py` |
| [langgraph-runtime-inmem 0.35.4](https://pypi.org/project/langgraph-runtime-inmem/0.35.4/) | `0109b40ce1df31c9226dfce5428c9483bf83ee8b61b02de564610f12410d344f` | `langgraph_runtime_inmem/queue.py` |

GraphHarbor 既有兼容 profile 以 `langgraph-api==0.13.0` 为局部基线。本次 0.15.4 调查不自动升级其兼容承诺，P1 须逐项冻结本能力对标版本。公开 PyPI `langgraph-runtime-postgres` 查询返回 404，未取得官方生产 PG queue 的实现；不可从 inmem 推断所有生产内部行为。

## Server 边界

| 能力 | 官方 Server 的职责 | 在本平台的归属 |
| --- | --- | --- |
| assistants / threads / runs / crons | CRUD、查询、配置版本、Run 关联、定时派发 | GraphHarbor；产品配置和授权由 API/Runtime 注入 |
| graph 加载和执行 | compiled graph/factory、注入 deployment checkpointer/store | GraphHarbor 执行；Runtime 提供图和模型/工具装配 |
| 持久化 | PG 核心资源、checkpoint、跨 Thread store；支持部分自定义后端 | GraphHarbor；本期不重建平台业务库 |
| durable queue / lease / retry | 入队、领取、同 Thread 并发约束、基础设施恢复、结束释放 slot | GraphHarbor；模型/provider 重试仍由 Runtime middleware 负责 |
| stream / join / cancel / HITL | SSE、重连、等待、取消、checkpoint interrupt/resume、multitask strategy | GraphHarbor 协议和生命周期；Web 消费，API 授权代理 |
| completion webhook | 完成后 POST、标准载荷、headers、URL 策略、HTTP 重试 | GraphHarbor 发送；API 本期接收并做通知 |
| authentication / resource authorization | 调用自定义 auth、传播身份、应用资源过滤 | GraphHarbor 扩展点；Runtime 校验 delegation；API 管理身份/项目政策 |
| custom app / middleware / lifespan | 服务启动、HTTP 扩展和中间件接线 | GraphHarbor 提供宿主能力；Runtime 按现有范式提供实现 |
| MCP / A2A / TTL / 缓存 / 加密 | 官方可配置的 Server 扩展能力 | 在 GraphHarbor 合理边界内，本专项仅记录，不新增开发任务 |
| 当前用户通知、已读、文案、第三方回复 | webhook 接收者或上层应用的业务 | Platform API + Web；不是 Server 的通用资源契约 |

官方架构：API 创建 PG pending Run，Redis 唤醒 Worker；Worker 从 PG claim/lease，执行图并写 checkpoint，通过 Redis pub/sub 向 SSE 输出；完成后更新状态并释放执行 slot。PG 是 Run 事实源，Redis 用于信号/流通信。`durability="sync"` 控制 checkpoint 写入，不代表 webhook 已持久送达。

这张表界定“可以放在哪里”，不是 GraphHarbor 全功能审计。当前支持情况须看其 capability/profile、正式包和相应测试，不能由“官方有”直接改成“本项目已有”。

## 官方 webhook 如何工作

### 请求与配置

OpenAPI 的 stateful/stateless Run Create、stream、wait 以及两类 Cron Create 均支持 `webhook`；stream 模型继承 Create 模型。Cron Patch 也支持修改该字段；batch 使用 Run Create 列表。准确资源路径是 `/threads/{thread_id}/...`，webhook 指南表格的 `/thread/...` 不能拿来实现路由。

SDK 只负责提交 URL。接收 `POST` 的 handler 必须由应用实现，不是 SDK 提供。应用可使用 Server 的 `http.app` 自定义路由，或本平台现有 API 服务；没有“必须 Runtime 自收再转发”的规定。

| 配置 | 实现位置 | 行为 |
| --- | --- | --- |
| `webhooks.headers` / `env_prefix` | `config/schemas.py::webhooks_validator` | 启动时解析 `${{ env.LG_WEBHOOK_TOKEN }}`；限制可引用 env 前缀，缺少变量拒绝启动 |
| `webhooks.url` | `webhook.py::validate_webhook_url_or_raise` | URL 长度、host/port allowlist、HTTPS、loopback/SSRF 检查；受理与发送时复查 |
| `webhooks.allowed_fields` | `WebhooksConfig` / `_filter_webhook_payload` | 顶层字段白名单；不支持只留 `error.error`、删除 `error.message` 这样的嵌套投影 |
| `http.disable_webhooks` | `webhook.py::call_webhook` | 停止发送，Run 仍执行；不是停用 Run route |

0.15.4 发布包确认支持 `allowed_fields`，但本次读取的 CLI main JSON schema 未列出它；规划先以发布包能力为证据，P1 核对目标 CLI 的校验/透传，不能宣称该配置一定可穿过任意版本 CLI。未设置或空白名单会发送完整载荷，`[]` 不能用作禁止发送。

### Worker 结果与载荷

`langgraph_api/worker.py::worker` 从 Run kwargs 读取 webhook，执行并产生 `WorkerResult(run, status, exception, checkpoint, run_started_at, run_ended_at, webhook)`：

- 已读分支区分成功、Worker hard timeout、用户 interrupt、rollback、可重试基础设施异常、最终错误。
- 可重试基础设施异常把 Run 置回 pending 后抛出，不能按这次 attempt 给用户发最终失败。
- `call_webhook` 合并 Run、最终 status、执行时间、`webhook_sent_at` 和 checkpoint values；异常经 `_serialize_exception` 进入结构化 `error`，通常含类型与 message。
- 默认 payload 可以含 input/config/metadata/values/error message。平台受管通知必须有自己的安全 profile，不能整份落平台通知库或返回浏览器。

Run 公共枚举仍是 `pending/running/error/success/timeout/interrupted`。已读 Worker 内部还有 `rollback` 结果分支，不能直接推导 webhook 与 REST Run enum 在所有路径完全一致；HITL、pending cancel、reaper、删除/rollback 的实际触发与载荷需差分验证。既有平台 DTO 不能凭这个内部值增加新的公开状态。

### 触发和发送

公开 inmem 实现的 `queue.py::queue` 在 task cleanup 中取正常 `WorkerResult`；有 webhook 时创建异步 callback task，用进程内 `WEBHOOKS` set 跟踪。`task.cancelled()` 或 task 本身抛出异常时跳过正常 result 回调；shutdown 会取消 WEBHOOKS tasks。这是已读 inmem 路径，不是官方 PG 生产后端的投递保证。

`langgraph_api/webhook.py::call_webhook` 调用 `http.py::http_request` 发送 POST。0.15.4 已读路径：

| 项目 | 真实实现 |
| --- | --- |
| 请求认证 | 指南建议 query token，也可配置静态 headers；此 sender 没有正文 HMAC 生成逻辑 |
| HTTP 重试 | Tenacity 最多 3 次调用，指数退避+jitter；timeout/network error、429、5xx 可重试 |
| 连接层 | webhook client 另设置 `retries=2`，底层连接尝试不能与上层 3 次混作总 HTTP 请求次数 |
| timeout | connect 5s、request/read 30s；不是每次请求整体固定 5s deadline |
| ACK | HTTP status 判断，关闭响应，不读取/校验 response body；HTTP 200 + `{"status":"error"}` 仍可能被当成功 |
| 最终失败 | `call_webhook` 捕获异常并记录日志；此函数没有持久重放/死信逻辑 |
| redirect | 使用 SSRF-safe client，`follow_redirects=True`、最多 5 次；不能声称官方默认“不跟随重定向” |

HTTPS 并非该版本默认强制；loopback 默认禁止，private IP 策略可配置。平台固定目标使用自己的 allowlist/HTTPS/CA/no-redirect 策略，不照搬默认值。以上参数来自本次具体发布包，不来自 LangSmith automation webhook 或 Engine/Fleet 业务通知。

## 与 GraphHarbor 的差距和代码落点

以下相对于 GraphHarbor 根目录，初始规划依据已读本地 checkout；post44 正式包验证已在实施记录中补充：

| 层 / 文件 | 当前证据 | 应补内容 |
| --- | --- | --- |
| `libs/langhost/src/langhost/cli.py::serve` | 把 `webhooks` 传给独立 `run_server`，且传入原始 config | 不能把 CLI 参数存在当成生效；补生产配置解析与校验契约 |
| `libs/langhost/src/langhost/server.py::run_server/create_app` | 自有宿主；已读生产路径没有 webhook config/loader 接线 | 统一 webhook 配置、启动校验、目标策略、能力报告 |
| `libs/langhost/src/langhost/core_api.py` Run/Cron create/patch | 已有标准资源与可信 principal 接入 | 原生 webhook 字段验证/保存，create/stream/wait/batch/cron 一致 |
| `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/queue.py::_dispatch_webhook` | 旧路径委托 `langgraph_api.webhook.call_webhook` | 不作为自有 production worker 已实现的证据；不把可选官方包变成生产依赖 |
| `.../production_worker.py::ProductionWorker.run_once` | 已读生产路径代码未发现 webhook result/dispatcher 接线 | 在真实终态收尾建立通用完成记录与投递接线，覆盖 factory/timeout/retry/cancel |
| `.../run_store.py::finish/fail/record_event/requeue_expired` | 已有持久终态、租约和 canonical event | 本期可靠增强在确认终态事务建 delivery，重试中不发；复用已停止规则 |
| `webhook_delivery.py` | post44 已实现 | 一套通用发送器；标准 Run payload 和平台受管安全 payload 用显式 profile 区分 |

## 兼容基线与生产增强

| 项目 | 官方依据 | 本期定位 |
| --- | --- | --- |
| Run/Cron webhook、POST、标准 payload | docs + OpenAPI + wheel | GraphHarbor 应实现的 Server 兼容基线 |
| 静态 headers、env 模板、URL 限制、disable、字段白名单 | docs/changelog + wheel | GraphHarbor 通用部署能力；平台选择最小安全配置 |
| HTTP 有界重试 | wheel `http.py` | 通用 sender 能力；兼容配置/参数按目标版本冻结 |
| API 幂等处理和站内 feed/read | SDK 不提供接收 handler，open-swe 自做业务处理 | Platform API/Web 负责 |
| terminal + Outbox 原子性、重启恢复、死信/重放 | 未在已读官方路径确认；生产 PG queue 未取得 | 为本期“不因重启丢失”的目标推荐的 GraphHarbor 增强，不能宣称上游保证 |
| HMAC/timestamp/key_id、严格 body ACK、no-redirect | 已读官方 sender 采用静态 headers/status ACK，redirect 行为不同 | post44 受管 profile 的安全/可靠策略；不强加给普通兼容 webhook |
| trusted callback context、origin_ref | 官方有 custom auth/可信身份上下文，无此命名的标准字段 | 优先复用既有私有 principal；本平台关联扩展，不硬编码项目政策 |
| terminal projector callable | 官方提供 app/auth/lifespan 等扩展，未查到此具体标准 hook | 先验证能否复用现有安全 code/event；不足时补最小通用 hook，由 Runtime 定义分类 |

推荐继续采用“一份 GraphHarbor delivery → API 幂等收件”，不用增加 Runtime 第二跳 relay/outbox。先补齐原生 webhook 契约，再在同一投递设施上提供本期可靠模式。标准 webhook 保留 SDK/REST 载荷；平台专用 `run.terminal` envelope 不冒充官方 Run，不静默替换标准字段。受管 Run 使用一个通知来源，避免两路重复业务通知。

## 验证与不确定项

P1/P2 须补两个层面的证据：

1. 官方兼容差分：冻结版本，Python/JS SDK 的 create/stream/wait/batch/cron/patch，payload/status、顶层字段白名单、headers、配置缺失、非法 URL、retry/ACK 行为逐项验证。官方有能力，不等于当前引擎已接通。
2. 本期生产验收：真实 PG、多 Worker、kill 在终态事务前后、网络/DB 故障、回调早于启动响应、cron fresh thread、HITL/取消确认、删除/rollback、重复投递和撤权，沿 [verification.md](verification.md) 执行。

本次没有取得官方 PG queue 全部实现，因此不能宣称上游 webhook 在 kill/reaper/所有删除路径上耐重启、至少一次或 exactly-once。GraphHarbor post44 自身的 PG/Worker/dispatcher 验证已完成；使用方正式三服务整链路受环境负载限制，保持 partial。
