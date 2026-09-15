# 模型目录防重与项目单默认模型互斥策略

## 背景与问题
1. **模型目录同物理端点重复录入**：
   原有模型录入接口 `POST /api/runtime/models` 及数据库模型定义未设置针对 `(provider, base_url, model_name)` 的唯一性约束。自动化测试脚本或用户可重复创建相同物理端点和模型名称的记录，导致模型目录中堆积多个同名模型（如出现 15 个 `DeepSeek-V4-Flash`），引发资产歧义及运行时授权混乱。
2. **多默认模型冲突**：
   在更新项目模型策略接口 `PUT /projects/{project_id}/runtime-policies/models/{model_id}` 时，原有 `upsert_model_policy` 仅将指定模型的 `is_default_for_project` 设为 `True`，未将该项目下其他旧默认模型重置为 `False`。导致同一项目下可能存在多个模型被同时标记为默认模型，前端列表展示出多个 `✓ default` 徽标，违背默认模型唯一性语义。

## 变更内容
1. **项目默认模型互斥排他机制**（`apps/platform-api/src/platform_api/modules/runtime_policies/infra/sqlalchemy/repository.py`）：
   - 在 `upsert_model_policy` 中，一旦设置 `is_default_for_project=True`，先执行批量更新，将当前项目下其他所有记录的 `is_default_for_project` 重置为 `False`，保证单个项目任何时刻至多只有 1 个默认模型。
2. **模型目录端点防重校验**（`apps/platform-api/src/platform_api/modules/runtime_catalog/`）：
   - 在 `repository.py` 中新增 `find_model_by_endpoint_and_name` 查询；
   - 在 `service.py` 的 `create_model` 和 `update_model` 中，增加针对 `(provider, base_url, model_name)` 的重名检测，冲突时抛出 `ConflictError(code="duplicate_model")`；
3. **前端防重交互拦截**（`apps/platform-web/src/modules/runtime/components/RuntimeModelEditor.vue`）：
   - 在模型编辑/新增抽屉中增加校验：校验用户填写的 Model ID 在当前中转站已有模型中是否存在，以及批量添加行中是否有自身重复，若重复则实时拦截并给出友好错误提示；
4. **自动化测试防护与幂等性**：
   - 新增专项单元测试 `apps/platform-api/tests/test_model_catalog_and_policy_uniqueness.py`，覆盖防重拦截（409 Conflict）与默认模型互斥策略；
   - 优化 `apps/runtime-service/tests/services/dearflow_agent/test_platform.py`，在测试时优先复用已有的同端点模型，避免向数据库刷入脏数据。

## 涉及文件
- [MODIFY] `apps/platform-api/src/platform_api/modules/runtime_policies/infra/sqlalchemy/repository.py`
- [MODIFY] `apps/platform-api/src/platform_api/modules/runtime_catalog/infra/sqlalchemy/repository.py`
- [MODIFY] `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py`
- [NEW] `apps/platform-api/tests/test_model_catalog_and_policy_uniqueness.py`
- [MODIFY] `apps/platform-web/src/modules/runtime/components/RuntimeModelEditor.vue`
- [MODIFY] `apps/runtime-service/tests/services/dearflow_agent/test_platform.py`
