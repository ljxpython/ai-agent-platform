# 知识库动态多项目绑定与免重启鉴权体系 - 整体方案

## 背景
在当前架构中，知识库（RAG-Anything-Use）的挂载依赖静态环境变量：
- `platform-api` 依赖 `PLATFORM_KNOWLEDGE_MCP_BINDINGS_JSON` 和 `PLATFORM_API_KNOWLEDGE_CONNECTIONS_JSON`；
- `runtime-service` 依赖 `RUNTIME_MCP_CONNECTIONS_JSON`；
- 远端 `rag-anything-use` 依赖 `KNOWLEDGE_MCP_TOKEN_SCOPES_JSON`。

这种静态设计存在致命生产缺陷：
1. **上线与维护成本极高**：每次在 Web 界面新建一个项目，工程师必须手动 SSH 登录服务器修改 `.env` 并在多端同步更新 Token，随后重启三个服务；
2. **高可用灾难**：重启导致所有在线 Agent 长连接断开、正在执行的任务中断；
3. **无法支持多租户 SaaS 商业化扩展**：无法做到“用户在平台一键创建项目，立即享有独立的知识库”。

## 目标
1. **0 手工配置与 0 服务重启**：平台新建项目后，立即生效独立的知识库，无需人工修改 `.env` 或重启任何服务。
2. **三层严格多租户数据隔离**：
   - 控制面：按租户与项目严格校验 IAM 权限，跨项目禁止访问；
   - 物理存储面：远端物理文件系统按 `${tenant_id}/${project_id}/${knowledge_base_id}/` 严格物理隔离；
   - 检索索引面：向量数据库与知识图谱按 `knowledge_base_id` 进行独立索引/Scope 强制过滤。
3. **两端协同闭环**：
   - 本地 `research/rag-anything-use` 完成无状态验签升级与测试验证；
   - 同步部署至远端 Ubuntu 主机（`sshmy2`），完成线上闭环。

## 方案设计

### 整体架构

```
┌────────────────────────────────────────────────────────────────────────┐
│                        1. 控制面 (Platform API)                         │
│                                                                        │
│  [ 前端创建项目 ] ──▶ PostgreSQL 自动创建记录并分配唯一 knowledge_base_id  │
│                                │                                       │
│       ┌────────────────────────┴────────────────────────┐              │
│       ▼                                                 ▼              │
│ [Web控制面查询文档/状态]                       [Agent 会话启动 / 发起 Run]      │
│  实时签发 Scoped Token                         通过 Thread Binding 动态注入     │
│  直连 RAG HTTP API                            动态 Scoped Token & MCP 声明     │
└───────┬─────────────────────────────────────────────────┬──────────────┘
        │                                                 ▼
        │                                  ┌─────────────────────────────┐
        │                                  │   2. 执行面 (Runtime)       │
        │                                  │                             │
        │                                  │ 从 Thread Binding 提取动态   │
        │                                  │ Token，直连 RAG MCP Gateway │
        │                                  └──────────────┬──────────────┘
        │                                                 │
        └────────────────────────┬────────────────────────┘
                                 │ HTTPS (或独立端口) 携带 Bearer Scoped JWT
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   3. 远端数据面 (RAG Anything Use / sshmy2)             │
│                                                                        │
│   [ FastMCP /mcp ] ──▶ [ KnowledgeTokenVerifier (无状态 HS256 验签) ]  │
│                                │ (解出 tenant, project, kb_id)         │
│                                ▼                                       │
│   [ 懒加载命名空间初始化 ] ──▶ 自动校验/创建专属物理路径与向量 Collection     │
│                                │                                       │
│                                ▼                                       │
│       /home/ubuntu/rag-data/{tenant_id}/{project_id}/{kb_id}/          │
└────────────────────────────────────────────────────────────────────────┘
```

### 关键改动点

#### 1. Platform-API：PostgreSQL 持久化与动态 Token 签发
- **文件：**
  - `apps/platform-api/src/platform_api/modules/projects/models.py`
  - `apps/platform-api/src/platform_api/modules/knowledge/service.py`
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/application/knowledge_bindings.py`
- **改动：**
  - 在 `projects` 表中持久化 `knowledge_base_id`（默认创建项目时自动生成 `kb_{32位hex}`）；
  - 新增 `KnowledgeTokenIssuer`：利用预共享的 `PLATFORM_API_KNOWLEDGE_SECRET`，通过 HS256 签发包含 `tenant_id`, `project_id`, `knowledge_base_id`, `exp` 的 Scoped JWT；
  - `build_knowledge_binding()` 动态返回携带该 Scoped Token 的 binding，并在 `knowledge/service.py` 控制面中支持从 DB 查询项目并动态构造连接。
- **理由：** 消除静态 JSON 依赖，将权威元数据下沉至数据库，基于密码学签名实现跨服务无状态信任。

#### 2. Runtime-Service：解耦静态 connections 配置，支持上下文动态注入
- **文件：**
  - `apps/runtime-service/src/runtime_service/tools/mcp.py`
  - `apps/runtime-service/src/runtime_service/runtime/mcp_config.py`
- **改动：**
  - 配置 `RUNTIME_KNOWLEDGE_MCP_GATEWAY_URL`（例如 `http://152.136.27.196:8000/mcp`）；
  - `load_mcp_tools` 当发现 `binding` 中带有动态签发的 `auth_token` 时，自动将其挂载为请求头 `Authorization: Bearer <auth_token>`，直接连接网关；
  - 保留现有静态 `RUNTIME_MCP_CONNECTIONS_JSON` 作为兼容 fallback。
- **理由：** Runtime 是纯执行引擎，不需要也无法提前知道未来所有的项目 ID，按需消费会话上下文凭据才是云原生标准。

#### 3. RAG-Anything-Use：升级 Token 校验器支持无状态动态验签与懒加载
- **文件：**
  - `/Users/lijiaxin/PyCharmMiscProject/research/rag-anything-use/src/knowledge/auth.py`
  - `/Users/lijiaxin/PyCharmMiscProject/research/rag-anything-use/src/knowledge/jobs.py`
- **改动：**
  - 在 `KnowledgeTokenVerifier.verify_token(token)` 中引入 JWT/HMAC 验签逻辑：
    - 若传入静态 Token（在 `KNOWLEDGE_MCP_TOKEN_SCOPES_JSON` 中），按原逻辑放行；
    - 若传入格式合规的 JWT，使用 `KNOWLEDGE_AUTHORIZATION_SECRET` 进行 HS256 验签；
    - 验签通过后，提取 Scope，调用 `KnowledgeJobStore.ensure_project(knowledge_base_id, tenant_id, project_id)` 进行持久化登记并自动准备物理目录。
- **理由：** 远端微服务无需与主数据库直连，纯无状态鉴权，具备极限抗压与水平扩展能力。

### 技术选型与权衡
- **选型 1：对称密钥签名 JWT (HS256) vs 非对称密钥 (RS256)**
  - 采用 HS256，因为 Platform API 与内部 RAG 服务属于同一机密受控网络，预共享 32+ 字节高强度密钥安全可控，计算开销极低（单次验签 < 0.1ms），避免复杂的公钥分发服务（JWKS）。
- **选型 2：动态懒加载 vs 显式 RPC 预建项目**
  - 采用动态懒加载：新项目第一次发起对话或上传文档时自动创建目录与索引空间，不需要在建项目时做阻塞式网络调用，架构最轻量（KISS 原则）。

## 链路影响

### 受影响的调用链路
1. **控制面链路**：
   `Platform Web` → `Platform API (/api/projects/{id}/knowledge/...)` → `动态生成 Token` → `RAG HTTP API`
2. **智能体执行面链路**：
   `Platform API (创建 Thread)` → `注入动态 MCP Binding (含 Token)` → `Runtime Worker (装配 mcp_tools)` → `RAG FastMCP (/mcp)` → `Milvus / 本地磁盘`

### 契约变更
- **Runtime Resource Binding (mcp)**：在 metadata 中新增可选字段 `auth_token` 与 `gateway_url`，原 `resource_id` 作为回退标识；
- **RAG FastMCP Authorization**：支持承载标准 JWT Bearer Token。

## 风险和依赖
- **密钥同步依赖**：`PLATFORM_API_KNOWLEDGE_SECRET` 与 RAG 的 `KNOWLEDGE_AUTHORIZATION_SECRET` 必须保持一致。
  - **应对：** 启动时检查长度（>= 32 字节），若未配置给出清晰错误日志。
- **时钟同步风险**：JWT 包含 `exp` 超时时间（建议 24 小时或 7 天），若两台服务器时钟相差过大可能拒载。
  - **应对：** 容忍 +/- 60 秒时钟偏移，预设充足有效期。

## 实施计划
1. **Phase 1：RAG 核心升级（本地验证）**：在本地 `rag-anything-use` 实现并单测验证无状态验签与懒加载。
2. **Phase 2：平台侧改造（Platform & Runtime）**：数据库表扩展、动态 Token 签发、Runtime 动态装配接线。
3. **Phase 3：远端同步部署与全链路联调**：将 RAG 代码推送到 `sshmy2`，平滑重启远端 `rag-service`，在平台 Web 新建项目实测一键生效。
