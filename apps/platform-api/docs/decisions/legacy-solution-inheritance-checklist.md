# 旧方案优点继承清单

这份清单不是要把旧 `platform-api` 原样搬回来，而是把旧方案里真正做对的东西抽出来，作为 `platform-api` 后续重构的硬性继承项。

> 更新说明：
> `runtime_service` 与 `platform-api` 现在都已切到新 runtime contract。
> 下面凡是提到 `config/configurable` 与 `context` 的兼容处理、`config.metadata.project_id` 作为真源等表述，均视为**已废弃旧决策**，不得再作为当前实现依据。

## 1. 必须继承的优点

### 1.1 官方 SDK 优先，而不是自写原生 client

旧方案最值钱的一点，就是没有在 `assistants / threads / runs / crons` 这些 LangGraph 原生资源上重新造轮子。

后续必须继承：

- 优先使用官方 `langgraph_sdk`
- 平台层只做权限、边界、审计、对象聚合
- 不在平台层重复维护 LangGraph API 细节

这是第一条，不满足这一条，后面都会重新走偏。

### 1.2 字段白名单清晰

旧方案在这些 service 里做得比较好：

- `assistants_service.py`
- `threads_service.py`
- `runs_service.py`

每个操作只允许透传明确字段，比如：

- run create / stream / wait 的字段集分开
- cron create / update / search / count 的字段集分开
- thread state / history / update 的字段集分开

这个优点必须继承，因为它能避免：

- 前端乱传字段
- 上游升级后平台 silently 接收脏参数
- 不同 endpoint 之间的语义串味

### 1.3 scope guard 独立出来

旧方案把这些东西单独放进了 `scope_guard.py`：

- `assistant` 是否属于当前项目
- `thread` 是否属于当前项目
- `project_id` 注入
- 运行时 project scope 注入

这件事做对了。

后续必须继续保持：

- ownership 校验不是 presentation 的临时代码
- 也不是 adapter 的顺手逻辑
- 它应该是独立、可复用、可测试的 application 规则

### 1.4 流式能力没有阉割

旧方案没有只做最简单的 JSON 接口，而是把这些关键能力都带上了：

- `runs.stream`
- `runs.join_stream`
- `runs.wait`
- `runs.create_batch`
- `crons`
- `history`
- `state`

这个优点必须继承。

因为工作台、chat、agent 执行体验里，真正关键的不是“能发请求”，而是：

- 能持续流式接消息
- 能 join 已存在 run
- 能 cancel
- 能看 history / state / checkpoint

如果这些被砍掉，平台前端迟早退化成假工作台。

### 1.5 路由薄，编排清楚

旧方案的路由虽然还是偏 FastAPI 风格，但有一个优点：

- 路由主要管入参、guard、response
- 真正的上游调用被收进 service

后续必须把这个优点保住，并在 v2 里再进一步：

- route 薄
- application service 只做编排
- upstream adapter 只做调用
- 不要把 HTTP 细节、权限细节、上游字段细节揉成一团

### 1.6 forwarded headers 处理一致

旧方案有统一的 header 透传逻辑：

- `authorization`
- `x-tenant-id`
- `x-project-id`
- `x-request-id`
- `x-api-key`

这个必须继续继承。

否则排查问题时会非常恶心：

- 鉴权不一致
- request trace 丢失
- 跨服务审计串不起来

### 1.7 `project_id` 注入规则已按新 contract 收口

当前正式规则：

- `context.project_id` 是业务真源
- 顶层 `metadata.project_id` 允许保留，作为检索 / 审计冗余
- `config.metadata.project_id` 不再作为主链注入口
- `config.configurable` 不再承接业务 project scope

这不是兼容规则，而是当前正式标准。

### 1.8 运行能力完整，不只盯着 happy path

旧方案的优点是覆盖了完整运行面，而不是只做：

- create
- list
- detail

真正该继承的是完整运行闭环：

- create
- wait
- stream
- join
- cancel
- batch
- cron
- history
- state

这套闭环才是 agent 平台最重要的能力面。

## 2. 旧方案里不该继承的地方

不是旧方案所有东西都要继承，下面这些就不该带进来。

### 2.1 不要把 `Request` 绑进业务层

旧方案很多 service 直接收 `Request`：

- 用起来快
- 但会让 application service 过度依赖 FastAPI

`platform-api` 不应该回退到这个写法。

正确做法：

- 在 adapter/factory 层处理 request-scoped client
- application 层拿 protocol / adapter 实例

### 2.2 不要让 HTTPException 成为业务语言

旧方案里不少异常直接是 `HTTPException`。

这个在 v2 里不应该继续扩大。

应该保持：

- application 讲平台错误
- presentation 再把平台错误映射成 HTTP

### 2.3 不要把“旧代码能跑”误当成“结构最优”

旧方案的目标是尽快把 LangGraph 工作台跑起来，所以很多东西是实用主义产物。

这些不能反向污染 v2：

- 数据聚合和上游调用耦在一起
- 框架上下文下沉太深
- 平台标准没有单独抽象成协议/规范

## 3. 后续重构时的继承检查表

每次做 LangGraph 相关重构，都按这张表过一遍。

### 3.1 adapter 设计检查

- [ ] 原生 LangGraph 资源是否优先走官方 SDK
- [ ] HTTP fallback 是否只保留 SDK 缺口项
- [ ] forwarded headers 是否统一
- [ ] 字段白名单是否显式定义
- [ ] stream / wait / join / cancel / cron 是否都覆盖

### 3.2 application 规则检查

- [ ] `project_id` 注入是否统一
- [ ] assistant ownership 校验是否存在
- [ ] thread ownership 校验是否存在
- [ ] `context.project_id` 是否是唯一业务真源
- [ ] graph target / assistant target 允许逻辑是否保留

### 3.3 平台质量检查

- [ ] 权限在 application，而不是散落 route
- [ ] 审计 action 可归类
- [ ] 错误映射有统一语义
- [ ] 自动化测试覆盖 stream 和错误路径
- [ ] 前端依赖的运行面没有缩水

## 4. 一句话原则

旧方案真正值得继承的，不是“那份代码”本身，而是这套思想：

> LangGraph 原生能力尽量贴官方；平台层专注治理、边界、聚合和审计。

后面只要偏离这句话，代码大概率又会慢慢长歪。
