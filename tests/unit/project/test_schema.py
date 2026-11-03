"""Consistency of the data schema definition."""

from __future__ import annotations

import json
import keyword

import pytest

from phrear.project.schema import (
    PARAM_QUANTITIES,
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
    assert document["schema_version"] == 1
