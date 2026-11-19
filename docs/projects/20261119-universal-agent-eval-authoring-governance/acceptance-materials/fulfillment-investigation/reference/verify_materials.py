"""只读复算合成材料；不连接平台、不调用模型、不写入上传文件。"""

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = datetime.fromisoformat("2026-11-18T18:00:00+08:00")
STATES = ("on_time", "shipped_late", "overdue_unshipped", "pending_not_due")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    assert rows and all(None not in row for row in rows), path
    return rows


def latest_events(rows, key):
    latest = {}
    for row in rows:
        if datetime.fromisoformat(row["updated_at"]) > CUTOFF:
            continue
        old = latest.get(row[key])
        version = int(row["event_version"])
        if old and version == int(old["event_version"]):
            assert row == old, "同版本冲突不能静默丢弃"
        if old is None or version > int(old["event_version"]):
            latest[row[key]] = row
    return list(latest.values())


def money(value):
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def evaluate(orders, payments, shipments, stores, exclude_test):
    payments = latest_events(payments, "payment_id")
    shipments = latest_events(shipments, "shipment_id")
    audit = []
    for order in orders:
        store = stores.get(order["store_id"])
        amount = Decimal(order["order_amount"])
        successes = sorted(
            (
                p
                for p in payments
                if p["order_id"] == order["order_id"]
                and p["status"] == "success"
                and datetime.fromisoformat(p["paid_at"]) <= CUTOFF
            ),
            key=lambda p: (p["paid_at"], p["payment_id"]),
        )
        running = Decimal(0)
        fully_paid_at = None
        for payment in successes:
            running += Decimal(payment["amount"])
            if running >= amount and fully_paid_at is None:
                fully_paid_at = datetime.fromisoformat(payment["paid_at"])
        reason = ""
        if (
            datetime.fromisoformat(order["created_at"]).date().isoformat()
            != "2026-11-17"
        ):
            reason = "out_of_window"
        elif order["order_status"] == "cancelled":
            reason = "cancelled"
        elif store is None:
            reason = "unknown_store"
        elif store["active"] != "true":
            reason = "inactive_store"
        elif exclude_test and store["is_test"] == "true":
            reason = "excluded_test_store"
        elif fully_paid_at is None:
            reason = "not_fully_paid"
        deadline = fully_paid_at + timedelta(hours=24) if fully_paid_at else None
        shipped = [
            datetime.fromisoformat(s["shipped_at"])
            for s in shipments
            if s["order_id"] == order["order_id"]
            and s["status"] in {"shipped", "delivered"}
            and s["shipped_at"]
            and datetime.fromisoformat(s["shipped_at"]) <= CUTOFF
        ]
        first_shipped = min(shipped) if shipped else None
        if reason:
            state = "excluded"
        elif first_shipped:
            state = "on_time" if first_shipped <= deadline else "shipped_late"
        else:
            state = "overdue_unshipped" if deadline <= CUTOFF else "pending_not_due"
        audit.append(
            {
                "order_id": order["order_id"],
                "region": store["region"] if store else "",
                "amount": amount,
                "reason": reason,
                "state": state,
                "deadline": deadline,
                "fully_paid_at": fully_paid_at,
            }
        )
    selected = [row for row in audit if not row["reason"]]
    overdue = [row for row in selected if row["state"] == "overdue_unshipped"]
    summary = {
        "eligible_orders": len(selected),
        "eligible_amount": money(sum((r["amount"] for r in selected), Decimal(0))),
        **{
            state: sorted(r["order_id"] for r in selected if r["state"] == state)
            for state in STATES
        },
        "overdue_amount": money(sum((r["amount"] for r in overdue), Decimal(0))),
        "overdue_rate_pct": money(Decimal(len(overdue)) * 100 / len(selected)),
    }
    return summary, audit


def verify():
    initial = ROOT / "upload/round-1"
    files = {
        name: read_csv(initial / name)
        for name in (
            "01_orders.csv",
            "02_payments.csv",
            "03_shipments.csv",
            "04_stores.csv",
            "05_dashboard_snapshot.csv",
        )
    }
    late_path = ROOT / "upload/round-3/06_late_shipments.csv"
    late = read_csv(late_path)
    assert [len(rows) for rows in files.values()] == [26, 30, 16, 6, 4]
    assert len(late) == 3
    assert len({r["order_id"] for r in files["01_orders.csv"]}) == 26
    assert Counter(p["event_id"] for p in files["02_payments.csv"])["E016"] == 2
    stores = {s["store_id"]: s for s in files["04_stores.csv"]}
    expected = json.loads((ROOT / "reference/expected-results.json").read_text())
    results = {}
    audits = {}
    for version, include_late, exclude_test in [
        ("V1", False, False),
        ("V2", True, False),
        ("V3", True, True),
    ]:
        results[version], audits[version] = evaluate(
            files["01_orders.csv"],
            files["02_payments.csv"],
            files["03_shipments.csv"] + (late if include_late else []),
            stores,
            exclude_test,
        )
        assert results[version] == expected[version], (version, results[version])
    final = audits["V3"]
    by_id = {r["order_id"]: r for r in final}
    assert by_id["O017"]["fully_paid_at"].isoformat() == "2026-11-17T11:00:00+08:00"
    assert by_id["O006"]["state"] == by_id["O022"]["state"] == "on_time"
    assert by_id["O023"]["deadline"] == CUTOFF + timedelta(seconds=1)
    assert by_id["O019"]["reason"] == by_id["O020"]["reason"] == "not_fully_paid"
    assert by_id["O024"]["state"] == by_id["O025"]["state"] == "overdue_unshipped"
    assert Counter(r["reason"] for r in final if r["reason"]) == {
        "cancelled": 1,
        "not_fully_paid": 4,
        "out_of_window": 1,
        "unknown_store": 1,
        "inactive_store": 1,
        "excluded_test_store": 2,
    }
    regions = {}
    for name in ["华东", "华南", "华中"]:
        rows = [r for r in final if not r["reason"] and r["region"] == name]
        regions[name] = {
            "eligible_orders": len(rows),
            "eligible_amount": money(sum((r["amount"] for r in rows), Decimal(0))),
            **{state: sum(r["state"] == state for r in rows) for state in STATES},
        }
    assert [(r["eligible_orders"], r["eligible_amount"]) for r in regions.values()] == [
        (9, "1812.63"),
        (4, "1311.93"),
        (3, "1941.94"),
    ]
    overdue_order = sorted(
        (r for r in final if r["state"] == "overdue_unshipped"),
        key=lambda r: (r["deadline"], r["order_id"]),
    )
    assert [r["order_id"] for r in overdue_order] == ["O002", "O025", "O024", "O018"]
    due = sum(not r["reason"] and r["deadline"] <= CUTOFF for r in final)
    assert due == 13 and money(Decimal(4) * 100 / due) == "30.77"
    return {
        "status": "passed",
        "versions": results,
        "final_regions": regions,
        "final_exclusions": dict(Counter(r["reason"] for r in final if r["reason"])),
        "overdue_priority": [r["order_id"] for r in overdue_order],
        "due_orders": due,
        "due_only_overdue_rate_pct": "30.77",
        "input_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / "upload").rglob("*"))
            if p.is_file()
        },
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
