# 02 前端 ChatSession 连接状态与报错条解耦治理实现

## 改动时间
2026-09-27

## 相关任务
- Task 2.1: 优化 ChatSession 错误条与重连状态的展示
- Task 2.2: 调优 SDK 传输层补丁配置与防抖

## 改动文件
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`

## 具体改动
1. **解耦短暂重连态（reconnecting）与破坏性错误条展示**：
   在 `ChatSession.vue` 中，原逻辑在 `connectionState === "reconnecting"` 时计算 `connectionMessage = "连接恢复中"`，直接触发顶部大红框 `role="alert"` 及固定的【恢复连接】按钮展示。而此时底层 SDK 正在按指数退避策略自动重连，用户点击按钮属于无操作（noop），且该红框会在 2~3 秒后随着重连成功而闪烁消失，造成严重的假性故障误导。
   **修改后：**
   `connectionMessage` 仅在 `connectionState === "paused"`（即重连彻底失败耗尽，需要用户手动介入）时才输出 `"连接已断开，请重试"` 并展示【恢复连接】按钮；在 `reconnecting` 阶段由 SDK 保持后台静默自愈重试，不打扰用户正在进行的阅读与输入。
2. **测试验证**：
   运行 `pnpm test:run src/modules/chat/`，24 个测试文件、221 个单测全部通过；`sdk-stream-recovery.test.ts` 中针对 `: heartbeat\n\n` 保活与 45 秒空闲检测的 11 套测试全部绿。
