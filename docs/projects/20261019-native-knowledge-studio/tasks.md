# 知识中台原生化重构（路线 C）- 任务拆分

## Phase 1: 项目详情页彻底瘦身与结构纯净化
- [x] **Task 1.1: 彻底移除 ProjectDetailPage 中的「项目知识库」Tab**
  - **内容：** 从 `ProjectDetailPage.vue` 移除 `ProjectKnowledgePanel` 组件导入、`activeProjectTab` 状态、Tab 切换栏以及 `activeProjectTab === 'knowledge'` 条件渲染分支。
  - **状态：** 已完成 2026-10-19，类型检查 0 错误，单元测试通过。

## Phase 2: 知识库中台原生智能问答工作台 (Chat Studio) 实现
- [x] **Task 2.1: 封装知识问答与图谱 API 服务客户端**
  - **内容：** 在 `apps/platform-web/src/services/knowledge/knowledge.service.ts` 中补充 `queryProjectKnowledge` 与 `getKnowledgeGraph` 两个核心方法，包含严密的类型定义。
  - **状态：** 已完成 2026-10-19

- [x] **Task 2.2: 实现原生 KnowledgeChatStudio 组件**
  - **内容：** 在 `apps/platform-web/src/modules/knowledge/components/` 下新建 `KnowledgeChatStudio.vue`，实现多模式切换（Hybrid/Local/Global/Naive）、对话气泡渲染、AI 思考回答、知识切片溯源折叠卡。
  - **状态：** 已完成 2026-10-19

## Phase 3: 知识库中台原生知识图谱工坊 (Graph Studio) 实现
- [x] **Task 3.1: 实现原生力导向图可视化组件 KnowledgeGraphStudio**
  - **内容：** 在 `apps/platform-web/src/modules/knowledge/components/` 下新建 `KnowledgeGraphStudio.vue`，基于 HTML5 Canvas 实现无依赖、极速流畅的力导向拓扑关系网，支持节点缩放拖拽、实体模糊搜索、节点类型染色与属性抽屉。
  - **状态：** 已完成 2026-10-19

## Phase 4: 整合集成与全量质量门禁验证
- [x] **Task 4.1: 在 ProjectKnowledgePage 中挂载原生组件，彻底淘汰 iframe**
  - **内容：** 将 `ProjectKnowledgePage.vue` 中的 `activeSection === 'graph'` 与 `'qa'` 替换为原生 `KnowledgeGraphStudio` 和 `KnowledgeChatStudio`。
  - **状态：** 已完成 2026-10-19

- [x] **Task 4.2: 质量门禁与全量测试回归**
  - **内容：** 执行 `pnpm test:run`、`pnpm run typecheck`、`pnpm run build`，确保所有单测全绿，打包构建成功。
  - **状态：** 已完成 2026-10-19

## 进度追踪
- [x] Phase 1 项目详情页彻底瘦身与结构纯净化
- [x] Phase 2 知识库中台原生智能问答工作台 (Chat Studio) 实现
- [x] Phase 3 知识库中台原生知识图谱工坊 (Graph Studio) 实现
- [x] Phase 4 整合集成与全量质量门禁验证
