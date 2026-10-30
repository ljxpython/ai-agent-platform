# Markdown深处定位补充有界文档开头

2026-10-30。T5.2/T5.3/T5.6/T5.7/T5.8的Phase修正；沿用已批准范围，尚非Final。

## 根因和边界

v49委派2子任务对`docs/subsystems/subagent.md`执行`query="provider contract"`，只见391附近接口而未见开头定义。子报告和最终结论均缺loop外可选能力；没有发生上下文摘要或压缩丢字。组内未修改应用或审计，全部六次完成后才接入修正。原质量2/3保留。

工具修正适用于任意Markdown：匹配窗口起始超过20行时，同一次已下载文件附`document_intro`，最多前20完整行、2000字符，与命中正文共享既有12000字符预算。首行过长则不附，不将部分行标成完整；命中仍优先、主窗口行号/续读语义保留。不新增HTTP、模型调用、权限或依赖，不写入目标答案，也不继续堆本题提示词。

## 改动位置

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/tools/github.py` → `build_github_tool()`：生成独立有界开头并从正文预算扣除；工具说明描述两窗口。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents/source_quotes.py` → `observed_github_windows()`：分别登记开头和命中窗口；只接受开头的行号、text、截断状态，身份始终来自同一根来源，不能用嵌套字段替换仓库/SHA/路径/URL。两窗口之间的空白区仍未读取。
- `tests/services/dearflow_agent/skills/test_research_batch.py`：与原题无关的Harbor存储合成文档，经真实工具验证开头/深处、12000总限、SHA/hash/namespace及两次HTTP；覆盖近头、非Markdown、无query、未命中、超长开头和超长匹配。
- `tests/services/dearflow_agent/test_source_quotes.py`：嵌套身份不可覆盖、未读间隙拒绝、错误/截断与固定提交规则。

T5.8跨上下文交接仍仅已读README Summary，每子1600/全Run4800/封装6500字符上限不变；任意Markdown开头不因此自动传给父上下文。已有报告字段4800/18000总限及主50/子16调用不变。

## 先红后绿

- 私有候选与合成契约：有效红/绿日志为`.local-stack/v49-document-intro-red-2.log`和`v50-document-intro-private-green-2.log`；最初无后缀两份夹具失败保留，不当功能证据。候选Ruff通过。
- 正式新增契约旧实现：`v50-document-intro-formal-red.log`，4 failed / 5 passed / 72 deselected，8.77秒。四处缺口为file/readme开头、长匹配预算及引用窗口。最初一次重定向路径错误没有运行pytest，已纠正，不作为红测。
- 接入后五文件：`v50-document-intro-regression.log`，136 passed / 8 warnings，13.62秒，exit0。命令：`python -m pytest tests/services/dearflow_agent/skills/test_research_batch.py tests/services/dearflow_agent/test_source_quotes.py tests/services/dearflow_agent/test_source_context.py tests/services/dearflow_agent/test_source_context_graph.py tests/services/dearflow_agent/test_research_synthesis.py -q`。

五份实现/测试/标准已同步主目录，所属Worker/API重启成功，Pro delegation=true，五服务running且API/Runtime ready。Ruff首轮仅一处测试import换行错误，修正后`v50-document-intro-ruff-corrected.log`通过；未改依赖。DSH/nanobot离线审计器组后识别独立开头和错误读取，来源身份不被嵌套字段覆盖，空structured_response也明确产出不通过结果；旧版本另存pre-intro文件，合成自检已通过，不回写旧结果。

## 独立正式原题预登记

清单`.local-stack/v50-document-intro-smoke-manifest.json`登记于`2026-10-29T16:07:21.896656+00:00`，SHA256 `66a525f736804ace3ad7a6e55430727c54ba5dd09561c47ad242284da100391d`。冻结1131公共文件、12测试、10审计器和4采集辅助脚本、环境/模型及原题启动脚本；采集器启动与终态均校验全部清单。

正式Web新Thread `2675af2f-ade0-4327-be99-ac6de8989ef7`、Run `68bbfafa-baae-4d93-a2fa-05a77cf73bff`已正常结束，原五项结论与支持引用5/5。原始文件SHA256 `bee70ad81e6f0c1938b1b3efd7636b29743ee447e596755a094d6f8c3557e503`，逐项review SHA256 `71a34a2dcd32d9b08b834ca65f1ac79d8e99d766389cff55c34dc78b8125861b`。

- 34/34 Usage完整、账本对平，三个真实code_explorer；主4次/累计输入67,880/峰20,879（配置窗口7.96%）。
- 三个真实子任务中两份报告成功，subagent方向耗尽原16次调用额度，返回明确ModelCallLimitExceededError失败回执；父未重派该任务，补读两份固定源码后以合法新增发现补齐。界面保持子任务失败，不伪装三子全部成功；原要求至少两方向由实际子任务处理，仍满足。该恢复路径有额外累计开销。
- 全Run输入481,521/输出17,314/总498,835，cache_read318,976，325.04秒。相比旧烟测总用量更高，不能据低窗口宣称费用下降。
- root自动摘要0、压力剪枝0、成功spill0；32份固定SHA/hash来源、24个显式引用范围及已读窗口通过。
- 原文交接1785字符、去重及确定性渲染一致；唯一最终流与checkpoint相同，未发布原始Schema草稿。五次录得报告尝试中三份Schema合法，沿既有预算纠正，不增加额度。
- 各子任务未解点按对应方向记录，不能拿子一未读实现的说明误当其他方向未读；附加实现细节主要依据文档而非运行验证。单次通过不证明稳定性。

原题、五项评分、xiaok Kimi 262144/8192、主50/子16与原文边界不变。仅作独立烟测，不混入后续六次。下一组见[63号](63-v51-controlled-validation.md)；真实语义稳定性、泛化和Final尚未通过。

回退仅撤本文两处实现与对应测试；原失败、来源文件和账本保留。

## 关联扩大回归与浏览器

在v51原题采样期间仅执行已冻结测试，不改任何实现/测试/环境。`.local-stack/run-v51-phase-regression.py`创建独立原生临时PostgreSQL并在结束时回收自己进程，未用业务库、不启Docker。35文件运行`.local-stack/v51-phase-runtime-regression.log`：672 passed / 16 skipped / 86 warnings，222.60秒，exit0。跳过包括3项旧模型真实摘要、Tavily/Showcase/Langfuse opt-in及9项引擎原生条件；不计通过，原生恢复E2E仍按独立入口验收。此处是Phase，不能提前写Final。

独立`subagent-final-verification`浏览器回放v50：原报告锚点、终态隐藏Stop、无整理悬挂、历史Run仍恰一条success，页面新pageerror=0；390px页面scrollWidth=390。`v50-history-browser-result.json`保存结果。首份mobile截图仍被历史侧栏遮挡，保留不当展示证据；关闭正确的`收起历史会话`后重拍`v50-history-mobile-report.png`，已人工查看原报告可见。未重发任务，未操作采样浏览器。
