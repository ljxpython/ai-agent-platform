# 01 现状审查与退役清单

## 目标

区分架构问题、确定性缺陷和待联调能力；给重构确定边界。审查依据是代码和本地检查，不把“旧代码全部很差”当作结论。

## 方案设计

### 1. 总体判断

现有 Vue/Vite、路由懒加载、service 层、Pinia 和官方 `useStream` 的基础选型可以继续使用。主要问题是**契约已收缩但前端仍保留旧字段；SDK 之外又维护多套状态；UI 正式能力与参考/调试内容混杂；新旧渲染链没有完成替换**。继续小修将维持这些边界冲突，值得重写 Chat 主链和页面编排。

本次统计 `.ts/.vue/.css` 文本行，含空行/注释，不是业务复杂度或压缩包大小：

| 范围 | 文件数 | 行数 |
| --- | ---: | ---: |
| `apps/platform-web/src`，含测试 | 222 | 43,140 |
| 上述范围剔除 `*.test.ts`/`*.spec.ts` | 187 | 39,860 |
| `src/modules/chat`，含测试 | 64 | 12,250 |
| `src/modules/examples` | 17 | 5,018 |
| `examples/sub2api-reference` | 261 | 101,800 |

### 2. 证据与后果

下表路径均相对 `apps/platform-web/`，行号对应审查快照。

| 级别 | 证据 | 问题与后果 | 处理 |
| --- | --- | --- | --- |
| P0 | `src/modules/chat/runtime-model-default.ts:7`、`:25`；Agent 表单 `model.model_id` | 目录已返回 `id`，这里调用 `item.model_id.trim()`；新契约数据可直接触发 TypeError。`is_default` 也已删除 | 目录类型收紧，选择器 value 全部使用记录 UUID；默认值从 Agent/项目策略或服务端决议取得 |
| P0 | `src/modules/chat/composables/platform-chat-stream/actions.ts:152`、`:178` | `respond/respondAll` 附带运行 config，后端审批路径拒绝 config/context/input 覆盖 | 审批请求仅含真实 interrupt ID 与决策；单独测试实际 HTTP body |
| P0 | `src/services/runtime/runtime-contract.ts:161`；Agent 创建/详情页 | create/update 共用旧 payload，可发送 `config/metadata`，PATCH 可带 `graph_id`；后端 `extra=forbid` | 分离 CreateAgentInput/UpdateAgentInput，字段白名单；更新不发送 graph_id |
| P1 | `src/modules/chat/components/ChatMessageList.vue:50–75` | 深度 watch 每次消息变化递增列表根 key，导致整棵消息树重建；展开状态、编辑焦点和流性能受影响 | 稳定 message/tool/block key，靠 Vue 响应式局部更新 |
| P1 | `src/modules/chat/stream-messages-to-ui.ts:69`、`:279` | `mergeTextChunks` 丢弃同回合前面的全部正文；AI `content` 仅处理 string，丢失结构化文本块 | 保留全部内容和源消息 ID，只折叠工作过程，不删除事实 |
| P1 | `src/modules/chat/composables/usePlatformChatStream.ts:39`、`:135`、`:194` | SDK live、persistedHead、branch 和 `preferPersistedProjection` 竞争；按 ID 合并时历史同 ID 消息优先，可能遮蔽实时更新 | SDK 持有当前线程投影；历史快照仅用于显式历史视图 |
| P1 | 同文件 `reconcileMissedTerminal`；`actions.ts:14` | 每个新 Run 最多 20 次 × 250ms 状态补偿；审批最多 60 次 × 500ms 完整刷新 | 查明 SDK/事件终态原因；正常流无轮询。仅断线、取消确认、结果未知时做有界 reconciliation |
| P1 | `src/modules/chat/composables/useChatThreadWorkspace.ts` 的 `loadThreadList` | 首批 100 个列表结果充当 Thread URL 有效性判断；不在首屏的有效链接会被替换成其他会话，还逐个探测旧坏线程 | URL 指定线程直接鉴权 GET；分页列表不裁决线程存在性；删除旧坏线程迁移逻辑 |
| P1 | `src/services/langgraph/client.ts` 的 `withCommandIdempotencyKey` | key 在 fetch 层临时生成；同一次 401 重试可复用，但没有面向用户动作的冻结 payload/超时重试记录 | 将 key 生命周期提升到本次动作；不可把原文相同当作同动作 |
| P1 | `src/stores/workspace.ts:44–47` | projectId 先变更，access 异步回写；没有请求序号/取消保护，快速 A→B 可被 A 的迟到结果覆盖 | 切换立即清理 access，按 session/project epoch 接受结果 |
| P1 | `src/modules/chat/components/BaseChatTemplate.vue`，1,385 行 | 同时负责草稿、URL、线程、发送、滚动、模型、历史、审批、多个面板与布局；`messages`/`uiMessages` 两条展示链并存 | 由 ChatSession 管生命周期、ChatWorkspace 管布局、Transcript 管展示 |
| P1 | `src/modules/examples/template-detail-loader.ts:5/16/27`；`src/router/routes.ts` 的 resources | 正式产品路由通过 `import.meta.glob(...?raw)` 暴露大量历史参考源码；不是仅供离线阅读的目录 | 删除整个资源模板产品链，参考项目留在独立 research 路径 |
| P1 | `e2e/test_showcase_demo_e2e.spec.ts` | 真链路测试 mock Graph 目录、写个人绝对路径、广泛记录响应与请求正文、以文字长度代替结果验证 | 区分 fixture 测试和真实 E2E，限定日志字段，验证后端 Run/实际结果 |
| P2 | `src/modules/chat/components/ChatInterruptPanel.vue:45` | 审批草稿按 interrupt 数组下标而非 ID 建 key；界面重排不等于同一审批。提交已有部分 ID 映射，但草稿和刷新语义仍需重写 | 草稿 key 使用 interrupt ID + 该审批中的 action index，绑定不可变请求指纹 |
| P2 | `src/modules/sql-agent/pages/SqlAgentPage.vue:16` | 固定 `sql_agent` 产品入口，当前默认部署 `langgraph.json` 仅含 reference_agent/workflow_demo | 用部署目录和有效 Agent 动态进入 Chat，不硬编码图存在 |
| P2 | `src/types/management.ts`、`services/assistants`、`utils/chatTarget.ts` | 管理模型、执行目标和兼容别名混合，前端仍传播 assistant/graph 多套目标参数 | 产品统一 Agent；执行只用 graphId；上游 assistant_id 和权限码保持真实契约 |
| P2 | `docs/control-plane-page-standard.md`、`docs/frontend-visual-baseline-standard.md` | 仍要求 agent_key、Operations 和旧参考宿主；与后端交接和本轮目标冲突 | 实施时直接更新生效标准，不能让下个开发者再按旧规范实现 |

P0 是最短发送/审批/管理链路阻断项；P1 是重构主因；P2 是边界和维护问题。未用浏览器证明的性能、竞态描述是代码推导风险，不宣称线上故障已经重现。

### 3. 已运行的确定性复现

2026-09-10，使用本地 TypeScript `transpileModule` 临时加载原模块，未改源文件：

| 输入 | 原代码实际输出 |
| --- | --- |
| 新目录对象 `{id,display_name,provider,base_url,protocol,model,enabled,credential_configured}` 传给 `resolveChatDefaultModelId` | `TypeError: Cannot read properties of undefined (reading 'trim')` |
| 连续两条 AI 消息 `first explanation`、`final answer` | 仅剩 `final answer` |
| AI `content: [{type:'text',text:'structured answer'}]` | 空数组 `[]` |

这些缺陷与已有 121 项测试全通过可以同时成立：旧 mock/用例没有覆盖新的真实数据形状。不得通过给类型补旧可选字段掩盖问题。

### 4. 保留、替换和删除

| 分类 | 对象 | 具体动作/前置 |
| --- | --- | --- |
| 保留依赖 | Vue/TS/Vite/Pinia/Router、官方 LangChain、markdown-it、axios、现有测试工具 | 不增加第二套 UI 框架、第二套流解析器或全局事件总线 |
| 保留能力并收敛 | 登录、项目/成员、用户、Agent、模型/策略、Graphs/Tools、审计、公告、个人设置、服务账号、平台治理 | 每项先与真实 API 对照，再替换表单/页面编排；不是将非 Chat 页面全部删除 |
| 审核后复用 | `components/base`、基础表格/分页/反馈、主题、i18n、Markdown | 保留有消费者且满足无障碍的部分；统一 token，不为每个页面复制皮肤 |
| 完整替换 | Chat 会话组合、旧 target normalization、双消息投影、轮询补偿、笨重通用模板 | 以 04/05 的单一入口替代，消费者迁走后删除旧文件和旧语义测试 |
| 计划删除 | `src/modules/examples/**`、`examples/sub2api-reference/**`、resources/ui-assets 路由及导航/i18n/样式引用 | 先移除 glob 和消费者，再删除目录；不动独立 open-swe 参考仓库 |
| 计划删除 | `src/modules/sql-agent/**`、固定菜单和入口说明 | 动态 Agent/Graph Chat 入口可用后删除；不删除后端 SQL 能力（当前不保证有此部署） |
| 无消费者候选 | `src/views/workspace/OverviewView.vue`、`PlaceholderView.vue`、`ChatMessageMeta.vue` 及其孤立工具渲染链 | 当前检索未见对应页面/组件消费者；删除前再次检查静态引用、动态注册、测试和构建入口 |
| 依赖删除候选 | `@tanstack/vue-virtual` | 当前 src 检索未见使用；待 05 长列表测量决定是否直接使用，否则删除。`zod` 在 env 中实际使用，不能一并删 |
| 旧文档 | 旧 Chat 迁移方案、已被新规范替代的设计 | 逐份判断是否仍指导当前实现；只有被替代的内容才 archive，完成本身不是归档理由 |

**不为减行数而删除权限、错误处理、有效业务或验证。** 不设“必须删掉百分之多少”指标；以生产无参考源码、无旧入口、无重复状态/投影为可验证结果。

重构前基线构建确认参考源码曾进入发布产物：`dist/assets` 共 342 个文件、5,328,265 bytes（未压缩），包含 `CreateAccountModal`、`EditAccountModal`、`OpsDashboardHeader` 对应 chunk。这是全部产物统计，不代表首屏加载了 5.3 MB。

## 任务拆分

- [x] A0：统计代码、核查主链、记录真实基线和复现。
- [x] A1：按批准范围完成删除与最终路由→能力→权限对账（02 末表）；AI 实施，用户负责最终产品验收。
- [x] A2：已删除 resources/examples、固定 SQL 入口、17 个 examples 模块文件及 262 个内嵌参考文件；独立 research 仓库保留。
- [x] A3：新 Chat 验收后删除旧模板、旧状态链及过时单测，保留有价值回归场景。
- [x] A4：移除未使用 vue-virtual，更新前端 README、三份活标准、功能总览及旧测试/脚本引用。

## 验证要求与记录

- [x] 搜索静态 import、动态 glob、路由、菜单、文案和测试引用，候选无消费者后才删除。
- [x] 新实现覆盖以上三个确定性复现，结果完整且不报错。
- [x] 生产 bundle 不含资源模板源码和旧页面入口。
- [x] 不存在 Operations/resync/模型远端刷新/退役知识库/测试用例产品请求。

2026-09-10 规划阶段记录（非当前状态）：`pnpm test:run` **35 文件 / 121 项通过**；`pnpm typecheck` 通过；`pnpm lint` 退出 0，但 **0 errors / 356 warnings**。这不是新契约浏览器验收。完整验证计划见 [06](06-delivery-and-acceptance.md)。

## 状态

退役及文档开发已完成；最终产物验证见 06 与 implementation/11-closeout.md。

## 2026-09-11 任务对账

前次静态核对记录：当时按代码及 [01 实现记录](implementation/01-contracts-and-session-foundation.md)、[09 消息验收](implementation/09-message-delivery-completion.md)、[10 发布验证](implementation/10-graphharbor-post27-release.md) 更新。任务勾选表示该任务范围已完成；下方/上方独立验收清单未勾项仍未完整验证，不能据此宣布整个阶段通过。本次仅核对文档与代码，未重跑业务测试。
