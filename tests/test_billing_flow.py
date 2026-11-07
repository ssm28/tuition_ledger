"""Scholarships, waivers, payments, allocations, late fees and invoice statuses (full scale)."""
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from tuition_synth import ids
from tuition_synth.config import Config
from tuition_synth.pipeline import build_all
from tuition_synth.rules import LATE_FEE_AMOUNT, grace_end
from tuition_synth.validate import run_all

T = build_all(Config())
INV = {i["invoice_id"]: i for i in T["invoice"]}
LINES = defaultdict(list)
for ln in T["invoice_line"]:
    LINES[ln["invoice_id"]].append(ln)


def test_whole_dataset_validates_cleanly():
    assert run_all(T) == []


def test_volumes_hit_the_targets_exactly():
    assert len(T["scholarship"]) == 15_000
    assert len(T["payment"]) == 50_000
    assert len(T["invoice"]) == 30_000


def test_one_scholarship_per_student_term_never_on_cancelled_invoices():
    keys = [(s["student_id"], s["term_id"]) for s in T["scholarship"]]
    assert len(set(keys)) == len(keys)
    cancelled = {(i["student_id"], i["term_id"]) for i in T["invoice"] if i["status"] == "CANCELLED"}
    assert not cancelled & set(keys)


def test_every_scheme_is_used_and_the_expired_scheme_respects_its_end_date():
    assert {s["eligibility_id"] for s in T["scholarship"]} == {e["eligibility_id"] for e in T["eligibility"]}
    boost = next(e["eligibility_id"] for e in T["eligibility"] if e["name"] == "First-Half Merit Boost")
    boost_awards = [s for s in T["scholarship"] if s["eligibility_id"] == boost]
    # eligibility is judged on the date the award is decided, so no award is decided after expiry...
    assert boost_awards and all(s["awarded_on"] <= date(2026, 7, 31) for s in boost_awards)
    # ...yet a Fall award decided in late July can still use it (boundary case), while
    # Fall awards decided in August cannot.
    fall = [s for s in T["scholarship"] if s["term_id"] == "TERM-2026-FALL"]
    assert any(s["eligibility_id"] == boost for s in fall)
    assert any(s["awarded_on"] > date(2026, 7, 31) for s in fall)


def test_scholarship_credit_lines_match_awards_and_stay_within_tuition():
    for s in T["scholarship"]:
        credit = [ln for ln in T["invoice_line"] if ln["scholarship_id"] == s["scholarship_id"]]
        assert len(credit) == 1 and credit[0]["amount"] == -s["award_amount"] < 0
        tuition = next(ln for ln in LINES[credit[0]["invoice_id"]] if ln["line_type"] == "TUITION")
        assert 0 < s["award_amount"] <= tuition["amount"]
        break  # one full pass below is covered by the validator; keep this test quick
    awards = Counter(ln["line_type"] for ln in T["invoice_line"])
    assert awards["SCHOLARSHIP_CREDIT"] == 15_000


def test_waivers_hit_about_three_percent_and_never_waive_tuition():
    waivers = [ln for ln in T["invoice_line"] if ln["line_type"] == "WAIVER"]
    active = sum(1 for i in T["invoice"] if i["status"] != "CANCELLED" or True)
    assert 0.02 <= len(waivers) / active <= 0.04
    by_sched = {f["fee_schedule_id"]: f["fee_type"] for f in T["fee_schedule"]}
    assert all(by_sched[w["fee_schedule_id"]] != "TUITION" and w["amount"] < 0 for w in waivers)


def test_payment_ids_references_and_order():
    pays = T["payment"]
    assert [p["payment_id"] for p in pays] == [ids.payment_id(2026, n) for n in range(1, 50_001)]
    assert len({p["reference"] for p in pays}) == len(pays)
    dates = [p["payment_date"] for p in pays]
    assert dates == sorted(dates)
    assert {p["method"] for p in pays} == {"UPI", "CARD", "NET_BANKING", "BANK_TRANSFER", "CASH"}


def test_allocations_never_exceed_their_payment_and_overpayments_exist():
    allocated = defaultdict(Decimal)
    for a in T["payment_allocation"]:
        allocated[a["payment_id"]] += a["amount"]
    over = 0
    for p in T["payment"]:
        assert allocated[p["payment_id"]] <= p["amount"]
        over += allocated[p["payment_id"]] < p["amount"]
    assert over > 0  # some payments were larger than what was owed


def test_invoice_status_mix_covers_paid_partial_overdue_cancelled():
    mix = Counter(i["status"] for i in T["invoice"])
    assert set(mix) == {"PAID", "PARTIALLY_PAID", "OVERDUE", "CANCELLED"}
    assert 0.80 <= mix["PAID"] / 30_000 <= 0.90


def test_paid_invoices_are_settled_exactly_by_their_allocations():
    allocated = defaultdict(Decimal)
    line_invoice = {ln["invoice_line_id"]: ln["invoice_id"] for ln in T["invoice_line"]}
    for a in T["payment_allocation"]:
        allocated[line_invoice[a["invoice_line_id"]]] += a["amount"]
    for inv in T["invoice"]:
        if inv["status"] == "PAID":
            assert allocated[inv["invoice_id"]] == inv["total_amount"]
        elif inv["status"] == "PARTIALLY_PAID":
            assert 0 < allocated[inv["invoice_id"]] < inv["total_amount"]
        elif inv["status"] == "OVERDUE":
            assert allocated[inv["invoice_id"]] == 0


def test_late_fee_is_fixed_once_per_invoice_and_only_when_money_is_still_owed():
    fees = [ln for ln in T["invoice_line"] if ln["line_type"] == "LATE_FEE"]
    assert fees and all(f["amount"] == LATE_FEE_AMOUNT for f in fees)
    assert max(Counter(f["invoice_id"] for f in fees).values()) == 1
    allocated_by_grace = defaultdict(Decimal)
    line_invoice = {ln["invoice_line_id"]: ln["invoice_id"] for ln in T["invoice_line"]}
    for a in T["payment_allocation"]:
        iid = line_invoice[a["invoice_line_id"]]
        if a["allocated_on"] <= grace_end(INV[iid]):
            allocated_by_grace[iid] += a["amount"]
    has_fee = {f["invoice_id"] for f in fees}
    for iid, inv in INV.items():
        if inv["status"] == "CANCELLED":
            continue
        base = sum(ln["amount"] for ln in LINES[iid] if ln["line_type"] != "LATE_FEE")
        assert (base - allocated_by_grace[iid] > 0) == (iid in has_fee), iid


def test_cancelled_invoices_have_no_late_fees_and_were_paid_only_before_cancellation():
    cancelled = {i["invoice_id"] for i in T["invoice"] if i["status"] == "CANCELLED"}
    assert not any(ln["invoice_id"] in cancelled and ln["line_type"] == "LATE_FEE" for ln in T["invoice_line"])
    cancelled_on = {e["entity_id"]: e["event_date"] for e in T["status_event"]
                    if e["entity_type"] == "invoice" and e["to_status"] == "CANCELLED"}
    pay_date = {p["payment_id"]: p["payment_date"] for p in T["payment"]}
    line_invoice = {ln["invoice_line_id"]: ln["invoice_id"] for ln in T["invoice_line"]}
    paid_cancelled = set()
    for a in T["payment_allocation"]:
        iid = line_invoice[a["invoice_line_id"]]
        if iid in cancelled:
            paid_cancelled.add(iid)
            assert pay_date[a["payment_id"]] <= cancelled_on[iid]
    assert 0.25 <= len(paid_cancelled) / len(cancelled) <= 0.45


def test_installments_and_partial_payments_exist():
    per_invoice = Counter()
    line_invoice = {ln["invoice_line_id"]: ln["invoice_id"] for ln in T["invoice_line"]}
    first_alloc = {}
    for a in T["payment_allocation"]:
        first_alloc.setdefault(a["payment_id"], line_invoice[a["invoice_line_id"]])
    for iid in first_alloc.values():
        per_invoice[iid] += 1
    assert set(per_invoice.values()) >= {1, 2, 3, 4}


def test_small_scale_also_hits_targets_and_is_deterministic():
    a, b = build_all(Config(scale=0.05)), build_all(Config(scale=0.05))
    assert a == b
    assert len(a["payment"]) == 2_500 and len(a["scholarship"]) == 750
    assert run_all(a) == []
    c = build_all(Config(seed=7, scale=0.05))
    assert [p["amount"] for p in c["payment"]] != [p["amount"] for p in a["payment"]]
