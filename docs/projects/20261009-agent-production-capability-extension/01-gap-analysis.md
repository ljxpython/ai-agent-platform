# open-swe 与当前项目的代码对照

## 阅读基线与证据限制

本次阅读日期为 2026-10-09，比较对象是用户指定的本地参考 checkout；以下参考路径相对于各仓库根目录。

| 对象 | 基线 | 证据边界 |
| --- | --- | --- |
| 本平台 | `85d63d87bdf84dabbb963f79e8dd4b2db4432ade` | 本轮只增加规划文档，业务代码未改 |
| open-swe | `ad417d64d91cc349d63d832c7b643637dc1774cf` | 阅读 dispatch/completion/model_errors/webhook tests，没有运行它的部署或测试 |
| GraphHarbor | `f9bb32ed123110cb07d18cf9c5b76a7895c7b33e` + 未提交改动 | 初始只读参考；正式 post44 已独立从 PyPI 冷安装，工作树仍不能替代正式产物 |
| 当前依赖锁 | `apps/runtime-service/pyproject.toml`、`uv.lock` 的 post44 | 已冷安装并启动正式包 Worker；源码与正式包结果分开记录 |

已查询 LangChain 官方 MCP、OpenAPI 和 Python SDK reference，并只读核对 `langgraph-api 0.15.4` 的 webhook/HTTP/配置/Worker 实现及官方 inmem queue。原生 webhook、认证头、URL 策略、顶层字段白名单和 HTTP 重试属于 GraphHarbor 可实现的 Server 边界；Outbox/HMAC/严格 ACK 是本期增强，不能宣称上游保证。完整证据见 [官方边界核对](07-langgraph-server-boundary.md)。默认 kwargs/values/metadata/error 不能整份保存或公开；LangSmith automation、Engine 或 Fleet 通知也不能用来证明 Run webhook 的语义。

## open-swe 实际怎样做

| 环节 | 文件 / 函数 | 实际设计 | 借鉴与限制 |
| --- | --- | --- | --- |
| 启动 | `agent/dispatch.py::create_durable_run` | sync durability、v3/resumable；地址与 secret 可用时注入 webhook | 借鉴统一受管启动，不把 callback URL 交给浏览器 |
| 地址 | `_resolve_completion_webhook_url` | 无 secret、相对地址、loopback 等条件下不启用；token 放 query | 借鉴显式禁用/可达性检查；生产身份改为正文签名 |
| 入口 | `agent/api/health.py` 的 `POST /webhooks/run-complete` | 验 token 后调用 completion handler | 自定义 app 路由能接收，不等于发送端可靠 |
| 校验 | `agent/completion.py::verify_run_complete_token` | `hmac.compare_digest(token, secret)` | 常量时间比较静态 bearer token；不是 HMAC 请求签名，正文和时间没有被绑定 |
| 分类 | `agent/middleware/model_errors.py::_record_model_error` | 模型调用现场分类后写 thread metadata | 借鉴现场提取安全分类；本平台不新增公开 `last_model_error` |
| 归因 | `completion.py::_failure_reason_code` | 校验异常类型与 run_id，避免上次模型错误串到本次失败 | 保留 Run 级、最终失败级归因；不能拿最新 Thread.error 推历史 Run |
| 通知 | `handle_run_completion`、`_post_failure_reply` | error/timeout 给 Slack/Linear/GitHub 发消息；interrupted 忽略；success 另做业务处理 | 只借鉴终态与业务展示分离；渠道、成本/feedback/review 逻辑不迁移 |
| 去重 | completion 中的 notification metadata 检查/更新 | thread metadata 保存最多 20 个 run ID；先读、发送、再写 | 并发与发送后 crash 会重复，ID 淘汰后也可能重复；本平台用事务和唯一键 |
| 失败响应 | `handle_run_completion` + webhook route | 部分异常结果是 `{"status":"error"}`，route 仍可能返回 HTTP 200 | 发送方可能误认成功；本平台只有持久提交后 ACK，临时失败返回 503 |
| 安全网 | `agent/reconcile.py` | 扫描 stale pending 并 cancel | 借鉴可恢复和兜底；终态仍由执行引擎裁决，不由业务通知函数裁决 |

`tests/webhooks/test_completion_webhook.py` 可参考合法/非法 token、状态分支和重复处理，但不替代本平台并发事务、多 Worker、断电恢复和 ACL 验证。

## 当前已经具备什么

| 能力 | 当前文件 / 函数 | 本期处理 |
| --- | --- | --- |
| 在线失败与超时反馈 | Web `modules/chat/composables/useChatSession.ts`、`ChatAgentStatusBar.vue` | 复用。不能宣称“所有失败都静默” |
| 模型错误分类 | Runtime `observability/errors.py::classify_exception/model_error_fields` | 复用现有 9 个分类；只补可靠终态的安全出口 |
| 模型失败记录 | `middlewares/model_errors.py::ModelErrorMiddleware._record` | 当前是安全日志/Langfuse，不是通知持久存储 |
| 模型恢复与有界重试 | `middlewares/model_resilience.py::awrap_model_call`、`middlewares/retry.py::RuntimeModelRetryMiddleware._raise` | 保留单一负责人；最终异常的 code 进入安全投影 |
| 预算/超时/准备/Workspace | `execution_budget.py`、`timeout_wrapup.py`、`run_prepare.py`、`runtime/errors.py` | 复用稳定码；不重新实现这些专项 |
| Tool message 修复 | `middlewares/runtime_config.py::sanitize_tool_call_messages/repair_model_tool_calls` | 已有 invalid/duplicate/orphan 修复；与本期无关，不追加专项任务 |
| 诊断和用量 | `observability/query.py::query_run_diagnostics`、usage ledger | Langfuse disabled/延迟时不能成为 completion 事实源；usage 不与通知事务耦合 |
| 图回调 | `observability/langfuse.py::_RuntimeDiagnosticsCallback` | `runtime.graph.completed` 不代表 Worker 已提交终态，无法覆盖 kill/factory/reaper |
| 启动网关 | API `RuntimeGatewayService.launch_runtime_run` | create/stream/Protocol/resume 等共享入口，已有 sync/v3/resumable |
| 接口适配 | `adapters/langgraph/runs_sdk_adapter.py`、`_promote_protocol_run_start` | 当前能透传 webhook，不证明生产引擎发回调；收紧输入需要兼容评审 |
| 提交记录 | `runtime_gateway/infra/sqlalchemy/models.py::RunRequestRecord` | 只做提交幂等/审计，run_id 写入可能晚于回调 |
| 定时任务 | API `scheduled_tasks/service.py::_payload/authorize_execution`；Runtime `runtime/scheduled.py::scheduled_execution` | 原生 cron 可创建新 thread，无 run_requests；现有 report 是 best-effort |
| 公告 | API `modules/announcements`、Web `AnnouncementCenter.vue` | 公告面向 global/project，不能承载用户私有 Run 失败；仅复用 UI primitives |
| 引擎终态 | GraphHarbor `run_store.py::finish/fail/record_event/requeue_expired` | 有持久终态与 UUID event_id，是可靠通知的基底 |
| 引擎 webhook | `queue.py::_dispatch_webhook` 与 `production_worker.py::ProductionWorker.run_once` | 旧内存任务路径存在；当前读到的生产路径无 durable delivery，须配套验证/实现 |

## 同事建议的逐项判断

| 建议 | 判断 | 本项目调整 |
| --- | --- | --- |
| 高优先级补 run completion | 采纳 | 解决持久化和跨会话发现，优先 error/timeout |
| 已有失败完全无通知 | 部分纠正 | 在线反馈已有；断连、后台、未打开会话与服务故障后的可靠通知不足 |
| 加 `ModelErrorMiddleware` 才能做 | 纠正 | 已有 middleware；所有图的基础终态不能依赖各 Agent 装配它 |
| 读 `last_model_error` | 不照搬 | 消费已提交终态中的安全码；临时失败恢复成功时不通知 |
| `{status, thread_id, run_id, error_type}` 就够 | 不足 | 还需 stable event_id、可信来源、status/reason、时间、sequence、幂等摘要与 sender 身份 |
| “HMAC 共享密钥”与示例等价 | 纠正 | 示例是静态 token；本项目签名绑定 raw body、timestamp、key ID、method/path |
| Runtime 或 API 任意放 handler | 需要分工 | API 收件/授权/产品投影；Runtime 安全归因；Engine 原子终态和投递 |
| SSE 通知用户 | 部分采纳 | 现有 SSE 继续在线反馈；本期另补当前用户受保护 feed，浏览器关闭时下次登录补看 |

## 真实差距与范围

| 差距 | 必需补齐 | 不应扩张 |
| --- | --- | --- |
| 终态发送不耐重启 | Engine Outbox、lease、重试、死信/恢复、原子提交 | 不另造 Agent 调度器 |
| 安全原因缺通用持久出口 | Runtime 纯投影；最终模型失败可附安全分类 | 不把原始异常重新串回异常链/Thread metadata |
| 提交关联存在竞态/cron 缺口 | API 先持久来源引用；Runtime 受验签来源；Engine 原样保留 opaque reference | 不信任浏览器 metadata/credential、不靠 run_requests 单表 |
| API 无私有 completion/feed | 幂等收件、当前 ACL、历史摘要、私有 feed/已读 | 不把公告广播当通知，不加渠道总线 |
| 前端跨会话不可见 | 同事实现项目内失败 feed 与历史摘要 | 不新建 Run 状态机，不新增成功 toast |

本项目只规划“运行完成通知与失败回调”。其他工程能力的对比用于识别已有实现，不能变成重做 middleware/tool/上下文系统的任务。职责、替代方案和发布约束见 [整体方案](plan.md)。
