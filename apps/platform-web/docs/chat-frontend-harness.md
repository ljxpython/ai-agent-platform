# Chat 前端验收入口

当前实现：`ChatPage.vue` → `ChatSession.vue` → `useChatSession.ts` / 官方 Vue SDK；动作使用 `run-actions.ts`，正文使用 `Transcript.vue`，审批使用 `ApprovalPanel.vue`。

## 运行方式

正式路由是 `/workspace/projects/{projectId}/chat?agentId={agentId}`；首次 ACK 后替换为 `/workspace/projects/{projectId}/chat/{threadId}`。Agent ID 是平台记录 UUID，不能用 graph_id 代替。

本地服务与测试模型已配置后，在 `apps/platform-web` 执行：

```bash
pnpm exec playwright test e2e/chat-refactor.spec.ts e2e/agent-refactor.spec.ts --workers=1
```

项目根目录使用隔离 API、Worker、平台数据库和测试图运行复杂协议验收：

```bash
Q5_DATABASE_URI="$TEST_DATABASE_URI" Q5_TEST_FILE=e2e/parallel-chat-refactor.spec.ts apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/q5_message_acceptance.py
Q5_DATABASE_URI="$TEST_DATABASE_URI" apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/q5_message_acceptance.py
```

队列及并行协议图使用确定性模型；不能以此替代真实模型与 Showcase 工具副作用验收。真实模型用例必须从配置读取凭据，不输出身份响应、完整请求体或密钥。

## 必须核对

1. 每次使用新测试项目、Thread；服务由本次源码启动。
2. 发送只产生一次 run.start；ACK 清理已发送内容，保留下次草稿。
3. 双轮正文、刷新后的 state、checkpoint 历史和页面一致。
4. 审批按 interrupt ID 映射，编辑参数保留类型；reject 不发生工具副作用。
5. 断开页面只释放订阅；取消由显式 cancel 发起，服务端终态单独核对。
6. 编辑重发使用真实 parent checkpoint；旧分支保留且队列不跨 Run 重放。
7. 移动导航、历史、检查器、焦点、浅深模式及横向溢出均验收。

完整验收范围和结果见 [前端重构项目](../../../docs/projects/20260910-platform-web-refactor/README.md) 与 implementation/11-closeout.md。只有实际通过的场景标记 done；环境阻塞、未执行和用户后置分别记录，不能由脚本存在推断通过。
