# 错误响应统一专项

## 项目概述

- **启动日期：** 2026-09-26
- **负责人：** @lijiaxin
- **模板类型：** 标准模板
- **级别：** 治理改动（平台公开错误契约及安全输出）。
- **状态：** `已完成`；公共错误出口、前端消费、真实提交→Run→审计→Langfuse、SSE 编号回调、memory 冲突、真实 peer、workspace 正向文件及浏览器错误态均已验证。现役 `reference_agent` 的 `runtime.tool.not_allowed` 属既有工具授权基线差异，不是本专项回归。
- **目标：** 统一平台HTTP错误，保留恢复信息，消除SDK转换丢字段，限制上游原文外泄。
- **允许修改：** platform-api、platform-web及其测试/文档。
- **硬边界：** Runtime/GraphHarbor 完全不修改；包括代码、测试、配置、依赖/锁文件、协议、数据库和部署。本专项不要求其配合升级、重启或重新配置。
- **父项目：** [跨服务规范治理](../20260922-cross-service-governance/README.md)。

## 执行顺序

1. 阅读[实施方案](plan.md)及[错误码与恢复字段清单](error-catalog.md)。
2. 按[tasks.md](tasks.md)依次执行前端、API和组合验证。
3. 按[verification.md](verification.md)执行Phase及Final，未通过不得标done。
4. 实施证据见 [implementation](implementation/01-platform-error-contract.md)；未完成项以 tasks.md 为准。

## 评审记录

- 2026-09-26，对话用户明确同意上轮方案，要求Runtime/GraphHarbor完全排除于改动范围，并要求细化为可交接文档。
- 已确认：平台出口统一；保留根级request_id；业务extra白名单；内部鉴权失败与用户登录失效分开；SDK无损适配；流内协议归SSE专项。
- 本轮据此补充确定性细则：来源状态与公开状态分离、现役错误码登记、memory二次转换规则和测试入口。用户随后明确仅验收新Web+新API，旧版兼容与回退测试从本专项移除。
- 未执行代码实施、生产发布、数据库操作；不把方案批准记成实现完成。
- 外部生产环境交付不属于本次执行包；实现者无需等待生产账号或发布时间即可在平台测试环境开发验收。

## 2026-09-26 实施进度

- E1.1、E1.2、E2.1、E2.2、E2.3 已实施；公共错误出口、安全 500、内部 401 委托失败转换和 pending 恢复字段可供其他专项集成。
- E3.1、E3.2 已完成 Final：隔离 fixture/Chromium 和真实三服务链路均有证据；新旧组合/回退原列为门禁，现按父项目统一版本边界移除。真实补验通过平台 API 自动创建并清理临时 peer、项目、授权 `showcase_demo` Agent 与 Thread，未改现役 Runtime 配置。
- 本专项未运行迁移、部署、Git 提交或分支操作。

## 2026-09-27 实施进度

- E3.1 新增显式开关的本地真实链路用例：临时项目下相同幂等键只产生一个 Run，两个请求编号关联同一 submission；审计可按编号查询，Langfuse 已导出匹配的 trace。memory 过期 revision 返回 409，SSE 打开/关闭日志与响应编号和 Run ID 一致。
- 现役 Chromium 聊天 Run/审批测试和错误页 403 编号展示通过。真实用例补验 owner/peer 读取、SSE 建立前 403、workspace 上传/读取及缺失文件 404；测试身份、项目、Agent 和 Thread 经平台接口清理。
- 现役 `reference_agent` Thread 的文件上传与 workspace 读取仍返回 403 `runtime.tool.not_allowed`；该 Agent 的工具授权基线与 `showcase_demo` 不同，本专项不修改 Runtime/GraphHarbor 权限。API 全量 301 项为286通过、15跳过、无错误；fork 测试替身已补齐现役 delegation upstream 方法。
- SSE 只接入已有结束原因回调和平台日志；不改变流内协议。Final 已完成。

## 证据与限制

2026-09-26 使用已安装SDK进行纯内存HTTP错误探针：当前覆盖error字段的转换丢失thread_id，保留对象并补顶层message/code的转换保留该字段。两次均仅一次请求，未连接网络、未修改业务文件。
这只证明SDK HTTPError正文保留，不代替授权fetch、Session对账或浏览器完整验证。

## 关联

- [SSE专项](../20260926-sse-event-contract/README.md)：本专项只负责握手失败及410恢复字段，流内失败和重订阅归SSE。
- [追踪专项](../20260926-trace-context-propagation/README.md)：不改ID算法、不增加traceparent。
- [JWT专项](../20260926-delegation-jwt-contract/README.md)：不修改签发/校验，只在平台出口转换错误。
- [业务边界专项](../20260925-runtime-business-boundary-decoupling/README.md)：保留pending Thread对账，不替其补做未完成Final。
