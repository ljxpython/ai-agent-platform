# Operations 退役与最小请求记录

实施日期：2026-09-10。用户已批准全量退役与新数据库重建。

## 改动
- 删除 operations 模块、平台 Worker、Redis 队列、artifacts、前端页面/轮询/导航和部署进程。
- runtime_gateway 使用 run_requests：身份、项目、Thread、Agent、幂等键、输入摘要、非敏感 Context、Run ID 与审批父 Run。上游返回明确 4xx 记 rejected，网络结果未知记 unknown；同键重试转交 Server 原子幂等。
- 新动作不再按相同消息内容永久去重；所有提交显式 reject，由 GraphHarbor 裁决并发。
- 审批使用标准 command.resume ID 映射；沿用父 Context、重新授权，重试不覆盖原 Run ID。
- 统一 HTTP SSE 分帧/过滤，覆盖跨块 CRLF、多行 JSON 与 UTF-8；运行状态/终态不再回写平台。
- Graph 目录直接刷新；模型连接由平台管理，删除远端模型刷新。Runtime 提供认证工具目录，平台读取工具权限声明。
- Agent 合并单表并移除持久化部署 URL；20 表空库基线删除 Operations/heartbeat/runtime_runs/interrupts。
- 系统健康探针执行真实 SELECT 1，不依赖平台 Worker。
- Runtime 校验受信 Server 的 Assistant UUID 或 Graph ID，支持标准 graph alias 执行。

## 后端验收（2026-09-10）

执行人：Codex。按用户最新范围，本次验收后端；前端集中后置，影响与调整见 [05 前端交接](../05-frontend-handoff.md)。

### 已取得证据

- 真实平台 Showcase **通过**：登录 → 项目 → 远端 Graph/Tool 目录 → 模型配置 → Agent → Thread → Run → 工具审批 → 真实执行。使用正式索引安装的 GraphHarbor/Runtime `0.13.0.post25`、PostgreSQL、Redis 和真实模型。
- 审批期间停止并重启 Platform API、Runtime API 和 Runtime Worker，完整 messages 与 interrupt ID 一致；最终 Run `be82a636-2b26-4e7b-b452-3e08e36acbf6` 为 success。
- 同 key 复用同 Run、同 key 改输入返回 409、禁用 Agent 后审批拒绝、跨项目拒绝、Operations 路由 404 均通过。经过 edit_file/write_file/execute 审批后，独立 Docker 运行生成的回归检查通过，报表 **43.50**，退出码 **0**。
- SSE 读取 131427 字节；验收脚本检查公开 JSON/SSE 不出现内部模型引用或模型 API Key。此项不等于浏览器重连/实时 token 展示验收。
- [真实链路证据](../evidence/20260910-platform-showcase-post25.json)。脚本：`scripts/platform_showcase_acceptance.py`，只用隔离库与自己启动的进程，结束后关闭这些进程，不改现有开发库。
- PostgreSQL 最终静态基线：20 张业务表，重复 upgrade、downgrade 到 base、再次 upgrade 通过，ORM metadata 差异为空。另一个隔离库验证两个并发请求竞争同 key，取得同一个请求记录 ID。[基线证据](../evidence/20260910-platform-baseline-postgres.json)、[竞争证据](../evidence/20260910-run-requests-postgres.json)。这里的竞争证明数据库唯一记录，不单独证明上游工具副作用 exactly-once。
- Runtime 定向回归：**47 passed，3 deselected，137.09 秒**，覆盖 modeling、runtime middleware、Showcase（排除 e2e/integration）；没有把 deselected 计作通过。
- run_requests 11 项、网关 26 项此前已通过；最终后端全量 **131 项：128 通过、3 skipped，239.953 秒，无失败/错误**，包含上游错误内部字段过滤与模型引用签名边界。Ruff `--select F` 通过；全量严格 lint 仍存在历史规则问题，不声明全量 lint 通过。

### 联调中发现并修复

1. Graph ID 被 Server 解析成 Assistant UUID 后，Runtime 原 scope 校验误拒绝；现在同时匹配受信 Server 的 graph_id/assistant_id，其他 Graph 仍拒绝。
2. Runtime 工具目录缺失；在 Runtime 业务 webapp 提供认证目录，平台消费实际权限声明，删除平台内的 read_reference 权限硬编码。
3. 重启验收在服务 ready 前查询造成 502；脚本改为各自等待 ready。旧轮次失败不作为成功证据。
4. 模型短期引用可能在排队后失效；Runtime 使用时间戳与共享业务密钥签名兑换，过期引用仅允许当前受信 Runtime 使用。引用签名、项目和模型启用状态仍校验；错误签名/时间戳/项目及过期引用边界有契约测试。GraphHarbor 不承接该业务认证。
5. Protocol HTTP SSE 在返回流之前检查上游状态；跨块 CRLF/UTF-8 统一过滤。公开上游错误详情也复用内部字段过滤，保留普通消息文本。

### 判定与尚未覆盖的后端边界

| 范围 | 状态 | 说明 |
| --- | --- | --- |
| Operations/resync 主链路退役 | done | 后端模块/Worker/配置/路由移除，全量回归及真实 404 |
| run_requests 替换运行镜像 | done | DB 竞争、应用重试/审批测试、真实同 key 与冲突；执行状态仍由 Server 持有 |
| 最终旧表删除与新库基线 | done | 20 表，PostgreSQL 升降升与 ORM 一致 |
| 真实 Runtime 与 Showcase 后端主链路 | done | 三进程重启、审批、实际模型/工具、独立结果核验 |
| 全部字段收缩与服务结构整理 | partial | 模型历史同步字段、Agent config/context/metadata 仍在；没有宣称所有历史字段/包装均已删除 |
| 网关完整边界矩阵 | partial | SDK join-stream 的上游失败前置、超 TTL 的真实排队与凭据轮换、所有故障窗口/取消重发/成员与模型撤权组合尚未取得完整真实证据；非 Context 配置的恢复冻结范围也需复核 |
| 前端与浏览器 | deferred | 用户要求后续统一处理；已有前端改动不是完成验收 |
| 容器部署与 LangGraph Server 完整等价性 | deferred | 按此前约定另行验收；Showcase 的 Docker 工具真实执行已验收 |

不承诺文件副作用 exactly-once/回滚，也不把本次本地主链路验收等同于生产容量或全工程完成。上述 partial 后端项目不能因前端后置而自动视为完成。

### 最终复验

Platform 执行：PLATFORM_RUNTIME_INTEGRATION=0 .venv/bin/python -m unittest discover -s tests -p 'test*.py' -q。131 项，128 通过、3 跳过。测试集自带 Runtime integration 关闭；真实联调另由 scripts/platform_showcase_acceptance.py 执行。部分测试 fixture 的 JWT 短密钥触发警告，不是本次真实服务密钥配置。

Runtime 定向执行 modeling、runtime middleware 和 Showcase，排除 e2e/integration：47 通过、3 deselected。不是 Runtime 全量重跑。见 [验收汇总](../evidence/20260910-backend-acceptance.json)。

## 后续收尾

以上为 post25 阶段的历史验证。模型与 Agent 字段收缩、标准审批授权、SSE 前置失败及超 TTL/轮换复验的当前状态，统一见 [11 后端收尾](11-backend-closeout.md)。
