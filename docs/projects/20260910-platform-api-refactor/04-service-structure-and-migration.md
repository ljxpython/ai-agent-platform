# 04 服务结构、新数据库与验收

## 目标

面向 Runtime 重建简约的 FastAPI 平台层：目录按职责组织、数据库从空库初始化、资源生命周期明确、核心业务有真实验证。旧代码和旧表仅用于理解需求，不约束新设计。

## 方案设计

### 目录与依赖范式

在 `apps/platform-api` 内交付单一正式实现，采用可安装的 `src/platform_api` 包：

```text
src/platform_api/
  main.py                    create_app、路由装配与 lifespan
  config.py                  环境配置与边界校验
  db.py                      engine、短事务和 Session 生命周期
  auth/                      身份、认证依赖及授权；按实际复杂度拆文件
  modules/
    <业务模块>/
      router.py              HTTP 参数、依赖与响应
      schemas.py             公开输入输出
      service.py             用例与权限校验；简单 CRUD 不强制多一层
      models.py              有持久化时才存在
      repository.py          查询复杂或复用时才存在
  adapters/
    langgraph/               官方 SDK 与必要的 Protocol HTTP/SSE 适配
migrations/                  新数据库初始化及后续版本演进
tests/                       新平台的可执行契约与回归测试
```

这是职责示意，不要求每个模块凑齐文件。模块按身份/IAM、项目、用户、服务账号、公告、Agent、模型、目录、策略、网关、审计和系统设置的实际职责划分。需要拆分时再从 main.py 提取装配函数，不预建 bootstrap 框架。包名变更同步更新启动命令、测试、镜像与脚本，不保留 app 的兼容重导出。

常规 CRUD 使用 SQLAlchemy 和 Pydantic。删除无消费 Protocol、伪异步 UoW 和简单模块的机械四层目录；复杂模块保留必要分工；不引入 BaseService、通用 CRUD Repository、DI 容器、插件系统或事件总线。跨模块由应用入口装配，目录只读能力不反向依赖策略签发；网关组合目录与授权决议。

### 新数据库职责

使用现有 PostgreSQL、SQLAlchemy、Alembic，不为重构更换技术栈。下表确定逻辑对象与必要约束；具体 DDL、索引与字段在对应实现中冻结，不照搬旧表集合。

| 对象 | 保留的数据与约束 |
| --- | --- |
| 身份、用户、服务账号、会话/凭证 | 当前认证必需的数据；身份唯一，密码与长期 token 不明文保存，撤销可验证 |
| 项目、成员与 IAM 授权 | 项目归属、成员关系与角色权限；成员关系唯一、外键完整，可信 tenant/project scope 由认证确定 |
| 模型配置、项目允许模型 | 七字段连接配置及加密密钥；项目允许关系唯一，默认模型必须属于允许且启用的集合 |
| agents | 单表保存项目、graph_id、名称、启用状态、默认模型与必要公开参数；项目内 graph_id 唯一，无 agent_profiles |
| Graph/Tool 策略 | 仅保留实际参与启动与恢复授权的规则；不镜像 Agent 工具实现，不建用户动态工具产品 |
| 目录快照（需要持久快照时） | 部署逻辑键、graph_id、真实 schema 与获取时间；可从部署端重建，不是注册事实源 |
| run_requests | 请求身份、提交结果、关联 Run 与必要恢复信息，详见下文；无执行活跃锁 |
| 审计、公告、系统设置 | 真实使用的管理功能；审计有身份、项目、动作、目标、结果，设置必须有实际消费方 |

`run_requests` 的最小合同：

- 请求 ID、tenant/project、actor、thread_id、graph_id、动作类型、客户端幂等 key。
- 客户端意图摘要用于识别同 key 改请求；已决议配置摘要和必要非敏感参数用于重试，模型以配置记录 ID 引用。两类摘要不混用，防止默认值变更破坏重试语义。
- 提交结果只描述 pending/accepted/rejected/unknown，另存 upstream_run_id、时间与受控错误码；它不是 Run 执行状态。
- 唯一约束覆盖可信身份作用域、项目、Thread、key；向上游透传同一作用域生成的稳定 key，具体编码与上游合同一起验证。
- 审批动作关联原 Run 与 interrupt ID；新 Run 新建关联，不覆盖原 Run。无消息、事件、checkpoint、明文密钥或可兑换模型引用副本。
- 不为同 Thread 设置平台 active 唯一锁；运行并发交给 Agent Server。同 key 并发提交依赖上游原子幂等，不能靠一张本地记录假装实现端到端保证。

新初始化基线不创建 testcase、knowledge、Operations/artifact/heartbeat、runtime_runs、runtime_run_interrupts 和 agent_profiles 旧表，不导入旧数据。新平台以后仍用 Alembic 管理自身 schema 演进；“无旧兼容”不是以后任意改已发布 migration。

### 数据库与 HTTP 生命周期

继续使用 SQLAlchemy 同步栈：

- 纯同步 CRUD 用 FastAPI 同步 endpoint。
- async 编排中的 DB 工作按完整短事务在线程内执行；Session 创建、查询、提交、关闭位于同一线程，不跨多个 to_thread 共享 Session。
- HTTP await 不在数据库事务内；先读取并关闭事务，远端调用后另开短事务记结果。
- 用标准 Session transaction/contextmanager，删除只把同步 commit 包成 async 的 UoW。
- lifespan 创建并关闭 engine 和复用 HTTP client；每请求传认证 headers，不修改共享 client 的默认 Authorization。
- JSON 与 SSE 建连有有限超时；长流读取单独配置，断开释放连接。认证查询同样遵循线程与事务规则。

### 删除范围与调用者

| 范围 | 同步清理 |
| --- | --- |
| Platform API 知识库、测试用例 | `modules/project_knowledge`、`modules/testcase`、`adapters/knowledge`、`adapters/interaction_data`，及路由、权限、配置、模型和专属测试 |
| Platform Operations | `modules/operations`、平台 Worker 入口、queue/heartbeat/artifact、Run reconciliation、任务装配、状态/健康接口、部署进程和脚本 |
| 平台专属依赖 | consumer 删除后移除 redis、openpyxl 及关联环境变量，更新锁文件；不删除 GraphHarbor 的执行依赖 |
| 前端知识库与测试用例 | knowledge/testcase 模块与 services、knowledge/testcase/testcase-v2 路由、菜单、项目入口、权限映射和对应页面测试 |
| 前端 Operations 与假同步 | Operations 页面/services，Agent resync 按钮、任务轮询；runtime/assistants service 解除 Operations 依赖，Graph/Tool 目录改直接受控读取/刷新 |
| 旧兼容与无入口包装 | assistants 产品别名、旧导入包、无效删除参数、AST schema、本地源码查找、无入口 SDK 包装、未消费接口 |

初始审查核查了现已删除的 `modules/operations/bootstrap.py` 注册任务：Run reconciliation、模型/工具/Graph 刷新、Assistant resync、两类 testcase 导出、knowledge scan/clear。业务退役与网关收缩后，剩余目录读取/刷新是有限时长 HTTP 请求，无需通用后台任务框架。

初始实现中，`entrypoints/http/system.py` 将平台 Worker 心跳计入健康状态，`modules/platform_config/application/service.py` 也读取 Operations 快照。退役时一并改为新 API 的实际存活/就绪检查，移除失效 feature flag，避免删掉 Worker 后平台永久显示不健康。

删除范围是平台层及其前端接入；`apps/interaction-data-service`、独立知识服务和 GraphHarbor API/Worker/Redis 不在本次删除范围。不预留空 knowledge/testcase/operations 模块；未来出现真实需求再设计。

审计使用路由/用例明确提供 action、target 和结果，逐步替代按 URL 猜动作的长分支。保留公告、系统设置和现有核心身份治理能力，不借退役两块业务扩大无关删减。新平台自动化测试必须保留并重建，不能因 testcase 产品退出而删除安全/网关验收。

### 实施与交付顺序

1. **新基础与核心数据：** 收敛职责，建立 src 包、资源生命周期、新 schema 和管理员初始化，更新启动入口与依赖。
2. **业务退役：** 删除知识库、测试用例、Operations 及前后端调用者，清理配置与部署。按任务完成可运行切片，不维护双套正式 API。
3. **部署端合同：** 验证并补齐 Graph/schema 只读发现、原子幂等、并发与未知提交恢复。GraphHarbor 只放通用能力。
4. **Agent 与网关：** 实现单表 Agent、模型决议、项目授权、run_requests 与安全流式转发；01 的缺陷转为正确预期测试。
5. **前端与独立交付：** 前端接新契约，镜像使用锁文件，打包 migrations/alembic.ini 与可安装应用，仅通过网络依赖 Runtime。
6. **真实验收：** 核心治理及聊天/审批/恢复链路通过，再恢复 Showcase 平台联调。

新环境使用新的数据库或隔离 schema，由新 Alembic 基线从空库初始化。不写旧数据迁移器、不承诺旧 Thread/审批接续、不执行旧新表双写。具体旧环境清理不属于当前规划修订，也不是应用启动的自动行为。

部署失败处理针对新平台自身：切换前验证新环境；失败可停止切换、重建隔离测试环境。开始承载真实数据后，用新平台的备份恢复与版本管理保护新数据；演练不重放已提交输入，不要求退回旧平台读取新表。

## 任务拆分

- [x] S1：落实新职责、入口与开发规范，更新 platform-api README、handbook、standards 和 CI；README 说明各部分用途与新增功能方式。**done：** README、三份活手册、正式包、启动入口与 CI 已更新，事务与目录范式见 12。
- [ ] S2：删除知识库、测试用例与 Operations 全链路及专属依赖，清理前端入口、环境示例和部署进程。**进行中：** 知识库/测试用例前后端、任务、权限、配置、依赖已移除；Operations 后端模块、队列、Worker、路由和配置已退役；前端整体复验 deferred。
- [x] S3：建立 src 包、同步短事务与 HTTP 生命周期，消除无效接口、空模块、机械四层和循环装配。**done（按用户批准的必要精简范围）：** 删除 async UoW、同步 CRUD/完整事务线程池、认证与审计线程边界、7 个简单模块压平；复杂模块保留必要分工。见 [12](implementation/12-transactions-and-layout.md)。
- [ ] S4：新表、约束、Alembic 和管理员初始化已验收（20 表升降升、metadata 无差异）；整套容器部署按用户决定 deferred，不编写旧数据迁移。
- [x] S5：完成 02/03 合同及核心业务集成，执行安全负面矩阵、真实链路和必要负载验证，逐专题记录结果。
- [x] S6：按验收结果汇总四态；平台完成后恢复 Showcase 后续工作。

## 验证要求与记录

### 历史基线

2026-09-10 重构前测试：167 项，163 通过、1 失败、3 跳过。Python SDK 0.4.2、FastAPI 0.135.3、SQLAlchemy 2.0.49；Runtime 已安装 GraphHarbor post21。执行命令、失败与证据见 [01](01-current-state-and-retirement.md)。

该结果仅用于追溯旧行为。旧测试按保留的产品契约重写，退役业务测试随业务删除，新平台不得沿用旧通过数宣称完成。

### 实施后验收

- [ ] 单元与 API：核心身份/IAM、项目、服务账号、公告、模型、Agent、策略、审计及系统设置的真实保留功能通过。
- [ ] PostgreSQL：空库初始化、重复初始化行为、唯一/外键约束、事务回滚、幂等竞争、默认模型授权一致性通过。
- [ ] 真实 Agent Server：登录→项目→Agent→模型→Thread→发送→流式→重开→审批→取消→再次发送；API 与 GraphHarbor Worker 重启后恢复正确。
- [ ] 两个项目、普通用户/管理员/服务账号：跨项目拒绝、禁用/撤权、可信审计、公开读面无内部凭据。
- [ ] 退役检查：无知识库、测试用例、Operations 路由/菜单/轮询；无专属配置、平台 Redis/导出依赖；目录刷新不产生任务。
- [ ] 前端：新 Agent/Models/Chat 和保留页面通过 typecheck、相关组件测试与关键浏览器链路，不扩展视觉重设计。
- [ ] 独立镜像：无 Runtime 源码或宿主绝对路径挂载，可发现真实 Graph/schema、初始化数据库并正确关闭资源。
- [x] 负载：并发登录/列表与长 SSE 共存；记录并发量、p95、错误率、连接数和事件循环延迟，不编造 QPS 目标。
- [x] 新平台备份恢复/重启演练：已提交请求可确认、无重复副作用、已关联 Run 可追溯，不依赖旧表。
- [x] 文档链接与 git diff --check；新旧工程状态一致，真实链路缺失时不标 done。

### 本次规划修订

2026-09-10：记录用户批准，更新全新平台范围、删除矩阵、新数据库职责与验收条件。本次未改产品代码、未执行数据库操作；不重跑无关的旧全量测试。5 篇专题的结构、代码围栏、9 个本地链接与旧约束检查通过；git diff --check 通过。以上是文档验证，不代表新平台功能验收。

### 2026-09-10 首个退役切片验证

实现见 [01 退役知识库与测试用例](implementation/01-retire-knowledge-testcase.md)，结构化证据见 [retirement-verification.json](evidence/retirement-verification.json)。本切片先于新基础实施，因为业务退役不依赖上游新合同，可独立验证并缩小后续改造范围。

- 后端全量 155 项：151 通过、1 失败、3 跳过，294.314 秒；唯一失败为重构前已有的本地 Graph 目录假设，未新增失败。
- 已验证退役 HTTP 路由返回 404，未注册任务被拒绝且不落库；保留的 IAM、Operations/Worker 与网关测试继续执行。
- 前端路由/权限 10 项通过，全量 ESLint 与 Python compileall 通过；前端生产构建（vue-tsc + Vite）通过，Vite 构建耗时 3m 1s。
- uv/pnpm 锁文件更新通过，pnpm 冻结离线锁文件校验通过；两份 Compose 静态配置校验通过，不代表已启动镜像。
- 文档 10 篇、33 个本地链接、代码围栏及证据 JSON 检查通过，git diff --check 通过。
- 未执行浏览器端到端、新数据库初始化、真实 Runtime 联调或部署恢复验证；本次切片及整体工程均不据此标 done。

### 2026-09-10 可安装包切片验证

实现见 [02 可安装平台包](implementation/02-installable-platform-package.md)，结构化证据见 [package-verification.json](evidence/package-verification.json)。

- 冻结离线依赖同步、wheel 构建和仓库外隔离安装烟测通过；215 个源码文件无旧 app 导入，旧源码目录已移除。
- 新资源生命周期测试 3 项通过，覆盖初始化失败清理、线程内管理员幂等初始化和 Worker 构造失败清理。
- 首次全量 158 项：153 通过、1 失败、1 错误、3 跳过，473.506 秒。失败仍为原有静态 Graph 目录假设；错误为本地 SSE 测试受环境 HTTP 代理影响。测试客户端设置 trust_env=False 后，该文件 3 项复验通过（21.247 秒），未再次执行全量，不将初次结果改写为全绿。
- 本地 Docker 镜像构建成功；容器禁网、无源码挂载、工作目录为 /tmp，确认从 site-packages 导入，完整进入/退出 lifespan，存活接口 200、未登录项目接口 401。Alembic 使用绝对配置路径可发现当前旧修订头 20260907_0007；没有执行数据库 upgrade。
- Python compileall、4 个启动脚本语法、两份 Compose 配置和 git diff --check 通过。工程文档检查通过。
- 镜像烟测关闭数据库；不代表新空库初始化、远端 Graph/schema 发现、真实 Runtime 或浏览器链路通过。新 schema、业务事务治理和 Operations 退役继续按原任务实施。

### 2026-09-10 远端发现回归

目录与 schema 后端移除宿主机源码依赖，见 [05 实现记录](implementation/05-remote-graph-discovery.md)。本地全量 156 项：153 通过、3 跳过，227.150 秒，无失败/错误；之前的生产静态目录假设测试已改成远端 registry 契约测试。全量启动后新增的两项断言已在对应文件复验通过。GraphHarbor 发现/状态投影 4 项通过；当前安装包与真实 Runtime/浏览器链路尚未完成验收。按用户要求，容器验证后置到整体开发完成。

## 状态

本阶段后端 done。20 表及模型/Agent 字段收缩、Operations/resync 退役、真实 Runtime/Showcase 后端验收完成；S3 事务规范化和必要目录精简 done，本地 PG/Redis 真实链路通过；完整 Docker 工具复验已通过，见 [12](implementation/12-transactions-and-layout.md)。前端、容器整体验收 deferred。当前证据见 [11 收尾记录](implementation/11-backend-closeout.md)，下方保留逐轮历史，不代表最新缺口。

### Agent 单表与新空库基线切片

2026-09-10：已合并 Agent/Profile ORM 与仓储，增加真实 SQLite 生命周期测试；旧 Alembic 链已替换为空库静态基线。Operations/Run 表及同步字段仍待退役，本专题保持 partial。详见 [08 实现记录](implementation/08-agent-single-table.md)。

### 最新验证要求与记录（2026-09-10）

本次以 HTTP/SDK 驱动真实后端完成 Showcase；最终独立执行报表 43.50、退出码 0。PostgreSQL 空库升降升、20 表 metadata 一致及请求记录并发唯一约束通过。详细测试计数、失败修复与未覆盖矩阵统一记在 [10](implementation/10-operations-run-requests.md)，避免多处维护不一致的测试数字。前端及容器部署均 deferred，不计为失败，也不计作已验收。

三项收尾已完成：20 条公开网关路由矩阵、真实 PostgreSQL 备份恢复、4 路登录/列表与 2 条长 SSE 混合负载均通过。详见 [13 三项验收收尾](implementation/13-backend-acceptance-closeout.md)。本阶段后端 done；前端/浏览器、整套容器部署、完整 Server 等价性 deferred。

S2/S4 清单中的未勾选部分只保留前端整体复验与整套容器部署（deferred），对应后端退役和数据库初始化已 done。历史未勾选场景须结合 11/12/13 的分层证据阅读，不代表新增开发缺口。备份恢复的范围和静止窗口限制见 13。
