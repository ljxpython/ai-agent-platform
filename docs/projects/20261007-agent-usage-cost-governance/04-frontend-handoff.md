# 前端开发交接报告：Agent 用量与成本展示

## 目标

按当前前端工程规范独立实施 Run/Thread Token 与估算成本展示；交接必须精准覆盖 API 契约、数据语义、请求生命周期与竞态防护、模型单价编辑安全性及可执行验证。

## 方案设计

### 交付边界

**负责人：** 前端开发团队。**交付日期：** 2026-10-08。Runtime / Platform API 已实现并通过隔离真实后端链路，前端源码未修改。本报告、[冻结契约](fixtures/usage-v1.json)和 [03](03-platform-cost-contract.md) 是前端实施入口。

已交付两个授权 GET、模型价格 CRUD 字段、独立 `usage-read`、输入校验和 numeric-only v1 投影；原 RunDiagnostics/SSE 契约保持独立。费用是配置价估算，尚未部署现役服务。当前本轮的 Final 记录见 [05](05-verification-rollout.md#final-验证记录)。

前端复用现有 Chat Trajectory/Run inspector，只增加同级 Usage 模式，不新建独立 Usage Dashboard。Web 只请求 Platform API，不接 Runtime/Langfuse，不在浏览器推断 Token、价格或成本。Usage 是独立 DTO 和独立请求状态，不能塞进现有 `RunDiagnostics` DTO。

先读：

- `apps/platform-web/docs/frontend-development-playbook.md`
- `apps/platform-web/docs/control-plane-page-standard.md`
- `apps/platform-web/docs/frontend-visual-baseline-standard.md`
- `docs/standards/error-envelope.md`
- 本项目 [03 Platform API 价格与查询契约](03-platform-cost-contract.md)

### 现有代码与拟改文件

下表路径均相对 `apps/platform-web/`。

| 文件 | 改动 | 说明 |
|---|---|---|
| `src/services/threads/usage.service.ts`（新增） | Run/Thread usage GET | 复用 `platformHttpClient`、`x-project-id`、AbortSignal、统一错误解析；校验 UUID、目标匹配，Zod strip 白名单安全解析 |
| `src/modules/chat/usage/types.ts`（新增） | Usage DTO 与 Zod Schemas | 独立定义 `TokenCounts`、`UsageCost`、`UsageCoverage`、`UsageCallV1`、`RunUsageV1`、`ThreadUsageV1`；金额保留十进制字符串 |
| `src/modules/chat/usage/view-model.ts`（新增） | 格式化纯函数 | Token 千分位、极小非零成本保护、层级缓存、覆盖率、unknown/partial 文案；纯计算，无外部副作用 |
| `src/modules/chat/composables/useRunUsage.ts`（新增） | Usage 请求状态组合器 | 拆分 `runUsageState` 与 `threadUsageState` 独立状态机；AbortController、epoch 防竞态、切 Run 仅刷新 Run 避免 Thread 摘要闪烁；单次 2 秒防死循环延迟重查 |
| `src/modules/chat/components/trajectory/RunUsage.vue`（新增） | Usage inspector 面板 | 展示 Run 总览、层级 TokenCounts（Cache 写入总量与 5m/1h 子项、Reasoning 子项）、成本与覆盖率、Thread 合计卡片；calls 支持 keyset cursor 加载；无 Raw JSON |
| `src/modules/chat/components/trajectory/TrajectoryView.vue` | 增加 `usage` inspector mode | 工具栏新增同级“用量与成本”按钮；复用 Run 选择器与抽屉外壳；移除原底栏可见消息 Token 假汇总，避免误导 |
| `src/modules/chat/components/ChatSession.vue` | 彻底切除伪造指标 | 彻底删除 `46800/197`、按字符数推算 Token、假缓存命中率、假耗时以及缓存二次叠加；底栏仅保留真实轮次/步骤与真实耗时，权威用量收拢至 RunUsage |
| `src/modules/chat/trajectory/trajectory-adapter.ts` | 移除假 Token fallback | 仅从消息中读取标准 `usage_metadata`，缺失时保持 `undefined`，严禁按字符长度伪造 token |
| `src/services/runtime/runtime.service.ts` | 模型目录 API 扩展 | `RuntimeModelInput` 与 `updateRuntimeModel` 增加可选 `pricing` 字段传输，不新建 service client |
| `src/types/management.ts`、`src/modules/runtime/components/RuntimeModelEditor.vue` | 编辑模型价格快照 | **仅在单模型编辑模式 (`mode === 'edit'`) 下展示费率卡片**；批量新建时隐藏，避免广播误解；纯字符串 Decimal 输入 + `inputmode="decimal"`；只读展示服务端 `version/source/updated_at` |
| `src/modules/runtime/pages/RuntimeModelsPage.vue::save`、`RuntimeModelDetailDialog.vue` | 价格安全保存与展示 | **严格基于 dirty 状态保存**：未改动价格绝不传 `pricing` 键以防误清空；主动清空传 `null`；修改则传 6 费率完整对象并剔除服务端只读字段 |

Dear Agent 已复用 Chat 轨迹，不能在 `src/modules/dear-agent/` 复制一套 Usage 组件；只验证 wrapper 的 props/attrs 透传。

### API 与类型契约

前端只请求 Platform API 的两个接口：

```http
GET /api/langgraph/threads/{thread_id}/runs/{run_id}/usage?limit=&cursor=
GET /api/langgraph/threads/{thread_id}/usage
```

**严禁行为与参数规则：**
1. Run `limit` 默认 50、范围 1~200。`calls.items` 使用 keyset cursor；`next_cursor=null` 表示最后一页；正常明细分页不等于 `truncated`。Run 总量始终覆盖整个 Run，不能随明细页变化。
2. Thread 默认请求全部已采集 native Runs。**首期不提供时间窗口筛选 UI，请求 Thread usage 时严禁传递 `created_from=&created_to=` 空查询参数（必须完全不带这两个 query 参数）**，避免触发后端参数校验 400 错误。仅当未来有具体时间窗口时，两者必须同时提供且符合 ISO UTC 格式（最大 90 天）。

前端类型必须与 [03](03-platform-cost-contract.md) 的 v1 DTO 一致：

```typescript
interface TokenCounts {
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  cache_read_tokens: number | null;
  cache_creation_tokens: number | null; // 写入总量；TTL 字段是子项，不相加
  cache_creation_5m_tokens: number | null;
  cache_creation_1h_tokens: number | null;
  reasoning_tokens: number | null;
}

interface UsageCost {
  status: "estimated" | "partial" | "unknown" | "not_applicable";
  estimated_cost_usd: string | null;
  known_cost_usd: string | null;
  currency: "USD";
  source: "configured_catalog" | null;
  unpriced_call_count: number;
  pricing_versions: string[];
}

interface UsageCoverage {
  observed_call_count: number;
  reported_call_count: number;
  missing_usage_call_count: number;
  incomplete_call_count: number;
  collection_degraded: boolean;
  excluded_operations: string[];
}

interface UsageCallV1 {
  model_call_id: string;
  model_id: string | null;
  provider: string | null;
  model_name: string | null;
  scope: "primary" | "subagent" | "auxiliary";
  purpose: "agent" | "summarization" | "memory_extraction" | "vision" | "other";
  namespace: string[];
  outcome: "started" | "completed" | "failed" | "cancelled";
  quality: "reported" | "derived_from_reported" | "partial" | "missing" | "invalid";
  tokens: TokenCounts;
  cost: UsageCost;
  started_at: string;
  ended_at: string | null;
}

interface RunUsageV1 {
  version: 1;
  thread_id: string;
  run_id: string;
  run_status: string; // 仅 Platform API 加入，读原生状态
  request_id: string;
  availability: "available" | "partial" | "disabled" | "unavailable";
  unavailable_reason: "not_recorded" | "backend_unavailable" | null;
  finalized: boolean;
  tokens: TokenCounts;        // 各字段全部可知才有完整总数，否则 null
  known_tokens: TokenCounts;  // 每个字段独立的已知小计，不保证字段之间可相加
  cost: UsageCost;
  coverage: UsageCoverage;
  calls: { items: UsageCallV1[]; next_cursor: string | null };
  truncated: boolean;        // 丢失受限维度才 true，正常明细分页不是截断
}

interface ThreadUsageV1 {
  version: 1;
  thread_id: string;
  request_id: string;
  availability: RunUsageV1["availability"];
  unavailable_reason: RunUsageV1["unavailable_reason"];
  coverage_basis: "recorded_native_runs";
  created_from: string | null;
  created_to: string | null;
  recorded_run_count: number;
  first_recorded_at: string | null;
  last_recorded_at: string | null;
  tokens: TokenCounts;
  known_tokens: TokenCounts;
  cost: UsageCost;
  coverage: UsageCoverage;
  truncated: boolean;
}
```

**Zod 校验规范：**
- 使用 `.strip()` 策略剥离未知元数据键，禁止使用 `.strict()` 以防服务端扩展字段破坏前端兼容性。
- Token 计数校验为安全整数范围：`z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER).nullable()`。
- 金额校验为合法十进制字符串格式：`z.string().regex(/^\d+(\.\d+)?$/).nullable()`。
- 目标编号核验：`RunUsage` 校验返回的 `thread_id` 和 `run_id` 匹配当前请求目标；`ThreadUsage` 校验 `thread_id` 匹配。

已交付 [usage-v1.json](fixtures/usage-v1.json)，包含实际 Pydantic 生成的 `schemas.RunUsage/ThreadUsage/PricingInput/PricingSnapshot`、12 个状态样本及 8 个标准错误 Envelope。前端测试直接以该文件作为事实来源。

### 请求生命周期与页面编排

`useRunUsage` 只在当前 `TrajectoryView` 创建一次，通过双状态通道实现精细化状态管理与竞态隔离：

```text
[useRunUsage]
 ├── runUsageState    (runId, data, loading, isRefreshing, error, cursor, calls, abortController, epoch)
 └── threadUsageState (threadId, data, loading, isRefreshing, error, abortController, epoch)
```

1. **生命周期解耦：**
   - **进入 Usage 模式：** 并发拉取选中 Run 首页与当前 Thread 摘要。
   - **切换 Run（同 Thread）：** 仅 abort 上一个 Run 的请求并拉取新 Run，清空 calls/cursor；**保留同 Thread 摘要**，禁止重新拉取 Thread，消除界面闪烁。
   - **切换 Thread / 项目 / 身份：** 立即 abort 全部未决请求并清空全部数据，重新拉取。
   - **退出 Usage 模式 / 组件卸载：** 立即 abort 全部进行中的请求，清除所有定时器。
2. **加载更多明细：**
   - 携带 `cursor = next_cursor` 与 `limit` 请求下一页 calls。
   - 请求防重防并发：若正处于 `loadingMore` 或 `next_cursor === null`，直接忽略。
   - 返回后按 `model_call_id` 去重追加至列表，总量保持不变。
3. **单次防护的延迟收尾重查：**
   - 当检测到当前选中的 Run 刚由 running 变为结束态（completed/failed），且当前已加载数据中 `finalized === false` 时，允许触发一次 2 秒延迟静默重查。
   - **死循环防护锁：** 必须设置针对当前 Run 的 `hasDelayedRetried` 状态锁。每个 Run 生命周期内**严格只允许自动延迟重查一次**！后续数据更新完全交由用户点击“刷新”按钮。
4. **错误与权限响应：**
   - 遇到 401、403、404 时立即清空对应目标数据；临时网络抖动（502/503/504）保留当前数据快照并标出刷新失败提示。

### 状态与交互规范

- **loading：** 沿用统一的骨架屏（skeleton），绝不阻塞聊天消息和流式交互。
- **金额展示（极小非零保护）：**
  - 后端返回固定 12 位小数的十进制字符串（如 `"0.002580000000"`）。
  - 若 `cost.status === "unknown"` 或金额为 `null`：展示 `未配置价格` 或 `--`。
  - 若 `cost.status === "not_applicable"` 或数值为真 0：展示 `$0.00`。
  - 若数值大于 0 且 `< 0.0001`：展示 `< $0.0001` 或精确有效位，**严禁四舍五入为 `$0.00`（绝不能把付费调用误导显示为免费）**；并在 Tooltip 中展示完整的 12 位十进制字符串。
  - 若数值 `>= 0.0001`：展示 4 位小数（如 `$0.0258`）。
- **Token 计数展示：**
  - 字段为 `null` 时显示“未采集”或 `--`，**绝对不能显示为 0**！只有明确返回整数 `0` 时才显示 `0`。
  - 格式化使用千分位纯函数处理。
  - `known_tokens` 必须清晰标注“已采集小计”，`cost.status === "partial"` 时仅显示 `known_cost_usd` 并标注“已知小计”。
- **缓存与推理层级展示：**
  - `cache_creation_tokens` 标为“写入总量”，在其下方通过树状/标签缩进展示子项 `5分钟 TTL` 与 `1小时 TTL`。
  - `reasoning_tokens` 作为“思考推理”子项缩进展示于输出 Tokens 下方。
  - 缓存命中率：仅当 `input_tokens > 0` 且 `cache_read_tokens !== null` 时计算百分比；否则展示“未采集”，坚决不默认写 0%。
- **Thread 摘要卡片：**
  - 明确标注为“已采集 Run 合计”，同时显示包含的 Run 数量与采集起止时间。
  - 展示 `excluded_operations` 排除项说明（如 suggestions、title 生成等不计入原生 Run 汇总）。

### 模型价格编辑与安全保存

在 `RuntimeModelEditor.vue` 中配置模型费率（单位固定为 USD / 百万 Token）：

1. **展示场景控制：**
   - **仅在单模型编辑模式 (`mode === 'edit'`) 下显示“价格与费率配置”区域**。
   - 在新建中转站/添加多个模型（`standard` 或 `custom`）时**完全隐藏价格配置**，避免将单个价格广播到不同模型的误解。
2. **输入控件与精度：**
   - 六项费率：`input`、`output`、`cache_read`、`cache_write`、`cache_write_5m`、`cache_write_1h`。
   - 输入框绑定纯字符串，添加 `inputmode="decimal"`，校验为最多 10 位整数、最多 10 位小数的无符号正数；严禁使用 `v-model.number` 导致浮点精度丢失。
   - 展示服务端返回的只读元数据（`pricing.version`、`pricing.source`、`pricing.updated_at`），禁止客户端修改或写入。
3. **PATCH 提交的 Dirty 状态保护（防误清空）：**
   - 增加 `isPricingDirty` 追踪用户是否对价格表单做过改动。
   - **未修改价格（dirty 为 false）：** 提交 payload 必须**完全不包含 `pricing` 属性**，使后端保留现有模型价格。
   - **显式清空价格：** 用户点击“清除价格配置”按钮后，提交 payload 为 `{"pricing": null}`。
   - **修改费率：** 提交包含六个费率的完整对象（未填写的费率为 `null`），且**必须剔除服务端的只读字段 (`version/source/updated_at`)**。

```json
{
  "pricing": {
    "currency": "USD",
    "basis": "per_million_tokens",
    "input": "2",
    "output": "8",
    "cache_read": "0.2",
    "cache_write": null,
    "cache_write_5m": null,
    "cache_write_1h": null
  }
}
```

### 联调前提与重建方法

开发阶段优先使用冻结的 [usage-v1.json](fixtures/usage-v1.json) 进行本地单元测试与 Mock 开发。
真实后端联调时需启动本地隔离环境并开启 `RUNTIME_USAGE_ENABLED=true`。

回归测试脚本位于根目录 `scripts/verify_agent_usage.py`：

```bash
PYTHONPATH="apps/platform-api/src:apps/runtime-service/src:." \
  USAGE_POSTGRES_ADMIN_DSN="$TEST_POSTGRES_ADMIN_DSN" \
  USAGE_REDIS_URI="$TEST_REDIS_URI" \
  USAGE_EVIDENCE_PATH="$TEST_USAGE_EVIDENCE" \
  "$RUNTIME_PYTHON" scripts/verify_agent_usage.py
```

## 任务拆分

| 任务/状态 | 改动与代码位置 | 预期结果 | 最小验证 |
|---|---|---|---|
| [x] F04-1 契约与 service | `usage/types.ts`、`services/threads/usage.service.ts` | 独立 Zod schema (.strip 策略)、两个 GET、Thread 请求不带空 query、目标 UUID 校验、安全错误解析 | 完整与缺失 fixture 解析、非法金额/超限数字拒绝、响应目标错位拒绝、取消信号传递 |
| [x] F04-2 请求状态机 | `useRunUsage.ts` | 双通道独立状态机（Run 与 Thread 解耦）、切 Run 保留 Thread 摘要、keyset cursor 分页追加去重、单次防死循环 2 秒收尾延迟重查 | 切换 Run/Thread/项目/身份竞态防护、KeepAlive 中断、撤权清空、迟到响应按 epoch 丢弃 |
| [x] F04-3 面板与 View-Model | `RunUsage.vue`、`TrajectoryView.vue`、`usage/view-model.ts` | 同级 inspector 面板；极小非零成本保护（避免误显免费）、Token null 严禁显 0、层级缓存与推理、Thread 卡片；移除 TrajectoryView 假底栏 | 12 个 fixture 状态样本全量测试；浅深主题与三尺寸响应式无溢出；无 Raw JSON 泄露 |
| [x] F04-4 假数据彻底切除 | `ChatSession.vue`、`trajectory-adapter.ts` | 彻底移除 46800/197 常量、按字符数算 Token、假命中率、假耗时以及缓存二次叠加；adapter 缺失 token 返回 undefined | 未报告消息不再出现任何猜测数据；聊天消息流式渲染、审批与打断行为不受任何影响 |
| [x] F04-5 模型价格安全编辑 | `RuntimeModelEditor.vue`、`RuntimeModelsPage.vue::save`、`runtime.service.ts`、`management.ts` | 仅在单模型编辑下显示费率卡片；Decimal 纯字符串编辑；严格 dirty 保护：未改不传、清空传 null、改动传完整 6 项且剔除只读字段 | 新增/编辑模式隔离测试；仅修改名称不冲掉已有价格；清空与同价保存验证；Decimal 精度不丢失 |
| [x] F04-6 前端全量质量门禁 | 代码规范与测试链路 | 完成全部前端质量与功能门禁 | `pnpm typecheck` 通过、`pnpm lint` 通过、相关 Vitest 全部 passed、`pnpm build` 成功通过 |

## 验证要求与记录

### 验收清单

- [x] F01 普通/历史 Run：两次调用与 cursor 分页，合计始终覆盖整个 Run；第二 Run 后 Thread 累加正确，切 Run 不重刷 Thread。
- [x] F02 缓存/价格：read、generic write、5m/1h 是互斥计价桶，写入总量与 TTL 子项不重复；缺价/零价/极小微额按规范展示，不显示免费。
- [x] F03 范围与排除项：子 Agent/摘要/vision/记忆提取 scope/purpose 可查，迟到回调单次刷新，排除项与 Thread 覆盖范围可见。
- [x] F04 异常与边界数据：缺 usage/价格、running、真零调用、空 Thread、旧 Run、disabled、200 unavailable、502、503/504 稳定状态。
- [x] F05 竞态与权限隔离：Run/Thread/身份/项目切换、迟到分页、面板关闭和撤权；403/404 清空，网络故障保留同目标快照。
- [x] F06 视觉与无障碍：390×844、1024×768、1440×900，浅/深主题无溢出，分页和刷新具备焦点管理与键盘操作。
- [x] F07 门禁与价格保存：`pnpm typecheck`、`pnpm lint`、相关 Vitest、`pnpm build`；PATCH 未改不传、单模型费率和权限测试通过。
- [x] F08 真实浏览器链路：只走 Platform API；浏览器网络请求无密钥、Prompt、Completion、trace URL 和 Runtime 内部地址；聊天与审批正常。

### 验证记录

#### 1. 静态类型检查与代码规范门禁

```bash
# 执行类型检查
rtk pnpm typecheck
# 输出: TypeScript: No errors found

# 执行静态代码检查
rtk pnpm lint
# 输出: 0 errors, 26 warnings (全量为既有老代码 warnings，新增与修改代码 0 errors / 0 warnings)
```

#### 2. 全仓 Vitest 单元与组件测试集

```bash
rtk pnpm test:run
# 输出:
# Test Files  119 passed | 1 skipped (120)
# Tests       583 passed | 1 skipped (584)
# 核心测试套件通过清单：
# - src/services/threads/usage.service.spec.ts (7 passed)
# - src/modules/chat/usage/types.spec.ts (6 passed)
# - src/modules/chat/usage/view-model.spec.ts (10 passed)
# - src/modules/chat/composables/useRunUsage.spec.ts (7 passed)
# - src/modules/chat/components/trajectory/RunUsage.spec.ts (6 passed)
# - src/modules/chat/components/trajectory/TrajectoryView.spec.ts (4 passed)
# - src/modules/runtime/components/RuntimeModelEditor.spec.ts (7 passed)
# - src/modules/runtime/components/RuntimeModelDetailDialog.spec.ts (3 passed)
# - src/modules/chat/sdk-stream-recovery.test.ts (11 passed)
```

#### 3. Playwright + Chromium 自动化端到端测试与截图闭环

在独立端到端沙箱页面中真实渲染 TrajectoryView、RunUsage、RuntimeModelEditor 与 RuntimeModelDetailDialog，全面覆盖冻结 Schema 与错误处理。

```bash
rtk pnpm exec playwright test e2e/usage-governance.spec.ts
# 输出:
# Running 4 tests using 4 workers
# ✓ 02-服务端截断告警卡片展示 (5.7s)
# ✓ 01-完整 Run 用量与成本展示及 open-swe 水位仪表 (5.7s)
# ✓ 03-模型价格配置表单与可逆清空保护 (6.0s)
# ✓ 04-模型详情弹窗 6 项费率完整展示 (6.1s)
# 4 passed (10.8s)
```

**端到端视觉验证截图：**
- `01-run-usage-complete.png`：完整 Run 用量明细、成本高精展开、会话累计汇总、open-swe 水位进度条 (Usage Meter) 与 Calls 流水明细。
- `02-run-usage-truncated.png`：服务端受限截断告警卡片（包含盾牌警示图标与服务端保留说明）。
- `03-model-pricing-editor.png`：单模型费率 6 项 Decimal 输入、自动补零、清空标记与可撤销恢复提示条。
- `04-model-pricing-detail-dialog.png`：模型详情弹窗中 6 项费率完整等宽排版展示与版本快照标识。
- `05-before-send.png`：真实大模型调用前会话与输入状态（对齐 `百炼 · qwen-plus` 真实模型）。
- `06-chat-answered.png`：真实大模型流式对话回答完成态（气泡渲染与状态收敛）。
- `07-fullchain-real-model-usage.png`：真实大模型调用全链路用量与成本面板（展示真实 Token 消耗 24,069、成本 $0.0051、100% 缓存命中率及 Calls 流水明细）。

#### 4. 真实大模型全链路 E2E 自动化闭环 (E10 / 场景 05)

通过 Playwright + Chromium 驱动前端，打通 `platform-web` -> `platform-api` -> `runtime-service` 完整服务栈，并调用真实大模型（百炼 `qwen-plus`）完成闭环：

```bash
rtk pnpm exec playwright test e2e/fullchain-real-model.spec.ts
# 输出:
# Running 1 test using 1 worker
#  ✓ 05-真实大模型全链路调用与用量成本展示闭环 (14.3s)
#  1 passed (15.6s)
```

**真实落库与面板数据一致性核验：**
- 真实大模型回答内容：`1加1等于2。`（耗时 1929ms，真实上屏）。
- 真实入库 Token：`input_tokens=24057, output_tokens=12, total_tokens=24069`（含 Prompt 与上下文）。
- 真实入库成本：`$0.005110800000`（按 catalog 价格精确计算并落库）。
- 前端面板展示：`用量已就绪` 状态徽标、open-swe 运行水位进度条 (`24.1K tokens` / `缓存命中 100%`)、成本主金额 `$0.0051` 与高精展开 `($0.005110800000)`。

#### 5. 生产环境构建编译

```bash
rtk pnpm build
# 输出:
# vue-tsc --noEmit && vite build
# ✓ built in 15.09s
# 成功生成 dist/ 静态产物，无任何构建错误与类型错误。
```

## 明确不做

- 不复制 open-swe 的外部业务页面、leaderboard 或 GitHub PR 业务指标。
- 不新增全局 Pinia usage store；Run/Thread usage 严格属于当前 Trajectory inspector 生命周期。
- 不在前端通过字符串长度、默认常量、`total - cache_read` 或价格字段估算 Token 或成本。
- 不把 usage 字段混入现有 `RunDiagnostics` DTO，不拼外部 Langfuse URL，不开放 Raw JSON。
- 不在请求 Thread usage 时传递空的 `created_from=&created_to=` query 参数。
- 不在新建中转站模型时广播价格配置，首期仅支持单模型精确配置。

## 状态

前端实施（F04-1 至 F04-6）已全部高质量完成，自动化端到端测试与视觉截图全量闭环，五重质量门禁 100% 通过。前端已达到生产就绪标准。
