# Docs 文档导航

这份首页的目标很简单：

> 让你在进入 `docs/` 后，不需要靠记忆猜“先看哪份文档”，就能按当前 Harness Engineering 体系找到正确入口。

## 1. 如果你要实际开始做任务

优先读：

1. [Root AGENTS Routing Surface](../AGENTS.md)
2. [AI 执行系统当前标准](./standards/01-ai-execution-system.md)
3. [AI 执行系统使用指南](./ai-execution-system-usage-guide.md)

这 3 份回答的是：

- 先怎么判任务
- 先读哪份 leaf standard
- B1 / B2 / B3 怎么选
- 以后怎么给 AI 提需求

## 2. 如果你要理解为什么这么设计

再读：

1. [Harness Engineering 学习与实践总纲](./knowledge/01-harness-engineering-foundation.md)
2. [AITestLab Harness Blueprint](./knowledge/02-aitestlab-harness-blueprint.md)
3. [Harness Operating Model](./knowledge/03-harness-operating-model.md)
4. [AI 执行系统设计说明](./knowledge/04-ai-execution-system-rationale.md)

## 3. 如果你要理解当前项目总开发范式

读：

- [当前项目开发范式说明](./development-paradigm.md)

## 4. 如果你要启动 / 联调 / 部署

读：

- [本地开发说明](./local-dev.md)
- [环境变量矩阵](./env-matrix.md)
- [部署文档](./deployment-guide.md)
- [本地部署契约](./local-deployment-contract.yaml)

## 5. 如果你要看变更与提交规则

读：

- [提交与 Changelog 规范](./commit-and-changelog-guidelines.md)
- [更新日志](./CHANGELOG.md)

## 6. 你应该如何理解 docs 的分层

- [`standards/`](./standards/01-ai-execution-system.md)
  - 当前正式标准
- [`knowledge/`](./knowledge/01-harness-engineering-foundation.md)
  - 背景、理由、思想与蓝图
- 根目录说明文档
  - 启动、部署、环境、整体范式

一句话：

> 要“现在怎么做”，先看 `standards`；要“为什么这样做”，再看 `knowledge`。
