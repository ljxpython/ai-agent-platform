# 06 Platform API：线程图片网关

## 目标与状态

- **状态：** 规划中，治理改动，等待人工评审；本文件不代表已实施。
- **目标：** Platform API 只负责用户对项目、线程和图片资源的访问控制，并以二进制流代理 Runtime 图片接口。
- **禁止越界：** Platform API 不管理图片工具开关、模型密钥、文生图审批策略或 MCP 配置；这些继续由 Runtime 收敛管理。
- **契约来源：** 路径、`ImageRef v1`、状态码和错误码以 [04-platform-image-contract.md](04-platform-image-contract.md) 为准。

## 1. 需要修改的文件

| 文件 | 改动 |
|---|---|
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py` | 给 Runtime upstream port 增加上传、读取图片的二进制方法及轻量返回类型 |
| `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py` | 使用现有 Runtime HTTP client 转发 raw body，限制响应体大小，只透传白名单响应头 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | 加载项目内线程、提取 graph、签发最小 delegation scope，并编排 upstream 调用 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` | 暴露用户侧 `PUT`、`GET` 端点；上传不解析 JSON，读取返回二进制响应 |
| `apps/platform-api/src/platform_api/core/security/tokens.py` | 增加 `image-upload`、`image-read` 两个 Runtime delegation operation |
| `apps/platform-api/docs/standards/runtime-gateway-interface-standard.md` | 记录公开接口、授权边界、大小限制和错误语义 |
| `apps/platform-api/tests/.../test_runtime_gateway_*.py` | 覆盖 service、HTTP、upstream 和 token scope；测试文件名按现有目录惯例落位 |

不新增独立“图片服务”、数据库表或对象存储适配器。图片仍属于线程 workspace，网关只做资源授权和转发。

## 2. 公开接口

Platform Web 只调用 Platform API，不直接访问 Runtime：

```http
PUT /runtime/threads/{thread_id}/images/uploads/{sha256}
Content-Type: image/png
Content-Length: 12345

<raw binary>
```

成功返回 `ImageRef v1` JSON。`sha256` 是请求正文的十六进制 SHA-256；同一线程重复上传相同内容必须幂等成功。

```http
GET /runtime/threads/{thread_id}/images/content?path=/workspace/generated/<id>.png
```

成功返回图片二进制。具体公开路由前缀若当前 router 已统一挂载 `/api`，由应用挂载层添加，不在 handler 中重复硬编码。

## 3. Application port

`ports.py` 只表达当前需要的两个动作（认证头由现有 `with_forwarded_headers` 自动注入，不在参数中重复传 token）：

```python
class RuntimeGatewayUpstream(Protocol):
    async def upload_thread_image(
        self,
        *,
        graph_id: str,
        thread_id: str,
        sha256: str,
        content_type: str,
        content_length: int,
        body: AsyncIterator[bytes],
    ) -> ImageRef: ...

    async def read_thread_image(
        self,
        *,
        graph_id: str,
        thread_id: str,
        path: str,
    ) -> BinaryPayload: ...
```

`BinaryPayload` 只包含 `body`（异步字节迭代器）、`content_type`、`content_length`、`etag`、`cache_control`。若现有 upstream 基类已有等价的 HTTP payload 类型，直接复用，禁止再造一层 DTO。

## 4. Service 编排与授权

### 4.1 上传

1. 从当前认证上下文取得 `tenant_id`、`project_id` 和用户身份，客户端不得提交这些字段。
2. 调用现有 `_load_thread(..., write=True)`；不存在返回 404，无项目写权限返回 403。
3. 从已加载线程 metadata 取得真实 `graph_id`；若缺失则抛出 `BadRequestError(code="graph_id_required")`。不得信任 query/body 中的 graph，也不得用 Showcase 常量兜底。
4. 校验 `sha256` 为 64 位小写十六进制；校验 `Content-Type`、`Content-Length` 和公开上传上限。
5. 签发绑定 tenant、project、thread、graph 且仅含 `image-upload` operation 的短期 delegation token，通过 `upstream = self._upstream.with_forwarded_headers(...)` 注入。
6. 将请求正文按流转发到 Runtime；不读取为 JSON，不转 Base64，不写数据库。
7. 校验 Runtime 返回满足 `ImageRef v1`，原样返回给 Web。

### 4.2 读取

1. 调用 `_load_thread(..., write=False)`；读取权限和线程归属校验不得因图片是静态文件而绕过。
2. 从线程 metadata 取得 `graph_id`；若缺失则抛出 `BadRequestError(code="graph_id_required")`。
3. 只接受以 `/workspace/uploads/`、`/workspace/generated/`、`/workspace/charts/` 开头且满足 04 契约的路径；最终文件安全校验仍由 Runtime 执行。
4. 签发仅含 `image-read` operation 的 delegation token，通过 `with_forwarded_headers` 注入。
5. 调用 Runtime，校验响应类型和长度后以流式返回二进制。

`_load_thread` 的读写语义必须沿用当前 service：上传属于线程写操作，读取属于线程读操作。不要复制一份项目授权逻辑到 HTTP handler。

## 5. Upstream 二进制转发

### 上传请求

- 使用现有异步 HTTP client 的 streaming body 能力。
- 只发送 `Content-Type`、可验证的 `Content-Length`、delegation token 和既有追踪头。
- 不调用 `.json()`，不把 body 拼进异常、结构化日志或 tracing attribute。
- 若 ASGI 层不能可靠得到 `Content-Length`，按块累计并在超过上限时立即终止；Runtime 仍做第二次边界校验。

### 读取响应

- 采用流式响应透传，结合读取迭代器进行累计字节计数；超过 20 MiB 上限时立即截断并抛出 `runtime_invalid_image_response`，避免在 Platform API 内存中全量缓冲 20 MiB 导致 OOM。
- 只透传 `Content-Type`、`Content-Length`、`ETag`、`Cache-Control`。
- 不透传 Runtime 的 `Set-Cookie`、认证头、Server 信息、任意 Content-Disposition 或 hop-by-hop header。
- `Content-Type` 必须在支持清单中，正文长度必须与声明一致；不可信或缺失时以实际读取字节数为准。

## 6. Delegation token

`core/security/tokens.py` 与 Runtime 对 operation 的白名单必须同时增加：

| operation | 允许调用 | 禁止调用 |
|---|---|---|
| `image-upload` | 对 token 绑定线程写入 `/workspace/uploads/` | 运行 graph、入队消息、读取图片、写 generated/charts |
| `image-read` | 读取 token 绑定线程允许目录中的图片 | 上传、运行 graph、入队消息 |

签名、issuer、audience、有效期和既有 tenant/project/thread/graph claim 不变。不得为了这两个 operation 放宽现有 `run-create` 或 `message-read`。

## 7. 错误映射

网关必须保留能指导 Web 行为的 4xx，不能把所有 Runtime 响应压成 502：

| 来源 | Platform API 响应 | 行为 |
|---|---|---|
| 用户未认证 | 401 | 由现有认证层返回 |
| 项目或线程无权限 | 403 | 不调用 Runtime |
| 线程或图片不存在 | 404 | 保留稳定 error code |
| hash、path、MIME 不合法 | 400 或 415 | 保留 04 定义的 error code |
| 请求图片过大 | 413 | 上传前或流式读取中终止 |
| Runtime token scope 拒绝 | 403 | 记录 operation 和 request id，不记录图片正文 |
| Runtime 超时/不可达 | 502/504 | 使用现有 upstream 异常映射 |
| Runtime 返回超大或非图片正文 | 502 | `runtime_invalid_image_response` |

错误正文保持平台现有错误 envelope。审计只记录用户、项目、线程、operation、path/hash、size、结果和 request id；禁止记录上传正文、下载正文、Base64、模型密钥或 delegation token。

## 8. 实施任务

- [ ] **A1 契约穿透试验：** 完成 08 的 G0；确认消息 extras 可穿过 SDK、GraphHarbor、checkpoint 和 history 后才开始平台实现。
- [ ] **A2 Token：** 两端加入 `image-upload`、`image-read`，为错误 operation、错线程、过期 token 增加测试。
- [ ] **A3 Port 与 upstream：** 实现 raw upload、受限 download、响应头白名单及超限终止。
- [ ] **A4 Service：** 复用 `_load_thread`，从 metadata 取得 graph，签发最小 scope token；补齐读写权限测试。
- [ ] **A5 HTTP：** 暴露 PUT/GET，保持 raw binary，接入现有依赖注入和错误 envelope。
- [ ] **A6 文档与回归：** 更新网关标准，运行 Platform API 单测、lint、类型检查和 Runtime delegation 契约测试。

依赖顺序：`A1 -> A2 -> A3 -> A4 -> A5 -> A6`。A3 与 A4 可在 A2 完成后并行，但 A5 必须等两者接口稳定。

## 9. 验证矩阵

| 场景 | 预期 |
|---|---|
| 合法 PNG 上传 | 200/201，返回完整 `ImageRef v1`，Runtime 文件 hash 与请求一致 |
| 同线程同 hash 并发 PUT | 均成功，只得到一个完整文件，无临时文件泄漏 |
| 正文与 URL hash 不符 | 400，Runtime 不发布文件 |
| 缺失/伪造 Content-Length | 仍受实际读取上限约束 |
| 错 tenant/project/thread | 403 或 404，不泄露资源是否存在 |
| 只持有 `image-read` 上传 | Runtime 403 |
| 读取 generated/chart 图片 | 响应正文 hash 正确，只含白名单头 |
| 读取非图片或越界路径 | 400/404，不读取 workspace 外文件 |
| Runtime 断连/超时 | 502/504，平台进程稳定，错误正文不含 token/body |
| 审计和应用日志扫描 | 无图片二进制、Base64、密钥和 delegation token |

完成条件：A1—A6 全部完成，Platform API 定向测试、Runtime token 契约测试通过，并由 08 的三服务 E2E 证明浏览器只能经 Platform API 访问线程图片。
