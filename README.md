# tuition-ledger-synth

Deterministic synthetic data generator and validator for a tuition, scholarship,
payment and balance-reconciliation workflow. Fixed seed `20261022`, parameterized scale.

> **Status:** master tables, enrollments, invoices, invoice lines and status history are generated,
> validated and tested. Scholarships, payments, refunds, the ledger and anomaly injection are
> being added next; this README is updated as each lands.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
tuition-synth docs        # regenerate docs/data_dictionary.md from the schema

# generate the master tables as CSV (scale 1.0 = full volume; 0.02 = small starter)
tuition-synth master --scale 0.02 --out out/

# generate everything built so far, run the validator, write CSVs
tuition-synth generate --scale 0.02 --out out/
```

Both commands print a short SHA-256 per file. Running it twice with the same seed and scale prints identical values.

## Project layout

| Path | Purpose |
|---|---|
| `src/tuition_synth/config.py` | Seed, scale, fixed as-of date, terms, base volumes |
| `src/tuition_synth/ids.py` | Deterministic ID builders and format checks |
| `src/tuition_synth/schema.py` | Single source of truth for tables, fields, enums, keys |
| `src/tuition_synth/reference_data.py` | Program catalog, fee amounts, scholarship schemes, name lists |
| `src/tuition_synth/master.py` | Generators for the master tables |
| `src/tuition_synth/transactions.py` | Enrollments, invoices, invoice lines |
| `src/tuition_synth/events.py` | Status-history log (every state change is a row) |
| `src/tuition_synth/validate.py` | Validator: structure, arithmetic, duplicates, lifecycle |
| `src/tuition_synth/export.py` | Stable-format CSV writer and checksums |
| `src/tuition_synth/docs.py` | Renders the data dictionary from the schema |
| `docs/data_dictionary.md` | Generated field-level dictionary |
| `DESIGN.md` | Assumptions, business rules, lifecycles, anomaly plan |
| `tests/` | Unit tests |

## Provenance

All data is synthetic. No external or personal data is used.

## License

MIT
