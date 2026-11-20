# 长会话 Checkpoint 存储治理与 Delta 采用

用户持续聊天、运行工具和恢复审批，需要会话可读、执行可恢复，同时避免每个新Run重复复制整条历史。本项目接入GraphHarbor最小边界/撤销日志与引用安全GC，将Reference Agent和平台助手消息迁移为官方Delta状态，保留完整原文和idle30天。

**当前状态：已完成（done，P01–P07及本地main交付）。** 正式post49/head015、Delta消息与审批恢复、队列、故障、容量、真实浏览器及备份恢复已验证。合入main并行改动后33项和浏览器2项通过；迁回本地main后同提交隔离回归14项通过。原文及idle30天保持，无活跃自动裁剪；主工作区现役服务未切换。

## 项目信息与导航

- 启动日期：2026-11-20；级别：治理改动。
- 影响范围：runtime-service、platform-api，按验收需要涉及 platform-web。
- [整体方案](plan.md)：事实、边界、实施顺序、Delta 建议和数据切换。
- [唯一任务进度](tasks.md)：P01–P07。
- [验证计划与记录](verification.md)：阶段验证（Phase）与整体验收（Final）分开记录。

## 两仓职责与历史关系

[GraphHarbor 同名关联项目](../../../../graphharbor/docs/projects/20261120-checkpoint-storage-governance/README.md)维护通用运行边界、撤销日志、引用安全 prune/GC 和正式包任务 S01–S07。核心不得引入具体 Agent、模型、工具、Workspace、评测或业务期限；独立安装、测试和发布不依赖平台仓库。

本仓维护图的消息状态、业务保留政策、正式包接入和业务验收。跨仓链接仅供导航，两仓不复制任务进度。

[10 月 Delta 调研](../20261004-langgraph-v3-delta-evaluation/README.md)与[既有生命周期项目](../20261030-session-and-runtime-retention-governance/README.md)保留各自设计、任务与证据，本项目不向旧项目追加方案或接管旧验收。

## 授权与下一步

用户已同意基线放大和无引用 blob 修复方向、GraphHarbor 通用边界与单一新实现，并授权验证所需双包正式发布。新增实现不加旧格式双读、长期双写或 fallback；需保留的数据采用一次性转换并验证恢复。规划阶段不读密钥。

2026-11-21 用户明确平台开发方式：涉及本仓的代码、依赖和迁移改动，一律在独立 Worktree 开发，按[资源隔离规范](../../standards/worktree-development.md)配置所属环境。本次批准范围的功能与必要验收全部完成后，才通过 Git 合并迁回本地 main，并完成合并后回归。该要求覆盖本项目所需的平台 Worktree 开发与本地迁回；远端推送、现役部署和既有数据销毁仍无新增授权。具体准备与交付分别记在 P02、P07。

在用户开始全部实施的授权下，普通Agent按已说明的建议仅迁移消息channel，继续使用create_agent；活跃会话保持原文和现有闲置30天策略，不开启自动裁剪，不增设未批准的恢复点窗口。

反向JSON Patch投影和维护预算已由用户确认且通过。引擎Run边界最大330B，万条prune最大708.201ms；平台200轮消息周期50逻辑字节比普通快照少约70%，同时记录读取代价。教学Workflow仍为普通聚合，完整原文/固定周期快照不保证永久有界；严格官方等价及现役容量未验。

批准范围已完成，详细证据见verification。实现d460137、合入并行main的代码提交cff8feb3；旧规划安全备份、AGENTS修改保留。未推远端，未执行GraphHarbor Git或生产部署/迁移。
