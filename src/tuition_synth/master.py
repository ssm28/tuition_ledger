"""Generators for the master (parent) tables.

Order matters: terms and programs first, then tables that point at them.
Every function returns a list of plain dicts whose keys match schema.py.

Randomness: each table gets its own random stream derived from
(seed, table label). Changing how one table is generated therefore never
shifts the numbers drawn for another table.
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from . import ids
from .config import TERMS, Config
from .reference_data import (
    FIRST_NAMES, LAST_NAMES, OTHER_FEES, PROGRAMS, SCHEDULE_LEAD_DAYS,
    SCHEMES, TERM_FEE_FACTOR,
)
from .schema import FEE_TYPES, INCOME_BANDS

Rows = list[dict]

INVOICE_DUE_DAYS = 30
INCOME_WEIGHTS = (30, 50, 20)  # LOW, MIDDLE, HIGH
CGPA_MEAN, CGPA_SD, CGPA_MIN, CGPA_MAX = 7.2, 1.0, 4.0, 10.0

# Admission year choices and weights per level; age at admission range (years).
_ADMISSION_YEARS = {"UG": ((2022, 2023, 2024, 2025), (20, 25, 30, 25)),
                    "PG": ((2024, 2025), (40, 60))}
_ADMISSION_AGE = {"UG": (17, 21), "PG": (21, 27)}


def rng_for(cfg: Config, label: str) -> random.Random:
    """Independent, reproducible random stream for one table."""
    return random.Random(f"{cfg.seed}:{label}")


def money(value) -> Decimal:
    """Exact 2-place decimal, rounded half-up. Money is never a float."""
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_terms() -> Rows:
    return [
        {"term_id": tid, "label": label, "start_date": start, "end_date": end,
         "invoice_due_days": INVOICE_DUE_DAYS}
        for tid, label, start, end in TERMS
    ]


def build_programs() -> Rows:
    return [
        {"program_id": ids.program_id(i), "program_code": code, "name": name, "level": level}
        for i, (code, name, level, *_rest) in enumerate(PROGRAMS, start=1)
    ]


def build_fee_schedules(programs: Rows, terms: Rows) -> Rows:
    """One row per (program, term, fee type). Amounts come from the catalog."""
    catalog = {p[0]: p for p in PROGRAMS}
    rows: Rows = []
    n = 0
    for prog in programs:
        _code, _name, _level, tuition, has_lab, _w = catalog[prog["program_code"]]
        base = {"TUITION": tuition, **OTHER_FEES}
        for term in terms:
            factor = Decimal(TERM_FEE_FACTOR[term["term_id"]])
            for fee_type in FEE_TYPES:
                if fee_type == "LAB" and not has_lab:
                    continue
                n += 1
                rows.append({
                    "fee_schedule_id": ids.fee_schedule_id(n),
                    "program_id": prog["program_id"],
                    "term_id": term["term_id"],
                    "fee_type": fee_type,
                    "amount": money(Decimal(base[fee_type]) * factor),
                    "effective_from": term["start_date"] - timedelta(days=SCHEDULE_LEAD_DAYS),
                    "effective_to": term["end_date"],
                    "status": "ACTIVE",
                })
    return rows


def build_eligibility(programs: Rows) -> Rows:
    id_by_code = {p["program_code"]: p["program_id"] for p in programs}
    rows: Rows = []
    for i, (name, min_cgpa, band, code, a_type, a_value, cap, start, end) in enumerate(SCHEMES, start=1):
        rows.append({
            "eligibility_id": ids.eligibility_id(i),
            "name": name,
            "min_cgpa": money(min_cgpa),
            "max_income_band": band,
            "program_id": id_by_code[code] if code else None,
            "award_type": a_type,
            "award_value": money(a_value),
            "max_award_amount": money(cap),
            "effective_from": start,
            "effective_to": end,
        })
    return rows


def build_students(cfg: Config, programs: Rows) -> Rows:
    rng = rng_for(cfg, "student")
    n = cfg.volume("students")
    catalog = {p[0]: p for p in PROGRAMS}
    weights = [catalog[p["program_code"]][5] for p in programs]
    chosen = rng.choices(programs, weights=weights, k=n)

    rows: Rows = []
    for i, prog in enumerate(chosen, start=1):
        level = prog["level"]
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)

        years, year_weights = _ADMISSION_YEARS[level]
        year = rng.choices(years, weights=year_weights, k=1)[0]
        admission = date(year, 8, 1) + timedelta(days=rng.randint(0, 30))

        age_min, age_max = _ADMISSION_AGE[level]
        age_days = rng.randint(int(age_min * 365.25) + 1, int((age_max + 1) * 365.25) - 1)

        cgpa = min(CGPA_MAX, max(CGPA_MIN, rng.gauss(CGPA_MEAN, CGPA_SD)))
        band = rng.choices(INCOME_BANDS, weights=INCOME_WEIGHTS, k=1)[0]

        rows.append({
            "student_id": ids.student_id(i),
            "full_name": f"{first} {last}",
            "email": f"{first}.{last}.{i:06d}@example.edu".lower(),
            "date_of_birth": admission - timedelta(days=age_days),
            "program_id": prog["program_id"],
            "admission_date": admission,
            "cgpa": money(f"{cgpa:.2f}"),
            "family_income_band": band,
            "status": "ACTIVE",  # baseline: every student is active; changes become status_events later
        })
    return rows


def build_master(cfg: Config) -> dict[str, Rows]:
    """All master tables, parents before children."""
    terms = build_terms()
    programs = build_programs()
    return {
        "term": terms,
        "program": programs,
        "student": build_students(cfg, programs),
        "fee_schedule": build_fee_schedules(programs, terms),
        "eligibility": build_eligibility(programs),
    }
