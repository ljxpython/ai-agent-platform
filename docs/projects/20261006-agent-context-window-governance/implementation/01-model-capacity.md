# 模型容量目录与受信连接

实施日期：2026-10-06 至 2026-10-07。对应 B01、B02。

## 实现

- `apps/platform-api/src/platform_api/modules/runtime_catalog/domain/models.py` 的 `RuntimeModelCreate/RuntimeModelUpdate/RuntimeModelCatalogItem` 增加 nullable `context_window_tokens`，输入严格正整数；省略更新保留原值，null 清除。
- `application/ports.py::StoredRuntimeModel`、`infra/sqlalchemy/models.py::RuntimeCatalogModelRecord`、`repository.py::_to_runtime_model/create_configured_model` 贯通容量。既有 `update_configured_model` 已使用 payload 的明确字段更新，不复制新更新分支。
- `application/service.py::_model_item/resolve_model_connection` 以及内部 HTTP 的 model-config 返回容量。凭据保持只在受信内部连接出现。
- `apps/platform-api/migrations/versions/20261006_0006_model_context_window.py` 在 revision `20260925_0005` 后只新增 nullable Integer，不 backfill。
- `apps/runtime-service/src/runtime_service/runtime/modeling.py::fetch_model_connection` 校验容量；`build_model` 统一调用 `_with_context_capacity`，覆盖本模型 profile 的 `max_input_tokens`，不修改官方模型全局 profile。

核心变化为 `model.profile = {**(model.profile or {}), "max_input_tokens": capacity}`；保持原输出上限和其他模型能力，摘要副本继承相同可信容量。

## 验证

- API 模型 CRUD/lifecycle 定向：16 passed；覆盖 null、非法类型和项目 BYOK 权限。
- Runtime modeling/Showcase tools 定向：27 passed；随后容量覆盖测试在组合测试中通过，确认新 gpt-4o 实例仍为官方 128000 profile。
- `tests/integration/test_context_offloading_migration.py`：独立 PostgreSQL 16 库 upgrade/downgrade/re-upgrade 1 passed，23.58s；存量容量初始 null，原密文及作用域保留。

上述为 Phase 结果，后续真实 HTTP/Worker 与前端联合验收独立记录。
