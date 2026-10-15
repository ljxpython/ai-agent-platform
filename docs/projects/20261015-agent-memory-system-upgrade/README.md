# 记忆系统架构升级 (Agent Memory System Upgrade)

## 项目概述
- **时间：** 2026-10-15 至 2026-10-25
- **目标：** 吸收 DeerFlow 记忆系统核心工程与算法优势，实现异步后台提取解耦、Prescreen 成本门禁、MMR 多样性检索、智能容量淘汰与去重，保留多租户隔离与人工候选审核底座。
- **负责人：** @lijiaxin
- **模板类型：** 多专题模板
- **状态：** 全部子专题已完成落地与验证 (done)

## 阅读顺序
1. [01 执行流解耦与 Prescreen 成本门禁](01-execution-and-prescreen.md)：主请求非阻塞改造（毫秒级释放）与对话有效性预筛规则，解决卡顿与 Token 浪费。
2. [02 检索算法重构与 MMR 多样性召回](02-retrieval-and-mmr.md)：彻底废除 2-gram 简单切词，引入 Token IDF 加权与 MMR 贪婪多样性重排。
3. [03 容量自治、近重复合并与平滑淘汰](03-lifecycle-and-eviction.md)：基于 token-Jaccard 的近重复合并与基于置信度/热度的 Eviction 软淘汰，解除 409 打满拒服限制。
4. [04 三层架构职责边界与契约打通](04-tier-boundaries-and-contracts.md)：明确 Platform-Web、Platform-API 与 Runtime-Service 的职责边界与契约协同（哪些做、哪些坚决不做）。

## 改动范围
- **影响服务：** `apps/runtime-service` (90%), `apps/platform-api` (5%), `apps/platform-web` (5%)
- **改动级别：** 治理改动
- **预计工作量：** 7-8 人天

## 关键决策
1. **执行流异步解耦**：彻底剥离 `aafter_agent` 中的同步 LLM 调用，通过后台 Worker / Asyncio Task 异步处理提取，对话完成立即响应前端。
2. **Prescreen 成本预筛选**：在调用 Extraction LLM 前引入轻量确定性规则与信号判定，对无稳定偏好表达的会话直接跳过提取，大幅削减 Token 开销。
3. **MMR 多样性重排替换 2-gram 交集**：引入 Token IDF 权重结合 MMR 算法，在预算限制内动态筛选信息密度最高、维度最丰富的事实。
4. **软淘汰 (Eviction) 替代硬上限报错**：摆脱 100 条容量满即报 409 拒服的死板逻辑，引入基于置信度、新鲜度与访问热度的淘汰/合并机制。
5. **坚守企业安全底座**：保留 PostgreSQL Advisory Lock 事务 CAS、三元组作用域隔离及 Human-in-the-loop（候选审核采纳制），去除 DeerFlow 的单租户文件系统与业务强绑定。
