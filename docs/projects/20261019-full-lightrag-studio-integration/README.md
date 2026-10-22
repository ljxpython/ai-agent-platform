# LightRAG 工业级知识中台全量能力复刻与无缝集成 (Full LightRAG Studio Integration)

## 项目概述
- **时间：** 2026-10-19 至 2026-10-21
- **目标：** 100% 完整复刻并接入 LightRAG 原生成熟的工业级知识中台三大核心能力（Graph Studio 2.0 拓扑工坊、全参数智能问答工作台、Knowledge Hub 资产中枢），彻底根治第三方登录拦截，实现项目级多租户隔离、Tab 直达穿透与无缝沉浸式体验。
- **负责人：** @lijiaxin (老王暴躁技术流督导)
- **模板类型：** 标准模板
- **状态：** 已完成

## 快速导航
- [整体设计方案](plan.md)
- [任务拆分与执行阶段](tasks.md)
- [验证计划与验收标准](verification.md)

## 改动范围
- **影响服务：**
  - 远端 LightRAG 核心服务（`<lightrag-repo>`）：
    - `run_lightrag_webui_server.py`：加固 SSO 静默握手机制，签发合法 JWT，消除登录拦截；增加 `embed` 沉浸模式支持；
    - `lightrag_webui`：支持 Tab 直达路由穿透（`#/graph`、`#/retrieval`、`#/documents`）与自适应布局；
  - `platform-web`：
    - `ProjectKnowledgePage.vue`：二级板块接入高保真全量工坊（沉浸式容器、项目参数穿透、Tab 联动）；
  - `platform-api`：
    - 代理生成当前用户与项目绑定的安全凭据，实现零登录弹窗的单点登录（SSO）。
- **改动级别：** 链路改动（跨 Web、API 与远端 RAG 运行时集成）
- **预计工作量：** 1.5 人天

## 关键决策
1. **彻底拒绝“简陋低幼玩具”，全面接入全量工业级能力**：
   - 彻底摒弃粗糙的简易 Canvas 模拟；
   - 完整交付用户截图中展示的 **Graph Studio 2.0**（N-Degree 拓扑、度数排名、实体分类过滤、图例色盘、控制手柄）、**智能问答工作台**（KG Top K、文本块 Top K、词元上限调节、重排策略、对比实验台）以及 **Knowledge Hub**。
2. **SSO 静默握手与 JWT 自动注入**：
   - 根治登录框弹窗拦截：远端 WebUI 服务端检测到平台来源或有效请求时，自动生成合法的长效 JWT 注入 `localStorage['LIGHTRAG-API-TOKEN']`，使 `useAuthStore` 直接处于 `isAuthenticated = true` 状态，彻底消灭登录页阻断。
3. **沉浸式内嵌与 UI 融合（去套娃化）**：
   - 传递 `embed=true` 参数，在内嵌模式下自动隐藏 9621 顶部的重复 Header 和多余 Logo，让其直接融入平台的二级板块中，界面高级感拉满。
4. **多租户与项目上下文严格绑定**：
   - 依托已实装的 `TenantResolutionMiddleware`，每一次操作均自动携带 `tenant_id=__default&project_id=${projectId}`，确保数据目录物理隔离，绝不串项目。
