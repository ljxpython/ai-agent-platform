# 定时 Agent 任务方案

## 已批准范围

2026-10-05 用户批准平台后端继续实施：CRUD、暂停/恢复、手动触发、历史分页、once 和预览；每个 Run 开始前一次聚合授权，失效拒绝并留痕；暂停/删除只阻止未来派发，已接受 Run 按正常生命周期处理；无人值守审批转失败。前端由同事开发，契约见 [frontend-handoff.md](frontend-handoff.md)。

GraphHarbor 是唯一 scheduler 和 Run 事实源。平台不新增 cron 表、occurrence 表、迁移或调度 worker，不保存用户 JWT，不承诺超出锁定 LangGraph 版本的任意 exactly-once。定义是创建者私有资源，同时受当前租户、项目权限约束。首期支持每次新建 Thread 或复用有 comment 权限的 Thread。

## DeerFlow 对照与成果

参考仓库：`/Users/lijiaxin/PyCharmMiscProject/research/deer-flow`。

| 层 | DeerFlow 源码与做法 | 本平台成果与边界 |
|---|---|---|
| 前端 | `frontend/src/app/workspace/scheduled-tasks/page.tsx`、`frontend/src/core/scheduled-tasks/`；表单、列表、历史和操作反馈 | 同事实现页面、客户端类型、时间展示和 Run/Thread 跳转；服务端决定时间与授权 |
| 产品 API | `backend/app/gateway/routers/scheduled_tasks.py`；CRUD、预览、触发和历史 | Platform API `modules/scheduled_tasks/` 提供 10 条接口，复用项目权限、模型决议、错误出口、审计和 Run 幂等 |
| 调度 | `backend/app/scheduler/service.py`、`backend/packages/harness/deerflow/scheduler/schedules.py`；数据库领取、恢复、容量约束 | 直接复用 GraphHarbor 原生 PG scheduler、持久队列与 worker |
| 存储 | `backend/packages/harness/deerflow/persistence/scheduled_tasks/` 与 `scheduled_task_runs/`；产品表与 occurrence | 产品定义存在原生 cron metadata.task_spec；Run cron_id 关联，原生 Run 为终态事实，平台审计补拒绝原因 |
| 执行 | `backend/app/gateway/services.py::launch_scheduled_thread_run`；复用正常 Run 生命周期 | 自动任务由原生 scheduler 建 Run；手动触发走受管 gateway；Runtime 图构造前聚合核验，审批失败 |

借鉴输入字段、服务端预览、逐次历史、UTC 存储和原子领取。DeerFlow 的 interval、通知、复制、聊天内建任务、活跃任务编辑锁不纳入首期。列表仅 enabled 筛选和分页，无服务端标题搜索、排序参数或最近 Run 汇总。

## 三层实现位置

### Platform API：产品契约与当前授权

`apps/platform-api/src/platform_api/modules/scheduled_tasks/{schemas,router,service}.py`：

- Schedule / TaskCreate / TaskUpdate 校验 once、五段 cron、IANA 时区、带偏移时间与字段白名单；preview() 转发 Runtime，once 转 UTC 七字段有限表达式。
- ScheduledTasksService 封装原生 create/get/search/count/update/delete，任务按 tenant/project/owner 过滤；非时间编辑保留下次时间。
- _payload() 复用 Agent/模型检查和 Thread ACL，将长期 HMAC marker 保存于内部 config；浏览器不接收 marker、身份快照或模型连接凭据。
- trigger() 复用 RuntimeGatewayService.create_thread_run() 和 run_requests。fresh Thread 使用任务 ID + 用户幂等键的 UUID5 reservation；同动作重试复用 Thread 与 Run，内容改变按既有 409 规则处理。
- history() 从 Runtime 读取过滤后分页的原生 Run，execution_errors() 按当前页 Run ID 补审计错误；删除定义后历史仍可读取。
- authorize_execution() 通过既有 actor loader 检查当前身份、服务账号凭据、成员授权、项目、Agent、模型、Thread 与策略；拒绝和结果写 scheduled_task.execution 审计。

路由注册位于 entrypoints/http/router.py；内部回查位于 modules/runtime_catalog/presentation/http.py；cron 委托枚举和 HTTP 审计映射同步更新。普通 /api/langgraph 20 条矩阵保持独立，产品入口为 /api/scheduled-tasks。

### Runtime Service：执行前授权与无人值守策略

`apps/runtime-service/src/runtime_service/runtime/scheduled.py::scheduled_execution()` 包装 reference、workflow、showcase、dearflow 四个 graph factory。定时和手动任务在图、模型和工具构造前回查平台，以当前角色、模型引用和工具策略替换保存快照；每次 Run 一次聚合核验，运行中不周期重验。

内部回查使用共享 ACL HTTP client，HMAC 绑定时间戳、接口和正文，30 秒窗口；平台校验 UUID、shape 和 tenant/project/owner/credential/Agent 与 marker 绑定。平台不可用则拒绝，原生 Run 保留失败终态；平台审计不可用不抹掉 Run 事实。

_ScheduledGraph 覆盖 ainvoke 与 LangGraph v3 stream；interrupt 转 scheduled_task_approval_required，不自动 approve。普通 Run 无 marker 时仍走原 factory。

http/crons.py 提供内部预览和历史：预览调用 GraphHarbor next_cron_date()，历史先过滤 cron/project/owner/tenant 再 SQL 分页。auth/platform.py / runtime/auth.py 增加 cron-read/write；执行 payload 新建/编辑仍需 run-create 委托。

### GraphHarbor：通用 Agent Server 能力

双包 0.13.0.post41 已发布 PyPI，平台 Runtime 已锁定并安装发布包。langhost/core_api.py 与 langgraph_runtime_pg/cron.py 对齐锁定 langgraph-api==0.13.0 / langgraph-sdk==0.4.3 的参数、时区、截止时间、身份签名、领取、派发与恢复，不接入平台业务表。

接续验证补齐：有限表达式最后一次保留 Run 并禁用定义；编辑执行 payload 刷新可信身份，暂停不覆盖；通用 RunRepository.search() 元数据 SQL 分页；Thread 创建原子唯一；Thread 已删的 queued Run 进入 error 并保存 terminal event。历史和预览是应用内部接口，未增加 GraphHarbor 非标准公开产品 API。

## 时间、状态与恢复

cron 使用五字段表达式，原生 parser 处理时区/DST和 end_time。once 是未来、带偏移、整秒、年份截至 2099 的 run_at，转 UTC 有限表达式；入队后定义 exhausted，Run pending/running/success/error 等状态另行展示。paused/exhausted 定义可手动执行，不推进计划时间。

暂停/删除不取消已接受 Run；编辑影响未来 Run，无活跃编辑锁。错过节拍、PG 多副本行锁、持久队列和重启恢复复用原生语义，不补跑所有错过节拍。派发事务失败不推进时间；提交后结果未知保留原幂等键重试对账。

没有新业务表迁移。回退先暂停 cron，等待或显式处理已接受 Run，再回退应用与依赖；不要先部署不支持 marker 的旧 Runtime。隔离库验证暂停阻止派发、删除后历史读取；未在生产执行应用回退或数据库恢复。

## 验收与交付边界

验证见 [verification.md](verification.md)：发布包真实 HTTP → cron → scheduler → ProductionWorker → Runtime guard → 平台 HMAC 回查 → Run 历史；覆盖 once、manual、分页、并发幂等、响应丢失、撤权、服务账号、Thread 删除。

交付为后端代码、隔离验收、GraphHarbor 发布和前端契约。平台远端部署、前端页面与浏览器联合验收后续完成；没有重启现役本地平台栈，不将隔离验收表述为生产上线。
