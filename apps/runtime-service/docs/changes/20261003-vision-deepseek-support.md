# Runtime 视觉识别能力升级：支持 DeepSeek 官方识图与异常透出优化

## 背景
此前图像识别分析工具（`analyze_image`）强绑定火山方舟的豆包模型配置（`DOUBAO_*`），且代码中粗暴使用 `except Exception:` 吞掉了底层供应商的真实报错，硬编码返回 `"Image analysis failed; check the Runtime vision configuration."`，导致接入点关停（`InvalidEndpoint.ClosedEndpoint`）、认证失败或配额超限时无法排查。
同时，用户希望能够使用 DeepSeek 官方模型（如 `deepseek-flash`）的视觉多模态能力替代豆包。

## 后续规则（2026-11-08 对照）

本篇保留 10-03 当日接入与 22 passed 记录，不作为供应商当前模型能力的永久保证。resolve_vision_config 仍按部署配置解析 Provider，具体模型是否支持图片需在目标连接验证；不要照抄历史私人凭据路径。10-06 后失败对外已改为稳定安全分类（如 image_analysis_unavailable），底层详情不直接回传模型或公开控制台，见 [工具容错专项](../../../../docs/projects/20261006-agent-tool-error-resilience/README.md)。

## 改动内容
1. **多供应商与 DeepSeek 视觉模型配置解析 (`resolve_vision_config`)**：
   - 优先级：通用 `VISION_*` > DeepSeek 官方配置 `DEEPSEEK_*`（默认选用多模态识图模型 `deepseek-flash`）> 兼容回退旧版 `DOUBAO_*`；
   - 自动获取 `DEEPSEEK_API_KEY` 与 `DEEPSEEK_URL`（默认 `https://api.deepseek.com`），无需配置豆包即可直接开箱即用。
2. **当时的错误详情改造（后续已收紧公开输出，见上）**：
   - 提取底层的 `error.message` / `error.code`（如 `ClosedEndpoint`、`InsufficientBalance` 等）及 HTTP 状态；
   - 智能体与控制台能直接看到具体错误原因，杜绝黑盒排查。
3. **真实环境与端到端实测验证**：
   - 结合当日经授权的私有环境配置中的 `DEEPSEEK_API_KEY`，使用真实截图端到端调用验证通过，准确识别界面内容并结构化输出；
   - 新增针对 `resolve_vision_config` 优先级覆盖和错误透出的单元测试，回归测试全量通过（22 passed）。

## 涉及文件
- `apps/runtime-service/src/runtime_service/tools/images.py`
- `apps/runtime-service/.env.example`
- `apps/runtime-service/.env`
- `apps/runtime-service/tests/services/showcase_demo/test_images_chart.py`
- `docs/FEATURES.md`
