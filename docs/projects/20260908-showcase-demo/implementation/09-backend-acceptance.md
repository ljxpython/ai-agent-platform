# 后端验收收尾

日期：2026-09-10。用户授权补齐后端验收，并提供包发布凭据位置，允许必要的配套依赖发布。

## 本轮范围

- `tests/services/showcase_demo/test_agent.py`：两个并行子 Agent 同时中断，按 ID 批准一个、拒绝另一个，检查真实文件副作用。
- `scripts/showcase_acceptance.py`：专用 PostgreSQL/Redis、正式鉴权、真实模型、独立 API/Worker；在修改审批时重启两进程，继续批准执行并独立检查报表和回归脚本。
- GraphHarbor 执行适配：通过官方 `context=` 参数传入 Context；普通调用与流式调用均覆盖中断恢复测试。
- GraphHarbor 状态接口：通过官方 `aget_state/aget_state_history` 还原增量通道、待执行节点和审批；Worker 持久化实际 graph ID 供状态读取。

## 验收中发现的问题

1. 原版 `0.13.0.post20` Worker 只在 config 中保存 Context，执行时没有传到 LangGraph Runtime；真实 Run 被正确的 Context 哈希校验拒绝。
2. 状态接口直接读取 checkpoint 底层 channel_values，遗漏 DeepAgents 增量保存的 messages。
3. 普通创建的 Thread 未记实际 graph ID，无法选择图来还原状态；补在已验证运行上下文的 Worker 领取阶段。

没有在 Demo 中增加依赖兼容补丁，也没有放宽鉴权。发布从 PyPI 的 post20 源码包生成隔离目录，只加入上述修复和测试；不打包 GraphHarbor 工作区中的其他未提交修改。

## 验证与发布

完成。框架完整回归 145 passed / 15 skipped（外部对照项），mypy、lint、format、构建和版本门禁通过；runtime-service 安装 post21 后 152 passed。最终 wheel 与 PyPI 安装版本分别通过真实模型/API/Worker 重启恢复验收。两个包已锁步发布 post21，四份产物哈希一致，应用 pyproject.toml/uv.lock 同步。结构化证据和命令统一见 verification.md。
