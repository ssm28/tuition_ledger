# Design notes

Status: **draft rules for review**. Every rule here must be implemented in
`rules.py` and enforced by `validate.py`; if a rule changes, change it here first.

## 1. Scope and assumptions

| # | Assumption | Why |
|---|---|---|
| A1 | Currency is INR; money is `Decimal` with 2 places. | Avoids float error; reconciliation must be exact. |
| A2 | Three terms in 2026 (Spring, Summer, Fall), one invoice per student per term, so about 3 invoices per student (30,000 / 10,000). | Matches the volume target and keeps the invoice-ID year consistent. |
| A3 | `INV-<student-id>-<year>-NNNNNN` embeds the full student ID (`INV-STU-000001-2026-000001`); the counter is per student per year. | Literal reading of the ID convention. |
| A4 | Fixed as-of date 2026-12-31 replaces "today". | Reproducibility. |
| A5 | Extension tables: `term`, `ledger_entry`, `status_event`. | Needed for dates, balance reconciliation and event history. |
| A6 | `Eligibility` holds scheme criteria; `Scholarship` holds an award to one student for one term. | Matches "define scholarship criteria and awards". |
| A7 | All personal data is fabricated (`@example.edu`); no external data is used. | Lawful provenance. |

## 2. Cardinality summary

- Program 1:N Student, FeeSchedule, Enrollment
- Term 1:N FeeSchedule, Enrollment, Invoice
- Student 1:N Enrollment, Invoice, Scholarship, Payment, Refund, LedgerEntry
- Enrollment 1:N Invoice (1:1 for valid data; a second active invoice is the "generated twice" anomaly)
- Invoice 1:N InvoiceLine
- Eligibility 1:N Scholarship
- **Payment N:M InvoiceLine via PaymentAllocation** (bridge)
- Payment 1:N Refund

## 3. Business rules (draft)

**Fees.** Each (program, term, fee type) has a FeeSchedule row with one fixed `amount` charged per term (no credit-hour maths). Summer fees differ from Spring/Fall so term-specific correctness is testable. An invoice line for a fee equals the `amount` of the schedule effective on the invoice issue date.

**Invoices.** One per enrollment, generated from eligible fee lines. `total_amount` = sum of its lines. Lines are append-only: late fees, scholarship credits and waivers are new lines, never edits.

**Scholarships.** A student qualifies if `cgpa >= min_cgpa`, income band is at or below `max_income_band` (if set), the program matches (if set), and the award date is inside the effective window. Award = percent of TUITION lines, or a fixed amount, capped by `max_award_amount` **and never more than eligible fees (TUITION lines)**. Applied as a negative SCHOLARSHIP_CREDIT line.

**Fee waivers.** Negative WAIVER line, only on non-tuition fee lines in the baseline.

**Payments and allocation.** A payment is allocated to open invoice lines, oldest due first. Allocation to a line never exceeds the line's outstanding amount, and the allocations of a payment never exceed the payment. Partial payment leaves the invoice PARTIALLY_PAID. Any unallocated remainder is an overpayment, held as credit on account.

**Late fees.** If an invoice has an outstanding balance more than 15 days after `due_date` (as of the payment date or the as-of date), add one LATE_FEE line of 2% of the outstanding balance, once per invoice.

**Withdrawals and cancellations.** Withdrawal refund share of tuition paid, by days since term start: <= 14 days 100%, <= 30 days 50%, <= 45 days 25%, later 0%. The enrollment becomes WITHDRAWN and refunds are created as REQUESTED -> APPROVED -> PAID. A cancelled enrollment cancels its unpaid invoice.

**Refund limit.** A refund can never exceed the student's net paid (payments received minus refunds already paid).

**Ledger.** Balance owed per student = sum of `ledger_entry.amount`. Charges and refunds are positive; payments, credits and waivers are negative. The invoice-level and student-level balances computed from invoice lines and allocations must equal the ledger.

## 4. Lifecycles

- Enrollment: ENROLLED -> WITHDRAWN | COMPLETED | CANCELLED
- Invoice: ISSUED -> PARTIALLY_PAID | PAID | OVERDUE; PARTIALLY_PAID -> PAID | OVERDUE; OVERDUE -> PARTIALLY_PAID | PAID; any open state -> CANCELLED
- Scholarship: AWARDED -> APPLIED | REVOKED
- Payment: POSTED -> REVERSED
- Refund: REQUESTED -> APPROVED | REJECTED; APPROVED -> PAID

Each transition is a `status_event` row.

## 5. Injected anomalies (labelled in `ground_truth`)

| issue_type | How it is injected | Expected decision |
|---|---|---|
| `ALLOCATION_EXCEEDS_PAYMENT` | One allocation sized above its payment. | Reject allocation |
| `SCHOLARSHIP_EXCEEDS_FEES` | Award above the student's TUITION total. | Cap or revoke |
| `DUPLICATE_INVOICE` | Second invoice for the same enrollment. | Cancel duplicate |
| `REFUND_EXCEEDS_NET_PAID` | Refund above net paid. | Reject refund |
| `BALANCE_LEDGER_MISMATCH` | Ledger entry altered for one student. | Investigate / re-post |

Rules: inject only after the clean baseline passes validation; touch only the labelled rows; keep `ground_truth` out of any validator input.

## 6. Open decisions

- Confirm refund and late-fee percentages (section 3) before implementing.
- Decide whether to commit the full-scale data or only the starter set plus checksums.

## 7. How master data is generated

- **Random streams:** each table draws from its own `random.Random(f"{seed}:{table}")`, so editing one generator never changes another table's numbers.
- **Programs:** 20, from `reference_data.PROGRAMS` (12 UG, 8 PG); popularity weights make enrollment uneven.
- **Fee schedules:** one row per program, term and fee type. LAB exists only for lab programs. Term factors: Spring 1.00, Summer 0.60, Fall 1.05, applied to every fee. Effective from 30 days before term start to term end.
- **Scholarship schemes (Eligibility):** 8 schemes: merit tiers, need-based, middle-income, one program-specific (CS), one fellowship (Data Science) and one that expires on 2026-07-31 (tests effective dates).
- **Students:** CGPA is normal(7.2, 1.0) clipped to 4.0-10.0; income band LOW/MIDDLE/HIGH is 30/50/20 percent; admission dates are before the first term so every student can enroll in all three terms. Every baseline student is ACTIVE.
- The scholarship scheme thresholds will be tuned when awards are generated so that about 15,000 awards result.

## 8. How enrollments and invoices are generated

- Every student gets one enrollment per term (3 each, 30,000 total) and one invoice per enrollment, issued 1-10 days before term start, due 30 days later.
- Outcome per enrollment is drawn once: 1.5% cancelled before term start (invoice CANCELLED too), 4% withdrawn after term start, the rest COMPLETED (the fixed as-of date is after every term).
- Withdrawal day is drawn from four windows (1-14, 15-30, 31-45, 46+ days after start) so every refund tier appears in the data.
- Invoice lines are copied from the fee schedule effective on the issue date; invoice totals are the sum of their lines.
- Every status change is recorded in `status_event` (numbered in date order). The validator checks that each row's status equals the last event and that every step is an allowed transition.
- Invoice statuses beyond ISSUED / CANCELLED (PARTIALLY_PAID, PAID, OVERDUE) are derived later, once payments exist.
