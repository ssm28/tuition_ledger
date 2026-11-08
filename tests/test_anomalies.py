"""Anomaly injection, ground truth and detection scoring (full scale)."""
import inspect
from collections import Counter, defaultdict
from decimal import Decimal

from tuition_synth.anomalies import ISSUE_CHECKS, score_detection
from tuition_synth.config import Config
from tuition_synth.pipeline import build_all, build_dataset
from tuition_synth.schema import TABLES
from tuition_synth.validate import run_all

CFG = Config()
BASE = build_all(CFG)
TABLES_X, TRUTH = build_dataset(CFG)
ISSUES = run_all(TABLES_X)
SCORE = score_detection(ISSUES, TRUTH)


def test_twenty_of_each_of_the_five_types():
    assert Counter(g["issue_type"] for g in TRUTH) == {t: 20 for t in ISSUE_CHECKS}
    assert len({g["anomaly_id"] for g in TRUTH}) == 100


def test_each_anomaly_sits_on_its_own_student():
    students = [g["student_id"] for g in TRUTH]
    assert len(set(students)) == len(students)


def test_every_labelled_row_exists_in_the_data():
    keys = {t: {r[TABLES[t].pk] for r in rows} for t, rows in TABLES_X.items()}
    for g in TRUTH:
        assert g["row_id"] in keys[g["table"]], g


def test_validator_finds_every_injected_anomaly():
    assert SCORE["detected"] == SCORE["injected"] == 100 and SCORE["recall"] == 1.0
    for stats in SCORE["per_type"].values():
        assert stats["detected"] == stats["injected"]


def test_no_collateral_damage_on_unlabelled_rows():
    assert SCORE["unexplained"] == []


def test_the_clean_baseline_has_no_issues_so_every_issue_comes_from_an_injection():
    assert run_all(BASE) == []
    assert len(ISSUES) >= 100


def test_validator_never_receives_ground_truth():
    assert list(inspect.signature(run_all).parameters) == ["tables", "as_of"]
    assert not any("issue_type" in t.field_names or "anomaly_id" in t.field_names for t in TABLES.values())
    assert "ground_truth" not in TABLES_X


def test_labels_describe_what_really_happened():
    alloc_total = defaultdict(Decimal)
    for a in TABLES_X["payment_allocation"]:
        alloc_total[a["payment_id"]] += a["amount"]
    pay = {p["payment_id"]: p for p in TABLES_X["payment"]}
    invoices = {i["invoice_id"]: i for i in TABLES_X["invoice"]}
    for g in TRUTH:
        rel = g["related_ids"].split(";")
        if g["issue_type"] == "ALLOCATION_EXCEEDS_PAYMENT":
            assert alloc_total[rel[0]] > pay[rel[0]]["amount"]
        elif g["issue_type"] == "DUPLICATE_INVOICE":
            dup, orig = invoices[g["row_id"]], invoices[rel[0]]
            assert dup["enrollment_id"] == orig["enrollment_id"] and dup["status"] != "CANCELLED"
        elif g["issue_type"] == "REFUND_EXCEEDS_NET_PAID":
            refund = next(r for r in TABLES_X["refund"] if r["refund_id"] == g["row_id"])
            paid = sum(p["amount"] for p in TABLES_X["payment"] if p["student_id"] == g["student_id"])
            assert refund["amount"] > paid - sum(
                r["amount"] for r in TABLES_X["refund"]
                if r["student_id"] == g["student_id"] and r["status"] == "PAID" and r["refund_id"] != g["row_id"])


def test_injection_changes_only_labelled_students():
    labelled = {g["student_id"] for g in TRUTH}
    key = lambda e: (e["source_table"], e["source_id"], e["entry_type"])
    before = {key(e): e for e in BASE["ledger_entry"]}
    after = {key(e): e for e in TABLES_X["ledger_entry"]}
    changed = {k for k in set(before) | set(after) if before.get(k, {}).get("amount") != after.get(k, {}).get("amount")}
    owners = {(before.get(k) or after.get(k))["student_id"] for k in changed}
    assert owners <= labelled
    # source tables: the rows that differ from the baseline all belong to labelled students
    for name in ("payment_allocation", "scholarship", "invoice", "refund", "payment"):
        base_rows = {r[TABLES[name].pk]: r for r in BASE[name]}
        for r in TABLES_X[name]:
            if base_rows.get(r[TABLES[name].pk]) != r:
                student = r.get("student_id")
                if student is None:   # allocations carry no student: look it up through the payment
                    student = next(p["student_id"] for p in TABLES_X["payment"] if p["payment_id"] == r["payment_id"])
                assert student in labelled, (name, r)


def test_small_scale_also_finds_everything_and_is_deterministic():
    cfg = Config(scale=0.02)
    t1, g1 = build_dataset(cfg)
    t2, g2 = build_dataset(cfg)
    assert g1 == g2 and len(g1) == 15            # at least 3 per type
    score = score_detection(run_all(t1), g1)
    assert score["recall"] == 1.0 and score["unexplained"] == []


def test_no_anomaly_run_stays_clean():
    tables, truth = build_dataset(Config(scale=0.02), anomalies=False)
    assert truth == [] and run_all(tables) == []
