# 04. 路线图与总清单

## 基线锁定

这轮迁移从现在开始只认下面三条：

- 功能、页面、交互链路的迁移真相源是 `apps/platform-web`
- 视觉、交互、美化特效的演进基线是当前 `apps/platform-web-vue`
- `apps/platform-web-sub2api-base` 只作为按需回看的视觉资产库，不再作为正式目标

额外说明：

- `apps/platform-web-v2` 不再作为本轮功能迁移目标
- 后续不再重开大范围风格试错，默认沿当前 `platform-web-vue` 继续精修
- `Resources` 是 dev 资源中心，不是正式业务页的替代品

## 迁移目标

最终目标不是“换成 Vue”这么空的话，而是：

- 当前平台已有功能全部迁移成功
- 新前端符合老板审美
- 代码符合新的 Vue 技术架构规范
- 迁移过程可分阶段验收
- 任何阶段都能说明现在做到哪一步

## 分阶段路线

### Phase 0：评估与基座确认

目标：

- 确认 `sub2api` 方案可行
- 确认最终目标架构
- 不开始业务迁移

完成标准：

- 上游代码已拉到本地
- 技术栈已确认
- 本地构建已验证
- 裁剪方案已确认
- 迁移规范已成文

### Phase 1：新 Vue app 初始化

目标：

- 新建正式迁移 app
- 建立干净目录结构
- 提取 layout / theme / base component / router / store / api client

完成标准：

- 新 app 可运行
- 登录页可展示
- workspace layout 可展示
- 主题样式可展示
- 不含上游无关业务页面

### Phase 1.5：视觉母版复刻

目标：

- 把 `sub2api-base` 最值钱的视觉语言迁进来
- 让 `platform-web-vue` 第一眼观感进入成熟后台区间

范围：

- token
- 全局样式
- auth / sidebar / topbar / workspace layout
- button / input / select / card / badge / empty state / banner

完成标准：

- 整体壳层与首批页面视觉语法统一
- 不再是“Vue 新项目默认皮肤”，而是明显带有成熟后台产品感

### Phase 1.6：系统交互母版补齐

目标：

- 把成熟后台真正值钱的公共交互件补齐

范围：

- pagination
- locale switcher
- announcement bell
- user dropdown
- toast
- base dialog / confirm dialog
- search input
- navigation progress
- 更成熟的 data table 母版

完成标准：

- 顶栏系统操作完整
- 列表页交互完整
- 通知和弹层策略统一
- 业务页不再自行拼装分页和顶栏交互

### Phase 2：平台基础能力迁移

目标：

- 先把最基础的平台能力迁进来

范围：

- 登录
- 当前用户
- 当前项目切换
- overview
- projects
- users
- assistants
- me
- security
- audit

完成标准：

- 这些页面全部能跑
- API 接口改为我们自己的平台接口
- 不再依赖 `sub2api` 的上游业务 API

### Phase 3：复杂工作区迁移

目标：

- 迁最关键、最容易出问题的复杂页面

范围：

- graphs
- runtime
- sql-agent
- threads
- chat
- testcase
  - generate
  - cases
  - documents

完成标准：

- 交互链路完整
- 大对象渲染不炸
- 文档预览、下载、线程懒加载等能力保持不退化

### Phase 4：硬化与验收

目标：

- 收尾、压风险、准备汇报

范围：

- lint
- typecheck
- build
- 关键烟测
- 演示账号验证
- 页面细节统一

完成标准：

- 技术验收通过
- 演示可稳定复现
- 老板展示路径清晰

## 当前主线执行顺序

下面这份清单是当前真正要按顺序推进的主线，不再和历史 Phase 混着理解：

### 1. 基线冻结与盘点

- [x] 明确功能迁移基线为 `apps/platform-web`
- [x] 明确视觉与交互基线为当前 `apps/platform-web-vue`
- [x] 输出 `apps/platform-web -> apps/platform-web-vue` 页面/功能/状态链路对照矩阵
- [x] 为剩余页面补齐“来源页 / 目标页 / 依赖接口 / 风险点 / 验收口径”表

### 2. 高价值主线功能补齐

- [x] `sql-agent`
- [x] `chat`
- [x] `chat` 执行态工作台补齐
  - [x] 运行中取消
  - [x] Debug / Continue
  - [x] `todos / files` 执行面板
  - [x] interrupt / HITL 处理
  - [x] tool call 详情 / sub-agent 卡片 / artifact 侧栏
- [x] `chat` markdown 级 AI 输出渲染
- [x] `chat` 消息级操作与 history 增强
  - [x] 消息级复制 / 重试 / 编辑
  - [x] retry / edit 后的 branch 切换与默认最新分支修正
  - [x] thread history 搜索 / 状态筛选 / 时间分组 / 删除
- [x] `testcase/generate`
- [x] `assistants/detail`
- [x] `assistants/new`
- [x] `projects/detail`
- [x] `users/detail`

### 3. 系统级一致性与体验补完

- [x] `chat` 会话列表默认折叠，改为抽屉式进入
- [x] `chat` 运行上下文与参数改为草稿态编辑，并补齐 `确定 / 还原`
- [x] `chat` 最近历史保留为调试折叠区，不再常驻主画布
- [x] `chat` 目标来源提示支持手动关闭
- [x] `chat` checkpoint history 可视化与“查看此分支”交互细节
- [x] 公告真实数据接入或演示替身方案
- [x] tooltip / 帮助提示体系
- [x] 首次引导与入口提示体系
- [x] `Resources` 新增“前端开发范式”入口页，统一沉淀页面母版与组件复用口径
- [x] 输出 `platform-web-vue` 正式前端开发手册，后续开发默认先看当前仓库文档与 Resources
- [x] dark mode 全链路一致性复查
- [x] 大屏与小屏下关键页面占满与溢出复查

### 4. 汇报与验收硬化

- [x] 演示账号、演示数据、演示路径固化
- [x] 关键链路烟测清单固化
- [x] 最终汇报口径整理
- [x] 验收回归与遗留清单归档

### 5. Chat 执行态补齐顺序

- [x] 第一步：运行中取消
- [x] 第二步：Debug / Continue
- [x] 第三步：`todos / files` 执行面板
- [x] 第四步：interrupt / HITL
- [x] 第五步：tool call 详情、sub-agent 卡片、artifact 侧栏

## 总清单

### A. 当前评估阶段

- [x] 明确功能迁移基线为 `apps/platform-web`
- [x] 明确视觉与交互基线为当前 `apps/platform-web-vue`
- [x] 拉取 `sub2api` 到 `apps/platform-web-sub2api-base`
- [x] 确认上游前端技术栈
- [x] 完成本地 `install`
- [x] 完成本地 `typecheck`
- [x] 完成本地 `build`
- [x] 明确它适合作为视觉基座
- [x] 明确它不适合作为直接长期开发代码
- [x] 输出裁剪方案
- [x] 输出目标架构与编码规范
- [x] 输出 UI 参考分析与后续开发范式
- [x] 输出 `platform-web-vue` 前端开发范式手册，并接入 Resources 可视化入口
- [x] 输出新 app 基座蓝图与职责边界
- [x] 输出现有页面到新模块的迁移映射与交付顺序
- [x] 输出 `platform-web-vue` 的 package / script / env 初始化规范
- [x] 输出 Phase 1 前置决策收敛文档
- [x] 输出以 `apps/platform-web` 为源头的页面/功能对照矩阵

### B. 正式迁移前准备

- [x] 确认正式新 app 名称为 `apps/platform-web-vue`
- [ ] 去掉 `apps/platform-web-sub2api-base` 的嵌套 `.git` 边界
- [x] 确认保留 `vue-i18n` 能力，Phase 1 只维护 `zh-CN`
- [x] 明确保留国际化扩展位，不在 Phase 1 做全量英文落地
- [x] 确认正式主题命名与品牌命名
- [x] 确认演示环境接入方式
- [x] 确认 Vue 新 app 的 package / script / env 规范
- [x] 确认正式承载 app 仍然是 `apps/platform-web-vue`
- [x] 确认不直接在 `apps/platform-web-sub2api-base/frontend` 上长期开发
- [x] 确认采用“借壳不借魂”的 UI 壳层迁移路线
- [x] 确认当前正确迁移方法是“视觉母版 + 系统交互母版 + 业务页”的分层迁移

### C. 基座搭建

- [x] 新建正式 Vue app
- [x] 迁移并改造全局样式系统
- [x] 迁移并改造 layout
- [x] 建立路由结构
- [x] 建立 auth store / workspace store / ui store
- [x] 建立 axios client 与拦截器
- [x] 建立基础组件层
- [x] 建立平台组件层
- [x] 建立首轮页面母版与视觉基座校准
- [x] 以 `sub2api-base` 的 token / style / layout 为模板重置 `platform-web-vue` UI 壳层
- [x] 迁入并重写 `AuthLayout / AppSidebar / AppHeader` 的成熟视觉骨架
- [x] 用新壳层回刷首批真实页面视觉
- [x] 完成第二轮视觉母版精修，整体效果已进入“几乎复刻”区间

### D. 系统交互母版

- [x] 迁入统一 `Pagination` 组件
- [x] 迁入统一 `SearchInput` 组件
- [x] 迁入 `LocaleSwitcher`
- [x] 迁入 `AnnouncementBell`
- [x] 迁入顶栏个人下拉菜单
- [x] 迁入统一 `Toast`
- [x] 迁入统一 `BaseDialog`
- [x] 迁入统一 `ConfirmDialog`
- [x] 迁入 `NavigationProgress`
- [x] 评估并迁入更成熟的 `DataTable`
- [x] 迁入列表页列设置 dropdown
- [x] 迁入列表页筛选设置 dropdown
- [x] 迁入统一排序图标与排序状态持久化
- [x] 迁入统一 `ActionMenu`
- [x] 迁入统一 `BulkActionsBar`
- [x] 补齐 dark mode 首屏初始化与整站一致性
- [x] 评估并沉淀 dev 环境组件/页面展示中心
- [x] 将 dev 环境资源库收敛为 `推荐模板 / 场景模板 / 模板库` 三层结构
- [x] 将 `团队推荐 Top 10` 抽成独立资源页并接入分类页跳转

当前补充说明：

- `projects / users / audit` 已经回刷到统一分页母版
- 顶栏系统区已接入 `LocaleSwitcher / AnnouncementBell / UserMenu`
- `WorkspaceProjectSwitcher / LocaleSwitcher / AnnouncementCenter / UserMenu` 已统一顶栏触发器与 dropdown 壳层语法
- `AnnouncementBell` 已优先接入真实公告接口，异常时回退演示数据
- `projects / users / audit` 已经接入统一 `DataTable / 列设置 / 排序持久化 / ActionMenu`
- `projects / users` 已接入统一 `BulkActionsBar / 行选择`
- `assistants / runtime models / runtime tools` 已经接入统一 `DataTable / 列设置 / 排序持久化 / ActionMenu`
- `graphs / testcase cases / testcase documents` 已经接入统一 `DataTable` 母版
- `testcase cases / testcase documents` 已经接入统一 `筛选设置 dropdown`
- `BaseSelect` 已切到 `Teleport + fixed positioning`，统一页大小选择、项目切换等下拉层行为
- `PaginationBar` 已补齐跳页输入，`DataTable` 已支持桌面表格与移动端卡片双模
- `NavigationProgress` 已接入全局根组件导航监听，页面切换时会提供顶部进度反馈
- `index.html` 已在 Vue 挂载前完成主题 class 注入，dark mode 首屏不再等应用启动后再切换
- dev 环境已新增 `UI 资产库` 入口，先承接 testcase 页面资源与共享 UI 母版索引
- dev 环境资源子页默认不再直出整库模板，而是先展示可决策的推荐模板和场景模板

### E. 业务迁移

- [x] 登录
- [x] overview
- [x] projects
- [x] project detail
- [x] users
- [x] user detail
- [x] assistants
- [x] assistant detail
- [x] assistants new
- [x] graphs
- [x] runtime
- [x] runtime models
- [x] runtime tools
- [x] me
- [x] security
- [x] audit
- [x] sql-agent
- [x] threads
- [x] chat
- [x] testcase generate
- [x] testcase cases
- [x] testcase documents
- [x] 评估并迁入可重放的新手引导框架
- [x] 评估并迁入帮助提示与 tooltip 体系
- [ ] 评估用户属性配置能力的前后端契约
- [ ] 评估分组替换、分组排序等复杂后台操作的前后端契约

### F. 收尾与验收

- [x] lint 通过
- [x] typecheck 通过
- [x] build 通过
- [x] 关键页面烟测通过
- [x] 演示账号可登录
- [x] 首批页面的主题、按钮、表格、筛选器视觉统一
- [x] 形成最终汇报口径

## 验收口径

这次迁移是否成功，按下面标准判断：

### 技术验收

- 所有核心页面可以正常进入
- 没有关键白屏
- 没有关键交互退化
- 构建和类型检查通过

### 视觉验收

- 整体观感接近 `sub2api` 这类成熟 SaaS 后台
- 不再有明显“临时后台”或“AI 模板”气质
- 左侧导航、顶部上下文条、主内容区关系清晰

### 工程验收

- 目录结构清晰
- 路由分层清晰
- store 不膨胀
- API 模块按业务域拆分
- 页面不直接写裸请求

## 当前建议

当前已经完成页面迁移主线、系统级一致性补完和演示硬化文档归档。

下一步默认动作应该是：

1. 新增功能继续遵守 `14-frontend-development-playbook.md`
2. 演示与回归先按 `15`、`16`、`17` 三份文档执行
3. 非主链路遗留项单独排期处理，不再反向干扰正式迁移主线
