# 06. 新 App 基座蓝图与职责边界

## 目标

这份文档要把一件事讲透：

- 新前端到底应该怎么搭
- 哪些能力从 `platform-web-v2` 继承
- 哪些能力从 `sub2api` 借鉴
- 哪些东西必须在新 app 里重建

如果这层不收敛，后面迁移很容易再次出现两个问题：

- 视觉借了别人的，业务却还是旧结构硬塞
- 架构换了壳子，代码边界还是乱

## 一、正式基座的收敛结论

### 1. 正式迁移必须是一个新 app

当前结论不变：

- 保留 `apps/platform-web-v2` 作为现有可运行基线
- 保留 `apps/platform-web-sub2api-base` 作为视觉与交互参考基座
- 正式开发在一个新的 Vue app 中进行

原因很直接：

- `v2` 的业务行为和接口已经有价值
- `sub2api` 的视觉系统和页面母版已经有价值
- 但它们的目录结构、路由结构、状态结构不是同一套东西

所以不能直接在任何一边上硬改到底。

### 2. 正式 app 名称已确认

正式名称确定为：

- `apps/platform-web-vue`

原因：

- 已经在现有目标架构文档里出现过
- 语义明确
- 不会再制造 `v3` 这种试验性名称的歧义

### 3. 正式 app 的唯一目标

新 app 不是为了“重写一遍前端”。

它的目标只有三个：

1. 把 `v2` 的平台功能完整迁入
2. 把 `sub2api` 的成熟视觉范式迁入
3. 在新的 Vue 工程边界下形成长期可维护的前端基座

## 二、三路来源的职责边界

### A. `platform-web-v2` 负责提供什么

`v2` 不再作为最终 UI 基座，但它仍然是最重要的业务真相来源。

它负责提供：

- 真实业务页面清单
- 真实接口域划分
- 真实工作台交互链路
- 已经验证过的平台组件抽象
- 已经跑通的业务细节与边界条件

当前明确可迁移的业务域包括：

- auth
- overview
- projects
- users
- assistants
- graphs
- runtime
- sql-agent
- threads
- chat
- testcase
- me
- security
- audit

当前明确值得保留的抽象方向包括：

- `workspace-shell-v2`
- `top-context-bar`
- `page-header`
- `filter-toolbar`
- `table-container`
- `page-state`
- `error-state`
- `empty-state`
- `confirm-dialog`
- `chat-entry-guide`
- `testcase-overview-strip`

结论：

- `v2` 提供的是“平台语义和业务行为”
- 不是“最终视觉实现”

### B. `sub2api` 负责提供什么

`sub2api` 不负责我们的业务，但它非常适合提供 UI 基座。

它负责提供：

- 设计 token 体系
- layout 结构
- 页面母版
- 轻量基础组件库
- icon facade
- 视觉层级与信息密度控制方式

当前明确应该借鉴的对象包括：

- `AuthLayout.vue`
- `AppLayout.vue`
- `AppHeader.vue`
- `AppSidebar.vue`
- `TablePageLayout.vue`
- `Input.vue`
- `Select.vue`
- `SearchInput.vue`
- `DataTable.vue`
- `BaseDialog.vue`
- `Pagination.vue`
- `StatusBadge.vue`
- `EmptyState.vue`
- `Skeleton.vue`
- `Toast.vue`
- `Toggle.vue`
- `Icon.vue`

结论：

- `sub2api` 提供的是“成熟的视觉与交互骨架”
- 不是“可直接复用的业务前端”

### C. 新 Vue app 必须自己重建什么

新 app 不是简单拷贝，而是重建一套适合我们平台的边界。

它必须自己负责：

- 新的路由组织
- 新的业务模块目录
- 新的 service 分层
- 新的 store 分层
- 新的 workspace 上下文
- 新的文件预览/下载抽象
- 新的页面母版与业务模块对接关系

尤其是下面几块，必须自己重建，不能直接照搬：

- `sub2api` 的 admin/user 双体系页面划分
- `sub2api` 的 API 组织方式
- `v2` 的 Next App Router 目录结构
- `v2` 的 React 组件实现

## 三、正式新 app 的目录职责矩阵

建议仍然以 `apps/platform-web-vue/src` 为根，职责收敛如下：

```text
src/
  main.ts
  App.vue
  router/
  layouts/
  modules/
  components/
    base/
    layout/
    platform/
  stores/
  composables/
  services/
  styles/
  types/
  utils/
```

各层职责建议固定如下：

### 1. `router/`

只负责：

- 路由表
- 路由守卫
- layout 挂载关系
- 登录与 workspace 访问控制

禁止负责：

- 页面数据请求
- 页面样式定义
- 业务状态缓存

### 2. `layouts/`

只负责：

- 页面总体骨架
- 左侧导航
- 顶部上下文条
- 主内容区容器
- auth 页骨架

建议至少包含：

- `AuthLayout`
- `WorkspaceLayout`
- `TablePageLayout`
- `DetailPageLayout`
- `WorkspaceToolLayout`

### 3. `components/base/`

只负责最基础、最稳定的可复用控件。

首批必须具备：

- `Button`
- `Input`
- `TextArea`
- `Select`
- `SearchInput`
- `DataTable`
- `Pagination`
- `BaseDialog`
- `ConfirmDialog`
- `Tabs`
- `Badge`
- `StatusBadge`
- `EmptyState`
- `LoadingState`
- `ErrorState`
- `Skeleton`
- `Toast`
- `ThemeToggle`
- `Icon`

### 4. `components/layout/`

负责骨架里的结构性组件。

首批建议具备：

- `AppSidebar`
- `AppHeader`
- `TopContextBar`
- `PageContainer`
- `PageHeader`
- `SectionCard`
- `FilterToolbar`

### 5. `components/platform/`

负责平台专属但跨页面复用的组件。

首批建议具备：

- `WorkspaceProjectSwitcher`
- `WorkspaceRoleBadge`
- `StateBanner`
- `SuccessBanner`
- `PageState`
- `ArtifactPreviewCard`
- `ArtifactActionBar`
- `ThreadListPanel`
- `ThreadDetailPanel`
- `ChatEntryGuide`
- `TestcaseOverviewStrip`

### 6. `modules/`

每个业务域自己维护：

- 页面
- 子组件
- composable
- 类型
- service 调用入口

建议一开始就按业务域拆开：

- `auth`
- `overview`
- `projects`
- `users`
- `assistants`
- `graphs`
- `runtime`
- `sql-agent`
- `threads`
- `chat`
- `testcase`
- `account`
- `audit`

### 7. `stores/`

只放全局状态：

- `auth`
- `workspace`
- `theme`
- `ui`

不要把列表数据、详情数据、临时筛选条件全部塞进全局 store。

### 8. `services/`

按业务域切分 API 访问层。

建议至少包含：

- `http/client.ts`
- `auth/auth.service.ts`
- `projects/projects.service.ts`
- `users/users.service.ts`
- `assistants/assistants.service.ts`
- `graphs/graphs.service.ts`
- `runtime/runtime.service.ts`
- `threads/threads.service.ts`
- `testcase/testcase.service.ts`
- `audit/audit.service.ts`

## 四、基座阶段必须先打好的五块能力

### 1. 主题与 token

必须优先完成：

- 颜色
- 阴影
- 圆角
- spacing
- 字体层级
- 明暗主题规则

因为后面所有组件都会依赖它。

### 2. 统一 layout

必须优先完成：

- 左侧主导航
- 顶部上下文条
- 主内容容器
- 页面头部

这是整站成熟感的第一来源。

### 3. 统一基础组件层

必须优先完成：

- 表单控件
- 表格控件
- 弹窗控件
- 三态控件
- 图标系统

没有这一层，后面页面一定会重新分叉。

### 4. 统一 workspace 上下文

必须优先完成：

- 当前用户
- 当前项目
- 当前角色
- 顶部上下文展示
- 项目切换行为

因为我们整站是工作台，不是普通内容站。

### 5. 统一文件操作抽象

必须优先完成一个统一的 artifact/document 能力层。

原因：

- 现在已经有 `pdf`
- 现在已经有 `image`
- 后面明确还会有 `docx`、`md` 等格式

所以不能每种文件类型都在页面里各写一套“预览 + 下载”逻辑。

建议新 app 一开始就抽出：

- `artifact.service`
- `useArtifactPreview`
- `ArtifactPreviewCard`
- `ArtifactActionBar`

## 五、哪些旧东西要带过去，哪些绝对不要

### 要带过去的是“抽象”

应该带过去的不是旧代码本身，而是下面这些抽象：

- `v2` 的 workspace 语义
- `v2` 的项目上下文切换能力
- `v2` 的业务域切分
- `sub2api` 的 token 和 layout 范式
- `sub2api` 的基础组件模型
- `sub2api` 的页面母版模型

### 绝对不要带过去的是“历史包袱”

不应该带过去的包括：

- `v2` 的 Next App Router 页面目录
- `v2` 的 React 组件实现
- `sub2api` 的上游业务页面和业务 API
- 超大单文件页面
- 页面内裸请求
- 页面内临时定义颜色、阴影、状态样式

## 六、Phase 1 的完成标准要再具体一点

新 app 的 Phase 1 完成，不应该只看“能跑起来”。

至少要同时满足下面这些标准：

- 登录页可用
- WorkspaceLayout 可用
- 左侧导航和顶部上下文条可用
- 主题切换完整生效
- 项目切换可用
- 基础按钮、输入框、表格、弹窗、分页可用
- Empty / Loading / Error 三态统一可用
- 预览与下载能力有统一入口

如果上面这些还没齐，就不能算真正进入业务迁移阶段。

## 七、最终收敛结论

新 app 的基座职责可以压缩成一句话：

- `v2` 提供业务真相
- `sub2api` 提供视觉骨架
- `apps/platform-web-vue` 负责把二者重组为长期可维护的正式前端

这就是后续所有迁移工作的边界线。
