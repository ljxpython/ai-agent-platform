# GitHub 调研工具与远程沙箱证据元组契约韧性治理 - 任务拆分

## Phase 1: 远程沙箱证据元组契约修复

### Task 1.1: 修复 `_evidence` 远程 RPC 返回值元组转换
- **改动内容：** 在 `_evidence` 函数中，对 `RemoteWorkspace.call("research_evidence", ...)` 返回的结果进行检查，如果为包含 2 个元素的 list/tuple，显式转换为标准 Python `tuple`。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/search.py` → `_evidence()`
- **预期结果：** 在远端 Docker 沙箱场景下，`_evidence` 返回的一致是 `(str, dict)` 二元组，LangChain `@tool(response_format="content_and_artifact")` 严格类型断言通过，不再抛出 `ValueError`。
- **验证项：** 编写单元测试模拟 `RemoteWorkspace.call` 返回 `list`，验证 `_evidence` 输出为 `tuple`，且 LangChain `tool.ainvoke` 成功执行无异常。
- **预计：** 0.2 天
- **状态：** `[x]` 已完成 2026-10-26

## Phase 2: GitHub 调研工具 Token 鉴权注入与限流防御

### Task 2.1: 在 `research_http.py` 中注入 `GITHUB_TOKEN` 支持
- **改动内容：** 读取环境变量 `GITHUB_TOKEN`，在请求 `api.github.com` 时注入 `Authorization: Bearer <token>`；若返回 401（Token 无效）同样转为标准受控 `ToolException`。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/research_http.py` → `get_public()`
- **预期结果：** 配置有效 Token 时可享受 5,000 次/小时高配额，无 Token 时继续保持匿名调用与 403 优雅降级。
- **验证项：** 单元测试覆盖带 Token 请求头构造、未带 Token 请求头、以及 401/403 异常映射。
- **预计：** 0.2 天
- **状态：** `[x]` 已完成 2026-10-26

### Task 2.2: 环境配置模板与说明补齐
- **改动内容：** 在 `apps/runtime-service/.env` 中增加 `GITHUB_TOKEN` 示例注释（与 `deer-flow` 对齐）。
- **代码位置：** `apps/runtime-service/.env`
- **预期结果：** 开发者可开箱即用填入自己的 GitHub Personal Access Token。
- **验证项：** 文件格式检查。
- **预计：** 0.1 天
- **状态：** `[x]` 已完成 2026-10-26

## Phase 3: 全量验证与闭环

### Task 3.1: Final 综合验证与回归测试
- **改动内容：** 执行 `runtime-service` 相关的单元测试集（`tests/tools/`、`tests/services/dearflow_agent/`），确保零回归。
- **验证项：** pytest 运行全部绿灯，四态判定输出。
- **预计：** 0.1 天
- **状态：** `[x]` 已完成 2026-10-26

## 进度追踪
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 全量验证通过
