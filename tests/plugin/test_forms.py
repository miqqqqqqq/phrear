"""Forms, relations and styles planned from the schema document."""

from __future__ import annotations

from typing import Any

import pytest

from phrear_qgis.client.forms import (
    FieldPlan,
    FormPlan,
    alias,
    display_expression,
    equality_filter,
    form_plan,
    form_plans,
    literal,
    project_key,
    relation_plans,
    rgba,
    styles,
    symbol_properties,
)


def table(schema: dict[str, Any], name: str) -> dict[str, Any]:
    return next(t for t in schema["project"]["tables"] if t["name"] == name)


def field(plans: dict[str, FormPlan], table_name: str, name: str) -> FieldPlan:
    return next(f for f in plans[table_name].fields if f.name == name)


@pytest.fixture(scope="module")
def plans_it(schema: dict[str, Any]) -> dict[str, FormPlan]:
    return form_plans(schema, "it")


def test_literals() -> None:
    assert literal("l/s") == "'l/s'"
    assert literal("dell'Arno") == "'dell''Arno'"
    assert literal(True) == "true" and literal(False) == "false"
    assert literal(2) == "2" and literal(0.5) == "0.5"
    with pytest.raises(ValueError):
        literal(float("nan"))
    assert equality_filter({"quantity": "discharge"}) == "\"quantity\" = 'discharge'"
    assert equality_filter({}) == ""


def test_alias_carries_the_unit() -> None:
    entry = {
        "name": "screen_top",
        "label": {"it": "Inizio filtro", "en": "Screen top"},
        "unit": "m",
    }
    assert alias(entry, "it") == "Inizio filtro [m]"
    assert alias(entry, "en") == "Screen top [m]"
    assert alias({"name": "rate", "label": {"en": "Rate"}}, "it") == "Rate"
    assert alias({"name": "rate"}, "it") == "rate"


def test_widgets_follow_the_field_type(plans_it: dict[str, FormPlan]) -> None:
    role = field(plans_it, "wells", "role")
    assert role.widget.type == "ValueMap"
    assert role.widget.config["map"] == [{"Estrazione": "extraction"}, {"Iniezione": "injection"}]
    assert field(plans_it, "wells", "active").widget.type == "CheckBox"
    # Real numbers in a text box: the spin box would round to the field precision.
    assert field(plans_it, "wells", "screen_top").widget.type == "TextEdit"
    notes = field(plans_it, "wells", "notes").widget
    assert notes.type == "TextEdit" and notes.config["IsMultiline"] is True
    position = field(plans_it, "hydro_units", "position").widget
    assert position.type == "Range"
    assert position.config["Min"] == 1 and position.config["Step"] == 1
    when = field(plans_it, "timeseries_values", "datetime").widget
    assert when.type == "DateTime" and when.config["calendar_popup"] is True


def test_every_widget_accepts_an_empty_value(plans_it: dict[str, FormPlan]) -> None:
    # A required field must stay empty until filled, not take the first entry or today.
    assert field(plans_it, "timeseries_values", "datetime").widget.config["allow_null"] is True
    assert field(plans_it, "param_values", "object_id").widget.config["AllowNull"] is True
    assert field(plans_it, "timeseries_values", "series_id").widget.config["AllowNull"] is True


def test_lookups_become_filtered_value_relations(plans_it: dict[str, FormPlan]) -> None:
    series = field(plans_it, "wells", "series_id").widget
    assert series.type == "ValueRelation" and series.lookup_table == "timeseries_meta"
    assert series.config["Key"] == series.config["Value"] == "series_id"
    assert series.config["FilterExpression"] == "\"quantity\" = 'discharge'"
    stations = field(plans_it, "line_stations", "series_id").widget
    assert stations.config["FilterExpression"] == "\"quantity\" = 'length'"
    recharge = field(plans_it, "recharge_zones", "series_id").widget
    assert recharge.config["FilterExpression"] == "\"quantity\" = 'velocity'"
    top = field(plans_it, "fixed_head_lines", "top_unit").widget
    assert (top.lookup_table, top.config["Key"], top.config["Value"]) == (
        "hydro_units", "position", "name"
    )  # fmt: skip
    scenario = field(plans_it, "wells", "scenario_id").widget
    assert scenario.lookup_table == "scenarios" and scenario.config["FilterExpression"] == ""


def test_constraints_and_defaults(plans_it: dict[str, FormPlan]) -> None:
    top = field(plans_it, "wells", "screen_top")
    assert top.required and not top.read_only and top.range_expression is None
    radius = field(plans_it, "wells", "radius")
    assert not radius.required
    assert radius.range_expression == '"radius" IS NULL OR ("radius" >= 0)'
    assert field(plans_it, "wells", "role").default == "'extraction'"
    assert field(plans_it, "wells", "active").default == "true"
    assert field(plans_it, "wells", "rate_unit").default == "'l/s'"
    assert field(plans_it, "param_values", "object_type").default == "'unit'"
    assert field(plans_it, "wells", "name").default is None
    assert field(plans_it, "timeseries_meta", "series_id").unique
    # Composite keys are checked by the core, not by single-field constraints.
    assert not field(plans_it, "param_values", "param").unique


def test_range_expression_with_both_bounds() -> None:
    plan = form_plan(
        {
            "name": "t",
            "fields": [{"name": "x", "type": "real", "minimum": 0, "maximum": 1}],
        },
        "en",
    ).fields[0]
    assert plan.range_expression == '"x" IS NULL OR ("x" >= 0 AND "x" <= 1)'


def test_system_fields_are_read_only_and_last(plans_it: dict[str, FormPlan]) -> None:
    names = [f.name for f in plans_it["wells"].fields]
    assert names[-2:] == ["created_at", "modified_at"]
    assert names[-3] == "notes"
    assert names[0] == "name"
    assert field(plans_it, "wells", "created_at").read_only
    assert field(plans_it, "change_log", "time").read_only


def test_every_schema_field_has_a_plan(
    schema: dict[str, Any], plans_it: dict[str, FormPlan]
) -> None:
    for t in schema["project"]["tables"]:
        assert sorted(f.name for f in plans_it[t["name"]].fields) == sorted(
            f["name"] for f in t["fields"]
        )
        for f in plans_it[t["name"]].fields:
            assert f.alias and f.widget.type


def test_display_expressions(schema: dict[str, Any]) -> None:
    relations = schema["project"]["relations"]
    assert display_expression(table(schema, "timeseries_meta"), relations) == '"series_id"'
    assert (
        display_expression(table(schema, "wells"), relations)
        == 'coalesce("name", to_string("fid"))'
    )
    assert display_expression(table(schema, "param_values"), relations) == (
        'concat("param", \' = \', "value")'
    )
    assert display_expression(table(schema, "timeseries_values"), relations) == (
        'concat("datetime", \' = \', "value")'
    )
    assert display_expression(table(schema, "change_log"), relations) is None


def test_relations(schema: dict[str, Any]) -> None:
    plans = {p.name: p for p in relation_plans(schema, "en", "/data/progetto")}
    assert set(plans) == {"Unit parameters", "Zone parameters", "Series values", "Stations"}
    zones = plans["Zone parameters"]
    assert zones.polymorphic and zones.parents == ("param_zones",)
    assert (zones.layer_field, zones.layer_expression) == ("object_type", "'zone'")
    units = plans["Unit parameters"]
    assert units.polymorphic and units.parents == ("hydro_units",)
    assert (units.layer_field, units.layer_expression) == ("object_type", "'unit'")
    assert (units.child, units.child_field, units.parent_field) == (
        "param_values", "object_id", "fid"
    )  # fmt: skip
    series = plans["Series values"]
    assert not series.polymorphic and series.parents == ("timeseries_meta",)
    stations = plans["Stations"]
    assert stations.polymorphic
    assert stations.parents == ("fixed_head_lines", "fixed_head_areas")
    assert (stations.layer_field, stations.layer_expression) == ("feature_layer", "@phrear_table")


def test_relation_ids_depend_on_the_project(schema: dict[str, Any]) -> None:
    a = {p.id for p in relation_plans(schema, "it", "/data/uno")}
    b = {p.id for p in relation_plans(schema, "it", "/data/due")}
    assert not a & b
    assert all(i.startswith("phrear_" + project_key("/data/uno")) for i in a)
    assert project_key("/data/uno") == project_key("/data/uno/")


def test_relations_reject_unsupported_filters(schema: dict[str, Any]) -> None:
    doc: dict[str, Any] = {
        "project": {
            "relations": [
                {
                    "name": "r",
                    "label": {},
                    "child": "c",
                    "child_field": "p",
                    "parent": "p",
                    "parents": [],
                    "parent_table_field": None,
                    "parent_field": "fid",
                    "child_filter": {"a": "1", "b": "2"},
                }
            ]
        }
    }
    with pytest.raises(ValueError, match="one child filter"):
        relation_plans(doc, "en", "/x")


def test_symbols(schema: dict[str, Any]) -> None:
    assert rgba("#2a78d6") == "42,120,214,255"
    assert rgba("#000000", 0.25) == "0,0,0,64"
    with pytest.raises(ValueError):
        rgba("blue")
    found = styles(schema)
    geometry = {t["name"] for t in schema["project"]["tables"] if t["geometry"]}
    assert set(found) == geometry
    kind, wells = symbol_properties(found["wells"])
    assert kind == "marker" and wells["name"] == "circle" and wells["size_unit"] == "MM"
    kind, domain = symbol_properties(found["domain"])
    assert kind == "fill" and domain["style"] == "no"
    assert domain["outline_color"] == rgba(found["domain"]["color"])
    kind, recharge = symbol_properties(found["recharge_zones"])
    assert kind == "fill" and recharge["style"] == "solid" and recharge["color"].endswith(",38")
    kind, lines = symbol_properties(found["fixed_head_lines"])
    assert kind == "line" and lines["line_width_unit"] == "MM"
    with pytest.raises(ValueError):
        symbol_properties({"kind": "raster", "color": "#000000"})
