# P2 模式与交互基础

## 改动时间
2026-09-14

## 改动文件

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/modes.py`
- `apps/runtime-service/src/runtime_service/runtime/capabilities.py`

## 具体改动

新增四种模式的单一契约：Flash 关闭规划，Standard 为默认基础模式，Pro 开启规划，Ultra 开启规划和委派并提高推理强度。能力查询现在返回 Dear Agent 支持的模式列表。

## 状态

模式定义已完成；尚未把模式选择接入模型配置解析，避免在 P2 基础切片中绕过现有 Runtime policy。七种字段、Context v2、研究和 MCP 能力保持未完成。

## 验证

- [x] Python 编译检查通过
- [ ] 模式运行时切换测试（待接入配置解析）
