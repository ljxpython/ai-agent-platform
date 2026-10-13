# 节点与位置绑定实施记录

## 时间与范围

2026-10-12 开始，2026-10-13 持续实施。用户已批准 G00/G01 和全部 T00–T15；本记录是实现细节，进度与验收以 tasks.md / verification.md 为准。

## 当前改动

- `apps/runtime-service/src/runtime_service/workspace/target.py` / `node_client.py`：可信远端句柄、HTTPS / CA / SAN / 客户端证书校验、无环境代理和重定向，连接随请求关闭；副作用丢响应后仅按原 ID 查询，绝不重新提交。
- `apps/runtime-service/src/runtime_service/sandbox_node/`：独立 Node 启动，原生 mTLS HTTP 协议注入已验证客户端证书；caller CN / token SHA256 / 执行域 / 来源 IP 同时校验；SQLite 操作登记与资源预留先于副作用。
- `apps/runtime-service/src/runtime_service/db/migrations/versions/0006_workspace_locations.py` / `workspace/locations.py`：新增位置表与后台 node_id；保留旧本地目录，首次原子绑定，配置冲突与 tombstone 拒绝。
- `workspace/remote_backend.py` 和两图组合根：远端完整 DeepAgents 文件结果，文件、技能快照、reader、图片、产物和后台共用远端身份；普通 local / Docker 分支保留。
- `workspace/terminal.py` / `sandbox_node/terminal.py`：复用现有 PTY 回放、输入序号、resize 和 expiry，仅 Node 分支传本机 Unix socket 与安全 env。
- `workspace/background.py` / `sandbox_node/background.py`：复用已批准 runner 和签名回执；历史 row 持有 node_id，Runtime 持久快照后明确 ack，节点才删除证据容器。
- `scripts/local-stack.sh` / `local_stack_worktree.py`：初始化仍 local，取消强制覆盖所属 env 的 backend；原数据库、Redis、执行域和目录登记约束保留。

## 复用与安全边界

`acquire_serialization.py` / `path_patterns.py` 从固定 deer-flow commit 原样复制，MIT / SHA256 随包分发；锁用于节点文件/资源转换，输出路径投影用于节点执行结果。契约测试适配本项目 import 与 ContextVar；没有 deerflow 运行依赖，没有复制其身份算法、宿主 env 继承、软容量池或完整 Harness。

之前文件入口只接受本机 Path；现在 `RemoteWorkspace` 明确不是 Path，调用方通过受限 Node 操作读取；Node 不接受任意宿主挂载、Docker 参数或镜像。位置表不随 env 切换覆盖，避免同 Thread 读到新空目录。

## 阶段验证

- 独立 Worktree deps 已安装，模块归属当前目录；PG / Redis 使用本机原生独立资源。
- 初始兼容基线：79 passed / 4 skipped / 3 failed；失败均为当时本机 Docker daemon 未启动，已启动本机 Docker，待真实重跑。
- 新节点 / 并发 / 路径测试首轮：30 passed；文件原子替换后的临时清理缺陷已修复并覆盖。
- 后台兼容回归：18 passed。原 mock DATABASE_URI 是占位字符串，fixture 现在明确隔离位置仓储，真实绑定另作 PG 验证。
- 实施进行中，尚未据此声明部署或 Final 完成。
