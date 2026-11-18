# 真实排障复盘后的取证补强

2026-11-17，关联T21–T25。用户批准现有助手的最小补强及当前主环境实施；不新增助手架构、Shell、全库访问、业务写工具或执行沙箱。

## 用户问题与事实边界

原会话在Agent评测项目调查11月13日失败Run，助手把review策略猜成用户未审批，把当前not_configured推断为故障时未采集，又在数据库可读目录为空时泛化为平台没有数据库。只读核对发现仍有持久checkpoint可用，因此不能宣布证据已经用尽。

目标Thread为`4385c902-bc3c-4575-ad0f-36c6b7f22368`，Run为`7bf743f7-786d-40dd-8ab7-871d4564e475`。运行发生于2026-11-13 06:56:59–06:57:11 UTC，即北京时间14:56:59–14:57:11。故障包和本次读取时间不代表故障时间。

原Run仅在本机只读核对，没有重跑或把原对话外发给模型。真实模型回归使用独立合成项目、Thread、Run、日志和脱敏失败形状。

## 最小实现与调用者

- API新增`modules/platform_assistant/diagnostics.py`，复用目标授权网关的history读取，按Run过滤limit=1后再次核对metadata.run_id。最多20任务/中断、200条消息类型计数；不透传异常正文、消息正文、审批参数或堆栈。截断时不能断言没有审批；最新checkpoint不代表完整历史。
- 现有`service.py`组合最终Run状态、追踪与持久状态。追踪5xx时仍可读状态，401/403不绕过；移除助手不需要的observation_id，避免把观测编号当失败节点。当前查询端、历史采集未知、平台执行请求与本次诊断请求分别标注。
- 现有`logs.py`按已验证Trace、执行请求编号或Run选择候选，逐条核对目标项目、Thread、Run、时间和当前权限。保留100条/64KB/每文件尾512KB边界；缺源、空结果与部分覆盖分开，retention固定unknown。旧Trace入口未放宽。
- 每轮authorize回调返回当前可读能力摘要，数据库空目录明确no_readable_sources且不含系统数据库；日志只给服务别名，源码独立授权，Shell仍不可用。Runtime沿原模型边界刷新，不污染原请求。
- Runtime提示和工具说明约束事实、未知项与最少下一步，追问重读并只引用本轮完整证据编号；不从review、空错误数组、泛化错误或not_configured排除原因，不编造配置开关或日志保留期。
- Web沿既有证据抽屉显示失败任务与审批摘要；追踪未配置仍可展示持久状态。日志0条不再显示“已命中”，来源不可用单独提示；同步证据类型及组件测试。

没有改共享LangGraph适配器、JWT/SSE协议、模型凭据、业务数据库结构或同事其他专项代码。

## 阶段验证与失败修正

### 确定性与集成

各服务使用自身.venv/依赖。最终结果：

| 验证 | 操作与观察 |
|---|---|
| API相关四文件 | 96 passed / 26.09秒。包括目标绑定、状态/追踪独立失败、超时、截断审批未知、撤目标成员后拒绝日志回退、碰撞/跨项目/时间过滤、来源与能力语义 |
| Runtime助手/签名HTTP链/R0 | 24 passed。真实签名HTTP工具调用独立合成API及SQLite，覆盖跨项目授权、持久失败、执行请求回退和空目录；模型工具循环为确定性夹具，不冒充真实模型 |
| Web证据抽屉 | 5 passed；同一回归内覆盖状态可读、空日志和来源不可用，组件测试使用原生抽屉stub，不冒充浏览器实测 |
| 类型与静态 | vue-tsc --noEmit退出0；本轮指定Python文件Ruff及前端三文件Prettier检查通过 |

复验命令：

```bash
# apps/platform-api
.venv/bin/python -m pytest tests/test_platform_assistant.py tests/test_platform_assistant_diagnostics.py tests/test_observability_api.py tests/test_run_diagnostics.py -q

# apps/runtime-service
.venv/bin/python -m pytest tests/test_platform_assistant.py tests/test_platform_assistant_diagnostics_chain.py tests/test_r0_baseline.py -q

# apps/platform-web
pnpm exec vitest run src/modules/platform-assistant/components/EvidenceDetailDrawer.spec.ts
pnpm exec vue-tsc --noEmit
```

新增capabilities曾使旧authorize响应全等断言失败，按预期新增契约更新后通过；模型边界断言也曾把说明文字中的not_checked当成旧JSON值，改为精确字段检查。未删除原测试覆盖。Python保留SWIG及langchain-community弃用警告，没有升级依赖压警告。原T12–T20扩大回归的既有Thread ACL断言失败仍按旧证据保留，本轮不称全仓通过。

### 真实模型多轮回答

沿既有模型catalog只读取配置，未新增或修改连接。首选maomaoai连接返回403 insufficient_user_quota；换用原助手最近实际使用的xiaok连接，模型仍为deepseek-v4.1-flash。凭据仅经私有管道交给夹具，不进入日志、文档或Git。

本地证据目录为`.local-stack/assistant-diagnostics-20261117-live-{1..5}/`：

- live-1接入失败，不计模型质量通过。
- live-2第三轮复用了旧引用；前两轮也较冗长。
- live-3机械断言通过，答案复核仍发现“不是模型失败”、把graph-1当节点、推断超出日志保留期、把平台请求编号交供应商查询等错误，因此不计质量通过。
- live-4精简投影/提示后核心事实改善，但仍有偏向改模型配置的建议，第二轮又复用旧指南引用；按失败保留。
- live-5最终四轮通过，1 passed / 65.88秒，11个工具结果。已逐轮核对失败阶段/继续追问/当前资料/请求编号回退，答案引用均来自本轮，未调用项目全量日志或公开搜索，未输出合成秘密。

最终答案能确认技能准备失败、底层根因未知；空中断仅限当前checkpoint，review不是审批结果，not_configured只描述当前查询端，空可读库目录不表示平台无系统库，保留期未知不能说已过期。请求回退命中模型受限事件时，不推定欠费，也不把平台执行编号当供应商编号。下一步指向已验证Run、时间和失败任务的原始异常，不让用户重新提交已有诊断包或直接重跑。有限样例仍有冗长表达，不构成所有回答正确的保证。

### 本地生效与原Run复核

只修改Git忽略的`apps/platform-api/.env`中`PLATFORM_API_ASSISTANT_LOG_FILES`，固定别名platform-api/runtime-api/runtime-worker指向本仓对应日志。不暴露物理路径给模型，不改用户权限、受管模型或业务库。API使用既有自动重载；没有执行自带迁移的platform-api restart-one。

确认Runtime数据库pending/running为0后，使用现有local-stack分别重载runtime-api和runtime-worker；最终API于19秒ready，Worker启动成功，主栈Web3000/API2142/Runtime8123均运行。脚本显示的docker是原有执行后端，没有新增或切换Docker方案。

重载后的首次状态断言失败，未保存当次响应，不能确定该次原因。后续保存的三次复核有两次明确state_query_timeout：原3秒总上限包含当前ACL和上游读取，在当前环境过紧。仅把此有界等待改为8秒，仍小于工具15秒超时；增加超时来源独立返回的回归。没有加自动重试、放宽权限或取消超时。

修后连续三次诊断请求为3.102、3.346、2.576秒，均读回checkpoint `1f1df2f6-cf25-631e-8001-e8cf50cded35`，失败任务`ExecutionSkillsMiddleware.before_agent`、错误码`runtime.execution_failed`，当前checkpoint中断为空。原失败响应复核记录保留于`.local-stack/assistant-diagnostics-20261117-current-final.json`；最终成功响应与计时在`assistant-diagnostics-20261117-current-verified.json`。

同一正式本地API返回当前追踪disabled/not_configured；固定日志按Run和2026-11-13T06:51:59.162592+00:00至07:02:11.116265+00:00窗口查询，结果empty/0条、retention=unknown。当前可读数据库目录为空，三个日志服务别名可见。部分Runtime日志缺项目关联时仍会被过滤，没有为提高命中率放宽授权。

## 本轮结论与限制

本轮已完成获准开发和本地技术验收，R01–R05对应结果见verification独立Final。当前只能定位原Run失败阶段，不能恢复未取得的底层异常；固定日志有界读取不能保证覆盖旧故障。

没有本轮Git提交、分支、推送、迁移或生产部署；真实Loki、生产采集/容量、独立盲测及新增证据状态的真实浏览器复验未做。旧浏览器链与旧Final仍只适用于原范围，不用来冒充本轮新增状态验收。

最终静态回读确认T01–T25连续唯一、25项done且没有未勾选子项；本次七份项目说明中的36个相对链接存在。七份说明与16个相关源码/测试文件的密钥/私钥模式检查为0；限定文件git diff --check、冲突标记及尾空白检查通过。16文件最终SHA256清单保存在`.local-stack/assistant-diagnostics-20261117-final-manifest.json`，未包含.env或模型凭据。任务、README、独立Final、CONTEXT与FEATURES结论已核对一致，CHANGELOG和追踪规范导航同步；JWT/SSE原草案不因本项目完成而毕业。
