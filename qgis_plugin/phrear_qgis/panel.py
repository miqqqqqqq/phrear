"""The Phrear panel: check and run the open project, list the problems, keep a log."""

from __future__ import annotations

import contextlib
import html
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qgis.core import Qgis, QgsProject
from qgis.gui import QgsDockWidget
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .client.events import Outcome
from .client.runs import (
    Labels,
    LogEntry,
    ProblemRow,
    StageRow,
    check_args,
    counts,
    log_entry,
    problem_row,
    problem_rows,
    progress,
    run_args,
    run_summary,
    stage_rows,
)
from .i18n import interface_language, tr

if TYPE_CHECKING:
    from .plugin import PhrearPlugin
    from .process import CoreProcess


def log_text(entry: LogEntry) -> str:
    templates = {
        "command_started": tr("phrear {command} started"),
        "command_completed": tr("phrear {command} completed in {seconds} s"),
        "command_failed": tr("phrear {command} failed: {message}"),
        "run_started": tr("Run {run_id} started with MODFLOW {engine}"),
        "run_completed": tr("Run {run_id} completed in {seconds} s"),
        "run_failed": tr("Run {run_id} failed: {message}"),
        "warning": tr("Warning [{code}] {message}"),
        "error": tr("Error [{code}] {message}"),
    }
    return f"{entry.time}  {templates[entry.key].format(**entry.values)}"


def where_text(row: ProblemRow) -> str:
    parts = []
    if row.table:
        parts.append(row.table_label or row.table)
    if row.fid is not None:
        parts.append(f"fid {row.fid}")
    if row.field:
        parts.append(row.field_label or row.field)
    if row.cell is not None:
        parts.append(tr("cell {cell}").format(cell=", ".join(str(i) for i in row.cell)))
    if row.path:
        parts.append(row.path)
    return " · ".join(parts)


def stage_text(stage: StageRow) -> str:
    if stage.status == "skipped":
        note = tr("not checked, it depends on {stages}").format(stages=", ".join(stage.skipped_for))
        return f"–  {stage.label} · {note}"
    mark = "✗" if stage.status == "errors" else "✓"
    notes = []
    if stage.errors:
        notes.append(tr("errors: {n}").format(n=stage.errors))
    if stage.warnings:
        notes.append(tr("warnings: {n}").format(n=stage.warnings))
    return f"{mark}  {stage.label}" + (f" · {', '.join(notes)}" if notes else "")


class PhrearPanel(QgsDockWidget):  # type: ignore[misc]
    def __init__(self, plugin: PhrearPlugin) -> None:
        super().__init__(tr("Phrear"), plugin.iface.mainWindow())
        self.plugin = plugin
        self.setObjectName("PhrearPanel")
        self.process: CoreProcess | None = None
        self.rows: list[ProblemRow] = []
        self.schema: dict[str, Any] | None = None
        self.labels = Labels(None, interface_language())

        body = QWidget()
        layout = QVBoxLayout(body)
        self.project_label = QLabel()
        self.project_label.setWordWrap(True)
        layout.addWidget(self.project_label)

        self.run_name = QLineEdit()
        self.run_name.setPlaceholderText(tr("Run name (empty: date and time)"))
        self.run_name.setToolTip(tr("Letters, digits, _ and -, up to 40 characters."))
        layout.addWidget(self.run_name)
        buttons = QHBoxLayout()
        self.check_button = QPushButton(tr("Check model"))
        self.check_button.setToolTip(
            tr("Check the project for errors and warnings (phrear check).")
        )
        self.run_button = QPushButton(tr("Run"))
        self.run_button.setToolTip(
            tr("Check, build and run the model with MODFLOW 6 (phrear run).")
        )
        self.cancel_button = QPushButton(tr("Cancel"))
        for button in (self.check_button, self.run_button, self.cancel_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.tabs = QTabWidget()
        problems = QWidget()
        problems_layout = QVBoxLayout(problems)
        problems_layout.setContentsMargins(0, 0, 0, 0)
        self.stages = QLabel()
        self.stages.setWordWrap(True)
        problems_layout.addWidget(self.stages)
        # A text browser wraps long messages, which item views elide in a narrow dock.
        self.problems = QTextBrowser()
        self.problems.setOpenLinks(False)
        problems_layout.addWidget(self.problems)
        self.tabs.addTab(problems, tr("Problems"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.tabs.addTab(self.log, tr("Log"))
        layout.addWidget(self.tabs, 1)
        self.setWidget(body)

        self.check_button.clicked.connect(self.check)
        self.run_button.clicked.connect(self.run)
        self.cancel_button.clicked.connect(self.cancel)
        self.problems.anchorClicked.connect(self._anchor)
        project = QgsProject.instance()
        project.readProject.connect(self.refresh)
        project.cleared.connect(self.refresh)
        self.refresh()

    def disconnect_project(self) -> None:
        project = QgsProject.instance()
        for signal in (project.readProject, project.cleared):
            with contextlib.suppress(TypeError, RuntimeError):
                signal.disconnect(self.refresh)

    # --- state ------------------------------------------------------------------------

    def refresh(self, *_: Any) -> None:
        root = self.plugin.projects.current()
        busy = self.process is not None
        if root is None:
            self.project_label.setText(tr("No Phrear project is open."))
        else:
            self.project_label.setText(tr("Project {folder}").format(folder=root.name))
        self.project_label.setToolTip(str(root) if root is not None else "")
        self.check_button.setEnabled(root is not None and not busy)
        self.run_button.setEnabled(root is not None and not busy)
        self.run_name.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.progress.setVisible(busy)

    # --- commands ---------------------------------------------------------------------

    def check(self) -> None:
        root = self.plugin.projects.current()
        if root is not None:
            self._start(root, check_args(root))

    def run(self) -> None:
        root = self.plugin.projects.current()
        if root is not None:
            self._start(root, run_args(root, self.run_name.text()))

    def cancel(self) -> None:
        if self.process is not None:
            self.process.cancel()

    def _start(self, root: Path, args: list[str]) -> None:
        """Run a command of the core on the saved project and follow its events."""
        if self.process is not None or not self.plugin.projects.saved(root):
            return

        def with_schema(schema: dict[str, Any]) -> None:
            self.schema = schema
            self.labels = Labels(schema, interface_language())
            process = self.plugin.run_core(args, self._finished, indicator=False)
            if process is None:
                return
            self.process = process
            process.event_received.connect(self._event)
            self._clear()
            self.status.setText(tr("phrear {command} in progress…").format(command=args[0]))
            self.progress.setRange(0, 0)
            self.refresh()

        self.plugin.projects.with_schema(with_schema)

    def _clear(self) -> None:
        self.rows = []
        self.problems.clear()
        self.stages.clear()

    def _event(self, event: dict[str, Any]) -> None:
        lang = interface_language()
        step = progress(event, lang)
        if step is not None:
            fraction, text = step
            if fraction is not None:
                self.progress.setRange(0, 1000)
                self.progress.setValue(round(1000 * fraction))
            if text:
                self.status.setText(text)
            return
        entry = log_entry(event, lang)
        if entry is not None:
            self.log.appendPlainText(log_text(entry))
        kind = event.get("event")
        if kind in ("error", "warning"):
            self._add_row(problem_row(event.get("problem") or {}, str(kind), lang, self.labels))

    def _finished(self, outcome: Outcome) -> None:
        self.process = None
        lang = interface_language()
        for row in problem_rows([], [], outcome.failure, lang, self.schema):
            self._add_row(row)
        if outcome.command == "check" and outcome.result is not None:
            self.stages.setText("\n".join(stage_text(s) for s in stage_rows(outcome.result, lang)))
        self.status.setText(self._outcome_text(outcome))
        if outcome.output:
            self.log.appendPlainText(outcome.output)
        summary = run_summary(outcome.result) if outcome.command == "run" else None
        if summary is not None:
            self.log.appendPlainText(tr("Results in {folder}").format(folder=summary.folder))
            self.run_name.clear()
        self.refresh()
        if self.rows:
            self.tabs.setCurrentIndex(0)

    def _outcome_text(self, outcome: Outcome) -> str:
        if not outcome.ok:
            return self.plugin.failure_text(outcome)
        _, warnings = counts(self.rows)
        summary = run_summary(outcome.result) if outcome.command == "run" else None
        if summary is None:
            if warnings:
                return tr("No blocking errors; warnings: {n}.").format(n=warnings)
            return tr("No problems found.")
        text = tr("Run {run_id} completed in {seconds} s.").format(
            run_id=summary.run_id, seconds=f"{summary.seconds:.1f}"
        )
        if summary.worst_budget_pct is not None:
            text += " " + tr("Largest budget error {pct} % (period {period}, step {step}).").format(
                pct=f"{summary.worst_budget_pct:.2g}",
                period=summary.worst_period,
                step=summary.worst_step,
            )
        if warnings:
            text += " " + tr("Warnings: {n}.").format(n=warnings)
        return text

    # --- problems ---------------------------------------------------------------------

    def _add_row(self, row: ProblemRow) -> None:
        self.rows.append(row)
        self.problems.append(self.row_html(len(self.rows) - 1))

    def row_html(self, index: int) -> str:
        """A problem as a paragraph: message, place and code, links, hint."""
        row = self.rows[index]
        mark = (
            '<span style="color:#d03b3b">✗</span>'
            if row.severity == "error"
            else '<span style="color:#d98f00">⚠</span>'
        )
        place = " · ".join(t for t in (where_text(row), row.code) if t)
        parts = [f"{mark} {html.escape(row.message)}"]
        details = f'<span style="color:gray">{html.escape(place)}</span>' if place else ""
        if row.locatable:
            links = (
                f'<a href="locate:{index}">{html.escape(tr("Show the feature"))}</a> · '
                f'<a href="form:{index}">{html.escape(tr("Open the form"))}</a>'
            )
            details = f"{details} — {links}" if details else links
        if details:
            parts.append(details)
        if row.hint:
            parts.append(f"<i>{html.escape(row.hint)}</i>")
        return "<p>" + "<br>".join(parts) + "</p>"

    def _anchor(self, url: QUrl) -> None:
        action, _, index = url.toString().partition(":")
        if not index.isdigit():
            return
        if action == "locate":
            self.locate(int(index))
        elif action == "form":
            self.open_form(int(index))

    def row_at(self, index: int) -> ProblemRow | None:
        return self.rows[index] if 0 <= index < len(self.rows) else None

    def _layer(self, row: ProblemRow) -> Any:
        layer = self.plugin.projects.layer_for(row.table or "")
        if layer is None:
            self.plugin.message(
                tr("The layer {layer} of the project is not loaded.").format(
                    layer=row.table_label or row.table
                ),
                Qgis.MessageLevel.Warning,
            )
        return layer

    def locate(self, index: int) -> None:
        """Select the feature and zoom to it; for a table, open its row."""
        row = self.row_at(index)
        if row is None or not row.locatable:
            return
        layer = self._layer(row)
        if layer is None:
            return
        fid = int(row.fid or 0)
        iface = self.plugin.iface
        if layer.isSpatial():
            layer.selectByIds([fid])
            iface.setActiveLayer(layer)
            canvas = iface.mapCanvas()
            canvas.zoomToFeatureIds(layer, [fid])
            canvas.flashFeatureIds(layer, [fid])
        else:
            iface.showAttributeTable(layer, f'"fid" = {fid}')

    def open_form(self, index: int) -> None:
        row = self.row_at(index)
        if row is None or not row.locatable:
            return
        layer = self._layer(row)
        if layer is None:
            return
        feature = layer.getFeature(int(row.fid or 0))
        if feature.isValid():
            self.plugin.iface.openFeatureForm(layer, feature)
