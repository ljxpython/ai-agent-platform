# F11 验证计划与记录

## 当前状态与证据口径

2026-10-10 用户确认暂缓 F11 开发（`deferred`）。评估与规划已完成；以下功能验证是未来参考，不属于本次交付，没有实施或开启批准。

本轮只做代码核查和规划文档。功能尚未实施，下面未来单元/集成/E2E均未执行；没有真实模型费用、没有启动服务、没有数据库/依赖改动。规划交付不等于功能 `done`。

验证按风险选取：重点在无Thread授权、旧消费者不回归、单次调用、草稿不丢失。无需用此按钮重跑所有业务Skill或创建新性能平台；受影响的安全调用者必须回归。

## 未来单元与组合测试

| ID | 位置（新增标明） | 必须断言 |
|---|---|---|
| U01 | API 新 `tests/test_runtime_gateway_input_polish.py` | 严格DTO、原始长度/空白/4000边界/emoji、未知字段、graph/Agent ID区分；关闭不调用provider |
| U02 | 同文件 + `test_runtime_thread_authorization.py` | project.runtime.execute、Agent/Graph active、Thread comment与graph一致；无Thread不创建Thread；缺默认模型拒绝 |
| U03 | `test_runtime_model_reference.py`（扩展） | purpose精确值、新用途HMAC、必须trusted Runtime、新/旧用途不能互兑、改签/过期/用途错/缺Thread普通引用拒绝；原Run/approve不回归 |
| U04 | API `test_runtime_delegation_contract.py`、`tests/fixtures/runtime_delegation_verifier.py`；Runtime `tests/runtime/test_auth.py` | 新operation按名称集合新增，不用枚举数量/索引；scope各维度/hash mismatch，旧operation继续严格校验 |
| U05 | Runtime 新 `tests/services/test_oneshot.py` + 现有 `test_suggestions.py` | 公共模型准备受管model/Context/ref；F11零环境凭据兜底；消费者只一次ainvoke、无bind_tools/agent；suggestions准备仍在timeout外，原`[]`/超时/JSON保持 |
| U06 | Runtime 新 `tests/services/test_input_polish.py` | 正常/原样、changed对原串计算；代码/think字面原样；slash/URL/路径保持；仅reasoning、toolcall、截断、空/超长结果拒绝；取消传播 |
| U07 | Runtime 新 `tests/http/test_input_polish.py` + `tests/runtime/test_platform_auth.py` | input-polish专属路由shape/scope；不访问native resources/其他内部入口；tenant/project/assistant/thread=None也精确匹配 |
| U08 | API `test_runtime_gateway_sdk_adapters.py`、`test_runtime_upstream_errors.py`、`test_error_response_contract.py` | adapter路径/headers、5xx/超时标准Envelope、精确安全码；不公开上游正文；授权拒绝不当成功 |
| U09 | API `test_audit_http_resolution.py`、`test_transaction_boundaries.py` | 动作/项目/主体定位，安全metadata字段；Session生命周期在同线程，远端等待不占事务；取消审计收尾 |
| U10 | `test_run_usage.py`、Runtime `tests/observability/`、相关usage fixture | input_polish明确排除，HTTP旁路不增加native Run ledger、不扣历史Run额度，现有numeric DTO保持 |
| U11 | Web 新 `input-polish/api.spec.ts` | 项目头/signal/字段、配置失败隐藏、identity缓存隔离、响应schema/changed/Unicode校验；POST不吞错 |
| U12 | Web 新 `composables/useInputPolish.spec.ts` | single-flight、generation、revision、ABA、切scope/模型/账号、KeepAlive隐藏、cancel、out-of-order、undo后续编辑失效 |
| U13 | `components/ChatComposer.spec.ts`、`composables/useChatSession.spec.ts`/接线测试 | 润色不触send/queue/resume/createThread；附件/PlanMode不变；运行/queue/review/stop/readonly禁用，IME与普通发送保留 |

provider异步等待、model init与兑换耗时都要用可控fake clock/task测整体预算；不能只mock返回值就宣称取消释放完成。应用层先拒绝的401/403/422与model failure分别计数。

## 真实集成测试

使用本Worktree注册资源。新增后端场景建议落在 `apps/platform-api/tests/integration/test_input_polish_chain.py`，只有显式测试开关和本环境配置时运行真实HTTP/provider；不得拿默认主库作为fixture。

- [ ] I01 有Thread：平台认证→ACL/模型→精确委托→Runtime→HMAC模型兑换→模型响应，核对project/graph/model及request/trace关联。
- [ ] I02 无Thread：新会话润色成功；平台Thread索引、Runtime threads/runs/checkpoints/inbox/workspace计数和文件hash不变；审计记录允许新增。
- [ ] I03 跨tenant/project、不同Thread/graph、未授权模型、私有BYOK另一项目、停用Agent/Graph均拒绝；provider请求计数为0。
- [ ] I04 服务账号/用户在请求准备后、模型引用兑换前撤权或停用，兑换拒绝；正常Run/suggestions引用缺Thread仍拒绝。
- [ ] I05 input-polish token逐个访问原生Run/Thread、title、suggestions、usage/diagnostics、Stop、workspace/terminal、memory/skills和capabilities；全部按既有拒绝边界，不触模型/工具。
- [ ] I06 模型/连接卡住、provider5xx/429/认证失败、finish_reason=length/仅思考/异常输出；超时有界、无业务重试，只有标准错误，日志不出现原文/凭据canary。
- [ ] I07 HTTP客户端断开/取消、旧响应迟到、并发不同用户；不出现后台自动补调用、请求串scope或遗留连接；不能据此承诺供应商不计费。
- [ ] I08 新增helper后真实suggestions仍返回合法数组并保持授权/空数组降级；标题和普通Run关键调用者未被用途引用误拦。

## 前端联合E2E

由同事与后端联合执行，路径建议 `apps/platform-web/e2e/input-polish.spec.ts`。

- [ ] E01 首条无Thread输入短中文→润色→检查草稿→undo；无Thread/Run创建；再手动发送只创建一次正常Run。
- [ ] E02 已有Thread润色→手动编辑→发送，附件仍在，PlanMode/AccessPolicy未变；原模型/工具审批行为保持。
- [ ] E03 单飞、loading/取消、失败toast、超时/网络/disabled；原文始终可发，502/504不登出。
- [ ] E04 等待时编辑A→B→A、完成后编辑R→S→R，旧回写和旧undo均不能生效。
- [ ] E05 切Thread/Agent/project/账号/model、后台KeepAlive与document隐藏；旧响应不覆盖，切回不自动重试。
- [ ] E06 运行/queue/计划待审/HITL/Stop/readonly禁用本动作；原审批、补充消息与停止仍正常。
- [ ] E07 4000/4001字符、emoji、全空白、短中文、代码/fence/think字面、slash/URL/路径；前后端一致，原样保护不丢内容。
- [ ] E08 360/390/768/1440、双主题、focus/compact、键盘/IME/a11y；没有tool区域重排、文字重叠、被遮挡发送/停止。
- [ ] E09 配置关闭→旧页面请求404并隐藏，普通发送正常；配套源码/配置回退，已在途请求有界完成，无数据清除。

至少E01/E02需真实受管模型；故障/竞态用确定性HTTP注入补充，不能全部mock后称真实链路验收。当前项目没有承诺供应商模型语义保真100%。

## 保真质量样例门禁

后续新增 `fixtures/polish-quality.json`，至少20份匿名样例，覆盖中文/英文/混合、短指令、已清晰指令、禁止执行/不可删除/暂不改库、日期/数值、URL/路径/前缀、代码/标签和prompt injection。禁止纳入真实秘密或用户原始私有材料。

- [ ] Q01 保护项：slash/URL/路径/代码/think字面零被接受的破坏；长度截断/多余toolcall应失败，不作为正常rewrite。
- [ ] Q02 意图：人工逐条检查“只分析不实施”、否定词、范围、量化约束，零被接受的关键反转/添事实。明显模糊任务不凭空补业务需求。
- [ ] Q03 收益：标记为自然语言模糊且可润色的样例中，至少80%被人工评为更清楚且无需补救；已清晰与保护样例允许changed=false。这是拟议验收门槛，批准前可调整，不是假测量。

规则只保护可识别片段，不能证明所有实体或语义一致；人工质量结果应留原样例ID、结果、评价和prompt/model版本。高风险效果不合格继续关闭，不用换个指标宣布通过。

## 性能、费用、取消与回退

- [ ] 执行20次短文本顺序样例记录冷/热构造、兑换、模型和总耗时p50/p95、失败率、输入/输出长度与可得token数据。建议正常短文本p95≤8秒；未达到先保持关闭或重新评审，不扩大timeout掩盖问题。
- [ ] Runtime总预算包含模型连接兑换与推理，8秒故障注入在8秒+1秒调度/HTTP余量内返回；同步构造阻塞不能以async timeout测试冒充已限制。
- [ ] 一个点击一次provider尝试，无SDK隐藏重试；原样保护零调用。认证401刷新只在平台未受理前允许，不加业务重发。
- [ ] 多用户并发不串scope；本请求取消后自有task/连接有界释放，HTTP abort不冒充provider未计费。
- [ ] 部署入口按可信身份/项目限频/并发、请求body限制和供应商费用/额度控制有直接HTTP证据；本地按钮single-flight不能替代。缺环境只完成独立验证，生产开关保持false。
- [ ] 关闭API开关、停止新委托签发、等待在途结束、恢复配套源码后，普通Run/suggestions依旧正常；无迁移/数据删除回退。

## 后续执行命令

以下是实施后的执行参考，不是本轮已执行记录。文档命令按仓库规则不加rtk；真实执行时再加。先按 [Worktree规范](../../standards/worktree-development.md) 初始化和安装本环境依赖。

```bash
# API定向，工作目录 apps/platform-api
uv run pytest "tests/test_runtime_gateway_input_polish.py" "tests/test_runtime_model_reference.py" "tests/test_runtime_gateway_suggestions.py" "tests/test_runtime_delegation_contract.py" "tests/test_audit_http_resolution.py" "tests/test_transaction_boundaries.py" "tests/test_run_usage.py" -q
uv run ruff check "src/platform_api" "tests"

# Runtime定向，工作目录 apps/runtime-service
uv run pytest "tests/services/test_oneshot.py" "tests/services/test_input_polish.py" "tests/http/test_input_polish.py" "tests/services/test_suggestions.py" "tests/http/test_suggestions.py" "tests/runtime/test_auth.py" "tests/runtime/test_platform_auth.py" "tests/runtime/test_modeling.py" -q
uv run ruff check "src/runtime_service" "tests"

# 前端同事，仓库根目录
pnpm --dir "apps/platform-web" test:run "src/modules/chat/input-polish/api.spec.ts" "src/modules/chat/composables/useInputPolish.spec.ts" "src/modules/chat/components/ChatComposer.spec.ts" "src/modules/chat/composables/useChatSession.spec.ts"
pnpm --dir "apps/platform-web" lint
pnpm --dir "apps/platform-web" typecheck
pnpm --dir "apps/platform-web" build
pnpm --dir "apps/platform-web" test:e2e "e2e/input-polish.spec.ts"

# 文档
python3 "scripts/check_docs.py"
git diff --check
```

Final对每个服务执行一次完整单测（API/Runtime `uv run pytest -q`，Web `pnpm test:run`）以及上述关键集成/E2E；只有新修改/失败或未解决疑点才重复扩大测试。新集成runner需先定义本环境开关/数据契约再执行，不能复制历史固定/tmp runner。

## 本轮规划验证记录：2026-10-10

### 已执行核查

- 当前平台初始 `git status --short` 干净；HEAD `2f08c5462571cd0244a7181e5d0d1388341b79c4`。
- 阅读CONTEXT、Worktree规范、三服务规范入口、JWT/错误/trace标准、对应经验及现有DearFlow/推荐问题专项；核查真实suggestions、模型引用/兑换、operation枚举、Usage排除、composer/send调用点。
- DeerFlow/Open-SWE本地源码只读搜索；未运行其服务或测试。Open-SWE“未找到F11”限定在本轮所读本地树；两参考树都有本地修改，Open-SWE存在合并状态。
- docs MCP明确支持standalone模型调用；reference MCP search返回ainvoke文档链接，get_symbol两种路径未找到详细符号。本轮未依据此编写API代码。
- `python3 scripts/check_docs.py` 在文档改动前执行失败：38条既有绝对路径违规，分布在9份已有文档；本轮不修改无关历史资料。变更后的定向文档与链接检查见下方收尾记录。
- 权限差异：代码与前端均区分project.runtime.execute与project.runtime.write，现有权限标准仅写read/write概括；新规划以代码当前execute路径为事实基准。另有既有title/capabilities入口对自定义operation限制不完整，与JWT标准的仅限专属路由意图不一致。仅登记review G6，未修代码/标准，等待人工评审。

### 关键参考文件SHA256

相对DeerFlow仓库根；用于识别本地参考取样，不等于发行版安全/兼容证明。

| 文件 | SHA256 |
|---|---|
| `backend/app/gateway/routers/input_polish.py` | `8615ee0871d4961ddc1a4a7137d97acdff4418185d794e163a635d2d1a4ff146` |
| `backend/packages/harness/deerflow/utils/oneshot_llm.py` | `b0322eeefdb7feebbbc307f809bdf913f4d0b20f74aa2e28438221f295b79c48` |
| `backend/packages/harness/deerflow/config/input_polish_config.py` | `92b81377d8864250df98e1c9feae02e0f5fa417efdd81f58a3df970de596b2f7` |
| `frontend/src/core/input-polish/api.ts` | `e635b6bcab40757d8e2ed490239e047a02b225c09f4658983b0204b50a3f99d5` |
| `frontend/src/components/workspace/input-box-helpers.ts` | `c8b9aff7bfaa2c18278e8f17f65d1f301308ae75cf21eadaa95170bad4d6e543` |

### 文档收尾记录

- `git status --short --untracked-files=all`：仅修改 CONTEXT/FEATURES，新增本目录7份文档；没有业务源码、配置、依赖、标准或数据库改动。
- `git diff --check`：通过；该命令不覆盖未跟踪文件，另用只读 Node 检查补齐新文档的行尾空白、冲突标记、终末换行、代码 fence 配对和本机绝对路径检查，全部通过。
- 定向本地链接检查：7份文档及 CONTEXT/FEATURES 本次新增行共21个本地文件链接有效。只核对文件存在，未验证外链可达性、所有锚点或 Mermaid 渲染。
- 功能总览表头检查：补齐 Web/Runtime 两处原有缺失分隔线，并将 API 的 F11 行放在分隔线之后；三服务表头检查通过。任务状态检查通过：P01～P04完成，未来评审/实施/联合验收未勾选。
- 复核内部 DTO、模型默认值合并及 suggestions 超时边界后，将公共复用收紧为模型准备段；调用、输出解析与失败行为归各消费者，避免抽取改变旧推荐问题语义。
- `python3 scripts/check_docs.py`：变更后仍失败，38条既有绝对路径违规、9份旧文档，与改动前一致；本轮新增目录无违规。保留这个既有全仓门禁问题，不宣称全仓文档检查通过。
- 本轮规划交付完成。业务单测、真实HTTP、供应商模型、浏览器E2E、性能与取消行为均未执行；这是规划范围，不作为功能验收或实施批准。

### 用户确认暂缓后的文档验证：2026-10-10

- 用户确认暂缓，G01记录完成；实施方案未批准，G02及Phase 2～4全部后置。原始候选条目与DearFlow总纲加入决策链接，防止旧候选描述被当作实施授权。
- `git diff --check`通过；7份专项文档及4份现有入口文档的本次链接共24个有效。专项文件无尾随空白/冲突标记/本机绝对路径，代码围栏和换行检查通过；P01～P04与G01完成，所有实施任务未勾选。
- 目标分支工作区初始干净，HEAD `01f2e8eb3e3d4d6fb1d321af745a4491e8ee706a`，与远端同步；保留其F15决策。目标基线的全仓文档检查失败为40条既有绝对路径问题、10份旧文件，比核查基线多2条F15旧问题，不归入本次新增违规。
- 当前Worktree为detached HEAD，没有独立功能分支。资源登记和目录检查均未发现本环境；按规范尝试`local-stack.sh stop`明确返回未初始化，未启动/停止任何服务，也未删除数据库或其他Worktree资源。
- 将文档提交cherry-pick到`feat/langgraph-v3-delta-evaluation`；仅CONTEXT的摘要冲突人工合并，保留F11/F15双方决定。对照目标HEAD确认F15评估、交接文件内容未变，DearFlow总纲原有内容全部保留。
- 合入后定向检查通过：7份专项、24个本地链接、任务暂缓状态、无冲突标记；`git diff --cached --check`通过。全仓文档检查仍为同一组40条/10份既有问题（忽略插入导致的行号位移），没有新增违规。最终变更均为文档，未跑业务测试或模型。

## Phase功能验证记录（未来）

尚未执行。后续逐Phase记录具体命令、通过/失败、修复与仍未完成项；不得写入下面Final区。

## Final功能验证记录（未来）

当前不适用：用户确认暂缓，功能状态为 `deferred`，没有功能验收结果。未来重新投入并实施完成后才记录真实联合结果和 `done/partial/blocked/deferred` 结论；本轮不调用verify-change，也不宣布任何功能验收通过。
