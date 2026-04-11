# Platform Web Vue 迁移总览

这组文档现在要固化的是最终执行口径，而不是继续讨论候选方案：

- 功能迁移基线固定为 `apps/platform-web`
- 视觉、交互、展示风格基线固定为当前 `apps/platform-web-vue`
- `apps/platform-web-sub2api-base` 只作为视觉资产与交互参考源，不再作为正式开发载体
- `apps/platform-web-v2` 只保留为历史参考，不再作为本轮迁移目标
- 后续所有规划、开发、验收都按 `apps/platform-web -> apps/platform-web-vue` 这条主线推进

## 当前状态

- [x] 明确功能迁移基线为 `apps/platform-web`
- [x] 明确当前视觉与交互基线为 `apps/platform-web-vue`
- [x] 明确 `apps/platform-web-v2` 不再作为正式迁移目标
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
- [x] 完成 `assistants/new` 与 `assistants/:assistantId` 页面迁移，补齐创建与详情链路
- [x] 完成 `projects/:projectId` 页面迁移，补齐项目概览与成员预览入口
- [x] 完成 `users/:userId` 页面迁移，补齐资料、安全、项目访问与最近审计链路
- [x] 完成 `projects/new` 页面迁移，补齐项目创建与工作区切换链路
- [x] 完成 `users/new` 页面迁移，补齐用户创建链路
- [x] 完成 `projects/:projectId/members` 页面迁移，补齐项目成员增删改链路
- [x] 完成首轮视觉基座校准：layout / sidebar / topbar / table page layout / filter toolbar / stat card / empty state
- [x] 完成第二轮 UI 壳层精修：workspace sidebar / topbar / card / status / empty state / table 母版统一到 `sub2api-base` 风格区间
- [x] 明确当前已经进入“视觉母版几乎复刻”阶段，而不是停留在最初的壳层试探阶段
- [x] 完成 `runtime / runtime models / runtime tools / graphs` 目录型 agent 工作区迁移
- [x] 完成 `threads` 懒加载详情页迁移，不再一次性渲染所有 thread 内容
- [x] 完成 `chat` 首次进入引导、最近目标复用、真实线程复用与流式对话工作台迁移
- [x] 完成 `chat` 交互精修
  - 会话列表默认折叠，改为左侧抽屉进入
  - 运行上下文与参数改为右侧抽屉，并增加 `确定 / 还原`
  - 最近历史降级为调试折叠区，不再常驻主界面
  - 目标来源横幅支持手动关闭
- [x] `chat` 执行态工作台补齐
  - [x] 运行中取消
  - [x] Debug / Continue
  - [x] `todos / files` 执行面板
  - [x] interrupt / HITL 处理视图
  - [x] tool call 详情、sub-agent 卡片、artifact 侧栏
- [x] `chat` markdown 级 AI 输出渲染
- [x] `chat` 消息级操作与 history 第一版增强
  - 消息级复制 / 重试 / 编辑
  - retry / edit 后的 branch 切换与默认最新分支修正
  - thread history 搜索 / 状态筛选 / 时间分组 / 删除
- [x] `chat` 剩余体验差距
  - 更完整的 checkpoint history 可视化与“查看此分支”交互打磨
  - 移动端 sheet / 小屏抽屉体验补完
- [x] 完成 `sql-agent` 到通用 chat 基座的收敛，固定 `sql_agent` 对话已可直接使用
- [x] 完成 `testcase` 一级入口与 `generate / cases / documents` 三个子页迁移，并恢复文档在线预览 / 原始下载前端链路
- [x] 完成 `platform-web-vue` 本地 `pnpm check` 验证与浏览器基础烟测
- [x] 确认正式采用“借壳不借魂”的 UI 壳层迁移路线
- [x] 完成第一批系统级交互母版迁移
  - `Pagination`
  - `LocaleSwitcher`
  - `AnnouncementBell`
  - 顶栏公告中心演示替身与本地已读状态
  - `HelpTooltip` 第一批接入
  - 顶栏个人下拉菜单
  - `Toast / BaseDialog / ConfirmDialog`
  - `DataTable / SearchInput / NavigationProgress`
  - `BulkActionsBar`
  - dark mode 首屏主题初始化
  - 顶栏 `ProjectSwitcher / LocaleSwitcher / AnnouncementCenter / UserMenu` 同源化
  - `BaseSelect` Teleport 下拉定位与 `PaginationBar` 跳页
- [x] 完成 dev 环境 `UI 资产库` 初版入口，开始沉淀 testcase 页面与共享 UI 母版资源
- [x] 完成 dev 环境 `Resources` 三层收敛：`推荐模板 / 场景模板 / 模板库`
- [x] 完成 `团队推荐 Top 10` 独立资源页与跨页跳转
- [x] 确认当前阶段不再重开大范围 UI 风格试错，后续美化基于当前 `platform-web-vue` 持续收敛
- [x] 产出 `apps/platform-web -> apps/platform-web-vue` 页面与功能对照矩阵
- [x] 公告中心真实后端最小闭环已打通
  - `feed / read / read-all`
  - 前端优先走真实接口，失败回退本地公告数据
- [x] 完成公告后台管理第一版闭环
  - `/workspace/announcements` 管理页已落地
  - 后端已补齐 `list / create / update / delete`
  - 支持全局公告与项目公告维护
- [x] 完成第一批页面级引导面板接入
  - `overview` 演示路径引导
  - `projects` 项目入口引导
- [x] 完成演示与验收硬化文档归档
  - 固定演示环境、账号与推荐走查顺序
  - 固定关键链路烟测清单
  - 固定最终汇报口径与遗留项归档

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
   - `platform-web`、`sub2api`、正式新 app 各自负责什么
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
13. `13-page-function-parity-matrix.md`
   - `apps/platform-web` 到 `apps/platform-web-vue` 的页面/功能状态矩阵
   - 已完成、部分完成、未开始、暂缓项一览
   - 当前主线执行顺序
14. `14-frontend-development-playbook.md`
   - `platform-web-vue` 的正式前端开发范式手册
   - 新页面、表格页、详情页、工作区页该怎么做
   - 组件复用、视觉约束、i18n、主题与 Resources 使用顺序
15. `15-demo-environment-and-walkthrough.md`
   - 演示环境、启动命令、账号与推荐演示顺序
   - 老板汇报和联调走查都按这份手册执行
16. `16-smoke-test-and-acceptance-checklist.md`
   - 命令级校验、页面级烟测、主题与响应式验收清单
   - 当前已验证结果与非阻塞项归档
17. `17-demo-report-and-residual-risks.md`
   - 对外汇报口径
   - 当前遗留风险与后续执行口径

## 当前建议

当前正式路线已经收敛为：

1. 以 `apps/platform-web` 作为页面、功能、交互链路的唯一迁移真相源
2. 以当前 `apps/platform-web-vue` 作为视觉、交互、美化特效的持续演进基线
3. 只在需要补资产时再回看 `apps/platform-web-sub2api-base`，不再围绕它重新开一条 UI 主线
4. 页面迁移主线完成后，统一按演示硬化文档做回归与汇报
5. dev 环境的 `Resources` 只承担模板沉淀和参考作用，不再反向主导正式业务页设计
6. 后续新增前端功能默认先遵守 `14-frontend-development-playbook.md`，再进入模板挑选和页面实现阶段
7. 演示、烟测、汇报默认先看 `15`、`16`、`17` 三份文档

补充说明：

- `chat/sql-agent` 已完成“可用对话基座 + 执行态工作台 + markdown 输出 + 消息级操作 + checkpoint history 可视化 + 小屏抽屉体验”
- 这轮额外修掉了 retry branch 默认分支与切换挂载点不正确的问题
- 当前正式页面迁移已经完成，剩余主差距已经收敛到系统级一致性细节、首次引导体系扩展与最终演示硬化

当前锁定的执行顺序见：

1. [04-roadmap-and-checklist.md](./04-roadmap-and-checklist.md)
2. [07-module-migration-map-and-delivery-order.md](./07-module-migration-map-and-delivery-order.md)

## 已知注意事项

- `apps/platform-web-sub2api-base` 当前带有上游 `.git` 目录
- 正式纳入当前 monorepo 前，需要先去掉这个嵌套仓库边界
- `apps/platform-web-v3` 只是试验产物，已经从当前仓库工作目录移走，不再作为正式候选方案
- 当前 `platform-web-vue` 的剩余问题已经收敛到非主链路项、仓库整理项和后续增量优化项
