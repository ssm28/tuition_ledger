# Design notes

Status: **draft rules for review**. Every rule here must be implemented in
`rules.py` and enforced by `validate.py`; if a rule changes, change it here first.

## 1. Scope and assumptions

| # | Assumption | Why |
|---|---|---|
| A1 | Currency is INR; money is `Decimal` with 2 places, rounded half-up (e.g. 617.285 becomes 617.29). | Avoids float error; reconciliation must be exact. |
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

**Fee waivers.** Negative WAIVER line that points (via `fee_schedule_id`) at the non-tuition fee line it waives, for the full fee; about 3% of invoices.

**Payments and allocation.** A payment (always for one student, one invoice) is allocated to that invoice's charge lines in line order, each up to the line's *net due* (the line amount minus the scholarship credit or waiver that targets it). Allocation to a line never exceeds the line's outstanding amount, and the allocations of a payment never exceed the payment. Partial payment leaves the invoice PARTIALLY_PAID. Any unallocated remainder is an overpayment, held as credit on account.

**Late fees.** A **fixed** late fee of INR 500 is added, once per invoice, as a LATE_FEE line dated the day after the grace period ends (due date + 15 days) if any amount is still unpaid at the end of the grace period.

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

## 5. Injected anomalies (labelled in `ground_truth.csv`)

20 of each type at full scale (at least 3 at any scale), each on a different student so no two anomalies interact.

| issue_type | How it is injected | Expected decision |
|---|---|---|
| `ALLOCATION_EXCEEDS_PAYMENT` | The last allocation of a fully-allocated payment is raised by 500, 1,000 or 2,500, so the payment is allocated beyond its amount. Only the latest payment of a fully paid, fee-free invoice is used, so no other allocation is disturbed. | REJECT_ALLOCATION |
| `SCHOLARSHIP_EXCEEDS_FEES` | An award is raised above the tuition of its term. | CAP_AWARD_AT_ELIGIBLE_FEES |
| `DUPLICATE_INVOICE` | A second invoice (counter 000004) for an enrollment, with copied fee lines, a late fee and its own status history. | CANCEL_DUPLICATE_INVOICE |
| `REFUND_EXCEEDS_NET_PAID` | A PAID OVERPAYMENT refund larger than the student's net paid (payments minus paid refunds). | REJECT_REFUND |
| `BALANCE_LEDGER_MISMATCH` | One PAYMENT or CHARGE ledger entry is changed, so the student's ledger balance no longer matches their records. | INVESTIGATE_AND_REPOST_LEDGER |

Rules: inject only after the clean baseline passes validation; touch only labelled rows; keep `ground_truth` out of every validator input. The ledger is rebuilt from the altered source rows (so it stays consistent with them) before the ledger anomaly is planted.

## 6. Decisions

- Late fee: fixed INR 500, once per invoice (chosen over a percentage).
- Refund tiers: 100% up to day 14, 50% up to day 30, 25% up to day 45, nothing after; late claims are REJECTED.
- Full-scale data is committed as gzip-compressed CSV (about 8 MB); the starter set is committed in CSV, JSON and SQL.

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

## 9. How scholarships, payments and late fees are generated

- **Scholarships:** every non-cancelled invoice is checked against all schemes on the date the award is decided (1-14 days before invoice issue). The best scheme the student qualifies for gives the candidate award (percent or fixed, capped by the scheme cap and by the tuition). Exactly 15,000 candidates are awarded, chosen at random (limited funding). Each award is a negative SCHOLARSHIP_CREDIT line on the invoice, dated at invoice issue, and the scholarship moves AWARDED -> APPLIED.
- **Payment behaviour per invoice:** 73% pay in full on time, 5% overpay, 10% pay in full but late, 8% pay only part, 4% pay nothing. Each paying invoice gets 1-4 installments (50/30/15/5%); counts are nudged so the total is exactly 50,000 payments.
- **Late payers** pay their final installment 1-45 days after the grace period, and that installment includes the late fee. Partial and non-paying invoices keep the late fee unpaid.
- **Overpayments** are allocated up to what is owed; the rest stays unallocated (credit on account).
- **Invoice status at the as-of date:** PAID (allocations cover the total), PARTIALLY_PAID (some but not all), OVERDUE (nothing paid, past due), CANCELLED. Because the as-of date is after every due date, ISSUED does not appear at the end, but it appears in the history.
- **Payments** are numbered in date order (PAY-2026-NNNNNN).

## 10. Refunds and the ledger

- **Withdrawal refunds:** for every WITHDRAWN enrollment, one refund per payment that paid tuition: `tuition allocated x tier share`. A withdrawal after day 45 earns nothing; 60% of those students still file a claim, which is REJECTED.
- **Cancellation refunds:** 35% of cancelled invoices were paid in full before the cancellation; the whole payment is refunded.
- **Overpayment refunds:** the unallocated part of a payment is refunded for 60% of overpayers (the rest stays as credit on account).
- **Refund path:** REQUESTED -> APPROVED -> PAID for 85%; 7% stay APPROVED and 8% stay REQUESTED; steps dated after the as-of date have not happened yet.
- **Ledger:** one entry per fee/credit/waiver/late-fee line, per payment, per PAID refund, and one REVERSAL per cancelled invoice. It is built from the source tables by `ledger.py`; the validator rebuilds it independently and also compares each student's ledger total with a balance computed straight from invoices, payments and refunds (`invoice totals of non-cancelled invoices - payments + paid refunds`).

## 11. Validation

`validate.py` runs structure checks (columns, PK uniqueness, ID format, required, types, enums, FK), then business rules (enrollments, invoices, scholarships, waivers, payments and allocations, late fees, invoice status, refunds, ledger, lifecycle). Each problem is an `Issue(check, table, row_id)`. `anomalies.score_detection` compares issues with `ground_truth`: an anomaly is detected if its expected check fired on its row, and any issue on a row that is neither labelled nor related to a labelled row counts as unexplained (a false alarm or collateral damage).

## 12. Exports and reproducibility

- `tuition-synth generate` writes `csv/` (optionally `.csv.gz`), `json/`, `sql/schema.sql` + `sql/seed.sql`, `ground_truth.csv/json`, `MANIFEST.json` (command, seed, scale, per-file rows and SHA-256, provenance) and `VALIDATION_SUMMARY.md`.
- The SQL seed loads into SQLite with foreign keys on; the schema carries PKs, FKs, UNIQUE and enum CHECK constraints.
- `tuition-synth reproduce` generates twice into temporary folders and compares row counts and checksums. CSV and gzip bytes are reproducible: sorted output, fixed line endings, no timestamps, `mtime=0` in gzip headers, per-table random streams.

## 13. Known limitations and trade-offs

- All terms are in 2026 and every student is enrolled in all three, which keeps volumes exact but is simpler than a real registry.
- Student status is ACTIVE for everyone; withdrawals are recorded on enrollments, not on the student.
- Payments belong to one student and one invoice; there are no lump sums covering several invoices, and credit on account is not automatically applied to later invoices.
- Scholarship awards are a random subset of eligible student-terms (limited funding), not a ranked selection; REVOKED and REVERSED states exist in the schema but are not used in the baseline.
- The as-of date must be after the end of the grace period plus 45 days for every invoice (true for the default).
