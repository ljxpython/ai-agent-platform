# Worktree 本地联调资源隔离

- **启动日期：** 2026-10-10
- **模板类型：** 标准模板
- **改动级别：** 治理改动（本地开发资源生命周期与 AI 工作流）
- **状态：** 已完成（`done`）；T01-T07 全部验收，包含配置与主工作区基础数据复用，2026-10-10。
- **目标：** 多个 Worktree 并行运行独立联调环境，统一分配、登记、检查和停止资源。
- **人工评审：** 用户于 2026-10-10 批准资源隔离方案，并追加要求默认 `admin / admin123`、继承 app `.env`、复用主库基础数据；源库只读、仅写新环境，范围见 [方案](plan.md)。

## 导航

- [方案与评审记录](plan.md)
- [任务与验收条件](tasks.md)
- [验证记录](verification.md)
- [Worktree 开发规范](../../standards/worktree-development.md)

## 范围

复用 `scripts/local-stack.sh`，补充本地环境登记/初始化、独立 PostgreSQL 数据库与角色、独立 Redis、Workspace/PID/日志隔离、依赖缓存复用和 Playwright 地址接线。新环境默认管理员为 `admin / admin123`，继承 app 环境配置，首次启动只读复制主库基础数据并排除历史。同步 AGENTS、开发指南和本地部署契约。主工作区保留默认地址和已有数据；不改业务 API、生产部署、依赖版本。实施与验收阶段未执行 Git 提交或分支操作；用户随后明确要求单独提交本地栈基线。

## 已有 Worktree 同步

2026-10-10 已将下列 31 个文件的本地栈相关改动同步到 7 个已有 Worktree：`3afa`、`7105`、`7604`、`99f7`、`aa74`、`abc6`、`b646`。逐目录应用补丁并校验，保留各目录已有业务改动、Git index 和 HEAD；未执行这些环境的 `init/deps/start`。

同步记录、逐目录补丁和原文件备份保存在主工作区的 `.local-stack/tooling-sync/`，该目录不入 Git。私有 `.env`、运行状态、数据库、Workspace、依赖目录未参与同步。

### 完整文件清单（31 个）

| 分类 | 数量 | 用途 |
|---|---|---|
| 运行与验证脚本 | 8 | 环境登记、资源启停、基础数据复制和回归验收 |
| E2E 配置 | 2 | 浏览器测试读取所属 Worktree 的地址和私有配置 |
| 仓库入口与忽略配置 | 3 | 引导开发者和 AI 阅读规范，排除私有运行状态 |
| 规范、指南与索引 | 10 | 使用规则、配置契约、经验及功能状态 |
| 专项文档与证据 | 8 | 方案、任务、实施和实际验收结果 |

```text
scripts/local-stack.sh
scripts/local_stack_processes.py
scripts/local_stack_worktree.py
scripts/local_stack_seed.py
scripts/test_local_stack_backend.py
scripts/test_local_stack_worktree.py
scripts/test_local_stack_seed.py
scripts/verify_worktree_local_stack.py
apps/platform-web/playwright.config.ts
apps/platform-web/e2e/support/platform.ts
.gitignore
AGENTS.md
README.md
docs/standards/worktree-development.md
docs/standards/README.md
docs/guides/local-dev.md
docs/guides/deployment-guide.md
docs/guides/env-matrix.md
docs/local-deployment-contract.yaml
docs/lessons/ai-workflow.md
docs/lessons/index.md
docs/FEATURES.md
docs/CHANGELOG.md
docs/projects/20261010-worktree-local-stack/README.md
docs/projects/20261010-worktree-local-stack/plan.md
docs/projects/20261010-worktree-local-stack/tasks.md
docs/projects/20261010-worktree-local-stack/verification.md
docs/projects/20261010-worktree-local-stack/implementation/01-native-stack-isolation.md
docs/projects/20261010-worktree-local-stack/implementation/02-config-and-baseline-data.md
docs/projects/20261010-worktree-local-stack/evidence/native-three-stacks.json
docs/projects/20261010-worktree-local-stack/evidence/native-three-stacks-baseline.json
```

`docs/CONTEXT.md` 是各工作区自己的状态快照，未覆盖目标 Worktree 的版本。用户批准的本次当前分支基线提交包含上述 31 个文件和主目录快照，共 32 个文件；共用文档仅提交本地栈相关段落，其他业务功能继续保持原有状态。新 Worktree 应从含此基线的提交创建。
