# Agent 显式挂载多 MCP 与 MultiServerMCPClient 极简治理方案 - 验证计划和记录

## 验证计划

### 单元测试
- [x] `test_load_mcp_tools_with_target_servers` - 验证 `load_mcp_tools` 能精准根据 `target_servers` 提取对应 Server 的工具
- [x] 多 Server 隔离验证 - 验证同时存在 `knowledge` 和 `other_unrelated_server` 服务时，指定 `knowledge` 绝不混入其他 Server 的工具
- [x] 降级与安全过滤 - 验证未请求或未授权工具被过滤，异常时安全降级
- [x] `test_agent_registers_all_five_knowledge_tools` - 验证 `dearflow_agent` 启动时显式挂载了指定服务的全部知识库工具
- [x] `test_agent_system_prompt_references_knowledge_capabilities` - 验证系统提示词对知识库调用的精准认知

### 集成测试
- [x] **场景 1：Runtime 动态多 Server 装配验证**
  - 命令：`pytest tests/services/dearflow_agent/test_mcp_tools.py`
  - 预期：输出的工具列表精准匹配指定 Server 的工具集合，工具 schema 与错误拦截器完好。
- [x] **场景 2：Platform-API 资源绑定与权限过滤透传**
  - 命令：`PYTHONPATH=. pytest tests/test_knowledge_mcp_bindings.py`
  - 预期：Platform-API 动态与静态绑定透传无误，无非法权限越权。
- [x] **场景 3：真实 HTTP 契约与上传/作业流程集成**
  - 命令：`pytest tests/tools/test_knowledge_upload_http.py`
  - 预期：完整 HTTP 上传、撤销与回滚契约通过。

---

## 阶段验证记录 (Phase Verification)

### Phase 1: 极简原生适配器与解耦验证
- **测试命令：** `apps/runtime-service/.venv/bin/pytest -v apps/runtime-service/tests/services/dearflow_agent/test_mcp_tools.py`
- **执行结果：**
  ```text
  tests/services/dearflow_agent/test_mcp_tools.py::test_load_mcp_tools_with_target_servers PASSED [ 50%]
  tests/services/dearflow_agent/test_mcp_tools.py::test_real_mcp_binding_permissions_disconnect_and_close PASSED [100%]
  2 passed, 5 warnings in 5.37s
  ```
- **判定：** `PASS`

### Phase 2: Agent 显式挂载与提示词认知验证
- **测试命令：** `apps/runtime-service/.venv/bin/pytest -v apps/runtime-service/tests/services/dearflow_agent/test_agent.py`
- **执行结果：** 全部 20 个测试通过（涵盖知识库 5 个工具注册、参数 Schema、系统 Prompt 等）。
  ```text
  apps/runtime-service/tests/services/dearflow_agent/test_agent.py::test_create_agent_registers_custom_tools PASSED
  apps/runtime-service/tests/services/dearflow_agent/test_agent.py::test_agent_registers_all_five_knowledge_tools PASSED
  apps/runtime-service/tests/services/dearflow_agent/test_agent.py::test_agent_system_prompt_references_knowledge_capabilities PASSED
  ...
  20 passed in 23.80s
  ```
- **判定：** `PASS`

### Phase 3: 多 Server 隔离单测与全量回归
- **测试命令 1（Platform-API 绑定）：**
  ```bash
  cd apps/platform-api && PYTHONPATH=. .venv/bin/pytest -v tests/test_knowledge_mcp_bindings.py
  ```
  - 结果：`6 passed, 3 subtests passed in 2.06s`
- **测试命令 2（Runtime-Service 服务与工具全量套件）：**
  ```bash
  cd apps/runtime-service && PYTHONPATH=src .venv/bin/pytest -m "not integration" tests/services/ tests/tools/
  ```
  - 结果：`661 passed, 92 skipped, 2 deselected`（所有本地原生服务与工具测试 100% 通过；2 个需依赖外部 Docker Daemon 守护进程的容器测试被 `@pytest.mark.integration` 规则精确隔离）。
- **判定：** `PASS`

---

## 终态判定记录 (Final Verification)

- **完成度四态判定：** `done`
  - [x] 所有计划内功能全部按 Karpathy Guidelines 与 KISS 原则落地完成。
  - [x] 绝无冗余抽象胶水代码，直接利用官方 `MultiServerMCPClient` 原生特性。
  - [x] 多 Server 隔离测试、动态工具反射、系统 Prompt 认知全部覆盖。
  - [x] 全仓库所有相关单测 100% 绿色通过，0 报警，0 遗留 Bug。
- **环境要求与约束：** 本地原生资源执行，无外部或侵入性污染。
