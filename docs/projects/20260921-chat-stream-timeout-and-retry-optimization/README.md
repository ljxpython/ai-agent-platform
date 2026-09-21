# 对话流式超时容错与 Transcript 解析优化

## 项目概述
- **时间：** 2026-09-21 至 2026-09-23（预计）
- **目标：** 解决大模型长推理思考耗时引发的网关 60s 硬超时截断、流式中断，以及前端 Transcript 投影算法粗暴将超时重试残余消息误判为“执行步骤与工具调用”导致正文消失的系统性缺陷。
- **负责人：** @lijiaxin
- **状态：** 规划中

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：**
  - `platform-api`（网关层 upstream 超时阈值、长连接代理保活机制）
  - `runtime-service`（模型调用超时策略、长推理阶段 SSE 心跳 keep-alive 帧推送）
  - `platform-web`（Transcript 算法与 `useTranscriptMessages` 对 retry 残余空消息的防御性过滤）
- **改动级别：** 链路改动
- **预计工作量：** 2 人天

## 核心问题定性
在处理复杂问题（如“南海应该有哪些优势？”）时，DeepSeek 等推理大模型需要较长的思考时间（高达 2000~3000 tokens reasoning）：
1. **模型首包超时触发重试**：后端首包等待超时（30s）抛出 `TimeoutError`，自动触发 LangGraph 节点重试；
2. **网关硬超时掐断流式**：从首发到重试吐字累计耗时超过 65s，撞上了 `PLATFORM_API_LANGGRAPH_UPSTREAM_TIMEOUT_SECONDS=60`，导致前端流式连接在收到正文前被强制断开；
3. **前端 Transcript 粗暴归并产生“假步骤”**：`transcript.ts` 在遇到同轮次的前后两条 AI 消息时，盲目将第一条超时的残余空消息推入 `turn.work`，界面错误渲染出“1 执行步骤与工具调用”，而因流式断开正文区空白；刷新页面后因从数据库重新拉取历史又能恢复显示。

## 关键决策
1. **网关超时放宽与心跳机制保障（后端）**：
   - 将 `PLATFORM_API_LANGGRAPH_UPSTREAM_TIMEOUT_SECONDS` 从 60s 放宽至 180s；
   - 在模型思考和节点执行期间，`runtime-service` 与 `platform-api` 需具备定时心跳机制（SSE `: ping` 伪帧或保活包），防止反向代理和客户端在长推理期间断连。
2. **Transcript 算法容错与清洗（前端）**：
   - 前端在归并轮次时，必须对同轮次重试残留的空 AIMessage（`content` 为空且 `tool_calls` 为空）进行前置识别与丢弃，绝不能落入 `turn.work` 被包装成“执行步骤与工具调用”。
   - 建立流式重试消息的无缝替换机制（同轮次新消息原子替换旧失败草稿消息）。
