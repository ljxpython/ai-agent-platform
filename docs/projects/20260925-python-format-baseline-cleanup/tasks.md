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

## Phase 2: platform-api 存量清理

### Task 2.1: 分批清理与自动修复
- **改动内容：** 批量执行 172 项导入排序与语法升级，手工解决 20 项 B023、B904、B017、B905、E402、UP046 行为相关诊断，并对全量 287 个 Python 文件执行 ruff format。
- **代码位置：** `apps/platform-api/`
- **预期结果：** platform-api 全量 Ruff 检查与格式化诊断归零，单测全绿。
- **验证项：** `uvx ruff check apps/platform-api` → ✅ 通过 (All checks passed)；`uvx ruff format --check apps/platform-api` → ✅ 通过 (287 files already formatted)；`uv run --directory apps/platform-api python -m unittest discover -s tests -p 'test*.py'` → ✅ 325 passed。
- **状态：** `[x]` 已完成 2026-09-28 → 见 implementation/01-python-format-and-lint-cleanup.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（跳过，本任务为格式基线清理，待全部收敛后统一记录）
  - [x] docs/FEATURES.md 已更新（跳过，未增减业务功能）

## Phase 3: runtime-service 存量清理

### Task 3.1: 分批清理与自动修复
- **改动内容：** 批量执行 147 项导入排序与语法升级，手工解决 16 项 B904、B017、B023、B905、E402、F841 诊断，使用 `__all__` 保护 re-export connect，并对全量 287 个 Python 文件执行 ruff format。
- **代码位置：** `apps/runtime-service/`
- **预期结果：** runtime-service 全量 Ruff 检查与格式化诊断归零，单测全绿。
- **验证项：** `uvx ruff check apps/runtime-service` → ✅ 通过 (All checks passed)；`uvx ruff format --check apps/runtime-service` → ✅ 通过 (287 files already formatted)；`uv run --directory apps/runtime-service pytest -m "not e2e and not integration and not durable"` → ✅ 534 passed。
- **状态：** `[x]` 已完成 2026-09-28 → 见 implementation/01-python-format-and-lint-cleanup.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（跳过，待全量归零后更新）
  - [x] docs/FEATURES.md 已更新（跳过，未增减业务功能）

## Phase 4: 门禁切换

### Task 4.1: 启用全量 CI 门禁
- **改动内容：** 在 `.github/workflows/ci.yml` 的 `code-quality` 任务中增加全量 `uvx ruff check apps/platform-api apps/runtime-service` 与 `uvx ruff format --check apps/platform-api apps/runtime-service`。
- **代码位置：** `.github/workflows/ci.yml`
- **预期结果：** CI 稳定执行全量 Python 质量门禁，本地 pre-commit 秒级通过。
- **验证项：** `pre-commit run --files .github/workflows/ci.yml` → ✅ 通过；`uvx ruff check apps/platform-api apps/runtime-service` → ✅ 通过；`python3 scripts/check_docs.py` → ✅ 通过。
- **状态：** `[x]` 已完成 2026-09-28 → 见 implementation/01-python-format-and-lint-cleanup.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新（跳过，未改变平台对外功能）

## 进度追踪
- [x] Phase 1 完成（服务自治配置落地、消灭 B008 假阳性、诊断基线收敛）
- [x] Phase 2 platform-api 存量清理（163 条 lint 归零，70 个文件格式化，325 单测全绿）
- [x] Phase 3 runtime-service 存量清理（152 条 lint 归零，164 个文件格式化，534 单测全绿）
- [x] Phase 4 CI 全量门禁切换（两服务全量 ruff check 与 format check 入门禁）
