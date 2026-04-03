# 04. 路线图与总清单

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

## 总清单

### A. 当前评估阶段

- [x] 保留 `apps/platform-web-v2` 作为当前基线
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
- [x] 输出新 app 基座蓝图与职责边界
- [x] 输出现有页面到新模块的迁移映射与交付顺序
- [x] 输出 `platform-web-vue` 的 package / script / env 初始化规范
- [x] 输出 Phase 1 前置决策收敛文档

### B. 正式迁移前准备

- [x] 确认正式新 app 名称为 `apps/platform-web-vue`
- [ ] 去掉 `apps/platform-web-sub2api-base` 的嵌套 `.git` 边界
- [x] 确认保留 `vue-i18n` 能力，Phase 1 只维护 `zh-CN`
- [x] 确认正式主题命名与品牌命名
- [x] 确认演示环境接入方式
- [x] 确认 Vue 新 app 的 package / script / env 规范
- [x] 确认正式承载 app 仍然是 `apps/platform-web-vue`
- [x] 确认不直接在 `apps/platform-web-sub2api-base/frontend` 上长期开发
- [x] 确认采用“借壳不借魂”的 UI 壳层迁移路线

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
- [ ] 以 `sub2api-base` 的 token / style / layout 为模板重置 `platform-web-vue` UI 壳层
- [ ] 迁入并重写 `AuthLayout / AppSidebar / AppHeader` 的成熟视觉骨架
- [ ] 用新壳层回刷首批真实页面视觉

### D. 业务迁移

- [x] 登录
- [x] overview
- [x] projects
- [ ] project detail
- [x] users
- [ ] user detail
- [x] assistants
- [ ] assistant detail
- [ ] assistants new
- [ ] graphs
- [ ] runtime
- [ ] runtime models
- [ ] runtime tools
- [x] me
- [x] security
- [x] audit
- [ ] sql-agent
- [ ] threads
- [ ] chat
- [ ] testcase generate
- [ ] testcase cases
- [ ] testcase documents

### E. 收尾与验收

- [x] lint 通过
- [x] typecheck 通过
- [x] build 通过
- [x] 关键页面烟测通过
- [x] 演示账号可登录
- [x] 首批页面的主题、按钮、表格、筛选器视觉统一
- [ ] 形成最终汇报口径

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

当前已经可以进入下一步，但下一步不是直接开写业务迁移，而是：

1. 先按 `apps/platform-web-vue` 执行 UI 壳层重置
2. 用 `sub2api-base` 的成熟视觉骨架替换当前简化版 layout / token / base component 表达
3. 再进入复杂业务模块迁移
