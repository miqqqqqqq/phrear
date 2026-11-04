"""Attribute forms, relations and layer styles planned from the schema document.

Everything here is plain data derived from ``phrear schema``: field aliases with
units, editor widgets, constraints, defaults, relations between layers and simple
symbols. The Qt side (``forms.py``, ``styles.py``) applies these plans to the
QGIS layers; this module needs neither QGIS nor Qt, so it is tested in CI.
"""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Text fields edited in a multi-line box.
MULTILINE_FIELDS = frozenset({"notes", "description", "detail"})
#: Layer variable holding the table name, used by polymorphic relations.
TABLE_VARIABLE = "phrear_table"


def localized(entry: dict[str, Any] | None, lang: str) -> str:
    entry = entry or {}
    return str(entry.get(lang) or entry.get("en") or "")


def quote_literal(value: str) -> str:
    """A string literal of the QGIS expression language."""
    return "'" + value.replace("'", "''") + "'"


def quote_field(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def literal(value: Any) -> str:
    """``value`` as a QGIS expression: strings quoted, booleans, numbers."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"not a finite number: {value!r}")
        return repr(value)
    return quote_literal(str(value))


def equality_filter(pairs: dict[str, Any]) -> str:
    return " AND ".join(f"{quote_field(k)} = {literal(v)}" for k, v in pairs.items())


@dataclass(frozen=True)
class Widget:
    """An editor widget of QGIS: its type id and configuration."""

    type: str
    config: dict[str, Any] = field(default_factory=dict)
    lookup_table: str | None = None
    """For a ``ValueRelation``, the table whose layer goes in the configuration."""


@dataclass(frozen=True)
class FieldPlan:
    name: str
    alias: str
    help: str
    widget: Widget
    read_only: bool
    required: bool
    unique: bool
    minimum: float | None
    maximum: float | None
    default: str | None
    """Default value as a QGIS expression."""

    @property
    def range_expression(self) -> str | None:
        """Expression true when the value is empty or within the schema range."""
        name = quote_field(self.name)
        checks = []
        if self.minimum is not None:
            checks.append(f"{name} >= {literal(self.minimum)}")
        if self.maximum is not None:
            checks.append(f"{name} <= {literal(self.maximum)}")
        if not checks:
            return None
        return f"{name} IS NULL OR ({' AND '.join(checks)})"


def alias(entry: dict[str, Any], lang: str) -> str:
    """The field label with its unit, e.g. «Inizio filtro [m]»."""
    label = localized(entry.get("label"), lang) or entry["name"]
    unit = entry.get("unit")
    return f"{label} [{unit}]" if unit else label


def widget(entry: dict[str, Any], lang: str) -> Widget:
    """The editor widget of a field.

    Every widget can show an empty value, required fields included: a list or a
    date that cannot be empty would silently fill the field with its first entry
    or with today. Required fields are enforced by a constraint instead. A
    ``ValueMap`` gets its empty entry on the Qt side, with a translated label.
    """
    kind = entry["type"]
    lookup = entry.get("lookup")
    if entry.get("choices"):
        values = [{localized(c["label"], lang) or c["value"]: c["value"]} for c in entry["choices"]]
        return Widget("ValueMap", {"map": values})
    if lookup:
        relation = {
            "Key": lookup["key"],
            "Value": lookup.get("value") or lookup["key"],
            "FilterExpression": equality_filter(lookup.get("filter") or {}),
            "AllowNull": True,
            "OrderByKey": True,
            "OrderByValue": False,
            "AllowMulti": False,
            "UseCompleter": False,
            "NofColumns": 1,
        }
        return Widget("ValueRelation", relation, lookup_table=lookup["table"])
    if kind == "boolean":
        return Widget(
            "CheckBox", {"CheckedState": "", "UncheckedState": "", "TextDisplayMethod": 0}
        )
    if kind == "integer":
        config: dict[str, Any] = {"Step": 1, "Style": "SpinBox", "AllowNull": True}
        if entry.get("minimum") is not None:
            config["Min"] = math.ceil(entry["minimum"])
        if entry.get("maximum") is not None:
            config["Max"] = math.floor(entry["maximum"])
        return Widget("Range", config)
    if kind == "datetime":
        return Widget(
            "DateTime",
            {
                "calendar_popup": True,
                "display_format": "yyyy-MM-dd HH:mm:ss",
                "field_format": "yyyy-MM-dd HH:mm:ss",
                "field_iso_format": False,
                "allow_null": True,
            },
        )
    # Real numbers stay in a text box: the spin box of QGIS rounds to the field
    # precision, which is 0 for GeoPackage columns.
    multiline = kind == "text" and entry["name"] in MULTILINE_FIELDS
    return Widget("TextEdit", {"IsMultiline": multiline, "UseHtml": False})


def field_plan(entry: dict[str, Any], lang: str, unique: bool = False) -> FieldPlan:
    default = entry.get("default")
    return FieldPlan(
        name=entry["name"],
        alias=alias(entry, lang),
        help=localized(entry.get("help"), lang),
        widget=widget(entry, lang),
        read_only=bool(entry.get("system")),
        required=bool(entry.get("required")),
        unique=unique,
        minimum=entry.get("minimum"),
        maximum=entry.get("maximum"),
        default=None if default is None else literal(default),
    )


@dataclass(frozen=True)
class FormPlan:
    table: str
    label: str
    help: str
    fields: tuple[FieldPlan, ...]
    """In form order: editable fields as in the schema, multi-line texts, system fields."""


def form_plan(table: dict[str, Any], lang: str) -> FormPlan:
    unique = {u[0] for u in table.get("unique") or [] if len(u) == 1}
    plans = [field_plan(f, lang, f["name"] in unique) for f in table["fields"]]
    order = {p.name: i for i, p in enumerate(plans)}
    plans.sort(
        key=lambda p: (p.read_only, p.widget.config.get("IsMultiline", False), order[p.name])
    )
    return FormPlan(
        table=table["name"],
        label=localized(table.get("label"), lang) or table["name"],
        help=localized(table.get("help"), lang),
        fields=tuple(plans),
    )


def form_plans(schema: dict[str, Any], lang: str) -> dict[str, FormPlan]:
    return {t["name"]: form_plan(t, lang) for t in schema["project"]["tables"]}


def display_expression(table: dict[str, Any], relations: list[dict[str, Any]]) -> str | None:
    """How a feature is named in lists, relation editors and form titles.

    A single-field key (``series_id``), else the name, else the fields of the
    composite key that the parent form does not already show, with the value.
    """
    names = [f["name"] for f in table["fields"]]
    unique = [list(u) for u in table.get("unique") or []]
    single = [u[0] for u in unique if len(u) == 1]
    if single:
        return quote_field(single[0])
    if "name" in names:
        return 'coalesce("name", to_string("fid"))'
    if not unique:
        return None
    known = set()
    for r in relations:
        if r["child"] == table["name"]:
            known.add(r["child_field"])
            known.update(r.get("child_filter") or {})
            if r.get("parent_table_field"):
                known.add(r["parent_table_field"])
    shown = [n for n in unique[0] if n not in known] or unique[0][:1]
    parts = [quote_field(n) for n in shown]
    expression = parts[0] if len(parts) == 1 else "concat(" + ", ' ', ".join(parts) + ")"
    if "value" in names:
        expression = f"concat({expression}, ' = ', {quote_field('value')})"
    return expression


# --- relations ------------------------------------------------------------------------


@dataclass(frozen=True)
class RelationPlan:
    id: str
    name: str
    label: str
    child: str
    child_field: str
    parent_field: str
    parents: tuple[str, ...]
    polymorphic: bool
    """True when the child stores the parent in ``layer_field``: several parent
    layers, or a single one with a fixed value of ``layer_field``."""
    layer_field: str | None = None
    layer_expression: str | None = None
    """Evaluated on each parent layer: the value of ``layer_field`` for its children."""


def project_key(root: str) -> str:
    """A short key of the project folder, so relations of two projects never clash."""
    normal = os.path.normcase(str(Path(root).resolve()))
    return hashlib.sha256(normal.encode("utf-8")).hexdigest()[:8]


def relation_plans(schema: dict[str, Any], lang: str, root: str) -> list[RelationPlan]:
    """Relations of the schema as QGIS relations.

    A relation with a child filter (``object_type = 'unit'``) becomes a polymorphic
    relation with one parent: QGIS then shows only the matching children and sets
    the filter field on the children added from the parent form.
    """
    key = project_key(root)
    plans = []
    for r in schema["project"].get("relations", []):
        parents = tuple(r["parents"]) if r.get("parents") else (r["parent"],)
        child_filter = r.get("child_filter") or {}
        common = {
            "id": f"phrear_{key}_{r['name']}",
            "name": localized(r.get("label"), lang) or r["name"],
            "label": localized(r.get("label"), lang) or r["name"],
            "child": r["child"],
            "child_field": r["child_field"],
            "parent_field": r["parent_field"],
            "parents": parents,
        }
        if r.get("parent_table_field"):
            plans.append(
                RelationPlan(
                    **common,
                    polymorphic=True,
                    layer_field=r["parent_table_field"],
                    layer_expression=f"@{TABLE_VARIABLE}",
                )
            )
        elif len(child_filter) == 1:
            (layer_field, value), *_ = child_filter.items()
            plans.append(
                RelationPlan(
                    **common,
                    polymorphic=True,
                    layer_field=layer_field,
                    layer_expression=literal(value),
                )
            )
        elif child_filter:
            raise ValueError(f"relation {r['name']}: only one child filter field is supported")
        else:
            plans.append(RelationPlan(**common, polymorphic=False))
    return plans


# --- styles ---------------------------------------------------------------------------


def rgba(color: str, opacity: float = 1.0) -> str:
    """``#rrggbb`` as the ``r,g,b,a`` string of QGIS symbol properties."""
    text = color.lstrip("#")
    if len(text) != 6:
        raise ValueError(f"not a #rrggbb colour: {color!r}")
    r, g, b = (int(text[i : i + 2], 16) for i in (0, 2, 4))
    alpha = round(max(0.0, min(1.0, opacity)) * 255)
    return f"{r},{g},{b},{alpha}"


def symbol_properties(style: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """(symbol kind, properties of ``createSimple``) for a schema layer style."""
    kind = style["kind"]
    color = style["color"]
    outline = style.get("outline") or color
    if kind == "marker":
        return kind, {
            "name": style.get("shape") or "circle",
            "color": rgba(color),
            "outline_color": rgba(outline),
            "outline_width": "0.3",
            "outline_width_unit": "MM",
            "size": str(style.get("size_mm") or 2.5),
            "size_unit": "MM",
        }
    if kind == "line":
        return kind, {
            "line_color": rgba(color),
            "line_width": str(style.get("width_mm") or 0.5),
            "line_width_unit": "MM",
            "capstyle": "round",
            "joinstyle": "round",
        }
    if kind == "fill":
        opacity = style.get("fill_opacity")
        opacity = 1.0 if opacity is None else float(opacity)
        return kind, {
            "color": rgba(color, opacity),
            "style": "solid" if opacity > 0 else "no",
            "outline_color": rgba(outline),
            "outline_width": str(style.get("width_mm") or 0.3),
            "outline_width_unit": "MM",
        }
    raise ValueError(f"unknown symbol kind: {kind!r}")


def styles(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {t["name"]: t["style"] for t in schema["project"]["tables"] if t.get("style")}
