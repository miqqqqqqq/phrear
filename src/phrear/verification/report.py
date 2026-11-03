"""Report of a verification: table, plots of numerical against analytical, JSON.

Plots follow the documentation style: analytical solution as a line, MF6 results
as points, recessive grid, one axis, legend always present. Colours are the first
slots of the validated categorical palette, which stay distinguishable for the
common colour-vision deficiencies; identity is also carried by the legend and by
line against marker.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

import phrear
from phrear.errors import Lang
from phrear.verification.runner import CaseResult

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3de"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a")
MAX_POINTS = 1500
_WORDS: dict[Lang, dict[str, str]] = {
    "it": {
        "analytical": "soluzione analitica",
        "simulated": "MF6 (centri cella)",
        "distance_well": "distanza dal pozzo r [m]",
        "distance_line": "distanza dalla prima linea a carico imposto [m]",
        "time": "tempo dall'avvio del pompaggio [d]",
        "unit": "m",
        "title": "Verifica di Phrear",
        "case": "Caso",
        "error": "Errore massimo [m]",
        "reference": "Riferimento [m]",
        "measure": "Misura",
        "tolerance": "Tolleranza",
        "outcome": "Esito",
        "passed": "superato",
        "failed": "non superato",
        "points": "punti di confronto",
        "parameters": "Parametri",
        "relative": "errore massimo / s_max",
        "absolute": "errore massimo in m",
        "intro": "Ogni caso è un progetto Phrear completo, costruito, controllato ed eseguito "
        "con MODFLOW 6 come un progetto dell'utente. I risultati ai centri cella sono "
        "confrontati con la soluzione analitica.",
    },
    "en": {
        "analytical": "analytical solution",
        "simulated": "MF6 (cell centres)",
        "distance_well": "distance from the well r [m]",
        "distance_line": "distance from the first fixed-head line [m]",
        "time": "time since pumping started [d]",
        "unit": "m",
        "title": "Phrear verification",
        "case": "Case",
        "error": "Largest error [m]",
        "reference": "Reference [m]",
        "measure": "Measure",
        "tolerance": "Tolerance",
        "outcome": "Outcome",
        "passed": "passed",
        "failed": "failed",
        "points": "comparison points",
        "parameters": "Parameters",
        "relative": "largest error / s_max",
        "absolute": "largest error in m",
        "intro": "Each case is a complete Phrear project, built, checked and run with "
        "MODFLOW 6 like a user project. The results at the cell centres are compared "
        "with the analytical solution.",
    },
}


def _style(ax: Any) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.xaxis.label.set_color(INK)
    ax.yaxis.label.set_color(INK)


def _sample(n: int) -> np.ndarray:
    if n <= MAX_POINTS:
        return np.arange(n)
    return np.unique(np.linspace(0, n - 1, MAX_POINTS).astype(int))


def plot_case(result: CaseResult, path: Path, lang: Lang) -> Path:
    words = _WORDS[lang]
    c = result.comparison
    quantity = c.quantity.get(lang)
    fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    if c.time is None:
        order = np.argsort(c.distance)
        ax.plot(c.distance[order], c.expected[order], color=MUTED, linewidth=2,
                label=words["analytical"], zorder=2)  # fmt: skip
        keep = order[_sample(order.size)]
        ax.scatter(c.distance[keep], c.simulated[keep], s=10, color=SERIES[0],
                   edgecolors="none", label=words["simulated"], zorder=3)  # fmt: skip
        well = result.case.relative
        ax.set_xlabel(words["distance_well"] if well else words["distance_line"])
        if well:
            ax.set_xscale("log")
        ax.legend(frameon=False, fontsize=8, labelcolor=INK)
    else:
        radii = np.unique(np.round(c.distance, 6))
        targets = (radii.min(), 250.0, 800.0)
        chosen = [float(radii[np.argmin(np.abs(radii - t))]) for t in targets]
        handles = []
        for colour, r in zip(SERIES, chosen, strict=True):
            mask = np.isclose(c.distance, r)
            order = np.argsort(c.time[mask])
            t, sim, exp = c.time[mask][order], c.simulated[mask][order], c.expected[mask][order]
            ax.plot(t, exp, color=colour, linewidth=2, zorder=2)
            ax.scatter(t, sim, s=12, color=colour, edgecolors="none", zorder=3)
            handles.append(Line2D([], [], color=colour, linewidth=2, label=f"r = {r:.0f} m"))
        handles += [
            Line2D([], [], color=MUTED, linewidth=2, label=words["analytical"]),
            Line2D(
                [],
                [],
                color=MUTED,
                marker="o",
                markersize=4,
                linestyle="none",
                label=words["simulated"],
            ),
        ]
        ax.set_xscale("log")
        ax.set_xlabel(words["time"])
        ax.legend(handles=handles, frameon=False, fontsize=8, labelcolor=INK)
    ax.set_ylabel(f"{quantity} [{words['unit']}]")
    ax.set_title(result.case.title.get(lang), fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def _fmt(value: float) -> str:
    return f"{value:.3g}"


def results_data(results: list[CaseResult], engine: str, created: datetime) -> dict[str, Any]:
    return {
        "created": created.isoformat(timespec="seconds"),
        "software": {"name": "phrear", "version": phrear.__version__},
        "engine": {"name": "MODFLOW 6", "version": engine},
        "cases": [
            {
                "name": r.case.name,
                "title": {"it": r.case.title.it, "en": r.case.title.en},
                "relative": r.case.relative,
                "tolerance": r.case.tolerance,
                "max_error_m": r.max_error,
                "reference_m": r.reference,
                "measure": r.measure,
                "passed": r.passed,
                "points": r.points,
                "duration_s": round(r.duration_s, 2),
                "parameters": r.case.parameters,
            }
            for r in results
        ],
    }


def _measure(r: CaseResult) -> str:
    return f"{100 * r.measure:.3g} %" if r.case.relative else f"{r.measure:.2g} m"


def _tolerance(r: CaseResult) -> str:
    return f"{100 * r.case.tolerance:g} %" if r.case.relative else f"{r.case.tolerance:g} m"


def write_report(
    results: list[CaseResult], folder: Path, lang: Lang, engine: str, created: datetime
) -> Path:
    """report.md, one PNG per case and results.json in ``folder``."""
    words = _WORDS[lang]
    folder.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {words['title']}",
        "",
        f"phrear {phrear.__version__}, MODFLOW 6 {engine}, {created:%Y-%m-%d %H:%M}.",
        "",
        words["intro"],
        "",
        f"| {words['case']} | {words['error']} | {words['reference']} | {words['measure']} "
        f"| {words['tolerance']} | {words['outcome']} |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        outcome = words["passed"] if r.passed else words["failed"]
        lines.append(
            f"| {r.case.title.get(lang)} | {_fmt(r.max_error)} | {_fmt(r.reference)} "
            f"| {_measure(r)} | {_tolerance(r)} | {outcome} |"
        )
    for r in results:
        image = plot_case(r, folder / f"{r.case.name}.png", lang)
        kind = words["relative"] if r.case.relative else words["absolute"]
        parameters = ", ".join(f"{k} {v}" for k, v in r.case.parameters.items())
        lines += [
            "",
            f"## {r.case.title.get(lang)}",
            "",
            r.case.description.get(lang),
            "",
            f"{words['parameters']}: {parameters}. {r.points} {words['points']}; "
            f"{kind} {_measure(r)}, {words['tolerance'].lower()} {_tolerance(r)}.",
            "",
            f"![{r.case.title.get(lang)}]({image.name})",
        ]
    (folder / "results.json").write_text(
        json.dumps(results_data(results, engine, created), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report = folder / "report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
