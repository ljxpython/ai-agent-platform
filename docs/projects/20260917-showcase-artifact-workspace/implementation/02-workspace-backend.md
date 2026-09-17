# 文件工作区后端实现

## 范围与决策

2026-09-17，按用户已批准方案实施第一阶段后端；前端功能不修改，Terminal 仍为第二阶段。复用线程工作区映射、签名 delegation、现有文件 transport；不新增数据库或依赖。

## 代码改动

- Runtime 新增 `workspace/browser.py`（WorkspaceBrowser）、`workspace/schemas.py`、`http/workspace.py`；webapp 注册路由。目录采用描述符枚举、O_NOFOLLOW 读取及普通文件检查，拒绝越界/符号链接/特殊文件，限制目录条目、分页和读取大小。
- `workspace/artifact_refs.py` 统一格式、预览策略及列表；保留 sha256.ext 不可变引用，读取再次校验内容；普通文件与产物分开，未知二进制只下载。
- `workspace/media.py` 补充 JPEG 后缀、图片真实格式匹配；`file_refs.py` 恢复上传独立白名单，artifact 扩展不改变上传许可。
- 公共 `tools/artifacts.py` 由 DearFlow 和 Showcase 共用；旧 DearFlow 工具模块兼容导出。Showcase agent 增加工具、runtime.tool.write 权限和审批，prompts 明确发布流程；子 Agent 返回路径，由主 Agent 发布。
- `services/dearflow_agent/capabilities.py` 从发布表派生 MIME，为两个 Agent 声明 workspace/artifacts 能力。
- 平台 `runtime_gateway` 的 HTTP/Service/Ports、`runtime_gateway_upstream.py` 和 `runtime_client.py` 新增四条接口、thread/project/target 校验及 MIME 运输支持。用一个受限 `thread_workspace` Service 方法复用鉴权，Ports 分 JSON 和文件两种返回；没有四套重复 scope 代码。
- HTML 独立新增 `workspace/html_preview.py`：标准库 HTMLParser 白名单 + CSP + 无权限 iframe。与方案初版 allow-scripts 不同，实际仅提供静态安全 HTML；原因是任意脚本可自导航，不能满足禁止外发的要求。原始 HTML 下载不变。
- `05-frontend-handoff.md` 记录已实现契约、响应示例、限制、错误及前端职责。

## 验证位置

- Runtime：`tests/test_workspace_browser.py`、`tests/test_workspace_http.py`、Showcase `test_agent.py` 新增批准/拒绝/恢复测试，复用 DearFlow 文件测试。
- 平台：`tests/test_runtime_gateway_workspace.py` 包含 scope 测试及两个 loopback HTTP 服务真实通信；SDK MIME 测试、公共路由权限矩阵扩展。
- `scripts/workspace_preview_security.mjs` 调用真实后端净化函数，再用 Chromium/Firefox 检查静态渲染、父页面隔离、导航/脚本/网络限制。不是前端页面实现。

具体执行结果见 [验证记录](../verification.md)。
