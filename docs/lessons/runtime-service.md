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
