"""Parameter arrays per model layer, for the NPF and STO packages of MF6."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from phrear.grid.model_grid import ModelGrid
from phrear.params.cells import CellParameters, ParamField, assign_cells
from phrear.params.values import ParameterSet

FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class LayerParameters:
    """Arrays of shape (nlay, nrow, ncol), internal units."""

    k: FloatArray
    """Horizontal K, m/d (NPF K)."""
    k33: FloatArray
    """Vertical K, m/d (NPF K33)."""
    ss: FloatArray
    """Specific storage, 1/m (STO SS)."""
    sy: FloatArray
    """Specific yield (STO SY); 0 where not given, e.g. confined units, where MF6 ignores it."""
    icelltype: npt.NDArray[np.int64]
    """1 convertible, 0 confined (NPF ICELLTYPE and STO ICONVERT)."""


def _filled(field: ParamField | None, geometric: bool, default: float) -> FloatArray | float:
    """The values of a field, with the cells no source covers set to its mean.

    Those cells are inactive (an active cell without a value is an error), so the
    value only has to be valid for MF6, which does not use it.
    """
    if field is None:
        return default
    values = field.values.copy()
    missing = np.isnan(values)
    if missing.any():
        known = values[~missing]
        if known.size == 0:
            values[missing] = default
        else:
            values[missing] = np.exp(np.log(known).mean()) if geometric else known.mean()
    return values


def layer_arrays(grid: ModelGrid, cells: CellParameters) -> LayerParameters:
    shape = grid.botm.shape
    k = np.empty(shape)
    k33 = np.empty(shape)
    ss = np.empty(shape)
    sy = np.empty(shape)
    icelltype = np.empty(shape, dtype=np.int64)
    for layer, position in enumerate(grid.layer_unit):
        unit = cells.units[position]
        k[layer] = _filled(unit.fields.get("kh"), True, 1.0)
        k33[layer] = _filled(unit.fields.get("kv"), True, 1.0)
        ss[layer] = _filled(unit.fields.get("ss"), False, 1e-5)
        sy[layer] = _filled(unit.fields.get("sy"), False, 0.0)
        icelltype[layer] = 1 if unit.unit.convertible else 0
    return LayerParameters(k=k, k33=k33, ss=ss, sy=sy, icelltype=icelltype)


def layer_parameters(grid: ModelGrid, params: ParameterSet) -> LayerParameters:
    """Arrays of a valid parameter set; raises on the first problem of the cells."""
    return layer_arrays(grid, assign_cells(grid, params))
