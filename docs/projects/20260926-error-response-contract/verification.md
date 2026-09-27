# 错误响应统一 - 验证执行手册

## 1. 验证边界

本专项仅平台代码可改，Runtime/GraphHarbor保持现役版本、配置和数据结构。不得为了测试修改Runtime回查URL或新增调试接口。
确定性故障在平台测试adapter/MockTransport注入；真实Runtime只通过现有平台网关使用专属测试项目进行验证。
只验收新Web+新API；旧Web、旧API、混用组合及旧API回退不设测试或Final门禁。下面是验收计划，skip不计通过；实际结果见Phase与Final独立记录。

## 2. Phase用例（必须实现的测试）

| ID | 输入/触发 | 精确断言 | 文件 |
|---|---|---|---|
| H01 | 本地业务异常含details/extra | status/code不改；根request_id=响应x-request-id；无meta迁移 | test_core_error_handling.py |
| H02 | 422含input/ctx/自定义秘密message，21项、非法loc/type | 只输出≤20项安全字段；无秘密；非法项丢弃 | 同上 |
| H03 | 401/403/404/405/429 | 401原code保留；405安全Allow；无Set-Cookie；有效Retry-After保留 | 同上 |
| H04 | create_app相同中间件顺序中路由抛含秘密的异常 | 500 JSON固定文案；x-request-id存在；正常Origin可读；日志无异常正文 | test_error_response_contract.py（新增） |
| H05 | 异常请求结束后再发正常请求 | ContextVar不串；身份/项目不混；取消不被转成500 | 同上 |
| U01 | error/detail/top/code string/未知JSON/HTML/空体/错误类型 | 按plan优先级；同一层字段配套；未知安全fallback | test_runtime_upstream_errors.py |
| U02 | 上游401/403/422/429/500/503；超时/连接失败 | 原状态与公开状态分离；401→502；503→502；timeout504；返回UpstreamServiceError | 同上 |
| U03 | error-catalog表驱动所有登记码 + 错误来源状态 + 未登记码 | 精确匹配，不用前缀allowlist；固定message | 同上 |
| U04 | 嵌套自由文本凭据/Authorization/模型Key | 公开body无哨兵、upstream_path/任意upstream_detail不存在 | 同上 |
| U05 | cursor_expired410/recovery有效或恶意值 | 仅thread_snapshot保留；没有其他upstream_detail字段 | test_runtime_gateway_sdk_adapters.py |
| M01 | memory_storage_unavailable来源503、memory_revision_conflict409、422 | 外部502仍保留存储不可用code；冲突409；校验details不被wrapper抹掉；无事实原文 | SDK adapter + test_runtime_gateway_memory_contract.py |
| P01 | create经真实公共转换函数得到401 | 对外502，但pending按真实401清理；浏览器不刷新登录 | test_thread_acl.py |
| P02 | create超时/500，探测404 | pending保留；extra含平台UUID及reconcile_path | 同上 |
| P03 | create500，探测同ID成功 | 返回原Thread，mark ready，只创建一次 | 同上 |
| P04 | 确定4xx后清理失败/ready失败 | 503 thread_provisioning_unconfirmed及ID保留 | 同上 |
| P05 | 探测签发失败/再次网络失败 | 原未知结果与ID保留，不丢异常字段 | 同上 |
| P06 | 非本人/异项目reconcile | 权限拒绝，无Thread信息/恢复ID泄露 | 同上 |
| F01 | Axios/SDK.text/对象/Blob相同Envelope | status/code/message/requestId/details/extra一致 | http-error.spec.ts（新增） |
| F02 | 授权fetch→实际SDK→Session create返回完整503/504/502错误 | pendingID保留；第二次先reconcile；创建计数1；不同用户/项目隔离 | session.service.spec.ts |
| F03 | 401刷新成功/失败、403、logout迟到响应 | 最多一次刷新；幂等键不变；原权限/会话代次机制保留 | langgraph/client.spec.ts、http/client.spec.ts |
| F04 | 非JSON、HTML、64KiB边界、取消、非法请求ID | 无原文提示；取消独立；只显示合法请求编号一次 | http-error.spec.ts |
| F05 | createLanggraphClient写请求得到502 | 网络调用计数1，SDK不自动重放；Session原maxRetries0保持 | langgraph/client.spec.ts |
| S01 | SSE握手拒绝/timeout | 先返回JSON4xx/5xx，不发送200或完成帧 | test_runtime_gateway_sdk_adapters.py |
| S02 | 成功流/下载开始后传输中断 | 资源关闭；无HTTP Envelope追加；未完整消费成功流到内存 | 同上 |
| B01 | Blob下载401/403/404/502 | 解成错误，不作为成果下载 | threads/workspace.service.spec.ts、images.service.spec.ts |
| C01 | 成果409/Skills冲突/Terminal输入冲突/Memory各码 | 原消费行为保持；只重试原本允许的读/已有幂等业务行为 | 现有service/composable测试 |

P测试必须从create_runtime_upstream_error得到异常，不允许只手造子类掩盖转换函数与catch类型不一致。

## 3. 命令入口

从仓库根执行，不在文档命令里加入rtk前缀。下列新增文件由对应任务实现后执行，不把不存在的测试算完成。

```bash
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_core_error_handling.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_upstream_errors.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_runtime_gateway_sdk_adapters.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_thread_acl.py"
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests" -p "test_error_response_contract.py"
pnpm --dir "apps/platform-web" exec vitest run "src/utils/http-error.spec.ts" "src/services/langgraph/client.spec.ts" "src/services/threads/session.service.spec.ts" "src/services/runtime-gateway/workspace.service.spec.ts" "src/services/http/client.spec.ts"
pnpm --dir "apps/platform-web" exec vitest run "src/services/dear-agent/memory.service.spec.ts" "src/services/dear-agent/skills.service.spec.ts" "src/services/threads/workspace.service.spec.ts" "src/services/threads/images.service.spec.ts" "src/composables/useArtifacts.spec.ts"
pnpm --dir "apps/platform-web" typecheck
```

Phase按改动选择上面最小集合。API测试用临时SQLite/MockTransport，不能加载正常业务库执行写入。

## 4. 隔离HTTP和浏览器测试的实现约定

新增 `apps/platform-api/tests/fixtures/error_contract_server.py`：
- 参考现有governance_server.py的临时SQLite生命周期与测试用户初始化，复用create_app，不改生产router/鉴权。
- 只监听127.0.0.1:12143，要求RUN_ERROR_CONTRACT_E2E=1；无开关直接退出。
- 启动时临时目录隔离DB，禁用生产OIDC/bootstrap；创建测试项目和owner/peer。内部身份通过测试登录，不在输出日志打印token。
- 通过app.dependency_overrides的gateway service/upstream依赖注入受控adapter；调用真正公共错误转换，不把写死最终Envelope当集成。
- 固定模拟路径场景：Thread create未知结果→同ID pending→ready；私有Thread peer403；workspace读取不存在404；文件读502/Blob；协议stream握手410；普通业务422。
- 场景按独立测试fixture ID区分，禁止由生产请求头启用故障。fixture只存在tests目录。
- 新增e2e/error-response-contract.spec.ts使用12143 API、13001 Web；Browser登录owner/peer，操作现有页面，断言可见提示/请求编号和Network错误结构；在测试上下文统计create/reconcile请求。
- fixture退出核对自有临时状态；不启动或调用Runtime。该项只能证明Web→真实API→受控上游，不能标作真实三服务E2E。

三个终端分别执行：

```bash
RUN_ERROR_CONTRACT_E2E=1 "apps/platform-api/.venv/bin/python" "apps/platform-api/tests/fixtures/error_contract_server.py"
VITE_PLATFORM_API_URL=/ VITE_DEV_PROXY_TARGET=http://127.0.0.1:12143 pnpm --dir "apps/platform-web" dev --host 127.0.0.1 --port 13001
RUN_ERROR_CONTRACT_E2E=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:13001 pnpm --dir "apps/platform-web" exec playwright test "e2e/error-response-contract.spec.ts" --project chromium --workers 1
```

已核对config/env.ts：本机DEV会将loopback API地址改写为同源，因此必须设置VITE_DEV_PROXY_TARGET到12143，不能仅设置API_URL。端口被占用不杀无关进程，选择另一对端口并记录实际值。

## 5. 固定Runtime不变的真实链路验收

在用户提供或现有已就绪的测试平台栈执行，不重配Runtime，不改其ACL回查地址。
- 登录测试平台，在专用临时项目创建owner/peer账号关系；经平台正常创建Thread/授予必要Agent/模型权限。
- owner读取Thread成功，peer访问私有Thread得到403，断言HTTP Envelope；owner读取不存在的workspace文件得到404（已有工作区时执行）。
- 对已开启个人记忆的测试项目读取当前revision后用过期revision提交修改，得到409/memory_revision_conflict；没有该能力时用Skills已知revision冲突作为替代，并记录实际场景。
- 正常Run和下载至少各一条不回归；SSE前置权限拒绝保持非200。流内协议恢复不在本项验收。
- 记录应用revision、SDK版本、Runtime现役版本、请求ID/响应快照；严禁记录token/模型密钥。
- 仅删除本轮创建的Thread/项目，经平台合法入口清理；没有授权的已有资源不删除。无可用测试栈则记partial，不能改Runtime突破范围。
- 可以复用现有集成配置PLATFORM_RUNTIME_INTEGRATION、PLATFORM_API_BASE_URL、PLATFORM_API_ACCESS_TOKEN、PLATFORM_API_PROJECT_ID指定测试目标；不得照跑旧正向集成脚本的过时响应形状断言。新增错误集成用例写入test_error_response_contract.py并用该开关隔离。

## 6. Final命令与判据

```bash
"apps/platform-api/.venv/bin/python" -m unittest discover -s "apps/platform-api/tests"
pnpm --dir "apps/platform-web" test:run
pnpm --dir "apps/platform-web" typecheck
pnpm --dir "apps/platform-web" build
python3 "scripts/check_docs.py"
git diff --check
```

对本轮API修改文件跑现有Ruff、对Web修改文件跑现有ESLint/Prettier检查；使用现有开发依赖，不安装/升级核心依赖或格式化无关文件。
记录现有全量失败与本专项失败的区别；任何本专项失败必须修复，历史失败不能忽略不报。

- [x] H/U/M/P/F/S/B/C全部通过。
- [x] 新Web+新API隔离浏览器通过。
- [x] 真实Runtime链路有独立证据。
- [x] 新Web+新API+当前Runtime通过；旧版本组合不属于本轮验收。
- [x] Runtime/GraphHarbor文件、依赖、配置与部署未变；无DB迁移。
- [x] 成功流无新增全量缓存/网络调用；大错误输入只产生有界公开详情。
- [x] 无敏感哨兵出现在浏览器/公开日志，临时数据清理结果已记录。
- [x] 活文档与tasks/README状态一致。

## Phase证据（2026-09-26，仅规划研究）

- 锁定SDK源码：HTTPError保存status/text；Protocol流错误优先读取顶层message。
- 使用node --input-type=module、已安装Client与纯内存fetch进行探针，两次均503且只调用一次fetch：
  - 现行转换：threadIdPreserved=false、requestIdPreserved=true。
  - 目标转换：threadIdPreserved=true、requestIdPreserved=true。
- 没有调用网络、没有保存测试代码、没有修改业务实现。探针不覆盖实际授权fetch/Session/UI。
- 应用单元/集成/浏览器尚未执行。
- 本轮文档检查：scripts/check_docs.py、相对链接/代码围栏与git diff --check通过；这些不是应用功能测试。

## Phase 验证记录（2026-09-26 实施）

- **基线：** 开始时 HEAD `8307495ff1426274f8b1644c8b4ef622a27d8ae8`，工作树已有 runtime-service、runtime_catalog、治理文档等他人改动，未覆盖；实施中他人提交将 HEAD 推进至 `e35b80debaad7e8b27f55487dddfead0a75b712f`。本专项改动仍未提交。Web 锁定 `@langchain/langgraph-sdk@1.10.2`；本机 URL `http://127.0.0.1:3000`、`:2142`、`:8123` 可达，但无 `PLATFORM_API_ACCESS_TOKEN`/专用项目环境变量。未记录凭据值。
- **E1.1：** `vitest run src/utils/http-error.spec.ts` 2 通过；Axios/SDK.text/Blob 字段、HTML与64KiB兜底、取消和请求编号。`vue-tsc --noEmit` 通过。
- **E1.2：** `vitest run` client、session、runtime-gateway workspace 共 20 项通过；追加授权 fetch → 已安装 SDK → Session pending 对账用例，创建计数 1；SDK 写请求 502 调用计数 1；401 单次刷新和幂等键原测试通过。
- **E2.1：** `test_runtime_upstream_errors.py` 4通过，精确码表、来源/公开状态和未知正文；`test_runtime_gateway_sdk_adapters.py` 19通过。另以只读脚本对比 `error-catalog.md` 全部4xx登记码与 `_PUBLIC_CODES`，`missing=[]`、`extra=[]`；修正了 `memory_setting_required` 为来源400。
- **E2.2：** `test_core_error_handling.py` 最终6通过（新增响应头白名单），`test_error_response_contract.py` 1通过，`test_runtime_gateway_memory_contract.py` 7通过；真实 create_app 中 500 与上游401转502均有固定JSON、CORS和匹配请求ID，日志/正文无测试哨兵。
- **E2.3：** `test_thread_acl.py` 28项通过、3项原有跳过；其中确定401通过公共转换函数进入创建分支，公开502且清理 pending。`test_run_requests.py` 25通过，内部401公开502但幂等记录按来源状态标记确定拒绝。`test_runtime_gateway_workspace.py` 4通过，固定公开安全文案。
- **E3.1：** `test_error_response_contract.py` 真实应用栈 HTTP 断言通过；`RUN_ERROR_CONTRACT_E2E=1` 隔离 fixture + Chromium 1项通过（12143 API、13001 Web）。浏览器授权fetch/SDK/Session创建一次、对账两次；peer403、workspace404/502、普通422响应结构及无秘密哨兵。fixture退出后自有状态文件已清理，两个临时端口已关闭。该受控链路不计作真实 Runtime 验证。
- **E3.2：** 文档与状态局部同步；Final 门禁缺项，不记通过。

## Phase 验证记录（2026-09-27）

- **E3.1 真实链路：** `PLATFORM_ERROR_CONTRACT_REAL=1` 执行 `test_error_response_contract.py`，2项通过。临时项目与 Agent 下，memory 为 `ready`，过期 revision 返回409 `memory_revision_conflict`；不存在的私有 Thread 返回403，错误正文 `request_id` 与响应头一致。两次相同幂等键提交请求编号 `fd035302311040529a3be5a7e231cf48` / `1ad1e1708cd14ac6a110e20511928780`，共用 submission `e0188a34-dcfa-4c77-8011-723df3b5f3ae`、Run `e3d5e635-e57b-4c97-89ef-5e5ddef4c050`；Run 状态 `success`，两条审计记录可按请求编号查询且关系一致，Langfuse trace `556f410a54c5eb54450e0a6629a4e821` 的可信 metadata 命中提交编号。测试 Thread 与项目先后经平台 DELETE 返回200；无凭据输出。
- **E3.1 SSE 回调：** `test_runtime_gateway_event_redaction.py` 8项通过；发送 `http.response.start` 失败不记录 opened，帧拒绝后 closed 保留 `frame_rejected`。真实 Run SSE 返回200并产生数据帧；请求编号 `44c9d72acb084483a3c7b09c3283dbce` 在现役平台日志的 `runtime.stream.opened/closed` 两条记录中均与同一 Run ID 匹配。日志必须使用服务实际启用的 INFO 通道；仅调用回调但日志未落地的初次检查曾失败，修正后复测通过。
- **E3.1 浏览器：** 现役 Web Chromium `chat-refactor.spec.ts --grep "Chat 1280"` 1项通过（3.5分钟，真实 Run/审批/恢复）；`RUN_ERROR_CONTRACT_REAL_E2E=1` 的错误专项用例 1项通过，真实平台403的 Network `request_id`、响应头及页面可见编号一致。该条记录创建时真实 peer 尚未补验，后续同日补验已通过并记录如下。
- **E3.2 已完成的回归：** Web 全量 `pnpm --dir apps/platform-web test:run` 为93套通过、1套既有跳过，397项通过、1项跳过；`typecheck` 与 `build` 均退出0，构建仅提示现有大 chunk。Playwright 文件 ESLint、定向 Ruff 新测试2文件及路由 `I,SIM` 均通过；完整路由 Ruff 仍有既有 `Depends` 诊断。隔离 Chromium 原错误用例复测1项通过，12143/13001已关闭，fixture状态文件已清理。`scripts/check_docs.py` 与本轮限定文件 `git diff --check` 通过；仓库全量 `git diff --check` 因另一个专项已有SDK patch的空格+tab告警退出2，未改该patch。
- **E3.1 真实补验：** 显式开启的 `test_real_submission_run_audit_and_observation` 复测 1 项通过，owner 读取 Thread 返回 200；不存在 Thread 的 `/stream/events` 握手返回 403 且无 `text/event-stream`；幂等提交仍共用 Run，Run 为 `success`，两条审计记录和 Langfuse trace 均匹配提交编号，SSE opened/closed 匹配流请求编号。临时 Thread 和项目先后经平台 DELETE 返回 200。现役 `reference_agent` 的上传和读取返回 `runtime.tool.not_allowed`，后续通过自动创建的 `showcase_demo` Agent 完成 workspace 上传、读取及缺失文件 404，详见下一条补验记录；未修改 Runtime 权限或跨越服务边界。
- **E3.2 API 全量：** 手册原命令无 `PYTHONPATH` 运行278项、13跳过、9个导入错误，不能算通过；按既有手册补 `PYTHONPATH=apps/platform-api:apps/platform-api/src` 实跑 301 项，285 通过、15 跳过、1 错误。先前 `test_runtime_gateway_http_matrix.py` 的 7 处错误来自手工测试上下文缺 `request_id/trace_id`，补齐两处后该文件 3 项通过；随后补齐 `test_thread_fork` 替身的 `create_thread`、`update_thread_state` 并更新现役 delegation factory 断言，最终全量为 301 项中 286 通过、15 跳过、无错误。Alembic只操作测试临时 SQLite，没有对现役数据库迁移。
- **E3.1 最后复测：** 增加 SSE 握手前 403 的正文编号与 `x-request-id` 一致断言后，显式真实用例 1 项通过。两次提交请求编号 `607359dfee654da49326182c21ca6d12` / `bdead868a7614d549bde7efdaaa7c4ad` 关联同一 submission `d954719a-f9e0-4429-acd6-1600a057613e` 和成功 Run `eff87ac3-038c-4fe2-8b3a-6a609d2e13c7`；Langfuse trace `0ff9c244f643d6066e51707e24ea9b0f`，SSE 请求编号 `9e7a66814a694142b066daf3af609ffb`。临时 Thread 和项目经平台接口清理。

 - **E3.1 真实 peer/workspace 补验：** 真实用例通过平台 API 自动创建第二测试身份、临时项目、`showcase_demo` Agent 和 owner/peer Thread。peer 读取 owner 私有 Thread 返回 403 `thread_action_denied`，根级 `request_id` 与 `x-request-id` 一致；授权 Agent 完成 workspace 文件上传、读取并校验内容一致，不存在文件返回 404 `workspace_file_unavailable`。临时成员、Thread、项目和 peer 均通过平台 API 清理（peer 设为 disabled）。现役 `reference_agent` 仍返回 403 `runtime.tool.not_allowed`，属于既有 Agent 工具授权基线差异，不改变 Runtime 权限，也不影响 `showcase_demo` 正向证据。

## Final证据

### 2026-09-27 Final（已完成）

状态 `done`。E3.1 的真实请求→提交→Run→审计→Langfuse、SSE opened/closed、memory 409、peer 403、workspace 上传/读取、缺失文件 404 及资源清理均已通过；`reference_agent` 的 `runtime.tool.not_allowed` 已明确为既有工具授权基线差异。E3.2 API 全量实跑 301 项，286 项通过、15 项跳过、无错误；此前 fork 测试替身缺少 `create_thread`/`update_thread_state` 已修复。Web 全量 397 项通过、1 项跳过，typecheck、build、文档检查和本轮定向质量检查通过。Runtime/GraphHarbor 未修改，未执行迁移、部署或 Git 操作。

### 2026-09-26 Final（历史快照：partial，已由 2026-09-27 Final 取代）

- **API 全量：** `PYTHONPATH=apps/platform-api:apps/platform-api/src ... unittest discover -s apps/platform-api/tests` 最终实跑286项，271通过、14既有跳过、1错误。唯一错误为 `test_thread_fork.test_fork_invokes_workspace_fork_when_delegation_configured` 的既有 `SimpleNamespace` 替身缺 `create_thread`；`fork_thread` 调用路径不在本专项改动范围。本专项旧安全文案断言已更新并在最终全量通过。最初无 PYTHONPATH 的手册命令有9个导入错误，属测试入口问题，不能算通过。
- **Web 全量：** 最终 `pnpm --dir apps/platform-web test:run`：90套中89通过、1既有跳过；376项中375通过、1既有跳过。此前两轮的Blob新增编号与工作台Cloudflare/Protocol 409提示断言已修复并在最终全量通过。
- **构建/类型：** `pnpm --dir apps/platform-web build` 与 `typecheck` 通过；定向 ESLint 通过。`uvx --offline ruff check` 对本轮新增核心错误模块及fixture/test共8文件通过；其余大型既有文件直接全文件检查出现历史 Ruff 诊断，未把全文件 Ruff 记通过。`compileall` 通过。
- **组合：** `test_error_response_contract.py` 经真实 create_app 中间件/handler，受控转换通过。隔离 `error_contract_server.py` 在临时SQLite及受控上游运行，Chromium `e2e/error-response-contract.spec.ts` 1项通过；仅证明新Web+新API+受控上游。启动时测试用户仓储必填字段缺失，补正后重新启动并通过；测试进程停止后 `/tmp/platform-error-contract-e2e.json` 已清理，12143/13001关闭。现役浏览器入口3000→平台API只读401基线曾检查，但无法证明本轮代码版本，不计本专项E2E。现役三服务端口可达，但缺测试专用项目凭据与隔离数据；真实 Runtime 链路明确为**未验证**。
- **最终增量复核：** 补 Run 来源401状态判断后 `test_run_requests.py` 25通过；补固定网络/HTML提示后受影响Web 14通过、typecheck/ESLint通过；补 4xx 登记状态后上游映射4通过。`scripts/check_docs.py`、`git diff --check` 再次通过。这些增量复核不替代未执行的真实 Runtime 门禁。
- **范围：** 未改 Runtime/GraphHarbor 文件、配置、依赖、协议和数据库；未迁移、部署、提交或操作分支。未创建临时平台业务数据，无需清理。`scripts/check_docs.py` 与 `git diff --check` 曾通过；文档修改后将复核。
- **阻塞/后续：** 需专用项目凭据以完成真实三服务链路；新旧组合与隔离回退门禁已按2026-09-26统一版本边界移除。API全量那个无关fork fixture错误需另案修复或确认基线；其余本轮触及的大型历史文件仍有既有 Ruff 基线诊断。当前结论为 `partial`，不是 Final 通过。
- **范围收敛复核（2026-09-26）：** 仅保留新Web+新API验收；相关测试目录无旧版组合/回退专用用例可删除。`scripts/check_docs.py` 与 `git diff --check` 通过；真实Runtime链路仍为**未验证**，此文档复核不改变Final的`partial`结论。
- **本地真实栈补验（2026-09-26）：** `scripts/local-stack.sh status` 确认 Runtime API/Worker、Platform API、Platform Web 运行。使用本地 bootstrap 管理员和现有项目，`/api/langgraph/info` 返回200；真实 Thread 创建返回200（request_id `2972f33387634f06b2d1f7aae382b1fd`）；不存在 workspace artifact 返回404 `artifact_not_found`，保留 `upstream_status_code=404`（request_id `692b901748ff452b9b85547399adac32`）；非法 assistant Run 返回403 `runtime_target_denied`（request_id `98f253ccb4c14fa08e14234a0de8e077`）。另执行真实审批 Run，状态 `interrupted → approve → success`，约24秒。临时 Thread 均已删除。专用 peer/memory 与真实浏览器仍未验证。
- **真实 Runtime 链路尝试（2026-09-26）：** 本机 `http://127.0.0.1:2142` 与 `http://127.0.0.1:8123` 可达；执行 `test_runtime_graphharbor_http` 得 `Ran 5 tests in 0.003s; OK (skipped=3)`。当前环境未注入 `PLATFORM_RUNTIME_INTEGRATION=1`、`PLATFORM_API_BASE_URL`、`PLATFORM_API_ACCESS_TOKEN`、`PLATFORM_API_PROJECT_ID`、`PLATFORM_API_EXPECTED_UPSTREAM_URL`，因此真实请求未发出，Runtime 链路仍明确标记**未验证/阻塞**，没有用 mock 或 skip 代替通过。
