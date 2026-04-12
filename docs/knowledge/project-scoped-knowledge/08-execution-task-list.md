# 项目级知识库执行任务单

> 使用方式：后续实际开发时，按阶段逐项打勾；没有验证证据的项不要提前打勾。当前仍未勾选的项，主要是需要真实联调环境继续完成的 live integration 验证。

## Phase 0：正式文档落地

- [x] 创建 AITestLab 仓库内正式文档目录
- [x] 固化第一阶段边界
- [x] 固化 future runtime-side MCP 边界
- [x] 固化实施顺序与验收清单

## Phase 1：LightRAG 数据面

### A1 workspace 解析统一化
- [x] 固化 `LIGHTRAG-WORKSPACE` header 规则
- [x] 固化 workspace 清洗/拒绝策略
- [x] 统一所有关键路由的 workspace 解析入口

### A2 workspace manager
- [x] 设计 `workspace -> LightRAG instance` 缓存对象
- [x] 共享不可变配置
- [x] 隔离 workspace 级状态与存储
- [x] 明确生命周期与懒初始化策略

### A3 关键 API workspace 化
- [x] documents upload
- [x] documents paginated
- [x] track status
- [x] pipeline status
- [x] query
- [x] graph label list / search
- [x] graphs
- [x] delete / clear

### A4 状态与 smoke test
- [x] 校验多模态状态一致性
- [x] 补 A/B 两个 workspace smoke test
- [x] 记录 service auth 约束

## Phase 2：platform-api-v2

### B1 模块骨架
- [x] 新增 `app/modules/project_knowledge/`
- [x] 新增 `app/adapters/knowledge/`
- [x] 建立 presentation / application / infra 结构

### B2 资源模型
- [x] 新增 `project_knowledge_spaces` 模型/迁移
- [x] 实现 repository / use case
- [x] 固化 `project_id -> workspace_key`

### B3 human-facing APIs
- [x] settings / summary API
- [x] documents APIs
- [x] query API
- [x] graph APIs
- [x] 错误映射

### B4 权限 / 审计 / operation
- [x] project knowledge permission 定义
- [x] 上传/扫描/清空接 operation
- [x] 关键操作审计挂点

## Phase 3：platform-web-vue

### C1 模块与路由
- [x] 新增 `src/modules/knowledge/`
- [x] 新增 knowledge service / types / composables
- [x] 路由组接入 `documents/retrieval/graph/settings`

### C2 Documents
- [x] 上传入口
- [x] 分页列表
- [x] track status
- [x] pipeline status
- [x] 删除 / 清空

### C3 Retrieval
- [x] query 表单
- [x] 结果 / 引用展示
- [x] 空态 / 错态 / loading

### C4 Graph
- [x] label search
- [x] 子图展示
- [x] 属性面板
- [x] 基础布局 / 缩放交互

### C5 Settings
- [x] 默认知识空间摘要
- [x] workspace 映射摘要
- [x] 服务状态 / 运行说明

## Phase 4：联调与验收

- [x] repo 内自动化证据已刷新（platform-api-v2 knowledge / operations targeted pytest、platform-web-vue vitest/build/lint、LightRAG workspace suite）
- [x] project A/B 隔离联调
- [x] platform-api-v2 facade smoke test
- [x] platform-web-vue 页面 smoke test
- [x] 验收清单逐项勾完（当前第一阶段 gating 项已完成；后续阶段项继续保留在 Phase 5 / 验收清单第 7 节）

## Phase 5：后续阶段（当前不执行）

- [ ] 多知识库绑定设计重开
- [ ] 共享知识库设计重开
- [ ] LightRAG MCP 正式化设计
- [ ] runtime-service MCP 接入设计
