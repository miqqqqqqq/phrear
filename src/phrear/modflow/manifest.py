"""Manifest of a run: what was built, from which project state, with which engine."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Final

import phrear
from phrear.checks.base import Inspection
from phrear.errors import RunError
from phrear.modflow.simulation import Simulation
from phrear.project import hashing
from phrear.project.project import RUNS_DIR

MANIFEST: Final = "manifest.json"
MANIFEST_VERSION: Final = 1
_RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def new_run_dir(root: Path, run_id: str | None, now: datetime) -> tuple[str, Path]:
    """A new run folder; never reuses an existing one."""
    runs = root / RUNS_DIR
    if run_id is not None:
        if not _RUN_ID.fullmatch(run_id):
            raise RunError("run.invalid_id", run_id=run_id)
        target = runs / run_id
        if target.exists():
            raise RunError("run.exists", run_id=run_id, path=str(target))
        return run_id, target
    stem = now.strftime("%Y%m%d-%H%M%S")
    candidate, n = stem, 1
    while (runs / candidate).exists():
        n += 1
        candidate = f"{stem}-{n}"
    return candidate, runs / candidate


def manifest_data(
    ins: Inspection,
    run_id: str,
    simulation: Simulation,
    engine: dict[str, str],
    created: datetime,
) -> dict[str, Any]:
    project = ins.project
    assert ins.grid is not None and ins.timeline is not None
    hashes = project.content_hashes()
    return {
        "manifest_version": MANIFEST_VERSION,
        "run_id": run_id,
        "created": created.isoformat(timespec="seconds"),
        "software": {"name": "phrear", "version": phrear.__version__},
        "engine": {"name": "MODFLOW 6", **engine},
        "project": {
            "name": project.config.name,
            "schema_version": project.config.schema_version,
            "content_hash": hashing.combined_hash(hashes),
            "hashes": hashes,
        },
        "settings": project.config.model_dump(mode="json"),
        "model": {
            **{k: v for k, v in ins.grid.summary().items() if k != "layers"},
            "layers": [
                {
                    "layer": k + 1,
                    "unit": position,
                    "convertible": next(
                        u.convertible for u in ins.grid.units if u.position == position
                    ),
                }
                for k, position in enumerate(ins.grid.layer_unit)
            ],
            "start_date": ins.timeline.calendar.start.isoformat(),
            "offset_d": ins.timeline.calendar.offset_d,
            "periods": len(ins.timeline.calendar.periods),
            "entries": simulation.entries,
            "series": simulation.series,
        },
        "warnings": [p.model_dump(mode="json") for p in ins.warnings],
        "files": list(simulation.files),
        "run": {"status": "built"},
    }


def write_manifest(folder: Path, data: dict[str, Any]) -> Path:
    """Write the manifest atomically (temporary file, then rename)."""
    path = folder / MANIFEST
    temporary = folder / f".{MANIFEST}.tmp"
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def read_manifest(folder: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    return data
