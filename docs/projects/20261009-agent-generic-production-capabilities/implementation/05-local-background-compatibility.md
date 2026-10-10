# 非 Docker 后台任务兼容：A 主方案 + B 精确兜底

**实施日期：** 2026-10-10；任务 AB01-AB03，用户已批准。实际开发、依赖、数据库与浏览器均属于指定 Worktree。引擎按 key 接受回执与平台接线由并行工作负责，本记录只覆盖 A/B。

## A：能力判断与模型工具可见性

- 新增 `apps/runtime-service/src/runtime_service/background_tasks/capabilities.py::{query_enabled,start_enabled}`：查询要求任务数据库配置；新启动再要求 docker、开关 `1` 和有效 host ID。仅读取配置，不探测数据库、Docker 或 Workspace。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/capabilities.py::graph_capabilities()` 复用公共判断，两图的查询/新启动能力分别投影；未接入图保持 false。
- `apps/runtime-service/src/runtime_service/middlewares/runtime_config.py::RuntimeConfigMiddleware.awrap_model_call()` 在已有权限过滤后隐藏不可用工具。`apps/runtime-service/src/runtime_service/tools/background.py::build_background_tools()` 保留内部启动入口供 checkpoint 重放，查询工具仅在有存储配置时装配；completion 不装配启动工具。
- 完全移除 ToolNode 启动入口会让配置关闭后重建的旧 checkpoint 返回未知工具，不能检查原任务。两组合根新增先中断工具节点、切 local/关闭开关、重建并恢复的测试，保留入口后模型仍看不到启动工具，原 unknown 回执可返回。
- Platform/Web 原有 capability 消费已经区分查询和新启动：只关新启动时任务 Tab 保留；无查询能力才隐藏。新增平台契约回归，不复制权限逻辑或增加前端启动表单。

## B：只在确认未登记时恢复

`apps/runtime-service/src/runtime_service/background_tasks/service.py::start_task()` 的顺序从“先检查环境再查回执”改为“校验输入、可信 key 读取回执、核对原摘要、最后检查新启动条件”。原 task 使用记录中的 `execution_host_id` 重算旧摘要；同请求返回 running/unknown/终态，改变命令、timeout、Workspace、skills 或 protected 仍冲突。没有摘要迁移、删除或自动重跑。

`apps/runtime-service/src/runtime_service/background_tasks/repository.py::read_submission()` 在查无记录时复用 `run_control.repository.inbox_blocked()` 检查源 Stop；`reserve_task()` 复用同一检查。数据库成功查无记录且源未被 Stop 拒绝后，非 Docker、关闭开关或无有效 host 才产生 `apps/runtime-service/src/runtime_service/runtime/errors.py::BackgroundTaskNotStarted`。

`apps/runtime-service/src/runtime_service/tools/errors.py::tool_error_content()` 在 Fatal 分支之前只恢复专门异常、`background_execute` 以及两个环境限制码，复用原结构化工具错误：`outcome=not_started`、`recovery=use_execute_for_short_task`。提示普通 execute 默认 30 秒、最大 60 秒；长任务拆分或使用受支持环境。相同码的普通 Workspace 异常、数据库故障、权限、审批/Stop、取消和登记后错误不被吞掉。Docker 故障不会自动调用 local shell。

`background_tasks_lifespan()` 允许没有数据库/host 的显式 local 调试启动；原执行域关开关后的对账保持既有语义。API/Worker 仍要求一致配置和相同执行域，跨 backend 滚动切换不提供原子交接。

## 验证位置

- Runtime：`tests/background/{test_tools_and_assembly,test_service,test_repository,test_compatibility}.py`。新增六配置 × 两图矩阵、精确失败/取消边界、真实 PG 原回执/Stop、两真实组合根以及重建 checkpoint。
- Probe 必要回归：`tests/services/{showcase_demo,dearflow_agent}/test_agent.py` 两处旧 `fetch_model_connection` 夹具改为当前 `fetch_model_bundle`；业务代码未重构。
- Platform：`apps/platform-api/tests/test_background_capabilities.py`，运行时关闭新启动、execute deny 与只读 ACL 不关闭查询。
- 非前端 E2E：本环境 `.local-stack/ab-local-api-check.py`，真实 Platform API/Runtime API/Worker/受管模型/审批/前台 execute 和任务查询，两图均 success；脱敏事实见 `verification.md` 的 AB03 记录。本轮未修改 Web 产品源码。
- Web：已有后台组件/服务 Vitest 定向回归通过。`apps/platform-web/e2e/background-compatibility.draft.ts` 是未通过的浏览器交接草稿，不进入默认测试收集；查询探针门禁、短任务恢复提示和浏览器收口由前端交接承接。

实际命令、数量、失败重试及 mock 边界统一记在 [Phase 验证](../verification.md)。非前端 A/B 与交接已 done；浏览器未通过及 qwen 空工具 ID 导致旧 sanitizer 丢回执的问题均明确交接。进度只看 [tasks.md](../tasks.md)；B01 与专项 Final 不能由本轮通过替代。
