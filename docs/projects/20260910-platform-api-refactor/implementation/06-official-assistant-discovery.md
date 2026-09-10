# 使用官方 Assistant 接口发现部署 Graph

2026-09-10：用户确认撤销自定义发现接口；GraphHarbor 与 LangGraph Server 完整等价性的专项验证后置。本轮只调整默认 Assistant 发现及其关联行为，不扩大到完整 Server 重写。

## 当前实现

- 删除 GraphHarbor GET /graphs 的处理函数、路由与 OpenAPI 条目。GraphHarbor 不接收平台项目配置、模型管理或其他业务逻辑。
- GraphHarbor 启动加载部署后注册默认 Assistant 与版本 1；ID 使用官方 `uuid5(NAMESPACE_URL, graph_id)`，metadata 为 `created_by: system`。插入使用数据库唯一约束及 ON CONFLICT DO NOTHING，已有配置不被启动流程覆盖。
- Assistant search/count 的作用域允许读取部署端系统默认记录，并保留项目自定义记录隔离。已不在 registry 中的系统默认记录不出现在搜索和计数结果里，不删除历史 Run 所引用的记录。
- graph_id 执行解析到默认 Assistant 的稳定 UUID，删除原来的按项目懒创建逻辑。默认 UUID 与 graph_id 均可定位 schema；自定义 Assistant UUID 继续检查 tenant/project。
- Platform 的目录刷新、网关 Graph 搜索/计数共用 `LangGraphRuntimeClient.list_deployed_graphs()`，只调用官方 POST /assistants/search，按 `metadata.created_by=system` 查询并分页去重。平台不创建上游 Assistant，普通列表仍只读快照。
- 前轮真实 schema 与公开字段筛选保留；不存在本机源码回退。05 中 /graphs 方案已被本记录替代。

## 验证

- Platform 目录、schema、Graph 搜索与网关关联测试：38 项通过，5.489 秒。包括 1001 条结果分页、非法响应保留快照、合法空结果、无权限不发上游请求。
- GraphHarbor 默认注册/发现、schema 与状态投影：5 项通过，14.25 秒。包括标准 UUID、系统 metadata、冲突安全 SQL、默认记录可读、项目隔离、匿名拒绝、graph_id 执行定位与 schema 不执行节点。
- GraphHarbor 注册测试使用数据库会话替身检查实际生成的 PostgreSQL 语句，未执行真实 PostgreSQL 重复启动/并发验证，不据此宣称数据库链路验收完成。
- 本轮不重复此前全量，不发布包，不替换运行中的 Runtime；GraphHarbor 现有未定义 policy 的 Run 创建问题仍待后续执行链修复。完整接口等价性、真实 Runtime 联调与容器验收均未宣称完成。

参考：官方 LangGraph Server 0.13.0 的 graph 注册实现与 [Assistant 部署语义](https://docs.langchain.com/langsmith/assistants#how-assistants-work-with-deployments)。GraphHarbor 运行时不导入 langgraph_api 私有代码。
