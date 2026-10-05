# 平台权限状态与刷新治理 - 整体方案

## 背景
前端把权限未加载、后台刷新失败、局部 Thread 403 和真实项目撤权统一渲染为“当前页面权限已失效”。项目切换、切屏和网络抖动因此频繁阻断页面，造成用户投诉；现有防误踢逻辑又以“有角色”替代页面所需权限，导致路由守卫与页面状态不一致。

## 目标
- 页面首次加载时明确区分 loading、暂不可确认、明确拒绝。
- 后台刷新失败保留最近一次确认的具体权限，不清空工作区。
- 真实 403/空权限/404 按项目、Thread 和会话范围处理。
- 刷新 Token 的网络失败不清理会话。
- 降低重复刷新和跨会话广播造成的请求放大。

## 方案设计

### 整体架构
`platform-web` 维护带项目和权限快照的状态，路由守卫与 Layout 使用同一判定；HTTP/Fetch 拒绝事件携带作用域。`platform-api` 和 `runtime-service` 继续执行权威授权，前端只负责体验和状态呈现。

### 关键改动点

#### 1. 前端项目权限状态机
- **文件：** `apps/platform-web/src/stores/workspace.ts`、`apps/platform-web/src/layouts/WorkspaceLayout.vue`、`apps/platform-web/src/router/guards.ts`
- **改动：** 保留上次确认的具体权限；区分首次加载、刷新暂不可用、明确无权；移除“有角色即可放行”的宽泛兜底。
- **理由：** 避免网络抖动伪装成撤权，同时不绕过具体页面权限。

#### 2. 作用域化拒绝和刷新合并
- **文件：** `apps/platform-web/src/services/http/client.ts`、`apps/platform-web/src/services/langgraph/client.ts`、`apps/platform-web/src/modules/chat/composables/useSessionConnection.ts`
- **改动：** 拒绝事件携带 project/thread/operation；项目刷新合并进行中的请求，局部 Thread 仅刷新自身；减少后台会话响应聚焦事件，保留每个保活 Thread 的 60 秒撤权检查。
- **理由：** 阻止单个操作错误扩大为整页失效和 N 倍请求。

#### 3. Token 续期错误分类
- **文件：** `apps/platform-web/src/services/http/client.ts`、`apps/platform-web/src/services/langgraph/client.ts`
- **改动：** 只有 refresh 端点明确返回 400/401 才清理会话；网络、超时、5xx 返回可重试错误并保留会话。
- **理由：** 登录状态不能被临时网络故障误杀。

#### 4. 后端链路校核
- **文件：** `apps/runtime-service/src/runtime_service/auth/platform.py`、`apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- **改动：** 核对并补充 ACL 回查超时、连接复用和作用域日志；不改变撤权语义。
- **理由：** 保持安全边界，同时降低反向校验导致的误判。

## 链路影响
### 受影响的调用链路
`platform-web → platform-api /access → runtime-service ACL 回查`

### 契约变更
- 前端内部拒绝事件增加作用域字段；不改变公开 HTTP 错误 Envelope。
- 401/403/5xx 的会话处理语义收敛；后端授权结果和状态码保持不变。

## 风险和依赖
- **风险：** 保留旧权限快照期间用户刚被撤权。→ **应对：** 所有业务请求仍由后端强制校验；明确 403 立即清除对应作用域。
- **风险：** 刷新合并导致状态更新延迟。→ **应对：** 可见性切换主动刷新，并保留显式重试。
- **依赖：** 需要可执行的前端单测和至少一条真实跨服务链路。

## 实施计划
1. Phase 1：修复项目权限状态和 Token 错误分类。
2. Phase 2：作用域化拒绝事件并合并刷新。
3. Phase 3：补齐 Runtime/网关校核、测试和全链路验证。

## 最终实施边界与上线/回退
状态：done（本地实现与验证范围）。Platform API 本次仅验证已有授权契约，工作区中此前的网关未提交修改不归属本项目。

- Runtime 连接池位于 auth/acl_client.py，供普通导入与 GraphHarbor 文件路径加载共用，不能将池放在会被重复加载的 platform.py。
- Layout 合并激活到 10 秒窗口并保留尾部刷新，明确项目拒绝可立即复核。后台保活 Thread 仍每 60 秒检查撤权，避免为了减少请求破坏撤权时效。
- 没有 schema/公开接口变化；Web 和 Runtime 可独立发布/回退到先前构建，不需要回滚数据库。
- 回退边界通过无 lifespan 独立鉴权 fallback 测试、新前端兼容现有 API 契约的真实浏览器测试验证；生产构建切换未执行。
- 本次未部署生产、未替换现役 Runtime API/Worker。Web 开发服务可热更新；Runtime 连接池和超时更改需发布并重启 Runtime API 才生效。
- 不涉及 JWT/SSE 草案毕业，错误 Envelope 未改变，仅补充前端消费规则。
