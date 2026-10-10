# Worktree 配置与主库基础数据复用

2026-10-10，对应追加 T05-T07。用户要求默认本地账号、复用各 app 环境配置和基础数据；进度以 tasks.md 为准。

## 改动

- `scripts/local_stack_worktree.py`：`initialize()` 继承主 Runtime/API `.env`，Web `.env` / `.env.local` 的副本进入私有 `web.env`；隔离字段覆盖基线，新管理员设为 admin/admin123，JWT/委托/PG/Redis/模型 master key 仍独立，历史 JWT verification keys 清为空集合。`export_environment()` 仅注入 Web 的 VITE_*，验证代理与端口归属，旧环境没有 web.env 时沿用受管地址。
- `scripts/local_stack_seed.py`：`seed_environment()` 核对登记和两目标库归属/完成状态；`copy_database()` 加目标事务锁与空库保护，源库在只读 repeatable-read 事务中以二进制 COPY 按白名单复制，保留 SQL NULL/JSON/UUID/时间戳。每库完成标记与数据一起提交。
- `prepare_platform()` 复用现有密码与模型凭据 helper，只在目标设初始管理员，重新加密模型 Key 并重映射目录 Runtime 地址。没有凭据 dump 或明文日志。
- `scripts/local-stack.sh`：新增 `seed` 入口；Worktree `start` 在 migrate 之后执行 `seed --if-empty`，旧非空环境保留数据，显式导入拒绝覆盖；主目录 start 不执行 seed。
- `scripts/test_local_stack_seed.py`：真实 PG 的关系/重加密/历史排除/幂等、坏密钥回滚、非空与错误归属/远端连接覆盖拒绝、结构差异回滚，以及部分成功后的重试和源库缺少 admin 时补建。`scripts/test_local_stack_worktree.py` 补充默认账号与 Web 配置继承。
- `scripts/verify_worktree_local_stack.py`：复制新 helper，检查三栈真实基础数据完成标记、默认账号、目标模型 Key 解密及源历史未复制，继续验证登录/目录/真实 Worker/Workspace/停止/重启。
- Worktree 规范、README、开发/环境指南和部署契约同步默认账号、配置继承、白名单及一次导入规则；37 条存量绝对路径按用户要求后置。

## 取舍

只复制可复用配置：Platform 15 张表，Runtime assistants/assistant_versions/dear_skills；新表默认不复制。排除所有会话执行数据、长期记忆、令牌、审计、定时任务、Redis/Workspace。两库各自取得开发配置快照，目标有完成标记后保留本环境修改，不提供自动清空/增量同步。

第一次夹具遗漏必填 slug/写错策略关联列，第二次清理受 PG 连接退出延迟影响；已按当前模型修正并等待测试连接消失，精确回收临时资源。新增 5 项真实 PG 与完整 24 项 local-stack 回归通过，连接覆盖/JWT 调整直接相关测试补验通过。

收尾按仓库根 Ruff 配置移除新增测试的冗余 noqa，并将未使用的夹具解包变量标为下划线前缀；相关脚本 lint/format 及 5 项真实 PG 重跑通过。旧脚本 6 条既有诊断与 HEAD 一致，未修改。

三栈首次验收误将启动产生的新审计视为复制历史，断言调整为核对源/目标审计 ID 无重叠后完整重跑通过；每套本次复制 1,208 条 Platform 和 10 条 Runtime 数据。默认登录、模型新密钥解密、Worker/Workspace/停止/重启及资源回收齐全，见 verification.md 和新 JSON 证据。
