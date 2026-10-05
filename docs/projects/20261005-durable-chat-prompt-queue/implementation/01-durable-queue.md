# 实现记录

## 已完成

- GraphHarbor Run 增加 `queue_position` 迁移与严格同 Thread FIFO claim。
- Worker 在取消真正停止前保留 lease，避免下一条消息抢跑。
- GraphHarbor 新增 pending queue 的 CAS 调序/取消接口。
- platform-api 通过受控 thread-edit 委托暴露 `/threads/{thread_id}/runs/queue`。
- platform-web 提交即 enqueue，服务端 pending Run 负责展示、取消和调序；旧 localStorage 项只作为草稿恢复。
- 路由矩阵补充 queue 接口并通过。

## 验证限制

- 前端 `vue-tsc --noEmit` 通过。
- platform-api 路由矩阵通过（4 tests, 305 subtests）。
- GraphHarbor ruff check/format 通过。
- GraphHarbor PostgreSQL 集成测试因本机 `postgres` 密码认证失败未能执行。
