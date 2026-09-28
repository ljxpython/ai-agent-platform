# Python 格式基线清理与存量全量收敛实现记录

## 改动时间
2026-09-28

## 相关任务
- Phase 2: platform-api 存量清理 (Task 2.1)
- Phase 3: runtime-service 存量清理 (Task 3.1)
- Phase 4: 全量 CI 门禁升级 (Task 4.1)

## 改动文件
- `apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py` (B904 修复)
- `apps/platform-api/src/platform_api/core/schemas.py` (UP046 PEP 695 语法升级)
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` (B904 修复)
- `apps/platform-api/tests/test_audit_stream_status.py` (B017 修复)
- `apps/platform-api/tests/test_runtime_delegation_contract.py` (B905 修复)
- `apps/platform-api/tests/test_runtime_gateway_event_redaction.py` (B023 修复)
- `apps/platform-api/tests/test_runtime_gateway_http_matrix.py` (对齐最新 checkpoint 路由与参数断言)
- `apps/platform-api/tests/test_runtime_gateway_memory_contract.py` (B017 修复)
- `apps/platform-api/tests/test_runtime_gateway_sdk_adapters.py` (B023 修复)
- `apps/platform-api/tests/test_runtime_gateway_skills.py` (E402 修复)
- `apps/runtime-service/src/runtime_service/http/workspace.py` (E402 修复)
- `apps/runtime-service/src/runtime_service/middlewares/runtime_config.py` (B905 修复)
- `apps/runtime-service/src/runtime_service/runtime/modeling.py` (B905 修复)
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/backend.py` (B904 修复)
- `apps/runtime-service/src/runtime_service/tools/images.py` (B904 修复)
- `apps/runtime-service/src/runtime_service/workspace/documents.py` (B904 修复)
- `apps/runtime-service/src/runtime_service/workspace/terminal.py` (B904 修复)
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/governance_storage.py` (显式 __all__ 保护 re-export connect)
- `apps/runtime-service/tests/durable/test_agent_server_durable.py` (B017 修复)
- `apps/runtime-service/tests/integration/test_agent_server_auth.py` (B017 修复)
- `apps/runtime-service/tests/runtime/test_tool_governance.py` (B023 修复)
- `apps/runtime-service/tests/services/dearflow_agent/test_research.py` (B023 修复)
- `apps/runtime-service/tests/test_image_workspace_storage.py` (F841 修复)
- `apps/runtime-service/tests/test_r0_baseline.py` (更新过时的基准 graphs 与 compose depends_on 断言)
- `.github/workflows/ci.yml` (增加全量 Python ruff check 与 ruff format --check 门禁)

## 具体改动摘要
1. **自动修复与格式化**：
   - `platform-api` 批量执行 172 处 import 排序与语法现代化修复，全量 287 个 Python 文件 format 规范化。
   - `runtime-service` 批量执行 147 处 import 排序与语法现代化修复，全量 287 个 Python 文件 format 规范化。
2. **人工行为相关 Lint 审查治理**：
   - 彻底解决所有 `B023` 循环变量绑定：使用默认参数 `lambda ..., _var=var: ...` 显式绑定当前循环迭代值，避免闭包捕获后期被篡改。
   - 规范化所有 `B904` 异常抛出：使用 `raise ... from exc` 保留原始调用栈异常链。
   - 解决所有 `B017` 盲目捕获：替换为确切的异常类型（`RuntimeError`, `ForbiddenError`, `httpx.HTTPError`）。
   - 解决所有 `B905`：为 `zip()` 显式指定 `strict=False`，防止长度不等时意外崩溃。
   - 保护 re-export 避免被误删：在 `governance_storage.py` 中显式定义 `__all__ = ["connect", "lock_scope"]`。
3. **CI 门禁升级**：
   - 在 `.github/workflows/ci.yml` 的 `code-quality` 任务中接入全量 `uvx ruff check apps/platform-api apps/runtime-service` 与 `uvx ruff format --check apps/platform-api apps/runtime-service`。
