# 错误响应统一专项

## 项目概述

- **启动日期：** 2026-09-26
- **负责人：** @lijiaxin
- **模板类型：** 标准模板
- **级别：** 治理改动（平台公开错误契约及安全输出）。
- **状态：** 方案已确认、执行细则已细化，待实施；本轮仅文档，功能验证未开始。
- **目标：** 统一平台HTTP错误，保留恢复信息，消除SDK转换丢字段，限制上游原文外泄。
- **允许修改：** platform-api、platform-web及其测试/文档。
- **硬边界：** Runtime/GraphHarbor 完全不修改；包括代码、测试、配置、依赖/锁文件、协议、数据库和部署。本专项不要求其配合升级、重启或重新配置。
- **父项目：** [跨服务规范治理](../20260922-cross-service-governance/README.md)。

## 执行顺序

1. 阅读[实施方案](plan.md)及[错误码与恢复字段清单](error-catalog.md)。
2. 按[tasks.md](tasks.md)依次执行前端、API和组合验证。
3. 按[verification.md](verification.md)执行Phase及Final，未通过不得标done。
4. 本会话继续其他专项讨论，不开始业务编码；后续明确进入实施时直接按本执行包工作，无需重复讨论已确认技术方向。

## 评审记录

- 2026-09-26，对话用户明确同意上轮方案，要求Runtime/GraphHarbor完全排除于改动范围，并要求细化为可交接文档。
- 已确认：平台出口统一；保留根级request_id；业务extra白名单；内部鉴权失败与用户登录失效分开；SDK无损适配；流内协议归SSE专项。
- 本轮据此补充确定性细则：来源状态与公开状态分离、现役错误码登记、memory二次转换规则、测试入口、发布兼容与回退判据。
- 未执行代码实施、生产发布、数据库操作；不把方案批准记成实现完成。
- 外部生产环境交付不属于本次执行包；实现者无需等待生产账号或发布时间即可在平台测试环境开发验收。

## 证据与限制

2026-09-26 使用已安装SDK进行纯内存HTTP错误探针：当前覆盖error字段的转换丢失thread_id，保留对象并补顶层message/code的转换保留该字段。两次均仅一次请求，未连接网络、未修改业务文件。
这只证明SDK HTTPError正文保留，不代替授权fetch、Session对账或浏览器完整验证。

## 关联

- [SSE专项](../20260926-sse-event-contract/README.md)：本专项只负责握手失败及410恢复字段，流内失败和重订阅归SSE。
- [追踪专项](../20260926-trace-context-propagation/README.md)：不改ID算法、不增加traceparent。
- [JWT专项](../20260926-delegation-jwt-contract/README.md)：不修改签发/校验，只在平台出口转换错误。
- [业务边界专项](../20260925-runtime-business-boundary-decoupling/README.md)：保留pending Thread对账，不替其补做未完成Final。
