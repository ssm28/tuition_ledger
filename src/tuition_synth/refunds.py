"""Refunds: withdrawal, cancellation and overpayment.

WITHDRAWAL    share of the tuition paid (tiers in rules.refund_share), one refund per
              payment that paid tuition. Withdrawals after the last tier get no refund;
              some of those students still ask, and the request is REJECTED.
CANCELLATION  everything paid on the cancelled invoice, one refund per payment.
OVERPAYMENT   the part of a payment that was never allocated (credit on account),
              refunded for some students.

Every refund follows REQUESTED -> APPROVED -> PAID (or stops earlier, or is
REJECTED). Steps dated after the as-of date have not happened yet.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from . import ids
from .config import Config
from .events import EventLog
from .master import Rows, money, rng_for
from .rules import refund_share

PATHS = ("PAID", "APPROVED", "REQUESTED")
PATH_WEIGHTS = (85, 7, 8)
P_REJECTED_CLAIM = 0.6        # late withdrawers who still file a claim
P_OVERPAY_REFUND = 0.6        # overpayers who ask for their credit back


def _chain(path: str, requested, approve_after: int, process_after: int):
    if path == "REJECTED":
        return [("REQUESTED", requested), ("REJECTED", requested + timedelta(days=approve_after))]
    steps = [("REQUESTED", requested)]
    if path in ("APPROVED", "PAID"):
        approved = requested + timedelta(days=approve_after)
        steps.append(("APPROVED", approved))
        if path == "PAID":
            steps.append(("PAID", approved + timedelta(days=process_after)))
    return steps


def build_refunds(cfg: Config, master: dict, enrollments: Rows, invoices: Rows, lines: Rows,
                  payments: Rows, allocations: Rows, log: EventLog) -> Rows:
    rng = rng_for(cfg, "refund")
    terms = {t["term_id"]: t for t in master["term"]}
    line_by_id = {ln["invoice_line_id"]: ln for ln in lines}
    pay_by_id = {p["payment_id"]: p for p in payments}
    invoice_by_enr = {i["enrollment_id"]: i for i in invoices}

    alloc_total, tuition_alloc = defaultdict(Decimal), defaultdict(Decimal)
    payments_of_invoice = defaultdict(set)
    for a in allocations:
        ln = line_by_id[a["invoice_line_id"]]
        alloc_total[a["payment_id"]] += a["amount"]
        if ln["line_type"] == "TUITION":
            tuition_alloc[a["payment_id"]] += a["amount"]
        payments_of_invoice[ln["invoice_id"]].add(a["payment_id"])

    drafts = []  # dicts; see below

    def draw_offsets():
        return rng.randint(1, 7), rng.randint(1, 5), rng.randint(1, 7)

    # --- withdrawals
    for enr in enrollments:
        if enr["status"] != "WITHDRAWN":
            continue
        inv = invoice_by_enr[enr["enrollment_id"]]
        share = refund_share((enr["withdrawn_on"] - terms[enr["term_id"]]["start_date"]).days)
        claim_roll = rng.random()
        path = rng.choices(PATHS, weights=PATH_WEIGHTS, k=1)[0]
        req_off, appr_off, proc_off = draw_offsets()
        if share == 0:
            if claim_roll >= P_REJECTED_CLAIM:
                continue
            path = "REJECTED"
        for pid in sorted(payments_of_invoice[inv["invoice_id"]]):
            paid = tuition_alloc[pid]
            amount = money(paid * share) if share > 0 else paid   # rejected claims ask for all they paid
            if amount <= 0:
                continue
            pay = pay_by_id[pid]
            drafts.append({
                "student_id": enr["student_id"], "payment_id": pid, "enrollment_id": enr["enrollment_id"],
                "reason": "WITHDRAWAL", "amount": amount, "path": path,
                "requested": max(enr["withdrawn_on"], pay["payment_date"]) + timedelta(days=req_off),
                "appr": appr_off, "proc": proc_off,
            })

    # --- cancellations
    for inv in invoices:
        if inv["status"] != "CANCELLED" or not payments_of_invoice[inv["invoice_id"]]:
            continue
        cancelled_on = log.date_of("invoice", inv["invoice_id"], "CANCELLED")
        path = rng.choices(PATHS, weights=PATH_WEIGHTS, k=1)[0]
        req_off, appr_off, proc_off = rng.randint(0, 3), rng.randint(1, 5), rng.randint(1, 7)
        for pid in sorted(payments_of_invoice[inv["invoice_id"]]):
            pay = pay_by_id[pid]
            drafts.append({
                "student_id": inv["student_id"], "payment_id": pid, "enrollment_id": inv["enrollment_id"],
                "reason": "CANCELLATION", "amount": alloc_total[pid], "path": path,
                "requested": max(cancelled_on, pay["payment_date"]) + timedelta(days=req_off),
                "appr": appr_off, "proc": proc_off,
            })

    # --- overpayments (credit on account)
    for pay in payments:
        leftover = pay["amount"] - alloc_total.get(pay["payment_id"], Decimal(0))
        roll = rng.random()
        path = rng.choices(PATHS, weights=PATH_WEIGHTS, k=1)[0]
        req_off, appr_off, proc_off = rng.randint(5, 30), rng.randint(1, 5), rng.randint(1, 7)
        if leftover > 0 and roll < P_OVERPAY_REFUND:
            drafts.append({
                "student_id": pay["student_id"], "payment_id": pay["payment_id"], "enrollment_id": None,
                "reason": "OVERPAYMENT", "amount": leftover, "path": path,
                "requested": pay["payment_date"] + timedelta(days=req_off),
                "appr": appr_off, "proc": proc_off,
            })

    drafts = [d for d in drafts if d["requested"] <= cfg.as_of]
    drafts.sort(key=lambda d: (d["requested"], d["payment_id"], d["reason"]))

    refunds: Rows = []
    for n, d in enumerate(drafts, start=1):
        steps = [s for s in _chain(d["path"], d["requested"], d["appr"], d["proc"]) if s[1] <= cfg.as_of]
        rid = ids.refund_id(d["requested"].year, n)
        previous = None
        for status, when in steps:
            log.add("refund", rid, previous, status, when)
            previous = status
        final_status, final_date = steps[-1]
        refunds.append({
            "refund_id": rid, "student_id": d["student_id"], "payment_id": d["payment_id"],
            "enrollment_id": d["enrollment_id"], "reason": d["reason"], "amount": d["amount"],
            "requested_on": d["requested"],
            "processed_on": final_date if final_status in ("PAID", "REJECTED") else None,
            "status": final_status,
        })
    return refunds
