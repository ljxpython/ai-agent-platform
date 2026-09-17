# Showcase 沙箱工作区与产物展示

## 项目概述

- **时间：** 2026-09-17
- **目标：** 让 Agent 在沙箱生成的架构图、文档、代码和其他文件能够在平台内被直观浏览、预览和下载。
- **负责人：** 待指定
- **状态：** 文件与 Terminal 后端 done；前端接入设计已交付、功能开发及浏览器交互验收 deferred（用户要求）。验证边界见 verification.md。
- **改动级别：** 链路 + 治理改动（跨服务文件契约、产物访问和浏览器执行隔离）

## 阅读顺序

1. [沙箱文件与 API 契约](01-sandbox-file-contract.md)：先完成 Runtime/Platform API 后端契约和实现
2. [Runtime 产物发布](02-runtime-artifact-publishing.md)：Runtime 如何识别、校验并发布产物
3. [平台展示工作区](03-platform-workspace-ui.md)：后端契约稳定后，最后开发 Platform Web
4. [文件级改动清单](04-code-change-map.md)：具体新增/修改/复用哪些代码、职责、路由映射与测试位置

5. [前端接入契约（实现版）](05-frontend-handoff.md)：实际响应、限制、安全策略及错误处理，接入以此文为准
6. [Terminal 后端](06-terminal-backend.md)：真实 PTY、local/Docker、安全与生命周期、代码落点及验证

## 改动范围

- **影响服务：** runtime-service、platform-api、platform-web
- **参考项目：** `/Users/lijiaxin/PyCharmMiscProject/research/open-swe`
- **预计工作量：** 8–12 人日，分阶段交付

## 实施顺序

### 第一阶段 A：后端先行

先完成 runtime-service 和 platform-api：文件树、普通文件内容读取、artifact 列表、artifact 内容读取、下载响应、安全头、scope 校验和 `present_artifacts`。本阶段不开发 platform-web 页面，只提供稳定契约和契约测试。

### 第一阶段 B：前端最后开发（本次只设计）

Platform Web 在后端契约冻结后实现 Workspace 面板。前端按 `03-platform-workspace-ui.md` 和 `04-code-change-map.md` 对接，不直接读取 Runtime，不拼接宿主路径，也不从自然语言猜 artifact 路径。

### 第二阶段：Terminal

用户已授权实施 Terminal 非前端开发项，Runtime PTY 与平台六类接口已交付；前端组件、分屏布局和浏览器交互按 05 最后开发。

## 测试节奏

不要求每个小改动执行全量测试。以大功能点为边界：Runtime artifact/file 后端完成后集中跑 Runtime 测试；Platform API 契约完成后集中跑 API、scope、安全和联调测试；Platform Web 最后完成后再跑组件测试、浏览器 E2E 和完整链路回归。中间小改动只做定向测试、语法或静态检查。

## 关键决策

1. 线程工作区是唯一事实源；浏览器只通过鉴权 API 访问文件，不暴露宿主绝对路径。
2. “工作区文件”和“已发布 artifact”分开建模：前者支持只读浏览/预览/下载，后者支持类型校验、不可变引用和预览策略；本期不提供编辑。
3. Showcase 第一阶段复用已有线程文件 API、ArtifactWorkspace 和现有前端组件能力，但先完成后端契约；前端页面最后开发。
4. Shell/Terminal 是独立的人工执行能力，用户已批准开始实施；复用 local/Docker 执行边界，手动输入不经过 Agent HITL，创建需显式确认。local 仅供宿主开发，多副本生产部署要求会话粘性路由。
