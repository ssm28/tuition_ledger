"""Command-line entry point. More subcommands (generate, validate) land as they are built."""
from __future__ import annotations

import argparse
from pathlib import Path

from .docs import render_data_dictionary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tuition-synth", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_docs = sub.add_parser("docs", help="Regenerate docs/data_dictionary.md from the schema")
    p_docs.add_argument("--out", type=Path, default=Path("docs/data_dictionary.md"))

    args = parser.parse_args(argv)
    if args.command == "docs":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_data_dictionary() + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
