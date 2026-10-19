# 知识中台原生化重构（路线 C）- 整体设计方案

## 1. 背景与核心痛点

### 1.1 现状与痛点
1. **项目详情页冗余**：项目详情中保留的知识面板导致用户无法确定管理中枢到底在哪里，需要彻底干掉。
2. **路线 A（Iframe 嵌入）的严重硬伤**：
   - 跨域 Cookie 隔离：远端 LightRAG WebUI（9621端口）属于第三方跨域服务，由于缺乏内嵌 SSO 静默握手机制，直接被路由守卫踢入登录页；
   - 界面视觉撕裂：第三方 WebUI 自成一套样式系统，与 platform-web 的设计语言、暗色模式严重违和；
   - 缺乏上下文联动：iframe 无法与平台内的通知系统、工作区上下文及快捷操作进行深度绑定。

### 1.2 目标定位
- **路线 C（原生组件重构与 API 驱动）**：
  - 架构上彻底废除 iframe，以平台第一方原生 Vue 3 组件的形式交付两大工作室；
  - 智能问答：调用 `/internal/knowledge/query` 接口，提供多模式（Hybrid/Local/Global/Naive）问答与切片引文溯源；
  - 知识图谱：调用 `/internal/knowledge/graph` 接口，以原生 Canvas/SVG 力导向图呈现实体关系网，支持搜索、高亮、拖拽与节点详情抽屉。

## 2. 架构与交互设计

### 2.1 智能问答工作台 (Chat Studio)
- **前端布局**：
  - 顶部控制条：模式切换（Hybrid / Local / Global / Naive）、Top K 数量调节（1-8）、清空上下文；
  - 中间对话流：气泡渲染、Markdown 丰富解析、大模型思考回答；
  - 召回切片抽屉/折叠卡：呈现相关切片、相似度分数、关联文档名称与所属段落页码；
  - 底部输入区：支持快捷提问，发送状态感知。

### 2.2 知识图谱工坊 (Graph Studio)
- **后端协议**：
  - GET `/internal/knowledge/graph?project_id={id}&entity_name={name}&depth=1&max_nodes=40`
  - 响应：
    ```json
    {
      "status": "ok",
      "entity": "量子力学",
      "total_nodes": 15,
      "total_edges": 20,
      "nodes": [{ "name": "...", "type": "...", "description": "..." }],
      "edges": [{ "source": "...", "target": "...", "weight": 1.0, "description": "..." }]
    }
    ```
- **前端交互**：
  - 原生 HTML5 Canvas 力导向图模拟（或者基于轻量 D3/Vis 算法模型），物理平滑碰撞；
  - 节点根据 `type`（如 Person、Concept、Organization、Technology）赋予不同色相；
  - 悬停（Hover）高亮直接相连的一度关系；
  - 单击节点呼出侧边栏，查看该实体的详细定义与所有出入度关联。

## 3. 服务端链路与安全
- 前端请求通过平台标准环境变量 `VITE_KNOWLEDGE_GATEWAY_URL`（默认指向 `http://152.136.27.196:8001`）发起，直接受 `tenant_id` 与 `project_id` 物理数据目录隔离保护；
- 零额外跨域登录弹窗，零账号割裂。
