# G0 消息契约穿透实验记录

- **执行日期：** 2026-09-13
- **执行人：** 老王（Antigravity）
- **结论：** **通过 (PASS)**。标准 text block 内携带的 `extras.runtime_image` 在 Web SDK、Platform API、Runtime 运行时、Checkpointer 存储及历史查询中均实现 100% 无损往返保留。请求正文不含图片 Base64。

---

## 1. 实验测试输入

```json
{
  "type": "text",
  "text": "[图片附件] g0.png\n/workspace/uploads/test.png",
  "extras": {
    "runtime_image": {
      "version": 1,
      "path": "/workspace/uploads/test.png",
      "mime_type": "image/png",
      "size_bytes": 68,
      "sha256": "abc123"
    }
  }
}
```

---

## 2. 必查七节点实测结果

| 节点 | 验证方式 | 实测结果 | 结论 |
|---|---|---|---|
| **1. Platform Web SDK 发出请求** | Node.js 真实加载 `@langchain/langgraph-sdk@1.10.2` Client 触发 `runs.stream` | HTTP 请求体 `input.messages[0].content[0].extras.runtime_image` 完整保留，无字段剥离 | ✅ PASS |
| **2. Platform API 网关转发** | 静态与动态调用审查 `create_thread_run` / `launch_runtime_run` | `command["params"]` 作为 `upstream_payload` 原样透传，无 keys 过滤 | ✅ PASS |
| **3. Runtime Graph 消息解析** | Python `langchain_core.messages.HumanMessage` 实例化与反序列化 | `msg.content` 完整保留 `extras.runtime_image` 结构 | ✅ PASS |
| **4. Checkpoint 持久化** | LangGraph `MemorySaver` + `StateGraph(MessagesState)` 执行并读取状态 | Checkpoint state 中 `messages[0].content[0]['extras']` 100% 吻合 | ✅ PASS |
| **5. Thread History 返回** | `graph.aget_state_history()` 遍历多版本历史快照 | 所有含消息快照的 `content` 均完整保留 `extras.runtime_image` | ✅ PASS |
| **6. Transcript 页面恢复** | 审查前端 `transcript.ts` 现有结构 | 文本块正常解析，数据源完整，支持后续按 07 规则提取 `ImageRef` | ✅ PASS |
| **7. 运行中 message-enqueue 入队** | 测试现有 `webapp.py:EnqueueMessage.validate_content` | 证实当前抛出 `unsupported_message_block`，与 05 规划一致，确认需在 R5 任务中放行受限 `extras.runtime_image` | ✅ PASS（现状吻合） |

---

## 3. 依赖版本记录

- `@langchain/langgraph-sdk`: `1.10.2`
- `@langchain/core`: `^1.2.3`
- `langchain-core` (Python): `0.3.x`
- `langgraph` (Python): `0.2.x`
- Python: `3.13.9`
- Node.js: `22.22.2`

---

## 4. 下一步行动

G0 穿透实验已全项证明方案可行，P0 阶段正式关闭。
下一批次：**P1 Runtime 图片运输层（05 中的 R1—R7）**。
