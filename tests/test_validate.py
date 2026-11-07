"""Break clean data on purpose and check that the validator notices."""
import copy
from datetime import timedelta
from decimal import Decimal

from tuition_synth.config import Config
from tuition_synth.pipeline import build_all
from tuition_synth.validate import run_all

CLEAN = build_all(Config(scale=0.05))


def broken():
    return copy.deepcopy(CLEAN)


def found(tables, check, table, row_id):
    return any(i.check == check and i.table == table and i.row_id == row_id for i in run_all(tables))


def test_clean_data_has_no_issues():
    assert run_all(CLEAN) == []


def test_detects_duplicate_invoice():
    t = broken()
    original = next(i for i in t["invoice"] if i["status"] == "PAID")
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


# ---------------------------------------------------------------- new checks
def test_detects_allocation_beyond_payment_amount():
    t = broken()
    alloc = t["payment_allocation"][-1]
    alloc["amount"] += Decimal("100000.00")
    assert found(t, "allocation_exceeds_payment", "payment_allocation", alloc["allocation_id"])


def test_detects_scholarship_exceeding_fees():
    t = broken()
    sch = t["scholarship"][0]
    inv = next(i for i in t["invoice"]
               if i["student_id"] == sch["student_id"] and i["term_id"] == sch["term_id"])
    tuition = next(ln for ln in t["invoice_line"]
                   if ln["line_type"] == "TUITION" and ln["invoice_id"] == inv["invoice_id"])
    sch["award_amount"] = tuition["amount"] + Decimal("1.00")
    assert found(t, "scholarship_exceeds_fees", "scholarship", sch["scholarship_id"])


def test_detects_ineligible_scholarship():
    t = broken()
    sch = t["scholarship"][0]
    student = next(s for s in t["student"] if s["student_id"] == sch["student_id"])
    student["cgpa"] = Decimal("1.00")
    assert found(t, "scholarship_not_eligible", "scholarship", sch["scholarship_id"])


def test_detects_missing_late_fee():
    t = broken()
    fee = next(ln for ln in t["invoice_line"] if ln["line_type"] == "LATE_FEE")
    t["invoice_line"].remove(fee)
    assert found(t, "late_fee_missing", "invoice", fee["invoice_id"])


def test_detects_wrong_invoice_status():
    t = broken()
    inv = next(i for i in t["invoice"] if i["status"] == "PAID")
    inv["status"] = "OVERDUE"
    assert found(t, "invoice_status", "invoice", inv["invoice_id"])


def test_detects_allocation_for_someone_elses_payment():
    t = broken()
    pay = t["payment"][0]
    other = next(s for s in t["student"] if s["student_id"] != pay["student_id"])
    pay["student_id"] = other["student_id"]
    assert any(i.check == "allocation_student_mismatch" for i in run_all(t))
