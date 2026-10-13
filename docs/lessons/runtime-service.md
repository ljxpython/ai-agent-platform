# runtime-service 经验库

> 适用范围：apps/runtime-service 服务内部代码、工具集成、Agent Graph 与治理模块改动。
> AI 读取时机：开始处理 runtime-service 内部或跨服务改动前按需读取。

---

## [坑] 纯 Re-export 中间模块未声明 `__all__` 导致符号被静态工具误删

- **场景：** 对 Python 模块执行 `ruff check --fix` 或启用 `F401`（未使用的 import）自动清理时。
- **错误：** 在仅作为符号汇聚/桥接对外重导出的中间模块中（如 `governance_storage.py` 汇聚导出 `connect` 给子模块），没有在文件内部直接使用该符号，且未显式声明 `__all__`，导致符号被当成无用导入静默删除，引发下游所有业务模块出现 `ImportError: cannot import name ...`。
- **正确：** 凡是作为对外暴露接口或中间 re-export 的模块，必须显式定义 `__all__ = ["symbol1", "symbol2"]`（或采用 `from mod import symbol as symbol` 导出惯用法），向静态分析工具显式声明导出意图，彻底防止符号被误删。
- **日期：** 2026-09-28

---

## [坑] 工作区不可信 HTML 预览清洗与沙箱放权避坑

- **场景：** 处理用户或智能体在沙箱工作区生成单文件富页面（如 Tailwind CDN、Google Fonts、SVG 图表）的安全清洗与前端预览时。
- **错误：** 一刀切禁用 script/link 导致现代样式全毁；HTMLParser 中将自闭合标签（如 `<base>`）设为 `skip` 导致后续整个 DOM 被永久吞没；对 script/style 内容盲目调用 `html.escape` 导致 JS 逻辑运算符语法报错；或在前端错误地混合添加 `allow-same-origin` 与 `allow-scripts` 导致 XSS 逃逸。
- **正确：** 前端 iframe 仅放权 `sandbox="allow-scripts"` 且绝不加 `allow-same-origin`（强制 Origin 为 null 隔绝宿主凭据）；后端 CSP 白名单放行公认安全 CDN 并限制 `connect-src https:` 阻断内网探测；HTMLParser 中自闭合标签单点忽略不设 skip，script/style 保留原始代码不转义。
- **日期：** 2026-10-02

---

## [坑] 审批恢复必须使用当前 interrupt ID 与原执行快照

- **场景：** 验证 HITL 停止后的显式恢复，或从前端提交审批决定。
- **错误：** 使用非 ID 映射的 resume，或同时传入新 input/config/context，分别触发过期审批冲突或参数拒绝。
- **正确：** 先读取当前 state 的真实 interrupt ID，按 ID 映射提交对应 decisions；恢复复用服务端原执行快照，不附带新配置，也不自动批准。
- **日期：** 2026-10-07

---

## [坑] HTTP 200 不等于调用者已收到回执

- **场景：** Runtime 通过 Platform 回调派发后台完成 Run，网络响应在服务端已写审计后才超时。
- **错误：** 看到 Platform HTTP 200 就把 Runtime 的交付状态标为 accepted，或立刻换 key 重发。
- **正确：** 调用者超时仍按 unknown/inflight 保留原 event/key；只有本地回执、Worker guard 或引擎只读接受回查能绑定原 Run。引擎没有只读回查时禁止自动重发。
- **日期：** 2026-10-09

---

## [坑] 回退应用需保留迁移链

- **场景：** Runtime 新增 Alembic head 后执行旧源码 drain/回退验证。
- **错误：** 直接启动不认识新 head 的旧包，误把迁移链缺失当成旧应用不兼容；或把数据库 downgrade 当成应用回退的固定前置步骤。
- **正确：** 先受控 drain，再使用包含当前迁移链的回退构建，保留数据库 head、调用事实、回执及额度，验证启动和旧读取能力；只有 schema 确实不兼容且有经批准的可逆方案时才另行回退数据库，不用 stamp 绕过检查。
- **日期：** 2026-10-09；2026-10-11 修订，保留 head 启动/旧额度读取证据见[Token 看板回退记录](../projects/20261011-token-usage-dashboard/05-delivery-and-verification.md#发布与回退建议)。

---

## [坑] Docker local 日志盘占用不能依赖 `inspect.LogPath`

- **场景：** 验证 Docker local logging 的轮转和实际磁盘占用。
- **错误：** 在 macOS Docker Desktop 上直接读取 `inspect.LogPath`；该字段可能为空，导致错误结论或误报失败。
- **正确：** 读取 Docker daemon 的 `DockerRootDir`，再按受验容器 ID 定位 `containers/<id>/local-logs`，用只读诊断容器统计文件大小。
- **日期：** 2026-10-09

---

## [坑] 受管后台命令工作目录是 `/workspace/work`

- **场景：** 用 Workspace 文件作为长命令测试的同步信号。
- **错误：** 已在 `/workspace/work` 下执行命令，却再拼接 `work/<filename>`，导致信号文件永远找不到。
- **正确：** 以 runner 的实际 workdir 为准，命令直接使用文件名；新增 fixture 要显式核对容器工作目录和挂载路径。
- **日期：** 2026-10-09

---

## [坑] 同版本候选 wheel 冷安装不能证明正式包包含新能力

- **场景：** 跨仓库配套开发，源码版本号与已发布版本相同，使用本地 wheel 做冷安装验收。
- **错误：** 仅凭版本号、CLI 或候选安装通过，就认定 PyPI 同名正式包也包含新接口或迁移。
- **正确：** 分别记录来源、双包版本、产物哈希、接口与迁移 head；候选只证明候选，正式接入须发布唯一新版本并从正式源独立安装复验。
- **日期：** 2026-10-07

---

## [坑] 异步 callback 异常不能替代同步派发阻断

- **场景：** 在 Runtime 预算、费用或安全策略中，试图通过异步 callback 的 `raise_error` 阻止同步模型请求。
- **错误：** LangChain Core 同步桥接可能吞掉异步 callback 协程异常，模型请求已经发出而策略看似“已拒绝”。
- **正确：** 在真实 compiled graph/Worker 中验证 provider 请求计数；同步入口挂同一事实源的同步派发守卫，异步路径避免未 await 协程，并单独保留 Usage callback 做唯一采集。
- **日期：** 2026-10-09

---

## [坑] 隐藏模型工具仍须保留旧回执入口

- **场景：** 环境或能力门禁降级（如 local 非 Docker 环境关停后台任务启动能力 `tasks.start=false`），模型侧动态隐藏 `background_execute` 等工具。
- **错误：** 一刀切把后台任务相关的数据结构、查询接口或前端入口全部注销，导致历史上曾由 Docker 环境产生的后台任务无法查看状态、取消或追溯回执。
- **正确：** 严格解耦启动权限与查询权限（`tasks.start` vs `tasks.query`）；关闭启动能力仅隐藏面向 LLM 的工具声明与新建入口，必须保留只读查询能力、旧回执渲染以及针对已有任务的取消操作。
- **日期：** 2026-10-10

---

## [坑] 错误码不足以证明未启动

- **场景：** 异步后台任务分发或执行链路中发生网络抖动、瞬态异常或超时。
- **错误：** 仅凭下游返回错误响应或网络超时，就盲目推断任务“根本未启动”并直接发起重试，导致后台耗时命令重复启动、破坏幂等性甚至污染工作区。
- **正确：** 只有明确收到服务端可信的“前置拒绝”（如参数校验失败、门禁拒绝）且无任何副作用时才能判定未启动；对于网络超时、中断或未知结果（`unknown`），绝不提示自动重试，前端与系统必须保留原状态并给出精确降级提示。
- **日期：** 2026-10-10

---

## [坑] 聚合接口不等于数据库负载隔离

- **场景：** 新增跨项目 Token 聚合接口，报表读取与调用事实采集共用 Runtime PostgreSQL。
- **错误：** 将只读 API、独立线程池、连接或索引当成 CPU/I/O 隔离；把超时返回的 p95 当作报表完成性能。
- **正确：** 同时验证查询可用性、读并发和采集写入影响；原始 ledger 聚合超标时先减少重复扫描，再评估可重建派生读模型或独立查询实例。同实例的派生表/另一数据库只减少或调整负载，是否满足写入门槛仍须实测。
- **日期：** 2026-10-11；证据与测量边界见[Token 看板 B01](../projects/20261011-token-usage-dashboard/05-delivery-and-verification.md#b01-容量阻塞与追加评审方案)。

---

## [坑] 性能验收需覆盖平台完整链路

- **场景：** 跨服务分析报表或高负载查询进行容量验收与性能摸底。
- **错误：** 仅在底层单独运行 SQL 探测或仅打压 Runtime 内部接口，忽略上游 Platform API 的 JWT 鉴权校验、Thread ACL 过滤、并发控制槽分配、序列化以及网络开销，误把底层单点耗时当成系统端到端时延。
- **正确：** 性能压测必须从面向客户端的最外层公开接口发起，携带真实鉴权凭据与并发流量，覆盖网关鉴权、全流程并发预算控制、下游引擎执行与 DTO 校验全链路，以最终公开接口表现判定是否达标。
- **日期：** 2026-10-12；证据见[Token 看板实施记录](../projects/20261011-token-usage-dashboard/implementation/02-b01-optimization.md)。

---

## [坑] 远端 Docker 不能只改 DOCKER_HOST

- **场景：** Runtime 与 Docker daemon 分属不同宿主机，保留本地开发并接入远端沙箱。
- **错误：** 仅替换 DOCKER_HOST，继续用 Runtime 本机 Path 读写文件；bind mount 的源路径实际属于 daemon 宿主机，导致附件、技能、产物或恢复链路失效。
- **正确：** 将执行和文件操作统一路由到持久绑定的 Sandbox Node，Node 使用本机 socket 与本机 Workspace；unknown 只回查原操作 ID，禁止换节点或回退重放。
- **日期：** 2026-10-13；用户批准沉淀，设计与验证见[远端沙箱专项](../projects/20261012-runtime-remote-docker-sandbox/README.md)。

---

## [坑] 容器与数据必须分开回收

- **场景：** 用户结束运行、空闲容器退场，之后重开同一 Thread 恢复文件。
- **错误：** 将删除容器等同于删除 Workspace，或在恢复时自动创建空目录掩盖原数据缺失。
- **正确：** 容器按租约与任务状态回收，Workspace 独立保留；retained、unknown、未确认日志或回执保护数据，精确清理须核对归属与未决资源；恢复只挂载已存在目录，旧 PTY 进程内存不恢复。
- **日期：** 2026-10-13；用户批准沉淀，生命周期与恢复证据见[远端沙箱专项](../projects/20261012-runtime-remote-docker-sandbox/verification.md)。

---

## [坑] 序号分配顺序不等于事务提交顺序

- **场景：** 数据库使用自增序列维护脏数据标记或操作版本日志，后台异步任务批量消费并清理低水位记录。
- **错误：** 误以为低版本号必然早于高版本号提交，在清理时直接按当前处理的最大版本执行 `DELETE WHERE version <= max_processed_version`，导致高版本已提交而低版本长事务尚未提交时，晚提交的低版本被直接误清或遗漏处理，造成数据坏死。
- **正确：** 脏记录清理必须严格遵循同快照水位，只能清理“当前快照可见且不高于任务处理水位”的脏记录；晚提交的低版本提交后依然保留在表中，由后续调度轮次安全补齐。
- **日期：** 2026-10-12；证据见[Token 看板实施记录](../projects/20261011-token-usage-dashboard/implementation/02-b01-optimization.md)。
