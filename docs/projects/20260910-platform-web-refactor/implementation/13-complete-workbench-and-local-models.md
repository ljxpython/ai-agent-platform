# 完整旧工作台恢复与本地模型链路修复

> 后续用户要求直接复制旧前端，最新组件还原和验证见 [14](14-copy-original-chat-components.md)。本文保留当时的实施范围与结果。

## 用户确认与范围

2026-09-11 用户指出 12 的视觉恢复不是目标版本，并明确要求重构前最后一版、包含高级模型选择器的完整工作台；同时授权将 `~/.my_best/.env` 的模型信息录入本地模型管理。12 的测试仅覆盖其记录场景，不能代表此次视觉产品要求及本地环境验收。

## 发现与改动

- 旧版基线为 Git `8056869` 的 Chat 工作台（最后一版高级模型选择器）。恢复历史侧栏/筛选、内嵌顶栏、专注模式、回复卡片、底部高级模型弹层，继续使用现有 SDK、审批、分支、队列逻辑。
- 模型选择使用当前模型 UUID；搜索、渠道分组和样式复用旧组件，模型管理链接对齐项目路由，保留键盘可操作性。
- 本地新库无模型、工具目录未同步；通过正式 API 录入配置、设置 `test` 项目默认模型、刷新工具目录。密钥只在内存中读取并由 API 加密存储，不写入代码、日志或文档。
- `reference_agent/agent.py` 仍读取旧 `_runtime_model_ref`，导致实际模型连接丢失并把 UUID 交给模型工厂。改为复用 `fetch_model_connection`，使用当前 `runtime_model_ref` 及其签名/权限校验。
- 本地 Runtime 库缺少 `runtime_message_inbox`，已执行现有幂等增量初始化；`local-stack.sh migrate/start` 补上业务 inbox 初始化，避免只迁移 GraphHarbor 引擎表。

## 已录入模型

DeepSeek 中转的 `DeepSeek-V4-Flash`、`qwen3.6-27b`、`MiniMax-M2.7`、`qwen3.6-35b-a3b`；GPT 中转 `gpt-5.6-terra`；豆包 `doubao-seed-1-6-vision-250815`；百炼 `qwen-plus`。百炼未指定默认模型名称，使用其模型目录中的常用聊天模型；未导入 embedding、音频、图像等非聊天模型。项目默认为 `DeepSeek-V4-Flash`。

## 状态与验收

`partial`：本地 Reference Agent、Workflow Demo 已实际回复，两个 Thread 刷新后回复保留；高级模型选择器键盘/搜索、专注模式和 390px 无横向溢出已验证。Reference 定向 11 passed，Chat 定向 21 passed / 1 skipped。最新三尺寸回归 2 passed / 1 failed：1024、390 通过，1440 在历史会话条目精确名称定位处超时，不能标记整套通过。

按用户要求重新逐项比较旧源码，发现 14 项功能/交互还原缺口，详见 [09 功能核对与补齐清单](../09-chat-workbench-restoration-audit.md)。后续以该清单逐项补齐，本记录不宣称完整工作台已恢复。
