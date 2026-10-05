# 平台 cron 与执行前拒绝留痕

日期：2026-10-05。任务：T1.2、T2.1—T2.3、T3.0、T4.1—T4.2。执行语义由用户批准。

## 实现

- Platform API modules/scheduled_tasks/{schemas,router,service}.py：10 条产品接口、once、时间预览、owner/project/tenant 隔离、manual reservation 与受管 Run 幂等、原生历史分页和审计补码。
- adapters/langgraph/runtime_gateway_upstream.py：原生 cron CRUD 与 Runtime 内部预览/历史 HTTP；entrypoints/http/router.py 注册接口，audit/http_resolution.py 注册动作。
- core/security/tokens.py、runtime_gateway/application/service.py：cron-read/write，内部 scheduled_config 与 enqueue 仅服务端路径开放，公开客户端白名单保持。
- runtime_gateway/application/thread_access.py：fresh/manual Thread reservation 并发登记复用；pending_actor 核对项目和创建者。
- runtime_catalog/presentation/http.py、auth_context.py：HMAC scheduled-authorization，shape/UUID/scope/30 秒窗口，当前身份与策略回查，记录执行拒绝与结果。
- Runtime runtime/scheduled.py：四个 factory 图构造前聚合核验；ainvoke/v3 stream 审批失败和结果上报；原生 Run 为回查/审计故障的持久兜底。
- Runtime http/crons.py、webapp.py、auth/platform.py、runtime/auth.py：内部原生时间预览、过滤先于 SQL 分页的历史、cron-read/write 与 run-create 边界。
- tests/test_scheduled_tasks.py、tests/runtime/test_scheduled.py、scripts/verify_scheduled_tasks.py：校验、签名、guard 与真实多服务探针。Thread 授权旧 fixture 补 editor 角色以匹配当前生产授权。

## GraphHarbor 接续补齐

post41：有限表达式耗尽保留最后 Run；执行 payload 编辑刷新受信身份；通用 metadata SQL 分页；Thread 创建 PG 原子唯一；Thread 删除后的 queued Run 进入 error/thread_not_found，terminal event 以空 FK 保存并在 trace 保留原 Thread ID。没有平台业务表或非标准公开 cron API。

## 验证与发布

GraphHarbor CI 126 passed/4 skipped；PyPI 双包 post41 已发布并独立安装。平台 pyproject/uv.lock/.venv 同步 post41，锁校验通过。发布包探针 22 个原生 Run：8 success、14 预期 error；覆盖并发、响应丢失对账、身份/凭据/项目/Agent/模型/Thread 失效与历史。完整命令和最终回归见 verification.md。

没有修改同事前端文件，没有 commit/push/tag，没有生产平台部署或现役栈重启。
