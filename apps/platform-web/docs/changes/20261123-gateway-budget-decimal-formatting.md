# 网关预算与花费金额展示小数位优化（消除冗长 12 位零）

**日期**：2026-11-23
**服务**：`platform-web`
**类型**：`fix`

## 背景与问题

AI 网关预算控制（Gateway Budget）在前端展示限额与花费时，直接渲染了后端返回的 12 位定点字符串（如 `$200.000000000000`、`$7.734293400000`）。在表格列表和进度条中占据过多宽度，排版拥挤紧凑，用户阅读体验差；且在编辑策略时，输入框内同样充斥大量尾部冗余零。

## 改动内容

1. **金额格式化纯函数实装（`apps/platform-web/src/modules/usage/composables/useGatewayBudgets.ts`）**：
   - 封装 `formatBudgetAmount(amountStr)`：对 $\ge \$0.01$ 的金额统一按标准货币习惯格式化为 2 位小数（并添加千分位，如 `200.00`、`7.73`）；对极小微额（$<\$0.01$）保留最多 4 位小数（如 `0.0035`），避免失真；
   - 封装 `stripTrailingZeros(val)`：回填编辑表单时自动修剪多余尾部零（如 `200.000000000000` $\to$ `200`）。

2. **视图组件优化（`GatewayBudgetsTab.vue`、`DeleteBudgetPolicyModal.vue`、`CreateBudgetPolicyModal.vue`）**：
   - 表格“限额与动作”列渲染格式化后的限额，通过 `:title` 保留完整 12 位精度悬浮提示；
   - 进度条列“已用额度/限额”与状态提示接入格式化；
   - 删除对话框确认文案接入格式化；
   - 编辑表单自动剔除尾部冗余零。

3. **测试覆盖与构建**：
   - `useGatewayBudgets.spec.ts` 补充针对 `formatBudgetAmount` 与 `stripTrailingZeros` 的单元测试；
   - `apps/platform-web` 44 项用量单测 100% 跑绿，`vue-tsc` 0 报错，`pnpm build` 生产构建成功并同步部署。

## 验证结果

- **单元测试**：Vitest `useGatewayBudgets.spec.ts` 10 项测试全部通过；
- **全量用量测试**：6 套件 44 项单测 100% 通过；
- **静态检查**：`vue-tsc --noEmit` 0 错误；
- **生产构建与发布**：本地 `pnpm build` 构建完成，dist 产物已同步至远端服务器 Webroot。
