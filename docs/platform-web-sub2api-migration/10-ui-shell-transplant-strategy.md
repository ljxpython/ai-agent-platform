# 10. UI 壳层迁移策略

## 结论

当前路线正式收敛为：

- `apps/platform-web-sub2api-base` 继续保留为只读参考仓
- `apps/platform-web-vue` 继续作为正式迁移目标 app
- 不直接在 `sub2api-base/frontend` 上长期开发
- 采用“借壳不借魂”的方式，把 `sub2api-base` 的成熟 UI 资产分层迁入 `platform-web-vue`

这里要先纠偏一件事。

这次迁移一开始确实是按“UI 壳层迁移”启动的，但随着 `platform-web-vue` 已经进入第二轮精修并完成多批真实业务页接入，这个表述已经不够准确。

现在的正确说法应该是：

- 不是只迁壳层
- 而是分三层迁移
  - 视觉母版
  - 系统交互母版
  - 业务页面

这里的“视觉母版”指的是：

- 设计 token
- 全局样式基座
- 布局骨架
- 基础视觉组件
- 图标与交互表达方式

这里的“系统交互母版”指的是：

- 分页
- 列表页搜索输入
- 多语言切换器
- 公告体系
- 顶栏个人下拉菜单
- toast / dialog / confirm
- navigation progress
- table page 的固定插槽与滚动方案

这里的“魂”指的是：

- 上游业务语义
- 上游路由树
- 上游鉴权模型
- 上游 API 组织方式
- 上游 admin / user 双体系页面

## 为什么不直接在 `sub2api-base/frontend` 上继续做

虽然 `sub2api-base` 的观感明显更成熟，但它不是一个只包含 UI 的模板仓。

它已经深度绑定了自己的：

- 用户侧与管理侧双体系路由
- 邮箱注册 / 2FA / OAuth / setup wizard
- 自己的 API client、公共设置、版本检测、后端模式开关
- 自己的业务页面与导航结构

如果直接在它上面删删改改，短期看似快，后面很容易出现：

- 路由语义被污染
- store 职责混乱
- API 模块命名带着上游业务残影
- 看起来像是“基于别人的产品硬改出来的前端”

这条路前期快，后期会烂。

## 为什么不继续只在 `platform-web-vue` 上小修小补

当前 `platform-web-vue` 的业务基座是对的，但视觉基座还不够成熟。

问题不只在颜色，而是整套系统都还没完全到位：

- 字号与字重节奏
- 导航密度
- 卡片与表格的层级关系
- 按钮、输入框、徽章、弹层的统一表达
- 顶部条与侧栏的品牌感
- 图标体系与空状态表达

继续在现有基础上零碎打补丁，收益会越来越低。

## 正式策略

### 1. 保留谁

正式承载 app 仍然是：

- `apps/platform-web-vue`

只读参考来源仍然是：

- `apps/platform-web-sub2api-base`

### 2. 迁什么

从 `sub2api-base` 中迁入以下资产类型：

- `tailwind.config.js` 的配色、阴影、渐变、动效 token 设计思路
- `src/style.css` 的全局样式基座
- `components/layout` 下的 Auth / Sidebar / Header / 容器骨架
- `components/common` / `components/icons` 中可抽象的基础 UI 表达
- `components/common` 中的系统级交互件与页面母版件
- 主题初始化与首屏无闪烁处理方式

### 3. 不迁什么

以下内容明确不进入正式方案：

- `views/auth/*` 中除登录视觉壳外的注册、重置密码、OAuth、2FA 业务实现
- `views/user/*`
- `views/admin/*`
- `views/setup/*`
- `stores/app.ts` 中和站点设置、版本检查、backend mode 强绑定的状态
- `stores/auth.ts` 中和上游接口契约强耦合的逻辑
- `api/*` 中上游业务接口实现
- 整套上游路由表

## 文件层面的处理原则

不是“直接复制文件后改一改”，而是按下面三类处理。

### A. 直接借用设计语言

这类文件主要提供视觉系统，不带强业务语义：

- `frontend/tailwind.config.js`
- `frontend/src/style.css`

处理方式：

- 以其为主，重写 `apps/platform-web-vue` 的 `tailwind.config.js`
- 以其为蓝本，重构 `apps/platform-web-vue/src/styles/index.css`

### B. 提取骨架，重写实现

这类文件方向对，但内部混了上游业务状态：

- `frontend/src/components/layout/AuthLayout.vue`
- `frontend/src/components/layout/AppSidebar.vue`
- `frontend/src/components/layout/AppHeader.vue`
- `frontend/src/components/layout/TablePageLayout.vue`
- `frontend/src/components/common/Pagination.vue`
- `frontend/src/components/common/LocaleSwitcher.vue`
- `frontend/src/components/common/AnnouncementBell.vue`
- `frontend/src/components/common/Toast.vue`
- `frontend/src/components/common/BaseDialog.vue`
- `frontend/src/components/common/ConfirmDialog.vue`
- `frontend/src/components/common/SearchInput.vue`
- `frontend/src/components/common/DataTable.vue`
- `frontend/src/components/common/NavigationProgress.vue`

处理方式：

- 保留视觉结构、布局关系和信息层级
- 保留组件职责与交互边界
- 替换为我们自己的路由、store、品牌文案和 workspace 上下文
- 不把上游业务 API、上游业务 store、上游 admin/user 语义直接带进来

### C. 只借思想，不借代码

这类文件耦合太重，不值得直接搬：

- `frontend/src/router/index.ts`
- `frontend/src/stores/app.ts`
- `frontend/src/stores/auth.ts`
- `frontend/src/api/*`

处理方式：

- 只参考组织方式和交互节奏
- 正式代码继续使用 `platform-web-vue` 自己的模块边界

## 正确的分层迁移法

这轮实际落地后的经验已经比较清楚，后面不能再按“先调一波样式，再看情况补组件”这么松散的方式做。

正式方法应该固定为下面三步。

### Step 1：先迁视觉母版

这一层解决的是“第一眼是否进入成熟后台审美区间”。

范围包括：

- token
- 全局样式
- auth / sidebar / topbar / workspace layout
- button / input / select / card / badge / empty state / banner

如果这层没完成，后面所有业务页都会显得散。

### Step 2：再迁系统交互母版

这一层解决的是“是不是只有样子像，还是连后台产品感都像”。

范围包括：

- 分页
- 搜索输入
- 顶栏语言切换
- 公告 bell 与公告弹层
- 顶栏个人菜单
- toast
- dialog / confirm
- 导航进度条
- 更成熟的表格容器与桌面/移动适配

这一步不补，页面会出现一种很典型的问题：

- 视觉已经像了
- 但一交互就露馅

### Step 3：最后迁业务页

业务页接入必须站在前两层之上。

否则会出现：

- 页面先落一版
- 后面为了补交互母版反复返工
- 每个模块写出自己的一套列表页和弹层逻辑

## 第一批要落的壳层改造

在 `apps/platform-web-vue` 中，第一批应优先处理这些点：

1. 重置设计 token
2. 重置全局样式基座
3. 改造登录页壳层
4. 改造 workspace 左侧导航
5. 改造顶部上下文条
6. 改造按钮 / 输入框 / 选择器 / 卡片 / 状态徽章 / 表格
7. 改造空状态、加载状态、筛选条和弹层

这些完成后，再去回刷：

- `overview`
- `projects`
- `users`
- `assistants`
- `me`
- `security`
- `audit`

## 实施顺序

### Phase A：视觉母版重置

目标：

- 让 `platform-web-vue` 的整体观感直接进入 `sub2api-base` 的审美区间

完成标准：

- 登录页、侧栏、顶栏、表格页母版明显切到新风格
- 现有首批页面无需重写业务即可同步变好看

### Phase B：系统交互母版补齐

目标：

- 让 `platform-web-vue` 不只是静态观感接近 `sub2api-base`
- 而是把成熟后台常见的系统交互也迁完整

完成标准：

- 顶栏具备语言切换、公告、个人菜单等成熟上下文操作
- 列表页具备统一分页、搜索输入和弹层策略
- toast / dialog / confirm / navigation progress 成为真正的系统级公共件

### Phase C：首批页面回刷

目标：

- 用新壳层统一第一批真实业务页

完成标准：

- 首批页面在视觉上不再像“同项目里混了两套设计”

### Phase D：复杂模块迁移

目标：

- 在新的壳层上继续做 `runtime / graphs / sql-agent / threads / chat / testcase`

完成标准：

- 复杂模块从第一天开始就长在正式视觉系统里，不需要后补大换皮

## 当前落地复盘

当前这轮已经完成的，其实不只是“换壳”：

- `tailwind.config.js` 的 teal/cyan token、阴影、渐变、背景光晕迁入
- `src/styles/index.css` 的 card / glass / sidebar / topbar / table / empty state / banner 基座重写
- `AuthLayout / AppSidebar / TopContextBar / WorkspaceLayout` 第二轮壳层精修
- `overview / projects / users / assistants / me / security / audit` 首批页面回刷到统一视觉语法
- `runtime / runtime models / runtime tools / graphs` 已迁成真实数据页
- `threads` 已迁成“先列表，后详情”的按需加载结构
- `chat` 已落首次引导与最近目标复用逻辑
- `testcase / cases / documents` 已具备正式工作区层级与文档预览下载前端链路

但同时也必须承认，当前还缺的正是系统交互母版这一层：

- `Pagination`
- `LocaleSwitcher`
- `AnnouncementBell`
- 顶栏个人下拉菜单
- `Toast / BaseDialog / ConfirmDialog`
- `SearchInput`
- 更完整的 `DataTable`
- `NavigationProgress`

所以这次迁移的下一步重点，不该再笼统表述成“继续做壳层”，而应该明确成：

- 补齐系统交互母版
- 再继续推进剩余业务页和复杂工作区

## 验收标准

这次分层迁移是否成功，按下面标准判断：

- 用户一眼能看出它更接近 `sub2api-base` 的成熟度，而不是当前 `platform-web-vue` 的简化版
- 不是只做到“样子像”，而是系统交互也进入成熟后台范式
- 现有业务接口、路由和 workspace 语义不被上游业务模型污染
- 页面改造以壳层替换为主，不出现大面积业务回归
- 后续复杂模块可以继续沿同一视觉范式开发

## 最终口径

这次不是“把 `sub2api` 前端整个搬过来”。

而是：

1. 把 `sub2api` 里最有价值的 UI 壳层资产抽出来
2. 把它们迁入 `apps/platform-web-vue`
3. 让 `apps/platform-web-vue` 成为既符合当前平台业务、又真正好看的正式新前端

## 当前未完成重点

当前还未完成：

- `sql-agent` 真实聊天画布接入
- `chat` 真实对话画布接入
- `testcase/generate` 真实 `test_case_agent` 对话模板接入
- 更完整的主题 preset 能力
- 更深层的系统交互组件体系沉淀
