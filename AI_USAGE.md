# AI usage statement

This project was built with the help of an AI assistant. This page says what the assistant did, what I decided
and checked myself, and where the evidence is. The prompts I wrote are in [`docs/PROMPT_LOG.md`](docs/PROMPT_LOG.md),
unedited.

## Summary

| | |
|---|---|
| Tool | Claude (Anthropic), used in the claude.ai chat interface |
| How it was used | One long conversation over two days. I described the goal and made the decisions; the assistant proposed the design and wrote the code, tests and documentation |
| What I did myself | Read and approved the business rules, made design decisions, ran the code and tests on my machine, inspected the generated data, found problems, managed the Git repository |
| Evidence of verification | 114 tests, a validator checked against planted errors, reproducibility reports, validation summaries (see below) |

## What the assistant did

| Area | Assistant's contribution |
|---|---|
| Planning | Proposed the schedule, the repository layout and the architecture (one schema as the source of truth, rules in one module, a separate validator, a separate ground-truth file) |
| Domain rules | Drafted the business rules in `DESIGN.md` (fees, scholarship eligibility, allocation, late fees, refund tiers, lifecycles) for my review |
| Code | Wrote the generators, validator, anomaly injector, exporters and command line in `src/tuition_synth/` |
| Tests | Wrote the test suite in `tests/` |
| Documentation | Drafted `README.md`, `DESIGN.md`, `docs/` and this page |
| Explanation | Explained concepts (primary and foreign keys, why a fixed "as-of" date is needed, what a validator and ground truth are) because I was new to this kind of project |

## Decisions I made

- Chose Python as the language.
- Asked to keep fees simple, so there are no per-credit-hour fees: each fee is one fixed amount per term.
- Chose a **fixed late fee of INR 500** instead of a percentage.
- Read the proposed business rules (late fees, refund tiers and the rest of `DESIGN.md`) and approved them.
- Asked for the remaining steps to be completed in one go once I was comfortable with the design.
- Asked for the ER diagram, the developer guide and this transparency documentation.
- Resolved a Git problem myself: the packages I received contained a `.git` folder from another copy, which clashed
  with my repository's history and made pushes fail; I fixed it so that I could push my files safely.

## How I checked the work

- I ran the test suite on my machine and read the generated CSV files.
- I followed one randomly chosen student's records across all the tables to understand how they connect.
- I tried changing a rule myself (Summer fee factor from 0.6 to 0.7). The test still passed, which showed that
  the test was checking the code against itself. It was rewritten to compare against the documented factors and
  hand-computed prices, and it now fails on that change.
- The validator is tested by deliberately breaking clean data (`tests/test_validate.py`).
- Planted errors are kept in a separate `ground_truth` file and the validator is scored against them: 100 of 100
  found, with no issue raised on any row that was not planted (`reports/validation_summary_full.md`).
- Two runs with the same seed give identical files (`reports/reproducibility_full.md`).
- The assistant ran the tests in its own sandbox with a minimal stand-in for `pytest`, because `pytest` was not
  installed there; the `pytest` run on my machine is the authoritative one.

## Mistakes found and fixed along the way

- The fee test compared the generated prices with the same constant the generator used, so it could not fail
  (found by my experiment above).
- The assistant first described a scholarship scheme's end date incorrectly (eligibility is judged on the date the
  award is decided, not on the term); it corrected this and added a test for the boundary.
- Scoring the validator against the ground truth exposed two flaws in the first version: the validator mislabelled
  scholarships of students with a duplicate invoice, and one planted error disturbed neighbouring rows. Both were fixed.
- A final review found that the report's list of check families was incomplete and that a leftover function was
  unused; both were corrected.

## Limits

AI-generated code and text can contain mistakes. The tests, the validation summaries and the reproducibility reports
document what was actually verified; the known simplifications of the data are listed in `DESIGN.md` section 13.
I am responsible for everything in this repository.
