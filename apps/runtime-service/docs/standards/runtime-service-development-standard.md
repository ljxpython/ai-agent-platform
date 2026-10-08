# Runtime Service 开发范式与规则

## 以 Showcase Demo 为模板

- `agent.py` 是唯一组合根：校验身份和 Context，获取模型，显式装配 Middleware、工具和子 Agent。
- `prompts.py` 只放提示词和纯渲染函数；不读环境变量、不发网络请求。
- `tools.py` 只放本服务真实业务动作；不返回模拟成功。
- `backend.py` 只处理工作区、资源边界和执行隔离；优先复用官方 Backend。
- `subagents.py` 用声明式角色和最小权限；禁止无边界通用子 Agent。
- `skills/` 是按需读取的资源，不授予权限。
- Graph 入口通过 `langgraph*.json -> graphs -> services/<name>/agent.py` 注册。

## 必须遵守

1. 先查本导航、相关 knowledge、官方 MCP 文档和现有调用者，再改代码。
2. 优先使用 LangChain/LangGraph/Deep Agents 官方能力，不自建 Agent 循环、Tool Registry、Builder 或审批 State。
3. 信任边界必须校验：身份、Context 哈希、tenant/project/thread scope、工具 allowlist 和审批动作。
4. 正式环境文件和命令执行必须限制在当前线程工作区；禁止回退到宿主机 shell，禁止把凭据或绝对路径放进 Prompt/Context。Showcase 经评审允许受信任本地开发显式选择 LocalShellBackend（本地栈默认 local），该模式不提供 shell 隔离，不用于生产或多租户环境；独立 Runtime 默认仍为 Docker。
5. 新增能力必须有单元或组合测试；跨边界改动补集成测试和至少一条 E2E 链路。
6. 变更保持最小：不为未来需求预留抽象，不复制旧 Runtime，不新增兼容 Adapter。
7. 影响功能现状时同步 `docs/FEATURES.md`；治理或跨服务改动更新 `docs/projects/` 记录。

## 新功能最短流程

阅读资料 → 复制 Showcase 的边界模式 → 在所属 Service 显式装配 → 编写最小测试 → 本地运行 → 更新文档和变更记录 → 提交评审。

## 通用会话停止与资源适配

`run_control/`持有平台控制动作、恢复租约、inbox屏障、资源回执和确定性报告；GraphHarbor持有Run/lease/checkpoint执行事实。Runtime使用正式引擎cancel-active与固定回执接口，不直接改引擎runs/lease表、不新增Agent循环或停止工具。该源码已隔离验证，正式配套版本/锁接入与真实Docker仍blocked；本期不代表现役可用。

- 新Agent沿当前组合根/图注册即可接入会话停止；`webapp.py`统一挂internal Stop路由和受管lifespan reconciler，无需每图加middleware。业务工具要传播 `CancelledError`，不要改成普通ToolMessage成功/失败。
- 长命令资源复用 `workspace/execution.py::execute_in_workspace()` 与 `run_control/resources.py::{register_resource,finish_resource,wait_cleanup}`。资源登记只保存thread/run/kind/status，不保存命令、宿主路径或凭据；重复取消也要等待已拥有的清理任务并持久记录confirmed/unconfirmed。
- LocalShellBackend仅用于受信本地开发；Python同步线程不能强杀，取消等待有界命令结束，超出确认等待保留unconfirmed。不得回退宿主shell提供生产隔离；真实Docker证据不能用local或mock替代。
- inbox enqueue/claim与Stop准备共用Thread advisory lock，屏障绑定固定旧run_id；执行退出后复用 `reconcile_run()` 按committed checkpoint对账。保留consumed，旧未消费项标user_stopped；新Run和已有run_ended/run_cancelled原因不被覆盖。
- 报告从固定目标取已保存计划/真实工具回执/合法成果，最多20 checkpoints、30 progress、20 artifacts，脱敏label/JWT/宿主路径；无证据明确unknown。业务工具可以沿现有Todo/ToolMessage/artifact引用提供证据，不为此自建业务摘要schema或自动summary Run。
- Stop不抹掉HITL，不自动resume；显式恢复绑定当前interrupt ID，不携新input/config/context。媒体/部署已接受但丢响应的unknown回执必须保留，同key重试不能再次购买或发布；独立Terminal/detached任务不冒充已取消。

职责、函数、迁移/回退与真实四图证据见[取消专项](../../../../docs/projects/20261007-agent-run-cancellation/README.md)；前端只消费安全DTO，未接入前不改变Run/SSE原契约。

## 新增代码粒度规范

> **适用范围：仅约束新增代码。存量代码不在此规范的覆盖范围内，不得借此规范触发对旧代码的"顺手重构"。**

### 函数原子化

- 一个函数只做一件事：要么协调（调其他函数），要么执行（做真实业务动作），不混用
- 新增普通函数目标 ≤ 60 行；LangGraph 节点函数目标 ≤ 40 行（节点只做状态路由 + 调用，不内嵌业务逻辑）
- 工具函数（`@tool`）：一个工具只封装一个真实业务动作，不捆绑多个副作用

### 参数与嵌套

- 新增函数参数目标 ≤ 4 个；超过时用 `dataclass` 或 `TypedDict` 包裹
- 嵌套层数目标 ≤ 3 层；优先用 early return / Guard Clause 扁平化条件分支

### 信号而非硬阻

上述数字是设计时的参考目标，不是 CI 门禁。写新代码时主动对照；若某个函数确实需要更多行，在函数上方注释说明原因（例如：协议解析、状态机分支穷举）。
