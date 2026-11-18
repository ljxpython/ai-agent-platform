# Agent 评测入口清理：实施与阶段验证

日期：2026-11-18。关联任务：[08 专题](../08-agent-evaluation-entry-cleanup.md)；任务状态只在该专题维护，本文件保存实施细节与证据，不构成整体验收（Final）通过。

## 范围、授权与环境

用户确认评测操作统一在 EvalFlow。Agent 仅保留当前会话“转为评测集”和“从历史会话建评测集”，历史列表可批量转换；后续出题、修订、发布、运行和诊断在 EvalFlow 完成。

用户已批准旧入口和重复助手清理；EvalFlow 在 `sshmy1:/opt/mlflow-eval-platform` 现场修改、验证及必要重载；准确远端地址、准确出口 IP 和回环 SSH 回调；最小依赖修复；新增一个仅属评测项目的执行者测试账号。没有授权删除业务数据、数据库降级、Git 提交/推送或无关生产变更。本轮未执行这些操作。

Agent 使用主工作区 Web3000/API2142/Runtime8123。EvalFlow 使用远端 Nginx9128/服务5000，未在本地镜像修改其后端。两个仓库的改动均未提交；本地 EvalFlow 镜像未执行 pull 或以文件覆盖远端。

## 清理边界与实现

- Web 删除 08 A 表列出的 12 个旧工作台/回答反馈/巡检文件，裁剪路由、消息列表和聊天接线。旧 URL 保留受权限守卫保护的迁移页，仅从 capabilities 取得合法 HTTP(S) 地址，校验 item UUID，拒绝凭据和客户端外链参数。
- 当前、历史、批量转换共用原提交弹窗；复用 workbench 能力和项目执行权限，保留 20 会话上限、时间/状态/分页、项目切换隔离，去掉好差评筛选。新增能力 composable、迁移页及历史选择测试。
- API 删除旧反馈、合成投递、巡检公开处理和仅供它们调用的 service/contracts 代码；旧 work-items 动作代理只保留 grant/revoke。保留转换、身份/签名、来源 ACL、用途、脱敏、回执、审计、撤权/停止和执行维护。公共测试夹具迁至 `apps/platform-api/tests/evaluation_fixtures.py`，平台助手与诊断测试继续使用。
- 删除 API `modules/evaluation/assistant_bridge.py` 及专属测试，裁剪路由注册、两个专属回调白名单和无剩余调用的绑定辅助函数。
- Runtime 删除 `graphs/evaluation_assistant.py`、`services/evaluation_assistant/{agent,workflow,prompts,tools}.py` 和专属工作流测试；裁剪 langgraph 注册、旧工具目录及专属身份/观测分支。保留 `dearflow_agent` 维护身份、历史安全分支、执行证据、环境和历史助手定义。
- 远端 `eval_platform/work_item_jobs.py` 删除两处向旧 Agent 助手 advance 的派发，保留发布/运行调度；`authoring_api.py` 跳过 authoring=false 调度，`work_items.py` 保留旧项读取/列表/汇总/授权管理并拒绝旧写，新建必须 authoring=true。EvalFlow 自己的出题 Agent 与 `advance_authoring` 保留。
- 通知改为“评测集【…】资料已送达”，明确到 EvalFlow 查看 AI 状态，发布和运行仍须另外确认；不再把资料交付误报为 AI 完成。旧通知不回写。

未删除 ORM、迁移、反馈/授权/评测历史或数据库。历史用途/维护仍有调用的配置和安全测试保留，没有按名称批量删除 evaluation 代码。

### 删除旧助手前的只读盘点

删除前，远端旧工作项与任务 JSON 均为 0；Agent 7 条 export 没有助手线程；Runtime 旧图会话/Run 均为 0。停止旧派发并完成远端回归、重载后，才删除本仓旧图。用户源会话未因此停止或删除。该结论只对应盘点时点，不表示远端没有后来本轮新建的 authoring 条目。

目标环境没有旧条目供浏览器验证；历史读取和旧写拒绝使用回归夹具覆盖，不伪造历史业务样本。

## 远端连接与依赖修复

Agent 新增 `evaluation_receiver_allowed_origins`，默认空；原本仅本地 HTTP 的规则保留，显式准确放行 `http://49.233.222.54:9128`。拒绝凭据、路径、query、fragment 和异常端口，HTTP 客户端不使用环境代理、不跟随重定向。`.env.example` 不含受信地址或密码。

远端仅追加准确出口 `111.227.13.240`，要求 `x-evalflow-request: 1`，保留 Host、本地 Origin/workspace 限制、签名和实时回源权限，不信任伪造 X-Forwarded-For。资料回调使用远端 `127.0.0.1:38375` → 本机 `127.0.0.1:2142` 的反向隧道，不开放公网回调端口。连接信息在本机 `.local-stack/evaluation-cleanup/callback-connection.json`；SSH master 为 `.local-stack/eval-ssh`。

现场 AI 出题首轮发现已声明的 deepeval/openai 缺失。按用户批准补装缺失包，原已安装包仅 click 从 8.5.0 调整为 8.3.3，其余锁定；依赖与约束证据在远端备份目录。另将不存在的 Mac `resource_file` 改为远端自身 `/opt/mlflow-eval-platform/.env`，tracking_uri 从拒绝连接的 5001 改为实际 5000；没有复制或打印密钥。

原配置备份在本机 `.local-stack/evaluation-cleanup/` 及远端 `.local-stack/entry-cleanup-backup-20261118/`。HTTP 没有 TLS；出口 IP 改变、本机 API 或 SSH 隧道离线会导致连接失败。该开发链路不是已经完成的跨机评测执行方案。

## 自动化阶段验证（Phase）

下列范围存在重叠，不相加为唯一样本总数。没有新产品改动后复用已有有效日志，不机械重复执行。

| 范围 | 实际结果 | 私有证据（所属仓库根目录下） |
|---|---|---|
| Web 相关 Vitest | 9 套 51 项通过 | `.local-stack/evaluation-cleanup/web-final-vitest.log` |
| Web 正常 `pnpm run build`、增量 ESLint | 构建包含 vue-tsc，通过；增量 ESLint 0 错误/警告 | 构建终端记录；`web-eslint.log` |
| API 扩大回归 | 188 passed，包含平台助手/诊断及共享安全夹具 | `api-final-pytest.log` |
| API 最后通知/路由/origin 修复后 | 60 passed | `api-router-final-pytest.log` |
| Runtime 回归 | 91 passed / 1 skipped / 5 warnings | `runtime-final-pytest.log` |
| Runtime 新 catalog 断言后 | 15 passed / 5 warnings | `runtime-catalog-final-pytest.log` |
| EvalFlow 远端扩大回归 | 585 passed / 1 warning | 远端备份目录 `regression-pytest.log` |
| EvalFlow 最终退役/准入/调度回归 | 22 passed | 同目录 `final-retirement-pytest.log` |
| API/Runtime 增量 Ruff | 通过 | 本轮终端记录 |
| EvalFlow Ruff | 修改行 0 条；相关文件全量仍 39 条原位置诊断 | 远端 `final-ruff.json` |

Runtime 跳过的是 `test_container_mounts_timeout_and_output_limit`，原因是 Docker daemon unavailable。保留原 SWIG 弃用告警、Starlette WSGI 弃用告警及 Web 的 Browserslist、chunk、canvas/Pinia/RouterLink 告警，不宣称全仓无告警。

本机 API/Runtime API/Worker 按所属 local-stack 脚本重载。正常刷新图/工具目录后，得到 5 个 Graph、83 个工具、5 个可选 Agent；没有旧 evaluation_assistant，dearflow_agent 正常，历史数据库定义保留。证据为 `live-catalog.json`。

## 真实浏览器与 HTTP 链路

使用 browser-skill 的 Agent Window 和获批合成资料。项目 `352e1fdd-10c3-44a5-820c-27ca2d7a7424`，被测正常 Agent `4a7ad779-e6ad-42e9-944e-5cf1949a1ac2`。没有采集客户业务数据或浏览器密码/cookie/token。

### 历史会话、真实出题与独立发布

历史算术会话 `f4ad4ddd-29d8-4aa6-a681-ccc900b3e601` 为纯合成 2 轮 4 消息。通过历史入口选择、确认用途，446.74ms 返回 202，通知跳转条目 `58ccbef8-47f8-5c57-826d-98091918911c`。

首次 AI 因资源文件路径失败，第二次候选结构失败，第三次 5 次调用成功；保留失败记录。采纳后手工去掉题面答案泄露，草稿 v2，再单独发布题库 v1，发布没有自动运行。题面为“计算17+26，只输出结果数字，不调用任何工具。”，预期 43。发布操作 `e31928a6-3858-4bf0-a3f0-96cb449c98db`，dataset `d-48b54849d87846169b11385af93c037c`。

显式运行操作 `888e7745-2d15-48da-844a-75f54e21a02f` 被源码验真阻止；随后正常停止为 cancelled，没有 task_id 或被测评测 Run。详见下一节，不能将旧本地成功运行作为这次远端运行证据。

### 当前会话、幂等与批量

当前转换条目 `fccec732-1f93-543b-a8a1-18fbe713b3c5`：362.66ms 返回 202，弹窗关闭，“资料已送达”通知进入正确条目；自动出题 3 次调用成功，候选未采纳/发布。相同 actor/body/request_id `d8441795-acd4-48b9-80ac-e28fc1ff9e9e` 重试返回 200/reused=true，条目、来源摘要和 AI 作业 ID 不变，无新作业。证据为 `live-idempotency.json`、`current-authoring-debug.json`。

新建合成聊天 `777dd271-8d41-4cf2-9164-12b06c7ca2f2`，输入 6+7 并要求不用工具，实际回答 13；正常历史和推荐问题保留，无回答评价/AI 改进入口。将该会话与历史算术会话批量提交到 `3c33cb78-8905-5cbb-b155-0e45603213b5`，远端实际收到 2 段 6 消息，通知准确。该条目 AI 首稿 3 次调用后因 `answer_contains requires nonempty assertions` 失败，0 发布/0 运行；未扩大修改 AI 生成器，也不把资料完整交付写成批量出题成功。

旧详情 URL 实测显示迁移说明和准确远端链接，无旧操作或自动提交；导航没有“评测与改进”，Agent 下拉没有旧助手。截图在本机证据目录：`history-submit.png`、`history-notification.png`、`remote-published.png`、`current-delivered.png`、`chat-cleaned.png`、`legacy-moved.png`、`batch-delivery-notification.png`、`batch-remote-sources.png`。分页与 20 条上限有组件/API 证据，尚无真实多页规模的连续翻页浏览器证据。

### 专用普通执行者与权限负例

按本轮明确批准，通过正常管理接口新增用户 `36472270-f19b-4d83-9a02-bfec3a65a48a`，仅授予上述项目 `project_executor`，无平台角色；未修改既有用户权限。凭据只在本机 0600 私有文件 `member-account.json`，不进入本记录。

该成员通过正常 HTTP 新建合成会话 `65ff3bc4-a4d4-4f5d-807b-403a097bf572`，普通 Run `799f232e-2842-432d-8e8b-4d3d85b1066d` 成功。首次把平台 Agent UUID 当 Runtime assistant_id 请求得到 403，按实际契约改为 `dearflow_agent` 图 key 后成功，未改产品权限逻辑。

- `auto_generate=false` 交付返回 202，条目 `f23d706f-b9b4-51fa-a032-912abd1fdfb9` 实际 1 段 2 消息、0 AI jobs、0 grants。
- 成员要求自动出题或自行 grant 均为 403；有 execute 而无 AI 用途授权，远端 generate 为 409“需要资料负责人授权”。
- 尝试管理员私有会话，HTTP 200 中业务状态明确 failed、materials 为空、无条目；跨项目 authoring 命令 403。HTTP 200 不被写成业务成功。
- 管理员也不能越过成员私有源 ACL。成员仅向该管理员显式分享本次合成 thread 的 read 后，管理员 grant/revoke 均 200；grant `6822f270-f848-467d-8409-4983cec47739` 已撤销，随后撤回 read 分享，恢复私有。没有改变项目级分享，也未发布/运行该成员条目。

证据为 `member-live-check.py`、`member-live-result.json`。这是两个真实身份的 HTTP 权限链路；普通成员浏览器未实测，不冒称双账号浏览器验收。

## 当前未通过的验收条件

**跨机源码验真：** 远端 `.local-stack/evaluation.json.agent_repo` 仍是本机 Mac 路径。`eval_platform/targets/catalog.py::resource_snapshot` 直接读取该路径下 Runtime 源码，实际报“缺少所属 Runtime 源码，无法记录提示词/内置技能版本”。`eval_platform/deployment.py::deployment_manifests` 还要求同机两个 app 的 `.venv/bin/python` 产生 STARTUP_MANIFEST，并与源码包哈希匹配。HTTP 资料回调不满足该同机假设。未改指远端旧 Agent 仓、伪造哈希、跳过校验或新增通用源码接口；需用户确定可信跨机源码/构建清单接入方案，再补成功运行和审批链路。

**2026-11-18资产原则纠正：** 此前将早期隔离资料到期封闭规则扩展到后来独立题库，并列为待人工裁决，是本轮判断错误。用户明确重申已生成题库即使到期也应正常使用，作为独立资产；远端Copilot专项README的D7也已写明保留永久题库资产保护。现以该既定原则补V8.5到期回归，不再等待题库保留政策裁决。继续取源与题库自身权限仍校验；原始会话快照的留存/访问规则未在本次澄清中改动，原真实grant/revoke和取消证据也不证明原始资料已清除。

### 隔离 API 回退与再升级

私有脚本 `api-rollback-probe.py` 用 `git archive HEAD` 提取旧 API、复制当前 API 到另一个私有临时目录，使用独立合成 SQLite。未接主库、创建分支/Worktree、复制依赖或降级数据库。

实际按 current-initial → old-rollback → current-upgrade 启动完整 FastAPI lifespan；三阶段正常登录/capabilities 均 200，两个保留 materials 路由均 422 参数校验而非 404，历史 export payload/receipt/status/expiry 摘要相同：`034a184f5dc54b6a9900b63425fd752fadaf0af350a6794a34d84fe75991a26e`。初始隔离配置缺成员/委托而失败，补齐测试配置后通过，未为此改产品。日志在 `api-rollback/`。

该证据只覆盖 API 应用回退/再升级，不覆盖 Web/Runtime/EvalFlow 全栈回退，也不证明跨机评测恢复。V8.3、V8.5、V8.7 及真实多页资料规模仍未全部满足；不能报告 08 整体完成。

## 改动保护与交付限制

本机 IAM policy、其测试及两个 UsageDashboard 文件按 `baseline-hashes.json` 核对，未覆盖他人改动；`routes.ts` 保留既有 usage 权限 any/双权限和仅项目入口的差异。远端未触碰既有私有 `.env.bak.20261118081154`，上游 `mlflow/` 状态为空。

现行助手指南、README、FEATURES、CHANGELOG 和两仓 CONTEXT 同步本轮行为及未验范围；原 01–07 和既有失败保留历史事实。收尾尝试关闭原 `ppwq` 会话时工具返回未注册，随后会话列表为空、浏览器 session_count 为0，确认没有残留工具会话；主服务及 SSH master 保留。远端5000未认证探测401，使用现有后台认证后200，未为探活放宽认证；公网9128与回调健康检查200。没有 Git 提交、推送或超出批准范围的部署。最终检查结果在同证据目录 `closeout-check.json`。
