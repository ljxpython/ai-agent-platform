# Dear Agent 个人记忆后端阶段实现

## 改动时间与范围

2026-09-24。对应 R01—R08、B01—B06 的本地后端与 Runtime 阶段；完成度以 [tasks.md](../tasks.md) 为准。本任务未改 platform-web 业务页面。

## Runtime

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py`：`MemoryCommand.valid_action_fields()` 按 action 拒绝无关字段；`MemoryStorage.change()` 在 scope 锁与事务中执行 CAS、去重、替换和容量控制，并返回本次事务的快照。此前保存后重新读取可能混入后续并发写入；现在响应与本次提交一致。重复设置和不变的编辑不增加 revision；替换后仍检查重复事实。`reserve_extraction_attempt()` 在 PG 内保留同 run 尝试次数，恢复执行不能再从零计数。
- `apps/runtime-service/src/runtime_service/http/dear_memory.py`、`runtime/auth.py`、`webapp.py`：新增无线程 GET/POST 与 `dear-memory-read/write` 委托，保留旧线程路由。公开投影剔除 `sources`、墓碑和内部提取字段；能力关闭时 GET 不查 PG。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory_access.py`、`agent.py`、`tools/memory.py`：通过带 HMAC 的 Platform ACL 回调复查线程是否仍为本人私有；新 run 装配、模型调用、工具执行与提取提交前检查，失败时关闭个人记忆。私有会话被分享后已生成的历史回答不能自动消除。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py`：主 run 最新用户消息的私有快照、结构化候选分类、两次尝试共用 180 秒预算、提取状态、数据库故障时召回降级。召回查询限制为存储允许的 500 字，授权错误不被吞成降级；恢复时依据私有队列 claim 排除队列消息。同 run 多条可信队列来源在[后续阶段](02-source-and-model.md)补齐。

## Platform API

- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`、`application/service.py`、`application/ports.py`、`adapters/langgraph/runtime_gateway_upstream.py`：新增 `/api/langgraph/dear/memory` GET/POST 与 Pydantic/OpenAPI 模型。沿用当前项目读/执行权限，owner 取真实认证用户；POST 流式限制 1.5 MB，敏感验证输入不回显。新路由不要求 Thread。
- `apps/platform-api/src/platform_api/core/security/tokens.py`、Runtime `runtime/auth.py`：双端同时加入新委托 operation，旧线程 operation 不可复用。
- `apps/platform-api/src/platform_api/modules/runtime_catalog/presentation/http.py`、`runtime_gateway/application/thread_access.py`：提供签名的当前 Thread ACL 判定；只允许未分享的本人私有 Thread 使用个人记忆。
- `apps/platform-api/src/platform_api/modules/audit/http_resolution.py`：用固定记忆 action 审计，不记录事实正文、引用或导入数组。`deploy/docker-compose.stack*.yml` 与 `scripts/local-stack.sh` 配置 Runtime 回调地址。

## 已新增或扩展的检查

Runtime：`test_memory_contract.py`、`test_memory_access.py`、`test_p6_governance.py`、`test_context.py` 及权限回归；Platform：`test_runtime_gateway_memory.py`、`test_runtime_gateway_memory_contract.py`、网关矩阵、adapter、审计及 Skills 回归。真实 HTTP→Runtime→隔离 PostgreSQL schema 用例覆盖无线程 CRUD、409、422 脱敏、413 和 Runtime 重启持久化；测试结束删除其临时 schema。最终本轮定向回归为 Runtime 68 passed、Platform 34 OK。

## 当前限制

此记录是第一阶段快照；多条可信队列来源、旧 JSON fixture、固定召回样本和独立真实模型已在[后续阶段](02-source-and-model.md)完成。运行中分享 SSE 竞态、完整平台 run、前端浏览器联验及联调环境仍待完成；无跨 run 自动补偿任务。
