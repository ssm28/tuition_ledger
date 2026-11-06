from pathlib import Path

from tuition_synth.docs import render_data_dictionary
from tuition_synth.schema import REQUIRED_ENTITIES, TABLES


def test_all_required_entities_present():
    entities = {t.entity for t in TABLES.values()}
    assert set(REQUIRED_ENTITIES) <= entities


def test_every_table_has_unique_required_string_pk():
    for t in TABLES.values():
        pk = next(f for f in t.fields if f.name == t.pk)
        assert pk.required and pk.unique and pk.type == "string", t.name


def test_foreign_keys_point_at_existing_primary_keys():
    for t in TABLES.values():
        for f in t.foreign_keys():
            table, column = f.fk.split(".")
            assert table in TABLES, (t.name, f.name)
            assert TABLES[table].pk == column, (t.name, f.name)


def test_no_duplicate_field_names_and_known_types():
    for t in TABLES.values():
        assert len(t.field_names) == len(set(t.field_names)), t.name
        assert {f.type for f in t.fields} <= {"string", "int", "decimal", "date"}


def test_parents_are_defined_before_children():
    seen = set()
    for name, t in TABLES.items():
        for f in t.foreign_keys():
            assert f.fk.split(".")[0] in seen | {name}, (name, f.fk)
        seen.add(name)


def test_committed_data_dictionary_is_up_to_date():
    path = Path(__file__).resolve().parents[1] / "docs" / "data_dictionary.md"
    assert path.read_text(encoding="utf-8") == render_data_dictionary() + "\n"
