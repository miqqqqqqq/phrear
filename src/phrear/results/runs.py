"""Finding the runs of a project."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from phrear.errors import ResultsError
from phrear.modflow.manifest import MANIFEST, read_manifest
from phrear.project import Project
from phrear.project.project import RUNS_DIR


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
