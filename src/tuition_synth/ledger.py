"""The student ledger: an append-only list of money movements derived from the source tables.

Sign convention: positive = the student owes more (charges, late fees, refunds paid out);
negative = the student owes less (payments, scholarship credits, waivers, reversals).
Balance owed = sum of a student's entries. A negative balance is credit on account.
"""
from __future__ import annotations

from . import ids
from .schema import FEE_TYPES

_LINE_TO_ENTRY = {t: "CHARGE" for t in FEE_TYPES}
_LINE_TO_ENTRY.update({"LATE_FEE": "LATE_FEE", "SCHOLARSHIP_CREDIT": "SCHOLARSHIP_CREDIT", "WAIVER": "WAIVER"})


def build_ledger(tables: dict) -> list[dict]:
    invoices = {i["invoice_id"]: i for i in tables.get("invoice", [])}
    cancelled_on = {
        ev["entity_id"]: ev["event_date"] for ev in tables.get("status_event", [])
        if ev["entity_type"] == "invoice" and ev["to_status"] == "CANCELLED"
    }
    entries = []   # (date, source_table, source_id, entry_type, student_id, amount)
    cancelled_total = {}
    for ln in tables.get("invoice_line", []):
        inv = invoices.get(ln["invoice_id"])
        if inv is None:
            continue
        entries.append((ln["line_date"], "invoice_line", ln["invoice_line_id"],
                        _LINE_TO_ENTRY[ln["line_type"]], inv["student_id"], ln["amount"]))
        if inv["status"] == "CANCELLED":
            cancelled_total[inv["invoice_id"]] = cancelled_total.get(inv["invoice_id"], 0) + ln["amount"]
    for iid, total in cancelled_total.items():
        entries.append((cancelled_on[iid], "invoice", iid, "REVERSAL", invoices[iid]["student_id"], -total))
    for p in tables.get("payment", []):
        if p["status"] == "POSTED":
            entries.append((p["payment_date"], "payment", p["payment_id"], "PAYMENT", p["student_id"], -p["amount"]))
    for r in tables.get("refund", []):
        if r["status"] == "PAID":
            entries.append((r["processed_on"], "refund", r["refund_id"], "REFUND", r["student_id"], r["amount"]))

    entries.sort(key=lambda e: e[:4])
    return [
        {
            "ledger_entry_id": ids.ledger_entry_id(n), "event_seq": n, "student_id": student,
            "entry_date": when, "entry_type": etype, "amount": amount,
            "source_table": table, "source_id": sid,
        }
        for n, (when, table, sid, etype, student, amount) in enumerate(entries, start=1)
    ]
