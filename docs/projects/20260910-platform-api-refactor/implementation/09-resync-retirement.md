# Resync 退役与网关前置安全修正

日期：2026-09-10；状态：partial，整体 Operations 退役尚未完成。

## 已实现

- 删除 Agent resync HTTP 路由、应用方法、仓储同步状态方法与 AssistantSyncStatus。
- 删除 Agent 的 sync_status/last_sync_error/last_synced_at；同步静态空库基线。
- 删除 AssistantResyncExecutor、Worker 注册与 Operations 提交白名单项。
- 删除前端 Agent 列表/详情页的 resync 请求、按钮、同步状态卡片；最近同步改为最近更新。
- 删除无效果 delete_runtime/delete_threads API 参数及前端传参。
- 删除 /api/assistants 及项目下 assistants 的产品 HTTP 别名；前端已使用 /api/agents。
- 网关要求 Agent 当前存在且 active；不再通过历史 Thread metadata 放行已删除/禁用 Agent。

## 验证

- resync 切片后端全量：158 项，155 通过、3 外部 HTTP 集成跳过，0 失败，323.669 秒。
- 前端 vue-tsc 与四个修改页面/服务 ESLint 通过。
- 网关授权修正后 Runtime 契约测试：22 项通过。
- 新增退役路由断言；Agent 实库测试增加禁用 Agent 即使 Thread 保留原 Graph metadata 也拒绝执行。
- 删除的旧 test_operations_artifact_flow.py 专门验证已退役 resync Worker；Operation 批量归档测试改用仍注册的 Graph refresh。

## 网关退役前置缺口

已核对官方 [reject 语义](https://docs.langchain.com/langsmith/reject-concurrent)，并查询 RunsClient.create API。

GraphHarbor post24 的 RunRepository.create 只记录 multitask_strategy；本轮在 GraphHarbor 源码增加按 Thread 数据库行锁串行化提交、reject 活跃 Run 冲突、跨 Thread/Assistant 幂等键冲突检查；HTTP 转成 409。真实隔离 PostgreSQL 并发及 HTTP 测试 2 项通过。该修正已发布 graphharbor/graphharbor-runtime 0.13.0.post25；runtime-service 锁文件及安装验证见下方最终记录。

同幂等键不同 payload 的完整冲突语义、请求参数冻结、unknown 恢复、短期凭据续签与上游审批仍需验证。没有把修复 reject 当作完整运行契约验收。

## 剩余

Operations 其余 Worker/目录任务与运行协调依赖仍存在；run_requests、新网关、最终数据库表收缩、真实 Platform→Runtime 模型联调和 Showcase 尚未完成。当前保留旧协调器，避免在没有新运行链验证前直接移除并发与审批保护。

## 最终回归

网关授权修正后全量：158 项，155 通过、3 跳过、0 失败，324.853 秒。退役别名路由补测 1 项通过；编译检查和 diff whitespace 检查通过。

post25 官方 PyPI 依赖解析完成，uv.lock 与 uv sync --frozen 已同步 graphharbor/graphharbor-runtime 两包。未提交或推送本轮代码。
