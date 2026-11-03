"""Parameter arrays per model layer, for the NPF and STO packages of MF6."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from phrear.grid.model_grid import ModelGrid
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
    """Specific yield (STO SY); 0 for confined units, where MF6 does not use it."""
    icelltype: npt.NDArray[np.int64]
    """1 convertible, 0 confined (NPF ICELLTYPE and STO ICONVERT)."""


def layer_parameters(grid: ModelGrid, params: ParameterSet) -> LayerParameters:
    shape = grid.botm.shape
    k = np.empty(shape)
    k33 = np.empty(shape)
    ss = np.empty(shape)
    sy = np.empty(shape)
    icelltype = np.empty(shape, dtype=np.int64)
    for layer, position in enumerate(grid.layer_unit):
        unit = params.by_position(position)
        k[layer] = unit.kh
        k33[layer] = unit.kv
        ss[layer] = unit.ss
        sy[layer] = unit.sy if unit.sy is not None else 0.0
        icelltype[layer] = 1 if unit.convertible else 0
    return LayerParameters(k=k, k33=k33, ss=ss, sy=sy, icelltype=icelltype)
