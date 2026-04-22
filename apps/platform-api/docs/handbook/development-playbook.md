# Platform API Development Playbook

这份文档把原来的工程标准和 Harness 玩法收成一份正式开发手册。

目标只有一个：

> 让人和 AI 都按同一套高质量轨道开发 `platform-api`。

## 1. 开发总原则

- 不为兼容旧 `platform-api` 破坏新结构
- 不把 `runtime-service` 的执行逻辑搬进控制面
- 不在 handler 里塞复杂业务
- 不跳过权限、审计和 operation 设计
- 结构性改动必须同步文档、测试和验收说明

## 2. 开发前先看什么

推荐顺序：

1. `project-handbook.md`
2. `architecture.md`
3. `../standards/permission-standard.md`
4. `../standards/audit-standard.md`
5. `../standards/operations-standard.md`
6. `../delivery/change-delivery-checklist.md`
7. `../delivery/module-delivery-template.md`
8. `../delivery/runbook.md`

如果你要追历史过程，再去看：

- `../archive/phases/`

## 3. 目录和分层规则

`app/` 下只允许这几类主目录承担核心职责：

- `core/`
- `modules/`
- `adapters/`
- `entrypoints/`
- `bootstrap/`

禁止重新长回这些坏结构：

- 一个全局 `api/` 包塞满所有业务
- 一个全局 `services/` 包承接所有 use case
- 一个万能 `access.py` 管全域数据访问

## 4. HTTP Handler 规则

HTTP handler 只做这几件事：

1. 解析请求
2. 获取上下文
3. 调用 use case
4. 组装响应 DTO
5. 映射错误

不允许在 handler 里直接写：

- 多步业务编排
- 复杂权限判断
- 多 repository 协调
- 上游 HTTP 细节
- 导出内容拼装

## 5. Application / Use Case 规则

每个 use case 必须清楚回答：

- 输入是什么
- 输出是什么
- 权限边界是什么
- 审计动作是什么
- 事务边界是什么
- 错误码是什么

推荐命名：

- `CreateProject`
- `ListProjectMembers`
- `RefreshRuntimeCatalog`
- `CreateServiceAccountToken`

## 6. Repository 与 Infra 规则

- repository 按模块拆分
- 一个 repository 只服务本模块领域
- 跨模块组合由 application 层完成
- infra 只做持久化和适配落地，不承接业务语义
- 只读跨模块查询优先抽成 query port / query service，不允许直接反向依赖对方 infra repository
- 包级 `__init__.py` 只做轻量导出，不做 `Service` 的 eager re-export

禁止：

- 新建另一个全局 `access.py`
- 让 repository 顺手实现业务规则
- 在 `identity`、`projects`、`runtime_gateway` 这类核心模块之间直接互相咬 infra repository
- 通过 `module/__init__.py` 间接触发整棵模块树初始化

## 7. Adapter 规则

所有外部依赖统一走 adapter。

当前重点：

- `langgraph`
- `interaction_data`

后续可扩展：

- `redis`
- `notification`
- `object_storage`
- `oidc`

application 层只依赖抽象 port，不依赖具体 URL、header、timeout、retry 细节。

## 8. 权限 / 审计 / Operation 三件套

任何结构性能力都先问自己三个问题：

1. 谁可以做
2. 做完怎么追责
3. 如果很慢，是否要进 operation

如果这三个问题没想清楚，就不要开始写代码。

### 8.1 权限

- 平台级和项目级严格分离
- 统一基于 `ActorContext`
- handler 只调用 policy，不拼散装角色判断

### 8.2 审计

- 每个关键动作都要有 `action`
- 成功、失败、取消都要可追踪
- 敏感字段要脱敏

### 8.3 Operation

- 超过 3 秒的动作优先考虑进 operation
- 需要取消、重试、历史追踪的动作必须进 operation

## 9. AI Harness 工作流

Harness 不是让 AI 自由发挥，而是让 AI 沿着已定义轨道推进。

默认顺序：

1. 确认模块归属
2. 确认 request / response 契约
3. 确认权限边界
4. 确认审计影响
5. 确认是否进入 operation
6. 最后才开始写代码

### 9.1 AI 禁止事项

- 直接在 handler 里写复杂业务
- 直接跨模块读写 repository
- 遇到权限问题临时硬编码角色
- 审计没设计好就先不记
- 为兼容旧坏结构继续复制旧实现

### 9.2 AI 最低交付物

结构性改动至少同步：

- 代码
- 文档
- 测试
- 验收方式
- 如涉及新模块或新治理页，再补模板

## 10. 测试和验收要求

至少覆盖这些层次：

- unit tests
- repository / infra tests
- API integration tests
- adapter regression tests
- opt-in upstream tests

出现这些改动时，必须补回归：

- 权限模型变化
- 审计字段变化
- runtime gateway adapter 行为变化
- operation 状态机变化

## 11. 交付规范

每一轮结构性改动都要能落到这些文档入口：

- `../delivery/change-delivery-checklist.md`
- `../delivery/module-delivery-template.md`
- `../delivery/runbook.md`

真正要交付给团队时，必须能回答：

- 入口在哪里
- 如何启动
- 如何验证
- 风险在哪里
- 哪些文档已经更新

## 12. 一句话收口

这份 playbook 的作用，不是把开发变慢，而是防止代码重新烂回“谁都能写、谁都说不清”的状态。
