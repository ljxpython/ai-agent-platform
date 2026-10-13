# Runtime 单节点远端 Docker 沙箱：验证计划与记录

> 2026-10-13：用户明确本期验收通过、剩余问题后续处理；项目状态 done（用户验收），T00–T15 本期收口。三模式/单节点公网链、安全/性能/进程恢复/应用回退已有真实证据，B01/B02 解除，wawapii 真实生图通过。I10 整机部分/后续独立 Final、真实编辑、留存夹具和残留 interrupt 排查按 [F01–F04](follow-ups.md) deferred；这不表示未执行测试通过。下列状态区分锁定契约、受控供应商、真实模型、公网与实际设备，跳过不计通过。

## 验收环境与证据要求

| 环境 | 必要条件 | 证明范围 |
| --- | --- | --- |
| local | 所属 Worktree 原生 PG / Redis，`RUNTIME_BACKEND=local`，隔离账号 / Thread / 路径 | 原有开发能力与回归；不证明远端 Docker 可用 |
| 本地 Docker | 显式沙箱测试需求下启动本地 Docker，既有预置镜像，target=local | 原有容器执行与清理；验证后回收项目专属资源 |
| remote | 真正的 Runtime API / Worker 主机或容器经公网 HTTPS + mTLS 连接 sshmy2，镜像 / Node / 证书 / caller 认证与出口 IP 允许列表就绪 | 远端文件、执行、终端、后台、重启与回收；不能用 mock 替代 |

本地联调遵守 [Worktree 规范](../../standards/worktree-development.md)，不使用其他 Worktree 的数据库 / `.venv` / `node_modules`。真实模型优先 miaomiaoai `deepseek-v4.1-flash`；故障注入不关停共享 daemon、不破坏其他域数据。

证据记录模式、协议 / 应用版本、镜像 digest、时间、场景、脱敏 Thread / resource 标识、请求与实际结果。对恢复文件核对字节 hash；对执行重放使用可计数副作用文件；对清理确认使用 inspect / 节点记录，不能只看 HTTP 200。token、SSH / TLS 私钥、原始用户敏感文件和模型 Key 不进入记录。deer-flow 的代码和测试在 [复用矩阵](deerflow-reuse.md) 中标注来源；来源检查或上游单测不能冒充 Runtime 已接入。

## 单元测试计划

| 编号 | 必须验证的行为 | 对应任务 | 状态 |
| --- | --- | --- | --- |
| U01 | 原 backend 默认、local-stack 初始 local、所属 env 显式 docker 可生效、docker target 缺省 local；普通 local 不连接 Node；local ↔ 本地 Docker 目录保持 | T01–T02 | done：86 项兼容基线、配置与 Worktree env 自检 |
| U02 | local 后台启动仍受门禁，旧任务查询 / 回执 / 取消不丢失；Office 固定 Docker reader 例外保持 | T01、T09 | done：后台兼容、真实 PG 历史读取与 Office 契约 |
| U03 | remote 必填键、非法 target、HTTP / 跨主机重定向拒绝；CA / SAN / 证书文件配置校验；URL / node / caller 域不符或 token 错误拒绝；禁环境代理 / 副作用重试，秘密脱敏 | T02–T03 | done：Node/client 60 项、TLS 信任 4 项、源 IP/HTTP 与回查 8 项 |
| U04 | 绑定首次原子建立、隔离执行域 / scope / graph、旧本地登记、已有位置冲突、purged / missing 拒绝 | T04 | done：真实 PG 原子绑定/换目标/节点/purged/missing 5 项 |
| U05 | operation / resource ID 摘要去重，重复接收只回查、已接收未决不执行；持久记录失败无副作用 | T03、T07 | done：Node/client 去重与拒绝，真实 Docker 副作用 0/1 |
| U06 | 文件虚拟路径、符号链接 / traversal 防护、只读 uploads / outputs / skills / 系统路径、配额、原子写入、hash 校验 | T05–T06 | done：文件链 101 项、Node 路径/配额/原子写入/hash |
| U07 | DeepAgents 完整文件协议与工具结果类型；skills 快照摘要 / 历史引用；FileRef / ImageRef / HTML CSP / Office 续读兼容 | T05–T06 | done：完整文件协议、两图主子/skills 2 项、Office 2 项 |
| U08 | execute timeout / 截断 / 取消 / unknown；所有权标签、deadline、准入和清理 unconfirmed；不继承远端 DOCKER_HOST | T07、T10 | done：真实 TLS execute/timeout/截断/Stop、Node 对账 |
| U09 | terminal request_id 去重、owner、offset / sequence、resize、无输入超时与寿命上限；Node 实例变化与遗留回收 | T08、T10 | done：真实 TLS PTY、idle/lifetime、重启旧实例拒绝 |
| U10 | 后台 lease / fence、固定 task ID、绑定摘要旧新兼容、签名回执、日志先确认后删除、missing / unknown 不重跑 | T09–T10 | done：真实 PG 35 项、TLS+PG 生命周期 5 项、后台链 1 项 |
| U11 | retained / queued / interrupted / unknown / delivery 未决保护，dry-run 不删除，apply 二次核对与互斥、deleting / purged 标记 | T11 | done：PG/Node retained、未决保护、精确 cleanup 与 tombstone |
| U12 | 同 key 互斥 / 不同 key 并行、锁表回收；取消等待 / 已获得锁 / 重复取消 / executor 关闭；ContextVar 传播；关闭准入后有界 drain，sibling 或文件操作仍使用时不清工作区 | T00、T03、T05、T07、T10 | done：60 项含互斥/并行/取消/drain/锁表与第二管理者 |
| U13 | readiness 依赖检查与启动对账；只读 discover / inspect / list 不创建 / 删除；按持久 ID、标签、镜像、mount、UID / 网络 / 权限核验，策略不兼容拒绝接管 | T03、T10 | done：readiness/discover、存量八类策略拒绝与启动对账 |
| U14 | 文件缺失、真空结果、搜索失败 / 部分遍历失败、超限截断、二进制上传下载分别处理；超限在 Node 生成时有界；edit 锁内校验 / 原子发布；文件 404 不触发沙箱重建 | T05–T06 | done：missing/空/部分失败/截断、二进制与 edit 竞态 |
| U15 | 路径映射的根结尾 / 相似前缀 / 标点 / 冒号路径列表 / 分隔符；env 仅保留本项目白名单，Node / TLS / DB / 模型秘密与凭据指针不进沙箱或公开 / 模型输出 | T00、T05–T08 | done：路径匹配契约、最小 env/凭据与输出脱敏 |
| U16 | 复制模块 / 测试来源、源提交 / SHA256、完整 MIT 与版权、必要 import 差异；无上游包依赖、未使用复制模块；wheel / 镜像随附许可与来源 | T00、T15 | done：源 hash、调用点与 MIT/PROVENANCE 随 wheel/双镜像 |

复用 `tests/test_workspace_http.py`、`test_thread_workspace_isolation.py`、`test_terminal.py`、`test_terminal_http.py`、`tests/background/`、`tests/workspace/test_office_docker.py` 等已有套件，新增测试验证边界和用户行为，不复制实现逐行断言。

## 集成测试计划

| 编号 | 场景与操作 | 验收结果 | 状态 |
| --- | --- | --- | --- |
| I01 | local 上传 / 文件读写 / Agent execute / 终端 / 同 Thread 二次执行；普通 shell 测试不启动 Docker | 路径、权限与原有行为一致，无 Node 网络调用 | done：86 项兼容基线；local/result.json 与恢复 local 后 local-closeout/result.json 的真实模型浏览器上传/执行/下载/重开通过 |
| I02 | 本地 Docker 用旧 env 运行命令 / terminal / 背景查询；显式开启后台后完成与取消 | target 缺省 local；当前挂载与资源回收正确，旧任务可查 | done：真实本地 Docker 执行/PTY/后台基线；docker-local/result.json 浏览器完整链通过 |
| I03 | 从真正 Runtime API / Worker 原生或容器部署请求公网 HTTPS readiness，完整 mTLS / caller 认证、SAN / CA 和实际出口 IP 校验；证书更新后重连 | node 身份 / 版本匹配；没有本机 Docker CLI 仍可 remote；仅受限 Node HTTPS 可达，无 Docker TCP / 明文 / per-container 端口 | done：public-readiness.json 与 public-security-restart.json 公网 mTLS/caller/源 IP/SAN/协议及重连通过；最新 wheel 的 Node 服务重启后原 ID/文件再验通过 |
| I04 | API / Worker 同时首次准备同 Thread；换配置 / node ID；另用两个 Worktree 访问同 Node | 绑定唯一；冲突拒绝；不同执行域不混目录 / 不误删 | done：PG 并发绑定/目标冲突；public-two-worktrees.json 两真实 Worktree 独立证书/caller、同 scope 文件隔离与跨 host 403，通过后原策略逐字节恢复 |
| I05 | remote 上传、文件树、read / write / edit / glob / grep、preview / raw / zip、图片引用与产物、研究证据、技能 / 部署包读取 | 所有入口读写同一远端文件；本地没有可写副本；hash / MIME / CSP、证据引用与治理审批保真 | done：public-business.json 文件/二进制/图片/HTML/ZIP/fork，public-platform.json 两图完整工具链；public-media-adapter-complete.json 研究证据/部署包/图表远端落盘与认证下载 hash |
| I06 | remote DOCX / PPTX 解析与续读；PDF / ZIP 回归，畸形 / 超限文件与 reader 取消 | 固定 Docker reader；定位和有界输出保持；非法结构不触发宿主 parser | done：公网 DOCX/PPTX 续读、两图真实模型 Office 和浏览器历史通过；畸形/超限/取消由锁定契约及真实本地 reader 复验覆盖 |
| I07 | remote 短命令完成、非零、timeout、输出截断、Stop；执行中断开 Runtime 网络 | 只有一次副作用；容器按 Node deadline 回收，文件仍在；unknown 如实报告 | done：公网一次副作用/非零/timeout/截断/原 ID 响应丢失恢复；public-joint.json 真实模型前台 Stop cleanup confirmed |
| I08 | remote terminal create / input / output / replay / resize / close；仅轮询不输入直至 idle；寿命上限 | 字节回放 / 输入幂等；15 分钟无输入与 1 小时上限生效；容器删、文件留 | done：public-platform.json 两图受认证 PTY 代理链与 public-business.json 输入/回放/resize/close；idle/lifetime 真实 Docker 及旧实例拒绝通过 |
| I09 | remote 后台完成 / 失败 / 超时 / 取消；重复 reconciler、错误签名、日志未确认 | lease / fence 生效；先持久回执 / 日志后删除；完成续接不重复，unknown 不重跑 | done：公网 PG 四终态/签名回执/日志 ack，真实 Worker 完成续接与 Stop；public-browser-recovery/result.json 原 accepted Run/日志及 suppressed 通知恢复通过 |
| I10 | 删除临时容器后重开同 Thread；重启 Runtime API / Worker、Node，再获授权重启专属节点 | 文件字节 / hash、位置与快照保留；新容器 ID；旧 PTY 可关闭重建，后台只对账 | done（进程/文件边界）+ deferred（用户决定，整机部分 F01）：同 Thread 重开、新容器/旧 PTY、原 ID/文件/checkpoint/hash/后台回执已验；正式整机重启仍需维护窗口与明确授权。public-recovery.json 的先前整机重启未获授权，不计正式 I10 |
| I11 | fork remote Thread，分别写同名文件；上传图片后生成 / 编辑 / 分析和图表产物读取 | fork 新绑定 / 目录；原 Thread 不变；供应商凭据留 Runtime；引用 / 下载正常 | done（沙箱适配边界）：公网 fork/真实图像分析/真实 MCP 图表、受控 generate/edit 远端 hash；wawapii 真实生图 succeeded 且远端/认证下载一致。真实编辑两次 unknown、用户决定 deferred，原回执保留，不代表编辑成功；旧供应商历史 unknown 不重发 |
| I12 | Node 响应丢失、进程崩溃、Docker 控制失联、container missing 与取消未确认 | 按原 ID 回查；未知不重跑、不本地 fallback；deadline 回收已知资源，后台证据留存 | done：public-business.json 公网真实 Node 调用后模拟响应丢失、原 ID 查回且副作用一次；真实 TLS 崩溃/Docker missing/unknown 与公网 Node 重启只读恢复；未关闭共享 daemon |
| I13 | 保留 Thread 闲置超过 TTL；删除 Thread 的专属 fixture 与排队 / unknown / 临界重新使用；dry-run / apply | 保留 Thread 不删；未决资源不删；只有显式授权候选可删，重开 purged 不造空目录 | done：真实 PG/Node retained/queued/unknown/grace/apply/purged 契约；公网 fork 删除后 mark/宽限 apply 拒绝，retained/历史 interrupted 均保护，未绕过事实删除 |
| I14 | 主 / 子 Agent 与上传 / reader 共同使用 workspace；prepare / edit / fork / janitor / apply 并发；连续取消与晚创建；Node shutdown 中仍有请求 | 同资源一次副作用；目录不误删、文件不半写、input 不重放；有界取消 / 关闭后锁 / 连接 / PTY / executor 无泄漏，未确认结果按原 ID 可查 | done：public-joint.json 两个真实模型 task 与运行中上传、前台 Stop；两图主子共享文件/skills、Node 同 key 锁/不同 key 并行及有界关闭真实边界通过 |
| I15 | 重启 Node 后只读发现受管容器、持久 operation 与未确认日志；注入错误镜像 / 挂载 / 网络标签的隔离 fixture；依赖预检失败 | 查询不创建 / 删除；策略不兼容拒绝接管，未知资源不清理；未完成对账或依赖不健康不准入，diagnostics 有界 / 脱敏 | done：公网 Node 重启/readiness/原操作与回执；八类不兼容存量策略、第二管理者和依赖拒绝由真实 TLS/锁定契约验证，未在现役共享 Docker 注入故障 |
| I16 | 远端 missing / 空目录 / 真无匹配 / 文件权限失败 / 部分遍历 / 达 limit 和 limit+1 / 二进制 / edit 竞态 | 正确区分错误与结果 / 截断；原公开结构保真，Node 侧有界；缺文件不变成缺沙箱重建，写入和 hash 一致 | done：真实 TLS 的 missing/空/权限/partial/limit/二进制/edit 竞态，公网文件/截断/hash/认证预览与 10 MiB 完整字节通过 |

长超时单测可用受控时钟；真实终端超时、后台 deadline 与启动恢复至少各有一条真实 Docker 证据，不能全部靠 monkeypatch。所有删除 / 节点重启场景使用独占测试数据和明确授权。

## 端到端测试计划

- [x] **E01：本地回归。** platform-web → platform-api → Runtime API / Worker → local；上传文件、真实模型读取 / 改写、生成产物、预览下载、关闭再开同 Thread，保留原审批 / Stop / 错误展示。
  - **done：** local/result.json 初次真实模型浏览器通过（55.6s）；local-closeout/result.json 恢复基线后再次通过（约 1.9m），原审批与单次 execute/hash/预览/下载/重开均正常。
- [x] **E02：本地 Docker 与 remote 双链路。** 同一个功能场景分别新建隔离 Thread，在 target=local / remote 下执行可计数命令；验证执行位置、只有一次副作用、结束无活跃临时容器、文件可读；remote 真实走公网 HTTPS + mTLS。
  - **done：** docker-local/result.json 本地 Docker（约 1.2m）及 remote/result.json 公网 remote（45.6s）真实模型同场景通过；Node 临时资源已排空，文件保留。
- [x] **E03：附件与完整工具链。** 真实远端 Thread 上传 DOCX / PPTX / 图片，Agent parse_document 有界续读，输出 Markdown / HTML / 普通命名产物，浏览器预览与认证下载，撤权后拒绝访问；skills / memory 快照与主 / 子 Agent 文件边界覆盖。
  - **done：** public-platform.json 两图真实模型 Office/图片/skills/主子/HTML/Markdown；public-browser-recovery/result.json 两图 Office 历史/预览/CSP/认证下载 hash；public-joint.json 真实分享撤权后六入口 403。
  - **真实图片补验边界：** wawapii 生图通过原生审批/Worker/远端落盘及两条认证下载 hash；编辑成功未确认，用户决定 deferred。原生生图成功与受控编辑适配分开记录，不能把 E03 勾选解释成真实编辑验收完成。
- [x] **E04：交互终端。** 从现有入口创建 / 输入 / resize / 关闭 remote PTY；写入文件后 close，Agent 读取该文件。沿用已有产品入口；如无可用 UI，以受认证 HTTP 验证，不以未新增终端界面作为本期扩大范围理由。
  - **done：** 两图现有受认证 HTTP 入口创建/输入/resize/close、文件保留；混合两槽和第三请求 429，沿用现有平台入口。
- [x] **E05：后台任务与取消。** remote 显式开启后台开关；提交耗时任务、页面离开、完成通知 / 回执 / 日志可查，Stop 和节点断开时未决状态正确；local 模式隐藏新建但历史查询保留。
  - **done：** public-platform.json 真实 Worker 完成通知/续接与 Stop；恢复浏览器核对原 accepted Run success 与持久日志，Thread Stop 后通知 suppressed 符合原语义；local 仍禁新建/保留历史。
- [x] **E06：恢复与保留。** 重启 Runtime 与 Node 后打开原 Thread；聊天由原持久库恢复，附件 / 工作文件 / 产物 hash 一致，新建容器 ID 不同。另测新 Thread 隔离、缺目录明确失败、保留 Thread 超 TTL 不丢数据。
  - **done（进程恢复与同会话文件边界）：** public-recovery.json 的 Node/API 恢复、原 checkpoint/消息/hash、新容器/旧 PTY；浏览器两图重开/后台回执通过。正式授权整机重启单独归 I10，按用户最新验收决定 deferred（F01）。
- [x] **E07：并发、取消与既有平台契约。** 真实模型主 / 子 Agent 与上传 / reader 并发，执行中 Stop / 断网 / Node 重启，对照原 ID / 回执、只读恢复与文件 hash；Platform API / Web 不增加公开接口或页面，现有审批、撤权和安全错误展示通过。
  - **done：** public-joint.json 真实模型双 task + 上传、前台一次副作用后 Stop、fork/撤权；API 42 passed/1 skipped、Web 51 passed、终端容量 12 passed。公网客户端丢响应与 Node 进程恢复单列，不重发。

记录浏览器、公开 API / Runtime 与节点资源证据的对应关系；公网 Node 单点命令 smoke 不能代替 platform-web → platform-api → Runtime → Node 的完整链路。

## 安全测试计划

- [x] **S01：公网信任边界。** 无客户端证书 / 非受信 CA / 过期证书 / 错 SAN 或错误服务端链失败；有效证书但无 token / 错 token / 错 execution host / node_id / 协议拒绝；非允许出口 IP 被拒。Node 端口只提供 mTLS HTTPS，公网 2375 / 2376、裸 HTTP 与容器执行端口不可用；SSH 固定指纹，仅运维。
  - **done：** public-security-restart.json 公网无/错/过期证书、SAN、token/IP/协议拒绝和 2375/2376 无监听；公网成功链与 Node 重连已验，SSH 固定主机验证仅用于运维。
- [x] **S02：作用域与凭据隔离。** 跨 tenant / project / Thread / graph / execution host 的文件、PTY、execute、cancel、background / remove 被拒；节点服务 token 不能在 Agent Context、公开 DTO / 错误 / trace 中出现。
  - **done（锁定契约及真实 TLS）：** Node/client 60 项、跨 scope 取消/后台 ID、PTY owner、旧新后台摘要兼容和公开错误投影通过；公网链路另见 E/S01。
- [x] **S03：路径与容器隔离。** traversal、符号链接、伪造宿主绝对路径、任意镜像 / mount / privileged / UID 被拒；沙箱没有 Docker socket / Node 密钥 / 其他工作区，保持 network=none 与当前资源 / 只读策略。
  - **done：** Node 路径/符号链接/跨 scope 与 extra Docker 参数前置拒绝、真实 TLS 容器策略通过；v2 终端镜像和非法镜像零副作用分别复验通过。
- [x] **S04：文件契约与预览。** 过大文件 / 伪 MIME / hash 不符 / 畸形 Office / ZIP 拒绝；HTML iframe / CSP 不退化；所有输出敏感错误正文脱敏。
  - **done：** 文件/图片/Office 与 API/Web 锁定契约、真实 reader 复验通过；两图浏览器 HTML CSP/iframe 无 same-origin/认证下载及 hash 通过，错误正文安全投影保持。
- [x] **S05：资源回收隔离。** scanner 不触碰未标记容器 / 其他域目录；磁盘不足前置拒绝；半写入与二次清理竞态安全；unknown / 未确认后台日志不擅自删除。
  - **done：** Node 对账/非归属资源不删/低磁盘与账本失败、真实 PG cleanup/tombstone/未决保护、TLS receipt ack 后删除均通过。
- [x] **S06：配置管理。** 新真实 env 和密钥文件被 Git 忽略且权限正确；配置诊断不打印内容；Node / Runtime API / Worker 注入同一受管配置而不是使用镜像内旧值。
  - **done：** 配置组 26 项、git check-ignore、所属 env/客户端四个文件 600 自检、API/Worker 同 env/v2 和 sshmy2 安装 hash/systemd 验证通过；只记录键名/权限，不保存秘密。
- [x] **S07：路径与秘密隔离。** 在本项目既有 local / Docker env 基线内测试，Node / caller / TLS / 模型 / DB 凭据、SSH agent / askpass 等凭据指针不可见；异常与成功工具输出不泄漏宿主路径，映射不误改相似前缀；保留 Runtime 管理模型 / 图片秘密的边界。
  - **done（当前 env 基线）：** 复制路径模块契约、最小 env 与真实 TLS timeout/有界输出/no-secrets 通过；不扩大 local 可信宿主 shell 的隔离承诺。
- [x] **S08：存量资源与进程边界。** 伪造 / 不兼容的标签、镜像、mount、网络、权限、owner 不被采纳或误删；Node 多进程管理配置拒绝或明确阻止第二管理者，不出现两个 janitor / 容量表 / PTY 实例。所有测试只用独占受管 fixture。
  - **done：** 60 项合集含原五类存量策略拒绝/未知资源保护/第二管理者锁；额外 seccomp/tmpfs/fsize 三类拒绝及真实 execute/PTY 共 10 passed；Node 崩溃恢复与单进程 sshmy2 服务通过。

## 性能与容量测试计划

local 和 remote 使用相同公开 API/文件字节及各自新 Thread，顺序为 remote 测量后恢复 local 对照。性能场景只用预置镜像，不把镜像首次下载时间算进普通执行；失败率、成功耗时与 HTTP 超时分别记录。

| 编号 | 负载与测量 | 验收门槛 | 状态 |
| --- | --- | --- | --- |
| P01 | 1 / 2 个并发容器，混合短 execute、terminal、reader、后台；第三个请求；记录 CPU / RAM / OOM / 槽位 | 2 槽原子执行，第三个在副作用前明确拒绝；无 OOM / daemon 异常；终态释放槽位 | done：公网 2 PTY + 16 并发 read 成功、第三 PTY 429；execute/reader/后台和真实 Docker 2 槽组合通过，active/未决最终为 0；资源观测为单次样本 |
| P02 | 有界输出 / 文件树 / grep / 10 MiB 上传下载，Runtime 与 Node RSS / 磁盘 / 临时文件；低磁盘 fixture | 现有输出 / 文件限额生效，没有逐文件往返或无界缓存；临时文件回收；低磁盘不删用户工作区 | done：公网有界输出/文件与准确 10 MiB hash；上传 0.879s/下载 23.225s，Runtime/Node 资源快照及真实 TLS RSS/低磁盘边界；不承诺生产吞吐 |
| P03 | 从公开 API 发起本地 / remote 成功操作，分别统计公网 RTT、工具 p50 / p95、文件吞吐与回收延迟 | 全链路可用且在既有执行 / HTTP deadline 内；取消 / 清理符合有界策略；完整报告开销，不宣称未批准的生产 SLO | done：local/remote 公开 API 各 36 次成功读/预览/目录，p50/p95 与 10 MiB 吞吐独立记录；公网 2 终端回收 654.12ms，所有结果在 HTTP deadline 内 |
| P04 | 节点 2 槽下混合 PTY / execute / 文件请求，创建 / 清理故障期间持续 readiness / 只读查询；多 Thread 反复创建关闭，记录连接 / 线程 / 锁表数量 | ASGI 事件循环不被同步 Docker / 锁等待阻塞；不同 key 可并行、同 key 互斥；短事务不持锁等网络，结束后进程资源数量有界 | done：public-joint.json 两槽混合并发读与第三 PTY 拒绝、public-capacity-observation.json 12 readiness/进程资源、TLS 不同 key/连接/锁/关闭测试；不是长时间生产压测 |

初始 2 容器是部署策略，不是宣称已验证吞吐。公网延迟与 4 核 / 约 3.6 GiB 的真实容量可能限制 reader / 并行 Agent；若不达门槛，先定位并修复，再由人工批准调整容量 / 限额。

## 回滚与数据保护验证计划

- [x] **R01：位置与迁移。** 冷安装 / 既有库升级、旧本地目录登记；保存当前 migration head 的旧应用回退启动；绑定 / tombstone 保留。不同目标不得自动读取或创建同名空工作区。
  - **done：** 真实 PG 位置/清理/原 scope 恢复 5 项，旧应用携迁移链保留 0008 head 回退 1 项通过；不执行 schema downgrade。
- [x] **R02：受控 drain。** 关闭新建、保留原 host 与节点通道，完成或取消现存任务并持久确认日志 / 回执；unknown / unconfirmed 时不能宣称 drain 完成。应用回退后保留远端目录与 Node 记录，不降级到宿主命令重跑。
  - **done（独占真实环境）：** 禁新建后的完成/取消/抑制续接/历史回执保留、TLS 日志 ack 与 API/Worker Thread Stop 通过；证据为 rollback-drain.json 与后台链路，不证明公网切流。
- [x] **R03：原有链路恢复。** 在具备原本地数据的独立环境重新验证 local 与本地 Docker 上传 / execute / 终端 / 历史查询；远端旧 Thread 明确暂停，不用“切回 env”冒充数据迁移。
  - **done：** local/本地 Docker 原核心浏览器与 86 项基线通过；所属 env 字节恢复原基线、API/Worker 同步 local/后台关闭后再次本地真实模型验收通过。远端旧 Thread 保留原绑定，不在 local 自动迁移或补空目录。
- [x] **R04：数据清理边界。** 对授权 fixture 做 dry-run、超保留期 apply 与 purged 读取，确认未影响其他域 / retained Thread；确认无备份的已删除目录无法自动恢复，用户可见说明准确。
  - **done：** 真实 PG/Node retained/宽限/未决保护/apply/tombstone/purged 拒绝重建通过；手册明确只恢复持久文件/已有备份，不恢复被删除且无备份数据。

本期不验收跨节点容灾或对象存储恢复；单机数据盘损坏后的恢复能力只有建立并实际验证备份后才能作额外承诺。

## 规划检查记录

### 2026-10-12：事实与范围核对

- 已读取 CONTEXT、Runtime / 跨服务规范、Runtime 经验库与 plan-project Skill。
- 已核对代码中的 backend 默认、Docker 隔离参数、前台 `--rm`、终端 900 / 3600 秒、后台 lease / fence / 日志回执和清理状态。
- 已核对 Office reader 固定 Docker 的现有约束、文件 / 图片 / fork 本机路径依赖，以及 R6 清理器仅扫描三层目录的限制。
- 服务器规格与公网 / 私网事实沿用本会话此前只读探测；本次文档阶段未重新执行远端操作，未保存包含秘密的 SSH 配置。
- `git diff --check` 通过；项目四份 Markdown 的 10 个文件 / 标题链接、围栏代码块、尾随空格与表格检查通过；变更文档检查共 6 个文件、0 个错误。
- `scripts/check_docs.py` 使用 `python3` 执行时仍报告仓库其他 12 个既有文档的 42 条 macOS 绝对路径问题；本次新增 / 修改的 6 个文件均不在错误列表中，因此没有扩大范围修改历史文档。

**规划结论：** 文档形成可评审方案。没有执行功能测试、性能测试、服务器安装或数据删除，不据此认定远端沙箱可用。

### 2026-10-12：公网方案修订与 deer-flow 复用核实

- 已核对参考 HEAD `cc664451f03140b376611f329ae400c313530bdb` 与限定路径 Git 状态：所读沙箱 / AIO / OpenSandbox / Provisioner 源码无未提交改动；`config.example.yaml` 有已暂存修改，不作为独立上游实现事实。
- 已读取根 MIT 许可证并采集 `LICENSE`、两个直接复用候选和关联测试的 SHA256，记录在 [复用评估](deerflow-reuse.md)；Python 版本要求与独立标准库依赖已核实。
- 使用 Python 3.13 通过 `importlib` 从参考目录加载 **未修改** 的两个候选，关闭字节码写入；抽样 assert 自检通过：路径根结尾 / 相似前缀 / 冒号列表 / 分隔符映射，不同 key 并行、取消等待后的锁表回收、再次取锁与 close 幂等。没有执行上游全量 pytest，也没有向本项目复制代码；这些只证明源模块可导入和抽样契约，不证明 Runtime 调用方已接入。
- Docker 官方远程访问与 bind mount 页面已通过启用证书校验的 `curl` 获取并核对：支持 SSH / TLS；客户端密钥具备宿主高权限风险；bind mount 源属于 daemon 主机。首次 Python 3.11 `urllib` 获取因本机 CA 配置失败，改用 `curl` 成功，未禁用 TLS 校验。
- 已核实远端 AIO 的两条路径：Provisioner 管 Pod / Service 生命周期，Gateway 直接访问 Pod 的 Sandbox API。OpenSandbox adapter 文档明确尚无跨进程 discovery / ownership；AIO warm-pool mixin 明确允许超过 replicas 软上限。方案不将这些限制当作本项目硬准入 / 恢复能力。
- 已形成 C01–C18 补齐矩阵、T00 模块 / 测试 / 许可接入任务，以及 U12–U16、I14–I16、E07、S07–S08、P04；改生产主通道为 HTTPS + mTLS，保留 caller 域认证与 SSH 运维，Platform API / Web 仅既有契约回归。
- 本次最终文档检查通过：7 份新增 / 修改文件、17 个项目文件与标题链接、围栏 / 表格 / 尾随空格、C01–C18 完整性与验收编号均为 0 错误；`git diff --check` 通过。首次检查发现 Markdown 表格内未转义管道符，已修正后复验。
- 仓库 `scripts/check_docs.py` 仍报告其他 12 个既有文件的 42 条本机绝对路径问题，本次 7 份文件没有该项错误；未扩范围修改历史文件。

**修订结论：** 能力范围和复用实现已具体到源码 / 调用方 / 任务 / 验收，G02–G05 保留用户确认；以上是当时规划检查；随后 G01 与全部实施于 2026-10-12 获用户批准，当前进入实施/验证，进度以 tasks.md 为准。

## Phase 验证记录

T00–T15 各一条，共 16 条；T13–T15 记录本期必要证据与用户批准后续边界，完整联合 Phase 证据在下节。用户最新本期验收收口在 Final 区独立记录，不把 Phase 重命名为原全矩阵独立 Final。

### T00：原样来源与实际接线（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；60 项含 serializer/path 契约；两模块源 hash 与 MIT/PROVENANCE 逐字节匹配，最新 wheel/双镜像含许可；evidence/vendor-hashes.json、delivery-artifacts.json。

### T01：三模式兼容基线（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；86 passed；local/本地 Docker 真实模型浏览器及原文件/终端/后台基线通过；Office 固定 Docker reader 例外保持。

### T02：配置与所属 env（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；配置/客户端 26 passed、证书 2 passed；env 优先级/同 host/缺键/no CLI 校验和真 seed 自检；local-closeout/development-config.json 恢复字节一致。

### T03：Node 协议与认证（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；Node/client 60 passed；真实 TLS/PG/崩溃/轮换 5 passed；公网 mTLS/token/IP/协议拒绝、readiness 与进程关闭通过。

### T04：持久位置绑定（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；真实 PG 位置/旧目录/冲突/tombstone/原 ID 恢复 5 passed，旧应用保留 0008 链启动；public-two-worktrees.json 两真实 Worktree 文件隔离。

### T05：完整远端文件协议（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；文件/图片/HTTP/Office 101 passed、2 skipped（跳过不计通过）；missing/空/partial/截断/edit 竞态；公网业务二进制/树/搜索/HTML/ZIP/fork。

### T06：Office/附件/skills 与产物（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；真实 TLS Office 2 passed，两图主子/skills 2 passed；public-platform.json 两真实模型根及 public-browser-recovery/result.json 附件历史/预览/认证下载；媒体/研究/部署包实际远端 IO 补验。

### T07：一次执行与有界 Stop（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；真实 Docker 单次/非零/timeout/截断/unknown/取消；公网调用后响应丢失原 ID 查回、副作用一次，public-joint.json 前台真实模型 Thread Stop cleanup confirmed。

### T08：远端 PTY（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；真实 PTY 输入去重/replay/resize/close/idle/lifetime；两图公开 terminal 代理链，2 槽下第三请求返回现有安全码 429；terminal-capacity.xml 12 passed。

### T09：后台任务持久回执（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；真实 PG 35 passed、TLS+PG 四终态；Worker 原固定 ID/签名回执/日志 ack 后清理与完成续接/Stop；公网真实 Worker/浏览器原 accepted Run 与日志恢复通过。

### T10：硬准入与 janitor/对账（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；合集 60 passed，存量八类反例/execute/PTY 10 passed；单管理者、容量/低磁盘/账本失败无副作用、有界关闭；公网 2 PTY + 16 read、第三 429 和结束 active 0。

### T11：容器与数据独立清理（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；PG/Node retained/unknown/宽限/apply/purged/缺目录拒绝，服务器备份还原 hash；公网原 Thread/文件与回执、fork grace 拒绝、历史 interrupted 保护。正式获授权整机 I10 是 T13/T14 后续门禁，未计完成。

### T12：sshmy2 专项部署与公网（2026-10-13）

- 验证项：tasks.md 对应 Task 验收项。
- 结果：✅ 通过；19111 放通后 Runtime → Node 公网业务/安全/模型/浏览器通过；最新 wheel d2060adc…87738 安装 hash/许可匹配，Node 服务更新后原 ID/文件恢复通过；无 Docker TCP、无新整机重启。

### T13：三模式与公网联合链（2026-10-13）

- 验证项：本期三模式、两图公网/真实模型/浏览器/Worker/Stop/恢复/权限与媒体适配；原 I10 整机部分及真实编辑成功由 G06 转后续。
- 结果：✅ 本期通过，既有详细结果见下方联合记录；Runtime 广泛回归 1713 passed/45 skipped/29 deselected，离线 daemon 四项相关复验6 passed，API42 passed/1 skipped、Web51 passed、容量12 passed；失败尝试保持。独占媒体回归65 passed/3 skipped，wawapii 生成成功、编辑两次 unknown 不当作成功。

### T14：安全、性能、故障与回退（2026-10-13）

- 验证项：既有 S/P/R 矩阵的当前可执行范围；正式整机重启按用户决定 F01 deferred。
- 结果：✅ 本期通过；公网 mTLS/caller/IP/权限拒绝、2 槽准入、真实进程恢复/证书轮换/保留迁移链应用回退与精确清理已有证据；10 MiB hash 一致，remote 下载23.225秒、样本不作生产 SLO。没有再次整机重启。

### T15：许可、文档、用户验收与精确清理（2026-10-13）

- 验证项：本期验收状态对齐、后续问题记录、原样/MIT 来源、秘密不入 Git、所属服务停止与专属资源回收。
- 结果：✅ 用户验收收口；两个模块/完整 MIT 三份 SHA256 一致，184 个文本对27个私有值扫描无泄漏；五服务 stopped，三库/两角色归属及零连接核验后删除，登记与 `.local-stack` 已释放。3条媒体回执/2份位置绑定/原图片和恢复凭据保全到主工作区忽略目录，600/700权限通过。Git 提交/合并与最终清理核验在 Final 区追加；未执行原整机重启后的独立 Final。

## 联合验收阶段记录（T13–T15）

### 2026-10-13：公网平台、恢复浏览器与容量错误修复

- B01/B02 已解除；[公网业务](evidence/public-business.json) 的所有检查通过（含准确 10 MiB），[两图平台链](evidence/public-platform.json) 6 组真实模型/Worker/PTY 通过。
- [联合链](evidence/public-joint.json) 4 组通过：fork 隔离/删除后宽限拒绝，真实 share 撤权后六入口 403；2 PTY + 16 read、第三 PTY 429；两个真实模型 task 与运行中上传、前台 execute 副作用一次后 Thread Stop confirmed。原 interrupted 历史受 cleanup 保护，未为清理改写事实。
- 第三 PTY 原返回 500/Platform 502：Node 正确返回容量 429，客户端误映射执行异常。只在 terminal.create 映射为原 terminal_session_limit 429，保留 execute unknown/not-started 规则；[最小回归](evidence/terminal-capacity.xml) 12 passed，真实公网第三请求 429。
- [恢复浏览器](evidence/public-browser-recovery/result.json) 1 passed（14.0s，总15.4s）：两图 Office 历史、HTML/CSP/无 same-origin/认证下载 hash、原 accepted 后台 Run success 与日志；Thread Stop 后卡片 suppressed 是正确状态。browserErrors 为空。仅改验收脚本，没有平台产品代码改动。
- [两个 Worktree](evidence/public-two-worktrees.json) 用各自独立 Python/目录和不同 caller 证书访问同一真实公网 Node；同 scope 文件隔离、冒充另一 host 403、精确 mark/宽限通过；原 caller 策略逐字节恢复、临时 peer 私钥删除，仅重启 Node 服务。

### 2026-10-13：广泛回归与边界复验

- 初次广泛尝试 [runtime-final.xml](evidence/runtime-final.xml)：13 failed/1605 passed/169 skipped；修复过时模型/PII/Plan/子图/inbox 夹具后 [runtime-closeout.xml](evidence/runtime-closeout.xml)：8 failed/1709 passed/45 skipped/29 deselected。均是失败 Phase 尝试，文件名中的 final 不代表专项 Final。
- 本轮修复迁移 head 断言和真实 legacy schema、技能子进程 execution/metadata/预算 run_id；保留旧应用原 head/额度与真实跨进程 A/B/disable/delete 断言。
- 曾尝试用量 schema 隔离，但仓储的连接 options 覆盖 search_path，产生 9 failed/32 passed/2 skipped；已撤回不适用的 schema 夹具改动。以显式所属专用测试数据库隔离 Worker，独占库 [13 passed/2 skipped](evidence/regression-usage-isolated.xml)。未改生产用量代码。
- [广泛回归](evidence/runtime-closeout-final.xml) 完成：1713 passed/45 skipped/29 deselected，1 failed/3 setup errors，1502.36s。剩余全在本地 Office Docker，查明 daemon 不在线；启动原 Docker Desktop 后 [6 passed](evidence/office-docker-closeout.xml)，29.26s，包含并解除全部 4 项失败，无产品代码修改。不重复一整轮已通过范围，不将两个结果合并伪造为一次全绿。
- Platform API [42 passed/1 skipped](evidence/platform-closeout.xml)，40.63s；Web 8 文件/51 passed，6.84s；本次自有 Python Ruff、浏览器 ESLint、vue-tsc 与 diff 检查通过。跳过、deselected 与忽略的 integration/e2e 不算通过；对应关键链另有真实公网/PG/TLS/E2E 证据。
- 失败 XML 中 DSN 密码已脱敏；后续 runner 的控制台/XML 均做凭据替换。真实配置、专用测试库 DSN、token 和私钥不进入 Git。
- [媒体适配](evidence/public-media-adapter-complete.json) 6 组通过：受控图片供应商 generate/edit → 真实公网 Node/公开下载 hash，真实 AntV MCP 图表及 hash，既有 Showcase 真实视觉分析证据、研究证据来源/hash、远端 ZIP 部署包读取/校验。没有实际发布网站。
- [图片供应商](evidence/public-media.json) 旧供应商首个真实生成请求 `image_submission_unknown`，保留原标识、不再提交；[补测尝试](evidence/public-media-adapter.json) 的额外 vision 配错供应商模型名而 400，不记成功。该历史失败与下方 wawapii 生图成功、编辑 deferred 分开统计；不可将受控供应商证据当作真实编辑成功。临时 Thread 删除后按宽限 mark，不绕过清理保护。

### 2026-10-13：真实图片供应商补验与只读排查

| 边界 | 状态 | 实际证据 |
| --- | --- | --- |
| wawapii 真实生图 | done | [完整链](evidence/public-media-real-provider.json)：Platform API → Worker/原生审批 → sshmy2 Node，`gpt-image-2.5-flare`；生成任务 succeeded / attempts=1，1024×1024 PNG、563829 字节，原文件与两条认证下载 SHA256 一致；[只读图像复查](evidence/image-generation-readonly-recheck.json)蓝圆白底通过，未重复购买 |
| wawapii 真实编辑成功 | deferred（用户决定） | 两次任务 unknown / attempts=1，原回执保留；第一次返回图片 URL 后下载失败，第二次 Run success 但工具结果仍 unknown。用户没有查询方式、决定稍后再验，不再付费调用；未取得成功图片，不能确认单次扣费或供应商编辑故障 |
| 图片 Key 与结果查询 | partial | [正确 origin GET](evidence/image-provider-correct-origin-query.json)：`/v1/usage` 200、Key 有效，但只含用量汇总；批量历史为空，同步编辑未能恢复；管理入口 401，未绕过登录。较早 [404 探测](evidence/image-provider-readonly-query.json)有 base_url 路径拼接错误，已标记无效，不能作入口不存在的证据 |
| SDK 请求与合成结果链 | done（离线边界） | [mock transport 自检](evidence/image-sdk-request-selfcheck.json)：生成 JSON、单图/参考图编辑 multipart、MIME/图片字节及合成图片落盘读取通过，真实供应商调用 0；不能证明 wawapii 编辑支持或成功 |
| 回执来源/下载 unknown 修复 | done（代码与最短链） | 新编辑来源为受信业务 Run，第二次正常报告 unknown；旧生成来源 `None` 原样保留。独占库 [65 passed / 3 skipped](evidence/media-provider-closeout-regression.xml)，29.58s；三个 skip 分别为 Office Docker 及两项真实模型/图片开关，不计通过；五文件 Ruff check/format 通过 |
| 响应留存夹具 | partial（真实未生效） | local-stack exports 覆盖临时 graph，第二次真实请求没有进入夹具，也未留存原响应；AI 漏查有效配置已披露。补上购买前有效 graph guard；[配置 guard](evidence/media-retention-config-selfcheck.json)/[合成留存](evidence/media-response-retention-selfcheck.json)自检通过，真实调用 0，不能替代实机留存验收 |

生成 Task 为 `a1ef89b7-0d2f-498d-83a5-6597ad6fa2e4`，SHA256 为 `d98a5f95ecc771273de0bd9dc8abcb8906aec9695bfcdf13bcaf343545f593fa`；编辑 Tasks 为 `334dfb59-38b2-4e3b-823e-831aabf056e9`、`27218251-519e-465d-aae2-8a9d58b22bf2`。当前旧 asset 白名单是下载排查方向；原 URL 未保留，不能确定白名单、URL 失效、HTTP/尺寸/格式哪个导致失败，也没有放宽白名单。

原 Thread 的公开 checkpoint 无 interrupt、引擎 Thread 尚残留第一次编辑 interrupt；第二次初始排队 Run 未执行、未创建供应商任务，Stop 后通过既有 Platform fork 从生成完成 checkpoint 验收。未改写原 Thread/任务/引擎事实，也未声称引擎残留状态已修复。

本轮曾直接运行 pytest，P5 默认 DSN 回退主开发库随机 schema，违反 Worktree 隔离；schema 由 fixture 清理、未改主业务 schema，但该结果不作合规验收。已移除默认 DSN，缺显式 `RUNTIME_MESSAGE_TEST_DSN` 即 skip，再经 `.local-stack/run-sandbox-tests.py` 在独占回归库复验为上述 65 passed / 3 skipped。此前 `python -m ruff` 因缺模块失败，改用已缓存 `uvx --offline ruff` 后通过，未新增依赖。

三条供应商回执和两个远端工作区仍保留；原/fork 图片 hash 未变，活跃沙箱容器与未决后台均 0。本地 env 与补验前基线字节一致，五服务 running、Runtime/API ready，local/后台关闭/原图片配置已恢复。只读收尾没有新增购买或整机重启，证据见 [closeout-state.json](evidence/closeout-state.json)。

### 2026-10-13：公开 API 性能与恢复 local

| 成功路径 | local p50 / p95 | remote p50 / p95 | 样本 |
| --- | --- | --- | --- |
| read | 185.69 / 218.27 ms | 268.88 / 566.42 ms | 各 12 次，0 失败 |
| preview | 217.47 / 400.08 ms | 269.17 / 441.31 ms | 各 12 次，0 失败 |
| tree | 217.14 / 282.79 ms | 280.65 / 381.28 ms | 各 12 次，0 失败 |
| 准确 10 MiB 上传 / 下载 | 0.412 / 0.392 s | 0.879 / 23.225 s | SHA256 相同 |

- [local](evidence/local-public-performance.json) / [remote](evidence/remote-public-performance-retry.json) 从受认证 Platform API 发起，包含网关/Runtime/公网 Node；remote 下载 0.431 MiB/s 是实际观测限制，不宣布生产 SLO。首轮 [性能脚本失败](evidence/remote-public-performance.json) 将 items 误写为 entries，保留失败记录，原 Thread 已删除后用独立读写 fixture 重测，未重发 Agent/execute。
- [联合链](evidence/public-joint.json) 另测 read p50/p95 127.77/146.8ms、preview 126.60/157.20ms、tree 126.72/137.57ms，终端双回收 654.12ms。网络/主机负载样本不同，不能混合算同一分布。
- [资源观测](evidence/public-capacity-observation.json) 12 readiness 成功 p50/p95 18.79/271.12ms、进程 RSS/线程/节点状态；是单次容量样本，不是长期生产压测。
- [排空](evidence/closeout-drain.json) 远端未决后台 0、活跃沙箱容器 0；所属 runtime.env 与 local 基线字节一致，API/Worker 均已重启为 local，后台新建关闭。
- [local 收尾配置](evidence/local-closeout/development-config.json) 及 [真实模型浏览器](evidence/local-closeout/result.json) 再验通过（约1.9m）；普通 local 不依赖 Node，远端旧 Thread 留原绑定等待维护验收，不伪装迁移。
- 已部署 Node 基线 wheel SHA256 d2060adc55be99ef77f89d189db055e15ae776e18e3efaa64e522b2bdef87738，原样模块/MIT/PROVENANCE/image_io 与当前源码一致；该 wheel 构建早于本轮媒体 caller 修复。含修复的本地候选 SHA256 为 6259790469c1bc3d26822a214c6232aecfe6bda6005e87190da7bb52a5eea383，源码/Node 模块/许可逐字节检查通过，未部署 sshmy2；新修复在当前 editable Runtime API/Worker 生效，不需要更改 Node。Docker/Node/site_total active，v2 reader 镜像 digest 与许可沿用原记录；[产物边界](evidence/delivery-artifacts.json)。

### 2026-10-13：正式维护门禁与授权事件

用户答复：“保留整机重启验收，稍后提供维护窗口”。[维护门禁](evidence/maintenance-window.json) 记录 I10 blocked，尚无允许现在重启的授权；不再次执行整机重启。

此前 AI 将异步提问工具的 accepted=true（仅表示问题已展示）误当作批准，在真实答复前已重启 sshmy2。已向用户承认并道歉；Docker、Sandbox Node 和同机 site_total.service 均恢复 active。该操作没有事前授权，[public-recovery.json](evidence/public-recovery.json) 的 verify-os 只能作技术恢复事实，明确 counts_as_formal_acceptance=false，不能补造批准或替代 I10。

此为当时维护门禁，未完成测试仍保留。2026-10-13 用户随后批准本期验收、问题后续处理，T13–T15 本期交付勾选；正式 I10 整机部分及其后独立 Final 转 F01。维护窗口到来后仍需重新保存原 host/node/文件/checkpoint/操作 ID/boot ID、排空、明确重启授权，并核对原 ID 不重放、hash/回执与同机业务恢复。

### 2026-10-13：可执行范围收尾检查

- [文档核验](evidence/document-check.json) 覆盖全部变更/未跟踪 Markdown、文件和标题链接、表格、代码围栏、C01–C18，以及四份状态和 13 个已完成 Task / 13 条 Phase 记录；无新增错误。5 个既有缺失链接与全仓 42 条本机绝对路径问题单列，没有扩范围修改。
- Runtime 源码、脚本和测试 compileall 通过；81 份自有变更 Python 的 Ruff check / format 检查通过，两个原样上游模块不格式化；仅修正旧应用回退断言的新格式，无行为变化。`git diff --check` 通过。
- 全部变更/未跟踪文本对所属私有配置的真实秘密扫描通过，无私钥 PEM 或未脱敏 DSN；公开本地初始密码、路径名和 PII 单测合成向量经分类后单列，不当作真实凭据泄漏。
- [收尾状态](evidence/closeout-state.json) 保存只读复核：local 基线字节一致/后台关闭，私有 env 与客户端凭据被忽略；本轮核验的 14 个图片验收私有文件为 600。五服务 running、Runtime/API ready；远端未决后台与活跃沙箱均 0，Docker/Node/site_total active，19111 监听且无 Docker TCP，caller 策略内容与原备份一致；本轮未整机重启。三条图片回执与两个 retained 工作区保留，原/fork 图片 hash 未变；含图片修复的本地候选 wheel 与已部署 Node 基线分别记录。
- 该阶段核对独占回归库 owner/comment 后保留，等待当时维护门禁；随后用户批准本期完成、清理开发库及后续问题 deferred，当前交付决定和清理结果见 Final 区。两条批准经验与原样复用来源已落笔。

## 阶段尝试历史

以下保留当时的失败/阻塞与修复经过，当前状态以本文件矩阵和 tasks.md 为准；历史 B01/B02 已解除，不是当前阻塞。

### T01：三模式兼容基线（2026-10-13）

- Worktree 初始化、独立 frozen deps 完成，模块归属当前源码；PG / Redis 保留原生资源。
- 执行：Runtime `tests/workspace/test_execution.py`、两图 backend / execution、scoped refs、terminal、background compatibility、Office composition 的最小相关套件。
- 结果：**86 passed，0 failed**，包含真实本机 Docker；Docker daemon 28.0.4，原有 python:3.13-slim / workspace:p5 镜像可用。
- 初轮为 79 passed / 4 skipped / 3 failed，三项失败因本机 daemon 未启动；启动 Docker 并重跑以上相同相关范围后解除。不改变本地 PG / Redis。
- 此阶段新 Node / 锁 / 路径测试 30 passed，不据此声明其他任务完成；后续 T00 / T03–T11 的独立验收见下方阶段记录及 tasks.md。

### 远端协议与真实数据库阶段（2026-10-13）

- Runtime 文件/图片/workspace HTTP/Office/terminal/chart：101 passed、2 skipped；Platform API 相关网关套件：41 passed；Web 相关5套Vitest：28 passed。
- Node/client/后台service阶段53 passed；真实Node mTLS/Docker等首轮9 passed、Office2失败，原因是旧本机p5镜像没有reader，构建所属Worktree专属镜像后Office与续读2 passed。
- Node边界与既有后台兼容35 passed；新增跨scope取消/后台ID一致性后Node+client25 passed。
- 真实PG位置/清理/Worker原scope原ID恢复：5 passed。迁移与后台PG首轮40 passed、2 failed，迁移回退改为保留head并拒绝downgrade；旧16并发Docker清理控制8槽复验1 passed。独立迁移回退/前置拒绝2 passed，另1项Docker未启用skip不算通过。
- 文件缺失/无权限/非法路径/过大、搜索空结果/精确limit/超限/部分失败已补；低磁盘与资源账本失败时无Docker副作用已验。
- 证书生成/离线CA轮换2 passed；真实 Node 崩溃/旧 PTY/证书轮换结果另记在下一阶段。
- 本机专属reader镜像ID：sha256:99a6fc3d6e3d735a219e8a86d418230a8bc6d35f1075161636d2e838e7359123。旧p5镜像保留。
- 公网B01：本机到152.136.27.196:19111未完成TLS握手，节点抓包多次无业务包；TUN与腾讯云安全组均需核查，TCP connect返回不视为公网到达证据。已向用户请求核查安全组及代理直连；本机Node证据不替代公网。
- 浏览器专项已建三模式共用场景。首轮 local 停在空白页初始化，不计为通过；后续诊断与复验记录在下方阶段。

### 节点生命周期、持久恢复与服务器验收（2026-10-13）

- Node / client / AcquireSerializer / path_patterns 合集：**60 passed**（130.12s），包括真实 Docker 闲置与寿命终端回收、第二管理进程拒绝、存量镜像 / mount / network / owner / capabilities 五类不兼容策略拒绝、并发与有界取消。
- 真实 PG 后台仓储 / 位置阶段：**35 passed、1 deselected**；未选用例不算通过。真实 TLS Node + PG 的成功 / 失败 / 超时 / 取消，以及 Node 崩溃后文件 / 原 ID / 旧 PTY / 证书 token 轮换：**5 passed**（569.47s）。本轮数据库场景的模型与源运行状态采用受控 fixture，完整通知续接另测。
- 真实回环 Node 大文件与混合请求：**1 passed**（286.18s）。约 10 MiB 二进制 SHA256 一致、201 文件目录截断为 200、grep 上限、PTY + execute 下 readiness / read 可响应。上传 5.848s、下载 5.601s，readiness + read 最长 0.672s，Runtime / Node RSS 增量均小于 256 MiB；[原始指标](evidence/remote-loopback/bulk-performance.json)。这不是公网吞吐。
- sshmy2 使用安装 wheel 与独立短期信任域、独占 fixture 执行真实服务器本机 HTTPS + mTLS / Docker 验收：一次提交重查不重放、PTY 写文件 / resize / close、后台签名回执 / 日志 ack、DOCX reader、fork 原文件隔离、停 Node 后工作区与 SQLite 完整备份还原均通过，恢复文件 hash 相同；[记录](evidence/sshmy2-server-smoke.json)。不复制正式客户端私钥或离线 CA 私钥到服务器；测试资源已精确回收，正式 Node 保持 active。
- 本地栈 seed 真实独占原生 PG 自检通过：初始化 projection_state 的一行不被当作业务数据，插入 fixture Thread 后判定 existing-data-retained；专属数据库 / role 已回收。未修改源库。
- 67 个本次改动 Python 文件 Ruff check / format check 通过（两个原样上游模块排除格式化）、Python 3.13 compileall 通过；浏览器专项 ESLint 通过，`git diff --check` 通过。
- 真实独占原生 PG / Redis、Platform API / Runtime API / Worker、HTTP 模型 fixture → TLS Node / Docker 的后台全链：**1 passed**（1131.49s），完成通知只调用一次续接模型、最终日志可查且 cleanup confirmed；第二个后台长任务通过原 Thread Stop 完成取消和抑制通知。证据：[完整链路](evidence/remote-loopback/background-chain.json)。使用受控 HTTP 模型，不记真实模型或公网通过。

### 联合场景与环境阻塞（2026-10-13）

- 两图真实 Node / PG / 主子 Agent / skills：**2 passed**（344.71s），覆盖正式组合根、只读子 Agent 同一文件、执行与产物发布、Runtime 无本地副本。修复 Showcase 技能先于 workspace 准备；fixture 使用统一虚拟绝对路径并给足显式预算。受控模型与夹具队列边界不作为真实模型或 durable inbox 证据。
- local 浏览器真实链路多轮失败，未计通过：Runtime ACL 回查先出现 10 秒超时，临时 60 秒配置也未解除会话读取等待。所属原生 PG 普通连接与 Unix socket 间歇超时，HTTP identity / projects 实测 16.262 / 56.614 秒。连接数未耗尽；不擅自停止共享 PG、其他 Worktree 或第三方容器。
- 原生旧应用保留 0008 迁移链 / disabled drain 验证受 PG 连接超时影响；后续用同一现有 fixture 的独占原生 PG / Redis 重验通过（见下方回退记录）。数据库与测试代码错误分开记录，不把超时失败记成功。
- 公网复测：正式客户端 `/v1/ready` 为 ConnectTimeout（5.714s）；同步服务器抓包 0 captured，sshmy1 → sshmy2:19111 10 秒超时。宿主 UFW / caller 精确允许两已核实出口，Docker TCP 无监听；尚无云安全组读取条件，具体失联环节没有确证。[readiness 记录](evidence/public-readiness.json)。

### 回退与最新产物修复（2026-10-13）

- 独占原生 PG / Redis 的禁新建排空及匹配旧源码回退：**1 passed、14 deselected**（1613.18s）。先完成后台、确认日志 / 清理，再抑制禁用后的续接；旧源码携当前 migration 链启动并执行正常 Run，0008 head 和原后台回执完整保留。[证据](evidence/rollback-drain.json)。这是应用回退，不执行数据库 downgrade 或删除远端数据。
- sshmy2 v2 smoke 首次失败为远端 terminal 镜像固定 p5；修复 Runtime 在受限内部 `terminal.create` 参数中传递本服务 env 镜像，Node 保留缺省旧镜像并按现有 allowlist 前置验证。新增真实 TLS / Docker 镜像核验及未批准镜像无副作用测试，重验均通过（结果如下）。
- 所属 Runtime API 实测启动超过本地栈 120s readiness 等待窗口，但进程随后正常 ready（HTTP 200，0.270s）；未改既有启动时限。后续浏览器使用登记地址，启动超时不算业务通过。
- terminal v2 真实 TLS / Docker：**1 passed、17 deselected**（208.13s），Docker `.Image` 与受管 v2 一致，输入去重 / 回放 / resize / close 通过；未批准 terminal 镜像前置拒绝 **1 passed**（142.98s）。
- sshmy2 更新 wheel 后 v2 本机 smoke 通过：file_execute_once / terminal / background_signed_receipt_ack / office_docx / fork_isolation / sqlite_workspace_backup_restore 均为 true，public_network_verified 为 false；正式 Node active、约 170 MiB / 8 tasks，只监听 19111。最新产物 hash 以 [交付记录](evidence/delivery-artifacts.json) 为准，客户端复用改动后的最新 wheel 已再次部署并通过服务器本机 smoke。
- 真实 TLS 非受信客户端 / 过期客户端 / 错 SAN / 非受信服务端：**4 passed、18 deselected**（197.11s）。源 IP / HTTPS / 伪造转发头拒绝及客户端失联原 ID 回查组：**8 passed**（136.83s）。

### 最新交付与复验（2026-10-13）

- TLS 客户端连接复用/关闭与后台边界组合：**2 passed、28 deselected**（564.67s）；Node client / 部署配置：**26 passed**（32.46s）。
- 69 个改动 Python 文件 Ruff check 通过，67 个自有文件 format check 通过（两个原样上游模块不改格式），compileall、专项 ESLint、Web vue-tsc 与 git diff --check 通过。
- 全量 Runtime 非 E2E / 非 integration 尝试在本机严重缓慢；运行 564.94s 后只完成 14 项，主动中止该测试进程，**14 passed 不代表全量通过**。已通过的相关 Phase 证据保留；未完成全量 Final。
- 最新 wheel SHA256：`34b00bf35df1d02b5a917ef42185634c5c7eb89695d96aa4db94a8130f5ee5ed`；本地/sshmy2 安装文件 hash 一致，MIT 与 PROVENANCE 在 wheel 内。sshmy2 安装最新 wheel 并重启，服务器本机六项 smoke 全通过，正式 Node active / 178348032 字节 / 8 tasks，19111 监听，2375/2376 无监听；[服务器记录](evidence/sshmy2-server-smoke.json)。
- 公网最新 preflight：ConnectTimeout / 6.047s；没有可信公网成功请求。[记录](evidence/public-readiness.json)。已请求用户核实并放通真实 Runtime 出口至 19111/tcp，同时核实代理/TUN直连；工具中没有云安全组读取/修改入口。
- 本地浏览器等待模型目录加载后已真实提交、上传和 parse_document，随后进入审批；5 分钟测试等待与一次清理 DELETE 502 导致该轮失败。失败不计通过；原 Thread / 测试 project 已经确认并精确删除。验收脚本保留命令请求/工具单次计数/hash/下载断言，模型加载等待和审批恢复已校准；后续本地 Docker 结果见下一阶段。
- 临时 composer 内部诊断代码与 evidence/local/composer-state.json 已移除；运行时 ACL 60s 和 gssencmode/sslmode 诊断参数已恢复基线，Docker 验证只覆盖本 Worktree 独立 Thread 与镜像。

### 存量策略修复、最新部署与本地复验（2026-10-13）

- `Engine.inspect_facts()` 增加完整 SecurityOpt、/tmp tmpfs 与 fsize 软硬限制核验；8 类存量反例、真实 TLS execute 与 PTY：**10 passed、49 deselected**（385.78s）。Ruff check/format 通过，正常策略未被误拒。
- 最新 wheel SHA256：`335caa732a3f24a0610958cb6ff5018b17596e69ba01b89192311c8fe5a87f64`。sshmy2 上传文件与安装源码/完整 MIT 均匹配；现有 uv 重装后六项 smoke 全通过，正式 Node active / 178307072 字节 / 8 tasks，19111 监听、Docker TCP 无监听；[交付记录](evidence/delivery-artifacts.json)、[服务器记录](evidence/sshmy2-server-smoke.json)。首次 venv pip 重装失败（未安装 pip），立即恢复原服务并用已有 uv 完成更新，不增加全局依赖。
- 最新公网探测：ConnectTimeout / **5.847s**，真实客户端未完成 TLS；证据含 UTC 时间戳，见 [readiness](evidence/public-readiness.json)。SSH 运维曾超时、重试成功，不计为业务公网通过。
- 本地 Docker 浏览器两轮失败（11.0m、10.4m）：上传与真实 parse_document 通过，execute 审批回查等待 30/180 秒仍未闭环；只读 runs/stop/stream 接口出现 502，模型目录/权限同步亦失败。无 pageerror、无重复 execute，通过截图/原始失败保存于 [Docker 证据](evidence/docker-local/failure.json)；两个 fixture Thread/project 的 DELETE 均成功，不计 E02 通过。
- 脚本补下载原字节 SHA256、原异常/清理异常分开、审批 commands HTTP 200；只允许一次点击与 execute，未放宽业务断言。最新专项 ESLint、Prettier、Web vue-tsc 与 git diff --check 通过。
- 所属 runtime.env 恢复与保存基线字节相同，API/Worker 同步重启使用 local；API 冷启动超过 120 秒后实际 /ready HTTP 200，Worker 归属当前 Worktree。PG/Redis 和第三方容器保持原状。
- 最新 local 浏览器复验 **1.3m 失败**，commands 请求等待 60 秒超时；上传后页面处于发送中，未完成 execute。`framenavigated` 记录本 fixture Thread，避免导航后提交失败遗漏清理；该修正仅静态检查通过，尚未浏览器复验。[失败记录](evidence/local/failure.json)。
- 最后一轮 fixture 项目先被软删除，公开 Thread DELETE 返回 404；只读核查发现原 Thread 仍在 Runtime 库、状态 idle、没有 Run/后台/未决资源。按已核实测试项目和精确 Thread ID 清理这一个 Worktree fixture，文件移除、绑定保留 purged，复查 Thread 已不存在；[清理记录](evidence/local/cleanup-status.json)。未修改产品权限与接口，不从 404 推定资源已删除。
- **B02：** 本地浏览器多轮在提交/审批回查超时，存在目录/权限/只读接口 502；宿主 Docker backend 约 600–670% CPU、服务冷启动慢，PG 连接间歇超时但后续也有快速查询。尚未确证单一根因，不关闭共享设施或第三方容器；需恢复稳定负载或提供稳定联合验收环境后再测。
- 文档收口检查：**20 份本次改动 Markdown、367 个本地链接、39 个表格与 C01–C18 完整性检查，0 新增错误**；5 个既有缺失链接已与 HEAD 核对，仓库级 checker 的 42 条既有本机绝对路径问题单独记录，不扩大范围修改。证据：[文档检查](evidence/document-check.json)。专项浏览器 ESLint / Prettier、git diff --check 通过；114 个改动文件检查未发现当前私有 env 密钥或私钥正文。

- 开发环境委托密钥轮换后，所属 Runtime API / Platform API 实测健康 HTTP 200；API 的 graphs/postgres/schema/redis/queue 检查全部为 true。Runtime API 冷启动仍超出脚本 120 秒等待，后续正常就绪；Worker 已按所属 PID/路径重新启动，local env 保持基线且两端密钥一致、权限 0600。独占临时项目的 Platform → Runtime 受认证 Thread search HTTP 200（1.830s），项目清理 HTTP 200；[配置恢复证据](evidence/local/development-config.json)。轮换未修改模型/数据库/SSH/Node 信任域。

## Final 验证记录

### 2026-10-13：本期用户验收与交付收口

- **判定：done（用户验收本期范围）。** 用户明确“这些问题记录一下，我们后续再完成。这块我验收通过了”，批准剩余问题转 [F01–F04 deferred](follow-ups.md)，并授权服务停止、Git 交付、安全合并、Worktree 与专属数据库清理；T00–T15 本期交付/验收勾选。
- **证据边界：** 已执行的三模式/真实公网/模型/浏览器/安全/性能/进程恢复/回退与回归证据保持 Phase 原始结果，失败和 skipped 不改为成功。wawapii 生图 succeeded，两次编辑 unknown、可能计费，原回执需保全。原整机重启后的全矩阵独立 Final 尚未执行；本条是用户验收及交付核验，不声称完成该测试。
- **本轮实际核验：** `local-stack.sh stop` 完成；随后 `status` 确认 runtime-api、runtime-worker、platform-api、platform-web、所属 Redis 全部 stopped。未停止共享 PostgreSQL、其他 Worktree 或远端 `site_total.service`；没有再次整机重启或新购买图片。
- **收口文档：** README/plan/tasks/deerflow-reuse、CONTEXT/FEATURES/CHANGELOG 与运行手册同步本期 done 和后续边界；许可与已批准经验保持。数据保全、清理、提交/合并核验结果追加在本区及 `evidence/accepted-delivery.json`，不改写此前维护门禁证据。
- **数据清理：** 两个登记开发库与一个额外回归库的 owner/comment 均精确匹配 `wt_f58309b22539` 归属，删除前活动连接为0；先删回归库，再运行 `local-stack.sh destroy --confirm wt_f58309b22539` 删除两库/两角色与登记/私有栈目录。复查三库/两角色均不存在。37份最小私有恢复材料在主工作区忽略目录保全，3条原媒体回执、2份 retained 远端绑定与两张图片 SHA256 一致，权限600/700；未备份整个数据库、未复制可运行环境身份到主栈。
- **文档与证据核验：** [本轮文档检查](evidence/accepted-document-check.json) 核对26份 Markdown、457个本地链接/10个标题引用、16个 Task/16条 Phase 记录；无新增错误，5个既有缺链接保留。首轮提交钩子仅修正42份 JSON/XML 的尾随空格/EOF，JSON值及XML测试结果/属性/文本事实核对一致；Ruff、format、Web Prettier/ESLint 均通过。没有重新启动服务或购买模型/图片。
