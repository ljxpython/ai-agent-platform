# Python 格式基线清理

## 项目概述
- **时间：** 2026-09-25
- **目标：** 分阶段消除 platform-api 与 runtime-service 的 Ruff 诊断和格式差异。
- **模板类型：** 标准模板
- **状态：** 进行中（Phase 1 规则基线与服务自治已落地完成；Phase 2/3/4 待后续择机分批实施）

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证计划](verification.md)

## 改动范围
- **影响服务：** platform-api、runtime-service
- **改动级别：** 治理改动
- **诊断基线（2026-09-28 最新校准）：**
  - 在落地专属配置与豁免后，真实诊断数已大幅收敛：
    - `platform-api`：163 条（消除 282 处 FastAPI B008 假阳性，其中 143 项支持自动修复）
    - `runtime-service`：152 条（排除 skills/沙箱外部脚本干扰，其中 136 项支持自动修复）
    - 全仓合计：315 条（绝大部分为 isort 导入排序和 pyupgrade 语法升级，真实缺陷极低）

## 评审与排期
- **Phase 1（已完成）：** 2026-09-28 完成两个服务的规则基线配置与假报错消灭。
- **Phase 2 ~ Phase 4（规划中）：** 存量文件分批格式化与全量 CI 门禁切换待后续人工分批推进。

## 关键决策
1. **服务级自治（Per-Service Governance）**：前后端、Runtime、API 在架构与物理上完全独立，拒绝根目录大一统规则，分别在各服务的 `pyproject.toml` 内配置专属 `[tool.ruff]`。
2. **消灭框架级假阳性**：FastAPI 的 `Depends/Query/Body` 等是标准 DI 依赖注入语法，配置 `extend-immutable-calls` 彻底消除 `B008` 假报错。
3. **特定目录豁免**：`platform-api` 排除 `migrations` (Alembic)；`runtime-service` 排除动态注入的 `**/skills/**` 与沙箱执行代码。
4. **守住 Blame 与增量安全**：绝不一键格式化存量 261 个历史文件；存量文件按后续 Phase 2/3 分批拆解审查，当前由 `pre-commit` 针对增量变更实施秒级拦截守护。
