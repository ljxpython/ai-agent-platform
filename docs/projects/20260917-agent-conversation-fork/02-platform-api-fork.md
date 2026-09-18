# Platform API 分叉编排

## 目标
把跨 thread 状态转存留在平台受控网关，复用 LangGraph SDK，不引入会话树表或 checkpointer SQL。

## 方案设计
修改 `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` 增加 `POST /threads/{thread_id}/fork`；修改 `application/service.py` 增加 `fork_thread()`。

执行顺序：加载来源 thread（write 授权和项目归属）-> 验证 `checkpoint_id` -> 获取该 checkpoint 的 state -> 用来源 graph、访问档位及 `forked_from` 创建目标 thread -> 写入 state 的 `values` -> 调用 Runtime Service `fork_thread_workspace` 将来源工作区文件完整深拷贝至目标工作区。创建后 state 写入失败时删除刚创建的 target，避免留下不可用会话。

metadata 保留平台路由与归属必需的 `project_id`、`graph_id`、`agent_id`（若来源存在）、`access_policy`、可选 `title` 和 `forked_from`；来源的其它任意用户 metadata 不透传，避免把旧资源绑定误带入新 thread。

## 任务拆分
- [x] 添加严格请求校验与路由矩阵条目。
- [x] 实现 `fork_thread()` 及失败补偿删除。
- [x] 签发 `workspace-fork` delegation token 并调用 Runtime upstream 的 `fork_thread_workspace`。
- [x] 添加 service 单元测试与 HTTP 边界测试。

## 验证要求与记录
- [x] 分叉调用顺序是 `get_state -> create_thread -> update_thread_state -> fork_thread_workspace`。
- [x] `values` 与来源快照一致，metadata 是平台重建后的最小集合。
- [x] state 写入失败会删除 target。
- [x] delegation token 配置就绪时成功触发 workspace fork upstream。

### 2026-09-17 验证
- ✅ `uv run python -m unittest tests/test_thread_fork.py tests/test_runtime_gateway_http_matrix.py`：4 项测试全部通过；覆盖状态复制、失败补偿、工作区同步触发、请求校验、认证和跨项目边界。
- ⚠️ Runtime Server 实例联调和浏览器分叉流程待 Platform Web 接入后执行。

## 状态
done：Platform API 分叉编排与工作区文件复制链路已全线联通并通过单测验证。
