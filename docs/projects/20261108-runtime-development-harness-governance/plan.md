# Runtime Agent 开发指南 - 整体方案

## 需求与范围调整

用户澄清：本次目标是帮助其他人在 runtime-service 下开发符合当前规范的 Agent，说明如何设计、如何开发、模块架构、规则和要求，以及该读哪些文档、参考哪些案例、查询哪些资料。用户已同意入口纠偏。

据此，本期重写开发指导和资料路由，不实施之前偏离目标的 GitHub Actions CI 接入、检查器扩展或全仓 Harness 重构；不新建服务 AGENTS 或修改项目 Skills。源码及现有权限契约保持原状。

## 为什么需要重写开发指导

现有规则有价值，但尚未形成从设计到交付的连续教程：

- 应用 README 仍用 R0～R6 描述总体开发现状，文档首页先列 17 篇历史设计，当前规范入口靠后。
- 开发规范混合通用要求和具体能力细节，缺少新 Agent 的类型选择、目录职责和逐步接入说明。
- 案例用途混在一起。小 Demo 展示单项机制，不能作为完整平台接入模板；Showcase 和 DearFlow 功能完整，但整包复制会引入无关能力。
- 案例 README 本身有过时表述：Showcase 仍写未进入生产配置和 post26；reference 的说明仍以早期接线为主。案例应同时定位当前源码和测试，不能只链接 README。
- Graph 实际注册经过 graphs 层；DearFlow/Showcase 的入口还有调度和后台完成包装。新增图也需检查 capability/tool catalog 等接入点，不是只改 langgraph.json。
- 当前规范与历史 Draft 不等价；官方文档的最新 API 也不等于本地锁定版本。

## 文档分工

| 文件 | 本期调整 | 回答的问题 |
|---|---|---|
| apps/runtime-service/README.md | 修正当前介绍、Graph 路径和开发导航，历史章节标明范围 | 从哪里开始 |
| apps/runtime-service/docs/README.md | 重写入口，把当前开发路径放在历史资料之前 | 文档怎么读 |
| apps/runtime-service/docs/standards/README.md | 区分主指南、规则、专题、证据与历史资料 | 哪些具有约束力 |
| apps/runtime-service/docs/standards/runtime-agent-development-guide.md | 新建完整 Agent 开发指南 | 怎样设计、怎样实现、怎样交付 |
| apps/runtime-service/docs/standards/runtime-service-reading-guide.md | 重写为必读/案例/按需专题/官方资料地图 | 看哪个案例、查什么资料 |
| apps/runtime-service/docs/standards/runtime-service-development-standard.md | 保留既有细节约束，只修正文档入口与 Graph 路径说明 | 必须守住哪些规则 |
| apps/runtime-service/docs/standards/runtime-service-onboarding-and-verification.md | 补充按 Agent 类型选择本地验证及 Worktree 入口 | 如何确认新 Agent 符合要求 |

首轮只处理入口和指南。用户追加要求后，全文审查所有 knowledge 并按篇修订必要内容，案例 README 直接按源码纠偏；不为减少文件而删除有效设计，也不修改案例实现或擅自改变安全语义。

## 开发指南大纲

1. 开发前写清：输入/输出、业务目标、工具副作用、审批、状态/恢复、平台能力与验收。
2. 选择形式：普通工具 Agent、显式 Workflow、需要文件/Skills/委派的 Deep Agent。
3. 模块架构：平台控制面、GraphHarbor 引擎、Runtime 公共层、Graph 导出层、Service 组合根、业务工具/资源。
4. 目录职责：必需文件与按需文件；不照抄整个 Showcase，不新增万能 Builder。
5. 构图生命周期：schema/state 探测、受信身份与 Context、模型连接、授权、装配和追踪；避免缓存跨租户运行对象。
6. 接入步骤：新 Service、稳定 Graph 入口、图配置、工具目录/能力声明、条件性 Plan/调度/Workspace 接入、包资源与测试。
7. 工具/Skills/子 Agent/Workflow 的具体边界、可靠性和失败处理要求。
8. 从最小普通 Agent 到按需能力的案例阅读顺序；每例配源码与测试。
9. 本地验证与交付清单，区分组合验证、真实运行和平台可用。
10. 官方资料查询方法：先代码/锁文件，再 LangChain docs/reference MCP，最后核对锁定版本。

## 验收条件

- 新开发者不需要先读完历史设计，就能选择合理 Agent 类型并画出模块职责。
- 每个关键模块说明“负责什么、不负责什么、复用哪里”。
- 普通 Agent、Workflow、Deep Agent、MCP/Backend 示例均有明确使用边界及测试入口。
- 明确注册图不等于完成平台能力接入；新增能力声明与受信权限不能混淆。
- 资料包括可点击的本地入口和官方来源，并说明查什么与版本核对方式。
- 文档路径、命令选择与当前代码核对；不把未运行的测试写成已通过。
- CI、测试脚本、依赖及业务源码差异为零。

## 执行顺序

先修订本项目范围与任务；随后完成入口和指南；最后做相对链接、源码/测试路径、命令边界和三类开发场景走查，回写验证与状态。

## 风险控制

资料中存在过时案例说明和历史生产限制。本期只整理当前开发方法；不宣称任何历史生产门禁被解除。跨服务/鉴权语义变化仍走根 AGENTS 的人工评审。本期不启动服务、连接数据库或调用真实模型。

## 当前状态

2026-11-08：首轮及追加文档范围均 done。完成入口、指南、45 篇 Runtime docs 与 7 篇案例 README 全文审查；追加轮修订 45 篇、保留 7 篇，逐篇理由见 document-review.md，最终验证见 verification.md。业务源码、依赖和 CI 未改动。

## 用户追加范围：逐篇内容审查

首轮交付后，用户要求继续优化案例 README，并阅读全文审查 apps/runtime-service/docs 内每篇文档，判断和实施必要修改。当时项目恢复进行中，新增 Task 5～7；现已全部完成，首轮 Final 与追加 Final 分别保留。

当前标准纠正经代码/测试确认的过时描述；历史设计与变更记录保留原阶段事实，在每篇中说明仍适用的设计、已被替代的主张和当前入口。安全/权限/契约的实质冲突标记并等待人工判断，不通过改文档批准新行为。CI、业务实现和依赖仍不在范围内。
