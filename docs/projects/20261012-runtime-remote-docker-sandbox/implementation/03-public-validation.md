# 公网恢复与剩余联合验收

2026-10-13 用户确认服务器已放开 19111，并授权继续实施；批准沉淀“容器与数据分开回收、远端不能只改 DOCKER_HOST”。

- 正式 Node 客户端从当前 Runtime 开发机经公网 HTTPS+mTLS 请求 sshmy2 readiness 成功（0.108s），证据见 [public-readiness.json](../evidence/public-readiness.json)。此前 B01 的公网连接超时已解除，后续业务与安全验收仍须逐项通过。
- 两条经验已写入 [Runtime 经验库](../../../lessons/runtime-service.md)，索引条数从 14 更新至 16。用户已批准，无须再次请求确认。
- deer-flow 两个原样模块位于 `apps/runtime-service/src/runtime_service/workspace/acquire_serialization.py` 与 `path_patterns.py`；完整 MIT、固定提交和 SHA256 位于同目录 `third_party/deerflow/`，此次重新核验与来源记录一致。
- 恢复工作时所属 local-stack 五个服务均已停止，先按 Worktree 登记配置启动原生资源与 local 基线；未假定上一轮服务仍存活。

任务进度以 [tasks.md](../tasks.md) 为准；本记录不替代剩余 T12–T15 或完整 Final。
