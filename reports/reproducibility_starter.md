# Reproducibility check

The dataset was generated twice with seed `20261022` and scale `0.02`, in separate temporary folders, and every output file was compared (row count and SHA-256 of the file contents).

**Result: IDENTICAL** across 32 files.

| File | Rows | SHA-256 (run 1) | Match |
|---|---:|---|:--:|
| `csv/eligibility.csv` | 8 | `8adda069806d3d7f...` | yes |
| `csv/enrollment.csv` | 600 | `b0f2bf39edde81e3...` | yes |
| `csv/fee_schedule.csv` | 276 | `97f79070d8ac353f...` | yes |
| `csv/invoice.csv` | 603 | `d28876792150e119...` | yes |
| `csv/invoice_line.csv` | 3,226 | `acfda4c422ad799f...` | yes |
| `csv/ledger_entry.csv` | 4,285 | `e1e8a2cd6fde6cdd...` | yes |
| `csv/payment.csv` | 1,000 | `bb2ce3218116a422...` | yes |
| `csv/payment_allocation.csv` | 2,923 | `70850a265846a3f5...` | yes |
| `csv/program.csv` | 20 | `45c53701c66c1ed0...` | yes |
| `csv/refund.csv` | 55 | `336ea4ff0cf90e0a...` | yes |
| `csv/scholarship.csv` | 300 | `0db4b3b343c9f4d9...` | yes |
| `csv/status_event.csv` | 4,457 | `f534878732e7d5b9...` | yes |
| `csv/student.csv` | 200 | `745835c6755a0bb6...` | yes |
| `csv/term.csv` | 3 | `7b2e6ca7983a4517...` | yes |
| `ground_truth.csv` | 15 | `892001c2e4216fe9...` | yes |
| `ground_truth.json` | 15 | `cf29d4473ad633c9...` | yes |
| `json/eligibility.json` | 8 | `193a347fa18b92f2...` | yes |
| `json/enrollment.json` | 600 | `25bb12468399be5b...` | yes |
| `json/fee_schedule.json` | 276 | `4ad9dbf3d849e6b9...` | yes |
| `json/invoice.json` | 603 | `261f8687dc2b800f...` | yes |
| `json/invoice_line.json` | 3,226 | `ce7ed02bb3e789ba...` | yes |
| `json/ledger_entry.json` | 4,285 | `fe4d0d8173f2594e...` | yes |
| `json/payment.json` | 1,000 | `7505eee920798796...` | yes |
| `json/payment_allocation.json` | 2,923 | `fadc9b880a894295...` | yes |
| `json/program.json` | 20 | `222508f18d44af7b...` | yes |
| `json/refund.json` | 55 | `386d6e7652669e1f...` | yes |
| `json/scholarship.json` | 300 | `48b94c6e315a73a9...` | yes |
| `json/status_event.json` | 4,457 | `dcfe612f8646d6b6...` | yes |
| `json/student.json` | 200 | `be20fc6ee9c53c98...` | yes |
| `json/term.json` | 3 | `e9152c14e655f49c...` | yes |
| `sql/schema.sql` | 0 | `86423a4ecd829a26...` | yes |
| `sql/seed.sql` | 17,956 | `081a69e0ded843ef...` | yes |
