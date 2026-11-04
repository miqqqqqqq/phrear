"""Numbered schema migrations (docs/SPEC.md, section 21).

``MIGRATIONS[n]`` upgrades a project from schema ``n`` to ``n + 1`` in place.
Every migration is tested on a project of the previous version. Before the first
migration step a backup of project.toml and model.gpkg is made under ``backups/``.
Migrations are registered at the end of this module, one module per version.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

Migration = Callable[[Path], None]
"""Upgrade the project in the given folder by one schema version."""

MIGRATIONS: dict[int, Migration] = {}
"""Filled at the end of the module, after the helpers the migrations may use."""


@dataclass(frozen=True)
class MigrationReport:
    from_version: int
    to_version: int
    backup: Path | None
    steps: tuple[int, ...] = field(default_factory=tuple)


def pending(found: int, target: int) -> tuple[int, ...]:
    """Source versions of the migrations needed to go from ``found`` to ``target``."""
    steps = tuple(range(found, target))
    missing = [v for v in steps if v not in MIGRATIONS]
    if missing:
        raise RuntimeError(f"no migration registered from schema {missing[0]}")
    return steps


def backup_project(root: Path, files: tuple[str, ...], version: int) -> Path:
    """Copy ``files`` of the project into ``backups/<timestamp>_schema<version>/``."""
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    target = root / "backups" / f"{stamp}_schema{version}"
    target.mkdir(parents=True, exist_ok=False)
    for name in files:
        source = root / name
        if source.exists():
            shutil.copy2(source, target / name)
    return target


def _register() -> None:
    from phrear.project.migrations import schema2

    MIGRATIONS[1] = schema2.upgrade


_register()
