# Showcase 沙箱工作区与产物展示 - 任务导航

本项目采用多专题文档；任务状态以各专题为准，本页只保留导航，避免多份清单漂移。

## 第一阶段 A：Runtime + Platform API 后端（当前先做）

- 文件树、预览/下载、安全与平台代理：[01](01-sandbox-file-contract.md)。
- 发布工具、格式支持、Showcase 装配：[02](02-runtime-artifact-publishing.md)，已完成；YAML 跨服务发布/列表/下载及 Runtime 重启后读取验证通过。
- 新增/修改文件、实施依赖和测试落点：[04](04-code-change-map.md)。

## 第一阶段 B：Platform Web（后端契约冻结后）

- 前端 Workspace、预览、下载及刷新：[03](03-platform-workspace-ui.md)，本次只设计，由前端开发者后续实现。

## 测试门槛

- Runtime 完整功能块完成后集中验证；Platform API 完成后执行联合验证。
- 前端完成后执行组件测试、浏览器 E2E 和完整链路回归。
- 中间小改动只执行定向测试、类型/语法检查和契约快照检查。

## 第二阶段：Terminal

- Runtime PTY、平台 API、连接/重连与生命周期已完成，任务和证据见 [06](06-terminal-backend.md)。
- 终端组件及浏览器交互后置，实施位置、接口和验收清单见 [05](05-frontend-handoff.md#terminal前端开发入口)。
- 对象存储、索引与清理策略仅在容量或多副本需求明确后评审。
