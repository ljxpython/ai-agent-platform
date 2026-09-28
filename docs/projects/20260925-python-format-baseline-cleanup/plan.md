# Python 格式基线清理 - 整体方案

## 背景
代码规范自动化专项已接入变更文件门禁，但全仓 Python 仍有存量差异。直接启用全量 Ruff 会阻断无关提交。

## 目标
- 坚持**服务级自治（Per-Service Governance）**原则，为独立部署与运行的各 Python 服务配置合身的 Ruff 规范。
- 消除框架级假阳性（如 FastAPI 依赖注入引发的 B008 报错），建立清晰真实的诊断基线。
- 渐进式分批清理存量格式与语法差异，避免大规模一次性提交破坏 git blame 与引发代码合并冲突。
- 最终在存量清理完毕后将 CI 平稳升级为全量检查。

## 方案设计

### Phase 1：基线与规则（已完成 - 2026-09-28）
- **架构决策：** 拒绝根目录统一 ruff.toml 覆盖，实施服务级自治配置。
- **配置落地：**
  - 分别在 `apps/platform-api/pyproject.toml` 与 `apps/runtime-service/pyproject.toml` 中配置专属 `[tool.ruff]`。
  - 核心规则集统一选用标准集：`E` (pycodestyle), `W` (warnings), `F` (Pyflakes), `I` (isort), `B` (flake8-bugbear), `UP` (pyupgrade)。
  - 忽略 `E501`（行宽由 formatter 全权管理，设置标准 88 字符）。
  - 配置 `[tool.ruff.lint.flake8-bugbear].extend-immutable-calls`，将 `fastapi.Depends`、`Query`、`Body`、`Header`、`Path`、`Security` 纳入不可变调用白名单，**彻底消灭 282 处 B008 伪错误**。
  - 目录豁免：`platform-api` 排除 `migrations`；`runtime-service` 排除 `**/skills/**` 与 `tests/acceptance_app`。
- **基准复核：**
  - `platform-api` 真实诊断收敛至 **163 条**（143 条可自动修复，其中未排序 import 占 107 条）。
  - `runtime-service` 真实诊断收敛至 **152 条**（136 条可自动修复，其中未排序 import 占 111 条）。
  - 两个服务各自 `uv run pytest` 单测 100% 保持通过。

### Phase 2：platform-api 存量分批清理（规划中）
优先按模块目录（`core/`、`modules/`、`entrypoints/`、`tests/`）处理自动修复项（import 排序 I001 与 pyupgrade UP），随后再人工审查处理少量手动诊断（如 B023 循环变量捕获等），并确保单测回归。

### Phase 3：runtime-service 存量分批清理（规划中）
按相同策略分批处理 `runtime_service/http/`、`runtime_service/services/` 与 `tests/`，保留每批执行证据。

### Phase 4：全量门禁升级（规划中）
两个服务存量清理全部归零后，在 CI（`.github/workflows/ci.yml`）中将 Python 检查由增量模式切换为全量 Ruff check 与 format check；本地 pre-commit 仍保留秒级增量守护。

## 风险和依赖
- 大规模自动格式化会产生难审查的 diff，必须拆批。
- 部分 lint 诊断涉及行为，不能靠全局 ignore 消除。
- 规则例外和迁移文件策略需维护者评审。

## 链路影响
仅影响开发质量门禁，不改变 platform-web → platform-api → runtime-service 的运行契约。
