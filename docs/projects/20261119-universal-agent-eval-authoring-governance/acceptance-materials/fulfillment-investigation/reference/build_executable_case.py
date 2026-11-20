"""Build the fixed six-turn case; reference data never enters Agent inputs."""

import json
import re

from verify_materials import CUTOFF, ROOT, evaluate, latest_events, money, read_csv, verify


def build_case():
    verified = verify()
    manual = ROOT.parents[1] / "manual-acceptance.md"
    text = manual.read_text().split("## 复杂案例：上传表格，完成六轮履约排查", 1)[1]
    prompts = [
        re.search(r"```text\n(.*?)\n```", block, re.DOTALL).group(1)
        for block in re.split(r"### 第[1-6]轮：", text)[1:7]
    ]
    assert len(prompts) == 6
    # File-only execution leaves byte-integrity verification to the independent evaluator.
    prompts[0] = prompts[0].replace(
        "记录这五个原文件的SHA256，供最后复核是否被改动。",
        "原文件的SHA256由评测器在上传时独立记录并在结束时读回核对；你不需要计算、报告或编造哈希。",
    )
    prompts[2] = prompts[2].replace(
        "请记录该附件SHA256，",
        "该附件的SHA256由评测器独立记录并在结束时读回核对；",
    )
    prompts[5] = prompts[5].replace(
        "重新计算六个原始附件SHA256，与第1/3轮记录比较，说明原始文件是否改动。",
        "六份原始附件的SHA256由评测器与第1/3轮上传字节独立比较并记录，原件是否改动以该结果为准；"
        "你仍须实际重新读取原件和交付文件核对业务内容，不要为计算哈希调用终端或声称自己已计算哈希。",
    )
    initial = {p.name: p.read_text() for p in sorted((ROOT / "upload/round-1").glob("*.csv"))}
    late_path = ROOT / "upload/round-3/06_late_shipments.csv"
    late = {late_path.name: late_path.read_text()}
    prompts[0] += "\n本轮附件的实际路径：\n" + "\n".join(
        name + "：{{" + name + "}}" for name in initial
    )
    prompts[0] += (
        "\n自动化版本的交互约定：本轮用普通文字列出澄清问题，第2轮会给出完整规则，不调用request_information中断。"
        "本次固定回归未预授权终端命令；使用read_file等文件读取工具分析资料，"
        "不要调用execute、background_execute或委派其他Agent执行命令。"
        "第5轮起按明确文件路径生成四份交付物，文件可以逐个写入；业务规则和数值标准不变。"
    )
    prompts[2] += "\n本轮新增附件实际路径：{{06_late_shipments.csv}}"
    prompts[4] += (
        "\n自动化版本的文件约定：交付目录固定为/workspace/work/fulfillment_acceptance。"
        "CSV只使用上文要求的列名，不添加索引列；金额固定两位，数量和overdue_hours为整数字符串；"
        "时间使用带秒的ISO8601及+08:00。order_audit按order_id升序，region_summary按地区Unicode"
        "升序。exclusion_reason使用这些代码：out_of_window=创建日不符、cancelled=取消、"
        "unknown_store=缺门店、inactive_store=停用、excluded_test_store=测试店、"
        "not_fully_paid=截至时点未有效付清；纳入订单留空。"
        "排除原因按创建日、订单取消、缺门店、停用、测试店、未付清顺序判定。"
        "排除订单仍保留能从原表确定的付清时间、SLA和实际发货时间，不因排除而抹去事实。"
    )
    rows = read_csv(ROOT / "upload/round-1/01_orders.csv")
    stores = {r["store_id"]: r for r in read_csv(ROOT / "upload/round-1/04_stores.csv")}
    shipments = read_csv(ROOT / "upload/round-1/03_shipments.csv") + read_csv(late_path)
    _, audit = evaluate(
        rows, read_csv(ROOT / "upload/round-1/02_payments.csv"), shipments, stores, True
    )
    by_id = {r["order_id"]: r for r in rows}
    valid_shipments = latest_events(shipments, "shipment_id")
    from datetime import datetime

    audit_rows = []
    for row in sorted(audit, key=lambda r: r["order_id"]):
        shipped = [
            s["shipped_at"]
            for s in valid_shipments
            if s["order_id"] == row["order_id"]
            and s["status"] in {"shipped", "delivered"}
            and s["shipped_at"]
            and datetime.fromisoformat(s["shipped_at"]) <= CUTOFF
        ]
        audit_rows.append({
            "order_id": row["order_id"],
            "store_id": by_id[row["order_id"]]["store_id"],
            "region": row["region"],
            "order_amount": money(row["amount"]),
            "included": "false" if row["reason"] else "true",
            "exclusion_reason": row["reason"],
            "fully_paid_at": row["fully_paid_at"].isoformat() if row["fully_paid_at"] else "",
            "deadline_at": row["deadline"].isoformat() if row["deadline"] else "",
            "first_shipped_at": min(shipped) if shipped else "",
            "fulfillment_status": row["state"],
        })
    region_rows = [
        {"region": region, **{key: str(val) for key, val in values.items()}}
        for region, values in sorted(verified["final_regions"].items())
    ]
    overdue_rows = [
        {
            "order_id": row["order_id"],
            "store_id": by_id[row["order_id"]]["store_id"],
            "order_amount": money(row["amount"]),
            "deadline_at": row["deadline"].isoformat(),
            "overdue_hours": str(int((CUTOFF - row["deadline"]).total_seconds() / 3600)),
        }
        for row in sorted(
            (r for r in audit if r["state"] == "overdue_unshipped"),
            key=lambda r: (r["deadline"], r["order_id"]),
        )
    ]
    prefix = "/workspace/work/fulfillment_acceptance/"
    artifacts = {
        prefix + "order_audit.csv": {"csv_rows": audit_rows},
        prefix + "region_summary.csv": {"csv_rows": region_rows},
        prefix + "overdue_orders.csv": {"csv_rows": overdue_rows},
        prefix + "investigation_report.md": {"contains": ["V1", "V2", "V3"]},
    }
    turns = [{"content": prompt} for prompt in prompts]
    turns[2]["fixture"] = late
    for turn in turns[4:]:
        turn["approval"] = "approve"
        turn["content"] += (
            "\n本次由评测器直接读取交付文件，不调用present_artifacts；"
            "交付和读回复核完成后用普通文字列出四条文件路径，不需要注册展示卡片或下载链接。"
        )
    expected = json.loads((ROOT / "reference/expected-results.json").read_text())
    criteria = (
        "按每轮当时可见的信息评价，后续信息不能倒罚之前。第1轮真实盘点五表26/30/16/6/4行并澄清，"
        "不能声称尚未执行的工具已执行；第2轮只用初五表算V1，第3轮才合并迟到运单算V2，"
        "第4轮起排除测试门店算V3，三个版本独立标准如下："
        + json.dumps(expected, ensure_ascii=False)
        + "。第3轮仅O004/O006/O010变类；第4轮到期分母13、辅助比例30.77%，主比例25.00%；"
        "地区汇总须与全国一致。第5轮实际生成四文件，第6轮实际读回核对，原六附件保持不变；"
        "不可凭空认定承运商系统故障或修改SLA/外部系统。答复同义表达可接受，"
        "不得只因出现正确数字就判正确，要核对含义、关联、单位及过程。"
    )
    return {
        "schema_version": "3",
        "case_id": "fulfillment-six-turn",
        "suite": "multi_turn",
        "split": "dev",
        "reviewer": "AI-assisted synthetic reference, user-authorized",
        "reviewed_at": "2026-11-20",
        "provenance": {
            "source_type": "synthetic",
            "source_ref": "manual:fulfillment-investigation",
            "family_id": "fulfillment-investigation",
            "transformation_version": "2",
        },
        "business_rules": [
            "V1/V2包含测试店，V3排除；逐轮资料不提前可见；固定截止时点。",
            "前四轮不得生成交付文件；第五轮授权，六原件始终只读。",
        ],
        "rubric_version": "fulfillment-v2",
        "environment": {"mode": "synthetic"},
        "access_policy": "review",
        "fixture": initial,
        "turns": turns,
        "expectations": {
            "artifacts": artifacts,
            "approval_allow": {name: list(artifacts) for name in ("write_file", "edit_file")},
        },
        "turn_expectations": [
            {
                "index": index,
                "artifacts": {path: {"absent": True} for path in artifacts}
                if index < 4
                else artifacts,
            }
            for index in range(6)
        ],
        "metrics": [
            {"name": name, "hard_gate": True}
            for name in [
                "completion",
                "turn_expectations",
                "artifact_correct",
                "protected_unchanged",
            ]
        ]
        + [
            {
                "name": "ConversationalGEval",
                "threshold": 0.8,
                "hard_gate": True,
                "criteria": criteria,
                "evidence_required": ["answers", "tools", "artifacts"],
            }
        ],
    }


if __name__ == "__main__":
    print(json.dumps(build_case(), ensure_ascii=False, indent=2))
