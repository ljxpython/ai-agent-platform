# 07. 模块迁移映射与交付顺序

## 目标

这份文档解决两个实际问题：

1. `platform-web-v2` 里每个页面，到新 Vue app 里应该落到哪里
2. 迁移顺序怎么排，才能最快看到稳定结果，且不把高风险页面提得过早

## 一、现有页面到新模块的映射

| 当前页面 | 新模块 | 页面类型 | 目标母版 | 优先级 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `/auth/login` | `modules/auth/login` | auth | `AuthLayout` | P0 | 首个必须跑通的页面 |
| `/workspace` | `router/workspace-redirect` | redirect | `WorkspaceLayout` | P0 | 负责登录后默认落点和项目上下文校验 |
| `/workspace/overview` | `modules/overview` | dashboard | `WorkspaceLayout` + `DashboardPageLayout` | P1 | 作为整体视觉与上下文的演示首页 |
| `/workspace/projects` | `modules/projects/list` | list | `TablePageLayout` | P1 | 列表页母版的标准样板 |
| `/workspace/projects/new` | `modules/projects/create` | form | `DetailPageLayout` | P1 | 用来验证表单页规范 |
| `/workspace/projects/[projectId]` | `modules/projects/detail` | detail | `DetailPageLayout` | P1 | 建议作为项目详情主入口 |
| `/workspace/projects/[projectId]/members` | `modules/projects/members` | list/detail | `DetailPageLayout` | P2 | 建议作为项目详情下的 tab 或二级页 |
| `/workspace/users` | `modules/users/list` | list | `TablePageLayout` | P1 | 可直接复用表格、筛选、分页体系 |
| `/workspace/users/new` | `modules/users/create` | form | `DetailPageLayout` | P2 | 与 projects/create 同一套表单基座 |
| `/workspace/users/[userId]` | `modules/users/detail` | detail | `DetailPageLayout` | P2 | 详情页母版样板之一 |
| `/workspace/assistants` | `modules/assistants/list` | list | `TablePageLayout` | P1 | Agent 相关页面，汇报价值高 |
| `/workspace/assistants/new` | `modules/assistants/create` | form | `DetailPageLayout` | P2 | 与 assistant detail 配套 |
| `/workspace/assistants/[assistantId]` | `modules/assistants/detail` | detail | `DetailPageLayout` | P2 | 后续与 chat/graph 联动 |
| `/workspace/graphs` | `modules/graphs` | workspace/tool | `WorkspaceToolLayout` | P3 | 核心业务，但复杂度较高 |
| `/workspace/runtime` | `modules/runtime/overview` | workspace/list | `WorkspaceLayout` | P3 | 建议保留概览入口 |
| `/workspace/runtime/models` | `modules/runtime/models` | list | `TablePageLayout` | P3 | 与 runtime tools 同域组织 |
| `/workspace/runtime/tools` | `modules/runtime/tools` | list | `TablePageLayout` | P3 | 中等复杂度 |
| `/workspace/sql-agent` | `modules/sql-agent` | workspace/tool | `WorkspaceToolLayout` | P3 | 汇报价值高，交互链路要稳 |
| `/workspace/threads` | `modules/threads` | master-detail | `WorkspaceToolLayout` | P4 | 必须改成点选后再加载详情，不再一次性全展开 |
| `/workspace/chat` | `modules/chat` | workspace/tool | `WorkspaceToolLayout` | P4 | 必须带首次引导和最近上下文恢复 |
| `/workspace/testcase` | `modules/testcase/index` | hub | `WorkspaceLayout` | P4 | 保持一级标题身份，下面挂三个二级页面 |
| `/workspace/testcase/generate` | `modules/testcase/generate` | workspace/form | `WorkspaceToolLayout` | P4 | 用例生成入口 |
| `/workspace/testcase/cases` | `modules/testcase/cases` | list/detail | `TablePageLayout` | P4 | 用例管理页 |
| `/workspace/testcase/documents` | `modules/testcase/documents` | list/preview | `WorkspaceToolLayout` | P4 | 文档预览、下载、多格式适配的核心页面 |
| `/workspace/me` | `modules/account/me` | settings | `DetailPageLayout` | P2 | 低风险，可早做 |
| `/workspace/security` | `modules/account/security` | settings | `DetailPageLayout` | P2 | 与 me 同域 |
| `/workspace/audit` | `modules/audit` | list | `TablePageLayout` | P2 | 典型审计列表页 |

## 二、模块组织建议

建议在 `modules/` 下按业务域切，而不是按页面类型切。

建议结构如下：

```text
modules/
  auth/
  overview/
  projects/
  users/
  assistants/
  graphs/
  runtime/
  sql-agent/
  threads/
  chat/
  testcase/
  account/
  audit/
```

各业务域内部再按需要拆：

- `pages/`
- `components/`
- `composables/`
- `types/`
- `services/adapter.ts`

这样做的好处是：

- 页面和业务逻辑靠得近
- 不会因为页面一多就到处跨目录跳
- 后期某个域重构时边界更清楚

## 三、交付顺序建议

这次迁移不建议按“页面名顺序”做，而应该按“依赖关系 + 汇报价值 + 风险”做。

### 阶段 A：先把地基搭出来

先做这些：

- 登录
- 全局路由与守卫
- 主题与 token
- WorkspaceLayout
- 顶部上下文条
- 项目切换
- 基础组件层

原因：

- 这部分决定后面所有页面是否能稳定复用

### 阶段 B：先做低风险但高可见页面

优先做：

- `overview`
- `projects`
- `users`
- `assistants`
- `me`
- `security`
- `audit`

原因：

- 这些页面能最快体现“新前端已经成熟起来了”
- 但交互复杂度相对可控
- 同时能把列表页、详情页、表单页母版都验证掉

### 阶段 C：再做中复杂度工作台页面

接着做：

- `runtime`
- `runtime/models`
- `runtime/tools`
- `graphs`
- `sql-agent`

原因：

- 这些页面对工作台布局、筛选区、表格区、工具区都有要求
- 但还没到最难的懒加载与多态文件预览那一步

### 阶段 D：最后做高风险交互域

最后做：

- `threads`
- `chat`
- `testcase/generate`
- `testcase/cases`
- `testcase/documents`

原因：

- 这些模块牵涉懒加载、会话状态、首次引导、文件预览、下载、多格式适配
- 它们最容易把架构和状态边界搞乱
- 应该放在前面基座稳定后处理

## 四、各阶段的产出口径

### 阶段 A 产出

必须能展示：

- 登录
- 左侧导航
- 顶部上下文条
- 主内容区
- 主题切换
- 项目切换

### 阶段 B 产出

必须能展示：

- 统一列表页母版
- 统一详情页母版
- 统一表单页母版
- Agent 相关基础页面可进入

### 阶段 C 产出

必须能展示：

- 工作台型页面不是临时拼接
- 工具类页面仍然保持统一视觉
- 运行时、图谱、SQL Agent 页面能稳定进入并操作

### 阶段 D 产出

必须能展示：

- thread 按需加载
- chat 首次引导和最近状态恢复
- testcase 一级标题与三个二级页面结构稳定
- 文档多格式预览与下载入口统一

## 五、风险排序

### 高风险

- `threads`
- `chat`
- `testcase/documents`

原因：

- 大对象渲染
- 状态恢复
- 按需加载
- 文件多格式处理

### 中风险

- `graphs`
- `runtime`
- `sql-agent`

原因：

- 工作台类布局复杂
- 信息密度高
- 页面局部状态多

### 低风险

- `overview`
- `projects`
- `users`
- `assistants`
- `me`
- `security`
- `audit`

原因：

- 列表、详情、表单、设置页模式相对稳定
- 更适合先打样板

## 六、未来开发一个新功能时的落地顺序

以后新增功能，必须照下面顺序走：

1. 先判断页面类型
2. 再选择对应母版
3. 再决定复用哪些基础组件
4. 再实现 service 和 composable
5. 最后才写页面业务内容

不要再出现这种做法：

- 先开个页面文件
- 写一堆临时 `div`
- 最后再想怎么补样式和交互

这种做法会直接把新基座做散。

## 七、当前最重要的收敛结论

如果只用一句话总结迁移顺序，那就是：

- 先做基座
- 再做低风险样板页面
- 再做中复杂工作台
- 最后做 chat / threads / testcase 这种高风险域

这个顺序既符合工程节奏，也符合你后面要给老板展示成果的节奏。
