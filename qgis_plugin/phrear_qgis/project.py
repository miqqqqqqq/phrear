"""Creating, opening and summarising Phrear projects in QGIS."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox

from .client.events import Outcome
from .client.project import (
    GPKG_FILE,
    is_project,
    layer_plan,
    new_project_args,
    table_rows,
    upgraded_uri,
)
from .dialogs import NewFolderDialog, NewProjectDialog, last_dir, remember_dir
from .editing import ensure_saved, keep_wall_clock, project_layers
from .forms import configure
from .i18n import interface_language, tr

if TYPE_CHECKING:
    from .plugin import PhrearPlugin

GROUP_PROPERTY = "phrear/project"
TABLE_PROPERTY = "phrear/table"
SCOPE, KEY = "Phrear", "project"


def _same(a: str | Path, b: str | Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


class ProjectManager:
    def __init__(self, plugin: PhrearPlugin) -> None:
        self.plugin = plugin
        self.schema: dict[str, Any] | None = None

    @property
    def window(self) -> Any:
        return self.plugin.iface.mainWindow()

    # --- layers of the projects -----------------------------------------------------

    def watch(self) -> None:
        """Protect the dates of the project layers, now and whenever they are added."""
        project = QgsProject.instance()
        self._layers_added(list(project.mapLayers().values()))
        project.layersAdded.connect(self._layers_added)

    def unwatch(self) -> None:
        with contextlib.suppress(TypeError, RuntimeError):
            QgsProject.instance().layersAdded.disconnect(self._layers_added)

    def _layers_added(self, layers: list[Any]) -> None:
        for layer in layers:
            if layer.customProperty(TABLE_PROPERTY):
                source = upgraded_uri(layer.source())
                if source is not None:
                    layer.setDataSource(source, layer.name(), layer.providerType())
                keep_wall_clock(layer)

    def layer_for(self, table: str) -> Any:
        """The layer of ``table`` of the open Phrear project, if it is loaded."""
        root = self.current()
        if root is None:
            return None
        for layer in project_layers(root / GPKG_FILE):
            if layer.customProperty(TABLE_PROPERTY) == table:
                return layer
        return None

    # --- current project ------------------------------------------------------------

    def current(self) -> Path | None:
        """The Phrear project of the QGIS project, if one was opened."""
        value, ok = QgsProject.instance().readEntry(SCOPE, KEY, "")
        return Path(value) if ok and value and is_project(Path(value)) else None

    def find_group(self, root: Path) -> Any:
        tree = QgsProject.instance().layerTreeRoot()
        for group in tree.findGroups(True):
            stored = group.customProperty(GROUP_PROPERTY)
            if stored and _same(stored, root):
                return group
        return None

    # --- actions with dialogs -------------------------------------------------------

    def new_project_dialog(self) -> None:
        dialog = NewProjectDialog(self.window)
        if dialog.exec():
            self.create(*dialog.values())

    def open_project_dialog(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self.window, tr("Open a Phrear project"), last_dir()
        )
        if chosen:
            remember_dir(Path(chosen).parent)
            self.open(Path(chosen))

    def example_dialog(self) -> None:
        dialog = NewFolderDialog(tr("Create the example project"), "esempio_phrear", self.window)
        if dialog.exec():
            self.create_example(dialog.folder)

    # --- operations -------------------------------------------------------------------

    def create(
        self,
        name: str,
        folder: Path,
        start: date,
        end: date,
        crs: str,
        on_done: Callable[[Any], None] | None = None,
    ) -> None:
        def done(outcome: Outcome) -> None:
            if self.plugin.report_failure(outcome, tr("New Phrear project")):
                return
            self.open(folder, on_done)

        self.plugin.run_core(new_project_args(name, folder, start, end, crs), done)

    def create_example(self, folder: Path, on_done: Callable[[Any], None] | None = None) -> None:
        def done(outcome: Outcome) -> None:
            if self.plugin.report_failure(outcome, tr("Create the example project")):
                return
            self.open(folder, on_done)

        self.plugin.run_core(["example", str(folder)], done)

    def with_schema(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Run ``callback`` with the schema document of the core, read once per session."""
        if self.schema is not None:
            callback(self.schema)
            return

        def done(outcome: Outcome) -> None:
            if self.plugin.report_failure(outcome, tr("Phrear")) or outcome.result is None:
                return
            self.schema = outcome.result
            callback(self.schema)

        self.plugin.run_core(["schema"], done)

    def open(self, root: Path, on_done: Callable[[Any], None] | None = None) -> None:
        if not is_project(root):
            QMessageBox.warning(
                self.window,
                tr("Open a Phrear project"),
                tr("{folder} has no project.toml or model.gpkg.").format(folder=root),
            )
            return
        group = self.find_group(root)
        if group is not None:
            self.plugin.message(
                tr("The project is already open in the layer group {group}.").format(
                    group=group.name()
                )
            )
            if on_done:
                on_done(group)
            return
        if not self.saved(root):
            return

        def got_info(outcome: Outcome) -> None:
            if self.plugin.report_failure(outcome, tr("Open a Phrear project")):
                return
            info = outcome.result or {}
            self.with_schema(lambda schema: self._loaded(self.load(root, info, schema), on_done))

        self.plugin.run_core(["info", str(root)], got_info)

    def saved(self, root: Path) -> bool:
        """Ask to save or discard unsaved edits on the project; False to stop."""
        ok, error = ensure_saved(root / GPKG_FILE, self.window)
        if error:
            QMessageBox.warning(self.window, tr("Unsaved edits"), error)
        return ok

    def _loaded(self, group: Any, on_done: Callable[[Any], None] | None) -> None:
        if on_done:
            on_done(group)

    def load(self, root: Path, info: dict[str, Any], schema: dict[str, Any]) -> Any:
        """Add the layers and tables of the project to a new group at the top of the tree."""
        project = QgsProject.instance()
        gpkg = root / GPKG_FILE
        epsg = int(info.get("crs", {}).get("epsg", 0))
        if not project.mapLayers() and epsg:
            project.setCrs(QgsCoordinateReferenceSystem(f"EPSG:{epsg}"))
        tree = project.layerTreeRoot()
        group = tree.insertGroup(0, tr("Phrear – {name}").format(name=info.get("name", root.name)))
        group.setCustomProperty(GROUP_PROPERTY, str(root))
        model_group = group.addGroup(tr("Conceptual model"))
        tables_group = group.addGroup(tr("Tables"))
        tables_group.setExpanded(False)
        invalid: list[str] = []
        layers: dict[str, Any] = {}
        lang = interface_language()
        for spec in layer_plan(schema, lang):
            layer = QgsVectorLayer(spec.uri(gpkg), spec.label, "ogr")
            if not layer.isValid():
                invalid.append(spec.name)
                continue
            layer.setCustomProperty(TABLE_PROPERTY, spec.name)
            project.addMapLayer(layer, False)
            (tables_group if spec.is_table else model_group).addLayer(layer)
            layers[spec.name] = layer
        invalid += configure(layers, schema, lang, str(root))
        project.writeEntry(SCOPE, KEY, str(root))
        self.plugin.project_changed()
        domain = layers.get("domain")
        if domain is not None and domain.featureCount() > 0:
            self._zoom_to(domain)
        if invalid:
            self.plugin.message(
                tr("Some tables or relations could not be loaded: {names}").format(
                    names=", ".join(invalid)
                ),
                Qgis.MessageLevel.Warning,
            )
        else:
            self.plugin.message(
                tr("Project {name} opened.").format(name=info.get("name", root.name)),
                Qgis.MessageLevel.Success,
            )
        return group

    def _zoom_to(self, layer: Any) -> None:
        canvas = self.plugin.iface.mapCanvas()
        destination = canvas.mapSettings().destinationCrs()
        extent = layer.extent()
        if destination.isValid() and destination != layer.crs():
            transform = QgsCoordinateTransform(layer.crs(), destination, QgsProject.instance())
            extent = transform.transformBoundingBox(extent)
        extent.scale(1.05)
        canvas.setExtent(extent)
        canvas.refresh()

    # --- summary ----------------------------------------------------------------------

    def summary(self) -> None:
        root = self.current()
        if root is None:
            self.plugin.message(
                tr("Open or create a Phrear project first."), Qgis.MessageLevel.Info
            )
            return
        if not self.saved(root):
            return

        def got_info(outcome: Outcome) -> None:
            if self.plugin.report_failure(outcome, tr("Project summary")):
                return
            info = outcome.result or {}
            self.with_schema(lambda schema: self._show_summary(info, schema))

        self.plugin.run_core(["info", str(root)], got_info)

    def summary_text(self, info: dict[str, Any], schema: dict[str, Any]) -> str:
        model = info.get("model", {})
        crs = info.get("crs", {})
        steady = tr("yes") if model.get("steady_initial") else tr("no")
        lines = [
            tr("Project {name}").format(name=info.get("name", "")),
            tr("Folder {path}").format(path=info.get("path", "")),
            tr("Coordinate reference system EPSG:{epsg} ({crs})").format(
                epsg=crs.get("epsg", "?"), crs=crs.get("name", "")
            ),
            tr("Model period from {start} to {end}, initial steady state {steady}").format(
                start=str(model.get("start_date", ""))[:10],
                end=str(model.get("end_date", ""))[:10],
                steady=steady,
            ),
            "",
        ]
        lines += [
            f"{label}: {count}" for label, count in table_rows(info, schema, interface_language())
        ]
        lines += ["", tr("Content hash {hash}").format(hash=str(info.get("content_hash", ""))[:16])]
        return "\n".join(lines)

    def _show_summary(self, info: dict[str, Any], schema: dict[str, Any]) -> None:
        QMessageBox.information(self.window, tr("Project summary"), self.summary_text(info, schema))
