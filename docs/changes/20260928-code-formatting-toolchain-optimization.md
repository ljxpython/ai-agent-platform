# 20260928 代码格式化与 Git Hook 工具链治理

## 背景

在进行代码提交时，由于前端 ESLint（`vue/max-attributes-per-line` 等样式规则）与 Prettier 格式化规则存在冲突，导致 pre-commit 中的 `platform-web-eslint --fix` 和 `platform-web-prettier --write` 互相推翻改动，使 pre-commit 检测到文件反复被改写而阻断提交。同时，缺乏 IDE 级保存即格式化配置，开发者在提交时容易临时遇到格式阻塞。

## 改动内容

1. **解耦 ESLint 与 Prettier 职责**：
   - 在 `apps/platform-web` 引入 `eslint-config-prettier`；
   - 在 `apps/platform-web/eslint.config.js` 的 Flat Config 数组末尾挂载 `eslintConfigPrettier`，彻底关闭所有与 Prettier 打架的样式规则；
   - 确立职责分工：ESLint 专职代码质量、语法错误与潜在 Bug 检查；Prettier 独家管理视觉排版。
2. **优化 `.pre-commit-config.yaml` 编排**：
   - 调整 Hook 顺序：先 Prettier 排版，后 ESLint 语法检查；
   - 为 Prettier 添加 `--ignore-unknown`，为 ESLint 添加 `--cache` 加速二次校验。
3. **建立团队 IDE 统一配置**：
   - 新增 `.vscode/settings.json`：开启 `editor.formatOnSave: true`，默认前端格式化器设为 Prettier，Python 设为 Ruff；
   - 新增 `.vscode/extensions.json`：推荐团队成员安装 Prettier、ESLint、Vue - Official 与 Ruff 扩展。

## 涉及文件

- `apps/platform-web/package.json`
- `apps/platform-web/pnpm-lock.yaml`
- `apps/platform-web/eslint.config.js`
- `.pre-commit-config.yaml`
- `.vscode/settings.json`
- `.vscode/extensions.json`

## 验证结果

- ✅ `pre-commit run` 对前端配置文件与修改文件 100% 绿牌通过（0 警告、0 错误、0 死循环）；
- ✅ `vue-tsc --noEmit` 类型检查 0 错误；
- ✅ `pnpm test:run` 单元测试通过。
