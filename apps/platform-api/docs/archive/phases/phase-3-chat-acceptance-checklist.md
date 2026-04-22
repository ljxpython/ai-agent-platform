# Phase 3 Chat 前端验收清单

这份清单只服务一件事：

> 让你可以对 `apps/platform-web-vue` 的 `chat` 页面做逐条验收，而不是靠感觉判断“好像能用”。

## 1. 验收前置条件

以下条件必须全部满足：

- [ ] `apps/runtime-service` 已启动 LangGraph upstream，端口 `8123`
- [ ] `apps/platform-api` 已启动，端口 `2024`
- [ ] `apps/platform-api-v2` 已启动，端口 `2142`
- [ ] `apps/platform-web-vue` 已启动，端口 `3000`
- [ ] `apps/platform-web-vue/.env.local` 已配置：

```bash
VITE_PLATFORM_API_URL=http://localhost:2024
VITE_PLATFORM_API_V2_URL=http://localhost:2142
VITE_PLATFORM_API_V2_RUNTIME_ENABLED=true
```

- [ ] 使用管理员账号登录：`admin / admin123456`
- [ ] 或使用普通账号登录：`test / test123456`
- [ ] 当前账号至少能访问一个项目

## 2. 启动命令清单

推荐直接在仓库根目录执行：

```bash
bash "./scripts/platform-web-vue-demo-up.sh"
```

然后检查：

```bash
bash "./scripts/platform-web-vue-demo-health.sh"
```

如果你需要逐个服务排查，再按下面的分步命令手动启动。

### 2.1 runtime-service

```bash
cd apps/runtime-service
uv run langgraph dev --config runtime_service/langgraph.json --port 8123 --no-browser
```

补充说明：

- [x] 已回归验证 `research_demo` 在线程 `state/history` 场景下可在这条默认命令上正常工作
- [x] 本轮已修复 `FilesystemBackend(root_dir=...).resolve()` 在 graph 工厂内触发的同步阻塞问题
- [x] 现在线程详情、历史恢复不再依赖 `--allow-blocking`

### 2.2 legacy platform-api

```bash
cd apps/platform-api
uv run uvicorn main:app --host 0.0.0.0 --port 2024 --reload
```

### 2.3 platform-api-v2

```bash
cd apps/platform-api-v2
uv run uvicorn main:app --host 127.0.0.1 --port 2142 --reload
```

### 2.4 platform-web-vue

```bash
pnpm --dir apps/platform-web-vue dev
```

## 3. 页面进入与引导验收

- [ ] 打开 `/workspace/chat` 时，如果当前项目从未选择过 `assistant / graph`，页面显示引导页而不是空白页或报错页
- [ ] 引导页文案明确提示用户去 `Assistants` 或 `Graphs` 选择目标
- [ ] 当前未选择项目时，页面显示“请先选择项目”，而不是直接报接口错误
- [ ] 从 `Assistants` 页面进入 chat 后，页面直接落到真正对话界面
- [ ] 从 `Graphs` 页面进入 chat 后，页面直接落到真正对话界面
- [ ] 从 `Threads` 页面打开某个 thread 后，页面直接落到对应 thread

通过标准：

- 首次打开有引导
- 有目标后不再重复引导
- 路由跳转后目标解析正确

## 4. 最近目标记忆验收

- [ ] 在当前项目中先选择一个 assistant 进入 chat
- [ ] 刷新页面或重新打开 `/workspace/chat`
- [ ] 页面不再回到引导页，而是直接恢复最近一次聊天目标
- [ ] 切换到另一个项目后，不会错误复用上一个项目的最近目标
- [ ] 手动点击“重置目标”后，再打开 chat 会重新回到引导页

通过标准：

- 最近目标是“按项目隔离”的
- 目标恢复正确
- 清除目标后行为可预期

## 5. 发消息与自动建线程验收

- [ ] 进入对话界面后，在输入框输入一条普通文本消息
- [ ] 点击发送后，如果当前没有 thread，系统会自动创建 thread
- [ ] 发送后左侧或历史区能看到新 thread
- [ ] 新 thread 的标题不是空白，也不是异常 ID 占位
- [ ] 首条消息和助手回复都能正常出现在消息流里

通过标准：

- 不需要手动建 thread
- 发消息即自动进入真实对话链路
- thread 与消息沉淀正常

## 6. 流式输出与运行状态验收

- [ ] 发送消息后，助手回复是逐步流式输出，不是一直卡住后一次性吐完
- [ ] 运行中发送按钮会切换成取消按钮
- [ ] 运行中页面不会整体锁死到无法查看历史
- [ ] 如果回复较长，消息区行为基本稳定，不出现整页白屏或崩溃
- [ ] 回复完成后，运行态恢复正常，输入框回到可输入状态

通过标准：

- 用户可以感知到运行中状态
- 回复完成后 UI 状态归位
- 没有卡死、白屏、整块失控

## 7. 中断 / 取消验收

- [ ] 在助手持续输出时点击取消
- [ ] 当前运行被中断，不再继续追加输出
- [ ] 页面不会因为取消而直接崩掉
- [ ] 取消后输入框重新可用，可以继续发下一条消息
- [ ] 如果 thread 状态里存在 interrupt，页面展示是可理解的，不是空白块

通过标准：

- 取消动作真实生效
- 取消后工作区仍可继续使用
- 中断态不会把页面搞坏

## 8. thread 历史与恢复验收

- [ ] 先完成至少两轮对话
- [ ] 切换到别的页面后，再回到 `/workspace/chat`
- [ ] 原 thread 历史能够重新加载出来
- [ ] 通过 `Threads` 页面点击某个 thread 进入 chat 时，能看到对应历史而不是新会话
- [ ] 历史消息顺序正确，没有明显重复或错位

通过标准：

- thread 和 history 可恢复
- `Threads -> Chat` 跳转链路正常
- 历史消息顺序基本正确

## 9. 运行参数与上下文验收

- [ ] 打开“运行上下文与参数”弹窗
- [ ] 能看到当前可选模型列表
- [ ] 能看到当前可选工具列表
- [ ] 修改模型、工具或参数后，可以正常发起下一轮消息
- [ ] 关闭弹窗后主对话界面状态正常，不出现遮罩残留或滚动异常

通过标准：

- 参数入口可发现、可打开、可关闭
- 参数变更后不会把对话链路打坏

## 10. 错误态验收

- [ ] 在未登录或登录态失效时访问 chat，会被正确重定向或给出明确提示
- [ ] 当前项目无权限时，页面显示明确的无权限态，而不是只有一条模糊报错
- [ ] `state/history` 局部失败时，页面仍保留 thread 基础信息，并给出局部 warning
- [ ] 后端报错时，不会直接渲染成浏览器原始异常对象

通过标准：

- 错误可理解
- 页面尽量降级，不是一炸全炸

## 11. 本轮不作为失败项的内容

以下内容如果还没做到，不算这轮 chat 核心链路验收失败：

- operations 正式治理页
- policy overlay 配置页
- platform config 正式治理页
- operation 通知中心
- 多 worker 并发与重试策略

这些属于后续 phase-3 其他条目，不属于 chat 本体是否可用的最低验收口径。

## 12. 验收结论模板

你手动验收后可以直接按这个格式记：

- 页面进入与引导：通过 / 不通过
- 最近目标记忆：通过 / 不通过
- 发消息与自动建线程：通过 / 不通过
- 流式输出与运行状态：通过 / 不通过
- 中断 / 取消：通过 / 不通过
- thread 历史与恢复：通过 / 不通过
- 运行参数与上下文：通过 / 不通过
- 错误态：通过 / 不通过

最终结论：

- [ ] Chat 页面达到“可演示、可继续开发”标准
- [ ] Chat 页面达到“可汇报”标准
- [ ] Chat 页面仍需继续修复问题后再验收

## 13. 本轮已完成回归

- [x] `platform-api-v2 /api/langgraph/threads/:id/state` 返回 `200`
- [x] `platform-api-v2 /api/langgraph/threads/:id/history` 返回 `200`
- [x] `research_demo` 的 thread 历史恢复不再触发 `BlockingError: os.readlink`
- [x] `Chat` 页面可加载历史消息与输入区，之前的“状态和历史刷新失败”告警已消失
- [x] `新对话` 按钮改为进入空白草稿态，不再点击一下就创建空 thread
- [x] 空白草稿态发送首条消息时，系统会自动创建新的 thread 并写回路由
- [x] 用户主动取消运行后，页面展示明确的 info 提示，不再把 `CancelledError()` 当作失败横幅抬出来
- [x] 取消运行后输入框保持可编辑，当前草稿会保留，能够继续发送下一条消息
- [x] `Threads -> Open in Chat` 跳转链路已回归验证，能够带着正确的 `threadId / target` 进入 Chat
- [x] “运行参数”弹窗确认后，后续消息可继续正常发送，不会把会话链路打断
