# Showcase Demo 渲染能力矩阵评估与逐项触发指南

本文档对照 `/Users/lijiaxin/PyCharmMiscProject/research/open-swe/docs/frontend-rendering-matrix.md` 中定义的 **13 项核心前端渲染能力**，对当前 `platform-web` 结合 `showcase_demo` 真实执行环境的落地现状进行了全面技术对齐，并提供**可逐项动手触发的测试提示词与操作指引**。

---

## 1. 核心渲染能力矩阵对照审计 (Matrix Audit)

| # | 能力要求 | 矩阵评级 | 落地状态 | 前端组件 / 源码位置 | 机制与现状说明 |
|---|---|:---:|:---:|---|---|
| **1** | **工具调用可视化** | 必备 | ✅ **完全搞定** | `ToolResult.vue`<br>`transcript.ts` | 状态机（执行中/已返回/失败/未完成）、参数多态展开、结果渲染；支持在侧边抽屉中 Inspect 查看。 |
| **2** | **HITL: Approve / Reject** | 必备 | ✅ **完全搞定** | `ApprovalPanel.vue`<br>`ChatSession.vue` | 侦测 `stream.interrupts`，主输入框自动锁死（`canSend=false`），浮出审批卡片，支持批准或附带拒绝理由驳回。通过 `stream.respondAll` 发起 Resume。 |
| **3** | **HITL: Edit 决策** | 必备 | ✅ **完全搞定** | `ApprovalPanel.vue` | 审批选项支持“修改参数”，提供 JSON 参数在线修改，前端实时比对并计算 `editedFields` 提示已变更字段。 |
| **4** | **多 Interrupt 并发** | 必备 | ✅ **完全搞定** | `approvals.ts`<br>`useChatSession.ts` | 支持单次/多次 interrupt 携带多个 `action_requests` 统一管理与映射；支持执行态消息排队（`queueMessage`）。 |
| **5** | **子智能体 + Todo List** | 必备 | ✅ **完全搞定** | `ChatSession.vue`<br>`ChatContextDrawer.vue` | 1. **子智能体**：消费 `stream.subagents` 动态渲染层级树形子任务卡片；<br>2. **Todo List**：联动 `values.todos`，在抽屉 `tasks` 标签页分组展示待办/进行中/已完成。 |
| **6** | **子智能体流式 Token** | 必备 (巨坑) | ✅ **完全搞定** | `SubtaskDetail.vue`<br>`Transcript.vue` | 接收子智能体 `namespace`，使用 `useTranscriptMessages(stream, namespace)` 单独隔离流式消息与工具调用。 |
| **7** | **Sandbox 文件系统模拟** | 高阶 | 🟡 **已实现面板** | `ChatContextDrawer.vue` (`files` tab) | 列出沙箱文件、行数与完整度标识，支持查看与在线编辑回写 Checkpoint；联动 `read_file` 抓取文件。 |
| **8** | **Skills (技能) 读取** | 辅助 | 🟡 **轻量实现** | `ChatSession.vue`<br>`ToolResult.vue` | 自动识别 `/skills/**` 路径并标记“已读取技能”，可在详情面板中查看；未设独立常驻 Tab。 |
| **9** | **推理 Token 流式渲染** | 必备 | ✅ **完全搞定** | `transcript.ts`<br>`MessageContent.vue` | 提取 `<think>` 标签及 `reasoning_content`，独立折叠框展示、思考耗时计时、动态光标、正文干净流出。 |
| **10** | **富文本 Markdown 流式** | 必备 | ✅ **完全搞定** | `MessageContent.vue` | `markdown-it` 渐进式拼装，流式输出时光标带脉冲动画，视口自动平滑下移。 |
| **11** | **代码变更面板 (Diff)** | 必备 | 🟡 **轻量卡片版** | `ToolResult.vue` | 识别 `edit_file` 工具时自动渲染红绿两栏（`old_string` 红底 vs `new_string` 绿底）对比；尚未集成 Monaco Diff 编辑器。 |
| **12** | **构件独立挂载 (Artifacts)** | 高阶 | 🟡 **骨架已挂载** | `ChatArtifactPanel.vue` | 右侧挂载独立分栏，响应 `stream.values.ui`，呈现结构化元数据与 Raw Payload；暂未做富交互组件。 |
| **13** | **沙箱终端实时回显** | 高阶 | ❌ **静态呈现** | `ToolResult.vue` | **受限后端架构**：`showcase_demo` 是 Docker 容器批处理执行命令后统一返回退出码与输出，未建 WebSocket PTY 长连接。前端采用深色终端框展示命令与退出码。 |

---

## 2. 前置环境与准备工作

在开始触发测试前，请确保本地后端与前端均已就位：

### 2.1 依赖环境检查
```bash
# 1. 确保已拉取 Docker 执行镜像（用于 showcase_demo 沙箱代码执行）
docker pull python:3.13-slim

# 2. 检查并启动后端服务（需挂载 showcase_demo）
# 工作目录: apps/runtime-service
uv run graphharbor serve --config langgraph.demo.json --host 127.0.0.1 --port 8123
```

### 2.2 前端进入对应会话
1. 打开浏览器进入平台前端工作台（`platform-web`）；
2. 智能体 / Graph 选择切换为：`showcase_demo`；
3. 新建一个空白会话（New Thread）。此时工作区会自动初始化预置的样例项目：
   - `/workspace/sales.csv`（销售原始数据）
   - `/workspace/report.py`（存在计算缺陷的报表脚本）
   - `/workspace/README.md`

---

## 3. 效果逐项触发指引 (Step-by-Step Trigger Guide)

按以下顺序依次输入 Prompt，即可逐个观察并验证对应效果：

---

### 🧪 触发项 1：Skills 读取与富文本流式打字机 (能力 8, 10)
- **目标效果**：
  Agent 首次唤起时自动读取内置的 `/skills/showcase-notes/SKILL.md`，正文 Markdown 逐字打字机流式输出，末尾带有脉冲光标。
- **触发 Prompt**：
  > “你好，请简要介绍一下你所了解的当前工作区环境以及你的职责。”
- **预期前端交互**：
  1. 上方出现 `工作过程 · 1 项` 折叠面板，展开后显示工具调用 `read_file`，路径为 `/skills/showcase-notes/SKILL.md`，状态流转为“已返回”；
  2. 点击该工具卡片下方的“在详情面板查看”，右侧抽屉弹开，标题为“已读取技能”，展示该 Skill 的内容；
  3. 下方回复文本实时逐字吐出，排版整洁，光标呼吸跳动。

---

### 🧪 触发项 2：思考过程实时呈现 (能力 9)
- **目标效果**：
  模型在思考阶段产生的内容被单独剥离到“思考过程”独立卡片中，并显示“已思考 X 秒”，正文保持干净。
- **触发条件**：
  在工作台右上角或参数弹窗中，切换模型为支持思考推理的模型（如 DeepSeek-R1、o1/o3-mini 或带 reasoning 的模型）。
- **触发 Prompt**：
  > “请深入思考并分析：在统计加权数据时，如果遗漏了数量维度，数学上会导致什么本质上的偏差？”
- **预期前端交互**：
  1. 回复上方首先出现一个灰色半透明的折叠框：“思考过程”；
  2. 思考文本流式逐字打出，右上角计时器动态递增（如 `已思考 3 秒`）；
  3. 思考完毕后折叠框可手动收起/展开，正文从下方开始正常流出。

---

### 🧪 触发项 3：只读分析与子智能体（Research Subagent）委派 (能力 1, 5, 6)
- **目标效果**：
  主 Agent 不直接读全部文件，而是通过 `task` 工具委派 `research` 子智能体；前端渲染出子智能体卡片，并独立展示其命名空间下的流式过程。
- **触发 Prompt**：
  > “请只分析销售报表 report.py 为什么算错，只读检查实际文件，给出原因和修复建议。不要修改文件，也不要运行代码。”
- **预期前端交互**：
  1. 主聊天流中出现一个子任务卡片：`research`（只读分析实际项目）；
  2. 卡片右侧显示状态（`执行中` -> `已返回`）；
  3. 展开该卡片，内部通过 `SubtaskDetail` 渲染子任务的执行过程（子 Agent 独立调用了 `read_file` 读取 `/workspace/report.py` 和 `/workspace/sales.csv`）；
  4. 主 Agent 最终回复指出问题：原代码计算总金额时只累加了单价，没有乘以数量（导致算出来是 27.00，而正确应该是 43.50）。

---

### 🧪 触发项 4：沙箱文件系统联动与在线查看（Files Tab）(能力 7)
- **目标效果**：
  Agent 在沙箱中探索过或存在于状态中的文件，实时同步到侧边抽屉的“Files”面板中。
- **操作步骤**：
  1. 点击工作台顶部工具栏或右侧抽屉按钮，打开上下文抽屉；
  2. 切换到 **Files** 标签页。
- **预期前端交互**：
  1. 左侧文件列表展示 `/workspace/report.py`、`/workspace/sales.csv`、`/workspace/README.md` 以及已读取的 Skill；
  2. 点击 `report.py`，右侧展示其完整代码与行数统计；
  3. 支持点击“编辑”，在输入框中修改内容并点击“保存并回写状态”。

---

### 🧪 触发项 5：TodoList 任务计划与实时同步（Tasks Tab）(能力 5)
- **目标效果**：
  Agent 遇到多步骤复杂任务时，调用 `write_todos`，抽屉中的 ToDo 列表实时更新。
- **触发 Prompt**：
  > “请为修复 report.py 并进行真实验证制定一份详细的执行计划，先列出清晰的待办事项。”
- **预期前端交互**：
  1. Agent 执行工具 `write_todos`，在聊天流中以专属卡片呈现：
     - 标题人文化为“更新任务清单 · 共 N 项”；
     - 展开可直观查看结构化待办列表（蓝色进行中圆点、灰色待办圆点）；
     - 卡片底部附带“在详情面板查看任务看板 →”快捷按钮；
  2. 点击快捷按钮或手动打开上下文抽屉切换到 **ToDo** 标签页；
  3. 可以看到任务被清晰拆解并分组展示：
     - `进行中` (In Progress)
     - `待处理` (Pending)
     - `已完成` (Completed)
  4. 标签页右上角有未完成数量角标。

---

### 🧪 触发项 6：人机回环审批（HITL Approve / Reject）(能力 2, 4)
- **目标效果**：
  Agent 准备写文件或跑 Docker 命令时被安全拦截；主输入框锁死；界面弹出审批面板。
- **触发 Prompt**：
  > “请开始修复 report.py 中的数量乘积错误，并运行代码验证结果。”
- **预期前端交互**：
  1. Agent 委派 `general-purpose` 执行助手，准备调用 `edit_file` 或 `write_file`；
  2. **输入框状态变动**：底部主输入框被禁用，提示“等待审批”；
  3. 页面出现橙黄色边框的审批面板（`ApprovalPanel`）：
     - 标题：“需要你的确认 · 1 项请求”；
     - 显示工具名：`edit_file` 或 `write_file`；
     - 显示拟修改的文件路径与内容；
  4. **测试拒绝（Reject）**：
     - 处理方式选“拒绝”；
     - 输入拒绝原因：“先不要直接改，我需要你先备份原文件”；
     - 点击“提交所选决策”；
     - 观察 Agent 收到驳回后停止修改，并回复确认已取消。

---

### 🧪 触发项 7：人机回环编辑决策（HITL Edit）与代码 Diff (能力 3, 11)
- **目标效果**：
  在人机审批时，用户人工修改 Agent 给出的入参，并提交修改后的版本；同时观察代码 Diff 卡片。
- **触发 Prompt**：
  > “现在请再次准备修改 report.py，将错误的统计逻辑修复。”
- **预期前端交互**：
  1. 审批面板再次弹出，针对 `edit_file` 工具；
  2. 处理方式选择 **“修改参数” (edit)**；
  3. 下方出现可编辑的 JSON 文本域；
  4. 在文本域中微调参数（例如添加一行注释或调整变量名），下方实时计算并显示：`变更字段：args`；
  5. 点击“批准”或“提交所选决策”；
  6. 执行后展开工作过程中的 `edit_file` 卡片，可以看到**红绿双栏代码对比**（红色为 `old_string`，绿色为 `new_string`）。

---

### 🧪 触发项 8：Docker 沙箱命令执行与终端结果回显 (能力 13)
- **目标效果**：
  Agent 调用 `execute` 在真实 Docker 容器中执行 Python 脚本，审批后回显黑底控制台与退出码。
- **触发 Prompt**：
  > “现在请使用 execute 运行 python /workspace/report.py，验证修复后的计算输出。”
- **预期前端交互**：
  1. 触发 `execute` 审批，显示待执行命令：`python /workspace/report.py`；
  2. 点击“批准”并提交；
  3. Docker 容器在沙箱内运行（约 1-3 秒）；
  4. 工具执行完成，卡片中展示：
     - 黑色终端背景框：`python /workspace/report.py`；
     - 运行状态：`退出码 0`；
     - 返回结果中展示报表执行打印的真实内容（如 `Total sales: 43.50`）。

---

### 🧪 触发项 9：外部文档抓取工具 (能力 1)
- **目标效果**：
  Agent 调用定制业务工具 `fetch_documentation`，安全抓取官方技术文档。
- **触发 Prompt**：
  > “请查阅 Python Decimal 的官方文档，向我解释金额计算为什么应该使用 Decimal 而不是 float。”
- **预期前端交互**：
  1. Agent 调用 `fetch_documentation` 工具，入参包含官方文档 URL；
  2. 工具返回清洗后的文档 Markdown 片段；
  3. Agent 基于抓取到的内容给出专业严谨的回答。

---

### 🧪 触发项 10：多轮历史分支与回退 (Branching & Fork)
- **目标效果**：
  在任一已发生的用户消息上直接编辑，派生历史分支，不影响原分支上下文。
- **操作步骤**：
  1. 鼠标悬停在上方之前发过的某条用户消息上；
  2. 点击出现的 **“编辑并创建分支”** 按钮；
  3. 在弹出的对话框中修改提示词并发送；
- **预期前端交互**：
  1. 页面重新从该检查点派生新分支执行；
  2. 抽屉的 **历史 (History)** 标签页中可以看到版本分叉，支持自由切换回原分支。

---

## 4. 常见问题排查速查 (Troubleshooting)

| 异常现象 | 排查切入点 |
|---|---|
| 发送后 Agent 没反应或报连接失败 | 检查 `runtime-service` 是否已启动，检查 8123 端口是否被防火墙阻断。 |
| 执行代码时报 Docker 错误 | 检查宿主机 Docker Desktop / dockerd 是否启动，检查是否已执行 `docker pull python:3.13-slim`。 |
| 工具调用卡片不出现 | 检查 `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts` 是否放行了子图 tool 事件。 |
| 审批卡片没弹出来，但输入框被锁死 | 查看浏览器控制台是否有报错；检查 `ChatSession.vue` 中 `reviews` 计算属性与 `ApprovalPanel.vue` 是否正常挂载。 |
| 思考过程折叠框没有出现 | 当前调用的模型服务是否支持 Reasoning 输出，或者返回数据中是否包含 `<think>` 标签。 |

---
*文档归档路径：`docs/projects/20260912-chat-streaming-standardization/showcase-matrix-trigger-guide.md`*
