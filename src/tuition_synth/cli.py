"""Command-line entry point: generate, reproduce, docs."""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import DEFAULT_SEED, Config
from .dataset import generate, reproduce, render_reproducibility
from .docs import render_data_dictionary

ALL_FORMATS = {"csv", "json", "sql"}


def _formats(text: str) -> set:
    chosen = {f.strip() for f in text.split(",") if f.strip()}
    unknown = chosen - ALL_FORMATS
    if unknown or not chosen:
        raise argparse.ArgumentTypeError(f"formats must be a comma list from {sorted(ALL_FORMATS)}")
    return chosen


def _add_run_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--scale", type=float, default=1.0, help="1.0 = full volume (10,000 students)")
    p.add_argument("--formats", type=_formats, default={"csv"}, help="comma list of csv,json,sql (default csv)")
    p.add_argument("--gzip", action="store_true", help="write CSV files gzip-compressed (.csv.gz)")
    p.add_argument("--no-anomalies", action="store_true", help="skip anomaly injection (clean baseline only)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tuition-synth", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="Generate, validate and export a dataset")
    _add_run_options(p_gen)
    p_gen.add_argument("--out", type=Path, default=Path("out"))

    p_rep = sub.add_parser("reproduce", help="Generate twice and compare checksums")
    _add_run_options(p_rep)
    p_rep.add_argument("--report", type=Path, default=None, help="write the result as Markdown to this path")

    p_docs = sub.add_parser("docs", help="Regenerate docs/data_dictionary.md from the schema")
    p_docs.add_argument("--out", type=Path, default=Path("docs/data_dictionary.md"))

    args = parser.parse_args(argv)
    if args.command == "docs":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_data_dictionary() + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
        return 0

    cfg = Config(seed=args.seed, scale=args.scale)
    if args.command == "generate":
        result = generate(cfg, args.out, args.formats, args.gzip, not args.no_anomalies)
        for name, rows in result["tables"].items():
            print(f"{name:<19} {len(rows):>8,} rows")
        print(f"baseline validation: {len(result['baseline_issues'])} issue(s)")
        if result["score"]:
            s = result["score"]
            print(f"anomalies: {s['detected']}/{s['injected']} detected, {len(s['unexplained'])} unexplained issue(s)")
        print(f"wrote {len(result['manifest']['files'])} files to {args.out} (see MANIFEST.json, VALIDATION_SUMMARY.md)")
        return 0 if result["ok"] else 1

    rows = reproduce(cfg, args.formats, args.gzip, not args.no_anomalies)
    text = render_reproducibility(cfg, rows)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8", newline="\n")
    return 0 if all(r["match"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
