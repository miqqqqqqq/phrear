"""Edit sessions of QGIS on the layers of a project.

The core reads and writes the GeoPackage directly, so edits still open in QGIS
would be invisible to it (docs/SPEC.md, section 5). Before a command the plugin
asks to save or discard them.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from qgis.core import QgsProject, QgsVectorLayer
from qgis.PyQt.QtWidgets import QMessageBox

from .i18n import tr

Choice = str
"""``save``, ``discard`` or ``cancel``."""


def _same_file(a: str | Path, b: str | Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def project_layers(gpkg: Path) -> list[Any]:
    """Vector layers of the QGIS project that read the given GeoPackage."""
    found = []
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsVectorLayer) and _same_file(layer.source().split("|")[0], gpkg):
            found.append(layer)
    return found


def unsaved(gpkg: Path) -> list[Any]:
    return [layer for layer in project_layers(gpkg) if layer.isEditable() and layer.isModified()]


def ask(layers: list[Any], parent: Any) -> Choice:
    names = "\n".join(f"• {layer.name()}" for layer in layers)
    answer = QMessageBox.question(
        parent,
        tr("Unsaved edits"),
        tr("These layers of the project have unsaved edits:\n{names}\n\nSave them first?").format(
            names=names
        ),
        QMessageBox.StandardButton.Save
        | QMessageBox.StandardButton.Discard
        | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Save,
    )
    if answer == QMessageBox.StandardButton.Save:
        return "save"
    if answer == QMessageBox.StandardButton.Discard:
        return "discard"
    return "cancel"


def ensure_saved(
    gpkg: Path, parent: Any, choose: Callable[[list[Any], Any], Choice] = ask
) -> tuple[bool, str]:
    """Save or discard the open edits on the project; False if the user cancels or saving fails."""
    pending = unsaved(gpkg)
    if not pending:
        return True, ""
    choice = choose(pending, parent)
    if choice == "cancel":
        return False, ""
    for layer in pending:
        ok = layer.commitChanges() if choice == "save" else layer.rollBack()
        if not ok:
            errors = "\n".join(layer.commitErrors())
            return False, tr("Saving {layer} failed:\n{errors}").format(
                layer=layer.name(), errors=errors
            )
    return True, ""
