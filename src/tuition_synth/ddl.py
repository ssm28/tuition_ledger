"""SQL schema (CREATE TABLE) and seed data (INSERT) generated from schema.py. Written for SQLite."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from .schema import TABLES, Table

_SQL_TYPES = {"string": "TEXT", "int": "INTEGER", "decimal": "NUMERIC", "date": "TEXT"}


def _quote(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def sql_value(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return _quote(value.isoformat())
    return _quote(str(value))


def create_table_sql(table: Table) -> str:
    cols = []
    for f in table.fields:
        parts = [f"  {f.name} {_SQL_TYPES[f.type]}"]
        if f.name == table.pk:
            parts.append("PRIMARY KEY")
        elif f.required:
            parts.append("NOT NULL")
        if f.unique and f.name != table.pk:
            parts.append("UNIQUE")
        if f.allowed:
            parts.append("CHECK ({} IN ({}))".format(f.name, ", ".join(_quote(a) for a in f.allowed)))
        cols.append(" ".join(parts))
    for f in table.foreign_keys():
        parent, column = f.fk.split(".")
        cols.append(f"  FOREIGN KEY ({f.name}) REFERENCES {parent}({column})")
    return f"CREATE TABLE {table.name} (\n" + ",\n".join(cols) + "\n);"


def schema_sql() -> str:
    head = "-- Generated from schema.py. Tables are listed parents first.\n"
    return head + "\n\n".join(create_table_sql(t) for t in TABLES.values()) + "\n"


def seed_sql(tables: dict, batch: int = 500) -> str:
    out = ["-- Seed data (synthetic). Load schema.sql first. Written for SQLite.", "PRAGMA foreign_keys = ON;", "BEGIN;"]
    for name, spec in TABLES.items():
        rows = tables.get(name)
        if not rows:
            continue
        cols = ", ".join(spec.field_names)
        for i in range(0, len(rows), batch):
            values = ",\n".join("(" + ", ".join(sql_value(r[c]) for c in spec.field_names) + ")"
                                for r in rows[i:i + batch])
            out.append(f"INSERT INTO {name} ({cols}) VALUES\n{values};")
    out.append("COMMIT;")
    return "\n".join(out) + "\n"
