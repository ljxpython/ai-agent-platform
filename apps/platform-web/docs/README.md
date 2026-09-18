# Platform Web 前端开发与设计规范导航

本文档是 `apps/platform-web` 服务的核心文档入口。任何前端开发、页面重构、UI 美化与新增组件，必须优先阅读并遵循以下当前生效的活规范。

---

## 核心标准文档清单

| 文档 | 类型 | 说明与核心约束 |
|---|---|---|
| [前端视觉基线与使用范式](frontend-visual-baseline-standard.md) | **强制基线** | 视觉壳层硬约束。**强制规定表单全量使用 `BaseSelect.vue`（严禁原生 `<select>` 裸奔）**、滑块联动、快捷预设药丸、卡片网格多选，禁止散装圆角与野蛮阴影 |
| [前端开发 Playbook](frontend-development-playbook.md) | **架构指导** | 定义 5 种页面 Archetype（List, Detail, Create/Edit, Workspace, Help）。**复杂表单推荐双栏工作台架构（Form + Live Preview）**，并附带官方标杆样板 |
| [控制面页面开发标准](control-plane-page-standard.md) | **工程规范** | 控制面页面 4 层架构（路由、壳层、Service、复用组件）、State/Store 约束、按钮级细粒度权限控制与审计埋点要求 |
| [Chat 运行时线规与 Harness](chat-frontend-harness.md) | **专业领域** | LangChain / LangGraph 官方 SDK 流式运行时交互、审批面板、时间旅行与会话生命周期 |

---

## 标杆范例（Living Specimens）

开发新页面或改版旧页面时，请直接参考以下代码实现，避免重复踩坑：

- **创建与编辑页标杆**：`src/modules/agents/pages/AgentEditorPage.vue`
  - 特性：左侧表单卡片分组 + 右侧实时 Agent 卡片透视看板；全量 `BaseSelect` 美化下拉框；Temperature/Top P 双向滑块联动；Max Tokens 药丸预设；交互式工具卡片网格。
- **列表与管理页标杆**：`src/modules/agents/pages/AgentsPage.vue`
  - 特性：搜索框防挤压自适应宽度；响应式卡片列表；首字母彩色圆圈 Avatar；StatusPill 状态指示；操作列权限守卫按钮。

---

## 提交前自查（PR Checklist）

每次提交前端 PR 前，必须在终端执行以下检查：

```bash
# 1. 检查是否有偷懒使用原生 <select>（发现后必须替换为 BaseSelect.vue）
rg -n "<select" apps/platform-web/src

# 2. 检查是否存在散装大圆角、重磨砂或过度阴影
rg -n "rounded-\\[(24|26|28)px\\]|bg-white/(80|90|95)|backdrop-blur|shadow-soft|shadow-card" apps/platform-web/src

# 3. 运行 TypeScript 静态检查与打包构建
pnpm --filter platform-web build

# 4. 运行全量单元测试
pnpm --filter platform-web test run
```
