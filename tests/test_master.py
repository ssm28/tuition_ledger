import tempfile
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from tuition_synth import ids
from tuition_synth.cli import main
from tuition_synth.config import TERMS, Config
from tuition_synth.export import sha256_of
from tuition_synth.master import build_master
from tuition_synth.reference_data import SCHEMES
from tuition_synth.schema import TABLES

CFG = Config(scale=1.0)
MASTER = build_master(CFG)
ID_KIND = {"term": "term", "program": "program", "student": "student",
           "fee_schedule": "fee_schedule", "eligibility": "eligibility"}


def test_row_counts():
    assert len(MASTER["term"]) == 3
    assert len(MASTER["program"]) == 20
    assert len(MASTER["student"]) == 10_000
    assert len(MASTER["eligibility"]) == len(SCHEMES)
    # 12 programs with a lab fee (5 fee types) + 8 without (4), over 3 terms
    assert len(MASTER["fee_schedule"]) == (12 * 5 + 8 * 4) * 3


def test_row_keys_match_schema_exactly_and_in_order():
    for table, rows in MASTER.items():
        assert rows, table
        for row in rows:
            assert list(row) == TABLES[table].field_names, table


def test_primary_keys_unique_and_well_formed():
    for table, rows in MASTER.items():
        pk = TABLES[table].pk
        values = [r[pk] for r in rows]
        assert len(values) == len(set(values)), table
        assert all(ids.is_valid(ID_KIND[table], v) for v in values), table


def test_required_fields_present_and_enums_respected():
    for table, rows in MASTER.items():
        for f in TABLES[table].fields:
            for row in rows:
                value = row[f.name]
                if f.required:
                    assert value is not None and value != "", (table, f.name)
                if f.allowed and value is not None:
                    assert value in f.allowed, (table, f.name, value)


def test_foreign_keys_resolve():
    for table, rows in MASTER.items():
        for f in TABLES[table].foreign_keys():
            ref_table, ref_col = f.fk.split(".")
            valid = {r[ref_col] for r in MASTER[ref_table]}
            for row in rows:
                if row[f.name] is not None:
                    assert row[f.name] in valid, (table, f.name, row[f.name])


def test_unique_business_keys():
    emails = [r["email"] for r in MASTER["student"]]
    codes = [r["program_code"] for r in MASTER["program"]]
    assert len(set(emails)) == len(emails)
    assert len(set(codes)) == len(codes)
    keys = [(r["program_id"], r["term_id"], r["fee_type"], r["effective_from"])
            for r in MASTER["fee_schedule"]]
    assert len(set(keys)) == len(keys)


# Independent source of truth: the rules written in DESIGN.md, NOT imported from
# the code under test. If someone edits the factors in reference_data.py, this
# test must fail.
EXPECTED_FACTORS = {
    "TERM-2026-SPRING": Decimal("1.00"),
    "TERM-2026-SUMMER": Decimal("0.60"),
    "TERM-2026-FALL": Decimal("1.05"),
}


def test_term_specific_fees_follow_the_documented_factors():
    amount = {(r["program_id"], r["term_id"], r["fee_type"]): r["amount"]
              for r in MASTER["fee_schedule"]}
    for (prog, term, fee), value in amount.items():
        spring = amount[(prog, "TERM-2026-SPRING", fee)]
        assert value == (spring * EXPECTED_FACTORS[term]).quantize(Decimal("0.01")), (prog, term, fee)


def test_known_price_points():
    """Hand-checked prices: B.Tech CS (PRG-001) tuition and LAB fee."""
    amount = {(r["program_id"], r["term_id"], r["fee_type"]): r["amount"]
              for r in MASTER["fee_schedule"]}
    assert amount[("PRG-001", "TERM-2026-SPRING", "TUITION")] == Decimal("90000.00")
    assert amount[("PRG-001", "TERM-2026-SUMMER", "TUITION")] == Decimal("54000.00")
    assert amount[("PRG-001", "TERM-2026-FALL", "TUITION")] == Decimal("94500.00")
    assert amount[("PRG-001", "TERM-2026-SUMMER", "LAB")] == Decimal("4800.00")


def test_date_ordering():
    for t in MASTER["term"]:
        assert t["start_date"] < t["end_date"]
    for f in MASTER["fee_schedule"]:
        assert f["effective_from"] <= f["effective_to"]
        assert f["amount"] >= 0
    first_term_start = min(t["start_date"] for t in MASTER["term"])
    for s in MASTER["student"]:
        assert s["admission_date"] < first_term_start
        age = (s["admission_date"] - s["date_of_birth"]).days / 365.25
        assert 17 <= age <= 40
    for e in MASTER["eligibility"]:
        assert e["effective_to"] is None or e["effective_from"] <= e["effective_to"]


def test_eligibility_values_are_sane():
    for e in MASTER["eligibility"]:
        assert 0 <= e["min_cgpa"] <= 10
        assert e["max_award_amount"] > 0 and e["award_value"] > 0
        if e["award_type"] == "PERCENT_OF_TUITION":
            assert e["award_value"] <= 100


def test_student_distributions_are_realistic():
    students = MASTER["student"]
    cgpas = [float(s["cgpa"]) for s in students]
    assert all(4.0 <= c <= 10.0 for c in cgpas)
    assert 6.9 <= sum(cgpas) / len(cgpas) <= 7.5
    bands = Counter(s["family_income_band"] for s in students)
    assert abs(bands["LOW"] / len(students) - 0.30) < 0.03
    assert abs(bands["MIDDLE"] / len(students) - 0.50) < 0.03
    assert abs(bands["HIGH"] / len(students) - 0.20) < 0.03
    per_program = Counter(s["program_id"] for s in students)
    assert len(per_program) == 20  # every program has students
    assert max(per_program.values()) > 3 * min(per_program.values())  # uneven, like real life


def test_same_seed_gives_identical_data_and_other_seed_differs():
    assert build_master(Config(scale=0.05)) == build_master(Config(scale=0.05))
    a = build_master(Config(seed=1, scale=0.05))["student"]
    b = build_master(Config(seed=2, scale=0.05))["student"]
    assert [s["cgpa"] for s in a] != [s["cgpa"] for s in b]


def test_csv_export_is_byte_reproducible():
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        for out in (d1, d2):
            assert main(["generate", "--scale", "0.02", "--out", out]) == 0
        for name in ("student", "program", "term", "fee_schedule", "eligibility"):
            p1, p2 = Path(d1) / "csv" / f"{name}.csv", Path(d2) / "csv" / f"{name}.csv"
            assert sha256_of(p1) == sha256_of(p2), name
        header = (Path(d1) / "csv" / "student.csv").read_text(encoding="utf-8").splitlines()[0]
        assert header.split(",") == TABLES["student"].field_names
