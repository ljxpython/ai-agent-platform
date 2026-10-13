# Runtime 单节点远端 Docker 沙箱：任务拆分

> 进度事实来源。G00 已获人工批准，项目进入实施；任务完成以验收证据为准，不以文件存在或某一阶段测试通过为准。
> 当前状态：已完成 / done（2026-10-13 用户验收）。T00–T15 本期范围收口；原 I10 整机部分/后续独立 Final、真实编辑、留存夹具与残留 interrupt 排查按用户决定转 [后续事项](follow-ups.md)。勾选表示本期交付/验收完成，不表示 deferred 验证已经执行。

## 规划交付

- [x] P01：读取项目状态、Runtime / 跨服务规范和当前执行、文件、终端、后台任务、清理代码；沿用本会话此前的服务器只读探测事实。
- [x] P02：创建 README / plan / tasks / verification，明确公网、单节点、三种模式、env 归属、容器与工作区不同生命周期。
- [x] P03：同步 CONTEXT / FEATURES，检查本次 Markdown、链接、事实与任务 / 验收覆盖，将真实结果写入 verification 的“规划检查”区域（2026-10-12）。
- [x] P04：核对 deer-flow 的 Provider / Provisioner、文件、身份、并发 / 租约、取消、回收、网络与 SDK 实现，记录 C01–C18、直接复制候选、MIT 许可、固定提交和本地未提交状态（2026-10-12）。
- [x] P05：完成 HTTPS + mTLS 修订、证书 env、任务 / 验收补齐与平台无业务改动边界，同步 CONTEXT / FEATURES。7 份变更文档、17 个项目文件 / 标题链接、围栏 / 表格 / 格式与 C01–C18 / 验收编号检查通过，`git diff --check` 通过；全仓既有 12 文件 / 42 问题已在 verification 单列（2026-10-12）。

## Phase 0：人工评审

### G00：批准详细治理方案

- [x] **状态：已批准，2026-10-12。** 用户明确批准修订后的 G01 公网 HTTPS + mTLS / caller 执行域认证 / Docker 本机 socket / SSH 运维边界，并授权开始全部实施；G02–G05 既有设计与 deer-flow 能力补齐 / 适合模块复用一并纳入。
- **评审材料：** [plan.md](plan.md#人工评审项)、[deer-flow 复用矩阵](deerflow-reuse.md)。
- **批准记录：** 批准人：用户；日期：2026-10-12；范围：T00–T15 全部实施、必要 schema / 配置 / 节点专属资源变更、sshmy2 专项部署与验证；保留边界：不为 sshmy1 安装 Docker，不改变共享 PG / Redis，不做全局 Docker 清理，不开放 Docker TCP API，不提交或推送 Git。
- **依赖规则：** 代码、schema、专项服务器配置和隔离资源操作已获授权；平台现有业务契约仍按方案保持不变。

### G06：本期验收、后续事项与交付清理

- [x] **状态：已批准，2026-10-13。** 用户明确“这些问题记录一下，我们后续再完成。这块我验收通过了”；本期按 done 收口，剩余验证/排查记录 deferred。授权停止本 Worktree 服务、提交和推送专项分支、安全合并及推送主工作区、清理该 Worktree 与专属测试开发数据库；覆盖 G00 当时不提交/推送 Git 的限制，不授权新图片购买或整机重启。

## Phase 1：兼容基线、配置与节点基础

### T00：直接复用模块、测试与来源接入

- [x] **状态：已完成，2026-10-13；固定源 hash、两个模块的实际调用、完整 MIT / 来源随 wheel 和本地 / sshmy2 v2 镜像分发均已验证。**
- **来源：** [deerflow-reuse.md](deerflow-reuse.md) 中 `sandbox/acquire_serialization.py`、`sandbox/path_patterns.py` 及相关纯契约测试。
- **位置：** 拟新增共享 `workspace/acquire_serialization.py`、`workspace/path_patterns.py`；`workspace/third_party/deerflow/LICENSE` / `PROVENANCE.md`；Runtime `tests/workspace/` 对应测试。
- **工作：** 固定提交 / 源哈希、保留 MIT 和版权、标注必要 import / 测试改动。互斥组件接 Node prepare / 文件变更 / fork / delete / resource 转换，路径匹配接 Node 结果和 Runtime 安全投影；与 T03 / T05 共同接线，不能放入未使用模块后宣称完成。
- **兼容：** 不复制 deer-flow 用户 / Thread ID 算法、字符串 `Sandbox` 接口、宿主 env 继承或整个 Harness；优先复用本项目清理、DB lease / fence 和文件安全模块。
- **验收：** U12、U15–U16，I14；独立契约与真实调用路径均通过；wheel / 镜像包含完整许可证和来源，无 `deerflow.*` 运行 import、新依赖或未使用代码。
- **依赖：** G00、T01。先交付可导入模块 / 来源 / 独立测试这一基线，供 T03 / T05 开始接入；完成卡必须在 T03 / T05 实际调用路径验收后填写，T03 / T05 不等待 T00 最终完成卡。
- **完成卡：** `workspace/acquire_serialization.py` / `path_patterns.py` 原样复用；Node 锁 / 输出映射实际使用，两个对应测试仅适配 import / trace fixture。
- **验证项：** 来源 hash 自检、契约及 Node 合集 60 passed、wheel 逐字节验证、本地 / sshmy2 v2 镜像内 MIT hash 和 PROVENANCE 自检通过；[产物](evidence/delivery-artifacts.json)。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT / FEATURES / CHANGELOG 已同步，整体 Final 状态在 T15 单列。

### T01：冻结三种模式的兼容基线

- [x] **状态：已完成，2026-10-13。**
- **范围：** `workspace/execution.py`、`workspace/terminal.py`、两个 Agent backend、`tools/documents.py`、`background_tasks/capabilities.py` 与当前相关测试。
- **工作：** 记录 local / 本地 Docker 的默认值、路径、权限、HITL / Stop、后台开关与旧任务可查语义；确认 Office 固定 Docker reader 例外。
- **验收：** U01、U02、I01、I02；既有本地文件与同 Thread 二次执行正常；不得为普通 local 引入 Docker / Node 依赖。
- **依赖：** G00。
- **完成卡：** 现有兼容基线冻结；单独 Runtime 默认 docker，本地栈初始化 local，Docker target 缺省 local，Office 固定 reader 与后台禁新建 / 可查历史语义保留。
- **验证项：** Runtime execution / 两图 backend / scoped / terminal / background compatibility / Office composition → 86 passed（包含真实 Docker）；初轮 daemon 未启动导致的 3 项失败已重跑解除。
- **合规检查：** [x] 基线确认；[x] 验证已执行；[x] tasks 已更新；CONTEXT / FEATURES 已标实施中，CHANGELOG 在能力验收时统一收口。

### T02：目标配置、env 与本地栈接线

- [x] **状态：已完成，2026-10-13；API/Worker 使用同一所属 env。**
- **位置：** `apps/runtime-service/.env.example`、`deploy/.env.runtime-service.example`、`deploy/.env.runtime-service.host-infra.example`；`scripts/local-stack.sh`、`scripts/local_stack_worktree.py`、`scripts/local_stack_processes.py`；配置校验入口。
- **工作：** 新增 target / node_id / HTTPS URL / AUTH_FILE / CA / 客户端证书与私钥路径的解析与校验；API / Worker 配置一致。保持本地栈默认 local、独立 Runtime 默认 docker、target 缺省 local。Worktree 初始仍为 local，但所属 runtime.env 的显式 docker 设置应生效，不被工具强制 local 覆盖；保留登记 host 与独立资源，不继承生产 host。
- **产出：** 示例模板；真实 env / token / 私钥不提交。补拟新增 `.env.sandbox-node` 和秘密目录的忽略规则，不修改用户真实 env。
- **验收：** U01、U03、S01、S06；remote 缺键 / node 身份不匹配前置失败，本机没有 Docker CLI 时 remote 仍可通过配置预检。
- **依赖：** T01。

- **完成卡：** `workspace/target.py` / `scripts/validate_runtime_config.py` / `scripts/local_stack_worktree.py` / `scripts/local-stack.sh` 接入三模式、缺键校验和所属 env 优先级；真实凭据留私有目录。
- **验证项：** 配置相关 19 passed、证书 2 passed；兼容基线 86 passed；真实 seed 自检通过。local 不加载 Node，本机无 CLI 不阻止 remote 配置验证。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT / FEATURES / CHANGELOG / 运行规范已同步，整体 Final 状态在 T15 单列。

### T03：最小 Node 协议、启动角色与认证

- [x] **状态：已完成，2026-10-13；本机真实 mTLS / 恢复与单管理者已验，公网部署验收见 T12。**
- **位置：** 拟新增 `apps/runtime-service/src/runtime_service/sandbox_node/`，共享 workspace 目标客户端；拟新增 `deploy/.env.sandbox-node.example` 与单进程 TLS / systemd 启动配置。
- **工作：** 固化内部 HTTP v1 DTO；复用现有 FastAPI / HTTP 依赖，独立 Node app 不运行 Agent / PG / Redis。mTLS 与 caller token / execution host 同时校验；显式本机 Docker socket、受管镜像集合、SQLite 操作 / 资源登记；readiness 在只读启动对账与依赖检查后准入。
- **连接与生命周期：** 原生 / 容器 Runtime 同一 HTTPS URL，CA / SAN 检查和客户端证书；禁系统代理 / 重定向 / 自动副作用重试，关闭连接池与线程资源。一个 Node 管理进程拥有 PTY / janitor / 容量，关闭准入后有界 drain。
- **验收：** U03、U05、U12–U13、I03、I14–I15、S01–S03、S08；无 / 错证书及跨域请求拒绝、密钥不进容器、资源记录失败无副作用、查询不创建 / 销毁。
- **依赖：** T02、T00 模块与来源基线；T00 实际接线证据在本 Task 产出。

- **完成卡：** `sandbox_node/service.py:create_app()`、`protocol.py:Rpc`、`ledger.py:Ledger` 与 `node_client.py` 接入受限协议、认证、持久账本、readiness / drain / 关闭。
- **验证项：** Node/client/上游模块合集 60 passed；真实 Node/PG 与崩溃 / 证书轮换 5 passed；sshmy2 独占 mTLS fixture 通过。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT / FEATURES / CHANGELOG / 运行规范已同步，整体 Final 状态在 T15 单列。

### T04：持久工作区绑定与旧目录兼容

- [x] **状态：已完成，2026-10-13；真实 PG 原子绑定 / 旧目录 / 冲突 / tombstone / 原 ID 恢复、迁移冷安装与旧应用保留 0008 链回退均已验。**
- **位置：** `workspace/scoped.py` → `thread_scope_hash()` / `resolve_thread_workspace()`；Runtime 应用 db 仓储与 `src/runtime_service/db/migrations/versions/`；Node workspace resolver。
- **工作：** 原子建立 execution host / tenant / project / thread / graph 到 storage target / node / workspace 的位置记录；旧本地目录不迁移。区分位置与计算 backend，本地 local ↔ 本地 Docker 使用同一目录。受控切换前登记旧工作区，冲突拒绝、不静默覆盖。
- **数据保护：** 保留 deleting / purged 标记；远端既有工作区丢失时不创建空目录假恢复；绑定不可被客户端 Thread metadata 改写。
- **验收：** U04、I04、I10、S02、R01；API / Worker 并发绑定一致，模式 / node 变更不能误读旧目录；migration 冷安装 / 升级和应用回退验证。
- **依赖：** T02、T03。

- **完成卡：** `workspace/locations.py` / `scoped.py` 与迁移 0006–0008 实现持久位置和资源绑定，API / Worker 恢复使用原 scope / 原 ID；应用回退保留 schema head 和历史回执。
- **验证项：** 真实 PG 位置 / 清理 / 恢复 5 passed；冷安装各分支通过；禁新建 drain + 匹配旧源码回退 1 passed（1613.18s），[回退证据](evidence/rollback-drain.json) 显示正常 Run 成功、0008 head 与原回执保留。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT / FEATURES / CHANGELOG 已同步，整体 Final 状态在 T15 单列。

## Phase 2：完整工作区能力接线

### T05：文件存储、DeepAgents backend 与执行快照

- [x] **状态：已完成，2026-10-13；真实 Node 两图主子 Agent / skills 与文件边界已验；浏览器整体门禁见 T13。**
- **位置：** DearFlow `workspace/backend.py` → `DearWorkspaceBackend` / `prepare_custom_skills()`、`middleware/skills.py` → `ExecutionSkillsMiddleware`；Showcase `services/demo/showcase_demo/backend.py` → `create_workspace()` / `build_backend()`；共享 workspace 文件操作与 Node handler。
- **工作：** remote 实现完整文件协议与 prepare；Node 复用安全目录 / 文件逻辑，不接受宿主路径。文件修改 / edit 在可信键锁内校验并原子发布，read / tree / search 生成时有界；missing / 空结果 / 失败 / 截断分开。Skills / memory / 系统内容由 Runtime 受信生成，按内容摘要发布只读快照；保留现有 CompositeBackend 和历史快照恢复，输出虚拟路径映射接 T00 helper。
- **调用方：** 主 / 子 Agent、只读子工具、文件上传下载接口、StateBackend / 大工具结果外置、图组合根均逐一检查；`.skill-executions` 登记、文件锁、快照 `.root.parent` 路径与恢复必须一同适配。
- **验收：** U06–U07、U12、U14–U15、I05、I10、I14、I16、S03–S04、S07；相同虚拟路径可用、跨 scope / 符号链接拒绝、Node 看不到 Runtime 模型 / 平台秘密；远端数据不写入本地 workspace。
- **依赖：** T04。

- **完成卡：** `workspace/remote_backend.py` / 两图 backend / `middleware/skills.py` / `sandbox_node/storage.py` 实现完整 DeepAgents 协议、远端 snapshot 和同绑定文件操作；Showcase 首次 skills 读取先幂等 prepare。
- **验证项：** 文件链 101 passed、2 skipped（跳过不算通过）；Node 边界合集 60 passed；两图主子 skills 2 passed，真实回环二进制 / grep / tree / edit / fork 与 10 MiB 哈希通过。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT / FEATURES / CHANGELOG / 运行规范已同步，整体 Final 状态在 T15 单列。

### T06：上传、预览、下载、图片、Office reader 与 fork

- [x] **状态：已完成，2026-10-13；真实 Node DOCX/PPTX、续读、二进制/HTML/ZIP、图片、产物与 fork 隔离已验；浏览器完整链路归 T13，公网门禁单独记录。**
- **位置：** `http/workspace.py`、`http/documents.py`、`http/images.py`；`workspace/browser.py`、`documents.py`、`artifact_refs.py`、`archives.py`、`document_reader.py`；`tools/images.py`、`tools/documents.py`、`tools/chart.py`、`tools/artifacts.py`；DearFlow `tools/search.py` → `_evidence()`、`tools/skills.py`、`tools/deployment.py` 及 Agent 组合根。
- **工作：** 所有文件入口按同一位置读写；保留 FileRef / ImageRef、SHA256、MIME、限额、分页、HTML CSP 和审批；远端 reader 使用既有 Docker 镜像 / 有界续读；同节点 fork 复用当前复制白名单。研究 / GitHub / 论文证据落 `/workspace/sources/`，技能包上传 / 更新与部署包读取也走原绑定，不回本机磁盘。
- **边界：** 图片 / 模型凭据保留在 Runtime；不得把 Runtime `.root` 的字符串转发为节点宿主挂载；partial upload 不成为可读成品；派生包临时文件必须回收。
- **验收：** U06–U07、U14–U15、I05、I06、I11、I16、E03、S03–S04、S07；真实 DOCX / PPTX、图片 / PDF / ZIP / HTML 与产物链路；不同 Thread 的 fork 文件隔离。
- **依赖：** T05、T07（reader 执行）；可以与 T07 并行开发，联合验收依赖两者完成。

- **完成卡：** `http/workspace.py` / `workspace/documents.py` / `image_io.py` / `artifact_refs.py` / `browser.py` / `tools/documents.py` 复用同一绑定，Office 经 Node reader，fork 复制白名单文件并建立新绑定。
- **验证项：** 既有文件链 101 passed、2 skipped，真实 TLS DOCX/PPTX 有界续读 2 passed；二进制/hash/图片/HTML/ZIP/fork 通过；sshmy2 v2 本机 DOCX、fork 与备份恢复通过。浏览器/public 验收不计入该完成卡。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks 状态；[x] CONTEXT / FEATURES / CHANGELOG / 运行规范已同步，整体 Final 状态在 T15 单列。

### T07：远端 execute、一次提交与 Stop / 回收

- [x] **状态：已完成，2026-10-13；一次执行、原 ID 回查/Stop、容量前置拒绝、timeout/截断与 Worker 恢复已验；公网平台链路见 T13。**
- **位置：** `workspace/execution.py` → `execute_in_workspace()` / `docker_workspace_args()`；共享 Node client；Node executor 与持久资源记录；现有 Run control resource 接线。
- **工作：** local / 本地 Docker 保持；remote 由 Node 执行，按节点 UID / GID 和受管参数挂载。执行前登记固定 ID / 摘要，取消与回查使用原 ID；保留 1–60 秒 timeout、输出截断、单次执行与 unknown 控制流。
- **验收：** U05、U08、U12、U15、I07、I12、I14、E02、S03、S05、S07；对可信“已接收”后丢响应的 fixture，副作用计数为 1；前置拒绝为 0，其他 unknown 不能推定执行次数但绝不重放。Stop 确认与清理 unconfirmed 分开，节点满额前置拒绝，晚创建 / 重复取消有界收尾。
- **依赖：** T03–T05。

- **完成卡：** `workspace/node_client.py:execute()`、`execution.py:execute_in_workspace()`、`run_control/resources.py` / `service.py` 与 Node engine 统一固定 ID、可信前置拒绝、unknown、deadline 与有界回收。
- **验证项：** Node/client 合集 60 passed，真实 PG 原 scope / 原 ID 恢复 5 passed；真实 TLS / 服务器 execute 去重与 timeout；前置拒绝副作用 0、可信已接收 fixture 副作用 1。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT / FEATURES / CHANGELOG / 运行规范已同步，整体 Final 状态在 T15 单列。

### T08：远端交互终端

- [x] **状态：已完成，2026-10-13；PTY 输入去重/回放/resize/owner/close、idle/lifetime、Node 重启旧实例拒绝已验。**
- **位置：** `workspace/terminal.py` → `TerminalSession` / `TerminalManager`；`http/terminal.py`；Node PTY。
- **工作：** remote PTY 归 Node，Runtime 继续鉴权与代理；保持 offset 字节回放、sequence 输入幂等、resize、owner 与 request_id 去重。无输入 15 分钟、最长 1 小时、close 后删除容器并保留文件。
- **重启：** Node 实例变化后旧 PTY 不恢复；对账并关闭旧实例遗留终端容器。Runtime / 浏览器重连只读查询，不重复写入 terminal input。
- **验收：** U09、I08、I10、E04、S02、S05；create / read / write / resize / close 与过期、限额、跨 owner 拒绝；本地 sticky routing 约束保留。
- **依赖：** T04、T05、T07。

- **完成卡：** `workspace/remote_terminal.py`、`terminal.py:TerminalManager` 与 `sandbox_node/terminal.py` 保留原 HTTP / owner / offset / sequence 契约，PTY 归 Node；关闭容器保留文件。
- **验证项：** 合集 60 passed 含真实 Docker idle / lifetime；TLS Node 终端与崩溃恢复、sshmy2 本机 create/write/resize/close 验收通过。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT / FEATURES / CHANGELOG / 运行规范已同步，整体 Final 状态在 T15 单列。

### T09：后台任务远端控制与日志回执

- [x] **状态：已完成，2026-10-13；真实 PG / API / Worker → TLS Node 后台完成续接、日志确认与 Thread Stop 已验；公网与真实浏览器见 T13。**
- **位置：** `workspace/background.py` → `BackgroundBinding` / `create_task_container()` / `inspect_task_container()` / `read_task_receipt()` / `remove_task_container()`；`background_tasks/service.py` → `start_task()` / `reconcile_due()`；`repository.py` 与 `output.py`。
- **工作：** 复用现有提交键、任务状态、Stop、lease / fence、签名回执和完成续接；位置摘要使用稳定远端标识。`execution_host_id` 仍是部署 / Worktree，node_id 单独绑定，既有本地记录保持旧摘要兼容。
- **清理：** 节点保存有界日志 / 回执，Runtime 持久确认后再删除；无确认保留证据。后台默认开关不变，失联 / missing container 保留 unknown、不重新提交。
- **验收：** U10、I09、I12、E05、S02、R02；完成、失败、取消、节点断开、Runtime 重启、回执未确认、重复 reconciler 与旧 local 查询均覆盖。
- **依赖：** T04、T05、T07。

- **完成卡：** `workspace/remote_background.py` / `background.py`、`background_tasks/service.py` / `repository.py` 接入原 node / task ID、lease / fence、签名回执与 ack 后删除，保留旧本地摘要与禁新建可查历史语义。
- **验证项：** 真实 PG仓储 35 passed；真实 TLS Node + PG 四终态及崩溃轮换组 5 passed；正式 Platform API / Runtime API / Worker 远端回环完成续接与 Thread Stop 1 passed（1131.49s），续接模型只调用一次。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT / FEATURES / CHANGELOG / 运行规范已同步，整体 Final 状态在 T15 单列。

## Phase 3：回收、恢复与真实部署

### T10：节点遗留容器对账与容量准入

- [x] **状态：已完成，2026-10-13；2 槽硬准入、低磁盘/账本写失败、存量八类策略拒绝、Node 崩溃对账已验。**
- **位置：** Node executor / resource ledger / janitor；`workspace/execution.py`、`terminal.py`、`background.py` 的远端清理通道。
- **工作：** 启动 / 周期对账受管标签和持久 ID，核验镜像 / 挂载 / 网络 / 权限 / deadline 策略；只读 discover / list 与准入 / 清理安全诊断。普通容器、终端按 deadline 回收，后台停止与证据删除分开；并发 prepare / 上传 / Agent / fork / apply 互斥，资源未决不能误清。全节点 2 活跃容器原子准入，磁盘不足前置拒绝；不扫描 / 删除未归属容器。
- **验收：** U08–U10、U12–U13、I12、I14–I15、S05、S08、P01–P02；Node 崩溃 / Runtime 断开仍有硬 deadline；不合策略的存量资源拒绝接管；没有全局 prune、超软上限或新 Redis ownership。
- **依赖：** T07–T09。

- **完成卡：** `sandbox_node/engine.py:reconcile()` / `Ledger.reserve()` / `service.py` 管理者锁接入硬准入和受管资源对账；Created 后台资源保持 reserved，策略不符拒绝接管。
- **验证项：** 合集 60 passed；新增 seccomp/tmpfs/fsize 与原五类存量策略、真实 TLS execute/PTY 10 passed；Node 崩溃恢复 1 项在 5 passed 组内；混合 readiness / 10 MiB 性能 1 passed，无 OOM、不同 key 可并行。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT / FEATURES / CHANGELOG / 运行规范已同步，整体 Final 状态在 T15 单列。

### T11：工作区保留、精确清理与同 Thread 恢复

- [x] **状态：已完成，2026-10-13；候选/retained/宽限/tombstone 与并发保护已验，真实进程重启和服务器 fixture 备份还原 hash 一致。**
- **位置：** 持久绑定仓储；Node workspace；`scripts/sandbox_workspace_cleanup.py` 精确清理入口；原 `scripts/r6_workspace_cleanup.py` / `services/demo/workspace_demo/policy.py` 保持既有用途。
- **工作：** 默认只报告工作区候选；所有保留 Thread 受保护。候选需删除 / 已核实孤儿事实、7 天示例宽限、无运行 / 排队 / interrupted / unknown / 回执未决资源；apply 互斥与二次核对、位置 tombstone。
- **恢复：** 重开同 Thread 新容器挂原目录；Runtime / Node / 主机重启后恢复文件和绑定；缺目录或 purged 返回失败，绝不自动补空目录；skills 快照按引用保护。
- **验收：** U11、I10、I13、E06、R01–R02；保留 Thread 闲置超 TTL 仍可恢复；所有删除测试只用授权的隔离 fixture。
- **依赖：** T04、T06、T08–T10。

- **完成卡：** `workspace/cleanup.py`、`sandbox_node/cleanup.py` 与 `scripts/sandbox_workspace_cleanup.py` 提供精确 report/mark/apply 和双侧二次核对，默认保留所有 retained Thread；位置丢失/purged 不建空目录。
- **验证项：** 真实 PG 位置 / cleanup / Worker 恢复 5 passed；Node 合集 60 passed；真实 TLS 重启与 sshmy2 SQLite / workspace 停机备份还原通过。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT / FEATURES / CHANGELOG / 运行规范已同步，整体 Final 状态在 T15 单列。

### T12：sshmy2 部署准备与公网连接

- [x] **状态：已完成，2026-10-13；用户放通 19111 后，真实 Runtime 开发机经公网 mTLS readiness、文件、execute、PTY、后台与 Office smoke 均通过，B01 已解除。**
- **位置：** `apps/runtime-service/deploy/` 的 Node TLS / systemd 交付配置、节点预检与运维说明。
- **工作：** 再次只读核实 Docker、磁盘、SSH、镜像源、实际 Runtime 出口 IP 和 Node URL / SAN；获具体授权后安装产物 / 专用账号 / 持久目录 / mTLS 证书与 token、镜像与单进程服务，按允许 IP 开放 Node HTTPS。Docker 无 TCP 监听、沙箱无端口 publish；SSH 仅运维。记录证书有效期 / 轮换与缺配置拒绝启动，不依赖 sshmy2 本地别名。
- **验收：** I03、S01、S06、P01；从真正的 Runtime 主机执行 remote 文件 / 命令 smoke；记录版本 / 镜像 digest / 端口 / 所有权，不记录秘密。
- **依赖：** T02、T03、T10；真正的平台切流需 T05–T11 全部通过。
- **风险边界：** 不为 sshmy1 安装 Docker，不改变现役 PG / Redis，不执行未经批准的防火墙 / 用户组变更或全局镜像清理。

- **完成内容：** Node 专用账号/证书/systemd/持久目录、v2 镜像与最新策略核验 wheel 已部署；安装源码与 wheel hash/MIT 一致，正式服务 active；服务器六项 smoke 再次全部通过。
- **验收证据：** [公网 readiness](evidence/public-readiness.json)、[公网业务 14 组检查](evidence/public-business.json)、[公网安全与 Node 重启](evidence/public-security-restart.json)。源 IP 拒绝后原 caller 策略已恢复；2375/2376 没有监听，Docker API 公网不可用。

## Phase 4：联合验收、回退与交付

### T13：单元、集成与三模式 E2E

- [x] **状态：本期验收完成，2026-10-13；三模式真实模型浏览器、两图公网完整工具/后台/Stop/恢复/撤权、回归与媒体存储适配已验；wawapii 真实生图 done，原 I10 整机部分和真实编辑按用户决定 deferred。**
- **位置：** Runtime 现有 `tests/` 套件及必要的 remote fixture；Platform API / Web 使用既有 workspace / terminal / background 测试与真实链路。
- **工作：** 执行 [verification.md](verification.md) 的 U / I / E 矩阵；真实公网 sshmy2 与浏览器验证上传、Agent 执行、产物预览下载、终端、后台与恢复。真实模型优先 miaomiaoai `deepseek-v4.1-flash`。
- **验收：** 三模式完整核心链路、C01–C18、现有权限和错误契约回归；测试 evidence 区分 mock / 本地 / 远端 / 真实模型，不以 mock 替代公网验收。
- **依赖：** T00–T12；覆盖复用矩阵 C01–C18 和补充的 U12–U16 / I14–I16 / E07。

- **完成内容：** Runtime 兼容基线、文件/reader、Node/client、真实 TLS/PG/两图主子/后台 API/Worker 链已验；三模式共享浏览器脚本含审批 commands 回执、execute 单次计数、产物 SHA256 与预览/下载。
- **验证项：** 三模式浏览器通过，恢复浏览器 1 passed（14.0s）；公网两图平台 6 组、联合链 4 组、真实两 Worktree 隔离通过；Runtime 广泛回归 1713 passed/45 skipped/29 deselected，Office 1 failed/3 errors 因 daemon 不在线，恢复后相同相关 6 passed，失败尝试保留；API 42 passed/1 skipped、Web 51 passed、终端容量 12 passed。详见 verification 的联合阶段记录。
- **后续验收：** 原 I10 正式整机重启仍需维护窗口与明确授权。真实图片生成已通过，两次编辑 unknown；用户最新批准本期通过、问题后续处理，见 F01–F04。受控供应商生成/编辑仅证明沙箱适配，不能替代真实编辑成功。
- **追加真实图片验收（2026-10-13）：** 旧供应商只读预检 HTTP 512“订单状态异常”，未重提旧 unknown。用户授权使用 `.my_best/.env` 图片三键，wawapii 模型预检通过；真实生成 `succeeded / attempts=1`，1024×1024 PNG、563829 字节，sshmy2 原文件/认证图片下载/workspace 下载 hash 一致，fork 原图也一致。只读复查蓝圆白底内容通过；[完整证据](evidence/public-media-real-provider.json)。
- **验收发现（2026-10-13）：** 用户授权使用 `.my_best/.env` 图片三键，新供应商模型预检通过、真实生成 `succeeded / attempts=1`；图片工具只读取可能为空的 `execution_info.run_id`，把来源 Run 写成字符串 `None`。先加回归并改读受信 Worker metadata，再沿原任务/原图执行剩余编辑，不重购生成、不改写历史回执。
- **编辑补验结果（2026-10-13）：** 用户授权的第二次独立编辑已执行一次，任务 `27218251-519e-465d-aae2-8a9d58b22bf2` 仍为 `unknown / attempts=1`，Run 正常报告结果未知，来源正确；首次 unknown 保留。私有响应留存 graph 被 local-stack exports 覆盖，未在真实 Worker 生效，也未留存原响应；AI 漏做有效配置检查已披露并补上购买前 guard，离线自检通过。原 Thread 残留 interrupt 使首次排队尝试无法执行，Stop 后通过既有 Platform fork 从生成完成 checkpoint 验收，未改写历史或修复引擎残留状态。
- **排查与暂缓（2026-10-13）：** 用户没有结果查询方式并决定暂缓编辑成功补验，不再付费请求。正确 origin 的 `/v1/usage` 200/Key 有效、批量历史为空，管理入口需另行登录，未发现可恢复同步编辑图片的查询；用量汇总不能确认单次扣费。旧域名白名单是待核实方向，没有原 URL 不能确定下载根因。SDK mock transport 的生成/单图/参考图请求与 MIME/字节检查通过，真实供应商调用 0。
- **修复与最小复验：** 回执来源/下载 unknown 修复和 `test_p5_media.py` 显式隔离 DSN 门禁已完成；独占回归库 [65 passed / 3 skipped](evidence/media-provider-closeout-regression.xml)，Ruff 五文件 check/format 通过。曾直接跑测试回退主开发库随机 schema，属隔离违规，已披露、移除默认 DSN 后在独占库重验；跳过不算成功。local 配置恢复、三条任务与两个远端目录保留。

### T14：安全、性能、故障与回退验证

- [x] **状态：本期验收完成，2026-10-13；安全/公网 2 槽混合负载/公开 API 性能/Node 进程恢复/证书轮换/应用回退已验；I10 整机部分按用户决定 deferred。**
- **工作：** 执行 S01–S08 / P01–P04 / R01–R04 矩阵；容量 / 低磁盘、mTLS / token / 跨域 / 路径 / 秘密、并发 / 取消 / 进程关闭、重启 / 响应丢失 / 清理未决、旧应用保留 migration head 回退。故障注入只影响项目专属资源，不关停共享 Docker daemon。
- **验收：** 所有权限与数据保护测试通过；没有副作用重放、旧工作区变空或越权清理；实测记录公网开销与节点容量，不用失败请求低延迟冒充性能。
- **依赖：** T13。

- **完成内容：** S02/S03/S05–S08 与 R01/R02/R04 已有锁定契约或真实环境证据；TLS/IP、容量、10 MiB/混合 readiness、证书轮换/崩溃/应用回退阶段通过。新增存量安全检查 10 passed，sshmy2 更新后 smoke 全过。
- **验证项：** local/remote 各 36 次成功公开读/预览/目录，remote p95 566.42/441.31/381.28ms；准确 10 MiB remote 上传 0.879s/下载 23.225s，local 0.412s/0.392s，hash 一致；2 PTY + 16 read 成功、第三 PTY 429、双回收 654.12ms，资源与 12 readiness 观测保存。
- **后续验收：** 正式获授权整机重启（F01）。先前未获授权重启的技术恢复结果单列，不计 I10；API/Worker 已排空并恢复原 local/后台关闭，远端旧 Thread 留原绑定。

### T15：Final 与文档收口

- [x] **状态：本期用户验收与文档收口完成，2026-10-13；许可、经验、配置恢复与可执行门禁已收口，B01/B02 已解除；原整机重启后的独立 Final 未执行、转后续 F01。**
- **工作：** 使用 `verify-change` 留存本期用户验收与四态判定，逐项核验 C01–C18；原整机重启后的独立 Final deferred。更新对应 Runtime / Worktree 生效标准、部署手册、FEATURES、CONTEXT；核验迁入来源 / 完整 MIT 随 wheel / 镜像分发；feat / fix / perf 用户可见变更进入 CHANGELOG。实现记录由 `implement-feature` 持续写入。
- **验收：** 全部 Task 逐项复核；没有可以继续完成的未结任务才可作完成汇报；治理方案的批准记录与服务器变更授权齐备。
- **收尾：** 2026-10-13 用户批准沉淀，两条经验已写入 `docs/lessons/runtime-service.md` 并更新索引；最新用户授权专项 Git 交付与精确清理，本 Worktree 五服务已停止。
- **依赖：** T13、T14；G06 明确批准剩余问题转后续，按 follow-ups.md 留存范围与继续处理条件。

- **完成内容：** Runtime/Worktree 规范、部署/env/systemd、来源/许可、运行手册、FEATURES/CONTEXT/CHANGELOG、C01–C18 与逐项 U/I/E/S/P/R 状态已同步；全部变更 Markdown/链接/标题/表格核查无新增错误，计数与既有文档问题见 [document-check.json](evidence/document-check.json)；真实秘密不入 Git，用户批准记录保留。
- **验收调整：** 先前维护门禁保留在历史记录；最新 G06 将正式 I10 整机部分/后续独立 Final 和媒体排查转后续，批准本期 done。没有重启授权，也未补造独立全矩阵测试通过；证据许可/源 hash/忽略与脱敏、local 恢复已核验。
- **授权事件：** 异步提问工具 accepted=true 曾被误当成授权，真实答复前误重启 sshmy2；已向用户承认并道歉。verify-os 技术证据明确 counts_as_formal_acceptance=false；没有事前授权，不补造批准，不再次整机重启。

## 进度追踪

- [x] 初版规划 P01–P03 和 deer-flow 评估 P04 完成（2026-10-12）。
- [x] 修订文档与检查 P05 完成（2026-10-12）。
- [x] G00：2026-10-12 用户批准完整修订方案与实施；G02–G05 不重复询问。
- [x] Phase 1：T00–T04 完成，直接复用模块与调用方已接入，持久绑定与旧应用回退已验。
- [x] Phase 2：T05–T09 完整能力接线完成（2026-10-13；公网联合验收另归 Phase 4）。
- [x] Phase 3：T10–T12 回收 / 恢复与公网部署完成；B01 已解除。
- [x] Phase 4：三模式/两图公网/恢复浏览器/安全/性能/应用回退已验且 local 已恢复；2026-10-13 用户本期验收通过，原 I10 整机部分与后续独立 Final 转 deferred。

当前状态：已完成 / done（用户验收本期需求）。T00–T15 本期交付/验收收口，B01/B02 已解除；用户批准剩余问题后续处理。wawapii 生图 done，两次编辑 unknown 回执保全；正式 I10 整机部分与后续独立 Final 未执行，F01–F04 deferred。既有 Phase 证据保持原事实，不改写为一次全矩阵全绿。

> 本文件代码路径除完整写出的 `scripts/`、`deploy/` 和 `apps/` 路径外，均相对 `apps/runtime-service/src/runtime_service/`；Node 新文件按 T03 固化，新增测试名称由实现确定，本文不冒充现存测试。
