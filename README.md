# tuition-ledger-synth

A deterministic synthetic-data generator and validator for a university **tuition, scholarship, payment and
balance-reconciliation** workflow: fee schedules, enrollments, invoices, scholarship eligibility, payment
allocation, late fees, withdrawals and refunds, and a student ledger. It plants five labelled kinds of data
errors, then checks that an independent validator finds them.

Everything is fully synthetic (fixed seed `20261022`, no external data) and reproducible byte for byte.

## Results at a glance (full scale)

| | |
|---|---|
| Students / programs / terms | 10,000 / 20 / 3 |
| Invoices | 30,000 (plus 20 injected duplicates) |
| Scholarship awards | 15,000 |
| Payments | 50,000 (partial, installments, overpayments, late) |
| Refunds | 3,000 (withdrawal, cancellation, overpayment; paid, pending, rejected) |
| Ledger entries | 213,768 |
| Clean-baseline validation issues | **0** |
| Injected anomalies found by the validator | **100 / 100**, 0 unexplained issues |
| Reproducibility (two runs, same seed) | **identical** checksums for every file |

Details: [`reports/validation_summary_full.md`](reports/validation_summary_full.md),
[`reports/reproducibility_full.md`](reports/reproducibility_full.md).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                                  # 114 tests, about a minute

# small starter dataset in all formats (what is committed in data/starter)
tuition-synth generate --seed 20261022 --scale 0.02 --formats csv,json,sql --out out/starter

# full dataset, compressed CSV (what is committed in data/full)
tuition-synth generate --seed 20261022 --scale 1.0 --formats csv --gzip --out out/full

# prove reproducibility: generate twice and compare every file
tuition-synth reproduce --scale 1.0 --report reports/reproducibility_full.md
```

The generator command, seed and scale used for every committed dataset are recorded in its `MANIFEST.json`.
`--no-anomalies` writes the clean baseline only. `--scale` shrinks or grows all volumes (programs stay at 20).

## What a dataset folder contains

| Path | Contents |
|---|---|
| `csv/<table>.csv` (or `.csv.gz`) | One file per table, columns in schema order |
| `json/<table>.json`, `sql/schema.sql`, `sql/seed.sql` | Same data as JSON and as SQLite-ready SQL (when requested) |
| `ground_truth.csv` / `.json` | The injected anomalies: type, row, student, related rows, expected decision. Never an input to the validator |
| `MANIFEST.json` | Command, seed, scale, provenance, and row count + SHA-256 for every file |
| `VALIDATION_SUMMARY.md` | Row counts, baseline result, check families, detection scores |

Committed datasets: [`data/starter`](data/starter) (scale 0.02: CSV, JSON, SQL) and
[`data/full`](data/full) (scale 1.0: gzip CSV).

## How it works

```
master data      term, program, student, fee_schedule, eligibility
   |
enrollments -> invoices + fee lines            (outcomes: cancelled / withdrawn / completed)
   |
scholarships (negative credit lines) + fee waivers
   |
payments -> allocations to invoice lines -> late fees -> invoice status
   |
refunds (withdrawal tiers, cancellation, overpayment) -> student ledger
   |
VALIDATE the clean baseline (must be 0 issues)
   |
inject 5 labelled anomalies -> ground_truth     (the ledger anomaly is planted last)
   |
VALIDATE again and score against ground_truth -> export -> manifest + summary
```

Every derived number (invoice totals, net dues, balances, statuses, refund amounts, ledger) is computed from
source records by the rules in [`rules.py`](src/tuition_synth/rules.py), never drawn independently.
Every status change is stored as a `status_event` row, so history is never overwritten.

## Documentation

| Document | What it is for |
|---|---|
| [`docs/ER_DIAGRAM.md`](docs/ER_DIAGRAM.md) | Entity-relationship diagram of the 14 tables, relationship table, one real invoice traced through every table |
| [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) | Architecture, data flow, what every source file does, rules and constants, every validator check, tests, how to extend, troubleshooting |
| [`DESIGN.md`](DESIGN.md) | Assumptions, business rules, lifecycles, anomaly plan, limitations |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Every field: type, required, allowed values, unit, uniqueness, rule (generated from the schema) |
| [`AI_USAGE.md`](AI_USAGE.md), [`docs/PROMPT_LOG.md`](docs/PROMPT_LOG.md) | How AI assistance was used, and the prompts, unedited |

## The five injected anomalies

`ALLOCATION_EXCEEDS_PAYMENT`, `SCHOLARSHIP_EXCEEDS_FEES`, `DUPLICATE_INVOICE`, `REFUND_EXCEEDS_NET_PAID`,
`BALANCE_LEDGER_MISMATCH`: 20 each at full scale, each on its own student. The validator finds all of them and
raises no issue on any unlabelled row (checked in `tests/test_anomalies.py`).

## Project layout

| Path | Purpose |
|---|---|
| `src/tuition_synth/config.py` | Seed, scale, fixed as-of date, terms, volumes |
| `ids.py`, `schema.py`, `docs.py` | ID conventions; single source of truth for tables and fields; data dictionary |
| `reference_data.py`, `master.py` | Program catalog, prices, scholarship schemes; master-table generators |
| `transactions.py`, `scholarships.py`, `payments.py`, `refunds.py`, `ledger.py` | Transaction generators |
| `rules.py` | Business rules as pure functions (eligibility, awards, late fee, net dues, refund tiers) |
| `pipeline.py`, `anomalies.py`, `validate.py` | Orchestration, anomaly injection and scoring, validator |
| `export.py`, `ddl.py`, `report.py`, `dataset.py`, `cli.py` | Exports, SQL, summary, command line |
| `tests/` | 114 tests: rules, generators, validator (by breaking data on purpose), anomalies, exports, reproducibility, documentation in sync |

## Provenance and licence

All data is synthetic. No public, personal or confidential data was used or collected (names are fabricated
combinations; e-mail addresses use `example.edu`). Released under the MIT licence.
