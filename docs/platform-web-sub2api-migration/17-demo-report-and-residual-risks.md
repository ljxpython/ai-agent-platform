# 17. 汇报口径与遗留归档

## 一句话口径

本轮不是单纯换 Vue 壳，而是已经把 `apps/platform-web` 的正式页面和关键交互链路迁进了 `apps/platform-web-vue`，同时把前端基座升级成了可持续开发的工程化后台。

## 当前可对外汇报的结果

### 1. 页面迁移结果

- `apps/platform-web` 源页面总数 `28`
- 已完成 `27`
- 暂缓 `1`

当前唯一暂缓项：

- `/auth/callback`
  - 原因：当前演示环境只走用户名密码登录，不走第三方登录回调

### 2. Agent 主线结果

已经可作为演示主线的页面：

- `assistants`
- `chat`
- `sql-agent`
- `threads`
- `testcase/generate`
- `testcase/cases`
- `testcase/documents`

已经可对外说明的能力：

- 通用 chat 工作台已打通真实 thread、run 与流式消息
- `sql-agent` 已收敛到统一 chat 基座，不再维护第二套壳
- `threads` 已改成先列表、后详情的懒加载模式
- `testcase` 已恢复三级结构和文档预览 / 下载主链路

### 3. 平台基础能力结果

已经可作为次要演示主线的页面：

- `overview`
- `projects`
- `projects/:projectId`
- `projects/:projectId/members`
- `users`
- `users/:userId`
- `announcements`
- `audit`
- `me`
- `security`

### 4. 前端工程化结果

已经固定下来的能力：

- 统一 layout、theme、base component、platform component
- 统一 `DataTable / Pagination / BaseSelect / ActionMenu / BulkActionsBar`
- 统一顶栏系统区：`ProjectSwitcher / LocaleSwitcher / AnnouncementCenter / UserMenu`
- 统一 dark mode 和响应式约束
- 统一 `Resources / Playbook` 开发范式入口

## 推荐汇报顺序

### 第 1 段：先讲结果，不先讲技术选型

建议直接说：

> 原平台页面和关键链路已经迁到新前端基座里，当前不是 demo 壳，而是可继续承接开发的正式宿主。

### 第 2 段：先演 agent，再演管理后台

建议顺序：

1. `overview`
2. `assistants`
3. `chat`
4. `sql-agent`
5. `testcase`
6. `threads`
7. `projects / users / announcements / audit`
8. `resources/playbook`

### 第 3 段：最后再讲工程化

建议强调：

- 这次没有在旧 app 上硬改
- 正式宿主已经收敛到 `apps/platform-web-vue`
- 后续新增页面可以复用统一母版和规范，不会继续长成一堆散乱页面

## 当前遗留项

### A. 非阻塞遗留

- `/auth/callback` 未纳入本轮
- `apps/platform-web-sub2api-base/.git` 嵌套仓库边界待清理
- Node `25.x` 有 engine warning，建议切回 LTS

### B. 后续优化项

- 帮助提示体系继续扩面
- 页面级引导面板继续扩面
- 继续基于 `Resources` 沉淀更多正式母版
- 继续把后续新增功能按 `14-frontend-development-playbook.md` 约束落地

## 回归归档结论

截至 `2026-04-05`，当前回归结论如下：

- 页面迁移主线已完成
- Agent 演示主线已可稳定进入
- 平台管理页主线已可稳定进入
- dark mode 与响应式两类公共风险已完成专项复查
- 剩余问题不在当前汇报主链路上

## 对内执行口径

接下来团队内部默认按下面规则执行：

1. 正式开发宿主只认 `apps/platform-web-vue`
2. 功能对齐只认 `apps/platform-web`
3. 视觉与交互风格只认当前 `platform-web-vue`
4. 新功能默认先看 `14-frontend-development-playbook.md`
5. 演示、回归、汇报默认先看 `15`、`16`、`17` 三份文档
