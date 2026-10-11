# 全场景本地原生资源优先与严禁滥用 Docker 规则固化

## 背景

在日常开发、测试与 Worktree 联调中，部分 AI 或开发者容易误以为需要启动 Docker 容器运行数据库或 Redis，导致开发机内存暴涨、磁盘 IO 骤降以及网络调试摩擦。
虽然底层脚本（`local-stack.sh`）、Worktree 规范（`worktree-development.md`）和非 Docker 部署手册均以宿主机原生基础设施为基准，但在协作入口 `AGENTS.md` 顶层缺乏显式红线约束。经用户批准，正式将“本地原生资源优先”提升为全场景通用的顶层硬约束。

## 改动

### AGENTS.md

1. **升级本地资源与 Worktree 联调章节**：
   - 明确「本地资源优先原则」全场景适用（无论是主工作区还是关联 Git Worktree）；
   - 规定日常开发、测试与联调必须优先使用宿主机本地原生的 PostgreSQL 与 Redis 服务，智能体执行默认走 `RUNTIME_BACKEND=local`；
   - 明确 Docker 的唯三例外：容器沙箱需求（如不可信代码执行）、特定专属工具镜像（如 F10 文档解析 reader）、或最终镜像构建验收；其余场景严禁擅自引入 Docker 容器增加负担；
   - 极简规定模型调用与测试优先使用 miaomiaoai 的 DeepSeek 模型（`deepseek-v4.1-flash`），作为单一事实源便于后续一键切换。
2. **扩充严禁行为（第 7 条）**：
   - 新增：`❌ 不得在没有沙箱隔离明确需求时擅自引入或依赖 Docker（数据库、Redis 与应用开发必须优先走宿主机本地原生资源）`。

## 影响文件

- `AGENTS.md`
- `docs/CONTEXT.md`
