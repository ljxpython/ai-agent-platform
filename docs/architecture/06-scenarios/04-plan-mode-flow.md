# 06-04 先规划后执行（Plan Mode）端到端全链路时序深度解密

> **场景定位与核心价值**：解析智能体在长程复杂工程任务中的**先规划后执行（Plan Mode）与原生审批治理链路**。
> 解决智能体“边想边盲目写代码、一错改毁全工作区”的严重痛点；在动工前动态裁剪工具集，强制生成分步实施计划并挂起抛出原生审批中断；前端提供双重视图与 Markdown XSS 消杀，支持人工批准、提出修改建议（1-2000字符）与放弃计划。

---

## 零、 场景拓扑与核心时序

```mermaid
sequenceDiagram
    autonumber
    participant Web as 前端工作台 (PlanReview.vue)
    participant API as Platform API (2142)
    participant Runtime as Runtime API (8123)
    participant Worker as Runtime Worker (LangGraph)
    participant LLM as 大语言模型

    %% 阶段一：启用规划模式发起运行
    Web->>API: 1. POST /api/v1/threads/{id}/runs (带 plan_mode=true, prompt)
    Note over Web: 输入框进入锁定态<br>显示“规划中”琥珀色徽章
    API->>API: 2. 注入受管契约 (锁定 plan_mode 标记)
    API->>Runtime: 3. 签发 Delegation JWT (operation="agent_run")
    Runtime->>Worker: 4. 派发 LangGraph 图执行

    %% 阶段二：动态裁剪工具与生成计划
    Note over Worker: 动态中间件生效：<br>裁剪掉 write_file/execute 等写工具<br>仅保留 read_file/glob 等只读调研工具
    Worker->>LLM: 5. 调研并起草分步实施方案 (Draft Plan)
    LLM-->>Worker: 6. 返回结构化计划 Markdown
    Worker->>Worker: 7. 触发 interrupt(type="plan_approval", plan=markdown)
    Note over Worker: 状态机挂起，保存 Checkpoint
    Worker-->>Runtime-->>API-->>Web: 8. SSE 下发 interrupt 事件 (payload 包含待审方案)

    %% 阶段三：前端交互与三种治理分支
    Note over Web: 弹出 PlanReview 双重视图<br>防 XSS 清洗渲染<br>提供：批准 / 提出修改建议 / 放弃

    alt 分支 A: 人工批准 (Approve)
        Web->>API: 9a. POST /commands (respond: {action: "approve"})
        API->>Runtime: 10a. 恢复执行 (resume)
        Note over Worker: 恢复原图流转<br>解封全量工具 (write_file/execute)<br>开始按批准计划真实写代码
    else 分支 B: 提出修改建议 (Revise, 1~2000字)
        Web->>API: 9b. POST /commands (respond: {action: "revise", feedback: "补充测试用例"})
        API->>Runtime: 10b. 恢复执行 (resume 带 feedback)
        Worker->>LLM: 11b. 结合修改意见重新起草计划
    else 分支 C: 放弃计划 (Abandon)
        Web->>API: 9c. POST /commands (respond: {action: "abandon"})
        API->>Runtime: 10c. 软收尾终止运行
    end
```

---

## 一、 关键阶段与源码坐标映射

| 阶段步骤 | 关键代码路径 | 职责与防御细节 |
|---|---|---|
| **1. 规划模式入参消杀** | `apps/platform-api/src/platform_api/core/runtime_contract.py` | `normalize_protocol_v2_command()` 校验 `plan_mode` 参数合规性 |
| **2. 工具动态裁剪守卫** | `apps/runtime-service/src/runtime_service/runtime/access_policy.py` | 识别 `plan_mode`，动态剥离 `WORKSPACE_WRITE_TOOLS`，仅放行调研工具 |
| **3. 原生规划中断挂起** | `apps/runtime-service/src/runtime_service/graphs/` | 调用 LangGraph 原生 `interrupt()`，写入持久化检查点 |
| **4. 前端安全渲染审核卡片** | `apps/platform-web/src/modules/chat/components/PlanReview.vue` | 严格 Markdown 语法消杀，输入框锁定，修改建议字数校验 |
