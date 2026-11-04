"""Check and run as seen by the plugin: arguments, problems, stages, log entries.

The core reports every problem with a code, texts in Italian and English and,
when it can, a reference to the layer, feature and field (``ObjectRef``). This
module turns events and results into rows for the Phrear panel; the Qt side only
draws them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

#: Summary failure of ``check`` and of ``build``/``run`` stopped by the check:
#: the errors themselves are already listed.
SUMMARY_FAILURES = frozenset({"check.failed"})


def _text(entry: dict[str, Any] | None, lang: str) -> str:
    entry = entry or {}
    return str(entry.get(lang) or entry.get("en") or "")


def check_args(root: Path) -> list[str]:
    return ["check", str(root)]


def run_args(root: Path, run_id: str = "") -> list[str]:
    """``run`` with the run name, if given; the core names it by date and time otherwise."""
    args = ["run", str(root)]
    if run_id.strip():
        args += ["--run-id", run_id.strip()]
    return args


# --- problems -------------------------------------------------------------------------


@dataclass(frozen=True)
class ProblemRow:
    severity: str
    """``error`` or ``warning``."""
    code: str
    message: str
    hint: str
    detail: str = ""
    kind: str | None = None
    table: str | None = None
    table_label: str = ""
    fid: int | None = None
    field: str | None = None
    field_label: str = ""
    cell: tuple[int, ...] | None = None
    """1-based (layer, row, column) as shown to the user."""
    path: str | None = None

    @property
    def locatable(self) -> bool:
        """True when the panel can show the object: a feature or a row of a table."""
        return self.table is not None and self.fid is not None


class Labels:
    """Table and field labels of the schema document."""

    def __init__(self, schema: dict[str, Any] | None, lang: str) -> None:
        self.tables: dict[str, str] = {}
        self.fields: dict[tuple[str, str], str] = {}
        for table in (schema or {}).get("project", {}).get("tables", []):
            self.tables[table["name"]] = _text(table.get("label"), lang) or table["name"]
            for f in table.get("fields", []):
                self.fields[(table["name"], f["name"])] = _text(f.get("label"), lang) or f["name"]

    def table(self, name: str | None) -> str:
        return self.tables.get(name or "", name or "")

    def field(self, table: str | None, name: str | None) -> str:
        if name is None:
            return ""
        return self.fields.get((table or "", name), name)


def problem_row(
    problem: dict[str, Any], severity: str, lang: str, labels: Labels | None = None
) -> ProblemRow:
    labels = labels or Labels(None, lang)
    ref = problem.get("ref") or {}
    table = ref.get("layer")
    field = ref.get("field")
    cell = ref.get("cell")
    return ProblemRow(
        severity=severity,
        code=str(problem.get("code", "")),
        message=_text(problem.get("message"), lang),
        hint=_text(problem.get("hint"), lang),
        detail=str(problem.get("detail") or ""),
        kind=ref.get("kind"),
        table=table,
        table_label=labels.table(table) if table else "",
        fid=ref.get("fid"),
        field=field,
        field_label=labels.field(table, field),
        cell=tuple(int(i) + 1 for i in cell) if cell is not None else None,
        path=ref.get("path"),
    )


def problem_rows(
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    failure: dict[str, Any] | None,
    lang: str,
    schema: dict[str, Any] | None = None,
) -> list[ProblemRow]:
    """Errors, then warnings, then the failure of the command when it adds something."""
    labels = Labels(schema, lang)
    rows = [problem_row(p, "error", lang, labels) for p in errors]
    rows += [problem_row(p, "warning", lang, labels) for p in warnings]
    if failure and failure.get("code") not in SUMMARY_FAILURES:
        rows.append(problem_row(failure, "error", lang, labels))
    return rows


def counts(rows: list[ProblemRow]) -> tuple[int, int]:
    errors = sum(1 for r in rows if r.severity == "error")
    return errors, len(rows) - errors


# --- stages of the check --------------------------------------------------------------


@dataclass(frozen=True)
class StageRow:
    label: str
    status: str
    """``ok``, ``errors`` or ``skipped``."""
    errors: int
    warnings: int
    skipped_for: tuple[str, ...]
    """Labels of the stages whose errors prevented this one."""


def stage_rows(result: dict[str, Any] | None, lang: str) -> list[StageRow]:
    stages = (result or {}).get("stages", [])
    labels = {s["stage"]: _text(s.get("label"), lang) or s["stage"] for s in stages}
    return [
        StageRow(
            label=labels[s["stage"]],
            status=str(s.get("status", "")),
            errors=int(s.get("errors", 0)),
            warnings=int(s.get("warnings", 0)),
            skipped_for=tuple(labels.get(d, d) for d in s.get("skipped_for", [])),
        )
        for s in stages
    ]


# --- progress and log -----------------------------------------------------------------


def progress(event: dict[str, Any], lang: str) -> tuple[float | None, str] | None:
    """(fraction, message) of a ``progress`` event, None for other events."""
    if event.get("event") != "progress":
        return None
    fraction = event.get("fraction")
    value = float(fraction) if isinstance(fraction, int | float) else None
    return value, _text(event.get("message"), lang)


def local_time(stamp: str | None) -> str:
    """``HH:MM:SS`` in the local time of the computer, from the UTC time of an event."""
    if not stamp:
        return ""
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return moment.astimezone().strftime("%H:%M:%S")


@dataclass(frozen=True)
class LogEntry:
    time: str
    key: str
    """What happened; the Qt side has a translated template for every key."""
    values: dict[str, str]
    level: str = "info"
    """``info``, ``warning`` or ``error``."""


def _seconds(value: Any) -> str:
    return f"{float(value):.1f}" if isinstance(value, int | float) else "?"


def log_entry(event: dict[str, Any], lang: str) -> LogEntry | None:
    """The log line of an event; None for events shown elsewhere (progress, result)."""
    kind = event.get("event")
    time = local_time(event.get("time"))
    command = str(event.get("command", ""))
    if kind == "command_started":
        return LogEntry(time, kind, {"command": command})
    if kind == "command_completed":
        return LogEntry(
            time, kind, {"command": command, "seconds": _seconds(event.get("duration_s"))}
        )
    if kind in ("command_failed", "run_failed"):
        error = event.get("error") or {}
        values = {"command": command, "run_id": str(event.get("run_id", ""))}
        values["message"] = _text(error.get("message"), lang)
        return LogEntry(time, kind, values, "error")
    if kind == "run_started":
        values = {
            "run_id": str(event.get("run_id", "")),
            "engine": str(event.get("engine_version", "")),
        }
        return LogEntry(time, kind, values)
    if kind == "run_completed":
        values = {
            "run_id": str(event.get("run_id", "")),
            "seconds": _seconds(event.get("duration_s")),
        }
        return LogEntry(time, kind, values)
    if kind in ("warning", "error"):
        problem = event.get("problem") or {}
        values = {
            "code": str(problem.get("code", "")),
            "message": _text(problem.get("message"), lang),
        }
        return LogEntry(time, kind, values, kind)
    return None


# --- results of a run -----------------------------------------------------------------


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    folder: str
    heads: str
    seconds: float
    steps: int
    worst_budget_pct: float | None
    worst_period: int | None
    worst_step: int | None


def run_summary(result: dict[str, Any] | None) -> RunSummary | None:
    if not result or "run_id" not in result:
        return None
    worst = result.get("max_budget_discrepancy") or {}
    return RunSummary(
        run_id=str(result["run_id"]),
        folder=str(result.get("folder", "")),
        heads=str(result.get("heads", "")),
        seconds=float(result.get("duration_s", 0.0)),
        steps=int(result.get("steps", 0)),
        worst_budget_pct=worst.get("pct"),
        worst_period=worst.get("period"),
        worst_step=worst.get("step"),
    )
