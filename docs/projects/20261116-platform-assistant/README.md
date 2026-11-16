# 平台内置助手

用户在平台页面打开同一个助手，可咨询用法、聊天、讨论创意，也可把错误信息交给它。助手按当前权限读取数据库、运行诊断、日志和研发源码，给出证据、建议与未知项；读操作不反复确认，写工具必须逐次选择执行或不执行。

**全栈各环节已实现并通过自动化验证，用户已确认验收通过。项目状态为已完成（done）。** 唯一进度来源为 [tasks.md](tasks.md)：11项任务全部完成（11/11 done）；后端/Agent、只读SQL、结构化日志与研发源码读取、强制写审批、前端独立模块（`modules/platform-assistant`）及旧日志页面防御性加固均已完成并验证全绿；本地服务已停止，专属测试数据库已删除，工作区代码交付合并主干。

本次采用一个 `create_agent`，不使用DeepAgents，不创建助手执行沙箱或shell。复用GraphHarbor持久历史、受管模型、预算、隐私、取消、流式协议及原生HITL审批。SQL复用LangChain SQLDatabase工具语义，Agent自行看结构并生成查询，Platform API负责独立只读连接与当前授权。当前数据库适配为PostgreSQL，可接多个获准数据源；其他引擎未实现。

所有登录用户可使用；无项目时幂等创建个人助手项目，不自动获得业务项目权限。使用指导优先内置/发布文档，源码只向明确获准研发开放。正式业务写工具为空，审批能力通过隔离测试工具验证，不虚构已交付业务修复动作。

真实链路已覆盖文档问答、自生成SQL关联聚合、同Thread续聊、重启恢复、新会话隔离、创意交流、结构化日志/源码、公开搜索、SSE和取消。另验证只读账号、权限撤销、旧历史/列表、查询与引用审计、跨进程审批及旧ID重放。具体测试结果、失败修复和已知基线测试问题见 [验证记录](verification.md)。

前端独立模块已落地于 `apps/platform-web/src/modules/platform-assistant/`，采用 Clean Architecture 独立解耦架构，包含全局抽屉、错误胶囊、独立审批卡、证据二级抽屉，详细协议与设计规范见 [前端开发交接](frontend-handoff.md)。

| 文档 | 用途 |
|---|---|
| [plan.md](plan.md) | 业务过程、架构、批准范围及设计取舍 |
| [tasks.md](tasks.md) | 唯一任务状态、验证结果、剩余责任方 |
| [frontend-handoff.md](frontend-handoff.md) | 前端可直接接线的协议、示例及浏览器验收要求 |
| [backend-operations.md](backend-operations.md) | 代码结构、配置、只读数据源、资料发布、复验和关闭恢复 |
| [verification.md](verification.md) | 原验收矩阵、阶段证据、后端技术结论与人工/全栈验收边界 |
| [实施与交付证据](implementation/02-backend-delivery.md) | 测试命令、真实Run、故障与回退证据 |

Git交付已获用户明确授权：`feat/platform-assistant` 分支提交推送远端，合并入主干 `main` 并推送；专属测试环境已销毁，专属数据库已删除，Worktree 资源回收。生产环境部署未授权。
