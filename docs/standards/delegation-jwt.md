---
status: draft
last_verified: 2026-09-27
confidence: medium
source_project: docs/projects/20260926-delegation-jwt-contract/verification.md
note: claim 规则和 23 项 operation 已验；消息内部原生 Run 子调用待 message-run-read-delegation 专项部署后补验
---

# Delegation JWT Schema（draft）

> **适用服务：** platform-api（签发方）、runtime-service（校验方）
> **验证证据：** API 299 passed；Runtime 只读鉴权 46 passed；真实 R01-R04 链路（含 68.499 秒跨 TTL Run）通过
> **⚠️ 未完成：** 消息内部原生 Run 子调用（message-enqueue / message-read）当前返回 403，待另行批准后补验

## JWT Header

```json
{
  "alg": "HS256",
  "typ": "JWT",
  "kid": "<runtime_delegation_kid>"
}
```

## Payload 字段

```json
{
  "sub": "<user_id 或 service-account:<UUID>>",
  "jti": "<uuid4().hex>",
  "iss": "<runtime_delegation_issuer>",
  "aud": "<runtime_delegation_audience>",
  "iat": 1727395200,
  "nbf": 1727395200,
  "exp": 1727395260,

  "type": "runtime_delegation",
  "delegation_version": 2,
  "tenant_id": "<tenant_id>",
  "project_id": "<project_id>",
  "role": "<role>",
  "permissions": ["project.runtime.read"],
  "policy_version": "<non-empty-string>",
  "credential_id": "<credential-uuid>",

  "allowed_model_ids": ["model-a"],
  "tool_overrides": {"tool_name": false},
  "tool_policy_version": "<non-empty-string>",

  "scope": {
    "tenant_id": "<必须与顶层一致>",
    "project_id": "<必须与顶层一致>",
    "assistant_id": "<string 或 null>",
    "thread_id": "<string 或 null>",
    "operation": "<23 项枚举之一>"
  },

  "context_hash": "sha256:<64位十六进制>",
  "request_id": "<32位小写十六进制>",
  "platform_trace_id": "<32位小写十六进制>"
}
```

## 字段约束

| 字段 | 约束 |
|---|---|
| `delegation_version` | 严格整数 2，布尔值也拒绝 |
| `type` | 精确等于 `runtime_delegation` |
| `sub` | 用户取 `actor.user_id`；service account 取 `service-account:<UUID>`；不接收客户端覆盖 |
| `allowed_model_ids` | 非空名称数组，唯一且排序；空数组被拒绝；无模型哨兵值 `platform:no-enabled-model` |
| `jti` | 每次签发生成，Runtime 允许缺省但平台始终生成 |
| `credential_id` | service account 签发必须携带；普通用户禁止携带 |
| `tool_overrides` | 值只能为 `false`；键符合名称规则；≤128 键；紧凑 JSON ≤4096 字节 |
| `context_hash` | 格式：`sha256:` + 64 位十六进制，总长 71 字符 |
| scope 额外键 | 只允许五个键，未知键拒绝 |
| 未知顶层 claim | Runtime 严格拒绝 |

## scope.operation 枚举（23 项）

```
read                    thread-create           thread-reconcile
run-create              thread-edit             thread-delete
run-cancel              run-delete              message-enqueue
message-read            image-upload            image-read
workspace-file-upload   workspace-file-read     workspace-fork
terminal-read           terminal-write          dear-skills-read
dear-skills-write       dear-memory-read        dear-memory-write
dear-governance-read    dear-governance-write
```

**原生资源白名单（仅 8 项可访问原生资源）：**
`read` / `thread-create` / `thread-reconcile` / `thread-edit` / `thread-delete` / `run-create` / `run-cancel` / `run-delete`

其余 15 项自定义 token，不能访问原生资源。

## 生命周期规则

- 委托到期不自动取消已接受 Run
- 已建立 SSE 不增加持续重鉴权或定时断流
- 重连 / 审批 / 取消等新 HTTP 请求加载当前身份重新签发
- 过期 JWT 用于新 Runtime 请求按现有 401 拒绝，不自动降级匿名，不自动重放用户动作

## 错误映射

| 场景 | 公开 HTTP | 公开 code |
|---|---|---|
| 签发失败（无原文 / claim / secret） | 503 | `runtime_delegation_not_configured` |
| Runtime 401 | 502 | `runtime_delegation_rejected` |
| Runtime 403 | 403 | 保留已登记安全码或 `forbidden` |
| ACL 回查 503 | — | 按既有公共转换 |

## 共享配置（双方必须一致）

| 配置项 | platform-api 侧 | runtime-service 侧 |
|---|---|---|
| 签名密钥 | `RUNTIME_DELEGATION_SECRET` | 用于校验 |
| Issuer | `runtime_delegation_issuer` | 校验时使用 |
| Audience | `runtime_delegation_audience` | 校验时使用 |
| Kid | `runtime_delegation_kid` | 从 header 读取 |
| TTL | 60s（默认），最长 300s | — |
