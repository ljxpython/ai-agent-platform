# 知识库中台原生化重构 - 路线 C：智能问答与知识图谱原生工坊 (Native Knowledge Studio)

## 项目概述
- **时间：** 2026-10-19 至 2026-10-21
- **目标：** 彻底弃用跨域与认证割裂的 iframe 外挂模式（路线 A），基于原生 Vue 3 组件与标准化 HTTP API，在项目知识库中台内原生重构「智能问答工作台 (Chat Studio)」与「知识图谱工坊 (Graph Studio)」，消除登录拦截，实现统一鉴权、样式融合与极速交互。
- **负责人：** @lijiaxin (老王暴躁技术流督导)
- **模板类型：** 标准模板
- **状态：** done

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证计划与记录](verification.md)

## 改动范围
- **影响服务：**
  - `platform-web`：
    - `ProjectDetailPage.vue`：彻底删除「项目知识库」Tab 与冗余面板（已完成）
    - `ProjectKnowledgePage.vue`：二级板块全面切换为原生组件驱动
    - `KnowledgeChatStudio.vue`：新建原生沉浸式问答工作台组件
    - `KnowledgeGraphStudio.vue`：新建原生知识图谱拓扑探索工坊组件
  - `platform-api` / 远端网关：
    - 代理并消费远端 LightRAG FastMCP/HTTP 网关（8001端口）的 `/internal/knowledge/query` 与 `/internal/knowledge/graph` 接口
- **改动级别：** 链路改动（跨前后端及远端 RAG 网关协议，新增数据流与原生交互）
- **预计工作量：** 1.5 人天

## 关键决策
1. **彻底拔除 iframe（反脆弱与统一鉴权）**：
   - 杜绝第三方原生 WebUI 的跨域 cookie 阻断与登录弹窗；前端直接通过平台服务或网关调用 LightRAG 纯 JSON 接口，彻底实现免登无缝融合。
2. **项目详情页与知识中台严格正交解耦**：
   - 项目详情页纯粹聚焦“项目基础信息、元数据与成员治理”；
   - 知识库的资料管理、入库排队、切片检索、混合问答与图谱可视化唯一归属于「项目管理 ➔ 知识库」。
3. **轻量高性能图可视化渲染**：
   - 前端图谱工坊采用轻量力导向图可视化引擎，支持实体类型高亮、度数关系拓扑、缩放平移以及点击节点查看属性。
4. **混合问答与思考链路可解释性**：
   - 智能问答支持 Local / Global / Hybrid / Naive 四大模式切换，展示大模型合成回答以及召回切片的精准溯源。
