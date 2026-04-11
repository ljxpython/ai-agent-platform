# Changelog

本项目的变更日志遵循 `docs/commit-and-changelog-guidelines.md` 的规范，并采用 Keep a Changelog 的结构。

## [Unreleased]

> 当前默认归档到下一版本：`v0.1.2`
>
> 维护规则：
>
> - 新的 `feat / fix / perf` 先补到下面对应分组
> - 发版前再从这里提炼成正式版本条目
> - 已经正式进入某个版本的内容，要从这里移走，别堆成一坨

### Added

- 待补充：新增能力、新页面、新入口、新模板

### Changed

- 待补充：交互收敛、视觉统一、工程化优化、性能改进

### Fixed

- 待补充：缺陷修复、兼容性问题、联调问题、回归问题

## [v0.1.1] - 2026-04-11

### Added

- 新增 `platform-api-v2` 控制面主线，补齐 runtime gateway、用户平台角色、testcase 管理与多类治理模块
- 新增 `runtime-service` 静态 graph 标准化骨架与 harness 开发范式说明，统一 assistant / deepagent / testcase 等运行时主线
- 新增 `platform-web-vue` 的系统治理、工作区导航、chat / sql-agent / testcase / threads 等演示主线路径补强

### Changed

- 统一 `platform-web-vue` 的品牌口径、侧边栏分组、顶栏下拉层、项目上下文与运行时目录刷新体验
- 将旧 `platform-api` / `platform-web` 主线收口到归档或兼容语境，正式入口切换为 `platform-api-v2` 与 `platform-web-vue`
- 重写根级文档、app docs 与正式架构图，使仓库叙事统一到 `AI Harness` 总哲学与当前正式链路

### Fixed

- 修复 chat 场景中的流式运行时契约对齐问题，稳定会话续接、工具结果展示与阅读跟随体验
- 修复 `platform-web-vue` 中的会话过期跳转、图表工具结果渲染与若干工作区交互收口问题
- 修复文档中仍把历史控制面 / 历史前端宿主当成当前默认实现的漂移问题

## [v0.1.0] - 2026-04-05

### Added

- 新增 `apps/platform-web-vue` 作为新的前端工作台宿主，承接迁移后的正式工作区布局与页面主线
- 新增 `chat / sql-agent / testcase / threads` 主线可演示能力，覆盖 agent 工作台、线程懒加载与文档链路
- 新增 `Resources / Playbook` 作为前端开发范式、页面母版与模板资源沉淀入口
- 新增演示环境、烟测、验收与汇报相关文档，固定 `Agent 工作台可演示版` 发版口径

### Changed

- 统一顶栏系统区交互，包括项目切换、语言切换、公告中心与用户菜单
- 统一列表页母版能力，包括 `DataTable / Pagination / 列设置 / 筛选设置 / ActionMenu / BulkActionsBar`
- 统一 `chat` 与 `sql-agent` 的执行态工作台、消息级操作、上下文抽屉与执行面板交互
- 对 dark mode、移动端与大屏布局做了专项收敛，修正关键页面占满、溢出与视觉一致性问题

### Fixed

- 修复线程页一次性展开所有 thread 内容导致的性能与可读性问题
- 修复 testcase 文档在线预览与原始下载主链路
- 修复 chat 中 retry / edit 后的分支挂载、默认最新分支与历史交互问题
- 修复多处顶栏、下拉、分页、筛选器与 tooltip 的交互一致性问题
