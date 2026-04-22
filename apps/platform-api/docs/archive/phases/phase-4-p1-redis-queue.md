# Phase 4 P1 - Redis Queue Backend 落地说明

这份文档记录 `operations` 从 `db_polling` 单后端，扩成 `db_polling + redis_list` 双后端的当前收口。

## 当前结论

- 本地 / smoke / 演示默认仍建议用 `db_polling`
- 已经补齐第一版正式 Redis queue backend：
  - `operations_queue_backend=redis_list`
  - `operations_redis_url`
  - `operations_redis_queue_name`
- 业务 executor、operation 状态机、前端协议都没有被推翻
- Redis backend 只替换：
  - submit dispatch
  - worker dequeue
  - retry requeue

## 为什么先落 `redis_list`

当前目标是把“正式队列后端”先接通，而不是一上来把 worker 调度系统写成巨型中间件套娃。

`redis_list` 这一版的收益：

- 代码简单，容易验证
- 提交、消费、重试链路已经真实走 Redis
- 不需要把现有 operation 状态机、审计、artifact、前端治理页全部返工

当前不急着直接上：

- Redis Streams consumer group
- dead letter queue
- worker heartbeat / lag metrics
- 多消费者分片治理页

这些属于下一轮稳定性和可观测性增强，不该和当前 phase-4/P1 混在一起搞成一锅粥。

## 当前实现

### 1. Dispatcher

- `db_polling`
  - `DatabasePollingOperationDispatcher`
  - submit 时不实际入队，worker 直接扫数据库 `submitted`
- `redis_list`
  - `RedisListOperationQueue`
  - submit 时把 `operation.id` 推入 Redis list

### 2. Worker

- `db_polling`
  - 继续走 `claim_next_submitted(...)`
- `redis_list`
  - 先从 Redis list `BRPOP`
  - 再按 `operation_id` 做条件 claim
  - 避免重复消费时直接把已完成任务重新执行

### 3. Retry

- 重试不是只改数据库状态
- 如果当前 backend 有 dispatcher，retry 成功回队时会再次 `dispatch`
- 所以 `redis_list` 下失败重试会重新进入 Redis 队列

## 当前配置

环境变量前缀：`PLATFORM_API_V2_`

- `OPERATIONS_QUEUE_BACKEND`
  - `db_polling` | `redis_list`
- `OPERATIONS_REDIS_URL`
  - 仅 `redis_list` 时必填
- `OPERATIONS_REDIS_QUEUE_NAME`
  - 默认：`platform.operations`

## 当前边界

- 当前 Redis backend 是 `list`，不是 `stream`
- 当前没有 dead letter queue
- 当前没有 worker consumer group / claim timeout / pending replay
- 当前 Redis client 采用短连接调用，优先保证边界正确和资源不泄漏

## 为什么这版已经够用

因为我们真正需要先验证的是：

- 平台是否真的能切换到外部队列
- 提交 / 消费 / retry 是否还能维持 operation 生命周期一致
- 业务 executor 是否完全不需要知道自己跑在 DB polling 还是 Redis queue 上

这些现在都已经成立。

## 后续演进建议

### Phase 4 / P2

- 增加 worker backlog / dequeue error / retry count 指标
- 增加 Redis queue 故障排查手册

### Phase 4 / P3 之后

- 如果并发 worker 和稳定性要求上来，再升级到：
  - Redis Streams
  - consumer groups
  - dead letter
  - pending replay

## 验收建议

1. 设置：
   - `PLATFORM_API_V2_OPERATIONS_QUEUE_BACKEND=redis_list`
   - `PLATFORM_API_V2_OPERATIONS_REDIS_URL=redis://127.0.0.1:6379/0`
2. 启动 `platform-api-v2`
3. 启动 worker
4. 从前端触发：
   - runtime refresh
   - assistant resync
   - testcase export
5. 确认 operation 仍然能正常：
   - submitted
   - running
   - succeeded / failed
6. 对一个带 retry 的 operation 验证失败后会重新入队
