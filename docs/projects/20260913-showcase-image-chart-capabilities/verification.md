# Showcase 图片与图表跨服务链路验证记录

## 1. 验证概述
- **日期：** 2026-09-13
- **执行人：** 老王（技术负责人）
- **验证范围：** P0 G0 契约实验、P1 Runtime 图片运输层、P2 Platform API 网关、P3 Platform Web 前端交互体验、P4 确定性自动化验证。
- **当前状态判定：** ⚠️ **部分完成（代码与确定性自动化测试全部通过，等待注入生产模型凭证进行真实环境 Smoke 验收）**

---

## 2. 自动化测试结果

### 2.1 Runtime Service
- **命令：** `pytest tests/test_image_http.py tests/test_image_workspace_storage.py tests/services/showcase_demo/test_images_chart.py`
- **结果：** 17 passed, 2 skipped in 30.29s (跳过的 2 项为真实外部 API 凭据在线调用测试)。
- **核心覆盖点：**
  - Hashed workspace thread 隔离与路径校验；
  - 5 MiB 上传大小、magic bytes、原子替换、NUL/路径穿越防御；
  - Internal PUT/GET 授权与 delegation scope 校验；
  - 豆包模型消息中间件物化（脱敏 extras，仅传递文件路径给视觉模型）；
  - `generate_image` HITL 审批返回与图表 MCP 结构化产物。

### 2.2 Platform API
- **命令：**
  - `python -m unittest tests.test_runtime_gateway_images tests.test_runtime_gateway_http_matrix`
  - `python -m unittest discover tests`
- **结果：** 全量 157 项单测全部通过（Ran 157 tests in ~11s, OK）。
- **核心覆盖点：**
  - PUT `/api/langgraph/threads/{thread_id}/images/uploads/{sha256}`：大小超限 413、哈希不匹配 400、无写权限 403、跨项目隔离；
  - GET `/api/langgraph/threads/{thread_id}/images/content`：路径穿越 400、20 MiB 累加熔断抛出 502、安全响应头白名单透传、`RuntimeStreamingResponse` 连接释放；
  - 全网关 24 个公开路由边界矩阵 100% 绿灯。

### 2.3 Platform Web
- **命令：**
  - `pnpm test:run`
  - `pnpm build`
- **结果：**
  - 单元测试：43 个测试文件，123 个用例全部 PASS（含 `images.service.spec.ts` 4 项、`transcript.test.ts` 7 项以及组件单测）；
  - 静态检查与打包：`vue-tsc --noEmit && vite build` 零 TS 错误，49s 完成生产构建打包。
- **核心覆盖点：**
  - `images.service.ts`：SHA-256 哈希计算、RuntimeImageRef 强校验、鉴权 Blob 获取；
  - `ThreadImage.vue`：Blob URL 创建与销毁生命周期、失败重试、缩放预览与本地下载；
  - `chat-content.ts` & `useChatSession.ts`：send/queue/fork 预处理拦截，图片上传后转换为纯文本块，杜绝 Base64；
  - `transcript.ts`：从 artifact、structured_content 提取图片，通过正则从历史输出中恢复图表弱引用；
  - `ApprovalPanel.vue`：文生图人机协同中文审批卡片渲染。

---

## 3. 安全矩阵核对

| 检查项 | 预期行为 | 验证状态 | 证据 / 覆盖用例 |
|---|---|---|---|
| 错租户 / 错项目 | 拒绝访问，不泄露路径与正文 | ✅ 已通过 | `test_runtime_gateway_images.py`: `test_upload_image_cross_project_rejected` |
| 路径穿越 | `..`、双编码、绝对宿主路径拒绝 | ✅ 已通过 | `test_image_http.py`, `test_runtime_gateway_images.py` |
| symlink 逃逸 | 阻断软链接指向工作区外 | ✅ 已通过 | `test_image_workspace_storage.py`: `test_symlink_defense` |
| MIME 与伪造扩展名 | 校验 magic bytes，非图片 415 | ✅ 已通过 | `test_image_http.py`: `test_upload_invalid_mime` |
| 消息防膨胀 | 消息体与数据库存储零 Base64 | ✅ 已通过 | `implementation/02-g0-contract-verification.md` 七节点穿透 |
| 内存泄漏防御 | 组件卸载/路径变更即刻 revokeObjectURL | ✅ 已通过 | `ThreadImage.vue`: `watch`, `onBeforeUnmount`, `onUnmounted` |

---

## 4. 四态判定总结

- [x] **P0：G0 消息契约实验** - 已完成（7 节点穿透无损）
- [x] **P1：Runtime 图片运输层** - 已完成（存储、HTTP、中间件、工具链全部落地）
- [x] **P2：Platform API 图片网关** - 已完成（流式代理、权限校验、熔断、矩阵测试全绿）
- [x] **P3：Platform Web 体验层** - 已完成（Blob 管理、上传排队、审批卡片、图表展示全绿）
- [ ] **P4：生产环境真实模型 Smoke 验收** - 待配置生产环境真实 API Key（豆包、GPT Image、AntV MCP）后执行最终联调

**结论：** 核心开发任务与自动化测试矩阵 100% 验收达标，状态标为 **“部分完成（代码与自动化验收已完成，待生产凭据联调）”**。
