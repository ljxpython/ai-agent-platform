# platform-web-vue 知识工作台实施方案

## 1. 文档目的

本文只讨论 `apps/platform-web-vue` 如何实现知识工作台页面。

当前页面设计必须服从正式控制面页面标准：路由入口、页面壳层、service 调用层、复用组件层四层拆分，正式页面统一只走 `platform-api-v2`（`apps/platform-web-vue/docs/control-plane-page-standard.md:11-66`）。

## 2. 核心原则

### 原则 A：功能参考 LightRAG，产品壳层参考 AITestLab

当前外部参考设计稿已经明确不应直接搬 LightRAG React UI，而应在 AITestLab 内按自己的 page shell / service 规范重做（外部参考：`docs/aitestlab-knowledge-platform-design.md:94-112`）。

### 原则 B：前端只认 `project_id`

前端只在 AITestLab 项目上下文里工作，不直接感知 `workspace_key`。这也符合当前正式 workspace store 只承载唯一项目上下文的要求（`apps/platform-web-vue/src/stores/workspace.ts:28-73`, `apps/platform-web-vue/docs/control-plane-page-standard.md:70-90`）。

### 原则 C：第一阶段先做真正有业务价值的页面

第一阶段建议顺序：

1. `documents`
2. `retrieval`
3. `graph`
4. `settings`

当前 **不建议** 先做 `overview`。原因是它更像一个状态壳层，而不是第一价值链路。

## 3. 路由建议

第一阶段建议新增：

- `/workspace/projects/:projectId/knowledge/documents`
- `/workspace/projects/:projectId/knowledge/retrieval`
- `/workspace/projects/:projectId/knowledge/graph`
- `/workspace/projects/:projectId/knowledge/settings`

可选：

- `/workspace/projects/:projectId/knowledge` -> redirect 到 `documents`

## 4. 页面分层建议

推荐目录：

```text
apps/platform-web-vue/src/modules/knowledge/
  pages/
  components/
  services/
  types/
  composables/
```

## 5. Phase 1 页面定义

### 5.1 Documents

第一优先级页面，负责验证数据面链路是否真正可用。

至少支持：

- 上传文档
- 目录扫描
- 分页列表
- track status
- pipeline status
- 删除 / 清空

实现要求：

- 列表页优先使用正式控制面表格页结构（`apps/platform-web-vue/docs/control-plane-page-standard.md:29-39`）
- 危险动作必须确认弹窗（`apps/platform-web-vue/docs/control-plane-page-standard.md:35-36`, `apps/platform-web-vue/docs/control-plane-page-standard.md:45-50`）
- 长耗时动作优先接 operation（`apps/platform-web-vue/docs/control-plane-page-standard.md:54-66`）

### 5.2 Retrieval

第二优先级页面，负责证明“这个知识空间真的能查”。

至少支持：

- query 输入
- 模式选择（如后端提供）
- 结果展示
- 上下文/引用展示
- 空态 / 错态 / 加载态

### 5.3 Graph

第三优先级页面，负责承接图谱浏览价值。

第一阶段建议先只做：

- label search
- 子图展示
- 属性面板
- 布局 / 缩放等基本交互

如果 graph mutation 没有明确业务必要性，先不纳入第一阶段。

### 5.4 Settings

最后补配置与说明页。

至少支持：

- 当前 project 绑定的默认知识空间
- 当前 workspace 映射摘要
- 服务健康 / 最近状态
- 运行说明 / 风险说明

## 6. service 设计要求

推荐新增：

- `src/services/knowledge/knowledge.service.ts`

严格要求：

- 页面不直接拼 URL（`apps/platform-web-vue/docs/control-plane-page-standard.md:54-59`）
- 正式页面统一只走 `platform-api-v2`（`apps/platform-web-vue/docs/control-plane-page-standard.md:61-66`）
- 新页面统一使用 `projectId` 做权限与数据上下文，不再扩散伪双上下文（`apps/platform-web-vue/docs/control-plane-page-standard.md:63-78`）

## 7. UI / 权限约束

- 页面必须复用 AITestLab 共享壳，不新起 LightRAG 风格 UI
- route 级 permission 放在 `meta.requiredPermissions`
- 页面动作统一用 `useAuthorization()`
- 无权限时优先导航裁剪、按钮禁用、友好提示，由后端兜底安全（`apps/platform-web-vue/docs/control-plane-page-standard.md:82-90`）

## 8. 第一阶段不做的前端内容

- LightRAG 原产品主题系统迁入
- assistant 绑定知识库页面
- shared knowledge 页面
- multi-knowledge binding 页面
