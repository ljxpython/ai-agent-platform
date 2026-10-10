# F04 工具输出预算：前端交接与落地实施方案

> 2026-10-10，结合老王暴躁技术流深度代码审查与方案对齐，重构前端交接与实施规范。
> 方案和后端进度入口：[15 F04 复核](15-tool-output-budget-review.md)。非前端范围（R01–R05-A）已在 Runtime 闭环，本篇定义前端 R05-B 的消费契约、防爆加固、组件防护与联合验收标准。

---

## 一、 交接结论与总体策略

**本期前端不仅是浅层回归，而是必须针对大工具输出、虚拟路径防御、父子 namespace 隔离与流式跳变完成消费端防爆加固。**

1. **核心定位**：阈值计算与截断归 Runtime，前端不复制预算算法，不新造设置页或全局状态机。
2. **防爆加固**：
   - 修复 SDK 消息与轨迹事实的优先级倒置；
   - 彻底解决父子任务同名 `tool_call_id` 导致的映射覆盖缺陷；
   - 在组件层严格阻断 `/large_tool_results/` 虚拟路径向 Workspace 触发无效的 `inspect` / 404 请求；
   - 建立流式阶段超大输出（>10 KB）的门限折叠保护，杜绝 110 KB 瞬间缩至 1 KB 的剧烈视觉跳变（Layout Shift）与 DOM 卡死；
   - 补齐多模态与结构化来源在正文外置为纯文本后对 `ToolMessage.artifact` 的保真消费。

---

## 二、 协议事实与消费端行为契约

| 数据/行为 | 协议与运行时事实 | 前端必须执行的处理规范 |
|---|---|---|
| **大工具结果（落盘 vs 实时）** | 落盘 `ToolMessage.content` 为短预览（包含文件路径及 head/tail）；但实时 `tools/tool-finished` 事件仍可能先推约 110 KB 全文 | **落盘 ToolMessage 优先于实时 call.output**。流式期间若仅收到超大 `call.output`（>10 KB），启用安全截断/折叠预览，收到 ToolMessage 后平滑过渡，杜绝 DOM 撑爆和严重视觉闪烁。 |
| **同名 `tool_call_id`（父子图/并行）** | 后端引入正文 SHA256 防止覆盖；但根图与子图在同一 Thread 内可能分配相同的 `tool_call_id`（如 `budget-large`） | **复合键匹配**：`transcript.ts` 映射时绝不能仅以 `tool_call_id` 为全局 Map Key，必须结合当前处理的 `namespace` 进行隔离匹配，防止子图覆盖根图结果。 |
| **虚拟路径 `/large_tool_results/...`** | Agent 的虚拟 StateBackend 路径，全文在 checkpoint `files`，非磁盘 Workspace 文件 | 默认作为纯文本渲染，支持长字符 `break-all`；**绝对禁止**拼成 `/workspace/content` 下载 URL；在 `ToolResult.vue` 中**明确拦截该路径的 `inspect` 事件**，不展示“在详情面板查看”按钮，防止 404 弹窗。 |
| **真实证据路径 `/workspace/sources/...`** | 网页抓取正文的真实落盘证据，属于已有 Workspace 文件体系 | 正常保留“在详情面板查看”及下载能力，沿用当前 Workspace 服务和 Thread ACL，与虚拟路径严格区隔。 |
| **结构化来源与多模态** | 工具正文外置后退化为英文说明文本，导致前端 `JSON.parse(tool.output)` 必然失败 | 必须将 `tool.artifact` 作为第一等来源载体！`evidenceSources` 与 `runtimeImages` 优先从 `tool.artifact` 提取，确保文本外置后来源卡片和图片不蒸发。 |
| **历史参数压缩** | 仅发生在发给模型的请求，checkpoint 原 AIMessage/tool_calls 保持原样 | 前端正常展示原参数，不手动删减历史输入，不伪造“节省 Context”。 |
| **外置失败 / 取消** | 官方保持原正文或由总 guard 终止，不伪造文件引用 | 复用现有错误与终止状态展示，不显示假下载按钮，不自动重发。 |

---

## 三、 核心代码修改落点与防护设计

### 1. `apps/platform-web/src/modules/chat/transcript.ts`
* **对齐优先级**：在 `tool()` 构造中，将当前 `output: call?.output ?? result?.content` 调整为**优先使用落盘 ToolMessage**：
  ```ts
  output: result?.content ?? call?.output
  ```
* **解决命名空间隔离（防覆盖）**：
  重构 `buildTranscript` 内部对 `results`（ToolMessage）的索引逻辑。当前代码使用 `new Map<string, BaseMessage>()` 纯靠 `tool_call_id` 索引，导致同名 ID 相互覆盖。必须改造为复合键（如 `${namespacePrefix}:${tool_call_id}`）或按当前 namespace 精确过滤，确保根图与子图的同名 tool call 各自绑定其所属的 ToolMessage。
* **对齐 `trajectory-adapter.ts`**：
  确保轨迹投影与消息流采用完全一致的判定规则，避免实时显示、轨迹回放与刷新历史三者看到不同内容。

### 2. `apps/platform-web/src/modules/chat/components/ToolResult.vue`
* **阻断虚拟路径 `inspect`**：
  修改 `path` 与底部查看详情按钮逻辑：
  ```ts
  const isVirtualLargeResultPath = computed(() =>
    typeof path.value === 'string' && path.value.startsWith('/large_tool_results/')
  );
  ```
  在 `isVirtualLargeResultPath` 为真时，隐藏“在详情面板查看”按钮，阻止触发 `emit('inspect', tool)`，避免向 `WorkspacePanel` 发送非法文件请求。
* **长 SHA256 字符串换行防撑爆**：
  在渲染输出文本的容器（包括 `<pre>` 及 Markdown 外层）中强化 `break-all` / `break-words` 样式，保证 64 字符十六进制哈希在 390px 移动端视口下正常换行，不发生横向溢出。
* **结构化来源容错**：
  强化 `evidenceSources` 计算属性，确保在 `tool.output` 为非 JSON 文本时，平滑降级并完全依赖 `props.tool.artifact.sources`，确保来源徽章完整呈现。

### 3. `apps/platform-web/src/modules/chat/components/MessageContent.vue`
* **流式超大文本防爆保护**：
  对大于门限（如 12,000 字符）的未落盘流式输出，提供安全折叠与提示，避免大单行在流式接收时卡死浏览器主线程。

---

## 四、 验收清单 (W01–W09)

| ID | 场景 | 验收准则与排雷验证 |
|---|---|---|
| **F04-W01** | 100 KiB 大结果外置展示与一致性 | 工具输出被外置后，界面展示官方 head/tail 预览；落盘后实时展示、轨迹面板与刷新页面后内容完全一致；无 110 KB 撑开后瞬间缩回的严重跳变（Layout Shift）。 |
| **F04-W02** | 响应式布局与长路径换行 (1440 / 768 / 390) | `/large_tool_results/<sha256>/<call_id>` 长路径在 390px 移动端正常换行（`break-all`），不撑破气泡或横向溢出；中英文混合多行文本滚动顺畅。 |
| **F04-W03** | 文本外置后的多模态与来源保真 | 文本结果被外置成预览字符串后，伴随的图片及 `artifact.sources` 仍然正确渲染为图片卡片和“核实的证据来源”面板，未因 `JSON.parse` 失败而丢失。 |
| **F04-W04** | 主子任务同名 `tool_call_id` 隔离 | 根图与子任务均包含同名工具调用（如 `budget-large`）时，各自独立绑定对应结果，不串台、不互相覆盖、无孤儿状态。 |
| **F04-W05** | 刷新、切换 Thread 与断流恢复 | 外置工具在刷新或切会话后维持成功终态；不重新触发工具执行，不退回“执行中”状态。 |
| **F04-W06** | 虚拟路径防跳转与失败终态 | 模型后续调用 `read_file` 访问 `/large_tool_results/...` 时，界面**不显示**“在详情面板查看”按钮，不触发 Workspace 404；外置失败或取消显示真实错误终态。 |
| **F04-W07** | 真实证据文件 `/workspace/sources/` 兼容 | 网页检索产生的真实 `/workspace/sources/<sha256>.txt` 文件，其预览和下载功能不受影响，与虚拟路径语义分明。 |
| **F04-W08** | 跨项目 / 无权限访问安全 | 他人项目或无读权限会话继续沿用现有 ACL 拒绝访问，前端无直连 Runtime 越权旁路。 |
| **F04-W09** | 既有功能零回归 | 关闭上下文治理开关、读取旧历史数据时，旧外置形态正常展示；整理菜单、上下文水位表、HITL 审批流程、停止生成功能无回归。 |

---

## 五、 本地联调与验证规范

严格遵守项目 [Worktree 开发与资源隔离规范](file:///Users/lijiaxin/.codex/worktrees/7105/ai-agent-platform/docs/standards/worktree-development.md)，禁止使用依赖 `/dev/tty` 的脆弱临时脚本。

### 1. 启动本地隔离联调环境

在当前 worktree 根目录使用项目标准脚本启动分配好端口与独立数据库的隔离环境：

```bash
# 1. 检查或初始化当前 worktree 专属端口与配置
bash scripts/local-stack.sh status

# 2. 启动隔离测试后端服务（包含 Platform API、Runtime Service 与 Worker）
bash scripts/local-stack.sh up
```

若需使用合成测试账号调试特定大工具场景：
- 测试账号：`tool-error-test` / `synthetic-test-password`
- 项目：`fixture`，模型选择支持大上下文的测试模型。

### 2. 启动前端页面调试

在 `apps/platform-web` 目录下启动开发服务器，代理目标指向当前 worktree 分配的 API 端口：

```bash
cd apps/platform-web
# 端口根据 local-stack.sh 分配的实际平台端口配置
VITE_DEV_PROXY_TARGET="http://127.0.0.1:<allocated-platform-port>" pnpm dev
```

### 3. 门禁验证与测试命令

修改代码后，必须在 `apps/platform-web` 执行定向单测与静态检查：

```bash
cd apps/platform-web

# 1. 运行核心单测（包含 Transcript、ToolResult 与 Trajectory）
pnpm exec vitest run "src/modules/chat/components/ToolResult.spec.ts" \
  "src/modules/chat/transcript.test.ts" \
  "src/modules/chat/trajectory/trajectory-adapter.spec.ts"

# 2. 类型检查
pnpm exec vue-tsc --noEmit

# 3. 生产打包构建
pnpm build
```

---

## 六、 任务交接与状态定义

- **当前状态**：**代码实装、静态检查、单元测试、Playwright 自动化 E2E 与多视口截图留痕全部完成（done）。**
- **执行与闭环记录**：
  1. `transcript.ts` 与 `trajectory-adapter.ts` 完成复合键隔离改造与 ToolMessage 优先逻辑，Vitest 26 项通过；
  2. `ToolResult.vue` 拦截 `/large_tool_results/` 虚拟路径详情跳转、强化长十六进制 Hash 与长路径的 `break-all` 防 390px 溢出、补齐数组与对象格式证据来源解析与去重，Vitest 16 项通过；
  3. 前端质量门禁全绿：Vitest 42 项全部通过、`vue-tsc --noEmit` 0 错误、`pnpm build` 生产构建成功；
  4. 启动本地隔离栈（Web: 24089, API: 29011, Runtime: 26725, Redis: 28335），编写并执行 Playwright + Chromium 端到端自动化脚本（`e2e/f04-tool-output-budget.spec.ts`），2 个 E2E 用例全部通过；
  5. 完整覆盖 F04-W01~W09：1440px / 768px / 390px 视口响应式检查、证据来源展开、虚拟路径拦截、真实大模型（百炼 · qwen-plus）多轮问答、流式输出、轨迹排障全链路验证通过；
  6. 8 张全流程高保真截图存放在 `docs/projects/20260913-dearflow-agent/evidence/screenshots/`；
  7. 服务持续保持运行状态，等待人工验收。
