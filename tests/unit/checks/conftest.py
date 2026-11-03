"""A complete model on the synthetic site, ready for the checks."""

from __future__ import annotations

import pytest
import shapely

from phrear.project import Project
from phrear.project.config import ConstantHeads

from ..boundaries.conftest import add_line, add_station, add_well, add_zone, center
from ..sites import X0, Y0

SOUTH = (X0 + 550.0, Y0 + 650.0)
NORTH = (X0 + 550.0, Y0 + 1850.0)


@pytest.fixture
def model_site(valid_site: Project) -> Project:
    """Parameters, initial heads, a fixed head line, a well and a recharge zone."""
    valid_site.config.initial_heads = ConstantHeads(value_m=30.0)
    valid_site.save()
    fid = add_line(valid_site, [SOUTH, NORTH])
    add_station(valid_site, "fixed_head_lines", fid, *SOUTH, value=30.0)
    add_well(valid_site, *center(7, 10), rate=5.0)
    add_zone(valid_site, shapely.box(X0, Y0, X0 + 3000, Y0 + 3000), rate=200.0)
    return Project.open(valid_site.root)
