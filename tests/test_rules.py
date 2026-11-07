"""Boundary tests for the pure business rules (no generated data needed)."""
from datetime import date
from decimal import Decimal

from tuition_synth.rules import (
    LATE_FEE_AMOUNT, award_amount, grace_end, is_eligible, late_fee_date, line_net_dues,
)

D = Decimal


def scheme(**over):
    base = {"min_cgpa": D("8.00"), "max_income_band": None, "program_id": None,
            "award_type": "PERCENT_OF_TUITION", "award_value": D("25.00"),
            "max_award_amount": D("30000.00"), "effective_from": date(2025, 12, 1), "effective_to": None}
    return {**base, **over}


def student(**over):
    base = {"cgpa": D("8.00"), "family_income_band": "MIDDLE", "program_id": "PRG-001"}
    return {**base, **over}


ON = date(2026, 3, 1)


def test_cgpa_boundary_is_inclusive():
    assert is_eligible(student(cgpa=D("8.00")), scheme(), ON)
    assert not is_eligible(student(cgpa=D("7.99")), scheme(), ON)


def test_income_band_means_this_band_or_lower():
    s = scheme(max_income_band="MIDDLE")
    assert is_eligible(student(family_income_band="LOW"), s, ON)
    assert is_eligible(student(family_income_band="MIDDLE"), s, ON)
    assert not is_eligible(student(family_income_band="HIGH"), s, ON)


def test_program_specific_scheme():
    s = scheme(program_id="PRG-001")
    assert is_eligible(student(program_id="PRG-001"), s, ON)
    assert not is_eligible(student(program_id="PRG-002"), s, ON)


def test_effective_window_is_inclusive_at_both_ends():
    s = scheme(effective_from=date(2026, 1, 1), effective_to=date(2026, 7, 31))
    assert is_eligible(student(), s, date(2026, 1, 1))
    assert is_eligible(student(), s, date(2026, 7, 31))
    assert not is_eligible(student(), s, date(2025, 12, 31))
    assert not is_eligible(student(), s, date(2026, 8, 1))


def test_award_percent_and_cap():
    assert award_amount(scheme(), D("90000.00")) == D("22500.00")        # 25%
    assert award_amount(scheme(), D("200000.00")) == D("30000.00")       # capped by scheme


def test_award_never_exceeds_tuition():
    fixed = scheme(award_type="FIXED_AMOUNT", award_value=D("15000.00"), max_award_amount=D("15000.00"))
    assert award_amount(fixed, D("10000.00")) == D("10000.00")           # fixed sum above the fees
    assert award_amount(fixed, D("90000.00")) == D("15000.00")


def test_late_fee_starts_the_day_after_the_grace_period():
    inv = {"due_date": date(2026, 2, 1)}
    assert grace_end(inv) == date(2026, 2, 16)        # 15 days after due: still no fee
    assert late_fee_date(inv) == date(2026, 2, 17)    # fee applies from here
    assert LATE_FEE_AMOUNT == D("500.00")


def line(lid, kind, amount, sched=None):
    return {"invoice_line_id": lid, "line_type": kind, "amount": D(amount), "fee_schedule_id": sched}


def test_net_dues_apply_credits_to_the_right_lines():
    lines = [
        line("L1", "TUITION", "90000", "FSC-1"), line("L2", "LAB", "8000", "FSC-2"),
        line("L3", "SCHOLARSHIP_CREDIT", "-20000"), line("L4", "WAIVER", "-8000", "FSC-2"),
        line("L5", "LATE_FEE", "500"),
    ]
    dues = line_net_dues(lines)
    assert dues == {"L1": D("70000"), "L2": D("0"), "L5": D("500")}
    assert sum(dues.values()) == sum(ln["amount"] for ln in lines)
