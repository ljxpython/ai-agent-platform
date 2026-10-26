# Phase 2 实施记录：执行面 Runtime 与核心智能体沉淀

## 概述
- **日期：** 2026-10-26
- **执行人：** @laowang-engineer
- **任务目标：** 全面沉淀 Runtime 执行引擎与 DearFlow 核心智能体的重大升级（异步记忆、MMR、弹性 MCP、流式沙箱与执行控制全矩阵）。

## 变更文件清单
1. `docs/architecture/07-agents/01-dearflow-agent/02-memory-engine.md` (重构)
   - 彻底废除旧版同步阻塞抽取架构（主耗时从 2~5s 降至 < 5ms）；
   - 写入 Prescreen 成本门禁判定流、中文分词+IDF 加权与双池 MMR 多样性重排数学模型；
   - 写入 PostgreSQL Advisory Lock 事务 CAS 乐观锁并发控制伪代码；
   - 废除 100 条 409 拒服限制，实装置信度与新鲜度加权的时间半衰期软淘汰机制。
2. `docs/architecture/05-runtime-service/concepts/13-asynchronous-memory-and-mmr-algorithm.md` (新增概念专篇)
   - 深入剖析 MMR 算法公式中余弦相关度与冗余度惩罚项的数学权衡；
   - 详述时间半衰期衰减函数与信息熵提升证据（信息熵提升 86.4%，矩阵计算耗时 0.8ms）。
3. `docs/architecture/05-runtime-service/concepts/14-resilient-mcp-fault-isolation.md` (新增概念专篇)
   - 深入剖析“缺工具即自杀”反模式的生产危害；
   - 详述 10s 装配期超时隔离、全局异常捕获软降级与运行期拦截兜底（`ToolMessage` 自愈）；
   - 详述 Agent 显式按需挂载（`MultiServerMCPClient`）杜绝幻觉。
4. `docs/architecture/05-runtime-service/concepts/09-workspace-sandbox-pty-and-asset-pipeline.md`
   - 增加 Smart Zip (ZIP_STORED) 原生流式直出替代 Base64 JSON 内存缓冲剖析（打包 9.4MB 大文件耗时由 21.5s 降至 0.36s，下降 98.3%）；
   - 增加单节点远端 Docker 沙箱与本地 Docker 双模式架构说明。
5. `docs/architecture/07-agents/01-dearflow-agent/04-workspace-sandbox.md`
   - 对立视角表格同步更新 Smart Zip 流式传输直出与单节点远端沙箱。
6. `docs/architecture/05-runtime-service/02-langgraph-execution.md`
   - 增加执行预算与步骤硬限软收尾（80% 琥珀色预警）、只读工具防死循环熔断（3轮预警/5轮硬拦截）、受管多模型故障毫秒级主备降级（Model Fallback）。
7. `docs/architecture/05-runtime-service/03-hitl-and-interrupts.md`
   - 增加先规划后执行模式（Plan Mode）的原生审批中断、修改建议（1-2000字）与恢复流转；
   - 增加 Iron Gate 安全避让机制，杜绝后台完成任务冲掉前台人工审批卡片。

## 验证结果
- 所有概念专篇 KaTeX 数学公式渲染无误。
- 伪代码与 `runtime-service` 真实 Python 模块 100% 对齐。
