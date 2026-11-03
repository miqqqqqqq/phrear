"""Verification command: verify."""

from __future__ import annotations

import argparse
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from phrear.commands.base import CommandSpec, Context
from phrear.errors import Lang, Localized, VerificationError
from phrear.events import Progress, Text
from phrear.modflow.engine import engine_version, mf6_executable
from phrear.verification.cases import CASES
from phrear.verification.report import results_data, write_report
from phrear.verification.runner import CaseResult, run_case


def _configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--case", action="append", default=None, help=f"case to run ({', '.join(CASES)})"
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="report folder (default: a new folder here)"
    )
    parser.add_argument(
        "--keep", action="store_true", help="keep the case projects in <output>/cases"
    )


def _output(path: Path | None, now: datetime) -> Path:
    target = path if path is not None else Path(f"phrear_verify-{now:%Y%m%d-%H%M%S}")
    if target.exists() and any(target.iterdir()):
        raise VerificationError("verify.output_exists", path=str(target))
    return target.resolve()


def _text(data: dict[str, Any], lang: Lang, report: Path) -> str:
    rows = []
    for c in data["cases"]:
        measure = f"{100 * c['measure']:.3g} %" if c["relative"] else f"{c['measure']:.2g} m"
        tol = f"{100 * c['tolerance']:g} %" if c["relative"] else f"{c['tolerance']:g} m"
        if lang == "it":
            outcome = "superato" if c["passed"] else "NON superato"
        else:
            outcome = "passed" if c["passed"] else "FAILED"
        rows.append(f"{c['title'][lang]:<48} {measure:>10}  (≤ {tol})  {outcome}")
    rows.append(f"Report: {report}")
    return "\n".join(rows)


def _verify(args: argparse.Namespace, ctx: Context) -> int:
    names = args.case or list(CASES)
    for name in names:
        if name not in CASES:
            raise VerificationError("verify.unknown_case", case=name, cases=", ".join(CASES))
    now = datetime.now().astimezone()
    output = _output(args.output, now)
    engine = engine_version(mf6_executable())
    results: list[CaseResult] = []
    with tempfile.TemporaryDirectory(prefix="phrear-verify-") as scratch:
        root = output / "cases" if args.keep else Path(scratch)
        for i, name in enumerate(names):
            case = CASES[name]
            if ctx.sink is not None:
                message = Text(it=case.title.it, en=case.title.en)
                ctx.sink.emit(Progress(stage="verify", fraction=i / len(names), message=message))
            else:
                ctx.out.write(f"{case.title.get(ctx.lang)}…\n")
            results.append(run_case(case, root))
    report = write_report(results, output, ctx.lang, engine, now)
    data = {**results_data(results, engine, now), "report": str(report)}
    ctx.result("verify", data, _text(data, ctx.lang, report))
    failed = [r.case.title for r in results if not r.passed]
    if failed:
        raise VerificationError(
            "verify.failed",
            cases=Localized(", ".join(f.it for f in failed), ", ".join(f.en for f in failed)),
            report=str(report),
            engine=engine,
        )
    return 0


COMMANDS = [
    CommandSpec("verify", "run the verification against analytical solutions", _configure, _verify)
]
