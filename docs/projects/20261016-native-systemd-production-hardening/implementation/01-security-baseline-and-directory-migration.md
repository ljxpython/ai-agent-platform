# 基础设施安全基座与生产目录搬迁

## 改动时间
2026-10-16

## 相关任务
- Task 1.1: 创建系统专用受限账号 `aiplatform`
- Task 1.2: 生产目录标准搬迁与权限收敛

## 具体改动
1. **创建专用无登录系统账号**：
   - 命令：`useradd -r -s /usr/sbin/nologin -d /opt/ai-agent-platform aiplatform`
   - 分配 UID 999，GID 988，锁定交互式登录权限。
2. **规范化迁移至 `/opt/ai-agent-platform`**：
   - 将原位于 `/root/PyCharmMiscProject/ai-agent-platform` 的代码、虚拟环境及配置完整搬迁至 `/opt/ai-agent-platform`。
   - 建立 `/root/ai-agent-platform` 软链接至 `/opt/ai-agent-platform`。
3. **敏感凭据权限锁死**：
   - 替换所有配置文件与脚本内部的硬编码旧路径。
   - 属主递归赋权：`chown -R aiplatform:aiplatform /opt/ai-agent-platform`。
   - 敏感文件（`.env`、mTLS 凭据）严格限定权限为 `600`。

## 验证证据
- `id aiplatform`: `uid=999(aiplatform) gid=988(aiplatform) groups=988(aiplatform)`
- `ls -ld /opt/ai-agent-platform`: `drwxr-x--- 14 aiplatform aiplatform 4096 Oct 16 17:04 /opt/ai-agent-platform`
- `su -s /bin/bash aiplatform -c ".../python3 -V"`: `Python 3.13.5` 正常执行。
