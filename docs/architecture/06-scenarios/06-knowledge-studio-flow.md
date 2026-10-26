# 06-06 知识资产上传、异步入库与只读检索时序深度解密

> **场景定位与核心价值**：解析原生知识中台（Knowledge Studio）从**多模态文档入库、Canvas 力导向图谱构建到 Agent 只读 MCP 检索与证据溯源**的端到端闭环时序。
> 彻底废除反向 SSH 穿透隧道，采用基于 Scoped HMAC 的单向自治架构，保障企业私有知识的安全入库、可交互图谱探索与防死循环检索问答。

---

## 零、 场景拓扑与核心时序

```mermaid
sequenceDiagram
    autonumber
    participant Web as 前端工作台 (Knowledge Hub / Graph Studio)
    participant API as Platform API (2142)
    participant LightRAG as LightRAG 知识服务 (8000)
    participant Runtime as Runtime Service (8123)

    %% 阶段一：知识上传与异步入库
    Note over Web,LightRAG: 【阶段一：知识资产安全上传与异步解析】
    Web->>API: 1. POST /api/v1/projects/{id}/knowledge/upload (multipart: PDF/DOCX)
    API->>API: 2. 校验文件魔数、SHA-256 去重与租户权限
    API->>API: 3. 动态签发 Scoped HMAC 令牌 (scope="knowledge:write")
    API->>LightRAG: 4. POST /documents (单向推送，带 Scoped Token)
    LightRAG-->>API: 5. 202 Accepted (返回 task_id)
    API-->>Web: 6. 上传成功，展示“解析排队中”卡片
    LightRAG-->>LightRAG: 7. 异步切片、实体/关系抽取与图谱落库

    %% 阶段二：原生图谱工坊交互
    Note over Web,LightRAG: 【阶段二：Canvas 力导向图谱工坊 (Graph Studio 2.0)】
    Web->>API: 8. GET /api/v1/projects/{id}/knowledge/graph
    API->>LightRAG: 9. 代理拉取项目实体关系拓扑
    LightRAG-->>API-->>Web: 10. 返回图节点与连边 JSON
    Web->>Web: 11. Canvas 原生力导向物理渲染，支持拖拽、聚焦与深浅主题

    %% 阶段三：智能体只读 MCP 检索与证据溯源
    Note over Web,Runtime: 【阶段三：Agent 只读知识检索闭环】
    Web->>API: 12. 用户提问项目专业问题
    API->>Runtime: 13. 签发 Delegation JWT 派发任务
    Runtime->>LightRAG: 14. 只读 MCP 携带只读 Scoped Token 查询 /api/v1/query
    Note over LightRAG: 无状态验签，执行图谱向量混合检索<br>返回证据片段及精准页码 (Page 15)
    LightRAG-->>Runtime: 15. 返回精准知识事实
    Runtime-->>API-->>Web: 16. SSE 流式输出回答，末尾附带精准来源卡片 [来源: 规范.pdf#P15]
```

---

## 一、 关键阶段与源码坐标映射

| 阶段步骤 | 关键代码路径 | 职责与防御细节 |
|---|---|---|
| **1. 凭据动态签发** | `apps/platform-api/src/platform_api/modules/knowledge/auth.py` | `generate_scoped_knowledge_token()`，单向防重放令牌 |
| **2. 文档入库与多模态解析** | `apps/platform-api/src/platform_api/modules/knowledge/service.py` | SHA-256 去重，异步任务排队，页码/段落元数据保留 |
| **3. 原生 Canvas 图谱工坊** | `apps/platform-web/src/modules/knowledge/components/GraphStudioCanvas.vue` | Canvas 力导向图渲染、免第三方登录弹窗 |
| **4. 只读 MCP 与防死循环** | `apps/runtime-service/src/runtime_service/services/mcp/knowledge_mcp.py` | `ProjectKnowledgeSearchClient`，严格只读与 4 次熔断 |
