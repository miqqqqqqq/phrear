"""Check commands: check."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from phrear.checks.base import STAGES, Inspection
from phrear.checks.inspection import inspect_project
from phrear.checks.registry import CHECKS
from phrear.commands.base import CommandSpec, Context
from phrear.errors import CheckError, Lang, Localized, ObjectRef
from phrear.events import ErrorEvent, Problem, WarningEvent
from phrear.project import Project

_RUN = {"it": "eseguiti {run} su {total}", "en": "{run} of {total} run"}
_WORDS = {
    "it": {
        "error": ("errore", "errori"),
        "warning": ("avviso", "avvisi"),
        "skipped": "non eseguito, dipende da",
        "outcome": "Esito",
        "none": "nessun errore",
        "Error": "Errore",
        "Warning": "Avviso",
        "fid": "fid",
        "cell": "cella",
    },
    "en": {
        "error": ("error", "errors"),
        "warning": ("warning", "warnings"),
        "skipped": "not run, depends on",
        "outcome": "Outcome",
        "none": "no errors",
        "Error": "Error",
        "Warning": "Warning",
        "fid": "fid",
        "cell": "cell",
    },
}


def _count(n: int, kind: str, lang: Lang) -> str:
    one, many = _WORDS[lang][kind]
    return f"{n} {one if n == 1 else many}"


def _where(ref: ObjectRef | None, lang: Lang) -> str:
    if ref is None:
        return ""
    words = _WORDS[lang]
    parts = [p for p in (ref.layer, ref.path) if p]
    if ref.fid is not None:
        parts.append(f"{words['fid']} {ref.fid}")
    if ref.field:
        parts.append(ref.field)
    if ref.cell is not None:
        parts.append(f"{words['cell']} {tuple(i + 1 for i in ref.cell)}")
    return f" ({', '.join(parts)})" if parts else ""


def _finding(problem: Problem, kind: str, lang: Lang) -> list[str]:
    message = problem.message.it if lang == "it" else problem.message.en
    hint = problem.hint.it if lang == "it" else problem.hint.en
    lines = [f"{_WORDS[lang][kind]} [{problem.code}]{_where(problem.ref, lang)}: {message}"]
    if hint:
        lines.append(f"  {hint}")
    return lines


def _data(ins: Inspection) -> dict[str, Any]:
    return {
        "errors": len(ins.errors),
        "warnings": len(ins.warnings),
        "stages": [
            {
                "stage": s.stage,
                "status": s.status,
                "errors": len(s.errors),
                "warnings": len(s.warnings),
                "skipped_for": list(s.skipped_for),
            }
            for s in ins.stages
        ],
        "checks": [{"name": name, "status": status} for name, status in ins.checks.items()],
    }


def _text(ins: Inspection, lang: Lang) -> str:
    words = _WORDS[lang]
    width = max(len(label.get(lang)) for label in STAGES.values())
    lines: list[str] = []
    for s in ins.stages:
        if s.status == "skipped":
            depends = ", ".join(STAGES[d].get(lang).lower() for d in s.skipped_for)
            status = f"{words['skipped']} {depends}"
        else:
            notes = [_count(len(s.errors), "error", lang)] if s.errors else ["ok"]
            if s.warnings:
                notes.append(_count(len(s.warnings), "warning", lang))
            status = ", ".join(notes)
        if s.stage == "model":
            run = sum(1 for v in ins.checks.values() if v != "skipped")
            status += f" ({_RUN[lang].format(run=run, total=len(CHECKS))})"
        lines.append(f"{STAGES[s.stage].get(lang).ljust(width)}  {status}")
    for p in ins.errors:
        lines += _finding(p, "Error", lang)
    for p in ins.warnings:
        lines += _finding(p, "Warning", lang)
    errors = _count(len(ins.errors), "error", lang) if ins.errors else words["none"]
    lines.append(f"{words['outcome']}: {errors}, {_count(len(ins.warnings), 'warning', lang)}.")
    return "\n".join(lines)


def _configure_check(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, nargs="?", default=Path(), help="project folder")


def _check(args: argparse.Namespace, ctx: Context) -> int:
    ins = inspect_project(Project.open(args.path))
    if ctx.sink is not None:
        for p in ins.errors:
            ctx.sink.emit(ErrorEvent(problem=p))
        for p in ins.warnings:
            ctx.sink.emit(WarningEvent(problem=p))
    ctx.result("check", _data(ins), _text(ins, ctx.lang))
    if ins.errors:
        n = len(ins.errors)
        errors = Localized(
            "1 errore bloccante" if n == 1 else f"{n} errori bloccanti",
            "1 blocking error" if n == 1 else f"{n} blocking errors",
        )
        raise CheckError("check.failed", errors=errors)
    return 0


COMMANDS = [
    CommandSpec(
        "check", "check the whole project and list errors and warnings", _configure_check, _check
    )
]
