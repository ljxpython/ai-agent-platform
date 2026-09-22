# 04 - Delegation JWT Schema 文档化

## 目标

将 `apps/platform-api/src/platform_api/core/security/tokens.py` 中已有的 Delegation JWT 实现，整理为独立的正式接口契约文档，方便 runtime-service 开发者在实现 JWT 校验时有权威参考，也为未来版本升级提供基线。

> **本子专题无代码变更，纯文档输出。**

## 方案设计

将代码中提取到的完整 JWT 信息整理为标准接口契约格式，存放于 `docs/standards/delegation-jwt-schema.md`。

**代码来源（已确认）：**
- `apps/platform-api/src/platform_api/core/security/tokens.py`
  - `create_runtime_delegation_token()` L126~L244
  - `empty_runtime_context_hash()` L262~L271

## Delegation JWT 完整 Schema（从代码提取）

### Header

```json
{
  "alg": "HS256",
  "typ": "JWT",
  "kid": "<runtime_delegation_kid>"
}
```

### Payload 完整字段

```json
{
  "sub": "<subject>",
  "jti": "<uuid-hex>",
  "iss": "<runtime_delegation_issuer>",
  "aud": "<runtime_delegation_audience>",
  "iat": 1726934400,
  "nbf": 1726934400,
  "exp": 1726934460,

  "type": "runtime_delegation",
  "delegation_version": 2,
  "tenant_id": "<tenant_id>",
  "project_id": "<project_id>",
  "role": "<role>",
  "permissions": ["project.runtime.read", "project.runtime.write"],
  "policy_version": "<non-empty-string>",

  "allowed_model_ids": ["model-a", "model-b"],
  "tool_overrides": {"tool_name": false},
  "tool_policy_version": "<non-empty-string>",

  "scope": {
    "tenant_id": "<non-empty-string>",
    "project_id": "<non-empty-string>",
    "assistant_id": "<string-or-null>",
    "thread_id": "<string-or-null>",
    "operation": "<operation-enum>"
  },

  "context_hash": "sha256:<64-hex-chars>"
}
```

### `scope.operation` 枚举（15 个合法值）

```
read
run-create
message-enqueue
message-read
image-upload
image-read
workspace-file-upload
workspace-file-read
workspace-fork
terminal-read
terminal-write
dear-skills-read
dear-skills-write
dear-governance-read
dear-governance-write
```

### 字段约束

| 字段 | 约束 |
|---|---|
| `exp - iat` | TTL 60s（默认），最长 300s |
| `delegation_version` | 当前固定为 `2`，整数 |
| `allowed_model_ids` | 每项 ≤128 字符，ASCII 无空白，排序去重 |
| `tool_overrides` | 值必须全为 `false`，≤128 个 key，JSON 序列化后 ≤4096 bytes，key 排序 |
| `context_hash` | 格式：`"sha256:" + 64位十六进制`，总长 71 字符 |
| `scope.assistant_id` | 非 `read` 操作时必须有值（非 null） |
| `policy_version` | 不可为空字符串 |
| `tool_policy_version` | 不可为空字符串 |

### `context_hash` 空值定义

当没有 Runtime 上下文时，context_hash 通过以下 payload 的 sha256 计算：

```json
{
  "schema": "runtime-context/v4",
  "model_id": null,
  "temperature": null,
  "max_tokens": null,
  "top_p": null
}
```

### 共享配置（双方必须一致）

| 配置项 | platform-api 侧 | runtime-service 侧 |
|---|---|---|
| 签名密钥 | `RUNTIME_DELEGATION_SECRET` | `RUNTIME_MODEL_CONFIG_SECRET`（用于验证） |
| Issuer | `runtime_delegation_issuer` | 校验时使用 |
| Audience | `runtime_delegation_audience` | 校验时使用 |
| Kid | `runtime_delegation_kid` | 从 header 读取 |

### 版本升级规则

当需要修改 payload 结构时：
1. `delegation_version` 必须递增（当前为 2）
2. 双方必须同时部署，不支持跨版本兼容（当前设计无向后兼容）
3. 版本升级前必须更新本文档

## 任务拆分

### Task 4.1: 创建 docs/standards/delegation-jwt-schema.md
- **改动内容：** 将上述 Schema 整理为正式文档，包含字段说明、约束、版本升级规则
- **代码位置：** `docs/standards/delegation-jwt-schema.md`（新建）
- **预期结果：** runtime-service 开发者无需查阅 tokens.py 就能知道完整 JWT 结构
- **验证项：** 文档内容与 `tokens.py` 中的 `create_runtime_delegation_token()` 实现完全一致，无遗漏字段
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

### Task 4.2: 在 platform-api 和 runtime-service 的文档中加入交叉引用
- **改动内容：** 在 platform-api `docs/handbook/` 和 runtime-service `docs/standards/` 中各加一行引用指向 `docs/standards/delegation-jwt-schema.md`
- **代码位置：** `apps/platform-api/docs/handbook/` 相关文档 + `apps/runtime-service/docs/standards/` 相关文档
- **预期结果：** 读任何一个服务的文档都能找到 JWT Schema 的权威位置
- **验证项：** 引用链接有效
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

## 验证要求与记录

### 验证要求
- [ ] `docs/standards/delegation-jwt-schema.md` 内容与代码实现一致（字段、约束、枚举值）
- [ ] 两个服务的文档中均有指向 Schema 文档的引用

### 验证记录
<!-- 实施后填写 -->

## 状态

规划中
