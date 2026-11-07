# 会话快照水合与媒体外置治理 - 验证计划与记录

> 更新：2026-11-07。本文是本项目唯一验收口径。功能、单元、三服务本地联调和真实浏览器模型链路已完成；固定 30 样本性能基线及远端 Workspace 故障注入未执行。

## 一、测试范围与环境

- 功能验收全部使用本次新版本新建的会话；完成后刷新、重连、继续提问和分支仍属于新功能验收。
- 不执行存量数据迁移、旧消息格式兼容或旧版本读取新引用的测试。
- 性能对比在改动前/后分别新建相同逻辑负载的隔离夹具；不要求新版读取旧版夹具，不访问生产会话。
- 按 `docs/standards/worktree-development.md` 使用所属隔离资源；记录服务提交/工作区改动摘要、依赖锁与补丁摘要、浏览器版本、机器规格、部署模式。
- GraphHarbor 基线 `0.13.0.post48`。任何必要修改须先证明是通用 Agent Server 缺陷，按其仓库规范评估；平台业务逻辑不得进入 GraphHarbor。
- 原稿中的生产 5.7MB、2.2–3.1 秒及解析阻塞数字仅为待复核背景，不作为实测基线或通过证据。

## 二、性能夹具与测量方法

T01 在功能修改前固定夹具生成方式和数据摘要，不能测试后更换口径：

- F1：45 条根消息，包含匹配的工具调用/结果、最终答复和 3 张有效 PNG（每张约 1.8MiB，实际字节记录）；文字与工具参数在前后版本保持相同逻辑内容。
- F2：同样的纯文本负载，去除媒体；用于确认没有靠省略文字和步骤达标。
- 功能测试另覆盖实际启用的其他媒体类型和子任务，不声称 F1 代表任意长会话。
- 主性能环境：同一台机器、同一 Chromium 版本、无 CPU 降速；浏览器网络设下载 10Mbps、上传 5Mbps、RTT 100ms，记录设置和实际入口。
- 每种情形每个版本至少 30 次有效样本，报告 p50/p95、失败次数及总样本数；失败不得从成功率中删除。加载测试复用已完成夹具，不为每个样本重复调用模型。
- 冷打开清除浏览器网络缓存与应用会话缓存；热切换预先加载同一会话并保留缓存。内部缓存状态单独注明。
- 时间分别记录请求发送、收到响应头、响应体完成、JSON 解析完成、正文/折叠步骤稳定绘制和媒体加载完成。
- 按请求实例配对，使用完成事件/响应体、浏览器 timing 或 trace 交叉核验；记录压缩传输字节与解压后字节，不用 Content-Length 代替全部测量。
- 记录所有 Thread/State/History/SSE 请求及调用来源、重复数量；内部 API→Runtime 时间和字节单列，不能把单个接口耗时当作用户端到端耗时。

## 三、统一性能目标

| 编号 | 验收项 | 通过条件 |
|---|---|---|
| P1 | 新消息媒体体积 | F1 的新 checkpoint 及公开消息/工具事件不含内联媒体二进制；单个引用元数据不超过 1KiB。报告接口与存储实测字节，不设任意会话总大小上限 |
| P2 | 冷打开正文可用 | F1 点击打开至正文/折叠步骤稳定可用的 p95，相对同条件改动前基线降低至少 50%；不等待图片下载完成 |
| P3 | 缓存切换响应 | F1 已缓存会话切换到正文/折叠步骤可见的 p95 ≤ 200ms；后续权威校验不得使最终答复退回中间态 |
| P4 | 数据就绪后的展示 | F1 权威数据解析就绪至正文/折叠步骤稳定绘制的 p95 ≤ 200ms；与 P2 的网络开销分开 |
| P5 | 完整性与请求数量 | 文本、工具关联、步骤与最终答复完整；首屏不因仅需当前消息而发起整批 History 请求；无重复初始化造成的多份相同当前快照 |
| P6 | 纯文本保护 | F2 不丢内容；冷打开 p95 相对基线劣化不超过 max(基线的 10%, 50ms) |

不能以删除正文、禁用审批/子任务或隐藏错误实现指标。异步图片加载可以引起正常布局更新，不要求“零重绘”。若目标在既定边界内无法满足，保留证据并重新讨论，不在测试后直接放宽。

## 四、功能与质量门禁

### 单元测试

- [x] Web：快照优先、历史按需读取、刷新恢复及图片预览通过相关回归和真实 E2E。
- [x] Runtime：结构化图片识别、同步/异步入口、不可变引用和模型请求副本展开通过测试。
- [x] API/Web：现有 Thread/Workspace 权限和图片引用投影在真实 E2E 通过。
- [x] 三服务本地链路、Runtime 回归、Web chat Vitest、vue-tsc 和 diff 检查通过。
- [ ] F1/F2 30 样本性能基线、远端 Workspace 故障注入：待完成，待独立容量/远端环境专项。

### 三服务集成与故障注入

- [x] Web → API → Runtime：读取新会话快照、媒体预览与刷新恢复。
- [x] 真实 checkpoint state 无原始图片 Base64，公开工具卡片显示引用路径。
- [ ] 快照请求期间运行开始/完成、快照返回后订阅前事件产生，最终消息与终态均不丢失。
- [ ] 断线、游标过期、晚到响应与跨会话切换，恢复不重投用户输入，不覆盖新状态。
- [ ] 他页/后台发起新运行的发现，以及前台重新进入/聚焦后的权威状态刷新。
- [ ] Thread/项目越权、撤权后缓存和媒体访问收敛、受控路径及 MIME/大小校验。
- [ ] 原文件覆盖、文件缺失、写入失败、模型解析失败；正文保留、错误明确、无悬空引用或副作用重放。
- [ ] 会话保留期内媒体可读；会话到期回收时沿已有 Workspace 生命周期处理，不删除仍被有效引用的数据。
- [ ] 当前支持的本地与远端 Workspace 路由均验证，不默认使用 Runtime 主机本地路径代替远端访问。
- [ ] 新版本进程重启后新会话及引用仍可读取，未展开媒体的状态可用于当前版本继续执行。

### 真实模型与浏览器 E2E

- [x] 创建新会话，真实 xiaok DeepSeek 读取带可辨识信息的图片并回答。
- [x] 新会话完成后刷新，图片和最终答复恢复且不倒退。
- [ ] 新会话运行中离开再进入、停止后继续提问、审批 resume、编辑分支及子任务详情。
- [x] 图片按需预览、引用字段和二进制显示一致。
- [x] 显式选择 xiaok 模型，未用 mock 替代真实看图。
- [ ] F1/F2 性能原始数据、汇总和 trace：待完成。

## 五、Phase 验证记录

### 2026-11-07：SDK、事件回放与 Runtime 工具事件时序核查

- SDK：npm registry 锁定包 `@langchain/langgraph-sdk@1.10.2` 的 SHA512 与 `pnpm-lock.yaml` integrity 一致；`dist/stream/controller.js` 与本机安装文件 SHA256 均为 `282ebedde723cb102684848c411494cfb3cc68e6778336cffc3a6f4a127d25c6`。核对 state hydrate、idle 延迟订阅、根事件订阅和消息 ID 封存。未核对生产 bundle。
- GraphHarbor：源码已有 subscribe-before-replay 和 sequence 去重；`libs/langhost/tests/test_stream_heartbeat_resilience.py` 定向测试通过，6 passed。该测试证明回放分页/队列清理/心跳，不等于平台应用级快照竞态或真实模型 E2E。
- Runtime：以本地 DeepAgents/LangGraph v3 `astream_events`、`InMemorySaver` 和确定性 fake model 运行工具探针。middleware 在 `handler()` 之后改写结果时，公开 `tools` 通道仍检测到原始媒体标记；工具返回前生成引用时，公开工具事件未含该标记。两种情形 checkpoint 均未包含该探针标记；此结果证明 post-handler 改写不足以保证公开工具事件外置，不证明所有实际图片/Command 路径已覆盖。
- 结论：实现位置应在平台 Runtime 工具返回出口。没有发现增加 GraphHarbor 业务能力或修改通用协议的理由。
- 本记录不是媒体功能已实现的声明。工具真实路径、引用落盘、模型读图和完整业务 E2E 仍未验证。

### 2026-11-07：Phase 0 静态评审与文档修订

- 已核查项目初稿与本地会话/媒体/API 代码，记录用户确认的新数据范围和 GraphHarbor 边界。
- 已修正状态混用、History 接口写法、重复造轮子风险、存量兼容设计和不一致的性能承诺。
- 初稿“Playwright 证据已完成”不再标为已验证；当前项目文档没有足以复核原数字的证据链接。
- 文档检查：通过一次性 Python 只读检查，4 份项目文档的 7 个相对链接均存在，8 组范围/任务/状态/入口一致性检查通过；已检查未跟踪项目文件的行尾空白，git diff --check 通过。
- 检查范围仅为文档；本阶段不包含运行时功能测试、性能实测或生产复现。

后续各 Phase 在此独立追加环境、命令、证据路径与结果，禁止混入 Final。

### 2026-11-07：此前本地功能阶段验证

- **状态：** `partial`；本地新会话功能范围通过，性能 30 样本、远端 Workspace、完整竞态/故障恢复场景 待完成。
- **执行环境：** 本地 PostgreSQL/Redis；Runtime 使用 `RUNTIME_BACKEND=local`；Web `http://127.0.0.1:3000`，API `http://127.0.0.1:2142`，Runtime `http://127.0.0.1:8123`；GraphHarbor 未修改。

### 单元与静态检查

- ✅ Runtime `uv run pytest -q tests/middlewares/test_image_reference_filesystem.py tests/middlewares/test_tool_output_budget.py tests/services/dearflow_agent/test_agent.py tests/services/dearflow_agent/test_p5_media.py`：63 passed，6 skipped。
- ✅ Web `pnpm exec vitest run src/modules/chat src/services/threads/session.service.spec.ts`：554 passed，1 skipped。
- ✅ Web `pnpm exec vue-tsc --noEmit`。
- ✅ Runtime middleware `py_compile`；`git diff --check`。
- ⚠️ Runtime `ruff check` 未执行：当前本地 Runtime 环境没有安装 `ruff` 可执行文件；Python 目标文件已通过语法检查和测试。

### 端到端链路：xiaok DeepSeek 图片外置与刷新恢复

**测试：** `apps/platform-web/e2e/session-image-offloading.spec.ts`，Playwright Chromium，1 passed（约 27 秒）。

**步骤与结果：**

1. 新建会话并显式选择 `xiaok DeepSeek E2E`。
2. 浏览器上传可识别 `BLUE` 的 PNG，发送“必须先用 read_file 读取图片”的请求。
3. 真实 Agent 执行 `read_file`；工具卡片显示已返回，回答识别出 `BLUE`。
4. 读取新 Thread state：存在 `extras.runtime_image`，不存在 `data:image/*;base64` 和 `"base64"` 字段。
5. 浏览器按引用加载图片；截图 `screenshots/xiaok-image-before.png`、`xiaok-image-after.png`、`xiaok-image-reloaded.png` 已人工检查。
6. 刷新页面后，图片和最终答复仍可见，没有退回中间状态。

### 阶段结论

⚠️ 本地新会话、Runtime 媒体外置、模型临时展开、Web 按需预览及刷新恢复已完成；GraphHarbor 保持通用 Agent Server 边界且未改动。30 样本性能基线、远端 Workspace 和完整竞态/故障注入尚无证据，项目保持 `partial`，不能作为治理改动最终完成结论。
- **完成条件：** T01–T07 范围全部落实；新会话功能、权限边界、失败保护和真实模型链路达到本地验收要求；GraphHarbor 保持通用 Agent Server 边界，任何本项目涉及的改动都不得引入平台业务概念。
- **四态规则：** 最终按真实证据使用 done / partial / blocked / 待完成；partial 不是可继续工作时的停止理由。
- **排除项：** 存量兼容、旧版本回退兼容和生产部署不属于本期验收；不以排除这些工作为由省略新功能的故障恢复测试。

## 六、Final 验证记录

尚未进入 Final；完成全部任务后执行。
