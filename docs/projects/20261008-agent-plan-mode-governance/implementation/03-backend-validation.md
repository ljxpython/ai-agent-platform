# 后端补强与验证收口

## 改动时间与相关任务

2026-10-09；T10-T23、T40、T41-B、T42-B、T43-B。进度以 `../tasks.md` 为准，完整命令与真实结果见 `../verification.md`。

## 最后补强

| 完整代码位置 | 改动与理由 |
| --- | --- |
| `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/subagents.py:build_subagents()` | 子图自己的 FilesystemMiddleware 工具实例交给 `PlanModeMiddleware(child=True)`；绑定真实实现而非工具名称，执行期仍保留原 write_file HITL |
| `apps/runtime-service/src/runtime_service/middlewares/plan_mode.py:awrap_model_call()/awrap_tool_call()` | 模型裁剪之外，实际 handler 前校验工具对象和整批调用；控制工具即使普通模式也不能被同名覆盖；保留结构化 SystemMessage blocks/metadata |
| `apps/runtime-service/src/runtime_service/runtime/planning.py:read_plan()/PlanSnapshot` | 验证状态/hash/决定，损坏状态不默认开放；单当前快照、64 KiB UTF-8 正文上限 |
| `apps/runtime-service/src/runtime_service/tools/plan_mode.py:_update()` | 固定审计字段，不含 Markdown/执行 ID；事件名 `runtime.plan.transition_prepared` 只代表准备返回 Command，实际批准以 checkpoint 为准 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:launch_runtime_run()/update_thread_state()/fork_thread()` | 当前计划/new Run/历史/unknown 交叉检查，损坏非空计划也保持限制；bootstrap 不可外部清除，fork 的 fork 和历史不能复用旧授权 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/planning.py:validate_plan_resumes()/project_agent_plan()` | 严格当前快照、人类身份、反馈和公开 DTO；重复回复也校验 digest，不接受私有放权字段 |
| `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py:redact_runtime_private_fields()` | state/history/SSE 只公开有限 agent_plan，用户正文同名键保留；原 event/id/seq/ns 和工具结果形状不改变 |

从只检查 `active=true` 改为“非空状态先验证，再检查 active”，防止损坏 `{"active": false}` 或列表/字符串在新 Run/state 更新处绕过限制。没有为损坏状态提供自动放权修复路径。

## 测试与 fixture

- `apps/runtime-service/tests/services/test_plan_mode_graphs.py`：子图独立实例、批准后 task 委托仍经原写工具 HITL 并实际落盘。
- `apps/runtime-service/tests/middlewares/test_plan_mode_safety.py`：隐藏工具/MCP/同名替换/子图控制/混批 handler 计数为 0、新周期状态隔离和结构化系统消息。
- `apps/runtime-service/tests/runtime/test_plan_contract.py`：真实临时目录和两类符号链接检查，规划 memory 写入跳过、草稿归一/幂等和有限审计字段。
- `apps/platform-api/tests/test_plan_mode_gateway.py`：损坏态、切 graph、unknown、bootstrap、配置两载体与 9 个 SSE 分片/协议投影场景。
- `apps/platform-api/tests/test_run_requests.py`：补齐 Thread 和禁用模型恢复策略 mock、更新 v6/转发调用断言，修复此前 29 个 fixture 失败，生产 UUID 验证保持。
- 两服务 `test_plan_performance.py`/`test_plan_mode_performance.py`：opt-in 本地过滤/state/history 投影计时与峰值内存，没有硬编码生产 SLO。
- `apps/runtime-service/tests/fixtures/tool_error_platform.py`：临时平台按 graph 配置注册 Agent；live opt-in 只读取受管测试模型三个连接配置，不复制凭据。
- `apps/runtime-service/tests/e2e/test_plan_mode_platform.py`：四图 HTTP/持久 Worker/并发批准/重启/原 HITL/封锁恢复；Reference 真实模型修改再审，DearFlow 真实模型写入；公开样例采集。

DearFlow live 首轮失败分别为供应商连接、Worker 冷启动和测试 tenant 路径；最后路径按 API 的 `__default` 计算，不用 catalog tenant UUID。独立复跑确认 read_file 读到输入，计划与工具批准前目标不存在，恢复后文件为 `plan-live-ok`、Run success。这个修复只触及测试。

## 已验证结果与边界

- Runtime 最后计划套件 `82 passed`；API 最后四套件 `85 passed, 6 subtests`。
- 四图 HTTP/Worker `1 passed`；DearFlow live 单独 `1 passed, 1 deselected`；Reference live revision `[1,2]` 成功属于早期混合失败整轮的局部实测，未冒充整个套件通过。
- 子图原 HITL、缓存符号链接和规划 memory=0 已通过；两项性能测试各 `1 passed`，数值见 verification。
- Agent 禁用期间新 Run/审批 403，Worker 重启保持当前 interrupt，重新启用可批准。未删除数据。
- 旧 Runtime 无含计划 Thread 的执行保护，按批准方案保留当前门禁，禁止降版；未执行旧二进制或生产部署。
- Runtime 既有 auth `verify=False` fixture 与六项旧 monkeypatch/wrapup 回归已用 HEAD 对照复现，保留范围外风险。
- 前端未修改，浏览器/Markdown XSS/最大正文和三尺寸双主题由同事验收；整个专项保留 partial，Final 未开始。

## 规范和交接

服务开发规范与网关标准补入通用接入流程和两侧 PLAN_GRAPHS 声明；跨服务 Delegation/SSE 标准补 Context v6/native interrupt/agent_plan，仍保留原专项 draft 门禁。前端交接冻结 DTO/可选字段/批准人形状、HTTP/Runtime 精确码、权限、两服务成对启动和隔离复跑说明。公开记录位于 `../samples/`，仅作历史 fixture，不能拿样例 interrupt ID 直接审批。
