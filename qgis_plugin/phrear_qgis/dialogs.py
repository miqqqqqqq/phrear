"""Dialogs for new projects and for the example project."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from qgis.core import QgsCoordinateReferenceSystem, QgsSettings
from qgis.gui import QgsProjectionSelectionWidget
from qgis.PyQt.QtCore import QDate
from qgis.PyQt.QtWidgets import (
    QDateEdit,
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

from .client.project import folder_free, new_project_problems, slug
from .i18n import tr

KEY_LAST_DIR = "phrear/last_dir"
DEFAULT_CRS = "EPSG:7791"


def last_dir() -> str:
    return str(QgsSettings().value(KEY_LAST_DIR, "") or str(Path.home()))


def remember_dir(folder: Path) -> None:
    QgsSettings().setValue(KEY_LAST_DIR, str(folder))


def problem_text(key: str) -> str:
    texts = {
        "name_missing": tr("Give a name to the project."),
        "parent_missing": tr("The parent folder does not exist."),
        "folder_used": tr("The project folder must be new or empty."),
        "dates_order": tr("The end date must follow the start date."),
        "crs_not_epsg": tr("Choose a coordinate reference system with an EPSG code."),
    }
    return texts.get(key, key)


def _folder_row(parent: QWidget, edit: QLineEdit, title: str) -> QWidget:
    box = QWidget()
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    browse = QPushButton(tr("Browse…"))

    def pick() -> None:
        chosen = QFileDialog.getExistingDirectory(parent, title, edit.text() or last_dir())
        if chosen:
            edit.setText(chosen)

    browse.clicked.connect(pick)
    row.addWidget(edit, 1)
    row.addWidget(browse)
    return box


def _to_date(value: Any) -> date:
    qdate = value.date()
    return date(qdate.year(), qdate.month(), qdate.day())


class NewProjectDialog(QDialog):  # type: ignore[misc]
    """Name, folder, CRS and model period of a new project."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("New Phrear project"))
        self.setMinimumWidth(560)
        self.name = QLineEdit()
        self.parent_dir = QLineEdit(last_dir())
        self.folder_name = QLineEdit()
        self.crs = QgsProjectionSelectionWidget()
        self.crs.setCrs(QgsCoordinateReferenceSystem(DEFAULT_CRS))
        today = date.today()
        self.start = QDateEdit(QDate(today.year, 1, 1))
        self.end = QDateEdit(QDate(today.year + 1, 1, 1))
        for edit in (self.start, self.end):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("dd/MM/yyyy")
        self.status = QLabel()
        self.status.setWordWrap(True)
        self._folder_edited = False
        self.name.textChanged.connect(self._follow_name)
        self.folder_name.textEdited.connect(self._stop_following)

        form = QFormLayout()
        form.addRow(tr("Name"), self.name)
        form.addRow(tr("Parent folder"), _folder_row(self, self.parent_dir, tr("Parent folder")))
        form.addRow(tr("Project folder"), self.folder_name)
        form.addRow(tr("Coordinate reference system"), self.crs)
        form.addRow(tr("Model start"), self.start)
        form.addRow(tr("Model end"), self.end)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addWidget(buttons)

    def _follow_name(self, text: str) -> None:
        if not self._folder_edited:
            self.folder_name.setText(slug(text) if text.strip() else "")

    def _stop_following(self, _: str) -> None:
        self._folder_edited = True

    @property
    def folder(self) -> Path:
        return Path(str(self.parent_dir.text()).strip()) / str(self.folder_name.text()).strip()

    def values(self) -> tuple[str, Path, date, date, str]:
        return (
            self.name.text().strip(),
            self.folder,
            _to_date(self.start),
            _to_date(self.end),
            str(self.crs.crs().authid()),
        )

    def _accept(self) -> None:
        name, _, start, end, crs = self.values()
        problems = new_project_problems(
            name, Path(self.parent_dir.text().strip()), self.folder_name.text(), start, end, crs
        )
        if problems:
            self.status.setText("\n".join(problem_text(p) for p in problems))
            return
        remember_dir(Path(self.parent_dir.text().strip()))
        self.accept()


class NewFolderDialog(QDialog):  # type: ignore[misc]
    """A new or empty folder, chosen as parent folder and name (for the example)."""

    def __init__(self, title: str, default_name: str, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        self.parent_dir = QLineEdit(last_dir())
        self.folder_name = QLineEdit(default_name)
        self.status = QLabel()
        self.status.setWordWrap(True)
        form = QFormLayout()
        form.addRow(tr("Parent folder"), _folder_row(self, self.parent_dir, tr("Parent folder")))
        form.addRow(tr("Project folder"), self.folder_name)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addWidget(buttons)

    @property
    def folder(self) -> Path:
        return Path(str(self.parent_dir.text()).strip()) / str(self.folder_name.text()).strip()

    def _accept(self) -> None:
        parent = Path(self.parent_dir.text().strip())
        if not parent.is_dir():
            self.status.setText(problem_text("parent_missing"))
            return
        if not self.folder_name.text().strip() or not folder_free(self.folder):
            self.status.setText(problem_text("folder_used"))
            return
        remember_dir(parent)
        self.accept()
