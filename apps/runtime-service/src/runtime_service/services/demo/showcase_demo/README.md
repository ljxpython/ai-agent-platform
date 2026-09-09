# Showcase：真实项目教学 Agent

这个服务演示如何在 LangChain、LangGraph、Deep Agents 的原生能力上，增加少量平台运行时接入。
它可以分析和修改实际文件，通过人工审批后在 Docker 中运行 Python。正式工具不返回模拟成功结果。

## 从一个真实任务开始

新线程会得到一个小型销售报表项目：

```text
/workspace/
├── README.md
├── sales.csv
└── report.py
```

`report.py` 是真实可运行程序，初始版本**故意保留一个教学缺陷**：统计时没有乘数量，输出 `27.00`；正确结果为 `43.50`。
这个缺陷属于输入样例，不属于 Agent 的执行实现。

可以依次尝试：

1. “只分析销售报表为什么算错，不修改、不运行。”
2. “修复这个问题，添加一个可运行的检查，然后验证。”
3. “查阅 Python Decimal 官方文档，解释金额计算为什么使用它。”

第一步只读。第二步可使用 Todo 和子 Agent，修改和执行前弹出审批。
第三步真实访问允许的官方文档站点。简单问题不强制列计划，也不按关键词强制走完整流程。

## 每个文件负责什么

| 文件 | 职责 | 开发新 Agent 时怎么借鉴 |
| --- | --- | --- |
| `agent.py` | 唯一组合根：校验身份和 Context，取得模型，组合官方 Agent/中间件，接入追踪 | 保持显式装配，不实现工具或 HTTP client |
| `prompts.py` | 主 Agent、只读研究助手、实现助手的指令 | 只放纯文本或纯渲染函数，不读环境变量和网络 |
| `subagents.py` | 两个明确的内部角色及最小工具、权限、审批 | 角色复杂前使用声明式 SubAgent，不增加第二个 graph ID |
| `backend.py` | 线程工作区初始化、官方 FilesystemBackend 与 Docker 执行适配 | 只实现框架缺少的资源边界，不重写文件和搜索工具 |
| `tools.py` | 受限 HTTPS 文档抓取 | 只放本服务特有的真实业务动作 |
| `skills/showcase-notes/SKILL.md` | 可按需读取的任务指南 | Skills 是资源，不是工具，也不能授予权限 |
| `examples/` | 初次使用线程时复制的 CSV 项目 | 测试夹具与模型 mock 不进入正式工具 |
| `__init__.py` | Python 包标识 | 不批量导入组合根 |

部署入口是 `runtime_service.graphs.showcase_demo:get_agent`，该文件只重导出服务的 `get_agent`。
注册位于应用根 `langgraph.demo.json`，不进入默认生产配置。

## 哪些直接使用官方能力

| 能力 | 实现 |
| --- | --- |
| Agent 循环、工具调用、长上下文处理 | `create_deep_agent` |
| 计划和实时进度 | `TodoListMiddleware` 的 `write_todos` 和 `values.todos` |
| 文件读写、grep、glob、执行 | `FilesystemMiddleware` 的原生工具 |
| Skills 发现和按需读取 | `SkillsMiddleware` 与 `CompositeBackend` |
| 委派 | `task` 工具和声明式 `SubAgent` |
| 审批 | `interrupt_on`、`HumanInTheLoopMiddleware`、`Command(resume=...)` |
| 持久化、流式事件 | LangGraph checkpointer、`astream`、namespace |
| 调用次数限制 | `ModelCallLimitMiddleware`、`ToolCallLimitMiddleware` |

二次封装只有平台身份/策略/模型接入、追踪、线程资源及受限文档抓取。
没有通用 Builder、工具 Registry、自建 Agent 循环或第二套审批 State。
不声明空的 `scenario`、`confirmation`、`sandbox_output` 字段；默认 State 与 Middleware 扩展就是事实来源。

## 子 Agent 和权限

`research` 只有 `ls/read_file/glob/grep`，不能写文件或执行代码。
`general-purpose` 是明确配置的实现助手，拥有读、写和执行工具，但没有再次委派或额外网络工具。
显式使用官方默认角色名，避免框架另加一个权限不清楚的通用子 Agent；不修改全局模型 HarnessProfile。

主/子 Agent 都接入 `RuntimeConfigMiddleware`。它在模型可见工具及实际调用边界检查：
可信身份、Context 哈希、assistant/thread scope、平台 allowlist 与该角色的显式工具集。
`WorkspaceMiddleware` 再确认资源所属 tenant/project/thread，防止把已绑定的图复用于另一个租户。

`RuntimeContext` 仍只有平台标准的 `model_id/temperature/max_tokens/top_p/tools`。
`tools=[]` 表示禁用工具；省略则使用服务默认工具清单，平台必须授权对应工具及权限。
`execute` 是可修改整个线程工作区的能力，不能授予只读角色；审批只代表用户同意，不能替代 Runtime 授权。

当前权限映射在 `agent.py` 的 `_TOOL_PERMISSIONS` 中显式列出。
每个角色最多 12 次模型调用、24 次工具调用；模型调用超时 30 秒。

## 路径、存储和真实执行

模型看到的文件和 shell 路径都是 `/workspace/...`；shell 工作目录也是 `/workspace`。
Skills 通过 `/skills/` 访问，由 `importlib.resources` 定位安装包资源，随 wheel 发布。
**不把开发机绝对路径放进 Prompt、Context 或 Skills 参数。**

| 部署变量 | 默认值 | 用途 |
| --- | --- | --- |
| `RUNTIME_SHOWCASE_WORKSPACE_ROOT` | `.runtime/showcase` | 专用数据根目录，可配置相对或绝对路径 |
| `RUNTIME_SHOWCASE_IMAGE` | `python:3.13-slim` | Docker 执行镜像；正式环境建议固定镜像 digest |

线程目录由可信 tenant/project/thread 的摘要派生。初始化不会覆盖用户已修改的样例文件。
命令容器只绑定当前线程的 `/workspace`，不挂载源代码、凭据或 Docker socket。
容器关闭网络、使用只读根文件系统、去除 capabilities，限制 CPU、内存、进程、文件大小和输出量。
命令默认 30 秒，最多 60 秒；返回真实 stdout/stderr 合并输出及退出码，最多 128 KiB。
异步执行沿用官方线程适配；取消 Run 不保证立即终止正在执行的命令，容器内命令仍受最多 60 秒限制。
执行 worker 面向 Linux/macOS，使用宿主进程 UID/GID；Windows 原生运行未验证。
Docker 不可用或镜像缺失会明确失败，**不会回退到宿主机 shell**。

官方文件工具直接读写受限的线程目录；shell 在容器中读写同一目录。
Shell 授权覆盖整个该工作区，不宣称按 shell 文本实现逐文件权限。
Skills 只读规则作用在独立的非执行 Backend 路由上；容器不能访问包内 Skills。

工作区文件独立于 checkpoint：恢复已有 Run 会继续使用真实文件，不会随 checkpoint 回滚文件系统。
容器在命令完成时删除，工作区保留。部署者负责磁盘配额、备份和停用线程的数据清理。
这个 Demo 不额外实现分布式存储和资源调度。多副本必须使用共享存储，并保证 Docker daemon 能看到相同的 bind-mount 路径。
建议在安装 Docker 的专用 worker 主机运行；若 runtime 自身在容器内，需要配置专用执行部署，不能直接照搬默认生产镜像。

## 本地运行与调用

在 `apps/runtime-service` 目录，按应用 `.env.example` 配置模型与 Runtime 认证，并准备 Docker：

```bash
docker pull python:3.13-slim
uv run graphharbor serve --config langgraph.demo.json --host 127.0.0.1 --port 8123
```

数据库、Redis、签名配置及独立 worker 启动方式沿用应用部署说明。
Platform 通过认证网关调用；不要为了演示跳过 JWT/Delegation 或开放测试身份开关。
正式入口不接受 `_runtime_test_*`；fake model 和测试身份仅存在于 `tests/`。

`get_agent` 是异步 graph factory。真实 Run 的 Backend 绑定线程，因此这里使用动态构图；
普通只依赖 StateBackend 的 Agent 应优先静态编译。schema/state 探测使用相同拓扑的不可执行图，
不创建线程目录、不请求模型 catalog、不启动 Docker。
checkpointer 由 Agent Server 注入，不在服务里创建进程内 saver。

流式调用使用官方参数：

```python
async for event in graph.astream(
    {"messages": [("user", "分析销售报表")]},
    config,
    context=context,
    stream_mode=["values", "updates", "messages"],
    subgraphs=True,
    version="v2",
):
    ...
```

远程 SDK 对应 `stream_subgraphs=True`。用 namespace/tool call ID 区分主/子 Agent；
子 Agent 通过父 Run 暂停和恢复，不是独立的平台 Run。

同一个 HITL payload 可含多个 `action_requests`，这不等于多个独立 interrupt。
审批列表必须按动作顺序提供同样数量的 decisions；多个独立 interrupt 使用 ID → decisions 映射。
调用方应在提交前校验数量和决定类型；非法 resume 会由官方 Middleware 抛错，不能承诺原地重试任意错误 payload。

## 验证

```bash
# 确定性模型驱动真实 Graph/文件工具；不调用外部模型和 Docker
uv run pytest tests/services/showcase_demo -m "not integration and not e2e"

# 实际 Docker 执行、文件产物、退出码、隔离与限制
uv run pytest tests/services/showcase_demo -m integration

# 真实模型只读流式分析；需配置本地 DeepSeek 模型连接
RUNTIME_SHOWCASE_LIVE_TEST=1 uv run pytest tests/services/showcase_demo/test_agent.py -k live_model
```

测试断言真实 Todo 状态、Skills 内容、文件变更、授权拒绝、子图事件和审批恢复。
外部模型可以在测试中替换为官方 fake model，以稳定覆盖分支；正式工具不替换为假实现。
完整进度与远程/前端验收边界见仓库 `docs/projects/20260908-showcase-demo/verification.md`。

框架参考：[Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview)、
[Backends](https://docs.langchain.com/oss/python/deepagents/backends)、
[Subagents](https://docs.langchain.com/oss/python/deepagents/subagents)、
[Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)。
