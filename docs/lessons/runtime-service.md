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

## [坑] 旧源码回退必须先退应用迁移

- **场景：** Runtime 新增 Alembic head 后执行旧源码 drain/回退验证。
- **错误：** 直接启动旧源码，旧版本不认识新迁移 head，误把启动失败当作旧代码不兼容。
- **正确：** 先停止新 API/Worker 并完成受控 drain，再用新迁移代码 downgrade 到旧 head；保留后台回执后启动旧源码验证普通 Run。
- **日期：** 2026-10-09

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
