"""Transaction tables: enrollments, invoices and invoice lines.

Flow per student and per term:
    enroll  ->  issue invoice from the price list  ->  maybe cancel / withdraw
Outcomes (cancelled, withdrawn, completed) are drawn once, then everything
else (dates, lines, totals, status history) follows from that outcome.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from . import ids
from .config import Config
from .events import EventLog
from .master import Rows, build_master, money, rng_for
from .schema import TABLES

P_CANCEL = 0.015     # share of enrollments cancelled before the term starts
P_WITHDRAW = 0.04    # share of enrollments withdrawn after the term starts
# Withdrawal timing: (weight, first day, last day) counted from term start.
# A last day of None means "until the end of the term". These windows line up
# with the refund tiers (<=14, <=30, <=45 days, later) so every tier occurs.
WITHDRAW_WINDOWS = ((40, 1, 14), (30, 15, 30), (20, 31, 45), (10, 46, None))
ENROLL_LEAD_DAYS = (15, 45)   # student enrolls this many days before term start
ISSUE_LEAD_DAYS = (1, 10)     # invoice is issued this many days before term start


def _schedule_index(fee_schedules: Rows) -> dict:
    index = defaultdict(list)
    for fs in fee_schedules:
        index[(fs["program_id"], fs["term_id"])].append(fs)
    return index


def _effective(fs: dict, on) -> bool:
    return fs["effective_from"] <= on and (fs["effective_to"] is None or on <= fs["effective_to"])


def build_enrollments_and_invoices(cfg: Config, master: dict, log: EventLog):
    """Return (enrollments, invoices, invoice_lines) and record status events."""
    rng_e = rng_for(cfg, "enrollment")
    rng_i = rng_for(cfg, "invoice")
    schedules = _schedule_index(master["fee_schedule"])
    enrollments: Rows = []
    invoices: Rows = []
    lines: Rows = []
    enr_n = 0

    for student in master["student"]:
        inv_seq = 0
        for term in master["term"]:
            enr_n += 1
            start, end = term["start_date"], term["end_date"]
            enr_id = ids.enrollment_id(enr_n)
            enrolled_on = start - timedelta(days=rng_e.randint(*ENROLL_LEAD_DAYS))
            draw = rng_e.random()

            inv_seq += 1
            inv_id = ids.invoice_id(student["student_id"], start.year, inv_seq)
            issue = start - timedelta(days=rng_i.randint(*ISSUE_LEAD_DAYS))
            due = issue + timedelta(days=term["invoice_due_days"])

            # --- invoice lines come from the price list valid on the issue date
            inv_lines = []
            for fs in schedules[(student["program_id"], term["term_id"])]:
                if _effective(fs, issue):
                    inv_lines.append({
                        "invoice_line_id": ids.invoice_line_id(inv_id, len(inv_lines) + 1),
                        "invoice_id": inv_id,
                        "line_type": fs["fee_type"],
                        "fee_schedule_id": fs["fee_schedule_id"],
                        "scholarship_id": None,
                        "description": f"{fs['fee_type'].title()} fee - {term['label']}",
                        "amount": fs["amount"],
                        "line_date": issue,
                    })
            if not any(ln["line_type"] == "TUITION" for ln in inv_lines):
                raise ValueError(f"no tuition schedule for {student['program_id']} {term['term_id']} on {issue}")

            # --- decide what happens to this enrollment
            status, withdrawn_on, inv_status = "ENROLLED", None, "ISSUED"
            log.add("enrollment", enr_id, None, "ENROLLED", enrolled_on)
            log.add("invoice", inv_id, None, "ISSUED", issue)

            if draw < P_CANCEL:
                cancelled_on = issue + timedelta(days=rng_e.randint(0, (start - issue).days))
                status, inv_status = "CANCELLED", "CANCELLED"
                log.add("enrollment", enr_id, "ENROLLED", "CANCELLED", cancelled_on)
                log.add("invoice", inv_id, "ISSUED", "CANCELLED", cancelled_on)
            elif draw < P_CANCEL + P_WITHDRAW:
                weights = [w for w, _lo, _hi in WITHDRAW_WINDOWS]
                _w, lo, hi = rng_e.choices(WITHDRAW_WINDOWS, weights=weights, k=1)[0]
                last_day = (end - start).days
                hi = last_day if hi is None else min(hi, last_day)
                withdrawn_on = start + timedelta(days=rng_e.randint(lo, hi))
                status = "WITHDRAWN"
                log.add("enrollment", enr_id, "ENROLLED", "WITHDRAWN", withdrawn_on)
            elif cfg.as_of >= end:
                status = "COMPLETED"
                log.add("enrollment", enr_id, "ENROLLED", "COMPLETED", end)

            enrollments.append({
                "enrollment_id": enr_id,
                "student_id": student["student_id"],
                "program_id": student["program_id"],
                "term_id": term["term_id"],
                "status": status,
                "enrolled_on": enrolled_on,
                "withdrawn_on": withdrawn_on,
            })
            invoices.append({
                "invoice_id": inv_id,
                "student_id": student["student_id"],
                "enrollment_id": enr_id,
                "term_id": term["term_id"],
                "issue_date": issue,
                "due_date": due,
                "currency": "INR",
                "total_amount": money(sum((ln["amount"] for ln in inv_lines), Decimal(0))),
                "status": inv_status,
            })
            lines.extend(inv_lines)
    return enrollments, invoices, lines


def recompute_invoice_totals(invoices: Rows, lines: Rows) -> None:
    """Set each invoice total to the sum of its lines (totals are derived, never typed in)."""
    sums: dict = defaultdict(Decimal)
    for ln in lines:
        sums[ln["invoice_id"]] += ln["amount"]
    for inv in invoices:
        inv["total_amount"] = money(sums[inv["invoice_id"]])


def build_core(cfg: Config) -> dict:
    """Master tables plus enrollments, invoices, lines and status history."""
    master = build_master(cfg)
    log = EventLog()
    enrollments, invoices, lines = build_enrollments_and_invoices(cfg, master, log)
    tables = {
        **master,
        "enrollment": enrollments,
        "invoice": invoices,
        "invoice_line": lines,
        "status_event": log.rows(),
    }
    return {name: tables[name] for name in TABLES if name in tables}
