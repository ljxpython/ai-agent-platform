# Agent 接入通用后台 Workspace 任务

当前实现见 `tools/background.py`、`background_tasks/` 与 `workspace/background.py`；与 DearFlow 业务模式、媒体供应商和外部部署无关。当前支持单执行主机受管 Docker；LocalShell、只读子图与 Reference/Workflow 不支持启动。发布限制见 [专项](../../../../docs/projects/20261009-agent-generic-production-capabilities/README.md)。

## 四个明确接入点

1. 组合根生成 `BackgroundBinding(workspace, image, scope, graph_id, skills, protected)`，路径必须来自现有已验证 Workspace，不能从用户工具参数指定。技能 snapshot 在 before-agent 才准备时传 binding lambda，执行时读取当前 snapshot；DearFlow 是实例。
2. 将 `build_background_tools(binding, completion=...)` 返回的工具装到根 Agent，并使用既有 `RuntimeConfigMiddleware`。普通 execute 保持同步等待；后台启动入口保留在 ToolNode 以处理旧 checkpoint，模型可见性按下面的配置门禁过滤。完成通知 Run 不装配 `background_execute`，不得开启新的后台任务链。业务使用方协调同一文件的并发写，本能力不提供 DAG/全 Workspace 事务。
3. 在该图 tool catalog/allowlist 中声明 `background_execute/background_task/cancel_background_task`；execute deny 同时禁止后台启动。review 对启动/取消保留官方 HITL；workspace_write/full_access 只按现有项目政策免审批。capability 只声明支持，不能授予权限；只读子图不继承三工具。
4. `graphs/{agent}.py` 用 `background_completion_execution(factory, agent_key=...)` 包装入口；可与现有 scheduled wrapper 共存，但 completion/cron marker 不能混用。guard 必须早于模型、MCP、Workspace 构造，复核签名/Context/当前授权/Stop。

```python
from runtime_service.runtime.background_completion import background_completion_execution
from runtime_service.tools.background import build_background_tools
from runtime_service.workspace.background import BackgroundBinding

binding = lambda: BackgroundBinding(
    workspace.root, image, workspace.scope, "my_agent", workspace.skills_root, True
)
tools = build_background_tools(binding, completion=bool(configurable.get("platform_background_completion")))
get_agent = background_completion_execution(get_agent, agent_key="my_agent")
```

以上变量来自组合根已验证身份和 Workspace；示例不是新的 Builder/Registry。服务 `webapp.py` 统一注册路由与 lifespan，不给每图建 cron 或 Agent polling loop。新图还需在平台 catalog 注册并验证当前模型/tool/Thread 授权；completion 提交仍经现有 launch_runtime_run。

## 工具契约

- `background_execute(command, timeout=900)`：返回真实登记/启动 Task v1，期限 1-3600 秒。同 origin Run/checkpoint namespace/tool_call 重放返回同 task，命令或 binding 摘要变更冲突。ACK 不代表命令完成；unknown 不自动再执行。
- `background_task(action="list"|"status"|"output", task_id=...)`：只读取当前五维 scope；list 不接受 task_id。output 为 16 KiB 有界纯文本，不解析授权或状态。
- `cancel_background_task(task_id)`：持久取消意图，清理结果通过查询确认；不要把 CancelledError 转成成功 ToolMessage。

## 非 Docker 兼容与精确降级

`background_tasks/capabilities.py` 是配置能力判断的公共入口：`background_tasks` 要求配置 `DATABASE_URI`；`background_tasks_start_enabled` 另要求 `RUNTIME_BACKEND=docker`、新提交开关为 `1`、有效 `RUNTIME_EXECUTION_HOST_ID`。这些判断不连接数据库或 Docker，也不创建 Workspace；配置能力不代表服务健康或执行授权。

`RuntimeConfigMiddleware` 在每次模型调用前隐藏不可用的后台工具；非 Docker、开关关闭、缺 host 时模型仍可使用已有前台 `execute`。内部启动入口保留，以免重建 Agent 后旧 checkpoint 得到“未知工具”并丢失原回执。无任务存储配置时查询工具及任务 Tab 隐藏；只关闭新启动时，查询、日志、授权取消和原执行域内对账保留。Platform 继续按当前 ACL/tool 策略进一步收窄新启动权限。

启动先按可信 Run/checkpoint namespace/tool_call key 读取原记录，再用记录的原 execution host 核对原有请求与 Workspace/skills 摘要。同请求返回原 task（含 unknown），异请求冲突。数据库成功确认无记录且源 Run 未被 Stop 拒绝后，非 Docker、关闭开关或无有效 host 才抛 `BackgroundTaskNotStarted`，由既有 ToolErrorMiddleware 返回 `outcome=not_started` 和短任务改用 execute 的提示。execute 仍默认 30 秒、最大 60 秒，并保留权限/HITL；长任务需拆分或使用受支持环境。

数据库缺配置/不可读、身份与权限、审批/Stop、取消、程序错误及登记后的故障均不能按错误码泛化降级；unknown 不建议前台重跑。Docker 故障不自动落宿主 shell。API/Worker 继续遵守同一执行域及一致配置的部署要求；滚动切换执行 backend 不提供跨拓扑原子交接。

origin_run_id 必须取可信 execution_info 或引擎 metadata 并核对一致；普通公开 context/工具参数不能提供身份、容器或私有 marker。通知提示只含 task/event/source Run 与安全终态，不注入原始日志。

## 最小接入验证

检验 schema-only/probe/maintenance 零资源；配置矩阵与模型可见工具/平台 capability 一致；错误 scope、execute deny、拒绝审批零启动；审批 resume 保留 call/命令摘要；关闭启动后重建 checkpoint 仍核对原 task、unknown 零重复；源 success 延续、error/timeout/Stop 清理，HITL interrupted 不误取消。完成 Run 的 guard 拒绝发生在 factory 前，新提交工具不可见。验证打包资源、真实 Docker 输出/退出码、两进程恢复、公开四路由、当前权限与 Stop 摘要。

部署、容量、日志 TTL 与 drain 见 [运行手册](../../../../docs/runbooks/runtime-background-tasks.md)。post43 lost-ACK 固定回执缺口仍阻止正式启用；接入新 Agent 不会自动消除此门禁。
