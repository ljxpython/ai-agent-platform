# Showcase 图片与图表 Agent 能力

## 项目概述
- **时间：** 2026-09-13
- **目标：** 为 runtime-service 提供可复用的图片识别、文生图工具，在 showcase_demo 中演示图表 MCP 子 Agent，并打通 Platform Web、Platform API 到 Runtime 的线程图片上传和展示链路。
- **负责人：** @lijiaxin
- **状态：** 部分完成；P0 G0 契约实验、P1 Runtime 运输层、P2 Platform API 网关、P3 Platform Web 体验及确定性自动化测试全部完成；待配置真实生产环境外部模型凭据进行线上 Smoke 验收。详见 [验证记录](verification.md)。
- **确认范围：** 用户已确认能力归属、线程产物路径、图片审批规则及 Runtime 内部管理。第二阶段方案（04—08）已完成评审批准，实施严格遵循 P0（G0）-> P1（Runtime 05）-> P2（Platform API 06）-> P3（Platform Web 07）-> P4（全链路验收）批次。

## 阅读顺序
1. [01-image-tools.md](01-image-tools.md)：公共图片工具与 workspace 产物
2. [02-chart-subagent.md](02-chart-subagent.md)：AntV MCP 图表子 Agent
3. [03-showcase-integration.md](03-showcase-integration.md)：showcase_demo 装配与验证
4. [04-platform-image-contract.md](04-platform-image-contract.md)：三服务共享 `ImageRef v1`、消息、artifact、HTTP 与权限契约
5. [05-runtime-image-transport.md](05-runtime-image-transport.md)：Runtime 图片存储、HTTP、消息物化与实施任务
6. [06-platform-api-image-gateway.md](06-platform-api-image-gateway.md)：Platform API 二进制网关、资源授权与错误映射
7. [07-platform-web-image-experience.md](07-platform-web-image-experience.md)：Platform Web 上传、Blob 展示、审批和子 Agent 产物恢复
8. [08-rollout-verification.md](08-rollout-verification.md)：实施门禁、三服务 E2E、安全矩阵、真实重启和回滚
9. [09-document-parsing-design.md](09-document-parsing-design.md)：PDF/文本/结构化文件解析工具与 Middleware 设计（后续扩展）
10. [10-platform-document-integration.md](10-platform-document-integration.md)：Platform API/Web 接入 FileRef、上传、消息和解析结果展示

## 改动范围
- **影响服务：** platform-web、platform-api、runtime-service
- **改动级别：** 治理改动；涉及跨服务图片资源契约、线程文件访问授权和 Runtime delegation scope。
- **实施门禁：** Runtime 第一阶段已完成；第二阶段必须先完成人工方案评审和 G0 消息契约穿透实验。

## 关键决策
1. 图片工具放在 runtime-service 通用 middleware/tool 目录，showcase_demo 只负责装配。
2. 图片产物统一写入当前线程 workspace，并返回 `/workspace/...` 虚拟路径。
3. 文生图需要人工审批；图片识别不需要人工审批。
4. 豆包模型按 ChatOpenAI 兼容接口接入；测试凭据从项目 `.env` 注入。
5. 工具权限由 runtime-service 内部固定策略收敛管理，上层不管理图片和 MCP 权限。
6. 新图片先上传线程 workspace，消息只携带 `ImageRef v1` 轻量引用，禁止把 Base64 送入运行队列。
7. Platform API 只管理用户对项目、线程和图片资源的访问，使用 `image-upload`/`image-read` 最小 delegation scope；不管理工具开关、模型 key 或 MCP。
8. 浏览器通过 Platform API 认证 GET 取得 Blob 并创建临时 URL，不直接把 `/workspace/...` 放入 `<img src>`。
9. 第一版不做对象存储、缩略图、Range、跨线程复制和定时清理；需要时另立项目，不在本链路里夹带实现。

## 核实结果与边界
- 复用公共 `middlewares/`，新增公共 `tools/images.py`；具体代码位置见 [实现记录](implementation/01-runtime-image-chart.md)。
- 新工具由 Runtime 固定启用，角色集合限制可见和可调用工具；身份、租户、Context 哈希、线程校验保留。既有 `task` 等受管工具仍使用原权限。
- 官方 `langchain-mcp-adapters 0.3.2` 按调用创建/关闭会话；schema 快照避免构图启动进程。
- AntV 0.9.10 返回文本图片 URL，`artifact=null`；Runtime 下载并验证图片后保存。未逐个验收全部图表类型。
- 测试凭据已写入被 Git 忽略的应用 `.env`；图片下载域名固定为 `multimodal.vibelearning.top`。
- `/workspace/...` 是 Agent/执行容器路径；平台访问契约已在 04—08 规划，但尚未实施，不宣称完成浏览器、真实 Server 重启或部署验收。
- 权限变更采用默认空的 `internal_tool_names`，未采用该参数的 Agent 维持原逻辑；回退本接入时不涉及数据库或既有文件删除。

## 第二阶段批准记录

用户已于 2026-09-13 完成方案评审并明确批准启动第二阶段实施：

1. `ImageRef v1`、标准 text block `extras.runtime_image` 和两个 artifact 层级作为三服务唯一图片契约。
2. Platform API 新增二进制 PUT/GET 网关及 `image-upload`、`image-read` delegation operation，读取采用流式传输配合 20 MiB 熔断。
3. Platform Web 新线程采用“创建线程 -> 上传图片 -> 创建 Run”，send/queue/fork（基于同一线程的原生流式 forkFrom）共用预处理。
## 实施批次完成记录

1. **P0 G0 契约实验**：已完成并归档至 [02-g0-contract-verification.md](implementation/02-g0-contract-verification.md)，证明 extras 链路无损穿透。
2. **P1 Runtime 图片运输层**：已完成并归档至 [01-runtime-image-chart.md](implementation/01-runtime-image-chart.md)，通过所有单元测试（17 passed, 2 skipped）。
3. **P2 Platform API 网关**：已完成并归档至 [03-platform-api-gateway.md](implementation/03-platform-api-gateway.md)，全网关 157 项单测和全路由矩阵 100% 绿灯。
4. **P3 Platform Web 交互体验**：已完成并归档至 [04-platform-web-experience.md](implementation/04-platform-web-experience.md)，全量 123 项测试通过，生产构建打包完成。
5. **P4 全链路验收**：详见 [verification.md](verification.md)，确定性测试全过，待生产凭证注入进行最终 Smoke 联调。
