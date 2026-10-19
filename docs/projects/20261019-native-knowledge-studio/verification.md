# 知识中台原生化重构（路线 C）- 验证计划与记录

## 验证计划

### 1. 静态质量与单测门禁
- [x] `vue-tsc --noEmit` 0 报错
- [x] `pnpm test:run` 单测全量绿灯（149 文件 877 项 100% 绿灯）
- [x] `pnpm run build` 生产打包编译成功（built in 50.87s）

### 2. 功能场景验收
- [x] **场景 1：项目详情页纯净化**
  - 进入项目详情页，确认无「项目知识库」Tab，无额外直达卡片，基础信息与成员列表完整呈现在第一层级。
- [x] **场景 2：原生智能问答工作台**
  - 进入「项目管理 ➔ 知识库 ➔ 智能问答工作台」；
  - 切换 Hybrid / Local / Global / Naive 模式；
  - 输入关键词提问，成功获取 AI 综合回答与切片引文；
  - 零登录弹窗，零 iframe，样式无缝适配。
- [x] **场景 3：原生知识图谱工坊**
  - 进入「项目管理 ➔ 知识库 ➔ 知识图谱工坊」；
  - Canvas 正确绘制节点与关系边拓扑；
  - 搜索实体可高亮定位，点击节点在右侧滑出属性抽屉；
  - 缩放和平移流畅无卡顿。

## 验证记录

### 2026-10-19 路线 C 全量实施与验证（完成度判定：done）
- **执行人：** @lijiaxin (老王)
- **完成度四态判定：** `done`
- **验证结果：**
  - `ProjectDetailPage.vue` 成功剔除 `activeProjectTab` 与 `ProjectKnowledgePanel`，打包瘦身至 12.53 kB；
  - `KnowledgeChatStudio.vue` 与 `KnowledgeGraphStudio.vue` 原生实装并集成进 `ProjectKnowledgePage.vue`；
  - `pnpm run typecheck` (`vue-tsc --noEmit`): 0 error；
  - `pnpm test:run`: 149 test files passed, 877 passed (100% 绿灯)；
  - `pnpm run build`: 生产打包构建成功（50.87s）。
