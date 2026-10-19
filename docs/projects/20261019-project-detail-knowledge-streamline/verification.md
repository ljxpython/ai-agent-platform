# 项目详情与知识中台交互收敛 - 验证计划和记录

## 验证计划

### 单元测试
- [x] `ProjectKnowledgePanel.spec.ts`
  - 验证知识库未启用时的告警 Banner 渲染（通过）
  - 验证知识库激活状态下的文档列表、可检索 Badge 渲染（通过）
  - 验证直达知识中台按钮与引导文案渲染，以及点击触发 router.push（通过）
  - 验证空状态下点击引导按钮触发 router.push（通过）
- [x] `routes.spec.ts` 路由测试回归（通过，6 passed）
- [x] `useThreadWorkspace.spec.ts` Pinia 隔离单测回归（通过，3 passed）

### 类型与语法检查
- [x] `vue-tsc --noEmit` 静态类型检查 0 错误
- [x] `eslint` 代码规范检查 0 错误（改动文件 0 warnings 0 errors）
- [x] `pnpm run build` 生产打包编译成功（built in 24.80s）

### 交互场景验证
- [x] **场景 1：项目详情页 ➔ 知识中台跳转**
  - 进入项目详情页，点击「项目知识库」Tab
  - 点击「打开项目知识库中台」按钮
  - 正确路由跳转至 `/workspace/projects/:projectId/knowledge`，直达企业级全功能知识中台
- [x] **场景 2：项目知识库中台 ➔ 二级板块切换（路线 A 沉浸式集成）**
  - 默认展示「知识资产中枢」：入库文档列表、构建任务队列、指标卡片与检索沙盒抽屉。
  - 切换至「知识图谱工坊」：沉浸式加载 LightRAG 原生拓扑可视化界面（端口 9621），自动注入当前项目的 `project_id` 和鉴权 Token；右上角配备新标签独立全屏打开入口。
  - 切换至「智能问答工作台」：沉浸式加载 LightRAG 智能问答与混合检索界面，支持对比 Local/Global/Hybrid 检索召回与问答。

## 验证记录

### 2026-10-19 实施与验证（完成度判定：done）
**执行人：** @lijiaxin (老王)
- **完成度四态判定：** `done`
- **单元测试结果：**
  - 全量回归测试：`pnpm test:run`，149 test files passed, 877 tests passed in 115s。
- **质量门禁结果：**
  - `pnpm run typecheck` (`vue-tsc --noEmit`): 0 error。
  - `pnpm run build`: 生产打包构建成功（41.90s）。
