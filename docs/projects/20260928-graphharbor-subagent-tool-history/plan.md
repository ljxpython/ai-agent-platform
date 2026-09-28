# 专项方案设计：子智能体工具调用历史回放与端侧承接设计

## 一、背景与目标

主 Agent 委派子智能体执行代码审查和复杂任务时，子智能体的具体操作轨迹（例如读取了哪些文件、执行了哪些 grep 命令）是不可或缺的审计信息。
当前系统在实时 SSE 阶段已支持子步骤展示，但刷新页面加载历史时，由于 GraphHarbor 及原生 LangGraph REST 接口局限，前端无法拿到子图的工具调用记录。

本方案旨在：
1. **明确上游对接标准**：向 GraphHarbor 团队提交 [RFC 提案文档](graphharbor-rfc.md)；
2. **设计平台端承接方案**：一旦 GraphHarbor 支持子图状态返回，我们在 `platform-api` 和 `platform-web` 侧如何精确改造承接；
3. **设计平台侧自救/兜底方案**：若 GraphHarbor 排期延期，我们如何在现有技术栈内自闭环解决该问题。

---

## 二、双轨解决方案设计

```mermaid
flowchart TD
    A[用户刷新浏览器加载会话历史] --> B{GraphHarbor 是否已支持 RFC?}

    subgraph 轨道一：GraphHarbor 支持（标准方案）
    B -- 是 (方案1/2) --> C[platform-api 透传 expand_subagents]
    C --> D[GraphHarbor 返回包含子图 checkpoint 的 state]
    D --> E[platform-web 将子图消息注入 stream.subagents]
    E --> F[SubtaskDetail 组件原生渲染 10 步工具调用]
    end

    subgraph 轨道二：GraphHarbor 暂未支持（平台侧自救兜底）
    B -- 否 (排期中) --> G[runtime-service DelegationMiddleware]
    G --> H[任务完成时将内部工具调用轨迹注入 task 工具的 artifact]
    H --> I[ToolMessage 携带 artifact.subagent_trace]
    I --> J[SubagentCard / SubtaskDetail 兼容解析 artifact 离线数据]
    J --> F
    end
```

---

## 三、如果 GraphHarbor 解决了，我们需要如何承接？

如果 GraphHarbor 团队采纳 [RFC 提案](graphharbor-rfc.md) 中的**方案 1（`expand_subagents=true` 聚合）**或**方案 2（支持按 `checkpoint_ns` 查询）**，平台端的具体承接改造如下：

### 1. platform-api（网关转发与参数放通）

- **文件：** `apps/platform-api/src/platform_api/adapters/langgraph/threads_sdk_adapter.py`
  - **改动**：在 `_STATE_FIELDS` 和 `_HISTORY_FIELDS` 中扩展支持 `subagents`、`checkpoint` 和 `checkpoint_ns`：
    ```python
    _STATE_FIELDS = ("subgraphs", "checkpoint_id", "expand_subagents", "checkpoint_ns", "checkpoint")
    ```
- **文件：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`
  - **改动**：在 `GET /threads/{thread_id}/state` 端点中增加 `expand_subagents: bool | None = Query(default=None)` 参数，并无损转发给 GraphHarbor。

### 2. platform-web（前端历史数据注入与组件点亮）

- **文件：** `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts` 与 `ChatSession.vue`
  - **改动**：
    1. 当加载初始线程状态（Initial Thread State）时，若响应中包含 `subagents` 映射，将其灌入前端 `@langchain/vue` 的 `stream.subagents` 响应式 Map 中；
    2. 为每一个子图注册对应的内部 `messages` 列表；
- **文件：** `apps/platform-web/src/modules/chat/components/SubtaskDetail.vue`
  - **改动**：
    已有的 `useTranscriptMessages(props.stream, props.namespace)` 能够直接从注入的命名空间中读出这 16 条消息并计算出 10 次工具调用；
    无需对 `<SubtaskDetail>` 进行大幅重构，已有展示逻辑自动完全点亮！

---

## 四、如果 GraphHarbor 暂时不解决，平台端如何自救解决？（降级兜底方案）

为了确保业务迭代不被外部依赖卡脖子，我们设计了**纯平台端自闭环的兜底方案**：

### 1. runtime-service 侧：DelegationMiddleware 轨迹附着
- **位置：** `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/subagents.py` 或通用的 Agent Middleware
- **实现机制**：
  在子智能体执行完成返回前，拦截器捕获子图 context 中的所有内部工具调用列表（工具名、入参、状态），将其打包为一个结构化的数组：
  ```python
  subagent_trace = [
      {"name": "ls", "input": {"path": "/workspace"}, "status": "finished"},
      {"name": "read_file", "input": {"file_path": "/workspace/report.py"}, "status": "finished"},
      {"name": "grep", "input": {"pattern": "total_sales"}, "status": "finished"},
      ...
  ]
  ```
  将其存放在返回给主图的 `ToolMessage` 的 `artifact` 字段中：
  `artifact = {"subagent_trace": subagent_trace, ...}`。

### 2. platform-web 侧：SubtaskDetail 兼容离线 Trace 降级渲染
- **文件：** `apps/platform-web/src/modules/chat/components/SubtaskDetail.vue`
  - **实现机制**：
    `subtaskTools` 计算属性增加降级兼容逻辑：
    ```ts
    const subtaskTools = computed<ToolItem[]>(() => {
      // 1. 若实时流/历史命名空间存在，优先使用实时工具流
      if (liveTools.length > 0) return liveTools;

      // 2. 兜底逻辑：若 stream 无数据，但 tool.artifact 中带有 subagent_trace，自动映射为 ToolItem 列表渲染
      const trace = asObject(props.tool?.artifact).subagent_trace;
      if (Array.isArray(trace)) {
        return trace.map((t, idx) => ({
          key: `fallback-subtool-${idx}`,
          id: `fallback-subtool-${idx}`,
          name: t.name,
          input: t.input,
          output: t.output,
          status: t.status || "finished",
        }));
      }
      return [];
    });
    ```
- **收益**：**完全不依赖 GraphHarbor 升级任何接口**，即使在当前版本的后端下，也能在 1 天内让前端刷新后立即呈现子智能体工具调用步骤！

---

## 五、链路影响与契约规范

| 调用环节 | 原契约行为 | 目标契约行为 | 影响评估 |
|---|---|---|---|
| platform-web → platform-api | `GET /threads/{id}/state` 返回根消息 | 增加 `expand_subagents=true` 支持返回子图状态 | 向后兼容，不传则行为不变 |
| platform-api → GraphHarbor | 只查根命名空间 `checkpoint_ns=""` | 支持传递 `checkpoint_ns` 或请求子图聚合 | 严格对齐 RFC 规范 |
| tool message artifact | 原生仅包含文本报告 | 兜底模式下附带 `subagent_trace` 数组 | 纯增量数据，不破坏现有前端逻辑 |
