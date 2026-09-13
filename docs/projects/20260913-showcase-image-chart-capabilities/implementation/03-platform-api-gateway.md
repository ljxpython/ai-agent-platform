# 03 Platform API 图片网关实现记录

## 1. 任务概述

按照治理方案 [06-platform-api-image-gateway.md](../06-platform-api-image-gateway.md) 与消息契约 [04-platform-image-contract.md](../04-platform-image-contract.md)，实现 Platform API 作为纯资源代理的图片网关，包含：
1. `BinaryPayload` 与 Upstream Port 协议定义；
2. HTTP client 与 upstream 适配器的原始二进制上传和受限流式下载（20 MiB 熔断，响应头白名单）；
3. Service 层的项目与线程读写权限校验、`graph_id` 强制提取、最小 delegation scope 签发（`image-upload` 和 `image-read`）与 `ImageRef v1` 校验；
4. HTTP presentation 层的 `PUT /api/langgraph/threads/{thread_id}/images/uploads/{sha256}` 与 `GET /api/langgraph/threads/{thread_id}/images/content` 端点挂载，并接入 `_redact_runtime_private_fields` 和 `RuntimeStreamingResponse`；
5. 全矩阵覆盖路由契约测试 `test_runtime_gateway_http_matrix.py` 与专属测试 `test_runtime_gateway_images.py`。

## 2. 涉及文件与改动明细

- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py`:
  - 增加 `BinaryPayload` frozen dataclass；
  - 在 `RuntimeGatewayUpstreamProtocol` 增加 `upload_thread_image` 和 `read_thread_image`。
- `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py`:
  - 增强 `create_runtime_upstream_error`，支持从 upstream detail 中提取业务 `code`（如 `image_not_found`, `image_hash_invalid` 等），避免机械覆盖为 fallback 码。
- `apps/platform-api/src/platform_api/adapters/langgraph/runtime_client.py`:
  - 实现 `upload_image`：流式 PUT raw binary，校验 200/201 JSON 返回；
  - 实现 `read_image`：流式 GET，校验 `Content-Type` 白名单（`image/png`, `image/jpeg`, `image/webp`），只透传 `content-type`, `content-length`, `etag`, `cache-control`，并在传输超 20 MiB 时立即熔断抛出 `runtime_invalid_image_response`。
- `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py`:
  - 接入 `_http.upload_image` 和 `_http.read_image`，路由到 Runtime `/internal/threads/{thread_id}/images/...`。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`:
  - 实现 `upload_thread_image`：
    - sha256 64 位十六进制校验；
    - content-type 白名单校验；
    - content-length 范围校验（<= 5 MiB）；
    - `_load_thread(..., write=True)` 读写权限控制；
    - 强制从 metadata 提取 `graph_id`（缺失抛 `graph_id_required`）；
    - 签发绑定 `image-upload` 的短期 delegation token；
    - upstream 返回满足 `ImageRef v1` 校验。
  - 实现 `read_thread_image`：
    - path 路径前缀与目录穿越（`..`）校验；
    - `_load_thread(..., write=False)` 权限控制；
    - 强制从 metadata 提取 `graph_id`；
    - 签发绑定 `image-read` 的短期 delegation token；
    - 调用 upstream 获取二进制流。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`:
  - `_delegation_operation` 映射 `/images/uploads` -> `image-upload`, `/images/content` -> `image-read`；
  - 暴露 PUT upload 与 GET content 路由，使用 `RuntimeStreamingResponse` 安全清理连接。
- `apps/platform-api/tests/test_runtime_gateway_http_matrix.py`:
  - 将两个图片端点纳入 CASES 全矩阵，验证 401/403/项目隔离/参数边界。
- `apps/platform-api/tests/test_runtime_gateway_images.py`:
  - 全方位验证成功流程、参数校验、跨项目拦截、错误传播与 502 熔断。

## 3. 验证结果

- `test_runtime_gateway_http_matrix.py`: 全部 24 个公开路由边界检查通过。
- `test_runtime_gateway_images.py`: 5 项专属测试（upload success, upload validations, read success, read validations, error propagation）全部通过。
