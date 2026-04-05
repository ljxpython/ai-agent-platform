# 07. 模块迁移映射与交付顺序

## 目标

这份文档解决两个实际问题：

1. `apps/platform-web` 里每个页面，到新 Vue app 里应该落到哪里
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

这轮迁移已经过了“先搭地基”的阶段，当前顺序要按“剩余差距 + 汇报价值 + 风险收口”来排。

### 阶段 A：锁定基线并补齐对照矩阵

先做这些：

- 盘点 `apps/platform-web` 现有页面和交互链路
- 标出 `apps/platform-web-vue` 已完成项、缺失项、半完成项
- 为剩余页面补齐接口依赖、状态依赖和验收口径

原因：

- 不先把真相源盘清楚，后面很容易出现“做了很多，但不是老板要看的那块”

### 阶段 B：优先补齐高价值主线页面

按下面顺序推进：

- `testcase/generate`
- `assistants/detail`
- `assistants/new`
- `projects/detail`
- `users/detail`

原因：

- 这批页面要么汇报价值最高，要么正好卡在当前功能闭环上
- 它们补齐后，`apps/platform-web-vue` 才算真正接住 `apps/platform-web` 的核心体验

### 阶段 C：补系统级一致性和展示能力

接着做：

- announcement 真实后端与管理页闭环
- tooltip / 帮助提示体系扩展
- 首次引导和入口提示体系扩展
- dark mode 全链路一致性
- 大屏、小屏下的布局占满和溢出治理

原因：

- 这部分不一定决定“能不能进页面”，但直接决定老板看到时觉得像不像成熟产品

### 阶段 D：最终验收与汇报硬化

最后做：

- 演示账号和演示数据固化
- 关键路径烟测
- 回归验收
- 最终汇报口径和展示脚本

原因：

- 到这一步不是继续加页面，而是把已有成果变成稳定可演示成果

## 四、各阶段的产出口径

### 阶段 A 产出

必须能展示：

- `apps/platform-web -> apps/platform-web-vue` 页面/功能对照矩阵
- 剩余页面的接口依赖、状态依赖、风险点、验收口径
- 已完成项、缺失项、半完成项的明确标记

### 阶段 B 产出

必须能展示：

- `sql-agent` 已接入通用 chat 基座，可稳定进入并完成核心对话操作
- `chat` 已具备首次引导、目标选择、最近状态恢复与真实线程复用
- `chat` 会话列表默认折叠，改为左侧抽屉进入，避免主画布被 thread 列表长期挤占
- `chat` 运行上下文与参数为右侧抽屉草稿态编辑，必须有 `确定 / 还原`
- `chat` 最近历史只作为调试折叠区保留，不再常驻页面
- `testcase/generate`、`assistants/detail/new`、`projects/detail`、`users/detail` 达到可演示状态

### 阶段 C 产出

必须能展示：

- 公告、提示、引导、主题一致性已经成体系
- 页面在常见分辨率下不会出现明显溢出或留白失衡
- 正式业务页与 dev 资源页职责分离清楚

### 阶段 D 产出

必须能展示：

- 演示账号可直接走完关键链路
- 汇报时能按固定路径展示核心功能
- 验收问题和剩余事项有清晰归档

## 五、风险排序

### 高风险

- `sql-agent`
- `chat`
- `testcase/generate`

原因：

- Agent 链路复杂
- 状态恢复
- 入口引导与上下文选择容易出错
- 汇报价值高，不能只做到“能打开”

当前状态补充：

- `sql-agent` 与 `chat` 已完成第一轮“可用对话基座”验收
- 两者共同缺口已经收敛为执行态工作台：运行中取消、Debug / Continue、`todos / files`、interrupt / HITL、artifact
- `testcase/generate` 仍然是主线高风险页，但在它之前必须先把 chat 基座的执行态能力补齐，否则后续 testcase 还会继续踩同一类坑

### 中风险

- `assistants/detail`
- `assistants/new`
- `projects/detail`
- `users/detail`
- `testcase/documents`

原因：

- 详情页通常会牵涉二级结构、关联数据和操作弹窗
- 文档类页面还要继续兼容多格式预览/下载

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

如果只用一句话总结当前迁移顺序，那就是：

- 先锁定 `apps/platform-web` 的真相源
- 再补 `sql-agent / chat / testcase generate / detail 页`
- 最后做系统级一致性和汇报硬化

这个顺序既符合工程节奏，也符合你后面要给老板展示成果的节奏。
