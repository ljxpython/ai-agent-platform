# 错误码与恢复字段清单

> 2026-09-26平台边界执行清单；Runtime源码仅作只读证据，不修改。本文与plan.md共同构成可执行契约。

## A. 平台自有错误

所有platform-api通过PlatformApiError及子类、build_error_response生成的现有code保持，不重命名身份/权限/配置/幂等/业务错误。
这不是允许任意上游code：只有平台本地代码创建的错误享有此规则。
生产者定位：`apps/platform-api/src/platform_api/core/errors/`、`entrypoints/http/middleware/auth_context.py`、`modules/`。
平台本地唯一非空业务extra生产分支是RuntimeGatewayService._thread_reconcile_error；create_thread会将它合并到来源上游异常。
平台基础UpstreamServiceError生成upstream；原adapter生成upstream_status_code/upstream_path/upstream_detail，后两者按本清单收窄。

details生产者：core/errors/handlers.py的RequestValidationError；modules/runtime_gateway/presentation/http.py的memory模型验证；core/errors/base.py中ValidationError的转发。前两者按plan安全规范；不扫改其他正常响应。

## B. 上游可公开机器码

下面清单固定在平台adapter，精确匹配code与来源HTTP（斜线表示允许多个来源状态）。
静态来源中的动态str(exc)无法证明安全，不纳入；未知统一fallback。此表是本期确定的公开清单，不宣称枚举全部Runtime/GraphHarbor内部异常。
普通已登记4xx保持code与HTTP；登记code却状态不匹配按未知处理。5xx仍转502；memory_storage_unavailable作为明确例外保留code。message完全由表生成，不信任上游message。

| code | 来源HTTP | 固定安全message | 只读生产/消费证据 |
|---|---|---|---|
| artifact_hash_mismatch | 409 | Artifact hash mismatch | `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py:85` |
| artifact_image_type_mismatch | 415 | Artifact image type mismatch | `apps/runtime-service/src/runtime_service/workspace/media.py:21` |
| artifact_not_found | 404 | Artifact not found | `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py:79` |
| artifact_source_denied | 400 | Artifact source denied | `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py:101` |
| artifact_source_unavailable | 404 | Artifact source unavailable | `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py:108` |
| damaged_pdf | 422 | Damaged pdf | `apps/runtime-service/src/runtime_service/workspace/documents.py:35` |
| dear_governance_disabled | 409 | Dear governance disabled | `apps/runtime-service/src/runtime_service/http/dear_governance.py:17` |
| dear_governance_scope_denied | 403 | Dear governance scope denied | `apps/runtime-service/src/runtime_service/http/dear_governance.py:25` |
| dear_memory_scope_denied | 403 | Dear memory scope denied | `apps/runtime-service/src/runtime_service/http/dear_memory.py:32` |
| dear_skills_disabled | 409 | Dear skills disabled | `apps/runtime-service/src/runtime_service/http/dear_skills.py:45` |
| dear_skills_scope_denied | 403 | Dear skills scope denied | `apps/runtime-service/src/runtime_service/http/dear_skills.py:42` |
| empty_file | 415 | Empty file | `apps/runtime-service/src/runtime_service/workspace/documents.py:43` |
| encrypted_pdf | 422 | Encrypted pdf | `apps/runtime-service/src/runtime_service/workspace/documents.py:32` |
| file_content_conflict | 409 | File content conflict | `apps/runtime-service/src/runtime_service/workspace/documents.py:137` |
| file_hash_mismatch | 400/409 | File hash mismatch | `apps/runtime-service/src/runtime_service/workspace/documents.py:101` |
| file_not_found | 404 | File not found | `apps/runtime-service/src/runtime_service/workspace/documents.py:97` |
| file_scope_denied | 403 | File scope denied | `apps/runtime-service/src/runtime_service/http/documents.py:23` |
| file_target_denied | 403 | File target denied | `apps/runtime-service/src/runtime_service/http/documents.py:25` |
| file_too_large | 413 | File too large | `apps/runtime-service/src/runtime_service/http/documents.py:52` |
| file_workspace_unavailable | 409 | File workspace unavailable | `apps/runtime-service/src/runtime_service/workspace/documents.py:122` |
| html_preview_too_large | 413 | Html preview too large | `apps/runtime-service/src/runtime_service/workspace/browser.py:193` |
| invalid_artifact_image | 415 | Invalid artifact image | `apps/runtime-service/src/runtime_service/workspace/media.py:19` |
| invalid_artifact_ref | 400 | Invalid artifact ref | `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py:65` |
| invalid_document | 422 | Invalid document | `apps/runtime-service/src/runtime_service/workspace/documents.py:82` |
| invalid_file_ref | 400 | Invalid file ref | `apps/runtime-service/src/runtime_service/workspace/documents.py:93` |
| invalid_memory_fact | 400 | Invalid memory fact | `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:195` |
| invalid_pdf_magic | 415 | Invalid pdf magic | `apps/runtime-service/src/runtime_service/workspace/documents.py:27` |
| invalid_presentation | 422 | Invalid presentation | `apps/runtime-service/src/runtime_service/workspace/media.py:60` |
| invalid_skill_frontmatter | 400 | Invalid skill frontmatter | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:65` |
| invalid_skill_metadata | 400 | Invalid skill metadata | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:69` |
| invalid_skill_package | 400 | Invalid skill package | `apps/runtime-service/src/runtime_service/http/dear_skills.py:57` |
| invalid_skill_path | 400 | Invalid skill path | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_catalog.py:21` |
| invalid_source_thread_id | 400 | Invalid source thread id | `apps/runtime-service/src/runtime_service/http/workspace.py:159` |
| invalid_workspace_cursor | 400 | Invalid workspace cursor | `apps/runtime-service/src/runtime_service/workspace/browser.py:75` |
| invalid_workspace_limit | 400 | Invalid workspace limit | `apps/runtime-service/src/runtime_service/workspace/browser.py:64` |
| invalid_workspace_path | 400 | Invalid workspace path | `apps/runtime-service/src/runtime_service/workspace/browser.py:38` |
| invalid_xls_magic | 415 | Invalid xls magic | `apps/runtime-service/src/runtime_service/workspace/documents.py:50` |
| memory_capacity_exceeded | 409 | Memory capacity exceeded | `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:110` |
| memory_duplicate_fact | 409 | Memory duplicate fact | `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:204` |
| memory_expired | 409 | Memory expired | `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:164` |
| memory_extraction_cancelled | 409 | Memory extraction cancelled | `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:309` |
| memory_fact_required | 400 | Memory fact required | `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:191` |
| memory_maintenance_required | 409 | Memory maintenance required | `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:148` |
| memory_not_found | 404 | Memory not found | `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:158` |
| memory_query_too_long | 400 | Memory query too long | `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:121` |
| memory_revision_conflict | 409 | Memory revision conflict | `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:135` |
| memory_setting_required | 400 | Memory setting required | `apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py:146` |
| memory_storage_unavailable | 503 | Memory storage unavailable | `apps/runtime-service/src/runtime_service/http/dear_memory.py:22` |
| presentation_size_or_type | 413 | Presentation size or type | `apps/runtime-service/src/runtime_service/workspace/media.py:24` |
| reserved_public_skill_name | 400 | Reserved public skill name | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:125` |
| skill_capacity | 409 | Skill capacity | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:116` |
| skill_frontmatter_required | 400 | Skill frontmatter required | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:61` |
| skill_name_conflict | 409 | Skill name conflict | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:114` |
| skill_name_mismatch | 400 | Skill name mismatch | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:148` |
| skill_not_found | 404 | Skill not found | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:85` |
| skill_package_capacity | 400 | Skill package capacity | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:36` |
| skill_package_size | 413 | Skill package size | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:29` |
| skill_revision_conflict | 409 | Skill revision conflict | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:100` |
| skill_security_blocked | 400 | Skill security blocked | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:127` |
| terminal_backend_invalid | 409 | Terminal backend invalid | `apps/runtime-service/src/runtime_service/workspace/terminal.py:61` |
| terminal_disabled | 409 | Terminal disabled | `apps/runtime-service/src/runtime_service/http/terminal.py:55` |
| terminal_docker_unavailable | 503 | Terminal docker unavailable | `apps/runtime-service/src/runtime_service/workspace/terminal.py:83` |
| terminal_exited | 409 | Terminal exited | `apps/runtime-service/src/runtime_service/workspace/terminal.py:257` |
| terminal_input_busy | 429 | Terminal input busy | `apps/runtime-service/src/runtime_service/workspace/terminal.py:261` |
| terminal_input_conflict | 409 | Terminal input conflict | `apps/runtime-service/src/runtime_service/workspace/terminal.py:248` |
| terminal_input_invalid | 400 | Terminal input invalid | `apps/runtime-service/src/runtime_service/http/terminal.py:123` |
| terminal_input_sequence | 409 | Terminal input sequence | `apps/runtime-service/src/runtime_service/workspace/terminal.py:251` |
| terminal_input_too_large | 413 | Terminal input too large | `apps/runtime-service/src/runtime_service/http/terminal.py:125` |
| terminal_instance_changed | 409 | Terminal instance changed | `apps/runtime-service/src/runtime_service/workspace/terminal.py:398` |
| terminal_not_found | 404 | Terminal not found | `apps/runtime-service/src/runtime_service/workspace/terminal.py:401` |
| terminal_offset_ahead | 409 | Terminal offset ahead | `apps/runtime-service/src/runtime_service/workspace/terminal.py:230` |
| terminal_resize_failed | 503 | Terminal resize failed | `apps/runtime-service/src/runtime_service/workspace/terminal.py:302` |
| terminal_scope_denied | 403 | Terminal scope denied | `apps/runtime-service/src/runtime_service/http/terminal.py:51` |
| terminal_session_limit | 429 | Terminal session limit | `apps/runtime-service/src/runtime_service/workspace/terminal.py:383` |
| terminal_start_failed | 503 | Terminal start failed | `apps/runtime-service/src/runtime_service/workspace/terminal.py:161` |
| terminal_workspace_unavailable | 409 | Terminal workspace unavailable | `apps/runtime-service/src/runtime_service/workspace/terminal.py:70` |
| unsafe_skill_package | 400 | Unsafe skill package | `apps/runtime-service/src/runtime_service/services/dearflow_agent/skill_governance.py:47` |
| unsupported_artifact_type | 415 | Unsupported artifact type | `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py:104` |
| unsupported_file_type | 415 | Unsupported file type | `apps/runtime-service/src/runtime_service/http/documents.py:46` |
| workspace_capability_unavailable | 409 | Workspace capability unavailable | `apps/runtime-service/src/runtime_service/http/documents.py:32` |
| workspace_directory_changed | 409 | Directory changed | `apps/runtime-service/src/runtime_service/workspace/browser.py:89` |
| workspace_directory_too_large | 413 | Workspace directory too large | `apps/runtime-service/src/runtime_service/workspace/browser.py:94` |
| workspace_directory_unavailable | 404 | Workspace directory unavailable | `apps/runtime-service/src/runtime_service/workspace/browser.py:85` |
| workspace_file_unavailable | 404 | Workspace file unavailable | `apps/runtime-service/src/runtime_service/workspace/browser.py:166` |
| workspace_not_file | 415 | Workspace not file | `apps/runtime-service/src/runtime_service/workspace/browser.py:155` |
| workspace_not_found | 404 | Workspace not found | `apps/runtime-service/src/runtime_service/workspace/browser.py:79` |
| workspace_preview_unsupported | 415 | Workspace preview unsupported | `apps/runtime-service/src/runtime_service/workspace/browser.py:185` |
| cursor_expired | 410 | Event cursor expired | `apps/platform-api/tests/test_runtime_upstream_errors.py` |
| thread_active_run_conflict | 409 | Thread already has an active run | `apps/platform-web/src/services/runtime-gateway/workspace.service.ts` |
| run_start_in_progress | 409 | Run start is in progress | `apps/platform-web/src/services/runtime-gateway/workspace.service.ts` |
| idempotency_key_conflict | 409 | Idempotency key conflict | `apps/platform-web/src/services/runtime-gateway/workspace.service.ts` |
| runtime.tool.not_allowed | 403 | Tool access denied | `apps/runtime-service/src/runtime_service/runtime/tool_access.py` |
| image_scope_denied | 403 | Image scope denied | `apps/runtime-service/src/runtime_service/http/images.py` |
| runtime_target_denied | 403 | Runtime target denied | `apps/runtime-service/src/runtime_service/http/images.py` |
| image_capability_unavailable | 409 | Image capability unavailable | `apps/runtime-service/src/runtime_service/http/images.py` |
| thread_project_denied | 403 | Thread project denied | `apps/runtime-service/src/runtime_service/http/images.py` |
| image_too_large | 413 | Image too large | `apps/runtime-service/src/runtime_service/http/images.py` |

文档扫描得到87项Runtime HTTP/DocumentError静态码，补充来自网关测试、UI消费和HTTP端点的明确机器码。纯Agent运行中的工具错误若不是HTTP失败，不属于此表。

补充图片异常（`apps/runtime-service/src/runtime_service/tools/images.py` → ImageWorkspaceError）：

| code | 来源HTTP | 固定安全message |
|---|---|---|
| image_digest_mismatch | 400 | Image digest mismatch |
| image_type_unsupported | 415 | Image type unsupported |
| image_content_conflict | 409 | Image content conflict |
| image_path_invalid | 400 | Image path invalid |
| image_not_found | 404 | Image not found |
| image_workspace_unavailable | 500 | 按默认5xx转换，不公开原message |

## C. 平台fallback码

| 场景 | code | message |
|---|---|---|
| Runtime401 | runtime_delegation_rejected | Runtime authentication failed |
| 未登记403 | forbidden | Permission denied |
| 未登记422 | validation_failed | Validation failed |
| 未登记429 | langgraph_upstream_rate_limited | Runtime request rate limited |
| Runtime5xx | langgraph_upstream_request_failed | Runtime request failed |
| 传输失败 | langgraph_upstream_unavailable | LangGraph upstream is unavailable |
| 超时 | langgraph_upstream_timeout | LangGraph upstream timed out |
| 其他4xx | 调用者原fallback_code | Runtime request failed |

fallback_code来自平台adapter调用点的固定字符串，不接受上游提供。SDK的thread_get/create/search/count/delete/update/state/history与run相关fallback保留，不合并名称。非JSON、未知code不得额外保留上游原文。

## D. extra精确清单

| 来源/条件 | 公开字段 | 类型及规则 |
|---|---|---|
| 公共上游错误 | error.extra.upstream | 固定langgraph |
| 收到真实上游HTTP | error.extra.upstream_status_code | 400—599整数；无响应不写 |
| cursor_expired且来源410 | error.extra.upstream_detail.recovery | 原值恰为thread_snapshot才保留；嵌套对象不得包含其他键 |
| 平台_thread_reconcile_error，以及create_thread合并的未知结果错误 | error.extra.thread_id | 平台自己生成的规范UUID |
| 同上 | error.extra.reconcile_path | 平台按ID生成/api/langgraph/threads/{id}/reconcile |

cursor recovery接受选中error.extra.upstream_detail.recovery、选中detail.recovery或顶层recovery；按此顺序第一个合法值。上游发送thread_id/reconcile_path一律不采纳；只能由平台本地create_thread添加。
memory wrapper不携带原文extra；可以保留公共upstream与来源状态。其他任何上游字段默认丢弃。

## E. 必须保持的消费者行为

| 消费者 | 保持项 |
|---|---|
| apps/platform-web/src/composables/useArtifacts.ts | workspace_directory_changed只重试读取首页一次 |
| apps/platform-web/src/modules/dear-agent/pages/DearAgentSkillsPage.vue | skill_revision_conflict/name_conflict/package_size/unsafe_skill_package/frontmatter_required/reserved_public_skill_name/security_blocked/capacity/name_mismatch原分支 |
| apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue | memory冲突/容量/重复/过期/不存在/维护/存储不可用及403、validation_failed详情分支 |
| apps/platform-web/src/composables/useThreadTerminal.ts | terminal_exited、terminal_input_sequence、terminal_input_conflict |
| apps/platform-web/src/services/runtime-gateway/workspace.service.ts | thread_active_run_conflict、run_start_in_progress、idempotency_key_conflict |
| apps/platform-web/src/services/threads/session.service.ts | 仅平台pending UUID驱动reconcile；不因502/503/504盲目重建 |

固定机器码不意味着所有页面本期都改为公共解析：只修改会丢字段的service边界，其余页面加定向回归。未来新增公开码必须同步本表、平台映射和契约测试，不用运行时自动扫描源码作为生产逻辑。

## F. 消息队列HTTP字符串码

`apps/runtime-service/src/runtime_service/webapp.py` 的enqueue_message将ValueError映射到HTTP字符串detail，精确允许以下值；其他字符串仍fallback：

| code | 来源HTTP | 固定安全message |
|---|---|---|
| payload_too_large | 413 | Payload too large |
| queue_full | 429 | Queue full |
| message_scope_required | 409 | Message scope required |
| idempotency_conflict | 409 | Idempotency conflict |
| message_id_conflict | 409 | Message id conflict |

这些代码只做平台映射，消息队列与Runtime实现不改。
