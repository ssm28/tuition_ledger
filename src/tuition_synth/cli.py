"""Command-line entry point. More subcommands (generate, validate) land as they are built."""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import DEFAULT_SEED, Config
from .docs import render_data_dictionary
from .export import sha256_of, write_csv
from .master import build_master
from .pipeline import build_all
from .validate import run_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tuition-synth", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_docs = sub.add_parser("docs", help="Regenerate docs/data_dictionary.md from the schema")
    p_docs.add_argument("--out", type=Path, default=Path("docs/data_dictionary.md"))

    p_master = sub.add_parser("master", help="Generate the master tables as CSV")
    p_master.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p_master.add_argument("--scale", type=float, default=1.0, help="1.0 = full volume")
    p_master.add_argument("--out", type=Path, default=Path("out"))

    p_gen = sub.add_parser("generate", help="Generate all tables built so far, validate, and write CSVs")
    p_gen.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p_gen.add_argument("--scale", type=float, default=1.0, help="1.0 = full volume")
    p_gen.add_argument("--out", type=Path, default=Path("out"))

    args = parser.parse_args(argv)
    if args.command == "docs":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_data_dictionary() + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    elif args.command == "master":
        cfg = Config(seed=args.seed, scale=args.scale)
        for table, rows in build_master(cfg).items():
            path = args.out / f"{table}.csv"
            write_csv(path, table, rows)
            print(f"{table:<13} {len(rows):>6} rows  sha256={sha256_of(path)[:12]}  {path}")
    elif args.command == "generate":
        cfg = Config(seed=args.seed, scale=args.scale)
        tables = build_all(cfg)
        for table, rows in tables.items():
            path = args.out / f"{table}.csv"
            write_csv(path, table, rows)
            print(f"{table:<13} {len(rows):>7} rows  sha256={sha256_of(path)[:12]}")
        issues = run_all(tables)
        print(f"validation: {len(issues)} issue(s)")
        return 1 if issues else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
