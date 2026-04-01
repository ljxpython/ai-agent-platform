# Platform Web V2 总清单

更新时间：2026-04-01

说明：

- 这份文档是 `platform-web-v2` 的唯一总清单
- 后续所有工作统一在这里推进和打勾
- 已完成项使用 `[x]`
- 未开始项使用 `[ ]`

## 1. 目标冻结

- [x] 确定不继续在 `apps/platform-web` 上直接改造
- [x] 确定新建 `apps/platform-web-v2` 承接迁移
- [x] 确定零成本开发路线
- [x] 确定不使用 `Ant Design Pro`
- [x] 确定技术路线为 `Next.js + Tailwind + Radix + shadcn/ui`
- [x] 确定布局路线为“左侧主导航 + 顶部上下文条 + 主内容区”
- [x] 确定默认主题为 `Refine HR 系`
- [x] 确定保留 `Workspace Neutral / Soft Admin` 作为可切换主题
- [x] 确定主题切换是正式能力，不是演示功能

## 2. 规划文档

- [x] 完成架构与 UI 基座方案文档
- [x] 完成迁移方案文档
- [x] 完成第一阶段 UI Foundation 文档
- [x] 完成目录结构与组件清单文档
- [x] 完成功能迁移台账
- [x] 完成迁移路线规划文档
- [x] 完成总清单文档

## 3. 视觉样板与主题

- [x] 在 `/Users/bytedance/PycharmProjects/test4` 建立独立样板目录
- [x] 完成 3 套整体风格样板
- [x] 调整默认风格到企业后台方向
- [x] 确定 `Refine HR 系` 作为默认主题
- [x] 完成样板中的一键切换主题能力
- [x] 完成样板中的主题持久化
- [x] 将样板风格 token 正式迁入 `platform-web-v2`

## 4. 目录骨架

- [x] 创建 `apps/platform-web-v2/docs`
- [x] 创建 `apps/platform-web-v2/public`
- [x] 创建 `apps/platform-web-v2/tests`
- [x] 创建 `apps/platform-web-v2/src/app`
- [x] 创建 `apps/platform-web-v2/src/components/ui`
- [x] 创建 `apps/platform-web-v2/src/components/platform`
- [x] 创建 `apps/platform-web-v2/src/components/icons`
- [x] 创建 `apps/platform-web-v2/src/providers`
- [x] 创建 `apps/platform-web-v2/src/lib/*`
- [x] 创建 `apps/platform-web-v2/src/hooks`
- [x] 创建 `apps/platform-web-v2/src/theme`
- [x] 创建 `apps/platform-web-v2/src/styles`

## 5. 工程初始化

- [x] 初始化 `package.json`
- [x] 初始化 `tsconfig.json`
- [x] 初始化 `next.config.mjs`
- [x] 初始化 `postcss` / `tailwind` 配置
- [x] 初始化 `eslint` / `prettier` 配置
- [x] 初始化 `src/app/layout.tsx`
- [x] 初始化 `src/app/page.tsx`
- [x] 初始化 `src/app/globals.css`
- [x] 初始化基础 metadata
- [x] 跑通最小开发服务器

## 6. 主题系统

- [x] 建立主题 token 映射
- [x] 建立主题 CSS variables
- [x] 实现 `ThemeProvider`
- [x] 实现 `ThemeToggle`
- [x] 默认主题接入 `Refine HR 系`
- [x] 接入 `Workspace Neutral`
- [x] 接入 `Soft Admin`
- [x] 主题持久化接入 `localStorage`
- [x] 刷新后保持用户主题选择

## 7. 基础 UI 组件层

- [x] 建立 `button`
- [x] 建立 `input`
- [x] 建立 `textarea`
- [ ] 建立 `dialog`
- [ ] 建立 `sheet`
- [ ] 建立 `tooltip`
- [ ] 建立 `avatar`
- [x] 建立 `card`
- [ ] 建立 `separator`
- [ ] 建立 `skeleton`
- [ ] 建立基础表格容器能力

## 8. 平台组件库

- [x] 实现 `WorkspaceShellV2`
- [x] 实现 `SidebarNav`
- [ ] 实现 `SidebarSection`
- [x] 实现 `TopContextBar`
- [x] 实现 `TopContextProject`
- [x] 实现 `TopContextActions`
- [x] 实现 `PlatformPage`
- [x] 实现 `PageHeader`
- [x] 实现 `PageActions`
- [ ] 实现 `FilterToolbar`
- [x] 实现 `DataPanel`
- [x] 实现 `FormSection`
- [ ] 实现 `DetailPanel`
- [x] 实现 `StateBanner`
- [x] 实现 `EmptyState`
- [ ] 实现 `ErrorState`
- [ ] 实现 `SuccessBanner`

## 9. Provider 与底层能力承接

- [x] 承接 auth guard 方案
- [x] 承接 token 存储逻辑
- [x] 承接 platform api base url 解析
- [x] 承接 `WorkspaceContext`
- [ ] 承接 `ThreadProvider`
- [ ] 承接 `StreamProvider`
- [ ] 承接日志 bootstrap 能力

## 10. P0 首批样板页迁移

- [x] 迁移 `/auth/login`
- [x] 迁移 `/workspace/projects`
- [x] 迁移 `/workspace/users`
- [x] 迁移 `/workspace/assistants`
- [x] 完成 P0 页面构建验证
- [ ] 完成 P0 页面基础联调验证

## 11. P1 标准管理页迁移

- [x] 迁移 `/workspace/projects/new`
- [x] 迁移 `/workspace/projects/[projectId]`
- [ ] 迁移 `/workspace/projects/[projectId]/members`
- [x] 迁移 `/workspace/users/new`
- [x] 迁移 `/workspace/users/[userId]`
- [x] 迁移 `/workspace/assistants/new`
- [x] 迁移 `/workspace/assistants/[assistantId]`
- [ ] 迁移 `/workspace/graphs`
- [ ] 迁移 `/workspace/runtime/models`
- [ ] 迁移 `/workspace/runtime/tools`
- [ ] 迁移 `/workspace/audit`
- [ ] 迁移 `/workspace/me`
- [ ] 迁移 `/workspace/security`

## 12. P2 复杂工作区迁移

- [ ] 迁移 `/workspace/chat`
- [ ] 迁移 `/workspace/threads`
- [ ] 迁移 `/workspace/sql-agent`
- [ ] 迁移 `/workspace/testcase/generate`
- [ ] 迁移 `/workspace/testcase/cases`
- [ ] 迁移 `/workspace/testcase/documents`

## 13. 功能完整性验收

- [ ] 核对旧 `platform-web` 路由是否全部覆盖
- [ ] 核对旧 `platform-web` 核心页面是否全部覆盖
- [ ] 核对项目切换链路是否正常
- [ ] 核对认证链路是否正常
- [ ] 核对 CRUD 管理页核心操作是否正常
- [ ] 核对 chat / thread / runtime 工作区是否正常
- [ ] 核对 testcase 工作区是否正常

## 14. 视觉与工程化验收

- [ ] 默认主题整体效果通过评审
- [x] 可切换主题工作正常
- [ ] 页面壳子统一，不再各写各的布局
- [ ] 基础组件与平台组件边界清晰
- [ ] 不存在第二套重型 UI 体系混入
- [ ] 关键页面复用统一母版

## 15. 最终替换准备

- [x] 完成构建验证
- [ ] 完成 lint 验证
- [ ] 完成关键路径手工联调
- [ ] 完成替换前最终核对
- [ ] 确认 `platform-web-v2` 达到替代旧前端条件
