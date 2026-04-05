# 05. UI 参考分析与后续开发范式

## 目标

这份文档回答五个问题：

1. `sub2api` 这个参考前端到底用了什么框架和 UI 方式
2. 它到底有没有依赖成熟中后台组件库
3. 为什么它整体观感明显比普通后台更成熟
4. 我们后续迁移时，应该采用什么范式，才能持续做出同等级的页面
5. 未来新增一个功能时，具体应该怎么落地，才能不把风格做散

补充说明：

- 这份文档负责解释“为什么”
- 正式执行口径已经沉淀到 `14-frontend-development-playbook.md`
- 后续开发默认先看 `14`，需要追溯参考来源时再回看这份 `05`

## 一、它实际用了什么

### 1. 前端基础技术栈

参考文件：

- `apps/platform-web-sub2api-base/frontend/package.json`

当前可确认的基础栈：

- `Vue 3`
- `Vite`
- `TypeScript`
- `Vue Router`
- `Pinia`
- `Axios`
- `vue-i18n`
- `Tailwind CSS 3`
- `Vitest`

配套能力库：

- `@vueuse/core`
- `@tanstack/vue-virtual`
- `chart.js` / `vue-chartjs`
- `driver.js`
- `vue-draggable-plus`
- `marked`
- `file-saver`
- `xlsx`
- `qrcode`

结论很明确：

- 它是一个 `Vue 3 + Tailwind CSS 3` 的前端
- 它不是那种“拿一个重型后台模板，换个 logo 就上线”的项目

### 2. 它没有依赖重型 UI 组件库

排查结果：

- 没有发现 `Element Plus`
- 没有发现 `Naive UI`
- 没有发现 `Ant Design Vue`
- 没有发现 `Vuetify`
- 没有发现 `PrimeVue`

这意味着一件事：

- 它的观感成熟，不是靠一个现成 UI 框架替它完成的
- 它真正依赖的是“自建视觉系统 + 自建基础组件层 + 稳定页面母版”

### 3. 它的图标也不是混着乱用

参考文件：

- `apps/platform-web-sub2api-base/frontend/src/components/icons/Icon.vue`
- `apps/platform-web-sub2api-base/frontend/src/components/common/ModelIcon.vue`

实际情况：

- 日常页面图标主要通过 `Icon.vue` 统一封装
- `Icon.vue` 里维护了统一的 SVG path map
- `@lobehub/icons` 没有被拿来当整站主图标系统
- 它只在 `ModelIcon.vue` 这种“模型品牌图标”场景里做补充

这个做法是对的，因为：

- 导航、按钮、筛选、状态图标必须统一笔触和节奏
- 模型品牌 icon 是少量特例，可以独立处理

## 二、它真正值钱的 UI 结构是什么

### 1. 第一层：设计 token

参考文件：

- `apps/platform-web-sub2api-base/frontend/tailwind.config.js`

它先定义了一层比较完整的设计 token：

- 颜色：`primary`、`accent`、`dark`
- 阴影：`glass`、`card`、`glow`
- 背景：`mesh-gradient`、`gradient-primary`
- 动画：`fade-in`、`slide-up`、`scale-in`
- 圆角：如 `4xl`

这层 token 的意义不是“好看一点”，而是：

- 后续所有组件有统一的颜色来源
- 状态、层级、悬浮、主题切换都能收敛
- 页面不会出现一会儿青色、一会儿蓝色、一会儿随手写十几个 hex 的混乱局面

### 2. 第二层：语义化样式类

参考文件：

- `apps/platform-web-sub2api-base/frontend/src/style.css`

它没有停在“全项目到处手写 Tailwind utility class”这一步，而是继续抽了一层语义类：

- `.btn`
- `.btn-primary`
- `.btn-secondary`
- `.btn-ghost`
- `.input`
- `.glass`
- `.glass-card`
- `.card`
- `.stat-card`

这一步非常关键，因为它把“样式选择权”从页面开发者手里收回了一半。

结果就是：

- 新页面默认长得像同一个产品
- 按钮、输入框、卡片不会每页一个样
- 主题切换和视觉升级不需要全站翻文件

### 3. 第三层：轻量基础组件库

参考目录：

- `apps/platform-web-sub2api-base/frontend/src/components/common`

它其实已经有一套轻量基础组件库，不是没有组件库，只是不是第三方重型库。

典型组件包括：

- `Input.vue`
- `Select.vue`
- `SearchInput.vue`
- `DataTable.vue`
- `BaseDialog.vue`
- `ConfirmDialog.vue`
- `Pagination.vue`
- `StatusBadge.vue`
- `EmptyState.vue`
- `Skeleton.vue`
- `Toast.vue`
- `Toggle.vue`
- `DateRangePicker.vue`

这套东西的价值在于：

- 交互风格统一
- 接口类型统一
- 业务页面只做拼装，不自己发明控件

### 4. 第四层：稳定 layout 与页面母版

参考文件：

- `apps/platform-web-sub2api-base/frontend/src/components/layout/AppLayout.vue`
- `apps/platform-web-sub2api-base/frontend/src/components/layout/AppHeader.vue`
- `apps/platform-web-sub2api-base/frontend/src/components/layout/AppSidebar.vue`
- `apps/platform-web-sub2api-base/frontend/src/components/layout/AuthLayout.vue`
- `apps/platform-web-sub2api-base/frontend/src/components/layout/TablePageLayout.vue`

它真正成熟的地方，是布局和页面母版非常稳定。

最典型的结构是：

- 左侧主导航
- 顶部上下文区
- 主内容区

列表页进一步固化为：

- `actions`
- `filters`
- `table`
- `pagination`

这意味着：

- 页面不是自由排布
- 而是先选母版，再往母版里填内容

### 5. 第五层：页面按范式开发，而不是按灵感开发

参考文件：

- `apps/platform-web-sub2api-base/frontend/src/views/admin/UsersView.vue`

以用户列表页为例，它的开发思路是：

1. 外层用 `AppLayout`
2. 列表母版用 `TablePageLayout`
3. 筛选区通过 `filters` slot 放进去
4. 表格区通过 `DataTable` 统一处理
5. 细胞级样式通过 `cell-*` slot 定制

所以它的页面虽然信息很多，但仍然是稳的。

## 三、它为什么能做得更好看

不是因为它“更会用 Tailwind”，而是因为它做对了下面几件事。

### 1. 它先搭系统，再搭页面

普通项目的问题通常是：

- 先写页面
- 写到哪算哪
- 后面再补组件

`sub2api` 的好处在于：

- 先有 token
- 再有基础样式类
- 再有基础组件
- 再有 layout 和 page pattern
- 页面只是最后一层

所以它的视觉能稳定复用，不会做一页像一页。

### 2. 它的层级感非常清楚

它的层级主要靠这些东西控制：

- 背景与内容容器的明暗差
- 卡片边框和阴影
- 顶部和侧边导航的稳定分区
- 统一的圆角体系
- 状态色和主色的克制使用

这会让页面“像产品”，而不是“像管理后台拼图”。

### 3. 它控制住了页面自由度

它没有给开发者太多“随便发挥”的空间：

- 按钮有既定变体
- 输入框有既定样式
- 表格有既定容器
- 弹窗有既定结构
- 列表页有既定母版

这点对我们尤其重要。

因为一旦每个新页面都能自由决定：

- 间距
- 圆角
- 色板
- 图标
- 卡片结构

那几周以后整站一定会再次变散。

### 4. 它的“设计感”来自克制，而不是炫技

它有渐变、有玻璃感、有背景装饰，但没有过量。

它好的地方是：

- 装饰主要放在 layout 和认证页
- 业务页还是以可读性、信息密度和清晰层级为主
- 视觉亮点被控制在少数位置

这也是为什么它不像很多 AI 模板那样“第一眼很炸，第二眼就廉价”。

## 四、我们未来应该采用什么范式

后续不管我们是迁移旧功能，还是开发新功能，都不能只学它的颜色和 CSS。

我们应该明确采用下面这套范式。

### 1. 三层 UI 结构范式

未来新 app 的 UI 层必须固定成三层：

1. `design tokens`
   - 颜色
   - 阴影
   - 圆角
   - spacing
   - 字体层级
   - 动画
2. `base components`
   - button
   - input
   - select
   - table
   - badge
   - modal
   - tabs
   - empty
   - loading
3. `page patterns / layouts`
   - auth page
   - dashboard page
   - table page
   - detail page
   - workspace page

结论：

- 页面不直接越级决定视觉
- 页面只能在既有 token、组件、母版之上组合

### 2. 新功能开发先分页面类型

以后开一个新功能，不是先开文件写 JSX/Vue template，而是先判断它属于哪种页面。

建议固定为以下几类：

- `dashboard`
- `table/list`
- `detail/form`
- `workspace/tool`
- `settings/security`

每一类页面都应该有对应母版。

比如：

- 列表页必须走 `TablePageLayout`
- 详情页必须走 `DetailPageLayout`
- 工作台页必须走 `WorkspaceLayout`

如果没有母版，先补母版，不要直接糊页面。

### 3. 页面只做编排，不承担底层视觉定义

页面文件应该负责：

- 拼装模块
- 绑定数据
- 控制业务流程

页面文件不应该负责：

- 临时定义按钮样式
- 临时定义表格结构
- 临时定义状态 badge 颜色
- 临时堆一组新的阴影和背景

一句话：

- 页面写业务
- 组件写交互
- token 写视觉规则

### 4. 图标、状态色、空态、加载态必须统一

这部分最容易被做散，所以必须固定。

未来要求：

- 页面图标统一走一个 `Icon` facade
- 品牌类图标单独走 `ModelIcon` 或同类 facade
- 成功、警告、危险、信息状态色必须固定
- Empty / Loading / Error 三态必须有统一组件

不允许出现：

- 这个页面用 Heroicons
- 那个页面用 Lucide
- 另一个页面又直接贴 SVG

### 5. 复杂交互下沉，不把页面写成巨型文件

新功能如果有复杂交互，应该下沉到：

- `composables`
- `services`
- `components/platform`

不要把一个页面写成：

- 请求
- 状态
- 渲染
- 动画
- 弹窗逻辑
- 表单校验

全塞一个文件。

视觉之所以容易崩，很多时候不是设计差，而是页面过于臃肿，没人敢收拾。

## 五、我们自己的开发范式建议

这部分是后续真正落地时要执行的开发流程。

### Step 1：先选母版

在开始新功能前，先回答：

- 这是列表页、详情页、工作台页还是仪表盘页
- 对应母版是否已经存在

如果不存在：

- 先补母版
- 再开发业务

### Step 2：再列出需要复用的基础组件

比如一个新页面需要：

- 搜索框
- 状态筛选
- 表格
- 分页
- 右侧详情弹窗

那就先确认是否已有：

- `SearchInput`
- `Select`
- `DataTable`
- `Pagination`
- `BaseDialog`

缺哪个补哪个，不要在页面里临时发明。

### Step 3：最后才开始写业务内容

业务开发阶段只关心：

- API 对接
- 数据状态
- 交互流程
- cell slot 的业务化展示

而不是重新决定：

- 按钮长什么样
- 卡片边框怎么写
- hover 阴影怎么配

### Step 4：开发完必须走视觉验收

每个新页面完成后，至少检查这些：

- 是否复用了既有 layout
- 是否复用了既有基础组件
- 是否新增了不受控颜色
- 是否新增了不受控阴影和圆角
- 是否出现多个图标体系混用
- 是否有统一的 empty / loading / error
- 是否在大屏和常规屏都占满内容区
- 是否与已有页面观感一致

## 六、未来新增一个功能时，如何做出同等级美观效果

如果后续要开发新功能，建议固定按照下面这条路径。

### 路径 1：先定义信息结构

先想清楚：

- 这个页面的主任务是什么
- 主操作是什么
- 次操作是什么
- 哪些信息需要常驻
- 哪些信息适合折叠

很多“丑”的页面，本质上不是颜色不对，而是信息结构乱。

### 路径 2：再套页面骨架

然后把信息装进固定骨架：

- 左侧导航
- 顶部上下文条
- 主内容区
- 页面标题区
- 操作区
- 筛选区
- 内容区

不要直接从内容块往上拼。

### 路径 3：再使用语义化组件

页面里优先使用：

- `Button`
- `Input`
- `Select`
- `Badge`
- `Table`
- `Dialog`
- `Tabs`

而不是优先使用：

- 一堆裸 `div`
- 一堆局部 utility class
- 一堆临时 hover/focus 样式

### 路径 4：最后才做少量差异化设计

真正的“设计感”，应该只出现在少量位置：

- 页面标题区
- 统计区
- 空态
- onboarding
- 重要 CTA

业务主体区还是应该保持冷静、稳定、可读。

## 七、对我们迁移方案的直接结论

基于这轮调研，结论已经比较清楚。

### 可以借鉴的部分

- `Vue 3 + Vite + TypeScript + Tailwind 3` 这套技术组合
- Tailwind token 体系
- 语义化基础样式类
- 轻量基础组件库
- 统一 icon facade
- 左侧导航 + 顶部上下文条 + 主内容区的 layout
- 列表页和认证页的页面母版思路

### 不能照抄的部分

- 上游业务路由
- 上游 API 组织
- 上游大而全页面文件
- 上游与我们业务无关的模块

### 我们真正应该迁移的，不是“几张页面”

真正该迁移的是这三层能力：

1. 设计 token
2. 系统交互基础组件
3. 页面母版

这里要再补一句这轮迁移后的实际经验。

一开始我们说“迁 token、基础组件、页面母版”是对的，但这次真正推进到 `platform-web-vue` 以后，发现“基础组件”还得再拆一层，不然很容易只迁到视觉，不迁到产品化交互。

更准确的表达应该是四层：

1. 设计 token
2. 基础视觉组件
3. 系统交互组件
4. 页面母版

这里的系统交互组件主要就是：

- pagination
- locale switcher
- announcement bell
- user dropdown
- toast
- dialog
- confirm
- search input
- navigation progress

如果只迁页面皮相，不迁这层系统交互，后续新增功能还是会迅速把风格和交互都做散。

## 八、后续执行要求

后续进入正式 Vue 迁移时，建议把下面这些要求当成硬规则：

- 不允许页面直接定义新的主色体系
- 不允许页面直接发明新的按钮和表单样式
- 不允许页面继续手写系统交互件替代公共件
- 不允许混用多套图标系统
- 不允许列表页脱离母版自由排布
- 不允许把复杂页面继续写成超大单文件
- 新功能必须先选母版，再选组件，再接业务

## 最终结论

`sub2api` 的成熟感，不是来自某个现成 UI 框架，而是来自一套完整的前端产品化方法：

- 用 `Tailwind token` 统一视觉规则
- 用轻量 `base components` 统一交互部件
- 用 `layout + page pattern` 统一页面结构

我们后续如果想稳定做出同等级效果，必须迁移并固化这套方法，而不是只模仿它某几张页面的样子。
