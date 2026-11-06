"""Break clean data on purpose and check that the validator notices."""
import copy
from datetime import timedelta
from decimal import Decimal

from tuition_synth.config import Config
from tuition_synth.transactions import build_core
from tuition_synth.validate import run_all

CLEAN = build_core(Config(scale=0.05))


def broken():
    return copy.deepcopy(CLEAN)


def found(tables, check, table, row_id):
    return any(i.check == check and i.table == table and i.row_id == row_id for i in run_all(tables))


def test_clean_data_has_no_issues():
    assert run_all(CLEAN) == []


def test_detects_duplicate_invoice():
    t = broken()
    original = next(i for i in t["invoice"] if i["status"] == "ISSUED")
    dup = dict(original, invoice_id=original["invoice_id"][:-6] + "000099")
    t["invoice"].append(dup)
    assert found(t, "duplicate_invoice", "invoice", dup["invoice_id"])


def test_detects_wrong_line_amount_and_total_mismatch():
    t = broken()
    line = t["invoice_line"][0]
    line["amount"] = line["amount"] + Decimal("500.00")
    assert found(t, "line_amount_mismatch", "invoice_line", line["invoice_line_id"])
    assert found(t, "invoice_total_mismatch", "invoice", line["invoice_id"])


def test_detects_broken_foreign_key():
    t = broken()
    t["invoice"][0]["student_id"] = "STU-999999"
    assert found(t, "fk_missing", "invoice", t["invoice"][0]["invoice_id"])


def test_detects_invalid_enum_and_missing_required_value():
    t = broken()
    t["enrollment"][0]["status"] = "ACTIVE"
    t["student"][0]["email"] = None
    issues = {(i.check, i.table) for i in run_all(t)}
    assert ("enum", "enrollment") in issues and ("required", "student") in issues


def test_detects_duplicate_primary_key():
    t = broken()
    t["program"].append(dict(t["program"][0]))
    assert any(i.check == "pk_duplicate" and i.table == "program" for i in run_all(t))


def test_detects_status_changed_without_history():
    t = broken()
    enr = next(e for e in t["enrollment"] if e["status"] == "COMPLETED")
    enr["status"] = "ENROLLED"
    assert found(t, "lifecycle_state_mismatch", "enrollment", enr["enrollment_id"])


def test_detects_illegal_transition():
    t = broken()
    ev = next(e for e in t["status_event"] if e["to_status"] == "COMPLETED")
    ev["to_status"] = "ISSUED"  # enrollment can never move to an invoice status
    assert any(i.check == "lifecycle_transition" for i in run_all(t))


def test_detects_withdrawal_without_date():
    t = broken()
    enr = next(e for e in t["enrollment"] if e["status"] == "WITHDRAWN")
    enr["withdrawn_on"] = None
    assert found(t, "withdrawal_date", "enrollment", enr["enrollment_id"])


def test_detects_wrong_due_date_and_line_sign():
    t = broken()
    t["invoice"][0]["due_date"] += timedelta(days=3)
    t["invoice_line"][1]["amount"] = -t["invoice_line"][1]["amount"]
    checks = {i.check for i in run_all(t)}
    assert "invoice_due_date" in checks and "line_sign" in checks
