# LightRAG 数据面收口方案

## 1. 文档目的

本文只讨论 LightRAG 数据面应该怎么改，目标是把它从“单实例知识服务”收口成“可被 AITestLab 按项目安全复用的 knowledge data plane”。

## 2. 当前问题基线

外部参考代码和设计稿已经给出两个关键事实：

- LightRAG 已支持 `LIGHTRAG-WORKSPACE` 请求头解析（外部参考：`lightrag/api/lightrag_server.py:458-486`）
- 但当前 API server 仍然以单个 `rag = LightRAG(...)` 实例初始化为中心（外部参考：`lightrag/api/lightrag_server.py:1254-1289`）

LightRAG 自己的拆分稿也明确指出了现状问题：

- `workspace` 还没在所有关键 API 路径里统一生效
- 许多流程仍偏向实例默认 workspace
- 请求级多 workspace 还没有形成统一解析和实例复用机制
- status 类接口需要继续核对作用域一致性

见外部参考：`docs/aitestlab-knowledge-lightrag-task-breakdown.md:52-97`。

## 3. Phase 1 目标

把 LightRAG 变成：

> **request-scoped multi-workspace knowledge data plane**

Phase 1 完成标志：

- 同一服务实例可承载多个 workspace
- 上传、查询、图谱、删除、状态跟踪都不串 workspace
- 平台 human-facing path 只需要传 `LIGHTRAG-WORKSPACE`

## 4. 推荐技术路线

### 4.1 不做全链路手工传 workspace

外部参考设计稿已经给出较合理方向：不要把整个 LightRAG 改成每个函数都显式传 `workspace`，而是在 API server 层引入 `workspace -> LightRAG instance` 的管理器（外部参考：`docs/aitestlab-knowledge-lightrag-task-breakdown.md:74-97`）。

当前建议继续沿这条线：

- 统一 header 解析与清洗
- 引入 `LightRAGWorkspaceManager`
- 每个请求先确定 workspace，再获取/创建对应 `LightRAG` 实例
- 共享不可变配置，隔离 workspace 级存储与状态

### 4.2 第一阶段最少要完成的 LightRAG 任务

- [x] 统一 request workspace 解析逻辑
- [x] 引入 workspace manager / registry
- [x] 覆盖 documents / query / graph / health / status 关键接口
- [x] 固化 `track_status / pipeline_status / doc_status` 的 workspace 一致性
- [x] 明确平台侧 service-to-service auth 边界
- [x] 补最少两个 workspace 的 smoke test

## 5. AITestLab 对 LightRAG 的输入契约

AITestLab 第一阶段只向 LightRAG 施加这些输入约束：

- `workspace_key`
- service auth
- human-facing path 里的请求参数

AITestLab 不把这些内容塞进 LightRAG：

- 平台用户
- 项目成员
- 项目权限
- 审计逻辑
- 页面/导航壳层

## 6. 与后续 MCP 方向的关系

future runtime-side path 不走 `platform-api-v2` 的统一程序化 API，而走 **LightRAG MCP**。这对 LightRAG 有两个隐含要求：

1. Phase 1 就不要把平台 UI 接口与 runtime tool 接口写死耦合在一起
2. workspace / status / document query 这些核心能力以后要能同时服务 HTTP facade 和 MCP tool facade

因此推荐把未来 MCP 视为 **Phase 2**：

- Phase 1：先把 HTTP data plane 收口好
- Phase 2：在同一数据面上加 MCP 工具层

## 7. Phase 2：LightRAG MCP 化方向

后续 MCP 需要至少满足：

- runtime caller 不直接拼 `workspace_key`
- 工具输入以 `project_id` 或等价平台主标识为主，而不是让业务代码散落 workspace 规则
- 文档查询、文档列表、索引状态、图谱/检索能力有稳定工具面
- tool message 返回值可被现有 LangGraph / agent 链路稳定消费

### 当前未决问题

这里仍有一个后续阶段必须明确的问题：

> 当 runtime-service 通过 LightRAG MCP 使用项目知识时，`project_id -> workspace_key` 的映射由谁在工具面内部解析？

当前建议把它记录为 **Phase 2 决策项**，不要把这个问题反向阻塞当前 Phase 1 的 human-facing control-plane 建设。

## 8. 不建议做的事

- 现在就把 LightRAG 直接变成平台治理服务
- 现在就为 future multi-knowledge / shared knowledge 做过重资源模型
- 现在就为了 runtime consumption 反向设计平台 facade
