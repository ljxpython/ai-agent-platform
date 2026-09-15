# 能力声明归属调整

## 已完成

- 将能力声明实现移动到 `apps/runtime-service/src/runtime_service/services/dearflow_agent/capabilities.py`。
- `runtime/capabilities.py` 仅保留兼容导出，现有 Web 能力接口、工具目录和工作区解析继续从原入口调用；没有复制两套实现，也不导入 Agent 组合根。
- Dear Agent 对外模式列表恢复为实际已接入的 Standard；四模式定义不代表运行时已支持四模式。

本次按用户要求整体移动，文件中既有 Showcase／Reference 分支暂保留，不表示这些能力属于 Dear Agent。后续如继续增加其他 Agent 能力，再按各服务声明归属调整公共查询。

## 验证

- 工作区隔离与 Showcase 文件回归：5 passed。
- `git diff --check` 通过。
- 当前 Runtime 虚拟环境未安装 Ruff，未执行 Ruff 检查。

前端代码未修改。
