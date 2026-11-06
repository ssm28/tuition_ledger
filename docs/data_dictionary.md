# Data dictionary

_Generated from `src/tuition_synth/schema.py` by `tuition-synth docs`. Do not edit by hand._

Money is decimal with 2 places in INR. Dates are ISO-8601. Tables marked _(extension)_ are additions beyond the 11 entities in the problem statement.

### `term` - Term _(extension)_

Academic term. Reference table (extension): needed for dates and term-specific fees.

**Primary key:** `term_id`

**Relationships / cardinality:**
- Term 1:N FeeSchedule
- Term 1:N Enrollment
- Term 1:N Invoice

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `term_id` | string | yes | yes |  |  | TERM-<year>-<NAME>, e.g. TERM-2026-FALL |
| `label` | string | yes |  |  |  | Human-readable name |
| `start_date` | date | yes |  |  |  | start_date < end_date |
| `end_date` | date | yes |  |  |  |  |
| `invoice_due_days` | int | yes |  |  | days | > 0; due_date = issue_date + this |

### `program` - Program

Academic program (20 in the baseline).

**Primary key:** `program_id`

**Relationships / cardinality:**
- Program 1:N Student (home program)
- Program 1:N FeeSchedule
- Program 1:N Enrollment

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `program_id` | string | yes | yes |  |  | PRG-NNN |
| `program_code` | string | yes | yes |  |  | Short code, e.g. BTECH-CS |
| `name` | string | yes |  |  |  |  |
| `level` | string | yes |  | UG, PG |  |  |

### `student` - Student

Synthetic student. All personal data is fabricated.

**Primary key:** `student_id`

**Foreign keys:** `program_id` -> `program.program_id`

**Relationships / cardinality:**
- Student 1:N Enrollment
- Student 1:N Invoice
- Student 1:N Scholarship
- Student 1:N Payment
- Student 1:N Refund
- Student 1:N LedgerEntry

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `student_id` | string | yes | yes |  |  | STU-NNNNNN |
| `full_name` | string | yes |  |  |  | Fabricated name |
| `email` | string | yes | yes |  |  | Fabricated, @example.edu domain |
| `date_of_birth` | date | yes |  |  |  | Age 17-40 at admission_date |
| `program_id` | string | yes |  |  |  | Home program |
| `admission_date` | date | yes |  |  |  |  |
| `cgpa` | decimal | yes |  |  | points (0-10 scale) | 0.00 <= cgpa <= 10.00; drives eligibility |
| `family_income_band` | string | yes |  | LOW, MIDDLE, HIGH |  | Drives need-based eligibility |
| `status` | string | yes |  | ACTIVE, WITHDRAWN, GRADUATED |  |  |

### `fee_schedule` - FeeSchedule

Fee definition per program, term and fee type, with effective dates.

**Primary key:** `fee_schedule_id`

**Foreign keys:** `program_id` -> `program.program_id`, `term_id` -> `term.term_id`

**Relationships / cardinality:**
- (program_id, term_id, fee_type, effective_from) is unique
- FeeSchedule 1:N InvoiceLine (optional)

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `fee_schedule_id` | string | yes | yes |  |  | FSC-NNNNN |
| `program_id` | string | yes |  |  |  |  |
| `term_id` | string | yes |  |  |  |  |
| `fee_type` | string | yes |  | TUITION, LAB, LIBRARY, TECHNOLOGY, ACTIVITY |  |  |
| `amount` | decimal | yes |  |  | INR | >= 0; fixed amount charged per term |
| `effective_from` | date | yes |  |  |  | <= effective_to |
| `effective_to` | date | no |  |  |  | Open-ended if empty |
| `status` | string | yes |  | ACTIVE, SUPERSEDED |  |  |

### `enrollment` - Enrollment

A student's enrollment in a program for one term.

**Primary key:** `enrollment_id`

**Foreign keys:** `student_id` -> `student.student_id`, `program_id` -> `program.program_id`, `term_id` -> `term.term_id`

**Relationships / cardinality:**
- (student_id, term_id) is unique
- Enrollment 1:N Invoice (1:1 expected)

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `enrollment_id` | string | yes | yes |  |  | ENR-NNNNNN |
| `student_id` | string | yes |  |  |  |  |
| `program_id` | string | yes |  |  |  |  |
| `term_id` | string | yes |  |  |  |  |
| `status` | string | yes |  | ENROLLED, WITHDRAWN, COMPLETED, CANCELLED |  | ENROLLED -> WITHDRAWN \| COMPLETED \| CANCELLED |
| `enrolled_on` | date | yes |  |  |  | Within term window (or shortly before start) |
| `withdrawn_on` | date | no |  |  |  | Required iff status = WITHDRAWN; >= enrolled_on |

### `eligibility` - Eligibility

Scholarship scheme criteria and award terms, with effective dates.

**Primary key:** `eligibility_id`

**Foreign keys:** `program_id` -> `program.program_id`

**Relationships / cardinality:**
- Eligibility 1:N Scholarship

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `eligibility_id` | string | yes | yes |  |  | ELG-NNN |
| `name` | string | yes |  |  |  |  |
| `min_cgpa` | decimal | yes |  |  | points | 0-10 |
| `max_income_band` | string | no |  | LOW, MIDDLE, HIGH |  | Highest income band that qualifies; empty = merit-only |
| `program_id` | string | no |  |  |  | Empty = all programs |
| `award_type` | string | yes |  | PERCENT_OF_TUITION, FIXED_AMOUNT |  |  |
| `award_value` | decimal | yes |  |  | percent or INR per award_type | > 0; percent <= 100 |
| `max_award_amount` | decimal | yes |  |  | INR | Hard cap per term |
| `effective_from` | date | yes |  |  |  |  |
| `effective_to` | date | no |  |  |  |  |

### `invoice` - Invoice

Bill for one enrollment. Lines are append-only; totals are derived from lines.

**Primary key:** `invoice_id`

**Foreign keys:** `student_id` -> `student.student_id`, `enrollment_id` -> `enrollment.enrollment_id`, `term_id` -> `term.term_id`

**Relationships / cardinality:**
- Invoice 1:N InvoiceLine
- (enrollment_id) is unique among non-CANCELLED invoices

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `invoice_id` | string | yes | yes |  |  | INV-<student-id>-<year>-NNNNNN, e.g. INV-STU-000001-2026-000001 |
| `student_id` | string | yes |  |  |  |  |
| `enrollment_id` | string | yes |  |  |  |  |
| `term_id` | string | yes |  |  |  |  |
| `issue_date` | date | yes |  |  |  |  |
| `due_date` | date | yes |  |  |  | issue_date + term.invoice_due_days |
| `currency` | string | yes |  | INR |  |  |
| `total_amount` | decimal | yes |  |  | INR | Derived: sum(invoice_line.amount) |
| `status` | string | yes |  | ISSUED, PARTIALLY_PAID, PAID, OVERDUE, CANCELLED |  | Derived from balance, dates and enrollment |

### `scholarship` - Scholarship

Scholarship award to a student for a term.

**Primary key:** `scholarship_id`

**Foreign keys:** `student_id` -> `student.student_id`, `eligibility_id` -> `eligibility.eligibility_id`, `term_id` -> `term.term_id`

**Relationships / cardinality:**
- Student must meet the Eligibility criteria on awarded_on

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `scholarship_id` | string | yes | yes |  |  | SCH-<year>-NNNNNN |
| `student_id` | string | yes |  |  |  |  |
| `eligibility_id` | string | yes |  |  |  |  |
| `term_id` | string | yes |  |  |  |  |
| `award_amount` | decimal | yes |  |  | INR | <= eligible fees (TUITION lines) and <= eligibility.max_award_amount |
| `awarded_on` | date | yes |  |  |  |  |
| `status` | string | yes |  | AWARDED, APPLIED, REVOKED |  | AWARDED -> APPLIED \| REVOKED |

### `invoice_line` - InvoiceLine

One charge or credit on an invoice. Signed: charges > 0, credits < 0.

**Primary key:** `invoice_line_id`

**Foreign keys:** `invoice_id` -> `invoice.invoice_id`, `fee_schedule_id` -> `fee_schedule.fee_schedule_id`, `scholarship_id` -> `scholarship.scholarship_id`

**Relationships / cardinality:**
- InvoiceLine N:M Payment via PaymentAllocation

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `invoice_line_id` | string | yes | yes |  |  | LINE-<invoice-id>-NN |
| `invoice_id` | string | yes |  |  |  |  |
| `line_type` | string | yes |  | TUITION, LAB, LIBRARY, TECHNOLOGY, ACTIVITY, LATE_FEE, SCHOLARSHIP_CREDIT, WAIVER |  |  |
| `fee_schedule_id` | string | no |  |  |  | Required for fee lines; empty for LATE_FEE / credits |
| `scholarship_id` | string | no |  |  |  | Required iff line_type = SCHOLARSHIP_CREDIT |
| `description` | string | yes |  |  |  |  |
| `amount` | decimal | yes |  |  | INR | Charges > 0; SCHOLARSHIP_CREDIT and WAIVER < 0 |
| `line_date` | date | yes |  |  |  | >= invoice.issue_date |

### `payment` - Payment

Money received from a student. May be partial or exceed what is owed.

**Primary key:** `payment_id`

**Foreign keys:** `student_id` -> `student.student_id`

**Relationships / cardinality:**
- Payment 1:N PaymentAllocation
- Unallocated remainder = overpayment / credit on account

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `payment_id` | string | yes | yes |  |  | PAY-<year>-NNNNNN |
| `student_id` | string | yes |  |  |  |  |
| `payment_date` | date | yes |  |  |  |  |
| `amount` | decimal | yes |  |  | INR | > 0 |
| `method` | string | yes |  | UPI, CARD, NET_BANKING, BANK_TRANSFER, CASH |  |  |
| `reference` | string | yes | yes |  |  | Fabricated gateway reference |
| `status` | string | yes |  | POSTED, REVERSED |  |  |

### `payment_allocation` - PaymentAllocation

Bridge between Payment and InvoiceLine (N:M).

**Primary key:** `allocation_id`

**Foreign keys:** `payment_id` -> `payment.payment_id`, `invoice_line_id` -> `invoice_line.invoice_line_id`

**Relationships / cardinality:**
- (payment_id, invoice_line_id) is unique

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `allocation_id` | string | yes | yes |  |  | ALLOC-<payment-id>-NN |
| `payment_id` | string | yes |  |  |  |  |
| `invoice_line_id` | string | yes |  |  |  |  |
| `amount` | decimal | yes |  |  | INR | > 0; sum per payment <= payment.amount; sum per line <= line.amount |
| `allocated_on` | date | yes |  |  |  | >= payment.payment_date |

### `refund` - Refund

Money returned to a student.

**Primary key:** `refund_id`

**Foreign keys:** `student_id` -> `student.student_id`, `payment_id` -> `payment.payment_id`, `enrollment_id` -> `enrollment.enrollment_id`

**Relationships / cardinality:**
- Refund N:1 Payment

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `refund_id` | string | yes | yes |  |  | REF-<year>-NNNNNN |
| `student_id` | string | yes |  |  |  |  |
| `payment_id` | string | yes |  |  |  | Payment being refunded |
| `enrollment_id` | string | no |  |  |  | Set for WITHDRAWAL / CANCELLATION |
| `reason` | string | yes |  | WITHDRAWAL, CANCELLATION, OVERPAYMENT |  |  |
| `amount` | decimal | yes |  |  | INR | > 0; <= net paid for the student |
| `requested_on` | date | yes |  |  |  |  |
| `processed_on` | date | no |  |  |  | >= requested_on; set when PAID or REJECTED |
| `status` | string | yes |  | REQUESTED, APPROVED, PAID, REJECTED |  | REQUESTED -> APPROVED \| REJECTED; APPROVED -> PAID |

### `ledger_entry` - LedgerEntry _(extension)_

Append-only student ledger (extension). Balance owed = sum(amount) per student.

**Primary key:** `ledger_entry_id`

**Foreign keys:** `student_id` -> `student.student_id`

**Relationships / cardinality:**
- LedgerEntry is derived from source rows; never edited in place

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `ledger_entry_id` | string | yes | yes |  |  | LED-NNNNNNNN |
| `event_seq` | int | yes | yes |  |  | Global, strictly increasing; defines order |
| `student_id` | string | yes |  |  |  |  |
| `entry_date` | date | yes |  |  |  |  |
| `entry_type` | string | yes |  | CHARGE, SCHOLARSHIP_CREDIT, WAIVER, LATE_FEE, PAYMENT, REFUND, REVERSAL |  |  |
| `amount` | decimal | yes |  |  | INR | Signed: charges and refunds > 0 (owed up); payments, credits, waivers < 0 |
| `source_table` | string | yes |  |  |  | Table the entry was derived from |
| `source_id` | string | yes |  |  |  | PK of the source row |

### `status_event` - StatusEvent _(extension)_

Lifecycle history (extension): every status change is a row; nothing is overwritten.

**Primary key:** `event_id`

**Relationships / cardinality:**
- Polymorphic reference: validated in code, not as a single FK

| Field | Type | Required | Unique | Allowed values | Unit | Rule |
|---|---|---|---|---|---|---|
| `event_id` | string | yes | yes |  |  | EVT-NNNNNNNN |
| `entity_type` | string | yes |  | enrollment, invoice, scholarship, payment, refund |  |  |
| `entity_id` | string | yes |  |  |  | PK in the table named by entity_type |
| `from_status` | string | no |  |  |  | Empty for the initial state |
| `to_status` | string | yes |  |  |  |  |
| `event_date` | date | yes |  |  |  |  |

