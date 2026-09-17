# Terminal 后端（第二阶段）

## 目标与实施授权

用户已明确要求开始 Terminal，完成非前端开发项；沿用已有 local/Docker 边界。前端只更新 05 接入文档。

## 方案

- 真实 POSIX PTY，固定 `/bin/sh`，支持交互输入、Ctrl-C、窗口调整；不接受客户端指定宿主目录、环境或执行程序。
- 平台普通鉴权 HTTP → Runtime terminal 专用 delegation。create/list/read/input/resize/close 六类操作；输出按字节 offset 拉取、有界环形缓冲、断线重连不重建 shell。HTTP 轮询避免额外 WebSocket token 和反向代理协议。
- 所有终端操作要求项目写权限；Runtime 还校验 runtime.tool.execute 和 execute 工具许可。会话绑定 tenant/project/thread/graph/user。直接人工输入不走 Agent HITL，创建必须显式确认 direct execution；不作为 Agent 工具暴露。
- Showcase 随 local-stack 配置选择 local 或 Docker；DearFlow 保持 Docker 及 work 可写、其余挂载只读规则。local 是开发便利，不是 OS 安全沙箱。
- 默认独立 Runtime 关闭终端，local-stack 默认启用；`RUNTIME_TERMINAL_ENABLED=0` 可关闭。单 Runtime 进程会话所有权，生产须粘性路由；跨实例/重启返回明确丢失错误，不伪造持久恢复。
- 每用户线程最多 4 个会话，单进程最多 32 个；每会话输出最多 1 MiB，读取块最多 64 KiB，输入最多 4 KiB；15 分钟无交互自动关闭，绝对时长 1 小时，退出状态保留 5 分钟。轮询不延长交互空闲期。
- Runtime 正常关闭时清理进程组和容器；Docker 内部 timeout 为 Runtime 异常退出提供绝对时长兜底。输入带序号、创建带 request_id，避免网络重试重复执行。

## 代码落点

- Runtime 新增 `workspace/terminal.py`（会话/配额/缓冲/清理）、`workspace/terminal_child.py`（PTY 控制终端启动）、`http/terminal.py`（协议模型/权限）；webapp 注册及 shutdown 清理。
- `workspace/execution.py` 提取现有 Docker 安全参数供命令执行和终端共用；不改现有命令语义。
- Runtime auth、platform tokens 增加 `terminal-read/terminal-write` scope；capabilities 声明。
- Platform 网关 service/ports/upstream/http 代理，复用项目/thread/catalog 权限和审计上下文。
- `scripts/local-stack.sh` 添加终端开关；`05-frontend-handoff.md` 写明轮询、偏移、输入重试、错误及多面板接入。

## 任务与验证

- [x] Runtime local/Docker PTY、生命周期与有界资源。
- [x] 两端 scope/写权限及网关路由。
- [x] 真 PTY 交互、Ctrl-C、resize、重连、幂等、跨用户/线程拒绝、过期/退出清理。
- [x] 两服务 HTTP 联调与原有文件链路回归。
- [x] 更新前端交接与实际验证证据。

## 验证要求与记录（2026-09-17）

- Runtime 集中测试 **33 passed**：真实 local/Docker PTY、Ctrl-C、窗口尺寸、输入去重与冲突、有界输出、前台 sleep 清理、空闲/绝对期限、关闭开关、跨用户/线程、execute 权限/工具许可、native Graph scope 拒绝、参数边界及原 Showcase backend/auth 回归。
- DearFlow 使用 `python:3.13-slim` 覆盖镜像测试同一 Docker 参数：work 可写，workspace 根与 skills 不可写；未改生产镜像选择规则。
- Platform 网关回归 **49 tests OK**：含六类 Terminal 路由授权矩阵、真实两服务 TCP/HTTP 创建/输入/轮询/重放/resize/关闭及 Runtime 重启旧 ID 409；原文件和 artifact 链路同时通过。
- 审计 **7 tests OK**，含六类 terminal 动作及输出正文不进入审计 metadata；local-stack 开关与 backend 默认/覆盖 **2 tests OK**。
- 新 Terminal Python 文件完整 Ruff、改动 Python 基础 E4/E7/E9/F、Shell 语法及 diff whitespace 检查通过。
- 测试发现并修复：Docker resize 只更新宿主 PTY 不够，增加容器内 stty 同步；关闭 Shell 必须清理独立前台进程组；PTY reader 与 close 的 fd 竞争需要在锁内读取。测试本身修正了命令回显被误认为完成、PTY 尚未 ready 时 pgrp=0 的判断。

测试命令与边界统一见 [verification.md](verification.md#terminal-第二阶段验证2026-09-17)。没有数据库迁移；开关 0 拒绝终端调用并关闭现有会话的行为已测试。未开展生产压测或多副本部署，进程配额不是生产容量结论。

## 实施限制与交接

会话和输出仅在 Runtime 进程内；多进程/多副本需要粘性路由，实例丢失必须由用户明确新建，不自动重放输入。local 是宿主开发模式，不隔离任意路径、网络或主动脱离终端的后台进程；Docker 提供容器边界与异常退出时长上限。人工 Terminal 不属于 Agent tool，不能宣称经过原 Agent HITL。没有命令全文审计或持久终端录像。

代码文件与函数见 [implementation/03-terminal-backend.md](implementation/03-terminal-backend.md)，前端新增 Vue/composable/service 文件、六类接口及验收清单已写入 [05](05-frontend-handoff.md)。

## 状态

Terminal 非前端开发及本阶段验证 **done**；前端实现与完整浏览器终端交互验收 **deferred**（用户明确要求最后开发）。生产压测/多副本验收 **deferred**，不能据本地验收宣称已完成生产部署。
