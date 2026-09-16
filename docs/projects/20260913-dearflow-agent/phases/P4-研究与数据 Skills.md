# P4 研究与数据 Skills：阶段执行包

> 本文件是 P4 实施时的唯一执行入口。先看需求清单了解做什么、交付标准和当前状态，再按专题链接查实现细节。需求清单与专题任务一起更新；已有代码不等于验收完成。前端暂不实施，需要配合时提前告知。

## 阶段目标

每个 Skill 独立迁移、确定性测试、Web E2E 和负例验证

2026-09-15接续确认：当前先实施后端，前端仅写交接、页面验收后置。P3约定后端及GraphHarbor post30对齐已完成，足以进入P4后端；F3未验收不阻塞本次后端推进，但不得因此把P3或P4整个阶段勾为done。K-G1/K-G2的K01必需切片与K01约定后端范围已完成；K02—K07按最新授权集中实现、统一验证，代码及交接已写入，真实结果逐项见10记录。

## 三类进度与推进规则

07台账保留Skill整体状态；下表是本阶段逐项交付状态，不用一个勾选混淆三个维度。后端完成须有确定性测试、真实平台／模型链路、负例、来源版本与产物证据；交接完成须列具体UI需求、接口／字段、代码落点与待验场景。后端done且交接done但页面deferred时，Skill整体仍为partial。

| 任务／需求 | 后端实现与验证 | 前端交接 | 页面验收 |
|---|---|---|---|
| K01 深度研究 | done：4项定向测试、wheel及真实样本复验通过；原pytest误报及修正后只读复验分别保留，见[09证据](../implementation/09-p4-k01-deep-research.md) | done：[K01交接](../frontend-handoff.md#p4k01-深度研究接入交接)，没有新增前端代码 | deferred，用户要求后置 |
| K02 论文评审 | done：组合及真实PDF链路通过，见[10](../implementation/10-p4-k02-k07-batch.md) | done：[批次交接](../frontend-handoff.md) | deferred |
| K03 GitHub仓库研究 | blocked：组合通过，真实GitHub匿名配额耗尽403，见[10](../implementation/10-p4-k02-k07-batch.md) | done：[批次交接](../frontend-handoff.md) | deferred |
| K04 咨询分析 | done：报告范围通过；图表依赖K09后置，见[10](../implementation/10-p4-k02-k07-batch.md) | done：[批次交接](../frontend-handoff.md) | deferred |
| K05 文献综述 | blocked：组合通过，真实arXiv 429／超时，未完成论文→子任务→引用链路，见[10](../implementation/10-p4-k02-k07-batch.md) | done：[批次交接](../frontend-handoff.md) | deferred |
| K06 代码文档 | done：组合及真实ZIP链路通过，见[10](../implementation/10-p4-k02-k07-batch.md) | done：[批次交接](../frontend-handoff.md) | deferred |
| K07 简报生成 | done：报告、搜索与正文fetch定向复验通过，见[10](../implementation/10-p4-k02-k07-batch.md) | done：[批次交接](../frontend-handoff.md) | deferred |
| K08 表格分析 | done：真实Docker、两表SQL、CSV与报告下载通过，见[11](../implementation/11-p4-k08-k11-batch.md) | done：[交接](../frontend-handoff.md) | deferred |
| K09 图表与地图 | partial：25/26真实图型通过，柱图＋地图模型链路done；双轴远端错误blocked | done：[交接](../frontend-handoff.md) | deferred |
| K10 网页代码产物 | done：真实HTML/CSS/JS生成、ZIP与下载安全复核通过，见[11](../implementation/11-p4-k08-k11-batch.md) | done：隔离预览仅交接 | deferred |
| K11 网页规范评审 | done：规范SHA256、静态file:line、报告发布下载通过，见[11](../implementation/11-p4-k08-k11-batch.md) | done：[交接](../frontend-handoff.md) | deferred |

最新用户确认：K02—K07改为集中实现、统一验证，覆盖本文件与07／10此前“当前项验完才能写下一项”的要求。先写完六项及必要依赖，再一次运行相关回归和资源验证、逐项真实验收；小改动不跑全量，失败只复测相关链路。每项区分实现完成／验证通过／前端交接／页面后置，见[10批次记录](../implementation/10-p4-k02-k07-batch.md)。新增确认：K08—K11也先集中实现、再统一验证，见[11批次记录](../implementation/11-p4-k08-k11-batch.md)。K12以后仍按依赖推进，不等待后置页面验收。K10生成网页文件属于Agent后端能力，开发Dear页面和HTML隔离预览属于前端交接，不混为同一工作。

## 需求清单

逐个迁移下列 Skill：原样复制优先，仅对实际不兼容的工具、澄清和文件引用做最小适配；每项验证通过后再推进下一项。原则及差异记录要求见[07迁移原则](../07-skills-migration.md#迁移原则原样复制优先实际不兼容处最小修改)。

| Skill／需求点 | 要交付什么 | 对应专题 | 当前状态 |
|---|---|---|---|
| deep-research：深度研究 | 多轮检索、核实来源、输出有引用的研究报告 | 07/K01 | partial：后端done、交接done／页面deferred |
| academic-paper-review：论文评审 | 读取单篇论文并给出可定位依据的评审 | 07/K02 | 已实现／验证见上方状态表 |
| github-deep-research：仓库研究 | 只读查询仓库、处理分页，输出代码依据和分析 | 07/K03 | 已实现／验证见上方状态表 |
| consulting-analysis：咨询分析 | 先澄清需求，再输出结构化分析 | 07/K04 | 已实现／验证见上方状态表 |
| systematic-literature-review：文献综述 | arXiv 检索、筛选与全文边界控制，形成综述 | 07/K05 | 已实现／验证见上方状态表 |
| code-documentation：代码文档 | 安全读取项目包、生成可下载的代码文档 | 07/K06 | 已实现／验证见上方状态表 |
| newsletter-generation：简报 | 根据研究来源生成简报文件 | 07/K07 | 已实现／验证见上方状态表 |
| data-analysis：数据分析 | CSV/XLSX/XLS 输入、受限分析、导出结果 | 07/K08 | 后端done，见11批次验证记录 |
| chart-visualization：图表和地图 | 对照上游图表类型，输出真实图表及可验证产物 | 07/K09 | partial：25/26通过，双轴远端blocked |
| frontend-design：网页产物 | 生成网页代码包，HTML 隔离预览；这是 Agent 产物能力 | 07/K10 | 后端done，见11批次验证记录 |
| web-design-guidelines：网页规范评审 | 获取有版本依据的规范，静态评审源码；不做浏览器自动操作 | 07/K11 | 后端done，见11批次验证记录 |
| 技能加载与资源校验 | 只读技能资源、wheel 打包、来源修订和启用版本可核查 | 07/K-G1、K-G2 | 待完成 |
| 按需补文件格式 | 在相应 Skill 前完成 PDF 文本提取、表格解析、安全解包与 HTML 隔离等依赖 | 04；03 | 待按项实施 |

每个 Skill 单独记录：来源与改写差异、依赖、确定性测试、真实模型链路、负例、产物和启用版本。后端验证通过但页面未验收时标记部分完成。

## 必读上下文

- 总纲：[README.md](../README.md)
- 主专题：[07-skills-migration.md](../07-skills-migration.md)
- 任务切片：`07/K01—K11；各 K 所需 03 工具、04 格式；08/F4、C07`

## 本阶段任务

- [ ] 按上方任务编号读取对应专题的“工作上下文／任务拆分／验证要求”。
- [ ] 只创建本阶段实际需要的目录和文件。
- [ ] 实施后写入项目 `implementation/`，并回填专题任务与总纲游标。

## 前置条件

- [x] 前一阶段状态明确：P3后端done、前端deferred／整体partial；post30后端完成，证据见[后端收口](../../20260915-graphharbor-v3-alignment/implementation/03-backend-closeout.md)。
- [ ] 本阶段涉及的契约生产方与消费方已在 08 章登记。

## 验收

- [ ] 使用专题文档列出的确定性测试和实际受影响链路验证。
- [ ] 未实现能力标记 deferred／partial，不用模拟结果勾选完成。

## 状态

K01后端及交接done，采用“原样复制优先、实际不兼容最小修改”原则，见[09记录](../implementation/09-p4-k01-deep-research.md)。K01整体partial，尚无Skill完成页面验收。K02—K07已集中实现，真实验证逐项收口；K08/K10/K11后端done；K09剩双轴远端错误，见11记录。
