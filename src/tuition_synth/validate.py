"""Validator: re-checks generated tables against the schema and the business rules.

It only looks at the tables. It never reads ground_truth, so it cannot "cheat".
Each problem found is an Issue with a check name, a table and a row ID, which
lets us later score the validator against the injected anomalies.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from . import ids
from .config import AS_OF_DATE
from .rules import (
    LATE_FEE_AMOUNT, award_amount, grace_end, is_eligible, late_fee_date, line_net_dues,
)
from .schema import LIFECYCLES, TABLES

_PY_TYPES = {"string": str, "int": int, "decimal": Decimal, "date": date}
_CHARGE_TYPES = ("TUITION", "LAB", "LIBRARY", "TECHNOLOGY", "ACTIVITY", "LATE_FEE")
_CREDIT_TYPES = ("SCHOLARSHIP_CREDIT", "WAIVER")


@dataclass(frozen=True)
class Issue:
    check: str
    table: str
    row_id: str
    detail: str = ""


# ------------------------------------------------------------------ structure
def check_structure(tables: dict) -> list[Issue]:
    """Columns, primary keys, ID formats, required fields, types, enums, foreign keys."""
    issues: list[Issue] = []
    for name, rows in tables.items():
        spec = TABLES[name]
        seen = set()
        for row in rows:
            rid = str(row.get(spec.pk))
            if list(row) != spec.field_names:
                issues.append(Issue("columns", name, rid, "columns differ from schema"))
                continue
            if row[spec.pk] in seen:
                issues.append(Issue("pk_duplicate", name, rid))
            seen.add(row[spec.pk])
            if not ids.is_valid(name, rid):
                issues.append(Issue("pk_format", name, rid))
            for f in spec.fields:
                v = row[f.name]
                if v is None or v == "":
                    if f.required:
                        issues.append(Issue("required", name, rid, f.name))
                    continue
                ok = isinstance(v, _PY_TYPES[f.type]) and not isinstance(v, bool)
                if not ok:
                    issues.append(Issue("type", name, rid, f.name))
                elif f.allowed and v not in f.allowed:
                    issues.append(Issue("enum", name, rid, f"{f.name}={v}"))

    keys = {n: {r[TABLES[n].pk] for r in rows} for n, rows in tables.items()}
    for name, rows in tables.items():
        spec = TABLES[name]
        for f in spec.foreign_keys():
            parent, _col = f.fk.split(".")
            for row in rows:
                v = row.get(f.name)
                if v is not None and v not in keys.get(parent, set()):
                    issues.append(Issue("fk_missing", name, str(row[spec.pk]), f"{f.name}={v}"))
    return issues


# ---------------------------------------------------------- enrollments/invoices
def check_enrollments(tables: dict) -> list[Issue]:
    issues: list[Issue] = []
    per_key = defaultdict(list)
    for e in tables.get("enrollment", []):
        per_key[(e["student_id"], e["term_id"])].append(e["enrollment_id"])
        wd = e["withdrawn_on"]
        if (e["status"] == "WITHDRAWN") != (wd is not None):
            issues.append(Issue("withdrawal_date", "enrollment", e["enrollment_id"],
                                "withdrawn_on must be set exactly when status is WITHDRAWN"))
        if wd is not None and wd < e["enrolled_on"]:
            issues.append(Issue("withdrawal_date", "enrollment", e["enrollment_id"], "before enrolled_on"))
    for eids in per_key.values():
        for dup in sorted(eids)[1:]:
            issues.append(Issue("duplicate_enrollment", "enrollment", dup))
    return issues


def check_invoices(tables: dict) -> list[Issue]:
    """Totals, dates, enrollment match, duplicate invoices and fee-line correctness."""
    issues: list[Issue] = []
    enrollments = {e["enrollment_id"]: e for e in tables.get("enrollment", [])}
    terms = {t["term_id"]: t for t in tables.get("term", [])}
    schedules = {f["fee_schedule_id"]: f for f in tables.get("fee_schedule", [])}
    invoices = {i["invoice_id"]: i for i in tables.get("invoice", [])}
    lines_by_invoice = defaultdict(list)
    for ln in tables.get("invoice_line", []):
        lines_by_invoice[ln["invoice_id"]].append(ln)

    open_by_enrollment = defaultdict(list)
    for inv in invoices.values():
        iid = inv["invoice_id"]
        enr = enrollments.get(inv["enrollment_id"])
        if enr and (enr["student_id"] != inv["student_id"] or enr["term_id"] != inv["term_id"]):
            issues.append(Issue("invoice_enrollment_mismatch", "invoice", iid))
        if inv["status"] != "CANCELLED":
            open_by_enrollment[inv["enrollment_id"]].append(iid)
        total = sum((ln["amount"] for ln in lines_by_invoice[iid]), Decimal(0))
        if total != inv["total_amount"]:
            issues.append(Issue("invoice_total_mismatch", "invoice", iid,
                                f"header {inv['total_amount']} vs lines {total}"))
        term = terms.get(inv["term_id"])
        if term and inv["due_date"] != inv["issue_date"] + timedelta(days=term["invoice_due_days"]):
            issues.append(Issue("invoice_due_date", "invoice", iid))
    for iids in open_by_enrollment.values():
        for dup in sorted(iids)[1:]:
            issues.append(Issue("duplicate_invoice", "invoice", dup,
                                "second active invoice for the same enrollment"))

    for ln in tables.get("invoice_line", []):
        lid, inv = ln["invoice_line_id"], invoices.get(ln["invoice_id"])
        if ln["line_type"] in _CHARGE_TYPES and ln["amount"] <= 0:
            issues.append(Issue("line_sign", "invoice_line", lid))
        if ln["line_type"] in _CREDIT_TYPES and ln["amount"] >= 0:
            issues.append(Issue("line_sign", "invoice_line", lid))
        if inv and ln["line_date"] < inv["issue_date"]:
            issues.append(Issue("line_date", "invoice_line", lid))
        if ln["line_type"] in ("TUITION", "LAB", "LIBRARY", "TECHNOLOGY", "ACTIVITY") and inv:
            fs = schedules.get(ln["fee_schedule_id"])
            enr = enrollments.get(inv["enrollment_id"])
            if fs is None:
                issues.append(Issue("line_fee_schedule_missing", "invoice_line", lid))
                continue
            if fs["fee_type"] != ln["line_type"]:
                issues.append(Issue("line_fee_type", "invoice_line", lid))
            if fs["amount"] != ln["amount"]:
                issues.append(Issue("line_amount_mismatch", "invoice_line", lid,
                                    f"line {ln['amount']} vs schedule {fs['amount']}"))
            if fs["term_id"] != inv["term_id"] or (enr and fs["program_id"] != enr["program_id"]):
                issues.append(Issue("line_wrong_schedule", "invoice_line", lid))
            issue_date = inv["issue_date"]
            if not (fs["effective_from"] <= issue_date
                    and (fs["effective_to"] is None or issue_date <= fs["effective_to"])):
                issues.append(Issue("line_schedule_not_effective", "invoice_line", lid))
    return issues


# ------------------------------------------------------------------ lifecycle
def check_lifecycle(tables: dict) -> list[Issue]:
    """Every status change follows the allowed transitions and the row's status matches the last event."""
    issues: list[Issue] = []
    events = defaultdict(list)
    for ev in tables.get("status_event", []):
        events[(ev["entity_type"], ev["entity_id"])].append(ev)
    for evs in events.values():
        evs.sort(key=lambda e: e["event_id"])

    for etype, allowed in LIFECYCLES.items():
        for row in tables.get(etype, []):
            rid = row[TABLES[etype].pk]
            evs = events.get((etype, rid), [])
            if not evs:
                issues.append(Issue("lifecycle_no_history", etype, rid))
                continue
            prev = None
            for ev in evs:
                if ev["from_status"] != prev:
                    issues.append(Issue("lifecycle_chain", etype, rid, f"{ev['event_id']} starts from {ev['from_status']}"))
                if ev["to_status"] not in allowed.get(prev, ()):
                    issues.append(Issue("lifecycle_transition", etype, rid, f"{prev} -> {ev['to_status']}"))
                prev = ev["to_status"]
            if prev != row["status"]:
                issues.append(Issue("lifecycle_state_mismatch", etype, rid, f"row {row['status']} vs history {prev}"))
    return issues


# ------------------------------------------------------- scholarships / waivers
def check_scholarships(tables: dict) -> list[Issue]:
    """Awards follow the eligibility rules, never exceed fees, and match their invoice credit."""
    issues: list[Issue] = []
    students = {s["student_id"]: s for s in tables.get("student", [])}
    schemes = {e["eligibility_id"]: e for e in tables.get("eligibility", [])}
    lines = {ln["invoice_line_id"]: ln for ln in tables.get("invoice_line", [])}
    invoices = {i["invoice_id"]: i for i in tables.get("invoice", [])}
    active_invoice = {(i["student_id"], i["term_id"]): i for i in invoices.values() if i["status"] != "CANCELLED"}
    tuition = {ln["invoice_id"]: ln["amount"] for ln in lines.values() if ln["line_type"] == "TUITION"}
    credits = defaultdict(list)
    for ln in lines.values():
        if ln["line_type"] == "SCHOLARSHIP_CREDIT":
            credits[ln["scholarship_id"]].append(ln)

    per_term = defaultdict(list)
    for sch in tables.get("scholarship", []):
        sid = sch["scholarship_id"]
        per_term[(sch["student_id"], sch["term_id"])].append(sid)
        scheme, student = schemes.get(sch["eligibility_id"]), students.get(sch["student_id"])
        inv = active_invoice.get((sch["student_id"], sch["term_id"]))
        if scheme and student and not is_eligible(student, scheme, sch["awarded_on"]):
            issues.append(Issue("scholarship_not_eligible", "scholarship", sid))
        if scheme and sch["award_amount"] > scheme["max_award_amount"]:
            issues.append(Issue("scholarship_exceeds_cap", "scholarship", sid))
        if inv is None:
            issues.append(Issue("scholarship_no_invoice", "scholarship", sid))
        else:
            fees = tuition.get(inv["invoice_id"], Decimal(0))
            if sch["award_amount"] > fees:
                issues.append(Issue("scholarship_exceeds_fees", "scholarship", sid,
                                    f"award {sch['award_amount']} vs tuition {fees}"))
            if scheme and sch["award_amount"] != award_amount(scheme, fees) \
                    and sch["award_amount"] <= min(fees, scheme["max_award_amount"]):
                issues.append(Issue("scholarship_amount_mismatch", "scholarship", sid))
        credit = credits.get(sid, [])
        if len(credit) != 1:
            issues.append(Issue("scholarship_credit_line", "scholarship", sid, f"{len(credit)} credit lines"))
        elif credit[0]["amount"] != -sch["award_amount"]:
            issues.append(Issue("scholarship_credit_mismatch", "scholarship", sid))
        elif inv is not None and credit[0]["invoice_id"] != inv["invoice_id"]:
            issues.append(Issue("scholarship_credit_wrong_invoice", "scholarship", sid))
    for sids in per_term.values():
        for dup in sorted(sids)[1:]:
            issues.append(Issue("duplicate_scholarship", "scholarship", dup))

    # waivers must point at a non-tuition fee line of the same invoice and not exceed it
    fee_by_schedule = defaultdict(dict)
    for ln in lines.values():
        if ln["line_type"] in ("LAB", "LIBRARY", "TECHNOLOGY", "ACTIVITY"):
            fee_by_schedule[ln["invoice_id"]][ln["fee_schedule_id"]] = ln
    for ln in lines.values():
        if ln["line_type"] == "WAIVER":
            target = fee_by_schedule[ln["invoice_id"]].get(ln["fee_schedule_id"])
            if target is None:
                issues.append(Issue("waiver_target", "invoice_line", ln["invoice_line_id"]))
            elif -ln["amount"] > target["amount"]:
                issues.append(Issue("waiver_exceeds_fee", "invoice_line", ln["invoice_line_id"]))
    return issues


# ------------------------------------------------------ payments / allocations
def check_payments(tables: dict) -> list[Issue]:
    issues: list[Issue] = []
    payments = {p["payment_id"]: p for p in tables.get("payment", [])}
    lines = {ln["invoice_line_id"]: ln for ln in tables.get("invoice_line", [])}
    invoices = {i["invoice_id"]: i for i in tables.get("invoice", [])}
    lines_by_inv = defaultdict(list)
    for ln in lines.values():
        lines_by_inv[ln["invoice_id"]].append(ln)
    dues = {}
    for inv_lines in lines_by_inv.values():
        dues.update(line_net_dues(inv_lines))

    for p in payments.values():
        if p["amount"] <= 0:
            issues.append(Issue("payment_amount", "payment", p["payment_id"]))

    per_payment, per_line = defaultdict(Decimal), defaultdict(Decimal)
    for a in sorted(tables.get("payment_allocation", []), key=lambda r: r["allocation_id"]):
        aid, pay, ln = a["allocation_id"], payments.get(a["payment_id"]), lines.get(a["invoice_line_id"])
        if a["amount"] <= 0:
            issues.append(Issue("allocation_amount", "payment_allocation", aid))
        if pay and a["allocated_on"] < pay["payment_date"]:
            issues.append(Issue("allocation_date", "payment_allocation", aid, "before payment date"))
        if ln and a["allocated_on"] < ln["line_date"]:
            issues.append(Issue("allocation_date", "payment_allocation", aid, "before line date"))
        if pay and ln:
            inv = invoices.get(ln["invoice_id"])
            if inv and inv["student_id"] != pay["student_id"]:
                issues.append(Issue("allocation_student_mismatch", "payment_allocation", aid))
        per_payment[a["payment_id"]] += a["amount"]
        if pay and per_payment[a["payment_id"]] > pay["amount"]:
            issues.append(Issue("allocation_exceeds_payment", "payment_allocation", aid,
                                f"total {per_payment[a['payment_id']]} vs payment {pay['amount']}"))
        if ln:
            if a["invoice_line_id"] not in dues:
                issues.append(Issue("allocation_to_non_charge_line", "payment_allocation", aid))
            else:
                per_line[a["invoice_line_id"]] += a["amount"]
                if per_line[a["invoice_line_id"]] > dues[a["invoice_line_id"]]:
                    issues.append(Issue("allocation_exceeds_line", "payment_allocation", aid))
    return issues


def check_late_fees_and_status(tables: dict, as_of=AS_OF_DATE) -> list[Issue]:
    """Late fee exists exactly when money was still owed after the grace period;
    invoice status agrees with what was actually allocated."""
    issues: list[Issue] = []
    lines_by_inv = defaultdict(list)
    for ln in tables.get("invoice_line", []):
        lines_by_inv[ln["invoice_id"]].append(ln)
    line_invoice = {ln["invoice_line_id"]: ln["invoice_id"] for ln in tables.get("invoice_line", [])}
    allocs = defaultdict(list)
    for a in tables.get("payment_allocation", []):
        iid = line_invoice.get(a["invoice_line_id"])
        if iid:
            allocs[iid].append(a)

    for inv in tables.get("invoice", []):
        iid = inv["invoice_id"]
        if inv["status"] == "CANCELLED":
            continue
        lns = lines_by_inv[iid]
        fee_lines = [ln for ln in lns if ln["line_type"] == "LATE_FEE"]
        base = sum((ln["amount"] for ln in lns if ln["line_type"] != "LATE_FEE"), Decimal(0))
        paid_by_grace = sum((a["amount"] for a in allocs[iid] if a["allocated_on"] <= grace_end(inv)), Decimal(0))
        expected = base - paid_by_grace > 0 and late_fee_date(inv) <= as_of
        if expected and not fee_lines:
            issues.append(Issue("late_fee_missing", "invoice", iid))
        if not expected and fee_lines:
            issues.append(Issue("late_fee_unexpected", "invoice", iid))
        for dup in fee_lines[1:]:
            issues.append(Issue("late_fee_duplicate", "invoice_line", dup["invoice_line_id"]))
        for fl in fee_lines:
            if fl["amount"] != LATE_FEE_AMOUNT or fl["line_date"] != late_fee_date(inv):
                issues.append(Issue("late_fee_wrong", "invoice_line", fl["invoice_line_id"]))

        paid = sum((a["amount"] for a in allocs[iid]), Decimal(0))
        net = inv["total_amount"]
        if paid >= net:
            want = "PAID"
        elif paid > 0:
            want = "PARTIALLY_PAID"
        else:
            want = "OVERDUE" if as_of > inv["due_date"] else "ISSUED"
        if inv["status"] != want:
            issues.append(Issue("invoice_status", "invoice", iid, f"{inv['status']} vs expected {want}"))
    return issues


def run_all(tables: dict, as_of=AS_OF_DATE) -> list[Issue]:
    return (check_structure(tables) + check_enrollments(tables) + check_invoices(tables)
            + check_scholarships(tables) + check_payments(tables)
            + check_late_fees_and_status(tables, as_of) + check_lifecycle(tables))
