"""Deterministic, zero-padded, immutable ID builders and format checks.

Conventions (from the problem statement):
    STU-000001            student
    TERM-2026-FALL        term
    INV-<student-id>-2026-000001
                          invoice; <student-id> is the full student ID, so
                          the result looks like INV-STU-000001-2026-000001.
                          The trailing counter is per student per year.
    SCH-2026-000001       scholarship award
    PAY-2026-000001       payment
    ALLOC-<payment-id>-01 payment allocation, per payment

Conventions not fixed by the statement (our choice, documented in DESIGN.md):
    PRG-001, FSC-00001, ENR-000001, ELG-001, LINE-<invoice-id>-01,
    REF-2026-000001, LED-00000001, EVT-00000001
"""
from __future__ import annotations

import re


def student_id(n: int) -> str:
    return f"STU-{n:06d}"


def term_id(year: int, name: str) -> str:
    return f"TERM-{year}-{name.upper()}"


def program_id(n: int) -> str:
    return f"PRG-{n:03d}"


def fee_schedule_id(n: int) -> str:
    return f"FSC-{n:05d}"


def enrollment_id(n: int) -> str:
    return f"ENR-{n:06d}"


def invoice_id(student: str, year: int, seq: int) -> str:
    return f"INV-{student}-{year}-{seq:06d}"


def invoice_line_id(invoice: str, n: int) -> str:
    return f"LINE-{invoice}-{n:02d}"


def eligibility_id(n: int) -> str:
    return f"ELG-{n:03d}"


def scholarship_id(year: int, n: int) -> str:
    return f"SCH-{year}-{n:06d}"


def payment_id(year: int, n: int) -> str:
    return f"PAY-{year}-{n:06d}"


def allocation_id(payment: str, n: int) -> str:
    return f"ALLOC-{payment}-{n:02d}"


def refund_id(year: int, n: int) -> str:
    return f"REF-{year}-{n:06d}"


def ledger_entry_id(n: int) -> str:
    return f"LED-{n:08d}"


def status_event_id(n: int) -> str:
    return f"EVT-{n:08d}"


_STU = r"STU-\d{6}"
_PAY = r"PAY-\d{4}-\d{6}"
_INV = rf"INV-{_STU}-\d{{4}}-\d{{6}}"

PATTERNS: dict[str, re.Pattern[str]] = {
    "student": re.compile(rf"^{_STU}$"),
    "term": re.compile(r"^TERM-\d{4}-[A-Z]+$"),
    "program": re.compile(r"^PRG-\d{3}$"),
    "fee_schedule": re.compile(r"^FSC-\d{5}$"),
    "enrollment": re.compile(r"^ENR-\d{6}$"),
    "invoice": re.compile(rf"^{_INV}$"),
    "invoice_line": re.compile(rf"^LINE-{_INV}-\d{{2}}$"),
    "eligibility": re.compile(r"^ELG-\d{3}$"),
    "scholarship": re.compile(r"^SCH-\d{4}-\d{6}$"),
    "payment": re.compile(rf"^{_PAY}$"),
    "payment_allocation": re.compile(rf"^ALLOC-{_PAY}-\d{{2}}$"),
    "refund": re.compile(r"^REF-\d{4}-\d{6}$"),
    "ledger_entry": re.compile(r"^LED-\d{8}$"),
    "status_event": re.compile(r"^EVT-\d{8}$"),
}


def is_valid(kind: str, value: str) -> bool:
    """True if `value` matches the ID format of entity `kind`."""
    return bool(PATTERNS[kind].match(value))
