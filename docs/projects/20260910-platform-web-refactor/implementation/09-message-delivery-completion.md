# 消息注入、回执恢复与端到端验收

日期：2026-09-11。关联 Q1—Q5。本记录接续 01、08，不把历史局部测试视作完整验收。

## 实现

| 位置（相对仓库根） | 改动与原因 |
| --- | --- |
| `apps/runtime-service/src/runtime_service/messaging/inbox.py` | `claim()` 自动回收目标 Run 的过期领取；保留稳定消息 ID、幂等键和序号。增加消费授权引用、条件拒绝、待处理 Run 查询及终态幂等查找；避免最近 100 条分页遗漏旧 pending |
| `apps/runtime-service/src/runtime_service/messaging/reconcile.py` | `reconcile_run()` 遍历目标 Run 已提交的根 checkpoint 历史，先确认消费再关闭终态剩余消息；不读 pending writes，不吞查询错误，不根据最新快照缺字段判定未消费 |
| `apps/runtime-service/src/runtime_service/middlewares/message_queue.py` | `abefore_model()` 复核当前权限后注入 HumanMessage；私有 Receipt 从每批覆盖改为同 Run 累积，跨 Run 重置；嵌套 namespace 不消费根队列 |
| `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py` | 根 Agent 挂载 Middleware，子 Agent 工厂不挂载；reference_agent 同样启用 |
| `apps/runtime-service/src/runtime_service/webapp.py` | 严格 Thread/graph scope、目标 Run 状态、内容类型和大小校验；GET 在 Run 终态先对账，再返回仅当前发送者回执；终态后允许原动作幂等确认 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | 校验目标 Run 属于 Thread，签发仅用于消息消费授权的短期引用；队列 graph 执行强制同步 checkpoint 持久化 |
| `apps/platform-api/src/platform_api/core/security/tokens.py` | 委托 operation 白名单增加 message-enqueue/message-read；真实 HTTP 验收发现旧白名单曾导致 503，已补签发测试 |
| `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py`、`presentation/http.py` | 新增内部消息消费授权回调，验证签名/用途/到期/Thread/Run，并复用当前用户、服务账户、项目成员与 graph 权限校验 |
| `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py` | state/SSE 递归移除私有 claim 与 authorization_ref，防止泄露内部授权引用 |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | 专用 queueMessage、GET hydration/终态/聚焦刷新、3 秒间隔且 30 秒截止的轮询；unknown 固定 payload/ID/key 重试，按用户/项目/Thread 保存到 sessionStorage；隐藏/卸载中止查询 |
| `apps/platform-web/src/modules/chat/components/ChatSession.vue` | 修复运行中排队按钮被普通发送 canSubmit 提前拦截；增加回执状态、刷新、unknown 重试和拒绝后恢复草稿；收到接收确认才清原草稿 |
| `apps/platform-web/src/modules/chat/pages/ChatPage.vue` | 停用 Agent 的已有 Thread 允许只读历史与回执，禁止发送；新会话仍拒绝停用目标，避免刷新后丢失拒绝回执入口 |

`consumed` 表示消息已进入持久上下文，不保证模型回答、工具副作用或外部事务完成。终态处理沿用已批准的惰性对账，不新增常驻平台 Worker。GraphHarbor 本轮无业务代码改动。

## 部署与回退

1. 在目标 Runtime 数据库备份后，使用 Runtime 环境显式执行 `python -m runtime_service.messaging`。增加 `authorization_ref` 列，不清空收件表，不依赖启动时静默迁移。
2. Runtime API 与 Worker 配置相同 `DATABASE_URI`；`RUNTIME_SELF_URL` 指向该 Runtime API，例如 `http://127.0.0.1:8123`。
3. Worker 配置 `PLATFORM_RUNTIME_MESSAGE_AUTH_URL=http://platform-api:2142/api/runtime/internal/message-authorization`，平台与 Runtime 委托密钥保持一致。授权回调不可用时保留 claim，等待过期恢复，不绕过授权注入。
4. 同时部署 Platform API 和 Web，先检查 GET/POST 回执及消费回调，再开放补充消息入口。
5. 回退时先关闭入口，保留 inbox/checkpoint；不得删除未消费记录。旧版不支持授权引用的 Middleware 不应继续领取本版本队列。

## 可复跑验证

- Runtime：`PYTHONPATH=apps/runtime-service/tests:apps/runtime-service/src apps/runtime-service/.venv/bin/python -m pytest --import-mode=importlib apps/runtime-service/tests/services/test_message_inbox_postgres.py -q`。真实 PostgreSQL，每用例独立 schema；模型参数需 `RUNTIME_MESSAGE_LIVE_MODEL=1` 才运行真实模型测试。
- API：在 `apps/platform-api` 执行 `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_runtime_delegation.py' -q`，同样运行 `test_model_connection_lifecycle.py`、`test_run_requests.py`。
- Web：在 `apps/platform-web` 执行 `pnpm exec vue-tsc --noEmit`、相关 ESLint 与 `pnpm exec vitest run src/modules/chat/composables/useChatSession.spec.ts src/services/threads/messages.service.spec.ts`。
- 完整网络链路：`Q5_DATABASE_URI=<专用测试PG库> Q5_GRAPHHARBOR_SOURCE=../graphharbor apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/q5_message_acceptance.py`（源码路径建议填写绝对路径）。脚本启动隔离 Runtime API/Worker、Platform API 和 Vite，结束只停止自身进程；平台数据用独立临时 SQLite，Runtime inbox/checkpoint 使用真实 PG。确定性模型加两轮慢工具用于稳定控制竞态，不将它称为真实外部模型。可追加 `--grep 'revoke|unknown'` 只跑相应用例。

## 证据与四态

- `done`：Runtime 队列测试最近 17 passed、1 skipped（该次未开启真实模型）；此前开启真实模型的组合回归 45 passed、1 skipped。真实模型测试中的授权 HTTP 为 mock，不能替代网络授权链路。
- `done`：API 委托 11 passed、授权/脱敏 7 passed、Run 请求 16 passed；Web 本轮定向 2 passed，类型和 ESLint 通过。此前全量 Web 69 passed、1 skipped。
- `done`：隔离网络链路首轮 3 passed（1.7 分钟），覆盖两批消息、注入前取消、注入后取消及刷新恢复；使用真实网关、消费授权 HTTP、GraphHarbor API/Worker 与 PostgreSQL。日志目录 `/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-g_7w2rnd`。当前源码 SDK 协议测试 2 passed。
- `done`：丢 ACK 浏览器恢复测试 1 passed：服务端先真实入队，再由浏览器网络故障拦截丢弃响应；刷新后用同 payload/message ID/Idempotency-Key 重试，最终上下文只有一条对应 HumanMessage。日志目录 `/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-fh61uzki`（该次共两项，unknown passed，revoke 在刷新后的 UI 断言失败）。
- `done`：网络撤权完整用例最终 1 passed（55.5 秒）：入队后停用 Agent，消费回调 403，Receipt 为 rejected，模型未收到补充；刷新后可读历史与拒绝回执，执行结束后发送按钮仍禁用。日志目录 `/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-dx8h8jww`。最终共 5 个网络浏览器场景分别通过；运行前固定源码，早期失败不计为通过。
- `done`：新增历史隔离/快照裁剪用例定向重跑 1 passed；最终 Python Ruff、Web TypeScript/ESLint、文档检查与 `git diff --check` 通过。移动端证据为 Chromium 390×844 视口，未宣称真机或所有移动浏览器兼容。
- `deferred`：双浏览器同 Thread 同时入队，用户明确后置，PG 并发测试不替代此项。

## GraphHarbor 构建边界（历史结论，发布进度见 10）

虚拟环境安装的 `graphharbor==0.13.0.post26` 不包含兄弟仓库工作区已有的 Vue 协议修复；实际现象是 Worker 执行完毕但官方 SDK 没有接收正确消息/终态。当前源码核验通过不等于已发布 wheel 通过。本轮没有修改 GraphHarbor、发布包或读取发布密钥。

验收源码文件 SHA-256（`../graphharbor/libs/langgraph-runtime-pg/src/langgraph_runtime_pg/`）：

- `graph_executor.py`：`d28033f66127b23737854d9e8099b85a4260fa14982079878512ef3fdfca2572`
- `protocol.py`：`bc00b3148240fa3a94394b78ea97b29b7f3472d60d8c8bfa31cf86ae611c67dd`

部署前须把这些通用协议修复纳入新版本构建，更新 Runtime 依赖锁并用该构建重跑网络脚本（不设置源码覆盖）。现有 post26 锁文件不是发布验收证据。全项目仍为 partial，双浏览器 deferred。

2026-09-11 后续：用户批准发布，post27 两包已上 PyPI，Runtime 锁文件和安装已更新；发布包最终复验见 [10 发布记录](10-graphharbor-post27-release.md)。上述 post26 阻塞不再代表当前安装状态。
