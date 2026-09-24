# 代码规范自动化 - 整体方案

## 背景
根目录 pre-commit 配置为空，agent 编辑代码时可能产生格式漂移。前端已有 ESLint/Prettier，Python 服务需要统一接入 Ruff。

## 方案设计
- 本地 pre-commit：通用文件检查；Python Ruff lint 自动修复与格式化；前端 ESLint/Prettier 自动修复。
- CI：只对当前变更文件重复执行格式检查和 lint，保持只读，不在 CI 改文件；历史存量不因本次治理突然全部重排。
- 钩子按路径筛选，只处理本次提交相关文件，不做全仓自动重排。
- 测试、typecheck、build 保持在 CI，不放入每次提交钩子。

## 风险和边界
- 历史文件可能尚未符合新格式；本次不批量格式化存量代码。
- 本地需要安装 `pre-commit`、Python `uv` 和前端 `pnpm`。
