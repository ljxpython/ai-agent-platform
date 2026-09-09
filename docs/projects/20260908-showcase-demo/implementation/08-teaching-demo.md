# 教学 Demo 收敛记录

日期：2026-09-09。关联 T1–T9；用户已采纳审查结论并授权实施。

## 实现

所有服务路径以下相对于 `apps/runtime-service/src/runtime_service/`。

| 位置 | 原行为 → 当前行为及原因 |
| --- | --- |
| `services/demo/showcase_demo/agent.py:get_agent` | 单个庞大展示入口 → 校验身份、Context、模型和 scope 后显式组合官方组件；无身份仅提供不可执行、无 IO 的探测图 |
| `services/demo/showcase_demo/prompts.py` | 散落展示指令 → 明确只读分析和实现任务，不按关键词强制跑流程 |
| `services/demo/showcase_demo/subagents.py:build_subagents` | 隐式角色权限 → research 只读、general-purpose 实现，显式工具集、审批、调用预算 |
| `services/demo/showcase_demo/backend.py:DockerWorkspaceBackend` | 固定成功执行与机器路径 → 按租户/项目/线程隔离真实目录、Docker 命令执行；官方文件工具保持原生 |
| `services/demo/showcase_demo/backend.py:build_backend` | 宿主路径作为 Skills 参数 → 包资源映射 `/skills/`，模型使用稳定虚拟路径 |
| `services/demo/showcase_demo/tools.py:fetch_documentation` | 可读 file:// → 有站点白名单、大小限制、不跟重定向的 HTTPS 文档抓取 |
| `middlewares/runtime_config.py:37` | 服务自行绕过授权 → 角色工具集与 Runtime allowlist 求交，模型及工具执行边界均检查 |
| `runtime/modeling.py:97` | 服务组合根内取连接 → 公共 `fetch_model_connection`，校验模型引用及返回字段，失败不泄露凭据 |

Todo 使用 `TodoListMiddleware` 的真实 State；移除空业务 State 和假执行工具。`examples/` 提供真实 CSV 报表，初始漏乘数量是明确标注的教学输入缺陷（27.00 → 43.50），不是正式能力 mock。

`pyproject.toml` 打包 README、Skills 与 examples；`.env.example` 声明工作区数据根和 Docker 镜像。showcase 从 `langgraph.json` 移到 `langgraph.demo.json`，对应能力注册测试同步。其他 Agent 注册保持原状。

## 行为测试与教学文档

旧 `tests/demo/test_showcase_demo.py` 被 `tests/services/showcase_demo/{test_agent,test_backend,test_tools}.py` 的行为验证替代。fake 模型/HTTP transport 仅在测试中用于稳定覆盖分支，正式工具执行真实操作；另外提供真实 Docker 和可选真实模型检查。

Demo `README.md` 解释每个模块、官方能力来源、开发借鉴方式、权限、部署路径、流式/审批和持久化限制。核心项目文档撤回旧“全完成”结论，任务与功能总览按当前证据更新；历史报告保留但不再作为事实源。

## 验证结果

相关回归 151 passed（含 Docker），真实模型 1 passed；定向 Ruff lint 和 Demo 格式检查通过；干净 wheel 安装后的资源与 schema 探测通过。命令、耗时和未验收边界统一见 [verification.md](../verification.md)。

公共模块的已有无关改动保留，不做全文件格式清理。没有新增通用 Builder、Registry、调度服务或替代官方 Agent 循环；未提交或切换分支。
