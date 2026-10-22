# LightRAG MCP 知识库真实文档状态与图谱资产对齐

## 项目概述
- **时间：** 2026-10-21 至 2026-10-21
- **目标：** 彻底铲除 LightRAG Gateway MCP 中扫描静态 `managed_assets` 目录并伪造 fake ID 的虚假文档列表实现；对接原生 `rag.doc_status` 真实存储，实现 13 份多模态文档（PDF、PNG、SVG、JSON、MD）及其状态、切片数的完整透出与 Agent 认知闭环；同步热部署至远端 `sshmy2` 并通过真实联调验收。
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** 已完成 (`done`)

## 项目总结
本项目已彻底拔除原先扫描静态 `managed_assets` 目录并伪造 fake ID 的草台班子假数据实现；通过重构 LightRAG FastMCP Server 请求作用域（基于 FastMCP 原生 `get_http_headers` / `get_http_request` 解析动态 Bearer Token）及修复底层 `json_doc_status_impl.py` 与 `json_kv_impl.py` 的共享内存串台 BUG，直连 `rag.doc_status` 真实存储。
- **真实数据全量对齐**：“平台默认项目”下真实透出 13 份多模态文档（PDF 3 份、图片 4 份、SVG 2 份、Markdown 3 份、JSON 1 份），包含切片数、字符数与更新时间；
- **项目名称精准对齐**：平台端项目名称与 LightRAG 远端 `meta.json` 自动同步保持完全一致；
- **物理级多租户文档隔离**：在不同项目（如 `test` 项目）下，文档列表返回精确为 0，串台泄漏为 0，彻底杜绝跨项目混淆；
- **代码热部署至生产远端**：已同步至 `sshmy2`（152.136.27.196:8001）并重启生效；
- **Playwright + Chromium 真实大模型 E2E 闭环测试全量通过**：运行真实模型（deepseek-v4.1-flash）全链路测试通过（Exit Code 0），留存 4 张高清验收证据截图。

## 快速导航
- [整体方案设计](plan.md)
- [实施任务拆分](tasks.md)
- [验证测试计划](verification.md)
- [实施记录](implementation/)
