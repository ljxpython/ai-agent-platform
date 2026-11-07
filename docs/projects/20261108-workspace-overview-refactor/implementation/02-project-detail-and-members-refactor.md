# 项目详情与成员管理工业级重构实现记录

## 改动概览
- **日期：** 2026-11-08
- **服务：** `platform-web`
- **主要文件：**
  - `apps/platform-web/src/modules/projects/pages/ProjectDetailPage.vue`
  - `apps/platform-web/src/modules/projects/pages/ProjectMembersPage.vue`

## 详细改动

### 1. 项目详情页（ProjectDetailPage.vue）
- 彻底拔除“不再伪装不存在的编辑能力”奇葩文案，启用 `compact` 紧凑模式；
- 清理基础信息与成员预览卡片内部的占位废话；
- 顶栏 8 按钮大瘦身：仅保留核心动作【复制 ID】、【设为当前项目 / 当前工作区项目】与【返回列表】；
- 落实方案 A：在页面底部建立独立的「项目治理与生命周期（Danger Zone）」卡片，统一收纳接管项目、恢复管理员、归档/恢复项目与删除项目高危操作。

### 2. 项目成员管理页（ProjectMembersPage.vue）
- 彻底清除 Header 和当前成员卡片内部的无意义说明文案；
- 搜索区瘦身：将原先占两行的 SearchInput 与重置/应用筛选按钮精简为单行紧凑即时搜索条（回车即搜、内嵌清空与筛选）；
- 成员列表项重构为高质感单行卡片（左侧彩色 Avatar + 用户名 + 短 ID；右侧平齐对齐的角色胶囊与移除按钮）；
- 容器引入 `max-h-[560px] overflow-y-auto` 滚动保护，杜绝 Mac 屏幕下被截断的问题。

## 门禁验证
- `vue-tsc --noEmit`：0 errors
- `eslint`：0 errors, 0 warnings
- `vitest run`：8/8 绿灯
- `vite build`：生产构建顺利输出
