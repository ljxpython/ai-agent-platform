# 11. UI 差距盘点与下一批迁移资产

## 目标

这份文档专门回答三个问题：

1. 当前 `platform-web-vue` 这轮“几乎复刻”到底完成到了哪一层
2. `apps/platform-web-sub2api-base` 里还有哪些成熟能力和组件封装没迁过来
3. 下一批最值得迁移的资产是什么，优先级怎么排

## 一、当前真实状态

先把话说清楚。

当前 `platform-web-vue` 已经不是最开始那个简陋试验版了。

这轮完成后，已经明显进入下面这个状态：

- 视觉母版已经接近 `sub2api-base`
- 左侧主导航 + 顶部上下文条 + 主内容区已经稳定
- 首批页面和一批复杂工作区已经能在新视觉里正常承载

但它还没有达到“系统级交互也完整迁过来”的程度。

所以当前最准确的判断是：

- 视觉复刻接近完成
- 系统交互母版已经完成第一批高优先级能力
- 页面观感已经好了很多
- 但产品化细节和成熟后台的完整度还差一截

## 二、本轮已完成的高优先级补齐

本轮已经落地：

- 统一 `PaginationBar`
- 顶栏 `LocaleSwitcher`
- 顶栏 `AnnouncementCenter` 前端壳层、演示公告替身与本地已读态
- 第一批 `HelpTooltip` 母版与 chat 头部关键操作提示
- 顶栏 `UserMenu`
- 全局 `ToastStack`
- 通用 `BaseDialog / ConfirmDialog`
- 统一 `SearchInput`
- 全局 `NavigationProgress`
- 统一 `DataTable`
- 统一 `ActionMenu`
- 列设置 dropdown
- 筛选设置 dropdown
- 排序图标与排序状态持久化
- `projects / users / audit` 三张列表页回刷统一分页
- `projects / users / audit` 三张列表页回刷统一 DataTable 交互母版
- `assistants / runtime models / runtime tools` 三张列表页回刷统一 DataTable 交互母版
- `graphs / testcase cases / testcase documents` 三张页面回刷统一 DataTable 交互母版
- `runtime models / runtime tools` 已补齐客户端分页承载
- `testcase cases / testcase documents` 已补齐筛选设置 dropdown 与分页承载
- `projects / users` 已补齐统一 `BulkActionsBar` 与行选择
- `dark mode` 已补齐首屏主题注入，避免应用挂载前闪烁
- dev 环境已补齐 `UI 资产库` 入口，开始承接 testcase 页面资源与共享交互母版索引

当前仍然保留的真实边界：

- `AnnouncementCenter` 已有可演示的公告替身，但还没有接真实后端公告接口
- `HelpTooltip` 已接入第一批高频入口，但帮助提示体系还没做到全站覆盖
- 中英文切换现在先覆盖共享壳层文案，不是全站全文案翻译完成
- `BulkActionsBar / 行选择` 目前先落在 `projects / users`，更大范围页面回刷还在待办

## 三、当前已经迁过来的部分

### 1. 视觉基座

已完成：

- `tailwind.config.js` 中的主色、阴影、渐变、背景氛围迁入
- `src/styles/index.css` 中的全局卡片、侧栏、顶栏、表格、空态语法迁入
- `AuthLayout`
- `WorkspaceLayout`
- `AppSidebar`
- `TopContextBar`

这一层基本已经进入“几乎复刻”的区间。

### 2. 基础视觉组件

已完成或已有替代件：

- `BaseButton`
- `BaseInput`
- `BaseSelect`
- `SurfaceCard`
- `MetricCard`
- `EmptyState`
- `StateBanner`
- `StatusPill`
- `FilterToolbar`
- `WorkspaceProjectSwitcher`

这些组件已经能支撑第一批页面看起来比较统一。

### 3. 已接入的真实业务页

已接入：

- `overview`
- `projects`
- `users`
- `assistants`
- `runtime`
- `runtime/models`
- `runtime/tools`
- `graphs`
- `threads`
- `chat` 首次引导
- `testcase/cases`
- `testcase/documents`
- `me`
- `security`
- `audit`

## 四、还没迁过来的成熟能力

这部分才是你这次走查还能看出差距的根因。

### P0：必须优先迁的系统交互件

#### 1. 分页组件

参考：

- `apps/platform-web-sub2api-base/frontend/src/components/common/Pagination.vue`

当前问题：

- `platform-web-vue` 的列表页大多还是“拉一页固定条数”
- `threads` 虽然有上一页/下一页，但仍是页面内手写逻辑
- 没有统一页码、页大小、跳页、结果区间展示

为什么值钱：

- 这是成熟后台列表页的基础设施
- 一旦缺失，每个列表页都会自己写一套分页逻辑
- 后面越做越乱

结论：

- 必迁

#### 2. 中英文切换

参考：

- `apps/platform-web-sub2api-base/frontend/src/components/common/LocaleSwitcher.vue`
- `apps/platform-web-sub2api-base/frontend/src/i18n/index.ts`

当前问题：

- `platform-web-vue` 只保留了 `zh-CN`
- 有 `vue-i18n` 基础，但没有可切换产品能力
- 顶栏也没有 locale 入口

为什么值钱：

- 不是因为当前一定要做英文全量，而是因为用户已经明确点了这项能力
- `sub2api-base` 的做法比较轻，适合保留扩展位
- 顶栏缺这个入口，整体完成度会差一截

结论：

- Phase 1 不要求全量英文落地
- 但 locale switcher 的产品位和实现骨架值得迁

#### 3. 公告 bell 与公告弹层

参考：

- `apps/platform-web-sub2api-base/frontend/src/components/common/AnnouncementBell.vue`
- `apps/platform-web-sub2api-base/frontend/src/stores/announcements.ts`

当前问题：

- `platform-web-vue` 顶栏没有公告体系
- 没有未读提示
- 没有公告弹层和详情弹层

为什么值钱：

- 这是成熟后台非常典型的顶栏系统级能力
- 能明显提升“这不是纯业务壳，是完整后台产品”的感觉

结论：

- 必迁
- 但要改接我们的平台公告接口或先留空实现骨架

#### 4. 右上角个人下拉菜单

参考：

- `apps/platform-web-sub2api-base/frontend/src/components/layout/AppHeader.vue`

当前问题：

- `platform-web-vue` 顶栏右上角现在只有静态用户信息块
- 缺少账号菜单、退出登录、资料页跳转等上下文操作

为什么值钱：

- 用户感知非常强
- 没它就很像“半成品壳层”

结论：

- 必迁

#### 5. Toast / Dialog / Confirm

参考：

- `apps/platform-web-sub2api-base/frontend/src/components/common/Toast.vue`
- `apps/platform-web-sub2api-base/frontend/src/components/common/BaseDialog.vue`
- `apps/platform-web-sub2api-base/frontend/src/components/common/ConfirmDialog.vue`
- `apps/platform-web-sub2api-base/frontend/src/stores/app.ts`

当前问题：

- `platform-web-vue` 还没有成体系的全局通知和弹层母版
- 列表页后续一旦加编辑、删除、批量操作，就会被迫现场造轮子

为什么值钱：

- 这组能力决定后面业务页是不是还能保持工程化

结论：

- 必迁

### P1：强烈建议迁的列表页母版件

#### 6. SearchInput

参考：

- `apps/platform-web-sub2api-base/frontend/src/components/common/SearchInput.vue`

当前问题：

- `platform-web-vue` 各列表页搜索框还是页面内手写
- 样式虽然接近，但职责没有沉淀

结论：

- 建议迁

#### 6.1 列设置 dropdown

参考：

- `apps/platform-web-sub2api-base/frontend/src/views/admin/UsersView.vue`
- `apps/platform-web-sub2api-base/frontend/src/views/admin/AccountsView.vue`

当前问题：

- `platform-web-vue` 的列表页没有“列设置”入口
- 用户无法按场景隐藏次要列
- 也没有默认隐藏列和本地记忆

值钱的点：

- 列开关状态持久化到 `localStorage`
- 新列默认可见，老列可按页面预设隐藏
- 适合长表格和大屏后台

结论：

- 已完成首屏主题初始化
- 后续继续补的是更多页面、弹层、引导态的深色细节一致性
- 这是纯前端能力，可以先迁

#### 6.2 筛选设置 dropdown

参考：

- `apps/platform-web-sub2api-base/frontend/src/views/admin/UsersView.vue`

当前问题：

- 目前我们的筛选器基本是页面写死
- 没有“显示哪些筛选项”的设置能力
- 没有筛选器可见性与筛选值持久化

值钱的点：

- 可以让用户按场景控制筛选复杂度
- 动态属性筛选可以挂进同一入口
- 对复杂表格页很有产品感

结论：

- 必须加入优化清单
- UI 层可以先迁，但动态属性筛选需要后端配合

#### 7. DataTable

参考：

- `apps/platform-web-sub2api-base/frontend/src/components/common/DataTable.vue`

当前问题：

- 现有列表页大多仍是页面里手写 `<table>`
- 没有统一的移动端回退、排序、empty/loading 骨架、列 slot 约定

注意：

- `sub2api-base` 的 `DataTable` 能力很重
- 不建议整份生搬
- 应该做“按我们需求裁剪后的平台版 DataTable”

结论：

- 建议迁设计和职责边界
- 不建议全量照抄实现

#### 7.1 排序图标与排序行为

参考：

- `apps/platform-web-sub2api-base/frontend/src/components/common/DataTable.vue`
- `apps/platform-web-sub2api-base/frontend/src/views/admin/AccountsView.vue`

当前问题：

- 我们现在很多表格还是静态表头
- 没有统一的排序图标反馈
- 没有统一的排序状态存储

值钱的点：

- 表头点击反馈明确
- 排序状态可本地持久化
- 列级能力和 `DataTable` 一起沉淀

结论：

- 必须加入优化清单
- 排序可以先做前端本地版
- 如果未来要做服务端排序，需要后端支持稳定排序字段

#### 8. TablePageLayout 的固定区块语义

参考：

- `apps/platform-web-sub2api-base/frontend/src/components/layout/TablePageLayout.vue`

当前情况：

- `platform-web-vue` 已经有 `TablePageLayout`
- 但目前更多还是一个容器
- footer slot 也还没明确承担统一 pagination 语义

结论：

- 不是重做
- 而是补足它和 pagination / table / filters 的配合约定

### P1：强烈建议迁的系统反馈件

#### 9. NavigationProgress

参考：

- `apps/platform-web-sub2api-base/frontend/src/components/common/NavigationProgress.vue`

当前问题：

- 路由切换缺少全局加载反馈
- 大屏后台里这个细节很容易提升成熟度

结论：

- 建议迁

#### 10. 深色模式整站一致性

参考：

- `apps/platform-web-sub2api-base/frontend/src/main.ts`
- `apps/platform-web-sub2api-base/frontend/src/components/layout/AppSidebar.vue`
- `apps/platform-web-sub2api-base/frontend/src/styles/onboarding.css`

当前问题：

- `platform-web-vue` 现在有 dark mode，但整站级完成度还不够
- 很多页面只是基础颜色切换，不是完整的后台主题系统

值钱的点：

- 首屏挂载前就注入主题 class，避免闪烁
- layout、表格、弹层、引导弹窗都跟随 dark mode
- 是成熟后台的重要完成度指标

结论：

- 必须加入优化清单

#### 10. 更完整的 Toast Store

参考：

- `apps/platform-web-sub2api-base/frontend/src/stores/app.ts`

当前问题：

- `platform-web-vue` 的 `ui` store 只管 sidebar collapsed
- 缺少系统级 UI 状态容器

结论：

- 值得增加一个更聚焦的平台 UI store
- 但不要照搬 `sub2api-base` 那个大而全的 `app store`

## 四、哪些地方我们已经有了，但还没做到位

这部分不能说“没有”，而是“有雏形但不完整”。

### 1. 顶栏

当前已有：

- `TopContextBar`
- 项目切换器
- 角色显示
- 静态用户卡片

还缺：

- locale switcher
- announcement bell
- user dropdown
- 更像产品顶栏的系统操作编排

### 2. 列表页

当前已有：

- `TablePageLayout`
- `FilterToolbar`
- `EmptyState`
- `StatusPill`

还缺：

- unified pagination
- reusable search input
- data table abstraction
- confirm / dialog / toast
- column settings
- filter settings
- sort icons + sort persistence
- bulk actions bar 的更大范围回刷
- action menu
- import / export dialog
- auto refresh

### 3. 主题能力

当前已有：

- `light / dark`
- `workspace` preset 占位

还缺：

- 真正的 preset 扩展方式
- 顶栏/侧栏/表格等整站级联切换策略继续收口
- 引导、公告、弹层的 dark mode 完整适配

### 4. 引导与帮助能力

当前已有：

- 我们自己的 agent/chat 首次引导思路

还缺：

- 全局 onboarding store
- 可重放的新手引导入口
- 基于页面元素锚点的步骤体系
- 针对管理页的引导文案与流程编排
- `HelpTooltip` 这类轻量帮助提示

说明：

- 完整引导内容不是纯 UI 皮肤
- 但“引导框架”和“重放入口”属于成熟后台可复用基础设施

### 5. 弹窗与操作矩阵

参考范围很大：

- `Create/Edit` 系列 modal
- `GroupReplaceModal`
- `UserAttributesConfigModal`
- `AccountActionMenu`
- `ImportDataModal`
- `AnnouncementReadStatusDialog`

当前问题：

- 我们还没有形成系统的弹窗矩阵
- 复杂页面未来一旦补编辑/创建/删除/更多操作，很容易各写各的

结论：

- 这一层要纳入优化清单
- 但实现顺序要分层
  - 先公共 dialog/confirm/action menu
  - 再迁具体业务 modal 模式

## 五点五、Chat 执行态工作台缺口

这部分不是简单的“聊天页面样式没补完”，而是旧版 `apps/platform-web` 真正带业务含义的 agent 工作台能力还没迁完。

当前 `platform-web-vue` 已有：

- 首次引导
- 最近目标恢复
- 真实 thread / run / stream
- 会话抽屉
- 运行参数抽屉
- 运行中取消
- Debug / Continue
- `todos / files` 执行面板
- interrupt / HITL 处理视图
- tool call 详情卡片
- sub-agent 卡片
- artifact 侧栏与生成式 UI 承载位
- 图片 / PDF 附件发送
- 消息级复制 / 重试 / 编辑
- retry / edit 后的 branch 切换
- thread history 搜索 / 状态筛选 / 时间分组 / 删除
- retry branch 默认落点与共享消息挂载点修正

当前缺失：

- 更完整的系统级一致性复查
- 公告、帮助提示、引导这类产品化母版细节
- 最终汇报链路与演示硬化

结论：

- `chat` 现在已经不是“只有基座”的状态
- 主链路工作台已经成型
- history 可视化和小屏抽屉体验已经补齐
- 后续重点转向系统级一致性和最终演示硬化

执行顺序：

1. 系统级一致性复查
2. 演示与验收硬化

## 五、哪些不该迁

这部分也要说清楚，不然又会有人想着整仓复制。

明确不该迁：

- `sub2api-base` 的 admin / user 双体系路由结构
- 它的 `stores/app.ts` 全量实现
- 它的站点公共设置、版本检测、backend mode 逻辑
- 它和我们业务无关的账户、订阅、充值、兑换、Sora 等页面
- 它那些直接绑定自身 API 契约的业务弹窗和业务 modal

结论：

- 借的是交互母版
- 不是业务语义

补充一下边界：

- `UserAttributesConfigModal` 这种“能力形态”值得借
- 但字段结构、保存契约、权限模型不能直接照搬
- `GroupReplaceModal` 这种“交互模式”值得借
- 但替换逻辑和服务端语义必须重做

## 六、下一批优先级建议

### 第一优先级

- `Pagination`
- `LocaleSwitcher`
- `AnnouncementBell`
- 顶栏个人下拉菜单
- `Toast`
- `BaseDialog`
- `ConfirmDialog`
- 列设置 dropdown
- 筛选设置 dropdown
- 排序图标与排序状态沉淀
- 深色模式整站完善

这一批做完，用户最容易感知“像成熟后台”的那些缺口会先补上。

### 第二优先级

- `SearchInput`
- 平台版 `DataTable`
- `NavigationProgress`
- `TablePageLayout` 与分页/表格的固定搭配规范
- `ActionMenu`
- `BulkActionsBar` 的更大范围页面回刷
- 自动刷新与增量刷新母版
- 帮助提示与 tooltip 体系

这一批做完，后续所有列表页开发效率和一致性会明显提升。

### 第三优先级

- 更深一层的 page-state 组件族
- 更完整的 theme preset 扩展能力
- 更强的桌面/移动适配细节
- 可重放的新手引导框架
- dev 环境下的组件与页面展示中心扩容

## 七、后端依赖分层

这部分必须说清楚，不然后面会误以为所有功能都能纯前端迁完。

### A. 纯前端可先做

- dark mode 基础能力
- locale switcher 外壳
- column settings
- filter settings 外壳
- sort icon / sort state
- toast / dialog / confirm
- navigation progress
- action menu 外壳

这类功能即使后端完全不配合，也可以先在前端落地。

### B. 前端母版可先做，但需要接口喂数据

- announcement bell / popup / read status
- pagination 对接真实分页接口
- dynamic filters
- dynamic columns
- 用户分组展示
- 表格二级统计单元格

这类功能可以先把 UI 搭好，但没有数据契约时只能展示空态、占位或 `-`。

### C. 强依赖后端契约

- 用户属性配置
- 分组替换
- 分组排序保存
- 批量操作
- 导入 / 导出
- 账户增量刷新 / ETag 刷新
- 公告管理 / 阅读状态
- 余额历史 / 允许分组 / API keys / scheduled tests

这类功能如果后端不配合，前端最多只能保留弹窗壳和交互草图，不能算真正迁移完成。

## 八、页面不正确或接口未接通时的表现

这部分是实际落地时最容易踩坑的。

### 1. 纯前端功能缺失时

- 页面不会白屏
- 但会显得“像个静态壳”
- 常见表现是没有列设置、没有筛选设置、没有用户菜单、没有主题一致性

### 2. 二级数据接口缺失时

- 主表格可能还能展示
- 二级单元格会显示 `-`
- 或显示 loading skeleton 后进入 error 文本
- 或控制台报错但主页面不一定白屏

典型例子：

- today stats
- usage summary
- capacity summary
- user attribute values

### 3. 写操作接口缺失时

- 弹窗可以打开
- 但提交会失败
- 页面通常会保留当前状态
- 同时通过 toast 报错

典型例子：

- create / edit
- delete
- replace group
- sort order save
- balance change
- import / export

### 4. 过滤和排序契约不匹配时

- UI 看起来像支持筛选和排序
- 但结果不稳定
- 用户会以为页面坏了

所以这类功能要么先做纯前端版并明确边界，要么等后端契约一起落。

## 九、dev 环境展示中心建议

这个想法是对的，而且很有必要。

我建议未来在前端里加一个只在 `dev` 环境可见的展示入口，专门承载：

- 布局母版
- 顶栏功能件
- 表格母版
- 分页 / 筛选 / 列设置 / 排序
- toast / dialog / confirm / action menu
- 公告 / locale / theme
- 引导 / tooltip
- 典型复合页面
  - users
  - groups
  - accounts
  - announcements

这个入口的价值很大：

- 未来开发者可以直接挑成熟组件和页面范式
- 不需要翻参考仓和业务页抄代码
- 可以用 mock data 展示，不必绑定真实接口
- 可以把“推荐用法”和“禁忌用法”都写在页面里

但有两个前提：

- 只能在 `dev` 或 feature flag 下暴露
- 必须和正式业务路由隔离，避免混进生产导航

## 十、对后续开发的直接要求

从这一轮开始，后续页面开发要严格遵守下面的顺序：

1. 先判断是否已有对应母版
2. 没有母版先补公共件
3. 再写业务页

不允许继续这样做：

- 页面里手写分页
- 页面里手写搜索输入
- 页面里各写各的弹窗
- 顶栏每改一次都直接改页面壳

## 十一、最终结论

`platform-web-vue` 现在已经把“像不像 `sub2api-base`”这个问题解决了一大半。

真正还没收尾的，不是页面颜色和字体，而是这批成熟后台最关键的系统交互母版：

- 分页
- 中英文切换
- 公告
- 右上角个人下拉菜单
- toast / dialog / confirm
- 列设置
- 筛选设置
- 排序图标和排序状态
- 编辑/更多操作弹窗体系
- 深色模式整站一致性
- 可重放的新手引导框架
- 更成熟的列表页基础设施

下一阶段如果把这批东西迁进去，整个前端就不只是“视觉上接近”，而会在使用感和工程化程度上真正进入同一个级别。
