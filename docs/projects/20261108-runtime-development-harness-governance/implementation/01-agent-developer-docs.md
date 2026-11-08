# Agent 开发指南重写

- **日期：** 2026-11-08。
- **关联任务：** Task 1～4。
- **背景：** 用户明确目标是帮助开发者设计并开发符合当前规范的 Agent，纠正此前偏向 CI/Harness 门禁的方案。

## 改动与理由

- 应用 README、docs/README、standards/README：把当前开发入口前置，修正 Graph 注册描述和部署链接，明确历史设计与当前规则边界。
- 新增 runtime-agent-development-guide.md：设计问题、Agent 类型、模块职责、目录、构图生命周期、注册/工具目录/能力接入、规则和交付清单。
- runtime-service-reading-guide.md：从笼统的 Showcase/knowledge 推荐改为按需求选案例；直接链接源码和测试，标明旧 README/fake/进程内资源的适用限制；增加官方资料表与 MCP/版本核对流程。
- runtime-service-development-standard.md：保留原有专题要求，只修改开头导读、案例选择、Graph 路径和开发流程。
- runtime-service-onboarding-and-verification.md：说明新 Agent 自己的测试不可被旧案例测试代替，增加分类验证和所属 Worktree 环境入口。
- 项目文档与状态索引：按用户范围重写计划；CI job、检查器扩展和新 AGENTS 不在本期。

## 验证及限制

修改范围文档检查、本地链接/锚点、源码符号、Graph 配置及三个开发场景静态走查通过，详情见 ../verification.md。没有修改业务代码、测试脚本、依赖或 CI；没有运行产品测试、启动服务或访问私有配置。

没有重写全部案例 README 和历史 knowledge；已明确提示过时描述并给出当前源码/测试定位。没有自行解除生产门禁或修改权限契约。
