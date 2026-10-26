# 02-06 原生知识中台与零隧道自治架构深度解密

> **模块定位与核心价值**：建立企业的**高可用知识资产中台与图谱检索体系**。
> 彻底废除脆弱的反向 SSH/HTTP 穿透隧道反模式，实装**单向自治验签架构（Zero-Tunnel Auth）**；深度融合 LightRAG 图结构，提供原生 **Graph Studio 2.0（Canvas 力导向图谱工坊）**、**Chat Studio** 与 **Knowledge Hub** 三大工业级能力；在 Agent 执行端通过只读 MCP 与精准段落/页码定位，提供低幻觉、可溯源的知识问答闭环。

---

## 零、 知识前置与上下文串联（Knowledge Bridges）

在阅读具体知识中台设计前，必须掌握三个底层核心概念，以及知识数据在全系统链路中的坐标。

### 1. 前置必备概念速查

- **概念 1：为什么传统 SSH 反向穿透隧道是生产反模式？**
  - **穿透隧道之殇**：传统方案常在内网或远端机器建立 `ssh -R` 反向穿透，一旦公网抖动或长连接断开，反向隧道容易发生“假死（Zombie Tunnel）”，平台无法感知，导致知识库调用频频超时；
  - **网络安全审计漏洞**：反向隧道直接把远端内网网络端口暴露给外部，破坏了企业的纵深防御网络隔离边界；
  - **单向自治的破局**：远端知识库收敛为**纯单向入站服务（仅需安全监听 HTTP/HTTPS 端口）**。每次请求由平台签发自带项目租户范围的 **Scoped HMAC/JWT 动态凭据**，远端无状态即时自验，杜绝隧道维护。
- **概念 2：LightRAG 图检索增强生成（Graph-based RAG）**
  - 传统的 Naive RAG 只做简单的向量相似度检索（Top-K Chunks），割裂了文档之间的实体关联；
  - LightRAG 在向量切片的基础上，提取实体（Entity）与关系（Relationship），构建双层知识图谱结构（Low-level 细节实体 + High-level 全局概念），极大提升了复杂交叉问题的召回质量。
- **概念 3：知识来源精确溯源（Provenance Grounding）**
  - 智能体回答必须带有**不可篡改的证据来源**。知识中台在切片入库时记录多模态元数据（文件指纹、标题、所在页码 `page_number`、幻灯片序号 `slide_index`），检索命中时在回答底部附带来源微胶囊，点击可直接高亮原文。

### 2. 链路上下文坐标

- **知识生产（入库）**：
  用户在 Web 端上传文档（PDF/DOCX/PPTX/TXT）或可信图片 -> Platform API 校验权限并入库审批 -> 异步派发至 LightRAG 进行分块与图谱提取 -> 状态落盘。
- **知识消费（检索）**：
  Runtime Worker 运行智能体 -> 发现用户问题涉及项目领域 -> 调用受管只读 MCP（`knowledge_search`） -> 携带 Scoped 凭据向 LightRAG 发起单向检索 -> 结果注入 LLM 上下文。

---

## 一、 对立视角：简易原型 vs 生产架构（Naive vs. Production）

### 1. 初学者的常规写法（Naive Demo）
很多初学者集成知识库时，直接在本地起一个带界面的第三方 RAG 框架，然后前端用 `<iframe>` 硬挂进去：
```html
<!-- 简易内嵌（存在严重生产隐患） -->
<iframe src="http://remote-rag-host:8000/knowledge-base" />
```

### 2. 生产环境下的致命缺陷
- **iframe 弹窗与认证穿台**：用户打开网页时频繁弹出 RAG 系统自带的登录窗口，无法融入平台的统一登录鉴权，甚至发生跨租户数据串台；
- **反向 SSH 隧道频繁死锁**：为了让主平台调通远端 RAG，运维手动在远端起 `ssh -N -R 8000:localhost:8000 ...`，服务器半夜断网一次，整个知识问答全部瘫痪；
- **Agent 工具调用死循环**：大模型使用知识检索工具时，若检索结果为空或格式不规范，模型不断更换关键词反复调用 `knowledge_search`，直到把 Token 预算耗尽。

### 3. 本项目的架构升级与设计取舍（Trade-offs）
- **废除 iframe，全自研原生 Knowledge Studio**：前端基于 Vue 3 + Canvas 原生绘制力导向图谱（Graph Studio 2.0），彻底消除第三方登录弹窗，视觉与主题无缝统一；
- **单向自治验签（Zero-Tunnel Auth）**：淘汰反向隧道与静态 `.env` 密钥配置，采用 Platform-API 动态签发 Scoped HMAC 令牌，远端纯单向验签，支持免重启多项目动态绑定；
- **只读 MCP 守卫与防死循环优化**：Agent 端挂载专门的只读检索工具，底层内置调用频次计数与防死循环熔断，连续 3 轮空召回自动安全降级，不再盲目重试。

---

## 二、 源码精准坐标映射（Code Pointer Map）

| 模块职责 | 核心代码路径 | 关键类 / 函数 / 变量 |
|---|---|---|
| **知识中台动态凭据签发** | `apps/platform-api/src/platform_api/modules/knowledge/auth.py` | `sign_knowledge_scoped_token()`, Scoped HMAC |
| **知识上传与异步解析入库** | `apps/platform-api/src/platform_api/modules/knowledge/service.py` | `upload_and_enqueue_document()`, 多模态切片调度 |
| **项目级只读知识检索 MCP** | `apps/runtime-service/src/runtime_service/services/mcp/knowledge_mcp.py` | `KnowledgeRetrievalMCP`, `search_project_knowledge()` |
| **防死循环熔断中间件** | `apps/runtime-service/src/runtime_service/middleware/loop_detection.py` | `ToolLoopDetectionMiddleware`, 3 轮预警/5 轮硬终止 |
| **原生图谱工坊 (Graph Studio)** | `apps/platform-web/src/modules/knowledge/components/GraphStudioCanvas.vue` | Canvas 力导向图、节点高亮、动态力学模拟 |
| **知识来源精准定位组件** | `apps/platform-web/src/modules/chat/components/CitationBadge.vue` | 段落高亮、页码定位、原文件安全下载拦截 |

---

## 三、 真实数据结构与报文（Real Payloads & DB Schemas）

### 1. Scoped HMAC 动态令牌载荷定义

```json
{
  "iss": "aiplatform.controlplane",
  "sub": "user_4a7b8c9d",
  "project_id": "proj_finance_2026",
  "scope": "knowledge:read",
  "doc_allowlist": ["doc_uuid_001", "doc_uuid_002"],
  "exp": 1792982400,
  "nonce": "e3b0c44298fc1c149afbf4c8996fb924"
}
```

- **安全防御设计**：
  - `project_id`：严格限定当前请求可检索的项目分区，杜绝跨租户越权；
  - `scope`：强校验 `knowledge:read` 或 `knowledge:write`，Agent 端签发的凭据永远只能持有 `knowledge:read` 权限；
  - `nonce`：防止单向请求被黑客网络嗅探后进行重放攻击。

### 2. 知识库多模态文档表（Platform DB: `knowledge_documents`）

```sql
CREATE TABLE knowledge_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id VARCHAR(64) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,               -- SHA-256 防重复上传
    status VARCHAR(32) NOT NULL DEFAULT 'queued', -- queued / processing / completed / failed
    total_pages INT DEFAULT 1,
    extracted_entities_count INT DEFAULT 0,
    storage_path VARCHAR(512) NOT NULL,
    created_by VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_knowledge_proj_status ON knowledge_documents (project_id, status);
CREATE UNIQUE INDEX uq_proj_file_hash ON knowledge_documents (project_id, file_hash);
```

---

## 四、 端到端函数级调用时序（Function-Level Trace）

```mermaid
sequenceDiagram
    autonumber
    participant Web as 前端工作台 (Vue3)
    participant API as Platform API (2142)
    participant RT as Runtime Service (8123)
    participant LightRAG as 远端 LightRAG (8000)

    %% 知识上传与自治入库
    Note over Web,LightRAG: 【阶段一：知识入库与异步图谱提取】
    Web->>API: 1. 上传文档 (multipart/form-data)
    API->>API: 2. 检查 SHA-256 去重与租户权限
    API->>LightRAG: 3. POST /documents (携带 Scoped Token，单向推送)
    LightRAG-->>API: 4. 返回任务已受理 (202 Accepted, task_id)
    API-->>Web: 5. 返回上传成功，前端展示“解析中”状态卡片
    LightRAG-->>LightRAG: 异步执行文本切片、实体抽取与图谱构建

    %% Agent 问答与检索闭环
    Note over Web,LightRAG: 【阶段二：Agent 只读知识检索闭环】
    Web->>API: 6. 用户提问：“根据公司财报，今年的研发预算是多少？”
    API->>RT: 7. 下发任务 (签发 Delegation JWT)
    RT->>RT: 8. LLM 决定调用 knowledge_search(query="2026年研发预算")
    RT->>LightRAG: 9. 只读 MCP 发起 POST /query (携带只读 Scoped Token)
    LightRAG->>LightRAG: 10. 无状态校验 HMAC，执行 Dual-level 图谱向量混合检索
    LightRAG-->>RT: 11. 返回 Top-K 证据块与精确页码 (Page 42, Para 3)
    RT->>RT: 12. 将证据块组装入 Prompt 继续推理
    RT-->>API-->>Web: 13. SSE 流式输出回答，末尾附带 [来源: 2026财报.pdf#P42]
```

---

## 五、 核心实现高保真伪代码（High-Fidelity Pseudocode）

### 1. 控制面：Scoped HMAC 动态凭据生成器

```python
# 对应源码：apps/platform-api/src/platform_api/modules/knowledge/auth.py
import hmac
import hashlib
import json
import time
import base64


def generate_scoped_knowledge_token(
    secret_key: str, project_id: str, scope: str = "knowledge:read", ttl: int = 300
) -> str:
    """生成具备项目隔离与操作白名单的单向自验证令牌"""
    payload = {
        "project_id": project_id,
        "scope": scope,
        "exp": int(time.time()) + ttl,
        "nonce": hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:16],
    }

    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload).encode())
        .decode()
        .rstrip("=")
    )

    signature = hmac.new(
        secret_key.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return f"{payload_b64}.{signature}"
```

### 2. 运行时：只读知识检索 MCP 与防死循环拦截

```python
# 对应源码：apps/runtime-service/src/runtime_service/services/mcp/knowledge_mcp.py
from langchain_core.tools import tool
import httpx


class ProjectKnowledgeSearchClient:

    def __init__(self, endpoint: str, scoped_token: str):
        self.endpoint = endpoint
        self.scoped_token = scoped_token
        self.call_count = 0

    async def search(self, query: str) -> str:
        # 防死循环硬护栏：单次会话内同一工具连续调用超过 4 次强制熔断
        self.call_count += 1
        if self.call_count > 4:
            return "【系统警告】：当前问题检索尝试次数过多，请基于已有已知信息给出审慎回答，停止继续调用本工具。"

        headers = {
            "Authorization": f"Bearer {self.scoped_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.endpoint}/api/v1/query",
                headers=headers,
                json={"query": query, "mode": "hybrid"},
            )
            if resp.status_code != 200:
                return (
                    f"【检索暂时不可用】：知识库服务返回状态码 {resp.status_code}"
                )

            data = resp.json()
            return data.get("result", "未找到直接相关的知识库资料。")
```

---

## 六、 架构不变量清单（Architectural Invariants）

1. **绝对禁止引入 SSH 反向穿透隧道**：所有知识中台微服务交互必须通过单向入站 HTTP/HTTPS API 承载，严禁使用任何反向穿透隧道脚本。
2. **凭据必须受 Scoped 作用域与项目物理隔离**：签发的令牌必须严格锁死 `project_id` 与操作权限（如只读），严禁签发全权通用的无界令牌。
3. **知识检索必须具备防死循环熔断保护**：Agent 挂载的知识检索工具必须内置单 Run 调用次数上限（上限 <= 5 次），杜绝空召回导致模型死循环消耗 Token。
4. **证据来源必须具备不可篡改溯源信息**：检索返回给大模型的上下文片段必须明确标注源文件名及定位信息，且在前端渲染时必须执行安全路径过滤，严禁伪协议跳转。
