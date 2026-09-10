# Platform API 架构说明

2026-09-10 更新。本文描述当前代码组织；实施与验证见[重构工程](../../../../docs/projects/20260910-platform-api-refactor/README.md)。

## 服务与数据边界

Platform API 管理身份、IAM、项目、Agent、模型连接、策略、公告、审计和系统设置，并提供受控 Runtime 网关。
GraphHarbor 持有 Thread、Run、Checkpoint、Interrupt 的执行事实；Runtime 服务定义图、模型与工具装配。
平台不运行图，不保存运行状态镜像，不提供 Operations/队列/Worker，也不接入知识库或测试用例产品业务。

```text
platform-web / SDK → platform-api → GraphHarbor API → Runtime graphs / Worker
                         ↓                     ↓
                    Platform DB           Runtime DB / Redis
```

平台使用独立数据库、20 表空库 Alembic 基线；不迁移旧数据。模型连接以 UUID 引用，Agent 的执行键是 graph_id。
run_requests 仅记录请求幂等、授权参数和 Run 关联，不保存消息、执行终态或模型密钥。

## 代码组织

| 位置 | 用途 |
| --- | --- |
| main.py / config.py | 应用工厂、路由及环境配置 |
| bootstrap/lifespan.py | 初始化与关闭进程资源 |
| core/ | 数据库、上下文、错误、安全与观测原语 |
| modules/ | 平台业务与授权用例 |
| adapters/langgraph/ | 官方 SDK 与必要 HTTP/SSE 接入 |
| entrypoints/http/ | 系统接口、认证、请求上下文与审计中间件 |

identity、projects、users、service_accounts、announcements、audit、platform_config 使用直接文件布局：

```text
modules/<module>/
  router.py       HTTP 参数、依赖和响应（有业务路由时）
  contracts.py    command/query 等输入契约
  schemas.py      公开 DTO、枚举（需要时）
  service.py      业务用例、授权与事务边界
  models.py       SQLAlchemy 表（有持久化时）
  repository.py   查询与持久化
  records.py      查询结果结构（需要时）
```

identity 的 actors.py 负责当前用户身份加载；audit 的 http_resolution.py/http_writer.py 负责 HTTP 审计动作解析与写入。
users 复用 identity 的用户表，不复制 models.py。platform_config 的 HTTP 路由在系统入口，不新建无用 router。
agents、runtime_catalog、runtime_policies、runtime_gateway 和 IAM 保留有实际职责的分工，不强制统一目录深度。
直接从定义文件导入，简单模块不保留旧四层导入兼容包；不为单个仓储实现添加空 Protocol。

## 数据库与网络边界

SQLAlchemy 保持同步栈。纯 CRUD 的 service 和 FastAPI endpoint 使用 def，由框架在线程池执行。
异步用例使用 run_in_threadpool 执行完整数据库工作单元，Session 创建、查询、提交/回滚、关闭均在同一线程。
core.db.session_scope 直接使用 sessionmaker.begin()；不再包装 async UnitOfWork。
远端 HTTP 调用前关闭读事务，得到有效响应后另开短事务写库；不跨 await 持有 Session。
认证、策略签发和审计同样遵守线程边界。请求取消时保护审计收尾，取消不让线程池数据库操作变成孤立 Session。

## 权限与接入

ActorContext 是可信身份来源。平台角色与项目成员权限独立；平台管理员管理项目元数据不等于拥有项目内容权限。
网关只签发受控委托，启动/恢复检查当前 Agent、Graph、模型和工具授权。标准 Runs 与 Protocol 审批共用授权路径。
模型密钥加密存储、只写不读，Runtime 经受信通道兑换当前凭据。公开 JSON/SSE/error 删除内部委托和模型引用。
Graph/Tool 显式刷新走有限超时 HTTP；普通目录读取只读快照，不扫描宿主源码或创建上游 Assistant。

前端契约及后续调整见[前端交接](../../../../docs/projects/20260910-platform-api-refactor/05-frontend-handoff.md)。
