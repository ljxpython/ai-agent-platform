# 非前端验证与回退证据

日期：2026-10-06 至 2026-10-07。对应 T03/T06/T07/T09；用户批准范围内的隔离验证，未写前端代码、提交、发布或操作现役数据库。

## 环境与入口

- 本工作树未安装新依赖，复用已有服务解释器；Runtime conftest 优先加载工作树 src。API 在服务目录显式 `PYTHONPATH=src`，避免 editable 安装读取相邻检出。
- 锁定依赖：LangChain 1.3.17、LangGraph 1.2.11、Deep Agents 0.7.8、GraphHarbor 0.13.0.post41、MCP adapters 0.3.2。
- `tests/services/dearflow_agent/test_tool_error_platform.py` 使用独占临时 Docker PostgreSQL 16 / Redis 7 和 SQLite Platform DB，独立 Platform API、Runtime API、Worker 进程及 workspace；测试结束只清理这些资源。
- `tests/fixtures/tool_error_platform.py` 是测试夹具，不注册在生产 langgraph.json。受控模型记录消费错误的 call ID/PID，不记录 Prompt、凭据或异常正文。
- 真实模型入口 `test_tool_error_live.py` 要求显式授权模型 env 文件；只读取模型连接参数，不输出值。先确定性触发只读 search 参数错误，再调用真实模型验证主/子图都能消费错误。Provider retry=0，无真实搜索、图片/媒体付费调用或写动作。

## 已执行结果

| 验证 | 结果 | 证明边界 |
| --- | --- | --- |
| Runtime 主子图/分类/流/callback/图片图表定向 | 91 passed / 2 skipped，240.39 秒 | 实际 graph/HITL/native/stream；旧 live 图片/图表 skip 不计通过 |
| MCP/Docker 资源 | 7 passed，34.12 秒 | 独立 HTTP MCP error 多模态/transport，Docker 非零退出、超时和副作用次数，缺 CLI 不宿主执行 |
| 真实模型主/子图 | 2 passed，58.32 秒 | 主图 1 次、子图加父图 2 次真实请求；错误进入模型，非空最终回复 |
| Platform 网关回归 | 89 项，85 passed / 4 skipped，127.989 秒 | 两类 SSE、state/history、namespace、幂等/权限/HTTP；旧 opt-in PG 不计通过 |
| 修正事件计量后的性能及分类/图片路径 | 34 passed，95.62 秒 | 固定内容有界；单文件路径错误与可信根致命错误；串行/并行实际 graph 测量 |
| 最新研究工具/native/技能定向 | 56 passed / 3 skipped，646.61 秒 | 新增 Provider 边界的 RuntimeAuthError/未知 ValueError 身份传播；旧字符串断言对齐安全 JSON |
| HTTP 根错误映射及文件/文档契约 | 25 passed，104.15 秒 | 两 Agent 的未创建根返回原 404，根软链接返回安全 500，原文件和成功工具结果保留 |
| Platform/Runtime 边界向量 | 1 passed，73.50 秒 | 工作树 API src 与独立 API 解释器；上下文 hash、澄清值契约一致 |
| 扩大 Runtime 修正后回归 | 288 passed / 17 skipped，1550.26 秒 | DearFlow、Showcase、观测、公共工具和流 patch；本组未执行两个旧重启文件 |
| 最新分类/观测/流回归 | 40 passed，52.55 秒 | 异常类型名 128 字节上限；外部 native JSON code 非字符串不打断 callback；安全/控制流保留 |
| 并行结果与同批审批中断 | 2 passed / 14 deselected，7.99 秒 | 成功/错误按 call ID 各一条；审批暂停零工具执行，恢复后只写一次，Provider 调用一次 |
| 隔离 HTTP / 重启 / Runtime 代码回退 | 1 passed，236.33 秒 | 完整主/子图、fatal SSE/Thread/tasks/state/history、模型拒绝、五种控制；三角色重启、新 JSON 回放、基线主/子旧字符串与五种控制再次通过 |
| 可信根无权限/空间不足注入 | 2 passed / 6 deselected，5.44 秒 | 临时 IO EACCES/ENOSPC 保持致命错误语义、稳定公开 code 与已有文件；未操作真实磁盘权限/容量 |
| 最终可信根保护/HTTP/图片/文档/成果/终端 | 55 passed / 2 skipped，57.81 秒 | 执行中缺根不重建；初始化/上传保留；真实 Docker/本地终端与成功生成输出；旧 live 2 项不计通过 |
| 最终媒体/研究/审批/技能快照与进程重启 | 42 passed / 2 skipped，474.26 秒 | 临时独占 PG，媒体结果未知不重复、研究证据、审批、原 5 项进程重启全部通过；旧 live 2 项不计通过 |
| 最终可信根保护后的隔离 HTTP / 重启 / 回退 | 1 passed，447.31 秒 | 新 IO 语义下完整主/子、fatal、五种控制、三角色重启及基线回退再次通过 |

本轮非前端实现与验证已完成。前端代码、浏览器场景和全专项 Final 留给同事，见 verification.md 的未完成项。

## API 公开 fatal 出口

GraphHarbor Worker 的 lifecycle/Thread.error 和原生任务结果仍可能携带 `str(exc)`。实际修改
`apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py:redact_runtime_private_fields()`，在已有公开出口使用
`runtime.execution_failed`。字符串和字典 error 保持原形状；有界 identifier 类型名可保留。content/artifact/metadata/values
和 result 中的普通业务数据不当作运行异常改写；原私有字段过滤继续执行。此改动不改变 HTTP 路由、Run 状态或 ToolMessage 契约，
也不声称 GraphHarbor 内部原始日志已脱敏。

API 旧心跳测试固定 sleep 在宿主并发负载下不稳定，改为 Event 等实际收到两次心跳，5 秒上限；业务逻辑未修改。

增强 HTTP canary 发现任务结束事件的独立泄露出口（首次 fatal 验证未通过）；依据锁定 LangGraph 的
TaskResultPayload/PregelTask 字段 id/name/result/interrupts 做精确识别，原始状态/namespace/调用 ID 保留，
不改写 error=None 的审批中断。修正后 API event redaction 19 项及 SDK adapter 23 项通过；随后完整 HTTP 重跑亦通过。

## 扩大回归与修正

首次扩大 Runtime 回归为 14 failed / 274 passed / 17 skipped，2952.66 秒；不是全量通过。
11 项为成果/示例文档旧原文断言，1 项是测试运行中已修正的指南工具名断言；独立最新定向已覆盖。
另 1 项揭示 ImageWorkspace 可信根致命化影响 HTTP 404，已在现有 webapp 添加最小异常映射：GET 的
FileNotFoundError cause 保留原 image/file/artifact/workspace not-found code；其他根故障安全 500；
不创建目录、不把 Agent 工具故障转可恢复错误。25 项重跑通过，并补两图 missing/unsafe-root 用例。
最后 1 项是旧边界测试写死工作树 `.venv`，已允许显式 PLATFORM_API_TEST_PYTHON 并固定工作树 API src；
独立 API 环境重跑通过。原重启审批/技能快照 5 项在首次扩大组中通过，未受随后文本/HTTP 修正影响；
其余范围扩大组修正后为 288 passed / 17 skipped，1550.26 秒。原重启 5 项与修正后组分别记录，
不声称一次全组 293 项通过。最新类型名上限和 native code 类型保护另有 40 项通过。

增强 HTTP 的失败与通过证据分开记录：612.55 秒首次 canary 失败揭示 tasks 原文泄露；804.99 秒重跑中
主/子图、fatal 公开出口及模型拒绝通过，但审批恢复请求覆盖配置，被现有接口正确返回 400。
fixture 已改为只传 assistant_id/command.resume，使用真实 interrupt ID 和原持久化配置。
随后一次启动超时 449.25 秒、一次启动退出 159.35 秒，不计功能通过；将模型类和 Agent 导入限制到 graph
factory，平台角色使用其自己的解释器，Runtime auth 导入也避开平台进程，不安装跨服务新依赖。
后续一次 state 读取超过测试栈网关 30 秒（403.28 秒失败），仅 fixture 将 upstream timeout 设置为
180 秒、客户端 240 秒；生产配置不改。688.83 秒重跑已通过主/子图、Protocol 回放、fatal 脱敏、模型拒绝，
审批恢复 success 且真实落盘，但测试预期 workspace hash 错误。核对平台 request context 后确认实际 tenant
为 `__default`，不是 fixture catalog TenantRecord；改为复用 `hashed_thread_root()` 精确校验作用域，保留
全独占根目录新增文件差集，确保没有落到其他 Thread。

618.02 秒重跑受到 Docker backend 失联影响，Run 为 interrupted/cancel_requested，清理超时；
该轮 1 failed / 1 teardown error 不计业务通过。2026-10-07 Docker daemon 恢复后，原本轮容器已不存在，
新的独占链路继续验证，没有重启或清理现役 5432/6379 及其他 worktree 资源。

恢复后一次 121.45 秒验证通过主/子图、fatal、模型拒绝、approve/edit/reject/clarification，取消返回 503。
根因是测试 Thread metadata 仅有 assistant_id，没有正式平台使用的 graph_id 绑定，run-cancel 委托无法签发。
修正全部 fixture 创建请求为 graph_id，并在创建后校验绑定；未更改生产授权逻辑。
接续 125.42 秒重跑已通过全部五种控制操作、三角色重启后的原消息逐字段回放、keep 文件及 Provider 次数保持，
但回退准备的 git archive 在服务目录使用根路径，退出 128。将该只读命令 cwd 固定仓库根；未变更 HEAD、分支
或工作树。本阶段完整重跑为 1 passed，236.33 秒；后续可信根保护后 447.31 秒再次通过。

## 完整隔离 HTTP 与回退证据

最终通过版本（可信根保护后 447.31 秒）创建 Thread 时使用正式 metadata.graph_id，审批目标用平台默认 tenant 与现有
hashed_thread_root 推导。主/子 Agent 的错误进入下次模型请求，受控模型记录全部来自 Worker PID；
非法参数场景 Provider 调用 0 次。SSE、Protocol、state/history 保留错误 call 配对，Run 最终 success。

| 场景 | Thread ID | Run ID | 结果 |
| --- | --- | --- | --- |
| 主 Agent | 68cf5009-7b54-4315-99ba-daf51a26246e | d3f309f6-5348-42b4-bb02-7ae958fac8dd | success，fixture-search_web 的 tool.invalid_input 保留 |
| 子 Agent | 0f6c22f8-a8f2-4bd6-8dcc-4c61738c1e73 | 10603e8d-1bfc-4d7e-872b-2557a43c073c | success，子图 tools namespace 与 Protocol 回放保留 |

fatal 场景真实进入 Provider 1 次，Run error；标准 SSE、Thread、state/history 和包含 tasks 的 Protocol
公开出口均无 EXCEPTION_CANARY。未授权模型拒绝返回 400/403，没有增加 Provider 调用。
approve/edit 仅在准确 scope 路径新建一个文件、内容 once/reviewed；reject/clarification 无新文件。
slow 请求进入 Provider 后用户取消，Run interrupted，调用计数只增加 1 次。

依次停止并重启 Worker、Runtime API、Platform API 后，两条原 Thread 的消息逐字段一致，keep 文件保留；
累计 Provider 调用仍为 2，重启没有重放副作用。基线使用只读 git archive HEAD（424ff90e）提取 Runtime
源码到临时目录，Runtime/Worker 优先加载该源码，Platform API 保留新公开错误安全过滤。
旧版本读取新 JSON 历史完全一致；新主/子 Run 使用旧 invalid_research_query 字符串仍 success，
approve/edit/reject/clarification/cancel 再次全部通过。没有删除 checkpoint、工作区或任务记录，
没有切换工作树、提交、生产回退或恢复旧公开异常泄露行为。

fixture 收尾停止三进程和独占 Docker PG/Redis；最终 docker ps 核对本轮 tool-errors 容器为空。
Docker 恢复前遗留的本轮独占回归 PG 也已不存在；没有触碰现役端口和其他 worktree 容器。

## 收口复查：执行中缺根不能重建

最终复查发现 `ImageWorkspace._directory(create=True)` 也创建可信根；读路径的 missing-root 回归不足以
证明写路径。新增回归真实复现为 1 failed / 8 deselected（6.23 秒），失败为缺根仍能创建 generated 目录。
保留同一个 IO helper，只增加显式 create_root 参数：默认工具写入仅创建根内子目录；DearWorkspaceBackend.prepare、
图片/文件上传、TerminalSession 初始化保持原安全 no-follow 创建行为。研究证据、图片/图表结果和 artifact 发布
缺根时传播 RuntimeWorkspaceError，不静默替换工作区。独立媒体成功测试显式准备临时根，贴合生产调用前置条件。

受影响路径首次扩大组为 2 failed / 53 passed / 2 skipped，21.79 秒；两项都是原终端测试验证失真：
本地 wait_output 匹配命令回显提前读文件，改为等待实际换行后的输出；Docker 挂载测试遗漏 backend=docker，
补显式后端设置。没有修改终端进程行为。最新代码的根保护/HTTP/上传/文档/成果/终端组为
55 passed / 2 skipped（57.81 秒）；媒体/研究/审批/重启组为 42 passed / 2 skipped（474.26 秒），
含此前分开记录的原 5 项重启。完整隔离 HTTP 为 1 passed（447.31 秒），真实重启与基线回退再次全部通过。
没有将这些重跑与原 288 项拼成一次全量结果。最终本轮独占 tool-error-final-workspace-4fc0-pg 已停止，
对应工具验证/fixture 进程退出；无遗留本轮容器。

## 性能实测

同一进程每组 10 个独立 Thread，Fake 模型、实际 graph、InMemorySaver；并行工具数为 1 或 4。
时间/峰值内存使用标准库，流字节为序列化 v3 事件 JSON（不是含 SSE framing 的网络线长），checkpoint 为
saver.storage 普通字典序列化后的平均大小（不是 PostgreSQL 表/索引/持久化写流量）。未知异常传播前的已发事件也计入。

| 并行数 | 路径 | wall ms/Run | CPU ms/Run | tracemalloc 峰值字节 | 流 JSON 字节/Run | checkpoint 字节/Run |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 无 middleware，成功 | 418.510 | 41.248 | 331352 | 1857 | 3044 |
| 1 | middleware，成功 | 359.358 | 39.854 | 195744 | 1857 | 3049 |
| 1 | 已知错误反馈 | 391.466 | 39.971 | 432642 | 2386 | 3041 |
| 1 | 未知异常传播 | 172.285 | 25.924 | 354833 | 493 | 1628 |
| 4 | 无 middleware，成功 | 570.646 | 66.834 | 377329 | 4134 | 3043 |
| 4 | middleware，成功 | 604.545 | 67.591 | 325323 | 4134 | 3046 |
| 4 | 已知错误反馈 | 561.223 | 67.948 | 636536 | 6250 | 3045 |
| 4 | 未知异常传播 | 374.553 | 51.643 | 848923 | 1596 | 1626 |

固定 Reference 错误内容 215 字节；每增加一个预期错误的流内容增长来自有界错误消息。宿主同时运行其他测试，
wall 受调度影响，不能据此声称吞吐达标或回退；项目没有批准延迟 SLO。

## 可复现命令

以下在 Runtime 服务目录，用已具备锁定依赖的解释器执行；不要把现役数据库 URI 传给隔离测试。

```bash
TOOL_ERROR_PLATFORM_TEST=1 PLATFORM_API_TEST_PYTHON="$PLATFORM_BASELINE_PYTHON" \
  "$RUNTIME_BASELINE_PYTHON" -m pytest tests/services/dearflow_agent/test_tool_error_platform.py -q -s
TOOL_ERROR_LIVE_TEST=1 TOOL_ERROR_MODEL_ENV_FILE="$TOOL_ERROR_MODEL_ENV_FILE" \
  "$RUNTIME_BASELINE_PYTHON" -m pytest tests/services/dearflow_agent/test_tool_error_live.py -q -s
TOOL_ERROR_PERF_TEST=1 "$RUNTIME_BASELINE_PYTHON" -m pytest tests/tools/test_tool_error_performance.py -q -s
```

API 在对应服务目录：

```bash
PYTHONPATH=src "$PLATFORM_BASELINE_PYTHON" -m unittest discover -s tests -p 'test_runtime_gateway_*.py'
```

完整联合 Final 留给前端交付后的浏览器验收；本记录只证明实际列出的非前端测试。
