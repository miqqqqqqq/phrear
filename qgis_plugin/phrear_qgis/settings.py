"""Where the core is: stored in the QGIS settings, edited in a dialog."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from qgis.core import QgsSettings
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .client.command import CoreLocation, default_core_dir, find_pixi, location_problems
from .i18n import tr

KEY_CORE_DIR = "phrear/core_dir"
KEY_PIXI = "phrear/pixi"


def _stored(key: str) -> str:
    return str(QgsSettings().value(key, "") or "")


def current_location(plugin_dir: Path) -> CoreLocation:
    """The stored location, or the one found automatically."""
    core = _stored(KEY_CORE_DIR) or str(default_core_dir(plugin_dir) or "")
    pixi = _stored(KEY_PIXI) or str(find_pixi(os.environ, Path.home()) or "")
    return CoreLocation(Path(core), Path(pixi))


def save_location(location: CoreLocation) -> None:
    settings = QgsSettings()
    settings.setValue(KEY_CORE_DIR, str(location.core_dir))
    settings.setValue(KEY_PIXI, str(location.pixi))


def problem_text(key: str) -> str:
    texts = {
        "pixi_missing": tr("The pixi executable was not found."),
        "core_dir_invalid": tr(
            "The core folder must be the phrear repository, with pixi.toml and src/phrear."
        ),
    }
    return texts.get(key, key)


class SettingsDialog(QDialog):  # type: ignore[misc]
    def __init__(
        self,
        location: CoreLocation,
        verify: Callable[[CoreLocation, Callable[[str], None]], None],
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Phrear settings"))
        self.setMinimumWidth(560)
        self._verify = verify
        self.core_dir = QLineEdit(str(location.core_dir) if location.core_dir.parts else "")
        self.pixi = QLineEdit(str(location.pixi) if location.pixi.parts else "")
        self.status = QLabel()
        self.status.setWordWrap(True)

        form = QFormLayout()
        form.addRow(tr("Core folder (phrear repository)"), self._with_browse(self.core_dir, True))
        form.addRow(tr("pixi executable"), self._with_browse(self.pixi, False))
        check = QPushButton(tr("Check"))
        check.clicked.connect(self._check)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        help_text = QLabel(
            tr(
                "Phrear runs its core with pixi in the environment of the phrear "
                "repository. Both are found automatically when possible."
            )
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        layout.addLayout(form)
        row = QHBoxLayout()
        row.addWidget(check)
        row.addWidget(self.status, 1)
        layout.addLayout(row)
        layout.addWidget(buttons)

    def _with_browse(self, edit: QLineEdit, folder: bool) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        browse = QPushButton(tr("Browse…"))

        def pick() -> None:
            if folder:
                chosen = QFileDialog.getExistingDirectory(self, tr("Core folder"), edit.text())
            else:
                chosen, _ = QFileDialog.getOpenFileName(self, tr("pixi executable"), edit.text())
            if chosen:
                edit.setText(chosen)

        browse.clicked.connect(pick)
        row.addWidget(edit, 1)
        row.addWidget(browse)
        return box

    def location(self) -> CoreLocation:
        return CoreLocation(Path(self.core_dir.text().strip()), Path(self.pixi.text().strip()))

    def _problems(self) -> list[str]:
        return [problem_text(p) for p in location_problems(self.location())]

    def _check(self) -> None:
        problems = self._problems()
        if problems:
            self.status.setText("\n".join(problems))
            return
        self.status.setText(tr("Checking…"))
        self._verify(self.location(), self.status.setText)

    def _accept(self) -> None:
        problems = self._problems()
        if problems:
            self.status.setText("\n".join(problems))
            return
        save_location(self.location())
        self.accept()
