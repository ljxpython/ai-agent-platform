# Phase 2: 核心实现

## 改动时间
2026-09-08

## 相关任务
- Task 2.1: 创建 agent.py — 认证与运行时配置
- Task 2.2: 创建 agent.py — create_deep_agent 配置
- Task 2.3: 创建 `__init__.py`
- Task 2.4: 注册 showcase_demo 到 Demo 路由表

## 改动文件
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py` (New)
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/__init__.py` (New)
- `apps/runtime-service/src/runtime_service/graphs/showcase_demo.py` (New)
- `apps/runtime-service/langgraph.json` (Modified)

## 具体改动

### 1. 创建 agent.py 并配置
**位置：** `agent.py`
**改动内容：**
- 定义了 `research_subagent` 和 `implementor_subagent`，分别携带对应的 mocked tools。
- 使用 `create_deep_agent` 生成 graph，指定了 `interrupt_on` 为 `write_project_file` 和 `execute_command`。
- 将 graph ID 设为 `showcase_demo`。

**理由：** 实现完整 capabilities 的综合 demo。

### 2. 添加 entrypoints 并注册到 langgraph
**位置：** `__init__.py`, `graphs/showcase_demo.py`, `langgraph.json`
**改动内容：**
- 暴露了 `get_agent`。
- 在 `langgraph.json` 中配置 `"showcase_demo"` 指向 `src/runtime_service/graphs/showcase_demo.py:get_agent`。

**理由：** 保证前端（或客户端测试）可以通过统一的 langgraph server 或引用查找到 `showcase_demo` 图配置。

## 验证
- [x] 配置正确无误。
