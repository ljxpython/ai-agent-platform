# 修复运行异常重投与 Agent 代码剖析死循环收敛治理

## 项目概述
- **时间：** 2026-10-28 至 2026-10-28
- **目标：** 解决 Agent 额度耗尽后前端静默自动重投 Prompt 的 Bug，治理 Agent 在代码资产剖析时微观强迫症递归调用导致的步数耗尽死循环，并建立模型预算告警时的收尾机制。
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** done

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证计划与记录](verification.md)

## 关联服务
- `apps/platform-web`：修复 `ChatSession.vue` 中 `send` 失败盲目重投（`submitQueuedMessage`）的 Bug；
- `apps/runtime-service`：完善 `SYSTEM_PROMPT` 代码与本地文件调研收敛准则，优化预算逼近上限时的中文化强制收尾感知。
