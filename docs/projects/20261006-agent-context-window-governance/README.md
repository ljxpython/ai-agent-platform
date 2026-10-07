# Agent 上下文窗口管理工程化

## 项目概述

- **启动日期：** 2026-10-06；实施排期在人工评审后确定。
- **目标：** 在官方 DeepAgents 摘要之上补齐模型容量、隐藏摘要流、可恢复状态和受控手动压缩，使长任务可继续执行且历史可查。
- **负责人：** 后端与 Runtime 已实施；前端由用户同事实现。
- **模板类型：** 标准模板。容量、压缩、契约与交互相互依赖，需要联合验收，不拆成独立项目。
- **改动级别：** 治理改动，包含跨服务契约与模型目录数据模型调整，影响持久状态和权限边界。
- **状态：** `done`：后端、Runtime 与前端 F01–F03 代码实现已全部交付，全链路单测、静态检查和生产构建通过；用户已在平台真实页面完成端到端联合验收（V02B / V03B 验收通过）。
- **预计工作量：** 后端与 Runtime 约 7–10 人天，前端约 2–3 人天，联合验收约 2 人天；为规划估算，不是承诺排期。

后端/Runtime 的 B01–B05、R01–R03 与服务端 V01/V02A 已交付，前端 F01–F03（模型容量配置与展示、整理状态微胶囊及自动淡出打断机制、手动维护动作与菜单守卫）已完成并通过 63 项前端定向单测、vue-tsc 类型检查和生产打包。真实 PostgreSQL、模型质量、HTTP v2/v3、取消/Worker 重启和开关回滚通过。用户已在真实会话完成端到端人工实测，全链路功能验收通过，需求圆满闭环交付。

## 阅读顺序

1. [整体方案](plan.md)：open-swe 怎么做、当前差距、采纳与不采纳项、三层职责、目标契约和代码位置。
2. [任务拆分](tasks.md)：逐项改动、负责人、前置条件和完成标准。
3. [验证计划与基线](verification.md)：本轮真实调研证据、后续测试矩阵及 Phase/Final 门禁。
4. [前端交接](frontend-handoff.md)：同事可独立使用的请求、事件、恢复规则、代码入口与验收清单。

## 已核实的关键结论

1. **“当前没有任何压缩机制”不成立。** DearFlow、Showcase 及其他 `create_deep_agent` 示例已有官方摘要；`reference_agent` 使用 `create_agent`，确实没有装配摘要。不能将其中一个图的情况推广到全仓。
2. 当前锁定 `deepagents 0.7.8`，常规摘要保留消息，通过私有 `_summarization_event` 重建模型有效上下文；overflow 分支可能转存大工具正文并替换为引用，需共同验证正文与文件恢复。DearFlow 的归档文件使用 checkpoint 支持的 `StateBackend`，不需要复制 open-swe 的沙箱存储。
3. 已复现默认 DeepSeek 和未知代理模型缺少 profile，触发阈值退回 `170000`；不能以统一 `80000` 代替模型容量治理。
4. 已复现摘要可以进入 `messages` 流；摘要模型上的 `nostream` 能抑制这类内部 token。`langsmith:hidden` 不等于对所有观测系统隐藏，也不等于免计费。
5. open-swe 的 `offload_conversation=True` 表示一次独立手动压缩，不是打开自动压缩。自动压缩默认存在，两种语义必须分开。

## 三层分工

| 层 | 是否需要开发 | 本期内容 |
|---|---|---|
| Runtime Service | 必须 | 复用官方摘要；模型预算适配；隐藏内部流；根图/子图一致装配；压缩状态；手动整理；失败与恢复保护 |
| Platform API | 必须 | 模型容量字段；内部模型连接扩展；手动动作校验/幂等/ACL；受管 Context 哈希；事件与私有状态过滤 |
| Platform Web | 需要少量适配；自动压缩和通用断流恢复都不依赖前端 | 模型容量编辑；压缩状态提示；受控手动动作；复用现有断流/切线程恢复，只补整理状态投影和竞态测试；由同事根据交接文档实现 |

## 本期边界

- 支持 `dearflow_agent` 与教学标准 `showcase_demo` 的根 Agent 和所有声明式子 Agent。
- 共享能力放 Runtime `middlewares/`，各服务仍在自己的 `agent.py` 显式装配。
- `reference_agent` 与其他基础/教学图的摘要接入后置；不对未接入图宣称具备此能力，手动请求明确拒绝。
- 本期不修改 GraphHarbor、消息 reducer、checkpoint 表或引擎调度；不引入第二套历史数据库、压缩循环或 token 计算服务。
- 不移植 GitHub/PR、Slack/Linear、作者信息、组织/仓库身份、sandbox provider 等 open-swe 业务属性。
- 不包含长期记忆增强、上下文使用率仪表盘、摘要模型独立选型或新 slash-command 系统。

## 已批准决策

1. 模型目录新增可空 `context_window_tokens`；启用新管理策略后，缺少可信容量或输出预算的模型在调用前明确拒绝；输出预算通过既有 `max_tokens` 或可信 profile 上限提供，必须评审对存量模型的影响。
2. 通过 `RuntimeContext.offload_conversation` 表达手动动作，双端升级 Context 哈希版本；布尔 `false` 不能关闭自动压缩。
3. 对外只发布脱敏后的压缩状态，不开放私有摘要、归档正文或内部路径；手动动作要求当前 Thread `comment` 权限及原生 Run 并发裁决。
4. 自动压缩在摘要/归档异常时明确失败，不无限重试或悄悄丢失上下文；历史保留与状态恢复必须真实验证。

人工评审已于 2026-10-06 完成，批准内容见 [review-record.md](review-record.md)。按 [tasks.md](tasks.md) 实施；前端完成与联合验收之前，功能项目不能标记 `done`。

## 关联项目

- [DearFlow 原上下文与记忆设计](../20260913-dearflow-agent/06-context-and-memory.md)：已有 M01 官方摘要基础，本专项补工程化能力，不重做长期记忆。
- [历史懒加载专项](../20261002-chat-history-lazy-loading-and-timeout-resilience/README.md)：解决浏览器历史装载，不代表模型上下文预算已解决。
- [持久消息队列专项](../20261005-durable-chat-prompt-queue/README.md)：手动压缩必须避免消费该专项的待处理消息；不修改 FIFO 设计。
- [LangGraph v3 与 DeltaChannel 评估](../20261004-langgraph-v3-delta-evaluation/README.md)：复用当前官方状态读取，不自行解码原始 channel 存储。
