# Phase 3 P4 - Platform Config 正式治理页

这份文档记录 `platform-config` 从“只读快照”扩展到“正式治理入口”的阶段收口。

## 已完成内容

- 后端正式入口：
  - `GET /_system/platform-config`
  - `PATCH /_system/platform-config/feature-flags`
- 权限与审计已经接上：
  - 读取走 `platform.config.read`
  - 更新 feature flags 走 `platform.config.write`
  - 审计动作：
    - `system.config.read`
    - `system.config.feature_flags.updated`
- 前端正式治理页已接入：
  - `apps/platform-web-vue/src/modules/platform-config/pages/PlatformConfigPage.vue`
  - 路由：`/workspace/platform-config`

## 当前页面能力

- 查看服务版本、环境、数据库、worker、runtime upstream 等运行快照
- 查看并修改 `feature flags`
- 统一纳入当前控制台视觉体系，不再靠临时 system 页面拼接

## 当前边界

- 当前治理重点只放在 feature flags，不把环境变量编辑直接暴露到页面
- 当前不做密钥管理、敏感配置明文展示或在线修改
- 当前不做跨环境同步和配置版本回滚

## 验收建议

1. 登录 `platform-web-vue`
2. 打开 `Platform Config`
3. 查看当前服务、数据库、runtime、operations 配置快照
4. 修改一个 feature flag
5. 刷新页面确认配置回显
6. 到审计页确认已产生对应记录
