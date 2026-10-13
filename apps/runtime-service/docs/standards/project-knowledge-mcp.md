# 项目知识 MCP 接入

公共 loader 位于 `runtime_service/tools/mcp.py`，声明校验位于 `runtime/mcp_config.py`。DearFlow/Showcase 在组合根显式装配；其他图、子图、Plan、schema-only、offload 不获得知识工具。沿官方 langchain-mcp-adapters 0.3.2，不另写客户端或 Agent 循环。

## 三份服务端配置

API `PLATFORM_KNOWLEDGE_MCP_BINDINGS_JSON` 默认 `{}`：

```json
{"__default:11111111-1111-4111-8111-111111111111":"knowledge_project_a"}
```

Runtime `RUNTIME_MCP_CONNECTIONS_JSON` 默认 `{}`：

```json
{
  "knowledge_project_a": {
    "transport": "streamable_http",
    "url": "http://127.0.0.1:8000/mcp",
    "headers": {"Authorization": "Bearer <private-random-token>"},
    "scope": {"tenant_id": "__default", "project_id": "11111111-1111-4111-8111-111111111111"},
    "allowed_tools": ["mcp_query_project_knowledge"]
  }
}
```

知识工程 `KNOWLEDGE_MCP_TOKEN_SCOPES_JSON` 将同一个私有token固定到tenant/project/已发布namespace。三个scope必须一致；配置后重启API、Runtime API/Worker与知识服务，并调用现有 graphs/tools refresh。目录是展示信息，授权沿当前项目tool-restrictions与执行委托复核。

新Thread在已有create用例内按可信tenant/project/thread签发内部binding；fork重签，旧Thread不迁移。浏览器不能选择resource，所有入口递归拒绝 `runtime_resource_bindings` / `__graphharbor_thread_metadata`，公开Thread/state/history/SSE剥离它们。知识URL/token/namespace不进Context，沿现有Thread ACL共享已检索片段。

## 工具与来源

查询工具 `mcp_query_project_knowledge(query, top_k=8)`：query1–2000字符，top_k1–8，固定hybrid。知识服务一次aquery_data，不生成答案；LightRAG关键词LLM和Embedding仍有费用，未自动计入平台模型Usage。

HTTP返回单JSON文本和同值structuredContent，status为ok/no_hit，sources为source_id/document_id/chunk_id/title/kind/preview/truncated。最多8条、800字符/片段、12KiB；无宿主路径、raw_data、Key、下载URL、伪页码。`knowledge.py` 官方interceptor在Adapter转换前约束文本及artifact。F04更低预算由 `ResultFilesystemMiddleware` 缩减完整字段，同步artifact；极小预算无法容纳合法来源时安全失败，保留合法JSON。

`RUNTIME_KNOWLEDGE_SOURCES_VERSION=1|2` 固定请求版本，默认1。模型工具schema隐藏版本参数，interceptor按服务配置注入，provider静默返回其他版本安全拒绝。v2顶层增加`sources_version:2`，来源增加`locator:{unit,start,end,block_type}`：unit为page/slide/unknown，已知范围是1-based正整数且start≤end，unknown两端为null；block_type为text/image/table/equation/null。PDF按可信页码，PPTX有可靠provenance才按slide，其他格式未知时不猜页码。正文/artifact/history/F04投影同值；回退请求v1仍保留旧v2历史可读。前端兼容后才切2。

错误保留MCP isError与既有ToolMessage error，公开固定knowledge_retrieval_failed或既有传输分类；CancelledError传播。Stop阻止迟到结果进入已结束Run，远端已提交只读请求可能继续。

## 普通成员明确共享上传

online协议兼容并通过真实联合验收后可加 `mcp_submit_project_knowledge_document(file_ref)` 和 `mcp_get_project_knowledge_ingest_job(job_id)`。Runtime `RUNTIME_KNOWLEDGE_UPLOAD_ENABLED=0` 默认关闭submit，关闭不禁用query/job。allowed_tools精确列出三工具；写工具只有submit例外，其四annotations固定readOnly=false/destructive=false/idempotent=true/openWorld=false，陌生mutation拒绝。工具目录与组合根defaults使用同一门禁。

新增API connections、Runtime/RAG同知识专用HMAC配置与回调要求见[成员上传部署手册](../../../../docs/projects/20261012-project-member-knowledge-upload/deployment-runbook.md)。只在DearFlow/Showcase根装配，Plan/schema-only/offload/子图/unbound/deny不提权。review/workspace_write走既有HITL，full_access沿原策略；submit不加入WORKSPACE_WRITE_TOOLS。

普通附件不自动共享。仅用户明确要求，Runtime校验当前Thread原六字段FileRef、HTTP私有回执及原bytes/hash/size/MIME；回执在Agent工作区之外保存，fork复制，旧文档无回执时使用内容地址文件名而非模型别名。工具单一参数file_ref也支持原五字段ImageRef，PNG/JPEG在私有图片HTTP收据与原bytes通过后才在interceptor转换为RAG六字段KnowledgeFileRef；WebP/生成图/outputs/伪六字段图片/跨Thread/无收据拒绝。图片原名经上传file_name query可信记录，同Thread相同引用采用首次成功原名；旧图片无收据需重传。图片5MiB、文档20MiB，不新增原件副本。调用精确upload授权→受管HTTP PUT原件→再授权→官方MCPToolCallRequest.override注入私有upload/grant headers。模型不接触host/Bearer/授权内容。

root ToolNode只接受空namespace或与可信execution_info.task_id一致的tools:<task_id>，并要求与execution_info.checkpoint_ns相同；子图/read委托/Plan/offload/活动计划/deny继续拒绝。前端模型可见text必须携带完整六字段FileRef或五字段ImageRef JSON，extras单独携带不会进入模型正文。

request_id由可信tenant/project/thread/run/tool_call确定性派生；提交最多等待30秒，不等解析。失ACK重新取grant并只读同key回查，不自动submit或换key；结果未知返回knowledge_submission_unconfirmed。聊天Stop不取消RAG已受理任务。任务工具读前/读后经平台复核当前read权限、active项目、Thread ACL/Run与deny。

提交/任务回执严格安全投影≤4KiB。status为queued/parsing/indexing/publishing/ready/failed，searchable单独表示当前版本可查性；提交有reused，任务读无reused。迁移资料允许job_id=null/status=ready/reused=true，回退时searchable可以false，不轮询null。官方Adapter转换前约束文本与structuredContent，并保留isError和CancelledError。确切签名、ID与DTO见[provider契约](../../../../docs/projects/20261012-project-member-knowledge-upload/provider-contract.md)。

## 维护/回退

资料留在外部 `rag-anything-use`。既有legacy路径仍为管理员离线CLI导入、检查ready、publish；已发布namespace冻结，服务持锁，更新用新namespace完整重建，切换凭据scope后重启。online扩展由外部RAG负责原件去重、异步worker与generation：G01已选择完整冻结快照恢复到独立候选workspace、仅增量处理新文档，成功后CAS切active，新旧资料累计可查，旧版本不可变。平台不维护第二套队列/成果缓存/索引。模型/Embedding/维度变更仍需新处理签名和完整重建边界。

online上传默认关闭；新文档/图片与v2真实联合验收见[平台接线专项](../../../../docs/projects/20261013-knowledge-documents-platform/verification.md)。只关闭Runtime/API新增upload开关时保留旧query、job工具和状态GET，并让已受理任务start/activate在原签名、Run与当前IAM校验下继续。RAG管理员项目uploads=off属于解析暂停/回退操作，queued保留，不等同平台新提交关闭；冻结版本回退前应停新提交、等待在途构建结束，再按RAG运维契约操作。全部知识停用才使用下述撤token流程。

停用先deny项目查询工具并处理在途Run，再撤token/移除映射/停MCP；仅删映射无法撤旧binding。保留Thread/checkpoint/语料，历史授权不变更为公开。运行环境与验证见[专项](../../../../docs/projects/20261011-project-knowledge-mcp/README.md)。本机Intel Mac的重型Docling解析受Torch wheel阻塞，不能以文本验收代替PDF/Office能力声明。
