"""Render the data dictionary (Markdown) from schema.py."""
from __future__ import annotations

from .schema import TABLES, Table


def _cell(text: str) -> str:
    return text.replace("|", "\\|") if text else ""


def _render_table(t: Table) -> str:
    ext = " _(extension)_" if t.extension else ""
    out = [f"### `{t.name}` - {t.entity}{ext}", "", t.description, "", f"**Primary key:** `{t.pk}`", ""]
    fks = t.foreign_keys()
    if fks:
        out.append("**Foreign keys:** " + ", ".join(f"`{f.name}` -> `{f.fk}`" for f in fks))
        out.append("")
    if t.relationships:
        out.append("**Relationships / cardinality:**")
        out.extend(f"- {r}" for r in t.relationships)
        out.append("")
    out.append("| Field | Type | Required | Unique | Allowed values | Unit | Rule |")
    out.append("|---|---|---|---|---|---|---|")
    for f in t.fields:
        out.append(
            "| `{}` | {} | {} | {} | {} | {} | {} |".format(
                f.name, f.type, "yes" if f.required else "no", "yes" if f.unique else "",
                _cell(", ".join(f.allowed)), _cell(f.unit), _cell(f.rule),
            )
        )
    out.append("")
    return "\n".join(out)


def render_data_dictionary() -> str:
    head = [
        "# Data dictionary",
        "",
        "_Generated from `src/tuition_synth/schema.py` by `tuition-synth docs`. Do not edit by hand._",
        "",
        "Money is decimal with 2 places in INR. Dates are ISO-8601. Tables marked "
        "_(extension)_ are additions beyond the 11 entities in the problem statement.",
        "",
    ]
    return "\n".join(head) + "\n" + "\n".join(_render_table(t) for t in TABLES.values())
