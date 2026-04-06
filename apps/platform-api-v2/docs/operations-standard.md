# Platform API V2 Operation / Job 标准

这份文档定义长任务的统一范式。后面凡是刷新、导出、批量同步这类动作，不准再直接在 HTTP 请求里傻等到结束。

## 1. 什么要进 operation

默认纳入 `operations` 的动作：

- catalog refresh
- testcase export
- batch sync
- 批量修复
- 大文件导入

经验规则：

- 超过 3 秒的动作优先考虑进 operation
- 需要重试、取消、历史追踪的动作必须进 operation

## 2. 标准状态机

统一状态：

- `submitted`
- `running`
- `succeeded`
- `failed`
- `cancelled`

必要时允许：

- `retrying`

禁止每个模块自己发明一套状态词。

## 3. 标准字段

每个 operation 至少有：

- `id`
- `kind`
- `status`
- `requested_by`
- `tenant_id`
- `project_id`
- `input_payload`
- `result_payload`
- `error_payload`
- `started_at`
- `finished_at`

## 4. 协议建议

- `POST /operations`
- `GET /operations/{id}`
- `POST /operations/{id}/cancel`

如果是资源专属动作，也可以暴露业务入口，但最终都要映射到 operation：

- `POST /catalog/graphs:refresh`
- 返回 `202` + `operation_id`

## 5. 执行器抽象

为了给后续 Redis / worker / queue 留口，执行器必须抽象成 port：

- `OperationDispatcher`
- `OperationRepository`
- `OperationExecutor`

当前可以先有本地实现：

- `InProcessOperationDispatcher`

后续无缝接入：

- Redis queue
- Celery / RQ / Dramatiq
- 独立 worker 进程

关键点是：HTTP 层永远只负责提交，不直接承接真正执行。

## 6. 幂等和重试

长任务要考虑：

- 同一请求是否允许重复提交
- 重试是否覆盖原任务还是新建任务
- 取消后是否允许恢复

推荐：

- 写接口支持 `idempotency_key`
- 重试保留原 operation 关系链

## 7. 审计联动

operation 生命周期必须写审计：

- `operation.submitted`
- `operation.started`
- `operation.succeeded`
- `operation.failed`
- `operation.cancelled`

## 8. 为什么这套设计能接 Redis

因为我们把边界提前钉死了：

- 状态机独立
- repository 独立
- dispatcher 独立
- executor 独立

后面要不要上 Redis，只是换掉 dispatcher 和 worker，不需要改业务 handler 和前端协议。
