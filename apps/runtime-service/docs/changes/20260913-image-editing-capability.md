# Runtime Service 图片编辑（图生图）能力与安全拦截提示优化

## 背景
在 Showcase Demo 场景中，用户提问基于已上传的原图进行重绘或风格转换时，原先平台仅提供 `generate_image(prompt)` 文生图与 `analyze_image(image_path, question)` 视觉识别两项能力，缺少直接输入已有图片路径进行图生图（Image-to-Image / Image Editing）的专用工具。
此外，原有工具在遇到模型供应商的内容安全审核拦截（如 `content_policy_violation`）时，吞掉了具体错误细节，仅抛出笼统的 `BadRequestError, status=400`，导致 Agent 无法获知拦截原因进而自我纠错。

## 改动内容
1. **新增 `edit_image` 图生图工具 (`src/runtime_service/tools/images.py`)**：
   - 入参：`image_path: str`（工作区待编辑图片路径）、`prompt: str`（修改重绘指令）；
   - 行为：通过工作区隔离沙箱安全读取原图（支持 PNG/JPEG/WebP 格式与大小安全校验），调用 `AsyncOpenAI.images.edit(...)` 执行图像编辑，并将生成的新图片持久化至 `/workspace/generated/`；
   - 输出：返回新图片工作区路径与 `runtime_images` artifact，前端开箱即用直接展示。
2. **提取公用图片处理与增强安全策略异常信息**：
   - 提取 `_extract_and_save_image` 统一处理 base64/url 解码与下载；
   - 提取 `_handle_image_provider_error`：当捕获到 `content_policy_violation` 时，输出结构化且明确的安全审核拦截提示，指引 Agent 或用户调整提示语中的敏感词。
3. **中间件人机审批接入 (`src/runtime_service/middlewares/images.py`)**：
   - 将 `edit_image` 纳入 `ImageToolsMiddleware` 的 `interrupt_on` 机制，与 `generate_image` 同样默认等待人工审批（approve/reject），保证工作空间写入与费用可控。
4. **提示词与契约更新 (`src/runtime_service/services/demo/showcase_demo/prompts.py`)**：
   - 在 `SYSTEM_PROMPT` 中明确区分文生图（`generate_image`）、图生图（`edit_image`）与识图（`analyze_image`）三项能力的权责与审批约定。
5. **单元测试与回归套件**：
   - 在 `tests/services/showcase_demo/test_images_chart.py` 中新增 `edit_image` 的审批测试、参数校验测试及安全策略报错提示测试，全量测试全部通过。

## 涉及文件
- `apps/runtime-service/src/runtime_service/tools/images.py`
- `apps/runtime-service/src/runtime_service/middlewares/images.py`
- `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/prompts.py`
- `apps/runtime-service/tests/services/showcase_demo/test_images_chart.py`
- `docs/FEATURES.md`
