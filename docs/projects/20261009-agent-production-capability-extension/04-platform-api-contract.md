# Platform API 契约 v1

> 用户已批准并完成非前端实现。实际 schema 见 [OpenAPI](frontend-contract/openapi.json)，真实 HTTP/Worker 响应见 [交接包](05-frontend-handoff.md)。唯一任务进度见 [tasks.md](tasks.md)；前端和现役部署未完成。

本文 `run.terminal`、HMAC 与严格 ACK 是已批准的受管 profile，区别于官方 Run webhook payload。GraphHarbor 原生兼容能力及本期扩展的区别见 [官方核对](07-langgraph-server-boundary.md)；固定目标与公网输入收紧仅约束本平台受管入口。

## 沿用现有开发范式

completion 是 runtime_gateway 的局部能力，参照现有 diagnostics/usage 分文件组织，不新建空 Protocol、通用 CRUD 基类、通知总线或 sink registry。

- application：`apps/platform-api/src/platform_api/modules/runtime_gateway/application/completion.py`（新）
- domain：`.../domain/completion.py`（新 Pydantic DTO/显式枚举）
- infra：`.../infra/sqlalchemy/models.py` 扩表；`.../infra/sqlalchemy/completion_repository.py`（新）
- history/feed/read/callback：`.../presentation/completion_http.py`，四个路由共用 `PrivateCompletionRoute`。
- 模型导入：`core/db/init_db.py::import_core_models`、`migrations/env.py`；启动router注册、Settings及 tests 同步。
- 路由注册：`apps/platform-api/src/platform_api/entrypoints/http/router.py`，增加completion_http路由；不另建FastAPI app。
- 执行认证：`core/security/tokens.py::create_runtime_delegation_token`，与 Runtime严格 claims解析对称。

以上 `.../` 表示 `apps/platform-api/src/platform_api/modules/runtime_gateway/`；建议的新函数见任务清单，现有入口不移模块。

## 受理来源和客户端边界

### 来源表 run_completion_origins

实际字段：origin_ref（UUID 格式字符串主键）、runtime_id（本期固定 default）、project_id、agent_key、source_kind（submission/schedule）、source_id、requested_by、thread_id（fresh 可空）、thread_mode、run_id（普通提交唯一）、state、created_at、updated_at。普通 source_id 为 RunRequest ID，schedule 在 native cron 响应后关联 source_id；每次更新用新的 origin_ref 表达受理版本。项目 UUID 与当前平台 ACL 确定归属，不另存可从来源推导的 tenant 或通知设置；不存 prompt、JWT、credential 或 secret。

普通来源在 `launch_runtime_run.reserve` 与 RunRequest 同事务创建；callback可能在 mark(run_id)前到达。绑定通过 compare-and-set，冲突返回409并审计，不能用后到响应覆盖早到已验证关联。

`presentation/http.py::get_runtime_gateway_service` 内的 `delegation_headers_factory` 需要新增可选origin参数，仅run-create/受控cron写入令牌；所有已有read/stop/suggestions委托默认不携带。origin是独立可选claim，不塞进既有严格scope/context schema。`ScheduledTasksService._upstream` 在实际cron create/update前使用已持久的origin，列表/预览请求没有通知来源；新任务首次拿到原生cron ID后再关联native_task_id，不依赖预先不存在的ID。

schedule origin在 `ScheduledTasksService._payload/create/update` 中随受签配置持久；一次schedule可产生多个Run。retired只停止新受理，不拒绝已经验收的Run晚到事件。fresh thread严格走现有 `thread_access.register` 与删除tombstone校验，project/owner从origin取，不信任callback自报。

schedule 更新创建新的 origin，不原地改旧 origin；旧 Run 仍按受理版本核对。原生 cron ID 创建响应后关联 source_id；响应丢失时已保存 origin 仍可接收已受理 Run。活跃旧 cron 回填由独立 dry-run/apply/revert 工具执行；原生 PATCH 无 CAS，回填窗口应暂停任务编辑，不能把普通创建路径当全量适配。

### 公网输入限制

所有 create、stream、Protocol run.start、resume/manual/schedule入口禁止浏览器提交 `webhook`、callback target/secret、origin_ref、私有callback_context（包括config/context/metadata嵌套注入），返回400安全错误。服务端启用受管callback时使用固定部署目标，不需要用户每次传URL。

这是已批准的安全契约收紧，SDK 调用方升级时也需移除公开 webhook/私有来源字段。裸 Runtime 的其他 webhook 用途由 Engine 自己的权限控制，本期不做全平台自定义 webhook 产品。

## 内网回调

`POST /api/runtime/internal/run-completion`

服务器HMAC headers、固定原文、时间窗口与传输见 [引擎交接](03-engine-terminal-delivery.md)。入口加入 `entrypoints/http/middleware/auth_context.py` 内部白名单，但handler必须独立验签；白名单不等于匿名授权。

处理顺序：

1. raw body 上限 64KiB，限制 Content-Type、重复/长度非法 headers；验签前不反序列化业务 JSON，不记录 body。
2. 从受控 key map 取 secret；本期主 key/轮换 key 都绑定 default runtime，校验 timestamp±30s、method/path/raw body HMAC、event header一致性。
3. Pydantic strict + extra=forbid；校验 UUID、长度、status/reason配对、sequence>=1、带时区时间、execution_stopped必须true。正文 schema 非法返回400；公网路由参数/正文校验为422。
4. 用origin_ref查询平台自己的来源记录；比较发送runtime、graph_id、预期thread/source类型、单Run绑定。允许启动响应竞态；不存在暂时来源返回503，超过接收窗口由发送端转死信，而非错误ACK。
5. 一次短事务写event+来源关联+notification投影；唯一键吸收重复，当前已删除对象记录suppressed，不复活。
6. 同event/digest重复返回200；同event不同digest或同Run第二个terminal返回409并告警。事务成功之后才ACK。

字段上限：graph_id 1-128、reason/model 为逐条 Literal；sequence 为严格 int，1 至 2^63-1，拒绝 bool；key ID<=128，timestamp<=20，signature 固定 71 字符，cursor<=1024。occurred_at 须带时区，schema_version 为严格整数1。未知码 fallback 在 Runtime projector 完成，API 未知码不静默接受。

受管正文（原生 webhook 仍独立使用普通 Run payload）：

```json
{
  "schema_version": 1,
  "event_id": "6b0f8c21-27d0-4d08-a333-5a18dff3c013",
  "event_type": "run.terminal",
  "origin_ref": "0da2b756-bfb0-4dc7-b6ca-1a2fef1c9c6b",
  "run_id": "2a6d0f2c-05ef-4ec7-a1f8-e9414b48f561",
  "thread_id": "81b4a30a-7cb7-4ebd-a564-6ff79409a6d7",
  "graph_id": "showcase_demo",
  "status": "error",
  "reason": "business_error",
  "outcome": {
    "reason_code": "runtime.model.retry_exhausted",
    "model_error_code": "provider_rate_limited"
  },
  "execution_stopped": true,
  "sequence": 42,
  "occurred_at": "2026-10-09T00:00:00Z"
}
```

`graph_id`为图键，不是assistant UUID。success/interrupted时两个错误码为null；timeout的reason_code固定runtime_run_timeout；error只接受Runtime白名单，缺精细原因统一runtime_execution_failed。不接受error_type原始类名、message、tenant/project/recipient、traceback、values或metadata。

ACK：

```json
{"accepted": true, "event_id": "6b0f8c21-27d0-4d08-a333-5a18dff3c013", "duplicate": false}
```

| HTTP | 意义 | 发送方 |
| --- | --- | --- |
| 200 | 已持久化或相同digest重复 | 校验ACK后delivered |
| 400/413/415/422 | 格式/大小/版本错误 | dead-letter，修复后手动重放 |
| 401/403 | key/签名/时间或可信来源越权 | dead-letter并告警；密钥修复后重放 |
| 409 | event/digest/Run/source冲突 | 不覆盖，报警与人工处理 |
| 429 | 接收端限流 | Retry-After有界重试 |
| 503/其他5xx | DB/临时依赖不可用，origin竞态 | 退避重试，不ACK |
| 3xx | 配置错误 | 不跟随redirect，不视为成功 |

HTTP错误使用现有error envelope，不泄漏哪个project/用户拥有该Run。日志仅稳定码、event/run/request id、sender和digest，不含原文。

## 平台持久化

### run_completion_events

实际字段：event_id 主键；runtime_id、origin_ref、project_id、thread_id/run_id、agent_key、status/reason、安全 reason/model 码、BIGINT sequence、occurred_at、accepted_at、body_digest、recipient_user_id（可空）、suppressed、detail_expires_at、dedup_expires_at。payload 恒为空对象，不保存回调正文；notification_code 在公开读取时由安全字段投影。

- unique(runtime_id,run_id)，不使用thread metadata短列表。
- recipient只来自origin.requested_by；service-account没有人类recipient。
- notification_code由受控纯函数投影，不输出原始错误；severity/action 由前端本地字典决定，不在回调中接收任意值。
- terminal不可被回调改成新状态；sequence变化不是允许第二终态的理由。
- 平台`delete_thread`事务/审计及Run删除/rollback网关路径同步设置suppressed/tombstone；直接Runtime维护删除只能通过当前受管Run读取确认后隐藏失效详情，不依赖不存在的对象签新读取委托。不得保留一个可公开打开的失效deep-link。

### run_completion_receipts

UUID 主键，unique(event_id,actor_user_id)，read_at UTC；幂等插入。event 详情过期后可清 receipt，不能一个 actor 已读导致其他 actor 状态变化。

事件详情 30d、digest tombstone 90d；origin 不自动清理，覆盖最晚 terminal/投递与人工重放。公开查询超过保留期返回 expired 或按现有不存在语义；不能用 TTL 让仍 pending 的 delivery 静默丢失。

同一 event 表保留 detail_expires_at/dedup_expires_at：30d 后不进入 feed，维护工具可清 receipt/安全详情；关联与 digest 留至90d。重复旧 event 仍 ACK duplicate，不重弹。超过30d 的新到 terminal 明确 suppressed，不生成可见 feed；自动维护不清 pending origin，不另建无限通知库。

## 历史 completion 查询

`GET /api/langgraph/threads/{thread_id}/runs/{run_id}/completion`

沿用当前session认证、`x-project-id`、`x-request-id`；当前Thread/Project read ACL，`Cache-Control: private, no-store`。本期不把签名callback身份当查询授权。

```json
{
  "version": 1,
  "thread_id": "81b4a30a-7cb7-4ebd-a564-6ff79409a6d7",
  "run_id": "2a6d0f2c-05ef-4ec7-a1f8-e9414b48f561",
  "availability": "available",
  "completion": {
    "event_id": "6b0f8c21-27d0-4d08-a333-5a18dff3c013",
    "graph_id": "showcase_demo",
    "status": "error",
    "reason": "business_error",
    "reason_code": "runtime.model.retry_exhausted",
    "model_error_code": "provider_rate_limited",
    "notification_code": "run_failed_provider_rate_limited",
    "occurred_at": "2026-10-09T00:00:00Z",
    "can_mark_read": true,
    "read_at": null
  },
  "request_id": "..."
}
```

| availability | completion | 含义 / 前端 |
| --- | --- | --- |
| available | 完整安全对象，包括success/interrupted | 有收件记录；只展示error/timeout摘要 |
| pending | null | 受管来源存在但completion未到；可做一次延迟重查 |
| unsupported | null | 旧Run/未启用能力，没有持久completion；不提示“运行失败” |
| expired | null | 受控tombstone证明详情超出保留期；不重试 |

缺completion不能自动推断Run成功/失败。没有记录时用现有Run查询校验目标存在和所属thread，再判断origin/能力；不能取Thread最新error。已删除/无权限使用现有404/403封套。依赖/DB临时不可用503；不会返回一个捏造的error completion。

共享thread中非recipient可读同一安全completion，但can_mark_read=false/read_at=null；已读endpoint不能替别人写receipt。

## 当前用户通知 feed

`GET /api/runtime/run-notifications?limit=20&unread_only=true&cursor=<opaque>`

- 沿用用户session、必填`x-project-id`；只返回当前用户发起的error/timeout和当前可读thread；不接受recipient/user_id/tenant筛选。
- 本期按当前项目发现；切换项目立即切换feed/cache。跨项目聚合、service-account转发、操作系统推送后置。
- limit 1-50，cursor最长1024、按received_at/event_id做keyset；cursor绑定actor/project/runtime/filter和快照上界，非法返回400。
- 默认unread_only=true；打开历史时可用false，read_at为当前actor状态。
- ACL必须在分页之前应用/批量判定，不得一次读一个远端thread形成N+1。若复杂共享ACL需分批扫描，next_cursor推进到最后已扫描项，明确scan_limit_reached避免空页无限回环。
- 轮询每次拉最新第一页，分页cursor只用于同一快照浏览历史；迟到旧Run按received_at成为新通知，UI展示occurred_at。不靠occurred_at增量水位，否则会漏迟到事件。

```json
{
  "version": 1,
  "availability": "available",
  "items": [
    {
      "event_id": "6b0f8c21-27d0-4d08-a333-5a18dff3c013",
      "thread_id": "81b4a30a-7cb7-4ebd-a564-6ff79409a6d7",
      "run_id": "2a6d0f2c-05ef-4ec7-a1f8-e9414b48f561",
      "graph_id": "showcase_demo",
      "status": "error",
      "reason": "business_error",
      "reason_code": "runtime.model.retry_exhausted",
      "model_error_code": "provider_rate_limited",
      "notification_code": "run_failed_provider_rate_limited",
      "can_mark_read": true,
      "occurred_at": "2026-10-09T00:00:00Z",
      "received_at": "2026-10-09T00:00:03Z",
      "read_at": null
    }
  ],
  "next_cursor": null,
  "scan_limit_reached": false,
  "request_id": "..."
}
```

正常空列表是200 available + items=[]；功能关闭是200 disabled + items=[]；DB故障503，不能假装空列表让前端删除已有数据。不返回prompt/thread title/raw error，也不返回API提供的任意跳转URL。首页最多显示当前页，所有合法失败持久可分页；本期不承诺每个历史事件都弹toast。

## 当前用户已读

`POST /api/runtime/run-notifications/{event_id}/read`，正文`{}`；当前actor是recipient且当前仍有读取权限才允许，session/CSRF策略沿用当前项目。幂等200：

```json
{
  "version": 1,
  "event_id": "6b0f8c21-27d0-4d08-a333-5a18dff3c013",
  "read_at": "2026-10-09T00:02:00Z",
  "request_id": "..."
}
```

重复请求返回原read_at；不存在/他人事件按现有404/403语义，不暴露存在性；503不持久更改前端已读。全部对外接口no-store，401清会话、403清权限数据、503保留同actor已有数据并标暂不可用。

## 安全码字典

固定 `reason` 配对：success/completed；timeout/timeout；interrupted/hitl_interrupt、cancel_requested、rollback；error/business_error、infrastructure_error、lease_expired。

`reason_code`：runtime_execution_failed、runtime_run_timeout、runtime_graph_step_limit_reached、runtime_model_call_limit_reached、runtime_tool_call_limit_reached；runtime.model.retry_exhausted、retry_budget_exceeded、stream_interrupted、provider_rejected、fallback_incompatible（后四项同样带 runtime.model. 前缀）；runtime.workspace.unavailable、execution_unavailable、backend_invalid、image_invalid、execution_outcome_unknown（后四项同样带 runtime.workspace. 前缀）。success/interrupted 为 null。

`model_error_code`：provider_rate_limited、provider_overloaded、provider_timeout、provider_unavailable、provider_auth_failed、provider_access_denied、context_too_long、model_unavailable、model_call_failed，或 null。单独 provider 类型映射为 reason_code=runtime_execution_failed，细类在 model_error_code；provider_timeout 的 status 为 error，不是 Worker timeout。

`notification_code`：run_timed_out；run_failed；run_failed_step_limit；run_failed_workspace；run_failed_provider_rate_limited、run_failed_provider_overloaded、run_failed_provider_timeout、run_failed_provider_unavailable、run_failed_provider_auth_failed、run_failed_provider_access_denied、run_failed_context_too_long、run_failed_model_unavailable、run_failed_model_call_failed。success/interrupted 为 null。以上字典不允许靠任意字符串前缀兜底扩充。
