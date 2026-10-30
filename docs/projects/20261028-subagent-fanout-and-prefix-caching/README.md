# 有界调研委派与子智能体上下文隔离

> **当前执行方向（2026-10-30，用户确认）：** 简化到官方 `task` + 只读 `general-purpose` 子 Agent。撤除本次自研结构化报告、父级合成、逐字引用校验和专用 `code_explorer`；保留既有预算、工具限宽、PII、Usage、取消、并发和失败隔离。下方原型、真实运行和失败记录是当时方案的历史证据，不再指导当前交接实现。实施进度以 [tasks.md](tasks.md) 最新任务区为准。

## 项目概述
- **时间：** 2026-10-28 起；当前简化实现与工程验证于2026-10-30完成
- **目标：** 通过定位后读取、可恢复工具结果和受限Subagent委派，减少重复输入并保留完整证据；分别验证上下文占用、累计用量与答案质量。
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** 已完成（`done`，仅指当前用户批准的简化实现与工程验证），用户于2026-10-30人工验收通过；所属服务已停止，分支已推送并快进合并main，Worktree、两个专属测试数据库/角色和隔离资源已清理。main收尾记录随本次提交推送，远端SHA回查证据保留在本地归档。相关回归560通过/13跳过/1项默认Docker环境失败，该项显式local后端复验通过；最后一次正式烟测正常交付，主峰40,707/131,072（31.1%），root自动整理观测值0，28/28 Usage完整。原五项明确语义覆盖3/5，不宣称答案稳定全对、费用收益或25%同质量降幅；历史失败保留；本轮仅合并推送代码，未部署共享服务；收尾见[67号](implementation/67-acceptance-merge-and-cleanup.md)。详见[当前Final边界](verification.md#final-验证记录2026-10-30当前简化范围)。

## 快速导航
- [Open SWE 方向的最小委派实现](implementation/66-open-swe-delegation-simplification.md)
- [v51新六次冻结对照](implementation/63-v51-controlled-validation.md)
- [只读子任务循环停止隔离与v52验证](implementation/64-readonly-child-loop-isolation.md)
- [v53六次冻结对照](implementation/65-v53-controlled-validation.md)
- [Markdown有界文档开头与引用窗口](implementation/62-bounded-document-intro.md)
- [v49六次完整对照与失败](implementation/61-v49-controlled-validation.md)
- [整体方案](plan.md)
- [DSH摘要前完成分析：源码对照与实施顺序](plan.md#2026-10-29借鉴dsh在摘要前完成研究的机制)
- [任务拆分](tasks.md)
- [验证计划与记录](verification.md)
- [DSH摘要前效率专项验证](verification.md#3a-dsh摘要前效率专项执行中)
- [v23六次对照数据](implementation/22-v23-controlled-comparison.json)
- [交付缺口与后续评审稿](implementation/23-evidence-handoff-review.md)
- [DSH预算对齐与下一步优化](implementation/24-dsh-budget-alignment.md)
- [另一公开仓库泛化题与评分预登记](implementation/26-generalization-preregistration.md)
- [第六次烟测逐项评分与Docker边界](implementation/27-phase5-smoke6-review.md)
- [第七/八次烟测与消息流审计](implementation/30-smoke7-and-stream-audit.md)
- [第九次烟测与v30冻结对照](implementation/31-smoke9-and-frozen-comparison.md)
- [v30六次对照结果](implementation/32-v30-controlled-comparison.md)
- [短来源原句绑定](implementation/33-source-quote-binding.md)
- [第十次烟测复核与字段级校验反馈](implementation/34-smoke10-and-validation-feedback.md)
- [第十一次语义缺口与有界原文交接修订](implementation/35-source-context-handoff-review.md)（2026-10-29用户已批准，含离线原型）
- [有界原文交接实施与验证](implementation/36-source-context-handoff-implementation.md)
- [第十二次烟测与 v33 六次冻结](implementation/37-smoke12-and-v33-freeze.md)
- [报告校验纠错修复与411项回归](implementation/39-validation-retry-correction.md)
- [v33六次对照结果与局限](implementation/40-v33-controlled-comparison.md)
- [GLM独立完整烟测预登记与失败](implementation/41-glm-independent-smoke-registration.md)
- [无效JSON与主级草稿纠错补齐](implementation/42-draft-recovery-correction.md)（验证中）
- [纠错补齐后的同配置独立烟测](implementation/43-draft-recovery-smoke-registration.md)（失败保留）
- [Kimi独立兼容性烟测登记](implementation/44-kimi-independent-smoke-registration.md)（失败保留）
- [证据反馈与只读单子流中断隔离](implementation/45-evidence-feedback-and-child-isolation.md)（478项通过）
- [修复后Kimi完整任务](implementation/46-evidence-feedback-smoke-registration.md)（交付成功，质量4/5）
- [Step5独立模型兼容性登记](implementation/47-step-independent-smoke-registration.md)（初始化前拒绝，调用0）
- [Step5合法输出配置独立检查](implementation/48-step-legal-output-smoke.md)（主模型失败/备用切换，诊断停止）
- [一次反馈全部引用错误字段](implementation/49-all-quote-feedback.md)（95项通过，已同步）
- [全字段反馈后Kimi质量检查](implementation/50-all-quote-feedback-smoke.md)（交付成功，质量4/5）
- [父级证据视图及覆盖核对](implementation/52-parent-evidence-view-and-coverage.md)（97项专项、66项调用方回归通过）
- [父级修正后独立正式检查](implementation/53-parent-coverage-independent-smoke.md)（交付成功，质量4/5）
- [原生HTTP夹具兼容与逐句核对诊断](implementation/54-http-fixture-and-clause-diagnostic.md)（恢复/回退通过，提示词候选未改善）
- [探索角色事实边界与DeepSeek Pro检查](implementation/55-role-scope-and-pro-smoke.md)（88项回归通过，正式独立任务中）
- [交付修订评审稿与离线原型](implementation/28-evidence-composition-review.md)（2026-10-29用户评审通过，实施中）

## 改动范围
- **影响服务：** apps/runtime-service；前置预算修复涉及 Platform API/Web 的既有 Token 通知和 Usage 校验。
- **改动级别：** 链路改动；T5.7的主级交付契约为已获人工批准的治理修订。不新增公共API或权限，预算准入停止沿既有投影修复。
- **主要位置：**
  - dearflow_agent/modes.py：控制 Pro/Ultra 的 task 工具可见性
  - dearflow_agent/agent.py、subagents/researcher.py：官方 task 与只读 general-purpose 角色
  - middlewares/filesystem.py、tool_output_pruning.py、conversation_offloading.py：保留既有可恢复工具结果、压力视图与最终请求边界；本轮不声明其单独性能收益
  - runtime-service/tests/services/dearflow_agent/：模式、权限、并发、隔离与预算测试
- **不涉及：** 新前端并发树、Artifact 新协议、独立 Subagent 调度引擎。

## 已有能力与前置条件
- 当前 Agent 已使用 DeepAgents task 工具、researcher 子 Agent 和每父图 3 路并发限制；本项目复用这些能力。
- 上下文溢出落盘和 ToolOutputPruning 已随 `78aa1717` 提交到 `main`；定向 subagent、TokenBudget、工具输出和上下文整理测试为 122 passed、1 skipped。
- RuntimeUsageCallback 已采集主/子 Agent 命名空间用量及缓存 Token 字段；共享预留和图级并发测试现已证明确定性调用的在途准入边界。输入使用近似计数，不能据此承诺供应商账单硬上限；真实所有 scope 仍须逐次核验。
- 产物发布工具和预览/下载页面已存在；本项目不增加新的交付 UI。
- 用户已于 2026-10-28 明确授权持续真实模型测试：maomaoai 余额不足时使用 xiaok，无需逐次询问。只发送固定公开仓库材料；切换提供方后重新建立同配置的 3 次有效基线，不混算不同提供方。
