# Platform API 使用手册

2026-09-10 更新。安装、启动及模块清单见[服务 README](../../README.md)，代码职责见[架构说明](architecture.md)，新增功能遵循[开发规范](development-playbook.md)。

## 平台负责什么

| 需求 | 模块 |
| --- | --- |
| 登录、刷新会话、修改密码、当前资料 | identity |
| 平台/项目权限 | iam |
| 用户、项目、成员与服务身份治理 | users / projects / service_accounts |
| Agent 配置、模型连接、远端能力和项目策略 | agents / runtime_catalog / runtime_policies |
| Thread/Run/审批/状态/事件受控访问 | runtime_gateway |
| 公告、审计与系统设置 | announcements / audit / platform_config |

Operations、平台 Worker/队列、知识库与测试用例产品已退役。目录刷新直接返回结果；图执行、取消与恢复由 Agent Server 负责。

## 身份与项目

- 一个部署实例使用服务端租户上下文，前端不选择或伪造 tenant。
- 登录和当前资料不携带完整项目角色；切换项目查询 GET /api/projects/{project_id}/access。
- 平台角色与项目成员角色独立，项目管理员不能管理全局用户；平台管理员也不能绕过项目内容授权。
- 项目支持 archive/restore，管理员接管使用明确的项目治理入口。
- 服务账号使用 API key；项目授权与 token 生命周期分开管理，撤销后不得继续使用。

## Agent 与 Runtime

浏览器经 /api/langgraph 访问 Runtime，携带当前平台认证和 x-project-id。
Agent CRUD 使用平台记录 UUID；执行 assistant_id 使用 graph_id。换图新建 Agent，不对上游 Assistant 做同步。
模型选项使用配置记录 UUID，同名模型可有不同地址和密钥；只展示 credential_configured，不读取或保存 API Key。

发送新动作生成 Idempotency-Key，网络重试复用原 key 和 payload；409 时核查执行状态，不自动换 key 重发。
审批从 Thread state 读取当前 interrupt ID，使用标准 command.resume 映射或 Protocol input.respond；不夹带 input/config/context。
断开 SSE 只关闭订阅，取消使用明确的 Run cancel。刷新后先恢复状态与订阅，不重放输入或自动批准。

## 审计与验证

审计记录身份、项目、动作、目标、请求 ID、结果和耗时；公开结果与错误均过滤内部凭据。
新库使用 Alembic 空库基线，不执行旧数据迁移。测试和真实 Runtime 验收使用隔离环境。

[最新工程进度](../../../../docs/projects/20260910-platform-api-refactor/README.md) · [前端影响与调整](../../../../docs/projects/20260910-platform-api-refactor/05-frontend-handoff.md)。
前端适配与浏览器验收后置；历史文档中的前端完成记录不能替代新契约验收。
