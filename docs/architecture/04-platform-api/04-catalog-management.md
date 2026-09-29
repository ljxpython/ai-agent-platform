# 04-智能体资产目录生命周期管理 (Agent & Runtime Catalog Lifecycle Management)

## 模块定位与核心价值

在 `ai-agent-platform` 中，智能体并非单一孤立的提示词脚本，而是由**模型（Models）、图（Graphs）、工具（Tools）、技能（Skills）与助手定义（Assistants/Agents）**深度协同组装而成的复合资产系统。

`modules/runtime_catalog` 与 `modules/agents` 是这一资产体系的“中央军械库”：
1. **资产全景纳管**：统一抽象并索引平台所有可用的执行图（Graph）、预置工具（Tools）、自定义技能（Skills）与底层大模型接入点（Models）。
2. **跨服务能力自动同步（Capability Discovery & Sync）**：当底层 `runtime-service` 注册了新的 LangGraph 流程或 MCP 插件工具时，目录服务能通过主动刷新（Refresh）机制自动发现并向平台数据库对齐元数据状态。
3. **凭据零泄露模型治理**：模型接入点（Model Catalog）支持平台级共享与项目级自定义，明文 API Key 经 Fernet 加密存储，对外部 API 永远只暴露掩码后的布尔标记（`credential_configured: bool`），仅在受限的运行时内部按需一次性解密下发。
4. **运行时动态装配绑定**：根据项目选用的 Assistant 版本，动态关联其底层 Graph 拓扑、默认提示词、可用模型集合与工具限制清单，拼装出最终的运行时装配蓝图。

---

## 零、知识前置与上下文串联（Knowledge Bridges）

### 1. 认知输入（前置模块输入）
- 依赖 [01-architecture.md](01-architecture.md)：使用 `session_scope()` 实现资产元数据的读写事务管理。
- 依赖 [02-runtime-gateway.md](02-runtime-gateway.md)：网关在启动 Run 前，需通过 Catalog 校验客户端传入的 `assistant_id` 与目标底层 Graph 是否合法。
- 依赖 [03-iam-and-governance.md](03-iam-and-governance.md)：利用 Fernet 工具包进行凭据加解密，并结合策略引擎对资产进行项目级过滤。

### 2. 本章核心流转
- **能力拉取与注册**：调用适配器从 `runtime-service` 查询 `/info` 与内部 capabilities 端点，同步图和工具元数据至 `runtime_tool_catalog` 与 `runtime_graph_catalog` 表。
- **模型凭据入库**：管理接口接收新建模型请求，使用主密钥加密明文 API Key 后落盘，抹除内存中的敏感字符串。
- **受控按需解密**：下游 `runtime-service` 真正发起推理前，携带合法 Delegation Token 调用内部端点 `/api/runtime/internal/model-config`，目录服务动态解密并返回连接元数据。

### 3. 认知输出（支撑后续模块）
- 为底层 `runtime-service`（后续专题）提供模型连接池配置、动态 Prompt 注入与图拓扑参数的校验依据。

---

## 一、对立视角：简易原型 vs 生产架构（Naive vs Production）

| 维度 | 简易原型方案 (Naive) | 本平台资产目录架构 (Production Architecture) | 选型与演进考量 |
| :--- | :--- | :--- | :--- |
| **资产发现** | 资产信息全部写死在配置 yaml 或前端代码里，运行时加了个新工具，前端必须发版更新。 | 动态发现与同步机制（Refresh Workflow），从 `runtime-service` 自动抓取最新的图和工具元数据并入库更新。 | 运行时与控制面解耦，底座图结构升级或热插拔新工具时，控制面一键刷新即可感知。 |
| **模型 API Key 存储** | 数据库明文存储；查询详情接口直接返回包含 API Key 的完整 JSON。 | 敏感凭证入库即加密，对前端及所有外部接口永远隐藏明文，仅输出 `credential_configured: bool`。 | 杜绝 API 报文窃听或前端状态泄露导致企业大模型商业凭证失窃，满足金融级安全合规。 |
| **模型凭据提供机制** | 用户发起对话时把 Key 放到上下文里传给后端，或后端全部走同一个共享的官方全局 Key。 | 细粒度 BYOK 与项目级隔离：各项目可覆盖独立 Key；推理时由运行时凭借单次 Delegation 凭据拉取解密配置。 | 实现成本核算清晰（各部门自付费用），同时防止单点凭证被滥用耗尽配额。 |
| **Agent 版本化管理** | 修改提示词或模型配置直接原地覆盖 `UPDATE` 数据库记录，无法回滚。 | 独立维护 Assistant 实体、草稿与发布版本，提供历史版本快照追溯与语义化版本绑定。 | 提示词微调可能导致智能体行为严重劣化，版本化支撑灰度发布与一键平滑回滚。 |

---

## 二、源码精准坐标映射（Code Pointer Map）

### 1. 资产领域模型与契约
- [modules/runtime_catalog/domain/models.py](../../../apps/platform-api/src/platform_api/modules/runtime_catalog/domain/models.py)：
  - `RuntimeModelCatalogItem`：模型目录查询实体（隐藏 Key，仅暴露 `credential_configured`）。
  - `RuntimeModelCreate` / `RuntimeModelUpdate`：模型创建与变更请求实体。
  - `RuntimeToolCatalogItem` 与 `RuntimeGraphCatalogItem`：工具与图元数据实体。
- [modules/runtime_catalog/application/credentials.py](../../../apps/platform-api/src/platform_api/modules/runtime_catalog/application/credentials.py)：
  - `encrypt_api_key()` 与 `decrypt_api_key()`：使用 `model_config_master_key` 的 Fernet 对称加密。

### 2. 目录应用服务与仓储
- [modules/runtime_catalog/application/service.py](../../../apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py)：
  - `RuntimeCatalogService`：处理模型增删改查、能力同步刷新、内部解密凭据签发。
- [modules/runtime_catalog/infra/sqlalchemy/repository.py](../../../apps/platform-api/src/platform_api/modules/runtime_catalog/infra/sqlalchemy/repository.py)：
  - `SqlAlchemyRuntimeCatalogRepository`：资产元数据持久化读写仓储。

### 3. 智能体与助手模块
- [modules/agents/presentation/](../../../apps/platform-api/src/platform_api/modules/agents/presentation)：智能体助手 CRUD 路由。
- [modules/agents/application/service.py](../../../apps/platform-api/src/platform_api/modules/agents/application/service.py)：助手业务逻辑、Graph 关联校验与发布控制。

---

## 三、真实数据结构与报文（Real Payloads & DB Schemas）

### 1. 模型目录返回报文（明文 Key 剥离）
外部查询接口获取的模型信息，API Key 已被彻底脱敏，仅保留配置状态指示：

```json
{
  "id": "model-claude-3-5-sonnet",
  "display_name": "Claude 3.5 Sonnet (Production)",
  "provider": "anthropic",
  "base_url": "https://api.anthropic.com/v1",
  "protocol": "anthropic",
  "model": "claude-3-5-sonnet-20241022",
  "enabled": true,
  "credential_configured": true,
  "scope_type": "project",
  "project_id": "proj-90f1ac23-4567"
}
```

### 2. 内部模型解密解析报文（供运行时引擎拉取）
当且仅当下游 `runtime-service` 携带合法 Delegation Token 请求内部安全端点 `/api/runtime/internal/model-config` 时，网关才会在内存中即时解密并返回真实配置：

```json
{
  "model_id": "model-claude-3-5-sonnet",
  "provider": "anthropic",
  "base_url": "https://api.anthropic.com/v1",
  "protocol": "anthropic",
  "model": "claude-3-5-sonnet-20241022",
  "api_key": "sk-ant-api03-xxxx-real-secret-key-xxxx",
  "temperature_default": 0.2,
  "max_tokens_default": 8192
}
```

---

## 四、端到端函数级调用时序（Function-Level Trace）

整个智能体资产目录的生命周期流转，包含**“资产录入与加密”**与**“执行期受控拉取”**两大阶段：

```mermaid
sequenceDiagram
    autonumber
    participant Admin as 平台/项目管理员
    participant CatalogAPI as RuntimeCatalogPresentation
    participant CatalogSvc as RuntimeCatalogService
    participant Fernet as credentials.py (Fernet)
    participant Repo as SqlAlchemyRuntimeCatalogRepository
    participant DB as Platform DB
    participant Runtime as runtime-service

    Note over Admin,DB: 阶段一：模型创建与凭据加密落盘
    Admin->>CatalogAPI: POST /api/runtime-catalog/models (携带明文 api_key)
    CatalogAPI->>CatalogSvc: create_model(command)
    CatalogSvc->>Fernet: encrypt_api_key(plain_key, master_key)
    Fernet-->>CatalogSvc: 返回密文 (gAAAAABl...)
    CatalogSvc->>Repo: save_model(record, ciphertext)
    Repo->>DB: INSERT INTO runtime_model_catalog VALUES (...)
    DB-->>Repo: 成功
    CatalogSvc-->>CatalogAPI: 返回 RuntimeModelCatalogItem (credential_configured=True)
    CatalogAPI-->>Admin: 201 Created (响应体绝无 api_key 字段)

    Note over DB,Runtime: 阶段二：运行时推理前受控按需解密
    Runtime->>CatalogAPI: GET /api/runtime/internal/model-config (带 Delegation Token)
    CatalogAPI->>CatalogAPI: 验证 Delegation JWT 签名与授权操作
    CatalogAPI->>CatalogSvc: get_internal_model_config(model_id, project_id)
    CatalogSvc->>Repo: get_model_record(model_id)
    Repo->>DB: SELECT * FROM runtime_model_catalog WHERE id = ...
    DB-->>Repo: 返回密文记录
    CatalogSvc->>Fernet: decrypt_api_key(ciphertext, master_key)
    Fernet-->>CatalogSvc: 还原真实明文 API Key
    CatalogSvc-->>CatalogAPI: 组装 InternalModelConfig
    CatalogAPI-->>Runtime: 200 OK (下发解密配置供瞬时推理使用)
```

---

## 五、核心实现高保真伪代码（High-Fidelity Pseudocode）

### 1. 凭据加密与敏感信息掩码（Credential Masking）
```python
# 对应 apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py

def create_model(self, *, actor: ActorContext, command: RuntimeModelCreate) -> RuntimeModelCatalogItem:
    # 1. 权限拦截：必须具备平台级或项目级模型写权限
    self._require_permission(actor, PermissionCode.PLATFORM_MODEL_WRITE)

    # 2. 对明文 API Key 执行对称加密
    encrypted_key = encrypt_api_key(command.api_key, master_key=self._master_key)

    with self._session_factory() as session:
        repo = SqlAlchemyRuntimeCatalogRepository(session)
        record = RuntimeModelRecord(
            id=str(uuid4()),
            display_name=command.display_name,
            provider=command.provider,
            base_url=command.base_url,
            protocol=command.protocol,
            model=command.model,
            encrypted_api_key=encrypted_key,
            enabled=command.enabled,
            scope_type=command.scope_type,
            project_id=command.project_id,
        )
        repo.save(record)

    # 3. 构造出库模型，明文 Key 绝不返回
    return RuntimeModelCatalogItem(
        id=record.id,
        display_name=record.display_name,
        provider=record.provider,
        base_url=record.base_url,
        protocol=record.protocol,
        model=record.model,
        enabled=record.enabled,
        credential_configured=bool(encrypted_key),
        scope_type=record.scope_type,
        project_id=record.project_id,
    )
```

### 2. 跨服务元数据动态刷新（Catalog Refresh Workflow）
```python
# 对应 apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py

async def refresh_catalog(self, *, actor: ActorContext) -> RuntimeCatalogRefreshResult:
    self._require_permission(actor, PermissionCode.PLATFORM_CATALOG_REFRESH)

    # 1. 从下游 runtime-service 拉取最新能力全景
    upstream_info = await self._upstream.get_info()
    upstream_graphs = upstream_info.get("graphs", [])

    synced_at = datetime.utcnow()
    updated_count = 0

    with self._session_factory() as session:
        repo = SqlAlchemyRuntimeCatalogRepository(session)

        # 2. 遍历同步所有 Graph 拓扑信息
        for graph_meta in upstream_graphs:
            graph_id = graph_meta["graph_id"]
            capabilities = await self._upstream.get_graph_capabilities(graph_id)

            repo.upsert_graph(
                graph_id=graph_id,
                display_name=graph_meta.get("name", graph_id),
                description=graph_meta.get("description", ""),
                source_type="system",
                sync_status="active",
                last_synced_at=synced_at,
            )

            # 3. 同步图内绑定的预置工具（Tools）
            for tool_meta in capabilities.get("tools", []):
                repo.upsert_tool(
                    tool_key=tool_meta["name"],
                    graph_id=graph_id,
                    name=tool_meta.get("display_name", tool_meta["name"]),
                    description=tool_meta.get("description", ""),
                    last_synced_at=synced_at,
                )
            updated_count += 1

    return RuntimeCatalogRefreshResult(ok=True, count=updated_count, last_synced_at=synced_at)
```

---

## 六、假想断电与极限场景推演（Thought Experiments）

### 场景一：平台主加密密钥（Master Key）配置丢失或错误
- **推演过程**：运维人员在重启部署 `platform-api` 时，错误配置或遗漏了环境变量 `MODEL_CONFIG_MASTER_KEY`。
- **系统表现**：当运行时向内部端点请求 `/api/runtime/internal/model-config` 进行模型配置解析时，`_fernet(master_key)` 立即识别到空密钥或非法密钥，抛出 `ModelCredentialError("model_config_master_key is not configured")`，转换为 HTTP 500 明确阻断执行，而绝不会向下游返回乱码或未经解密的密文，防止底层 HTTP 请求向 OpenAI/Claude 抛出畸形认证头。

### 场景二：底层 Runtime Service 动态删除了某个 Graph
- **推演过程**：后端研发在 `runtime-service` 中下线了一个名为 `legacy_data_analyst` 的实验性图，但数据库中仍有历史关联记录。
- **系统表现**：当运维触发 `refresh_catalog` 时，平台对比当前活跃清单与数据库全量记录，将未在最新 `/info` 中出现的图状态标记为 `sync_status="stale"`。用户再次尝试调用关联了该图的 Assistant 时，网关层前置拦截并提示“底层图已下线”，杜绝了请求抛入下游后发生未捕获的 KeyError 崩溃。

### 场景三：攻击者伪造请求试图读取内部模型配置端点
- **推演过程**：攻击者利用已泄露的普通用户账号，直接向平台内部端点 `/api/runtime/internal/model-config?model_id=xxx` 发起 GET 请求，试图窃取明文 API Key。
- **系统表现**：该端点挂载了内部认证守卫（Internal Delegation Guard），强制要求请求头包含由平台专门签发给 `runtime-service` 的专用 Delegation JWT。普通用户或 Bearer Token 无法通过签名校验，直接被拦截并返回 `401 Unauthorized`，杜绝凭证窃取风险。

---

## 七、架构不变量清单（Architectural Invariants）

1. **凭据非对称暴露原则**：对外部管理平台暴露的模型查询模型（`RuntimeModelCatalogItem`），绝对禁止包含明文 API Key 字段；对外可见的只有 `credential_configured` 布尔标记。
2. **凭据即时解密不缓存原则**：内部模型配置端点解密得到的明文 API Key，仅用于当前推理请求的内存组装，绝对禁止被二次写入任何日志文件、缓存服务（Redis）或长期持久化介质。
3. **能力发现单向对齐原则**：平台目录中的 Graph 与 Tool 实体必须以 `runtime-service` 实际暴露的能力为事实来源（Source of Truth），平台数据库只作为缓存与策略绑定媒介。
4. **失效资产软隔离原则**：当下游图下线或工具废弃时，目录服务只将其标记为 `stale` 或 `disabled`，严禁物理硬删除，确保历史会话重放与 Checkpoint 审计追踪的引用完整性。
