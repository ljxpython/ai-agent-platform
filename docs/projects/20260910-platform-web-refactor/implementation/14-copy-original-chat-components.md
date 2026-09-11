# 直接取回旧版 Chat 前端组件

## 范围与来源

2026-09-11 用户再次明确：直接复制重构前最后一版的前端，保留当前后端逻辑。本轮在当前 Web 中接回 Git `8056869` 的展示组件，不恢复旧 `useChatWorkspace` / `usePlatformChatStream`、旧请求字段或旧 Agent/Graph 双入口。

沿用 implement-feature / verify-change 的既有项目留痕。本轮不修改 Platform API、Runtime、GraphHarbor，不新增依赖；此前后端修复仍保留。

## 实际取回的源码

路径前缀：`apps/platform-web/src/modules/chat/`。

| 文件 | 来源及必要适配 |
| --- | --- |
| `components/ChatThreadSidebar.vue` | 直接取回旧文件；恢复日期分组、预览区域、分页、逐条删除。适配当前服务端分批加载、权限与稳定的可访问名称；预览字段未提供时沿用旧空内容提示 |
| `components/ChatRunOptionsDialog.vue` | 直接取回旧文件；恢复 Max Tokens 与确认/取消/还原，模型提交改为当前 UUID |
| `components/ChatContextDrawer.vue` | 直接取回旧文件；恢复概览、ToDo、Files、历史四区与原布局，接入当前公开状态与 checkpoint；文件编辑入口仅在存在真实写回回调时开放 |
| `components/ChatArtifactPanel.vue` | 直接取回，内容与 `8056869` 完全一致；继续安全显示公开 `ui` 条目 |
| `components/ChatAgentStatusBar.vue` | 直接取回旧文件；“继续执行”适配为跳转当前审批面板，不绕过逐项审批 |
| `components/ChatMessageList.vue` | 从旧文件提取消息模板、气泡、标识及操作栏，接到当前 `buildTranscript`；恢复用户复制、原位编辑与回复重试。公开工具内容仍使用当前安全渲染器 |
| `thread-list-view-model.ts`、`history-view-model.ts`、`branching.ts`、`live-follow-view-model.ts` | 取回纯展示转换函数；不恢复旧网络编排 |
| `components/ChatComposer.vue`、`ChatModelSelector.vue` | 上一轮已从旧版恢复，本轮继续使用；手机附件操作保留图标与可访问名称，给高级模型选择器留足宽度 |

`apps/platform-web/src/styles/index.css` 与旧 `8056869` 完全一致。本次没有另造配色、组件库或聊天风格。

## 接线与必要修复

- `pages/ChatPage.vue`：使用旧侧栏与专注模式条，沿用当前项目/Agent/Thread 路由和过期响应隔离；按用户、项目、Agent、Thread 存储文字草稿。`apps/platform-web/src/stores/auth.ts` 在退出登录时清理该类草稿。
- `components/ChatSession.vue`：旧弹窗操作只修改参数草稿，确认后使用现有 `parseAgentContext` 校验并提交；取消不污染当前参数。详情抽屉读取当前 state/history，查看快照不创建 Run；原位编辑和重试调用现有 `session.fork`。重试从回答前 checkpoint 无 input 重新执行，保留原用户消息 ID；取回旧消息旁分支导航，只读浏览不发 Run。旧跟随提示卡、未读计数和最后活动反馈接回当前状态；打开抽屉/参数时暂停跟随。
- `composables/useTranscriptMessages.ts`：父图明确写入自己 `values.messages` 的子图返回结果属于正式回复，不能再因最早来自子图而隐藏；停止流式后以精确 namespace 的公开 values 校准半截回放，其他子图消息仍隔离。继续使用官方 SDK 通道与消息类型，不另建 SSE 解析器。
- `components/ChatMessageList.vue`：旧浅色气泡模板补充必要的深色背景/文字对比；用 `data-author` 区分用户输入与 Agent 回复，验收不再让用户输入命中回复断言。
- `apps/platform-web/src/components/base/BaseDrawer.vue`：补 dialog 可访问名称、入场动画结束后聚焦及 Tab/Shift+Tab 焦点约束，便于读屏和键盘操作。

## 验证方法与范围

- `e2e/workbench-restoration.spec.ts`：真实本地 API、Runtime 与已配置模型，覆盖参数非法值/确认/取消、草稿刷新、Agent 正式回复、原位编辑创建分支、刷新读回、只读快照、浅/深主题、1440/390 布局、模型弹层及专注模式。断言限定 Agent 消息，不匹配用户提示词。
- `e2e/parallel-chat-refactor.spec.ts`：保持并行审批、父子消息隔离、三尺寸和 20 次 Thread 切换断言；定位随旧版抽屉和逐条删除按钮更新。
- `ChatMessageList.spec.ts`：复制范围及旧操作栏传递当前消息 ID；`useTranscriptMessages.spec.ts`：正式返回结果提升、子图隔离、终态半截回放校准；`auth.spec.ts`：退出清理草稿。
- 原 `chat-refactor.spec.ts`、`showcase-refactor.spec.ts` 更新旧版编辑/抽屉入口定位，保留业务断言；未重新执行的用例不计为本轮通过。

执行命令（Web 工作目录）：

```bash
pnpm exec vitest run src/modules/chat src/stores/auth.spec.ts
pnpm lint
pnpm build
NO_PROXY=127.0.0.1,localhost,::1 pnpm exec playwright test e2e/workbench-restoration.spec.ts --workers=1 --reporter=line
```

隔离三尺寸链路（仓库根目录）：

```bash
NO_PROXY=127.0.0.1,localhost,::1 \
Q5_DATABASE_URI=postgresql://lijiaxin@127.0.0.1:5432/graphharbor_web_refactor_20260910 \
Q5_TEST_FILE=e2e/parallel-chat-refactor.spec.ts \
apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/q5_message_acceptance.py
```

## 状态

`partial`（完整功能核对口径）：旧组件取回及接线完成；37 项定向测试、三尺寸审批/子图与生产构建通过。历史摘要数据和文件/Artifact 等专项交互验收仍按 09 保留待办。

09 是前一时点的差异审查，不是本轮执行结果。恢复旧展示不自动证明其中所有业务能力均已补齐：独立文件写回、完整 Skills/文件 API、PTY 和双浏览器同 Thread 入队保持既定边界；消息旁相邻分支导航已经恢复。会话预览 UI 已恢复，但现有列表只读取 metadata.preview，没有该字段时仍显示空内容提示，不代表历史摘要数据已补齐。

## 最终验证记录

- Chat/auth 定向测试：**37 passed / 1 skipped**；跳过项为需单独运行环境的 SDK 链路测试，不计通过。
- `pnpm lint`、`pnpm build`（含 vue-tsc）：通过；未新增依赖。
- 最新三尺寸混合审批/嵌套子图：**3 passed（2.8m）**；包括 1440/1024/390、每尺寸 20 次 Thread 切换和公开/私有正文隔离。日志：`/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-g2zz14i0`。
- 初轮真实工作台测试因模型输出插入换行导致严格短句断言失败；改为允许空白差异，仍限定 Agent 正文及完整文字。抽屉焦点检查发现打开后焦点未稳定进入；已增加 after-enter 聚焦和焦点落在外部时的 Tab 兜底，修改后 eslint、vue-tsc 再次通过。最终真实回归结果以下一条为准。
- 最终增强真实工作台回归：**1 passed（55.3s）**。覆盖真实 Agent 回复、Max Tokens 确认/取消、草稿刷新、回复重试、只读相邻分支不发 Run、原位编辑后刷新、历史快照、抽屉初始焦点及 Shift+Tab、模型弹层 Escape 焦点返回、1440/390 浅深主题和专注模式。
- 最后一次源码改动是 BaseDrawer 焦点修复：其后 eslint、vue-tsc 与上述真实 E2E 通过；生产构建与三尺寸回归在该修复前通过，不虚报为修复后重跑。

最终截图：[桌面浅色](screenshots/14-workbench-1440-light.png) · [桌面深色](screenshots/14-workbench-1440-dark.png) · [手机浅色](screenshots/14-workbench-390-light.png) · [手机深色](screenshots/14-workbench-390-dark.png)。

截图复验：等待抽屉退出动画结束后再截图，最终用例再次通过（55.3s）；已替换四张最终截图。
