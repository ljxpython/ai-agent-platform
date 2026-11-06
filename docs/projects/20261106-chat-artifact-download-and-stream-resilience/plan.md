# 前端 Markdown 产物链接拦截下载与空闲会话长连接断开误报治理 - 整体方案

## 背景

在实际使用智能体平台生成产物（如 PPTX、调研文档）及多会话切换操作时，暴露出两个严重影响用户体验的前端缺陷：

1. **点击下载 PPTX 跳转空白会话缺陷**：
   - Agent 完成生成并调用 `present_artifacts` 登记产物后，在总结中按规范输出了 Markdown 链接：`[下载 PPTX](artifact://5382da7fee127023503035bf2d0401c8ab147e8a3e27cb4564e66490bd191723)`。
   - 前端 Markdown 渲染器 `apps/platform-web/src/utils/markdown.ts` 的 `SAFE_PROTOCOLS` 仅包含 `["http:", "https:", "mailto:", "blob:"]`，未将平台定义的 `artifact:` 纳入白名单。
   - `sanitizeUrl` 强行将 `artifact://...` 重写为 `href="#"`，且全局规则注入了 `target="_blank"`。
   - 用户点击后，浏览器新开标签页打开了带 `#` 锚点的空白页，未触发任何下载，用户误以为生成失败。

2. **切换切回已完成会话时弹出 `Event stream closed.` 幽灵误报**：
   - 平台前端采用 `ChatSessionPool` 会话池保活已打开的会话；切至其他会话时，后台会话被置为 `visible = false` 并调用 `parkEvents()` 挂起 SSE 连接以释放浏览器连接槽。
   - 当用户从其他会话切回该会话时，`visible` 变回 `true`，触发 `reconnectStream().catch(fail)` 尝试重连。
   - 对于已执行完毕（无活跃 Run）的会话，后端与反向代理连接关闭，SDK 重连失败抛出 `Error("Event stream closed.")`。
   - 前端 `isNonFatalStreamError` 漏掉了该异常判定，导致 `fail(cause)` 将空闲连接断开误判定为致命崩溃，在顶部弹出橙色横条并让状态栏爆红 `✕ 执行出错: Event stream closed.`。

## 目标

1. **产物一键下载与安全闭环**：
   - 在 Markdown 渲染层安全保留 `artifact://` 协议，不被洗为 `#`。
   - 在前端点击链接时精准拦截 `artifact://<artifact_id>`，解析产物元数据并调用 `getWorkspaceContentBlob` 触发浏览器原生文件下载（自动带上正规文件名和扩展名），严禁打开新空白标签页。
   - 完善容错提示，若产物文件不存在或已失效，弹出友好 Toast 引导用户前往工作区抽屉核查。
2. **连接池重连韧性与误报消除**：
   - 完善 `isNonFatalStreamError`，明确将 `Event stream closed.`、`Protocol event stream closed.` 等空闲断开异常识别为无害流断开。
   - 在切回会话时，如果会话处于终态（无 active run），即使重连被拒也不弹出错误横幅，确保已完成的静态历史记录展现干净、优雅。

## 方案设计

### 模块一：Markdown 产物协议放行与原生下载拦截

#### 1. 协议白名单放行
在 `apps/platform-web/src/utils/markdown.ts` 中：
- 将 `artifact:` 加入 `SAFE_PROTOCOLS`，确保 `sanitizeUrl("artifact://xxx")` 完整保留原链接。
- 在 `link_open` 规则中，对于 `href.startsWith("artifact://")` 的链接，移除 `target="_blank"`，并添加特定类名（如 `pw-artifact-link`）和 `data-artifact-id` 属性，方便事件代理捕获。

#### 2. 点击事件拦截与文件下载触发
在 `ChatMessageItem.vue` 或 `ChatMessageContent.vue` 的 DOM 容器上（或全局点击事件）：
- 监听 `click` 事件。
- 检查目标元素是否为 `a[data-artifact-id]` 或 `href.startsWith("artifact://")`。
- 若匹配：
  1. 调用 `event.preventDefault()` 和 `event.stopPropagation()`，彻底阻断默认超链接跳转行为；
  2. 提取 `artifactId`；
  3. 通过项目上下文 `activeProjectId` 及 `threadId`，向平台 API 查询该产物的元数据或直接调用下载接口；
  4. 使用平台现成的 `getWorkspaceContentBlob` / `triggerBlobDownload` 将二进制流转为文件并自动唤起浏览器下载保存。

### 模块二：空闲会话重连异常收敛与防误报

#### 1. 非致命流错误收敛
在 `apps/platform-web/src/modules/chat/composables/useChatSession.ts` 中：
- 扩展 `isNonFatalStreamError` 判定逻辑：
  ```typescript
  const isNonFatalStreamError = (err: unknown): boolean => {
    if (!err) return true;
    const raw = err instanceof Error ? err.message : String(err);
    return (
      raw.includes("409 Conflict") ||
      raw.includes("pending or running run") ||
      raw.includes("multitaskStrategy is 'reject'") ||
      raw.includes("already in flight") ||
      raw.includes("Upstream stream ended before terminal chunk") ||
      raw.includes("AbortError") ||
      raw.includes("BodyStreamBuffer") ||
      raw.includes("Event stream closed") ||
      raw.includes("Protocol event stream closed")
    );
  };
  ```

#### 2. 唤醒重连错误静默处理
在 `useChatSession.ts` 的 `watch([visible, ...])` 唤醒监听中：
- 当用户切回会话（`eventsParked.value` 为 true 时唤醒）执行 `reconnectStream()`：
  若当前会话没有正在运行的 Run（`!active(run.value)`），catch 捕获到错误时进行静默消化，重置 `eventsParked = false`，不调用 `fail(cause)`，杜绝状态栏误报红框。

## 关键改动点

| 改动文件 | 改动点 | 预期效果 |
| :--- | :--- | :--- |
| `apps/platform-web/src/utils/markdown.ts` | 增加 `artifact:` 协议白名单，特殊标记产物链接 | 避免清洗为 `#`，防止外跳新标签页 |
| `apps/platform-web/src/modules/chat/components/ChatMessageContent.vue` | 增加产物链接点击委托与流式下载触发 | 点击 `artifact://...` 原生下载文件 |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | `isNonFatalStreamError` 补充断流错误，终态静默过滤 | 切会话不再闪烁橙条与红色错误横幅 |

## 风险与应对
- **风险 1：** 若产物在沙箱回收或重置后被删除，用户点击可能报错 404。
  - **应对：** 点击下载接口加 try-catch 保护，404 时弹出轻量 Toast 提示“产物文件已归档或不可用，可在工作区面板中查看”。
- **风险 2：** `Event stream closed` 过滤是否会掩盖真实的流式中断？
  - **应对：** 仅对没有处于 active run 状态下的空闲会话或者已被判定为已完成的回合忽略；若当前处于 `isRunning` 状态且流被异常切断，依然保留现有重试与恢复链路。

## 实施计划
1. **Phase 1: 代码仓库基线提交**：将上一阶段完成的会话删除死锁治理代码安全提交并推送到远端仓库。
2. **Phase 2: 方案评审与确认**：用户评估方案设计与改动范围。
3. **Phase 3: 编码实施**：前端 Markdown 协议拦截下载 + 会话池断流误报消除。
4. **Phase 4: 全面验证**：单元测试、TypeScript 类型检查、生产构建与真实点击下载/切会话验证。
