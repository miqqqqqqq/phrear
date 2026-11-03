"""Parameter commands: params."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from phrear.commands.base import CommandSpec, Context
from phrear.errors import Lang
from phrear.params.values import PARAM_LABELS, ParameterSet, load_parameters
from phrear.project import Project
from phrear.project.schema import PARAM_QUANTITIES, TABLES_BY_NAME
from phrear.units import INTERNAL_UNITS_DISPLAY

_SOURCES = {c.value: c.label for c in TABLES_BY_NAME["param_values"].field("source").choices}
_HEADERS = {
    "it": ("Unità", "Parametro", "Valore", "Unità di misura", "Valore interno", "Origine"),
    "en": ("Unit", "Parameter", "Value", "Unit of measure", "Internal value", "Source"),
}


def _data(params: ParameterSet) -> dict[str, Any]:
    return {
        "units": [
            {
                "position": u.position,
                "name": u.name,
                "convertible": u.convertible,
                "kh_md": u.kh,
                "kv_md": u.kv,
                "ss_1m": u.ss,
                "sy": u.sy,
                "ne": u.ne,
                "values": [
                    {
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
                    for pv in u.values.values()
                ],
            }
            for u in params.units
        ]
    }


def _table(params: ParameterSet, lang: Lang) -> str:
    rows: list[tuple[str, ...]] = [_HEADERS[lang]]
    for u in params.units:
        for pv in u.values.values():
            source = _SOURCES[pv.source].get(lang) if pv.source in _SOURCES else "—"
            internal = INTERNAL_UNITS_DISPLAY[PARAM_QUANTITIES[pv.param]]
            rows.append(
                (
                    u.label,
                    PARAM_LABELS[pv.param].get(lang),
                    f"{pv.original_value:.4g}",
                    pv.original_unit or "-",
                    f"{pv.value:.4g} {internal}",
                    source,
                )
            )
        if "kv" not in u.values:
            label = "K verticale (da Kv/Kh)" if lang == "it" else "Vertical K (from Kv/Kh)"
            rows.append((u.label, label, "", "", f"{u.kv:.4g} m/d", ""))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return "\n".join(
        "  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)).rstrip() for r in rows
    )


def _configure_params(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, nargs="?", default=Path(), help="project folder")


def _params(args: argparse.Namespace, ctx: Context) -> int:
    params = load_parameters(Project.open(args.path))
    for problem in params.warnings:
        ctx.warn(problem)
    ctx.result("params", _data(params), _table(params, ctx.lang))
    return 0


COMMANDS = [
    CommandSpec(
        "params", "hydrogeological parameters per unit, converted", _configure_params, _params
    )
]
