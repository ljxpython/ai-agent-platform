# 后台任务接受回执接入与联合收口

- **启动日期：** 2026-10-11。
- **状态：** 已完成（`done`）；K01–K11 全部收口，前端修补、Playwright E2E 真实模型自动化闭环与三视口全景留痕通过，用户人工抽检验收通过。
- **模板类型：** 标准模板。
- **级别：** 治理级链路改动，涉及固定回执授权、持久请求、迁移合并和应用镜像。
- **目标：** 在主分支合并后的统一代码上，补齐后台任务 T01/T05/T08、T10/F12 的剩余门禁，使接受回执、通知续接、Stop 和撤权形成可验收的完整链路。
- **协作：** 主分支合并已完成；Codex 负责 Platform API、Runtime Service、测试与运维交付；前端同事负责必要前端修补与浏览器联合验收。

## 实施工作区

唯一实施目录：`~/.codex/worktrees/b01-closeout/ai-agent-platform`。用户确认 99f7 合并完成后，从集成分支 `feat/langgraph-v3-delta-evaluation` 的 `2b94585b` 创建 detached Worktree；来源后台提交已包含，未提交本轮修改、未部署现役。

独立环境 `wt_43727db9404e`，Web `http://127.0.0.1:29286`、API `http://127.0.0.1:23818`、Runtime `http://127.0.0.1:24548`、Redis 28816。独立依赖、PG、Redis、Workspace 与日志由 `scripts/local-stack.sh` 管理；故障 fixture 另建本 Worktree 内 disposable 服务。2026-10-11 交付检查时长期 Docker 栈已启动，API/Worker/Web/Redis 均运行、HTTP 入口均 200；本环境显式开启后台启动，仓库默认仍关闭。服务状态以本目录 `local-stack status` 为准。

f5a8 保留先前规划副本，99f7 为来源；均不能替代本目录验收代码。来源与三套 head 见 [baseline.md](baseline.md) 和 [实施记录](implementation/01-baseline-and-migrations.md)。

展开的绝对路径、正式包来源/hash、镜像、三套 head 与源码摘要见[实际产物清单](implementation/artifacts.json)。清单用于产物定位，进度仍以 tasks/verification 为准。

## 已有成果与剩余范围

| 层次 | 已核实的来源成果 | 本专项接续 |
|---|---|---|
| GraphHarbor | 接受回执专项 13/13、done，正式双包 `0.13.0.post45`；B01 已解除 | 消费正式版本和既有证据；不重复开发引擎 ledger/接口 |
| Platform API | `99f7` 已实现最终 bytes/key/digest 落盘、固定只读委托、acceptance adapter、reconcile-only | 已完成新执行 Context/签名、origin/callback 共存、迁移汇合/SQLite UUID 修复和故障/权限 Final |
| Runtime Service | `99f7` 已实现同 event 对账、原 Run 绑定、Stop suppressed、执行前 guard、A/B | 已恢复 credential/callback 接线、收窄自动候选，并完成 post45 Linux 镜像、资源、竞态与匹配版本回退 Final |
| Platform Web | `99f7` 的 F01–F11、ABF01–ABF03 已完成 | 修accepted文案、抑制候选和HITL/异步避让缺口，完成F12；只交接同事，无新接受回执页面 |

较新功能的合并核对与必要修补见 [baseline.md](baseline.md) 和 [完成续接修复](implementation/02-completion-context-and-merge-repairs.md)。

## 阅读顺序

1. [baseline.md](baseline.md)：来源、已完成事实、未提交改动和迁移分支风险。
2. [plan.md](plan.md)：三层职责、准确代码落点、协议、实施顺序和回退。
3. [tasks.md](tasks.md)：11 项可执行任务与依赖，进度唯一事实源。
4. [verification.md](verification.md)：18 项接续门禁、原专项矩阵映射、Phase/Final 记录。
5. [frontend-handoff.md](frontend-handoff.md)：前端必要事项、验收、联调条件与可转发话术。

`implementation/` 记录本次补丁和证据；进度只看 tasks，最终结果只看 verification。

## 范围约束与完成条件

- 延续已批准的后台任务与 A 主方案+B 精确兜底；不实现 LocalBackgroundRunner，不扩大生产执行拓扑，不把固定只读权限扩为通用 read。
- 首版沿用受管 Docker execution host、原控制 daemon、稳定 host ID 和共享挂载。新提交保持默认关闭，真实验证只在所属隔离环境显式启用。
- 本专项不自动部署现役、发布镜像或提交 Git。产物构建和运行验证完成后，正式启用仍需单独部署决定。
- K01–K08 完成后可报告“非前端范围完成”；整项目只有 K09–K11 与全部适用门禁完成才 `done`。前端等待不阻止独立后端工作继续推进。
- 引擎 `accepted` 只证明创建事务接受；任务执行、资源清理、完成 Run 执行、用户收到通知分别取证。

## 与原专项关系

来源为 `docs/projects/20261009-agent-generic-production-capabilities/`；当前目录保存**剩余工作**，不替代其已批准设计、历史失败和 Phase 证据。主分支合并后 K01 核对原 T01/T05/T08/T10、F12 并建立双向导航。原任务在对应新任务实际通过后回填完成状态，不以创建本专项解除验收门禁。

当前没有 Block；B01 保持解除，原 T01/T05/T08 已由本轮非前端 Final 回填完成。K09/K10 是用户指定交给前端同事的剩余任务，现役部署另行决定。报告哈希、Run/Task 与副作用计数见 [脱敏证据](implementation/final-evidence.json)，准确修补点与话术见 [前端交接](frontend-handoff.md)。

## 实施登记（2026-10-11）

用户确认99f7已合并并授权实施。唯一实施目录为 `~/.codex/worktrees/b01-closeout/ai-agent-platform`，基线 `2b94585b`，独立环境 `wt_43727db9404e`。原 f5a8 仅保留规划副本，不作为验收代码。K01/K02 已验证，后续状态以 tasks 为准。
