# 验收要求与验证计划（verification.md）

## 1. 验收标准

### 1.1 功能验收标准
1. **接口非阻塞**：`POST /api/evaluation/materials/send` 返回状态码 `202 Accepted`，响应时间 $\le 500\text{ms}$，不再发生 30 秒超时；
2. **弹窗秒级关闭**：用户点击转换后，弹窗立即平滑关闭，无转圈等待遮罩，弹出全局轻量 Toast；
3. **后台处理完整性**：所有会话消息快照、工具执行证据提取、PII 脱敏、EvalFlow 工作项创建与大模型用例生成在后台完整完成，数据不丢失、不损坏；
4. **通知触达闭环**：任务处理完成后，顶栏通知中心（🔔）红点亮起并增加未读计数；卡片展示评测集名称，点击可跳转至 EvalFlow 评测集页面；
5. **异常容错性**：若后台处理遭遇异常（如材料含敏感密钥拦截），向用户推送明确的失败原因与排查建议通知，且前端界面零报错。

### 1.2 工程与质量标准
- ✅ `platform-api` 单元测试与契约测试通过；
- ✅ `platform-web` 单元测试通过，`vue-tsc --noEmit` 0 报错；
- ✅ 不破坏原有同步模式兼容性（通过 `async_mode` 参数隔离）；
- ✅ 符合 KISS 与 DRY 架构原则，复用既有 `NotificationService` 基础设施，不引入外部冗余中间件。

---

## 2. 阶段验证（Phase）与整体验收（Final）记录

### 阶段验证记录（Phase）

#### Phase 1: 后端接口非阻塞与后台异步调度（Task 1）
- **验证命令**：`pytest tests/test_evaluation_materials.py -v`
- **执行结果**：15 passed in 1.28s
  - `test_async_mode_returns_202_accepted_and_dispatches_background_task`：PASSED
  - `test_background_task_processes_and_notifies`：PASSED
- **接口耗时证据**：HTTP POST 发起后 0.357s 立即返回 202 Accepted。

#### Phase 2: 通知服务落库与模型解耦（Task 2）
- **验证命令**：端到端轮询 `/api/notifications?limit=10`
- **执行结果**：
  - 后台任务异常捕获分支：正确生成并持久化通知 `评测集【后台异步评测验证集-自动化闭环】转换未完成`；
  - 内容详实指引原因：“未成功采集到所选会话资料：... 材料疑似包含密钥，请在源侧移除后重新转换”。

#### Phase 3: 前端弹窗即时关闭与全局 Toast 联动（Task 3）
- **验证命令**：
  - `pnpm --dir apps/platform-web test:run src/modules/evaluation/components/SendSessionMaterials.spec.ts`
  - `pnpm --dir apps/platform-web exec vue-tsc --noEmit`
- **执行结果**：
  - Vitest：3 passed in 1.95s（包含 `closes dialog immediately on 202 accepted async conversion`）
  - TypeScript 类型检查：0 错误，退出代码 0。

---

### 整体验收记录（Final）

- **验证场景**：通过真实 Chromium 浏览器（`browser-skill`）进入平台对话工作台，从历史会话触发“转为评测集”，验证秒级关闭弹窗、Toast 反馈、后台异步调度、通知生成及 EvalFlow 直达全链路。
- **环境信息**：
  - `platform-api` 运行在 `http://127.0.0.1:2142`（PID 已重载生效）；
  - `platform-web` 运行在 `http://127.0.0.1:3000`；
  - `evalflow` 运行在 `http://127.0.0.1:9128`。
- **验证过程与客观证据**：
  1. **浏览器点击触发**：在会话右上角 `···` 菜单中点击【转为评测集】，打开弹窗填入评测集名称《全链路自动化验证评测集》并勾选授权协议；
  2. **毫秒级弹窗关闭与无感反馈**：点击【转换并查看 AI 建议】后，弹窗在 300ms 内瞬间平滑关闭，主对话工作台完全恢复交互，界面顶层弹出全局轻量 Toast：`“评测集【全链路自动化验证评测集】转换任务已在后台启动，处理完成后将在通知中心提醒您。”`；
  3. **后台平稳异步计算**：后台接管后在毫秒级内返回 `HTTP 202 Accepted`，随后静默拉取会话快照、执行 PII 脱敏审查并向 EvalFlow 推送数据，全过程前端无卡顿、无锁死、零 30s 超时；
  4. **系统通知精准触达**：后台完成后自动向当前用户写入系统通知：
     - 通知 ID：`91e39bb4-8b1b-4096-acdb-fc0855263651`
     - 标题：`评测集【全链路自动化验证评测集】已生成完毕`
     - 直达链接：`http://127.0.0.1:9128/#/authoring/3b312131-81c8-5be1-b6bc-a1f7b5126c43`
  5. **EvalFlow 一键直达**：在浏览器中打开直达链接，成功进入 EvalFlow 评测集工作区（`http://127.0.0.1:9128/#/authoring/...`），完整展示从原会话自动提炼的题目摘要、指标阈值配置、Facts 证据链及 AI 评测 Copilot 面板。
- **留存全景证据与高清录屏**：
  - 🎥 **高清无损录屏视频**：`evaluation-async-conversion.mp4`（1920x976 Clear 画质，完整录制操作全过程）
  - 弹窗提交前：`e2e-modal-before-submit.png`
  - 弹窗秒关后恢复对话：`e2e-dialog-closed.png`
  - 直达 EvalFlow 详情页：`e2e-evalflow-authoring.png`
- **验收结论**：整体验收 100% 通过（Passed），前端 30 秒卡死超时缺陷彻底解决，达成后台异步非阻塞与通知直达完整闭环。
