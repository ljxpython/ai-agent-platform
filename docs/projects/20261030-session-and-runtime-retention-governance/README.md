# 会话与运行时数据生命周期治理

- 启动日期：2026-10-30；级别：治理改动；模板：标准模板。
- 状态：已完成（done，8/8 任务；Phase与Final核验通过）。
- 人工评审：2026-10-30 用户同意 GraphHarbor 承担通用 TTL/可靠删除，平台定义业务规则；同意 Workspace 随会话删除、取消额外七天等待及此前风险修正。后续已授权提交、推送并合并主工作区；未部署生产服务。
- 导航：[方案](plan.md) · [任务](tasks.md) · [验证](verification.md) · [实现记录](implementation/01-platform-runtime-retention.md) · [维护手册](../../runbooks/session-retention-maintenance.md)
- 开发 Worktree：`/Users/lijiaxin/.codex/worktrees/retention-governance/ai-agent-platform`；环境 `wt_5642ffa8be9a` 已停止并销毁，Worktree 已清理。
- GraphHarbor 项目：`/Users/lijiaxin/PyCharmMiscProject/graphharbor/docs/projects/20261030-thread-retention-lifecycle/`。

目标：连续 30 天无用户主动查看或发送的会话自动删除；手动与自动删除共用可靠流程，确认资源释放后立即回收 Workspace，安全处理关联事实和幂等凭证。

GraphHarbor 双包正式 `0.13.0.post48` 已发布、冷安装验收并接入本 Worktree。三服务真实链路 13 项、浏览器真实模型 5 项及相关回归通过，证据见验证记录。功能提交 `5635e621` 已推送功能分支并快进合并主工作区 `main`；专属服务、数据库、Redis、Workspace 和 Worktree 已清理，生产服务尚未部署，Linux systemd 模板仅静态核验。
