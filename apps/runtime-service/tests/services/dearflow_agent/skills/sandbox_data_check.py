"""Executed inside the offline image, not imported by the host test runner."""
import importlib.util
from pathlib import Path

import duckdb
import openpyxl

spec = importlib.util.spec_from_file_location("analyze", "/skills/data-analysis/scripts/analyze.py")
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)

work = Path("/workspace/work")
for name, amount in (("one", 10), ("two", 20)):
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = "Sales"
    sheet.append(["id", "amount", "formula"])
    sheet.append([1, amount, "=1+1"])
    wb.save(work / f"{name}.xlsx")
(work / "ids.csv").write_text("id,region\n1,East\n")
con = duckdb.connect(":memory:", config={"memory_limit": "128MB", "threads": "1",
    "autoinstall_known_extensions": "false", "autoload_known_extensions": "false", "max_temp_directory_size": "0B"})
mapping = analysis.load_files(con, [str(work / "one.xlsx"), str(work / "two.xlsx"),
                                    str(work / "ids.csv"), "/workspace/uploads/legacy.xls"])
assert len(mapping) == 4 and len(set(mapping.values())) == 4
assert con.execute('SELECT formula FROM "Sales"').fetchone() == ("=1+1",)
assert con.execute('SELECT amount FROM "Legacy"').fetchone() == (7.0,)
analysis.action_inspect(con, mapping)
analysis.action_summary(con, "Sales", mapping)
analysis.action_query(con,
    'SELECT sum(amount) AS total FROM (SELECT id, amount FROM "Sales" UNION ALL SELECT id, amount FROM "Sales_1") JOIN ids USING (id)',
    mapping, str(work / "results.csv"))
for sql in ("SELECT * FROM read_csv_auto('/etc/passwd')", "INSTALL httpfs", "LOAD httpfs",
            "ATTACH '/tmp/escape.db'", "SET enable_external_access=true",
            "SELECT 1; SELECT 2", "COPY (SELECT 1) TO '/workspace/work/escape.csv'",
            "SELECT * FROM range(10001)", "SELECT * FROM read_csv_auto('https://example.org/data.csv')"):
    try:
        analysis.action_query(con, sql, mapping)
    except (ValueError, duckdb.Error):
        pass
    else:
        raise AssertionError("Unsafe SQL accepted: " + sql)
try:
    analysis.action_query(con, "SELECT 1", mapping, "/tmp/escape.csv")
except ValueError:
    pass
else:
    raise AssertionError("Output escaped workspace")
analysis.action_query(con, "SELECT '=1+1' AS formula", mapping, str(work / "formula.csv"))
assert "'=1+1" in (work / "formula.csv").read_text()
analysis.action_query(con, 'SELECT amount FROM "Legacy"', mapping, str(work / "results.json"))
assert '"amount": 7.0' in (work / "results.json").read_text()
collision = duckdb.connect(":memory:")
(work / "headers.csv").write_text("a-b,a_b,__dear_column_0\n1,2,3\n")
analysis._load_csv(collision, str(work / "headers.csv"), {})
assert collision.execute("SELECT * FROM headers").fetchone() == (1, 2, 3)
assert [col[0] for col in collision.description] == ["a_b", "a_b_1", "__dear_column_0"]
print("DATA_BATCH_OK")
