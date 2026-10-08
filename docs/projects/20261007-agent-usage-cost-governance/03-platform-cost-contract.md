# Platform API 价格与查询契约

## 目标

复用模型目录维护价格，按既有项目/Thread 权限代理 Runtime 用量查询。Runtime 保留执行事实，Platform API 不建第二份计费表、不跨库读 Runtime SQL。

## 方案设计

### 1. 价格配置：一个可空对象

在 `runtime_catalog_models` 新增可空 `pricing_json`（现有 SQLAlchemy JSON 类型），扩展已有模型 Create/Update/Item 及 `StoredRuntimeModel`。采用结构化 Pydantic 校验，rates 的值为十进制字符串，服务端计算用 Decimal。不建价格微服务、继承层或价格表。

```json
{
  "pricing": {
    "currency": "USD",
    "basis": "per_million_tokens",
    "input": "2.0000000000",
    "output": "8.0000000000",
    "cache_read": "0.2000000000",
    "cache_write": null,
    "cache_write_5m": "2.5000000000",
    "cache_write_1h": "4.0000000000"
  }
}
```

这是测试配置示例，不代表任何模型官方价格。版本、来源和时间由服务端生成，模型目录只在合法 price write 时更新：

```json
{
  "pricing": {
    "currency": "USD",
    "basis": "per_million_tokens",
    "input": "2.0000000000",
    "output": "8.0000000000",
    "cache_read": "0.2000000000",
    "cache_write": null,
    "cache_write_5m": "2.5000000000",
    "cache_write_1h": "4.0000000000",
    "version": "82a29f7d-7e18-4c47-bf4e-ef293667193b",
    "source": "configured_catalog",
    "updated_at": "2026-10-07T08:00:00Z"
  }
}
```

规则：

- 全对象 nullable：旧模型/未配置保持 `pricing=null`；create 可不传，PATCH 不传保留，显式 null 清空；不自动为已有数据设置零价。
- 六项 rates 可空，非空只接受无指数的非负 decimal string（最多 10 位小数，且不超过 NUMERIC(20,10) 对应范围），拒绝 bool/NaN/Infinity/负数和未知键。
- 不要求所有模型都有缓存价；只要调用实际使用到的非零桶都有价才计算。普通写入、5m、1h 费率互不替代。
- version 为服务端 uuid；相同归一化对象 PATCH 不变 version，真实变价/清空后重设才生成新 version。客户端不能写 version/source/time。
- 现有平台模型按现有 Catalog write 权限管理；项目 BYOK 只能管理自己的记录。无同一公共模型的项目价格覆盖。继续复用已有审计动作，审计只记录模型 ID、版本和变化字段，不记录密钥。
- 支持线性 token price。不同多模态桶价格、上下文阶梯、batch、优惠等无法表达时使用 `unsupported_pricing`，先记 Token，后续另评审扩展。
- 价格 CRUD 不向外部服务发送模型 Prompt 或查询官方价格；不引入新的依赖/爬虫。

### 2. 可信模型连接响应

`RuntimeCatalogService.resolve_model_connection()` 保持短期引用校验、当前模型/Agent/Thread 权限核验和凭据解密逻辑，仅增加可选 `pricing` 对象。JSON 的 provider/model/api_key 等既有连接字段不变。

Runtime 的 `fetch_model_connection()` 当前只提取固定字符串字段，需要新增明确的内部连接类型，解析并保留安全 pricing。各工厂的 model_builder 重建/动态换模也必须使用实际模型的连接价格，不能用显示名选择同名价格。已接受的原生 Run 中价格以工厂取得的快照为准，同一工厂生命周期的父子调用共享同版本；worker 重启后若取到新版本则按调用存不同版本，summary 明确列出。

每个调用保存完整无 secret 的价格快照，金额用 Decimal 存 NUMERIC(28,12)，不在单次 Token 处提前舍入。公共 JSON 金额序列化为固定十进制字符串，精度最多 12 位小数。目录变价/模型删除不更改历史记录，没有有效价格的老 Run 不自动用今天价格回填。

本期成本语义为 `configured_catalog` 价格的估算，不能称“真实供应商账单”；本期没有 provider cost 接入。Langfuse 是已有观测副本，可交叉核对相同调用，不对它同步发请求求价格。

### 3. 公开与内部 API

| 公共接口 | Runtime 内部接口 | 用途 |
|---|---|---|
| `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/usage` | `GET /internal/threads/{thread_id}/runs/{run_id}/usage` | Run 总量与独立分页的 calls |
| `GET /api/langgraph/threads/{thread_id}/usage` | `GET /internal/threads/{thread_id}/usage` | 已采集 native Runs 的 Thread 合计，不返回全部 messages/calls |

平台执行：解析 UUID → `_load_thread(write=False)` 当前授权 → Run 级用现有 upstream get 验证 Run/Thread 一致 → 签发 Thread-bound usage-read → 调 Runtime → Pydantic 白名单验证 → 加原生 Run 状态和当前 request_id。Runtime 再执行 scope + 当前 `authorize_thread_targets(action="read")`。返回 `Cache-Control: no-store`。

冻结参数：

| 参数 | 规则 |
|---|---|
| Run `limit` | 默认 50，1-200；合计始终覆盖整 Run，与明细分页无关 |
| Run `cursor` | 可选受约束 base64 编码的 started_at + model_call_id keyset；校验 shape/长度，不拼 SQL。cursor 不授予权限，无需新增签名系统 |
| Thread `created_from/created_to` | 两者一起提供；默认不限制时间，只在已授权的一个 Thread 上索引聚合；自定义窗口最多 90 天，UTC，左闭右开 |
| Thread response | 不分页 tokens，数据库聚合结果固定大小；pricing_versions 保留最多 50 项并设置 truncated，本期不加 models 排行字段 |
| namespace/model string | 有界白名单；不回显任意 metadata 原文 |

默认 Thread 全时间聚合只针对该 Thread 下已采集 Run，满足 session 累加要求；无全项目/all-users endpoint。数据过大时短 statement timeout 返回 unavailable，未测出瓶颈前不设滚动计数表。

### 4. DTO v1（已实现，尚未部署现役）

共享结构：

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
  tokens: TokenCounts;       // 各字段全部可知才有完整总数，否则 null
  known_tokens: TokenCounts;// 每个字段独立的已知小计，不保证字段之间可相加
  cost: UsageCost;
  coverage: UsageCoverage;
  calls: { items: UsageCallV1[]; next_cursor: string | null };
  truncated: boolean;       // 丢失受限维度才 true，正常明细分页不是截断
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

所有观测调用 usage 已报告、采集/调用已结束且未降级后，才给完整 `tokens`；在此前提下各字段仍需该字段覆盖全部调用，否则为 null。cache/reasoning 未报告不妨碍已经完整的 input/output/total。只要存在 missing/partial/invalid usage、started/open 或 degraded，完整 tokens 全部为 null；`known_tokens` 逐字段保留已知小计，各字段可能来自不同调用，不能强制 input+output=total。`cache_creation_tokens` 为写入总量，5m/1h 为子项；reasoning 是 output 子项，不能重复累计。

成本：采集已结束、全部观测调用已结束且可计价、没有 degraded/缺失消费时，整个 Run 才为 estimated；有已知金额但任一调用未知、未完成或采集降级时用 partial，`estimated_cost_usd=null`，只给 `known_cost_usd`；所有调用不可计价用 unknown，不能给完整金额。运行中的 Run 始终只给已知小计。Thread 汇总遵守相同规则；`unpriced_call_count` 统计成本未知或未完成的观测调用，无法推断未观测的调用数，只用 collection_degraded 声明风险。零模型调用且 ended 已确认时才为 total=0、cost=not_applicable；manifest 缺失是 not_recorded。

Thread 的 `coverage_basis` 必须展示为“已采集 Run 合计”。它不保证包含上线前 Run、排除的 one-shot 或非 LLM 费用。首期不从 checkpoint/Langfuse 补旧账，也不与 current displayedMessages 相加。

G0 已批准的保留边界：首期不新增自动过期清理，native Run 删除不抹掉已发生开销，Thread 合计仍按 ledger 聚合；具体 Run GET 因原生记录已不存在返回 404。Thread 删除/当前撤权后所有 usage 查询拒绝（当前 Thread ACL 先拒绝可返回403）。后续物理删除/过期策略另评审；90 天只限制自定义查询窗口，不是保留期限。

权限错误走现有 Envelope：未登录 401、当前资源拒绝 403、不存在或错归属 404；非法 UUID/窗口/cursor 400。已授权后的 Runtime 数据库故障为 200 + unavailable/backend_unavailable，保留当前 native run_status；协议损坏/无效 DTO 为 502，网络超时走既有 503/504 映射。不能把权限错误折成“暂无用量”。

所有计数 API 约束为 0..Number.MAX_SAFE_INTEGER，超过则 invalid_response/unknown，不截成错误数字；内部 DB 仍 bigint。金额只用字符串，未知 key 会丢弃。

### 5. Delegation：沿用五字段 scope

已新增 `usage-read`，必须绑定非空 Thread、assistant/tenant/project，现有 `scope` 仍为五字段。**不增加 scope.run_id**：Run ID 位于 URL，Platform 已验证原生归属，Runtime SQL 必须匹配 Run+Thread+tenant+project+graph。该 token 读取授权 Thread 内用量；需要单 Run token 时另评审，不虚构现有 JWT 字段。

usage-read 只允许两个内部 GET，不能访问原生 Thread/Run、模型连接、Workspace、MCP 或其他自定义 endpoints。`read`、`diagnostics-read`、`run-create` 也不能代替 usage-read。沿现有签发 TTL、当前用户/服务账号与撤权校验。

已按用户批准同步修改：

- `core/security/tokens.py` 与 Runtime `runtime/auth.py` 的 operation 名称集合/Thread 约束。
- Runtime `http/usage.py` 的 endpoint 精确匹配；`auth/platform.py` 保持 native whitelist 不包含 usage-read。
- 两端 Delegation fixture 和 tests，使用名称集合，不写固定 operation 个数。
- JWT 标准与健康表增加本专项证据，但不替原 JWT 全局 draft 遗留项毕业。

保持原有 RunDiagnostics DTO、diagnostics-read 和 SSE 契约，首期不增加 optional usage 槽位。前端复用入口/交互模式，不复用操作权限。

### 6. 代码落点

下表除明确跨服务/迁移路径外，均相对 `apps/platform-api/src/platform_api/`；新符号是规划命名，现有符号按实际实现维护。

| 文件/现有符号 | 工作 |
|---|---|
| `apps/platform-api/migrations/versions/20261007_0006_model_pricing.py`（已新增，前序 `20260925_0005`） | 新增 nullable pricing_json；迁移无旧数据回填，保留新字段回退 |
| `modules/runtime_catalog/domain/models.py::RuntimeModelCreate/Update/RuntimeModelCatalogItem` | PricingInput/PricingSnapshot 结构；PATCH 未传/null 语义 |
| `modules/runtime_catalog/application/ports.py::StoredRuntimeModel` | 添加安全 pricing 值 |
| `modules/runtime_catalog/infra/sqlalchemy/models.py::RuntimeCatalogModelRecord` 与 `repository.py::_to_runtime_model/create_configured_model/update_configured_model` | JSON 列、创建/更新/返回；不碰 model API key 存储 |
| `modules/runtime_catalog/application/service.py::_validated_model_values/_model_item/create_model/update_model/resolve_model_connection` | 价格归一化、版本生成、现有权限/审计与内部响应 |
| `modules/runtime_catalog/presentation/http.py` | 原有 model CRUD DTO，不加另一套价格路由 |
| `modules/runtime_gateway/application/usage.py`（新增） | Public/Runtime DTO 白名单和有限字段 |
| `modules/runtime_gateway/application/service.py` | `get_thread_run_usage/get_thread_usage`，复用 _load_thread/_thread_upstream |
| `modules/runtime_gateway/application/ports.py` 与 `adapters/langgraph/runtime_gateway_upstream.py` | 现有 upstream 增加两个 GET；HTTP等待不占 SQL 事务 |
| `modules/runtime_gateway/presentation/http.py` | 两个 GET、request_id、no-store、参数解析；只调用 service |
| `core/security/tokens.py`、Runtime `runtime/auth.py`、标准/fixture | operation 与隔离契约同步 |

## 任务拆分

| 状态/任务 | 预期结果与代码 | 最小验证 |
|---|---|---|
| [x] P03-1 价格模型/迁移 | pricing_json + Pydantic Input/Snapshot，空/旧库兼容 | SQLite/PG 迁移，null/不传、非法价、仅缓存 TTL 价 |
| [x] P03-2 CRUD/版本/权限 | CatalogService 归一化/UUID版本，平台/项目各自价格 | 既有 Model Catalog 测试 + BYOK 越权、同价幂等、清空重设、审计脱敏 |
| [x] P03-3 内部连接快照 | resolve_model_connection 与 fetch_model_connection 不丢 pricing | 引用签名/过期、动态换模、同名不同 catalog、多消费者类型/回归 |
| [x] P03-4 usage-read | 两端集合、Thread 约束、native whitelist | API 签发与 Runtime 交叉测试，所有兄弟操作互拒、当前撤权 |
| [x] P03-5 查询/投影 | Gateway GET 与 Runtime SQL 授权聚合 | 错归属、pagination 与总量独立、unknown/partial，坏 DTO/不可用 |
| [x] P03-6 文档与收尾 | JWT/网关活规范、FEATURES/CONTEXT 只按真实实现更新 | 专项相对链接、schema fixture 一致、无现役部署假声明 |

### P03-1 完成卡：价格模型/迁移

- **改动内容/预期：** 六费率 Decimal 字符串、nullable JSON；旧模型未配置，不回填零。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_catalog/domain/models.py`、`infra/sqlalchemy/models.py`、`apps/platform-api/migrations/versions/20261007_0006_model_pricing.py`。
- **验证项：** SQLite 空/旧迁移、PG 实际升级，非法价/未知字段/version 拒绝；price/migration 定向通过。
- **状态：** [x] 2026-10-07 开发和 Phase 完成。
- **合规检查：** [x] 实现；[x] 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（专项 Added）。

### P03-2 完成卡：CRUD/版本/权限

- **改动内容/预期：** 完整对象替换、同价版本幂等、null 清空；现有模型权限和安全审计复用。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py::_price_snapshot/create_model/update_model`、`presentation/http.py`、`modules/audit/http_resolution.py`。
- **验证项：** 目录、BYOK 越权、归一化/version、PATCH 三态、审计白名单；通过。
- **状态：** [x] 2026-10-07 开发和 Phase 完成。
- **合规检查：** [x] 实现；[x] 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（共用专项行）。

### P03-3 完成卡：内部连接快照

- **改动内容/预期：** 内部可信连接保留实际 catalog UUID 与完整价格，按模型调用冻结，不重算历史。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py::resolve_model_connection`、Runtime `runtime/modeling.py`。
- **验证项：** 短期引用与模型构造回归、不同模型身份；真实变价/清空/模型删除后旧金额不变；通过。
- **状态：** [x] 2026-10-07 开发和 Phase 完成。
- **合规检查：** [x] 实现；[x] 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（共用专项行）。

### P03-4 完成卡：usage-read

- **改动内容/预期：** 五字段 scope 保持，Thread 绑定；只允许两个 GET，native/模型/兄弟入口互拒。
- **代码位置：** `apps/platform-api/src/platform_api/core/security/tokens.py`、Runtime `runtime/auth.py/http/usage.py`、双端 fixture。
- **验证项：** API 签发/Runtime 校验独立进程矩阵、当前 ACL/服务账号凭据、原生 whitelist；通过。
- **状态：** [x] 2026-10-07 开发和 Phase 完成。
- **合规检查：** [x] 实现；[x] 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（共用专项行）。

### P03-5 完成卡：查询/投影

- **改动内容/预期：** Run/Thread GET、keyset 参数与 UTC 窗口、安全白名单；200 unavailable 与权限/协议/网络错误分开。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/usage.py/service.py`、`presentation/http.py`、`adapters/langgraph/runtime_gateway_upstream.py`。
- **验证项：** usage/pricing/route 定向 32 passed、305 subtests；真实 HTTP 总量、分页、缺价、错归属和故障通过。
- **状态：** [x] 2026-10-07 开发和 Phase 完成。
- **合规检查：** [x] 实现；[x] 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（共用专项行）。

### P03-6 完成卡：文档/冻结交接

- **改动内容/预期：** 同步 JWT/网关活规范、状态快照和用户变更；交付 actual schema、12 个状态与错误样本。
- **代码位置：** 本专题、04/05、`docs/standards/delegation-jwt.md`、网关标准、`fixtures/usage-v1.json`。
- **验证项：** Pydantic 验证全部 fixture，JSON schema 与当前类一致；规范 operation/route 与源码集合一致；专项文档检查。
- **状态：** [x] 2026-10-07 交付完成，统一静态复验在 Final 执行。
- **合规检查：** [x] 实现；[x] fixture 验证；[x] 本节状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（共用专项行）。

## 验证要求与记录

- 单元：Decimal/JSON、price version、PATCH/权限/审计、DTO 白名单、参数与 error envelope。
- 集成：真实短期连接、两端 JWT、Scoped PostgreSQL 汇总、清空/变价/模型删除后历史不变。
- E2E：API 提交两个 Run、多模型/子图/缓存后经 usage-read 查调用、Run 和 Thread，前后 totals 相等。
- 成本边界：不同费率、cache TTL、缺价、多模态/非线性、真实零与未知、多版本汇总。
- 已实施，Phase 与 Final 分开记录；供应商账单、前端浏览器和现役部署不在本轮证据范围。

测试落点：`apps/platform-api/tests/test_model_pricing.py`、`test_run_usage.py` 与既有 catalog/delegation/gateway inventory。沿仓库既有 pytest/fixture，不新增测试框架。

### Phase 验证记录（2026-10-07，6 项任务）

| Task | 已执行证据 |
|---|---|
| P03-1 | 价格/迁移/审计/用量定向 38 passed、6 subtests；真实 PG 前向升级和旧应用启动 |
| P03-2 | price/catalog 定向 30 passed；API pricing+inventory 19 passed、305 subtests；审计复验通过 |
| P03-3 | 内部引用/catalog 定向和 Runtime modeling；[HTTP 证据](fixtures/e2e-evidence.json) 验证变价/清价/模型删除 |
| P03-4 | Delegation 与 usage 17 passed、52 subtests；追加 route 矩阵 305 subtests，operation 按名称互拒 |
| P03-5 | usage/pricing/route 最新 32 passed、305 subtests；最新 16 项真实隔离 HTTP/Worker 链路 |
| P03-6 | [冻结 schema/fixtures](fixtures/usage-v1.json) 全部 Pydantic 校验，04 接口与实际 CRUD/GET 核对 |

使用服务既有 `$API_PYTHON -m pytest -q`，服务工作目录和 `PYTHONPATH=src`；各行集合有重叠，不累加。Final 全服务回归、文档/schema/质量门禁独立记录在 05。

## 状态

六项开发及 Phase/Final 完成，Platform 范围 done；新能力定向与真实链路通过，全量既有失败见 05。按批准方案落地单一 catalog 价格、完整快照、独立 usage-read 和独立 GET，前端已闭环，整项目 done。
