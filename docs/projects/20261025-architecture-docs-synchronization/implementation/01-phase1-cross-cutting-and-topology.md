# Phase 1 实施记录：宏观拓扑与跨服务通信大动脉同步

## 概述
- **日期：** 2026-10-26
- **执行人：** @laowang-engineer
- **任务目标：** 解决架构文档与代码事实源之间的拓扑脱节与跨服务大动脉断层。

## 变更文件清单
1. `docs/architecture/01-overview/01-system-topology.md`
   - 重构 Mermaid 全景静态拓扑图，引入 Prometheus/Grafana/Loki/Promtail 四容器可观测体系、LightRAG 知识中台、远端 Docker 沙箱与 PTY 交互终端。
   - 补充三轨物理隔离存储（业务库、运行时专库、知识中台专库）定义与端口标准化（2142, 8123, 3000, 8000, 3100, 9090, 3001）。
2. `docs/architecture/01-overview/02-tech-stack.md`
   - 技术清单补齐：`prometheus-client`、Loki、Promtail、LightRAG、MultiServerMCPClient、xterm.js。
   - 增加核心架构选型深度逻辑：为什么选 Loki+Prometheus 超轻量（186MB）而不选重型 ELK；为什么选单向自治验签而不选脆弱的反向 SSH 穿透隧道。
3. `docs/architecture/01-overview/03-design-principles.md`
   - 增加原则五：弹性装配与防自杀容错（Resilience Over Rigid Validation），详述 10s 装配期超时隔离与优雅降级。
   - 增加原则六：全链路 W3C 贯穿与零盲区可观测性（`traceparent` 协议与毫秒级日志穿透）。
4. `docs/architecture/02-cross-cutting/04-trace-and-observability.md`
   - 全面重写：W3C `traceparent` 标准格式（`00-{trace_id}-{span_id}-01`）跨微服务派生与双向回显。
   - 结构化日志打标 `[service] [trace_id] [span_id]` 与 Promtail 正则提取规范。
   - 自研轻量代理 API 直查 Loki TSDB、自回声阻断、前端三级自适应 Langfuse URL 构造器。
5. `docs/architecture/02-cross-cutting/06-knowledge-studio-and-zero-tunnel.md` (新增)
   - 新增原生知识中台与单向免隧道自治架构规范。
   - 详述 Canvas 力导向图谱工坊 2.0、Scoped HMAC 动态令牌、知识库文档切片与多模态元数据表（`knowledge_documents`）。
   - 只读 MCP 检索与连续 4 次防死循环硬熔断机制。
6. `docs/architecture/02-cross-cutting/01-communication-matrix.md`
   - 通信大动脉由 4 条正式扩充为 6 条（新增知识中台单向通道与监控双轨拉取通道）。
7. `docs/architecture/02-cross-cutting/03-sse-streaming-pipeline.md`
   - 补充默认 LangGraph v3 事件帧投影、前端 values 帧防洪比对机制以及 `service.state` 轻量断流极速自愈。

## 验证结果
- Mermaid 拓扑图与时序图语法校验合法，无死节点。
- 所有端口和环境变量与主干代码实际部署对齐。
