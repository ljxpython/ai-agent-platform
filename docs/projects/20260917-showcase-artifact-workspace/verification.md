# 验证记录（2026-09-17）

## 范围与结论

第一阶段文件后端与第二阶段 Terminal 后端 **done**。前端功能与完整聊天/终端页面 E2E **deferred**，用户明确后置。未改数据库；Terminal 复用原 local/Docker 模式，第二阶段增加 PTY 能力和开关。

## 已执行证据

- Runtime 集中回归：123 passed、3 skipped，新增审批用例最初因测试目录未创建失败，修正后定向复验 2 passed（批准、拒绝与内存 checkpoint 恢复）。合计该组 125 个用例通过；未将失败或 skipped 算作通过。
- 最后 Runtime 文件/HTTP/PPTX 安全定向复验：40 passed，覆盖 YAML/源码/Markdown/SVG、PNG/JPG/JPEG/WebP、PDF/XLS/XLSX/ZIP、路径穿越、符号链接及目录替换竞争、截断/超限、损坏产物、scope。
- 文档/归档用例追加合法 PPTX 发布与读取后定向复验：1 passed。
- Platform API 网关回归：49 tests OK，包含所有公开路由权限矩阵、新格式 MIME 运输、旧 files/content 兼容。
- 平台真实两服务 HTTP 用例后补 Runtime 重启验证，定向复验：2 tests OK；重启后未重新发布，列表及摘要下载保持一致。
- Chromium 与 Firefox：静态 HTML 布局保留、父页面不可读、无脚本/导航/网络请求，均 PASS。测试使用后端实际生成的安全文档，无平台前端依赖。
- 新增 Python 文件按仓库完整 Ruff 规则通过；所有改动 Python 文件的 E4/E7/E9/F 基础检查通过。现有大文件完整规则仍有历史告警（FastAPI Depends 默认参数 B008、旧 import 排序等），未做无关全文件清理。

## 可复跑命令

在 apps/runtime-service：

```bash
uv run --frozen pytest tests/test_workspace_browser.py tests/test_workspace_http.py tests/services/dearflow_agent/test_files.py tests/services/dearflow_agent/test_agent.py tests/services/showcase_demo tests/test_image_workspace_storage.py tests/test_scoped_and_refs.py -q
uv run --frozen pytest tests/services/showcase_demo/test_agent.py -k artifact_publication -q
uv run --frozen pytest tests/test_workspace_browser.py tests/test_workspace_http.py tests/services/dearflow_agent/test_files.py tests/services/dearflow_agent/test_p5_media.py::test_pptx_rejects_active_content_and_entities -q
```

在 apps/platform-api（该服务使用 unittest，venv 没有 pytest，不为此新增依赖）：

```bash
uv run --frozen python -m unittest discover -s tests -p 'test_runtime_gateway_*py' -q
uv run --frozen python -m unittest discover -s tests -p test_runtime_gateway_workspace.py -q
```

仓库根目录：

```bash
node apps/runtime-service/scripts/workspace_preview_security.mjs
```

浏览器脚本复用 platform-web 已有 Playwright 依赖；Firefox 测试浏览器本次已下载，无前端代码改动。

## 边界说明

- 两服务测试是真实 localhost TCP/HTTP、真实 Runtime 签名 token 校验及文件 IO；平台身份/catalog/thread 元数据使用固定测试夹具，并非生产登录/数据库端到端验证。真实授权拒绝另由公共路由锁定契约矩阵覆盖。
- 三个跳过项为已存在的付费在线模型/图表/图片生成 E2E，需要各自 opt-in 开关；它们不属于本次文件后端改动，未调用付费生成服务。
- 本地/Docker 原有测试随 Showcase 回归执行；此次不修改执行 backend。生产分布式挂载、配额和对象存储不属于本期。
- Runtime 进程重启后的产物持久读取已验证；Agent 恢复使用 InMemorySaver 契约测试，不宣称已验证生产 GraphHarbor/PostgreSQL checkpoint 重启。
- HTML 支持静态预览；任意脚本会被移除，外链被禁。动态脚本预览不是本次交付能力。
- 回滚为回退新路由/工具装配；无 schema 迁移、无数据重写，旧 uploads/outputs 下载兼容测试通过。已发布扩展格式需保留新白名单才能继续通过旧下载入口读取。

代码位置与交接见 [04](04-code-change-map.md)、[05](05-frontend-handoff.md)。

## Terminal 第二阶段验证（2026-09-17）

执行人：Codex。非前端开发及必要验证 **done**，前端与浏览器交互 E2E **deferred**（用户要求）；生产压测/多副本验证 **deferred**（不在本次本地交付范围）。

| 功能块 | 实际证据 |
| --- | --- |
| Runtime PTY、安全与执行后端回归 | 33 passed，79.17s；无 skip；包括真实 local/Docker、DearFlow 挂载、Ctrl-C、resize、关闭前台 sleep、TTL、输入幂等、字节重放、限额、权限与签名 scope |
| Platform 网关 | 49 tests OK，177.784s；六类终端路由进入公共授权矩阵；含真实双服务 HTTP 创建→输入→输出→重放→resize→关闭；Runtime 重启旧会话 ID 返回 409，文件仍可读取 |
| 审计 | 7 tests OK；覆盖 created/listed/output.read/input.sent/resized/closed，响应内容不写入 metadata |
| local-stack | 2 tests OK；默认启用、dotenv 设置、外部环境覆盖、非法开关；原 local/docker 选择保留 |
| 静态检查 | 新 Terminal 文件完整 Ruff；已有改动 Python E4/E7/E9/F；bash -n；git diff --check |

Runtime 中执行：

```bash
uv run --frozen pytest tests/test_terminal.py tests/test_terminal_http.py tests/runtime/test_auth.py tests/runtime/test_platform_auth.py tests/services/showcase_demo/test_backend.py -q
```

Platform API 中执行：

```bash
uv run --frozen python -m unittest discover -s tests -p 'test_runtime_gateway_*py' -q
uv run --frozen python -m unittest discover -s tests -p test_audit_http_resolution.py -q
```

仓库根目录执行：

```bash
python3 -m unittest discover -s scripts -p test_local_stack_backend.py -q
bash -n scripts/local-stack.sh
git diff --check
```

复现 Docker 用例需要可用 daemon 及已存在的 `python:3.13-slim` 镜像（运行使用 `--pull=never`）；此次实际运行通过，未把 Docker skip 算作证据。Runtime 的 5 条 Swig 弃用警告及 Platform 的 websockets 弃用/asyncio 慢任务提示是依赖/调试日志，无测试失败。

修复记录：Docker 窗口 resize 改为宿主 PTY + 容器 stty 同步；关闭时兼顾前台作业独立进程组，Shell SIGHUP 后有界等待并兜底 kill；reader 在 fd 锁内读取防止 close 竞争。测试误判（回显匹配、启动中 pgrp=0）修正后复验通过。最终集中回归基于修复后的实现。

边界：双服务测试的平台身份、catalog、thread 元数据使用固定夹具，真实 Runtime token 和 PTY；生产身份/数据库联调及浏览器 UI 尚未验证。local 无宿主 OS 隔离和 daemonized 作业回收保证；Docker 关闭通常立即清理，daemon 不可达时依赖 1h timeout 并告警。无 schema 迁移；关闭能力开关的拒绝及会话清理已验证，代码回退仍须正常停止 Runtime 以触发 shutdown。Terminal 会话不保证跨重启恢复，多 Runtime 进程必须部署粘性路由。
