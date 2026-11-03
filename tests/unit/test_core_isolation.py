"""The core must not depend on QGIS or Qt (docs/SPEC.md, sections 5 and 22)."""

from __future__ import annotations

import ast
from pathlib import Path

import phrear

FORBIDDEN_ROOTS = {"qgis", "PyQt5", "PyQt6", "PySide2", "PySide6", "qtpy", "sip"}
CORE_DIR = Path(phrear.__file__).parent


def _imported_roots(path: Path) -> set[str]:
    """Top-level package names imported by a source file (absolute imports only)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_core_sources_do_not_import_qt_or_qgis() -> None:
    offenders = {
        str(path.relative_to(CORE_DIR)): sorted(_imported_roots(path) & FORBIDDEN_ROOTS)
        for path in CORE_DIR.rglob("*.py")
    }
    assert {name: mods for name, mods in offenders.items() if mods} == {}


def test_scan_covers_core_sources() -> None:
    assert (CORE_DIR / "cli.py").is_file()


def _print_calls(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return sum(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"
        for node in ast.walk(tree)
    )


def test_core_does_not_print() -> None:
    """No print in the core (section 22); only the CLI writes to the console."""
    offenders = {
        str(path.relative_to(CORE_DIR)): n
        for path in CORE_DIR.rglob("*.py")
        if path.name != "cli.py" and (n := _print_calls(path))
    }
    assert offenders == {}
