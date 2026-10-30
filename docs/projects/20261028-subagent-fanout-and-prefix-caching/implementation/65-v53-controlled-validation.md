# v53 只读循环故障隔离后的完整冻结对照

2026-10-30。T5.3/T5.6/T5.7/T5.8及T3.2的Phase验证，不是Final。

修正后的独立正式任务v52已按原五项5/5、完整Usage/来源/交接/唯一最终流通过，才于本组首个模型调用前登记`.local-stack/relaxed-v53-manifest.json`，SHA256 `a6588b916ad0dc2cbcf35b0cbc785fd0709a2ce0848b4d9f1ec4b0043cf6b08e`。

- 固定原问题、公开仓库SHA `477b4f420553e8a52c2fbccc464d7561b239c443`及原五项评分；xiaok kimi-k3，目录窗口262144、输出8192、headroom65536。供应商实际窗口/部署fingerprint仍未知。
- Usage开启、累计费用额度关闭；主50/子16、工具100、并发3及时间/循环设置不增额。有界原文、结构化交接及来源校验不变。
- 冻结1131公共文件、12测试、10审计器和5辅助脚本（含只负责执行与留日志的审计包装脚本），以及原题脚本、采集器和环境；两臂仅Pro delegation不同。开始和结束核对摘要，组内不改实现或审计器。
- 顺序委派1/2/3→串行1/2/3，每次新Thread并等待终态，六次全部保留，不因失败中止、替补或混入v52及旧样本。组结束后恢复Pro=True。
- 委派3/3须最终五项结论及支持引用全对、2–3真实只读code_explorer、root自动摘要0、主峰≤配置窗口50%、Usage完整。只有两组同质量才计算25%主累计输入降幅；串行失败时比较完成率并报告实数。

采集器`.local-stack/collect-v53.py`，委派日志`collect-v53-delegation.log`，串行日志`collect-v53-serial.log`。六次Run均已有终态；串行2采集器因正式UI认证检查失败而中断，Run自身error与部分材料保留，不重发。委派1/2/3及串行1/3人工评分均已落盘；串行2无最终报告记0/5。原题质量门槛未通过，不进入nanobot或Final。

## 分次记录

| 次 | Run | 主累计输入/峰 | 全Run总Token | 最终五项 |
|---|---|---:|---:|---|
| 委派1 | 27818999-9d17-4933-947f-8d9ad68b5efe | 29,688 / 17,495 | 276,156 | 5/5 |
| 委派2 | f5b26aaa-cbdd-4db5-8743-9c6e4321c9d9 | 98,067 / 20,769 | 253,329 | 2/5 |
| 委派3 | f54afeb5-101a-466f-ba6b-6ad3bdf9fe57 | 30,110 / 17,917 | 283,940 | 4/5 |
| 串行1 | 2c8ae2dc-4a0b-4d53-a90a-7acd5323ed13 | 139,884 / 27,558 | 146,073 | 2/5 |
| 串行2 | cbbdd140-46fe-4858-9d07-a7f387724da2 | 已知11,877 / 未知 | 未知 | 0/5，error |
| 串行3 | c4cb7ad1-c7cd-476b-8468-d2e6a1b75b58 | 216,999 / 29,559 | 227,471 | 2/5 |

- 委派1 success，210.59秒，24/24 Usage完整，root自动摘要0，三个真实只读子namespace；来源坐标、引用已读窗口、有界交接/渲染与单一最终流核验通过。评分文件`.local-stack/delegation-relaxed-v53-1-review.json`，SHA256 `72eb7d17b04ae1b65bcdbdba41b323b90891b2d8c4f715c5b35e90fe5968e679`。
- 委派2 success，Usage完整、root自动摘要0；最终结论漏掉“较早历史压缩为摘要”、`request-error`仅处理规范上下文溢出、fork仅播种已完成父历史三项限定。评分文件`.local-stack/delegation-relaxed-v53-2-review.json`。
- 委派3 success，Usage完整、root自动摘要0；漏掉fork播种“已完成父历史”限定。评分文件`.local-stack/delegation-relaxed-v53-3-review.json`。
- 委派质量仅1/3，不满足3/3；输入实数仅作为组内观测，不作为同质量节省结论。
- 串行1 success，7/7 Usage完整，157.35秒，root自动摘要0；固定SHA的14条引用窗口核验通过，人工2/5。逐项理由见`.local-stack/serial-relaxed-v53-1-review.json`，原始材料`.local-stack/serial-relaxed-v53-1.json`。
- 串行2 Run error（`runtime.execution_failed`）；4次primary调用只有1次有Usage，已知输入11,877，其余用量缺失，Run总量未知；无最终报告，核心0/5。采集器UI认证检查失败一并保留，不覆盖Run自身错误。原始材料`.local-stack/serial-relaxed-v53-2.json`。
- 串行3 success，10/10 Usage完整，401.36秒，root自动摘要0；固定SHA的11条最终引用窗口核验通过，人工2/5。逐项理由见`.local-stack/serial-relaxed-v53-3-review.json`，原始材料`.local-stack/serial-relaxed-v53-3.json`。
- 串行质量0/3。六次两臂没有同质量结果，不计算25%输入降幅。价格、供应商实际窗口与部署fingerprint仍未知；不从上下文峰值推算总输入或窗口大小。
- 定向应用回归见`verification.md`本Phase：103 passed、1 skipped。T5.6/T3.2未通过；不执行nanobot与Final，不宣称泛化或项目完成。
