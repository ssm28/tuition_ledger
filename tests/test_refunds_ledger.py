"""Refunds and the ledger on the clean baseline (full scale)."""
from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal

from tuition_synth.config import Config
from tuition_synth.pipeline import build_all
from tuition_synth.validate import expected_balances, run_all

T = build_all(Config())
PAYMENT = {p["payment_id"]: p for p in T["payment"]}
ENROLLMENT = {e["enrollment_id"]: e for e in T["enrollment"]}
TERM_START = {t["term_id"]: t["start_date"] for t in T["term"]}
LINE_TYPE = {ln["invoice_line_id"]: ln["line_type"] for ln in T["invoice_line"]}
ALLOCATED, TUITION = defaultdict(Decimal), defaultdict(Decimal)
for a in T["payment_allocation"]:
    ALLOCATED[a["payment_id"]] += a["amount"]
    if LINE_TYPE[a["invoice_line_id"]] == "TUITION":
        TUITION[a["payment_id"]] += a["amount"]


def test_baseline_is_clean():
    assert run_all(T) == []


def test_all_reasons_and_statuses_occur():
    assert {r["reason"] for r in T["refund"]} == {"WITHDRAWAL", "CANCELLATION", "OVERPAYMENT"}
    assert {r["status"] for r in T["refund"]} == {"REQUESTED", "APPROVED", "PAID", "REJECTED"}


def test_withdrawal_refunds_follow_the_documented_tiers():
    tiers = ((14, Decimal("1.00")), (30, Decimal("0.50")), (45, Decimal("0.25")))   # from DESIGN.md
    checked = 0
    for r in T["refund"]:
        if r["reason"] != "WITHDRAWAL":
            continue
        enr = ENROLLMENT[r["enrollment_id"]]
        days = (enr["withdrawn_on"] - TERM_START[enr["term_id"]]).days
        share = next((s for last, s in tiers if days <= last), Decimal("0.00"))
        if r["status"] == "REJECTED":
            assert share == 0                       # only claims outside every tier are rejected
        else:
            assert share > 0
            assert r["amount"] == (TUITION[r["payment_id"]] * share).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        checked += 1
    assert checked > 1000


def test_cancellation_and_overpayment_refund_amounts():
    for r in T["refund"]:
        if r["reason"] == "CANCELLATION":
            assert r["amount"] == ALLOCATED[r["payment_id"]] == PAYMENT[r["payment_id"]]["amount"]
        if r["reason"] == "OVERPAYMENT":
            assert r["amount"] == PAYMENT[r["payment_id"]]["amount"] - ALLOCATED[r["payment_id"]] > 0


def test_refunds_never_exceed_what_the_student_paid():
    paid, refunded = defaultdict(Decimal), defaultdict(Decimal)
    for p in T["payment"]:
        paid[p["student_id"]] += p["amount"]
    for r in T["refund"]:
        if r["status"] == "PAID":
            refunded[r["student_id"]] += r["amount"]
    assert all(refunded[s] <= paid[s] for s in refunded)


def test_processed_date_is_set_only_for_finished_refunds():
    for r in T["refund"]:
        assert (r["processed_on"] is not None) == (r["status"] in ("PAID", "REJECTED"))
        if r["processed_on"]:
            assert r["processed_on"] >= r["requested_on"] >= PAYMENT[r["payment_id"]]["payment_date"]


# ------------------------------------------------------------------ ledger
def test_ledger_entry_count_matches_its_sources():
    counts = Counter(e["entry_type"] for e in T["ledger_entry"])
    cancelled = sum(1 for i in T["invoice"] if i["status"] == "CANCELLED")
    paid_refunds = sum(1 for r in T["refund"] if r["status"] == "PAID")
    assert len(T["ledger_entry"]) == len(T["invoice_line"]) + len(T["payment"]) + paid_refunds + cancelled
    assert set(counts) == {"CHARGE", "SCHOLARSHIP_CREDIT", "WAIVER", "LATE_FEE", "PAYMENT", "REFUND", "REVERSAL"}


def test_ledger_signs():
    for e in T["ledger_entry"]:
        positive = e["entry_type"] in ("CHARGE", "LATE_FEE", "REFUND")
        assert (e["amount"] > 0) == positive, e["entry_type"]


def test_ledger_is_ordered_and_gapless():
    seqs = [e["event_seq"] for e in T["ledger_entry"]]
    assert seqs == list(range(1, len(seqs) + 1))
    dates = [e["entry_date"] for e in T["ledger_entry"]]
    assert dates == sorted(dates)


def test_student_balance_from_ledger_equals_balance_from_records():
    ledger = defaultdict(Decimal)
    for e in T["ledger_entry"]:
        ledger[e["student_id"]] += e["amount"]
    direct = expected_balances(T)
    assert all(ledger[s["student_id"]] == direct[s["student_id"]] for s in T["student"])


def test_cancelled_invoices_net_to_zero_in_the_ledger():
    cancelled = {i["invoice_id"] for i in T["invoice"] if i["status"] == "CANCELLED"}
    net = defaultdict(Decimal)
    line_invoice = {ln["invoice_line_id"]: ln["invoice_id"] for ln in T["invoice_line"]}
    for e in T["ledger_entry"]:
        if e["source_table"] == "invoice_line" and line_invoice[e["source_id"]] in cancelled:
            net[line_invoice[e["source_id"]]] += e["amount"]
        elif e["source_table"] == "invoice" and e["source_id"] in cancelled:
            net[e["source_id"]] += e["amount"]
    assert len(net) == len(cancelled) and all(v == 0 for v in net.values())


def test_balances_have_both_debt_and_credit_on_account():
    ledger = defaultdict(Decimal)
    for e in T["ledger_entry"]:
        ledger[e["student_id"]] += e["amount"]
    assert any(v > 0 for v in ledger.values())      # students who still owe money
    assert any(v < 0 for v in ledger.values())      # overpaid students (credit on account)
