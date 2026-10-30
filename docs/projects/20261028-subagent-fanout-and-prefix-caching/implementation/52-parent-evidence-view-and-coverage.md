# 父级证据视图、覆盖核对与摘录字段修正

2026-10-29，T5.3/T5.7/T5.8，沿用户持续开发授权实施。

## 最小改动

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/synthesis.py`：当前Run注册表及去重原文在最后一条真实研究ToolMessage的模型视图中出现一次。已交接task原文仍以注册表替换，串行读取正文/非文本块完整保留；无工具回执的整理后视图沿原SystemMessage兜底，不编造工具调用。Checkpoint与对外回执不改。整合指令在证据后，先核对完整问题覆盖，再取舍；同主题下遗漏的事实可作为additions，避免把“已有主题”误判为“已完整回答”。
- `subagents/report.py`：主子共用excerpt字段与纠错提示明确“只放复制原句；引用放sources”。未改字段、引用匹配规则、上下文范围或额度。
- `tests/services/dearflow_agent/test_source_context_graph.py`：串行/委派×legacy/Worker的四场景增加证据角色、原读取保留、单一注入断言；补多模态回执保留及整理后无工具回执的兜底，不改变持久历史。
- `tests/services/dearflow_agent/synthesis_support.py`：测试模型解析注册表时允许其后有独立原文区块。

没有评分事实/目标仓库路径进入应用提示词，没有新模型或工具，没有扩大主50/子16、原文1600/4800、报告4800/18000或权限。父级仍须遵循原组合和证据校验；模型节点只发布一份通过校验的最终答复。

## Phase验证

原实现红测4 failed/6 deselected；首轮94 passed/1 failed，发现新指令令15项错误回执达2030字符，已缩短重复说明，未提高断言或限额；再测95 passed。加入多模态/整理后分支后97 passed/7 warnings（8.42秒），exit0。日志位于所属`.local-stack/v42-evidence-{role-red,coverage-green,coverage-green-2,coverage-green-3}.log`。Ruff与diff已过；调用方扩大回归、应用同步和重启后独立正式任务继续执行，未提前作为Final或真实质量通过。

## 回退

调用方追加回归66 passed/2 skipped/53 warnings（96.43秒），exit0；跳过项不计通过。四文件与标准已逐字同步，证明`.local-stack/v42-source-integration-result.json`。首次同步检查发现测试helper未在旧冻结清单中，整批写入前停止；核对其唯一差异就是本次解析修改后再同步，没有覆盖无关修改。所属Runtime API/Worker已重启。独立正式任务先登记于53号后启动，结果待验。

仅恢复本次四文件及标准段落到v40冻结hash；不删除历史、账本、证据或回执。当前禁止提交/部署，后续正式任务必须新登记实现，不混入v40或旧六次。
