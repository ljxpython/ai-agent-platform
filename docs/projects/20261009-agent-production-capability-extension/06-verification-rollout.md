# 发布、容量与回滚

> 用户已批准双包直接发布与非前端实施；GraphHarbor post44 四产物已上传 PyPI，平台已更新正式 lock。迁移/故障/回退仅操作隔离库，未部署或修改现役环境。真实验证统一记录在 [verification.md](verification.md)。

## 参数和SLO

以下为用户批准的初始目标和实际配置；实测数据与限制单列，不作为上游保证：

| 项 | 初始建议 | 验证与边界 |
| --- | --- | --- |
| callback raw body | <=64KiB | oversize 413，受管小消息不含业务正文 |
| HTTP timeout | 5s | 事务外发送，超时可重试 |
| signature窗口 | ±30s | 时钟同步；每次重试签名刷新 |
| dispatcher退避 | exponential + jitter，最多5min | 429尊重有界Retry-After，不把不可重试错误无限循环 |
| 自动投递窗口 | 24h | 超过转dead_letter并告警，不能静默删除 |
| pending/dead-letter保留 | 至少30d | 修复密钥/目标可手动重放；超期处置须记录明确discard结果 |
| API event/receipt | 30d | 原始正文从不入库；receipt与event同步清理 |
| digest/source tombstone | digest 90d；origin不自动清理 | 覆盖最大重放期；schedule活跃期间来源不失效 |
| frontend poll | 可见页15s，错误退避至60s | 单actor/project只一份；hidden暂停 |
| 正常送达延迟 | terminal→API p95 <=10s（暂定） | 不含浏览器poll；隔离真实环境测量后批准 |
| callback/feed响应 | p95 <=200ms（暂定） | callback20/s、feed10req/s、100k保留事件下测基线 |

如果终态流量不匹配上述基线，由人工批准调整目标；不得为了通过验收隐藏outbox积压或减少case。callback p95与terminal→visible不同，后者额外受前端poll/在线状态影响。

## 配置归属

实际配置见两个服务 `.env.example`、`deploy/docker-compose.stack.yml` 和 [配置矩阵](../../guides/env-matrix.md)：

| 部署方 | 配置 | 边界 |
| --- | --- | --- |
| Engine/Runtime | GRAPHHARBOR_TERMINAL_WEBHOOK_ENABLED/URL/KEY_ID/SECRET；langgraph.json 的 webhooks.terminal.projector | API/所有 Worker 共用；secret仅服务器，生产HTTPS/受控CA，target不可来自browser |
| API | PLATFORM_API_RUNTIME_COMPLETION_ENABLED/KEY_ID/SECRET/VERIFICATION_KEYS | 主 key 和旧 key map 同时验证，本期均绑定 default runtime；不把运行发起JWT当callback credential |
| API admission | managed completion enabled/capability gate | receiver/Runtime配套就绪再注入来源；全入口统一 |
| Web | 后端feed availability | 无secret/URL配置；disabled隐藏私有通知入口 |

不直接修改用户全局环境变量；部署样例只填占位符。实际密钥轮换/发布必须有发布者与审计，日志/请求URL禁止带secret。这里只新增completion transport安全要求，不顺手更改现有ACL TLS fallback。

先在 receiver 的 VERIFICATION_KEYS 保留旧 key，再切所有 sender 的 KEY_ID/SECRET，观察旧 delivery 重签送达后再移除旧 key。时钟校验默认30s；可由 PLATFORM_API_RUNTIME_COMPLETION_CLOCK_SKEW_SECONDS 调整至1..300，但不能用扩大窗口替代时钟同步。

正式发布清单见 [release-manifest.json](evidence/release-manifest.json)，四个 SHA256 与 PyPI 一致。普通 webhook 与受管 terminal profile 同包发布，共用 delivery 表；框架代码不包含平台 ACL、provider 字典、通知对象或业务文案。

## 灰度顺序

1. P1批准来源/签名/保留期，冻结外部版本与双端contract。
2. additive迁移：API origin/event/receipt与Engine Outbox；先验备份、旧包读写兼容，不破坏性downgrade。
3. 部署API receiver/read/feed，保持admission/sender disabled。验证HMAC、schema、当前ACL和DB故障HTTP矩阵。
4. 安装经批准的正式Runtime/Engine包；全进程hook/target配置就绪，先能力探测与单一隔离测试项目启用。
5. 启用managed admission和dispatcher；核对error/timeout/stop/HITL/cron，正常投递/duplicate/conflict/dead-letter指标。
6. 前端同事接入真实API，项目级灰度；完成browser全链路、三尺寸和权限验证。
7. 指标稳定、Final与回滚证据通过后扩大范围。生产发布不包含在本轮授权里。

“受理了Run但暂时不能投递”应保留安全completion，通知失败不回滚运行结果。项目灰度选择由服务器策略决定，不给LLM/浏览器任意callback目标。

## 混合版本兼容

| 组合 | 期望 |
| --- | --- |
| 旧API / 新Runtime+Engine | 旧无origin的Run照常执行，不伪造平台通知 |
| 新API / 旧Runtime+Engine | capability不足时managed completion不启用；历史返回unsupported，不发送旧parser不识别的claim |
| 新全部 / 旧scheduled配置 | 保持旧任务执行和当前report；在批准backfill前无origin的历史/旧cron标unsupported，不谎称已覆盖 |
| 新全部 / 旧Web | 现有SSE/Run/Stop正常，API已持久收到的feed等新Web可见 |
| 新Web / receiver临时不可用 | 503保留同actor旧安全数据；不把Run改error或永久丢未读 |
| 新sender / 旧receiver回退 | dispatcher暂停或暂存；不能把持续422当delivered，恢复匹配receiver后重放 |

全量覆盖要求：已有活跃schedule必须在同一实施范围做受控来源回填/重签或原生任务patch，保留schedule时间/owner/权限/幂等；任务未回填的兼容窗口只能标partial。回填要给出数量dry-run、tombstone/撤权跳过、逐项结果和可回退快照，不批量静默更新。

## 故障处置与可观测性

- 记录outbox pending/dead-letter数量、最老pending年龄、delivery attempts/status、last stable error code、inbox duplicate/conflict与事务耗时；metrics不以无限run_id当label。
- 日志带event/run/request/sender ID，禁止body、secret、headers签名、provider message和HTTP响应正文。
- 401/403上涨：先查key ID、时钟、CA与source关联；修复后重放dead-letter，不重复执行Agent。
- 503/429或网络故障：有界退避，检测积压；故障恢复后catch-up，不能盲目增加Worker导致重试风暴。
- 同event不同body/同Run第二终态：409 quarantine并报警；人工核对事件与事务，禁止“覆盖即可恢复”。
- 操作员重放只复用原event/body，重签发送；对外用户无replay权限。超保留期只能显式discard审计，不能制造新event重新弹通知。
- thread/run已删除：引擎独立snapshot仍可投递；API根据删除事实持久suppressed并ACK，无失效deep-link。
- Langfuse故障不影响completion链路；diagnostics/Usage仍按原能力降级。

运维入口（在目标环境私有配置下运行，以下为操作参考，本轮只在隔离环境验证）：

```bash
graphharbor webhooks list
graphharbor webhooks replay <delivery-uuid>
graphharbor webhooks confirm-stop <delivery-uuid>
```

`confirm-stop` 仅核对并收敛已有停止证据，不把 fence 自行改成已停止；replay 只重发原 snapshot。`discard` 为操作员显式处置，`cleanup` 仅清已 delivered/discarded 且超过保留期的记录。API 的 `scripts/maintain_run_completions.py` 默认只预览，`--apply` 清30d详情/receipt及90d去重墓碑；来源不自动清理。

## 回滚步骤与验收

先回滚消费者风险，再维持未送达数据：

1. **暂停新增来源/目标启用**：停止managed admission注入；不取消在跑Run，不删除已保存来源。
2. **暂停dispatcher**：保留pending/delivering/dead-letter，租约可超时接管。若新receiver健康，可先drain；异常时不得继续向不匹配版本发送。
3. **保护收件和receipt**：已持久安全投影保持只读或暂时disabled；已读不能因回退丢失。
4. **回退Runtime/Engine/API包**：按批准的兼容版本矩阵保留 additive 表/索引。GraphHarbor 旧 post43 要求 migration head011，新 post44 要求012；隔离演练只把迁移标记切回011，保留新表，再升级到012。此步骤必须暂停 API/Worker/admission/dispatcher，不可在运行中改标记；旧包在 head012 会拒绝启动，不提供滚动混用保证。不执行删除表的 downgrade，不改 checkpoint/lease 事实。
5. **验证旧链路**：create/stream/resume/cron、HITL、Stop、Usage、Diagnostics、模型策略和context维护仍正确。
6. **恢复升级后重放**：receiver恢复、时钟/key就绪，再以原event/body重签；same event只一条feed项。

删除/保留期演练必须证明pending不会被RuntimeEvent CASCADE清掉。回滚包若不能承载已受理新origin/私有上下文，必须提前暂停new admission并选择受支持drain窗口；不能靠“先上线看看”发现兼容问题。

## 完成判定

- `done`：tasks P1-P5、正式包、真实多Worker/三服务E2E、前端同事验收、性能/安全/回滚和Final证据全部齐全。
- `partial`：有代码/隔离测试但缺上述任意必要证据；记录具体缺项，不上线现役。
- `blocked`：缺人工批准、外部正式包或真实条件，已完成可独立任务并记录条件/替代尝试/请求。
- `deferred`：明确后置的外部渠道、跨项目聚合和成功toast，不当成本期未验收项。

当前发布、实现和非前端验收以 tasks/verification 的真实记录为准；前端尚未实现，整个专项不能宣称 done。现役部署与现役 cron 回填需要独立部署安排，不属于当前验收缺陷。
