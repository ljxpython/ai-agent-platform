# 本期用户验收与交付清理

2026-10-13；用户本期验收通过，并授权剩余问题后续处理、停本 Worktree 服务、Git 提交/推送/安全合并及 Worktree/所属数据库清理。关联 [G06/T15](../tasks.md)、[后续 F01–F04](../follow-ups.md)。本文件记录交付操作，不替代任务进度或原全矩阵独立 Final。

- [x] runtime-api、runtime-worker、platform-api、platform-web、所属 Redis 已停止；`local-stack.sh status` 五项均 stopped。
- [x] README/plan/tasks/verification/deerflow-reuse、FEATURES/CHANGELOG/运行手册统一本期 done、后续 deferred；不改写失败、unknown 或未经授权的整机重启证据。
- [x] 保全37份最小私有恢复资料到主工作区忽略目录，含3条原媒体回执、2份 retained 远端绑定、原/ fork 图片和节点凭据；图片 SHA256 与权限600/700通过，真实秘密不入 Git。
- [x] 精确核验 owner/comment/零连接后先删除独占回归库，再用标准 destroy 删除两个登记开发库与两个角色；三库/两角色及 `.local-stack` /登记均复查已释放。不停止共享 PG、不触及其他 Worktree。
- [ ] 提交并推送 `feat/runtime-remote-docker-sandbox`，核验源/MIT/秘密与 staged 范围。
- [ ] 在主工作区当前分支 `feat/langgraph-v3-delta-evaluation` 合并并推送；保留原 HEAD 历史和用户未提交的 `custom-chart-visualization.zip` 删除。
- [ ] 在所有 Git 与数据保全核验后移除本 Worktree，复核三库/角色/登记已释放。

主工作区与本 Worktree 初始 HEAD 同为 `06d941300948c17144dc862500e1bb58e92dcf86`；已 fetch，远端主工作区对应分支仍在相同提交。采用 Git 合并保持既有功能和历史，不通过整目录覆盖或 reset 更新主工作区；若主工作区期间出现新改动，合并前重新核对。

本期清理不删除 sshmy2 的持久工作区/Node 账本，不新增图片计费请求、不再次重启整机；含媒体修复的 Runtime 候选 wheel 未替换服务器已部署 Node 基线。

提交钩子的 Ruff/formatter 精确排除 `workspace/acquire_serialization.py` 与 `path_patterns.py`，防止原样复用模块被自动格式化；两个模块与完整 MIT 仍由来源 SHA256 核验，其调用方/契约测试照常验证。提交前184份文本对27个私有值扫描无泄漏。
