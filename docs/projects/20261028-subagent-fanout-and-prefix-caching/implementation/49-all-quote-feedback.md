# 一次反馈全部引用错误字段

2026-10-29，关联T5.3/T5.7/T5.8。原Kimi烟测的compaction子任务先后收到overview、findings[0]、findings[1]、findings[2]、findings[3]错误；一份初稿同时有多处错误，但旧校验每轮只报告第一处。这增加了无新证据的模型调用，接近16次上限。

## 最小修复

`apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents/source_quotes.py:validate_finding_quotes()`保持所有来源、行号、固定提交与逐字引用校验，将缺失和不匹配的字段分别收集，一次抛出含全部字段路径的有界错误。相同原因只写一次，避免父级15项的反馈被现有2000字符限制截掉。只包含内部字段路径和既有修正建议，不回显来源或模型草稿正文。

现有ResearchReport与ResearchSynthesis中间件、SDK ToolStrategy纠错和预算沿用；不加调用、工具、提示词答案、报告字段或交接原文。已查询LangChain官方[结构化输出错误处理](https://docs.langchain.com/oss/python/langchain/structured-output#error-handling-strategies)，并核对安装版调用计数实现；没有重写执行器或计数器。

## 验证与同步

新增多字段/不回显正文以及父、子完整图纠错回归；固定3次模型调用：读取→无效交付→一次修正，不重读、不扩额。覆盖子级5项与父级15项最大值，全部字段与既有纠错指令总长仍小于2000。旧实现红测3 failed/35 deselected/5 warnings（7.49秒），日志`.local-stack/v40-all-quote-feedback-red.log`。

首轮修复后93 passed/2 failed，是新测试误把私有计数字段当作公开返回读取；保留日志并移除该错误断言，继续核对真实模型调用恰3次。最终引用、报告、主级组合及原文交接关联集95 passed/7 warnings（9.74秒），日志`.local-stack/v40-all-quote-feedback-green-2.log`；Ruff与diff检查通过。这只是Phase，不代替真实语义验收。

两份改动已核对主目录旧摘要后逐字同步，记录`.local-stack/v40-source-integration-result.json`；没有复制私有配置或数据。所属Runtime API/Worker重启后登记新独立真实任务。Step5失败已保留，不再重发；采用此前实际交付完整的Kimi检查本次实现。
