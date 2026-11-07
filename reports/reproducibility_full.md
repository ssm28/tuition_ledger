# Reproducibility check

The dataset was generated twice with seed `20261022` and scale `1.0`, in separate temporary folders, and every output file was compared (row count and SHA-256 of the file contents).

**Result: IDENTICAL** across 16 files.

| File | Rows | SHA-256 (run 1) | Match |
|---|---:|---|:--:|
| `csv/eligibility.csv` | 8 | `8adda069806d3d7f...` | yes |
| `csv/enrollment.csv` | 30,000 | `dd8a6be557cfa9b1...` | yes |
| `csv/fee_schedule.csv` | 276 | `97f79070d8ac353f...` | yes |
| `csv/invoice.csv` | 30,020 | `27e0c3956cf5117a...` | yes |
| `csv/invoice_line.csv` | 160,809 | `65b20c659fc60e39...` | yes |
| `csv/ledger_entry.csv` | 213,768 | `bc0a1d54743ea1a4...` | yes |
| `csv/payment.csv` | 50,000 | `3e360e3976ba2e8e...` | yes |
| `csv/payment_allocation.csv` | 146,496 | `ef322dc28e4fedf9...` | yes |
| `csv/program.csv` | 20 | `45c53701c66c1ed0...` | yes |
| `csv/refund.csv` | 3,000 | `d966abc259a6016f...` | yes |
| `csv/scholarship.csv` | 15,000 | `fd00b15d6e278bb5...` | yes |
| `csv/status_event.csv` | 223,383 | `4f9526683d561321...` | yes |
| `csv/student.csv` | 10,000 | `8a522d42b4550227...` | yes |
| `csv/term.csv` | 3 | `7b2e6ca7983a4517...` | yes |
| `ground_truth.csv` | 100 | `3454a089888df387...` | yes |
| `ground_truth.json` | 100 | `49180b361833cce6...` | yes |
