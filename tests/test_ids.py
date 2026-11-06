from tuition_synth import ids


def test_documented_examples():
    assert ids.student_id(1) == "STU-000001"
    assert ids.term_id(2026, "fall") == "TERM-2026-FALL"
    assert ids.invoice_id("STU-000001", 2026, 1) == "INV-STU-000001-2026-000001"
    assert ids.scholarship_id(2026, 1) == "SCH-2026-000001"
    assert ids.payment_id(2026, 1) == "PAY-2026-000001"
    assert ids.allocation_id("PAY-2026-000001", 1) == "ALLOC-PAY-2026-000001-01"


def test_builders_match_their_patterns():
    stu = ids.student_id(42)
    inv = ids.invoice_id(stu, 2026, 3)
    pay = ids.payment_id(2026, 50000)
    samples = {
        "student": stu,
        "term": ids.term_id(2026, "summer"),
        "program": ids.program_id(7),
        "fee_schedule": ids.fee_schedule_id(12),
        "enrollment": ids.enrollment_id(9),
        "invoice": inv,
        "invoice_line": ids.invoice_line_id(inv, 2),
        "eligibility": ids.eligibility_id(4),
        "scholarship": ids.scholarship_id(2026, 15000),
        "payment": pay,
        "payment_allocation": ids.allocation_id(pay, 1),
        "refund": ids.refund_id(2026, 5),
        "ledger_entry": ids.ledger_entry_id(1),
        "status_event": ids.status_event_id(1),
    }
    assert set(samples) == set(ids.PATTERNS)
    for kind, value in samples.items():
        assert ids.is_valid(kind, value), (kind, value)


def test_malformed_ids_rejected():
    assert not ids.is_valid("student", "STU-1")
    assert not ids.is_valid("student", "stu-000001")
    assert not ids.is_valid("invoice", "INV-STU-000001-2026-1")
    assert not ids.is_valid("payment_allocation", "ALLOC-PAY-2026-000001")


def test_ids_sort_lexicographically_in_creation_order():
    values = [ids.student_id(n) for n in (1, 2, 10, 9999, 10000)]
    assert values == sorted(values)
