# Python 格式基线清理

## 项目概述
- **时间：** 2026-09-25 ~ 2026-09-28
- **目标：** 消除 platform-api 与 runtime-service 的 Ruff 诊断和格式差异，全量升级 CI 门禁。
- **模板类型：** 标准模板
- **状态：** 已完成（done）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证计划](verification.md)
- [实现记录](implementation/01-python-format-and-lint-cleanup.md)

## 改动范围
- **影响服务：** platform-api、runtime-service
- **改动级别：** 治理改动
- **治理成果（2026-09-28 最终验收）：**
  - `platform-api`：163 条历史存量 Lint 诊断全部清零；287 个 Python 文件全量规范格式化；325 项单测全绿。
  - `runtime-service`：152 条历史存量 Lint 诊断全部清零；287 个 Python 文件全量规范格式化；534 项单测全绿。
  - 全仓合计：**0 errors，574 files formatted**。
  - CI 门禁：在 `.github/workflows/ci.yml` 成功接入全量 Python 静态检查与格式门禁。

## 评审与排期
- **Phase 1（已完成）：** 2026-09-28 规则基线配置与假报错消灭。
- **Phase 2（已完成）：** 2026-09-28 platform-api 存量清理与行为审查。
- **Phase 3（已完成）：** 2026-09-28 runtime-service 存量清理与 baseline 对齐。
- **Phase 4（已完成）：** 2026-09-28 CI 全量门禁升级。

## 关键决策
1. **服务级自治（Per-Service Governance）**：前后端、Runtime、API 在架构与物理上完全独立，拒绝根目录大一统规则，分别在各服务的 `pyproject.toml` 内配置专属 `[tool.ruff]`。
2. **消灭框架级假阳性**：FastAPI 的 `Depends/Query/Body` 等是标准 DI 依赖注入语法，配置 `extend-immutable-calls` 彻底消除 `B008` 假报错。
3. **特定目录豁免**：`platform-api` 排除 `migrations` (Alembic)；`runtime-service` 排除动态注入的 `**/skills/**` 与沙箱执行代码。
4. **守住 Blame 与增量安全**：分批审查行为相关诊断（B023 循环闭包、B904 异常链、B017 盲目捕获），并结合各服务专属测试套件保证零业务回归。
5. **Re-export 符号保护机制**：对于纯 re-export 模块（如 `governance_storage.py`），显式声明 `__all__` 彻底避免自动工具误删导入。
