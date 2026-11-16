"""Execute generated SQL on a dedicated PostgreSQL read-only dataset."""

import json
import re
import threading
from contextlib import contextmanager

import psycopg
import sqlglot
from psycopg.rows import dict_row
from sqlglot import exp
from sqlglot.optimizer.scope import Scope, traverse_scope

from platform_api.core.errors import (
    BadRequestError,
    ForbiddenError,
    ServiceUnavailableError,
)

_SLOTS = threading.BoundedSemaphore(4)
_FUNCTIONS = frozenset(
    {
        "ABS",
        "AVG",
        "CEIL",
        "CEILING",
        "COALESCE",
        "COUNT",
        "DATE_TRUNC",
        "EXTRACT",
        "FLOOR",
        "GREATEST",
        "LEAST",
        "LENGTH",
        "LOWER",
        "MAX",
        "MIN",
        "NULLIF",
        "ROUND",
        "SUM",
        "UPPER",
        "SUBSTRING",
        "TRIM",
        "CAST",
        "CURRENT_DATE",
        "CURRENT_TIMESTAMP",
        "ROW_NUMBER",
        "RANK",
        "DENSE_RANK",
        "LAG",
        "LEAD",
        "CASE",
        "IF",
        "EXISTS",
        "TIMESTAMP_TRUNC",
        "DATE_DIFF",
        "DATE_ADD",
        "DATE_SUB",
    }
)


def validated_sql(query, source):
    try:
        statements = sqlglot.parse(query, read="postgres")
        if len(statements) != 1 or not isinstance(
            statements[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)
        ):
            raise ValueError()
        tree = statements[0]
        if len(list(tree.walk())) > 1000:
            raise ValueError()
        cte_references = {
            id(node)
            for scope in traverse_scope(tree)
            for node, resolved in scope.selected_sources.values()
            if isinstance(node, exp.Table) and isinstance(resolved, Scope)
        }
        for node in tree.walk():
            if isinstance(
                node,
                (
                    exp.DML,
                    exp.DDL,
                    exp.Into,
                    exp.Lock,
                    exp.Command,
                    exp.Dot,
                    exp.Parameter,
                    exp.Placeholder,
                ),
            ):
                raise ValueError()
            if isinstance(node, exp.Func):
                name = (
                    node.name.upper()
                    if isinstance(node, exp.Anonymous)
                    else node.sql_name().upper()
                )
                if name not in _FUNCTIONS:
                    raise ValueError()
            if isinstance(node, exp.Cast) and getattr(
                node.to.this, "value", None
            ) not in {
                "TEXT",
                "VARCHAR",
                "INT",
                "BIGINT",
                "SMALLINT",
                "DOUBLE",
                "FLOAT",
                "BOOLEAN",
                "DATE",
                "TIMESTAMP",
                "TIMESTAMPTZ",
                "DECIMAL",
                "DECIMAL128",
                "DECIMAL256",
            }:
                raise ValueError()
            if isinstance(node, exp.Table):
                if not isinstance(node.this, exp.Identifier) or node.catalog:
                    raise ValueError()
                if not node.db and id(node) in cte_references:
                    continue
                if node.name not in source.tables or node.db not in (
                    "",
                    source.schema_name,
                ):
                    raise ValueError()
                node.set("db", exp.to_identifier(source.schema_name, quoted=True))
                node.set("this", exp.to_identifier(node.name, quoted=True))
        return tree.sql(dialect="postgres")
    except (ValueError, RecursionError, sqlglot.errors.SqlglotError):
        raise BadRequestError(
            code="assistant_sql_denied",
            message="只允许授权表上的单条只读查询及支持的分析函数。",
        ) from None


@contextmanager
def connection(source):
    if not _SLOTS.acquire(blocking=False):
        raise ServiceUnavailableError(
            code="assistant_query_busy", message="查询繁忙，请稍后重试。"
        )
    try:
        with psycopg.connect(
            source.dsn, connect_timeout=3, row_factory=dict_row
        ) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '2000ms'")
            conn.execute("SET LOCAL lock_timeout = '500ms'")
            conn.execute("SET LOCAL search_path = pg_catalog")
            conn.execute("SET LOCAL work_mem = '4MB'")
            role = conn.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            ).fetchone()
            membership = conn.execute(
                "SELECT 1 FROM pg_auth_members WHERE member = current_user::regrole LIMIT 1"
            ).fetchone()
            if not role or any(role.values()) or membership:
                raise ForbiddenError(
                    code="assistant_database_role_unsafe",
                    message="数据源必须使用独立的最小权限只读账号。",
                )
            if conn.execute(
                "SELECT has_schema_privilege(current_user, %s, 'CREATE') AS allowed",
                (source.schema_name,),
            ).fetchone()["allowed"]:
                raise ForbiddenError(
                    code="assistant_database_role_unsafe",
                    message="只读账号不得拥有查询 schema 的创建权限。",
                )
            if not source.tables:
                source.tables = [
                    r["name"]
                    for r in conn.execute(
                        "SELECT c.relname AS name FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind IN ('r','v','m','p') AND has_table_privilege(current_user,c.oid,'SELECT') ORDER BY c.relname",
                        (source.schema_name,),
                    ).fetchall()
                ]
            if any(
                not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", table)
                for table in source.tables
            ):
                raise ValueError("invalid configured table")
            rights = conn.execute(
                "SELECT has_table_privilege(current_user, relation, 'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') AS writable, has_table_privilege(current_user, relation, 'SELECT') AS readable FROM unnest(%s::text[]) AS relation",
                ([source.schema_name + "." + table for table in source.tables],),
            ).fetchall()
            if any(row["writable"] or not row["readable"] for row in rights):
                raise ForbiddenError(
                    code="assistant_database_role_unsafe",
                    message="只读账号的表授权不符合读取约定。",
                )
            yield conn
    except (psycopg.Error, ValueError):
        # PostgreSQL diagnostics can contain SQL literals and connection secrets.
        raise ServiceUnavailableError(
            code="assistant_database_unavailable",
            message="只读数据源不可用，或查询超时/语法不受支持。",
        ) from None
    finally:
        _SLOTS.release()


def schema(source, table_names=None, table_offset=0):
    with connection(source) as conn:
        if table_names and any(name not in source.tables for name in table_names):
            raise ForbiddenError(
                code="assistant_table_denied", message="未获准读取所请求的表结构。"
            )
        page = source.tables[table_offset : table_offset + 100]
        selected = table_names or page[:20]
        columns = conn.execute(
            "SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = %s AND table_name = ANY(%s) ORDER BY table_name, ordinal_position LIMIT 501",
            (source.schema_name, selected),
        ).fetchall()
        relations = conn.execute(
            "SELECT child.relname AS table_name, ca.attname AS column_name, parent.relname AS foreign_table, pa.attname AS foreign_column FROM pg_constraint c JOIN pg_class child ON child.oid=c.conrelid JOIN pg_namespace ns ON ns.oid=child.relnamespace JOIN pg_class parent ON parent.oid=c.confrelid JOIN pg_namespace pns ON pns.oid=parent.relnamespace JOIN LATERAL unnest(c.conkey,c.confkey) AS keys(child_att,parent_att) ON true JOIN pg_attribute ca ON ca.attrelid=child.oid AND ca.attnum=keys.child_att JOIN pg_attribute pa ON pa.attrelid=parent.oid AND pa.attnum=keys.parent_att WHERE c.contype='f' AND ns.nspname=%s AND pns.nspname=%s AND child.relname=ANY(%s) AND parent.relname=ANY(%s) ORDER BY child.relname, ca.attnum LIMIT 101",
            (source.schema_name, source.schema_name, selected, source.tables),
        ).fetchall()
    return {
        "dialect": "postgresql",
        "tables": page,
        "total_tables": len(source.tables),
        "next_table_offset": table_offset + 100
        if table_offset + 100 < len(source.tables)
        else None,
        "schema_tables": selected,
        "columns": columns[:500],
        "relations": relations[:100],
        "truncated": len(columns) > 500 or len(relations) > 100,
        "revision": source.revision,
        "sample_rows": False,
    }


def query(source, sql):
    with connection(source) as conn:
        statement = validated_sql(sql, source)
        with conn.cursor(name="assistant_read") as cursor:
            cursor.execute(statement)
            rows = cursor.fetchmany(101)
    encoded_rows, size = [], 0
    truncated = len(rows) > 100
    for row in rows[:100]:
        encoded = json.dumps(row, ensure_ascii=False, default=str)
        if size + len(encoded.encode()) > 64000:
            truncated = True
            break
        encoded_rows.append(json.loads(encoded))
        size += len(encoded.encode())
    return {
        "rows": encoded_rows,
        "row_count": len(encoded_rows),
        "truncated": truncated,
        "revision": source.revision,
        "limit": 100,
    }
