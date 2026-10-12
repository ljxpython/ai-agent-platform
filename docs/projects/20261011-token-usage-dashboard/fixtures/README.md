# 冻结 API 契约与样例

本目录是前端 mock/契约开发输入，数字和 ID 是确定性测试样例，不是生产账单。所有响应样例已按 Platform API 的公开 Pydantic DTO 校验，schema 由同一 DTO 生成。

| 文件 | 场景 |
|---|---|
| `usage-dashboard-v1.schema.json` / `usage-run-page-v1.schema.json` | 两种响应结构 |
| `dashboard-query.schema.json` / `runs-query.schema.json` | 参数结构；平台重复 `project_ids` 规则另见 03 |
| `dashboard-complete.json` | 完整 Token=1100，估算费用、前窗、趋势和排行 |
| `dashboard-partial.json` | 不完整总量为空，已知小计继续可用 |
| `dashboard-empty.json` | 具有历史采集依据的已记录 0 |
| `dashboard-not_recorded.json` | 开采集、所选范围尚无历史 |
| `dashboard-disabled.json` | 无记录且新采集关闭 |
| `dashboard-unavailable.json` | DB 查询故障，未知数字 |
| `dashboard-unpriced.json` | Token 完整、费用未知 |
| `dashboard-no-projects.json` | 平台无有效项目，不查询 Runtime；采集现状为 null |
| `runs-visible.json` / `runs-empty.json` | 可見运行 / 无后续页 |
| `runs-empty-with-cursor.json` | ACL 过滤空页、仍有后续候选 |
| `error-invalid-query.json` / `error-range-exceeded.json` | HTTP 400 / 422 Envelope |
| `error-upstream-invalid.json` / `error-upstream-timeout.json` | HTTP 502 / 504 Envelope |
| `error-query-capacity.json` | HTTP 503；看板整链路排队或执行超过5秒，保留筛选并提供手动重试 |
| `hmac-vector.json` | 内部固定签名向量，双端测试使用 |

`runs-empty-with-cursor.json` 中游标使用明确测试密钥生成，时间固定且已过期，只用于 mock 透传；真实联调必须使用本次响应的游标。前端不解析/自造游标，不向真实接口提交此 fixture。

HMAC 文件中的密钥明确为测试专用，时间也固定且过期；可核对正文哈希和签名，不能作为当前 HTTP 认证使用。正式密钥仅后端配置持有。

input=1000、output=100、cache_read=200、write=100、reasoning=30，total=1100；不能把子集加成1430。金额 12 位 USD 字符串，unknown/null 与完整 0 分开。所有公开样例不含 Prompt、私有标题、连接凭据或内部 tenant/filter 字段。
