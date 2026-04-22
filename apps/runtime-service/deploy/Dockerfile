FROM langchain/langgraph-api:3.13

# Repo-managed Dockerfile for runtime-service container delivery.
# This file is based on the current LangGraph dockerfile generation pattern,
# but is checked into the repo so end users can build without local CLI setup.

# -- Adding local package ./ --
ADD ./ /deps/runtime-service
# -- End of local package ./ --

# -- Installing all local dependencies --
RUN for dep in /deps/*; do \
        echo "Installing $dep"; \
        if [ -d "$dep" ]; then \
            (cd "$dep" && PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir -c /api/constraints.txt -e .); \
        fi; \
    done
# -- End of local dependencies install --

ENV LANGGRAPH_HTTP='{"app": "/deps/runtime-service/runtime_service/custom_routes/app.py:app", "cors": {"allow_origins": ["*"], "allow_methods": ["*"], "allow_headers": ["*"], "allow_credentials": false}}'
ENV LANGSERVE_GRAPHS='{"assistant": {"path": "/deps/runtime-service/runtime_service/agents/assistant_agent/graph.py:graph", "description": "默认助手主入口：基于 create_agent 的推荐范式，内置 HumanInTheLoopMiddleware 与多模态处理中间件。"}, "customer_support_handoffs_demo": {"path": "/deps/runtime-service/runtime_service/agents/customer_support_agent/graph.py:graph", "description": "客服交接演示：通过状态机步骤（保修收集→问题分类→方案处理）驱动 handoff 流程。"}, "deepagent_demo": {"path": "/deps/runtime-service/runtime_service/agents/deepagent_agent/graph.py:graph", "description": "deepagent 统一入口：包含 subagents + skills 的深度任务分解执行，并合并了本地数据分析产物工作流能力。"}, "personal_assistant_demo": {"path": "/deps/runtime-service/runtime_service/agents/personal_assistant_agent/graph.py:graph", "description": "个人助理演示：calendar/email 子代理协同，由 supervisor 统一调度。"}, "research_demo": {"path": "/deps/runtime-service/runtime_service/agents/research_agent/graph.py:graph", "description": "研究助手演示：基于 deepagent 的研究任务分解流程，支持 research_agent 私有 skills 与可选 Tavily MCP 检索工具。"}, "skills_sql_assistant_demo": {"path": "/deps/runtime-service/runtime_service/agents/skills_sql_assistant_agent/graph.py:graph", "description": "SQL 技能助手演示：middleware 注入技能目录，按需 load_skill 加载 schema 与业务规则。"}, "sql_agent": {"path": "/deps/runtime-service/runtime_service/services/sql_agent/graph.py:graph", "description": "SQL 问答服务：基于内置 Chinook SQLite 示例库的只读查询 Agent，自动完成表发现、schema 检查、SQL 生成、自检与执行。"}, "test_case_agent": {"path": "/deps/runtime-service/runtime_service/services/test_case_service/graph.py:graph", "description": "测试用例分析智能体：基于 create_deep_agent + 私有 Skills 体系，支持需求分析、测试策略制定、用例设计、质量评审与格式化输出，多模态输入（图片/PDF）通过 MultimodalMiddleware 解析。"}, "test_case_agent_v2": {"path": "/deps/runtime-service/runtime_service/services/test_case_service_v2/graph.py:graph", "description": "测试用例分析智能体 V2：基于独立的 create_deep_agent + 私有 Skills 体系，使用 LightRAG project-scoped MCP 进行知识检索，支持需求分析、测试策略制定、用例设计、质量评审与格式化输出。"}}'

# Keep env-file loading in compose/runtime config. This image only sets the
# graph/http registry and installs the app package.

# -- Ensure user deps didn't inadvertently overwrite langgraph-api --
RUN mkdir -p /api/langgraph_api /api/langgraph_runtime /api/langgraph_license \
    && touch /api/langgraph_api/__init__.py /api/langgraph_runtime/__init__.py /api/langgraph_license/__init__.py
RUN PYTHONDONTWRITEBYTECODE=1 uv pip install --system --no-cache-dir --no-deps -e /api
# -- End of ensuring user deps didn't inadvertently overwrite langgraph-api --

# -- Removing build deps from the final image --
RUN pip uninstall -y pip setuptools wheel
RUN rm -rf /usr/local/lib/python*/site-packages/pip* /usr/local/lib/python*/site-packages/setuptools* /usr/local/lib/python*/site-packages/wheel* \
    && find /usr/local/bin -name "pip*" -delete || true
RUN rm -rf /usr/lib/python*/site-packages/pip* /usr/lib/python*/site-packages/setuptools* /usr/lib/python*/site-packages/wheel* \
    && find /usr/bin -name "pip*" -delete || true
RUN uv pip uninstall --system pip setuptools wheel && rm /usr/bin/uv /usr/bin/uvx
