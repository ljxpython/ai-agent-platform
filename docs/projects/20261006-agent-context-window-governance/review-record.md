# 人工评审记录

## 评审时间

2026-10-06

## 评审结论

用户确认方案通过，授权开始实施后端与 Runtime 范围；前端 F01–F03 交由同事按 `frontend-handoff.md` 实施。本轮继续推进直到只剩前端事项，除非出现真实阻塞。

## 已冻结决策

- 容量只来自受信模型目录/内部连接；容量或输出预算未知时在模型调用前报明确错误。
- Context 升级到 `runtime-context/v5`，手动维护使用 `config.configurable.platform_runtime.offload_conversation`。
- 公共状态只暴露有界整理状态，私有摘要、路径、内部会话标识和内部事件不得出现在公共 state、history、JSON 或 SSE。
- 手动维护必须通过现有 Run/command 入口，执行前检查 Thread、权限、空输入、并发、审批、待发消息和资源状态；最终并发仍由 GraphHarbor 裁决。
- 手动维护只进行摘要，不执行正常回答、工具、MCP、子 Agent、队列 claim 或记忆副作用。
- 采用 nullable migration 和 feature flag；回滚保留历史/checkpoint，不删除数据，先完成隔离环境迁移回退演练。

## 未授权范围

- 不修改 GraphHarbor、前端源码或新增外部存储。
- 不将参考项目中的 GitHub/Slack/Linear、sandbox provider 等业务逻辑带入本项目。
