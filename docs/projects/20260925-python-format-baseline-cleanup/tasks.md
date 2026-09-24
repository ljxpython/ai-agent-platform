# Python 格式基线清理 - 任务拆分

## Phase 1: 基线与规则

### Task 1.1: 固定 Ruff 基线
- **改动内容：** 固定工具版本与规则，按服务、目录、规则统计诊断。
- **代码位置：** `apps/platform-api/pyproject.toml`、`apps/runtime-service/pyproject.toml`
- **预期结果：** 可重复的诊断基线。
- **验证项：** 保存 Ruff 全量统计与版本信息。
- **状态：** `[ ]` 待开始

### Task 1.2: 确认目录策略
- **改动内容：** 确认 migrations、scripts、tests 的 lint/format 策略。
- **代码位置：** 两个服务的 Ruff 配置。
- **预期结果：** 规则例外有明确理由。
- **验证项：** 维护者评审。
- **状态：** `[ ]` 待开始

## Phase 2: platform-api

### Task 2.1: 分批清理
- **改动内容：** 按目录处理格式、import 和其余 Ruff 诊断。
- **代码位置：** `apps/platform-api/`
- **预期结果：** platform-api 全量 Ruff 检查通过。
- **验证项：** Ruff 检查与受影响测试。
- **状态：** `[ ]` 待开始

## Phase 3: runtime-service

### Task 3.1: 分批清理
- **改动内容：** 按目录处理格式、import 和其余 Ruff 诊断。
- **代码位置：** `apps/runtime-service/`
- **预期结果：** runtime-service 全量 Ruff 检查通过。
- **验证项：** Ruff 检查与受影响测试。
- **状态：** `[ ]` 待开始

## Phase 4: 门禁切换

### Task 4.1: 启用全量 CI 门禁
- **改动内容：** CI 执行全量 Python lint 与 format 检查。
- **代码位置：** `.github/workflows/ci.yml`
- **预期结果：** 全量门禁稳定通过。
- **验证项：** 两服务测试、全量 Ruff、CI。
- **状态：** `[ ]` 待开始

## 进度追踪
- [ ] Phase 1 完成
- [ ] Phase 2 完成
- [ ] Phase 3 完成
- [ ] Phase 4 全量验证通过
