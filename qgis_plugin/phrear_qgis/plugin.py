"""Menu, toolbar and actions of the Phrear plugin."""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from qgis.core import Qgis, QgsApplication, QgsMessageLog
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QAction, QIcon
from qgis.PyQt.QtWidgets import QMessageBox, QProgressBar, QPushButton

from .client.command import CoreLocation, location_problems
from .client.events import Outcome
from .i18n import install_translator, interface_language, tr
from .process import CoreProcess
from .project import ProjectManager
from .settings import SettingsDialog, current_location, problem_text

LOG_TAG = "Phrear"


def log(message: str, level: Any = None) -> None:
    QgsMessageLog.logMessage(message, LOG_TAG, level or Qgis.MessageLevel.Info)


def action_text(command: str) -> str:
    """What a command is doing, for the indicator shown while it runs."""
    texts = {
        "env": tr("Checking the environment"),
        "info": tr("Reading the project"),
        "schema": tr("Reading the data schema"),
        "new": tr("Creating the project"),
        "example": tr("Creating the example project"),
    }
    return texts.get(command, f"phrear {command}")


def environment_text(data: dict[str, Any]) -> str:
    mf6 = data.get("mf6") or {}
    lines = [
        tr("Phrear core {version}").format(version=data.get("phrear", "?")),
        tr("MODFLOW 6 {version}").format(version=mf6.get("version", tr("not found"))),
        tr("Python {version}").format(version=data.get("python", "?")),
        tr("FloPy {flopy}, GDAL {gdal}, PROJ {proj}").format(
            flopy=data.get("flopy", "?"), gdal=data.get("gdal", "?"), proj=data.get("proj", "?")
        ),
    ]
    return "\n".join(lines)


class PhrearPlugin:
    def __init__(self, iface: Any) -> None:
        self.iface = iface
        self.plugin_dir = Path(__file__).parent
        self.menu = tr("&Phrear")
        self.actions: list[Any] = []
        self.toolbar: Any = None
        self.translator: Any = None
        self.processes: set[CoreProcess] = set()
        self.projects = ProjectManager(self)

    # --- QGIS plugin interface ------------------------------------------------------

    def initGui(self) -> None:
        self.translator = install_translator(self.plugin_dir)
        self.menu = tr("&Phrear")
        self.toolbar = self.iface.addToolBar(tr("Phrear"))
        self.toolbar.setObjectName("PhrearToolbar")
        theme = QgsApplication.getThemeIcon
        self._action(tr("New Phrear project…"), self.projects.new_project_dialog,
                     theme("/mActionFileNew.svg"))  # fmt: skip
        self._action(tr("Open a Phrear project…"), self.projects.open_project_dialog,
                     theme("/mActionFileOpen.svg"))  # fmt: skip
        self._action(tr("Create the example project…"), self.projects.example_dialog)
        self._action(tr("Project summary"), self.projects.summary)
        self._separator()
        icon = QIcon(str(self.plugin_dir / "icons" / "phrear.svg"))
        self._action(tr("Check the Phrear environment"), self.check_environment, icon)
        self._action(tr("Phrear settings…"), self.show_settings)
        self._action(tr("About Phrear"), self.show_about)

    def unload(self) -> None:
        for process in list(self.processes):
            process.cancel()
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            if self.toolbar is not None:
                self.toolbar.removeAction(action)
        self.actions.clear()
        if self.toolbar is not None:
            self.toolbar.deleteLater()
            self.toolbar = None
        if self.translator is not None:
            QCoreApplication.removeTranslator(self.translator)
            self.translator = None

    def _separator(self) -> None:
        separator = QAction(self.iface.mainWindow())
        separator.setSeparator(True)
        self.iface.addPluginToMenu(self.menu, separator)
        self.actions.append(separator)

    def _action(self, text: str, callback: Callable[[], None], icon: Any = None) -> Any:
        action = QAction(text, self.iface.mainWindow())
        if icon is not None:
            action.setIcon(icon)
        action.triggered.connect(callback)
        self.iface.addPluginToMenu(self.menu, action)
        if icon is not None:
            self.toolbar.addAction(action)
        self.actions.append(action)
        return action

    # --- running the core -------------------------------------------------------------

    def location(self) -> CoreLocation | None:
        """The configured location, or None after telling the user what is missing."""
        location = current_location(self.plugin_dir)
        problems = location_problems(location)
        if problems:
            text = " ".join(problem_text(p) for p in problems)
            self.iface.messageBar().pushMessage(
                tr("Phrear"),
                tr("{problems} Open Phrear settings to fix it.").format(problems=text),
                level=Qgis.MessageLevel.Warning,
                duration=10,
            )
            return None
        return location

    def run_core(
        self,
        args: Sequence[str],
        on_finished: Callable[[Outcome], None],
        location: CoreLocation | None = None,
    ) -> CoreProcess | None:
        location = location or self.location()
        if location is None:
            return None
        process = CoreProcess(location, args, interface_language(), self.iface.mainWindow())
        indicator = self._indicator(process)

        def finished(outcome: Outcome) -> None:
            self.processes.discard(process)
            self._close_indicator(indicator)
            self._log_outcome(outcome)
            on_finished(outcome)
            process.deleteLater()

        process.finished.connect(finished)
        self.processes.add(process)
        log(tr("Running phrear {args}").format(args=" ".join(args)))
        process.start()
        return process

    def _indicator(self, process: CoreProcess) -> Any:
        """Message with a busy bar and a cancel button while the command runs."""
        bar = self.iface.messageBar()
        item = bar.createMessage(
            tr("Phrear"), tr("{action} in progress…").format(action=action_text(process.command))
        )
        progress = QProgressBar()
        progress.setRange(0, 0)
        progress.setMaximumWidth(240)
        progress.setTextVisible(False)
        cancel = QPushButton(tr("Cancel"))
        cancel.clicked.connect(process.cancel)
        item.layout().addWidget(progress)
        item.layout().addWidget(cancel)

        def on_event(event: dict[str, Any]) -> None:
            fraction = event.get("fraction") if event.get("event") == "progress" else None
            if isinstance(fraction, (int, float)):
                progress.setRange(0, 100)
                progress.setValue(round(100 * fraction))

        process.event_received.connect(on_event)
        return bar.pushWidget(item, Qgis.MessageLevel.Info)

    def _close_indicator(self, item: Any) -> None:
        with contextlib.suppress(RuntimeError):  # already closed by the user
            self.iface.messageBar().popWidget(item)

    def message(self, text: str, level: Any = None, duration: int = 6) -> None:
        self.iface.messageBar().pushMessage(
            tr("Phrear"), text, level=level or Qgis.MessageLevel.Info, duration=duration
        )

    def report_failure(self, outcome: Outcome, title: str) -> bool:
        """Tell the user why a command did not succeed; True if it did not."""
        if outcome.ok:
            return False
        if outcome.cancelled:
            self.message(tr("The command was cancelled."), Qgis.MessageLevel.Info)
        else:
            QMessageBox.warning(self.iface.mainWindow(), title, self.failure_text(outcome))
        return True

    def _log_outcome(self, outcome: Outcome) -> None:
        lang = interface_language()
        for problem in outcome.warnings:
            message = problem.get("message", {})
            log(f"[{problem.get('code')}] {message.get(lang, '')}", Qgis.MessageLevel.Warning)
        if outcome.output:
            log(outcome.output)
        if not outcome.ok:
            log(self.failure_text(outcome), Qgis.MessageLevel.Critical)

    def failure_text(self, outcome: Outcome) -> str:
        if outcome.start_error:
            return tr("The core could not be started: {error}").format(error=outcome.start_error)
        if outcome.cancelled:
            return tr("The command was cancelled.")
        if outcome.wrong_schema:
            return tr(
                "The core speaks a different version of the event protocol ({found}); "
                "update the plugin and the core together."
            ).format(found=", ".join(outcome.wrong_schema))
        text = outcome.failure_text(interface_language())
        if text:
            return text
        return tr("The core stopped with exit code {code}.").format(code=outcome.exit_code)

    # --- actions ----------------------------------------------------------------------

    def check_environment(self) -> None:
        def done(outcome: Outcome) -> None:
            window = self.iface.mainWindow()
            if outcome.ok and outcome.result is not None:
                QMessageBox.information(
                    window, tr("Phrear environment"), environment_text(outcome.result)
                )
            else:
                QMessageBox.warning(window, tr("Phrear environment"), self.failure_text(outcome))

        self.run_core(["env"], done)

    def verify_location(self, location: CoreLocation, report: Callable[[str], None]) -> None:
        def done(outcome: Outcome) -> None:
            if outcome.ok and outcome.result is not None:
                report(environment_text(outcome.result))
            else:
                report(self.failure_text(outcome))

        self.run_core(["env"], done, location)

    def show_settings(self) -> None:
        dialog = SettingsDialog(
            current_location(self.plugin_dir), self.verify_location, self.iface.mainWindow()
        )
        dialog.exec()

    def show_about(self) -> None:
        QMessageBox.about(
            self.iface.mainWindow(),
            tr("About Phrear"),
            tr(
                "Phrear: groundwater modelling for QGIS with MODFLOW 6.\n\n"
                "Plugin: GPL-2.0-or-later. Core: EUPL-1.2.\n"
                "Copyright (C) 2026 Michele.\n\n"
                "https://github.com/miqqqqqqq/phrear"
            ),
        )
