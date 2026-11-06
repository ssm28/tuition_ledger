# tuition-ledger-synth

Deterministic synthetic data generator and validator for a tuition, scholarship,
payment and balance-reconciliation workflow. Fixed seed `20261022`, parameterized scale.

> **Status:** foundation (config, ID conventions, schema, data dictionary). The generator,
> anomaly injector and validator are being added next; this README is updated as each lands.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
tuition-synth docs        # regenerate docs/data_dictionary.md from the schema
```

## Project layout

| Path | Purpose |
|---|---|
| `src/tuition_synth/config.py` | Seed, scale, fixed as-of date, terms, base volumes |
| `src/tuition_synth/ids.py` | Deterministic ID builders and format checks |
| `src/tuition_synth/schema.py` | Single source of truth for tables, fields, enums, keys |
| `src/tuition_synth/docs.py` | Renders the data dictionary from the schema |
| `docs/data_dictionary.md` | Generated field-level dictionary |
| `DESIGN.md` | Assumptions, business rules, lifecycles, anomaly plan |
| `tests/` | Unit tests |

## Provenance

All data is synthetic. No external or personal data is used.

## License

MIT
