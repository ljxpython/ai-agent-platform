# Runtime 与 GraphHarbor 业务边界解耦：平台协作入口

## 项目概述

- **启动日期：** 2026-09-25。
- **级别：** 治理改动，跨 platform-api、runtime-service 和 GraphHarbor；含授权与历史数据迁移。
- **状态：** `partial`。已实施平台 ACL 回查、thread 创建预留/受限 reconcile、可信 project metadata、模型与 tracing 关联；定向 Runtime Service、Platform API 与 workspace 测试通过。完整 Agent Server 入口矩阵、历史 SQL scope 移除、候选包联合验收及生产切换仍未完成。
- **主方案：** [GraphHarbor 项目概览](../../../../graphharbor/docs/projects/20260925-runtime-business-boundary-decoupling/README.md)。此跨仓库相对链接要求两仓同级检出；仓库不在同一工作区时，请在 graphharbor 仓库打开相同项目路径。
- **单一事实源：** 任务、验证和评审记录集中在 GraphHarbor 主方案；本入口不复制任务状态。

## 阅读顺序和平台责任

| 专题 | 平台改动 | 主方案 |
|---|---|---|
| 身份与授权 | 复用 delegation、runtime_gateway、thread_access；补原生资源 operation/目标验证、ACL 回调、创建与补偿顺序 | [01](../../../../graphharbor/docs/projects/20260925-runtime-business-boundary-decoupling/01-identity-and-authorization.md) |
| 模型与 trace | tokens.py 的可选 correlation 签发；复用 graph factory、模型引用兑换、Langfuse/OTel | [02](../../../../graphharbor/docs/projects/20260925-runtime-business-boundary-decoupling/02-model-and-tracing.md) |
| Workspace | 复用 workspace/deepagent.py，补安全覆盖；保留现有路径和可信 thread metadata 绑定 | [03](../../../../graphharbor/docs/projects/20260925-runtime-business-boundary-decoupling/03-workspace-and-packaging.md) |
| 迁移与联合验收 | 历史 metadata 回填、稳定幂等键、Store 客户端清点、worker 快照切换、候选 wheel 和回退 | [04](../../../../graphharbor/docs/projects/20260925-runtime-business-boundary-decoupling/04-data-migration-and-cutover.md) |

## 已确认的边界

2026-09-25 用户明确：彻底解耦，不保留旧业务兼容。主方案已改为候选版本联合验收后维护窗口一次切换；取消双读/双写及旧 API/worker 混跑。官方 LangGraph 契约仍需遵循。历史数据默认保留并离线迁移，不把此决定解释为清库授权。平台逐模块适配清单、鉴权层次和 ACL 定义已补入主方案 README。

1. tenant/project、角色、模型/工具策略、ACL 和 workspace 仍是平台业务能力。GraphHarbor 只执行应用提供的标准 Auth 与通用运行协议。
2. ACL 仍以平台数据库为权威，保留共享、审批与限时 takeover；不采用 owner-only 替代，不复制一套 ACL 数据库。
3. 现有 runtime_gateway 已承担上游调用，不新建旧计划设想的 dispatch 服务；现有 platform:SHA256(project,thread,key) 稳定幂等键继续复用。
4. with_forwarded_headers 当前合并 headers；x-request-id 传递不应误报为丢失。JWT 尚未包含可选 correlation claims，具体补齐见 02。
5. workspace 本地实现已经存在；不搬用户文件、不改 thread_scope_hash，不恢复 interaction-data-service。

## 评审与验收

跨仓库详细计划与阶段实施进度以 GraphHarbor 主方案为准。用户已批准实施，不代表生产切换或历史数据删除已获准；阶段验收继续覆盖授权回调与平台 operation 映射、创建补偿、任务身份有效期、幂等域、Store namespace 契约及数据回退。平台 AGENTS.md 要求治理改动“方案评审（人工）→批准→实施”，批准记录写在主方案 README。

2026-09-25 阶段验证：Runtime Service Auth 43 passed；Runtime Service model/tool/observability 58 passed；workspace 定向测试 54 passed；Platform API ACL/gateway/delegation 36 passed、3 skipped、335 subtests passed。完整最终联合验收、浏览器和生产数据迁移尚未执行；各专题保留剩余检查项。
