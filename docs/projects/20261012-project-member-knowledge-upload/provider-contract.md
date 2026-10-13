# RAG 联调契约与修复验收

2026-10-13更新；平台非前端与V02真实Agent/生命周期联合验收已完成，RAG基线main `c30e2149`。本文保留`5be564a`两项协议修复证据；最新图片/来源v2、安全配置、Final及前端接续见[承接专项](../20261013-knowledge-documents-platform/README.md)。本轮未修改同事RAG业务源码。

2026-10-12历史复验：实际Platform API + RAG HTTP/MCP/supervisor PUT → MCP queued → start/activate 200 → ready；同request_id GET 200、reused=true且usage/attempt不变。RAG78/API17/Runtime91项、模型协议及Runtime官方Adapter各七检查通过。[当时安全证据](evidence/rag-5be564a-recheck.json)与[验证边界](verification.md)可交同事复核。原`febe70a`的403/405及模型失败仅作[历史证据](evidence/rag-recheck.json)，不再是当前协议阻塞。

## 当前源码事实

当前只读核对 `/Users/lijiaxin/PyCharmMiscProject/rag-anything-use/src/knowledge/` 和其专项证据：G01 选择**完整冻结快照恢复到独立 workspace，仅原生增量处理新文档**；12 个存储完整 flush/finalize，不需要平台另建成果缓存/索引或队列。早期`implementation/g01-evidence.md`、`g01-real.json` 和 `rag-real-chain.json` 属于 RAG 团队证据；2026-10-13平台实际联验另有[独立记录](../20261013-knowledge-documents-platform/verification.md)。

平台已兼容 capability `read`→公开 `read_enabled`、PUT 仅返回 upload_id、用户 `credential_id=""`、service_account UUID、activate 的整数 base_revision，以及 RAG 安全错误码。普通用户空凭据已可被 RAG 当前 verifier 接纳，不再将其列为仍未修复的阻塞。

**两项修复与验收结果：**

| 原缺口 | RAG 当前位置 | 5be564a 实现 | 本轮验收 |
| --- | --- | --- | --- |
| 后台 start/activate 请求字段不完整 | `src/knowledge/operation_auth.py:operation_identity/authorize`，job_worker/generations 调用 | 持久保留graph_id和原文件hash/size/name/MIME；每次新签issuer/audience/iat/exp/nonce；旧identity缺字段安全拒绝 | **通过**：实际start/activate 200，真实后台发布ready；篡改/过期/错主体/撤权拒绝，Thread删除后已受理任务仍ready |
| 失 ACK 只读回查未注册 | `src/knowledge/http_routes.py`、`upload_service.py:lookup_request`、`jobs.py:request_receipt` | 同request_id GET按token scope、有效upload grant、原主体/文件/来源校验；不依赖新写开关，不enqueue | **通过**：实际GET200/同job/reused=true，usage/attempt不变；错主体/hash/name拒绝；暂停新写仍可回查；Runtime模拟失ACK后实际GET恢复成功 |

以上协议缺口已解除，平台严格校验保持。最新capability实际支持TXT/MD/PDF/DOCX/PPTX/PNG/JPEG；当前平台已逐格式联验（TXT与MD共用文本链）。选择范围仍取provider与网关交集，图片5MiB/文档20MiB，WebP/音视频不开放知识入库。模型耗时/重试与业务质量/生产负载仍需按目标样本评估。

## 安全配置与身份

API/Runtime/RAG 使用同一知识专用 HMAC key ID/secret，secret 至少 32 字节，不与 access/refresh/delegation/completion key 复用。静态 project Bearer 只限定连接的 tenant/project/knowledge_base，不单独授予成员写入。

API 可信绑定 `tenant:project UUID → resource_id`；`PLATFORM_API_KNOWLEDGE_CONNECTIONS_JSON` 再绑定相同 resource 的 origin/Bearer/scope/knowledge_base_id。Runtime connection scope 与 RAG token scope 必须相同；浏览器/模型不可选 host/token/kb/resource。

ID：request=`kr_`+32小写hex，upload=`ku_`+32hex，job=`kj_`+32hex，document=`kd_`+32hex，kb=`kb_`+32hex。target_revision 为有界 namespace 字符串（现 RAG `kg_...`），base_revision 为非负 JSON integer。

普通用户 subject=canonical UUID，principal_type=user，credential_id 为空字符串。服务账号 subject=`service-account:<UUID>`，principal_type=service_account，credential_id=当前令牌 UUID。平台每次重新加载主体、凭据和成员；queued 不代表未来执行/发布无须授权。

## 精确授权 POST

`POST /api/runtime/internal/knowledge/authorize`，`Content-Type: application/json`，无 query，正文最多 16 KiB。格式：

```json
{"version":1,"key_id":"knowledge-v1","values":{},"signature":"<64 lowercase hex>"}
```

canonical：Python `json.dumps(values,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False)`。UTF-8 编码；签名为 HMAC-SHA256 hex，输入严格为 `knowledge-operation-request\n` 加 canonical。返回**原样 JSON envelope**，不是 base64；返回签名域为 `knowledge-operation-grant\n`。version 必须整数 1，额外字段拒绝。

所有操作的 values 必填：

| 字段 | 要求 |
| --- | --- |
| issuer/audience | upload/read：runtime-service→platform-api；start/activate：rag-anything-use→platform-api |
| operation | read/upload/start/activate 精确用途 |
| tenant_id/project_id/resource_id | 可信当前项目、canonical project UUID、配置 resource |
| subject/principal_type/credential_id | 上述身份，不从工具参数获取 |
| graph_id | dearflow_agent 或 showcase_demo |
| thread_id/run_id/tool_call_id | 原受理来源；UUID Thread/Run，tool_call_id 1–256字符无控制字符 |
| request_id | `"kr_" + sha256(canonical([tenant_id,project_id,thread_id,run_id,tool_call_id]).encode()).hexdigest()[:32]` |
| iat/exp/nonce | 每次新请求 integer Unix秒，iat≤now+5且now<exp，0<exp-iat≤30；固定5秒未来签发时差，无过期宽限；nonce uuid4.hex |

操作特有字段：

| 操作 | 特有字段 | 平台检查 |
| --- | --- | --- |
| upload | sha256/size_bytes/file_name/mime_type；knowledge_base_id 可不填 | 新上传开关、当前 upload 权限、active项目、comment ACL、原Run主体、非Plan/offload、当前 submit deny |
| start | 上述四文件字段、knowledge_base_id、job_id | 当前原主体/凭据/成员/项目及 submit deny、原Run来源；不要求Thread存活，不受平台关闭新上传影响 |
| activate | start全部字段，再 target_revision/base_revision | 同上；grant 精确绑定候选和基准版本；active切换CAS由RAG完成 |
| read | job_id；knowledge_base_id 可不填；不带文件字段 | 当前 read 权限、active项目、read ACL、原Run及 job工具 deny；仅Runtime在任务读取前后调用，RAG无需消费此grant |

sha256=64hex，size_bytes=1–20MiB integer，file_name=1–200字符且无路径/控制字符，MIME 为合法有界类型。job_id/target/base 在不适用操作时省略或使用允许的 null；read 不接受四文件字段。响应 values 填入可信 kb，issuer=platform-api、audience=rag-knowledge，iat/exp/nonce 重新签发，最长30秒，其余原字段精确保持；可选值在响应中为 null。

request nonce 不存一次消费表；合法短时重放仍重新授权，费用去重依赖 RAG 的原件/hash/处理签名和 requests 唯一键。IAM/发布之间最多30秒租约窗口，不声称跨库强事务。

## 原件传输与 MCP

1. Runtime 校验当前Thread原字节和六字段文档FileRef；五字段图片ImageRef必须有Agent挂载外可信收据，在interceptor转换为RAG六字段引用。然后调用upload授权。
2. `PUT <可信MCP origin>/internal/knowledge/uploads/{request_id}`，Bearer为配置值；`X-Knowledge-File-Ref`=ASCII canonical FileRef，`X-Knowledge-Operation-Grant`=canonical grant envelope，`Content-Type`=FileRef MIME；body=原始bytes。返回 `{"upload_id":"ku_..."}`，必须在完整持久保存后返回。
3. 上传结束再调用 upload 授权；官方 MCP `MCPToolCallRequest.override(headers=...)` 私有注入 `X-Knowledge-Upload-ID` 与新grant。
4. MCP tool名 `mcp_submit_project_knowledge_document(file_ref)`，工具 schema 顶层仅一个 required file_ref object；四 annotations 固定 readOnly=false/destructive=false/idempotent=true/openWorld=false。不能把秘密或全文作为工具参数。
5. 受理返回 queued/reused 安全回执，Agent结束本次提交，不等解析；状态工具 `mcp_get_project_knowledge_ingest_job(job_id)` 顶层仅 required job_id string，readOnly=true。

各直接HTTP请求和MCP submit/job最长30秒；提交超时/传输失ACK时 Runtime 不再调用submit，重新取得租约后用下述GET核实。CancelledError传播；聊天 Stop不取消已持久受理的RAG任务。

**已实现并实测的只读回查：**

```text
GET /internal/knowledge/uploads/{request_id}
Authorization: Bearer <trusted project token>
X-Knowledge-Operation-Grant: <fresh upload grant, same original request>
```

返回 `{"request_id":"kr_...","receipt":null}` 表示当次查询未确认受理；已受理返回相同 request_id 加安全提交回执，`reused=true`。必须按已保存的原 identity、hash、size 与 scope 验证，不能因 token 属于同一项目就读取其他人的私有上传事实。GET 不新建任务，不消费次数，网络重连不能换 key。

## 回执和状态 HTTP

提交回执：version、job_id、document_id、file_name、status、searchable、error_code、created_at、updated_at、reused。文本 JSON=structuredContent，仅一个 text block，≤4KiB。公开字段投影后无 upload/grant/token/raw_data/host path。

status=queued/parsing/indexing/publishing/ready/failed；searchable 为当前版本可查性，独立于任务状态。failed必须安全 error_code；其余 error_code=null。timestamp 为带时区 ISO8601，updated≥created。迁移历史无job的重复提交可 job_id=null/status=ready/reused=true；searchable可随回退为false，此时不要声称仍可查或轮询null。任务GET/MCP job必须有真正job_id，去掉reused。

API代理四 RAG只读端点 `/internal/knowledge/{capabilities,documents,jobs,jobs/{job_id}}`，Bearer固定scope。能力字段 version/read（或read_enabled）/upload_enabled/supported_mime_types/max_file_bytes/disabled_reason。分页 `{items,total}`，limit默认20、1–100，offset≥0；资料列表仅active版本ready/searchable文档。安全错误精确白名单见双端schemas；未知错误统一knowledge_unavailable。

## 交付后真实验收

两协议无需再请求同事补修。2026-10-13已在当前平台实际Agent Worker与Ubuntu隔离RAG验证普通executor上传/审批、成员累积检索、处理中/ready跨Run同hash零新增用量、两项目排队/旧读、Stop/重启/Fork、权限拒绝及冻结版本回退；RAG119项包含候选失败/CAS/受控崩溃恢复，不能外推生产故障承诺。前端与正式部署接续按[交接](../20261013-knowledge-documents-platform/frontend-handoff.md)，目标环境仍须自行验收，Bearer/HMAC仅私有注入。默认新增上传关闭、来源1，关闭新上传不取消已受理任务。
