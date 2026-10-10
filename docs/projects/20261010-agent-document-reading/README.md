# Agent 通用文档读取能力补齐 - F10 重审

## 项目概述

- **时间：** 2026-10-10；用户已批准实施，Runtime/API/Web全部实施、UX优化与全链路自动化Playwright端到端验收已完成，用户人工浏览器实测验收通过。
- **目标：** 在现有文件上传、FileRef 和文档工具上补真实缺口，让 Agent 按需读取 Office 文档，并控制附件上下文成本。
- **负责人：** 老王（全栈开发与全链路端到端闭环验证）。
- **模板类型：** 标准模板；三个服务属于同一条交付链，不拆成三份独立专题。
- **状态：** 已完成（`done`）；全部后端、前端 Task 3.1/3.2 与 Playwright 真实模型浏览器闭环验收均通过，4 张全景截图已留痕；用户人工实测验收通过，本地服务已停止。
- **本轮交付范围：** Runtime/API 开发、Web 前端开发（MIME纠正/原字节下载/错误优先/语义投影/DOC PPT专属徽标/无假预览仅下载/工作区415人性化提示）、前后端定向单测与静态门禁、Playwright 真实模型端到端闭环测试。

## 结论

**建议做文档读取缺口补齐，不照搬“上传即转 Markdown、每轮注入全文”的 F10。**

| 范围 | 推荐 | 理由 |
| --- | --- | --- |
| 已有上传、下载、线程隔离、FileRef、PDF/文本解析 | 复用 | 已有公共实现和调用链，重建会形成两套 |
| 附件上下文 | 优先补齐 | 当前 middleware 每次模型调用枚举全部 uploads，没有数量预算；旧 A09/T07 已记录同一缺口 |
| DOCX/PPTX 输入与按需读取 | 纳入最小方案 | 上传白名单未打通；PPTX 生成能力不能证明可读取用户上传的 PPTX |
| XLS/XLSX 分析 | 保留现有沙箱 Skill | 已有 DuckDB/openpyxl/xlrd 方案；转成 Markdown 会丢失结构和计算语义 |
| 自动全文转换、持久化旁生 .md、MarkItDown 全量依赖 | 本期不做 | 尚未证明有独立收益，会增加上传耗时、双份文件和失败生命周期 |
| OCR、旧 DOC/PPT、复杂版面、通用 Excel 预览工具 | 后置 | 是独立能力，不能用库声明或空文本当作已支持 |

## 快速导航

1. [源码对照与辩证分析](reference-analysis.md)：DeerFlow、Open-SWE 与本仓实际做法，以及同事方案的取舍。
2. [整体方案](plan.md)：服务职责、文件位置、冻结契约、安全边界与回退。
3. [任务拆分](tasks.md)：本轮规划完成项与后续实施任务，唯一施工状态表。
4. [验证计划和记录](verification.md)：真实格式、隔离、恢复、性能与浏览器门禁。
5. [前端交接](frontend-handoff.md)：交给同事的文件清单、契约、状态、失败和验收要求。

实际改动见 [Office 实现记录](implementation/01-office-reading.md)。

## 本轮交付与验证

- Runtime：同一官方 `parse_document` 工具补 DOCX/PPTX 文本读取、section/slide定位、有界续读和固定Docker reader；消息FileRef直接复用，移除每轮全uploads系统索引。
- API：只扩上传/读取MIME白名单；原字节、六字段FileRef、ACL、Delegation、审计与fork授权复制沿用现有链路。
- 专项：Runtime定向64 passed（2旧opt-in skipped）、API文件/审计/ACL组合66 passed（3旧外部skipped）、真实Docker6 passed；Showcase DOCX与DearFlow PPTX均完成真实模型/Worker读取、历史、连续上传和fork，Showcase另完成Worker重启验证。证据见 `verification.md`。
- 全量：Runtime1189 passed/25 failed/52 skipped；API分批执行的完整顶层门禁仍有4个HEAD基线断言/fixture失败和1次冷启动超时。已做基线归因，未修改范围外行为；详见Final风险，不写“全量全绿”。
- 交接：[frontend-handoff.md](frontend-handoff.md)已冻结文件清单、契约、验收和可直接转发的话术；本轮未改任何前端业务文件，未提交或部署。

## 改动范围

- **影响服务：** runtime-service、platform-api；platform-web 仅规划和交接，实施由同事完成。
- **改动级别：** 已按治理改动完成用户方案评审。新增不可信 Office 解析复用受限执行与跨服务 MIME/工具结果契约；没有数据库迁移或新鉴权体系。
- **预计工作量：** 后端与验证粗估 8-12 工程日，前端约 1.5-2.5 工程日；不含人工评审等待、生产发布、OCR 和复杂版面，不作为已承诺排期。依赖版本与 Docker 样本验证后重估。
- **实施门禁：** 用户已通过方案评审；实施先完成 Phase 0 的依赖、工具接线和消息契约 Spike，再冻结具体版本、返回样本和资源预算。批准范围内不重复请求许可；真实阻塞项如实记录。

## 关键决策

1. 原始文件与 `FileRef v1` 保持唯一输入事实源，不改变上传响应，也不塞入解析状态或转换路径。
2. 唯一读取入口仍为公共 `parse_document`；扩格式，不另建 UploadsMiddleware 或转换服务。
3. 优先复用消息已有文件引用，删除每轮全目录系统索引；只有实测引用丢失时补有界请求副本。历史文件复用现有 `ls/glob` 等工具发现，不自动注入正文。
4. PDF/文本/CSV/ZIP 保留现有行为；Excel 仍由已授权的数据分析链路处理。
5. 新 Office 读取在受限执行进程中运行，优先复用现有 Docker 执行、取消和资源回执；不能用 `to_thread` 宣称实现了隔离。
6. 本期不扩大 Plan Mode 或子 Agent 的只读工具名单；二者的限制必须如实展示和测试。
7. 后端完成、前端完成与联合 Final 分别留证；交接文档完成不等于前端能力已上线。
8. 遵循官方 LangChain/LangGraph 工具接口和现有 `create_deep_agent` 接线；沿 `AgentMiddleware.tools` 注册同一 `parse_document`，由现有 Agent 执行，保留原生 ToolMessage、工具治理和取消链路。

## 与已有专项的关系

- [原文档能力设计](../20260913-showcase-image-chart-capabilities/09-document-parsing-design.md)和[文件全链路集成](../20260913-showcase-image-chart-capabilities/10-platform-document-integration.md)是现有能力来源；本期不重做其上传、消息或授权链路。
- [DeerFlow 能力重审 A09](../20260913-dearflow-agent/11-20260928-capability-reassessment.md)与[接续方案 T07](../20260913-dearflow-agent/12-completion-plan.md)中的附件索引切片由本专项细化；其他 T07 事项仍在原项目维护，不随 F10 标记完成。
- 原 PPTX 发布与图片型幻灯片验证继续有效，不借本次上传扩展放宽已有成果校验。

## 已确认的实施决策

| 决策 | 推荐范围 | 评审影响 |
| --- | --- | --- |
| D01 范围 | 有界引用上下文 + DOCX/PPTX 按需读取；维持现有 Excel 分析 | 确认是否具有实际 Office 输入需求，不把“通用”理解为所有格式/所有图 |
| D02 资源与依赖 | 复用 Docker 执行；复用 python-pptx，仅补 python-docx | 新解析器版本、镜像打包、取消/资源限额须经样本验证 |
| D03 读取契约 | FileRef 不变；parse_document 增可选读取选项与非 PDF 定位字段 | 前后端共同冻结样本，保留旧 PDF/文本响应 |
| D04 权限范围 | 普通运行的 Showcase/DearFlow 根图；不新增 Plan/子图授权 | 若另需规划时读 Office 或子图读 Office，单列权限闭包评审，不顺手放权 |

2026-10-10 用户明确“同意你的方案”，确认按 LangGraph 范式接入，并再次确认 OCR、旧 DOC/PPT 和复杂版面后置；随后明确“方案评审通过，可以开始实施”，授权完成除前端外的所有开发项及验证。D01-D04 据此批准；Docker 是本项目的执行隔离选择，不是 LangGraph 强制要求。解析依赖版本、质量和资源预算须实测；生产发布与 Git 操作未授权。
