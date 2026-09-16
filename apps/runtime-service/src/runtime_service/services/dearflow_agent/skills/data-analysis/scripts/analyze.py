"""
Data Analysis Script using DuckDB.

Analyzes Excel (.xlsx/.xls) and CSV files using DuckDB's in-process SQL engine.
Supports schema inspection, SQL queries, statistical summaries, and result export.
"""

import argparse
import datetime
import json
import logging
import os
import re
from pathlib import Path

import duckdb
import openpyxl
import xlrd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def sanitize_table_name(name):
    value = re.sub(r"[^a-zA-Z0-9_]", "_", str(name)) or "column"
    return "t_" + value if value[0].isdigit() else value


def safe_path(value, *, output=False):
    path = Path(value)
    bases = [Path("/workspace/work")] if output else [Path("/workspace/uploads"), Path("/workspace/work")]
    resolved = path.resolve()
    if not any(resolved.is_relative_to(base) for base in bases) or path.is_symlink():
        raise ValueError("analysis_path_denied")
    if not output and (not resolved.is_file() or resolved.stat().st_size > 20 * 1024 * 1024):
        raise ValueError("analysis_input_missing_or_too_large")
    return resolved


def unique_name(name, names):
    base = sanitize_table_name(name)
    candidate = base
    counter = 1
    while candidate.casefold() in {str(n).casefold() for n in names}:
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def _load_excel(con, file_path, table_map):
    path = Path(file_path)
    if path.suffix.lower() == ".xlsx":
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=False, keep_links=False)
        sheets = ((sheet.title, sheet.iter_rows(values_only=True)) for sheet in workbook)
    else:
        workbook = xlrd.open_workbook(path, on_demand=True)
        sheets = ((sheet.name, (sheet.row_values(i) for i in range(sheet.nrows))) for sheet in workbook.sheets())
    try:
        for sheet_name, iterator in sheets:
            iterator = iter(iterator)
            header = next(iterator, ())
            if not header:
                continue
            if len(header) > 256:
                raise ValueError("analysis_column_limit")
            columns = []
            for name in header:
                columns.append(unique_name(name if name is not None else "column", columns))
            rows = []
            for row in iterator:
                if (len(rows) + 1) * len(columns) > 100000:
                    raise ValueError("analysis_cell_limit_100000")
                rows.append(tuple(row))
            types = []
            for i in range(len(columns)):
                values = [r[i] for r in rows if r[i] is not None]
                if values and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
                    types.append("DOUBLE")
                elif values and all(isinstance(v, (datetime.date, datetime.datetime)) for v in values):
                    types.append("TIMESTAMP")
                else:
                    types.append("VARCHAR")
            name = unique_name(sheet_name, table_map.values())
            fields = ", ".join(f'"{c}" {kind}' for c, kind in zip(columns, types))
            con.execute(f'CREATE TABLE "{name}" ({fields})')
            if rows:
                con.executemany(f'INSERT INTO "{name}" VALUES ({", ".join("?" for _ in columns)})', rows)
            table_map[f"{path.name}:{sheet_name}"] = name
    finally:
        if path.suffix.lower() == ".xlsx":
            workbook.close()
        else:
            workbook.release_resources()


def _load_csv(con, file_path, table_map):
    name = unique_name(Path(file_path).stem, table_map.values())
    relation = con.read_csv(str(file_path), header=True)
    names, projections = [], []
    for column in relation.columns:
        safe = unique_name(column, names)
        names.append(safe)
        quoted = column.replace('"', '""')
        projections.append(f'"{quoted}" AS "{safe}"')
    relation.project(", ".join(projections)).create(name)
    table_map[str(file_path)] = name


def load_files(con, files):
    if not 1 <= len(files) <= 10 or len(set(files)) != len(files):
        raise ValueError("analysis_file_count")
    table_map = {}
    for value in files:
        path = safe_path(value)
        if path.suffix.lower() in (".xls", ".xlsx"):
            _load_excel(con, str(path), table_map)
        elif path.suffix.lower() == ".csv":
            _load_csv(con, str(path), table_map)
        else:
            raise ValueError("unsupported_analysis_input")
    if not table_map:
        raise ValueError("no_tables")
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")
    return table_map




def action_inspect(con: duckdb.DuckDBPyConnection, table_map: dict[str, str]) -> str:
    """Inspect the schema of all loaded tables."""
    output_parts = []

    for original_name, table_name in table_map.items():
        output_parts.append(f"\n{'=' * 60}")
        output_parts.append(f'Table: {original_name} (SQL name: "{table_name}")')
        output_parts.append(f"{'=' * 60}")

        # Get row count
        row_count = con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        output_parts.append(f"Rows: {row_count}")

        # Get column info
        columns = con.execute(f'DESCRIBE "{table_name}"').fetchall()
        output_parts.append(f"\nColumns ({len(columns)}):")
        output_parts.append(f"{'Name':<30} {'Type':<15} {'Nullable'}")
        output_parts.append(f"{'-' * 30} {'-' * 15} {'-' * 8}")
        for col in columns:
            col_name, col_type, nullable = col[0], col[1], col[2]
            output_parts.append(f"{col_name:<30} {col_type:<15} {nullable}")

        # Get non-null counts per column
        col_names = [col[0] for col in columns]
        non_null_parts = []
        for c in col_names:
            non_null_parts.append(f'COUNT("{c}") as "{c}"')
        non_null_sql = f'SELECT {", ".join(non_null_parts)} FROM "{table_name}"'
        try:
            non_null_counts = con.execute(non_null_sql).fetchone()
            output_parts.append("\nNon-null counts:")
            for i, c in enumerate(col_names):
                output_parts.append(f"  {c}: {non_null_counts[i]} / {row_count}")
        except duckdb.Error as exc:
            output_parts.append(f"Column counts unavailable: {exc}")

        # Sample data (first 5 rows)
        output_parts.append("\nSample data (first 5 rows):")
        sample = con.execute(f'SELECT * FROM "{table_name}" LIMIT 5').fetchall()
        header = [col[0] for col in columns]
        output_parts.append("  " + " | ".join(header))
        for row in sample:
            output_parts.append("  " + " | ".join(str(v) for v in row))

    result = "\n".join(output_parts)
    print(result)
    return result


def action_query(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    table_map: dict[str, str],
    output_file: str | None = None,
) -> str:
    """Execute a SQL query and return/export results."""
    statements = con.extract_statements(sql)
    if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
        raise ValueError("analysis_select_only")
    result = con.execute(sql)
    columns = [desc[0] for desc in result.description]
    rows = result.fetchmany(10001)
    if len(rows) > 10000:
        raise ValueError("analysis_result_limit_10000")

    # Format output
    if output_file:
        return _export_results(columns, rows, output_file)

    # Print as table
    return _format_table(columns, rows)


def _format_table(columns: list[str], rows: list[tuple]) -> str:
    """Format query results as a readable table."""
    if not rows:
        msg = "Query returned 0 rows."
        print(msg)
        return msg

    # Calculate column widths
    col_widths = [len(str(c)) for c in columns]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    # Cap column width
    max_width = 40
    col_widths = [min(w, max_width) for w in col_widths]

    # Build table
    parts = []
    header = " | ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(columns))
    separator = "-+-".join("-" * col_widths[i] for i in range(len(columns)))
    parts.append(header)
    parts.append(separator)
    for row in rows:
        row_str = " | ".join(
            str(v)[:max_width].ljust(col_widths[i]) for i, v in enumerate(row)
        )
        parts.append(row_str)

    parts.append(f"\n({len(rows)} rows)")
    result = "\n".join(parts)
    print(result)
    return result


def _export_results(columns: list[str], rows: list[tuple], output_file: str) -> str:
    """Export query results to a file (CSV, JSON, or Markdown)."""
    output_file = str(safe_path(output_file, output=True))
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    ext = os.path.splitext(output_file)[1].lower()

    if ext == ".csv":
        import csv

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            def safe_cell(value):
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                    return chr(39) + value
                return value
            writer.writerow([safe_cell(c) for c in columns])
            writer.writerows([safe_cell(v) for v in row] for row in rows)

    elif ext == ".json":
        records = []
        for row in rows:
            record = {}
            for i, col in enumerate(columns):
                val = row[i]
                # Handle non-JSON-serializable types
                if hasattr(val, "isoformat"):
                    val = val.isoformat()
                elif isinstance(val, (bytes, bytearray)):
                    val = val.hex()
                record[col] = val
            records.append(record)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False, default=str)

    elif ext == ".md":
        with open(output_file, "w", encoding="utf-8") as f:
            # Header
            f.write("| " + " | ".join(columns) + " |\n")
            f.write("| " + " | ".join("---" for _ in columns) + " |\n")
            # Rows
            for row in rows:
                f.write(
                    "| " + " | ".join(str(v).replace("|", "\\|") for v in row) + " |\n"
                )
    else:
        msg = f"Unsupported output format: {ext}. Use .csv, .json, or .md"
        print(msg)
        raise ValueError(msg)

    msg = f"Results exported to {output_file} ({len(rows)} rows)"
    print(msg)
    return msg


def action_summary(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    table_map: dict[str, str],
) -> str:
    """Generate statistical summary for a table."""
    # Resolve table name
    resolved = table_map.get(table_name, table_name)
    if resolved not in table_map.values():
        raise ValueError('unknown_analysis_table')

    try:
        columns = con.execute(f'DESCRIBE "{resolved}"').fetchall()
    except duckdb.Error:
        available = ", ".join(f'"{t}" ({o})' for o, t in table_map.items())
        msg = f"Table '{table_name}' not found. Available tables: {available}"
        print(msg)
        return msg

    row_count = con.execute(f'SELECT COUNT(*) FROM "{resolved}"').fetchone()[0]

    output_parts = []
    output_parts.append(f"\nStatistical Summary: {table_name}")
    output_parts.append(f"Total rows: {row_count}")
    output_parts.append(f"{'=' * 70}")

    numeric_types = {
        "BIGINT",
        "INTEGER",
        "SMALLINT",
        "TINYINT",
        "DOUBLE",
        "FLOAT",
        "DECIMAL",
        "HUGEINT",
        "REAL",
        "NUMERIC",
    }

    for col in columns:
        col_name, col_type = col[0], col[1].upper()
        output_parts.append(f"\n--- {col_name} ({col[1]}) ---")

        # Check base type (strip parameterized parts)
        base_type = re.sub(r"\(.*\)", "", col_type).strip()

        if base_type in numeric_types:
            try:
                stats = con.execute(f"""
                    SELECT
                        COUNT("{col_name}") as count,
                        AVG("{col_name}")::DOUBLE as mean,
                        STDDEV("{col_name}")::DOUBLE as std,
                        MIN("{col_name}") as min,
                        QUANTILE_CONT("{col_name}", 0.25) as q25,
                        MEDIAN("{col_name}") as median,
                        QUANTILE_CONT("{col_name}", 0.75) as q75,
                        MAX("{col_name}") as max,
                        COUNT(*) - COUNT("{col_name}") as null_count
                    FROM "{resolved}"
                """).fetchone()
                labels = [
                    "count",
                    "mean",
                    "std",
                    "min",
                    "25%",
                    "50%",
                    "75%",
                    "max",
                    "nulls",
                ]
                for label, val in zip(labels, stats):
                    if isinstance(val, float):
                        output_parts.append(f"  {label:<8}: {val:,.4f}")
                    else:
                        output_parts.append(f"  {label:<8}: {val}")
            except duckdb.Error as e:
                output_parts.append(f"  Error computing stats: {e}")
        else:
            try:
                stats = con.execute(f"""
                    SELECT
                        COUNT("{col_name}") as count,
                        COUNT(DISTINCT "{col_name}") as unique_count,
                        MODE("{col_name}") as mode_val,
                        COUNT(*) - COUNT("{col_name}") as null_count
                    FROM "{resolved}"
                """).fetchone()
                output_parts.append(f"  count   : {stats[0]}")
                output_parts.append(f"  unique  : {stats[1]}")
                output_parts.append(f"  top     : {stats[2]}")
                output_parts.append(f"  nulls   : {stats[3]}")

                # Show top 5 values
                top_vals = con.execute(f"""
                    SELECT "{col_name}", COUNT(*) as freq
                    FROM "{resolved}"
                    WHERE "{col_name}" IS NOT NULL
                    GROUP BY "{col_name}"
                    ORDER BY freq DESC
                    LIMIT 5
                """).fetchall()
                if top_vals:
                    output_parts.append("  top values:")
                    for val, freq in top_vals:
                        pct = (freq / row_count * 100) if row_count > 0 else 0
                        output_parts.append(f"    {val}: {freq} ({pct:.1f}%)")
            except duckdb.Error as e:
                output_parts.append(f"  Error computing stats: {e}")

    result = "\n".join(output_parts)
    print(result)
    return result


def main():
    parser = argparse.ArgumentParser(description="Analyze Excel/CSV files using DuckDB")
    parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="Paths to Excel (.xlsx/.xls) or CSV files",
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["inspect", "query", "summary"],
        help="Action to perform: inspect, query, or summary",
    )
    parser.add_argument(
        "--sql",
        type=str,
        default=None,
        help="SQL query to execute (required for 'query' action)",
    )
    parser.add_argument(
        "--table",
        type=str,
        default=None,
        help="Table name for summary (required for 'summary' action)",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Path to export results (CSV/JSON/MD)",
    )
    args = parser.parse_args()

    # Validate arguments
    if args.action == "query" and not args.sql:
        parser.error("--sql is required for 'query' action")
    if args.action == "summary" and not args.table:
        parser.error("--table is required for 'summary' action")

    # ponytail: no cache; re-import bounded inputs to avoid shared mutable SQL state.
    con = duckdb.connect(":memory:", config={"memory_limit": "128MB", "threads": "1",
        "autoinstall_known_extensions": "false", "autoload_known_extensions": "false",
        "max_temp_directory_size": "0B"})
    table_map = load_files(con, args.files)

    # Perform action
    if args.action == "inspect":
        action_inspect(con, table_map)
    elif args.action == "query":
        action_query(con, args.sql, table_map, args.output_file)
    elif args.action == "summary":
        action_summary(con, args.table, table_map)

    con.close()


if __name__ == "__main__":
    main()
