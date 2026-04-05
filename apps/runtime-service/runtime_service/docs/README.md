# runtime_service 文档入口

`runtime_service` 是 `runtime-service` 的执行层，负责 graph 注册、运行时参数解析、模型与工具装配、鉴权以及附加能力路由。

## 新成员先读什么

推荐阅读顺序：

1. `docs/02-architecture.md`
2. `agents/assistant_agent/graph.py`
3. `agents/deepagent_agent/graph.py`
4. `agents/personal_assistant_agent/graph.py`
5. `docs/archive/02-runnableconfig-vs-serverruntime.md`
6. `docs/04-agent-scaffold-templates.md`
7. `docs/05-template-to-runnable-agent-10min.md`
8. `docs/03-agent-development-playbook.md`
9. `docs/07-service-modularization.md`
10. 按专题再读鉴权、多模态与其他文档

其中：

- `agents/assistant_agent/graph.py`：当前推荐的 assistant 开发范式
- `agents/deepagent_agent/graph.py`：deepagent 范式参考模板
- `agents/personal_assistant_agent/graph.py`：subagent / supervisor 协作范式参考模板
- `agents/assistant_agent/graph_legacy.py`：历史实现，仅保留兼容与参考价值
- `agents/assistant_agent/graph_entrypoint.py`：兼容导出文件，避免旧引用立刻失效

## 当前 graph 一览

- `assistant`：默认主入口，推荐基于它继续演进
- `deepagent_demo`：深任务分解范式
- `customer_support_handoffs_demo`：步骤式状态流范式
- `personal_assistant_demo`：supervisor + subagent 范式
- `research_demo`：deepagent 研究范式（research_agent 私有 skills + 可选 Tavily MCP）
- `skills_sql_assistant_demo`：middleware + skills 范式
- `usecase_workflow_agent`：业务工作流范式，当前实现见 `services/usecase_workflow_agent/README.md`，后续重构计划见 `services/usecase_workflow_agent/refactor-plan.md`
- `test_case_agent`：测试用例分析与正式持久化服务，设计见 `docs/10-test-case-service-persistence-design.md`

graph 注册以 `runtime_service/langgraph.json` 和 `runtime_service/langgraph_auth.json` 为准。

## 本地启动

在 `apps/runtime-service` 目录执行：

```bash
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser --allow-blocking
```

说明：

- `research_demo`、`deepagent_demo`、`test_case_agent` 这类依赖 Deep Agents 文件后端/skills 的 graph，在当前本地 `langgraph-api 0.7.58` 下需要 `--allow-blocking`，否则容易被 `blockbuster` 拦成 `BlockingError`。
- 如果是部署环境，可以在 `langgraph.json` 中直接使用内联 `env`：

```json
{
  "env": {
    "BG_JOB_ISOLATED_LOOPS": "true"
  }
}
```

- 容器环境也可以直接在启动前设置：

```bash
export BG_JOB_ISOLATED_LOOPS=true
```

- 需要注意：`BG_JOB_ISOLATED_LOOPS=true` 对后台 worker/部署环境有价值，但单独配置它并不能替代当前本地 dev 的 `--allow-blocking`。

常用验证：

```bash
curl -sS -X POST http://127.0.0.1:8123/assistants/search -H "Content-Type: application/json" -d '{}'
curl -sS http://127.0.0.1:8123/internal/capabilities/tools
curl -sS http://127.0.0.1:8123/internal/capabilities/models
```

## 多模态自测（devtools）

`runtime_service/devtools/` 是开发期自测用的辅助脚本集合，不属于生产运行时逻辑；它的目标是让后端在不依赖前端的情况下复现/检查多模态输入。

- `runtime_service/devtools/multimodal_frontend_compat.py`：把 PDF / 图片等原始输入编码为「前端形状」的 content blocks，便于本地自测。
- `runtime_service/devtools/dump_multimodal_fixtures.py`：遍历并输出 fixtures 的原始 bytes 与（如有）PDF 文本提取结果。
- `runtime_service/tests/multimodal_selfcheck.py`：直接走一遍 `MultimodalMiddleware` 的解析与改写链路，适合单文件调试。

运行命令：

```bash
./.venv/bin/python -m runtime_service.devtools.dump_multimodal_fixtures
uv run python runtime_service/tests/multimodal_selfcheck.py --file runtime_service/test_data/11a1f536fbf8a56a69ffa6b298b2408d.jpeg
uv run python runtime_service/tests/multimodal_selfcheck.py --file runtime_service/test_data/12-多轮对话中让AI保持长期记忆的8种优化方式篇.pdf
```

fixtures 存放在 `runtime_service/test_data/`。

## 运行时最小心智模型

- graph 入口统一从 `langgraph.json` 注册
- 运行时参数主要经由 `runtime/options.py` 解析
- 模型装配在 `runtime/modeling.py`
- 工具装配在 `tools/registry.py`
- MCP server 清单在 `mcp/servers.py`
- 自定义 HTTP 路由在 `custom_routes/`
- 鉴权逻辑在 `auth/provider.py`

最常用运行时参数：

- `model_id`
- `system_prompt`（仅用于外部覆盖；未提供时由各 graph 自己回退到业务默认 prompt）
- `enable_tools`
- `tools`
- `temperature`
- `max_tokens`
- `top_p`

## 文档分工

- `docs/02-architecture.md`：稳定运行时契约与目录边界
- `docs/archive/02-runnableconfig-vs-serverruntime.md`：流程背景资料与设计上下文
- `docs/01-auth-and-sdk-validation.md`：鉴权模式与验证方法
- `docs/03-agent-development-playbook.md`：三种主模式的团队规范与选型规则
- `docs/04-agent-scaffold-templates.md`：三种主模式对应的脚手架模板
- `docs/05-template-to-runnable-agent-10min.md`：从模板到可运行 graph 的最小落地流程
- `docs/06-multimodal-middleware-design.md`：当前多模态实现状态与扩展边界
- `docs/07-service-modularization.md`：同一运行时内的业务服务模块化规范
- `docs/08-middleware-development-playbook.md`：middleware 目录组织、生命周期钩子与测试规范
- `docs/09-test-case-service-skills-troubleshooting.md`：test_case_service 的 skills / 多模态问题排查
- `docs/10-test-case-service-persistence-design.md`：test_case_service 与 interaction-data-service 的新持久化范式
- `docs/11-testcase-platform-workspace-design.md`：Testcase 平台工作区、管理接口与页面结构的一期设计

## 开发约定

1. 优先参考活代码，不先参考抽象模板
2. 默认以 `assistant_agent/graph.py` 为 create_agent 推荐范式
3. 复杂任务分解参考 `deepagent_agent/graph.py`
4. subagent / supervisor 协作参考 `personal_assistant_agent/graph.py`
5. 流程文档优先参考 `docs/archive/02-runnableconfig-vs-serverruntime.md`、`docs/04-agent-scaffold-templates.md`、`docs/05-template-to-runnable-agent-10min.md`
6. 显式步骤流可额外参考 `customer_support_agent/graph.py`
7. 业务服务模块化开发规范见 `docs/07-service-modularization.md`
8. middleware 开发规范见 `docs/08-middleware-development-playbook.md`
9. 改完代码后至少跑相关 pytest 与 `python -m compileall runtime_service`
