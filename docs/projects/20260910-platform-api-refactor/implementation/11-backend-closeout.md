# 后端剩余事项收尾

日期：2026-09-10。范围：上一轮验收中列出的字段收缩、网关边界与真实延迟/轮换验证；前端和容器整体验收继续后置。

## 实现

### 模型与 Agent

- 模型连接改用不可变的数据库 UUID；移除 model_key、runtime_id、同步状态/时间、原始快照、远端默认和软删除字段。POST 始终创建独立连接，同一模型名称不再覆盖已有地址或凭据。项目默认、策略、delegation 和 Context 统一使用记录 ID，删除 provider:model 旧别名解析。
- Agent 删除未参与执行的 config、metadata_json 和部署 URL；保留公开 Context 默认值（model_id、temperature、max_tokens、top_p、tools），校验未知字段及参数范围。graph_id 创建后不可变，换图应创建对应 Agent；创建时查询真实部署 schema，不接受不存在的 Graph。
- 更新未投入使用的新库静态基线；仍为 20 张业务表。既有开发数据库不执行破坏性迁移。

### 网关与授权

- 标准 Runs 的 command.resume 与 Protocol input.respond 共用父 Run、活跃 interrupt、当前项目/Agent/Graph/模型/工具授权检查。父 Run 按当前 checkpoint.metadata.run_id 查找授权记录，不取最近一次请求，避免后续取消请求关联错父执行。支持多个 ID 映射；审批不允许夹带 input/config/context。每次恢复单独记录，不覆盖父 Run。
- run_requests 新增最小 config_snapshot，冻结公开递归上限；只支持 recursion_limit（1–1000，缺省 25）。不持久化任意 configurable 或密钥；凭据仍每次从可信通道取得。重试复用首次决议，审批继承父请求配置。
- SDK JSON 调用保留；Run join-stream 使用既有 HTTP 流适配，以便在向客户端发送 HTTP 200 前检查上游状态。保留 Last-Event-ID，连接超时映射 504，断开仅关闭订阅，不隐式取消。
- 模型引用携带签名保护的主体标识与 Agent 键。兑换时重新读取当前项目、成员/服务账号 token、Agent、Graph 和模型策略，禁用/撤销后拒绝兑换；不从旧引用复原历史角色。用户身份加载逻辑与 HTTP 认证复用，认证查询放到线程池。

### GraphHarbor 配套修复

真实创建 Agent 的 schema 查询暴露 DeepAgents 的 NotRequired 注解转换错误。原实现把状态 channels 转成 Pydantic model，丢失 TypedDict 注解上下文。

GraphHarbor 改为复制图和 builder，用原 state_schema 调用 LangGraph 原生 get_output_jsonschema；不修改运行图，不复制 schema 解析器，不加入平台业务认证。普通 Pregel 保留 channels 方式。接口测试覆盖 NotRequired、不同 input/output/state 与查询无副作用；真实 Showcase 图探测通过。

发布 `graphharbor==0.13.0.post26`、`graphharbor-runtime==0.13.0.post26`；发布前核对本地源码与已安装 post25，除本次 core_api schema 修复外，两包源码一致。版本锁步、构建和 PyPI 上传通过，Runtime 依赖同步更新；四份产物 SHA-256 与 PyPI 一致，见 [发布哈希](../evidence/20260910-post26-sha256.json)。

## 验证要求与记录

- 平台最终全量：139 项，136 passed、3 skipped，298.964 秒，无失败/错误。跳过的集成测试不计作通过。
- 新模型生命周期测试：5 项通过，覆盖同名独立连接、轮换保持 ID、公开字段无凭据、模型禁用、项目策略/成员撤权、服务账号 token 撤销、Agent 禁用。
- 最新 run_requests 16 项通过（33.260 秒），包含 checkpoint 原始 Run 与后来取消请求的区分。
- 网关回归覆盖：提交响应关联落库失败、取消提交后的同 key 重试、多个 interrupt 按 ID 恢复、父配置继承、非法配置拒绝、审批重试、上游建连超时和错误前置。
- 最终 PostgreSQL 空库：重复 upgrade、downgrade、再次 upgrade，通过；20 张业务表与 ORM metadata 无差异，模型/Agent 删除字段及 config_snapshot 已核对。
- Runtime 从 PyPI 安装 post26 后定向回归：47 passed、3 deselected，176.41 秒。
- GraphHarbor schema 接口 4 项通过；真实 Showcase 原生 state schema 探测通过；相关框架 Ruff lint 检查通过；格式检查仍有已有差异，未整体重排已发布代码。
- 平台 Ruff F 检查通过；项目严格规则仍有既有及广泛风格项，不声明全仓库严格 lint 全绿。
- 首轮平台回归揭示旧测试仍要求 Agent.config，已按新契约修正并通过最终全量；两轮真实验收分别发现同步字段残余和 schema 注解缺陷，均已修复，不把失败轮次记为成功。

### 真实取消场景追加修复

取消接口使用统一 ACK 返回包装，原包装遗漏内部字段过滤；现与普通 JSON 共用过滤，取消响应也删除 runtime_model_ref/_runtime_*。取消审计路径段数原判断为 8、实际为 7，导致完整路径写入 64 字符 target_id；现正确记录 Run UUID，未知路由不再把路径充当目标 ID（完整路径已有独立 path 字段）。SDK/ACK 回归 12 项、审计回归 6 项均通过。

## 真实验收

`scripts/platform_showcase_acceptance.py` 使用新隔离 PostgreSQL、独立 Redis 前缀与自有 API/Worker：先验证真实 pending Run 的并发 reject、取消与重新发送，再使用默认 60 秒模型引用 TTL，创建 Run 后等待超过 60 秒并轮换模型凭据，最后启动 Worker。模型必须读取最新凭据、完成实际修复与审批，才算延迟恢复通过。

**实际结果：通过。** 新 Thread `59c3270e-7cf8-4cf9-bfee-ea7fe162cb7c`，6 次工具审批后最终 Run `895ff817-32ce-4727-869e-b0ffd42045c1` 为 success。

- 真实 pending 并发 reject、取消后新动作、同 key 复用和改 payload 409 通过。
- 创建时使用无效旧凭据，实际等待 62 秒（超过默认 60 秒引用 TTL）后轮换密钥并启动 Worker，真实模型执行成功。
- 审批暂停期间重启 Platform API、Runtime API 和 Worker，messages 与 interrupt ID 一致；Agent 禁用时审批 403，重新启用后标准 `command.resume` 成功。
- edit_file/write_file/execute 审批均实际执行；独立 Docker 执行生成的回归测试通过，报表和 result.txt 均为 43.50，退出码 0。
- SSE 读取 105030 字节，公开响应无内部模型引用；跨项目读取被拒绝，Operations/resync 路由 404。取消 ACK 与审计修复在此次真实调用中通过。
- 验收脚本正常退出（exit 0），关闭自己启动的进程；隔离数据与本地日志保留，没有修改既有开发库。

[真实 post26 证据](../evidence/20260910-platform-showcase-post26.json) · [收尾测试汇总](../evidence/20260910-closeout-acceptance.json)。

### 验收启动边界

post26 复验曾因本机 Python 冷启动超过 180 秒而未就绪；该轮未进入业务链路，不计通过。验收脚本将 API readiness 等待延长到 600 秒，保持产品请求超时不变，继续使用全新隔离库复验。

## 保留的工程边界

本记录收尾的是 10 中字段收缩及网关功能缺口，不代表整个 04 的 S3 完成：身份、项目等模块仍存在同步 Session 的 async UoW 包装和原四层目录，全服务事务规范化与模块压平继续标记 partial。严格全仓 lint、前端、整套容器部署和 LangGraph Server 完整等价性也不能由本轮结果推定完成。

## 状态

| 范围 | 状态 | 证据 |
| --- | --- | --- |
| 模型/Agent 字段与 20 表基线收缩 | done | 生命周期回归、PostgreSQL 升降升、metadata 无差异 |
| 标准审批、父 Run、当前授权、SSE/ACK 与审计 | done | 定向契约回归及 post26 真实调用 |
| 超 TTL 排队、凭据轮换、三进程重启与 Showcase | done | post26 真实模型、工具、SSE 与独立结果核验 |
| 全服务事务与模块压平（S3） | partial | 仍有同步 Session 的 async UoW 包装及原目录层级 |
| 前端、容器整体验收、完整 Server 等价性 | deferred | 按用户此前决定另行推进 |

本轮功能收尾 done，原工程整体仍 partial，不能宣称所有结构任务均已完成。前端影响统一见 [05](../05-frontend-handoff.md)。
