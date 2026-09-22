# 平台公共模型与项目私有模型 (BYOK) 双层架构落地记录

- **日期**：2026-09-22
- **关联 ADR**：`docs/decisions/20260922-byok-project-model-architecture.md`
- **涉及服务**：`apps/platform-api`, `apps/platform-web`

---

## 1. 背景与目标
解决平台早期中心化管控模型凭据带来的“部分凭据未配置”假报警及项目普通使用者无法自主接入私有模型 Key 的矛盾。构建“平台公共模型托管池”与“项目私有模型 (BYOK)”双层治理体系。

## 2. 后端落地 (Phase 2)
1. **Alembic 迁移**：
   - 文件：`apps/platform-api/migrations/versions/20260922_0004_model_byok_scope.py`
   - `runtime_catalog_models` 表扩展 `scope_type` (VARCHAR(16)) 与 `project_id` (UUID, 外键)。
   - 增加 `ix_runtime_catalog_models_scope_project` 复合索引。
   - SQLite 批处理显式外键约束名 `fk_runtime_catalog_models_project_id`，支持 SQLite 与 PostgreSQL 兼容。
2. **数据与实体映射**：
   - `RuntimeCatalogModelRecord`、`StoredRuntimeModel`、`RuntimeModelCatalogItem`、`RuntimeModelCreate` 均包含 `scope_type` 与 `project_id`。
3. **仓储与业务逻辑 (RBAC)**：
   - `SqlAlchemyRuntimeCatalogRepository`：项目视图联合查询 `(scope_type == 'platform') OR (scope_type == 'project' AND project_id == target_project_id)`。
   - `RuntimeCatalogService`：
     - 公共模型管理需 `PLATFORM_MODEL_WRITE`。
     - 私有模型创建/更新/删除需 `PROJECT_RUNTIME_WRITE`。
     - 拦截跨项目私有模型篡改（403 `ForbiddenError`）。
     - 修复项目视图公共模型脱敏逻辑：保留真实 `credential_configured`，隐藏公共 `base_url`。
4. **运行时网关代理**：
   - `RuntimeGatewayService`：按项目上下文放行有效私有模型及平台授权模型，拦截跨租户伪造模型引用。
5. **API 端点**：
   - `POST /api/runtime/models`、`PATCH /api/runtime/models/{model_id}` 支持传入作用域与项目。
   - `DELETE /api/runtime/models/{model_id}` 支持私有模型自主物理删除。

## 3. 前端落地 (Phase 3)
1. **数据契约与接口服务**：
   - `types/management.ts`：`RuntimeModelItem` 扩展 `scope_type` 与 `project_id`。
   - `services/runtime/runtime.service.ts`：`RuntimeModelInput` 支持作用域，新增 `deleteRuntimeModel` 服务方法。
2. **中转站卡片交互 (`ProviderStationCard.vue`)**：
   - 卡片头部区分「私有 BYOK」与「平台托管」标签。
   - 凭据指示器区分「私有凭据已配置/未配置」与「平台托管就绪/待配置」，彻底消除假警报。
   - 表格凭据列同步根据作用域智能呈现。
3. **模型编辑抽屉 (`RuntimeModelEditor.vue`)**：
   - 支持 `scopeType` 动态标题（“添加项目私有模型 (BYOK)” vs “添加全局平台模型”）。
   - 保留各主流大模型预设与推荐清单。
4. **项目模型主页面 (`RuntimeModelsPage.vue`)**：
   - 顶栏增加「+ 添加私有模型 (BYOK)」快捷入口（具备 `project.runtime.write` 权限可见）。
   - 项目视图结构化拆分为两大独立板块：
     - **项目私有模型 (BYOK)**：显示团队自建模型，支持查看、编辑、设为项目默认及删除模型（带二次确认 Dialog）；无私有模型时展示引导卡片。
     - **平台公共模型**：显示平台标准化底座，支持项目授权与设为默认，隐藏运维敏感配置项。
   - 保留平台管理视图（`/workspace/models`）全局中转站管理体验。
   - 新增模型删除确认弹窗 (`BaseDialog`)，提供危险操作防御。

## 4. 验证结果
- `apps/platform-api/tests/test_byok_model_lifecycle.py`：5 passed。
- `apps/platform-api` 单元测试：231 passed, 13 skipped, 0 failed。
- `apps/platform-web` 单元测试：84 test files, 320 passed, 0 failed。
- `apps/platform-web` 类型检查与生产打包：`vue-tsc --noEmit && vite build` 0 errors 通过。
- `apps/platform-web` 代码规范检查：`eslint` 0 errors 通过。
- 本地微服务栈健康检查：runtime-api, runtime-worker, platform-api, platform-web 均 200 OK。
