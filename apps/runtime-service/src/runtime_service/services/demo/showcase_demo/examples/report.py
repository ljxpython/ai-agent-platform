"""Small sales report used by the showcase teaching task."""

import csv
from decimal import Decimal
from pathlib import Path


def total_sales(path: Path) -> Decimal:
    with path.open(newline="", encoding="utf-8") as source:
        return sum(
            (Decimal(row["unit_price"]) for row in csv.DictReader(source)), Decimal(0)
        )


if __name__ == "__main__":
    print(f"Total sales: {total_sales(Path(__file__).with_name('sales.csv')):.2f}")
