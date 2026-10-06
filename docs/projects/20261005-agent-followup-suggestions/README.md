# Agent 回答后推荐问题

## 项目概述

- **时间：** 2026-10-05 起
- **目标：** 借鉴 DeerFlow，在 Agent 完成一轮回答后默认生成 3 个（服务端硬上限 5 个）可点击的后续问题，并通过 `platform-web → platform-api → runtime-service` 安全闭环返回。
- **负责人：** @laowang
- **模板类型：** 多专题模板
- **状态：** 部分完成；Platform API 与 Runtime Service 已实现并通过定向验证，前端业务接入待交接，真实三服务 E2E/浏览器验收待具备运行环境后执行。

## 阅读顺序

1. [总体架构与契约](01-architecture-and-contract.md)：DeerFlow 实现拆解、现状差距、目标链路和跨服务契约。
2. [Platform API 方案](02-platform-api.md)：鉴权、线程访问、模型授权、Runtime 委托和接口落点。
3. [Runtime Service 方案](03-runtime-service.md)：无工具一次性模型调用、解析清洗、Runtime 授权和测试落点。
4. [Platform Web 前端交接](04-platform-web-handoff.md)：交给前端同事实施的文件清单、交互状态和验收条件。
5. [验证与发布计划](05-verification-and-rollout.md)：单元、集成、端到端、性能、降级和灰度门禁。

## 改动范围

- **影响服务：** `platform-web`、`platform-api`、`runtime-service`
- **改动级别：** 链路改动（跨服务新增 HTTP 契约和 Runtime 能力）
- **预计工作量：** 后端与 Runtime 约 2～3 人天；前端由同事按交接文档实施，约 1～2 人天；真实链路验收另计。

## 关键决策

1. 前端只访问 Platform API；不把 Runtime 地址、Runtime JWT 或模型密钥暴露给浏览器。
2. 建议问题是一次性、无工具、无持久化的推理，不创建 LangGraph Run，不写 Thread 消息，不污染 Agent 历史。
3. V1 由前端提交最近的 user/assistant 文本，Platform API 负责线程和模型权限校验并限制大小；后续若审计要求“服务端事实消息”，再增加 Runtime 历史快照读取，不把它混进本期。
4. 建议生成是 best-effort：模型超时、解析失败或 Runtime 暂时不可用返回空数组；鉴权失败、线程越权和非法输入仍返回标准错误。
5. 输入框已有的静态 `ComposerSuggestions.vue` 保留；回答后的动态 follow-up suggestions 使用独立组件和状态，避免两个语义混成一套。
6. 首版不新增数据库表、不持久化建议、不为建议建立正常 Run；可观测性只记录请求、耗时、数量、结果和失败原因摘要。
7. 该能力已新增 Delegation JWT `scope.operation=suggestions-generate`；标准仍为 draft，已补充 operation 枚举和隔离说明，正式标准评审与发布仍待人工完成。

## 当前交付边界

- Platform API：已实现配置查询、Thread suggestions 接口、Thread/项目/Graph/模型策略校验、delegation 和 Runtime 降级。
- Runtime Service：已实现独立 suggestions endpoint、JWT scope 校验、无工具 one-shot 模型调用、输出清洗和 best-effort 降级。
- Platform Web：已实现带 `x-project-id` 与单例缓存的 API 封装、思维链与多模态清洗纯函数、生命周期状态机（KeepAlive 补偿、Stop 抑制、竞态防护）、FollowUpSuggestions 紧凑展示组件与草稿冲突确认弹窗，并完成 ChatMessageList 与 ChatSession 的集成。
- 验证：Platform Web 27 项单测全绿、vue-tsc 0 错误、ESLint 0 错误、生产打包成功通过；Platform API/Runtime 定向测试与改动文件 Ruff 已通过；全链路三服务真实 E2E 待具备远端真实运行环境后执行。

## 实施前待评审决策

1. **数量边界：** 默认返回 3 条，Platform API/Runtime 硬上限 5 条；前端按配置展示，避免把“默认值”和“协议上限”混为一谈。
2. **输入边界：** 最近 6 条 user/assistant 消息，单条最多 4,000 字符，总计最多 12,000 字符；超出直接 422，不截断用户已提交的单条内容。
3. **失败语义：** 模型超时、provider 5xx、非法输出统一 `200 + {suggestions: []}`；鉴权、Thread ACL、模型授权和请求校验失败保留标准错误 Envelope。
4. **安全契约：** 新增 `suggestions-generate` operation，仅允许建议内部路由，不能访问原生 Thread/Run、workspace、skills、memory 或工具资源。

## 参考实现

参考目录：`/Users/lijiaxin/PyCharmMiscProject/research/deer-flow`

已核对的关键文件：

- `backend/app/gateway/routers/suggestions.py`
- `backend/packages/harness/deerflow/config/suggestions_config.py`
- `frontend/src/components/workspace/input-box.tsx`
- `frontend/src/core/suggestions/api.ts`
- `frontend/src/core/suggestions/hooks.ts`
- `frontend/src/components/ai-elements/suggestion.tsx`
