# Showcase Demo 接入

## 目标
让 `showcase_demo` 展示公共图片工具和图表子 Agent 的标准装配方式，同时保持现有组合根、审批和运行时边界。

## 方案设计
- `agent.py` 继续作为唯一组合根，装配公共图片工具和 chart-agent。
- `subagents.py` 增加 chart-agent，不修改现有 research/general-purpose 角色职责。
- `prompts.py` 补充图片和图表能力的使用规则，明确何时识别、生成和委派。
- `tools.py` 不复制公共图片实现。
- README 补充 workspace 路径、审批行为、环境变量和示例请求。

## 任务拆分
- [x] 在 showcase_demo 装配公共图片工具。
- [x] 装配 chart-agent 并更新主 Agent 指令。
- [x] 更新 Demo README 和环境变量说明。
- [x] 增加 fake model/MCP adapter 测试，真实外部调用单独标记 e2e 并显式 opt-in。

## 验证要求与记录
- [x] 单元测试覆盖装配、权限和审批配置。
- [x] 集成测试覆盖文生图、图片识别和图表 MCP 三条路径。
- [x] Runtime 内端到端验证主 Agent → chart-agent → MCP 的完整委派链路。
- [x] 验证现有文件分析、修改、执行和审批测试不回归。

2026-09-13 验证：
- `pytest tests/services/showcase_demo tests/middlewares/test_runtime_middleware.py tests/runtime/test_runtime_config_validation.py -m "not integration and not e2e" -q`：55 项通过，5 项 deselected（51.85 秒；外部测试另行执行，不把 deselected 当通过）。
- `pytest tests/services/showcase_demo -m integration -q`：2 项通过，真实 Docker 执行与隔离。
- 图片生成审批→识图→MCP 的真实外部链路：1 项通过（131.12 秒）。
- 真实主模型自主图表委派：1 项通过（47.90 秒）。
- 公共图片工具、图片 Middleware、MCP 模块通过 mypy 检查；改动代码执行 Ruff 检查。
- 现有部署未重启，未测试浏览器图片展示、Server 审批重启恢复；它们不属于本次 Runtime 能力接入的完成声明。

## 状态
done（Runtime 接入范围）
