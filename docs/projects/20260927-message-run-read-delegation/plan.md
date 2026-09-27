# 消息内部 Run 回查委托修复方案

**状态：** 代码已实施，本机自动化验证通过；现役跨服务真实链路未验证。

## 冲突

Platform API 对消息入口签发 `message-enqueue` 或 `message-read`。Runtime 消息端点接受该 operation，却在内部带同一 Authorization 查询 GraphHarbor 原生 `/threads/{thread_id}/runs/{run_id}`；原生 `auth.on` 只接受8类操作，故先于 Thread ACL 回查返回403。Platform API 在消息入队前已经用本次请求的 `read` 委托查询目标 Run。列表入口只在存在待处理消息时触发内部回查。

## 方案

1. Platform API 的请求级网关工厂只在消息 operation 上添加内部头 `x-runtime-run-read-authorization`，值为该请求已经签发的 `read` 委托。现有 `authorization` 仍是消息 operation；不新签 token、不增加 claim 或 operation。
2. Runtime 消息端点校验内部头中的 JWT，要求其 operation 为 `read`，与消息委托的 identity、tenant、project、credential 一致，且绑定的 Thread 为空或为当前 Thread；失败在内部查询前拒绝。
3. Runtime 内部 GET Run 只使用通过上述校验的 `read` 委托。GraphHarbor 原生授权继续按当前 Thread ACL 回查。消息委托仍被原生 `auth.on` 拒绝。
4. 只在 Runtime 消息端点使用该头；不记录或返回任一委托。没有新数据库访问、迁移、后台任务或配置项。

## 取舍与边界

复用现成的请求级 `read` 委托，避免让 Runtime 直接读取 GraphHarbor 的 Run 表，也不修改原生操作白名单。两份 JWT 只能同时用于同一身份与项目；即使持有不同用户的 `read` token，也不能借消息入口代查 Run。缺头、过期、错身份、错凭据、错 Thread 都失败关闭。原生查询仍可能因当前 ACL 撤销返回403，这是应保留的拒绝。

## 文件

- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py::get_runtime_gateway_service`
- `apps/runtime-service/src/runtime_service/webapp.py::enqueue_message / list_messages`
- 两侧相关测试；必要的正式规范与项目进度文档

## 验收

消息入队与待处理列表能完成内部原生 Run 状态回查；身份/资源错配与权限撤销不放行；直接持消息 token 访问原生 Run 仍403。API、Runtime 定向测试及至少一条平台到 Runtime 的隔离链路有真实证据；无法运行的现役部署链路标“未验证”。
