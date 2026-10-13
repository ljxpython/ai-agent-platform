# 前端接口与工具样本

本目录样本来自6394隔离栈真实 Platform API、Runtime Worker、官方 MCP Adapter 和 Ubuntu RAG 的公开回包，公开资料均为生成的 Orion 验收资料。不包含私有Token/HMAC、模型Key、内部binding、宿主原件路径或用户登录信息。来源preview中的`asset:<opaque-id>`是RAG安全资产标识，不是可打开URL，不渲染成链接。

| 样本 | 来源与用途 |
|---|---|
| capabilities.json / capabilities-upload-disabled.json | 实际四GET之一；动态七类MIME，公开字段read_enabled；只关闭新增写后的read=true。 |
| documents.json / jobs.json / job.json | editor从API读取的真实资料、任务和单任务，含limit/offset；失败任务可能searchable=true，因为同资料后续重试已发布，错误仍须优先。 |
| submit-queued.json | PDF真实root审批后回执，queued/searchable=false。 |
| submit-ready-reused.json | 新Thread/Run提交同PNG，复用原任务，RAG无新增入库用量。 |
| submit-processing-reused.json | 原builder受控暂停时，另一Run复用parsing任务；状态可查性保持独立。 |
| job-failed.json | PNG首轮授权受跨机时钟差拒绝；历史失败保留，之后该资料重试成功，不能覆盖原失败。 |
| job-ready-hidden.json | 冻结版本回退后该任务ready但searchable=false。 |
| pending-approval.json | Fork文件复制后的真实审批interrupt，没有submit回执，不应默认queued。 |
| file-ref-pdf.json / image-ref-png.json / image-ref-jpeg.json | 实际会话原件HTTP返回，文档六字段，图片五字段，不把图片伪造为文档。 |
| query-v1.json / query-v2.json / query-v2-images.json | reader实际Agent工具结果，v1无locator，v2有page及unknown；ID/preview有界。 |
| tool-submit-queued.json / tool-query-v1.json / tool-query-v2.json | 真实ToolMessage公开字段，content是官方text块数组；artifact.structured_content与文本JSON同值。 |

测试设计边界（不用伪装成真实回包）：迁移`job_id=null,status=ready,reused=true`、`knowledge_submission_unconfirmed`、跨页/slide、恶意字段/字符串请按契约制作单测参数。真实样本没有可靠slide或跨页时，不为了截图造页码。前端应使用source_id作为来源身份，保留同标题的不同chunk/locator，避免仅按title合并丢证据。真实浏览器验收请连后端，不能把本目录fixture用route.fulfill替代入库。
