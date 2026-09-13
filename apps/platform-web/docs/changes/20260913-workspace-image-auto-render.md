# 前端对话正文与工具卡片工作区图片自动解析与渲染

## 背景与诉求
1. **纯文本路径体验割裂**：
   在智能体执行文生图（`generate_image`）、图像编辑/图生图（`edit_image`）或图表绘制工具后，往往在最终回复正文中输出 `成品路径：/workspace/generated/xxxx.png`。此前前端正文解析器未将生图路径转为图片块，导致用户在聊天气泡中只看到冰冷的文本路径，无法直观查看画面内容。
2. **工具卡片产物感知薄弱**：
   工具调用结果卡片（`ToolResult.vue`）在底层未显式携带特定 `artifact` 数据结构时，仅展示原始 JSON 字符串或文本，且英文工具名对普通用户不够友好。

## 变更内容
1. **通用工作区图片提取与自动渲染 (`transcript.ts`)**：
   - 将工作区正则拓展为覆盖所有核心目录与常见格式：`WORKSPACE_IMAGE_PATH_REGEX = /\/workspace\/(?:charts|generated|uploads)\/[a-zA-Z0-9_-]+\.(?:png|jpg|jpeg|webp)/gi`。
   - 实现 `extractWorkspaceImageRefs` 并向下兼容原有 `extractChartWeakImageRefs`。
   - 在流式正文分块合并（`consolidated`）的后置处理中，自动扫描文本引用的工作区图片路径，去重派生 `kind: 'image', imageRef` 块，直接复用 `<ThreadImage>` 组件原生渲染大图、支持点击放大查看和下载。
2. **工具卡片产物感知与中文化增强 (`ToolResult.vue`)**：
   - 为生图、修图、视觉分析等工具建立友好中文别名映射（如“文生图”、“图像编辑/图生图”、“图像识别分析”）。
   - 在工具结果卡片折叠态副标题中显式透出生成图片路径；同时在 `runtimeImages` 中引入文本回退提取，使工具卡片内部也能内联展示预览图。
3. **提示词协同微调 (`prompts.py`)**：
   - 在 Showcase Demo 系统的 `SYSTEM_PROMPT` 中明确规范：出图后简要描述画面并给出完整 `/workspace/...` 路径，前后端链路闭环。
4. **测试与质量验证**：
   - 前端单元测试 `transcript.test.ts`、`ToolResult.spec.ts` 全量通过。
   - 前端静态类型检查与构建（`vue-tsc --noEmit && vite build`）832 个模块 0 错误编译通过。
   - 后端 Runtime 图片单元测试 `test_images_chart.py` 15 项全绿。

## 涉及文件
- [MODIFY] `apps/platform-web/src/modules/chat/transcript.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/transcript.test.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/components/ToolResult.vue`
- [MODIFY] `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/prompts.py`
