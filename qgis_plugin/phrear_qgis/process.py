"""The core run as a separate process, without blocking QGIS."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal

from .client.command import CoreLocation, clean_environment, core_command
from .client.events import EventStream, Outcome, collect


def qgis_roots() -> list[str]:
    """Install folders of QGIS, whose entries are removed from PATH for the core."""
    roots: list[str] = []
    prefix = Path(str(QgsApplication.prefixPath() or ""))
    if prefix.parts:
        roots.append(str(prefix.parent.parent if prefix.parent.name == "apps" else prefix))
    if os.environ.get("OSGEO4W_ROOT"):
        roots.append(os.environ["OSGEO4W_ROOT"])
    return roots


class CoreProcess(QObject):  # type: ignore[misc]
    """One command of the core; emits every event and, at the end, the outcome."""

    event_received = pyqtSignal(dict)
    finished = pyqtSignal(object)

    def __init__(
        self, location: CoreLocation, args: Sequence[str], lang: str, parent: Any = None
    ) -> None:
        super().__init__(parent)
        self.command = args[0] if args else ""
        self._program, *self._arguments = core_command(location, args, lang)
        # elsewhere than Windows the command gets its own process group, so that
        # cancelling stops pixi and everything it started
        self._group = sys.platform != "win32" and shutil.which("setsid") is not None
        if self._group:
            self._arguments = [self._program, *self._arguments]
            self._program = str(shutil.which("setsid"))
        self._stream = EventStream()
        self._events: list[dict[str, Any]] = []
        self._stderr = bytearray()
        self._cancelled = False
        self._reported = False
        self._process = QProcess(self)
        environment = QProcessEnvironment()
        for name, value in clean_environment(dict(os.environ), qgis_roots()).items():
            environment.insert(name, value)
        self._process.setProcessEnvironment(environment)
        self._process.setWorkingDirectory(str(location.core_dir))
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.finished.connect(self._done)
        self._process.errorOccurred.connect(self._error)

    def start(self) -> None:
        self._process.start(self._program, self._arguments)

    def is_running(self) -> bool:
        return bool(self._process.state() != QProcess.ProcessState.NotRunning)

    def cancel(self) -> None:
        """Stop the command and everything it started (pixi, the core, MODFLOW 6)."""
        if not self.is_running():
            return
        self._cancelled = True
        if sys.platform == "win32":
            # killing pixi alone would leave the core and MODFLOW 6 running
            subprocess.run(
                ["taskkill", "/PID", str(self._process.processId()), "/T", "/F"],
                capture_output=True,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        elif self._group:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(int(self._process.processId()), signal.SIGTERM)
        else:
            self._process.kill()

    def _read_stdout(self) -> None:
        for event in self._stream.feed(bytes(self._process.readAllStandardOutput())):
            self._events.append(event)
            self.event_received.emit(event)

    def _read_stderr(self) -> None:
        self._stderr += bytes(self._process.readAllStandardError())

    def _report(self, exit_code: int | None, start_error: str | None = None) -> None:
        if self._reported:
            return
        self._reported = True
        outcome: Outcome = collect(
            self.command,
            self._events,
            exit_code,
            self._stream,
            self._stderr.decode("utf-8", errors="replace"),
            cancelled=self._cancelled,
            start_error=start_error,
        )
        self.finished.emit(outcome)

    def _done(self, exit_code: int, exit_status: Any) -> None:
        self._read_stdout()
        self._read_stderr()
        for event in self._stream.finish():
            self._events.append(event)
            self.event_received.emit(event)
        crashed = exit_status == QProcess.ExitStatus.CrashExit
        self._report(None if crashed or self._cancelled else int(exit_code))

    def _error(self, error: Any) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._report(None, start_error=str(self._process.errorString()))
