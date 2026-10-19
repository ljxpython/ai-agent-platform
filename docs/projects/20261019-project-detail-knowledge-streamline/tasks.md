# 项目详情与知识中台交互收敛 - 任务拆分

## Phase 1: 核心交互实现

### Task 1.1: 增强 ProjectKnowledgePanel 导航引导与直达按钮
- **改动内容：** 在 `ProjectKnowledgePanel.vue` 的头部 SurfaceCard 区域增加知识中台引导区，展示知识库运行状态，并提供明确跳转至 `workspace-project-knowledge` 路由的直达按钮。
- **代码位置：** `apps/platform-web/src/modules/projects/components/ProjectKnowledgePanel.vue`
- **预期结果：** 用户在项目详情的“项目知识库”Tab 中，能够一眼看清该项目关联的 LightRAG 底座状态，并可一键点击进入左侧知识中台工作台。
- **验证项：** 按钮点击可正确触发路由跳转；底座状态正确显示。
- **预计：** 0.25天
- **状态：** `[x]` 已完成 2026-10-19

### Task 1.2: 优化空状态引导与文案
- **改动内容：** 优化“暂无已发布知识资料”空状态提示，增加前往知识中台上传文档的引导链接，消除与中台的认知割裂。
- **代码位置：** `apps/platform-web/src/modules/projects/components/ProjectKnowledgePanel.vue`
- **预期结果：** 当项目无资料时，用户不仅知道可在聊天界面提交，更清楚知道可前往知识中台批量上传与管理。
- **验证项：** 空状态下有清晰引导文案与链接。
- **预计：** 0.25天
- **状态：** `[x]` 已完成 2026-10-19

## Phase 2: 测试与代码质量

### Task 2.1: 单元测试更新与回归
- **改动内容：** 在 `ProjectKnowledgePanel.spec.ts` 中增加对跳转按钮与引导元素的单元测试断言。
- **代码位置：** `apps/platform-web/src/modules/projects/components/ProjectKnowledgePanel.spec.ts`
- **预期结果：** 单元测试 100% 绿灯。
- **验证项：** `pnpm --filter platform-web test:unit`
- **预计：** 0.25天
- **状态：** `[x]` 已完成 2026-10-19

### Task 2.2: 静态类型与质量门禁
- **改动内容：** 执行 `vue-tsc` 与 `eslint` 检查。
- **代码位置：** `apps/platform-web/`
- **预期结果：** 0 errors, 0 warnings。
- **验证项：** `pnpm --filter platform-web type-check`
- **预计：** 0.25天
- **状态：** `[x]` 已完成 2026-10-19

## Phase 3: 全量验证与收口

### Task 3.1: Final 全量验证
- **改动内容：** 执行全套单元测试回归，验证页面交互无报错。
- **验证项：** 单元测试通过 + 界面元素完整 + 契约无破坏。
- **状态：** `[x]` 已完成 2026-10-19

## Phase 4: 路线 A - 项目知识库二级板块（图谱工坊与智能问答集成）

### Task 4.1: 在 ProjectKnowledgePage 实现二级板块分段切换器
- **改动内容：** 在 `ProjectKnowledgePage.vue` 中新增 `activeSection` 响应式变量（`assets` | `graph` | `qa`），提供「知识资产中枢」、「知识图谱工坊」、「智能问答工作台」三合一切换器，并配备全屏独立打开控制台辅助入口。
- **代码位置：** `apps/platform-web/src/modules/knowledge/pages/ProjectKnowledgePage.vue`
- **预期结果：** 用户无需跳出项目上下文，即可在当前项目知识库内直接切换使用资产中枢、图谱探查和智能问答。
- **验证项：** 分段控制器切换顺畅，Tab 对应渲染正确内容。
- **状态：** `[x]` 已完成 2026-10-19

### Task 4.2: 嵌入 LightRAG 原生图谱工坊与问答容器
- **改动内容：** 构造带项目隔离上下文的动态安全嵌入 URL（`tenant_id=__default&project_id=${projectId}`），沉浸式嵌入 LightRAG WebUI，支持图谱拓扑探索与 Local/Global/Hybrid 混合检索模式比对。
- **代码位置：** `apps/platform-web/src/modules/knowledge/pages/ProjectKnowledgePage.vue`
- **预期结果：** iframe 容器尺寸自适应，跨域与上下文传参正常。
- **验证项：** `pnpm test:run`、`pnpm run typecheck`、`pnpm run build` 全部成功通过。
- **状态：** `[x]` 已完成 2026-10-19

## 进度追踪
- [x] Phase 1 核心交互实现
- [x] Phase 2 测试与代码质量
- [x] Phase 3 全量验证与收口
- [x] Phase 4 路线 A - 项目知识库二级板块（图谱工坊与智能问答集成）
