# 六轮订单履约排查：上传材料

所有订单、门店和金额均为本次验收虚构，不含客户或生产数据。CSV为UTF-8文本，既可作为真实附件上传，也可用Excel打开；不用安装依赖、不用运行生成命令。

完整对话见[人工验收手册的复杂案例](../../manual-acceptance.md#复杂案例上传表格完成六轮履约排查)。不要把整份手册、参考答案或校验脚本上传给被测Agent；每轮只复制标明的用户输入，按指定轮次上传文件。

## 上传顺序

| 轮次 | 文件 | 数据行数（不含表头） | 用途 |
|---|---|---:|---|
| 第1轮 | [01_orders.csv](upload/round-1/01_orders.csv) | 26 | 订单与应付金额 |
| 第1轮 | [02_payments.csv](upload/round-1/02_payments.csv) | 30 | 支付事件，保留重复、拆分及状态版本 |
| 第1轮 | [03_shipments.csv](upload/round-1/03_shipments.csv) | 16 | 初次运单快照，含取消／仅建单／截止时间之后的记录 |
| 第1轮 | [04_stores.csv](upload/round-1/04_stores.csv) | 6 | 地区、启用状态及测试门店标记 |
| 第1轮 | [05_dashboard_snapshot.csv](upload/round-1/05_dashboard_snapshot.csv) | 4 | 有意设置错误的旧看板，作为待核对数据，不是答案 |
| 第3轮 | [06_late_shipments.csv](upload/round-3/06_late_shipments.csv) | 3 | 后续补传的迟到运单，不能在第一轮提前上传 |

从仓库根目录执行下面命令可在Finder打开第一批材料，文档中的命令不带RTK前缀：

```bash
open "docs/projects/20261119-universal-agent-eval-authoring-governance/acceptance-materials/fulfillment-investigation/upload/round-1"
```

第3轮再打开旁边的`upload/round-3/`。不要编辑后另存原CSV，否则文件哈希会改变。

## 字段与关联

| 表格 | 主键／关联键 | 字段说明 |
|---|---|---|
| orders | `order_id`；`store_id`关联stores | `created_at`创建时间，`order_status`为confirmed／cancelled，`order_amount`为CNY应付金额 |
| payments | 同一`payment_id`存在多个`event_version`；`order_id`关联orders | `event_id`事件编号，`status`为pending／success／failed／voided，`amount`为该支付金额，`paid_at`实际支付时间，`updated_at`事件更新时间 |
| shipments | 同一`shipment_id`可有多个版本；`order_id`关联orders | `status`为label_created／shipped／delivered／cancelled，`shipped_at`实际发货时间，`updated_at`事件更新时间 |
| stores | `store_id` | `active`和`is_test`均使用true／false；`region`为华东／华南／华中 |
| dashboard_snapshot | `metric` | 旧看板输出值；不能反推或编造旧系统代码和事故原因 |

全部时间已含`+08:00`。本案例的统计时间固定为**2026-11-18 18:00:00+08:00**，不是测试当天时间。哪个版本计入、怎样去重、是否排除测试店等业务规则，在第2／4轮才由用户确认。

## 给验收者的核对材料

- [冻结的分阶段参考结果](reference/expected-results.json)：V1是第2轮，V2是第3轮补传后，V3是第4轮排除测试门店后。
- [实际文件复算结果及SHA256](reference/verification.json)：从这六个真实CSV独立读取计算的结果。
- [只读复算脚本](reference/verify_materials.py)：仅使用Python标准库，不连平台、不调用模型、不写上传材料。

可从仓库根目录复算：

```bash
python3 "docs/projects/20261119-universal-agent-eval-authoring-governance/acceptance-materials/fulfillment-investigation/reference/verify_materials.py"
```

复算通过只说明样本与参考结果一致，不说明Agent已通过该案例。用户实际上传、六轮处理、生成文件和转评测集的结果均待用户执行。
