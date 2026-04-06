# Platform API V2 工程标准与 Harness

这份文档是 `platform-api-v2` 的开发标准。

后面无论是人写代码，还是 AI 代理写代码，都必须遵守这里的规则。

## 1. 总原则

- 不以兼容旧 `platform-api` 目录结构为目标
- 不把 `runtime-service` 的执行逻辑搬进控制面
- 不允许继续堆“万能 access.py”
- 不允许继续让业务服务层依赖 FastAPI `Request`
- 不允许用“先跑通再说”破坏权限和审计边界

## 2. 目录标准

### 2.1 只允许 4 类顶层目录

`app/` 下只保留：

- `core/`
- `modules/`
- `adapters/`
- `entrypoints/`

### 2.2 禁止回到旧式分层

禁止重新长出这种结构：

- 一个 `api/` 包挂满所有业务
- 一个 `services/` 包塞满所有 use case
- 一个 `db/access.py` 管全域数据访问

## 3. Route Handler 标准

HTTP handler 只允许做这 5 件事：

1. 解析 request
2. 取上下文
3. 调用 use case
4. 组装 response DTO
5. 映射错误

禁止在 handler 里直接写：

- 复杂权限判定
- 多步业务编排
- 多个 repository 调度
- 上游 HTTP 细节
- 文件导出内容拼装

## 4. Use Case 标准

每个 use case 必须：

- 有明确输入模型
- 有明确输出模型
- 有明确权限边界
- 有明确事务边界
- 有明确错误口径

推荐命名：

- `CreateProject`
- `ListProjectMembers`
- `CreateAssistant`
- `RefreshRuntimeCatalog`

## 5. Repository 标准

- repository 必须按模块拆分
- 一个 repository 只服务一个领域模块
- 跨模块数据组合由 application 层完成

禁止：

- 再建一个新的全局 `access.py`
- 让 repository 顺手承接业务规则

## 6. Adapter 标准

所有外部依赖统一走 adapter。

当前必须收进 adapter 的包括：

- LangGraph upstream
- interaction-data-service

后续包括：

- Redis
- notification
- object storage

adapter 允许知道：

- URL
- headers
- timeout
- retries
- upstream error mapping

application 层不允许知道这些细节。

## 7. 权限标准

### 7.1 平台级和项目级必须分离

平台级角色只控制：

- 用户管理
- 全局 catalog refresh
- 平台配置
- 全局审计

项目级角色只控制：

- 项目资源读写
- assistant/project policy/testcase/project audit

### 7.2 禁止混用

禁止再出现：

- 任意项目 admin 拥有全局管理权限
- 平台角色判定依赖“是否在任一项目是 admin”

## 8. 审计标准

### 8.1 必须记录的字段

- request_id
- plane
- action
- target_type
- target_id
- actor_user_id
- actor_subject
- tenant_id
- project_id
- result
- status_code
- duration_ms

### 8.2 action 命名

统一用：

`{domain}.{resource}.{verb}`

示例：

- `identity.session.created`
- `project.member.removed`
- `assistant.updated`
- `catalog.model.refresh_requested`
- `runtime.run.cancelled`

### 8.3 不能只记 access log

只有 `method/path/status` 不算真正的审计。

审计必须能回答：

- 谁做的
- 对哪个资源做的
- 为什么失败
- 属于哪个平面

## 9. Operation / Job 标准

下列动作默认要纳入 `operations`：

- refresh
- export
- batch sync
- 大批量删除/修复

统一协议目标：

- `POST /operations`
- `GET /operations/{id}`
- `POST /operations/{id}/cancel`

## 10. 配置与安全标准

- dev 与 prod 的安全口径必须分开
- 不允许生产默认 secret
- 不允许生产自动 bootstrap 默认管理员
- docs 开关必须可控

## 11. 测试标准

至少分四层：

- unit tests
- repository tests
- API integration tests
- real upstream opt-in tests

任何权限或审计改动，都必须补对应回归测试。

## 12. AI Harness 标准

这里说的 Harness，不是让 AI 自由发挥，而是让 AI 在固定轨道里稳定产出。

### 12.1 AI 改动入口顺序

后面 AI 修改 `platform-api-v2`，默认顺序是：

1. 先看模块归属
2. 再看 request/response 契约
3. 再看权限边界
4. 再看审计影响
5. 最后才开始写代码

### 12.2 AI 不允许做的事

- 直接在 handler 里塞业务逻辑
- 直接跨模块读写 repository
- 为了赶进度跳过权限/审计
- 引入未被文档批准的新模式

### 12.3 AI 输出要求

任何结构性改动至少要同步：

- 对应模块文档
- checklist
- 验收方式

### 12.4 Harness 产物

最终 `platform-api-v2` 的 Harness 要包含：

- 架构蓝图
- 工程标准
- 权限标准
- 审计标准
- 阶段清单
- 验收清单

## 13. 当前拍板

后续 `platform-api-v2` 中任何不符合上述规范的旧式设计，都允许直接重写，不为旧结构让路。
