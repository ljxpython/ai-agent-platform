# 03 - 控制面超长管理页组件化瘦身

## 目标
治理控制面（Control Plane）管理模块中“把页面主列表、详情抽屉、创建/编辑弹窗、子资源 CRUD 全塞进一个 1000+ 行 `.vue` 文件”的反模式，使所有管理页严格对齐 `docs/control-plane-page-standard.md` 的 4 层结构，单页面文件控制在 **350 ~ 400 行以内**。

## 重点改造页面清单（按代码行数排序）

### 1. `DearAgentSkillsPage.vue`（1312 行 → 拆分为 1 页 + 3 组件）
- **问题诊断**：单文件内同时写了公共/自定义技能列表、ZIP 上传导入弹窗、冲突覆盖弹窗、技能详情抽屉（含目录树 + Markdown 渲染 + 代码复制）。
- **拆分结构**：
  - `pages/DearAgentSkillsPage.vue` (~320 行)：顶部切换、搜索过滤、技能卡片网格编排。
  - `components/SkillDetailDrawer.vue` (~380 行)：技能详情抽屉、文件树切换与文件内容预览。
  - `components/SkillUploadModal.vue` (~260 行)：自定义技能导入与更新弹窗。

### 2. `ServiceAccountsPage.vue`（1260 行 → 拆分为 1 页 + 3 组件）
- **问题诊断**：单文件内包含统计卡片、账号列表、创建/编辑账号弹窗、Token 签发弹窗（含一次性密钥复制）、以及包含“项目授权 (Project Grants) + API Key 列表”的复杂详情抽屉。
- **拆分结构**：
  - `pages/ServiceAccountsPage.vue` (~350 行)：统计概览、筛选栏与主账号表格。
  - `components/ServiceAccountDetailDrawer.vue` (~360 行)：账号详情抽屉（分区展示 Project Grants 绑定管理与 API Key Token 列表）。
  - `components/ServiceAccountFormDialog.vue` (~180 行)：创建/编辑服务账号弹窗。
  - `components/ServiceAccountTokenDialog.vue` (~200 行)：签发新 Token 及一次性明文密钥展示弹窗。

### 3. `RuntimeModelsPage.vue` (1091 行) + `RuntimeModelEditor.vue` (1132 行) + `ToolRestrictionsPanel.vue` (899 行)
- **问题诊断**：`RuntimeModelsPage` 同时承载了“双层模型管理（平台公共 + 项目 BYOK）”和“Runtime 工具目录”两个截然不同的主视图；`RuntimeModelEditor` 单文件 1132 行塞入了表单、连通性探测、多阶段状态机与右侧实时卡片预览。
- **拆分结构**：
  - 从 `RuntimeModelsPage.vue` 拆出 `components/RuntimeToolsCatalogTab.vue` (~280 行) 与 `composables/useRuntimeModelsCatalog.ts` (~250 行)。
  - 从 `RuntimeModelEditor.vue` 拆出右侧预览面板 `components/RuntimeModelLivePreview.vue` (~260 行) 与参数预设子块。

### 4. `AgentEditorPage.vue` (972 行) 与 `DearAgentMemoryPage.vue` (905 行)
- **拆分结构**：
  - `AgentEditorPage.vue`：拆出右侧实时透视卡片 `components/AgentLiveInspectorCard.vue` (~250 行) 与动态 Schema 参数表单组件 `components/AgentSchemaFieldsForm.vue` (~220 行)。
  - `DearAgentMemoryPage.vue`：拆出记忆详情/编辑抽屉 `components/MemoryDetailDrawer.vue` (~280 行)。

## 任务拆分
- [x] Task 3.1：拆分 `DearAgentSkillsPage.vue` (1312行) 与 `DearAgentMemoryPage.vue` (905行) 的抽屉与弹窗组件 - **状态：** 待开始
- [x] Task 3.2：拆分 `ServiceAccountsPage.vue` (1260行) 的详情抽屉、账号表单弹窗与 Token 签发弹窗 - **状态：** 待开始
- [x] Task 3.3：拆分 `RuntimeModelsPage.vue` (1091行)、`RuntimeModelEditor.vue` (1132行) 与 `AgentEditorPage.vue` (972行) - **状态：** 待开始

## 验证要求与记录
### 验证要求
- [x] 所有拆分后的页面 `.vue` 文件行数 ≤ 450 行
- [x] `pnpm test:unit` 与 `pnpm typecheck` 全量通过
- [x] 权限门禁（`useAuthorization`）在子组件中保持与原页面一致

## 状态
规划中
