# 全栈大模型监控告警与统一消息推送中心 (Alert & Notification Center)

> **启动日期：** 2026-11-16
> **所属仓库：** `ai-agent-platform`（Worktree 分支：`feat/alert-and-notification-center`）
> **关联项目：** `mlflow-eval-platform` (EvalFlow), `LightRAG`
> **当前状态：** 用户已端到端真实测试并确认验收通过 (Done)。所有后端/前端/防抖/飞书推送功能全量绿灯交付。

---

## 业务背景与用户痛点

在当前已构建的智能体（`ai-agent-platform`）、知识库（`LightRAG`）与大模型评测基座（`mlflow-eval-platform`）三大系统协同运转中，研发、测试与业务人员面临严重的**“黑盒运行、故障哑巴、预算失控、多端无感知”**痛点：

1. **Agent 运行时异常无声无息**：
   - 智能体执行陷入死循环（Tool Loop）、Token 预算消耗超限或沙箱容器崩溃时，只有盯着控制台的人才能发现，缺乏主动实时告警；
   - 耗时数十分钟的后台长任务（Background Task）执行完毕后，用户不知道何时完成，只能手动反复刷新页面。
2. **AI 网关与模型服务故障无预警**：
   - 外部大模型供应商（DeepSeek / 通义千问等）突发限流（429 Too Many Requests）或欠费（402 Payment Required）时，服务默默失败，缺少第一时间的运维通知与切源告警。
3. **自动化评测退化无法阻断**：
   - `mlflow-eval-platform` 自动化回归打擂时，如果模型得分出现断崖式下跌，缺少及时的卡点告警推送到飞书/邮件群，无法形成质量闭环。
4. **多渠道通知割裂与重复造轮子**：
   - 平台缺少统一的通知抽象，各模块若各自硬编码飞书或邮件脚本，不仅难以维护且容易引发告警风暴（Alarm Storm）。

---

## 核心定位：为什么必须做在 `ai-agent-platform`？

系统定位采取 **“一核两翼，生产者-消费者”** 架构：

| 系统 | 角色定位 | 核心职责 |
| :--- | :--- | :--- |
| **`ai-agent-platform`** | **唯一中枢 (Hub)** | **业务与通知总控平台**：托管统一用户体系、租户权限、通知渠道配置、站内信持久化、告警收敛降噪与飞书/邮件统一分发。 |
| **`mlflow-eval-platform`** | **告警源 (Producer)** | **评测与网关事件源**：通过标准 Webhook 推送网关 429 熔断、预算超限预警、评测指标退化等事件给中枢。保持上游 MLflow 0 侵入。 |
| **`LightRAG`** | **告警源 (Producer)** | **知识库事件源**：通过轻量错误回调推送文档解析崩溃、向量索引构建 OOM 等事件给中枢。保持底层轻量。 |

---

## 关键技术选型（遵循 KISS 与 DRY 原则）

1. **引擎底座：选用 `Apprise`（纯 Python 轻量通知框架）**
   - **理由：** 纯 Python SDK，直接 `uv add apprise` 零额外进程开销；原生支持 80+ 种通知渠道（飞书、钉钉、企微、邮件、Slack、Telegram 等）；
   - **坚决弃用 `Novu`：** 坚决拒绝引入 Node.js/NestJS 微服务、MongoDB、Redis 独立运维集群的过度设计（Over-engineering），守住轻量化与极速开发底线。
2. **进阶定制：飞书富文本互动卡片（Feishu Interactive Card）**
   - 针对国内高频使用的飞书群，封装极简的卡片模板渲染器，支持彩色状态条、关键字段摘要与 **可操作 Action 按钮**（如 `[🔍 查看 Trace 链路]`、`[🔄 一键重试]`）。
3. **持久化与状态管理**：
   - 复用现有 PostgreSQL 数据库，新增轻量表（`notifications`, `notification_channels`, `alert_rules`, `alert_events`），零新增数据库中间件。

---

## 文档导航

- 📘 [详细技术方案与架构设计 (plan.md)](plan.md)：包含完整系统拓扑、数据库 ER 设计、告警防抖状态机与接口契约；
- 📋 [唯一任务进度清单 (tasks.md)](tasks.md)：按阶段拆解的任务清单、完成标准与代码改动位置；
- 🧪 [四级验收要求与验证计划 (verification.md)](verification.md)：静态门禁、单测、模拟渠道触发与真实飞书端到端验收要求。
