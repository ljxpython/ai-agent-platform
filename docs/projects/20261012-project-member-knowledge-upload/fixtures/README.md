# 前端协议 fixture

七份 JSON 由 `apps/runtime-service/tests/tools/test_knowledge_upload_http.py` 的真实 HTTP 测试生成：平台认证、数据库授权、HMAC、Runtime interceptor、官方 MCP HTTP Adapter 均实际运行；外部 provider 是受控内存协议服务。**ready/documents 由 fixture 模拟发布，不是 LightRAG 解析/增量发布或费用证据。**

每份外层 `origin/scenario/payload` 是测试样例包装。queued 的 payload 包含 ToolMessage content 与 artifact，DTO 为 `payload.artifact.structured_content`；reused/job 的 payload 是 Adapter artifact，DTO 为 `payload.structured_content`；capabilities/jobs/ready/documents 的 payload 就是平台 GET 正文。前端不能把样例包装当业务DTO。

| 文件 | 场景 |
| --- | --- |
| [queued.json](queued.json) | 首次受理，queued/searchable=false/reused=false |
| [reused.json](reused.json) | 原调用 key 重复提交，原 job_id/reused=true |
| [job.json](job.json) | 状态工具安全回执，无 reused |
| [capabilities.json](capabilities.json) | 已配置隔离 provider 的能力响应；不代表本地部署开关已开启 |
| [jobs.json](jobs.json) | 项目任务分页，items/total |
| [ready.json](ready.json) | 模拟发布后单任务 ready/searchable=true |
| [documents.json](documents.json) | 模拟当前发布版本资料分页 |

生成命令（Runtime app 目录）：

```bash
KNOWLEDGE_UPLOAD_FIXTURES="/绝对路径/当前Worktree/docs/projects/20261012-project-member-knowledge-upload/fixtures" uv run --frozen pytest "tests/tools/test_knowledge_upload_http.py" -q --tb=short
```

ID/时间是隔离合成数据，生成时 ID 可能变化；不要把样例值作为生产配置。迁移无 job、回退不可查、failed 和工具错误边界见 [前端交接](../frontend-handoff.md) 与 `tests/tools/test_knowledge_upload.py`，前端据契约补组件场景。
