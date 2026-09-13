# 公共图片工具

## 目标
提供可被多个 Agent 复用的图片识别和文生图工具，并将产物安全写入当前线程 workspace。

## 方案设计
- 在 runtime-service 通用工具目录增加 `generate_image` 与 `analyze_image`。
- 使用公共图片 Middleware 挂载工具，Agent 只声明启用；workspace 通过绑定资源传入，公共实现不依赖 showcase_demo 模块。
- 文生图使用 GPT Image；图片识别使用兼容 `ChatOpenAI` 的豆包模型。
- 工具只接收模型需要的业务参数，不向模型暴露宿主机路径或 API key。
- 生成产物写入线程 workspace：`/workspace/generated/<id>.png`（扩展名依据实际 PNG/JPEG/WebP）。
- 文生图返回虚拟路径；识图返回分析文本且不写文件，保持只读。
- 凭据测试阶段从项目 `.env` 读取；禁止写入 Prompt、Context、checkpoint 或返回值。

## 权限与审批
- `image.generate`：runtime-service 内部固定为需要人工审批。
- `image.analyze`：只读调用，不需要人工审批。
- 上层不传递或配置这两个工具的权限。

## 任务拆分
- [x] 确认通用工具目录和现有模型/凭据加载方式。
- [x] 实现 GPT Image 生成及 workspace 落盘。
- [x] 实现豆包多模态识别及输入校验。
- [x] 接入 runtime-service 固定权限与审批策略。

## 验证要求与记录
- [x] 单元测试覆盖图片大小/格式限制、路径逃逸、符号链接和下载错误。
- [x] 集成测试确认产物落入当前线程 workspace，并返回 `/workspace/...`。
- [x] 验证文生图触发审批，拒绝无请求；图片识别不触发审批且不写文件。

2026-09-13：`test_live_image_approval_vision_and_chart_delegation` 通过（131.12 秒）。确定性主模型驱动真实 graph，批准后调用图片中转，豆包识别结果为 “The shape is a circle, and its color is blue.”，随后真实 MCP 图表落盘。
首次外部图片调用返回工具错误，未伪造产物；复测成功。首次下载域名发现仅用于测试，现已移除动态放行逻辑并写入固定本地配置。
凭据不记入本记录；原始产物保留在系统 pytest 临时 workspace（可能被后续系统清理）。

## 状态
done（Runtime 图片工具范围）
