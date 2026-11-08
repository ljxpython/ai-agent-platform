# Runtime 全文审查与案例纠偏

日期：2026-11-08。关联 Task 5–7；仅文档实现，没有改动源码、依赖、CI 或产品行为。

## 覆盖与处理

全文读取 Runtime docs 45 篇与案例 README 7 篇，长文分段补读。追加轮修订 45 篇、保留 7 篇，逐项理由和依据见 [document-review.md](../document-review.md)。首轮已修订的导航/运行手册经过复核后可保留，不为扩大 diff 再写一遍。

- 现行规范：统一 Worker attempt 时间预算，明确 Workflow 内存 saver 的教学边界，修正取消专项的旧 Docker blocked；知识 MCP 区分静态/受信动态绑定与 Runtime 授权、RAG Worker 本地自治。
- 案例：reference、Workflow、Deep、Backend、MCP、Showcase 按实际入口和资源分支改写。修复测试模型键、prepared_count、正式注册/入口包装、权限与预算描述；例子直接指向存在的测试，避免新增未运行调用片段。
- 历史设计：逐篇列明有效原则与被后续方案取代的主张，在相关章节加上后续依据；撤下错误异步 resolver/Backend 装配伪代码，修复目录拼接错误和研究来源误归属。
- 整合记录：区分 09-04 最小基线、09-05 未完成与 09-07 后续验收；七字段不是永久 schema，opaque reference 不等于被拒绝的 revision registry，10-30 保留策略接替 pending。
- changes：保留当日证据，纠正公开错误透出/审批的现行边界；28 passed、2 skipped 不写作 30 项全通过，启发式覆盖率不写作实测保证。
- 导航：缺失历史文件撤下无效链接并说明 checkout 未保留；公共 chart schema 改为真实路径。没有伪造归档文件。

## 验证与剩余边界

验证范围为全文内容、相对文件/标题链接、现有文档检查器、源码/测试 AST 定位、Graph JSON、RuntimeContext、锁定版本、示例语法、52 行审查覆盖与 Markdown-only 差异。实际计数及最终结果见 [verification.md](../verification.md)。检查使用临时标准库脚本，不扩展仓库检查器。

产品单元、集成、真实模型、外部 MCP、Docker、浏览器与生产部署均未执行；历史通过记录不计入本轮验证。Workflow 内存 saver 和教学全局 profile 限制已明示，没有在这次文档任务中改变实现。外部研究未重新调查，API 资料按现行导航查询及本地版本核对。
