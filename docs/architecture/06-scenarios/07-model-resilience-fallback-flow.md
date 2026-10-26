# 06-07 大模型瞬态故障毫秒级主备容灾降级时序深度解密

> **场景定位与核心价值**：解析智能体在执行长程复杂任务时，遭遇外部 LLM 供应商**网络抖动、429 限流或服务宕机时的毫秒级容灾降级（Model Fallback）时序**。
> 消除大模型服务商作为外部不可控单点的脆弱性；通过受管备用模型自动切换中间件与签名快照，保障关键任务的确定性执行，并在前端呈现备用模型微胶囊 Tag 保持透明。

---

## 零、 场景拓扑与核心时序

```mermaid
sequenceDiagram
    autonumber
    participant Worker as Runtime Worker (LangGraph 节点)
    participant ResilienceMid as 模型容灾中间件 (ModelResilience)
    participant PrimaryLLM as 生产主模型 (如 DeepSeek-R1)
    participant BackupLLM as 受管备用模型 (如 DeepSeek-Flash / 本地模型)
    participant Web as 前端聊天窗口 (Vue3)

    Worker->>ResilienceMid: 1. 向主模型发起流式生成请求
    ResilienceMid->>PrimaryLLM: 2. 调用 POST /chat/completions (主模型)

    %% 主模型发生瞬态故障
    Note over PrimaryLLM: 触发 429 频繁限流 / 网络丢包超时 / 503 服务宕机
    PrimaryLLM--xResilienceMid: 3. 抛出 APIStatusError (503 Service Unavailable)

    %% 容灾中间件毫秒级介入
    Note over ResilienceMid: 捕获瞬态故障，判定命中重试与降级策略：<br>1. 记录主模型失败原因与重试计数<br>2. 毫秒级提取备用模型凭据与配置 (Backup Model)<br>3. 重新组装不可变消息签名快照
    ResilienceMid->>BackupLLM: 4. 自动重定向调用备用模型 (无需重头跑图)
    BackupLLM-->>ResilienceMid: 5. 备用模型正常返回流式 Token 块

    %% 输出与前端感知
    ResilienceMid-->>Worker: 6. 成功返回流式回答，附加 fallback_active 元数据
    Worker-->>Web: 7. SSE 流式输出，前端聊天气泡上方呈现：<br>【已启用备用模型: DeepSeek-Flash】微胶囊 Tag
```

---

## 一、 关键阶段与源码坐标映射

| 阶段步骤 | 关键代码路径 | 职责与防御细节 |
|---|---|---|
| **1. 备用模型配置与网关签名** | `apps/platform-api/src/platform_api/modules/models/` | 模型 Catalog 配置受管备用模型与恢复重试策略 |
| **2. 运行时容灾拦截中间件** | `apps/runtime-service/src/runtime_service/middleware/model_resilience.py` | 捕获 429/5xx 异常，执行最大等待时间与备用模型平滑替换 |
| **3. 前端透明感知微胶囊** | `apps/platform-web/src/modules/chat/components/MessageHeader.vue` | 识别 `fallback_model` 标记，高亮琥珀色备用模型标签 |
