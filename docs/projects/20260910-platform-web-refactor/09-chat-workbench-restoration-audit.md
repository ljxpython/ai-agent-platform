# Chat 工作台还原：功能差异与补齐清单

## 结论与核对范围

核对日期：2026-09-11。用户确认的目标是**重构前最后一版、包含高级模型选择器的完整聊天工作台**；保留本轮 SDK、权限、审批、队列和分支执行逻辑。

**本轮直接取回 Git `8056869` 的旧展示组件，并接入当前执行逻辑。** 下表更新为实际恢复情况；历史摘要数据和未重新验收的链路仍明确标注 `partial`。此前测试仅代表各自记录的范围。实施与证据见 [14](implementation/14-copy-original-chat-components.md)。

本清单直接比较 Git `8056869` 的源码和当前工作区，并结合本轮实际测试。旧组件存在仅证明旧版提供过该入口，不代表其旧后端链路一定正确。以下不把“新代码没有恢复”和“实测运行报错”混为一谈。

证据标记：**源码**＝已核对实现；**实测**＝本轮已运行；**待验**＝尚无本轮完整通过证据。四态：`done` / `partial` / `blocked` / `deferred`；`partial` 包括未实现和未验收，具体见每行说明。

## 1. 已发现的运行故障及修复情况

| 问题 | 根因、当前处理 | 状态与证据 |
| --- | --- | --- |
| 本地新库聊天无可用模型 | 录入 7 个模型并启用当前 `test` 项目策略，默认 DeepSeek-V4-Flash | `done`：正式 API 录入；默认模型真实推理成功。其余 6 个未逐个做推理验收 |
| Reference Agent 调用模型失败 | 仍读旧 `_runtime_model_ref`；改为当前 `runtime_model_ref` 并复用 `fetch_model_connection` | `done`：11 项 reference 测试通过，本地 Reference Agent 实际回复成功 |
| Reference Agent 默认工具被拒绝 | 本地工具 catalog 未初始化；通过正式刷新接口同步 11 个工具 | `done`：本地 Reference Agent 链路通过；保留显式禁用策略 |
| 消息回执查询 500 | 本地 Runtime 缺少业务 inbox 表；已执行幂等初始化，启动迁移脚本加入业务迁移命令 | `partial`：本地初始化已执行；新增脚本完整 `migrate/start` 路径待复验，不以 `bash -n` 代替迁移验收 |
| 错误信息显示 `[object Object]` | SDK 将结构化错误直接转成 Error；页面已加友好回退文案 | `partial`：页面避免直接展示对象字符串；尚未完整恢复错误码、业务原因的可读展示 |
| 三尺寸并行 Chat 回归定位失败 | 按恢复后的按钮可访问名称、详情抽屉更新定位，保留正文与审批断言 | `done`：最新 1440/1024/390 全部通过（3 passed）；每个场景含 20 次 Thread 切换 |

本地真实浏览器已分别在 Reference Agent、Workflow Demo 得到“本地模型连接正常。”，两条 Thread 刷新后仍能看到回复。因此本次“无回复”已在上述场景修复；这不等于所有 Agent、全部模型均已验证。

## 2. 旧版功能没有完整还原的部分

优先级：P0 阻断正常使用；P1 完整工作台必须补齐；P2 视觉与反馈细节。下列未勾选项是工作清单，不因主链路测试通过自动完成。

| 编号 | 旧版能力 | 当前源码与用户影响 | 补齐内容 / 验收标准 | 优先级 / 配合端 |
| --- | --- | --- | --- | --- |
| R01 | 日期分组、消息预览 | `partial`：旧分组和预览区域已恢复；metadata.preview 缺失仍显示空内容 | 后续补合法摘要数据；不逐条请求整段历史 | P1 / Web |
| R02 | 逐条删除、分页、无匹配提示 | `partial`：旧组件已接回，沿用服务端分批加载及确认；实际删除失败场景待专门验收 | 删除当前/非当前会话、失败保留条目 | P1 / Web |
| R03 | Max Tokens、确认/取消/还原 | `done`：旧参数草稿接入当前 context；真实 Run 使用 1024，取消的 2048 未提交 | 参数合法性、确认/取消已实测 | P1 / Web |
| R04 | 消息级重试 | `done`：回答前 checkpoint 无 input 重新执行，保留用户消息 ID | 真实重试产生可导航分支 | P1 / Web |
| R05 | 前后分支、序号 | `done`：取回旧 branching 算法并适配路由节点 checkpoint | 实测只读导航不发 Run，返回最新 | P1 / Web |
| R06 | 消息复制、原位编辑 | `partial`：旧操作栏、回答单独复制、原位编辑已恢复并测试；含附件编辑未重验 | 保留附件约束验证待办 | P1 / Web |
| R07 | 隔离文字草稿 | `done`：按用户/项目/Agent/Thread 存储；退出清理 | 刷新恢复实测、退出清理单测通过；不持久化附件对象 | P1 / Web |
| R08 | 统一详情抽屉四区 | `done`：旧概览/ToDo/Files/历史及真实状态接回 | 最终真实回归抽屉焦点、历史/Files 标签与手机操作通过 | P1 / Web |
| R09 | 公开文件复制/下载 | `partial`：旧查看、复制、下载代码已接回；完整文件操作待实测 | 真实写回 `deferred`，没有假保存入口 | P1 / Web |
| R10 | 独立 state.ui 面板 | `partial`：原组件逐字取回，接公开 ui；非空 Artifact 浏览待定向实测 | 安全 JSON 展示，不执行任意 HTML | P1 / Web |
| R11 | 历史时间线与快照 | `done`：旧时间线、摘要与快照接回 | 展示转换单测、真实只读快照与返回最新已通过 | P1 / Web |
| R12 | 跟随暂停与未读提示 | `partial`：旧 view-model 和提示卡接回，4 项单测通过 | 图片延迟/长流滚动场景待专门验收 | P2 / Web |
| R13 | 顶栏、主题、专注模式 | `done`（本轮验收范围）：旧展示恢复 | 最终桌面/手机、浅深、弹层、专注与截图通过 | P2 / Web |
| R14 | 粘性状态栏与最后活动 | `partial`：旧状态栏接回；审批跳转当前面板 | 不恢复旧空响应审批；各终态反馈待专项验收 | P2 / Web |

`done` 只代表上述限定的功能和证据，不代表所有极端场景均覆盖。`partial` 明确区分实现已接回与尚缺专项实测；后置需求仍见第 4 节。

## 3. 已恢复或已有实现，不能误写成失效

| 能力 | 当前状态 | 本轮证据与剩余验收 |
| --- | --- | --- |
| 高级模型选择器 | `done`（控件范围） | 已恢复搜索、渠道分组、项目默认及管理链接；键盘选择提交模型 UUID 的单测通过，浏览器打开/搜索/Escape 焦点通过；不代表全部模型推理通过 |
| 左历史、右聊天、回复卡片、底部输入框 | `partial`（完整视觉） | 直接取回旧组件并接当前状态；必要适配见 14，不宣称与旧后端行为完全相同 |
| Agent 统一选择 | `done`（既有交付） | 已授权 Graph 对齐 Agent，用户不再独立选择 Graph；本地两个 Agent 实际对话成功 |
| 流式发送、刷新读回 | `done`（本地两 Agent 场景） | 本轮真实浏览器验证，详见 13；更广场景保留原验收范围 |
| 停止、断线恢复、unknown 请求核实 | `partial`（本轮重新验收） | 当前保留 `useChatSession` 实现及前序测试；最新完整工作台下还需定向回归 |
| 多审批、复杂子图、工作过程折叠 | `done`（三尺寸回归范围） | 最新 1440/1024/390：3 passed；正文隔离、混合审批、连续 Thread 切换通过 |
| Markdown、公开 reasoning、工具结果、图片/文件链接 | `done`（既有渲染能力） | `Transcript`、`MessageContent`、`ToolResult` 保留；整页视觉验收仍待完成 |
| 附件选择、粘贴、预览、移除 | `partial`（本轮重新验收） | Composer 与附件 composable 接线保留；本轮未逐模型验证多模态能力 |
| 运行中补充消息、回执、unknown 幂等重试 | `partial`（本地重新验收） | 现有实现保留；inbox 初始化已执行，本轮真实长任务补充消息尚未重新完整验收 |
| 专注模式和手机布局 | `done`（本轮布局范围） | 1440/390 浅深截图、无溢出、弹层、Files 空态、专注退出与焦点返回通过；全部业务操作不在此扩大声明 |

## 4. 必须保留的边界

- **明确后置 `deferred`**：双浏览器同 Thread 同时入队、完整文件/Skills API、交互式 PTY。不得把这些混入本轮必须补齐清单，也不得打完成勾。
- 旧 `values.files` 编辑不等于真实沙箱文件写回；完整文件 API 后置。现阶段可以恢复公开完整内容的查看、复制、下载，不虚构写回成功。
- 旧 Artifact 面板只是条目和 JSON 展示，并非完整生成式 UI 引擎；恢复该能力不意味着实现任意动态组件执行。
- 旧列表搜索也是对已取得条目做过滤；当前不承诺全库全文搜索。分页与筛选范围应在界面讲清楚。
- Web 优先补呈现和交互；Platform API 负责权限、目录及网关，Runtime 负责模型参数与公开状态。只有核对出真实契约缺口才改后端。
- 本次没有证据要求 GraphHarbor 增加新能力；禁止把业务展示、模型目录和文件业务写入 GraphHarbor。

## 5. 实施及验收勾选表

- [x] 锁定用户确认的完整旧工作台基线，对照旧源码与当前代码形成差异表。
- [x] 录入 7 个本地模型，并验证默认模型在两个 Agent 的真实回复及刷新读回。
- [x] 修复最新回归的会话定位问题，完成 1440/1024/390 三尺寸回归，不弱化审批和正文断言。
- [ ] 完成 R01—R02 会话侧栏还原与服务端分页衔接。
- [x] 完成 R03 运行参数草稿、Max Tokens 及真实执行参数验证。
- [x] 恢复消息操作、分支导航与隔离文字草稿，完成真实重试/原位编辑/只读导航验证；含附件编辑另待验。
- [x] 完成 R08、R11 会话详情抽屉与历史可读展示。
- [ ] 完成 R09 已公开完整文件的复制/下载；真实写回保持上述边界。
- [ ] 完成 R10 合法公开 Artifact 条目展示。
- [ ] 完成 R12—R14 跟随反馈、顶栏及状态呈现。
- [ ] 完成新增 inbox 启动迁移路径及本地补充消息回执复验。
- [x] 完成浅/深主题、模型弹层、详情抽屉、移动布局/专注截图及键盘焦点验收；未覆盖的附件/文件操作不计入。
- [x] 最终 lint、类型检查、生产构建及 Chat/auth 定向测试通过；最新结果同步 08、14 与项目总状态。

每项完成需要同时满足：代码有入口、接入当前契约、可操作验证通过。不能仅凭文件存在或历史测试结果打勾。

## 6. 源码与验证索引

旧版均取自 Git `8056869`，路径前缀为 `apps/platform-web/src/modules/chat/`：

- `components/BaseChatTemplate.vue`：整体布局、草稿存储、跟随策略、专注模式与抽屉接线。
- `components/ChatThreadSidebar.vue`：分组、预览、逐条删除与分页。
- `components/ChatRunOptionsDialog.vue`：Max Tokens、参数草稿、确认/取消/还原。
- `components/ChatMessageList.vue`：消息复制、编辑、重试及相邻分支切换。
- `components/ChatContextDrawer.vue`、`ChatArtifactPanel.vue`：详情分区、文件操作、历史与 `state.ui` 展示。

当前工作区：

- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`：列表、目标、路由、草稿重置。
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`：参数、详情、历史、模型、附件、回执和跟随。
- `apps/platform-web/src/modules/chat/components/ChatModelSelector.vue`、`ChatModelSelector.spec.ts`：恢复的高级选择器及 UUID/键盘测试。
- `apps/platform-web/src/modules/chat/components/Transcript.vue`、`MessageContent.vue`、`ToolResult.vue`：消息操作与内容展示。
- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`：新 SDK 生命周期、审批、队列与待确认请求存储。
- `apps/platform-web/src/services/threads/session.service.ts`：当前列表仅选择摘要字段，分页大小 20。
- `apps/runtime-service/src/runtime_service/services/reference_agent/agent.py`、`tests/services/reference_agent/test_agent.py`：模型引用修复与 11 项定向测试。
- `scripts/local-stack.sh`：新增 Runtime 业务 inbox 迁移步骤。

旧时点实施与真实本地验证：[13 完整工作台与本地模型](implementation/13-complete-workbench-and-local-models.md)。前序测试：[12](implementation/12-visual-agent-and-local-stack.md)，保留其历史范围，不扩写为本轮完整恢复通过。

前一轮失败证据（保留历史，不作为最新结果）：`/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-xloje4ui/browser-results/`；1440 场景在 `e2e/parallel-chat-refactor.spec.ts:102` 历史条目定位超时。临时日志可能被系统清理，修复后应保留最终可复跑命令及结果。

前一轮该回归结果为 **2 passed / 1 failed**：1024、390 通过，1440 失败。通过的尺寸不能替代失败尺寸，也不覆盖上述缺失功能。

最新结果覆盖前述历史定位失败：三尺寸 **3 passed**，增强真实工作台 **1 passed**，Chat/auth **37 passed /1 skipped**。截图、命令与范围见 [14](implementation/14-copy-original-chat-components.md)。
