# DeepSeek Pro同配置六次冻结对比

2026-10-29，T5.6/T3.2。55号独立正式烟测原五项5/5、来源/完整Usage/单一流/原文限额和root自动摘要0通过后，首次组内调用前登记。

固定原DSH提交、原题和五项评分；maomaoai/deepseek-v4-pro（ID `46cd9fd7-4ddb-43b4-8d2b-fcb7f8c5035c`）、目录窗口1,000,000/输出8192、同公共源码/工具/环境与主50/子16/三并发/工具100。关闭累计费用限额但采集完整Usage，既有调用/时间/循环保护有效。供应商真实部署窗口/fingerprint未知，绝对输入单列。

顺序固定委派1/2/3→串行1/2/3，每次新Thread、等终态再下一次；两臂仅运行Worktree的Pro delegation布尔值不同，主目录一直True。六次全部保留，无替补、不中途改配置、无旧样本混算。委派须3/3原五项及引用全对、至少两真实独立code_explorer、root自动摘要0、主峰≤目录窗口50%、Usage完整；只有两臂同质量时计算25%主累计输入中位数降幅，否则报告完成率/实际输入/耗时且不宣称同质量降幅。

清单`.local-stack/relaxed-v45-manifest.json`在首次调用前冻结应用/环境/原题/采集器及审计工具hash，采集器`collect-v45.py`；文件行号与目录补充审计分开保留。原组v30/v33与所有独立失败保留，本组不替补它们。全部终态后核对，恢复Pro=True并重启，原题通过再按26号原问题/评分登记同模型nanobot泛化与Final。

登记时间`2026-10-29T13:27:15.769297+00:00`，清单SHA256 `dd8ecf1ef6f3e06830d64e0f449bf9fdf143fcbeb7aef4ca50e123aff200b96e`，1131份公共源码冻结。首轮委派Run `33e2c802-2be8-43b0-8763-c2bb273d7917`，Thread `f0eefe7f-d646-4f7d-8196-f78e37283202`，正式组运行中，尚无稳定性结论。

## 首轮失败与采集恢复

首轮终态error，1194.808305秒，三个code_explorer报告均成功，但主级产生21条相同的交付校验反馈，未生成合法最终报告；原五项均不通过。53次实际maomaoai/deepseek-v4-pro调用中52次completed、1次failed，Usage为partial、未finalized、缺1次，完整累计量未知。已知主输入639,727、主峰30,094、已知全scope总量1,478,775 Token；不把已知和当完整总量。root运行/失败事件已捕获，观察到自动摘要0，不能据此将本轮判为成功。

原始`.local-stack/delegation-relaxed-v45-1.json`，SHA256 `091bc572638c384be997def532f466ad095687bcb85c4f52598c03499a211299`，独立`.review.json`记录失败，原audit评分pending保留。50份固定来源hash/ref、53份调用profile关联核对通过；成功最终报告所需的handoff/live-final不适用，未伪记通过。末次错误为`runtime.model.provider_rejected`，不推断具体供应商原因。

采集期间Platform API的uvicorn子进程发生libuv原生断言（`uv__finish_close`），健康请求超时。仅用所属`local-stack.sh restart-one platform-api`按原配置恢复；原Run已error，恢复采集，未重发。保留原采集器解码错误、重启日志与`recover-v45-delegation-1.py`，未改冻结应用/环境/原采集器文件。

恢复后第二轮启动在模型选择器处中断，只有start-intent、没有start/source-start。正式API Thread search确认最新Thread仍为首轮；页面也处于未绑定Thread的新会话地址。刷新页面恢复目录/模型状态后才继续同一第二轮，保留原intent与独立inspection记录，随后仍按第三轮→串行三轮完成固定组，不补首轮。恢复wrapper只调整已完成样本跳过和经核对的未发送intent处理，模型/题目/评分/公共代码不变。

交付重试的离线候选见[57号](57-synthesis-delivery-retry-candidate.md)。候选尚未接入；先完成本组六个固定终态，保留本组失败后再实施最短修复，不在组内改代码或换样本。

## 六次终态（冻结代码下全部保留）

三次委派后按原顺序完成三次串行；六次均为error、无合法主级报告、质量未通过，不能计算同质量输入降幅。第2/3次委派与三次串行均在早期模型请求失败，公开错误为`runtime.model.provider_rejected`，尚无证据把原因限定为余额。未更换组内模型或补样本。

| 组/序号 | Run | 已报告/已观察调用 | 已知总Token |
| --- | --- | --- | --- |
| 委派1 | `33e2c802-2be8-43b0-8763-c2bb273d7917` | 52/53 | ≥1,478,775 |
| 委派2 | `c7ba0735-558c-42ce-bd19-19ff38058664` | 1/2 | ≥14,040 |
| 委派3 | `25d636f3-0169-4742-aeed-e3e9ef5c4505` | 0/1 | unknown |
| 串行1 | `3fbcebcc-217f-4024-887a-cd7c6fe05c41` | 0/1 | unknown |
| 串行2 | `d04f8567-6009-4c6e-9654-82a842e5100a` | 0/1 | unknown |
| 串行3 | `5d095cc5-0bfc-4218-a939-ef023796b7b6` | 0/1 | unknown |

每轮缺一次供应商Usage，完整用量均未知，不用零补齐。所属`.local-stack/v45-six-terminal-review.json`保留原始文件摘要、coverage与输入实数；已核对1131份冻结公共文件无漂移。组结束后恢复Pro=True，再开始57号修复；该过程不改写以上失败。最终数据文件为`delegation-relaxed-v45-{1,2,3}.json`及`serial-relaxed-v45-{1,2,3}.json`。
