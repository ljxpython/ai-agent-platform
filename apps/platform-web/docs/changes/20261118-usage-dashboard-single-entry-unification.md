# Token 看板入口收敛与多作用域自适应治理

## 背景

此前在侧边栏【项目管理】与【平台管理】两个分组下均挂载了名为「Token 看板」的导航项，两处名称和图标完全相同，且均加载 `UsageDashboardPage.vue` 组件，导致管理员用户在侧边栏看到重复双胞胎入口，产生严重的心智割裂与误解。

## 改动内容

1. **侧边栏导航收敛 (方案 B)**：
   - 从 `apps/platform-web/src/router/routes.ts` 的侧边栏导航映射中移除 `"workspace-usage"`，保留 `"workspace-project-usage"`；
   - 彻底移除【平台管理】中的重复入口，全平台统一从【项目管理 -> Token 看板】单入口访问。
2. **看板内部增加作用域自适应切换分段控件 (Segmented Control)**：
   - 平台管理员（拥有 `platform.usage.read` 权限）：
     - 默认展示当前项目用量，同时在 Header 顶部提供分段控制器：`[当前项目名]` 与 `[全平台总览 (所有项目)]`；
     - 切换到全平台总览时，动态派生 `kind: 'platform'` 作用域，并同步 URL `?scope=platform`，驱动网关大盘、调用明细与历史治理全量呈现全平台数据；
     - 切换到当前项目时，派生 `kind: 'project'` 作用域，展示当前项目专属用量与日志。
   - 普通项目成员（无 `platform.usage.read` 权限）：
     - 隐藏切换控件，仅展示当前项目名称标签，受严格的数据范围隔离保护。
3. **测试覆盖**：
   - 在 `UsageDashboardPage.spec.ts` 中补充超管权限与作用域切换的自动化测试用例，所有 34 项用量单测 100% 通过。

## 涉及文件

- `apps/platform-web/src/router/routes.ts`
- `apps/platform-web/src/modules/usage/pages/UsageDashboardPage.vue`
- `apps/platform-web/src/modules/usage/pages/UsageDashboardPage.spec.ts`
