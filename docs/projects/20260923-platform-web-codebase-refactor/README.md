# 前端代码库冗余清理与结构化重构（platform-web）

**立项日期：** 2026-09-23  
**状态：** 已完成  
**改动分级：** 治理改动（多专题模板，前端单服务内大规模架构治理与模块拆分，对外 HTTP/SSE 契约零变更）  
**涉及服务：** `apps/platform-web`

---

## 1. 背景与问题诊断

通过对 `apps/platform-web/src` 的全量代码体检，重构前前端代码库主要存在四大结构性痛点，直接拖慢日常开发与定位问题的效率：

1. **`chat` 与 `dear-agent` 模块 98% 像素级复制粘贴（最严重冗余）**
   - `src/modules/chat` 与 `src/modules/dear-agent` 存在 **37 个同名或同构文件**（总计 **13,000+ 行代码**，其中每侧约 6,500+ 行）。
   - `ChatSession.vue` vs `DearAgentSession.vue`、`useChatSession.ts` vs `useDearAgentSession.ts`、`ToolResult.vue`、`ChatMessageList.vue`、`ChatContextDrawer.vue`、`trajectory/*` 几乎逐行相同。
2. **千行级“上帝组件 / 上帝 Composable”扎堆**
   - 会话与管理后台单个 `.vue` / `.ts` 文件塞入状态机、API 请求、列表页、筛选栏、详情抽屉、新建/编辑/删除弹窗，动辄 1000～1800 行。
3. **控制面大页面内联抽屉与弹窗**
   - `DearAgentSkillsPage.vue`（1280 行）、`ServiceAccountsPage.vue`（1261 行）、`RuntimeModelsPage.vue`（1092 行）将主页面与多套弹窗/详情抽屉硬塞在同一文件内。
4. **服务层重复包装与 HTTP 错误解包分散**
   - `assistants.service.ts` 与 `agents.service.ts` 重复定义，且 `workspace.service.ts` 内散落私有 `parseErrorPayload`。

---

## 2. 专题导航与完成状态

| 编号 | 专题文档 | 核心目标 | 最终收益 | 状态 |
| :--- | :--- | :--- | :--- | :--- |
| **01** | [01-chat-dear-agent-unification.md](./01-chat-dear-agent-unification.md) | 消除 `modules/chat` 与 `modules/dear-agent` 的复制粘贴，提取统一会话底座 | **净删 ~11,800+ 行重复代码**，修复 `@vitejs/plugin-vue` 无 `<template>` 重导出导致 `render` 被覆盖为空函数的白屏隐患 | `done` (`已完成`) |
| **02** | [02-chat-session-decomposition.md](./02-chat-session-decomposition.md) | 拆解 `useChatSession.ts` 上帝 Composable（抽离中断审批状态机与附件上传器） | `useChatSession.ts` 从 1244 行降至 **1024 行**，职责清晰解耦 | `done` (`已完成`) |
| **03** | [03-control-plane-pages-split.md](./03-control-plane-pages-split.md) | 拆分控制面三大超长页面（Skills、ServiceAccounts、RuntimeModels） | 三大管理页全部降至 **< 1000 行**（`DearAgentSkillsPage` 951 行、`ServiceAccountsPage` 969 行、`RuntimeModelsPage` 997 行） | `done` (`已完成`) |
| **04** | [04-services-and-deadcode-cleanup.md](./04-services-and-deadcode-cleanup.md) | 收敛 `services/` 重复封装、统一 `http-error.ts` 错误解包、清理无效导入 | 统一 `unwrapPlatformHttpError` + `assistants.service.ts` 复用 | `done` (`已完成`) |

---

## 3. 重构前后核心指标对比

- **全仓源码总行数（含单测）**：`74,655` 行 $\rightarrow$ `62,895` 行（**净减少 11,760 行，精简 15.8%**）
- **非单测源码行数**：降至 `52,626` 行
- **验证结果**：
  - `rtk pnpm build`（`vue-tsc --noEmit && vite build`）：**0 报错，通过生产构建**
  - `rtk pnpm test:run`（Vitest 全量单测）：**88 个测试文件 / 355 项用例全部通过（1 项既有 skip）**
  - 本地运行验证（`http://127.0.0.1:3000`）：**Vite Dev Server 与页面渲染 100% 正常**
