# 01. 可行性评估

## 结论

结论很明确：

- 适合把 `sub2api` 当成新的前端视觉与交互基座
- 不适合把它整仓直接当成我们的正式前端来长期开发
- 适合“借壳迁移”
- 不适合“原地魔改”

## 为什么它适合作为候选基座

### 1. 视觉风格更贴近老板想要的成熟 SaaS 后台

`sub2api` 的观感优势主要体现在：

- 左侧主导航成熟稳定
- 顶部信息区不乱
- 卡片、按钮、表格、状态色是同一套语言
- 背景、阴影、留白和圆角控制得比较克制
- 没有明显“AI demo 模板味”

这正好对应当前目标：

- 页面更美观
- 更像正式企业产品
- 老板一眼看过去能接受

### 2. 前端基础设施是完整的

本地拉取代码后，当前看到的前端规模如下：

- `frontend/src` 文件数：`326`
- `frontend/src/views` 文件数：`65`
- `frontend/src/components` 文件数：`146`
- `frontend/src/api` 文件数：`38`

说明它不是一个纯视觉样板，而是一套完整产品前端，已有这些可复用基础设施：

- `Vue 3 + Vite + TypeScript`
- `Vue Router`
- `Pinia`
- `Axios API Client`
- `Tailwind CSS 3`
- `vue-i18n`
- 公共布局、表格页布局、toast、loading、dropdown、dialog、图表、表单能力

### 3. 本地验证通过

在 `apps/platform-web-sub2api-base/frontend` 下已完成：

- `pnpm install`
- `pnpm typecheck`
- `pnpm build`

结论：

- 这套前端基座在本地是可安装、可编译、可继续评估的

## 为什么不能直接在这套代码上一路硬改

### 1. 上游业务模型和我们完全不是一回事

`sub2api` 是：

- AI API Gateway
- 订阅、API Key、账户池、代理、兑换码、套餐、账单、Sora 等业务

我们的目标是：

- Agent Platform Console
- 项目、用户、助手、图谱、运行时、SQL Agent、Threads、Chat、Testcase

这两套业务模型几乎没有重合。

如果直接在它现有页面上强改，最后会出现：

- 目录名和业务不对应
- 路由名和功能不对应
- store 被塞满历史包袱
- API 模块名混乱
- 页面看起来像新产品，代码却是旧产品尸体拼起来的

### 2. 它当前工程边界不适合直接纳入我们的 monorepo

当前上游仓库路径是：

- `apps/platform-web-sub2api-base`

已知问题：

- 带有自己的 `.git`
- 前端构建输出默认写到 `../backend/internal/web/dist`
- 路由、store、API、文案、页面组织全部围绕上游产品设计

所以它现在更像：

- 一个上游参考仓库

而不是：

- 已经适配当前项目约束的正式 app

### 3. 现有代码也有明显的迁移风险

已观察到的问题：

- 许多页面组件体量偏大，单文件职责比较重
- 布局是“每个页面自己包 `AppLayout`”的方式，不是更清晰的嵌套路由布局
- 存在不少上游产品逻辑耦合
- 生产构建时有 chunk 警告
  - `AccountsView` 产物超过 `500 kB`
  - `vendor-ui` 产物超过 `400 kB`
- `app.ts` / `router.ts` 等模块存在动态导入与静态导入混用警告

这些不影响它作为基座参考，但说明：

- 如果直接拿来长期开发，后期会越来越乱

## 最终判断

### 推荐程度

- 视觉基座：高
- 技术基座：中高
- 直接成品复用：低

### 推荐策略

推荐采用下面这个策略：

1. 固定以 `apps/platform-web` 作为功能迁移基线
2. 把 `apps/platform-web-sub2api-base` 作为视觉与交互参考基座
3. 正式迁移时，在 `apps/platform-web-vue` 中持续承接开发
4. 只抽取有价值的视觉和交互资产
   - layout
   - style token
   - table/form/card/common
   - router/store/api 基础设施
5. 平台业务按 Vue 新架构逐页迁移并统一回刷

一句话：

- 功能看 `platform-web`
- 壳层学 `sub2api`
- 正式落地在 `platform-web-vue`
