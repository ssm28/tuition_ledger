from collections import Counter, defaultdict
from decimal import Decimal

from tuition_synth import ids
from tuition_synth.config import Config
from tuition_synth.transactions import build_core, recompute_invoice_totals
from tuition_synth.validate import run_all

CORE = build_core(Config(scale=1.0))
ENR, INV, LINES = CORE["enrollment"], CORE["invoice"], CORE["invoice_line"]


def test_volumes_match_the_brief():
    assert len(CORE["student"]) == 10_000
    assert len(ENR) == 30_000 and len(INV) == 30_000


def test_one_enrollment_per_student_per_term_and_one_invoice_each():
    assert len({(e["student_id"], e["term_id"]) for e in ENR}) == 30_000
    per_student = Counter(e["student_id"] for e in ENR)
    assert set(per_student.values()) == {3}
    assert len({i["enrollment_id"] for i in INV}) == 30_000


def test_clean_baseline_has_zero_validation_issues():
    assert run_all(CORE) == []


def test_invoice_ids_are_per_student_sequential():
    by_student = defaultdict(list)
    for inv in INV:
        by_student[inv["student_id"]].append(inv["invoice_id"])
    ids_for_first = by_student["STU-000001"]
    assert ids_for_first == [
        "INV-STU-000001-2026-000001", "INV-STU-000001-2026-000002", "INV-STU-000001-2026-000003"]
    assert all(ids.is_valid("invoice", i["invoice_id"]) for i in INV)


def test_outcome_mix_and_withdrawal_timing_cover_every_refund_tier():
    n = len(ENR)
    mix = Counter(e["status"] for e in ENR)
    assert 0.03 <= mix["WITHDRAWN"] / n <= 0.05
    assert 0.01 <= mix["CANCELLED"] / n <= 0.02
    assert mix["COMPLETED"] + mix["WITHDRAWN"] + mix["CANCELLED"] == n  # as-of date is after every term
    starts = {t["term_id"]: t["start_date"] for t in CORE["term"]}
    days = [(e["withdrawn_on"] - starts[e["term_id"]]).days for e in ENR if e["status"] == "WITHDRAWN"]
    assert any(d <= 14 for d in days) and any(15 <= d <= 30 for d in days)
    assert any(31 <= d <= 45 for d in days) and any(d > 45 for d in days)
    assert all(d >= 1 for d in days)


def test_cancelled_enrollments_have_cancelled_invoices_and_nothing_else_does():
    status_by_enr = {e["enrollment_id"]: e["status"] for e in ENR}
    for inv in INV:
        expected = "CANCELLED" if status_by_enr[inv["enrollment_id"]] == "CANCELLED" else "ISSUED"
        assert inv["status"] == expected


def test_invoice_lines_follow_the_price_list():
    lines_per_invoice = Counter(ln["invoice_id"] for ln in LINES)
    assert set(lines_per_invoice.values()) == {4, 5}  # lab programs get a LAB line
    # same program, different term: summer invoice is cheaper than spring, fall dearer
    stu = CORE["student"][0]["student_id"]
    totals = {i["term_id"]: i["total_amount"] for i in INV if i["student_id"] == stu}
    assert totals["TERM-2026-SUMMER"] < totals["TERM-2026-SPRING"] < totals["TERM-2026-FALL"]
    # B.Tech CS (PRG-001): 90000+8000+1500+3000+2000 = 104500 in Spring
    cs = next(i for i in INV if i["term_id"] == "TERM-2026-SPRING"
              and next(s for s in CORE["student"] if s["student_id"] == i["student_id"])["program_id"] == "PRG-001")
    assert cs["total_amount"] == Decimal("104500.00")


def test_dates_make_sense():
    terms = {t["term_id"]: t for t in CORE["term"]}
    enr = {e["enrollment_id"]: e for e in ENR}
    for inv in INV:
        start = terms[inv["term_id"]]["start_date"]
        assert enr[inv["enrollment_id"]]["enrolled_on"] <= inv["issue_date"] < start
        assert inv["due_date"] > inv["issue_date"]


def test_status_events_are_numbered_in_time_order():
    events = CORE["status_event"]
    assert [e["event_id"] for e in events] == [ids.status_event_id(i) for i in range(1, len(events) + 1)]
    dates = [e["event_date"] for e in events]
    assert dates == sorted(dates)
    first = Counter(e["to_status"] for e in events if e["from_status"] is None)
    assert first == {"ENROLLED": 30_000, "ISSUED": 30_000}


def test_recompute_totals_restores_correct_values():
    small = build_core(Config(scale=0.02))
    expected = [i["total_amount"] for i in small["invoice"]]
    for i in small["invoice"]:
        i["total_amount"] = Decimal("0.00")
    recompute_invoice_totals(small["invoice"], small["invoice_line"])
    assert [i["total_amount"] for i in small["invoice"]] == expected


def test_same_seed_same_data_different_seed_different_data():
    assert build_core(Config(scale=0.05)) == build_core(Config(scale=0.05))
    a = [e["status"] for e in build_core(Config(seed=1, scale=0.2))["enrollment"]]
    b = [e["status"] for e in build_core(Config(seed=2, scale=0.2))["enrollment"]]
    assert a != b
