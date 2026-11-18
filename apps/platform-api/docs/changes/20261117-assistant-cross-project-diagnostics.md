# 平台助手跨项目排障权限与真实诊断打通

## 背景
用户在平台助手会话中提供跨项目的真实运行故障数据包（包含 `thread_id` 和 `run_id`）时，由于助手会话默认绑定在专属沙箱项目（个人助手项目），后端直接将助手的 `project_id` 传给网关，导致网关在校验 thread 归属时判定 `metadata['project_id'] != project_id`，直接抛出 `thread_action_denied`，致使助手无法读取任何诊断信息并报错无能为力。

## 改动内容
1. **自动反查目标 Thread 真实归属项目**：
   - `apps/platform-api/src/platform_api/modules/platform_assistant/service.py`：当收到 `target_thread_id` 时，通过 `thread_access.get()` 从底层数据库自动查出该 thread 的真实 `target_project_id`，并使用目标项目 ID 请求网关诊断接口 `gateway.get_thread_run_diagnostics`、快照接口 `gateway.get_thread_run` 与日志接口 `authorized_logs`。
2. **安全隔离合规**：
   - 网关内部严格通过 `_load_thread(actor=actor, project_id=target_project_id, ...)` 校验当前登录用户（`actor`，如 admin 账号或该项目成员）是否拥有该目标项目的合法读取权限；若当前用户无权访问目标项目，依然严格执行权限阻断，绝无跨租户或横向越权漏洞。
3. **自动化测试**：
   - 在 `tests/test_platform_assistant.py` 增加 `test_diagnostics_cross_project_uses_target_thread_project_id`，覆盖跨项目线程排障场景，73 项相关单测全绿。

## 涉及文件
- `apps/platform-api/src/platform_api/modules/platform_assistant/service.py`
- `apps/platform-api/tests/test_platform_assistant.py`
