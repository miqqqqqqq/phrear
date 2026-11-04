"""Consistency of the data schema definition."""

from __future__ import annotations

import json
import keyword

import pytest

from phrear.project.schema import (
    PARAM_QUANTITIES,
    SCHEMA_VERSION,
    SERIES_QUANTITIES,
    TABLES,
    FieldType,
    TableDef,
    schema_document,
)
from phrear.units import conversion_factor

# Words that would need quoting in SQL or in QGIS expressions.
SQL_RESERVED = {
    "order", "index", "group", "select", "table", "from", "where", "key", "fid", "geom",
    "default", "check", "unique", "primary", "references", "limit", "offset",
}  # fmt: skip


@pytest.mark.parametrize("table", TABLES, ids=lambda t: t.name)
def test_table_is_well_formed(table: TableDef) -> None:
    names = table.field_names
    assert len(names) == len(set(names)), "duplicate field names"
    assert table.label.it and table.label.en
    assert table.help.it and table.help.en
    for f in table.fields:
        assert f.name.isidentifier() and not keyword.iskeyword(f.name)
        assert f.name not in SQL_RESERVED, f"{table.name}.{f.name} is a reserved word"
        assert f.label.it and f.label.en, f"{table.name}.{f.name} lacks a label"
        if f.default is not None and f.choices:
            assert f.default in f.choice_values
        for choice in f.choices:
            assert choice.label.it and choice.label.en
        if f.quantity is not None:
            assert f.type is FieldType.TEXT
            assert isinstance(f.default, str)
            conversion_factor(f.default, f.quantity)
    for columns in table.unique:
        assert set(columns) <= set(names)


def test_table_names_are_unique() -> None:
    names = [t.name for t in TABLES]
    assert len(names) == len(set(names))


def test_param_choices_match_quantities() -> None:
    from phrear.project.schema import TABLES_BY_NAME

    param = TABLES_BY_NAME["param_values"].field("param")
    assert set(param.choice_values) == set(PARAM_QUANTITIES)
    quantity = TABLES_BY_NAME["timeseries_meta"].field("quantity")
    assert set(quantity.choice_values) == set(SERIES_QUANTITIES)


def test_station_targets_are_layers_of_the_schema() -> None:
    from phrear.project.schema import TABLES_BY_NAME

    targets = TABLES_BY_NAME["line_stations"].field("feature_layer").choice_values
    for name in targets:
        assert TABLES_BY_NAME[name].is_layer


def test_schema_document_is_json_serialisable() -> None:
    document = schema_document()
    text = json.dumps(document, ensure_ascii=False)
    assert '"wells"' in text
    assert document["schema_version"] == SCHEMA_VERSION == 2


def test_relations_and_lookups_point_to_existing_fields() -> None:
    from phrear.project.schema import RELATIONS, TABLES, TABLES_BY_NAME

    def has(table: str, field: str) -> bool:
        return field == "fid" or field in TABLES_BY_NAME[table].field_names

    for r in RELATIONS:
        assert has(r.child, r.child_field), r.name
        for parent in (r.parent, *r.parents):
            if parent is not None:
                assert has(parent, r.parent_field), (r.name, parent)
        assert (r.parent is None) == bool(r.parents), r.name
        if r.parent_table_field is not None:
            choices = TABLES_BY_NAME[r.child].field(r.parent_table_field).choice_values
            assert set(r.parents) <= set(choices), r.name
        for field, value in r.child_filter:
            assert value in TABLES_BY_NAME[r.child].field(field).choice_values
    for table in TABLES:
        for f in table.fields:
            if f.lookup is not None:
                assert has(f.lookup.table, f.lookup.key), (table.name, f.name)
                assert has(f.lookup.table, f.lookup.value or f.lookup.key), (table.name, f.name)
                for field, value in f.lookup.filter:
                    assert value in TABLES_BY_NAME[f.lookup.table].field(field).choice_values


def test_every_layer_has_a_style() -> None:
    from phrear.project.schema import TABLES

    kinds = {"Point": "marker", "MultiLineString": "line", "MultiPolygon": "fill"}
    for table in TABLES:
        if table.geometry is not None:
            assert table.style is not None and table.style.kind == kinds[table.geometry], table.name


def test_schema_document_has_relations_lookups_and_styles() -> None:
    from phrear.project.schema import schema_document

    doc = schema_document()
    assert [r["name"] for r in doc["relations"]] == [
        "unit_parameters", "zone_parameters", "series_values", "feature_stations"
    ]  # fmt: skip
    wells = next(t for t in doc["tables"] if t["name"] == "wells")
    series = next(f for f in wells["fields"] if f["name"] == "series_id")
    assert series["lookup"] == {
        "table": "timeseries_meta",
        "key": "series_id",
        "value": "series_id",
        "filter": {"quantity": "discharge"},
    }
    lines = next(t for t in doc["tables"] if t["name"] == "fixed_head_lines")
    top = next(f for f in lines["fields"] if f["name"] == "top_unit")
    assert top["lookup"]["key"] == "position" and top["lookup"]["value"] == "name"
    assert wells["style"]["kind"] == "marker" and wells["style"]["color"].startswith("#")
