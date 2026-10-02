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
