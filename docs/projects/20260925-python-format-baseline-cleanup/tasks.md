# Python 格式基线清理 - 任务拆分

## Phase 1: 基线与规则

### Task 1.1: 固定 Ruff 基线与服务自治配置
- **改动内容：** 拒绝根目录一刀切，在 `apps/platform-api/pyproject.toml` 与 `apps/runtime-service/pyproject.toml` 分别配置专属 `[tool.ruff]`，启用 `E, W, F, I, B, UP` 规则集，配置 `extend-immutable-calls` 彻底消除 282 个 FastAPI B008 假阳性。
- **代码位置：** `apps/platform-api/pyproject.toml`、`apps/runtime-service/pyproject.toml`
- **预期结果：** 建立可重复且真实的诊断基线，单测与本地 pre-commit 全绿。
- **验证项：** `uvx ruff check apps/platform-api --statistics` 与 `uvx ruff check apps/runtime-service --statistics` 采样记录；两服务 `uv run pytest` 全绿。
- **状态：** `[x]` 已完成（2026-09-28）

### Task 1.2: 确认目录与模块策略
- **改动内容：** 在各服务 `extend-exclude` 中排除 `migrations`、`**/skills/**`、`tests/acceptance_app` 和 `.venv`；并在 `[tool.ruff.lint.isort]` 绑定 `known-first-party`。
- **代码位置：** `apps/platform-api/pyproject.toml`、`apps/runtime-service/pyproject.toml`
- **预期结果：** 排除外部注入代码和动态生成的迁移脚本，避免伪错误污染。
- **验证项：** 重新采样验证被排除目录不产生诊断。
- **状态：** `[x]` 已完成（2026-09-28）

## Phase 2: platform-api 存量分批清理（待后续实施）

### Task 2.1: 分批清理与自动修复
- **改动内容：** 优先按模块目录（`core/`、`modules/`、`entrypoints/`、`tests/`）执行自动修复（`I001` 导入排序与 `UP` 语法升级），再逐项审查修复少量行为相关诊断（如 `B023`、`B904`）。
- **代码位置：** `apps/platform-api/`
- **预期结果：** platform-api 全量 Ruff 检查与格式化诊断归零。
- **验证项：** `uvx ruff check apps/platform-api` 与 `uv run pytest`。
- **状态：** `[ ]` 待开始（用户后续安排）

## Phase 3: runtime-service 存量分批清理（待后续实施）

### Task 3.1: 分批清理与自动修复
- **改动内容：** 优先处理 `runtime_service/http/`、`runtime_service/services/` 和 `tests/` 中的 `I001` 导入排序与自动修复项，再手动处理少量语法诊断。
- **代码位置：** `apps/runtime-service/`
- **预期结果：** runtime-service 全量 Ruff 检查与格式化诊断归零。
- **验证项：** `uvx ruff check apps/runtime-service` 与 `uv run pytest`。
- **状态：** `[ ]` 待开始（用户后续安排）

## Phase 4: 门禁切换（待后续实施）

### Task 4.1: 启用全量 CI 门禁
- **改动内容：** 在 `.github/workflows/ci.yml` 中将 Python 门禁从变更文件检查升级为全量 check 与 format check。
- **代码位置：** `.github/workflows/ci.yml`
- **预期结果：** CI 稳定执行全量 Python 质量门禁。
- **验证项：** CI 流水线测试、两服务单测。
- **状态：** `[ ]` 待开始（用户后续安排）

## 进度追踪
- [x] Phase 1 完成（服务自治配置落地、消灭 B008 假阳性、诊断基线收敛）
- [ ] Phase 2 platform-api 存量清理
- [ ] Phase 3 runtime-service 存量清理
- [ ] Phase 4 CI 全量门禁切换
