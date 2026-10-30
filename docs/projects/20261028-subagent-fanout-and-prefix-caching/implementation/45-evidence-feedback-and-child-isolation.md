# 证据校验反馈与只读子任务流中断隔离

2026-10-29，关联T5.3/T5.6/T5.7/T5.8。v35/36完整烟测均已收取终态后开始修改，不改冻结运行。沿用28/35号已批准交付契约及原五项质量门槛。

## 已复现的问题与修复范围

- `subagents/source_quotes.py:validate_finding_quotes()`：已读源码存在时，目录tree引用也被要求提供逐行原句，但目录列表没有该格式。只对当前上下文实际成功读取、固定40位SHA及同仓库路径的目录列表免除此句子要求；源码行、混合目录/源码、错提交/错路径/失败读取仍走原校验，不接受凭空目录证据。
- `subagents/report.py:ResearchReportMiddleware.awrap_model_call()`、`middleware/synthesis.py:ResearchSynthesisMiddleware.awrap_model_call()`：反馈使用真实schema字段路径（overview/findings[i]/additions[i]），避免把概述算作findings[0]；4800限额校验给出实际长度与超额量，不放宽上限。
- `tools/errors.py:on_tool_error()`：仅对已装配的只读task角色、`RuntimeResolutionError`精确码`runtime.model.stream_interrupted`回传明确失败，沿用现有ToolErrorMiddleware，不重发、不重试子任务、不合成成功报告，保留已完成兄弟任务供父级披露缺口。鉴权、权限、取消、预算、未知错误及其他角色继续传播。

## 验证与回退

先补目录/混合引用、真实字段路径、实际长度、错误白名单单测，以及完整图单子流中断/兄弟成功/父继续与取消边界；原实现先红，修复后专项及相关扩大集。验证日志、同步摘要和真实任务另记。不加第二调度器、模型审稿或调用额度。回退仅撤本次共享校验/错误适配差异，保留所有历史数据、失败证据及其他已授权实现。

## 实际验证与整合

首轮红测7 failed/22 passed，其中完整图新增夹具遗漏import导致NameError，补齐import后单独重跑仍因真实流中断上抛而失败（1 failed），分别保留`.local-stack/v37-evidence-feedback-red.log`和`v37-child-isolation-red.log`。修复后的首轮1 failed/102 passed/1 skipped，为已有测试仍断言旧`finding[0]`路径；改成真实字段路径，并补充findings[0]纠错轮后，专项104 passed/1 skipped，27.05秒。扩大关联集478 passed/54 skipped/1 deselected/114 warnings，223.26秒，exit0；Docker场景未选中、不计通过。修改文件Ruff通过、两目录diff检查通过。

8份源码/测试/标准修正已按摘要校验后逐字同步主目录（其中6份旧内容核对v35清单；其余两份核对当前差异），未复制私有配置和数据。证明`.local-stack/v37-source-integration-result.json`；所属Runtime API/Worker已重启。新增修复仍须真实任务验证，未提前勾选稳定性或Final。
