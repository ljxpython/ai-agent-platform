# 探索角色约束澄清与DeepSeek Pro独立正式检查

2026-10-29，T5.3/T5.7/T5.8，用户持续开发与模型测试授权范围内。

## 已知失败与最小修正

54号两次独立模型诊断共2次实际调用：maomaoai/deepseek-v4-pro结构化成功但仍全部include、无新增，xiaok/deepseek-v4.1-flash返回纯正文而非要求的Schema，均未解决固定材料问题。全部结果保留；不据此证明供应商因果或选择成功样本。逐句核对候选未接入应用。

`apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents/code_explorer.py`仅澄清：自身只读/上下文等执行约束不能当成目标仓库事实；conditions每句也需同引用支持，无依据的比较或否定省略。修正其旧“excerpt带引用”措辞，与现有Schema“excerpt只含原句、引用在sources”一致。没有目标仓库路径/评分事实，没有新增字段、工具或额度。专项88 passed/1 skipped/13 warnings（68.14秒）、Ruff通过；所属`.local-stack/v45-role-scope-green.log`。源码hash核对后同步主目录，证明`v45-source-integration-result.json`；Runtime API/Worker重启后再正式运行。

## 独立正式检查预登记

一次新Thread，通过正式Web→API→Runtime发送原题。使用已配置maomaoai/deepseek-v4-pro，model ID `46cd9fd7-4ddb-43b4-8d2b-fcb7f8c5035c`，目录窗口1,000,000、输出8192；供应商部署真实窗口未知，报告绝对输入，不将较大目录分母当成应用优化收益。原SHA/题/五项评分、主50/子16/三并发/工具100、原文和报告上限、费用限额关闭/Usage开启不变。

首次发送前冻结`.local-stack/v45-pro-smoke-21-manifest.json`，采集器`collect-v45-pro-smoke.py`，原题从旧UI脚本逐字复用，仅选择模型不同。属于模型/角色兼容性独立检查，不替补v42、不算正式六次，不混算模型或实现。全部终态保留；仅原质量完整通过后登记新同配置两臂六次、nanobot及Final。

登记时间`2026-10-29T13:12:52.708992+00:00`，清单SHA256 `94c2aa457fe8336241e235cb63ab4c978baccb4d8dca254e83bf2356b6a51e09`。Run `e8e23320-164b-4b7b-825f-7ffa14a783bf`，Thread `e58d1a7f-38ba-4cfe-9bfa-f8bfb10e16d6`；终态待回填。

## 终态

success，552.604339秒；38/38实际maomaoai/deepseek-v4-pro，Usage完整finalized、账本对平。主6次累计输入134,936、峰30,733；子32次输入546,488；总736,963 Token，cache read512,896。目录窗口1M下峰值3.0733%，供应商部署窗口仍未知，不以比例与旧Kimi/DeepSeek作代码收益归因。配置价格估算$1.7678944，非供应商最终账单。

原五项事实人工评分5/5：包/契约分层、默认compaction、完整触发/剪枝/重试、可选loop外多命名provider、fresh/history-seeded/进程外形态及父级发现均有结论和支持引用。本次第三方向没有笼统“不共享父上下文”的条件；一个子任务因GitHub上游读取失败交回未知，父级补读同SHA文档，显式争议旧未知并新增5项证据结论，没有将失败伪装成功。三份合法报告、31份来源hash、单一最终流、交接重渲染、4374字符去重原文和root自动摘要0均通过，公共源码/环境无漂移。非核心实现细节未穷举源码证明，不将本单例写成工业级稳定结论。

文件行号审计初次调度早于audit.json依赖而失败，未产生结果；另存重跑日志，没有修改原始记录。旧sources字段解析器不识别3个目录引用，原false保留；新增独立`audit-directory-sources.py`仅对本Run成功、固定ref目录响应与本地提交的目录项逐项核对，其余文件行号结果不变，全部通过。该补充不将目录当行为证据，不改变五项评分。数据为所属`.local-stack/v45-pro-smoke-21-terminal.json`（SHA256 `517efbee41c18e79775f3261b715cbf76e36952cfbc9379b229c5deba82ddaf0`）、八类原审计/目录补充及`v45-pro-smoke-21-review.json`。

仅独立烟测门槛已过，下一步另冻结同模型/实现/窗口的委派3次→串行3次，不将本次算入组内。
