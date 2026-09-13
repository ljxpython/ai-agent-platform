# Runtime Service 文档体系建设

## 项目概述
- **时间：** 2026-09-13 至待定
- **目标：** 建立以 Showcase Demo 为范式、以 knowledge 设计资料为依据的 Runtime Service 开发与介入文档体系。
- **状态：** 部分完成：标准指南已落地，仓库级总入口重写后置

## 阅读顺序
1. [现状与信息架构](01-information-architecture.md)：明确资料分层和权威关系。
2. [开发范式](02-development-paradigm.md)：规定新 Agent、工具、Backend、Middleware 的实现方式。
3. [介入与验证手册](03-onboarding-and-verification.md)：让新开发者能本地运行、测试和提交变更。

## 改动范围
- **影响服务：** runtime-service 文档与示例代码
- **改动级别：** 治理改动（开发规范和知识入口）
- **预计工作量：** 2–4 人天

## 关键决策
1. `src/runtime_service/services/demo/showcase_demo` 作为唯一标准 Demo。
2. `docs/knowledge` 保留设计依据；生效规范进入 `docs/standards` 或本项目产出的正式指南。
3. 文档按读者任务组织，不复制所有历史设计全文。
