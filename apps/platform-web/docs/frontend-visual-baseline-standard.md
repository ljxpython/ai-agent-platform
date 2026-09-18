# Platform Web 前端视觉基线与使用范式

这份文档专门约束 `apps/platform-web` 的正式视觉壳层。目的很直接：后续任何人继续开发页面，都必须站在统一壳层上扩展，不准再把页面写成一堆散装的磨砂、发光、漂浮卡片。

---

## 1. 参考基线

正式参考基线固定为：

- 当前 `apps/platform-web/src/components`、`src/layouts` 和 `src/styles`

对齐重点不是照抄业务，而是继承这套前端的几个优点：

- 左侧主导航是实心、稳定、低干扰的
- 顶部上下文条轻，不抢页面主体
- 页面标题区简洁，不做夸张 hero
- 下拉、弹层、筛选、表格壳层保持同一套材质语言
- 主色只做强调，不把整页染成一片蓝绿

当前 `apps/platform-web` 的正式风格，也必须围绕这套基线继续收敛。

---

## 2. 视觉目标

统一目标只有五条：

- 稳：导航、顶部条、标题层级稳定，适合中后台长时间使用
- 克制：主色做强调，不做大面积染色和强对比炫技
- 一致：按钮、下拉、弹层、筛选条、卡片使用共享壳
- 可扩展：新页面只需要组合共享壳，不需要重新设计“页面皮肤”
- 可维护：一眼能看出哪些是布局壳、哪些是业务模块、哪些是强调态

---

## 3. 正式共享壳

下面这些是正式页面优先复用的共享壳，不允许绕开：

- 布局壳：
  - `WorkspaceLayout`
  - `AppSidebar`
  - `TopContextBar`
  - `PageHeader`
- 视觉基础类：
  - `pw-sidebar`
  - `pw-topbar`
  - `pw-page-shell`
  - `pw-page-header`
  - `pw-card`
  - `pw-card-subtle`
  - `pw-panel`
  - `pw-panel-lg`
  - `pw-panel-muted`
  - `pw-panel-muted-lg`
  - `pw-panel-info`
  - `pw-panel-success`
  - `pw-panel-warning`
  - `pw-filter-bar`
  - `pw-table-frame`
  - `pw-topbar-action`
  - `pw-topbar-dropdown`
  - `pw-dialog-panel`
  - `pw-pagination-shell`
- 基础组件：
  - `SurfaceCard`
  - `MetricCard`
  - `GuidePanel`
  - `StateBanner`
  - `FilterToolbar`
  - `PaginationBar`
  - `DataTable`

结论很简单：后续业务页面只组合这些壳，不重新发明新壳。

---

### 3.1 表单与高级交互组件基线（强制规范）

表单是控制面最核心的交互载体，严禁使用原生粗糙控件“裸奔”。必须遵循以下组件与设计规范：

1. **下拉选择框：强制使用 `BaseSelect.vue`**
   - **严禁**：在业务页中使用原生 `<select class="pw-input">`（macOS 会强弹蓝色粗暴系统浮层，破坏全局质感）。
   - **标准**：全量引入 `<BaseSelect v-model="..." :options="[{ value, label }]" />`。具备柔和阴影、平滑浮动定位、选中项蓝色高亮与对勾指示。
2. **连续数值与权重微调：滑块 + 伴生小输入框联动**
   - 适用于 `Temperature`、`Top P`、置信度等范围值微调。
   - 必须使用 `input[type="range"]` 与数字输入框双向实时同步，并附带直观的分段刻度指示（例如 `0.0 严谨 / 0.7 均衡 / 1.5 创意`），降低用户认知门槛。
3. **大额数值/Token 阈值输入：药丸快捷预设标签**
   - 适用于 `Max Tokens`、超时时间、分页大小等输入框。
   - 在输入框顶部或侧边提供快捷预设药丸按钮（如 `[2k, 4k, 8k, 16k, 清除]`），支持一键填充与重置。
4. **多选与功能授权网格：交互式卡片网格**
   - 严禁使用单调密集的原生 checkbox 列表。
   - 必须采用响应式卡片网格（Grid），卡片内含标题、`tool_key` 代码徽章、来源 Tag、以及一目了然的圆环勾选态和选中微光边框，并配备“全选 / 清空”辅助快捷动作。
5. **复杂配置页面的架构：双栏工作台架构（Form + Live Inspector）**
   - 严禁单列 20 个字段从上滑到下的大长条大白板。
   - 推荐使用 `xl:grid-cols-[1.28fr_0.72fr]`：左栏按业务领域进行卡片化表单分组；右栏实时响应用户输入，所见即所得呈现 Agent 实体预览与底层 Graph 拓扑说明。

---

## 4. 明确禁止

下面这些做法，后续开发默认视为不合格：

- 页面直接手写一套新的导航、顶部条、标题区
- 新增大面积 mesh、glow、彩色雾化背景
- 新增 `backdrop-blur` + `bg-white/80` + `shadow-soft` 这类散装玻璃壳
- 大量使用 `rounded-[24px]`、`rounded-[28px]` 这类随手写的大圆角
- 每个页面自己定义一套 hover、active、selected 颜色
- 用主色大面积铺底，把中后台做成营销页
- 在同一页面同时混用 2 到 3 套卡片材质语言
- **业务页面直接使用原生 `<select>` 标签**（必须使用 `BaseSelect.vue`）
- **长表单单列空荡荡排布**（复杂表单必须按业务领域卡片化并优先使用双栏预览架构）

典型反例：

- `rounded-[24px] border bg-white/80 shadow-soft backdrop-blur`
- `bg-primary-50/90 text-primary-700 shadow-card`
- `bg-white/95 border-white/70 shadow-card backdrop-blur-xl`

这些不是不能存在，而是必须被收敛到共享类里统一定义，不能散着长。

---

## 4.1 顶栏与品牌区硬约束

这一条后续必须死守，不能再飘：

- 左侧品牌区固定为 `36px` 图标容器 + 单行品牌标题
- 品牌区可以保留版本号，但版本只留在品牌区，不要再挂到顶部条里重复展示
- 顶部公告、语言、项目切换、用户菜单统一使用轻触发器
- 顶部入口默认无外边框、无白底胶囊、无额外阴影
- 公告入口优先保持图标型，不要把顶栏塞成长按钮
- 侧栏导航图标、标题字号、间距统一跟当前共享壳层同级，不准单页自己改大改小

一句话：品牌区和顶栏入口是整站门面，不允许哪个页面或哪个人临时“顺手改一下”。

---

## 5. 页面开发清单

### P0 壳层对齐

先统一公共壳层，再谈页面细节。`P0` 固定包括：

- `src/styles/index.css`
- `src/layouts/WorkspaceLayout.vue`
- `src/components/layout/AppSidebar.vue`
- `src/components/layout/TopContextBar.vue`
- `src/components/layout/PageHeader.vue`
- `src/components/layout/UserMenu.vue`
- `src/components/layout/LocaleSwitcher.vue`
- `src/components/layout/AnnouncementCenter.vue`
- `src/components/platform/WorkspaceProjectSwitcher.vue`

`P0` 完成标准：

- 左侧导航回到实心白底/深底的稳定壳
- 顶部条和标题区层级更轻
- 项目切换、语言切换、公告、用户菜单使用统一入口样式
- 下拉和弹层去掉过重磨砂、过大圆角和过厚阴影
- 侧栏品牌区保留图标 + 标题 + 版本号，顶部条不重复展示版本

### P1 页面清理

`P1` 优先处理汇报时最容易被老板看到的正式治理页：

- `src/modules/overview/pages/OverviewPage.vue`
- `src/modules/control-plane/pages/ControlPlanePage.vue`
- `src/modules/system-governance/pages/SystemGovernancePage.vue`
- `src/modules/platform-config/pages/PlatformConfigPage.vue`
- `src/modules/service-accounts/pages/ServiceAccountsPage.vue`

`P1` 目标：

- 先替换最扎眼的散装卡片壳
- 把嵌套卡片收敛到 `pw-card` / `pw-card-subtle`
- 把状态块、风险块、快捷入口块做成统一表达
- 列表、抽屉、详情弹窗优先使用 `pw-panel*` 系列，不再在页面里重新拼白玻璃卡片
- grid 页面默认先处理 `stretch` 问题，`SurfaceCard` 一律顶对齐，避免被同一行最高卡片拉成大白板

### P2 页面清理

Chat 视觉以重构前 `612fbde` 的 `pw-chat-workspace/stream/turn/composer/empty-state` 为基线；只恢复视觉，继续使用新 SDK、Transcript、审批和回执逻辑。Agent 是唯一聊天目标入口。


`P2` 覆盖 Chat 工作区、审批、工具/文件详情与保留管理页面：

- 沿用共享 tokens、按钮、表单和弹层，浅深主题保持相同结构。
- 390×844、1024×768、1440×900 都须能操作；弹层可滚动、键盘可关闭并恢复焦点。
- 输入和审批保持可达；流式更新不抢焦点、不强制回到底部。
- resources/examples、固定 SQL、退役 testcase 页面已移除，不再是产品或视觉基线。

---

## 6. 页面评审 Checklist

每次加页面或改页面，必须自己过一遍：

- 这个页面有没有直接手写新的视觉壳
- 标题区是否复用了 `PageHeader`
- 顶部交互入口是否复用了 `pw-topbar-action`
- 列表/筛选/分页是否复用了共享组件
- 卡片是否存在 3 套以上不同半径、阴影、背景材质
- 深色模式首屏是否与浅色模式保持一致结构
- 小分辨率下下拉、弹层、抽屉有没有越界或遮挡

只要上面有两条答不上来，这个页面就不能算完成。

---

## 7. 给后续开发者的硬规则

后续新增功能时，按这个顺序做：

1. 先看这份文档，确认页面属于哪类壳
2. 先查现有共享组件能不能复用
3. 不够用时，优先补共享壳，再让业务页面消费
4. 业务页面只负责内容编排，不负责重新定义材质
5. 提交前用 `rg` 检查有没有新增散装类名

建议自查命令：

```bash
# 1. 检查是否存在散装圆角、重磨砂或野蛮阴影
rg -n "rounded-\\[(24|26|28)px\\]|bg-white/(80|90|95)|backdrop-blur|shadow-soft|shadow-card" apps/platform-web/src

# 2. 检查是否有偷懒使用原生 <select>（必须改用 BaseSelect）
rg -n "<select" apps/platform-web/src
```

查出来不是绝对错误，但必须解释为什么没有走共享壳。
`rg "<select"` 查出若在业务页面中（非底座组件），Code Review 直接打回。
