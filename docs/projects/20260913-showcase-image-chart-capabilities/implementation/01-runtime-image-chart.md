# Runtime 图片和图表能力接入

日期：2026-09-13。用户已确认公共图片工具、线程落盘、文生图审批、豆包兼容接口、Runtime 内部授权，并在模型检查后同意实施。

## 实现位置

- `apps/runtime-service/src/runtime_service/tools/images.py`：`ImageWorkspace` 绑定可信线程根目录；`build_image_tools` 提供生成和识图。路径通过目录描述符逐层打开，拒绝符号链接与越界，图片限制大小和像素。provider 错误去除凭据与响应正文。
- `apps/runtime-service/src/runtime_service/middlewares/images.py`：`ImageToolsMiddleware` 复用官方 HITL，挂载图片工具和每次文生图审批。其他 Agent 复用时传入绑定的 workspace。
- `apps/runtime-service/src/runtime_service/middlewares/runtime_config.py`：增加仅限可信组合根传入的 `internal_tool_names`；在平台既有工具集合之外加入本地声明，再与角色工具集合求交。身份、Context 哈希、模型授权、assistant/thread scope 检查照常执行。旧调用方默认空集合，保持原行为。
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/chart.py`：官方 MCP tool adapter + 结果拦截器；AntV 图片 URL 下载后存为线程产物。使用 `@antv/mcp-server-chart@0.9.10`，每次会话由官方适配器创建和清理，无自建进程池。启动/下载失败返回原生 MCP 错误结果，避免适配器重新抛出普通 ToolException。
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/chart-schemas.json`：实测版本的 schema 快照，支持离线构图和无网络 schema 探测；电子表格工具不装配。升级需同步快照。
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py`、`subagents.py`、`prompts.py`：主 Agent 挂载图片 Middleware，chart-agent 独占图表工具、仅额外具有只读文件权限。
- `apps/runtime-service/pyproject.toml`：将 schema 快照纳入 wheel，无新增运行依赖。
- `apps/runtime-service/tests/services/showcase_demo/test_images_chart.py`：审批、拒绝、识图只读、符号链接、下载限制、角色隔离、结果落盘及 opt-in 真实链路检查。

## 明确的语义调整

旧逻辑：所有工具必须由上层 policy/principal 授权。

新逻辑：旧工具保持原规则；新增图片/MCP 工具由组合根固定管理。`Context.tools=[]` 只禁用既有受管工具，不能禁用新增内部工具。主 Agent 的 `task` 仍遵循已有授权，不扩大为全仓库工具治理迁移。

识图直接返回文本，不写 `/workspace/analysis/*.json`，以兑现“无需审批、只读”的约定；之前初稿的分析落盘描述予以修正。

AntV 实测原始结果：`content` 为文本图片 URL，`artifact=null`。不能将 LangChain ToolMessage 的外壳误认为 MCP 返回结构化图片 artifact。

图片生成中转配置为 `gpt-image-2.5-flare`，仅证明该中转接口的行为，不断言底层官方模型身份。

## 验证状态

Runtime 范围 done；结果分别记录至 01/02/03 专题。55 项确定性检查、2 项 Docker 集成检查、真实图片/识图/MCP 链路和真实主模型自主委派均已通过。未部署，未把平台浏览器或 Server 重启验收算作通过。
