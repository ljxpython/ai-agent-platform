# 提交前与 CI 代码质量门禁

2026-09-25，完成 Task 1.1/1.2。

- `.pre-commit-config.yaml`：启用通用文件检查、Ruff lint/format、前端 ESLint/Prettier；前端钩子将仓库相对路径转换为 app 内路径。
- `.github/workflows/ci.yml`：安装相同工具，只对本次变更文件执行 pre-commit，避免历史基线阻断所有提交。
- 原因：根配置原先为空；全仓试跑发现 731 条 Ruff 诊断、297 个 Python 文件格式差异，不适合混入本次改动。
- 验证：`pre-commit validate-config`、定向 pre-commit 运行及 `git diff --check` 通过；CI 远程执行尚未验证。
