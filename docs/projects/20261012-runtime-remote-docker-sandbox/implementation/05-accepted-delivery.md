# 本期用户验收与交付清理

2026-10-13；用户本期验收通过，并授权剩余问题后续处理、停本 Worktree 服务、Git 提交/推送/安全合并及 Worktree/所属数据库清理。关联 [G06/T15](../tasks.md)、[后续 F01–F04](../follow-ups.md)。本文件记录交付操作，不替代任务进度或原全矩阵独立 Final。

- [x] runtime-api、runtime-worker、platform-api、platform-web、所属 Redis 已停止；`local-stack.sh status` 五项均 stopped。
- [x] README/plan/tasks/verification/deerflow-reuse、FEATURES/CHANGELOG/运行手册统一本期 done、后续 deferred；不改写失败、unknown 或未经授权的整机重启证据。
- [x] 保全37份最小私有恢复资料到主工作区忽略目录，含3条原媒体回执、2份 retained 远端绑定、原/ fork 图片和节点凭据；图片 SHA256 与权限600/700通过，真实秘密不入 Git。
- [x] 精确核验 owner/comment/零连接后先删除独占回归库，再用标准 destroy 删除两个登记开发库与两个角色；三库/两角色及 `.local-stack` /登记均复查已释放。不停止共享 PG、不触及其他 Worktree。
- [x] 提交并推送 `feat/runtime-remote-docker-sandbox`，实现提交 `6472d0d828f7865d04ee5a72817dc442cf9e8e51`；源/MIT/秘密与 staged 范围核验通过。
- [x] 在主工作区当前分支 `feat/langgraph-v3-delta-evaluation` 快进合并并推送至同一实现提交；保留原 HEAD 历史和用户未提交的 `custom-chart-visualization.zip` 删除。
- [x] 在 Git 与数据保全核验后移除本 Worktree；目录和 Git Worktree 登记均复查不存在，三库/两角色/本地栈登记已释放；其他 Worktree 保留。

主工作区与本 Worktree 初始 HEAD 同为 `06d941300948c17144dc862500e1bb58e92dcf86`；实现提交已推送到两个远端分支。采用 Git 快进合并保持既有功能和历史，不通过整目录覆盖或 reset 更新主工作区；核验2654个未改动原文件的 Git 对象一致、原有受控路径删除数为0，平台 API/Web 产品源码无专项差异。移除 Worktree 前已确认无未提交或未跟踪源码，剩余仅所属依赖/构建/测试缓存；后续最小恢复资料留主工作区忽略目录。

本期清理不删除 sshmy2 的持久工作区/Node 账本，不新增图片计费请求、不再次重启整机；含媒体修复的 Runtime 候选 wheel 未替换服务器已部署 Node 基线。

提交钩子的 Ruff/formatter 精确排除 `workspace/acquire_serialization.py` 与 `path_patterns.py`，防止原样复用模块被自动格式化；两个模块与完整 MIT 仍由来源 SHA256 核验，其调用方/契约测试照常验证。初步184份文本对27个私有值扫描无泄漏；最终 staged 187份文本对17个实际私有值核验，凭据文件路径单独分类，无秘密或私钥泄漏，203份受控改动/原路径删除0，八项 pre-commit 全通过。
