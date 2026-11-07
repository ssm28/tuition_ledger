"""Exports (CSV / JSON / SQL / gzip), manifest, summary and reproducibility."""
import gzip
import hashlib
import json
import sqlite3
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from tuition_synth.cli import main
from tuition_synth.config import Config
from tuition_synth.dataset import generate, reproduce
from tuition_synth.schema import TABLES

CFG = Config(scale=0.02)
TMP = tempfile.TemporaryDirectory()
OUT = Path(TMP.name) / "starter"
RESULT = generate(CFG, OUT, {"csv", "json", "sql"})
TABLES_X = RESULT["tables"]


def test_run_is_ok_and_has_the_expected_files():
    assert RESULT["ok"]
    names = {f["path"] for f in RESULT["manifest"]["files"]}
    assert "ground_truth.csv" in names and "sql/schema.sql" in names and "csv/student.csv" in names
    assert (OUT / "VALIDATION_SUMMARY.md").exists() and (OUT / "MANIFEST.json").exists()


def test_manifest_matches_files_on_disk():
    for f in RESULT["manifest"]["files"]:
        if f["path"].endswith((".csv", ".json", ".sql")):
            data = (OUT / f["path"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == f["sha256"], f["path"]
            if f["path"].startswith("csv/") or f["path"] == "ground_truth.csv":
                assert len(data.decode().splitlines()) - 1 == f["rows"], f["path"]


def test_json_export_has_schema_columns_and_row_counts():
    for name, rows in TABLES_X.items():
        data = json.loads((OUT / "json" / f"{name}.json").read_text(encoding="utf-8"))
        assert len(data) == len(rows)
        assert list(data[0]) == TABLES[name].field_names


def test_sql_seed_loads_with_foreign_keys_and_matches_the_data():
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript((OUT / "sql" / "schema.sql").read_text(encoding="utf-8"))
    db.executescript((OUT / "sql" / "seed.sql").read_text(encoding="utf-8"))
    for name, rows in TABLES_X.items():
        assert db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] == len(rows), name
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    # the money still reconciles inside SQL: invoice totals equal the sum of their lines
    bad = db.execute("""SELECT COUNT(*) FROM invoice i
                        JOIN (SELECT invoice_id, SUM(amount) s FROM invoice_line GROUP BY invoice_id) l
                          ON l.invoice_id = i.invoice_id WHERE ABS(i.total_amount - l.s) > 0.005""").fetchone()[0]
    assert bad == 0
    total = db.execute("SELECT SUM(total_amount) FROM invoice").fetchone()[0]
    assert abs(Decimal(str(total)) - sum(i["total_amount"] for i in TABLES_X["invoice"])) < Decimal("0.01")


def test_sql_constraints_reject_bad_data():
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript((OUT / "sql" / "schema.sql").read_text(encoding="utf-8"))
    db.executescript((OUT / "sql" / "seed.sql").read_text(encoding="utf-8"))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE invoice SET status = 'NOT_A_STATUS' WHERE rowid = 1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE invoice SET student_id = 'STU-999999' WHERE rowid = 1")


def test_gzip_csv_is_deterministic_and_decompresses_to_the_same_content():
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        generate(CFG, Path(d1), {"csv"}, gzip_csv=True)
        generate(CFG, Path(d2), {"csv"}, gzip_csv=True)
        a, b = (Path(d1) / "csv" / "student.csv.gz").read_bytes(), (Path(d2) / "csv" / "student.csv.gz").read_bytes()
        assert a == b
        assert gzip.decompress(a) == (OUT / "csv" / "student.csv").read_bytes()


def test_validation_summary_reports_the_key_numbers():
    text = (OUT / "VALIDATION_SUMMARY.md").read_text(encoding="utf-8")
    assert "0 issue(s)" in text and "15/15" in text and "**0**" in text


def test_reproducibility_two_runs_match_for_every_file():
    rows = reproduce(CFG, {"csv", "sql"})
    assert rows and all(r["match"] for r in rows)


def test_different_seed_changes_the_data():
    with tempfile.TemporaryDirectory() as d:
        other = generate(Config(seed=5, scale=0.02), Path(d), {"csv"})
    a = {f["path"]: f["sha256"] for f in RESULT["manifest"]["files"]}
    b = {f["path"]: f["sha256"] for f in other["manifest"]["files"]}
    assert a["csv/student.csv"] != b["csv/student.csv"]


def test_cli_generate_reproduce_and_bad_format():
    with tempfile.TemporaryDirectory() as d:
        assert main(["generate", "--scale", "0.02", "--formats", "csv,sql", "--out", d]) == 0
        report = Path(d) / "repro.md"
        assert main(["reproduce", "--scale", "0.02", "--report", str(report)]) == 0
        assert "IDENTICAL" in report.read_text(encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["generate", "--formats", "xml"])
