"""Documentation that is checked against the code, so it cannot silently drift."""
import re
from pathlib import Path

from tuition_synth.report import FAMILIES
from tuition_synth.schema import TABLES

ROOT = Path(__file__).resolve().parents[1]
ER = (ROOT / "docs" / "ER_DIAGRAM.md").read_text(encoding="utf-8")


def _mermaid() -> str:
    match = re.search(r"```mermaid\n(.*?)\n```", ER, re.S)
    assert match, "docs/ER_DIAGRAM.md has no mermaid block"
    return match.group(1)


def test_er_diagram_has_every_table_with_its_primary_key():
    diagram = _mermaid()
    for table in TABLES.values():
        block = re.search(r"\n    " + table.name + r" \{\n(.*?)\n    \}", diagram, re.S)
        assert block, f"table {table.name} missing from the ER diagram"
        assert f"string {table.pk} PK" in block.group(1), table.name


def test_er_diagram_has_every_foreign_key_as_a_relationship_and_attribute():
    diagram = _mermaid()
    for table in TABLES.values():
        block = re.search(r"\n    " + table.name + r" \{\n(.*?)\n    \}", diagram, re.S).group(1)
        for fk in table.foreign_keys():
            parent = fk.fk.split(".")[0]
            symbol = r"\|\|--o\{" if fk.required else r"\|o--o\{"
            assert re.search(rf"\n    {parent} {symbol} {table.name} : ", diagram), (parent, table.name)
            assert f"string {fk.name} FK" in block, (table.name, fk.name)


def test_er_diagram_attributes_exist_in_the_schema():
    diagram = _mermaid()
    for table in TABLES.values():
        block = re.search(r"\n    " + table.name + r" \{\n(.*?)\n    \}", diagram, re.S).group(1)
        for line in block.splitlines():
            _type, name = line.split()[:2]
            assert name in table.field_names, (table.name, name)


def test_every_validator_check_belongs_to_exactly_one_report_family():
    raised = set(re.findall(r'Issue\("([a-z_]+)"', (ROOT / "src" / "tuition_synth" / "validate.py").read_text()))
    listed = [check for checks in FAMILIES.values() for check in checks]
    assert len(listed) == len(set(listed)), "a check is listed in two families"
    assert set(listed) == raised


def test_markdown_links_to_files_resolve():
    for md in ROOT.rglob("*.md"):
        if "data" in md.relative_to(ROOT).parts:
            continue
        for target in re.findall(r"\]\(([^)#\s]+)\)", md.read_text(encoding="utf-8")):
            if target.startswith(("http", "mailto")):
                continue
            assert (md.parent / target).exists(), f"{md.relative_to(ROOT)} links to missing {target}"
