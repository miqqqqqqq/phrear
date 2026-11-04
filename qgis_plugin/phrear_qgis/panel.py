"""The Phrear panel: check and run the open project, list the problems, keep a log."""

from __future__ import annotations

import contextlib
import html
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qgis.core import Qgis, QgsProject
from qgis.gui import QgsDockWidget
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .client.events import Outcome
from .client.results import RunRow, default_heads, export_args, run_rows, runs_args
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
from .results import heads_layer, load_export, load_heads, remove_export, show_time

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
        self.run_rows: list[RunRow] = []
        self.runs_process: CoreProcess | None = None
        self.listed_root: Path | None = None
        self.preferred_heads = ""

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
        exports = QHBoxLayout()
        self.grid_button = QPushButton(tr("Show grid"))
        self.grid_button.setToolTip(
            tr("Build the grid and load its cells with top, bottoms and IDOMAIN (phrear grid).")
        )
        self.cells_button = QPushButton(tr("Show assigned cells"))
        self.cells_button.setToolTip(
            tr("Load the cells assigned to wells, fixed heads and recharge (phrear bc).")
        )
        exports.addWidget(self.grid_button)
        exports.addWidget(self.cells_button)
        layout.addLayout(exports)

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
        runs = QWidget()
        runs_layout = QVBoxLayout(runs)
        runs_layout.setContentsMargins(0, 0, 0, 0)
        self.runs = QTreeWidget()
        self.runs.setHeaderLabels([tr("Name"), tr("Date"), tr("State"), tr("Duration")])
        self.runs.setRootIsDecorated(False)
        runs_layout.addWidget(self.runs)
        run_buttons = QHBoxLayout()
        self.load_button = QPushButton(tr("Load heads"))
        self.folder_button = QPushButton(tr("Open folder"))
        self.refresh_button = QPushButton(tr("Refresh"))
        for button in (self.load_button, self.folder_button, self.refresh_button):
            run_buttons.addWidget(button)
        runs_layout.addLayout(run_buttons)
        self.tabs.addTab(runs, tr("Runs"))
        layout.addWidget(self.tabs, 1)
        self.setWidget(body)

        self.check_button.clicked.connect(self.check)
        self.run_button.clicked.connect(self.run)
        self.cancel_button.clicked.connect(self.cancel)
        self.problems.anchorClicked.connect(self._anchor)
        self.grid_button.clicked.connect(lambda: self.export("grid"))
        self.cells_button.clicked.connect(lambda: self.export("bc"))
        self.load_button.clicked.connect(self.load_selected)
        self.folder_button.clicked.connect(self.open_folder)
        self.refresh_button.clicked.connect(self.list_runs)
        self.runs.itemDoubleClicked.connect(lambda _item, _column: self.load_selected())
        self.runs.currentItemChanged.connect(lambda *_: self._run_buttons())
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
        for button in (self.check_button, self.run_button, self.grid_button, self.cells_button):
            button.setEnabled(root is not None and not busy)
        self.run_name.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.progress.setVisible(busy)
        self.refresh_button.setEnabled(root is not None)
        if root != self.listed_root:
            self.listed_root = root
            self.run_rows = []
            self.runs.clear()
            if root is not None:
                self.list_runs()
        self._run_buttons()

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

    def export(self, kind: str) -> None:
        """Write the grid or the assigned cells of the project and load them."""
        root = self.plugin.projects.current()
        if root is None or self.process is not None:
            return
        remove_export(root, kind)  # the core cannot replace a file open in QGIS on Windows
        self._start(root, export_args(kind, root))

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
        if outcome.command == "run":
            self.list_runs()
            if summary is not None and outcome.ok and summary.heads:
                self.preferred_heads = default_heads(outcome.result) or self.preferred_heads
                self._show_heads(summary.run_id, summary.heads)
        if outcome.ok and outcome.command in ("grid", "bc") and outcome.result:
            self._show_export(outcome.command, str(outcome.result.get("export", "")))
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

    # --- runs and results -------------------------------------------------------------

    def list_runs(self) -> None:
        root = self.plugin.projects.current()
        if root is None or self.runs_process is not None:
            return

        def listed(outcome: Outcome) -> None:
            self.runs_process = None
            if outcome.ok and self.plugin.projects.current() == root:
                self.preferred_heads = default_heads(outcome.result) or self.preferred_heads
                self._fill_runs(run_rows(outcome.result, interface_language()))

        self.runs_process = self.plugin.run_core(runs_args(root), listed, indicator=False)

    def _fill_runs(self, rows: list[RunRow]) -> None:
        self.run_rows = rows
        self.runs.clear()
        for index, row in enumerate(rows):
            state = row.status_label
            if row.same_project is False:
                state += " · " + tr("project changed")
            duration = f"{row.duration_s:.1f} s" if row.duration_s is not None else ""
            item = QTreeWidgetItem([row.run_id, row.created, state, duration])
            tips = [row.folder]
            if row.same_project is False:
                tips.append(tr("The project has changed since this run."))
            if row.budget_pct is not None:
                tips.append(tr("Largest budget error {pct} %").format(pct=f"{row.budget_pct:.2g}"))
            if row.error:
                tips.append(row.error)
            for column in range(4):
                item.setToolTip(column, "\n".join(tips))
            item.setData(0, Qt.ItemDataRole.UserRole, index)
            self.runs.addTopLevelItem(item)
        for column in range(4):
            self.runs.resizeColumnToContents(column)
        self._run_buttons()

    def selected_run(self) -> RunRow | None:
        item = self.runs.currentItem()
        index = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        return (
            self.run_rows[index] if isinstance(index, int) and index < len(self.run_rows) else None
        )

    def _run_buttons(self) -> None:
        row = self.selected_run()
        self.load_button.setEnabled(row is not None and row.can_load)
        self.folder_button.setEnabled(row is not None)

    def load_selected(self) -> None:
        row = self.selected_run()
        if row is None:
            return
        if not row.can_load:
            self.plugin.message(
                tr("Run {run_id} has no heads to load ({state}).").format(
                    run_id=row.run_id, state=row.status_label
                ),
                Qgis.MessageLevel.Warning,
            )
            return
        self._show_heads(row.run_id, row.heads or "")

    def open_folder(self) -> None:
        row = self.selected_run()
        if row is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(row.folder))

    def _project_group(self) -> tuple[Path, Any] | None:
        root = self.plugin.projects.current()
        group = self.plugin.projects.find_group(root) if root is not None else None
        if root is None or group is None:
            self.plugin.message(tr("Open the Phrear project first."), Qgis.MessageLevel.Warning)
            return None
        return root, group

    def _show_heads(self, run_id: str, path: str) -> None:
        found = self._project_group()
        if found is None:
            return
        root, group = found
        already = heads_layer(root, run_id) is not None
        layer = load_heads(group, root, run_id, path, self.preferred_heads)
        if layer is None:
            self.plugin.message(
                tr("The heads of run {run_id} could not be loaded from {path}.").format(
                    run_id=run_id, path=path
                ),
                Qgis.MessageLevel.Critical,
            )
            return
        show_time(self.plugin.iface.mapCanvas(), layer)
        self.plugin.iface.setActiveLayer(layer)
        if already:
            self.plugin.message(
                tr("The heads of run {run_id} are already loaded.").format(run_id=run_id)
            )
        else:
            self.plugin.message(
                tr(
                    "Heads of run {run_id} loaded; move through time with the temporal controller."
                ).format(run_id=run_id),
                Qgis.MessageLevel.Success,
            )

    def _show_export(self, kind: str, path: str) -> None:
        found = self._project_group()
        if found is None or not path:
            return
        root, group = found
        layer = load_export(group, root, kind, path, self.schema or {}, interface_language())
        if layer is None:
            self.plugin.message(
                tr("{path} could not be loaded.").format(path=path), Qgis.MessageLevel.Critical
            )
