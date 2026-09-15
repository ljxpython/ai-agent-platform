# P0/P1 真实部署验证收口

日期：2026-09-14。范围：用户授权的 P0/P1 后端剩余验证；不修改或重新验收前端，不提交代码。前序业务修复、逐文件／函数定位和基础测试见 [04 实施记录](04-p0-p1-foundation-closeout.md)。

## 结论与完成范围

- **done：P0 后端风险验证**。补齐最小契约基线、本机 Agent Server API／独立 Worker／Docker 持久目录联调，以及可控 MCP 任务协议试验。
- **done：P1 后端最小真实底座**。完整平台 HTTP 链路完成 TXT 上传、官方澄清、Worker 重启、原 checkpoint 恢复、容器执行审批、真实发布、下载和 SHA-256 核验。
- **deferred：本轮前端验证**，依据用户“前端暂时不需要考虑”的范围约束。历史前端实现不受本轮修改，浏览器页面刷新／下载 E2E 不能据此标完成。
- **partial：整个 Dear Agent 项目**。P2—P7、23 项业务 Skills、生产多机部署和外部任务业务实现尚未完成；本记录不是生产发布批准。

## 本次具体修改哪些文件

路径均相对仓库根；业务修复的完整清单继续以 04 为准，本次收口新增以下测试能力。

| 文件／函数 | 修改内容与排查入口 |
|---|---|
| `apps/runtime-service/tests/services/dearflow_agent/test_platform.py` / `test_platform_creates_and_completes_dear_run` | 扩展原基础文本烟测：独立项目和 Agent 注册、真实模型配置、能力查询、TXT 上传、按 interrupt ID resume、受控执行／发布、下载校验；可选重启 Worker 后比较 checkpoint。文件模式期限 480 秒，文本模式 120 秒，超时报错对应实际期限 |
| `apps/runtime-service/tests/services/dearflow_agent/mcp_task_probe.py` / `generate`、`read_task`、`get_task`、`get_result`、`cancel` | 新增仅测试使用的官方 MCP stdio 服务；SQLite 临时持久任务、服务自定义幂等键、提交落盘后退出模拟 ACK 丢失、重启查询／取结果／取消。没有向业务服务添加测试存储或另一套运行管理器 |
| `apps/runtime-service/tests/services/dearflow_agent/test_mcp_task_probe.py` / `test_mcp_task_ack_loss_restart_result_and_cancel` | 新增官方 ClientSession 跨进程故障试验；验证 ACK 丢失时任务已存在、同键恢复不重复创建、结果和取消终态在再次重启后保留 |
| `docs/projects/20260913-dearflow-agent/phases/P0-评审与风险验证.md`、`phases/P1-最小真实底座.md` | 将已取得真实证据的剩余后端需求勾选完成，保留前端范围边界 |
| 本项目 `README.md`、`01-architecture-and-boundaries.md`、`08-web-and-platform-contracts.md`、`09-background-work-and-scope.md`、`10-delivery-and-production-verification.md`、`docs/FEATURES.md` | 更新接续游标、契约落点、B02 Spike 状态和阶段汇总；不把后续业务标为完成 |

## 真实平台文件及重启验收

工作目录 `apps/runtime-service/`：

```bash
DEAR_PLATFORM_TEST=1 DEAR_PLATFORM_FILES_TEST=1 DEAR_PLATFORM_RESTART_TEST=1 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py --tb=short -s
```

结果：**退出 0，1 passed in 374.63s**。原始关键输出：

```text
verification project=58754b29-2139-4727-8b7f-d450b70348c8 thread=9db13262-6755-40fd-89b6-8df470549fb9 run=867852bb-956f-46b5-932b-4801675c1c69
file-chain verified; worker_restarted=True
1 passed in 374.63s (0:06:14)
```

输出的 run 是初始 Run；每次 resume 创建后续 Run，测试持续跟踪最新 Run 至成功，仍在同一 thread。按以上 project／thread 可查询完整历史。

实际动作：本机 Platform API `127.0.0.1:2142` 正常登录 → 独立项目注册 Dear Agent → 创建线程 → 能力查询 → 上传合成 TXT → 官方 select 澄清 → 第一次中断时调用仓库 `scripts/local-stack.sh restart-one runtime-worker` → 重读 state，checkpoint 完全一致 → 按 ID 恢复 → 读取技能与输入 → 批准 execute → Docker 写入大写 TXT → 批准 present_artifacts → 平台下载 → 内容及发布引用哈希一致。测试强制断言澄清、执行、发布三种中断均发生，不把模型直接回答当文件成功。

沿用本机启动脚本的 API／独立 Worker、真实数据库和 Docker；工作目录按 `RUNTIME_WORKSPACE_ROOT` 及 graph/tenant/project/thread 隔离。API、Worker 和 Docker 挂载必须指向同一宿主绝对目录。该结果证明本机持久目录在 Worker 重启后可续用，**不证明跨机共享存储、多副本故障切换或浏览器刷新**。执行镜像及版本锁见 04。测试新增模型在 finally 禁用，独立项目／线程保留作排查证据，不删除用户数据。

此前 502 为历史失败；同一部署基础文本复跑及本次文件链路均通过。证据支持间歇性模型上游连接故障，缺少模型代理内部日志，不能进一步断言 DNS 或代理重启原因。

## P0 最小契约冻结（当前 P1 切片）

这里冻结实际已验证的接口，不另造服务间 schema 包。扩大能力或破坏兼容时同步生产方、消费方与测试；P2 Context v2 不在本次冻结范围。

| 编号 | 生产方 → 消费方／接口与版本 | 已验证范围 |
|---|---|---|
| C01 | Platform 项目 Agent 目录 → Runtime Thread；`POST /api/projects/{project_id}/agents`、`POST /api/langgraph/threads`；graph=`dearflow_agent` | 正常注册后按授权创建／运行。不能绕过项目 Agent 目录直接启用任意 graph；前端筛选分页另验 |
| C02 | Runtime `services/dearflow_agent/capabilities.py` → Platform `GET /api/langgraph/threads/{thread_id}/capabilities` | `schema_version=1`；Standard、text/select、TXT、files；Dear message_queue=false、independent_subagent_cancel=false；静态声明不授予权限 |
| C03 | Platform 签发当前 Context → Runtime 现有解析与 scope/hash 校验 | 沿用现有 Context，不升级到 v2；`model_id` 是平台注册模型 UUID，`tools` 是已授权工具清单。resume 从原配置恢复，不能通过答案改模型／工具／身份 |
| C04 | Runtime workspace → Platform 文件代理 | `PUT /api/langgraph/threads/{thread_id}/files/uploads/{sha256}` 上传；`GET /api/langgraph/threads/{thread_id}/files/content?path=...` 下载；ArtifactRef `version=1`，实际字段以公共 `workspace/artifact_refs.py` 为准；JWT、scope、路径和哈希校验，缺文件 404／损坏哈希 409 |
| C05 | 官方 interrupt/HITL → Platform Run API → 同线程恢复 | 澄清请求／回答 `schema_version=1`，仅 text/select；`POST /api/langgraph/threads/{thread_id}/runs` 携带 `command.resume` ID 映射；审批沿用 decisions，澄清沿用 values；原有 input.respond 适配与幂等回归见 04 |

澄清恢复示例（ID 来自当前受信 state）：

```json
{"command":{"resume":{"<interrupt_id>":{"schema_version":1,"status":"answered","values":{"operation":"uppercase"}}}}}
```

工具审批对应 ID 的值为 `{"decisions":[{"type":"approve"}]}`；不得用澄清回答代替审批。平台预校验失败为 422，不创建恢复 Run。连续 ID、重复提交、混合工具批次、安全负例见 04 的确定性与网关测试；本次部署测试走正常批准路径。官方事件／state 为事实源，没有 DeerFlow 自定义提问终止事件。

## P0 长 MCP 风险试验（09/B02）

工作目录 `apps/runtime-service/`：

```bash
.venv/bin/python -m pytest -q tests/services/dearflow_agent/test_mcp_task_probe.py --tb=short
```

结果：**退出 0，1 passed in 37.06s**。使用已安装 `mcp==1.26.0` 的 `ClientSession.experimental` 和 `Server.experimental` task APIs，stdio 传输。服务在 SQLite 提交成功后、返回 task handle 前退出；客户端确实断连，数据库已有一条任务。重启同键恢复并读取 `synthetic-result`；再创建长延迟任务并取消；第三次进程确认 completed／cancelled 保留，数据库总数为 2。

| 能力 | 试验结论／采用边界 |
|---|---|
| 提交、get、result、cancel、重启 | 可控任务服务通过；仅对明确声明 Tasks 能力的服务启用 |
| ACK 丢失重试 | 可控服务自定义 key 保证找回同任务；这是供应商能力，不是 MCP 通用 exactly-once。无幂等键或查询能力时必须记录 unknown，不自动重复付费提交 |
| 官方通知路径 | 冻结为经授权的官方 Run API，禁止直接写 checkpoint。P1 已实测正常创建／中断恢复；真正外部结果通知、幂等 outbox 与授权续期在 P5 验证 |
| 活动根 Run | 后续复用既有消息队列；Dear P1 尚未启用，不能同时投队列又新建 Run。P2 先接入验证，P5 再验外部结果通知 |
| 不在此试验范围 | 真实媒体供应商、HTTP MCP、input_required、取消与成功竞态、双 Worker lease/fence、凭据续期、推送通知、任务 TTL 清理；P5 B03—B06 实现及验收 |

本次完成的是 B02 最小协议风险验证，测试服务的 SQLite 不进入业务代码。API 为 experimental，升级 MCP 时必须复跑本测试；正式供应商要逐个验证，不能根据本试验宣称全部支持恢复或取消。

## 收口检查

仓库根执行 `python3 scripts/check_docs.py`、`git diff --check` 均退出 0；Runtime 环境用 Python `ast.parse` 检查本次 3 个测试文件，语法通过。完整部署测试通过后只修正了测试超时提示中的秒数，未改变运行行为，因此未重复消耗模型调用。现有 Runtime 环境未安装 Ruff，本次语法检查不冒称 lint 或类型检查；仓库 Python 统一质量工具门禁仍按 10 章约定另行落实。

## 下一阶段交接

后端可转入 [P2 执行包](../phases/P2-研究与交互基础.md)：先核对已有模式定义和 Context，再推进研究工具／证据、MCP 权限、队列与完整提问表单；本轮未擅自扩展 P2。前端需要对接时提前告知，浏览器 E2E 由前端阶段另行验收。Store 原子修订留 P6；外部任务持久业务与多 worker 故障验证留 P5；全量生产验证留 P7。
