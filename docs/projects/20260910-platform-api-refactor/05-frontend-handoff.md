# 05 前端影响与后续调整

## 范围与状态

2026-09-10 用户明确调整顺序：本次先做后端验收，前端问题后续统一解决。本专题状态为 **deferred**；已有前端删除与接口改动保留，但不据此宣称页面或浏览器验收完成。本次不继续扩展前端实现。

后端当前契约与收尾证据见 [11 收尾记录](implementation/11-backend-closeout.md)，前一轮主链路证据保留在 [10](implementation/10-operations-run-requests.md)。以下记录收缩后的实际接口，前端实现与验收尚未覆盖这些新字段。

## 影响与对应调整

| 变化 | 对前端的影响 | 后续调整 |
| --- | --- | --- |
| Operations、平台 Worker、队列、artifacts、resync 退役 | 旧任务查询、轮询、下载、重试和同步按钮无法使用；旧路由无兼容实现 | 清理 Operations 路由、菜单、权限、service、composable、缓存与定时器；ControlPlane、PlatformConfig、SystemGovernance 移除队列、Worker 心跳和任务卡片；不要把不存在的 Worker 显示为故障 |
| 知识库、测试用例产品退役 | 旧导航、统计、快捷入口及权限失效 | 删除引用，保留其他产品业务；自动化测试不属于被删除的测试用例产品 |
| Agent 产品接口规范化 | `/api/assistants` 旧产品别名及 resync 不能再调用 | 列表/创建使用 `/api/projects/{project_id}/agents`，详情/修改/删除使用 `/api/agents/{id}`；删除无效同步和删除选项 |
| Agent 与部署 Graph 分工明确 | 管理记录 UUID 与执行 `graph_id` 不能混用；不再有同步 ready 状态 | CRUD 使用返回的 `id`；标准 Runs 的 `assistant_id` 使用选中 Agent 的 `graph_id`；启停按 `active/disabled`；不直接对上游创建 Assistant |
| 目录刷新同步完成 | 不再返回 Operation ID，旧轮询会失败 | POST `/api/runtime/graphs/refresh` 或 `/api/runtime/tools/refresh`，等待 `{ok,count,last_synced_at}` 后重读对应 GET 列表；请求中禁重复点击，失败展示可重试错误，不能把失败当空目录 |
| 模型由平台管理 | `/api/runtime/models/refresh` 已移除；远端刷新不能导入或覆盖模型 | GET/POST `/api/runtime/models`，PATCH `/api/runtime/models/{model_id}`；表单使用 provider、display_name、base_url、protocol、model、api_key、enabled；编辑时未换密钥就省略 api_key，不回填掩码字符串 |
| 模型凭据不公开 | 浏览器不能兑换内部模型引用或拼接受信鉴权 | 只根据 `credential_configured` 提示已配置；选择模型记录 ID；不请求 `/api/runtime/internal/model-config`，不保存 delegation、runtime_model_ref 或上游 API Key |
| schema 来自真实部署 | 本机文件路径、AST fallback 不再成立 | 使用 `/api/graphs/{graph_id}/assistant-parameter-schema` 获取公开参数；只渲染允许字段，部署不可用时显示错误，不提供宿主绝对路径输入 |
| `run_requests` 取代运行镜像 | Operations 状态和平台提交状态不能作为 Chat 执行状态 | Thread/Run/state/history/events 统一经 `/api/langgraph` 读取；不新增 run_requests 列表轮询，不在浏览器复制服务端执行状态机 |
| 新动作与重试严格区分 | 相同文本不是相同动作；无 key 的网络重发可能新建 Run | 每次用户发送生成一个 `Idempotency-Key`，同动作网络重试复用 key 和原 payload；新消息、重新执行、独立审批生成新 key；不要在共享 HTTP client 上保留上一动作的 key |
| 并发由 Server 使用 reject 裁决 | 同会话活跃 Run 或同 key 改 payload 可返回 409 | 禁止自动换 key 重发以绕过冲突；刷新当前 Run 后提示用户。保留草稿；显式取消后确认上游结果，再允许新动作 |
| 审批按 interrupt ID 恢复 | 顺序索引审批、把审批作为普通消息、审批时修改模型/Context 均不可靠 | 从当前 Thread state 读取 ID；使用标准 resume 映射，或下面的 Protocol command；审批只提交工具决策，不附带 config/context 覆盖；403/过期冲突后重新读取状态 |
| SSE 与 JSON 内部字段过滤 | UI 不得依赖 `_runtime_*` 或模型引用字段；事件可能跨任意网络块 | 继续使用 SDK 或正确 SSE 解析器；按服务端事件更新展示，不按 fetch chunk 切 JSON；断开订阅不代表取消，取消使用显式 Run cancel |
| 全新数据库基线 | 旧项目、Agent、Thread 和审批不能自动接续 | 新环境重新登录/选择项目；旧 ID 返回 404 时清理该选择和失效缓存，不自动重放旧输入、迁移旧审批或伪造恢复 |

需要项目作用域的目录/schema/网关请求携带当前 `x-project-id` 和平台登录认证。切换项目时清理旧订阅和项目缓存，不沿用旧 Thread；浏览器始终通过平台网关访问 Runtime。

## Chat 调整示例

标准 Run 创建路径：`POST /api/langgraph/threads/{thread_id}/runs`，请求头携带本次动作的 `Idempotency-Key`。

```json
{
  "assistant_id": "showcase_demo",
  "input": {"messages": [{"role": "user", "content": "检查并修复销售报表"}]}
}
```

Protocol 审批路径：`POST /api/langgraph/threads/{thread_id}/commands`。当前协议 `id` 使用整数，不能使用任意字符串；它不是幂等键。真实验收已使用以下形状：

```json
{
  "id": 2,
  "method": "input.respond",
  "params": {
    "interrupt_id": "从当前 state 读取的 ID",
    "response": {"decisions": [{"type": "approve"}]}
  }
}
```

`decisions` 必须与该 interrupt 中的动作对应；不应把示例的一项批准硬编码成所有审批。标准 Runs 恢复采用 `command.resume = {interrupt_id: response}`。新 Run ID 与父 Run ID 不同，UI 不能覆盖旧历史或靠旧终态认为恢复已结束。

刷新页面或 SSE 断线后先取 Thread state、待处理 interrupt 和 Run 状态，再恢复订阅；不要自动重发消息或自动批准。明确的 401 要重新认证，403 表示当前授权拒绝，404 清理失效选择，409 要核实动作/执行状态；超时属于结果未知，重试使用原 key。

## 收尾后冻结的字段契约

- Agent 已删除 runtime_base_url、config、metadata，只接受公开 context 默认值（model_id、temperature、max_tokens、top_p、tools）；更新请求不接受 graph_id，换图需新建 Agent。前端表单和 PATCH 必须删掉旧字段，不能整份旧响应回传。
- 模型列表项为 id、display_name、provider、base_url、protocol、model、enabled、credential_configured。runtime_id/model_id/is_default/sync_status/last_seen_at/last_synced_at 均已从模型目录响应删除，列表只含 count/models；策略条目仍保留 catalog_id、model_id（两者均指模型记录 UUID）、display_name、policy。
- 所有执行 Context 的 model_id、Agent 默认模型和策略选择均使用模型记录 UUID，不能传 provider:model 或模型名称；同名模型可对应不同服务地址和凭据。前端选项 label 可显示名称/地址，value 必须为 id。
- 标准 Runs 只允许公开 config.recursion_limit（1–1000，缺省 25）；原参数重试复用首次冻结值，审批不传 config/context/input。多 interrupt 使用一个 command.resume ID 映射；已经处理的同一 ID 不能靠换 HTTP key 再执行。
- Run JSON 的上游状态和 Protocol lifecycle 映射是不同接口，不能仅凭 SSE 中 `completed` 推断所有 JSON 状态也被改名。

## 已改动与尚待验收

已有前端代码移除了 Operations、resync、模型刷新及部分控制面卡片，并改为直接刷新 Graph。上一阶段 Vitest 35 文件、121 项通过，vue-tsc 与相关页面 ESLint 通过；这些仅是代码检查证据，没有本轮浏览器验收。

后续从以下位置检查实际调用与交互，不重新搭建前端架构：

- `apps/platform-web/src/services/assistants/assistants.service.ts`、`services/runtime/runtime.service.ts`：产品 CRUD、目录刷新、模型配置。
- `apps/platform-web/src/services/platform/workspace-context.ts`、`services/system/system-governance.service.ts`、router/sidebar/permissions：移除退役能力和任务依赖。
- Agent 列表/创建、Graphs、RuntimeModels、Chat/审批，以及 ControlPlane、PlatformConfig、SystemGovernance 页面：空态、错误态、加载态和失效缓存。

## 后续前端验收清单

- [ ] 全站没有 Operations/resync/模型远端刷新/知识库/测试用例入口或后台请求；控制台无相关 404 与未处理异常。
- [ ] 新库登录、项目选择、模型密钥只写、Graph/Tool 刷新、Agent 创建/启停与 schema 表单正常。
- [ ] 新动作新 key，同动作重试同 key；409 不自动重复执行；两个项目的缓存与订阅隔离。
- [ ] Showcase 发送、真实流式、刷新恢复、审批 approve/reject/edit、多 interrupt 按 ID、撤权后拒绝、取消后再次发送通过。
- [ ] 浏览器响应、日志和本地存储没有内部凭据；SSE 断线不会自动取消或自动批准。
- [ ] Vue 类型、组件测试及真实浏览器回归通过后，才将本专题从 deferred 更新为 done。

2026-09-10 后端收尾修订：以上新字段契约替换上一轮遗留字段说明。实际实现及证据见 [11 收尾记录](implementation/11-backend-closeout.md)。前端仍 deferred；不能把先前类型检查结果套用到收缩后的字段契约。

本轮事务规范化与目录精简仅改变后端 Python 调用方式和导入路径，HTTP URL、请求/响应字段与 20 表结构不变；前端无需为该内部重构新增适配，仍按本专题既有清单完成上一轮字段契约调整。
