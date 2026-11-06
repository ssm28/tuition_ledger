"""CSV export with a stable byte format, so checksums are reproducible."""
from __future__ import annotations

import csv
import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

from .schema import TABLES


def format_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def write_csv(path: Path, table: str, rows: list[dict]) -> None:
    """Write rows with the schema's column order, UTF-8, LF line endings."""
    columns = TABLES[table].field_names
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([format_value(row[c]) for c in columns])


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
