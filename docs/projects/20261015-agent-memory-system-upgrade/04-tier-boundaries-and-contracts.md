# 记忆系统架构升级 - 04 三层架构职责边界与契约打通

## 1. 目标与背景

当前平台严格遵循三层解耦架构：
```
[ platform-web (前端) ] ──> [ platform-api (控制面后端) ] ──> [ runtime-service (执行引擎) ]
```
在借鉴参考 DeerFlow 的设计时，必须严格区分：哪些是 DeerFlow 的单体/本地化特定逻辑，哪些是符合我们微服务分层范式的核心能力。严禁跨层越权，严禁在错误的层级引入冗余业务或重复造轮子。

本专题目标：
明确前端（`platform-web`）、控制面后端（`platform-api`）与执行引擎层（`runtime-service`）的边界裁决，明确"哪些要做"、"哪些坚决不做（略过）"，以及跨服务契约如何保持向下兼容。

---

## 2. 三层职责详细划分与裁决

### 2.1 运行时服务层 (`runtime-service`) —— 核心主战场 (90% 改动)

#### ✅ 需要做的事
1. **异步非阻塞提取派发**：改写 `MemoryContextMiddleware.aafter_agent`，引入后台非阻塞任务，释放主对话请求（见 01 专题）；
2. **Prescreen 成本门禁与确定性信号识别**：新建 `prescreen.py`，负责会话有效性过滤，大幅砍掉无效提取开销（见 01 专题）；
3. **检索器重构与 MMR 算法**：新建 `relevance.py`，改写 `MemoryStorage.context()`，实现 IDF 权重与多样性重排（见 02 专题）；
4. **Fact Dedup 与 Eviction 软淘汰**：新建 `eviction.py`，改写 `MemoryStorage.propose` 和 `_save`，实现容量自平衡与近重复合并（见 03 专题）；
5. **契约数据丰富化**：在 `MemoryStorage.view()` 输出中补充轻量级状态（如 `stats: { facts_count, candidates_count, prescreen_skip_count }`），便于控制面和前端感知。

#### ❌ 坚决不做（略过）的事
1. **不照搬 DeerFlow 的本地文件系统存储（FileMemoryStorage）**：DeerFlow 在本地写 Markdown + YAML front matter，在单机开发时方便，但在容器化集群中会遇到分布式锁与文件同步灾难。我们坚定保留 **PostgreSQL JSON Document + Advisory Lock + Revision CAS** 的权威存储底座。
2. **不照搬外部 RAG / 知识库混淆实现**：DeerFlow 把部分知识检索混入了 Memory 工具体系。我们平台拥有清晰的 MCP 知识库架构规范，Memory 只专注几千字符的高密度用户偏好/事实，长篇文档检索一律走 MCP，不将长文本知识塞进 Memory。
3. **不照搬多后端（Mem0/OpenViking/Honcho）适配层**：现阶段我们不需要集成第三方 SaaS 记忆服务，保持以内部自建的高性能内存算法+PG 存储为主，杜绝过度设计（YAGNI 原则）。

---

### 2.2 控制面后端 (`platform-api`) —— 安全网关与审计穿透 (5% 改动)

#### ✅ 需要做的事
1. **透传 Runtime 增强后的状态字段**：在 `LangGraphRuntimeGatewayUpstream` 与 `RuntimeGatewayService` 中，透传 Runtime 返回的 `stats`（容量健康状态、候选数量、预筛选统计），使前端能正常拿到数据。
2. **保持基于 Delegation JWT 的安全验签**：继续由 Platform API 根据用户登录态生成带有租户与项目上下文的受限 Delegation Token，维持微服务间的绝对安全隔离。

#### ❌ 坚决不做（略过）的事
1. **不建第二套记忆数据库表**：Platform API 严禁私自落库保存记忆事实或候选，所有权威数据归属于 Runtime PostgreSQL，Platform API 严格作为鉴权反向代理与审计记录器（DRY 原则）。
2. **不在 API 层做任何文本切词或算法提取**：计算密集型与模型相关操作全部由 Runtime 处理，API 层保持纯粹的 I/O 穿透。

---

### 2.3 平台前端 (`platform-web`) —— 体验与状态感知 (5% 改动)

#### ✅ 需要做的事
1. **容量状态由"硬报错"转变为"健康进度条"**：
   - 当前页面：若容量打满，操作直接弹红报错；
   - 改造后：在 [DearAgentMemoryPage.vue](apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue) 顶部增加轻量级容量进度条（如 `78/100 条`），当接近 100 条时展示提示文字："系统将自动平滑整理低频事实"，消除用户的打满焦虑。
2. **近重复合并与高置信度候选标签增强**：
   - 候选卡片支持显示增强标签（如"近重复已合并"、"置信度: 极高"），让用户在点击"采纳 (Accept)"时心里更有底。
3. **搜索交互防抖 (Debounce)**：
   - 搜索输入框增加 300ms 本地防抖，减少无效请求。

#### ❌ 坚决不做（略过）的事
1. **不搞 DeerFlow 复杂的用户画像与大盘图谱**：DeerFlow 在前端展示复杂的用户心理画像摘要等花哨功能，在实际企业协作中实用价值低。我们继续保持聚焦"生效事实"与"待审核候选"的双栏高能卡片布局，界面整洁清爽。
2. **不搞多格式导入导出解析器**：全量保留现有的追加式导入导出与文本恢复，不在前端增加复杂的第三方格式（如 Notion/Obsidian）转换逻辑。

---

## 3. 跨服务契约变更总结

### 对外 API: `GET /api/langgraph/dear/memory`
保持向后兼容，返回体 Payload 结构微调：
```json
{
  "schema_version": 1,
  "revision": 42,
  "epoch": 3,
  "automatic_candidates": true,
  "facts": [...],
  "candidates": [...],
  "stats": {
    "facts_count": 85,
    "candidates_count": 12,
    "capacity_status": "healthy",  // "healthy" | "near_capacity" | "evicting"
    "prescreen_skipped_total": 128
  }
}
```

---

## 4. 任务拆分

- [x] **Task 4.1**：Platform API 校验并透传 Runtime 新增的 `stats` 字段，确保数据直通前端。
- [x] **Task 4.2**：Platform Web 改造容量感知 UI，增加容量进度条与状态解释文案。
- [x] **Task 4.3**：端到端跨服务链路集成与契约测试验证。

---

## 5. 验证要求与记录

### 验证要求与实际结果
- **契约兼容性验证**：后端升级并增加 `stats` 字典后，现有前端与控制面网关契约完全兼容无报错；
  - `apps/runtime-service` 测试通过：`33 passed, 5 warnings`；
  - `apps/platform-api` OpenAPI 契约测试通过：`7 passed`；
  - `apps/platform-web` 单元测试通过：`5 passed`，类型检查通过：`vue-tsc` 0 错误。
- **全链路追踪与原子性**：三层架构分层清晰，Runtime 保留权威 PG 存储，API 保持 I/O 透传与 Token 验签，Web 感知容量健康度。

### 状态
已完成 (done)
