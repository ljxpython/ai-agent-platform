# Python 格式基线清理 - 整体方案

## 背景
代码规范自动化专项已接入变更文件门禁，但全仓 Python 仍有存量差异。直接启用全量 Ruff 会阻断无关提交。

## 目标
- 统一两个 Python 服务的 Ruff lint 与 format 配置。
- 清理现有诊断和格式差异，并记录必要的规则例外。
- 将 CI 从变更文件检查升级为全量 Python 检查。

## 方案设计

### Phase 1：基线与规则
固定 Ruff 版本、Python 目标版本和规则集合；按服务、目录、规则统计诊断。确认 migrations、scripts、tests 的策略。
核对 Ruff 配置实际来源（包括仓库外继承配置），限定自有 Python 文件；此前扫描包含 Markdown 代码块输出，297 不应直接视为 Python 文件数。以固定版本重新扫描结果作为验收基线。

### Phase 2：platform-api
分目录处理格式和 import 排序，再修复其余 lint 诊断。涉及行为的修复独立审查并运行相应测试。

### Phase 3：runtime-service
采用相同流程分批清理，保留每批的检查与测试证据。

### Phase 4：全量门禁
两个服务全量检查通过后，CI 启用全量 Ruff check 与 format check；pre-commit 继续只检查变更文件。

## 风险和依赖
- 大规模自动格式化会产生难审查的 diff，必须拆批。
- 部分 lint 诊断涉及行为，不能靠全局 ignore 消除。
- 规则例外和迁移文件策略需维护者评审。

## 链路影响
仅影响开发质量门禁，不改变 platform-web → platform-api → runtime-service 的运行契约。
