# 文档重建方案

## 现状与问题

基线 `a3e65da`。`apps/platform-api/docs` 共 **64 个文件**：导航 1、handbook 3、standards 4、delivery 9、decisions 6、diagrams 12、archive 29。非归档区 35 个文件，其中 Markdown 23 个。已核对完整文件清单、活文档标题、主要规范和源码；实施阶段还要逐篇核对正文，不把盘点当作逐句审核完成。

| 位置 | 已确认的问题 | 当前依据 |
| --- | --- | --- |
| docs/README.md | 声称旧 Phase B/C/D Freeze 已完成，并把已归档交付清单作为当前入口 | 当前后端状态见重构工程 13；两个 runtime-contract 清单实际位于 archive/delivery |
| delivery/runbook.md:21、34、46 | 要求平台选择队列后端、检查 Worker heartbeat、启动已删除的 Worker 入口 | entrypoints/http/system.py：就绪检查当前 API 数据库；平台无 Worker |
| delivery/postgres-baseline.md:104 | 表清单仍包含 agent_profiles | migrations/versions/20260910_0001_platform_baseline.py：20 张业务表 |
| standards/permission-standard.md:99–106 | 列出已退役的 platform/project.operation 权限 | core 权限定义、IAM policies 及实际路由 |
| standards/audit-standard.md:90 | 开头宣布 Operations 退役，正文仍要求 operation/job 生命周期事件 | audit/http_resolution.py、http_writer.py 与审计中间件 |
| delivery/change-delivery-checklist.md:17、45 | 仍要求评估 Operations、编译旧 app 目录 | src/platform_api 包；现有 development-playbook 已定义按需文件与短事务 |
| diagrams/operation-lifecycle.* | 图继续指导创建 operation、Queue Backend、Worker、artifact | 对应业务已退役 |
| 三份 handbook | 已在本次重构更新，主体方向正确 | 复用，补漏和消除重复即可 |
| apps/platform-api/README.md | 仍有重构进行中、旧验收记录等阶段性重复说明 | 快速入口应指向最新状态，不继续累积收尾段落 |

Markdown 链接初查未发现活文档链接目标缺失，但许多路径只是反引号文字，现有检查不会验证，例如导航中两个已归档的 delivery 路径。需要同时核查导航文字路径和真正链接。

## 目标目录

```text
apps/platform-api/
  README.md                         服务定位、安装启动、最小验证、文档入口
  docs/
    README.md                       按读者任务导航、事实来源与维护规则
    handbook/
      project-handbook.md           平台能力与主要使用流程
      architecture.md               服务/数据边界、实际目录和请求流
      development-playbook.md        新功能怎么写、事务/导入/测试规则
      configuration.md               配置分类、必填条件、密钥边界
      database.md                    当前20表职责、初始化、迁移约束
      runbook.md                     本地启动诊断、健康、发布与备份恢复
    standards/
      permission-standard.md         身份、项目授权、服务账号与撤权
      audit-standard.md              实际审计字段、动作、失败/取消、脱敏
      runtime-gateway-interface-standard.md
                                    当前公开网关、幂等、审批、SSE与受信模型引用
    archive/
      README.md                      历史边界、原位置→替代文档索引
      ...                            现有29个历史文件保留
      pre-refactor/                  本次被替代文档，保留相对分类
```

目标为 **10 篇当前文档**（docs 导航 + 6 篇 handbook + 3 篇 standards），另有服务 README 和归档索引。按任务组织，不再添加一套 guides/reference/tutorials 平行体系。未来真实出现单服务能力变更或独立 ADR 时，仍遵循根 AGENTS 的 changes/、decisions/ 规则；本轮不预建空目录。

## 每篇的责任与源码锚点

| 文档 | 要回答的问题 | 事实依据 |
| --- | --- | --- |
| 服务 README | 怎么安装、配置、启动、验证？ | pyproject.toml、uv.lock、.env.example、main.py、alembic.ini |
| project-handbook | 平台负责什么，登录→项目→Agent/模型→Runtime 怎么使用？ | 注册路由、modules、前端交接文档；不写未验收页面操作 |
| architecture | 业务与执行事实分别归谁，模块如何组织？ | main/bootstrap/core/modules/adapters/entrypoints；以 Mermaid 内嵌必要图 |
| development-playbook | CRUD、异步 HTTP、授权审计和新表怎么开发？ | 一个真实同步用例和一个异步目录刷新用例；test_transaction_boundaries.py |
| configuration | 哪些配置必须填写、两服务之间如何配对？ | config.py、.env.example、load_settings、Runtime 受信配置；只记录实际使用项 |
| database | 当前表分几类、如何初始化、何时做迁移？ | Alembic 静态基线、Base.metadata、init_db.py；区分20业务表与版本表 |
| runbook | 如何诊断数据库/鉴权/upstream/SSE，如何恢复？ | 系统路由、真实验收脚本、备份演练；API/Runtime Worker 明确分开 |
| permission | user/service account、平台角色与项目角色如何判定？ | ActorContext、权限枚举、IAM policy、auth_context、权限测试 |
| audit | 什么行为记录、失败/取消如何收尾、什么不能记录？ | audit 模块、审计中间件及测试；不预留 Operations/outbox |
| gateway | 当前20条路由、参数边界、重试/resume/cancel/SSE 如何使用？ | runtime_gateway、adapters/langgraph、20条HTTP矩阵与真实证据 |

配置文档按启动、数据库、认证、Runtime、模型凭据与观测分类。环境变量名/默认值/必填条件必须核对源码；示例使用占位值与相对路径，不复制本机 .env 或令牌。网关不手抄所有 DTO/schema；公开参数以代码契约为依据，文档重点解释授权、幂等与故障语义。

## 旧文件处置清单

以下处置清单已按用户批准完成，结果见implementation/01-docs-rebuild.md。archive/pre-refactor 下保留原相对路径，索引写明替代正文和原因。既有 archive 29 个文件不重写历史事实，仅按需修复导航。

| 原文件（均相对 apps/platform-api/docs） | 处置 | 目标/原因 |
| --- | --- | --- |
| README.md | 重写 | 仅任务导航，删除旧 Freeze 总结 |
| handbook/project-handbook.md | 保留修订 | 能力和使用流程，去掉架构/工程状态重复 |
| handbook/architecture.md | 保留修订 | 当前结构、服务和数据边界 |
| handbook/development-playbook.md | 保留修订 | 唯一开发流程正文，合并有用交付规则 |
| standards/permission-standard.md | 重写 | 删除旧权限和路径，核对当前角色 |
| standards/audit-standard.md | 重写 | 删除旧 job 生命周期与扩展预留 |
| standards/runtime-gateway-interface-standard.md | 重写 | 实际公开契约；删除旧兼容与 Operations 条款 |
| standards/operations-standard.md | 归档 | 退役事实合入架构边界，不保留独立活标准 |
| delivery/postgres-baseline.md | 合并后归档 | handbook/database.md |
| delivery/runbook.md | 合并后归档 | handbook/runbook.md，重新核实命令与故障处置 |
| delivery/change-delivery-checklist.md | 合并后归档 | development-playbook，不重复根 AGENTS |
| delivery/module-delivery-template.md | 合并后归档 | development-playbook 的最小检查项，无强制模块模板 |
| delivery/release-template.md | 合并后归档 | runbook 的发布与回退边界，不编造已验收部署 |
| delivery/circular-import-remediation-checklist.md | 归档 | 已被直接导入规范替代的执行计划；有效规则留 development-playbook |
| delivery/platform-runtime-graphharbor-integration-checklist.md | 合并后归档 | runbook 引用现有真实脚本与重构工程证据 |
| delivery/platform-web-capability-coverage.md | 归档 | 旧前端能力结论已过时，当前交接见重构工程05 |
| delivery/platform-web-gap-closure-checklist.md | 归档 | 提取仍相关事项到现有05交接后再归档，不另开前端计划 |
| decisions/chat-use-stream-contract.md | 归档 | 已是 Archived 占位；现行语义进网关标准 |
| decisions/first-batch-module-map.md | 归档 | 旧模块迁移地图被实际src布局替代 |
| decisions/frontend-switch-strategy.md | 归档 | 旧切换策略；当前未完成项核对05交接 |
| decisions/langgraph-sdk-migration-plan.md | 归档 | 迁移执行清单被当前adapter与测试替代，非现行ADR |
| decisions/legacy-solution-inheritance-checklist.md | 归档 | 有效原则合入活文档，旧兼容计划失效 |
| decisions/platform-capability-reconciliation.md | 归档 | 含旧Operation/Testcase业务对账，当前能力见FEATURES与05 |
| diagrams/{system-context,request-lifecycle,permission-model,agent-chat-flow,business-domain-boundaries,operation-lifecycle}.{drawio,svg} | 六组共12文件归档 | 当前必要关系用 architecture/标准中的 Mermaid，不维护双份图源与导出图 |

旧文档不能仅因为名字像“阶段清单”就归档：先提取仍有效的规则或未完成事项，确认有现行替代来源，再移动。若正文核对发现仍有效的独立决策，保留并在清单标明例外，不为凑目录删除有用信息。

## 维护规则与边界

- 代码/配置/测试决定实际行为；活规范描述当前约束；工程文档记录决策过程与证据。发现冲突时修正文档，不为迁就旧文档改代码。
- 当前文章不堆叠日期补丁、Freeze 标语或逐轮测试数字。状态链接到重构工程13，前端影响链接05；历史证据不搬进 handbook。
- 保留的安全限制必须核对：管理员不隐含项目内容权限、凭据不进入公共响应、Session 同线程且不跨HTTP等待、取消与审计语义。
- runbook 不能把就绪接口 HTTP 200 当作 ready=true；按当前响应字段判断。PG 备份要求匹配客户端版本、静止写入窗口、单独保管密钥和工作区，保留两库/Redis恢复边界。
- 更新所有当前消费者链接，包括服务README、docs/FEATURES、仓库导航和必要的前端交接；历史工程证据不改写，只修复指向移动文件的实际链接。
- 无API、数据库结构、依赖、包发布、前端或容器实现变更。无文档站和新增文档框架，优先复用 scripts/check_docs.py；它目前仅检查旧宿主名与本机路径，不能替代链接和事实验证。

## 实施顺序与风险

1. 固定逐文件清单，核对配置、权限、审计、路由、表及测试锚点。
2. 先完成活正文与可运行命令，再切换导航并归档旧文件，避免归档后找不到现行规范。
3. 查全部引用、跑文档检查和相关只读命令，记录四态并同步FEATURES。

主要风险是把历史规则或待办丢掉、把后置项误标完成，以及把真实秘密复制进示例。通过逐项去向、05/13交接与脱敏占位规避。预计2–3个实施切片，不承诺未经验证的时间或生产容量目标。

## 实施状态

2026-09-10按本方案完成，状态done；新增configuration/database/runbook、归档28文件、活文档10篇。实际检查和范围外错误见verification.md。
