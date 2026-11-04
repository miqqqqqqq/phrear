"""Finding and listing the runs of a project."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from phrear.errors import Localized, ResultsError
from phrear.modflow.manifest import MANIFEST, read_manifest
from phrear.project import Project, hashing
from phrear.project.project import RUNS_DIR
from phrear.results.exporters import EXPORTERS

#: States of a run in its manifest, plus ``incomplete`` for a folder without one
#: (a build interrupted before the manifest was written).
STATUS_LABELS: Final[dict[str, Localized]] = {
    "built": Localized("costruito, non eseguito", "built, not run"),
    "running": Localized("in corso o interrotto", "running or interrupted"),
    "completed": Localized("completato", "completed"),
    "failed": Localized("non riuscito", "failed"),
    "incomplete": Localized("incompleto", "incomplete"),
}


def completed_run(project: Project, run_id: str | None) -> tuple[str, Path, dict[str, Any]]:
    """The named run, or the latest completed one; it must be completed."""
    runs = project.root / RUNS_DIR
    if run_id is not None:
        folder = runs / run_id
        if not (folder / MANIFEST).is_file():
            raise ResultsError("results.run_not_found", run_id=run_id, path=str(runs))
        manifest = read_manifest(folder)
        status = manifest.get("run", {}).get("status", "unknown")
        if status != "completed":
            raise ResultsError("results.not_completed", run_id=run_id, status=status)
        return run_id, folder, manifest
    found: list[tuple[str, str, Path, dict[str, Any]]] = []
    for manifest_path in runs.glob(f"*/{MANIFEST}"):
        manifest = read_manifest(manifest_path.parent)
        run = manifest.get("run", {})
        if run.get("status") == "completed":
            found.append((run.get("started", ""), manifest_path.parent.name, manifest_path.parent,
                          manifest))  # fmt: skip
    if not found:
        raise ResultsError("results.no_run")
    _, name, folder, manifest = max(found, key=lambda f: (f[0], f[1]))
    return name, folder, manifest


def _run_entry(folder: Path, project_hash: str, products: dict[str, str]) -> dict[str, Any]:
    entry: dict[str, Any] = {"run_id": folder.name, "folder": str(folder)}
    try:
        manifest = read_manifest(folder)
    except (FileNotFoundError, json.JSONDecodeError):
        manifest = {}
    if not manifest:
        created = datetime.fromtimestamp(folder.stat().st_mtime).astimezone()
        status = "incomplete"
        entry |= {"created": created.isoformat(timespec="seconds"), "status": status}
    else:
        run = manifest.get("run", {})
        status = str(run.get("status", "built"))
        status = status if status in STATUS_LABELS else "incomplete"
        run_hash = manifest.get("project", {}).get("content_hash")
        entry |= {
            "created": manifest.get("created"),
            "status": status,
            "started": run.get("started"),
            "duration_s": run.get("duration_s"),
            "engine_version": manifest.get("engine", {}).get("version"),
            "phrear_version": manifest.get("software", {}).get("version"),
            "content_hash": run_hash,
            "same_project": run_hash == project_hash if run_hash else None,
            "periods": manifest.get("model", {}).get("periods"),
            "warnings": len(manifest.get("warnings", [])),
            "max_budget_discrepancy": run.get("max_budget_discrepancy"),
            "error": run.get("error"),
        }
    label = STATUS_LABELS[status]
    entry["status_label"] = {"it": label.it, "en": label.en}
    entry["products"] = {
        name: str(folder / filename)
        for name, filename in products.items()
        if (folder / filename).is_file()
    }
    return entry


def list_runs(project: Project) -> dict[str, Any]:
    """Every run folder of the project, newest first, with its state and products.

    ``same_project`` tells whether the project content is still the one the run
    was built from (combined content hash, docs/SPEC.md, section 3.1).
    """
    project_hash = hashing.combined_hash(project.content_hashes())
    products = {name: e.filename for name, e in EXPORTERS.items()}
    runs = project.root / RUNS_DIR
    folders = [f for f in runs.iterdir() if f.is_dir()] if runs.is_dir() else []
    entries = [_run_entry(f, project_hash, products) for f in folders]
    entries.sort(key=lambda e: (str(e.get("created") or ""), e["run_id"]), reverse=True)
    defaults = {name: e.default_dataset for name, e in EXPORTERS.items() if e.default_dataset}
    return {"content_hash": project_hash, "default_datasets": defaults, "runs": entries}
