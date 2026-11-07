"""Scholarship awards and fee waivers, applied to invoices as negative lines.

Awards: every non-cancelled invoice is checked against every scheme; the best
scheme the student qualifies for gives that term's candidate award. Funding is
limited, so exactly `volume("scholarships")` of the candidates are awarded
(a random subset, like applicants being selected). Each award becomes a
SCHOLARSHIP_CREDIT line on the invoice.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from . import ids
from .config import Config
from .events import EventLog
from .master import money, rng_for
from .rules import award_amount, is_eligible

P_WAIVER = 0.03                  # share of invoices with one non-tuition fee waived
AWARD_LEAD_DAYS = (1, 14)        # award is decided this many days before invoice issue
WAIVABLE = ("LAB", "LIBRARY", "TECHNOLOGY", "ACTIVITY")


def _credit_line(invoice_id: str, n: int, line_type: str, fee_schedule_id, scholarship_id,
                 description: str, amount, line_date) -> dict:
    return {
        "invoice_line_id": ids.invoice_line_id(invoice_id, n),
        "invoice_id": invoice_id,
        "line_type": line_type,
        "fee_schedule_id": fee_schedule_id,
        "scholarship_id": scholarship_id,
        "description": description,
        "amount": amount,
        "line_date": line_date,
    }


def build_scholarships(cfg: Config, master: dict, invoices: list, lines: list, log: EventLog) -> list:
    rng = rng_for(cfg, "scholarship")
    students = {s["student_id"]: s for s in master["student"]}
    tuition = {ln["invoice_id"]: ln["amount"] for ln in lines if ln["line_type"] == "TUITION"}
    line_count = Counter(ln["invoice_id"] for ln in lines)

    candidates = []
    for inv in invoices:
        if inv["status"] == "CANCELLED":
            continue
        awarded_on = inv["issue_date"] - timedelta(days=rng.randint(*AWARD_LEAD_DAYS))
        student, fees = students[inv["student_id"]], tuition[inv["invoice_id"]]
        best = None
        for scheme in master["eligibility"]:
            if is_eligible(student, scheme, awarded_on):
                amount = award_amount(scheme, fees)
                if best is None or amount > best[1]:   # ties keep the lowest eligibility_id
                    best = (scheme, amount)
        if best:
            candidates.append((inv, best[0], best[1], awarded_on))

    wanted = min(cfg.volume("scholarships"), len(candidates))
    chosen = sorted(rng.sample(range(len(candidates)), wanted))

    scholarships = []
    for n, idx in enumerate(chosen, start=1):
        inv, scheme, amount, awarded_on = candidates[idx]
        sch_id = ids.scholarship_id(inv["issue_date"].year, n)
        scholarships.append({
            "scholarship_id": sch_id,
            "student_id": inv["student_id"],
            "eligibility_id": scheme["eligibility_id"],
            "term_id": inv["term_id"],
            "award_amount": amount,
            "awarded_on": awarded_on,
            "status": "APPLIED",
        })
        log.add("scholarship", sch_id, None, "AWARDED", awarded_on)
        log.add("scholarship", sch_id, "AWARDED", "APPLIED", inv["issue_date"])
        line_count[inv["invoice_id"]] += 1
        lines.append(_credit_line(
            inv["invoice_id"], line_count[inv["invoice_id"]], "SCHOLARSHIP_CREDIT", None, sch_id,
            f"Scholarship - {scheme['name']}", -amount, inv["issue_date"]))
    return scholarships


def add_waivers(cfg: Config, invoices: list, lines: list) -> int:
    """Waive one non-tuition fee on a small share of invoices. Returns how many."""
    rng = rng_for(cfg, "waiver")
    fee_lines = {}
    for ln in lines:
        if ln["line_type"] in WAIVABLE:
            fee_lines.setdefault(ln["invoice_id"], []).append(ln)
    line_count = Counter(ln["invoice_id"] for ln in lines)
    added = 0
    for inv in invoices:
        if inv["status"] == "CANCELLED":
            continue
        draw = rng.random()
        options = fee_lines.get(inv["invoice_id"], [])
        if draw < P_WAIVER and options:
            target = rng.choice(options)
            line_count[inv["invoice_id"]] += 1
            lines.append(_credit_line(
                inv["invoice_id"], line_count[inv["invoice_id"]], "WAIVER", target["fee_schedule_id"], None,
                f"Fee waiver - {target['line_type'].title()} fee", -money(target["amount"]), inv["issue_date"]))
            added += 1
    return added
