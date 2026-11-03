"""Reading the features of the conceptual model."""

from __future__ import annotations

import math
from typing import Any

import geopandas as gpd
import pyogrio

from phrear.project.project import Project


def is_null(value: Any) -> bool:
    """NULL as read by pyogrio: None, NaN or NaT."""
    if value is None:
        return True
    try:
        return bool(value != value)
    except (TypeError, ValueError):
        return False


def number(value: Any) -> float | None:
    """A REAL or INTEGER field as float, None for NULL."""
    return None if is_null(value) else float(value)


def text(value: Any) -> str | None:
    """A TEXT field stripped, None for NULL or empty."""
    if is_null(value):
        return None
    stripped = str(value).strip()
    return stripped or None


def read_features(project: Project, layer: str) -> gpd.GeoDataFrame:
    """Active features of the base model, indexed by fid in increasing order.

    NULL in ``active`` means the schema default, True; features with a
    ``scenario_id`` belong to a scenario and are left out.
    """
    frame = pyogrio.read_dataframe(project.gpkg_path, layer=layer, fid_as_index=True)
    if frame.empty:
        return frame
    active = frame["active"].map(lambda v: True if is_null(v) else bool(v)).astype(bool)
    base = frame["scenario_id"].map(lambda v: text(v) is None).astype(bool)
    return frame[active & base].sort_index()


def feature_label(name: Any, fid: int) -> str:
    """How a feature is named in messages: «name» (fid n), or fid n."""
    label = text(name)
    return f"«{label}» (fid {fid})" if label else f"fid {fid}"


def fmt(value: float) -> str:
    """Compact number for messages."""
    if math.isfinite(value) and abs(value) >= 1e-3:
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{value:.4g}"
