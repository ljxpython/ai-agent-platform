# usecase_workflow_agent 设计说明

本文定义 `graph_src_v2/services/usecase_workflow_agent/` 的第一版 runtime-service 样板实现。

目标不是一次性把整个平台做完，而是先做出一个真实可运行的 LangGraph agent 项目，再从这个项目反推后续 agent 的开发规范、方法和使用方式。

## 1. 业务目标

这个样板要解决的真实问题是：

- 前端上传需求文档（重点支持 PDF）
- 智能体读取需求并提炼结构化需求点
- 智能体生成候选用例
- 智能体按规范评审候选用例
- 用户查看当前候选结果并提出修改建议
- 智能体继续修订并再次评审
- 只有用户确认没有问题时，才执行最终持久化动作

## 2. 目录结构

```text
graph_src_v2/services/usecase_workflow_agent/
  __init__.py
  graph.py
  prompts.py
  tools.py
  schemas.py
  README.md
```

职责约定：

- `graph.py`：只做 deepagent 装配
- `prompts.py`：父 agent 与子智能体 prompt
- `tools.py`：本地业务工具，不进入公共 tools registry
- `schemas.py`：服务内部常量与结构定义
- `README.md`：这一个样板项目的设计说明

## 3. 技术路线

本样板直接基于当前仓库已经在用的三条能力：

- `create_deep_agent`
- `HumanInTheLoopMiddleware`
- `MultimodalMiddleware`

这样做的原因：

- 你的需求天然是多阶段、多角色、多轮修订
- 需要支持 PDF 等附件输入
- 最终持久化动作必须有人审确认关口

## 4. PDF 处理策略

这个样板不重新实现 PDF 上传和协议归一化，而是直接复用现有链路。

### 4.1 前端侧已有逻辑

`apps/runtime-web` 里已经支持：

- 文件选择上传
- 拖拽上传
- 粘贴上传
- PDF 转多模态 content block

关键逻辑：

- `apps/runtime-web/src/lib/multimodal-utils.ts`
  - PDF 被编码为：
    - `type: "file"`
    - `mimeType: "application/pdf"`
    - `data: <base64>`
- `apps/runtime-web/src/hooks/use-file-upload.tsx`
  - 支持 `application/pdf`

### 4.2 runtime-service 侧已有逻辑

`apps/runtime-service/graph_src_v2/middlewares/multimodal.py` 已经能：

- 识别 `application/pdf`
- 构建附件 artifact
- 注入 `multimodal_attachments`
- 生成 `multimodal_summary`
- 把附件摘要作为 system context 注入给模型

因此本样板的原则是：

- 不自己重复写 PDF 协议解析入口
- 直接挂 `MultimodalMiddleware()`
- 智能体与工具消费中间件提供的结构化附件上下文

## 5. agent 角色拆分

### 5.1 父 deepagent

父 agent 名称：

- `usecase_workflow_agent`

职责：

- 协调整个流程
- 调子智能体完成分析和评审
- 根据用户反馈继续修订
- 在明确确认后调用持久化工具

### 5.2 子智能体

建议第一版只保留两个真正的思考型子智能体：

- `requirement-analysis-subagent`
  - 提炼功能点、规则、前置条件、边界条件、异常场景
- `usecase-review-subagent`
  - 检查覆盖性、规范性、缺失项、歧义项，并提出修订建议

注意：

- “最终持久化”不做成自由思考型子智能体
- 它更适合作为一个本地业务工具，由父 agent 在人审通过后调用

## 6. 本地业务工具

这类工具不进入公共 `graph_src_v2/tools/registry.py`。

它们只属于当前样板项目。

第一版建议保留 3 个高语义工具：

- `record_requirement_analysis`
  - 记录结构化需求分析结果
- `record_usecase_review`
  - 记录候选用例 + 评审结果 + 修订建议
- `persist_approved_usecases`
  - 仅在用户明确确认后执行最终持久化动作

当前第一版先把这些工具做成 runtime 内可调用的结构化返回。
后续再对接 `interaction-data-service` 或平台服务接口。

## 7. 人工确认关口

这是这个样板最关键的一条规则：

- 智能体可以分析
- 智能体可以生成候选用例
- 智能体可以评审
- 智能体可以根据用户建议继续改
- 但智能体不能在没有明确确认前自己落库

因此：

- `persist_approved_usecases` 必须挂 `HumanInTheLoopMiddleware`
- allowed decisions 至少包含：
  - `approve`
  - `edit`
  - `reject`

这样一来，这个样板就把“人审后落库”的业务约束真正固化到了 runtime 层。

## 8. 第一版范围

第一版只做 runtime 样板闭环：

1. 支持 PDF 需求输入（复用现有中间件）
2. deepagent 父 agent
3. 两个子智能体
4. 三个本地业务工具
5. 最终持久化动作必须经人工确认
6. 注册到 `langgraph.json`
7. 最小测试

第一版明确不做：

- platform-web 页面实现
- platform-api 转发层
- interaction-data-service 真正 HTTP 持久化对接
- 复杂审批工作流

## 9. 为什么这个样板重要

后续我们不是单独解释“LangGraph 应该怎么用”，而是直接从这个真实项目里反推规范：

- 什么情况下该用 `create_agent`
- 什么情况下该用 `create_deep_agent`
- 子智能体该怎么拆职责
- 本地业务 tool 该不该进入公共 registry
- `HumanInTheLoopMiddleware` 该放在哪一层
- 附件/PDF 该怎么复用现有链路

这也是这个样板的真正价值：

- 它先是一个可工作的业务项目
- 然后才是我们的方法论来源
