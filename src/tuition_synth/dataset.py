"""Generate, validate, score and export one dataset directory."""
from __future__ import annotations

import platform
import tempfile
from pathlib import Path

from . import __version__
from .anomalies import inject_anomalies, score_detection
from .config import Config
from .export import write_dataset
from .pipeline import build_all
from .report import render_validation_summary
from .validate import run_all


def generate(cfg: Config, out: Path, formats: set, gzip_csv: bool = False, anomalies: bool = True) -> dict:
    """Build the dataset, validate it and write everything to `out`. Returns a result dict."""
    tables = build_all(cfg)
    baseline_issues = run_all(tables, cfg.as_of)
    truth = inject_anomalies(cfg, tables) if anomalies else []
    issues = run_all(tables, cfg.as_of) if anomalies else baseline_issues
    score = score_detection(issues, truth) if anomalies else None

    command = f"tuition-synth generate --seed {cfg.seed} --scale {cfg.scale} --formats {','.join(sorted(formats))}"
    command += (" --gzip" if gzip_csv else "") + ("" if anomalies else " --no-anomalies")
    meta = {
        "project": "tuition-ledger-synth", "version": __version__, "command": command,
        "seed": cfg.seed, "scale": cfg.scale, "as_of": cfg.as_of.isoformat(), "python": platform.python_version(),
        "anomalies_injected": len(truth),
        "source": {"type": "fully synthetic", "external_data_used": False,
                   "note": "No public or personal data was used; names are fabricated, emails use example.edu."},
    }
    manifest = write_dataset(out, tables, truth, formats, gzip_csv, meta)
    (out / "VALIDATION_SUMMARY.md").write_text(
        render_validation_summary(meta, tables, baseline_issues, issues, score), encoding="utf-8", newline="\n")
    ok = not baseline_issues and (score is None or (score["recall"] == 1.0 and not score["unexplained"]))
    return {"tables": tables, "truth": truth, "baseline_issues": baseline_issues, "issues": issues,
            "score": score, "manifest": manifest, "ok": ok}


def reproduce(cfg: Config, formats: set, gzip_csv: bool = False, anomalies: bool = True) -> list[dict]:
    """Generate twice into temporary folders and compare row counts and checksums (Step 10)."""
    runs = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate(cfg, Path(tmp), formats, gzip_csv, anomalies)
            runs.append({f["path"]: f for f in result["manifest"]["files"]})
    rows = []
    for path in sorted(runs[0]):
        a, b = runs[0][path], runs[1].get(path)
        rows.append({"path": path, "rows": a["rows"], "sha256_run1": a["sha256"],
                     "sha256_run2": b["sha256"] if b else "", "match": bool(b) and a["rows"] == b["rows"]
                     and a["sha256"] == b["sha256"]})
    return rows


def render_reproducibility(cfg: Config, rows: list[dict]) -> str:
    ok = all(r["match"] for r in rows)
    out = ["# Reproducibility check", "",
           f"The dataset was generated twice with seed `{cfg.seed}` and scale `{cfg.scale}`, in separate "
           "temporary folders, and every output file was compared (row count and SHA-256 of the file contents).", "",
           f"**Result: {'IDENTICAL' if ok else 'DIFFERENT'}** across {len(rows)} files.", "",
           "| File | Rows | SHA-256 (run 1) | Match |", "|---|---:|---|:--:|"]
    out += [f"| `{r['path']}` | {r['rows']:,} | `{r['sha256_run1'][:16]}...` | {'yes' if r['match'] else 'NO'} |" for r in rows]
    return "\n".join(out) + "\n"
