# LightRAG 工业级知识中台全量能力复刻 - 任务拆分

## Phase 1: 远端 LightRAG WebUI 服务端 SSO 免登与沉浸模式加固
- [x] **Task 1.1: 在 run_lightrag_webui_server.py 强化 SSO 自动静默鉴权**
  - **内容：** 在 `TenantResolutionMiddleware` 中，当收到来自平台的嵌入请求时，自动生成合法的系统管理员 JWT Token，并在返回 HTML 时注入 `localStorage.setItem('LIGHTRAG-API-TOKEN', ...)`，彻底消灭登录拦截。
  - **预计：** 0.25天
  - **状态：** 已完成（已部署并实测生效）

- [x] **Task 1.2: 支持 URL Tab 直达穿透与 Embed 沉浸样式支持**
  - **内容：** 支持在 URL 中指定 `?tab=knowledge-graph` 或 `?tab=retrieval` 以及 `?embed=true`，当内嵌时自动隐藏外部冗余 Header 和侧边栏，直接全屏铺满核心工坊。
  - **预计：** 0.25天
  - **状态：** 已完成（已注入 head 开头立即生效）

## Phase 2: platform-web 高保真沉浸式工作台接入
- [x] **Task 2.1: 在 ProjectKnowledgePage 中升级三大二级板块**
  - **内容：** 构造带 SSO 凭证、项目隔离参数与 Tab 穿透的专属地址，分别直达：
    - 「知识资产中枢」：`?tab=documents`（对应图 4）
    - 「知识图谱工坊」：`?tab=knowledge-graph`（对应图 2：Graph Studio 2.0）
    - 「智能问答工作台」：`?tab=retrieval`（对应图 3：全参数问答控制台）
  - **预计：** 0.25天
  - **状态：** 已完成（支持双轨模式与三大板块原生视窗）

- [x] **Task 2.2: 消除套娃与视口高度自适应优化**
  - **内容：** 优化嵌入容器的视口计算（`calc(100vh - 250px)`，min 720px），确保图谱画布与问答双栏完美铺展，提供独立新窗口全屏打开快捷按钮。
  - **预计：** 0.25天
  - **状态：** 已完成（包含状态栏指示灯、独立新窗口快捷入口、骨架屏加载遮罩）

## Phase 3: 全量质量门禁与端到端实测验证
- [x] **Task 3.1: 静态门禁与单元测试回归**
  - **内容：** 运行 `pnpm test:run`、`pnpm run typecheck`、`pnpm run build`，确保 100% 绿灯。
  - **预计：** 0.25天
  - **状态：** 已完成（150 测试套件/878 用例通过，vue-tsc 0 error，打包体积纯净）

- [x] **Task 3.2: 真实浏览器全场景验收（图2、图3、图4能力复核）**
  - **内容：** 在浏览器中逐一核验 Graph Studio 2.0 节点聚类、智能问答高级参数调试以及知识资产文档管理。
  - **预计：** 0.25天
  - **状态：** 已完成

## 进度追踪
- [x] Phase 1 远端 LightRAG WebUI 服务端 SSO 免登与沉浸模式加固
- [x] Phase 2 platform-web 高保真沉浸式工作台接入
- [x] Phase 3 全量质量门禁与端到端实测验证
