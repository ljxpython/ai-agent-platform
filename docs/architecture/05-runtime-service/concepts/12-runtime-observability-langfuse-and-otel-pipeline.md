# 运行时可观测性架构、Langfuse 与 OTel 追踪管线深度剖析 (Runtime Observability, Langfuse & OpenTelemetry Pipeline)

> **老王暴躁技术流寄语**：
> “很多搞 AI Agent 的菜鸟团队，往往在可观测性上栽大跟头：要么在代码里到处裸写 `print` 打印日志，线上出了 Bug 抓瞎两眼一抹黑；要么是直接把第三方 APM 的 SDK 往代码里一塞了事，结果监控平台网络一抖、限流或者配错 Key，直接抛出未捕获异常把正在跑图的 Agent 全盘搞崩！
> 操，监控是拿来保命的，不是拿来要命的！可观测性是业务的辅助手段，绝不能反客为主把业务主航道搞死！
> `apps/runtime-service/src/runtime_service/observability` 模块给全行业树立了一个教科书级的标杆：**用最严苛的消杀对待外部元数据，用最温柔的软着陆对待业务链路。** 哪怕监控服务被打到死机，底座的图计算也绝不陪葬！”

---

## 一、30秒速通全景：可观测性模块核心机制速查表

`apps/runtime-service/src/runtime_service/observability/` 复用 Langfuse 与可选 OTel，并补充有界错误诊断、构图计时与只读查询。2026-10-06 批准的实现及验证见 [专项](../../../projects/20261006-agent-observability-hardening/README.md)：
```
observability/
├── __init__.py      # 统一暴露门面符号
├── langfuse.py      # Langfuse 软着陆适配器、数据脱敏、元数据白名单注入与本地轻量诊断
├── otel.py          # 可选 OTLP 根图/启动阶段 span 与故障隔离
├── errors.py        # 模型边界有限分类，不输出异常正文
├── diagnostics.py   # 安全 JSON 日志、受信关联字段及确定性 trace ID
├── startup.py       # 构图局部阶段 collector，不缓存 Thread
└── query.py         # 官方异步 observations 查询，白名单 DTO
```

| 核心机制 | 核心代码 / 类 | 物理职责 (大白话) | 解决的生产致命痛点 |
| :--- | :--- | :--- | :--- |
| **一、软着陆动态代理 (Fail-Soft)** | `_FailSoftCallback`<br>`_RecordingExporter` | 利用动态代理包装原生 SDK 回调，将所有 `on_*` 方法产生的 401、429、500 或超时异常全部在内部消化并打点，绝不向外冒泡。 | 彻底杜绝监控平台网络抖动、限流或后端故障导致大模型长耗时推理任务被异常中断。 |
| **二、零信任元数据消杀 (Zero-Trust)** | `_redact()`<br>`_mask()`<br>`_approved_metadata()`<br>`_trusted_metadata()` | 强行清洗敏感字段（API Key/Cookie/Token），截断长字符串；将调用方传入的外部身份强行用服务端验签小票覆盖；抹除回调大段 Payload 防 Prompt 泄密。 | 杜绝调用方伪造 `user_id` 篡改监控审计轨迹；防止商业机密与系统 API Key 在监控控制台明文裸奔。 |
| **三、本地离线诊断** | `_RuntimeDiagnosticsCallback`、`log_diagnostic` | 正式组合根即使关闭远程导出仍装本地回调；捕获 Token计数、graph退出、耗时与工具异常类型，模型尝试由 middleware 独立记录。 | 不依赖外部观测服务即可保留已写出的诊断；不保证进程崩溃后的完整记录。 |
| **四、可选 OTel** | `OTelDiagnosticsCallback`<br>`initialize_otel()` | 配置OTLP后建立 runtime.execution/startup/graph；platform_trace_id仅作为关联属性，不是OTel trace ID。 | 本期没有W3C propagation，不宣称完整分布式父子trace；可按平台关联ID查日志。 |
| **五、有界优雅排空 (Bounded Flush)** | `close_langfuse()`<br>`close_otel()` | 服务停机时在后台守护线程触发缓冲区 Flush，设置严格的 5 秒超时保护，超时果断撤退。 | 杜绝 K8s 节点滚动更新或进程退出时，由于网络挂起导致进程永久僵死，最终被 K8s 超时强杀。 |

---

## 二、架构全景大动脉：数据怎么脱敏，Trace 怎么流转？

在生产环境下，从上层请求打入、Agent 图组装，到数据脱敏上报，整体架构流转拓扑如下：

```
+─────────────────────────────────────────────────────────────────────────────────────────────+
|                                    Platform-API 控制面网关                                   |
|   携带事实小票 facts: { tenant_id, project_id, user_id, platform_trace_id, model_id... }     |
+─────────────────────────────────────────────────────────────────────────────────────────────+
                                               │
                                               ▼
+─────────────────────────────────────────────────────────────────────────────────────────────+
|                         apps/runtime-service: Agent 组合根组装                               |
|                     (如 services/dearflow_agent/agent.py: get_agent)                         |
|                                                                                             |
|   1. 提取可信元数据 (trusted_metadata: 提示词版本、策略哈希、技能哈希、执行模式)                |
|   2. 调用 with_langfuse_tracing(agent, bound_config, graph_id, trusted_metadata)             |
+─────────────────────────────────────────────────────────────────────────────────────────────+
                                               │
                                               ▼
+─────────────────────────────────────────────────────────────────────────────────────────────+
|                             observability/langfuse.py 核心装配层                            |
|                                                                                             |
|   [身份白名单校验]                                                                            |
|   - 丢弃未授权字段，强制用 trusted_metadata 覆盖调用方的 user_id / request_id               |
|                                                                                             |
|   [安全脱敏管线]                                                                              |
|   - _SENSITIVE_KEYS: 遇到 authorization/token/api_key/secret 统统变为 [REDACTED]            |
|   - _mask(): 将回调层大段输入输出消杀为 [REDACTED]，只留结构化度量指标                        |
|                                                                                             |
|   [回调三剑客注入 bound["callbacks"]]                                                         |
|   ├── 1. _FailSoftCallback(LangfuseCallbackHandler) ──> 软着陆代理，吞掉所有 SDK 内部异常     |
|   ├── 2. OTelDiagnosticsCallback ────────────────────> 可选 execution/startup/graph Span      |
|   └── 3. _RuntimeDiagnosticsCallback ─────────────────> 本地度量：Token计数/耗时/工具异常   |
+─────────────────────────────────────────────────────────────────────────────────────────────+
         │                                       │                                  │
         │ (异步上报)                             │ (OTLP 协议)                       │ (标准日志)
         ▼                                       ▼                                  ▼
+──────────────────+                   +──────────────────+               +──────────────────+
|  Langfuse 服务端 |                   | OpenTelemetry 收集|               | 本地 stdout 输出  |
|  - Trace 树状调用 |                   | - 全链路分布式 Span|               | - runtime_run_   |
|  - Token 消耗大盘 |                   | - 端到端时延分布  |               |   completed JSON |
+──────────────────+                   +──────────────────+               +──────────────────+
```

---

## 三、四大工业级设计哲学源码硬核解密

### 1. 软着陆代理（Fail-Soft Decorator）：绝不让 APM 反客为主搞挂业务！

很多初学者直接在代码里引入第三方 SDK 的 `CallbackHandler`。一旦监控服务器发生宕机、网络波动抖动或者鉴权过期，原生 SDK 抛出的异常会直接在 LangGraph 调度循环里炸开，导致用户长达 3 分钟的深度分析任务瞬崩！

`observability/langfuse.py` 运用 Python 元编程动态代理彻底杜绝了此类隐患：

```python
# 对应 apps/runtime-service/src/runtime_service/observability/langfuse.py 第 103 行
class _FailSoftCallback(BaseCallbackHandler):
    """Keep SDK callback failures outside the Agent result path."""

    def __init__(self, delegate: BaseCallbackHandler) -> None:
        self._delegate = delegate
        self.raise_error = False

    def __getattribute__(self, name: str) -> Any:
        # 拦截所有 on_* 回调方法 (on_llm_start, on_tool_end, on_chain_error 等)
        if name.startswith("on_"):
            delegate = object.__getattribute__(self, "_delegate")
            method = getattr(delegate, name)

            def call(*args: Any, **kwargs: Any) -> Any:
                try:
                    result = method(*args, **kwargs)
                except Exception as error:  # 核心保命机制：捕获吞掉全部异常，绝不向外抛出！
                    _record_export_error(error)
                    return None
                if not inspect.isawaitable(result):
                    return result

                async def wait() -> Any:
                    try:
                        return await result
                    except Exception as error:
                        _record_export_error(error)
                        return None
                return wait()
            return call
        return super().__getattribute__(name)
```
- **老王点评**：
  “看到这个 `__getattribute__` 没有？利用 Python 动态反射把原生 SDK 的每一个回调方法都穿上一层‘防弹服’！无论是同步还是异步方法，底层只要报 401 Unauthorized、429 限流、还是网络超时，通通被 `_record_export_error` 记录到内部的内存 Counter 中（`_metrics["export_error"] += 1`），Agent 核心计算图连眼皮都不眨一下继续往前跑！这才是生产级高可用代码的标杆设计！”

---

### 2. 零信任消杀与元数据白名单分层（Zero-Trust Metadata & Redaction）

外部请求打到 Agent 底座，客户端可能在 Config 里随手塞入敏感数据，或者攻击者恶意伪造字段企图污染审计轨迹。底座设立了严格的白名单和敏感词粉碎机制：

```python
# 对应 apps/runtime-service/src/runtime_service/observability/langfuse.py 第 27-70 行
_CALLER_METADATA = frozenset({
    "run_id", "thread_id", "assistant_id", "assistant_version", "deployment_version"
})

_TRUSTED_METADATA = frozenset({
    "tenant_id", "project_id", "user_id", "model_id", "config_hash",
    "prompt_version", "prompt_hash", "policy_version", "policy_hash",
    "skills_hash", "execution_mode", "effective_reasoning", "request_id", "platform_trace_id"
})

_SENSITIVE_KEYS = frozenset({
    "authorization", "cookie", "set-cookie", "token", "access_token",
    "api_key", "x-api-key", "secret", "client_secret", "password"
})
```

- **严格白名单过滤**：外部调用方传进来的 Metadata 只有在 `_CALLER_METADATA` 集合中的键才被允许保留；
- **权威小票覆盖（防伪造身份）**：调用方如果在请求中伪造了 `user_id="super_admin"`，在 `with_langfuse_tracing()` 中会被网关验签得到的 `trusted_metadata` 强行覆盖，绝无篡改可能；
- **敏感词粉碎消杀**：任何键名包含敏感词，或者字符串长度超过 256 字符的，统统就地替换为 `[REDACTED]`；
- **Prompt 数据保护 (`_mask`)**：默认抹除回调 payload 中的原始大文本，防止用户的商业私密数据和敏感上下文无脑落入第三方平台。

---

### 3. 本地常驻离线诊断器（_RuntimeDiagnosticsCallback）

很多平台一旦关了外部 APM，本地就变成瞎子。底座在 `with_langfuse_tracing()` 中，无论是否开启远程 Langfuse，都会装配一个纯本地的轻量诊断器：

```python
# 对应 observability/langfuse.py（省略部分指标与兼容日志）
class _RuntimeDiagnosticsCallback(BaseCallbackHandler):
    """Bounded Run/Tool diagnostics independent of Langfuse export."""

    def on_llm_end(self, response: Any, *, run_id: Any, **_: Any) -> None:
        usage = getattr(response, "llm_output", None) or {}
        token_usage = usage.get("token_usage", {}) if isinstance(usage, Mapping) else {}
        total = token_usage.get("total_tokens")
        if isinstance(total, int) and total >= 0:
            _metrics["token_total"] += total

    def _finish(self, run_id: Any, status: str) -> None:
        started = self._starts.pop(run_id, None)
        duration_ms = (
            round((time.monotonic() - started) * 1000, 2)
            if started is not None else None
        )
        _metrics[f"run_{status}"] += 1
        log_diagnostic(
            "runtime.graph.completed",
            {
                "graph_id": self._graph_id,
                **self._metadata,
                "callback_run_id": str(run_id),
                "outcome": status,
                "duration_ms": duration_ms,
            },
        )
```
- `get_observability_metrics()` 可断言 `run_success`、`token_total` 与 `tool_error`，具体耗时取决于图和环境，不承诺固定0.05秒。
- `ModelErrorMiddleware` 位于 fallback/retry 内侧、timeout 外侧，记录每次失败后重新抛出同一异常。恢复后Run仍可success；取消/HITL不算provider失败。
- 本地诊断只保存类型、稳定码、有限namespace/ID和duration；原始message/body/stack/header不得进入新诊断日志或安全OTel/Langfuse事件。
- Langfuse diagnostic event 在创建前通过公开 `propagate_attributes(session_id=...)` 绑定session；tenant/project/native Run派生trace ID，与graph回调共用显式trace_context。关掉导出时页面无法从stdout回查，本期无诊断数据库。

---

### 4. 停机优雅排空与防死锁（Bounded Graceful Flush）

服务在执行优雅下线时，若直接退出会导致缓冲区指标丢失；若无脑阻塞等待，一旦网络不可达会导致整个进程卡死无法被操作系统回收。

```python
# 对应 apps/runtime-service/src/runtime_service/observability/langfuse.py 第 418 行
def close_langfuse(*, timeout_seconds: float = 5.0) -> None:
    """Flush the process client with a bounded best-effort shutdown."""
    global _client
    client = _client
    if client is not None:
        done = threading.Event()

        def flush() -> None:
            try:
                client.flush()
            except Exception:
                logger.exception("runtime_langfuse_flush_error")
            finally:
                done.set()

        threading.Thread(target=flush, daemon=True).start()
        # 严格限制最多等待 5.0 秒，超时果断撤退！
        if not done.wait(timeout_seconds):
            _metrics["flush_timeout"] += 1
            logger.warning("runtime_langfuse_flush_timeout")
        _client = None

    close_otel(timeout_seconds=timeout_seconds)
```
- **核心价值**：后台独立线程刷盘 + 5.0 秒硬性超时看门狗，兼顾“最大努力送达指标”与“杜绝停机死锁”。

---

## 四、生产实际应用全景链路

### 1. 业务 Agent 组合根无侵入接入范式

在智能体装配阶段（如旗舰智能体 `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py`），通过标准钩子一行挂载：

```python
# dearflow_agent/agent.py 第 401 行
return with_langfuse_tracing(
    agent,
    bound,
    graph_id="dearflow_agent",
    trusted_metadata={
        "user_id": facts.principal.user_id,
        "tenant_id": facts.principal.tenant_id,
        "project_id": facts.principal.project_id,
        "model_id": resolved.model_id,
        "config_hash": resolved.config_hash,
        "prompt_version": resolved.prompt_version,
        "prompt_hash": resolved.prompt_hash,
        "policy_hash": hashlib.sha256(json.dumps(asdict(facts.policy), sort_keys=True).encode()).hexdigest(),
        "request_id": facts.request_id,
        "platform_trace_id": facts.platform_trace_id,
        "execution_mode": mode.name,
        "effective_reasoning": reasoning,
        "skills_hash": skills_hash(),
    },
)
```

#### 在 Langfuse 控制台上的真实呈现：
- **Trace Name**：`dearflow_agent`（精准识别 Agent 类型）；
- **Session ID**：当前对话的 `thread_id`（同一会话的多轮问答自动汇聚于同一 Session）；
- **User ID**：真实租户下的操作者唯一标识；
- **Tags**：`["runtime-service", "dearflow_agent"]`；
- **Metadata**：打上模型版本、提示词哈希（`prompt_hash`）、安全策略哈希（`policy_hash`）以及激活技能集哈希（`skills_hash`）。哪天模型出现异常输出，凭借这套数字指纹能 100% 还原当时的装配现场！

### 2. Web 控制面 Lifespan 统一接管

在 `apps/runtime-service/src/runtime_service/webapp.py` 中，可观测性与服务生命周期绑定：

```python
# webapp.py
# 生命周期片段，完整代码以 webapp.py 为准
initialize_langfuse()
async with diagnostics_client_lifespan():
    yield
# 原有 finally 继续关闭 terminals 和观测客户端
close_langfuse(timeout_seconds=5.0)
```

---

## 五、切斯特顿栅栏：Naive vs Production 架构攻防对比

| 场景 / 攻击面 | Naive 粗暴做法 (玩具设计) | Production 生产做法 (`observability/` 严苛体系) | 栅栏背后的血泪教训 (为什么必须这么做) |
| :--- | :--- | :--- | :--- |
| **监控平台网络抖动** | 直接使用第三方 SDK 原生回调 | `_FailSoftCallback` 动态代理吞噬异常，计入内部指标 | 外部网络一旦 502/429/超时，原生 SDK 抛错会导致正在跑图的长任务直接崩塌！ |
| **调用方伪造身份** | 直接透传请求入参中的 `user_id` | 强制使用 HMAC 验签提取的 `trusted_metadata` 强行覆盖 | 攻击者可在请求体伪造超管身份，篡改审计日志，造成严重的安全合规漏洞！ |
| **敏感凭证防泄露** | 回调原样上传全部 State 与参数 | `_SENSITIVE_KEYS` 严格过滤 + `_mask` 抹除裸文本 | 用户的私密 Token、大模型 API Key 容易随监控数据泄露给第三方 APM 服务商！ |
| **停机退出流程** | 进程退出直接退出或无限同步 `flush()` | 守护线程异步刷盘 + 5.0 秒硬性超时看门狗 | 无限阻塞会导致 K8s 判定 Pod 优雅停机超时直接强杀，甚至引发级联停机阻塞！ |
| **离线/单测环境** | 必须启动远程 Langfuse 容器才能跑通 | 关闭导出仍绑定本地诊断，不作业务网络调用；有实际装配和日志成本 | 本地单测可以独立验证，增量成本按专项A/B实测。 |

---

## 六、老王架构不变量与避坑清单

1. **软着陆铁律不变量**：可观测性模块发生的任何异常（网络失败、配置错误、反序列化异常），绝对禁止向外抛出中断 Agent 主业务执行流程。
2. **元数据覆盖不变量**：调用方传入的外部元数据只允许读取白名单字段，核心租户、用户与追踪指纹必须由 `trusted_metadata` 权威小票强行覆盖。
3. **单例与无死锁不变量**：进程内只允许维持一个 Langfuse 客户端与 OTel Provider 单例；退出排空必须受到最大 5 秒超时的严格钳制。
4. **离线自治不变量**：在 `LANGFUSE_ENABLED != true` 且OTLP未配置时，诊断不调用外部观测网络；本地计时与日志仍执行，不承诺零成本。

## 七、构图与安全查询

四个正式graph在真实context/model/MCP/workspace/compile代码块记录阶段。UTC时间用于展示、monotonic用于duration；collector每次构图独立，最多16阶段，schema探测直接跳过。factory失败也可记录startup；授权前失败没有可信Run身份时只能保留安全本地事件，不能伪造跨服务归属。

平台新增 `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/diagnostics`。项目/Thread授权及原生Run归属校验后，以Thread绑定的diagnostics-read调用Runtime；Runtime再回查当前ACL/credential，用官方observations v2读取metadata，100 observations/50 traces/2秒总预算。未知字段不公开，外链URL固定null，不新增表或回写Thread。

响应 `run_status` 来自原生Run，模型错误是尝试观察，不能据最后一次429推断最终失败。Langfuse最终一致，返回available/partial/disabled/unavailable；观测故障不改变Run。查询request_id与原执行request_id分开，前端实现和浏览器验收由同事按 [交接](../../../projects/20261006-agent-observability-hardening/frontend-handoff.md) 接续。
