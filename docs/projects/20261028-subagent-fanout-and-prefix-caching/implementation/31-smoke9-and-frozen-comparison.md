# 第九次烟测与 v30 冻结对照

2026-10-29。用户已批准28号A/B方案。本文为Phase证据；T5.3/T5.6/T5.7/T3.2/T3.3仍未完成，不代替Final。

## 第九次独立烟测

Run `59765d3f-6b26-4cfd-8895-91649998721a`，Thread `06c0927f-c994-4ddc-94a1-d303670c2b37`。正式Web→API→Runtime，新Thread，xiaok `deepseek-v4.1-flash`、W=131072、O=8192、累计Token限额关闭；原题、固定SHA与五项评分不变。

| 指标 | 实际结果 |
| --- | --- |
| 终态 / Usage | success；36/36完整、missing/incomplete均0、finalized、总账对平 |
| 主级 | 6次，输入136618、输出5224、峰值31269（23.86%） |
| 子级 | 三个真实code_explorer，30次，输入612404、输出30842、峰值41915 |
| 全部Token / 耗时 | 785088 / 523.32秒；价格未配置，费用未知 |
| root自动摘要 | 0；没有以缺失事件推定为0 |
| 来源 / 请求计量 | 59份来源（子51）固定SHA/hash/blob一致；36/36 profile与账本对应 |
| 最终交付 | 14344字符；root messages seq29203恰一次，ID/正文与checkpoint一致，seq29240成功终态，无原始ResearchSynthesis工具消息泄漏 |

人工按原五项评分为**5/5**：能力族Service Definition/Provider/Consumer及subagent注册/工具定位；较早历史摘要、压力、手动命令、可选剪枝与base默认启用；pre-step、规范溢出、先剪枝与replacement generation前进才重试；subagent在loop外且多provider共存；fresh/fork已完成历史、进程外形态及父级发现。分别由组README、compaction概述/实现、subagent子系统及组README支撑，不要求逐字复述评分表。

引用机械审计原结果仍为false：35个可解析引用均在46个读取窗口内，但正文30个缩写无法自动解析，且原解析器不收集`path:行号`格式。另存人工辅助扩展审计，不覆盖原结果：核对sources字段的完整路径/逗号行区间、正文完整路径，以及5行subagent正文的显式别名映射，共99个字段/行区间检查，均存在于固定blob并在实际已读窗口内。**存在且读过只证明来源坐标，不能证明每句推论正确。**

报告仍有附加精度问题，不能把5/5宣传成全文无误：一处将`start()`与`startContinuable()`的返回时机合并，L136实际只支持后者；区间选择一处“保留整轮”与同一行“不保留整轮”限定不一致。两处不改变上述五项原评分，作为额外质量观察保留，不据此改题或放宽原门槛。任务描述也仍存在模型自行细化，不能凭提示词/字符串断言声称模型始终逐字保留范围。

原始证据：所属Worktree `.local-stack/v29-full-smoke-9-terminal-read.json`，SHA256 `e5f096f87691632e1821433056b9c1aa2fa00d24933a0fcdb4fdb2f35d690b38`；同名audit/report/sources/context/citation-windows/expanded-citations/live-final文件、start与源码hash全部保留。`v29-expand-citations.py`是本样本的离线人工辅助审计，不进入Agent输入或实现。

## 当前回归

`v29-current-composition-regression.log`：DearFlow服务专项、模型容灾组合、PII组合共**299 passed、54 skipped、1 deselected**，408.54秒。唯一deselected为Docker执行场景，不启动Docker、不记通过；skip保持skip。此前预算/隐私96 passed、流式V3/legacy四场景及各专项见30号，集合重叠不累加。代码及测试实现沿29/30号记录，Ruff与diff检查已通过；这些仍是Phase验证。

## v30 正式组预登记

- 注册时间：`2026-10-29T06:29:57.541989+00:00`，早于首个正式模型请求。
- 私有manifest：`.local-stack/relaxed-v30-manifest.json`，SHA256 `92b2330ad44ba11c17a29516d8e8a41365474039253af8660237deffbfd495f8`。
- 冻结1129个公共源码/配置及必要采集脚本的hash，另冻结环境、原题启动脚本、采集器；原题启动脚本hash仍为`834ed26258017e6b0c121648d58577a9e86cd9624b9d6195ba40ce0f64a4d856`。两臂唯一差异是Pro delegation布尔值，True/False hash沿原预登记。
- xiaok DeepSeek模型ID `070cced3-350b-42ec-b678-994dd07b7078`、窗口131072、输出8192；供应商部署fingerprint未报告，不声称底层部署版本已证实固定。保留50次主模型、16次子模型、100次主工具、600秒单次模型超时等既有保护。
- 顺序：委派1/2/3→串行1/2/3，每次新Thread，前一次终态且证据落盘后再发下一次；六个终态全保留，不因质量失败替补。
- 新私有`collect-v30.py`每次启动前/终态后检查所有公共hash、模式与环境，持久化启动意图后才发请求，拒绝覆盖或未知状态重发；串行也捕获子来源通道。每样本独立Redis前后快照，不继承旧样本数据。
- 当前委派采集已启动；尚无正式组结论。之后按原门槛评分、计算实数；无同质量串行结果不宣称25%降幅。原组通过后才运行26号nanobot预登记；Final及整合仍在后续。

采集器前置修正：初次在清空浏览器捕获数组时，CLI eval未加`--raw`，装饰输出不能JSON解析；堆栈证明尚未执行`start-baseline.js`、没有发送首个正式请求。原始脚本、失败日志及start-intent保留；06:32:56 UTC在首个模型请求前追加独立`relaxed-v30-collector-amendment-1.json`，仅修正CLI解析并在证据明确的首样本复用启动意图。修订采集器hash `c04f67c3017460e6c5d2075f488f80d2d7f1b3bdb94ba74e0373d34baba3fffb`，公共源码、环境、模型和原题均未变；原manifest不覆盖。
