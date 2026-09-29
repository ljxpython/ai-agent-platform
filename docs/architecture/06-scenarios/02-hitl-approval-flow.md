# 02-工具调用触发审批与恢复全链路 (Tool Execution Approval & Resumption Flow)

## 模块定位与核心价值

在智能体落地到真实生产系统的过程中，最危险的场景莫过于让模型无节制地执行具有副作用（Side-effect）的写操作，例如：修改远程数据库、覆写关键配置文件、甚至触发生产环境的发布管道。

为了在保证智能体自主解决问题能力的同时，牢牢守住企业安全的底线，`ai-agent-platform` 实现了端到端贯穿的**人机协同审批与断点恢复闭环（Human-in-the-Loop Approval & Resumption）**。

本链路深度融合了 **LangGraph 运行时的中断挂起能力**、**API 网关的防篡改协议守卫** 以及 **前端会话池的状态机去重过滤**。它不仅解决“如何在需要时让用户点确认”，更关键的是解决了分布式长周期任务中的硬核工程挑战：
1. **跨服务断点物理落盘**：审批不是内存阻塞，而是状态机物理挂起入库，支持离线等待数天。
2. **防参数偷换攻击（Anti-Tamper Guard）**：用户审批的是执行“脚本 A”，绝对禁止攻击者在恢复执行指令时偷换为“脚本 B”。
3. **快照回放死锁防御（Replay Deadlock Defense）**：解决在重新拉取历史 Checkpoint 时，已审批过的动作再次弹出弹窗死锁前端交互的痼疾。

---

## 零、知识前置与上下文串联（Knowledge Bridges）

### 1. 认知输入（前置模块输入）
- 依赖 [03-platform-web/02-chat-session-engine.md](../03-platform-web/02-chat-session-engine.md)：掌握前端 `useSessionInterrupts.ts` 的 `resolvedReviewIds` 去重机制。
- 依赖 [04-platform-api/02-runtime-gateway.md](../04-platform-api/02-runtime-gateway.md)：掌握网关对 `input.respond` 指令的合法性过滤与 `resume_configuration_override` 拦截。
- 依赖 [05-runtime-service/03-hitl-and-interrupts.md](../05-runtime-service/03-hitl-and-interrupts.md)：掌握底座运行时三档访问策略（`review`, `workspace_write`, `full_access`）与 `interrupt()` 状态机。

### 2. 本章核心流转
- **敏感策略拦截**：模型决定调用具有写权限的工具，底座判定命中当前访问策略规则，抛出 `interrupt()`。
- **状态机冻结与事件下发**：底座落盘中断快照，通过 SSE 向前端下发附带唯一 `interrupt_id` 的事件。
- **前端去重渲染与用户决策**：前端比对未决列表，弹出模态交互卡片供用户审核；用户点击批准。
- **防篡改参数组装与解冻执行**：通过 `input.respond` 携带 `interrupt_id` 回传，网关完成防篡改校验，底座精准唤醒原挂起节点继续执行。

### 3. 认知输出（支撑后续模块）
- 为 [03-subagent-dispatch.md](03-subagent-dispatch.md) 中子智能体执行敏感任务时如何向主流程回传审批事件提供场景支撑。

---

## 一、对立视角：简易原型 vs 生产架构（Naive vs Production）

| 维度 | 简易原型方案 (Naive) | 本平台生产级全链路架构 (Production Architecture) | 选型与演进考量 |
| :--- | :--- | :--- | :--- |
| **中断挂起机制** | 在 Python 代码中使用全局事件（如 `asyncio.Event`）在内存中阻塞等待。 | 底座利用 Pregel 原生 `interrupt()` 将当前状态机和调用栈完全序列化落盘到 Checkpoint 表中。 | 内存方案在服务器重启或容器漂移时会导致任务彻底假死，而数据库快照方案支持跨天离线恢复。 |
| **恢复安全性** | 恢复执行时允许传入任意新的 `config`、`prompt` 或换用模型。 | 网关层严格只允许传递 `interrupt_id` 与对应 decision 字典，传入其他参数直接抛出 400 阻断。 | 杜绝安全绕过：防止攻击者在需要审核的操作时提交合法操作，但在恢复时偷偷换用注入代码。 |
| **快照重播体验** | 页面 F5 刷新拉取历史事件流时，之前已经批准过的弹窗再次弹出来死锁界面。 | 前端维护会话级 `resolvedReviewIds` 响应式集合，历史快照中已处理的审批项直接静默忽略。 | 彻底杜绝回放已解决事件导致的交互死锁，保障历史长会话的平滑重载。 |
| **多澄清提问处理** | 允许模型在一次决策中同时并发调用 3 个提问工具，导致前端连环弹出多个模态框。 | 挂载 `ClarificationBatchGuard`，单步推理严格限制仅允许 1 个澄清中断，超出部分自动熔断。 | 杜绝大模型并行 Tool Call 造成的用户认知混乱与状态机多分支恢复竞争。 |

---

## 二、源码精准坐标映射（Code Pointer Map）

### 1. 前端审批渲染与去重拦截
- [apps/platform-web/src/modules/chat/composables/useSessionInterrupts.ts](../../../apps/platform-web/src/modules/chat/composables/useSessionInterrupts.ts)：
  - `activeReview`：当前处于等待决策状态的激活审批项。
  - `resolvedReviewIds`：已处理审批 ID 集合，用于快照回放去重。
  - `submitReview()`：构建并向网关发送 `input.respond` 指令。

### 2. 控制面反向代理与防篡改
- [apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py](../../../apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py)：
  - `send_thread_command()`：在 `method == "input.respond"` 时执行字段白名单过滤，阻断 `resume_configuration_override`。

### 3. 底座运行时挂起与状态机解冻
- [apps/runtime-service/src/runtime_service/runtime/access_policy.py](../../../apps/runtime-service/src/runtime_service/runtime/access_policy.py)：
  - `interrupts_for_access_policy()`：依据会话策略匹配判定是否触发审批。
- [apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/deployment.py](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/deployment.py)：
  - 典型高危部署工具，配置强审批拦截。

---

## 三、真实数据结构与报文（Real Payloads & DB Schemas）

### 1. 底座抛出的中断事件（SSE event: interrupt）
```http
event: interrupt
id: 1ef7cb92-1205
data: {
  "interrupt_id": "int-deploy-98fbc18c",
  "action": "deployment_execute",
  "title": "生产环境发布确认",
  "description": "智能体申请执行生产环境静态页面部署",
  "params": {
    "target_domain": "prod.platform.internal",
    "bundle_path": "/workspace/outputs/dist.zip",
    "git_commit": "7a8bc92"
  },
  "created_at": "2026-09-29T11:32:00Z"
}
```

### 2. 前端提交的恢复执行报文（POST /commands）
```http
POST /api/projects/proj-90f1ac23/threads/th-e90f23b1/commands HTTP/1.1
Host: api.platform.local
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
x-project-id: proj-90f1ac23
Content-Type: application/json

{
  "id": 2002,
  "method": "input.respond",
  "params": {
    "resume": {
      "int-deploy-98fbc18c": {
        "action": "approve",
        "operator": "user-super-admin",
        "timestamp": 1727580725
      }
    }
  }
}
```

---

## 四、端到端函数级调用时序（Function-Level Trace）

完整的人机协同中断挂起与解冻恢复调用链路时序：

```mermaid
sequenceDiagram
    autonumber
    participant Client as Platform Web (Vue 3)
    participant UIHook as useSessionInterrupts.ts
    participant Gateway as API: RuntimeGatewayService
    participant Upstream as API: Upstream Adapter
    participant Pregel as Runtime: LangGraph Pregel
    participant Tool as deployment_execute (高危工具)

    Note over Pregel,Tool: 阶段一：敏感操作拦截与状态机物理冻结
    Pregel->>Tool: 触发工具调用 (命中 review 访问策略)
    Tool->>Pregel: 调用 interrupt("int-deploy-98fbc18c", payload)
    Pregel->>Pregel: 1. 冻结当前节点堆栈上下文
    Pregel->>Pregel: 2. 状态机写快照落盘 (status="interrupted")
    Pregel-->>Upstream: 3. 下发 SSE event: interrupt (带 interrupt_id)
    Upstream-->>Gateway: 原始流数据透传
    Gateway-->>Client: 4. SSE 广播 interrupt 事件

    Client->>UIHook: 5. 捕获 interrupt 事件
    UIHook->>UIHook: 6. 检查 resolvedReviewIds (不在集合中)
    UIHook-->>Client: 7. 弹出全局审批对话框 (展示部署参数与影响范围)

    Note over Client,Gateway: 阶段二：用户决策与防篡改网关验证
    Client->>UIHook: 用户点击【批准发布】
    UIHook->>Gateway: 8. POST /commands (method="input.respond", resume={int_id: {...}})

    Gateway->>Gateway: 9. 校验 params 键名白名单
    alt 攻击者夹带额外配置 (如篡改 prompt 或 model)
        Gateway-->>Client: 抛出 400 BadRequest (resume_configuration_override)
    else 合法恢复报文
        Gateway->>Upstream: 10. send_thread_command(透传 input.respond)
        Upstream->>Pregel: 11. POST /threads/{id}/commands
    end

    Note over Pregel,Tool: 阶段三：精准解冻与工具执行闭环
    Pregel->>Pregel: 12. 根据 interrupt_id 找到原挂起节点的返回槽位
    Pregel->>Tool: 13. 唤醒并正式执行物理部署动作
    Tool-->>Pregel: 14. 部署成功，返回结果日志
    Pregel-->>Gateway: 15. 下发后续流式消息帧 (status="running")
    Gateway-->>Client: 16. 流式渲染后续输出
    Client->>UIHook: 17. resolvedReviewIds.add("int-deploy-98fbc18c")
    UIHook-->>Client: 18. 关闭审批弹窗并移除阻塞蒙层
```

---

## 五、核心实现高保真伪代码（High-Fidelity Pseudocode）

### 1. 前端回放去重与决策提交（useSessionInterrupts.ts）
```typescript
// 对应 apps/platform-web/src/modules/chat/composables/useSessionInterrupts.ts

export function useSessionInterrupts(threadId: Ref<string>, sendCommand: Function) {
  const activeReview = ref<ReviewItem | null>(null);
  // 维护已处理的审批 ID 集合，杜绝历史快照回放死锁
  const resolvedReviewIds = ref<Set<string>>(new Set());

  function handleInterruptEvent(eventData: InterruptPayload) {
    const interruptId = eventData.interrupt_id;
    // 关键防御：如果历史回放或者网络重放该事件，直接忽略
    if (resolvedReviewIds.value.has(interruptId)) {
      return;
    }
    activeReview.value = {
      id: interruptId,
      action: eventData.action,
      params: eventData.params,
    };
  }

  async function submitDecision(approved: boolean) {
    if (!activeReview.value) return;
    const interruptId = activeReview.value.id;

    // 1. 构建标准恢复指令
    await sendCommand({
      method: 'input.respond',
      params: {
        resume: {
          [interruptId]: {
            action: approved ? 'approve' : 'reject',
            timestamp: Date.now(),
          },
        },
      },
    });

    // 2. 标记已处理，防止后续重播再次弹出
    resolvedReviewIds.value.add(interruptId);
    activeReview.value = null;
  }

  return { activeReview, handleInterruptEvent, submitDecision };
}
```

### 2. 网关防篡改验证守卫（service.py）
```python
# 对应 apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py

async def send_thread_command(self, *, actor: ActorContext, project_id: str, thread_id: str, payload: dict[str, Any], ...):
    if payload.get("method") == "input.respond":
        params = payload.get("params") or {}

        # 严厉打击参数篡改：恢复执行时只能包含审批相关的 resume 槽位！
        # 任何人试图在 resume 时传入 model_id、prompt 或 tool 变更均立即抛出 400 阻断
        allowed_keys = {"interrupt_id", "response", "resume", "assistant_id", "responses", "namespace"}
        if set(params) - allowed_keys:
            raise BadRequestError(
                code="resume_configuration_override",
                message="Resume cannot change execution configuration"
            )

        resumes = params.get("resume")
        if not isinstance(resumes, dict) or not resumes:
            raise BadRequestError(code="interrupt_id_required", message="Resume requires valid interrupt IDs")

        # 校验通过，原样转发至底层运行时解冻
        return await self._upstream.send_thread_command(thread_id, payload)
```

---

## 六、假想断电与极限场景推演（Thought Experiments）

### 场景一：用户审批弹窗弹出后，由于误操作刷新了浏览器页面
- **推演过程**：页面刚刚弹出“生产环境部署确认”弹窗，用户不小心按了 F5 刷新了网页。
- **系统表现**：
  1. 页面重载后，`useChatSession` 重新拉取会话的最新 Checkpoint 状态。
  2. 发现底层图状态依然处于 `interrupted`，快照中保留着该未处理的 `int-deploy-98fbc18c`。
  3. 前端重新挂载，`resolvedReviewIds` 初始为空，识别到该中断未被解决，**重新精准渲染审批弹窗**。
  4. 用户点击批准，流程继续无缝流转，彻底避免了“一刷新任务假死”的问题。

### 场景二：用户拒绝审批高危操作（点击【拒绝执行】）
- **推演过程**：用户查看部署参数后认为时机不合适，点击了模态框上的【拒绝】按钮。
- **系统表现**：前端发送 `resume: {int_id: {"action": "reject", "reason": "等待变更窗口"}}`。底座接收到拒绝决策后，不会发生程序崩溃，而是由被挂起的工具节点捕获该结果，向上层模型返回一个语义化的 `ToolMessage(content="Action was rejected by user: 等待变更窗口")`。大模型接收到该拒绝反馈后，进入正常反思流程，输出文字回复用户（例如：“收到，已取消本次上线，待后续通知”）。

### 场景三：黑客抓包试图篡改恢复报文越权修改提示词
- **推演过程**：攻击者在用户点击审批时拦截报文，在 JSON 里硬塞入 `{"config": {"configurable": {"model_id": "malicious-model"}}}`。
- **系统表现**：报文到达 `platform-api` 网关层时，`send_thread_command` 严格计算 `set(params) - allowed_keys`，发现存在未经授权的 `config` 字段，直接在网关最外围抛出 `400 BadRequestError ("resume_configuration_override")`。请求直接被掐死，根本没有机会接触底座运行时。

---

## 七、架构不变量清单（Architectural Invariants）

1. **审批状态外部持久化原则**：所有中断的挂起与恢复，必须基于已提交的底层数据库 Checkpoint 驱动，严禁在应用内存中依赖单机 Event、Future 或 Sleep 等无状态机制维持审批。
2. **恢复执行零配置篡改原则**：处理 `input.respond` 恢复执行时，入参严格只能包含 `interrupt_id` 与对应的决策响应，绝对禁止携带任何运行时配置覆盖参数。
3. **前端回放幂等性原则**：已完成决定的 `interrupt_id` 必须由前端记入已解决集合（`resolvedReviewIds`），后续接收到同一 ID 的历史快照事件必须静默丢弃。
4. **决策结果闭环原则**：用户的批准或拒绝决策，必须以标准的 `ToolMessage` 形式回填至图的执行历史中，保证模型的下一步决策具有完整的因果认知依据。
