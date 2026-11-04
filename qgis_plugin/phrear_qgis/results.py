"""Results in QGIS: heads of a run as a temporal mesh layer, grid and boundary cells."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qgis.core import (
    Qgis,
    QgsCategorizedSymbolRenderer,
    QgsColorRampShader,
    QgsFillSymbol,
    QgsInterval,
    QgsMeshDatasetIndex,
    QgsMeshLayer,
    QgsMeshRendererScalarSettings,
    QgsProject,
    QgsRendererCategory,
    QgsSingleSymbolRenderer,
    QgsStyle,
    QgsTemporalNavigationObject,
    QgsVectorLayer,
)

from .client.project import layer_uri
from .client.results import cell_categories, heads_group
from .i18n import tr

RUN_PROPERTY = "phrear/run"
EXPORT_PROPERTY = "phrear/export"
SECTION_PROPERTY = "phrear/section"
SAME_PROPERTY = "phrear/project"


#: Sub-groups of a project group, top to bottom: features above cells, cells above
#: the heads, which cover the whole domain.
SECTIONS = ("model", "cells", "results", "tables")


def section(group: Any, key: str, title: str) -> Any:
    """The sub-group ``key`` of a project group, created in its place when missing."""
    children = group.children()
    position = len(children)
    for i, child in enumerate(children):
        other = child.customProperty(SECTION_PROPERTY)
        if other == key:
            return child
        if other in SECTIONS and SECTIONS.index(other) > SECTIONS.index(key):
            position = min(position, i)
    sub = group.insertGroup(position, title)
    sub.setCustomProperty(SECTION_PROPERTY, key)
    return sub


def _layers_with(prop: str, value: str, root: Path) -> list[Any]:
    found = []
    for layer in QgsProject.instance().mapLayers().values():
        if layer.customProperty(prop) == value and layer.customProperty(SAME_PROPERTY) == str(root):
            found.append(layer)
    return found


# --- heads ----------------------------------------------------------------------------


def heads_layer(root: Path, run_id: str) -> Any:
    found = _layers_with(RUN_PROPERTY, run_id, root)
    return found[0] if found else None


def load_heads(group: Any, root: Path, run_id: str, path: str, preferred: str = "") -> Any:
    """Add ``heads.nc`` of a run as a mesh layer in the «Results» section; None if invalid."""
    existing = heads_layer(root, run_id)
    if existing is not None:
        return existing
    layer = QgsMeshLayer(path, tr("Heads – {run_id}").format(run_id=run_id), "mdal")
    if not layer.isValid():
        return None
    layer.setCustomProperty(RUN_PROPERTY, run_id)
    layer.setCustomProperty(SAME_PROPERTY, str(root))
    style_heads(layer, preferred)
    QgsProject.instance().addMapLayer(layer, False)
    section(group, "results", tr("Results")).insertLayer(0, layer)
    return layer


def style_heads(layer: Any, preferred: str = "") -> None:
    """Show the water table with one colour ramp over all times."""
    groups = [
        layer.datasetGroupMetadata(QgsMeshDatasetIndex(i)) for i in range(layer.datasetGroupCount())
    ]
    if not groups:
        return
    index = heads_group([g.name() for g in groups], [g.isTemporal() for g in groups], preferred)
    meta = layer.datasetGroupMetadata(QgsMeshDatasetIndex(index))
    low, high = meta.minimum(), meta.maximum()
    settings = layer.rendererSettings()
    settings.setActiveScalarDatasetGroup(index)
    scalar = settings.scalarSettings(index)
    ramp = QgsStyle.defaultStyle().colorRamp("Viridis")
    shader = QgsColorRampShader(low, high, ramp, QgsColorRampShader.Type.Interpolated)
    shader.classifyColorRamp(9)
    scalar.setColorRampShader(shader)
    scalar.setClassificationMinimumMaximum(low, high)
    scalar.setOpacity(0.85)
    # One colour per cell: averaging neighbours would smooth the drawdown cones.
    scalar.setDataResamplingMethod(QgsMeshRendererScalarSettings.DataResamplingMethod.NoResampling)
    settings.setScalarSettings(index, scalar)
    layer.setRendererSettings(settings)


def show_time(canvas: Any, layer: Any) -> None:
    """Put the time span of the heads in the temporal controller, one frame per day."""
    properties = layer.temporalProperties()
    if not properties.isActive():
        return
    extent = properties.timeExtent()
    QgsProject.instance().timeSettings().setTemporalRange(extent)
    controller = canvas.temporalController()
    if isinstance(controller, QgsTemporalNavigationObject):
        controller.setTemporalExtents(extent)
        controller.setFrameDuration(QgsInterval(1, Qgis.TemporalUnit.Days))
        controller.setNavigationMode(Qgis.TemporalNavigationMode.Animated)
        controller.setCurrentFrameNumber(0)


# --- grid and boundary cells ----------------------------------------------------------


def remove_export(root: Path, kind: str) -> None:
    """Remove the layer of an export before the core writes the file again.

    On Windows a file open in QGIS cannot be replaced.
    """
    ids = [layer.id() for layer in _layers_with(EXPORT_PROPERTY, kind, root)]
    if ids:
        QgsProject.instance().removeMapLayers(ids)


def load_export(
    group: Any, root: Path, kind: str, path: str, schema: dict[str, Any], lang: str
) -> Any:
    names = {"grid": tr("Model grid"), "bc": tr("Boundary condition cells")}
    layer = QgsVectorLayer(layer_uri(path, "cells"), names[kind], "ogr")
    if not layer.isValid():
        return None
    layer.setCustomProperty(EXPORT_PROPERTY, kind)
    layer.setCustomProperty(SAME_PROPERTY, str(root))
    if kind == "grid":
        symbol = QgsFillSymbol.createSimple(
            {"style": "no", "outline_color": "128,128,128,180", "outline_width": "0.1"}
        )
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    else:
        field = layer.fields().indexFromName("feature_layer")
        values = [str(v) for v in layer.uniqueValues(field)] if field >= 0 else []
        categories = []
        for c in cell_categories(schema, lang, values):
            symbol = QgsFillSymbol.createSimple(
                {"color": c.fill, "outline_color": c.outline, "outline_width": "0.1"}
            )
            categories.append(QgsRendererCategory(c.value, symbol, c.label))
        layer.setRenderer(QgsCategorizedSymbolRenderer("feature_layer", categories))
    QgsProject.instance().addMapLayer(layer, False)
    section(group, "cells", tr("Grid and cells")).insertLayer(0, layer)
    return layer
