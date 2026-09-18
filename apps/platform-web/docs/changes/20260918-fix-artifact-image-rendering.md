# 修复：产物图片渲染全链路缺陷

## 背景

`present_artifacts` 工具产物统一写入 `/workspace/outputs/` 目录后，前端各层路径白名单均未同步更新，导致合法产物图片被全链路判定为非法，用户看到裂图或完全不渲染。同时存在图片原地切块机制缺失的排版问题。

## 改了什么

### 1. `src/modules/chat/transcript.ts`

- **`WORKSPACE_IMAGE_PATH_REGEX`**：正则加入 `outputs` 目录分支，覆盖 `present_artifacts` 标准产物路径。
- **原地切块与路径下方渲染（Render Image Beneath Path）**：`splitTextByImages` 升级为对显式 Markdown 图片（`![alt](path)`）、行内反引号路径（`` `.../workspace/...` ``）和裸路径三态精准切块。对行内反引号包裹的路径，完整保留正文中的反引号代码样式（避免破坏反引号语法与段落），并紧随其后在路径下方渲染出 `<ThreadImage>` 大图卡片，提供直观的图文排版体验。
- **保护多行代码块与超链接**：`getFencedCodeAndLinkRanges` 精准排除多行围栏代码块（```` ``` ```` / `~~~`）与普通 Markdown 链接（`[text](url)`），防止脚本和超链接内的路径被误识别破坏。
- **修复 `g` flag 全局正则 `lastIndex` 污染**：在每次 `test()` 前 reset `lastIndex`，避免循环中跨调用状态累积导致随机漏匹配。
- **同步 Dear Agent 模块**：将 `modules/dear-agent/transcript.ts` 与 `modules/chat/` 完全对齐，引入 `outputs` 目录白名单、代码保护与原地切块机制，废除将图片无脑追加在消息末尾的旧逻辑。

### 2. `src/services/threads/images.service.ts`

- **`isValidImageRef` allowedPrefixes**：加入 `/workspace/outputs/`，使 `present_artifacts` 返回的 `RuntimeImageRef` 能通过校验，进入后续图片渲染流程。

### 3. 后端服务与网关（`platform-api` 与 `runtime-service`）

- **`platform-api` 网关层 `read_thread_image`**：`allowed_prefixes` 白名单补充 `/workspace/outputs/`，解决请求 outputs 产物图片时在网关直接被 400 拦截的问题。
- **`runtime-service` 工作区层 `image_refs.py` & `images.py`**：`validate_image_path`、`validate_image_ref` 与 `read_asset` 均将 `outputs` 纳入合法图片目录，对 outputs 下的 64 位 SHA256 文件名及哈希完整性进行一致性校验。

### 4. `src/modules/chat/components/ToolResult.vue`

- **`runtimeImages` computed**：在查 `tool.artifact` 之后、查字符串 output 正则扫描之前，新增对结构化 `tool.output` 的 `extractRuntimeImages` 调用。`present_artifacts` 的产物是结构化对象而非字符串，此前完全被丢弃。

### 5. `src/modules/chat/components/ChatMessageList.vue`

- **fork 按钮 disabled 逻辑**：加入 `!getForkCheckpointId(displayEntry)` 判断，无有效历史快照时按钮 disabled + tooltip 显示"暂无可用历史快照"，防止用户点击后进入无效的分页回溯流程最终报错。

## 涉及文件

- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- `apps/runtime-service/src/runtime_service/workspace/image_refs.py`
- `apps/runtime-service/src/runtime_service/tools/images.py`
- `apps/runtime-service/tests/test_scoped_and_refs.py`
- `apps/platform-web/src/modules/chat/transcript.ts`
- `apps/platform-web/src/modules/dear-agent/transcript.ts`
- `apps/platform-web/src/services/threads/images.service.ts`
- `apps/platform-web/src/modules/chat/components/ToolResult.vue`
- `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- `apps/platform-web/src/modules/chat/transcript.test.ts`
- `apps/platform-web/src/modules/dear-agent/transcript.spec.ts`
