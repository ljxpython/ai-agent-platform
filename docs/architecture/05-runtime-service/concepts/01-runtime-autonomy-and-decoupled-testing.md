# 01-执行层微服务自治与无依赖测试架构 (Runtime Autonomy and Decoupled Testing)

> **模块定位与核心价值**：深度解剖底层执行引擎（`runtime-service`）如何在生产级高密安全防御（Delegation JWT、Opaque Token、双层 RBAC）的前提下，通过依赖注入、PEP 纯数学验签自闭环与独立测试套件，实现“开发脱离控制面、单测零上层网络依赖、图执行零大模型调用开销”的真正微服务自治架构。

---

## 零、痛点与生活演进史（Why Runtime Autonomy?）

在很多初创团队或二流架构中，经常会出现令人窒息的“微服务连体婴儿（Distributed Monolith）”现象：
- 算法同学只想改一下 Agent 图节点的一个条件路由或 Prompt 模板；
- 结果一跑单元测试，终端疯狂报错 `httpx.ConnectError: Failed to connect to platform-api:8000`；
- 原来执行层代码里硬编码了去控制面查询用户表、核验 RBAC 权限、兑换大模型密钥；
- 算法同学被逼着在本地装 Node.js、起前端容器、起 PostgreSQL、跑数据迁移、登录账号生成 Token……改一行代码耗时 2 小时，全员效率暴跌！

```
[❌ 分布式单体反模式]
runtime-service 单测 ──(HTTP RPC)──> platform-api ──> platform DB (缺一不可，连体婴儿)

[✅ 本平台微服务自治架构]
runtime-service 自身是纯粹的状态机与纯数学 PEP 校验核，拔掉网线、断开上层，照样全速自测！
```

### 生活大白话类比：发动机台架测试 vs 整车上路牌照
1. **愚蠢的连体做法**：工厂车间里，工程师每拧一下发动机螺栓，或者测试一下气缸点火，都必须要求交警队在场审核车主驾驶证、车管所核发临时牌照、ETC 扣一次高速过路费。连基本的出厂点火测试都跑不通。
2. **本平台的工业解耦做法**：
   - **台架测试（本地单测）**：发动机直接固定在测试台架上，油门和阻力用外接电动机模拟（通过 `configurable._runtime_model` 注入 `BindableFakeChatModel`），不费一滴汽油（零 Token 费用），毫秒级完成万次点火测试；
   - **闭合电路测试（HTTP 接口集成测试）**：安检门（`auth/platform.py`）只认统一规范的防伪印章（JWT 签名）。测试人员在车间内部拿同一套工模印章自己盖戳（本地对称密钥自签发 Token），安检门通过纯数学比对无条件放行，**根本不需要呼叫市政交警系统（不需要启动 platform-api）**！

---

## 一、对立视角：简易原型 vs 生产架构（Naive vs Production）

### 20 行极简对立代码：测试可观测性与架构解耦

```python
# ==================== ❌ 耦合连体婴儿 (Naive Demo: 反模式) ====================
class NaiveAgentRunner:
    def __init__(self, platform_api_url: str):
        self.client = httpx.Client(base_url=platform_api_url)

    def run(self, thread_id: str, prompt: str):
        # 💥 致命伤 1：执行层强依赖控制面在线，单测离线直接崩溃
        # 💥 致命伤 2：每次单测必须调用真实的商业大模型，测试费刷爆信用卡
        user_info = self.client.get("/iam/verify").json()
        real_key = self.client.get("/catalog/decrypt-key").json()["key"]
        llm = ChatOpenAI(api_key=real_key)
        return llm.invoke(prompt)

# ==================== ✅ 本平台微服务自治架构 (Production: 本平台实现) ====================
class AutonomousAgentRunner:
    def resolve_model(self, config: RunnableConfig) -> BaseChatModel:
        # 优势 1：开辟可控测试注入通道，优先使用注入的确定性 Mock 模型
        injected = config.get("configurable", {}).get("_runtime_model")
        if injected is not None:
            return injected
        # 优势 2：生产模式下严格走解密连接通道
        return self._build_production_model(config)

    def run(self, config: RunnableConfig, prompt: str):
        llm = self.resolve_model(config)
        return llm.invoke(prompt)
```

---

## 二、真实工程三层解耦测试架构（Real Engineering Architecture）

`apps/runtime-service` 构筑了一套由浅入深的**三层自洽测试体系**，彻底实现了对上层控制面的零依赖：

```
                    ┌────────────────────────────────────────────────────────┐
                    │  Layer 3: 独立调试层 (Standalone Demo CLI Mode)        │
                    │  - langgraph.demo.json / 环境变量直连本地大模型         │
                    └────────────────────────────────────────────────────────┘
                                               ▲
                                               │
                    ┌────────────────────────────────────────────────────────┐
                    │  Layer 2: HTTP 接口集成层 (Self-Signed Integration)    │
                    │  - monkeypatch 注入 SECRET / 本地 _make_token() 签名   │
                    └────────────────────────────────────────────────────────┘
                                               ▲
                                               │
                    ┌────────────────────────────────────────────────────────┐
                    │  Layer 1: 纯图与状态机单元测试 (Pure Unit Test Level)    │
                    │  - configurable._runtime_model 注入 FakeChatModel      │
                    └────────────────────────────────────────────────────────┘
```

---

### 层级一：图与状态机纯本地单测（Unit Test Level）

- **适用场景**：验证 LangGraph 节点转移、多轮对话分支、工具参数捕获与系统 Prompt 组装。
- **源码实证**：
  - [`apps/runtime-service/src/runtime_service/services/reference_agent/agent.py`](../../../../apps/runtime-service/src/runtime_service/services/reference_agent/agent.py#L75-L115)
  - [`apps/runtime-service/tests/support.py`](../../../../apps/runtime-service/tests/support.py)
  - [`apps/runtime-service/tests/test_r0_baseline.py`](../../../../apps/runtime-service/tests/test_r0_baseline.py#L222-L250)

#### 1. 注入机制与 Fake 模型定义
在 [`tests/support.py`](../../../../apps/runtime-service/tests/support.py) 中，平台提供了专用的轻量级测试模型：
```python
class BindableFakeChatModel(FakeListChatModel):
    """支持工具绑定的确定性测试模型，模拟大模型输出而不发起任何外部网络请求"""
    def bind_tools(self, tools: Sequence[BaseTool | dict[str, object] | object], **kwargs) -> Runnable:
        return self
```

#### 2. 在测试用例中毫秒级执行
```python
def test_reference_agent_uses_deterministic_fake_model() -> None:
    # 直接构建带 _runtime_model 的配置字典
    fake_model = BindableFakeChatModel(responses=["reference agent response"])
    config = {
        "configurable": {
            "_runtime_model": fake_model
        }
    }
    # 初始化图并运行
    graph = asyncio.run(get_reference_agent(config))
    result = asyncio.run(
        graph.ainvoke(
            {"messages": [{"role": "user", "content": "ping"}]},
            context=RuntimeContext(),
        )
    )
    assert result["messages"][-1].content == "reference agent response"
```
**特征**：
- 零外部进程依赖；
- 单个测试耗时通常低于 **5 毫秒**；
- 绝不消耗大模型 API 账单。

---

### 层级二：HTTP 接口集成测试（Self-Signed Integration Level）

- **适用场景**：测试 `runtime-service` 的 FastAPI 端点（文件树 `/workspace/tree`、沙箱执行 `/terminals`、中断恢复、流式推送），以及 `@auth.authenticate` 鉴权中间件。
- **源码实证**：
  - [`apps/runtime-service/tests/test_workspace_http.py`](../../../../apps/runtime-service/tests/test_workspace_http.py#L14-L60)
  - [`apps/runtime-service/tests/test_image_http.py`](../../../../apps/runtime-service/tests/test_image_http.py#L26-L60)

#### 1. PEP 纯数学验签的威力
`runtime-service` 作为策略执行点（PEP），根本不维护用户数据库，它只依赖环境变量中的几个非对称/对称密钥配置：
```python
# runtime_service/auth/platform.py
verified = verify_delegation_claims(
    token,
    secret=_setting("PLATFORM_RUNTIME_DELEGATION_SECRET"),
    issuer=_setting("PLATFORM_RUNTIME_DELEGATION_ISSUER"),
    audience=_setting("PLATFORM_RUNTIME_DELEGATION_AUDIENCE"),
)
```

#### 2. 测试中如何实现“自给自足”的闭环？
测试套件利用 `pytest` 的 `monkeypatch` 在当前测试进程中注入一套已知的测试密钥，并在测试辅助模块中提供本地小票签发函数：

```python
SECRET = "r1-test-secret-with-at-least-32-bytes"

def _make_token(*, tenant_id="tenant-a", project_id="project-a", operation="workspace-file-read"):
    now = int(time.time())
    claims = {
        "type": "runtime_delegation",
        "delegation_version": 2,
        "sub": "user-a",
        "tenant_id": tenant_id,
        "project_id": project_id,
        "role": "developer",
        "permissions": ["runtime.tool.read"],
        "scope": {"assistant_id": "dearflow_agent", "operation": operation},
        "iat": now,
        "exp": now + 60,
        "iss": "runtime-test",
        "aud": "runtime-service",
        "context_hash": runtime_context_hash(None),
    }
    return jwt.encode(claims, SECRET, algorithm="HS256")
```

测试发起请求：
```python
def test_signed_workspace_http(monkeypatch):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    headers = {"Authorization": f"Bearer {_make_token(operation='workspace-file-read')}"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/internal/threads/th-1/workspace/tree", headers=headers)
        assert res.status_code == 200
```
**整个测试期间，`platform-api` 服务连一个字节的进程都不需要启动！**

---

### 层级三：算法独立交互与本地调试（Standalone Demo Level）

- **适用场景**：算法工程师独立调试 Prompt、观察 LangGraph 状态图的分支跳跃，或使用 LangGraph Studio 页面直连调试。
- **源码实证**：
  - `langgraph.demo.json`
  - [`apps/runtime-service/src/runtime_service/services/reference_agent/README.md`](../../../../apps/runtime-service/src/runtime_service/services/reference_agent/README.md)
- **运行机制**：
  在单机开发时，算法同学只需在 `.env` 中提供开发用的大模型 Key（如 `DEEPSEEK_PROXY_API_KEY` 或 `OPENAI_API_KEY`），通过：
  ```bash
  rtk langgraph dev --config langgraph.demo.json
  ```
  即可启动一个包含完整图形可视化界面的单机服务，支持在浏览器中即时输入 Prompt 进行交互调试，彻底从臃肿的微服务全家桶中解放出来！

---

## 三、老王灵魂拷问与工业级避坑指南（Engineering Reality）

### ❓ 灵魂拷问 1：你在 `configurable` 里留了个 `_runtime_model` 接口，生产环境攻击者不会偷偷塞个假模型绕过审计吗？

> **老王怒喷**：艹！老王我像是那么马虎的人吗？
> 看代码：[`runtime/resolver.py` Line 43-79](../../../../apps/runtime-service/src/runtime_service/runtime/resolver.py#L43-L79)：
> 1. **网关入口击毙**：入口处的 `reject_untrusted_configurable` 拥有最严格的白名单清洗，客户端敢塞任何带下划线或私有前缀的字段，直接当场 `400 Bad Request` 击毙！
> 2. **构图完毕立即拔除**：在 Agent 图初始化完成后，代码立即执行：
>    ```python
>    bound_configurable.pop("_runtime_model", None)
>    ```
>    把测试插桩直接从配置字典中抹除！进入图执行状态机后，内存里根本没有这个键，黑客想利用都没地方下嘴！

---

### ❓ 灵魂拷问 2：为什么测试自签 Token 必须老老实实算一遍 JWT，能不能直接在代码里写个 `if env == 'test': return True` 跳过鉴权？

> **老王答疑**：
> 绝不容许在业务代码里写任何 `skip_auth` 的逻辑！
> 1. **严防代码腐烂逃逸**：历史上无数重大安全事故，都是因为程序员写了 `if DEBUG: pass`，结果运维上线时某个配置配错，导致生产环境全局免鉴权裸奔；
> 2. **测试保真度（Test Fidelity）**：集成测试的目的就是验证“包括验签、过期时间校验、租户 ID 提取、操作矩阵权限拦截在内的全链路”。如果把鉴权跳过了，你测出来的 200 OK 根本无法证明生产环境能跑通。
> 本平台通过“本地注入测试 SECRET + 自签标配 Token”，既保持了零依赖，又保证了生产鉴权代码 100% 被真实执行测试！

---

## 四、架构不变量清单（Architectural Invariants）

1. **执行层离线完全自治不变量**：`runtime-service` 的所有核心计算、图状态机、工具执行与单元测试，严禁对 `platform-api` 产生强在线依赖；拔掉微服务网络连接，底层图单测必须 100% 能够独立通过。
2. **测试插桩生产绝对隔离不变量**：用于单元测试依赖注入的内部标记（如 `_runtime_model`），在跨越生产网关边界时必须被物理清洗与剔除，严禁任何生产流量激活测试旁路。
3. **安全中间件零旁路穿透不变量**：集成测试验证 HTTP 接口时，必须通过合法签名的本地自签令牌走完完整的鉴权适配器（`auth/platform.py`），严禁在服务端代码中引入任何绕过鉴权的全局 Debug 开关。
