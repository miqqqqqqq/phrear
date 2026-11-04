"""Results as seen by the plugin: runs of a project, heads layers, grid and cell exports.

The list of runs comes from ``phrear runs``; states, labels and products are
those of the core. This module turns them into rows and plans the layers; the Qt
side loads them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .forms import rgba


def _text(entry: dict[str, Any] | None, lang: str) -> str:
    entry = entry or {}
    return str(entry.get(lang) or entry.get("en") or "")


def runs_args(root: Path) -> list[str]:
    return ["runs", str(root)]


@dataclass(frozen=True)
class RunRow:
    run_id: str
    folder: str
    status: str
    status_label: str
    created: str
    """``YYYY-MM-DD HH:MM``, local time of the run."""
    duration_s: float | None
    same_project: bool | None
    heads: str | None
    budget_pct: float | None
    error: str

    @property
    def can_load(self) -> bool:
        return self.status == "completed" and self.heads is not None


def mesh_uri(path: str | Path) -> str:
    """Source of a heads file for the MDAL provider, with its driver named.

    Without the driver MDAL tries its other formats first, and the HDF5 ones fill
    the output of QGIS with diagnostics while probing the file.
    """
    return 'Ugrid:"' + str(path).replace("\\", "/") + '"'


def default_heads(data: dict[str, Any] | None) -> str:
    """Name of the dataset to show first in the heads of a run, from ``runs`` or ``run``."""
    data = data or {}
    return str(data.get("heads_default") or (data.get("default_datasets") or {}).get("heads", ""))


def run_rows(data: dict[str, Any] | None, lang: str) -> list[RunRow]:
    rows = []
    for run in (data or {}).get("runs", []):
        worst = run.get("max_budget_discrepancy") or {}
        error = run.get("error") or {}
        rows.append(
            RunRow(
                run_id=str(run["run_id"]),
                folder=str(run.get("folder", "")),
                status=str(run.get("status", "")),
                status_label=_text(run.get("status_label"), lang) or str(run.get("status", "")),
                created=str(run.get("created") or "")[:16].replace("T", " "),
                duration_s=run.get("duration_s"),
                same_project=run.get("same_project"),
                heads=(run.get("products") or {}).get("heads"),
                budget_pct=worst.get("pct"),
                error=str(error.get("message") or ""),
            )
        )
    return rows


def heads_group(names: list[str], temporal: list[bool], preferred: str) -> int:
    """Index of the dataset group to show first in a heads layer.

    ``preferred`` is the name the core gives to the head of the uppermost saturated
    cell (``heads_default`` of ``run``, ``default_datasets`` of ``runs``); without
    it, the first group that changes in time.
    """
    if preferred and preferred in names:
        return names.index(preferred)
    return next((i for i, t in enumerate(temporal) if t), 0)


# --- exports of the current project ---------------------------------------------------

EXPORTS = {
    "grid": ["grid"],
    "bc": ["bc"],
}


def export_args(kind: str, root: Path) -> list[str]:
    """``grid --export`` or ``bc --export``: cells written to ``exports/`` and loaded."""
    return [*EXPORTS[kind], str(root), "--export"]


@dataclass(frozen=True)
class Category:
    value: str
    label: str
    fill: str
    """``r,g,b,a`` as in the symbol properties of QGIS."""
    outline: str


def cell_categories(
    schema: dict[str, Any], lang: str, values: list[str], opacity: float = 0.45
) -> list[Category]:
    """One category per source layer found among the boundary cells.

    The cells exported by ``bc --export`` name the layer of the feature they come
    from (``feature_layer``) and take the colour of that layer in the schema.
    """
    tables = {t["name"]: t for t in schema["project"]["tables"]}
    categories = []
    for value in sorted(set(values), key=lambda v: list(tables).index(v) if v in tables else 99):
        table = tables.get(value) or {}
        color = (table.get("style") or {}).get("color") or "#808080"
        categories.append(
            Category(
                value=value,
                label=_text(table.get("label"), lang) or value,
                fill=rgba(color, opacity),
                outline=rgba(color),
            )
        )
    return categories
