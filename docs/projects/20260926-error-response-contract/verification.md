# 错误响应统一 - 验证执行手册

## 1. 验证边界

本专项仅平台代码可改，Runtime/GraphHarbor保持现役版本、配置和数据结构。不得为了测试修改Runtime回查URL或新增调试接口。
确定性故障在平台测试adapter/MockTransport注入；真实Runtime只通过现有平台网关使用专属测试项目进行验证。
应用测试尚未执行；下面是实施者必须完成的计划，skip不计通过。

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

- [ ] H/U/M/P/F/S/B/C全部通过。
- [ ] 隔离浏览器通过；真实Runtime链路有独立证据。
- [ ] 新Web+旧API、新Web+新API通过；旧Web+新API风险已证实且上线顺序明确。
- [ ] 隔离回退到旧API+新Web，重复401/409/Blob/pending检查；不能把有旧安全缺口版本重新开放为生产回退。
- [ ] Runtime/GraphHarbor文件、依赖、配置与部署未变；无DB迁移。
- [ ] 成功流无新增全量缓存/网络调用；大错误输入只产生有界公开详情。
- [ ] 无敏感哨兵出现在浏览器/公开日志，临时数据清理结果已记录。
- [ ] 活文档与tasks/README状态一致。

## Phase证据（2026-09-26，仅规划研究）

- 锁定SDK源码：HTTPError保存status/text；Protocol流错误优先读取顶层message。
- 使用node --input-type=module、已安装Client与纯内存fetch进行探针，两次均503且只调用一次fetch：
  - 现行转换：threadIdPreserved=false、requestIdPreserved=true。
  - 目标转换：threadIdPreserved=true、requestIdPreserved=true。
- 没有调用网络、没有保存测试代码、没有修改业务实现。探针不覆盖实际授权fetch/Session/UI。
- 应用单元/集成/浏览器尚未执行。
- 本轮文档检查：scripts/check_docs.py、相对链接/代码围栏与git diff --check通过；这些不是应用功能测试。

## Final证据

未开始，待实施。每条记录包含命令、环境、revision、通过/失败/skip、残留与证据文件；不能复制其他项目成功数字。
