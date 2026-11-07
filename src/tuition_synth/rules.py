"""Business rules as small pure functions, shared by the generators and the validator.

Keeping the rules in one place means "what the data should look like" is
written down once. DESIGN.md describes the same rules in words.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from .master import money
from .schema import FEE_TYPES

INCOME_RANK = {"LOW": 0, "MIDDLE": 1, "HIGH": 2}
GRACE_DAYS = 15                      # days after the due date before a late fee applies
LATE_FEE_AMOUNT = money("500")       # fixed late fee, charged once per invoice
CHARGE_LINE_TYPES = FEE_TYPES + ("LATE_FEE",)

# Withdrawal refund: share of the tuition paid, by days since term start.
# (last day of tier, share). Later than the last tier: nothing is refunded.
REFUND_TIERS = ((14, Decimal("1.00")), (30, Decimal("0.50")), (45, Decimal("0.25")))


def is_eligible(student: dict, scheme: dict, on) -> bool:
    """Does `student` meet the scheme's criteria on date `on`?"""
    if student["cgpa"] < scheme["min_cgpa"]:
        return False
    band = scheme["max_income_band"]
    if band and INCOME_RANK[student["family_income_band"]] > INCOME_RANK[band]:
        return False
    if scheme["program_id"] and student["program_id"] != scheme["program_id"]:
        return False
    if on < scheme["effective_from"]:
        return False
    return scheme["effective_to"] is None or on <= scheme["effective_to"]


def award_amount(scheme: dict, tuition):
    """Award for one term: percent of tuition or a fixed sum, never above the
    scheme cap and never above the tuition itself (the 'eligible fees')."""
    if scheme["award_type"] == "PERCENT_OF_TUITION":
        raw = tuition * scheme["award_value"] / 100
    else:
        raw = scheme["award_value"]
    return money(min(raw, scheme["max_award_amount"], tuition))


def grace_end(invoice: dict):
    return invoice["due_date"] + timedelta(days=GRACE_DAYS)


def late_fee_date(invoice: dict):
    """First day a late fee can be charged: the day after the grace period ends."""
    return grace_end(invoice) + timedelta(days=1)


def line_net_dues(lines: list) -> dict:
    """For one invoice: charge line id -> amount still payable after credits.

    A WAIVER reduces the fee line it points to (same fee_schedule_id);
    a SCHOLARSHIP_CREDIT reduces the TUITION line. Payments are allocated
    against these net amounts.
    """
    dues = {ln["invoice_line_id"]: ln["amount"] for ln in lines if ln["line_type"] in CHARGE_LINE_TYPES}
    by_schedule = {ln["fee_schedule_id"]: ln["invoice_line_id"] for ln in lines if ln["line_type"] in FEE_TYPES}
    tuition = next((ln["invoice_line_id"] for ln in lines if ln["line_type"] == "TUITION"), None)
    for ln in lines:
        if ln["line_type"] == "WAIVER":
            target = by_schedule.get(ln["fee_schedule_id"])
        elif ln["line_type"] == "SCHOLARSHIP_CREDIT":
            target = tuition
        else:
            continue
        if target in dues:
            dues[target] += ln["amount"]
    return dues


def refund_share(days_since_term_start: int) -> Decimal:
    """Share of paid tuition refunded for a withdrawal `days_since_term_start` days into the term."""
    for last_day, share in REFUND_TIERS:
        if days_since_term_start <= last_day:
            return share
    return Decimal("0.00")
