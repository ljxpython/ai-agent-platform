# P0/P1 专属底座修复与验收

## 本轮范围

本记录承接前三轮实施记录，说明此前“有代码、无 Dear 专属证据”的实际问题和修复位置。前端代码不在本轮修改范围内。以下文件路径以仓库根目录为起点，函数名用于代码定位。

## 代码修改清单

| 文件 | 函数／位置 | 改动与原因 | 排查入口 |
|---|---|---|---|
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` | `get_agent`、`PERMISSIONS` | 修复正式构图失败：锁版本禁止给执行 Backend 配置覆盖默认路由的文件权限，且 FilesystemMiddleware 的 tools 不能是空列表。权限只覆盖技能路由，受限子 Agent 保留 read_file 接口但由 Runtime 空白名单拒绝执行 | `test_agent.py` 的构图、探测、Standard 禁止委派测试 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py` | `_can_write/write/edit` | 文件写入保护移到 Backend policy hook：只允许规范化后仍位于 work 的路径；容器路径限制仍由挂载提供。官方权限不能保护 Shell，因此不能仅调换 allow/deny 顺序 | protected-files 参数化测试 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/clarification.py` | `_validate/wrap_model_call/awrap_model_call` | 混批检查从 after_model 移到模型响应返回处，避免 HITL 先暂停、guard 尚未执行；单次提问不能与其他工具混批 | mixed-clarification 测试 |
| `apps/runtime-service/src/runtime_service/workspace/artifact_refs.py` | `ArtifactWorkspace.read` | 将底层文件缺失／不安全路径异常映射为 DocumentError 404，避免输出文件下载出现未处理的 500；哈希不符仍为 409 | 文件 HTTP 越权、损坏测试 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/clarification.py` | `validate_clarification_resumes/_validate` | 新增 P1 回答预校验，读取官方 interrupt.value，严格校验版本、text/select、多字段、必填、选项和大小；失败 422，不创建恢复 Run。工具审批不套用澄清 schema | `test_run_requests.py` |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | `send_thread_command` | 活跃中断归属检查后、Run 创建前调用回答预校验；已有幂等重试继续走原请求 digest 和授权复核 | 不合法回答零提交、合法回答恢复、旧请求幂等测试 |
| 同上 | `get_thread_capabilities` | 从授权线程获取 graph，经目标权限检查、委托签发后查询 Runtime 能力；用户不能传任意 graph 绕过线程归属 | capability target 测试 |
| 同上 | `launch_runtime_run` | Dear Agent 加入现有 durability=sync 配置，减少恢复点尚未持久化就返回的窗口 | Run 请求回归 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/ports.py` | `RuntimeGatewayUpstreamProtocol.get_graph_capabilities` | 增加能力查询端口，保持应用层不依赖 HTTP 客户端实现 | 网关适配器 |
| `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py` | `get_graph_capabilities` | 将 graph 标识 URL 编码，调用 Runtime 内部能力接口 | 适配器契约与 HTTP 路由测试 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` | `get_thread_capabilities` | 新增授权线程能力 HTTP 路由，返回前走既有私有字段脱敏；矩阵测试发现未脱敏并已修复 | HTTP 路由矩阵 |

Platform 与 Runtime 不跨服务导入 Python schema。P1 回答语义在各自边界校验；七字段扩展仍属 P2，需要同步两端。

## 接口与部署落点

- 新增公开接口：`GET /api/langgraph/threads/{thread_id}/capabilities`，沿用平台身份及 `x-project-id`。
- Runtime 内部接口：`GET /internal/capabilities/graphs/{graph_id}`，必须使用匹配 graph 的签名委托。
- 澄清回答仍通过官方 `input.respond`／`command.resume`，无新暂停协议；错误响应为 422／`invalid_clarification_answer`。
- P1 工作区：`RUNTIME_WORKSPACE_ROOT` 下按 graph 与 tenant/project/thread scope 哈希隔离；运行进程与 Docker daemon 必须看到同一绝对挂载路径。当前证据为单机本地持久目录，不宣称跨主机共享卷已验收。
- 镜像：已构建 `runtime-agent-workspace:p1`，本轮本地 image ID 为 `sha256:47b24927ee5a5a4a5fec799b1e8df186077a3c7161baf5d04940cce91a4c32f4`。这是本地 ID，不冒称已发布的 registry digest；部署可通过 `RUNTIME_WORKSPACE_IMAGE` 固定镜像。

## 新增与修改测试

| 文件 | 覆盖能力／证据限制 |
|---|---|
| `apps/runtime-service/tests/services/dearflow_agent/test_agent.py` | 正式 DeepAgents graph＋固定模型；approve/edit/reject、两字段提问、重建恢复、混批、篡改 scope/Context、只读路径、真实 Docker 执行发布、探测无资源、Standard 禁止 task/Todo、连续中断 ID |
| `apps/runtime-service/tests/services/dearflow_agent/test_files.py` | 真实 JWT 委托＋Runtime ASGI：上传、下载、租户／graph／线程隔离、缺文件 404、symlink 与哈希损坏 |
| `apps/runtime-service/tests/services/dearflow_agent/test_execution.py` | 真实容器只读挂载、超时、128 KiB 输出上限、取消后无延迟文件副作用 |
| `apps/runtime-service/tests/services/dearflow_agent/test_restart.py` | 独立 PostgreSQL、两个 Python 进程、同一 Dear graph 的待审批 checkpoint 恢复。不是完整 GraphHarbor HTTP worker 重启演练 |
| `apps/runtime-service/tests/services/dearflow_agent/test_live.py` | 显式开启后调用已有真实模型，合成 TXT → 技能读取 → 容器处理 → 审批 → 真实产物；不覆盖平台登录页面 |
| `apps/runtime-service/tests/services/dearflow_agent/test_platform.py` | 显式开启后，登录本地平台，创建独立项目、注册 Dear Agent、查询能力、创建测试模型与真实 Run；finally 停用测试模型。当前部署模型代理 502，保留失败而非跳过或假成功 |
| `apps/platform-api/tests/test_run_requests.py` | 新增澄清 422 不创建 Run、正确回答续接、能力查询先授权测试，复用原幂等／撤权回归 |
| `apps/platform-api/tests/test_runtime_gateway_http_matrix.py` | 新路由纳入成功／无项目／禁止访问／脱敏矩阵 |

## P0 来源与锁版本

上游仓库 HEAD：`44ae750545caff29506906f4b0b1ebf79cb23fa7`。上游工作树有本地文档／脚本变更，不能将整个目录称为干净快照；以下参考文件单独记录 SHA-256：

| 文件 | SHA-256 |
|---|---|
| DeerFlow `LICENSE`（MIT） | `b23dff4d4bac8d17b6efaaa7e88c2b730149c4dda45699ce676b719cfdffe7e1` |
| `backend/packages/harness/deerflow/agents/lead_agent/agent.py` | `7c55780374bc732e56a2ff8843a357daf8e525e3002e2342115fad7b9049b0be` |
| `backend/packages/harness/deerflow/tools/builtins/clarification_tool.py` | `c84d8f5780803e3346f95a9d6618de01043336e0f8bffe0d2a5e98830d371ad8` |
| 本仓库 `apps/runtime-service/uv.lock` | `64d06689d456e2b02e43f4cbc522eb8d35ebe8ecd0673b5925a2c5b1792a8f58` |

本轮核验安装版本：DeepAgents 0.7.8、LangChain 1.3.17、LangGraph 1.2.11、SDK 0.4.3、GraphHarbor 0.13.0.post27。没有引入 DeerFlow 包或复制上游 23 项业务 Skill；烟测 Skill 为本项目资源。后续复制上游资源需保留 MIT 声明并逐项记录修订。

官方依据：LangChain Docs 的 Python DeepAgents permissions／Composite backends，以及本地锁版本源码。禁止使用覆盖沙箱默认路由的 permissions；write/edit 使用官方 Backend policy hook 扩展点。

## Store 风险结论

对独立 PostgreSQL 实跑 AsyncPostgresStore：跨连接读取、namespace 隔离和删除验证通过。`aput` 的公开签名没有 expected_revision／CAS 参数；P6 不能将普通覆盖写声称为并发修订保护，需要在那里实现最小原子版本控制并验证删除不复活。本轮不增加记忆 CRUD，也不建立第二套存储工厂。

## 验证运行方式

Runtime 目录：

```bash
DEAR_TEST_DATABASE_URI='<disposable PostgreSQL DSN>' .venv/bin/python -m pytest -q tests/services/dearflow_agent
DEAR_LIVE_TEST=1 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_live.py
uv build --wheel --out-dir /tmp/dear-p1-wheel --no-sources
```

Platform API 目录（现有环境没有 pytest，使用项目原有 unittest）：

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_run_requests.py' -q
.venv/bin/python -m unittest discover -s tests -p 'test_runtime_gateway*.py' -q
```

结果在本记录末尾回填；跳过的 live/数据库测试不算通过。临时数据库与业务数据库隔离，不读取或修改已有业务表。

## 实际验证结果

| 验证 | 实际结果 | 完成度与边界 |
|---|---|---|
| Dear 专属 graph、文件 HTTP、Docker、跨进程 PostgreSQL（不含 live 和完整部署） | **21 passed** | done；固定模型验证控制流，真实容器和数据库验证副作用／持久恢复 |
| `DEAR_LIVE_TEST=1 ... test_live.py` | **1 passed**，43.23 秒 | done；真实模型完成 TXT → 技能 → Docker → 审批 → 产物 |
| Platform `test_run_requests.py` | **20 tests OK** | done；真实应用服务＋SQLite 请求持久化，Runtime 调用为受控替身 |
| Platform `test_runtime_gateway*.py` | 39 项通过；路由矩阵发现能力响应未脱敏，修复后单独重跑该矩阵 **1 test OK** | done（受影响边界）；不是实服务 E2E |
| wheel | 构建成功，压缩包内 SKILL.md／check_text.py 内容存在 | done；输出在 `/tmp/dear-p1-wheel/` |
| Store | 真实 PostgreSQL 跨连接读、namespace 隔离、删除通过 | done（风险识别）；P6 CAS 实现不在本轮完成 |
| 完整 Platform → Agent Server 部署 | 项目、Agent 注册、能力查询、Run 提交通过；执行进入模型后失败 | **blocked**：模型代理 502／All connection attempts failed，尚未完成文本回答，更未通过部署文件全链路与 worker 重启 |

Runtime 专属测试命令需要提供隔离数据库 DSN；完整部署测试独立开启：

```bash
DEAR_PLATFORM_TEST=1 .venv/bin/python -m pytest -q tests/services/dearflow_agent/test_platform.py --tb=short -s
```

部署测试第一次遇到的 403 是测试项目缺少 Agent 注册，不是放宽权限的理由。已通过正常 `POST /api/projects/{project_id}/agents` 注册；运行模型需使用平台 catalog ID，不直接传默认 provider:model 字符串。当前平台已配置模型与本轮创建的独立测试模型均在 worker 流式调用中返回 502；直接 graph 的真实模型任务通过，不据此推断部署端也可用。

部署失败排查：`runtime-worker.log` 中 Run `a1cd932a-efa7-4b8e-a04b-da6ea5444dc3`，调用链进入 `langchain_openai.chat_models.base._astream` 后报 `OpenAIAPIError 502`。需要核查 worker 使用的模型连接／代理流式路径与上游网络，不通过关闭流式能力掩盖问题。测试未修改既有模型；本轮测试模型按 `dear-p1-verification-` 前缀单独建立并停用，独立测试项目／Run 保留供排查。

## 阶段结论

- P1 核心后端实现与上述分段验收 **done**；完整部署模型调用为 **blocked**，因此整个 P1 仍为 **partial**，不是“代码还没写完”或“只差 Docker 启动”。
- P0 的来源版本、官方交互、Docker 和 Store 风险识别已有证据；长任务 B02 尚未有任务服务的提交／ACK 丢失／重启证据，保持未完成，在媒体技能前必须解决。
- 当前没有宣称 GraphHarbor HTTP worker 重启通过，跨进程 PostgreSQL 测试不能替代它。前端按用户要求未改。
- Python 语法与文档链接检查通过；当前虚拟环境无 Ruff，未将编译检查记为 lint 通过。
- 独立 PostgreSQL 容器 `dear-p1-verification-db` 验证后已停止，保留数据便于排查；需要复测可执行 `docker start dear-p1-verification-db`，端口为本机 55439。未停止用户已有数据库、Runtime 或平台服务。

## 502 专项复查：最新结论

用户追问后进行了定向复查，本节更新上文的历史 blocked 状态：

- 两次部署失败为模型代理返回 HTTP 502，body 为 `Upstream error: All connection attempts failed`。这证明 worker 收到了 HTTP 错误响应，失败发生在代理继续访问其上游时；不是 Docker 执行失败，也不是已另行修正的 403 注册问题。
- 平台测试模型的 base_url 与直接测试一致；worker 的模型配置地址与代理环境已检查，未发现另一个 HTTP_PROXY／HTTPS_PROXY 配置。
- 同地址普通请求 HTTP 200；流式请求 HTTP 200；实际 `ChatDeepSeek.astream` 完整接收内容，19 个 chunk，约 1 秒。
- 再次执行 `DEAR_PLATFORM_TEST=1 ... test_platform.py`：**1 passed，43.42 秒**。平台注册、能力查询、受信模型连接获取、真实 Run 执行和最终状态读取通过。测试模型 finally 停用。
- 本次成功的 project：`1f7b5cc6-db5e-4751-90db-d1fd70bddcf3`；thread：`c81dabea-948c-471f-9d12-ea16cb43a781`；Run：`834978f1-9f87-4bd4-8cd2-7d8482eb460e`。

结论：此前 502 更符合暂时性／间歇性上游连接失败，当前复测已恢复；没有为此关闭 streaming、放宽权限或修改已有模型配置。尚无模型代理服务端日志，不能进一步断言是代理重启、上游宕机、DNS 还是连接资源问题。

P1 当前缺口已缩小为完整部署的文件／审批同任务闭环与 HTTP worker 重启验收；“基础部署模型请求持续 502”不再是当前阻塞。P0 长任务 B02 仍未完成。
