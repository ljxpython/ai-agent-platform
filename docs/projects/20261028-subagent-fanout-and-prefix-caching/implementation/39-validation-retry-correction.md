# 报告校验纠错的具体缺陷与修复验证

2026-10-29。关联 T5.3/T5.7/T5.8。v33 六次全部终态后，应用修复及专项/扩大回归已完成；真实完整任务仍待验证，本条不是新的效果验收结论。

## 已复现的问题

`subagents/report.py:ResearchReportMiddleware.awrap_model_call()` 在引用校验失败后，用一条 SystemMessage 替换整个 SDK 响应。模型收到 `finding[n].excerpt` 报错，却没有自己刚提交的草稿与对应工具回执。v33 第二个委派样本中，一个子级反复收到同一字段报错并耗尽 16 次额度，只交回两份合法报告。

`middleware/synthesis.py:ResearchSynthesisMiddleware.awrap_model_call()` 在研究已激活后遇到纯正文输出，立即抛出 `Missing validated ResearchSynthesis`，即使尚有模型调用额度。v33 前两个串行样本都因未获得合法最终交付而失败。第二个串行样本此前还存在格式纠错，不能将所有失败统一归因为纯正文第一次响应。

引用校验仍应严格拒绝不匹配原句；纯正文仍不能冒充经过验证的组合。这两个缺陷的修复目标是在现有调用上限内让错误可纠正，沿用已有 ResearchReport / ResearchSynthesis 契约、SDK 调度、取消和流规则。

## 无网络复现

所属 Worktree `.local-stack/validate-retry-probe.py` 使用真实 compiled graph 和确定性假模型，四个场景均限制最多 3 次模型调用，无网络、无应用源码改动：

| 场景 | 原实现 | 候选行为 |
| --- | --- | --- |
| 子级引用错误，纠正需要看到自己被拒草稿 | 3 次后失败，草稿不可见 | 按 SDK 错误纠正方式保留 AI 草稿及对应 error ToolMessage，3 次后报告合法 |
| 主级读取后直接输出正文 | 2 次后失败 | 发既有交付格式反馈，仍用原调用预算纠正，3 次后组合合法 |

日志与输出为 `v33-validation-retry-probe-fixed.log`、`v33-validation-retry-probe.json`。首次原型把假模型计数保存在会被流式中间件浅复制的标量字段，导致主级计数错误；改为共享请求记录后复现通过。首轮失败日志 `v33-validation-retry-probe.log` 保留，不作应用故障或模型收益结论。

已查询官方 [ToolStrategy 错误纠正](https://docs.langchain.com/oss/python/langchain/structured-output#error-handling-strategies) 与 [ModelResponse](https://reference.langchain.com/python/langchain/agents/middleware/types/ModelResponse)，并核对本环境已安装 `langchain/agents/factory.py`：SDK 原生格式纠错保留 AI 工具调用和对应 ToolMessage，只有本次结构化结果非空才结束。子级候选沿用此方式；主级继续隐藏未经验证的最终 Schema/正文，保持单次发布最终表格。

## 应用及验证边界

应用修改限于上述两个中间件及对应测试。子级错误回执与原调用 ID 配对，不能触发执行工具；引用错误不能伪装成成功。主级仅把缺失交付格式转为现有预算内纠错，不吞取消、超时、权限、供应商或其他异常；用尽原额度后仍显式失败。

接入后先跑真实 compiled graph：草稿可见且配对、没有额外源读取、重复失败按原额度停止、主级纯正文纠正、取消传播、最终流只发布一次。继续验证原权限/三并发/私有 namespace/预算/交接回归。v33 原数据不修改；修复后配置另登记，不能与 v33 混算，也不能靠这次复现把语义遗漏判为已解决。

没有新增报告字段、原文跨上下文范围、工具权限、模型或调用额度。这是已批准交付契约的纠错实现修复，按既有实施授权继续，不新增人工审批步骤。

## 应用改动与实际结果

`subagents/report.py` 对仅含一个 ResearchReport 调用的引用失败响应，保留原 AI 工具调用并配对 status=error 的 ToolMessage；返回的 structured_response 为空，SDK 继续现有循环。混合批次保留原先的受控反馈路径，不把额外执行工具排进下一轮。`middleware/synthesis.py` 将研究已激活后的纯正文替换为原格式反馈；原 after_agent 仍检查最终合法组合，用尽预算后拒绝未完成交付。

新测试先在原应用执行得到 **2 failed**（6.26 秒），分别复现草稿丢失与纯正文提前失败。修复后引用/组合/报告/交接图的专项 **57 passed**（8.34 秒）；随后补混合批次无额外执行回归，一并进入扩大集。

扩大集复用 DearFlow 全目录、执行预算/容灾/PII 组合、工具限宽/剪枝：**411 passed / 54 skipped / 1 deselected / 110 warnings，171.01 秒，exit 0**。唯一未选中项为需要 Docker 的既有错误工具场景；跳过和未选中都不记通过，不启动 Docker。日志分别为所属 `.local-stack/v34-validation-retry-{red,green,regression}.log`。Ruff 首次尝试本服务不存在的独立 binary 失败；随后通过共享缓存中的 `uvx --offline ruff check` 成功，没有安装或更换应用依赖。

实际改动：两份源文件、`test_source_quotes.py` 的三项图回归、`test_research_synthesis.py` 纯正文预算 fixture，以及服务规范入口相应段落。来源提取/报告字符限额/主子调用和三并发不变；v33 原始数据及其失败门槛保持原样。扩大回归仍为 Phase，未把它写成 Final 或整体完成。
