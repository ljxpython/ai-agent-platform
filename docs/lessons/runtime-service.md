# runtime-service 经验库

> 适用范围：apps/runtime-service 服务内部代码、工具集成、Agent Graph 与治理模块改动。
> AI 读取时机：开始处理 runtime-service 内部或跨服务改动前按需读取。

---

## [坑] 纯 Re-export 中间模块未声明 `__all__` 导致符号被静态工具误删

- **场景：** 对 Python 模块执行 `ruff check --fix` 或启用 `F401`（未使用的 import）自动清理时。
- **错误：** 在仅作为符号汇聚/桥接对外重导出的中间模块中（如 `governance_storage.py` 汇聚导出 `connect` 给子模块），没有在文件内部直接使用该符号，且未显式声明 `__all__`，导致符号被当成无用导入静默删除，引发下游所有业务模块出现 `ImportError: cannot import name ...`。
- **正确：** 凡是作为对外暴露接口或中间 re-export 的模块，必须显式定义 `__all__ = ["symbol1", "symbol2"]`（或采用 `from mod import symbol as symbol` 导出惯用法），向静态分析工具显式声明导出意图，彻底防止符号被误删。
- **日期：** 2026-09-28
