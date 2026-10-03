# Runtime 视觉识别能力升级：支持 DeepSeek 官方识图与异常透出优化

## 背景
此前图像识别分析工具（`analyze_image`）强绑定火山方舟的豆包模型配置（`DOUBAO_*`），且代码中粗暴使用 `except Exception:` 吞掉了底层供应商的真实报错，硬编码返回 `"Image analysis failed; check the Runtime vision configuration."`，导致接入点关停（`InvalidEndpoint.ClosedEndpoint`）、认证失败或配额超限时无法排查。
同时，用户希望能够使用 DeepSeek 官方模型（如 `deepseek-flash`）的视觉多模态能力替代豆包。

## 改动内容
1. **多供应商与 DeepSeek 视觉模型配置解析 (`resolve_vision_config`)**：
   - 优先级：通用 `VISION_*` > DeepSeek 官方配置 `DEEPSEEK_*`（默认选用多模态识图模型 `deepseek-flash`）> 兼容回退旧版 `DOUBAO_*`；
   - 自动获取 `DEEPSEEK_API_KEY` 与 `DEEPSEEK_URL`（默认 `https://api.deepseek.com`），无需配置豆包即可直接开箱即用。
2. **彻底消灭“盲吞异常”，透出供应商真实错误详情**：
   - 提取底层的 `error.message` / `error.code`（如 `ClosedEndpoint`、`InsufficientBalance` 等）及 HTTP 状态；
   - 智能体与控制台能直接看到具体错误原因，杜绝黑盒排查。
3. **真实环境与端到端实测验证**：
   - 结合用户本地 `~/.my_best/.env` 中的官方 `DEEPSEEK_API_KEY`，使用真实截图端到端调用验证通过，准确识别界面内容并结构化输出；
   - 新增针对 `resolve_vision_config` 优先级覆盖和错误透出的单元测试，回归测试全量通过（22 passed）。

## 涉及文件
- `apps/runtime-service/src/runtime_service/tools/images.py`
- `apps/runtime-service/.env.example`
- `apps/runtime-service/.env`
- `apps/runtime-service/tests/services/showcase_demo/test_images_chart.py`
- `docs/FEATURES.md`
