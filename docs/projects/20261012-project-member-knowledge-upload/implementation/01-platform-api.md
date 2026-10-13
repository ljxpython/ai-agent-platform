# Platform API 成员知识控制面

2026-10-12；对应 A01/A02。当前 Worktree `6394/ai-agent-platform`，分支 `feat/project-knowledge-mcp`。

## 改动与理由

原平台只在 Thread create/fork 注入受信 MCP resource，缺少知识资料/任务视图和普通成员上传授权。本轮沿模块化单体增加 `modules/knowledge/`，使用已有 Actor、IAM、Thread ACL、RunRequestsRepository、项目工具限制、错误 Envelope 和 HTTP 审计。

| 文件 | 具体入口 | 行为 |
| --- | --- | --- |
| `apps/platform-api/src/platform_api/modules/iam/application/policies.py` | `PermissionCode`、`PROJECT_PERMISSION_MAP` | 新增 `project.knowledge.read/upload`，三项目角色均允许，executor 不获得 runtime.write |
| `apps/platform-api/src/platform_api/modules/knowledge/router.py` | `capabilities/documents/jobs/job/authorize` | 四公开 GET；一个独立签名的内部授权 POST；限制查询键和正文大小 |
| `apps/platform-api/src/platform_api/modules/knowledge/service.py` | `current_actor/require_scope/KnowledgeService.read` | 每次加载当前主体/凭据/成员；项目 active；网络前后授权；Session 不跨 await |
| `apps/platform-api/src/platform_api/modules/knowledge/authorization.py` | `KnowledgeRead/KnowledgeOperation/parse_operation/authorize_operation` | 精确 read/upload/start/activate，专用 HMAC；绑定 scope、原 Run 主体、工具、文件与候选；30 秒 grant |
| `apps/platform-api/src/platform_api/modules/knowledge/schemas.py` | `KnowledgeCapabilities/KnowledgeDocument/KnowledgeJob` | 严格安全字段、ID、文件名、时间、分页及错误白名单 |
| `apps/platform-api/src/platform_api/adapters/knowledge/client.py` | `KnowledgeClient.get` | 受管 origin/token；读取最多 1 MiB，10 秒总截止时间，拒绝重定向 |
| `apps/platform-api/src/platform_api/config.py` | `KnowledgeConnection/Settings.validate_security_guards` | 绑定与连接 scope 一致；独立 secret；新增写能力默认关闭 |
| `apps/platform-api/src/platform_api/bootstrap/lifespan.py` | lifespan | HTTP client 生命周期统一管理 |
| `apps/platform-api/src/platform_api/entrypoints/http/router.py`、`middleware/auth_context.py` | router/认证入口 | 注册新模块；内部 POST 由专用签名验证，用户 Bearer 不授予授权能力 |
| `apps/platform-api/src/platform_api/modules/audit/http_resolution.py` | `resolve_http_audit` | 知识 GET 与精确授权动作；只记录操作和有界关联 ID |

旧处理方式：平台无法按知识用途授权普通成员，只能管理员离线维护。新处理方式：独立知识权限加当前状态校验，原线程执行权限、已有审批策略继续起作用；平台只保存治理事实，RAG 负责原件、任务与索引。

`upload` 要求 Thread comment；`read` 要求 Thread read，并在工具结果返回后复核。`start/activate` 保留原 Run 的可信来源，重新检查原主体、凭据、项目与 deny；不要求 Thread 继续存在，因此聊天 Stop/删除不取消已受理入库。

新增接口不迁移数据库。读授权是 Runtime/平台内部使用，不要求 RAG 新增 read 签名支持。后台授权输入和丢 ACK 回查仍需同事按 [provider 契约](../provider-contract.md) 对齐。

## 验证

`tests/test_knowledge_member_upload.py` 覆盖三角色、非成员、撤权、项目禁用、scope、分页、恶意 DTO、超时与异步 Session 边界；`tests/test_knowledge_authorization.py` 覆盖签名/过期、Run 主体、Thread 删除、Plan/deny、服务账号撤权、read 项目 active 与真实审计写入。实际执行结果维护在 [verification.md](../verification.md)，本文件不作为进度来源。

签名 nonce 未建立一次消费表；短窗口内合法重复请求仍会重查当前权限，任务幂等由 RAG request_id 和原件 hash 提供。grant 是最多 30 秒租约，发布和 IAM 不是跨库原子事务。
