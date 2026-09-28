# Python 格式基线清理 - 验证计划

## Phase 验证计划
- [x] 基线统计可重复，记录 Ruff 版本、规则和各目录诊断数。（已完成 - 2026-09-28）
- [ ] 每批执行对应目录 `ruff check` 与 `ruff format --check`。（Phase 2/3 实施时按批执行）
- [ ] 每批执行受影响服务的相关测试。（Phase 2/3 实施时按批执行）

## Final 验证计划
- [ ] `ruff check apps/platform-api apps/runtime-service`
- [ ] `ruff format --check apps/platform-api apps/runtime-service`
- [ ] platform-api 与 runtime-service 测试全部通过。
- [ ] CI 全量 Python 门禁通过。

## 验证记录

### 2026-09-28 Phase 1 规则基线与服务自治落地验证

#### 1. 诊断基线采样
- **工具版本：** Ruff v0.13.2 (Python 3.13)
- **platform-api 诊断分布（消除 282 处 FastAPI B008 假阳性）：**
  ```text
  107 I001   [*] unsorted-imports (可自动修复)
   20 UP017  [*] datetime-timezone-utc (可自动修复)
   10 B023   [ ] function-uses-loop-variable
    8 UP037  [*] quoted-annotation (可自动修复)
    5 F401   [*] unused-import (可自动修复)
    3 UP035  [*] deprecated-import (可自动修复)
    3 E402   [ ] module-import-not-at-top-of-file
    3 B904   [ ] raise-without-from-inside-except
    2 B017   [ ] assert-raises-exception
    1 UP046  [ ] non-pep695-generic-class
    1 B905   [ ] zip-without-explicit-strict
  总计：163 errors（143 条支持 --fix 自动修复）
  ```
- **runtime-service 诊断分布（排除 skills 外部脚本）：**
  ```text
  111 I001   [*] unsorted-imports (可自动修复)
   19 F401   [*] unused-import (可自动修复)
    5 B017   [ ] assert-raises-exception
    5 B904   [ ] raise-without-from-inside-except
    4 UP017  [*] datetime-timezone-utc (可自动修复)
    2 UP035  [*] deprecated-import (可自动修复)
    2 B023   [ ] function-uses-loop-variable
    2 B905   [ ] zip-without-explicit-strict
    1 E402   [ ] module-import-not-at-top-of-file
    1 F841   [ ] unused-variable
  总计：152 errors（136 条支持 --fix 自动修复）
  ```

#### 2. 服务测试与门禁验证
- **platform-api 契约测试：**
  `uv run --directory apps/platform-api pytest tests/test_assistants_runtime_contract.py`
  - 结果：`2 passed in 1.39s`
- **runtime-service 执行测试：**
  `uv run --directory apps/runtime-service pytest tests/services/dearflow_agent/test_clarification_interrupt_fix.py`
  - 结果：`3 passed in 0.69s`
- **本地 pre-commit 验证：**
  `pre-commit run --files apps/platform-api/pyproject.toml apps/runtime-service/pyproject.toml`
  - 结果：秒级全绿通过，无任何钩子阻断。

## 状态
进行中（Phase 1 验证通过；Phase 2 ~ 4 待后续存量治理时推进）。
