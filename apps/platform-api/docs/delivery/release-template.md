# Platform API Release Template

## 版本信息

- 版本号：
- 基线分支：`main`
- 发布口径：`agent 工作台可演示版`
- 发布日期：
- 发布人：
- 环境样板：
- 数据库后端：`sqlite / postgres`
- 队列后端：`db_polling / redis_list`

## 本次发布包含

- 新增：
- 优化：
- 修复：
- 文档更新：

## 影响范围

- 前端：`apps/platform-web`
- 后端：`apps/platform-api`
- 数据库：
- 配置项：
- 备份文件：

## 发布前检查

- [ ] CI 通过
- [ ] `python3 -m compileall app` 通过
- [ ] `.venv/bin/python -m unittest discover -s tests` 通过
- [ ] `platform-web-demo-up.sh` 能启动
- [ ] `platform-web-demo-health.sh` 全绿
- [ ] 管理员账号可登录
- [ ] chat / operations / platform-config 手动验收通过
- [ ] 数据库已备份
- [ ] 当前环境变量与目标环境样板一致

## 回滚方案

- 回滚代码 tag：
- 回滚配置：
- 恢复数据库备份：
- 回滚后 smoke：
  - [ ] `/_system/probes/ready`
  - [ ] 登录
  - [ ] chat
  - [ ] operations
  - [ ] platform-config

## 风险说明

- 
