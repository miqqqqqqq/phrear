"""Parameter arrays per layer."""

from __future__ import annotations

import numpy as np
import pytest

from phrear.grid.model_grid import build_model_grid
from phrear.params.layers import layer_parameters
from phrear.params.values import load_parameters
from phrear.project import Project


def test_layers_take_the_values_of_their_unit(valid_site: Project) -> None:
    grid = build_model_grid(valid_site)
    arrays = layer_parameters(grid, load_parameters(valid_site))
    assert grid.layer_unit == (1, 2, 2)
    assert arrays.k.shape == grid.botm.shape
    assert np.unique(arrays.k[0]) == pytest.approx([8.64])
    assert np.unique(arrays.k33[0]) == pytest.approx([0.864])
    assert np.unique(arrays.sy[0]) == pytest.approx([0.15])
    for layer in (1, 2):  # the two sublayers of the aquifer
        assert np.unique(arrays.k[layer]) == pytest.approx([50.0])
        assert np.unique(arrays.k33[layer]) == pytest.approx([5.0])
        assert np.unique(arrays.ss[layer]) == pytest.approx([1e-5])
        assert np.all(arrays.sy[layer] == 0.0)
    assert [int(np.unique(arrays.icelltype[i])[0]) for i in range(3)] == [1, 0, 0]
