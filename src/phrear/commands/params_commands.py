"""Parameter commands: params."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from phrear.commands.base import CommandSpec, Context
from phrear.errors import Lang
from phrear.grid.model_grid import build_model_grid
from phrear.params.cells import assign_cells
from phrear.params.export import export_parameters
from phrear.params.values import PARAM_LABELS, ParameterSet, ParamValue, load_parameters
from phrear.project import Project
from phrear.project.project import EXPORTS_DIR
from phrear.project.schema import PARAM_QUANTITIES, TABLES_BY_NAME
from phrear.units import INTERNAL_UNITS_DISPLAY

PARAMS_EXPORT = "params.gpkg"

_SOURCES = {c.value: c.label for c in TABLES_BY_NAME["param_values"].field("source").choices}
_HEADERS = {
    "it": ("Unità", "Parametro", "Valore", "Unità di misura", "Valore interno", "Origine"),
    "en": ("Unit", "Parameter", "Value", "Unit of measure", "Internal value", "Source"),
}


def _value(pv: ParamValue) -> dict[str, Any]:
    return {
        "param": pv.param,
        "value": pv.original_value,
        "unit": pv.original_unit,
        "internal_value": pv.value,
        "internal_unit": INTERNAL_UNITS_DISPLAY[PARAM_QUANTITIES[pv.param]],
        "source": pv.source,
        "min": pv.minimum,
        "max": pv.maximum,
        "fid": pv.fid,
    }


def _data(params: ParameterSet) -> dict[str, Any]:
    return {
        "units": [
            {
                "position": u.position,
                "name": u.name,
                "convertible": u.convertible,
                "vertical": u.vertical,
                "kh_md": u.uniform("kh"),
                "kv_md": u.kv if "kh" in u.values and u.vertical in u.values else None,
                "ss_1m": u.uniform("ss"),
                "sy": u.sy,
                "ne": u.ne,
                "values": [_value(pv) for pv in u.values.values()],
                "zones": [
                    {
                        "fid": z.fid,
                        "name": z.name,
                        "values": [_value(pv) for pv in z.values.values()],
                    }
                    for z in u.zones
                ],
            }
            for u in params.units
        ]
    }


def _table(params: ParameterSet, lang: Lang) -> str:
    rows: list[tuple[str, ...]] = [_HEADERS[lang]]
    zone_word = "zona" if lang == "it" else "zone"

    def add(owner: str, pv: ParamValue) -> None:
        source = _SOURCES[pv.source].get(lang) if pv.source in _SOURCES else "—"
        internal = INTERNAL_UNITS_DISPLAY[PARAM_QUANTITIES[pv.param]]
        rows.append(
            (
                owner,
                PARAM_LABELS[pv.param].get(lang),
                f"{pv.original_value:.4g}",
                pv.original_unit or "-",
                f"{pv.value:.4g} {internal}",
                source,
            )
        )

    for u in params.units:
        for pv in u.values.values():
            add(u.label, pv)
        if "kv" not in u.values and {"kh", "anisotropy"} <= u.values.keys():
            label = "K verticale (da Kv/Kh)" if lang == "it" else "Vertical K (from Kv/Kh)"
            rows.append((u.label, label, "", "", f"{u.kv:.4g} m/d", ""))
        for z in u.zones:
            for pv in z.values.values():
                add(f"{u.label} · {zone_word} {z.label}", pv)
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return "\n".join(
        "  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in rows
    )


def _configure_params(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, nargs="?", default=Path(), help="project folder")
    parser.add_argument(
        "--export",
        action="store_true",
        help=f"write the parameters of every cell, with their origin, to {EXPORTS_DIR}/"
        f"{PARAMS_EXPORT}",
    )


def _params(args: argparse.Namespace, ctx: Context) -> int:
    project = Project.open(args.path)
    params = load_parameters(project)
    for problem in params.warnings:
        ctx.warn(problem)
    data = _data(params)
    text = _table(params, ctx.lang)
    if args.export:
        grid = build_model_grid(project)
        cells = assign_cells(grid, params)
        target = project.root / EXPORTS_DIR / PARAMS_EXPORT
        data["export_features"] = export_parameters(grid, cells, target, project.config.crs)
        data["export"] = str(target)
        text += f"\nExport: {target}"
    ctx.result("params", data, text)
    return 0


COMMANDS = [
    CommandSpec(
        "params", "hydrogeological parameters per unit, converted", _configure_params, _params
    )
]
