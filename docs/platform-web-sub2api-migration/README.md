# Platform Web Vue 迁移评估

这组文档用于固化一个新结论：

- 当前 `apps/platform-web-v2` 保留，作为可运行基线
- `sub2api` 已拉到本地，路径为 `apps/platform-web-sub2api-base`
- 后续如果正式切 Vue 路线，不在 `apps/platform-web-v2` 上继续堆 UI
- 先完成评估、裁剪、架构与规范设计，再进入真正的页面迁移

## 当前状态

- [x] 将 `sub2api` 上游代码拉取到本地
- [x] 确认其前端技术栈为 `Vue 3 + Vite + TypeScript + Vue Router + Pinia + Tailwind CSS 3`
- [x] 完成本地基础验证
  - `pnpm install`
  - `pnpm typecheck`
  - `pnpm build`
- [x] 确认它可以作为“视觉基座候选”
- [x] 确认它不能被当成“无脑直接复用”的成品前端
- [x] 完成 UI 参考前端的组件体系、布局体系与开发范式分析
- [x] 确认正式新 app 名称为 `apps/platform-web-vue`
- [x] 完成 `platform-web-vue` 的 package / script / env 初始化规范
- [x] 完成 Phase 1 前置决策收敛
- [x] 完成 `platform-web-vue` 最小可运行基座初始化
- [x] 完成真实登录链路、路由守卫与工作台上下文基座接入
- [x] 完成 `modules/` 目录下首批真实业务页面落地
- [x] 完成 `overview / projects / users / assistants / me / security / audit` 首批页面接入真实平台接口
- [x] 完成首轮视觉基座校准：layout / sidebar / topbar / table page layout / filter toolbar / stat card / empty state
- [x] 完成第二轮 UI 壳层精修：workspace sidebar / topbar / card / status / empty state / table 母版统一到 `sub2api-base` 风格区间
- [x] 明确当前已经进入“视觉母版几乎复刻”阶段，而不是停留在最初的壳层试探阶段
- [x] 完成 `runtime / runtime models / runtime tools / graphs` 目录型 agent 工作区迁移
- [x] 完成 `threads` 懒加载详情页迁移，不再一次性渲染所有 thread 内容
- [x] 完成 `chat` 首次进入引导与最近目标复用逻辑迁移
- [x] 完成 `testcase` 一级入口与 `cases / documents` 二级页迁移，并恢复文档在线预览 / 原始下载前端链路
- [x] 完成 `platform-web-vue` 本地 `pnpm check` 验证与浏览器基础烟测
- [x] 确认正式采用“借壳不借魂”的 UI 壳层迁移路线
- [x] 完成第一批系统级交互母版迁移
  - `Pagination`
  - `LocaleSwitcher`
  - `AnnouncementBell`
  - 顶栏个人下拉菜单
  - `Toast / BaseDialog / ConfirmDialog`
  - `DataTable / SearchInput / NavigationProgress`
  - `BulkActionsBar`
  - dark mode 首屏主题初始化
- [x] 完成 dev 环境 `UI 资产库` 初版入口，开始沉淀 testcase 页面与共享 UI 母版资源
- [x] 完成 dev 环境 `Resources` 三层收敛：`推荐模板 / 场景模板 / 模板库`
- [x] 完成 `团队推荐 Top 10` 独立资源页与跨页跳转

## 文档列表

1. `01-feasibility-assessment.md`
   - 是否适合迁移
   - 为什么适合
   - 为什么不能直接硬改
2. `02-pruning-plan.md`
   - 哪些保留
   - 哪些删除
   - 哪些必须重建
3. `03-target-architecture.md`
   - 迁移后的目标前端架构
   - 目录规范、路由规范、状态规范、API 规范、组件规范
4. `04-roadmap-and-checklist.md`
   - 分阶段实施路线
   - 总清单
   - 验收口径
5. `05-ui-reference-analysis-and-development-paradigm.md`
   - 参考前端用了什么框架和 UI 方式
   - 为什么它看起来更成熟
   - 我们后续应该采用什么开发范式
   - 新功能如何持续做出同等级观感
6. `06-foundation-blueprint-and-responsibility-matrix.md`
   - 新 app 基座怎么搭
   - `v2`、`sub2api`、正式新 app 各自负责什么
   - 哪些抽象应该迁入，哪些包袱不能带过去
7. `07-module-migration-map-and-delivery-order.md`
   - 现有页面到新模块的映射关系
   - 分阶段交付顺序
   - 各模块风险等级与迁移优先级
8. `08-package-script-and-env-conventions.md`
   - `platform-web-vue` 的包管理规范
   - 脚本规范
   - 环境变量与配置入口规范
9. `09-pre-migration-decisions.md`
   - `vue-i18n` 的保留策略
   - 品牌与主题命名
   - 演示环境接入方式
10. `10-ui-shell-transplant-strategy.md`
   - 为什么不直接在 `sub2api-base/frontend` 上长期开发
   - 为什么 `platform-web-vue` 仍然是正式承载 app
   - 哪些 UI 资产迁入，哪些上游业务实现不迁入
   - 从“借壳”纠偏到“视觉母版 + 系统交互母版 + 业务页”分层迁移的正确方法
11. `11-ui-shell-gap-analysis-and-next-assets.md`
   - 当前这轮“几乎复刻”到底完成到了哪一层
   - `sub2api-base` 里还有哪些成熟功能和组件封装没迁过来
   - 哪些值得迁，哪些不该迁，下一批优先级怎么排
12. `12-dev-ui-assets-gallery.md`
   - dev 环境 `UI 资产库` 的定位
   - testcase 页面资源如何沉淀进展示中心
   - `sub2api-base` 优秀前端页面如何作为参考区挂进去
   - 后续开发者如何把页面母版和共享交互件接入资源页

## 当前建议

当前推荐路线不是：

- 直接在 `apps/platform-web-sub2api-base/frontend` 里一路魔改

而是：

1. 先保留 `apps/platform-web-sub2api-base` 作为上游参考基座
2. 正式开工时，新建一个受当前 monorepo 管控的新 app
3. 先从 `sub2api/frontend` 中迁视觉母版：token、style、layout、基础视觉组件
4. 再迁系统交互母版：pagination、locale、announcement、user menu、toast、dialog、navigation progress
5. 严格不带入上游业务路由、业务 store 和 API 语义
6. 最后再把我们自己的平台业务页逐步接入

## 已知注意事项

- `apps/platform-web-sub2api-base` 当前带有上游 `.git` 目录
- 正式纳入当前 monorepo 前，需要先去掉这个嵌套仓库边界
- `apps/platform-web-v3` 只是试验产物，已经从当前仓库工作目录移走，不再作为正式候选方案
- 当前 `platform-web-vue` 的主要差距已经从“系统级交互母版缺失”转向“更大范围页面回刷、更多资源资产沉淀和深色细节统一”
