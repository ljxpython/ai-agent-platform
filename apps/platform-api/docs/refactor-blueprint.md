# Platform API 重构蓝图

这份文档不是“未来也许会做什么”的空话，而是给 `apps/platform-api` 的下一阶段重构定边界、定术语、定顺序。

它主要解决 4 个问题：

- 当前代码为什么还能跑，但还不够像一个长期可维护的平台后端
- 一个正常的平台控制面后端，通常要把哪些能力做成一等公民
- 我们后面重构时，代码应该往什么结构收敛
- 新功能进来时，开发者和 AI 代理应该按什么范式落地

## 1. 先讲人话：为什么现在就该重构

当前 `platform-api` 的产品方向没有跑偏，但工程结构已经出现早期巨石征兆：

- 路由、权限、数据访问、上游调用混在一起
- `Request` 对象一路渗透到服务层
- 同步 SQLAlchemy Session 大量跑在异步路由里
- `db/access.py` 已经变成全域数据访问大仓库
- 长耗时动作还没有 `operation/job` 这层
- 多租户只有模型雏形，还没有真正进入治理设计
- 自动化测试主要覆盖 auth，平台核心能力覆盖不足

这类问题在项目初期最容易被忽略，因为“现在还能跑”。但一旦继续堆功能，后面会同时出现 5 个坏结果：

1. 任意改一个功能，都容易误伤别的模块。
2. API 契约越来越散，前后端协作成本越来越高。
3. 后面做 worker、容器拆分、监控、审计增强时会痛苦翻倍。
4. AI 代理很难在这种代码结构里稳定持续开发。
5. 早期省掉的重构成本，会在中后期成倍偿还。

所以，这次重构不是“为了更优雅”，而是为了让平台后端以后还能稳定长大。

## 2. 这次重构不追求什么

先把不做的事情说清楚，免得一上来又搞过度设计：

- 现在不追求拆成一堆微服务
- 现在不追求一次性做完整多租户企业版能力
- 现在不追求把所有接口全部推翻重写
- 现在不追求先上复杂事件总线、工作流引擎、服务网格

当前最合适的目标不是“微服务平台”，而是：

> 把 `platform-api` 收敛成一个模块化单体控制面，并为后续独立 worker、独立部署和长期演进打基础。

## 3. 术语卡片

为了避免后面讨论时鸡同鸭讲，先统一几个关键词。

### 3.1 Control Plane

平台控制面，负责治理和管理，不负责真正执行智能体。

在当前项目里，主要就是：

- 用户、项目、成员、权限
- 资源目录与治理策略
- 审计、配置、公告、管理入口
- 对运行时的受控网关与协议整形

### 3.2 Data Plane / Runtime Plane

真正执行 Agent 的那一层。

在当前项目里主要是：

- `apps/runtime-service`

它负责 graph、model、tool、MCP、agent 执行，不应该被平台治理代码污染。

### 3.3 Module Monolith

模块化单体。不是把所有代码写成一个大文件，也不是一上来拆很多服务，而是在一个应用里先把边界拆清楚。

这次重构的目标就是这个。

### 3.4 Adapter

外部系统适配器。

例如：

- LangGraph upstream adapter
- interaction-data-service adapter
- 未来的通知、对象存储、SSO adapter

原则是：业务层不直接依赖 FastAPI `Request`，也不直接到处拼 HTTP 请求。

### 3.5 Use Case

一个明确的业务动作。

例如：

- 创建项目
- 给项目添加成员
- 创建 assistant
- 同步 runtime catalog
- 导出 testcase Excel

每个 use case 都应该有稳定输入、输出、权限边界和错误口径。

### 3.6 Unit of Work

一次请求内的数据库工作单元。

目标是：

- 一个请求尽量只进入一次主要事务边界
- 不在权限判断、业务逻辑、序列化过程中反复开 session

### 3.7 Operation / Job

长耗时或异步动作的统一抽象。

例如：

- catalog refresh
- 批量导出
- 未来的 tenant 初始化
- 大批量同步或清理任务

这类动作不应该一直走同步 HTTP 阻塞到结束，而应该有：

- operation id
- status
- started_at / finished_at
- result / error
- 后台 worker

### 3.8 Catalog Snapshot

运行时能力快照，不等于平台主数据。

当前 `graph / model / tool` 更接近这个概念：

- 上游发现
- 平台缓存
- 平台治理覆盖

而不是平台唯一真相源。

## 4. 当前设计里，什么是对的

别把现状说得一无是处。当前 `platform-api` 已经做对了几件关键事：

- 平台控制面和 `runtime-service` 已经拆层
- 已经从 catch-all 透明代理收敛为显式路由
- 已经开始做项目边界治理和 audit
- 已经引入 assistant 映射、runtime catalog、testcase 聚合
- 平台数据库主数据和结果域服务没有完全揉在一起

所以重构不是推翻方向，而是把内部工程结构补到平台级标准。

## 5. 一个正常的平台后端应该有哪些能力

按长期标准看，一个成熟的平台控制面后端，至少要把下面这些能力做成一等公民。

### 5.1 身份与访问控制

- 用户认证
- token 生命周期
- 用户状态与角色
- 项目级授权
- 后续可扩展到 SSO / OIDC / service account / API key

### 5.2 组织与资源层级

- tenant
- workspace / project
- agent / assistant
- runtime catalog object
- document / testcase / thread 等资源归属

### 5.3 资源目录与治理

- assistant 作为平台主数据
- graph/model/tool 作为 catalog snapshot + policy overlay
- 不同项目对资源可见性、启用状态、默认值的治理

### 5.4 运行时网关

- 受控访问 upstream runtime
- 项目边界注入
- 协议整形
- 统一错误映射
- 流式接口支持

### 5.5 作业中心

- refresh
- export
- sync
- batch action
- 长耗时任务状态查询

### 5.6 审计与可观测性

- request id
- audit event
- 结构化日志
- metrics / trace
- 失败分类
- 下游调用可追踪

### 5.7 配置与密钥治理

- 环境配置分层
- 敏感信息不允许生产默认值
- 后续支持外置配置与密钥引用

### 5.8 API 治理

- 稳定 schema
- 统一分页
- 统一错误码
- 幂等策略
- 长任务协议
- 版本演进规则

## 6. 目标架构

### 6.1 推荐目录骨架

```text
apps/platform-api/app/
  core/
    config/
    security/
    context/
    observability/
    db/
    errors/
  modules/
    identity/
    iam/
    tenants/
    projects/
    assistants/
    runtime_catalog/
    runtime_gateway/
    testcase/
    announcements/
    audit/
    operations/
  adapters/
    langgraph/
    interaction_data/
    notifications/
  entrypoints/
    http/
    worker/
```

### 6.2 各层职责

#### `core/`

放全局共享但不属于具体业务模块的基础设施：

- settings
- auth token
- request context
- db session / unit of work
- 通用错误
- logging / trace / audit helper

#### `modules/`

按领域拆模块，每个模块至少收敛 4 层：

```text
modules/projects/
  domain/
  application/
  infra/
  presentation/
```

推荐职责如下：

- `identity`：登录、refresh token、密码、当前用户
- `iam`：角色、授权策略、资源访问判定
- `tenants`：租户与组织层
- `projects`：项目、成员、归属
- `assistants`：平台 assistant 主数据与配置
- `runtime_catalog`：graph/model/tool 快照与治理
- `runtime_gateway`：threads/runs/assistants/graphs 的平台受控代理
- `testcase`：testcase 管理接口、导出、对 interaction-data-service 的聚合
- `announcements`：公告中心
- `audit`：审计查询与事件模型
- `operations`：异步任务中心

#### `adapters/`

所有外部系统接入统一收进 adapter：

- LangGraph
- interaction-data-service
- 未来的对象存储、通知、SSO

约束：

- adapter 可以知道 HTTP、SDK、headers
- application 层只能依赖 adapter interface，不直接依赖 FastAPI `Request`

#### `entrypoints/`

- `http/`：FastAPI router、依赖注入、response schema
- `worker/`：后台任务入口

## 7. 目标开发范式

这部分是后面要沉淀成团队标准和 AI Harness 标准的核心。

### 7.1 Route Handler 必须变薄

HTTP 层只做 5 件事：

1. 解析请求
2. 取上下文
3. 调用 use case
4. 把 domain result 转成 response schema
5. 映射错误

禁止继续把下面这些逻辑堆进 router：

- 复杂授权判定
- 多步事务编排
- 大量字段合并
- 上游调用细节
- Excel / 文件拼装

### 7.2 服务层不能再依赖 FastAPI Request

后面要逐步把：

- `Request`
- `request.app.state`
- `request.headers`
- `request.state`

从业务服务层里清出去。

业务层应该拿到的是这些明确对象：

- `ActorContext`
- `ProjectContext`
- `AppSettings`
- `UnitOfWork`
- `LangGraphGatewayPort`
- `InteractionDataPort`

### 7.3 Repository 必须按模块拆

不能再继续扩写 `db/access.py` 这种全域访问大文件。

建议拆成：

```text
modules/users/infra/user_repository.py
modules/projects/infra/project_repository.py
modules/assistants/infra/assistant_repository.py
modules/runtime_catalog/infra/catalog_repository.py
```

原则：

- 一个 repository 只服务一个模块
- 跨模块聚合由 application 层编排，不通过“万能 access.py”解决

### 7.4 一次请求尽量只进入一次主事务

后面要减少这种情况：

- 授权开一次 session
- 业务再开一次 session
- 序列化时又顺手查一次

目标是：

- request scoped context
- request scoped unit of work
- 明确事务边界

### 7.5 上游系统统一走 adapter

不要再在各个模块里各自拼：

- URL
- headers
- timeout
- error mapping

这些东西应该统一收在 adapter 层。

### 7.6 API 必须 typed

后面新增或重构的接口，原则上都要有：

- request model
- response model
- error code enum 或明确错误口径

避免继续大量返回：

- `dict[str, Any]`
- `Any`
- 原始 upstream payload

### 7.7 长耗时动作必须进入 operation/job 模式

优先纳入：

- catalog refresh
- testcase export
- 未来的批量同步
- 未来的 tenant / workspace 初始化任务

推荐协议：

- `POST /operations`
- 返回 `202` + `operation_id`
- `GET /operations/{id}`

### 7.8 安全默认值要区分 dev 和 prod

开发环境允许：

- bootstrap admin
- 本地默认账号
- 简化配置

生产环境必须：

- 默认 secret 不允许启动
- 默认 admin 不允许自动创建
- docs 开关默认关闭
- 必要安全配置缺失时直接 fail fast

### 7.9 测试要按层次补齐

目标至少分四层：

- domain / application unit tests
- repository tests
- API integration tests
- real upstream opt-in tests

## 8. 建议的模块关系

### 8.1 Assistant 模块

定位：

- 平台主数据
- 维护 assistant 的身份、配置、治理字段、上游映射

它不负责：

- 真正执行 run
- 线程历史存储

### 8.2 Runtime Catalog 模块

定位：

- 维护 `graph / model / tool` 的 catalog snapshot
- 维护项目级治理覆盖

它不负责：

- 替代 runtime 成为唯一真相源

### 8.3 Runtime Gateway 模块

定位：

- 平台受控访问 LangGraph upstream
- 注入项目边界
- 统一错误口径
- 统一流式协议包装

它不负责：

- 承担业务智能体逻辑
- 承担平台主数据存储

### 8.4 Testcase 模块

定位：

- 平台权限
- 协议整形
- 聚合导出

它不负责：

- 自己成为 testcase 真正存储层

### 8.5 Operations 模块

定位：

- 长任务跟踪与执行编排
- 后续 worker 主入口

## 9. 迁移顺序

这次重构不建议一把梭哈。正确顺序应该是从“先立框架，再搬能力”开始。

### P0：冻结坏味道继续扩散

先做这些约束：

- 新功能不要再往 `db/access.py` 继续堆大块逻辑
- 新功能不要再让业务服务依赖 `Request`
- 新功能不要再新增裸 `dict[str, Any]` 风格 response
- 新功能先写清模块归属

### P1：搭骨架

目标：

- 建 `core/`、`modules/`、`adapters/`、`entrypoints/` 目录
- 建 request context / actor context / project context
- 建 request scoped unit of work
- 把共享错误和 response 约定收口

这一步不追求大规模迁功能，先把新世界搭出来。

### P2：先迁最稳定的控制面模块

建议顺序：

1. `identity`
2. `projects`
3. `users`
4. `members`
5. `announcements`

原因：

- 这些模块边界相对清晰
- 不强依赖复杂 upstream
- 最适合先沉淀新的开发范式

### P3：迁平台主数据和治理模块

建议顺序：

1. `assistants`
2. `runtime_catalog`
3. `runtime_policies`
4. `audit`

这一步开始把“平台主数据”和“catalog snapshot”正式拉开。

### P4：迁 runtime gateway

把下面这批能力收进 `runtime_gateway`：

- threads
- runs
- assistants proxy
- graphs proxy

重点不是把接口名改花，而是把：

- adapter
- error mapping
- scope injection
- stream handling

真正做成一层。

### P5：引入 operations + worker

优先接入：

- catalog refresh
- export
- 未来批量任务

这一步完成后，平台后端的长期形态才算真正稳住。

### P6：测试与生产口径补齐

最后补：

- 自动化测试矩阵
- 生产安全开关
- 监控与指标
- 文档、runbook、验收清单

## 10. 一条新需求进来，应该怎么判断改哪里

以后无论是人还是 AI 代理，先按这 6 个问题过一遍：

1. 这是平台治理能力，还是 runtime 执行能力？
2. 这个功能的真相源在哪里？
3. 这是同步请求，还是应该变成 operation/job？
4. 它属于哪个模块？
5. 谁负责权限？谁负责边界注入？
6. 它的稳定 request/response 契约是什么？

只要这 6 个问题说不清，就不要急着开写。

## 11. 和根 README 中 Harness 思想的关系

根 `README.md` 里提到的 Harness，不是“AI 随便写代码”，而是“在明确边界、稳定契约、可复用范式里持续开发”。

这份蓝图就是 `platform-api` 这部分 Harness 的具体化：

- `边界`：把控制面、结果域、运行时网关、catalog、operation 分开
- `契约`：把 typed API、统一错误、operation 协议、上下文模型写清楚
- `范式`：规定 route、use case、repository、adapter、worker 的落地方式
- `闭环`：后续每次重构都能按模块迁移、按清单验收、按文档对齐

也就是说：

> Harness 是总纲，这份蓝图是 `platform-api` 在 Harness 之下的专用施工图。

## 12. 当前我们先拍板的结论

为了避免后面反复讨论，这里先明确几条当前结论：

- 正式目标是“模块化单体控制面”，不是立刻拆微服务
- `platform-api` 只做控制面治理、协议整形、聚合和边界控制
- 智能体执行逻辑仍然留在 `runtime-service`
- `interaction-data-service` 继续作为结果域服务，不回灌到平台主数据层
- assistant 是平台主数据
- graph/model/tool 是 catalog snapshot + policy overlay
- 长耗时动作后续要统一收敛到 operations/worker

## 13. 这份蓝图的验收标准

当我们说“`platform-api` 完成第一阶段架构重构”时，至少要满足：

- 新增功能已经可以按模块目录落地，而不是继续堆在旧巨石文件里
- 业务服务层不再直接依赖 FastAPI `Request`
- repository 已按模块拆分，`db/access.py` 停止继续膨胀
- request context、actor context、project context、unit of work 已成型
- 至少一个长耗时动作切到 operation/job 模式
- 至少一批核心接口已改成 typed request/response
- 测试不再只剩 auth 基础能力

## 14. 参考资料

为了避免这份蓝图完全拍脑袋，当前主要参考了这些公开资料：

- FastAPI Bigger Applications  
  https://fastapi.tiangolo.com/tutorial/bigger-applications/
- Azure Architecture - Control planes for multitenant solutions  
  https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/considerations/control-planes
- Azure Architecture - Gateway Aggregation pattern  
  https://learn.microsoft.com/en-us/azure/architecture/patterns/gateway-aggregation
- Azure Architecture - Asynchronous Request-Reply pattern  
  https://learn.microsoft.com/en-us/azure/architecture/patterns/asynchronous-request-reply
- AWS Well-Architected SaaS Lens - Hide tenant details / tenant context  
  https://docs.aws.amazon.com/zh_tw/wellarchitected/latest/saas-lens/layers-hide-tenant-details.html
- Backstage Software Catalog  
  https://backstage.io/docs/next/features/software-catalog/
