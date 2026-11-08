"""Dataset export (CSV, JSON, SQL, gzip) with a stable byte format, so checksums are reproducible."""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from .anomalies import GROUND_TRUTH_COLUMNS
from .ddl import schema_sql, seed_sql
from .schema import TABLES


def format_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ whole dataset
def csv_bytes(columns: list, rows: list[dict]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([format_value(row[c]) for c in columns])
    return buf.getvalue().encode("utf-8")


def _write(path: Path, data: bytes, gzip_it: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if gzip_it:
        # mtime=0 and no file name keep the compressed bytes identical between runs
        with path.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as gz:
            gz.write(data)
    else:
        path.write_bytes(data)


def json_bytes(columns: list, rows: list[dict]) -> bytes:
    lines = [json.dumps({c: (None if row[c] is None else (row[c] if isinstance(row[c], int) else format_value(row[c])))
                         for c in columns}, ensure_ascii=False) for row in rows]
    return ("[\n" + ",\n".join(lines) + "\n]\n").encode("utf-8")


def write_dataset(out: Path, tables: dict, truth: list[dict], formats: set, gzip_csv: bool, meta: dict) -> dict:
    """Write every table (and the ground truth) in the requested formats; return the manifest."""
    files = []

    def add(path: Path, name: str, rows: int, raw: bytes, gz: bool = False) -> None:
        _write(path, raw, gzip_it=gz)
        files.append({"path": path.relative_to(out).as_posix(), "table": name, "rows": rows,
                      "sha256": hashlib.sha256(raw).hexdigest(), "bytes": path.stat().st_size})

    suffix = ".csv.gz" if gzip_csv else ".csv"
    for name, rows in tables.items():
        cols = TABLES[name].field_names
        if "csv" in formats:
            add(out / "csv" / f"{name}{suffix}", name, len(rows), csv_bytes(cols, rows), gz=gzip_csv)
        if "json" in formats:
            add(out / "json" / f"{name}.json", name, len(rows), json_bytes(cols, rows))
    if truth:
        add(out / "ground_truth.csv", "ground_truth", len(truth), csv_bytes(GROUND_TRUTH_COLUMNS, truth))
        add(out / "ground_truth.json", "ground_truth", len(truth), json_bytes(GROUND_TRUTH_COLUMNS, truth))
    if "sql" in formats:
        add(out / "sql" / "schema.sql", "schema", 0, schema_sql().encode("utf-8"))
        add(out / "sql" / "seed.sql", "seed", sum(len(r) for r in tables.values()), seed_sql(tables).encode("utf-8"))

    manifest = {**meta, "files": files}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest
