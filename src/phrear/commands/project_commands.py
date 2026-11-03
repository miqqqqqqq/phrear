"""Project commands: new, info, schema, migrate."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from phrear.commands.base import CommandSpec, Context
from phrear.events import SCHEMA_VERSION as EVENT_SCHEMA_VERSION
from phrear.events import event_json_schema
from phrear.project import Project
from phrear.project.project import DEFAULT_EPSG
from phrear.project.schema import schema_document


def _date_arg(text: str) -> datetime:
    """Accept YYYY-MM-DD or an ISO 8601 date-time (local time)."""
    try:
        if len(text) == 10:
            d = date.fromisoformat(text)
            return datetime(d.year, d.month, d.day)
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date {text!r}, use YYYY-MM-DD") from exc


# --- new ------------------------------------------------------------------------


def _configure_new(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, help="folder of the new project")
    parser.add_argument("--name", help="project name (default: folder name)")
    parser.add_argument(
        "--crs", type=int, default=DEFAULT_EPSG, help=f"EPSG code (default {DEFAULT_EPSG})"
    )
    parser.add_argument("--start", type=_date_arg, required=True, help="model start, YYYY-MM-DD")
    parser.add_argument("--end", type=_date_arg, required=True, help="model end, YYYY-MM-DD")


def _new(args: argparse.Namespace, ctx: Context) -> int:
    path: Path = args.path
    project = Project.create(
        path, name=args.name or path.resolve().name, start=args.start, end=args.end, epsg=args.crs
    )
    data = {"path": str(project.root), "name": project.config.name, "crs": project.config.crs}
    text = (
        f"Progetto «{project.config.name}» creato in {project.root}"
        if ctx.lang == "it"
        else f"Project '{project.config.name}' created in {project.root}"
    )
    ctx.result("new", data, text)
    return 0


# --- info -----------------------------------------------------------------------


def _configure_info(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, nargs="?", default=Path(), help="project folder")


_INFO_LABELS = {
    "it": {
        "name": "Progetto",
        "path": "Cartella",
        "schema": "Schema",
        "crs": "Sistema di riferimento",
        "period": "Periodo",
        "steady": "Primo periodo stazionario",
        "tables": "Contenuto",
        "hash": "Hash del contenuto",
        "yes": "sì",
        "no": "no",
    },
    "en": {
        "name": "Project",
        "path": "Folder",
        "schema": "Schema",
        "crs": "Coordinate reference system",
        "period": "Period",
        "steady": "Initial steady-state period",
        "tables": "Content",
        "hash": "Content hash",
        "yes": "yes",
        "no": "no",
    },
}


def _info_text(data: dict[str, Any], lang: str) -> str:
    lab = _INFO_LABELS[lang]
    model = data["model"]
    lines = [
        f"{lab['name']}: {data['name']}",
        f"{lab['path']}: {data['path']}",
        f"{lab['schema']}: {data['schema_version']}",
        f"{lab['crs']}: EPSG:{data['crs']['epsg']} ({data['crs']['name']})",
        f"{lab['period']}: {model['start_date']} → {model['end_date']}",
        f"{lab['steady']}: {lab['yes'] if model['steady_initial'] else lab['no']}",
        f"{lab['tables']}:",
        *(f"  {name}: {count}" for name, count in data["tables"].items()),
        f"{lab['hash']}: {data['content_hash']}",
    ]
    return "\n".join(lines)


def _info(args: argparse.Namespace, ctx: Context) -> int:
    data = Project.open(args.path).summary()
    ctx.result("info", data, _info_text(data, ctx.lang))
    return 0


# --- schema ---------------------------------------------------------------------


def _configure_schema(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", type=Path, help="write the document to this file")


def full_schema_document() -> dict[str, Any]:
    """Data schema and event protocol, for clients that cannot import the core."""
    return {
        "project": schema_document(),
        "events": {"schema_version": EVENT_SCHEMA_VERSION, "json_schema": event_json_schema()},
    }


def _schema(args: argparse.Namespace, ctx: Context) -> int:
    document = full_schema_document()
    text = json.dumps(document, ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.write_text(text + "\n", encoding="utf-8")
        summary = {"output": str(args.output)}
        ctx.result("schema", summary, str(args.output))
    else:
        ctx.result("schema", document, text)
    return 0


# --- migrate --------------------------------------------------------------------


def _configure_migrate(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", type=Path, nargs="?", default=Path(), help="project folder")


def _migrate(args: argparse.Namespace, ctx: Context) -> int:
    report = Project.migrate(args.path)
    data = {
        "from_version": report.from_version,
        "to_version": report.to_version,
        "backup": str(report.backup) if report.backup else None,
        "steps": list(report.steps),
    }
    if not report.steps:
        text = (
            f"Il progetto è già allo schema {report.to_version}."
            if ctx.lang == "it"
            else f"The project is already at schema {report.to_version}."
        )
    else:
        text = f"Schema {report.from_version} → {report.to_version}; backup: {report.backup}"
    ctx.result("migrate", data, text)
    return 0


def _specs() -> list[CommandSpec]:
    return [
        CommandSpec("new", "create a new project", _configure_new, _new),
        CommandSpec("info", "summary of a project", _configure_info, _info),
        CommandSpec("schema", "data schema and event protocol as JSON", _configure_schema, _schema),
        CommandSpec(
            "migrate", "upgrade a project to the current schema", _configure_migrate, _migrate
        ),
    ]


COMMANDS = _specs()
