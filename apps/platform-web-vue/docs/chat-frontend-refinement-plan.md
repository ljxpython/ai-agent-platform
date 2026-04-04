# Chat 前端收敛方案

## 目标

- 保持 `apps/platform-web-vue` 现有视觉风格、主题变量、组件体系不变。
- 吸收 `2026-03-21-testing-deep-agents-ui` 在聊天产品上的逻辑优点。
- 让 chat 基座成为后续 `sql-agent`、`research`、`testcase`、`audit` 等页面复用的工程底座。

## 非目标

- 不迁移 Next.js / shadcn / App Router 技术栈。
- 不替换现有 `BaseButton`、`SurfaceCard`、`BaseDrawer`、`PageHeader` 等 UI 基座。
- 不通过修改后端状态协议来修正前端展示问题。

## 指导原则

1. 视觉以 `platform-web-vue` 为主，逻辑只借参考实现的长处。
2. `composable` 负责数据源和流式状态，`view model` 负责展示态整形，组件只负责渲染。
3. 所有“稳定展示”问题优先在前端 view model 解决，不污染 runtime / platform-api 协议。
4. 复杂聊天能力必须拆成可复用的独立模块，不能继续往 `BaseChatTemplate.vue` 里硬塞判断。

## 目标架构

### 1. 页面壳

- `ChatPage.vue`
- `SqlAgentPage.vue`
- 其他未来复用 chat 基座的业务页

职责：

- 解析路由和目标对象
- 选择要不要展示入口引导
- 组合通用 chat 基座

### 2. 数据源层

- `useChatWorkspace`
- `useChatAttachments`

职责：

- 线程列表、线程详情、流式运行、断点恢复
- 附件上传、粘贴、拖拽
- 运行参数、取消、重试、checkpoint 分支

### 3. 展示态层

后续拆成以下几个稳定模块：

- `buildChatThreadListView`
- `buildChatPlanViewModel`
- `buildChatDisplayMessages`
- `buildChatMessageMetaView`
- `createChatMessageActions`

职责：

- 把后端原始数据转换成前端稳定展示结构
- 隔离“实时状态”和“用户可理解的展示状态”
- 为组件提供可直接渲染的数据

### 4. 组件层

- `BaseChatTemplate.vue`
- `ChatTasksFilesPanel.vue`
- `ChatMessageMeta.vue`
- `ChatArtifactPanel.vue`
- `ChatInterruptPanel.vue`
- 已拆：`ChatThreadDrawer`、`ChatComposer`、`ChatContextDrawer`、`ChatMessageList`
- 后续继续拆：`ChatToolCallCard`

职责：

- 只接收整理好的展示数据
- 不直接承担复杂状态推导

## 参考项目可吸收的优点

1. 线程列表分组、筛选、摘要、状态徽标。
2. 附件上传支持拖拽、粘贴、去重。
3. 工具调用、审批中断、sub-agent 卡片统一归口。
4. Markdown 渲染统一出口。
5. 聊天页面按“页面壳 / hooks / 展示组件”分层。

## 当前确定的实现策略

### ToDo / 计划展示

- 主计划优先从消息历史里的第一次 `write_todos` 工具调用提取。
- 如果消息里拿不到，再退回第一次可用的实时 `todos`。
- 后续实时 `todos` 只负责推进主计划里的状态，不再覆盖主计划内容。
- 不在首版计划中的新任务归入“临时执行项”单独展示。
- 这是一层纯前端 view model，不改后端协议。

### 样式处理

- 保持当前 `platform-web-vue` 的主题、色板、圆角、阴影、排版。
- 允许吸收参考项目的布局细节和组件职责拆分，但不照抄其 CSS 变量和全局样式。

### 前端拆包策略

#### 第一阶段：先做路由级懒加载

- 优先把 `src/router/routes.ts` 里的工作台页面改成动态 `import()`。
- 原因很直接：
  1. 收益最大，改动范围最可控。
  2. 不会污染业务模块边界。
  3. 先解决“首包过大”这个最明显的问题，再决定是否需要更细的 chunk 策略。
- 结果：
  - 主入口 chunk 从约 `680KB` 降到约 `291KB`。
  - 已经消除 `>500kB` 的 Vite 大 chunk warning。

#### 第二阶段：只对高价值共享块继续精细拆包

- 不直接上大范围 `manualChunks`，避免把工程切成一堆难维护的小碎块。
- 当前优先处理“资源库模板详情链路”：
  - 模板列表页只保留静态目录元数据。
  - 参考模板源码读取、代码拆解、详情预览改为点开弹窗时再动态加载。
- 这一步的目标不是继续压主入口，而是避免资源页首屏把模板源码能力整包吞进去。

#### 当前构建观察

- 当前较大的共享 chunk 主要包括：
  - `index-*.js` 约 `293KB`
  - `types-*.js` 约 `232KB`
  - `en-*.js` 约 `237KB`
  - `zh-Cn-*.js` 约 `175KB`
  - `useSub2apiTemplateDialog-*.js` 已从约 `98KB` 收敛到约 `31.85KB`
  - `template-detail-loader-*.js` 约 `39.29KB`
  - `Sub2apiTemplateDialog-*.js` 约 `12.99KB`
  - `Sub2apiTemplatePreview-*.js` 约 `26.73KB`
- 其中：
  - `types-*.js` 更接近 chat / threads / 展示层共享逻辑聚合块。
  - `en` / `zh-Cn` 这类大块并不是当前站点 i18n 文案本身过大，而是资源库引入参考模板源码后形成的源码文本 chunk。
  - 资源库模板详情链已经拆成“模板目录入口块 + 详情弹窗块 + 预览舞台块 + 源码读取块”，避免用户一进入资源页就把整条详情链全吞下去。

#### 后续继续优化的顺序

1. 先观察资源库模板详情按需加载改完后的构建结果。
2. 如果 `types-*.js` 仍然明显偏大，再分析它到底聚合了哪些共享模块。
3. 只有在确认存在“稳定且高复用的大型公共依赖”后，才考虑在 `vite.config.ts` 增加有限度的 `manualChunks`。
4. 不做按 `node_modules` 粗暴切碎的愚蠢方案，避免维护成本和缓存命中一起变烂。

## 执行顺序清单

- [x] 明确“视觉沿用 `platform-web-vue`、逻辑吸收参考项目”的迁移原则
- [x] 明确 ToDo 稳定展示应由前端 view model 负责，而不是后端 snapshot
- [x] 新增本方案文档
- [x] 实现 `useChatPlanViewModel` / 纯函数版本，完成 ToDo 主计划与临时执行项分离
- [x] 把 `ChatTasksFilesPanel.vue` 改为消费前端计划展示模型
- [x] 补充计划展示相关单测
- [x] 抽离线程列表 view model
- [x] 抽离消息块 view model
- [x] 抽离工具调用卡片 view model
- [x] 抽离 `ChatThreadDrawer`
- [x] 抽离 `ChatComposer`
- [x] 抽离 `ChatContextDrawer`
- [x] 抽离 `ChatMessageList`
- [x] 抽离消息动作控制层 `createChatMessageActions`
- [x] 完成路由级懒加载，先把主入口大包问题压下去
- [x] 识别资源库模板详情链路的额外包体开销
- [x] 将资源库模板目录与源码详情加载拆开，改为按点击动态加载
- [x] 把拆包策略、现状和后续优化方向写入文档
- [ ] 收敛 `BaseChatTemplate.vue`，让它只负责编排，不继续堆业务判断

## 当前阶段验收标准

- “所有任务”不再随着实时 `todos` 整表漂移。
- “当前任务”来自主计划，不再直接展示后续临时改写任务。
- 参考项目的逻辑优点以 Vue 工程化方式落地，现有样式不被破坏。
- 主入口 chunk 不再出现 Vite 大包告警，资源库模板详情能力不再强绑在列表页首屏里。
