# 有界已读原文交接实施与验证

2026-10-29。关联T5.3/T5.6/T5.7/T5.8。**状态：实施中；真实质量及完整验收尚未完成。** 用户本次明确批准35号范围，并要求完成全部开发和必要验证后保持服务启动，交给用户验收。

## 应用改动

源码在所属隔离Worktree `/Users/lijiaxin/.codex/worktrees/subagent-baseline-20261028/ai-agent-platform`；下列路径以仓库根为准。

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents/source_quotes.py:observed_github_windows()`：提取既有成功、公开GitHub固定SHA来源识别，原句校验和新交接共用；不读取来源指针或本机参考仓库。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents/source_context.py`：只从完整连续的实际行窗口选择README概述首段，保留原文、行号、来源call和观测窗口SHA256。支持语言后缀、中文概述标题及完整EOF，拒绝截断、浮动ref、不连续/未闭合窗口、代码围栏和非正文块；超长整段跳过。每子最多2段且紧凑JSON≤1600字符，版本化ResearchHandoff≤6500，模型仍只生成≤4800的ResearchReport。
- `subagents/code_explorer.py`、`subagents/researcher.py`：将程序封装钩子放在报告guard之前；原生SDK的after_agent反序执行，先验证合法报告、再附原文。没有可用原文时沿旧报告路径；失败/取消不包装成成功。
- `middleware/synthesis.py:ResearchSynthesisMiddleware`：只解析本Run实际配对的task返回，保留旧报告兼容；Run私有注册表新增去重且全Run≤4800字符的原文集合，串行GitHub读取沿同一提取规则。最终模型视图将其标作非可信资料，按原问题检查实质遗漏并用原有additions补充；不自动生成、打分或认可结论。父新增引句只允许实际已读的原文行范围。
- `source_context.py:ResearchResultFilesystemMiddleware`、`agent.py`：父级filesystem只对通过内部Schema及6500字符边界的成功task交接包保留完整内容；其他工具、失败、错误版本或超限包沿既有限宽/归档。通用工具上限没有整体放宽。

没有新依赖、调度器、审稿模型、公共接口/SSE或额外调用额度。主50/子16、三并发、SDK取消、授权及最终单次Markdown流保持原契约。

## Phase验证

先新增通用导出资格哨兵测试；模块尚未实现时专项收集失败，错误为新模块不存在。实现后原文/原句相关44项通过。新增真实compiled graph组合后，下列最小集合 **51 passed / 7 warnings，17.74秒，exit 0**（集合重叠，不与44相加）：

```sh
# 在所属Worktree/apps/runtime-service执行
uv run --frozen pytest tests/services/dearflow_agent/test_source_context.py tests/services/dearflow_agent/test_source_context_graph.py tests/services/dearflow_agent/test_research_synthesis.py -q
```

证据：`.local-stack/v33-source-context-specialist.log`。覆盖：原文/来源哈希与行号、截断/ref/路径/不连续/不闭合/非正文拒绝、单子与全Run限额/去重、旧报告兼容、恶意指令仅作原文、原生SDK交接钩子次序、串行/委派两种路径、legacy/Worker V3最终输出恰一次且等于checkpoint、末轮仅交付Schema、6500包跨同步/异步filesystem不被截断、错误包正常限宽、同Thread跨Run复用call id不复用旧证据、PII只改最终模型副本、失败与取消不回传合法交接。所有哨兵与原题答案无关。

初次扩大测试日志重定向使用错误的相对路径，shell在pytest启动前拒绝；纠正到所属`.local-stack`后执行。Ruff首次发现5项本次新增的导入/未用import/多余f前缀问题，均已修正。

随后保留交接包的display/spill长度诊断，避免把少计一个task误判为节省；相关graph/计量回归12 passed / 7 warnings，11.70秒。扩大集合包含DearFlow、执行预算/容灾/PII组合与工具限宽/剪枝：**408 passed / 54 skipped / 1 deselected / 112 warnings，481.76秒，exit 0**；日志`.local-stack/v33-source-context-regression.log`。跳过和未选中项不计通过。修改文件Ruff及两个目录git diff --check均通过。

独立原题第十二次烟测于09:32:08 UTC冻结：1131份公共源码，manifest `.local-stack/v33-full-smoke-12-manifest.json`，SHA256 `8e07c919ee1c8948532ff39696e05f9182d0f1ae30939bba2524577ac4eb0a15`。原题、xiaok模型、窗口/输出、主50/子16及环境均未变。预检Redis上限1GiB、OOM 0、其他error_replies 18。首次Redis预检在错误工作目录未找到所属配置，在发送请求前退出；纠正到所属根目录并保留失败，不使用任何主目录配置回退。

离线新审计器核对交接原文与本Run实际工具窗口/哈希、Run限额及最终重渲染；同时修正既有组成审计器对pruning事件名的识别，兼容实际`.pruned`，不改应用事件、不用旧的错误计数推断收益。

正式独立烟测已终态，原五项5/5、Usage36/36、主峰值21.42%、root摘要0；完整审阅及引用机械假阳性说明见[37号](37-smoke12-and-v33-freeze.md)。v33正式六次已冻结并开始采集；另一仓库泛化及Final尚未执行，单次成功不能代替稳定性验收。

## 回退与交付边界

撤销新封装/提取及父级解析接线，可恢复旧ResearchReport交接；保留现有Run、来源、Usage和全部失败。无数据库迁移，无Docker前置。本次不执行Git提交、推送或部署。最终按用户最新要求保持所属local栈运行，不沿用旧验证文档中的收尾停服务要求。
