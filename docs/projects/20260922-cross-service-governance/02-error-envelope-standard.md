# 02 - 错误响应 Envelope 标准化

## 目标

统一四个服务的 HTTP 错误响应格式，以 platform-api 现有 `ErrorResponse` 模型为基准扩展，消除 runtime-service 和 IDS 各自使用 FastAPI 默认格式导致的前端解析混乱问题。

## 当前问题（代码已确认）

| 服务 | 当前错误格式 | 问题 |
|---|---|---|
| platform-api | `{"error": {"code": "...", "message": "...", "details": [], "extra": {}}, "request_id": "..."}` | ✅ 好，作为基准 |
| runtime-service | `{"detail": {"code": "...", "message": "..."}}` 或 `{"detail": {"code": "..."}}` | ❌ 根字段是 `detail` 不是 `error` |
| interaction-data-service | `{"detail": "string_code"}` | ❌ 最简陋，detail 是纯字符串 |

**前端影响：** `apps/platform-web/src/services/*` 中的错误解析代码需要针对不同服务写不同的分支，容易遗漏。

## 方案设计

### 统一标准格式

采用 platform-api 现有格式，并在此基础上做一个小调整：将 `request_id` 从根级别移入 `meta` 对象（便于后续加入 `trace_id`、`service` 等字段）：

```json
{
  "error": {
    "code": "not_found",
    "message": "The requested resource was not found",
    "details": []
  },
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "service": "runtime-service"
  }
}
```

**字段规范：**

| 字段 | 类型 | 必须 | 说明 |
|---|---|---|---|
| `error.code` | string | ✅ | 机器可读的错误码，`snake_case`，如 `not_found` |
| `error.message` | string | ✅ | 人类可读描述，英文 |
| `error.details` | array | 否（422 时填充） | 字段级校验错误列表 |
| `meta.request_id` | string | 否 | 请求追踪 ID |
| `meta.service` | string | 否 | 产生错误的服务名，便于调试 |
| `meta.trace_id` | string | 否 | W3C traceparent 的 trace_id（03 子专题实施后填充）|

### platform-api 迁移

**改动最小**：只需将现有 `ErrorResponse` 模型的 `request_id` 字段从根级别迁移到 `meta` 字段：

```python
# 当前
class ErrorResponse(BaseModel):
    error: ErrorBody
    request_id: str | None = None

# 目标
class MetaBody(BaseModel):
    request_id: str | None = None
    service: str = "platform-api"
    trace_id: str | None = None

class ErrorResponse(BaseModel):
    error: ErrorBody
    meta: MetaBody | None = None
```

> **注意：** `extra` 字段保留在 `error` 内，不迁移（`UpstreamServiceError` 场景下携带 upstream 信息）

### runtime-service 迁移

**当前：** 直接 `raise HTTPException(detail={"code": "...", "message": "..."})`，无统一 handler

**目标：**
1. 创建 `runtime_service/core/errors/` 模块，参考 platform-api 的 `core/errors/` 结构
2. 定义 `RuntimeServiceError` 基类和常见子类
3. 注册 FastAPI exception handler，将所有错误转换为标准 Envelope
4. 替换现有 `raise HTTPException` 为新的错误类

**影响文件（已确认）：**
- `apps/runtime-service/src/runtime_service/http/workspace.py`
- `apps/runtime-service/src/runtime_service/http/images.py`
- `apps/runtime-service/src/runtime_service/http/dear_skills.py`

### interaction-data-service 迁移

**当前：** `raise HTTPException(detail="invalid_project_id")`，detail 是字符串

**目标：** 类似 runtime-service，建立简单的错误类体系和统一 handler

## 任务拆分

### Task 2.1: 定义跨服务错误 Envelope 标准文档
- **改动内容：** 创建 `docs/standards/error-envelope.md`，包含格式规范、字段说明、code 命名约定
- **代码位置：** `docs/standards/error-envelope.md`（新建）
- **预期结果：** 有权威文档可供所有服务开发者参考
- **验证项：** 文档覆盖格式定义、错误码命名规范、各服务 code 枚举清单
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

### Task 2.2: 迁移 platform-api 的 ErrorResponse（request_id → meta）
- **改动内容：** 将 `ErrorResponse.request_id` 重构为 `ErrorResponse.meta: MetaBody`
- **代码位置：** `apps/platform-api/src/platform_api/core/schemas.py` → `ErrorResponse` / `ErrorBody`
- **预期结果：** platform-api 的错误响应根字段为 `{error: {...}, meta: {...}}`
- **验证项：** `pytest apps/platform-api/tests/` 全量通过，手动验证错误响应格式
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

### Task 2.3: 为 runtime-service 建立统一错误处理
- **改动内容：** 新建 `runtime_service/core/errors/`，定义错误基类，注册 exception handler，替换现有 HTTPException
- **代码位置：**
  - 新建：`apps/runtime-service/src/runtime_service/core/errors/base.py`
  - 新建：`apps/runtime-service/src/runtime_service/core/errors/handlers.py`
  - 修改：`apps/runtime-service/src/runtime_service/http/workspace.py`
  - 修改：`apps/runtime-service/src/runtime_service/http/images.py`
  - 修改：`apps/runtime-service/src/runtime_service/http/dear_skills.py`
- **预期结果：** runtime-service 所有错误响应符合统一 Envelope 格式
- **验证项：** `pytest apps/runtime-service/tests/`，人工验证几个错误场景的响应格式
- **预计：** 1.5 天
- **状态：** `[ ]` 待开始

### Task 2.4: 为 interaction-data-service 建立统一错误处理
- **改动内容：** 新建简单的错误类体系和 exception handler
- **代码位置：** `apps/interaction-data-service/app/core/errors/`（新建）
- **预期结果：** IDS 所有错误响应符合统一 Envelope 格式
- **验证项：** `pytest apps/interaction-data-service/`，人工验证错误场景
- **预计：** 1 天
- **状态：** `[ ]` 待开始

### Task 2.5: 更新 platform-web 的 service 层错误解析
- **改动内容：** 统一 `apps/platform-web/src/services/` 中的错误解析逻辑，移除针对不同服务的分支判断
- **代码位置：** `apps/platform-web/src/services/`（HTTP 错误处理部分）
- **预期结果：** 前端 service 层使用统一的错误解析函数，不再需要 `if (error.detail)` 之类的分支
- **验证项：** `pnpm --filter platform-web test run`，手动测试各服务的错误场景
- **预计：** 0.5 天
- **状态：** `[ ]` 待开始

## 验证要求与记录

### Phase 验证
每个 Task 完成后用最小测试集验证。

### Final 验证
- [ ] 单元测试：所有服务的错误 handler 测试
- [ ] 集成测试：platform-api 收到 runtime-service 错误时透传格式正确
- [ ] E2E：前端页面正确显示来自不同服务的错误信息
- [ ] 回归：现有功能不受影响

### 验证记录
<!-- 实施后填写 -->

## 状态

规划中
