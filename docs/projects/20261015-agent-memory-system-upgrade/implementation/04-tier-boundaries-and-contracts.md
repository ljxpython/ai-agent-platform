# 记忆系统架构升级 - 04 专题实现记录：三层架构职责边界与契约打通

## 1. 改动背景与目标

在完成 Phase 1 (非阻塞 Prescreen)、Phase 2 (MMR 检索重排) 和 Phase 3 (容量自治与近重复合并) 后，平台已具备完整的企业级长期记忆引擎。
本专题聚焦跨层契约向下兼容与三层职责边界落地：
1. **Runtime Service**：在 `project_document()` 与 `envelope()` 中计算并输出 `stats` 字典（含事实计数、候选计数、容量健康状态 `healthy|near_capacity|evicting` 以及预筛跳过计数）；
2. **Platform API**：在 `MemoryDocumentView` 与 `MemoryView` 中定义 `MemoryStatsView`，透传 `stats` 字段，维持 Delegation JWT 验签；
3. **Platform Web**：定义 `MemoryStats` 接口并在 `DearAgentMemoryPage.vue` 中支持动态容量健康进度条、状态徽章与容量解释说明，消除用户对硬限制的打满焦虑。

---

## 2. 详细改动清单

### 2.1 运行时服务 (`apps/runtime-service`)
- **[memory.py](apps/runtime-service/src/runtime_service/services/dearflow_agent/memory.py)**：
  - 在 `project_document()` 中动态计算并注入 `stats` 结构；
  - 导出 `capacity_status`（<85 条为 `healthy`，85~99 条为 `near_capacity`，>=100 条为 `evicting` 平滑整理）；
- **[dear_memory.py](apps/runtime-service/src/runtime_service/http/dear_memory.py)**：
  - 在 HTTP 响应外层 `envelope()` 中挂载 `stats` 字典，确保跨层兼容。

### 2.2 控制面后端 (`apps/platform-api`)
- **[http.py](apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py)**：
  - 新增 Pydantic 模型 `MemoryStatsView`；
  - 在 `MemoryDocumentView` 与 `MemoryView` 中新增可选属性 `stats: MemoryStatsView | None = None`，保证序列化时字段完整向下透传。

### 2.3 平台前端 (`apps/platform-web`)
- **[memory.service.ts](apps/platform-web/src/services/dear-agent/memory.service.ts)**：
  - 新增 `MemoryStats` 接口定义，在 `MemoryDocument` 与 `MemoryView` 中加入 `stats?: MemoryStats | null`；
- **[DearAgentMemoryPage.vue](apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue)**：
  - 增加 `capacityRatio`、`capacityStatus`、`capacityStatusText`、`capacityBadgeClass`、`capacityBarClass` 计算属性；
  - 在事实卡片上方集成健康进度条与彩色状态徽标；
  - 增加超额平滑整理提示文案，提升用户交互体验。

---

## 3. 验证结果

1. **Runtime Service**：
   - 33 项单元测试全部通过：`33 passed, 5 warnings in 7.61s`；
2. **Platform API**：
   - 契约测试全部通过：`test_runtime_gateway_memory_contract.py` (7 passed)；
   - 路由测试通过：`test_runtime_gateway_memory.py` (1 passed, 1 skipped)；
3. **Platform Web**：
   - 单元测试全部通过：`memory.service.spec.ts` (5 passed)；
   - 类型检查通过：`vue-tsc --noEmit` 0 错误。
