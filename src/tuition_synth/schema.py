"""Schema: the single source of truth for tables, fields, enums and keys.

The data dictionary (docs/data_dictionary.md) is generated from this module,
and the validator reuses it for enum / primary-key / foreign-key checks, so
documentation and checks cannot drift apart.

Money: decimal, 2 places, currency INR (see DESIGN.md). Dates: ISO-8601
(YYYY-MM-DD). No wall-clock timestamps are used, for reproducibility.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------- enums
LEVELS = ("UG", "PG")
INCOME_BANDS = ("LOW", "MIDDLE", "HIGH")
STUDENT_STATUS = ("ACTIVE", "WITHDRAWN", "GRADUATED")
FEE_TYPES = ("TUITION", "LAB", "LIBRARY", "TECHNOLOGY", "ACTIVITY")
SCHEDULE_STATUS = ("ACTIVE", "SUPERSEDED")
ENROLLMENT_STATUS = ("ENROLLED", "WITHDRAWN", "COMPLETED", "CANCELLED")
INVOICE_STATUS = ("ISSUED", "PARTIALLY_PAID", "PAID", "OVERDUE", "CANCELLED")
LINE_TYPES = FEE_TYPES + ("LATE_FEE", "SCHOLARSHIP_CREDIT", "WAIVER")
AWARD_TYPES = ("PERCENT_OF_TUITION", "FIXED_AMOUNT")
SCHOLARSHIP_STATUS = ("AWARDED", "APPLIED", "REVOKED")
PAYMENT_METHODS = ("UPI", "CARD", "NET_BANKING", "BANK_TRANSFER", "CASH")
PAYMENT_STATUS = ("POSTED", "REVERSED")
REFUND_REASONS = ("WITHDRAWAL", "CANCELLATION", "OVERPAYMENT")
REFUND_STATUS = ("REQUESTED", "APPROVED", "PAID", "REJECTED")
LEDGER_TYPES = (
    "CHARGE", "SCHOLARSHIP_CREDIT", "WAIVER", "LATE_FEE", "PAYMENT", "REFUND", "REVERSAL",
)
EVENT_ENTITIES = ("enrollment", "invoice", "scholarship", "payment", "refund")

# Allowed status transitions per entity: {from_status: (to_status, ...)}.
# `None` is the starting point (the row is created in its first status).
LIFECYCLES = {
    "enrollment": {None: ("ENROLLED",), "ENROLLED": ("WITHDRAWN", "COMPLETED", "CANCELLED")},
    "invoice": {
        None: ("ISSUED",),
        "ISSUED": ("PARTIALLY_PAID", "PAID", "OVERDUE", "CANCELLED"),
        "PARTIALLY_PAID": ("PAID", "OVERDUE", "CANCELLED"),
        "OVERDUE": ("PARTIALLY_PAID", "PAID", "CANCELLED"),
    },
    "scholarship": {None: ("AWARDED",), "AWARDED": ("APPLIED", "REVOKED")},
    "payment": {None: ("POSTED",), "POSTED": ("REVERSED",)},
    "refund": {None: ("REQUESTED",), "REQUESTED": ("APPROVED", "REJECTED"), "APPROVED": ("PAID",)},
}


# ---------------------------------------------------------------- model
@dataclass(frozen=True)
class Field:
    name: str
    type: str  # string | int | decimal | date
    required: bool = True
    allowed: tuple = ()
    unit: str = ""
    unique: bool = False
    rule: str = ""
    fk: str = ""  # "table.column" this field references


@dataclass(frozen=True)
class Table:
    name: str
    entity: str
    pk: str
    description: str
    fields: tuple
    relationships: tuple = ()
    extension: bool = False  # True = added by us, not in the statement's entity list

    @property
    def field_names(self) -> list:
        return [f.name for f in self.fields]

    def foreign_keys(self) -> list:
        return [f for f in self.fields if f.fk]


def _pk(name: str, rule: str) -> Field:
    return Field(name, "string", True, unique=True, rule=rule)


# ---------------------------------------------------------------- tables
TERM = Table(
    "term", "Term", "term_id",
    "Academic term. Reference table (extension): needed for dates and term-specific fees.",
    (
        _pk("term_id", "TERM-<year>-<NAME>, e.g. TERM-2026-FALL"),
        Field("label", "string", rule="Human-readable name"),
        Field("start_date", "date", rule="start_date < end_date"),
        Field("end_date", "date"),
        Field("invoice_due_days", "int", unit="days", rule="> 0; due_date = issue_date + this"),
    ),
    ("Term 1:N FeeSchedule", "Term 1:N Enrollment", "Term 1:N Invoice"),
    extension=True,
)

PROGRAM = Table(
    "program", "Program", "program_id",
    "Academic program (20 in the baseline).",
    (
        _pk("program_id", "PRG-NNN"),
        Field("program_code", "string", unique=True, rule="Short code, e.g. BTECH-CS"),
        Field("name", "string"),
        Field("level", "string", allowed=LEVELS),
    ),
    ("Program 1:N Student (home program)", "Program 1:N FeeSchedule", "Program 1:N Enrollment"),
)

STUDENT = Table(
    "student", "Student", "student_id",
    "Synthetic student. All personal data is fabricated.",
    (
        _pk("student_id", "STU-NNNNNN"),
        Field("full_name", "string", rule="Fabricated name"),
        Field("email", "string", unique=True, rule="Fabricated, @example.edu domain"),
        Field("date_of_birth", "date", rule="Age 17-40 at admission_date"),
        Field("program_id", "string", fk="program.program_id", rule="Home program"),
        Field("admission_date", "date"),
        Field("cgpa", "decimal", unit="points (0-10 scale)", rule="0.00 <= cgpa <= 10.00; drives eligibility"),
        Field("family_income_band", "string", allowed=INCOME_BANDS, rule="Drives need-based eligibility"),
        Field("status", "string", allowed=STUDENT_STATUS),
    ),
    ("Student 1:N Enrollment", "Student 1:N Invoice", "Student 1:N Scholarship",
     "Student 1:N Payment", "Student 1:N Refund", "Student 1:N LedgerEntry"),
)

FEE_SCHEDULE = Table(
    "fee_schedule", "FeeSchedule", "fee_schedule_id",
    "Fee definition per program, term and fee type, with effective dates.",
    (
        _pk("fee_schedule_id", "FSC-NNNNN"),
        Field("program_id", "string", fk="program.program_id"),
        Field("term_id", "string", fk="term.term_id"),
        Field("fee_type", "string", allowed=FEE_TYPES),
        Field("amount", "decimal", unit="INR", rule=">= 0; fixed amount charged per term"),
        Field("effective_from", "date", rule="<= effective_to"),
        Field("effective_to", "date", required=False, rule="Open-ended if empty"),
        Field("status", "string", allowed=SCHEDULE_STATUS),
    ),
    ("(program_id, term_id, fee_type, effective_from) is unique",
     "FeeSchedule 1:N InvoiceLine (optional)"),
)

ENROLLMENT = Table(
    "enrollment", "Enrollment", "enrollment_id",
    "A student's enrollment in a program for one term.",
    (
        _pk("enrollment_id", "ENR-NNNNNN"),
        Field("student_id", "string", fk="student.student_id"),
        Field("program_id", "string", fk="program.program_id"),
        Field("term_id", "string", fk="term.term_id"),
        Field("status", "string", allowed=ENROLLMENT_STATUS,
              rule="ENROLLED -> WITHDRAWN | COMPLETED | CANCELLED"),
        Field("enrolled_on", "date", rule="Within term window (or shortly before start)"),
        Field("withdrawn_on", "date", required=False,
              rule="Required iff status = WITHDRAWN; >= enrolled_on"),
    ),
    ("(student_id, term_id) is unique", "Enrollment 1:N Invoice (1:1 expected)"),
)

INVOICE = Table(
    "invoice", "Invoice", "invoice_id",
    "Bill for one enrollment. Lines are append-only; totals are derived from lines.",
    (
        _pk("invoice_id", "INV-<student-id>-<year>-NNNNNN, e.g. INV-STU-000001-2026-000001"),
        Field("student_id", "string", fk="student.student_id"),
        Field("enrollment_id", "string", fk="enrollment.enrollment_id"),
        Field("term_id", "string", fk="term.term_id"),
        Field("issue_date", "date"),
        Field("due_date", "date", rule="issue_date + term.invoice_due_days"),
        Field("currency", "string", allowed=("INR",)),
        Field("total_amount", "decimal", unit="INR", rule="Derived: sum(invoice_line.amount)"),
        Field("status", "string", allowed=INVOICE_STATUS, rule="Derived from balance, dates and enrollment"),
    ),
    ("Invoice 1:N InvoiceLine", "(enrollment_id) is unique among non-CANCELLED invoices"),
)

INVOICE_LINE = Table(
    "invoice_line", "InvoiceLine", "invoice_line_id",
    "One charge or credit on an invoice. Signed: charges > 0, credits < 0.",
    (
        _pk("invoice_line_id", "LINE-<invoice-id>-NN"),
        Field("invoice_id", "string", fk="invoice.invoice_id"),
        Field("line_type", "string", allowed=LINE_TYPES),
        Field("fee_schedule_id", "string", required=False, fk="fee_schedule.fee_schedule_id",
              rule="Required for fee lines and WAIVER lines (the fee being waived); empty for LATE_FEE / SCHOLARSHIP_CREDIT"),
        Field("scholarship_id", "string", required=False, fk="scholarship.scholarship_id",
              rule="Required iff line_type = SCHOLARSHIP_CREDIT"),
        Field("description", "string"),
        Field("amount", "decimal", unit="INR",
              rule="Charges > 0; SCHOLARSHIP_CREDIT and WAIVER < 0"),
        Field("line_date", "date", rule=">= invoice.issue_date"),
    ),
    ("InvoiceLine N:M Payment via PaymentAllocation",),
)

ELIGIBILITY = Table(
    "eligibility", "Eligibility", "eligibility_id",
    "Scholarship scheme criteria and award terms, with effective dates.",
    (
        _pk("eligibility_id", "ELG-NNN"),
        Field("name", "string"),
        Field("min_cgpa", "decimal", unit="points", rule="0-10"),
        Field("max_income_band", "string", required=False, allowed=INCOME_BANDS,
              rule="Highest income band that qualifies; empty = merit-only"),
        Field("program_id", "string", required=False, fk="program.program_id",
              rule="Empty = all programs"),
        Field("award_type", "string", allowed=AWARD_TYPES),
        Field("award_value", "decimal", unit="percent or INR per award_type", rule="> 0; percent <= 100"),
        Field("max_award_amount", "decimal", unit="INR", rule="Hard cap per term"),
        Field("effective_from", "date"),
        Field("effective_to", "date", required=False),
    ),
    ("Eligibility 1:N Scholarship",),
)

SCHOLARSHIP = Table(
    "scholarship", "Scholarship", "scholarship_id",
    "Scholarship award to a student for a term.",
    (
        _pk("scholarship_id", "SCH-<year>-NNNNNN"),
        Field("student_id", "string", fk="student.student_id"),
        Field("eligibility_id", "string", fk="eligibility.eligibility_id"),
        Field("term_id", "string", fk="term.term_id"),
        Field("award_amount", "decimal", unit="INR",
              rule="<= eligible fees (TUITION lines) and <= eligibility.max_award_amount"),
        Field("awarded_on", "date"),
        Field("status", "string", allowed=SCHOLARSHIP_STATUS, rule="AWARDED -> APPLIED | REVOKED"),
    ),
    ("Student must meet the Eligibility criteria on awarded_on",),
)

PAYMENT = Table(
    "payment", "Payment", "payment_id",
    "Money received from a student. May be partial or exceed what is owed.",
    (
        _pk("payment_id", "PAY-<year>-NNNNNN"),
        Field("student_id", "string", fk="student.student_id"),
        Field("payment_date", "date"),
        Field("amount", "decimal", unit="INR", rule="> 0"),
        Field("method", "string", allowed=PAYMENT_METHODS),
        Field("reference", "string", unique=True, rule="Fabricated gateway reference"),
        Field("status", "string", allowed=PAYMENT_STATUS),
    ),
    ("Payment 1:N PaymentAllocation", "Unallocated remainder = overpayment / credit on account"),
)

PAYMENT_ALLOCATION = Table(
    "payment_allocation", "PaymentAllocation", "allocation_id",
    "Bridge between Payment and InvoiceLine (N:M).",
    (
        _pk("allocation_id", "ALLOC-<payment-id>-NN"),
        Field("payment_id", "string", fk="payment.payment_id"),
        Field("invoice_line_id", "string", fk="invoice_line.invoice_line_id"),
        Field("amount", "decimal", unit="INR",
              rule="> 0; sum per payment <= payment.amount; sum per line <= line.amount"),
        Field("allocated_on", "date", rule=">= payment.payment_date"),
    ),
    ("(payment_id, invoice_line_id) is unique",),
)

REFUND = Table(
    "refund", "Refund", "refund_id",
    "Money returned to a student.",
    (
        _pk("refund_id", "REF-<year>-NNNNNN"),
        Field("student_id", "string", fk="student.student_id"),
        Field("payment_id", "string", fk="payment.payment_id", rule="Payment being refunded"),
        Field("enrollment_id", "string", required=False, fk="enrollment.enrollment_id",
              rule="Set for WITHDRAWAL / CANCELLATION"),
        Field("reason", "string", allowed=REFUND_REASONS),
        Field("amount", "decimal", unit="INR", rule="> 0; <= net paid for the student"),
        Field("requested_on", "date"),
        Field("processed_on", "date", required=False, rule=">= requested_on; set when PAID or REJECTED"),
        Field("status", "string", allowed=REFUND_STATUS, rule="REQUESTED -> APPROVED | REJECTED; APPROVED -> PAID"),
    ),
    ("Refund N:1 Payment",),
)

LEDGER_ENTRY = Table(
    "ledger_entry", "LedgerEntry", "ledger_entry_id",
    "Append-only student ledger (extension). Balance owed = sum(amount) per student.",
    (
        _pk("ledger_entry_id", "LED-NNNNNNNN"),
        Field("event_seq", "int", unique=True, rule="Global, strictly increasing; defines order"),
        Field("student_id", "string", fk="student.student_id"),
        Field("entry_date", "date"),
        Field("entry_type", "string", allowed=LEDGER_TYPES),
        Field("amount", "decimal", unit="INR",
              rule="Signed: charges and refunds > 0 (owed up); payments, credits, waivers < 0"),
        Field("source_table", "string", rule="Table the entry was derived from"),
        Field("source_id", "string", rule="PK of the source row"),
    ),
    ("LedgerEntry is derived from source rows; never edited in place",),
    extension=True,
)

STATUS_EVENT = Table(
    "status_event", "StatusEvent", "event_id",
    "Lifecycle history (extension): every status change is a row; nothing is overwritten.",
    (
        _pk("event_id", "EVT-NNNNNNNN"),
        Field("entity_type", "string", allowed=EVENT_ENTITIES),
        Field("entity_id", "string", rule="PK in the table named by entity_type"),
        Field("from_status", "string", required=False, rule="Empty for the initial state"),
        Field("to_status", "string"),
        Field("event_date", "date"),
    ),
    ("Polymorphic reference: validated in code, not as a single FK",),
    extension=True,
)

# Creation order = parents before children.
TABLES = {
    t.name: t
    for t in (
        TERM, PROGRAM, STUDENT, FEE_SCHEDULE, ENROLLMENT, ELIGIBILITY,
        INVOICE, SCHOLARSHIP, INVOICE_LINE, PAYMENT, PAYMENT_ALLOCATION,
        REFUND, LEDGER_ENTRY, STATUS_EVENT,
    )
}

REQUIRED_ENTITIES = (
    "Student", "Program", "FeeSchedule", "Enrollment", "Invoice", "InvoiceLine",
    "Scholarship", "Eligibility", "Payment", "PaymentAllocation", "Refund",
)
