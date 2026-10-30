# 只读子任务循环停止的故障隔离

2026-10-30。既有T2.2单子失败隔离遗漏修复，属于Phase验证，不是Final。v51完整六次冻结组结束且核对无漂移后实施；没有更改该组记录或补样。

## 改动

- `apps/runtime-service/src/runtime_service/tools/errors.py:on_tool_error()`：只对已配置只读task角色、精确`RuntimeExecutionError`类型及`runtime.loop.detected`错误码返回`tool.operation_failed`、`outcome=failed`、`recovery=do_not_repeat`。说明任务未完成，由父级使用已完成兄弟证据或披露缺口。子级原循环保护照常停止，主级循环继续原生失败。
- `tests/tools/test_tool_errors.py`：覆盖获准角色、错误工具/角色、相似错误码、鉴权、隐私子类、全局预算及取消，不将这些控制误吞为可恢复失败。
- `tests/services/dearflow_agent/test_subagents.py:test_code_explorer_graph_boundaries()`：完整图先成功读源，再让一子反复漏ref，实际触发LoopDetectionMiddleware；断言该子失败不可重派、兄弟完成、父级继续、无同级取消，来源/权限边界保持有效。
- Runtime开发标准同步明确精确例外。未自动补ref，未关闭循环保护，未放宽主50/子16、工具100、并发3或原文交接范围，未改原题和评分。

## 验证及同步

- 旧实现无模型探针失败，修复后探针通过，日志`v52-loop-isolation-probe-red/green.log`。
- 正式红测：3 failed、24 passed、54 deselected、17 warnings（39.27s）；失败覆盖两个只读角色及完整图中的兄弟取消传播。
- 相关五文件回归：170 passed、1 skipped、89 warnings（46.11s），`.local-stack/v52-loop-isolation-regression.log`。跳过项不计通过。
- 所属venv及全局无Ruff，失败日志保留；使用已有缓存`uvx --offline ruff check`退出0，`v52-loop-isolation-ruff-uvx.log`。未安装新依赖。
- 四份文件已逐差异检查并同步主审查目录，摘要见`.local-stack/v52-loop-isolation-sync.json`；没有Git提交、推送或部署。

## 后续真实验证

修正后的独立正式Web→API→Runtime原题登记清单`.local-stack/v52-loop-isolation-smoke-manifest.json`，SHA256 `f0e495d9d5b6f3e318872116865281facb54916174bc9423ab2a9f491cde280b`，首次模型调用前冻结1131公共文件、12测试、10审计器、4辅助脚本及环境。仍用xiaok kimi-k3、窗口262144/输出8192/headroom65536和原题；实际供应商窗口/部署fingerprint未知。

先加载修正并确认所属五服务ready，再执行该独立任务。只有最终五项结论与支持引用、来源、Usage及唯一最终流均通过，才登记新的六次组；旧失败继续保留。稳定性、nanobot单次泛化与Final仍未通过，T5.3/T5.6/T5.7/T5.8/T3.2/T3.3不提前勾选。

### 独立正式任务结果

- Run `1b4f22e5-be1f-49c3-ba62-1d6116b48a53`，Thread `2f287d57-8a57-4949-a5c8-3917e6b50765`，success，260.72秒。原始`.local-stack/v52-loop-isolation-smoke-terminal.json`，SHA256 `aa6af345591d8ff7463a556ce765b903511b29be2872efa1614b225f6ba1c8b7`。
- 人工逐项只按最终结论及其支持引用评分，5/5；固定来源、实际已读行、字段坐标、有界交接和唯一最终流核验通过。三个真实只读code_explorer均成功，27份来源；最终流恰一条且与checkpoint正文一致。
- Usage 27/27、finalized=true、无missing/incomplete/degraded；主2次调用，累计输入30,269、峰18,076（配置窗口6.90%）；主自动摘要0。全Run输入333,188、输出22,532、总355,720 Token；窗口低不代表整Run费用下降。
- 原文交接去重后1,785字符、确定性渲染与保存结果一致；9个审计执行均退出0，人工质量评分`.local-stack/v52-loop-isolation-smoke-review.json`，SHA256 `d8b3b333cd9d0403f231b5285244090f01a7c832bc1dbb13063a45836d1f39ce`。完整图回归已验证故障隔离，本次真实任务没有触发循环停止，不能将其描述为真实故障注入。
- 两目录冻结清单中1010份应用源码、配置和测试逐字一致，所属五服务ready；Runtime API/Worker已加载修正，Pro=True。新的六次对照见[65号](65-v53-controlled-validation.md)，独立成功不计入组样本。
