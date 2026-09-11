# 2026-09-11 旧视觉、Agent 归一与本地启停

## 批准与范围

用户批准修复本仓库进程启停、恢复旧 Chat 视觉并保留新逻辑、已授权 Graph 自动对齐为 Agent。随后明确批准完整备份后重建旧本地 Platform API 开发库。未修改 Runtime 数据库、未发布 GraphHarbor、未提交或推送代码。

## 实现

- `scripts/local-stack.sh` 与 `scripts/local_stack_processes.py`：按命令和精确 app 工作目录识别服务，处理手工启动、uv/pnpm 包装及 reload 子进程。失效 PID 不再代表服务存活。TERM 超时后复核命令身份并 KILL；不按端口杀无关进程。
- API `modules/agents/infra/sqlalchemy/repository.py` 的 `align_authorized_graphs`：有效目录及项目授权决定可见 Agent，读取列表时幂等补齐。沿用无 overlay 时允许的既有语义；保留现有 UUID、名称和 context。savepoint 与 project/graph 唯一约束处理并发。
- Web `ChatPage.vue`、`GraphsPage.vue`、`AgentsPage.vue`、`AgentEditorPage.vue`：只选择 Agent，Graph 链接也解析 Agent；删除手工新建/删除入口及无消费者 service 方法。以有效 Agent 列表判断可聊天性，避免管理员 Graph 目录包含禁用项时误判。撤权历史保留只读，执行网关继续复核授权。
- `ChatSession.vue`、`Transcript.vue`：恢复旧 `pw-chat-*` 容器、浅深主题、气泡、标识、输入区和空态，桌面历史搜索回到侧栏。保留 SDK、v-memo、审批、队列、分支与取消编排。
- `patches/@langchain__langgraph-sdk@1.10.2.patch`：官方 scoped messages 投影收到子级 values 时会覆盖父级正文。ESM/CJS 增加精确 namespace 判断；页面投影标记为持续订阅，避免根终态抢先暂停仍在回放的子图，生命周期仍由 registry dispose 释放；通过 pnpm patchedDependencies 和锁文件安装，不修改 GraphHarbor 过滤语义。`scoped-sdk.spec.ts` 在未修补版本实际失败（parent 被 child 替换），修补后通过。升级 SDK 时需重跑该用例，官方修复后删除补丁。
- SDK 接管订阅时同时恢复已暂停的 handle，覆盖 root terminal 在 `subscribe()` 返回前到达的竞态；使用真实 `SubscriptionHandle` 验证暂停后仍能接收后续 scoped 正文。
- API `RuntimeStreamingResponse.stream_response` 在响应结束/取消时主动关闭脱敏生成器；`LangGraphRuntimeClient.stream` 使用已有 AnyIO 的 shield 保护 HTTP 连接清理。避免依赖 GC 同时回收嵌套生成器造成 `aclose(): asynchronous generator is already running`，不改变 Run 取消语义。

## 本地开发库重建

旧库缺少 `agents.status`，模型必填字段包含 NULL，不能使用空库基线原地升级。已停止本地 Platform API，完成 SQLite backup、integrity_check 和全部 27 张表行数核验；保留原始主文件。备份位置：

`apps/platform-api/.data/backups/20260911-123755/platform-api.db`

重新执行 `apps/platform-api/scripts/init_db.py` 创建当前 20 表，新库 integrity_check=ok、agents.status 存在；重启 API 后管理员登录、项目范围模型目录、自动 Agent 列表真实 HTTP 200。测试项目已清理。原有用户/项目/Agent/模型配置留在备份，不自动恢复旧数据；新库管理员来自现有 bootstrap 配置。

## 验证记录

- 实际 start → stop → start 通过，3000/2142/8123 释放；API/Worker/Web 子进程退出，无关 interaction-data-service 保留。
- `python3 scripts/test_local_stack_processes.py`：无 PID 服务与忽略 TERM 的子进程停止，另一仓库同名服务保留。
- API Agent 定向 unittest：4 passed；自动对齐用例含四请求首次读取、配置保留、撤权/恢复和访问拒绝。
- API 流脱敏与 SDK adapter：16 passed，包含发送阶段断连后上游在响应退出前完成异步清理。
- SDK scoped 定向测试：2 passed，覆盖 namespace 隔离及订阅返回前已暂停的恢复。
- 三尺寸 `parallel-chat-refactor.spec.ts`：3 passed（1440/1024/390），覆盖混合并行审批、嵌套正文隔离、刷新恢复、焦点归还、移动导航、20 次桌面 SPA 会话切换。最终日志 `q5-message-hmytuo79`，Platform API 日志无 `RuntimeError`/`Traceback`/`Task exception`。
- 截图：[桌面浅色](screenshots/12-parallel-1440-light.png)、[桌面深色](screenshots/12-parallel-1440-dark.png)、[1024](screenshots/12-parallel-1024-light.png)、[390](screenshots/12-parallel-390-light.png)。
- 真实 Graph 的 Agent/移动端浏览器回归：3 passed（`q5-message-63vknw8h`），配置编辑/刷新保留、Graph 入口解析 Agent、撤权隐藏/历史只读、恢复原 Agent 身份、移动取消保留草稿且只有一次 `run.start`。网关日志无异常。
- 移动空态截图：[浅色](screenshots/12-chat-mobile-light.png)、[深色](screenshots/12-chat-mobile-dark.png)，已通过图像工具查看；布局无横向溢出与输入框可达另有浏览器断言。
- 最终补丁安装后的 Web 全量：77 passed / 1 skipped；SDK chain 需独立运行环境，不计为通过。
- 最终 Web lint、类型检查及生产构建通过；Python 定向 Ruff 通过（HTTP 路由沿用 FastAPI `Depends/Body/Query` 默认参数，检查排除既有 B008 报告）；`git diff --check` 通过。
- 最终代码已通过 `restart-one platform-api` / `restart-one platform-web` 加载：API `http://127.0.0.1:2142/_system/health`、Web `http://127.0.0.1:3000` 均 ready；启停同时回收了本仓库无 PID 文件的遗留 API 进程。

## 状态

`done`：本次已批准实现及必要验证完成，08 与项目概览同步。双浏览器同 Thread 入队、完整文件/Skills API、PTY 继续 deferred。
