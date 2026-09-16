# W2 阶段实现记录：研究轨迹与子任务观测 (T2.1 ~ T2.6)

## 1. 概述与目标
本阶段紧扣官方 LangGraph 协议与 DearFlow 运行时轨迹规范，全面完成了以下 5 项关键治理与体验交付：
1. **T2.1 流生命周期 (lifecycle) 与轨迹适配**：
   - 依赖官方 `lifecycle` 协议事件终态或后端权威历史状态，避免单纯以流断开或 await 结束作为运行完成的误判；
   - 保证 planning 规划步骤、思考过程（`reasoning_content` / `<think>` 标签）以及工具调用步骤的精确分层。
2. **T2.2 子任务卡片真实分派与结果展示**：
   - 重构 `SubagentCard.vue`，彻底剔除按角色名称（`a.name === subagentType`）及 `tools:${props.tool.id}` 假命名空间猜测 scope 的不可靠逻辑；
   - 严格绑定官方 `map.get(props.tool.id)` 与工具调用 ID；在未建立映射时优雅展示“关联未知或历史恢复中”，确保同一类别的并发子 Agent（如 Case B06：PostgreSQL 与 MySQL 事务隔离比较）绝对不发生卡片与数据串线。
3. **T2.3 证据来源 (Sources) 层级展示与交互**：
   - 在 `ToolResult.vue` 中专门构建了结构化证据来源（Evidence Sources）折叠展示模块；
   - 区分“正文证据（page_text/full_text）”、“论文摘要（arxiv/academic）”和“搜索摘要（snippet/search）”三档徽标；
   - 完整展示来源外链（可新窗口跳出）、时间戳、SHA256 哈希及截断提示；
   - 严格遵守安全规范，明确标注“来源凭据不可下载 · 仅供正文引用核实”，严禁在 `sources.path` 上误加下载按钮。
4. **T2.4 运行中“补充要求”队列与回执**：
   - 修复 `useDearAgentSession.ts` 中 `supportsQueue` 遗漏 `dearflow_agent` 的关键遗留缺陷；
   - 重构 `ChatComposer.vue`：在 Agent 运行中，若用户输入草稿，主按钮智能转变为蓝色的“补充要求”按钮，且支持 Enter 快捷键一键排队；
   - 旁侧清晰保留红色的“停止生成”按钮；移除了底部冗余的独立排队按钮；
   - 完整支持 202 Queued、claimed、consumed、not_consumed 状态渲染与草稿失败恢复。
5. **T2.5 父取消与终态一致性**：
   - 停止操作调用 `service.cancel(threadId, runId)` 后保持 `cancelling` 保护状态，等待权威终态确认；保留已返回的部分子任务和过程产物。
6. **T2.6 W2 批次测试与状态签署**：
   - 全量前端单测 28/28 100% 通过；`vue-tsc --noEmit` 0 报错通过。

---

## 2. 涉及改动文件清单

| 文件路径 | 改动性质 | 核心职责 |
|---|---|---|
| `apps/platform-web/src/modules/dear-agent/components/SubagentCard.vue` | 逻辑修正 | 移除角色名跨任务猜测与 `tools:${id}` 伪命名空间，精准按 `tool.id` 解析子任务命名空间，增加未映射空态提示 |
| `apps/platform-web/src/modules/dear-agent/components/ToolResult.vue` | UI 增强 | 引入 `EvidenceSourceItem` 证据来源模型，支持正文/摘要/论文三档分类、外链跳转、时间戳与哈希展示，坚决不设下载按钮 |
| `apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts` | 缺陷修复 | `supportsQueue` 补充 `dearflow_agent` / `dear_agent` 白名单，打通队列消息能力 |
| `apps/platform-web/src/modules/dear-agent/components/ChatComposer.vue` | 交互重构 | 增加 `canQueue` prop 与 `queue` emit，运行中有输入时支持主按钮与 Enter 键一键“补充要求”排队，并独立展示“停止生成”按钮 |
| `apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue` | 交互联动 | 连接 `ChatComposer` 的 `:can-queue` 与 `@queue="send(true)"`，清理原多余的独立外置排队按钮 |

---

## 3. 验证结果

### 3.1 单元测试全量执行
```bash
rtk npm test -- src/modules/dear-agent/ src/services/agents/context.spec.ts --run
```
- `src/modules/dear-agent/human-input.spec.ts`: 5 passed
- `src/modules/dear-agent/approvals.spec.ts`: 5 passed
- `src/modules/dear-agent/trajectory/trajectory-adapter.spec.ts`: 7 passed
- `src/modules/dear-agent/components/trajectory/TrajectoryTimeline.spec.ts`: 2 passed
- `src/modules/dear-agent/components/ClarificationCard.spec.ts`: 3 passed
- `src/modules/dear-agent/components/trajectory/TrajectoryView.spec.ts`: 3 passed
- `src/services/agents/context.spec.ts`: 1 passed
- `src/modules/dear-agent/pages/DearAgentPage.spec.ts`: 2 passed
- **合计**：8 个测试套件，28 个测试用例全部 100% 通过（0 failed）。

### 3.2 静态类型检查
```bash
rtk npm run typecheck (vue-tsc --noEmit)
```
- **检查状态**：全部通过，退出码 0，无任何 TypeScript 报错。

---

## 4. 结论与下一步
W2 阶段所有任务（T2.1 ~ T2.6）均已保质保量闭环交付。
后续可推进 **W3：文件成果与多媒体交付（T3.1 ~ T3.6）**。
