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

唯一装配工具 `mcp_query_project_knowledge(query, top_k=8)`：query1–2000字符，top_k1–8，固定hybrid。知识服务一次aquery_data，不生成答案；LightRAG关键词LLM和Embedding仍有费用，未自动计入平台模型Usage。

HTTP返回单JSON文本和同值structuredContent，status为ok/no_hit，sources为source_id/document_id/chunk_id/title/kind/preview/truncated。最多8条、800字符/片段、12KiB；无宿主路径、raw_data、Key、下载URL、伪页码。`knowledge.py` 官方interceptor在Adapter转换前约束文本及artifact。F04更低预算由 `ResultFilesystemMiddleware` 缩减完整字段，同步artifact；极小预算无法容纳合法来源时安全失败，保留合法JSON。

错误保留MCP isError与既有ToolMessage error，公开固定knowledge_retrieval_failed或既有传输分类；CancelledError传播。Stop阻止迟到结果进入已结束Run，远端已提交只读请求可能继续。

## 维护/回退

资料留在外部 `rag-anything-use`，管理员离线CLI导入、检查ready、publish。已发布namespace冻结，服务持锁；更新用新namespace完整重建，切换凭据scope后重启。模型/Embedding/维度变更必须新namespace。

停用先deny项目查询工具并处理在途Run，再撤token/移除映射/停MCP；仅删映射无法撤旧binding。保留Thread/checkpoint/语料，历史授权不变更为公开。运行环境与验证见[专项](../../../../docs/projects/20261011-project-knowledge-mcp/README.md)。本机Intel Mac的重型Docling解析受Torch wheel阻塞，不能以文本验收代替PDF/Office能力声明。
