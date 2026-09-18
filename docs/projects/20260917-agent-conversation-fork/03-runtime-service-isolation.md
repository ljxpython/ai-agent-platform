# Runtime Service 隔离

## 目标
确保分叉后的执行使用新的受签名 thread_id，并天然隔离 workspace、终端、消息队列和资源绑定。

## 方案设计
Runtime Service 不持有对话树，LangGraph Server 是 thread/checkpoint 事实源。Platform API 给每次目标 thread Run 签发已有的 delegation token；`runtime_config` 已校验 token scope 的 `thread_id` 与执行 thread 相同。`resolve_thread_workspace(tenant, project, thread_id)` 按新 ID 计算物理工作区路径，实现新老会话物理隔离。

为了让新分支获得来源分支的工作区上下文，Runtime Service 增加了内部受控接口：
- `POST /internal/threads/{thread_id}/workspace/fork`，请求体包含 `source_thread_id`。
- 该接口由 Platform API 在分叉 state 创建后，签发特定 `operation="workspace-fork"` 的 delegation token 内部调用。
- 接口在服务端通过 `shutil.copytree(source_root, target_root, dirs_exist_ok=True, symlinks=False, ignore_dangling_symlinks=True)` 完成物理工作区文件（含 `/outputs` artifacts）的深拷贝。
- 拷贝完成后，新分支与原分支的工作区物理目录完全独立，任何一侧的新增/修改/删除绝不影响另一侧。

## 任务拆分
- [x] 为新旧 thread workspace 路径不相同补一条测试。
- [x] 确认目标 run 的 delegation token 必须使用目标 thread_id。
- [x] 实现 `POST /internal/threads/{thread_id}/workspace/fork` 工作区文件安全深拷贝。
- [x] 在 `verify_delegation_claims` 中支持 `workspace-fork` delegation operation 白名单。
- [x] 增加工作区文件复制及物理隔离性测试（修改 target 不影响 source）。
- [ ] 确认 queue、terminal 与资源绑定不从来源 thread 继承。

## 验证要求与记录
- [x] 相同租户和项目下不同 thread 得到不同 workspace 根目录。
- [x] source token 不能访问 target runtime resource。
- [x] fork 接口能完整将 source workspace 文件复制到 target workspace，且两者互不干扰。

### 2026-09-17 验证
- ✅ `uv run pytest tests/test_thread_workspace_isolation.py`：3 项通过，确认 source/target thread workspace 路径不同；来源 token 读取目标 `/workspace/tree` 返回 `403 file_scope_denied`；分叉接口成功复制所有文件，并在随后的修改与新建中保持物理隔离。
- ✅ `uv run pytest tests/test_workspace_http.py`：2 项通过，确认工作区文件与 artifact 既有浏览与下载接口未受回归影响。

## 状态
done：Runtime thread 隔离及工作区文件深拷贝完整交付并通过验证。

