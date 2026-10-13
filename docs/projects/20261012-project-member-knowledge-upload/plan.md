# 平台侧实施方案

2026-10-13更新。用户方向评审与实施授权均已具备；非前端实施与V02真实联合验收已完成，Final及前端接续以[承接专项](../20261013-knowledge-documents-platform/verification.md)为准。保留`5be564a`协议修复历史，不再将实际Agent/生命周期列为待验。

## 范围

admin/editor/executor 可明确要求把当前 Thread 附件加入项目知识库。附件仍走原上传接口；普通附件不自动共享。Agent 经受管 MCP 提交，原件和 job 持久受理后即返回；解析由 RAG worker 执行，聊天 Stop 不取消已受理任务。

API 提供项目 capabilities/documents/jobs 和当前权限；Runtime 验证可信附件、传输原件、注入私有 grant；RAG 保存任务与知识事实。只接两主图 DearFlow/Showcase，保留既有 Plan、HITL、deny 和子图边界。默认关闭新增写能力，legacy 查询保持。

## API

- 新权限 `project.knowledge.read` / `project.knowledge.upload`，三项目角色均允许，不扩大 `project.runtime.write`。
- `GET /api/projects/{project_id}/knowledge/capabilities`。
- `GET /api/projects/{project_id}/knowledge/documents?limit=20&offset=0`。
- `GET /api/projects/{project_id}/knowledge/jobs?limit=20&offset=0`。
- `GET /api/projects/{project_id}/knowledge/jobs/{job_id}`。
- `POST /api/runtime/internal/knowledge/authorize`，专用 HMAC 请求，操作 read/upload/start/activate。read 检查当前 Thread read ACL、成员与 active 项目，任务读取前后复核；upload 检查当前 Thread comment ACL 与成员权限；start/activate 检查原主体当前成员、凭据、项目生命周期及原 Run 来源，不因聊天 Stop/删除 Thread 取消已受理任务。

同步数据库工作在线程池内打开/关闭自己的 Session，不跨网络 await 持有事务。受管服务 URL/Bearer 只来自配置，浏览器/模型不可指定。

## Runtime 与 RAG 契约

- `mcp_submit_project_knowledge_document(file_ref)`：六字段文档FileRef或五字段图片ImageRef；图片经私有HTTP收据和原bytes校验后在interceptor转换，模型不补原名。精确校验 schema/annotations，指定写工具例外，不开放其他 mutation。
- `mcp_get_project_knowledge_ingest_job(job_id)`：只读状态。
- 内部上传 `PUT /internal/knowledge/uploads/{request_id}`；状态读取 `/internal/knowledge/capabilities`、`/documents`、`/jobs`、`/jobs/{job_id}`。
- 私有 `X-Knowledge-Upload-ID`、`X-Knowledge-Operation-Grant` 由官方 MCP interceptor 注入，不进模型、artifact 或历史。
- request_id 从可信 tenant/project/thread/run/tool_call 确定性派生；失去 ACK 重新取得授权，保留原 key，只读 `GET /internal/knowledge/uploads/{request_id}` 回查，不换 key 自动重提。
- 回执 `version,job_id,document_id,file_name,status,searchable,reused,error_code,created_at,updated_at`。迁移复用允许 `job_id=null,status=ready,reused=true`，searchable 仍反映当前 active 版本，回退可为 false；任务 GET 必须有 job_id，reused 仅提交回执。
- 工具输出最多 4 KiB，严格安全 DTO；未知上游错误不透传。列表使用既有 OffsetPage。

具体字段和签名已固化为可执行测试、[provider 契约](provider-contract.md)与[脱敏 fixture](fixtures/README.md)。专用 key 不复用 access/delegation/callback secret；grant 最长 30 秒，上传完成后提交前重新授权。撤权到授权租约到期存在最多 30 秒边界，不声称发布与 IAM 强事务。原件上传/每次直接授权/MCP 调用各有 30 秒上界，API provider GET 总截止 10 秒；不宣称整次提交仅有一个 30 秒总截止。

## 验证与依赖

2026-10-12历史：`febe70a`的403/405失败保留；`5be564a`实际start/activate200、GET200、两文档ready与可信ToolRuntime/官方Adapter联调通过，RAG78/API17/Runtime91回归通过。该轮一次后台失败原因未采集，不能根据成功重跑抹去历史。

2026-10-13：RAG main `c30e2149`与当前平台真实Worker/两Agent通过六格式上传审批、另一成员新旧检索、处理中/ready同hash零新增用量、两项目排队与旧读、Stop、Fork及API/Worker/RAG重启、冻结版本回退/恢复、撤权/Plan门禁。20MiB仅验证字节边界及异步回执，业务复杂度/生产负载不外推。平台不另建缓存/索引/队列。前端多格式/图片/v2与无mock浏览器由同事接续，正式新增上传仍默认关闭；最终回归/清理见[承接验证](../20261013-knowledge-documents-platform/verification.md)。
