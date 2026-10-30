# Open SWE 方向的最小委派实现

2026-10-30。用户明确批准删除不必要代码、恢复简洁实现并复用 Open SWE/官方 SDK。本次是当前简化方向的实施与验证，不改写旧组失败。

## 实现

- 删除 5 个自研 Runtime 模块：`middleware/synthesis.py`、`subagents/code_explorer.py`、`subagents/report.py`、`subagents/source_context.py`、`subagents/source_quotes.py`，以及 6 个专属测试/夹具。以隔离栈删除前备份计，分别为 973 行实现与 1,720 行测试；这些文件原未跟踪，Git diff 不显示为 tracked deletion。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` 仅声明一个只读 `general-purpose`。复用已安装 DeepAgents 的 task 执行、隔离状态与普通文本回传，保留现有三路 semaphore；不再覆盖 SDK task 描述或定义新的报告/合成协议。
- 子任务装配现有 `search_web/fetch_page/github_query` 和 `ls/read_file/glob/grep`。同步 RuntimeConfig 可用工具集合与 PlanMode 只读实例，项目工具授权仍生效。没有写入、执行、产物发布、嵌套 task 工具。
- 主提示词、researcher 声明、工具错误处理及预算/容灾/PII/工具输出测试改为普通文本交接；保留已存在的共享预算、Usage、PII、取消、并发、循环停止隔离和工具输出边界。子模型调用上限恢复既有 24，预警 5。
- 先搜索全部调用方，再清理专属测试；其他预算投影、上下文工具治理、GitHub 有界读取与本地栈修改保留。未增加依赖、公共 API、数据库表或调度器。

## 复用边界

参考库 `/Users/lijiaxin/PyCharmMiscProject/research/open-swe` 已 fetch 到 `241c74b8f306c270c428f708e469572f511329fe`。参考工作树有本地内容与分叉，未 checkout/pull 覆盖；最新源码通过 `git show FETCH_HEAD:...` 核对。

旧布局 `agent/chat.py:_chat_general_purpose_subagent()`（87–104 行）通过同名声明替换默认通用角色，并使用只读文件工具白名单。最新 `openswe/server.py`（2240–2254 行）同样只装配一个通用子角色与既有工具。平台直接复用二者共用的官方 SDK 执行器，保留自身 Runtime 鉴权和中间件；未逐字复制 Open SWE 的应用组合根、异步 Worker 或 Anthropic 缓存适配。Open SWE 最新依赖与本平台版本不同，不能宣称整套移植。

## 已执行验证

1. 真实 compiled graph 工具回归：修改前 `ls/glob/grep/github_query` 四项报 `runtime.tool.not_allowed`，`read_file` 通过；修正后三个目录工具、读取与 GitHub 五项全部通过。断言来自实际子 namespace 的成功 ToolMessage。
2. DearFlow 主图/研究/子任务/共享预算/错误隔离、模型韧性、PII、工具输出与 pruning 组合：**275 passed / 12 skipped / 56 warnings，85.27s**。跳过项包括显式门控的外部环境测试，不计为通过。
3. Ruff 与 `git diff --check` 通过；Runtime src/tests 中旧报告模块与类引用零匹配。
4. 精确同步所属 Worktree 的 7 份 Runtime 文件与 11 份关联测试/夹具，删除 5 份旧实现与 6 份旧测试；删除前备份和 SHA256 清单在 `.local-stack/open-swe-simplification-{backup,sync.json}`。未覆盖其他差异。
5. 仅通过所属 `scripts/local-stack.sh restart-one` 重启 Runtime Worker/API；五服务 running、Runtime ready 与 API 健康。Web `http://127.0.0.1:29201`，环境 `wt_bf33bcf838fd`，backend=local，未启动 Docker。
6. 主提示词改为仅对缺口、冲突和关键条件定向复核，不再无条件重读子级来源。该句后的最短回归 **53 passed / 2 skipped / 27 warnings，54.57s**；不与前述275项相加。
7. 第二次真实烟测暴露官方 `ToolCallLimitExceededError` 未被只读 task 错误边界接住。在共享 `tools/errors.py:on_tool_error()` 原有模型额度分支中增加这一官方异常类型；未改24次子模型/48次子工具上限、父级额度、白名单或预算策略。调用方 DearFlow/Showcase 均由各自只读角色白名单约束，reference_agent 不获得该隔离能力。
8. 在既有分类与真实组合测试中先复现 **3 failed / 17 passed**，修复后 **20 passed**；另加一个并行组合用例证明兄弟证据仍保留，额度组合 **5 passed**。主级超额、无只读角色、非task、权限/PII/取消/全局预算和未知异常继续传播。最新完整相关回归 **282 passed / 12 skipped / 60 warnings，92.73s**；JUnit在所属栈 `.local-stack/open-swe-final-regression.xml`，Ruff/diff通过。
9. 三文件精确备份/同步记录在 `.local-stack/open-swe-tool-limit-isolation-sync.json`，所属 Runtime Worker/API已再次重启；没有改数据库、启动Docker或触及其他栈。

定向命令（在 `apps/runtime-service`）：

```bash
uv run --no-sync pytest tests/services/dearflow_agent/test_agent.py tests/services/dearflow_agent/test_research.py tests/services/dearflow_agent/test_subagents.py tests/services/dearflow_agent/test_delegation_budget.py tests/services/dearflow_agent/test_tool_errors.py tests/services/dearflow_agent/skills/test_research_batch.py tests/services/test_model_resilience_composition.py tests/services/test_pii_composition.py tests/tools/test_tool_errors.py tests/middlewares/test_runtime_middleware.py tests/middlewares/test_tool_output_budget.py tests/middlewares/test_tool_output_pruning.py tests/e2e/test_tool_output_budget.py -q --tb=short
```

## 正式路径真实烟测

首个调用前登记 `.local-stack/open-swe-smoke-registration.json`，固定公开 DSH SHA `477b4f420553e8a52c2fbccc464d7561b239c443`，xiaok `deepseek-v4.1-flash`、Pro、输出 8192。研究三个方向与原题一致，但角色名改为 general-purpose、去掉提示词 Markdown 反引号；本轮是独立烟测，不是旧冻结组的补样或同配置对照。

- Thread：`cb83745b-d181-437b-89b6-01ea673e7d52`。
- Run：`289dd589-55f2-424a-8ed1-e38f540cb088`。
- 终态 success，244.08秒，三个真实 general-purpose 均完成；Usage24/24完整且finalized，总463,322 Token。主10调用、累计输入276,183、单次峰38,495；子14调用、累计输入153,051、峰25,078。价格未知，不据低上下文占用宣称费用下降。
- 报告语义存在缺陷：触发公式漏headroom，retain合法不等式写反，六类provider与一个driver混为七类，历史摘要/循环外可选能力限定表达不充分。该次不算语义质量通过；原始报告未人工修正。
- 用量中未见summarization purpose、所属日志未观测摘要；root完整回放未取得，不写成精确0次。
- 正式 Web 提交，API 查询 Run/Usage，子工具通过正式 SSE 订阅采集；不在辅助脚本生成或替换模型报告。

第二次使用定向复核提示词，登记及终态在 `.local-stack/open-swe-targeted-smoke-{registration,result}.json`：

- Thread `a3603072-72d2-42a1-9f56-f0bd6307ed7c`，Run `50724e63-eb84-4adb-a427-593b9cf537ed`，188.67秒，error。
- 三子启动，两子完成、一子因48次工具上限失败，异常穿透父task导致无最终交付。该失败是第7项最小修复的直接证据，保留而不替补。
- 主4调用、峰16,743；子26调用。虽30/30有Usage，账本collection_degraded且未finalized，完整总量未知；已知和521,258 Token只能记为已知量。
- 采集中的 `sse` 含首轮残留，不能当作本Run根事件；仅 `sourceSse` 的本Run子事件可作来源/lifecycle证据。终态后主动中止订阅不等于Run被取消。

最小修复后第三次正式独立烟测已终态：

- Thread `2cacf20e-32c5-49d1-849c-4e622635cf6d`，Run `34e206f3-df16-4f12-af74-2d6735c238f1`。
- `.local-stack/open-swe-tool-limit-smoke-registration.json` 在提交前记录当前源码/配置hash与282项回归；模型、输出、原题沿用第二次，唯一本次行为修复是子工具额度错误隔离。
- success，349.11秒，三个真实 general-purpose 均完成。37/37 Usage完整、available/finalized、missing/incomplete均0，未降级；主10次调用，累计输入277,207，单次峰50,313/131,072（38.4%）；子27次调用，累计输入569,347、峰56,434。全Run输入846,554、输出48,152，总894,706 Token，cache_read456,320；价格未知。
- 贯穿root running→completed的捕获保留全部custom事件，未观测到offloading，故本轮root自动整理观测值0。订阅在终态后主动关闭，transport complete=false不能当作Run取消或未完成。
- 70份来源（57子、13父）的固定SHA、原文hash、真实Git内容及README目录校验通过；59个读取窗口对应87个可解析引用，86个已观察，另一个为报告明确标记未读的范围。7处缩写仍有歧义，不能宣称全部引用通过。原始来源/引用/事件审计保存在 `.local-stack/open-swe-tool-limit-smoke-result.json.{sources,citation-windows}.json` 和 `open-swe-tool-limit-smoke-events-audit.json`。
- 原五项核心语义按最终正文核对为4/5：包组织、默认compaction与历史摘要、触发/剪枝/溢出重试、提供方与父级发现有覆盖；未陈述subagent是agent loop之外的可选能力，第4项失败，不以子报告或引用内容补分。附加表格把已经列出的image-offload包名又列为未知，也保留为质量局限。
- 最终正文13,228字符，finish_reason=length，附加建议末句被8192输出上限截断；todos仍为0/3。原始报告和截图 `open-swe-tool-limit-smoke-{report.md,final.png}` 均保留，不能仅因Run success把交付完整性写成通过。

针对收尾问题只在现有 `prompts.py` 增加两项通用说明：随进展如实更新todos；答复合并重复、仅覆盖用户所问、来源用仓库根起的完整路径并完整收尾。没有加入本题答案、路径或报告协议；没有增加模型调用额度、状态机或审稿模型。备份与精确同步记录在 `.local-stack/open-swe-concise-answer-sync.json`，prompts SHA256为 `b516558c60440d9d7d1ed9e133d95d7fd92afb70cc65ca4695add61c802367f7`，所属Runtime Worker/API已依次重启。

扩大相关回归27文件：首次 **560 passed / 13 skipped / 1 failed / 60 warnings，143.92s**，失败为既有Showcase真实执行测试默认选择Docker，当前本地栈没有Docker服务；相同默认配置单独复现仍失败。显式 `RUNTIME_BACKEND=local` 单独复验该项 **1 passed / 5 warnings，5.87s**，未改业务代码或放宽断言。首次失败与两次复验日志/JUnit分别保存在 `.local-stack/open-swe-{simplified-final-regression,showcase-execution-recheck,local-execution-recheck}.{log,xml}`；不能把不同环境结果写成一次全绿，13个skip不算通过。

第四次仅验证上述通用交付提示，调用前登记 `.local-stack/open-swe-concise-smoke-registration.json`，源码/配置清单hash `9390404e8a6c276c21c823e82f31843374c059f1e03ccd4cfcb7af245ea8358f`。正式Web新建Thread `1ccc5abf-0043-402e-aa1d-ac2694a22131`，Run `9856913c-d061-4b76-8adc-4e4cf4e61da1`，沿用xiaok/Pro/8192及原三方向任务。本次独立烟测不替补前三次，不混入旧冻结统计组。

- success，226.27秒，三个真实 general-purpose 均完成。28/28 Usage完整、available/finalized、missing/incomplete均0，未降级，`token_budget=null`。主7次调用，累计输入191,773，单次峰40,707/131,072（31.1%）；子21次调用，累计输入269,416、峰32,600。全Run输入461,189、输出36,642，总497,831 Token，cache_read255,232；价格未知。
- root事件选取完整running→completed的 `sse[7]`，过滤器未过滤custom，未观测offloading事件，本轮root自动整理观测值0；不叠加重复hook捕获。终态后的主动关闭不视为Run取消。
- 52份来源（43子、9父）的固定SHA、原文hash、Git原文及README目录校验通过。36个读取窗口、74个可解析行引用中73个处于已读窗口；另1个是正文明确标为未读的 `subagent/package.json#L111`，不是支持结论的证据。缩写路径歧义0，不将“未读”范围计为已核验引用。
- 最终正文12,725字符，`finish_reason=stop`，已完整收尾并由浏览器截图复核；页面按既有规则折叠长内容，可展开全文。没有创建todos、没有write_todos调用，不能声称“待办跟踪已验证通过”。
- 按原五项逐项检查最终正文的完整语义覆盖为 **3/5**：第1项包职责、第2项默认压缩/早期历史、第3项触发/剪枝/规范溢出及generation重试有覆盖；第4项没有明确说明agent loop之外的可选能力，第5项有fresh/fork/外部provider，但未明确父级可发现其子级。只读来源真实不能替代结论完整性。
- 报告自述方向二/三为11/16次调用，当前Run工具事件实际为12/18次，方向一14次也超过建议约8次；模型自述不是计数事实。各子仍在原48次硬工具上限内。本轮不加新计数框架或为原题硬编码提示。
- 原始结果、正文、截图、来源、引用与事件审计分别为所属栈 `.local-stack/open-swe-concise-smoke-result.json`、`open-swe-concise-smoke-report.md`、`open-swe-concise-smoke-final.png`、`open-swe-concise-smoke-result.json.{sources,citation-windows}.json` 和 `open-swe-concise-smoke-events-audit.json`。

当前简化实现、相关工程验证与服务交接完成；原语义稳定性门槛未达到，跨任务泛化、费用收益和25%同质量降幅没有新证据。停止追加样本凑通过，将这些局限交给人工验收，不恢复自研报告协议。

## 回退与限制

本次未改依赖/数据结构。若验收异常，可用隔离栈精确备份恢复本轮文件、撤回同名角色装配并重启所属 Runtime；不回滚数据库或删除历史 Run。未执行 Git 提交/推送或共享环境部署。

一次烟测不能证明稳定质量、跨模型效果、成本下降或 25% 同质量输入降幅；旧失败保留。截图 49% 是上下文占用，不是固定验收值。
