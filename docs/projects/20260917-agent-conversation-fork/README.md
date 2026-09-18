# Agent 对话新建分支

## 项目概述
- **时间：** 2026-09-17 至待定
- **目标：** 用户可从一个已完成的 Agent 回复创建独立会话，并从该回复后的 LangGraph 状态继续对话。
- **负责人：** @lijiaxin
- **状态：** 已完成：后端 API、Runtime 隔离、前端交互（分支按钮、标题递增、状态流转）及全套单元/组件测试均已通过。

## 阅读顺序
1. [契约与状态边界](01-contract-and-state-boundary.md)：定义“新建分支”和当前时间旅行的差别。
2. [Platform API 分叉编排](02-platform-api-fork.md)：本阶段实施的受控 API、状态转存和审计。
3. [Runtime Service 隔离](03-runtime-service-isolation.md)：新 thread 的鉴权、工作区和队列边界。
4. [Platform Web 对接](04-platform-web-handoff.md)：回复下方按钮和新对话框的接入契约。
5. [联调测试与问题复盘](05-issues-and-learnings.md)：全景复盘工作区刷新、分支污染、调用上限、产物白名单与图表渲染排查。

## 改动范围
- **影响服务：** `platform-web`、`platform-api`、`runtime-service`
- **改动级别：** 治理改动（跨服务会话状态复制、授权与审计边界）
- **预计工作量：** 3 人天

## 关键决策
1. 分叉必须新建 LangGraph thread；现有 thread 的 checkpoint 重跑只用于时间旅行，不能冒充新会话。
2. Platform API 读取已授权来源 checkpoint，以 `threads.create` + `threads.update_state` 建立目标状态；不直连或复制 checkpointer 数据库。
3. 新 thread 继承可序列化 LangGraph state 与最小来源元数据；工作区文件由 Platform API 签发 `workspace-fork` delegation token，在分叉时由 Runtime Service 进行物理目录安全深拷贝，既继承原工作区文件与产物，又保证新旧分支后续修改物理隔离。
4. Runtime 不新增会话树存储；其既有的 thread scope 和 workspace 以新 thread_id 自然隔离。
