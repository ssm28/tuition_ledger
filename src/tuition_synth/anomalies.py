"""Labelled anomaly injection, ground truth, and scoring of the validator against it.

The clean baseline is generated first. Then a fixed number of deliberate mistakes
are planted, each on a student no other anomaly touches, and every one is written
to ground_truth (a separate file that the validator never sees).

Five anomaly types (from the problem statement):
    ALLOCATION_EXCEEDS_PAYMENT  one allocation is inflated so a payment is allocated beyond its amount
    SCHOLARSHIP_EXCEEDS_FEES    an award is larger than the tuition it is meant to reduce
    DUPLICATE_INVOICE           the same enrollment is invoiced a second time
    REFUND_EXCEEDS_NET_PAID     a refund pays out more than the student ever paid
    BALANCE_LEDGER_MISMATCH     one ledger entry disagrees with its source record
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from . import ids
from .config import Config
from .events import renumber
from .ledger import build_ledger
from .master import money, rng_for
from .rules import LATE_FEE_AMOUNT, late_fee_date
from .schema import FEE_TYPES

ANOMALIES_PER_TYPE = 20     # at scale 1.0; at least 3 per type at any scale

# issue_type -> (table the label points at, validator check that should flag it)
ISSUE_CHECKS = {
    "ALLOCATION_EXCEEDS_PAYMENT": ("payment_allocation", "allocation_exceeds_payment"),
    "SCHOLARSHIP_EXCEEDS_FEES": ("scholarship", "scholarship_exceeds_fees"),
    "DUPLICATE_INVOICE": ("invoice", "duplicate_invoice"),
    "REFUND_EXCEEDS_NET_PAID": ("refund", "refund_exceeds_net_paid"),
    "BALANCE_LEDGER_MISMATCH": ("student", "balance_ledger_mismatch"),
}
DECISIONS = {
    "ALLOCATION_EXCEEDS_PAYMENT": "REJECT_ALLOCATION",
    "SCHOLARSHIP_EXCEEDS_FEES": "CAP_AWARD_AT_ELIGIBLE_FEES",
    "DUPLICATE_INVOICE": "CANCEL_DUPLICATE_INVOICE",
    "REFUND_EXCEEDS_NET_PAID": "REJECT_REFUND",
    "BALANCE_LEDGER_MISMATCH": "INVESTIGATE_AND_REPOST_LEDGER",
}
GROUND_TRUTH_COLUMNS = ["anomaly_id", "issue_type", "table", "row_id", "student_id",
                        "related_ids", "description", "expected_decision"]


def inject_anomalies(cfg: Config, tables: dict) -> list[dict]:
    """Plant the anomalies in `tables` (in place) and return the ground-truth rows."""
    rng = rng_for(cfg, "anomaly")
    count = max(3, round(ANOMALIES_PER_TYPE * cfg.scale))
    used: set = set()
    truth: list[dict] = []

    def record(issue_type, row_id, student, related, description):
        truth.append({
            "anomaly_id": f"GT-{len(truth) + 1:04d}", "issue_type": issue_type,
            "table": ISSUE_CHECKS[issue_type][0], "row_id": row_id, "student_id": student,
            "related_ids": ";".join(related), "description": description,
            "expected_decision": DECISIONS[issue_type],
        })

    def choose(candidates, student_of):
        """Up to `count` candidates, in a seeded random order, each on a student not yet used."""
        picked = []
        for cand in rng.sample(candidates, len(candidates)):
            student = student_of(cand)
            if student not in used:
                used.add(student)
                picked.append(cand)
                if len(picked) == count:
                    break
        return picked

    lines_by_invoice = defaultdict(list)
    for ln in tables["invoice_line"]:
        lines_by_invoice[ln["invoice_id"]].append(ln)
    invoice_of_line = {ln["invoice_line_id"]: ln["invoice_id"] for ln in tables["invoice_line"]}
    invoices = {i["invoice_id"]: i for i in tables["invoice"]}
    allocs_by_payment = defaultdict(list)
    for a in sorted(tables["payment_allocation"], key=lambda r: r["allocation_id"]):
        allocs_by_payment[a["payment_id"]].append(a)

    # ---- 1. payment allocated beyond its amount
    # Only the latest payment of an invoice qualifies, so no later allocation lands on the same
    # lines and the damage stays on the one row we label.
    latest_payment = {}
    for pid, als in allocs_by_payment.items():
        iid = invoice_of_line[als[0]["invoice_line_id"]]
        latest_payment[iid] = max(latest_payment.get(iid, pid), pid)
    candidates = []
    for pay in tables["payment"]:
        als = allocs_by_payment.get(pay["payment_id"])
        if not als or pay["amount"] < 1000 or sum(a["amount"] for a in als) != pay["amount"]:
            continue
        inv = invoices[invoice_of_line[als[0]["invoice_line_id"]]]
        if latest_payment[inv["invoice_id"]] != pay["payment_id"]:
            continue
        has_fee = any(ln["line_type"] == "LATE_FEE" for ln in lines_by_invoice[inv["invoice_id"]])
        if inv["status"] == "PAID" and not has_fee:
            candidates.append(pay)
    for pay in choose(candidates, lambda p: p["student_id"]):
        last = allocs_by_payment[pay["payment_id"]][-1]
        old, bump = last["amount"], money(rng.choice((500, 1000, 2500)))
        last["amount"] = old + bump
        record("ALLOCATION_EXCEEDS_PAYMENT", last["allocation_id"], pay["student_id"], [pay["payment_id"]],
               f"allocation raised from {old} to {last['amount']} on a payment of {pay['amount']}")

    # ---- 2. scholarship larger than the eligible fees
    tuition = {}
    for inv in tables["invoice"]:
        if inv["status"] != "CANCELLED":
            t = next(ln for ln in lines_by_invoice[inv["invoice_id"]] if ln["line_type"] == "TUITION")
            tuition[(inv["student_id"], inv["term_id"])] = (inv["invoice_id"], t["amount"])
    for sch in choose(tables["scholarship"], lambda s: s["student_id"]):
        invoice_id, fees = tuition[(sch["student_id"], sch["term_id"])]
        old = sch["award_amount"]
        sch["award_amount"] = fees + money(rng.choice((100, 750, 2000, 5000)))
        record("SCHOLARSHIP_EXCEEDS_FEES", sch["scholarship_id"], sch["student_id"], [invoice_id],
               f"award raised from {old} to {sch['award_amount']} on tuition of {fees}")

    # ---- 3. invoice generated twice
    next_event = 10**8 - 1       # placeholder IDs, replaced by renumber() below
    for original in choose([i for i in tables["invoice"] if i["status"] != "CANCELLED"], lambda i: i["student_id"]):
        year = original["issue_date"].year
        new_id = ids.invoice_id(original["student_id"], year, 4)   # students have invoices 1..3
        issue = original["issue_date"] + timedelta(days=rng.randint(1, 3))
        dup = dict(original, invoice_id=new_id, issue_date=issue,
                   due_date=issue + (original["due_date"] - original["issue_date"]), status="OVERDUE")
        new_lines = []
        for ln in lines_by_invoice[original["invoice_id"]]:
            if ln["line_type"] in FEE_TYPES:
                new_lines.append(dict(ln, invoice_line_id=ids.invoice_line_id(new_id, len(new_lines) + 1),
                                      invoice_id=new_id, line_date=issue))
        new_lines.append({
            "invoice_line_id": ids.invoice_line_id(new_id, len(new_lines) + 1), "invoice_id": new_id,
            "line_type": "LATE_FEE", "fee_schedule_id": None, "scholarship_id": None,
            "description": "Late payment fee", "amount": LATE_FEE_AMOUNT, "line_date": late_fee_date(dup),
        })
        dup["total_amount"] = sum((ln["amount"] for ln in new_lines), Decimal(0))
        tables["invoice"].append(dup)
        tables["invoice_line"].extend(new_lines)
        for status, prev, when in (("ISSUED", None, issue), ("OVERDUE", "ISSUED", dup["due_date"] + timedelta(days=1))):
            tables["status_event"].append({
                "event_id": ids.status_event_id(next_event), "entity_type": "invoice", "entity_id": new_id,
                "from_status": prev, "to_status": status, "event_date": when})
            next_event -= 1
        record("DUPLICATE_INVOICE", new_id, original["student_id"], [original["invoice_id"], original["enrollment_id"]],
               f"second invoice for enrollment {original['enrollment_id']}")

    # ---- 4. refund larger than the net amount paid
    payments_of = defaultdict(list)
    for pay in tables["payment"]:
        payments_of[pay["student_id"]].append(pay)
    refunded = defaultdict(Decimal)
    for r in tables["refund"]:
        if r["status"] == "PAID":
            refunded[r["student_id"]] += r["amount"]
    next_refund = max(int(r["refund_id"].split("-")[2]) for r in tables["refund"]) + 1
    for student in choose(sorted(payments_of), lambda s: s):
        pay = max(payments_of[student], key=lambda p: (p["amount"], p["payment_id"]))
        net_paid = sum(p["amount"] for p in payments_of[student]) - refunded[student]
        amount = net_paid + money(rng.choice((500, 1500, 5000)))
        requested = min(pay["payment_date"] + timedelta(days=10), cfg.as_of - timedelta(days=5))
        rid = ids.refund_id(requested.year, next_refund)
        next_refund += 1
        tables["refund"].append({
            "refund_id": rid, "student_id": student, "payment_id": pay["payment_id"], "enrollment_id": None,
            "reason": "OVERPAYMENT", "amount": amount, "requested_on": requested,
            "processed_on": requested + timedelta(days=3), "status": "PAID"})
        for status, prev, days in (("REQUESTED", None, 0), ("APPROVED", "REQUESTED", 1), ("PAID", "APPROVED", 3)):
            tables["status_event"].append({
                "event_id": ids.status_event_id(next_event), "entity_type": "refund", "entity_id": rid,
                "from_status": prev, "to_status": status, "event_date": requested + timedelta(days=days)})
            next_event -= 1
        record("REFUND_EXCEEDS_NET_PAID", rid, student, [pay["payment_id"]],
               f"refund of {amount} while net paid is {net_paid}")

    # The ledger is derived from the (now altered) source rows, so it stays consistent with them...
    tables["status_event"] = renumber(tables["status_event"])
    tables["ledger_entry"] = build_ledger(tables)

    # ---- 5. ...except for this one: a ledger entry that no longer matches its source
    entries = defaultdict(list)
    for e in tables["ledger_entry"]:
        if e["entry_type"] in ("PAYMENT", "CHARGE"):
            entries[e["student_id"]].append(e)
    for student in choose(sorted(entries), lambda s: s):
        entry = rng.choice(entries[student])
        old, delta = entry["amount"], money(rng.choice((250, 500, 750, 1200)))
        entry["amount"] = old + delta
        record("BALANCE_LEDGER_MISMATCH", student, student, [f"ledger_entry:{entry['ledger_entry_id']}"],
               f"{entry['entry_type']} entry {entry['ledger_entry_id']} changed from {old} to {entry['amount']}")
    return truth


def score_detection(issues: list, truth: list[dict]) -> dict:
    """Compare validator issues with the ground truth.

    detected  - an injected anomaly counts as found if the expected check fired on its row
    explained - every issue should sit on an injected row (or a row named in related_ids);
                anything else is an unexplained issue, i.e. a false alarm or collateral damage
    """
    fired = {(i.table, i.row_id, i.check) for i in issues}
    per_type: dict = {}
    explained_rows = set()
    for gt in truth:
        table, check = ISSUE_CHECKS[gt["issue_type"]]
        stats = per_type.setdefault(gt["issue_type"], {"injected": 0, "detected": 0})
        stats["injected"] += 1
        stats["detected"] += (table, gt["row_id"], check) in fired
        explained_rows.add((gt["table"], gt["row_id"]))
        for rel in filter(None, gt["related_ids"].split(";")):
            if ":" in rel:
                t, _, rid = rel.partition(":")
                explained_rows.add((t, rid))
    unexplained = [i for i in issues if (i.table, i.row_id) not in explained_rows]
    injected = sum(s["injected"] for s in per_type.values())
    detected = sum(s["detected"] for s in per_type.values())
    return {
        "per_type": per_type, "injected": injected, "detected": detected,
        "recall": detected / injected if injected else 1.0,
        "issues_total": len(issues), "unexplained": unexplained,
    }
