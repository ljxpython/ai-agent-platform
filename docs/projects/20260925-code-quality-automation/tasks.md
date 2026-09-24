# 代码规范自动化 - 任务拆分

## Phase 1: 配置

### Task 1.1: 根级 pre-commit 门禁
- **改动内容：** 接入通用检查、Python Ruff、前端 ESLint/Prettier。
- **代码位置：** `.pre-commit-config.yaml`
- **预期结果：** 提交前自动修复并阻止明显格式/语法问题。
- **验证项：** `pre-commit validate-config` 与定向 hooks
- **状态：** `[x]` 已完成 2026-09-25

### Task 1.2: CI 只读质量检查
- **改动内容：** 增加 Python Ruff 和前端 Prettier 检查。
- **代码位置：** `.github/workflows/ci.yml`
- **预期结果：** 绕过本地钩子的提交仍会在 CI 失败。
- **验证项：** YAML 校验和命令可执行性
- **状态：** `[x]` 已完成 2026-09-25

## Phase 2: 文档
- [x] 记录方案、边界和验证结果
