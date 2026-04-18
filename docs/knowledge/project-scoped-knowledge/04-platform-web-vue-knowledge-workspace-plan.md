# platform-web-vue 知识工作台实施方案

## 1. 文档目的

本文说明 `apps/platform-web-vue` 在新默认口径下如何承接知识工作台。

重点是：

- 前端仍然以 `projectId` 为唯一正式上下文
- retrieval scope/filter UX 比 workspace 选择器更符合新的默认方案
- multi-workspace 只能作为 fallback，不应成为默认主交互

## 2. Current reality

当前正式前端事实仍然成立：

- 路由和页面组织是 project-scoped
- 页面不直接感知 `workspace_key`
- 知识页面由 `platform-api-v2` 提供控制面 facade

## 3. Preferred future default

### 原则 A：前端默认只认 `projectId`

这条原则不变。

### 原则 B：项目内隔离优先做 retrieval scope / filter UX

在默认未来方向下，前端更合理的交互是：

- 文档 metadata/tag 可见性
- retrieval scope 选择
- filter chips / query scope presets
- soft boost / hard filter 的结果反馈

而不是默认让用户选择：

- knowledge space A / B / C

### 原则 C：不把 target state 当 current reality

当前前端契约尚未提供 metadata-aware retrieval 字段，因此文档里所有相关设计都必须标记为 target state。

## 4. 路由建议

默认仍保持：

- `/workspace/projects/:projectId/knowledge/documents`
- `/workspace/projects/:projectId/knowledge/retrieval`
- `/workspace/projects/:projectId/knowledge/graph`
- `/workspace/projects/:projectId/knowledge/settings`

这组路由仍然有效，不需要为了新默认方案变更成多 workspace 路由模型。

## 5. 页面重点

### Documents

当前现实：
- 仍是项目默认知识空间的文档工作台

Preferred future default：
- 文档列表与详情未来可展示 metadata/tag
- 上传/导入未来可配合 metadata 编辑能力

### Retrieval

这是变化最大的页面。

Preferred future default：
- 支持 retrieval scope/filter 交互
- 呈现当前使用的是 default project workspace + domain filters，而不是多 workspace
- 能清晰提示哪些结果来自 target domain / boosted domain

### Graph

图谱浏览仍然保留，但 future 若图谱也需要 domain-aware 检索，应通过通用 filter 语义增强，而不是切多 workspace 图谱入口。

### Settings

Settings 页要明确说明三件事：

- current reality：当前项目默认 workspace 映射
- preferred future default：项目内隔离未来优先靠 metadata-aware retrieval
- fallback：multi-workspace 仅在上游能力不足时采用

## 6. Fallback UX

如果 fallback multi-workspace 进入实施范围，前端应谨慎处理：

- 不要直接默认暴露“多个知识库对象模型”
- 只有当业务上必须让用户显式区分知识空间时，才单独设计该交互

## 7. Rejected option

**Rejected**：把 AITestLab 私有 taxonomy 直接设计成前端到上游协议字段。

前端可以让用户理解“底层架构/应用层/组件/网络/存储/计算”等概念，但对外协议应经过平台层归一化成通用 metadata/filter 能力。

## 8. 结论

在默认未来方向下，前端知识工作台应从“workspace 映射摘要优先”转向“retrieval scope/filter UX 优先”，同时继续保持 project-scoped 页面组织。

## 9. File-level adaptation anchor: `knowledge.service.ts`

这轮讨论里，`platform-web-vue` 的 file-level 主锚点明确为：

- `apps/platform-web-vue/src/services/knowledge/knowledge.service.ts`

配套页面/组件落点为：

- `apps/platform-web-vue/src/modules/knowledge/pages/KnowledgeRetrievalPage.vue`
- `apps/platform-web-vue/src/modules/knowledge/components/KnowledgeQuerySettingsPanel.vue`
- `apps/platform-web-vue/src/modules/knowledge/pages/KnowledgeDocumentsPage.vue`
- `apps/platform-web-vue/src/modules/knowledge/pages/KnowledgeSettingsPage.vue`
- `apps/platform-web-vue/src/types/management.ts`

### 9.1 Current reality

当前前端知识检索页已经支持：

- `query`
- `mode`
- token / top_k / chunk_top_k
- `user_prompt`
- `enable_rerank`

但仍然**没有**正式 metadata-aware retrieval UI：

- 没有 metadata filters
- 没有 metadata boosts
- 没有 strict / prefer scope 交互
- 上传链路没有正式 metadata 输入面

### 9.2 Preferred future default（target state）

前端默认不引入“项目内多 workspace 切换器”，而是引入：

- retrieval scope / filter UX
- metadata/tag 可见性
- strict / prefer 模式
- 结果域回显（当前命中了哪些过滤条件）

#### Retrieval 页
建议新增：

- `metadata_filters`
- `metadata_boost`
- `strict_scope`
- scope badge / current filter summary
- recent query state 包含 scope

#### Documents 页
建议新增：

- 上传时 metadata / tags 输入
- 列表展示 metadata 摘要
- 详情页展示 metadata

#### Settings 页
建议新增：

- 推荐 taxonomy 展示
- retrieval preset 展示
- current reality / preferred future default / fallback 说明

### 9.3 File-level implementation checklist

实现顺序建议：

1. `src/services/knowledge/knowledge.service.ts`
   - query / stream query payload 扩 metadata-aware retrieval 字段
   - upload payload 增 metadata 承载位
2. `src/types/management.ts`
   - 正式化 metadata filter / boost / document metadata 类型
3. `KnowledgeQuerySettingsPanel.vue`
   - 加 filter / strict / boost 输入控件
4. `KnowledgeRetrievalPage.vue`
   - 接 filter state、结果回显、localStorage
5. `KnowledgeDocumentsPage.vue`
   - 接 metadata 输入/展示
6. `KnowledgeSettingsPage.vue`
   - 补规则说明与 preset

### 9.4 Not recommended

`platform-web-vue` **不应该**：

- 让用户默认选择多个 knowledge spaces
- 直接持有 `workspace_key`
- 把 AITestLab 私有 taxonomy 字段直接当成上游协议字段

正式建议是：

> 前端负责 **交互、展示、范围控制 UX**，不负责定义物理隔离模型。

## 10. Field-level UI / payload draft（target state）

> 注意：本节属于 **preferred future default / target state**，描述的是前端在上游能力就绪后的建议交互与 payload 结构。

### 10.1 Retrieval settings state draft

`KnowledgeQuerySettingsPanel.vue` / `KnowledgeRetrievalPage.vue` 未来建议新增这些前端状态：

```ts
metadata_filters?: {
  tags_any?: string[]
  tags_all?: string[]
  attributes?: Record<string, string | string[]>
}
metadata_boost?: {
  tags_any?: string[]
  attributes?: Record<string, string | string[]>
  weight?: number
}
strict_scope?: boolean
```

建议 UI 控件：

- tags multi-select
- key/value attributes editor
- `strict scope` 开关
- `prefer scope`（可映射到 `metadata_boost`）
- current scope summary badge

### 10.2 Retrieval request draft

由 `knowledge.service.ts` 发给控制面的 payload 建议类似：

```json
{
  "query": "解释当前项目的底层架构",
  "mode": "mix",
  "metadata_filters": {
    "tags_any": ["architecture"],
    "attributes": {
      "layer": ["infrastructure"]
    }
  },
  "metadata_boost": {
    "attributes": {
      "module": ["storage", "network", "compute"]
    },
    "weight": 1.2
  },
  "strict_scope": true,
  "include_references": true,
  "include_chunk_content": true
}
```

### 10.3 Retrieval UX requirements

- recent query 持久化时，除了 `query` 和 `user_prompt`，还应带上当前 scope/filter
- 结果页应展示：
  - 当前 filter summary
  - strict / prefer 状态
  - references 是否主要命中当前 scope
- 页面应允许一键回退到“全项目无过滤查询”

### 10.4 Documents upload draft

Documents 上传未来建议补充 metadata 录入区：

```ts
{
  tags: string[]
  attributes: Record<string, string>
}
```

默认交互建议：

- 上传文件
- 填 tags
- 选 layer/module/domain 这类项目内推荐属性
- 提交

这里的属性名可以在前端以“推荐字段”呈现，但不应被文档写成 LightRAG 只接受这些字段。

### 10.5 Document list / detail draft

`KnowledgeDocumentsPage.vue` 未来建议：

- 列表页显示 tags 摘要
- 详情页显示完整 metadata
- 允许按 tags / attributes 做辅助筛选（非第一优先级）

### 10.6 Settings draft

`KnowledgeSettingsPage.vue` 未来可展示：

- 推荐 tags
- 推荐 attributes
- retrieval preset
- 当前系统仍处于 current reality / target state / fallback 哪个阶段

### 10.7 前端边界再确认

前端可以理解：

- architecture
- application
- component
- storage
- network
- compute

但这些在协议里应被当成：

- 本地 UI preset / taxonomy example
- 而不是上游协议的硬编码字段语义

## 11. 前端字段命名建议（v1）

为避免前端状态名和上游协议漂移，前端建议尽量与 target-state contract 对齐：

### Retrieval local state
- `metadata_filters`
- `metadata_boost`
- `strict_scope`

### Upload local state
- `metadata.tags`
- `metadata.attributes`

### 可保留的本地 UI 别名
界面文案层可以使用：
- 查询范围
- 优先范围
- 严格范围
- 标签
- 属性

但在真正发请求前，应统一归一化成：
- `metadata_filters`
- `metadata_boost`
- `strict_scope`
- `metadata`

### 不推荐
前端不建议把本地状态命名为：
- `selectedKnowledgeSpace`
- `knowledgeScopeId`
- `domainFilterPayload`

因为这些名字会把交互误导向“多 workspace / 私有 taxonomy 协议”。
