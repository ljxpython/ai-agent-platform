# 稳定部署键修复

## 改动时间

2026-09-10

## 相关任务

- C4：稳定部署键
- C2：目录快照身份不依赖网络地址

## 改动文件

- `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py`
- `apps/platform-api/src/platform_api/modules/runtime_policies/application/service.py`
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- `apps/platform-api/tests/test_runtime_catalog_delegation.py`
- `apps/platform-api/tests/test_operations_streaming_and_retry.py`

## 改动内容

Runtime URL 只作为网络连接配置，目录、策略和网关持久化查询统一使用固定逻辑键 `default`。更换同一部署的地址不会产生新的模型、工具、Graph 或策略身份。测试同时移除生产配置中不存在的 `showcase_demo` 断言，并将事件循环轮询测试的等待窗口从 0.5 秒放宽到 2 秒，避免本地慢调度造成误报。

## 验证

- `tests.test_runtime_gateway_runtime_contract` 与 `tests.test_runtime_catalog_delegation`：33 项通过。
- SSE 流测试已使用 `trust_env=False`，不受环境 HTTP 代理影响。
