"""Initial heads: constant, raster, checks."""

from __future__ import annotations

import numpy as np
import pytest

from phrear.conceptual.initial_heads import initial_heads
from phrear.errors import GeometryError, InitialHeadsError
from phrear.grid.model_grid import ModelGrid, build_model_grid
from phrear.project import Project
from phrear.project.config import ConstantHeads, InterpolatedHeads, RasterHeads, RunHeads

from ..grid.conftest import X0, plane, write_raster


@pytest.fixture
def grid(site: Project) -> ModelGrid:
    return build_model_grid(site)


def test_constant_heads_fill_every_layer(site: Project, grid: ModelGrid) -> None:
    site.config.initial_heads = ConstantHeads(value_m=30.0)
    heads = initial_heads(site, grid)
    assert heads.mode == "constant"
    assert heads.strt.shape == grid.botm.shape == (3, 15, 20)
    assert np.all(heads.strt == 30.0)
    assert heads.warnings == ()


def test_raster_heads_are_sampled_on_the_grid(site: Project, grid: ModelGrid) -> None:
    field = plane(0.002, -0.001, 30.0)  # 2 per mille towards east, 1 per mille towards north
    write_raster(site.root / "rasters" / "heads.tif", field)
    site.config.initial_heads = RasterHeads(raster_path="rasters/heads.tif")
    heads = initial_heads(site, grid)
    x, y = grid.geometry.centers()
    # the mean of a plane over a cell is its value at the centre
    for layer in range(3):
        assert heads.strt[layer] == pytest.approx(field(x, y), abs=1e-4)
    assert heads.warnings == ()


def test_raster_heads_must_cover_the_active_cells(site: Project, grid: ModelGrid) -> None:
    write_raster(
        site.root / "rasters" / "heads.tif",
        plane(0.0, 0.0, 30.0),
        nodata_mask=lambda x, y: x > X0 + 2000,
    )
    site.config.initial_heads = RasterHeads(raster_path="rasters/heads.tif")
    with pytest.raises(GeometryError) as info:
        initial_heads(site, grid)
    assert info.value.code == "geometry.raster_coverage"
    assert info.value.fields["n_cells"] == 5 * 15  # the five eastern columns


def test_dry_columns_are_a_warning(site: Project, grid: ModelGrid) -> None:
    # below the base of the model (0 m) in the five western columns
    write_raster(
        site.root / "rasters" / "heads.tif", lambda x, y: np.where(x < X0 + 1000, -5.0, 30.0)
    )
    site.config.initial_heads = RasterHeads(raster_path="rasters/heads.tif")
    heads = initial_heads(site, grid)
    assert [w.code for w in heads.warnings] == ["init.dry_columns"]
    assert "In 75 colonne" in heads.warnings[0].message.it
    assert "riga 1, colonna 1" in heads.warnings[0].message.it


def test_heads_below_the_top_unit_are_not_dry_columns(site: Project, grid: ModelGrid) -> None:
    # 35 m is below the copertura (40-50 m) but within the aquifer
    site.config.initial_heads = ConstantHeads(value_m=35.0)
    assert initial_heads(site, grid).warnings == ()


def test_missing_initial_heads(site: Project, grid: ModelGrid) -> None:
    site.config.initial_heads = None
    with pytest.raises(InitialHeadsError) as info:
        initial_heads(site, grid)
    assert info.value.code == "init.missing"


@pytest.mark.parametrize("settings", [InterpolatedHeads(), RunHeads(run_id="r1")])
def test_later_modes_are_not_available(
    site: Project, grid: ModelGrid, settings: InterpolatedHeads | RunHeads
) -> None:
    site.config.initial_heads = settings
    with pytest.raises(InitialHeadsError) as info:
        initial_heads(site, grid)
    assert info.value.code == "init.mode_not_available"
    assert info.value.fields["mode"] == settings.mode
