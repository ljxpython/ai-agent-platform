# Showcase：真实项目教学 Agent

演示文件读写、执行、Skills、委派、审批和平台能力如何在一个 Deep Agent 组合根中协作。先读 [Agent 开发指南](../../../../../docs/standards/runtime-agent-development-guide.md)，再按需要选择本例的能力；不要为简单 Agent 复制整套工具。

## 从一个真实任务开始

线程首次准备时会得到 [examples](examples/README.md) 中的 README、sales.csv、report.py。报表故意只累加单价，输出 27.00；乘上数量后的正确金额为 43.50。这是教学输入，不应在维护 Agent 时顺手修掉。

可以依次要求“只分析原因”“修复并验证”“查阅 Python Decimal 官方资料”。工具返回真实结果；写入和执行是否需要人工确认取决于受信 `access_policy`，不能承诺所有模式都弹审批。

## 阅读顺序与模块

| 文件 | 职责 / 应学习的边界 |
|---|---|
| [agent.py](agent.py) | 唯一组合根：探测/执行分流、身份与 Context、受管模型、工具及 middleware 装配 |
| [prompts.py](prompts.py) | 主角色和子角色的业务指令 |
| [backend.py](backend.py) | 工作区准备、文件 Backend、公共执行适配；不重建资源调度 |
| [subagents.py](subagents.py) | research、general-purpose 及有 chart_tools 时的 chart-agent |
| [tools.py](tools.py) | 本服务的受限 HTTPS 文档抓取 |
| [chart.py](chart.py) → [公共 chart.py](../../../tools/chart.py)、[chart-schemas.json](../../../tools/chart-schemas.json) | 服务兼容导出与公共 AntV MCP schema、调用及图片落盘；探测不启动外部进程 |
| [skills/showcase-notes/SKILL.md](skills/showcase-notes/SKILL.md) | 按需加载的任务知识，不授予执行权限 |

稳定入口为 [graphs/showcase_demo.py](../../../graphs/showcase_demo.py)，在服务工厂外包装 scheduled_execution 与 background_completion_execution。正式 `langgraph.json` 和 `langgraph.demo.json` 均注册本图；不能继续按旧版“仅 demo、只重导出”接线。

## 平台装配与权限

Agent 循环、task、文件工具、Skills 和 interrupt/resume 复用框架。平台层显式接入 RuntimeConfig、受管模型容错、Workspace、Token/调用/时间预算、Plan、消息与后台能力、隐私、上下文治理、公共文档/图片/MCP 和观测。精确启用条件与顺序以 agent.py 及 [组合测试](../../../../../tests/services/showcase_demo/) 为准，不能用早期“只有少量封装”清单替代。

Context 不接受 tools。模型参数、execution_mode/access_policy、offload 和 Plan 等字段以 [RuntimeContext](../../../runtime/contracts.py) 为准；目录、defaults、实际工具集与签名禁用项须一致，新增工具不存在 internal 绕过。

- research：ls/read_file/glob/grep，只读，无执行。
- general-purpose：文件读写和执行，无再次 task 或额外网络工具。
- chart-agent：仅在图表能力已装配时提供，文件只读加图表工具，无 shell/任意写文件/再次委派。

角色工具可见性与执行授权都要检查。Workspace 绑定可信 tenant/project/thread；审批不替代授权。不要缓存包含某次运行身份或资源的图。

## Workspace、执行与恢复

文件工具使用 `/workspace/...` 虚拟路径，shell 使用工作区相对路径，如 `python report.py`。Skills 使用只读资源路由，不能给 shell 授予包目录访问权。工作区文件独立于 checkpoint，恢复 checkpoint 不回滚真实文件。

`backend.py` 的 Docker 路径委托公共 `workspace/execution.py:execute_in_workspace`。执行目标、remote 模式、租约、资源登记、清理和存储要求以 [沙箱手册](../../../../../../../docs/runbooks/runtime-sandbox-node.md) 和 [Workspace/停止规则](../../../../../docs/standards/runtime-service-development-standard.md#workspace-执行目标与恢复) 为准；不再假设每条命令后删除容器或所有部署都共享同一宿主挂载路径。Thread 回收沿 [保留与删除专项](../../../../../../../docs/projects/20261030-session-and-runtime-retention-governance/README.md)。

LocalShellBackend 仅供受信本地开发，不隔离宿主文件、网络或 CPU/内存。该适配允许 1–60 秒超时；同步线程无法强杀，取消不保证立即结束命令及子进程，资源回执可能 unconfirmed。Docker/remote 失败不能回退宿主 shell。

## 预算与失败

当前默认模型次数为每 Run 50、每 Thread 500，工具为每 Run 100、每 Thread 1000；分别可通过 AGENT_MODEL_CALL_LIMIT_PER_RUN/THREAD、AGENT_TOOL_CALL_LIMIT_PER_RUN/THREAD 调整。主子角色各自计数，不宣称是全局合计额度。模型单次超时按受管 policy 解析，不再固定写成 30 秒。

正式软收尾使用受信 Worker attempt 的 RunBudget；内部重建和子 Agent 不能重新起表。旧 `resolve_wrapup_after_seconds()` 是无 RunBudget 的本地调用兼容路径，不是生产接入示例。Token 累计、上下文窗口、模型次数、工具次数、supersteps 和时间预算是不同约束，见 [现行预算规则](../../../../../docs/standards/runtime-service-development-standard.md#run-时间预算与收尾)。

工具和模型的可恢复错误沿公共分类处理；取消、权限、隐私和未知结果不伪装成功。完成标记或额度停止不等于业务目标已全部完成。

## 图片、文档与 MCP

主图显式装配公共 ImageToolsMiddleware 与 DocumentToolsMiddleware。图片能力含生成、编辑和分析；副作用审批按 access_policy，视觉模型选择按当前服务配置/受管路径，不能把“只用豆包”当成永久接口限制。图片/文档工具复用线程引用和公共安全校验，不接收任意宿主路径；生成付费请求不能盲目重试。

chart-agent 通过官方 task 和 MCP adapter 使用锁定的 AntV schema，图片转存到线程工作区。外部图表服务可能处理图表数据，不能宣称纯本地计算。schema 随包发布；升级时同步 schema 与格式测试。

项目知识 MCP 沿 [公共规范](../../../../../docs/standards/project-knowledge-mcp.md) 显式挂载，服务端绑定和工具策略决定可用性。外部发现失败隔离不意味着授权校验可以跳过。

## 运行与验证

本地栈和模型/认证配置先按 [运行与验证](../../../../../docs/standards/runtime-service-onboarding-and-verification.md) 准备；关联 Worktree 必须先遵循 [资源隔离规范](../../../../../../../docs/standards/worktree-development.md)。当前锁定版本看应用 pyproject.toml/uv.lock，不用本 README 固定某个旧 post 版本。

探测图保留相同 schema，但不创建工作区、请求模型目录或启动 Docker；正式 checkpointer 由底座提供。运行时 Context、受管模型和身份沿平台链路，不能开放 `_runtime_test_*` 给浏览器。

在应用目录按范围运行：

```bash
# 确定性组合测试
uv run pytest tests/services/showcase_demo -m "not integration and not e2e"
# 需要真实 Docker 等隔离资源
uv run pytest tests/services/showcase_demo -m integration
# 图片/图表的非外部验收
uv run pytest tests/services/showcase_demo/test_images_chart.py -m "not e2e"
```

外部模型/图片测试会发生真实调用和费用；所需开关与条件以 test_agent.py、test_images_chart.py 的 skip/marker 为准，不把 skip 记为通过。重启验收入口为应用 `scripts/showcase_acceptance.py`，需要独立 DB/Redis、模型和执行环境；先按运行指南准备，不在默认共享环境直接迁移。

重点核对：探测无副作用、工具授权、角色缩权、Skills 只读、真实文件变化、Todo、审批与恢复、取消及预算。HITL 的 action_requests 与 decisions 数量/顺序应一致；多个 interrupt 以实际 ID 恢复。子 Agent 使用父 Run 与独立 namespace，不是另一个平台 Run。

早期端到端结果保留在 [Showcase 验证记录](../../../../../../../docs/projects/20260908-showcase-demo/verification.md)，后续能力需读各自专项。本文于 2026-11-08 按源码修订，未重新执行产品或外部服务测试。
