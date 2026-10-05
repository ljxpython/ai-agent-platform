# 权限状态与页面判定

## 改动
- `workspace` Store 保留项目权限快照，区分 `ready/denied/unavailable`，列表刷新失败不清空当前上下文。
- `route-access.ts` 统一路由守卫与驻留页面的具体权限判定，移除“有角色即可放行”。
- Layout 将“暂时无法确认”与“权限已失效”分开，并提供原地重试。

## 验证
- workspace/router/Layout 定向测试通过；浏览器冷启动、刷新失败和真实撤权场景通过。
