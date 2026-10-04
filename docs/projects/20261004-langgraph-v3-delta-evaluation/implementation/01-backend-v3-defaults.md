# Platform API 默认 v3

## 改动时间

2026-10-04

## 相关任务

- Task 2.1：后端默认 Run 版本统一为 v3

## 改动文件

- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- `apps/platform-api/tests/test_run_requests.py`

## 具体改动

- 将协议 promote、Run 创建和最终 launch payload 的缺省版本统一注入为 `v3`。
- 将 resume 从已保存 Run 缺失版本时的 fallback 从 `v2` 改为 `v3`。
- 更新默认流模式注释，明确这是 Run SSE 默认配置，v3 是默认消费协议，显式 v2 仍合法。
- 将请求测试的缺省期望改为 v3，同时继续覆盖显式 v2 和 v3。

## 兼容性

- `version` 仍只接受 `v2` 或 `v3`。
- 已保存 `kwargs.version == "v2"` 的历史 Run resume 仍上送 v2。
- 线程 Protocol v2 的 legacy envelope 逻辑未改动。

## 验证

- `uv run pytest -q tests/test_run_requests.py`：27 passed，2 subtests passed。
