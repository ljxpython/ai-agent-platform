# Chat 前端收敛方案

## 当前冻结说明

- 本文档记录的是 chat 前端第一阶段收敛原则、UX 规则和拆包策略。
- 从“聊天流内核”角度看，后续正式迁移方案已经单独冻结到：
  - `./chat-langchain-vue-migration-blueprint.md`
- 后续凡是涉及 `useChatWorkspace`、流式消息、branch / interrupt / tool call 真相源的改造，以那份蓝图为准；本文继续负责页面壳、UX 规则、展示层拆分原则。

## 最新联调状态（2026-04-07）

- `testcase agent` 文本流式对话已真实打通，前端可创建 thread、发送消息、实时拿到 agent 回复。
- 图片附件对话已真实打通，上传后的图片会作为消息内容提交到 `runs/stream`，页面能看到附件卡片、工具调用和最终回复。
- PDF 附件入口已补一轮真实联调：
  - 页面：`/workspace/testcase/generate`
  - 验证线程：`c9d78156-694c-474a-ae79-8d5f99c2380c`
  - 当前附件状态为 `parsed`，不再因为 PDF 摘要模型失败直接落成 `failed`
  - 如果摘要模型不可用，会退回到“基于已抽取文本继续分析”的降级路径
- 旧坏线程已隔离：
  - 坏线程：`281a09cb-2d5a-4b06-aa44-4139a4d22bb1`
  - 默认打开 `/workspace/chat` 时，不再自动落入该线程
  - 显式打开该线程时，页面会展示“历史线程状态损坏，建议新开对话继续”的 warning
- chat composable 已完成第一轮拆包：
  - `useChatWorkspace.ts` 退回编排层
  - 新增 `usePlatformChatStream.ts` 承接流式消息内核
  - 新增 `useChatThreadWorkspace.ts` 承接 thread 列表 / 详情 / 坏线程隔离
- chat composable 已完成第二轮拆包：
  - `usePlatformChatStream.ts` 继续收口到编排层
  - 新增 `platform-chat-stream/helpers.ts`
  - 新增 `platform-chat-stream/actions.ts`
  - 运行参数构建、interrupt / thread failure 推导、send / retry / resume / cancel 等逻辑已从主文件拆出
- 修复记录：
  - 浏览器本地开发环境下，`127.0.0.1` / `localhost` 混用会导致 LangGraph SDK 流式请求跨域或 URL 解析异常；现在前端统一回到同源绝对地址。
  - `useStream.submit()` 不能直接提交 `HumanMessage` 类实例；现在统一提交标准消息字典，避免服务端出现 `MESSAGE_COERCION_FAILURE`。
- 当前如果还看到某些旧 thread 的 `state 400`，优先判断是否为修复前产生的坏线程，不要先怀疑现在线路又炸了。

## 目标

- 保持 `apps/platform-web` 现有视觉风格、主题变量、组件体系不变。
- 吸收 `2026-03-21-testing-deep-agents-ui` 在聊天产品上的逻辑优点。
- 让 chat 基座成为后续 `sql-agent`、`research`、`testcase`、`audit` 等页面复用的工程底座。

## 非目标

- 不迁移 Next.js / shadcn / App Router 技术栈。
- 不替换现有 `BaseButton`、`SurfaceCard`、`BaseDrawer`、`PageHeader` 等 UI 基座。
- 不通过修改后端状态协议来修正前端展示问题。

## 指导原则

1. 视觉以 `platform-web` 为主，逻辑只借参考实现的长处。
2. `composable` 负责数据源和流式状态，`view model` 负责展示态整形，组件只负责渲染。
3. 所有“稳定展示”问题优先在前端 view model 解决，不污染 runtime / platform-api 协议。
4. 复杂聊天能力必须拆成可复用的独立模块，不能继续往 `BaseChatTemplate.vue` 里硬塞判断。

## 目标架构

### 1. 页面壳

- `ChatPage.vue`
- `SqlAgentPage.vue`
- 其他未来复用 chat 基座的业务页

职责：

- 解析路由和目标对象
- 选择要不要展示入口引导
- 组合通用 chat 基座

### 2. 数据源层

- `useChatWorkspace`
- `useChatThreadWorkspace`
- `usePlatformChatStream`
- `useChatAttachments`

职责：

- `useChatWorkspace`：页面编排层，组合运行目录、thread 工作台和 stream 内核
- `useChatThreadWorkspace`：线程列表、线程详情、坏线程隔离、线程切换
- `usePlatformChatStream`：流式运行、断点恢复、重试、编辑重发、中断恢复
- 附件上传、粘贴、拖拽
- 运行参数、取消、重试、checkpoint 分支

### 3. 展示态层

后续拆成以下几个稳定模块：

- `buildChatThreadListView`
- `buildChatPlanViewModel`
- `buildChatDisplayMessages`
- `buildChatMessageMetaView`
- `createChatMessageActions`

职责：

- 把后端原始数据转换成前端稳定展示结构
- 隔离“实时状态”和“用户可理解的展示状态”
- 为组件提供可直接渲染的数据

### 4. 组件层

- `BaseChatTemplate.vue`
- `ChatTasksFilesPanel.vue`
- `ChatMessageMeta.vue`
- `ChatArtifactPanel.vue`
- `ChatInterruptPanel.vue`
- 已拆：`ChatThreadDrawer`、`ChatComposer`、`ChatContextDrawer`、`ChatMessageList`
- 后续继续拆：`ChatToolCallCard`

职责：

- 只接收整理好的展示数据
- 不直接承担复杂状态推导

## 参考项目可吸收的优点

1. 线程列表分组、筛选、摘要、状态徽标。
2. 附件上传支持拖拽、粘贴、去重。
3. 工具调用、审批中断、sub-agent 卡片统一归口。
4. Markdown 渲染统一出口。
5. 聊天页面按“页面壳 / hooks / 展示组件”分层。

## 当前确定的实现策略

### ToDo / 计划展示

- 主计划优先从消息历史里的第一次 `write_todos` 工具调用提取。
- 如果消息里拿不到，再退回第一次可用的实时 `todos`。
- 后续实时 `todos` 只负责推进主计划里的状态，不再覆盖主计划内容。
- 不在首版计划中的新任务归入“临时执行项”单独展示。
- 这是一层纯前端 view model，不改后端协议。

### Chat UX v1 交互规则

#### 目标

- 聊天主消息区只负责承载“对话主线”。
- `ToDo / 文件 / 历史 / 上下文概览` 归入右侧会话详情面板。
- 工具调用保留在消息主线里，以“当前回合可点开查看详情”的方式呈现。
- 运行参数独立成弹窗入口，不再塞进检查面板里让人找半天。
- 目标来源合并进“概览”，页面顶部只保留轻提示，不重复堆全文。
- agent 持续输出时，只有用户明确处于“跟随直播态”才自动贴底。
- 用户一旦开始阅读历史或检查侧栏，系统不能再抢焦点、抢滚动位置。

#### 滚动状态机

定义两种明确状态：

1. `跟随直播态`
2. `阅读暂停态`

规则如下：

- 当消息区距离底部小于 `80px` 时，视为处于 `跟随直播态`。
- `跟随直播态` 下：
  - assistant 持续输出时，消息区平滑跟随到底部。
  - 新增工具调用、ToDo 更新、计划推进都只更新当前消息，不切换滚动锚点。
- 用户一旦手动上滑离开底部，立即切换为 `阅读暂停态`。
- `阅读暂停态` 下：
  - 禁止任何新消息、工具调用、ToDo 更新强制滚动。
  - 右下角只展示“有新消息 / Agent 仍在运行 / 回到底部”浮层提示。
  - 只有用户主动点击“回到底部”才恢复 `跟随直播态`。

#### 右侧检查面板

- 右侧面板独立滚动，不与主消息区共享滚动锚点。
- 首版固定四个 Tab：
  - `概览`
  - `ToDo`
  - `Files`
  - `历史`
- 打开右侧面板后，默认视为用户进入检查态，主消息区停止自动跟随。
- 面板内更新只体现在：
  - 当前内容刷新
  - Tab 徽标 / 计数变化
- 如果某一项需要定位到对应消息，只允许提供“定位到消息”按钮，不能自动跳。

#### 运行参数

- 运行参数使用独立弹窗，不和右侧检查面板混在一起。
- 入口按钮固定放在聊天头部操作区，命名直接叫 `运行参数`。
- 弹窗里提供：
  - `模型`
  - `工具开关 / 工具选择`
  - `Debug Mode`
  - `Temperature / Max Tokens`
  - `还原 / 确认`

#### 消息流组织

- 一个 assistant 回合优先收敛成一条主消息。
- 工具调用事件挂在该回合消息下方，以摘要条 + 点击展开详情的方式展示。
- ToDo 变化优先展示为“计划已更新”摘要入口，不直接把用户视口拉到计划区。
- 工具摘要默认折叠，只展示：
  - 工具名
  - 当前状态
- 调用数量 / 子任务数量
- 用户点开后再看参数和结果。
- 结构化事件可以更新，但不再作为新的滚动焦点。

#### 用户体验验收口径

- 用户上滑查看历史时，新消息不会把页面强行拉走。
- 用户点开 `ToDo` 时，工具调用更新不会把主消息区跳转到工具卡片。
- 用户停在底部时，assistant 持续输出会稳定自动跟随。
- 用户离开底部时，系统只做“安静提示”，不做强制打断。
- 主消息区永远只承载“对话正在怎么推进”，右侧面板才承载“计划、工具、上下文这些结构化检查信息”。

### Chat 流式阅读交互标准（2026-04-08 冻结）

这部分是后续 chat 页面必须遵守的正式标准，不再允许各个页面自己发明一套滚动和阅读逻辑。

#### 1. 主消息流只承载主叙事

- assistant 文本回复始终是主消息流的第一优先级。
- 工具调用、子任务、ToDo 变更、执行细节都属于“次级信息”。
- 次级信息只能以两种方式出现：
  - 挂在当前 assistant 回合下方的摘要条 / 折叠详情
  - 进入右侧检查面板查看
- 禁止把工具结果、计划更新、上下文状态直接做成新的滚动锚点。

#### 2. 自动跟随只允许存在两种状态

- `跟随直播态`
  - 用户停留在底部附近。
  - assistant 持续输出时允许自动贴底。
- `阅读暂停态`
  - 用户正在看历史、看工具详情、看右侧面板或运行参数。
  - 新输出只能更新内容和提示，不能抢焦点、不能强制滚动。

#### 3. 阅读暂停态的触发源

- 用户主动上滑离开底部。
- 用户打开右侧会话详情面板。
- 用户打开运行参数弹窗。
- 用户展开某条消息下的工具详情 / 子任务详情。

#### 4. 恢复跟随的唯一方式

- 用户主动滚回底部。
- 用户点击“回到底部 / 继续跟随”提示。
- 用户关闭检查态后重新回到底部。

#### 5. 新消息提示规则

- 如果用户不在跟随直播态：
  - 有新消息时提示“有新消息”
  - 仍在执行中时提示“Agent 仍在运行”
  - 只允许提示，不允许自动跳转
- 右下角提示必须是轻量浮层，不能遮住主要输入区和操作区。

#### 6. 工具详情默认行为

- 默认折叠，只展示工具名、数量、状态、摘要。
- 只有用户主动展开时，才展示参数、结果、图片或结构化输出。
- 展开工具详情默认视为进入阅读暂停态。

#### 7. 滚动实现原则

- 所有自动滚动必须统一经过一个 follow gate。
- 禁止在多个 watcher / 组件里各自直接 `scrollTo`。
- 流式阶段的连续更新必须做节流或合并，避免滚动“抖”和“急”。

#### 8. 交互目标

- 用户想“看直播”时，系统稳稳跟着走。
- 用户想“读细节”时，系统老老实实别抢。
- 用户看完后，能一键回到底部继续跟随。

### 样式处理

- 保持当前 `platform-web` 的主题、色板、圆角、阴影、排版。
- 允许吸收参考项目的布局细节和组件职责拆分，但不照抄其 CSS 变量和全局样式。

### 前端拆包策略

#### 第一阶段：先做路由级懒加载

- 优先把 `src/router/routes.ts` 里的工作台页面改成动态 `import()`。
- 原因很直接：
  1. 收益最大，改动范围最可控。
  2. 不会污染业务模块边界。
  3. 先解决“首包过大”这个最明显的问题，再决定是否需要更细的 chunk 策略。
- 结果：
  - 主入口 chunk 从约 `680KB` 降到约 `291KB`。
  - 已经消除 `>500kB` 的 Vite 大 chunk warning。

#### 第二阶段：只对高价值共享块继续精细拆包

- 不直接上大范围 `manualChunks`，避免把工程切成一堆难维护的小碎块。
- 当前优先处理“资源库模板详情链路”：
  - 模板列表页只保留静态目录元数据。
  - 参考模板源码读取、代码拆解、详情预览改为点开弹窗时再动态加载。
- 这一步的目标不是继续压主入口，而是避免资源页首屏把模板源码能力整包吞进去。

#### 当前构建观察

- 当前较大的共享 chunk 主要包括：
  - `index-*.js` 约 `293KB`
  - `types-*.js` 约 `232KB`
  - `en-*.js` 约 `237KB`
  - `zh-Cn-*.js` 约 `175KB`
  - `useSub2apiTemplateDialog-*.js` 已从约 `98KB` 收敛到约 `31.85KB`
  - `template-detail-loader-*.js` 约 `39.29KB`
  - `Sub2apiTemplateDialog-*.js` 约 `12.99KB`
  - `Sub2apiTemplatePreview-*.js` 约 `26.73KB`
- 其中：
  - `types-*.js` 更接近 chat / threads / 展示层共享逻辑聚合块。
  - `en` / `zh-Cn` 这类大块并不是当前站点 i18n 文案本身过大，而是资源库引入参考模板源码后形成的源码文本 chunk。
  - 资源库模板详情链已经拆成“模板目录入口块 + 详情弹窗块 + 预览舞台块 + 源码读取块”，避免用户一进入资源页就把整条详情链全吞下去。

#### 后续继续优化的顺序

1. 先观察资源库模板详情按需加载改完后的构建结果。
2. 如果 `types-*.js` 仍然明显偏大，再分析它到底聚合了哪些共享模块。
3. 只有在确认存在“稳定且高复用的大型公共依赖”后，才考虑在 `vite.config.ts` 增加有限度的 `manualChunks`。
4. 不做按 `node_modules` 粗暴切碎的愚蠢方案，避免维护成本和缓存命中一起变烂。

## 执行顺序清单

- [x] 明确“视觉沿用 `platform-web`、逻辑吸收参考项目”的迁移原则
- [x] 明确 ToDo 稳定展示应由前端 view model 负责，而不是后端 snapshot
- [x] 新增本方案文档
- [x] 实现 `useChatPlanViewModel` / 纯函数版本，完成 ToDo 主计划与临时执行项分离
- [x] 把 `ChatTasksFilesPanel.vue` 改为消费前端计划展示模型
- [x] 补充计划展示相关单测
- [x] 抽离线程列表 view model
- [x] 抽离消息块 view model
- [x] 抽离工具调用卡片 view model
- [x] 抽离 `ChatThreadDrawer`
- [x] 抽离 `ChatComposer`
- [x] 抽离 `ChatContextDrawer`
- [x] 抽离 `ChatMessageList`
- [x] 抽离消息动作控制层 `createChatMessageActions`
- [x] 完成路由级懒加载，先把主入口大包问题压下去
- [x] 识别资源库模板详情链路的额外包体开销
- [x] 将资源库模板目录与源码详情加载拆开，改为按点击动态加载
- [x] 把拆包策略、现状和后续优化方向写入文档
- [x] 定稿 `Chat UX v1` 交互规则，明确滚动状态机与右侧检查面板边界
- [x] 将 chat 主消息区滚动逻辑改为“跟随直播态 / 阅读暂停态”
- [x] 将右侧检查面板收敛为 `概览 / ToDo / Files / 历史`
- [x] 将工具调用恢复为消息区可点击展开详情
- [x] 将运行参数从检查面板中拆出，改为独立弹窗入口
- [x] 将目标来源合并进概览，页面顶部只保留轻提示
- [x] 增加“有新消息 / Agent 仍在运行 / 回到底部”浮层提示
- [x] 收敛工具调用与计划更新展示，禁止结构化事件抢占主消息区滚动焦点
- [x] 收敛 `BaseChatTemplate.vue`，让它只负责编排，不继续堆业务判断
- [x] 完成 `testcase agent` 基于 `@langchain/vue/useStream` 的真实文本链路联调
- [x] 完成 `testcase agent` 图片附件链路联调

## Chat 流式阅读整改执行清单

- [x] `P0` 将 chat 自动滚动收敛成统一 follow gate，不再散落在多个 watcher 里各自判断
- [x] `P0` 补齐阅读暂停态触发源：主消息区工具详情展开也必须暂停自动跟随
- [x] `P0` 工具调用 / 子任务详情默认折叠，去掉“运行中自动展开”的粗暴行为
- [x] `P1` 新消息浮层提示统一成“有新消息 / Agent 仍在运行 / 回到底部”的标准文案
- [x] `P1` 自动滚动增加节流 / 合并，减少流式输出时的频繁滚动抖动
- [x] `P1` 关闭检查态或回到底部后，自动恢复稳定跟随，不残留错误的未读状态
- [x] `P2` 完成 chat 页面静态校验：`pnpm --dir apps/platform-web typecheck`
- [x] `P2` 完成 chat 页面静态校验：`pnpm --dir apps/platform-web lint`
- [x] `P2` 完成 chat 页面交互单测：`pnpm --dir apps/platform-web exec vitest run src/modules/chat/components/ChatMessageList.spec.ts`
- [x] `P2` 完成 chat 页面构建校验：`pnpm --dir apps/platform-web build`

## 本轮代码落地记录（2026-04-08）

- `BaseChatTemplate.vue`
  - 自动跟随改为 follow gate 控制，暂停原因统一收口为：
    - `manualScroll`
    - `contextDrawer`
    - `runtimeOptions`
    - `messageMeta`
  - 自动滚动改为统一调度，使用合并后的 `scheduleScrollToLatest()`，避免流式阶段频繁直接 `scrollTo`
  - 主消息内容区增加高度变化观察；assistant 文本在同一条消息内持续变长时，也能稳定触发贴底
  - 流式输出期间增加 pinned-to-bottom loop；只要用户仍处于跟随直播态，就持续维持贴底，不再依赖单一事件源碰运气
  - 关闭检查态 / 回到底部后，会清理未读与缓冲状态，并恢复稳定跟随
- `ChatMessageMeta.vue`
  - 工具调用与子任务详情默认折叠
  - 展开 / 收起显式向上抛出事件，供主消息流进入或退出阅读暂停态
  - 摘要说明补充“展开详情会暂停自动跟随”
- `ChatMessageList.vue`
  - 将消息元信息展开事件继续向上传递给 chat 基座，避免子组件自己偷偷管理滚动
- `ChatMessageList.spec.ts`
  - 锁定“运行中也默认折叠工具详情”
  - 锁定“展开 / 收起会把状态继续上抛给 chat 基座”

## 当前阶段验收标准

- “所有任务”不再随着实时 `todos` 整表漂移。
- “当前任务”来自主计划，不再直接展示后续临时改写任务。
- 参考项目的逻辑优点以 Vue 工程化方式落地，现有样式不被破坏。
- 主入口 chunk 不再出现 Vite 大包告警，资源库模板详情能力不再强绑在列表页首屏里。
- Chat 页面在实时输出期间不再抢用户滚动位置，结构化侧信息改为右侧独立检查流。
