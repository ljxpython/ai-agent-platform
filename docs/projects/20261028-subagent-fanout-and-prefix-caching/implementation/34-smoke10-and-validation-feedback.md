# 第十次烟测失败复核与校验反馈修复

2026-10-29。关联T5.3/T5.6/T5.7。**Phase验证，仍未达到真实质量门槛。** 沿28号已批准的格式纠错/短原句范围继续，无新增调度器、审稿模型、权限或额度。

## 第十次独立正式烟测

冻结依据见33号。Run `79cc79c6-e809-4d22-a0c8-2d41cedbd014`，Thread `1257aa91-b0a3-410f-886b-994bddc0dac8`，原始证据SHA256 `a8e223062c0d5b08d0985d43a0dc4493ddfd752b6ac4a473fd1f1e74d118c133`。全新Thread、正式Web入口、原题与五项不变，终态前1130份公共文件hash一致。

| 指标 | 实际结果 |
| --- | --- |
| 运行 / 耗时 | success，528.40秒；业务终态不等于质量通过 |
| 实际子任务 / 有效报告 | 三个code_explorer，仅一份成功；另两份为无效报告及调用额度耗尽 |
| 原五项 | 1/2/3/4通过，5失败：未说明父Agent可发现自己的子级；列出list_agents不能代替该行为 |
| Usage | 48/48完整，primary 8、subagent 40，账本与summary对平，token_budget=null |
| 主累计输入 / 主峰值 | 211964 / 38147，峰值占131072的29.10% |
| 全scope用量 | 输入1219731、输出57563、总1277294；cache_read763008，缓存不抵扣窗口 |
| 上下文处理 | root自动摘要0；profile48/48，无spill成功、展示限宽或压力剪枝，不由此推断所有任务永不摘要 |
| 来源 | 63份固定SHA/hash/blob通过，子49份；独立sources字段26处区间均已读 |
| 最终流 | 恰一次root消息，seq43929，正文与checkpoint一致，终态seq43966，无原始Schema泄漏 |
| Redis | OOM前后均0；其他错误回复增加4，原数保留 |

第2项综合表格的人工Consumer、压力时最老历史摘要、基础默认和可选剪枝计通过；正文只写command-compact而未直接展开`/compact`，作为呈现局限保留。第3项综合pre-step、规范溢出限定、剪枝先后和generation前进才重试判定，引用支持与坐标分开检查。机械引用窗口审计的false保留：父级理由中的裸`#L636-L656`被错误归给另一README；独立sources字段核验不受该别名影响，不用辅助解析替代语义评分。

不以这次4/5重建正式六次，不将其替补到v30。来源原句存在只能证明引句可核验，不能证明所有子句均被引句支撑或原问题完整。

## 已定位的可修复问题

离线检查本次子namespace的SDK更新，仅提取工具参数和错误，不新增模型调用。compaction子级八次ResearchReport均把overview写成字符串，并另设overview_conditions等顶层字段；后期参数已从7093缩至2560字符，仍为相同字段形状错误。原固定纠错文案只重申Schema与4800限额，没有给出具体字段错误，未能引导其修复结构。

另一子级曾因5838/5137字符超长失败，又有两次原句不匹配，最终3389字符报告成功；原句校验原反馈未标明哪条发现失败。包目录子级未交回合法结构化报告，保持失败。

本轮只修上述通用反馈链，不把父级发现等本题答案加入提示词，不放宽4800/18000、主50/子16或五项评分。

## 代码与验证

源码仍仅在所属Worktree；以下路径以`apps/runtime-service/`为根：

- `subagents/report.py:validation_feedback()`复用SDK `ToolStrategy.handle_errors`回调，从SDK异常链中的Pydantic错误提取最多8条字段路径/规则、最多2000字符；不回显原始输入值或任意异常正文。`code_explorer.py`与`researcher.py`共用。
- `middleware/synthesis.py:synthesis_strategy()`共用同一字段错误提取；失败Schema仍不进入公开消息流，内部SystemMessage保留受限纠错详情。
- `subagents/source_quotes.py:validate_finding_quotes()`明确失败发现索引，不向模型补充未读来源。
- 通用测试用重试边界/事件草稿哨兵，覆盖错误overview形状→预算内纠正、错误不含原始值、原句定位，以及父级错误反馈和最终单一发布。

两个新增回归先红：2 failed（7.22秒）。修复后报告/组合/原句专项44 passed（8.06秒），新增父级组合场景后45 passed（7.69秒）。扩大DearFlow及预算/容灾/PII组合为**327 passed、54 skipped、1 deselected、112 warnings（228.58秒，exit 0）**；Ruff及两目录diff检查通过，集合重叠不累加。跳过项不算通过，未启动Docker。

已串行重启所属Runtime API/Worker并确认健康。08:00:11 UTC另冻结1130份公共文件，manifest `.local-stack/v32-full-smoke-11-manifest.json`，SHA256 `59d34117768d49a215a1e647d714038a5b52c52479cb6ab9d315d2e241e73693`。第十一次独立原题烟测正式Web Run `c5b7ce5b-8fb7-4fc4-82b9-d875e67d274d`、Thread `8dfdd61e-22aa-4142-8fef-2108f9f9b89f`已结束；相对第十次只改上述反馈链，原题/评分/模型/窗口/环境及调用额度不变。本次不属于正式六次或替补样本。

## 第十一次独立正式烟测终态与人工复核

原始证据SHA256 `b3f4797042f060a62b38d2b614bdd1ffe07b53c73ea5bb8a37eb3c0c6b0a969c`。终态后再次核对1130份公共源码无漂移。

| 指标 | 实际结果 |
| --- | --- |
| 运行 / 耗时 | success，310.22秒；质量仍未通过 |
| 子任务 / 合法报告 | 三个code_explorer全部交回合法报告：4126、4753、4576字符 |
| 原五项 | 1/3/4/5通过，2失败：未说明随附基础配置默认启用；不能把加载后auto:true的默认参数等同默认挂载 |
| Usage | 33/33完整，primary 7、subagent 26；missing/incomplete均0，账本对平，token_budget=null |
| 主累计输入 / 峰值 | 162970 / 32307；峰值占131072的24.65% |
| 全scope用量 | 输入666822、输出36251、总703073；cache_read421504，不抵扣窗口 |
| 上下文处理 | root自动摘要0；profile33/33；spill成功、展示截断、压力剪枝均0 |
| 来源 | 49份固定SHA/hash/blob核验通过，子40份；47处机械引用窗口、51处独立sources范围均已读 |
| 最终流 | root消息seq29283恰一次，正文同checkpoint，终态seq29320，无原始Schema泄漏 |
| Redis | OOM前后0；其他错误回复159→162，不记为全部错误0 |

字段反馈在真实链路起效：两个子级先把overview写成字符串，收到具体字段错误后改为对象；超长及原句索引纠错也在原16次调用额度内完成。仅证明格式纠错有效，不能用三份合法报告抵消第2项缺失。

离线复核明确了丢失位置：两个子级均在完整、未截断的`packages/compaction/README.md`第1–55行读到第12行默认装配事实；compaction子级还在后端README第28行再次读到。其5669字符初稿与4753字符最终稿都没有这条结论，故不是4800限额纠错才删掉。父级对15条发现全部include，字段原样呈现，additions为空；缺口发生于来源→子报告的语义提炼。程序能验证引句确实读过，不能由一个匹配原句证明复合结论完整或每个子句都有证据。

人工评分及上述边界落盘于`.local-stack/v32-full-smoke-11-final-review.json`，原audit的`manual_review_pending`保留为prior，评分为`[true,false,true,true,true]`。浏览器终态快照/截图为`v32-full-smoke-11-final-ui.yaml/.png`；长报告需点“展开全文”，展开后的DOM快照为`v32-full-smoke-11-expanded-ui.yaml`。浏览器累计console错误另存现状，不能据截图称所有浏览器错误为0。

本次4/5失败保留，不重跑相同配置挑成功，不启动依赖质量通过的正式六次或nanobot；Final仍未开始。后续固定材料诊断、原文交接离线原型及待评审方案见[35号](35-source-context-handoff-review.md)，不能把扩大窗口、更多Schema纠错或继续堆叠本题提示当作已证实的解法。

SDK依据：[ToolStrategy API](https://reference.langchain.com/python/langchain/agents/structured_output/ToolStrategy)、[错误回调官方说明](https://docs.langchain.com/oss/python/langchain/structured-output#error-handling-strategies)，并核对当前安装源码：其ValueError的cause为Pydantic ValidationError。使用已有扩展点，未修改依赖。

证据位于所属`.local-stack/v31-full-smoke-10-*`、`v32-full-smoke-11-*`、同名terminal-read的audit/report/sources/context/citation-windows/source-fields/live-final/report-attempts，以及`v32-validation-feedback-*.log`；失败原始数据保留。离线复核脚本为`review-v32-smoke-11.py`，包含来源/报告/决定/源码hash自检，不调用模型。
