# platform-web 知识图谱前端重构方案

> Superseded: 本文已被 `10-platform-web-knowledge-graph-single-milestone-plan.md` 取代，后者是当前有效的单阶段实施计划。本文保留仅用于历史参考。

## 1. 文档目的

本文只讨论一件事：

> `apps/platform-web` 中知识图谱页应该如何从当前的手写 SVG 实现，重构为可维护、可扩展、可验证的正式图谱前端。

本文是实施前的冻结方案，不直接包含代码修改。

---

## 2. 当前结论

当前知识图谱页已经具备基础业务入口，但实现路线不适合作为正式版本继续扩展。

结论固定为：

1. **不继续在当前手写 SVG 实现上做功能叠加**
2. **不直接迁移 LightRAG 的 React 图谱代码**
3. **采用 Vue + Sigma + graphology 的正式图引擎方案**
4. **复用 AITestLab 的正式控制面壳层与知识工作台结构**

---

## 3. 当前问题复盘

当前实现位于：

- `apps/platform-web/src/modules/knowledge/pages/KnowledgeGraphPage.vue`

当前页面的主要问题不是“样式差一点”，而是实现分层本身有问题。

### 3.1 技术问题

- 图数据、布局算法、渲染、拖拽、缩放、搜索、属性面板全部堆在单文件里
- 力导向布局为前端手写同步计算，节点一多就会出现性能和稳定性问题
- 缩放、平移、旋转依赖整体 SVG transform，而不是独立 camera 模型
- 节点聚焦通过“移动节点到画布中心”实现，不是真正的视角聚焦
- 边、箭头、曲线、标签、节点高亮都靠手绘路径维护，后续扩展成本很高
- 事件体系不完整，hover / edge interaction / label density control 都比较弱

### 3.2 产品问题

- 图谱交互显得像“演示图”，不像正式工作台
- 标签、属性、搜索、图例、布局控制虽然都在页面里，但没有统一的图引擎状态模型
- 视觉上混入大量页面级玻璃态和大圆角，不符合正式控制面视觉基线
- 当前“旋转图谱”并不是知识图谱用户真正需要的高优先级能力

---

## 4. 外部参考结论

### 4.1 对 LightRAG 前端的结论

LightRAG 值得借鉴的是**架构分层**，不是直接搬实现。

应该借鉴的部分：

- 图数据获取与图实例构建分离
- 图状态独立管理
- 图控件、布局控件、搜索、属性面板拆分为独立组件
- 使用正式图引擎承接布局、交互、渲染

不应该直接搬的部分：

- React 组件实现
- `@react-sigma/*` 依赖链
- LightRAG 原产品的 UI 壳层
- LightRAG 中偏编辑型的图谱操作能力

### 4.2 对 Sigma 的结论

Sigma 适合作为正式图谱前端引擎，原因是：

- 面向大图可视化，渲染性能明显优于当前 SVG 手绘方案
- 底层使用 graphology，图数据模型和交互能力更完整
- 支持节点/边事件、camera、label 渲染控制、reducer、高亮和过滤
- 可以在不改业务 API 的前提下承接现有 `nodes/edges` 子图接口
- 适合只读浏览型知识图谱工作台

结论：

- **采用 `sigma` + `graphology`**
- **不采用 React wrapper**
- Vue 项目内直接封装 Sigma 实例和控制层

---

## 5. 正式方案

## 5.1 方案原则

### 原则 A：前端只替换图引擎，不推翻现有知识工作台入口

保留：

- project 级知识工作台路由
- 现有 `knowledge.service.ts` API
- 标签入口、属性面板、设置面板、图例等工作台概念

替换：

- 中央图谱渲染区
- 布局与交互实现
- 图谱状态组织方式

### 原则 B：复用正式控制面壳层，不迁入 LightRAG 风格 UI

图谱页必须继续服从：

- `apps/platform-web/docs/control-plane-page-standard.md`
- `apps/platform-web/docs/frontend-visual-baseline-standard.md`

换句话说：

- 图谱引擎可以升级
- 正式页面壳层不能跟着变成 LightRAG 的 React 产品壳

### 原则 C：先交付只读、稳定、顺手的图谱工作台

第一阶段只做：

- 子图浏览
- 标签切换
- 节点/边高亮
- 属性查看
- 节点搜索与聚焦
- 布局切换
- 基本视图控制

第一阶段不做：

- 图谱编辑
- 节点/边删除或合并
- 在线扩图 / 裁剪
- 图谱写回
- 复杂多人协同能力

---

## 5.2 目标架构

推荐在 `apps/platform-web/src/modules/knowledge/` 下新增图谱专属分层：

```text
apps/platform-web/src/modules/knowledge/
  components/graph/
    KnowledgeGraphCanvas.vue
    KnowledgeGraphToolbar.vue
    KnowledgeGraphLabelPanel.vue
    KnowledgeGraphInspector.vue
    KnowledgeGraphLegend.vue
    KnowledgeGraphSearch.vue
    KnowledgeGraphSettings.vue
  composables/
    useKnowledgeGraphData.ts
    useKnowledgeGraphSigma.ts
    useKnowledgeGraphSearch.ts
  stores/
    knowledgeGraph.ts
  utils/
    knowledge-graph-adapter.ts
    knowledge-graph-colors.ts
    knowledge-graph-layout.ts
```

分层职责固定如下：

### A. `useKnowledgeGraphData.ts`

负责：

- 图谱标签列表加载
- 热门标签加载
- 标签搜索
- 子图数据获取

不负责：

- 布局
- 渲染
- 视图状态

### B. `knowledge-graph-adapter.ts`

负责：

- 将后端返回的 `nodes/edges` 转为 graphology graph
- 统一 node label / type / color / size / degree / searchable text
- 统一 edge label / weight / type

不负责：

- 业务请求
- UI 面板

### C. `knowledgeGraph` store

建议使用 Pinia，符合当前项目技术栈。

负责：

- selected node / edge
- hovered node / edge
- 当前 label
- 搜索词
- 当前布局模式
- 显示开关
- camera 聚焦意图

不负责：

- 原始 HTTP 请求

### D. `useKnowledgeGraphSigma.ts`

负责：

- 创建 / 销毁 Sigma 实例
- 绑定 graphology graph
- 绑定 click / hover / stage 事件
- 设置 reducers
- 驱动 camera 聚焦
- 驱动 layout 切换

### E. 组件层

负责：

- 工具栏
- 搜索栏
- 图例
- 属性面板
- 设置面板
- 标签面板

---

## 5.3 推荐依赖

建议新增：

- `sigma`
- `graphology`
- `graphology-layout-forceatlas2`
- `graphology-layout-noverlap`
- `minisearch`

可选增强：

- `@sigma/node-border`
- `@sigma/edge-curve`

明确不引入：

- `@react-sigma/*`
- React 生态 wrapper
- 新的重量级 UI 依赖

---

## 6. 页面能力规划

## 6.1 第一阶段必须交付

### 图谱加载

- 按 label 拉取子图
- 支持 `*` 作为全图入口
- 支持 max depth / max nodes 参数
- 正确处理 loading / empty / error

### 图谱展示

- 使用 Sigma 承接节点与边渲染
- 节点按类型着色
- 节点大小按 degree 或归一化权重计算
- 边样式弱化为辅助信息，不做过重视觉存在感

### 基本交互

- 拖拽平移
- 滚轮缩放
- fit/reset view
- 点击节点选中
- hover 节点高亮邻居
- 点击空白取消选择

### 检索与聚焦

- 标签搜索
- 当前子图节点搜索
- 搜索结果聚焦到 camera
- 快速定位 Top 节点

### 信息侧栏

- 节点属性面板
- 节点关系摘要
- 原始 JSON 查看
- 图例面板
- 基本设置面板

### 布局

- 默认 `ForceAtlas2`
- 提供 `Noverlap` 补布局
- 可保留一个轻量备用布局（例如 circular）

---

## 6.2 第一阶段明确不做

- 图谱旋转
- 边标签默认全量展示
- 复杂动画布局编排
- 节点编辑 / 边编辑
- 图谱 merge / prune / expand
- 多选批量操作
- 导出图片 / 导出图文件

原因很直接：

- 这些能力对“先把图谱做顺手”帮助有限
- 会显著扩大实施范围
- 很多能力更接近编辑器，不是第一阶段的浏览型工作台

---

## 7. 与当前页面的关系

当前页面不是完全推倒重来，而是“壳层保留、图引擎替换、状态重组”。

### 7.1 保留的内容

- `KnowledgeGraphPage.vue` 作为页面入口
- `PageHeader`
- `KnowledgeWorkspaceNav`
- project knowledge 路由和权限语义
- `knowledge.service.ts` 图谱相关 API
- 标签、设置、图例、属性、搜索这些工作台概念

### 7.2 替换的内容

- 手写 `buildForcePositions`
- 手写 `buildRadialPositions`
- 手写 SVG path / node / arrow 渲染
- 手写 pan / zoom / rotate 主逻辑
- 基于节点位置挪动的 focus 实现

---

## 8. 实施顺序

## Phase 0：方案冻结

- [ ] 冻结本方案文档
- [ ] 冻结 PRD 与 test spec
- [ ] 明确第一阶段不做项

## Phase 1：图谱内核落地

- [ ] 引入 `sigma` / `graphology` 依赖
- [ ] 新增 graph adapter
- [ ] 新增 graph store
- [ ] 新增 Sigma composable
- [ ] 跑通子图加载 -> graphology -> Sigma 渲染链路

## Phase 2：工作台控件接入

- [ ] 标签面板迁入新状态流
- [ ] 节点搜索迁入 graph index
- [ ] 属性面板改为选中态驱动
- [ ] 图例与设置面板迁入 store
- [ ] reset / focus / fit view 接 camera

## Phase 3：布局与交互打磨

- [ ] 默认布局收敛到 ForceAtlas2
- [ ] 补 noverlap / secondary layout
- [ ] 邻居高亮 reducer
- [ ] 选中态 reducer
- [ ] 边弱化与标签密度控制

## Phase 4：回归与视觉收口

- [ ] loading / empty / error 全面验证
- [ ] 深色/浅色模式验证
- [ ] 大屏 / 小屏工作区布局验证
- [ ] 权限与 project 切换回归

---

## 9. To-do 清单

以下清单作为后续实施的唯一执行入口。

### A. 依赖与基础设施

- [ ] 为 `apps/platform-web` 增加 Sigma 与 graphology 依赖
- [ ] 确认类型支持与构建链兼容
- [ ] 确认无新增不必要的大型 UI 依赖

### B. 数据适配

- [ ] 设计 `RawGraph -> GraphologyGraph` 适配函数
- [ ] 统一节点 label 解析规则
- [ ] 统一节点 type 解析规则
- [ ] 统一节点颜色映射规则
- [ ] 统一节点大小映射规则
- [ ] 统一边 label 与权重解析规则

### C. 状态管理

- [ ] 新增知识图谱 Pinia store
- [ ] 拆出 selected / hovered / layout / search / visibility 状态
- [ ] 迁出页面内临时图谱状态

### D. Sigma 封装

- [ ] 封装 Sigma 生命周期
- [ ] 封装事件注册
- [ ] 封装 camera 控制
- [ ] 封装 reducer
- [ ] 封装布局切换入口

### E. 页面组件拆分

- [ ] 拆出 `KnowledgeGraphCanvas`
- [ ] 拆出 `KnowledgeGraphLabelPanel`
- [ ] 拆出 `KnowledgeGraphSearch`
- [ ] 拆出 `KnowledgeGraphInspector`
- [ ] 拆出 `KnowledgeGraphLegend`
- [ ] 拆出 `KnowledgeGraphSettings`

### F. 交互能力

- [ ] 节点点击选中
- [ ] 节点 hover 高亮邻居
- [ ] 空白点击清空选中
- [ ] 节点搜索聚焦
- [ ] fit/reset view
- [ ] label 显示密度控制

### G. 回归与验收

- [ ] 图谱页 loading / empty / error 状态齐全
- [ ] project 切换后图谱状态正确重置
- [ ] 深色模式显示正常
- [ ] 100 / 300 / 1000 节点规模的交互表现人工验证
- [ ] 与 documents / retrieval / settings 页无交互冲突

---

## 10. 验收标准

本方案实施完成后，至少满足：

1. 图谱页不再依赖手写 SVG 主渲染逻辑
2. 图谱页使用正式图引擎承接节点、边、camera 与事件
3. 代码不再集中堆在单文件页面中
4. 页面仍保持 AITestLab 正式控制面风格
5. 节点搜索、聚焦、选中、属性查看体验明显优于当前版本
6. 第一阶段不因图谱编辑能力而扩 scope

---

## 11. 风险与约束

### 风险 A：一次性照搬 LightRAG React 设计

后果：

- 技术栈不匹配
- 代码不可维护
- UI 壳层跑偏

规避：

- 只借架构，不借 React 代码

### 风险 B：Sigma 落地时把页面逻辑继续塞回单文件

后果：

- 只是“把 SVG 换成库”，没有真正解决维护问题

规避：

- 必须按 composable / store / canvas / side panel 分层

### 风险 C：第一阶段混入编辑能力

后果：

- 方案失焦
- 实施周期不可控

规避：

- 第一阶段严格限定只读浏览工作台

---

## 12. 最终决策

最终决策固定为：

- `platform-web` 知识图谱页采用 **Vue + Sigma + graphology** 重构
- 保留正式控制面壳层与现有 project knowledge API
- 不继续维护手写 SVG 图谱主实现
- 不直接迁移 LightRAG React 图谱代码
- 先完成方案、PRD、test spec，再进入实施
