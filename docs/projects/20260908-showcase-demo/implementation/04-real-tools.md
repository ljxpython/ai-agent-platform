# 切换到真实 Agent 工具调用

## 改动时间
2026-09-08

## 相关任务
- 用户反馈：切换 Mock Tools 到真实的 Agent 工具调用。

## 改动文件
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/tools.py`
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py`
- `apps/runtime-service/tests/demo/test_showcase_demo.py`

## 具体改动

### 1. 移除 mock filesystem 工具
**位置：** `tools.py`
**改动内容：** 
- 删除了 `read_project_file`, `write_project_file`, `search_code` 这类返回假数据的 Mock 函数。
- 引入真正的请求 `urllib.request` 给 `fetch_documentation`。

### 2. 集成 FilesystemMiddleware
**位置：** `agent.py`
**改动内容：**
- 使用 `FilesystemMiddleware(backend=StateBackend())` 来提供安全沙箱下的真实工具调用，包括 `read_file`, `write_file`, `edit_file`, `grep`, `glob`。
- 子智能体也相应配置了对应权限的 `FilesystemMiddleware` 以保证能力一致性。
- 更新了 system_prompt、tool_permissions 等关联配置，与真正的工具匹配。

### 3. 测试适配
**位置：** `test_showcase_demo.py`
**改动内容：** 
- 测试断言及工具 payload 修改匹配了 `write_file`, `grep` 的结构和名称。

## 验证
- [x] 单元测试 `test_showcase_demo.py` 已全部通过。
