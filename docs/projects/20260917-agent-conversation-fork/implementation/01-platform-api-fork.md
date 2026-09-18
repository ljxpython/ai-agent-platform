# Platform API 会话分叉

## 改动时间
2026-09-17

## 相关任务
- `02-platform-api-fork.md`：严格请求校验、`fork_thread()` 和单元测试。
- `03-runtime-service-isolation.md`：验证新 thread 的 workspace 根目录隔离。

## 改动文件
- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- `apps/platform-api/tests/test_thread_fork.py`
- `apps/platform-api/tests/test_runtime_gateway_http_matrix.py`
- `apps/runtime-service/tests/test_thread_workspace_isolation.py`

## 具体改动
新增 `POST /api/langgraph/threads/{thread_id}/fork`。请求只允许 `checkpoint_id` 和可选 `title`；服务加载同项目来源 thread，读取指定 checkpoint，继承必需的路由与归属元数据（`project_id`、`graph_id`、`agent_id`、`access_policy`、`forked_from` 及可选 `title`），创建 target thread，再仅写入 `values`。

state 写入失败时删除刚创建的 target。分叉不复制来源 workspace、消息队列、运行或旧 checkpoint config；Runtime 继续使用 target thread_id 的既有作用域和 workspace 派生逻辑。

## 验证
- [x] Platform API 单元与 HTTP 契约测试：3 项通过
- [x] Runtime workspace 隔离测试：2 项通过，含来源 token 对目标 workspace 的 403 拒绝
- [ ] 全栈分叉 E2E（前端接入后执行）
