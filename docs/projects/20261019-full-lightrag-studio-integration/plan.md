# LightRAG 工业级知识中台全量能力复刻 - 架构与实施方案

## 1. 深度复盘与问题本质

### 1.1 用户期望与现状差距
- **用户期望**：
  在平台「项目管理 ➔ 知识库」中，能够 100% 完整使用 LightRAG 原生研发的工业级功能：
  1. **Graph Studio 2.0 (N-Degree Subgraph)**：支持 277 实体、471 关联关系、1°/2°/3° 深度探索、实体分类 (Category) 过滤、核心关键实体 TOP 15 排行榜、多群落聚类算法、11 种实体图例、左下角悬浮控制台；
  2. **智能问答工作台**：支持对比实验台、Markdown 深度图表渲染、会话历史列表、右侧强大的高级参数调试器（包含全局分析、KG Top K、文本块 Top K、词元上限 30000、重排、仅高上下文等）；
  3. **Knowledge Hub 知识资产中枢**：支持指标趋势看板、文件夹树、流水线状态、格式多模态解析分面（文本/模态/图谱处理）。
- **此前暴露的严重缺陷**：
  - 手写的简化版 Canvas 组件只有几十行代码，无法呈现复杂的图谱聚类和实体分析，功能覆盖率不足 5%，如同“玩具”；
  - 简单的 iframe 接入（路线 A）由于缺乏合法的 JWT SSO 握手，直接被 LightRAG 前端路由守卫判定为未登录，弹出了粗暴的账号密码登录框。

---

## 2. 三大实现路径技术对比与方案选型

| 评估维度 | 方案 A+：无缝 SSO 握手 + 沉浸式深度内嵌 (推荐) | 方案 B：微前端架构 (Wujie / Qiankun) | 方案 C：Vue 3 纯代码级全量手工重写 |
|---|---|---|---|
| **功能复刻度** | **100% 毫无保留**（完整承载原厂上万行代码的所有功能） | **100%**（完整运行 React 产物） | **10%~30%**（工作量巨大，容易漏掉海量细节） |
| **登录拦截问题** | **彻底根治**（服务端自动签发并注入合法 JWT） | **彻底根治**（主子应用共享 Context） | 无登录问题（纯自研接口） |
| **视觉与套娃体验** | **优秀**（通过 `?embed=1` 隐藏冗余 Header/Sidebar） | **极佳**（微前端沙箱容器融入） | **极佳**（完全是第一方原生代码） |
| **实施周期与风险** | **0.5 ~ 1 天**（精准、可控、即刻见效） | **2 ~ 3 天**（需处理 React/Vue 运行时隔离与构建链） | **2 ~ 4 周**（数万行 React/Cytoscape 代码需人工重写） |
| **原厂功能跟进** | **自动同步**（远端 LightRAG 升级，平台立刻获得新特性） | **需重新构建打包** | **无法同步**（后期维护成本极高） |

### 架构选型结论
👉 **首选方案 A+（工业级无缝 SSO 握手 + 沉浸式深度内嵌）**：
这是云原生与平台架构中最标准的“中台集成模式”。通过服务端无感知自动签发合法 JWT、沉浸式隐藏外部导航、以及项目多租户上下文物理隔离，**在最小开发成本下，瞬间将 LightRAG 100% 工业级能力完整复刻进平台**！

---

## 3. 方案 A+ 详细技术实现设计

### 3.1 核心攻坚 1：彻底消灭登录拦截（SSO 静默握手）
- **根因剖析**：
  LightRAG 的 `AppRouter.tsx` 严格检查 `localStorage.getItem('LIGHTRAG-API-TOKEN')` 是否是合法的 JWT，并调用 `isTokenLocallyValid()` 验证三段式结构与过期时间。
- **解决方案**：
  1. 在 `run_lightrag_webui_server.py` 中，增强 `TenantResolutionMiddleware`：
     - 当检测到客户端请求携带平台握手标记或受信任上下文（或者直接在内网反向代理中），服务端自动使用 `auth_handler.create_token(username="admin", role="admin")` 生成一个合法的长效 JWT！
     - 在首次返回 HTML 时，动态注入：
       ```html
       <script>
         localStorage.setItem('LIGHTRAG-API-TOKEN', '...');
         localStorage.setItem('LIGHTRAG-CORE-VERSION', 'v1.5.8');
       </script>
       ```
     - 使得 LightRAG WebUI 在初始化时直接判定 `isAuthenticated = true`，**永远不会展示登录界面**！

### 3.2 核心攻坚 2：深度路由与 Tab 穿透（Deep-Linking）
- **让每个板块精准对应**：
  LightRAG 内部由 Zustand 的 `useSettingsStore` 管理 `currentTab`：
  - `documents`：知识资产中枢
  - `knowledge-graph`：Graph Studio 2.0
  - `retrieval`：智能问答工作台
- **穿透方案**：
  在 WebUI 中支持读取 URL Query 参数 `?tab=knowledge-graph` 或 `?tab=retrieval`，当加载时自动激活对应 Tab，直接呈现用户截图中完美的特定页面！

### 3.3 核心攻坚 3：消除双 Header 套娃与界面融合（Embed Mode）
- 当传入 `?embed=true` 时：
  - 自动通过 CSS 或配置隐藏 9621 顶部的 `SiteHeader` 和左侧的 `AppSidebar`；
  - 内容区域（图 2 的全景图谱、图 3 的问答双栏）直接铺满当前平台分配的容器；
  - 整体视觉与我们的 `platform-web` 浑然一体，没有丝毫外挂痕迹！

### 3.4 核心攻坚 4：项目多租户物理隔离
- URL 中固定携带 `tenant_id=__default&project_id=${projectId}`；
- 远端 `TenantResolutionMiddleware` 自动切换工作区存储路径到 `sandbox_storage/__default/${projectId}/`；
- 用户在 Graph Studio 里看到的就是且仅是当前项目的 277 个实体，在问答工作台里提问调用的就是且仅是当前项目的知识库！
