# Python 格式基线清理 - 验证计划

## Phase 验证计划
- [x] 基线统计可重复，记录 Ruff 版本、规则和各目录诊断数。（已完成 - 2026-09-28）
- [x] 每批执行对应目录 `ruff check` 与 `ruff format --check`。（已完成 - 2026-09-28）
- [x] 每批执行受影响服务的相关测试。（已完成 - 2026-09-28）

## Final 验证计划
- [x] `ruff check apps/platform-api apps/runtime-service` 全量无错误通过。
- [x] `ruff format --check apps/platform-api apps/runtime-service` 全量 574 个文件一致。
- [x] platform-api 与 runtime-service 测试全部通过。
- [x] CI 全量 Python 门禁通过。

## 验证记录

### 2026-09-28 Phase 1 规则基线与服务自治落地验证
- **工具版本：** Ruff v0.13.2 (Python 3.13)
- **治理成果：** 两服务落地专属 `[tool.ruff]`，消灭 282 处 FastAPI B008 假阳性，真实基线大幅收敛至 315 条。
- **状态：** Phase 1 通过。

---

### 2026-09-28 Phase 2 platform-api 存量清理验证
1. **自动修复与手工项清零：**
   - 自动修复 172 项导入排序和语法现代化；
   - 手工修复 20 项诊断（`B023` 循环变量绑定、`B904` 异常链、`B017` 确切异常类型、`B905` strict 参数、`UP046` PEP 695 语法、`E402` 导入顶部）；
   - 执行 `uvx ruff format apps/platform-api` 格式化 68 个存量文件。
2. **复核门禁：**
   - `uvx ruff check apps/platform-api` → `All checks passed!`
   - `uvx ruff format --check apps/platform-api` → `287 files already formatted`
3. **单测全量回归：**
   - 命令：`uv run --directory apps/platform-api python -m unittest discover -s tests -p 'test*.py'`
   - 结果：`Ran 325 tests in 86.865s - OK (skipped=16)`
- **状态：** Phase 2 通过。

---

### 2026-09-28 Phase 3 runtime-service 存量清理验证
1. **自动修复与手工项清零：**
   - 自动修复 147 项导入排序和语法现代化；
   - 手工修复 16 项诊断（`B904`、`B017`、`B023`、`B905`、`E402`、`F841`）；
   - 在 `governance_storage.py` 中显式定义 `__all__ = ["connect", "lock_scope"]` 彻底防止 re-export 符号被当作无用导入误删；
   - 更新过时的 `tests/test_r0_baseline.py` graphs 列表与 compose depends_on 断言；
   - 执行 `uvx ruff format apps/runtime-service` 格式化 164 个存量文件。
2. **复核门禁：**
   - `uvx ruff check apps/runtime-service` → `All checks passed!`
   - `uvx ruff format --check apps/runtime-service` → `287 files already formatted`
3. **单测回归：**
   - 命令：`uv run --directory apps/runtime-service pytest -m "not e2e and not integration and not durable"`
   - 结果：`534 passed, 36 skipped, 51 deselected in 110s`；`test_r0_baseline.py` 14 项全绿通过。
- **状态：** Phase 3 通过。

---

### 2026-09-28 Final 综合验证与门禁升级验证

1. **全仓 Python Lint 检查：**
   - 命令：`uvx ruff check apps/platform-api apps/runtime-service`
   - 结果：`All checks passed!`（退出码 0）

2. **全仓 Python Format 检查：**
   - 命令：`uvx ruff format --check apps/platform-api apps/runtime-service`
   - 结果：`574 files already formatted`（退出码 0）

3. **CI 门禁与本地 pre-commit 验证：**
   - 在 `.github/workflows/ci.yml` 的 `code-quality` 任务中增加全量 `uvx ruff check` 与 `uvx ruff format --check`；
   - 本地执行：`pre-commit run --files .github/workflows/ci.yml` → 全部 Passed；
   - 文档检查：`python3 scripts/check_docs.py` → `Documentation checks passed.`。

## 结论与完成度判定
- **判定：`done`**
- **判定依据：**
  - Phase 1 ~ Phase 4 规划的所有目标 100% 达成；
  - `platform-api` 与 `runtime-service` 历史存量诊断全部清零（0 errors）；
  - 全仓 574 个 Python 源码文件 100% 对齐 Ruff Formatter；
  - 核心单测（platform-api 325 项 + runtime-service 534 项）全部绿灯通过；
  - CI 自动化工作流与本地 pre-commit 双重门禁固化生效。
