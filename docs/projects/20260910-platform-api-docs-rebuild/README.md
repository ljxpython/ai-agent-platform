# Platform API 文档重建

- **日期：** 2026-09-10
- **目标：** 以已验收代码为依据，重建简洁、可执行、不会误导后续开发者的 Platform API 文档。
- **负责人：** @lijiaxin
- **级别：** 治理改动（开发规范与事实来源治理，不改变产品契约）。
- **状态：** done；2026-09-10用户批准后完成10篇活文档、28文件归档与必要验证；后续按用户授权修复全仓24处个人路径，文档检查已通过。
- **代码基线：** `a3e65da`，已推送 `origin/feat/platform-web-chat-redesign`。
- **前置：** [平台后端重构](../20260910-platform-api-refactor/README.md)本阶段 done；前端/浏览器、整套容器部署和 Server 完整等价性仍 deferred。

## 阅读顺序

1. [方案与逐项处置](plan.md)：现状证据、目录、职责和旧文件去向。
2. [任务](tasks.md)：实施顺序与交付范围。
3. [验证](verification.md)：文档、源码、命令与验收状态的一致性要求。

## 建议决策

1. 保留 handbook 与 standards；把运维和数据库说明收进 handbook，移除独立 delivery 分类。
2. 活文档每个主题只有一个正文来源；服务 README 负责快速启动，docs README 负责导航，工程目录保留实施过程和证据。
3. 复用已经更新的三份 handbook，不把所有文档一律推倒重写；清理过时正文，不能继续在开头加免责声明后保留错误规则。
4. 旧阶段清单、被替代的决策和旧图进入 archive；仅因阶段结束而仍有效的文档不归档。
5. 不增加文档站、生成框架或每模块模板；用户已批准，按方案实施重写与归档。

## 完成记录

[实施记录](implementation/01-docs-rebuild.md) · [验证与限制](verification.md) · [新的文档入口](../../../apps/platform-api/docs/README.md)。
