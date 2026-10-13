# Runtime 可信附件与受管 MCP 上传

2026-10-12；对应 R01/R02/O01。沿现有官方 `langchain-mcp-adapters==0.3.2`，未升级依赖或新增 Agent 循环。

## 改动与理由

旧 loader 只允许 readOnly MCP 工具；普通附件上传后没有可信原始文件名证明。新增仅一个精确写工具例外，原件走受管 HTTP，Agent 工具参数仍只有 FileRef。

| 文件 | 具体入口 | 行为 |
| --- | --- | --- |
| `apps/runtime-service/src/runtime_service/workspace/attachment_receipts.py` | `AttachmentReceipts.record/require/copy_to` | 私有目录保留 HTTP 上传六字段事实，拒绝 symlink/非普通文件；fork 保留可信原名 |
| `apps/runtime-service/src/runtime_service/http/documents.py` | `upload` | 原文件入 workspace 后记录可信回执；对外六字段契约不变 |
| `apps/runtime-service/src/runtime_service/http/workspace.py` | `fork_workspace` | 原文件复制后复制可信回执，私有目录不挂载给 Agent |
| `apps/runtime-service/src/runtime_service/tools/knowledge_upload.py` | `_identity/_file/_grant/knowledge_upload_interceptor` | 绑定真实身份/Run/tool_call；读原字节校验；授权→PUT→再授权→官方 override 私有 headers；失 ACK 按原 key 回查 |
| `apps/runtime-service/src/runtime_service/tools/knowledge_jobs.py` | `JobReceipt/receipt_result/project_job_result/error_result` | 提交/任务状态安全投影；4 KiB 回执；保留 isError 与取消语义 |
| `apps/runtime-service/src/runtime_service/tools/mcp.py` | `_knowledge_schema/load_mcp_tools` | 精确 schema 与四 annotations；陌生 mutation 拒绝，原查询路径继续安全投影 |
| `apps/runtime-service/src/runtime_service/runtime/mcp_config.py` | `knowledge_upload_enabled/configured_mcp_names` | 默认关闭 submit；catalog 与 defaults 自动裁剪；旧查询不依赖新开关 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`、`services/demo/showcase_demo/agent.py` | 两 `get_agent` 组合根 | 三知识工具只接主图；Plan/schema/offload/unbound/deny 与子图边界保持 |
| 同两服务 `prompts.py` | 知识能力提示 | 仅用户明确共享才提交；queued 后报告任务，不轮询等解析 |
| 两 app `.env.example`、`scripts/local-stack.sh`、`scripts/local_stack_worktree.py` | 默认值/CALLBACKS/configs | 同环境回调；已有 Worktree 缺新增地址时从本登记 API 派生，不回退主环境 |

`mcp_submit_project_knowledge_document(file_ref)` 沿 review/workspace_write 原生 HITL；full_access 沿既有策略。未加入 `WORKSPACE_WRITE_TOOLS`，不将项目共享操作视为普通工作区写入。批准后执行仍重查当前权限。

新附件使用可信六字段回执；旧附件无回执时校验原字节与 hash，并将模型传入别名替换为已存内容地址文件名，不能伪造原上传名。服务端允许的原件上限仍为 20 MiB；RAG 支持格式以 capability 为准。

原件传输和每次授权最长 30 秒，MCP submit/job 最长 30 秒；丢 ACK 再取得新租约，用同 request_id 只读查回执，不自动新建提交。恢复失败返回 `knowledge_submission_unconfirmed`；Stop/cancel 原样传播，已受理任务由 RAG 独立继续。

迁移复用无 job 时只接受 `status=ready,reused=true`，searchable 独立反映回退后的当前可查性，可为 false。失 ACK 回查返回非 object JSON 时同样安全投影为结果未确认，不泄漏原异常、不二次 submit；新增回归先复现 AttributeError 后补类型校验。

## 验证

`tests/tools/test_knowledge_upload.py` 覆盖跨 Thread、hash/MIME/size/path、symlink、旧附件/fork、私有 header、撤权、ACK/取消、恶意 DTO、陌生 mutation/annotations/schema。`tests/services/test_knowledge_composition.py` 覆盖两主图六模式和三审批策略 approve/reject；真正权限检查由 interceptor 与 HTTP 集成另行覆盖。附件 HTTP 与 fork 回归证明新回执确实由原接口生成/复制。

`tests/tools/test_knowledge_upload_http.py` 使用真实平台 HTTP/认证/SQL/HMAC、Runtime 与官方 MCP Adapter；provider 是受控 fixture。fixtures 是该链生成的安全响应，不代表真实 LightRAG ready/索引证据。结果见 [verification.md](../verification.md)。
