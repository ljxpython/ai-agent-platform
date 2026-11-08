# 工作区总览工业级重构与信息密度治理 - 任务拆分

## Phase 1: 顶栏精简与治理入口收纳

### Task 1.1: 净化 PageHeader 与收纳平台治理按钮
- **改动内容：**
  - 移除 `PageHeader` 中无意义的 `description="从当前项目继续工作。"`
  - 将原本位于 `SurfaceCard` 内突兀的 `<router-link to="/workspace/control-plane">` 移除并移入 `PageHeader` 的 `#actions` 插槽，按权限受控渲染
  - 压缩头部外边距，提升首屏有效信息利用率
- **代码位置：** `apps/platform-web/src/modules/overview/pages/OverviewPage.vue`
- **预期结果：** 顶部整洁、紧凑，无任何废话文本，管理按钮归入右上角操作区
- **验证项：** `pnpm vitest run src/modules/overview/pages/OverviewPage.spec.ts` → ✅ 通过 (4/4 绿灯)
- **状态：** `[x]` 已完成 2026-11-08 → 见 [01-overview-refactor.md](implementation/01-overview-refactor.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [ ] CONTEXT.md 已更新（此 Task 暂不触发最终状态切换）

## Phase 2: 核心指标看板搭建

### Task 2.1: 组装 4 联 MetricCard 指标数据源
- **改动内容：**
  - 在 `OverviewPage.vue` 中引入 `MetricCard` 组件
  - 在 `load()` 函数中并行加载项目 Agent 总数、最近会话活跃数、已注册能力/工具数
  - 渲染包含「智能体矩阵」、「活跃对话」、「装配工具」和「系统运行时」的四联卡片
- **代码位置：** `apps/platform-web/src/modules/overview/pages/OverviewPage.vue`
- **预期结果：** 页面顶部呈现高信息密度的指标条，支持深浅色主题自适应
- **验证项：** `pnpm vitest run src/modules/overview/pages/OverviewPage.spec.ts` → ✅ 通过 (4/4 绿灯)
- **状态：** `[x]` 已完成 2026-11-08 → 见 [01-overview-refactor.md](implementation/01-overview-refactor.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

## Phase 3: 主辅双栏布局重构与 Agents/Threads 增强

### Task 3.1: 重构快捷开工横幅与快速恢复区
- **改动内容：**
  - 将原单调的项目信息卡片改造为紧凑型项目工作台 Hero：
    - 展示项目名、状态指示灯（🟢 就绪）、项目描述
    - 快速发起对话按钮与常用操作
- **代码位置：** `apps/platform-web/src/modules/overview/pages/OverviewPage.vue`
- **预期结果：** 首屏具备明确的“快速开工”召唤力，消除大片无用留白
- **验证项：** `pnpm vitest run src/modules/overview/pages/OverviewPage.spec.ts` → ✅ 通过
- **状态：** `[x]` 已完成 2026-11-08 → 见 [01-overview-refactor.md](implementation/01-overview-refactor.md)

### Task 3.2: 升级项目 Agents 列表卡片
- **改动内容：**
  - 在 Agent 列表项中透出模型 ID（如 `model_id`）与运行状态微胶囊
  - 增加卡片右侧快捷【立即对话】图标按钮（带 Tooltip 提示），一键带参数进入 Chat
  - 优化 hover 边框阴影反馈
- **代码位置：** `apps/platform-web/src/modules/overview/pages/OverviewPage.vue`
- **预期结果：** 具备丰富信息量与直接交互能力的 Agent 列表
- **验证项：** `pnpm vitest run src/modules/overview/pages/OverviewPage.spec.ts` → ✅ 通过
- **状态：** `[x]` 已完成 2026-11-08 → 见 [01-overview-refactor.md](implementation/01-overview-refactor.md)

### Task 3.3: 升级最近对话列表卡片
- **改动内容：**
  - 会话更新时间改为友好的人性化时间展示（刚刚、X分钟前、X小时前、X天前）
  - 卡片增加可恢复状态点与右侧悬浮滑动箭头
  - 空状态对齐平台标准 `EmptyState`
- **代码位置：** `apps/platform-web/src/modules/overview/pages/OverviewPage.vue`
- **预期结果：** 对话列表信息清晰，直观引导用户继续上次会话
- **验证项：** `pnpm vitest run src/modules/overview/pages/OverviewPage.spec.ts` → ✅ 通过
- **状态：** `[x]` 已完成 2026-11-08 → 见 [01-overview-refactor.md](implementation/01-overview-refactor.md)

## Phase 4: 全量构建与验证

### Task 4.1: 前端静态类型检查与单测回归
- **改动内容：**
  - 运行 `pnpm vitest run` 确保 160 套测试套件 953 项单测 100% 绿灯
  - 运行 `pnpm typecheck`（`vue-tsc --noEmit`）静态类型检查 0 报错
  - 运行 `pnpm eslint` 确保代码风格 0 错误
- **代码位置：** `apps/platform-web`
- **预期结果：** 单测 100% 绿灯，0 TypeScript 报错，0 ESLint 报错
- **验证项：** 全套本地工具链门禁检验 → ✅ 通过
- **状态：** `[x]` 已完成 2026-11-08 → 见 [01-overview-refactor.md](implementation/01-overview-refactor.md)

## 进度追踪
- [x] Phase 1 顶栏精简与治理入口收纳
- [x] Phase 2 核心指标看板搭建
- [x] Phase 3 主辅双栏布局重构与 Agents/Threads 增强
- [x] Phase 4 全量构建与验证
