# GraphHarbor post27 发布与 Runtime 接入

日期：2026-09-11。用户明确批准 GraphHarbor 发布。

## 发布结果

- `graphharbor==0.13.0.post27`、`graphharbor-runtime==0.13.0.post27` 已发布到正式 PyPI，四份 wheel/sdist 的 SHA-256 均与本地一致。
- 发布包含官方框架 SDK 流协议、完整 state schema 和 Run 并发/幂等目标校验修复。未加入平台队列表、平台鉴权或其他业务代码。
- 按用户提供的凭据位置进行 token 上传，没有在命令参数、日志或文档记录密钥；未执行 git commit/push/tag，也未创建 GitHub Release。
- GraphHarbor 发布记录（相对本仓库根）：`../graphharbor/docs/release-notes-0.13.0.post27.md`。

## 接入改动

- `apps/runtime-service/pyproject.toml`：将 GraphHarbor 固定为 `0.13.0.post27`。
- `apps/runtime-service/uv.lock`：同步两包的版本、PyPI 下载地址与哈希，其余生态依赖保持原锁定版本。
- 执行 `uv sync --frozen --reinstall-package graphharbor --reinstall-package graphharbor-runtime`，确认两个安装分发均不存在 `direct_url.json`，排除本地 wheel 或 editable 覆盖。

## 验证

- GraphHarbor：`uv lock --check`、版本检查、Ruff format/check、mypy（36 源文件）、四产物 Twine 检查通过。
- 全库测试：**150 passed、18 skipped**（Python 3.11，97.36 秒），专用 PostgreSQL `graphharbor_release_post27`；外部对照/模型场景跳过不计入通过。
- 发布前 wheel：五个网络浏览器场景 **5 passed**（2.9 分钟），日志 `/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-bh3jd7qz`。
- 发布后 PyPI 安装：**5 passed（2.5 分钟）**，无源码覆盖。日志 `/var/folders/q6/4nvs05t90rg041hyp3_kws640000gn/T/q5-message-_qj7z0v1`。Runtime 锁文件检查、文档检查及两个仓库 diff 空白检查通过。
- 四态：本次发布与 Runtime 依赖接入 **done**；源码版到发布包的阻塞已解除。

复跑：`Q5_DATABASE_URI=<专用测试PG库> apps/runtime-service/.venv/bin/python apps/runtime-service/scripts/q5_message_acceptance.py`，不设置 `Q5_GRAPHHARBOR_SOURCE`。

本次发布不等于生产服务已经部署；既有服务进程未主动重启。双浏览器并发继续按用户决定 deferred，全项目 G6/Q5 其他未覆盖门禁不自动转为 done。
