# 05 安全审批与人机协作澄清边界及全权负责常驻设计

## 1. 背景与问题复盘

### 1.1 线上/联调现场问题
在用户选择「全权负责 (Full access)」策略后与智能体对话（例如触发“设计功能方案：根据业务需求给出优雅的架构与接口设计”），智能体因缺少设计所需的前置业务约束，主动调用了 `request_information` 工具。
随后出现两个问题：
1. **状态被意外篡改**：在 `request_information` 触发中断或等待用户输入后，输入框左侧的访问策略从「全权负责 (Full access)」变回了「审阅每项操作 (Review)」。
2. **交互语义混淆**：即使开启了全权负责，当智能体需要人类填写必要参数或做关键业务信息确认时，用户依然需要编辑和填报信息。

### 1.2 根因分析 (Root Cause)
经过全链路排查，代码库中存在两处致命的硬编码缺陷：
1. **`refreshAccessPolicy()` 暴力三元运算**：
   在 `apps/platform-web/src/modules/chat/composables/useChatSession.ts:78` 与 `useDearAgentSession.ts:82` 中：
   ```typescript
   // 缺陷代码：仅判断了 workspace_write，导致 full_access 被强制归入 review
   accessPolicy.value = policy === "workspace_write" ? "workspace_write" : "review";
   ```
   当线程在后端正确保存了 `full_access` 后，每次流中断触发 `verify()` 进而调用 `refreshAccessPolicy()`，或者页面重载时，前端直接将其判定为非 `workspace_write`，从而强行重置为 `review`！
2. **草稿态首发补发漏判 `full_access`**：
   在 `send()` 首发消息逻辑中：
   ```typescript
   // 缺陷代码：只拦截了 workspace_write
   if (accessPolicy.value === "workspace_write") {
     await updateThreadAccessPolicy(options.projectId, thread.thread_id, "workspace_write");
   }
   ```
   草稿态预选 `full_access` 后发送首条消息，由于条件不匹配，未向 Platform API 补发 `PATCH` 请求，导致后端线程 metadata 仍为创建时默认的 `review`，首轮对话后被后端拉平回审阅模式。

---

## 2. 核心概念边界厘清（架构铁律）

系统必须在架构和心智模型上严格区分两类完全不同性质的中断：

```
                           ┌───────────────────────────────┐
                           │      LangGraph 中断 (Interrupt) │
                           └───────────────┬───────────────┘
                                           │
                   ┌───────────────────────┴───────────────────────┐
                   ▼                                               ▼
     【安全审批 (Security Approval)】               【业务澄清输入 (Clarification/Input)】
    典型工具：write_file / execute / deploy           典型工具：request_information
    ──────────────────────────────────────          ──────────────────────────────────
    • 目的：防御越权与破坏性副作用                    • 目的：智能体遇到信息真空，主动向人求助
    • 场景：Agent 已算好参数，向系统要权限            • 场景：Agent 算不出参数，向人类要输入
    • 受控：受 access_policy 控制                   • 受控：不受 access_policy 豁免
      - review: 逐项拦截审批                         - 无论任何策略（哪怕 Full access），
      - workspace_write: 工作区内免审                 都必须暂停并展示表单等待人类输入！
      - full_access: 全量免审直接执行
```

### 2.1 铁律一：全权放权 (Full access) 绝不等于跳过人类输入
- **全权放权** 的核心承诺是：**“信任智能体所作所为，不再弹出安全拦截对话框向人类索取执行授权。”**
- 但如果智能体调用了 `request_information`，说明智能体缺少业务决策输入（例如目标 QPS、数据库选型、业务预算等）。
- **如果把人机协作输入也“免审默认放行”，智能体将拿到一组空值（None / null），后续执行将产生幻觉、脏数据甚至程序崩溃。**
- 因此：**人机交互类工具天然独立于安全审批策略，哪怕在 Full access 模式下，也必须挂起并提供编辑/输入界面！**

### 2.2 铁律二：会话访问策略必须强一致常驻
- 会话的策略代表当前对话生命周期内用户授予的安全基准（`review` / `workspace_write` / `full_access`）。
- 任何业务中断（如填写 `request_information`）、网络重试、消息分叉或轮次推进，**绝不能改变既有的策略状态**。
- 只有用户在界面上主动切换并确认，策略才能变更。

---

## 3. 技术实施方案

### 3.1 状态机与 Composable 修复
1. **`refreshAccessPolicy()` 完整三态映射**：
   ```typescript
   if (!disposed && thread?.metadata && typeof thread.metadata === "object") {
     const policy = (thread.metadata as Record<string, unknown>).access_policy;
     if (policy === "workspace_write" || policy === "full_access") {
       accessPolicy.value = policy;
     } else {
       accessPolicy.value = "review";
     }
   }
   ```
2. **`send()` 草稿态非默认策略通用补发**：
   ```typescript
   if (accessPolicy.value !== "review") {
     try {
       await updateThreadAccessPolicy(
         options.projectId,
         thread.thread_id,
         accessPolicy.value,
       );
     } catch (cause) {
       accessPolicy.value = "review";
       fail(cause);
       return false;
     }
   }
   ```
3. 对齐文件范围：
   - `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
   - `apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts`

### 3.2 交互与表单对齐
- **Dear Agent 模块**：已有成熟的 `ClarificationForm` 交互卡片，当触发 `request_information` 时呈现表单，用户填报后通过 `resume` 恢复执行，随后策略坚挺保持为 `full_access`。
- **主平台 Chat 模块**：
  - 针对 `request_information` 工具中断，避免直接展示冷冰冰的原始 JSON 审批卡片；
  - 确保提交补充信息后，前端状态机平滑恢复，不触发策略回滚。

---

## 4. 实施与验证清单

- [x] 架构概念与边界方案文档固化 (`05-clarification-vs-approval-boundary.md`)。
- [ ] 修复 `useChatSession.ts` 中 `refreshAccessPolicy` 与 `send()` 的策略还原与补发逻辑。
- [ ] 修复 `useDearAgentSession.ts` 中对应的策略还原与补发逻辑。
- [ ] 编写/更新针对 `full_access` 草稿态首发 PATCH 与流中断后策略常驻的单元测试。
- [ ] 运行平台全套前端单测（18+ 项）、`vue-tsc` 类型检查与构建验证。
