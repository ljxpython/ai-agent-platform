# 委托鉴权机制与短时令牌（Delegation JWT）深度解剖

> **设计核心目标**：实现控制面（`platform-api`）与执行面（`runtime-service`）的**物理级安全解耦**。
> 杜绝两个严重缺陷：① 内部服务裸奔（内网攻击即沦陷）；② 透传前端用户长期 Token（导致执行层越权与密钥泄漏）。

---

## 零、 知识前置与上下文串联（Knowledge Bridges）

在深入阅读具体的代码和加密字段前，必须先理清三个前置概念，以及这一步在全系统链路中的具体坐标。

### 1. 前置必备概念速查（不看这个后面看不懂）

- **概念 1：用户登录凭据（User JWT）与委托凭据（Delegation JWT）的本质区别**
  - **User JWT**：用户在网页上输完账号密码后签发，代表“我是张三”，有效期较长（通常数小时或数天）。它属于**前端用户会话凭据**，绝对不能泄露给执行层，更不能直接用来指挥大模型；
  - **Delegation JWT**：由控制面网关针对单次具体操作临时签发，代表“平台授权张三在指定项目内调一次 GPT-4o 跑这个线程”，有效期只有 **60 秒**。它属于**内部服务间工作凭据**，具有严格的最小权限范围。
- **概念 2：为什么选用 HS256 对称加密，而不是 RSA 非对称公私钥？**
  - 在大型公网微服务中常用 RS256（公钥验证、私钥签名）。但在本项目中，`platform-api` 和 `runtime-service` 属于同一个内网受信体系，共享相同的环境变量配置；
  - 对称加密（HS256）的运算开销比非对称加密低 10 倍以上。在高并发流式对话场景下，网关每秒需要处理密集的换签与验签，HS256 能够大幅降低 CPU 负载并缩短首字延迟。
- **概念 3：LangGraph SDK 的原生 Auth 认证模型**
  - 许多人以为 LangGraph 只是一个 Python 图编排库，实际上它的服务端框架定义了两级鉴权生命周期：
    - `@auth.authenticate`：请求入口认证拦截器，负责提取 HTTP Authorization 头并解码出身份字典；
    - `@auth.on`：细粒度资源守卫，在具体操作 `threads`（线程）或 `runs`（执行实例）时触发，支持基于业务规则做二次拦截。

### 2. 链路上下文坐标（从哪来到哪去）

- **输入来源（上游）**：
  前端用户在界面点击“发送”，`apps/platform-web/src/composables/useChatSession.ts` 携带用户的 User JWT 调用控制面接口 `POST /api/v1/threads/{id}/runs/stream`。
- **当前处理（本层）**：
  控制面 `platform-api` 拦截到请求，核验用户是否在目标项目内，查出该项目允许调用的模型白名单与工具禁用策略，然后调用 `tokens.py` 现场“现炒现卖”签发一张 60 秒有效的 Delegation JWT。
- **输出去向（下游）**：
  控制面将这张 Delegation JWT 塞进 HTTP Header `Authorization: Bearer <delegation_jwt>`，通过反向代理打到 `runtime-service`（8001 端口）。Runtime 的 `@auth.authenticate` 验签放行后，把模型白名单注入给 LangGraph 图节点开始推理。

---

## 一、 源码精准坐标映射（Code Pointer Map）

阅读本篇时，可直接对照仓库内的真实实现文件：

| 模块职责 | 核心源码路径 | 关键类 / 函数 / 钩子 |
|---|---|---|
| **小票签发工厂** | `apps/platform-api/src/platform_api/core/security/tokens.py` | `create_runtime_delegation_token()` |
| **网关凭证装配** | `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` | `_delegation_operation()`, `delegation_headers_factory()` |
| **策略与白名单提取** | `apps/platform-api/src/platform_api/modules/runtime_policies/application/service.py` | `RuntimePoliciesService.build_delegation_policy()` |
| **运行时验签适配器** | `apps/runtime-service/src/runtime_service/auth/platform.py` | `@auth.authenticate`, `verify_delegation_claims()` |
| **LangGraph 细粒度资源守卫** | `apps/runtime-service/src/runtime_service/auth/platform.py` | `@auth.on` 路由守卫（`deny_image_scope_on_server_resources`） |

---

## 一、 真实 JWT 报文与字段规范（Schema Level）

每次网关向 Runtime 发起调用时，必须在 HTTP Header 中携带：
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InJ1bnRpbWUtZGV2In0...
```

### 1. Header 头部结构
```json
{
  "alg": "HS256",
  "typ": "JWT",
  "kid": "runtime-delegation-key-v1"
}
```

### 2. 真实完整的 Payload 字段（已脱敏样例）
```json
{
  "sub": "user_2tg0GvH7aK8b9",
  "jti": "e4c7b8a192f04e1ab3450912f8a7e6b5",
  "iss": "platform-api",
  "aud": "runtime-service",
  "iat": 1727600000,
  "nbf": 1727600000,
  "exp": 1727600060,

  "type": "runtime_delegation",
  "delegation_version": 2,
  "tenant_id": "tenant-default",
  "project_id": "proj-9876",
  "role": "project_developer",
  "permissions": ["project.runtime.read", "project.runtime.write"],
  "policy_version": "pv_20260928_01",
  "credential_id": "cred-771a-49c0",

  "allowed_model_ids": [
    "openai/gpt-4o",
    "deepseek/deepseek-chat"
  ],
  "tool_overrides": {
    "bash_exec": false,
    "system_rm_rf": false
  },
  "tool_policy_version": "tpv_20260928_01",

  "scope": {
    "tenant_id": "tenant-default",
    "project_id": "proj-9876",
    "assistant_id": "asst_code_helper",
    "thread_id": "th_88a91b2c",
    "operation": "run-create"
  },

  "context_hash": "sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
  "request_id": "c1f20d6f43e54b67912e8317c4b699a2",
  "platform_trace_id": "c1f20d6f43e54b67912e8317c4b699a2"
}
```

### 3. 23 个严格受控的 Operation 命名空间
系统不支持泛通配符（如 `*`）。在 `tokens.py` 第 192~215 行硬编码了 23 项合法操作枚举，任何未列入的操作都会在签发阶段直接报错抛出 `ValueError`：
- **只读类**：`read`、`message-read`、`image-read`、`workspace-file-read`、`terminal-read`、`dear-skills-read`
- **线程管理**：`thread-create`、`thread-reconcile`、`thread-edit`、`thread-delete`
- **运行控制**：`run-create`、`run-cancel`、`run-delete`、`message-enqueue`
- **资源扩展**：`image-upload`、`workspace-file-upload`、`workspace-fork`、`terminal-write` 等

---

## 二、 端到端函数级调用时序（Trace Execution Stack）

当用户在界面发起一次聊天生成（`POST /api/v1/threads/{id}/runs/stream`）时，系统内部函数调用链如下：

```mermaid
sequenceDiagram
    autonumber
    participant UI as 前端组件 (useChatSession.ts)
    participant GW_HTTP as API 入口 (http.py)
    participant Policy as 策略引擎 (service.py)
    participant Signer as 签发核心 (tokens.py)
    participant Upstream as 反向代理 (runtime_client.py)
    participant RT_Auth as 运行时验签 (platform.py)
    participant SDK_Hook as LangGraph 资源守卫 (@auth.on)

    UI->>GW_HTTP: POST /api/v1/threads/{id}/runs/stream
    Note over GW_HTTP: 提取用户 JWT，解析出当前租户与操作人
    GW_HTTP->>Policy: build_delegation_policy(project_id)
    Policy-->>GW_HTTP: 返回: allowed_model_ids, tool_overrides, policy_version
    GW_HTTP->>Signer: create_runtime_delegation_token(scope={"operation": "run-create", ...})

    rect rgb(240, 248, 255)
        Note over Signer: 校验 1: 密钥长度 >= 32 字节<br>校验 2: tool_overrides 必须全为 false (仅能显式禁用)<br>校验 3: operation 必须在 23 项白名单内<br>计算过期时间: exp = now + 60
    end
    Signer-->>GW_HTTP: 返回 HS256 签名的 JWT 字符串

    GW_HTTP->>Upstream: 转发请求至 Runtime (Header: Authorization Bearer <token>)
    Upstream->>RT_Auth: @auth.authenticate 拦截请求
    RT_Auth->>RT_Auth: verify_delegation_claims() 验证签名、aud、exp
    RT_Auth-->>SDK_Hook: 挂载 UserDict 至 LangGraph 上下文

    rect rgb(255, 250, 240)
        Note over SDK_Hook: 校验 4: 检查 operation 是否被允许访问该资源<br>校验 5: 检查当前 thread_id 是否与小票严格一致<br>校验 6: 检查用户角色是否满足操作门槛
    end

    SDK_Hook-->>Upstream: 准入放行，启动 LangGraph 图状态机执行
```

---

## 三、 核心实现高保真伪代码（1:1 还原真实业务）

### 1. 控制面：防篡改签发器（提取自 `tokens.py`）

```python
# 对应源码：apps/platform-api/src/platform_api/core/security/tokens.py
import json
import time
import uuid
import jwt
from typing import Mapping, Sequence

# 强制白名单枚举，杜绝通配符注入
ALLOWED_OPERATIONS = {
    "read",
    "thread-create",
    "thread-reconcile",
    "run-create",
    "thread-edit",
    "thread-delete",
    "run-cancel",
    "run-delete",
    "message-enqueue",
    "message-read",
    "image-upload",
    "image-read",
    "workspace-file-upload",
    "workspace-file-read",
    "workspace-fork",
    "terminal-read",
    "terminal-write",
    "dear-skills-read",
}


def create_runtime_delegation_token(
    *,
    subject: str,
    tenant_id: str,
    project_id: str,
    role: str,
    permissions: Sequence[str],
    policy_version: str,
    allowed_model_ids: Sequence[str],
    tool_overrides: Mapping[str, bool],
    tool_policy_version: str,
    scope: Mapping[str, str | None],
    secret: str,
    request_id: str | None = None,
    platform_trace_id: str | None = None,
) -> str:
    # 规则 1：内网对称密钥硬性要求至少 32 字节（256 位熵）
    if len(secret.encode("utf-8")) < 32:
        raise ValueError("runtime delegation secret must be at least 32 bytes")

    # 规则 2：tool_overrides 采用“封禁机制”，值必须全为 False，严禁越权启用未授权工具
    if not isinstance(tool_overrides, dict) or any(
        v is not False for v in tool_overrides.values()
    ):
        raise ValueError("tool_overrides must contain only false values")

    # 规则 3：Operation 强校验
    operation = scope.get("operation")
    if operation not in ALLOWED_OPERATIONS:
        raise ValueError(f"unsupported runtime delegation operation: {operation}")

    now = int(time.time())
    payload = {
        "sub": subject,
        "jti": uuid.uuid4().hex,  # 唯一票据编号，杜绝重放
        "iss": "platform-api",
        "aud": "runtime-service",
        "iat": now,
        "nbf": now,
        "exp": now + 60,  # 严格 60 秒生存期
        "type": "runtime_delegation",
        "delegation_version": 2,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "role": role,
        "permissions": list(permissions),
        "policy_version": policy_version,
        "allowed_model_ids": list(allowed_model_ids),
        "tool_overrides": tool_overrides,
        "tool_policy_version": tool_policy_version,
        "scope": dict(scope),
        "request_id": request_id,
        "platform_trace_id": platform_trace_id,
    }

    return jwt.encode(
        payload,
        secret,
        algorithm="HS256",
        headers={"kid": "runtime-delegation-key-v1"},
    )
```

### 2. 执行面：LangGraph 细粒度拦截守卫（提取自 `platform.py`）

```python
# 对应源码：apps/runtime-service/src/runtime_service/auth/platform.py
from langgraph_sdk import Auth

auth = Auth()


@auth.authenticate
async def authenticate(
    authorization: str | None = None,
) -> Auth.types.MinimalUserDict:
    # 1. 验证格式与解出 Bearer
    token = extract_bearer_token(authorization)

    # 2. 验签与过期校验 (HS256 签名匹配、aud 匹配、exp 未超期)
    verified = verify_delegation_claims(
        token,
        secret=get_env("PLATFORM_RUNTIME_DELEGATION_SECRET"),
        issuer="platform-api",
        audience="runtime-service",
    )

    # 3. 将身份、模型白名单与工具限制挂入上下文，不泄露密钥
    return {
        "identity": verified.principal.user_id,
        "is_authenticated": True,
        "tenant_id": verified.principal.tenant_id,
        "project_id": verified.principal.project_id,
        "allowed_model_ids": list(verified.policy.allowed_model_ids),
        "denied_tools": verified.policy.denied_tool_names,
        "runtime_scope": dict(verified.scope),
    }


@auth.on
async def enforce_scope_and_thread_isolation(
    ctx: Auth.types.AuthContext, target_resource: dict
):
    scope = ctx.user["runtime_scope"]
    operation = scope.get("operation")

    # 规则 4：小票绑定的 Thread ID 与实际访问的 Thread ID 必须严格相等，防止水平越权
    bound_thread = scope.get("thread_id")
    target_thread = target_resource.get("thread_id")

    if (
        bound_thread
        and target_thread
        and str(bound_thread) != str(target_thread)
    ):
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Thread scope mismatch: 禁止跨会话操作"
        )

    # 规则 5：只有 scope.operation 为 run-create 时，才允许在 runs 资源上触发 create 动作
    if ctx.resource == "runs" and ctx.action == "create":
        if operation != "run-create":
            raise Auth.exceptions.HTTPException(
                status_code=403, detail="当前委托凭据不允许创建运行实例"
            )
```

---

## 四、 常见攻击防范与安全边界设计（Edge Cases & Security Hardening）

1. **防重放与短生命周期（60s TTL）**：
   - 即使日志组件意外打印了 Header，该凭证在 60 秒后自动成为废纸，黑客拿到也无法发起离线重放攻击。
2. **防横向跨项目越权（Project Isolation）**：
   - 用户属于 Project A，即使通过前端篡改数据把 `thread_id` 改成 Project B 的线程，网关在 `build_delegation_policy()` 阶段查验用户所属 Project，签发出的 `project_id` 与目标线程所属项目冲突，Runtime 立即根据 ACL 阻断。
3. **工具与模型白名单锁定（BYOK Security）**：
   - 大模型调用费用极高，小票中包含 `allowed_model_ids`。Worker 启动 Agent 时，一旦检测到图节点试图实例化白名单之外的模型，直接在 Python 进程内抛出拒绝异常。
