# Phase 4 前端治理页验收清单

这份清单覆盖 `platform-web-vue` 在 `phase-4` 新增和增强的治理页。

## 0. 当前开发状态

- [x] 已新增 `Control Plane` 统一组合页
- [x] 已增强 `Service Accounts` 治理流
- [x] 已增强 `System Governance` 值班视图
- [x] 已通过 `pnpm lint`
- [x] 已通过 `pnpm typecheck`
- [x] 已通过 `pnpm build`
- [x] 已修复 `Service Accounts` 页面超限拉取导致的 `422`

## 1. Control Plane

- [x] 左侧导航能看到 `Control Plane`
- [x] 页面能展示环境 / ready / health / queue / service account 五个核心指标
- [x] 页面能展示当前风险摘要
- [x] 页面能展示统一快捷入口并跳转到具体治理页
- [x] 页面能展示 recent operations / recent audit / recent service accounts

## 2. Platform Config

- [x] 能打开 `Platform Config`
- [x] 能看到 requests / top paths / trace headers
- [x] 能看到 worker heartbeat 列表
- [x] 能看到 security / environment / data governance 快照
- [x] 修改 feature flag 后能保存并回显

## 3. Service Accounts

- [x] 左侧导航能看到 `Service Accounts`
- [x] 页面能展示 service account 统计卡片
- [x] 能创建新的 service account
- [x] 能编辑描述与角色
- [x] 能启用 / 停用 service account
- [x] 能为指定 account 创建 token
- [x] 创建 token 后能看到明文 token 且可复制
- [x] 能通过确认弹窗撤销 token
- [x] 支持按 token 名称 / 前缀检索
- [x] 分页可以正常切页
- [x] 详情抽屉能正确展示 account / token 明细

## 4. System Governance

- [x] 左侧导航能看到 `System Governance`
- [x] 页面能展示 `live / ready / health`
- [x] 页面能展示值班风险面板
- [x] 页面能展示 requests / queue / workers 趋势图
- [x] 页面能展示 worker metrics
- [x] 页面能打开 worker heartbeat 详情抽屉
- [x] 自动轮询默认开启
- [x] 切换 `ready` 状态时有 toast 提示

## 5. 最小手动验收步骤

1. 启动 demo 栈：`bash "./scripts/platform-web-vue-demo-up.sh"`
2. 登录前端
3. 依次验：
   - `Control Plane`
   - `Platform Config`
   - `Service Accounts`
   - `System Governance`
4. 同步观察 `platform-api-v2` 日志和 `/_system/probes/ready`

## 6. 最终验收记录

验收时间：`2026-04-06`

- [x] `Control Plane` 页面可正常打开
- [x] `Platform Config` 页面可正常打开
- [x] `Service Accounts` 页面可正常打开，列表请求为 `limit=200`
- [x] `System Governance` 页面可正常打开
- [x] 页面级 console 未出现新的 error
