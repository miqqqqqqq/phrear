"""Inspection of a project: stages, gathered errors, model checks."""

from __future__ import annotations

import pytest

from phrear.checks.base import Check
from phrear.checks.inspection import inspect_project
from phrear.checks.registry import CHECKS, register
from phrear.errors import Localized
from phrear.events import Problem
from phrear.project import Project, gpkg

from ..boundaries.conftest import add_well, center
from ..sites import X0, Y0, unit_fid


def _codes(problems: list[Problem]) -> list[str]:
    return [p.code for p in problems]


def test_complete_model_passes(model_site: Project) -> None:
    ins = inspect_project(model_site)
    assert ins.ok
    assert [s.status for s in ins.stages] == ["ok"] * 6
    assert set(ins.checks.values()) == {"ok"}
    assert _codes(ins.warnings) == ["geometry.thin_unit"]
    assert ins.boundaries is not None and ins.heads is not None and ins.layers is not None


def test_errors_of_several_units_are_gathered(model_site: Project) -> None:
    with gpkg.connect(model_site.gpkg_path) as conn:
        conn.execute(
            'DELETE FROM "param_values" WHERE (object_id = ? AND param = ?) '
            "OR (object_id = ? AND param = ?)",
            (unit_fid(model_site, 1), "sy", unit_fid(model_site, 2), "ss"),
        )
    ins = inspect_project(model_site)
    assert _codes(ins.stage("params").errors) == ["params.missing", "params.missing"]
    assert ins.stage("boundaries").skipped_for == ("params",)
    assert ins.checks["rates"] == "skipped" and ins.checks["newton_off"] == "ok"
    assert ins.params is None


def test_errors_of_several_features_are_gathered(model_site: Project) -> None:
    add_well(model_site, X0 + 100.0, Y0 + 100.0)  # outside
    add_well(model_site, *center(7, 4), screen_top=10.0, screen_bottom=45.0)  # inverted
    ins = inspect_project(model_site)
    assert _codes(ins.stage("boundaries").errors) == ["bc.outside_active", "bc.screen_order"]
    assert ins.boundaries is None
    assert not ins.ok


def test_failed_grid_skips_what_depends_on_it(model_site: Project) -> None:
    with gpkg.connect(model_site.gpkg_path) as conn:
        conn.execute('DELETE FROM "domain"')
    ins = inspect_project(model_site)
    assert _codes(ins.stage("grid").errors) == ["geometry.no_domain"]
    assert ins.stage("initial_heads").skipped_for == ("grid",)
    assert ins.stage("boundaries").skipped_for == ("grid",)
    assert ins.stage("params").status == "ok"


def test_missing_initial_heads(model_site: Project) -> None:
    model_site.config.initial_heads = None
    assert _codes(inspect_project(model_site).errors) == ["init.missing"]


def test_steady_period_needs_a_fixed_head(model_site: Project) -> None:
    with gpkg.connect(model_site.gpkg_path) as conn:
        conn.execute('UPDATE "fixed_head_lines" SET active = 0')
    ins = inspect_project(model_site)
    assert _codes(ins.errors) == ["check.no_fixed_head"]
    assert ins.checks["no_fixed_head"] == "errors"
    model_site.config.model.steady_initial = False
    assert inspect_project(model_site).ok


def test_well_in_a_fixed_head_cell(model_site: Project) -> None:
    add_well(model_site, *center(7, 0))
    ins = inspect_project(model_site)
    assert "check.well_in_fixed_head" in _codes(ins.warnings)
    assert ins.ok


@pytest.mark.parametrize(
    ("layer", "fields", "code"),
    [
        ("wells", {"rate": 500.0}, "check.well_rate_high"),
        ("recharge_zones", {"rate": 5000.0}, "check.recharge_high"),
        ("recharge_zones", {"rate": 0.5}, "check.recharge_low"),
    ],
)
def test_suspicious_magnitudes(
    model_site: Project, layer: str, fields: dict[str, float], code: str
) -> None:
    with gpkg.connect(model_site.gpkg_path) as conn:
        conn.execute(f'UPDATE "{layer}" SET rate = ?', (fields["rate"],))
    warnings = _codes(inspect_project(model_site).warnings)
    assert code in warnings


def test_newton_off_with_convertible_units(model_site: Project) -> None:
    model_site.config.options.newton = False
    (problem,) = [p for p in inspect_project(model_site).warnings if p.code == "check.newton_off"]
    assert "1 (copertura)" in problem.message.it


def test_registry() -> None:
    assert list(CHECKS) == ["no_fixed_head", "well_in_fixed_head", "rates", "newton_off"]
    clash = Check("rates", Localized("x", "x"), "warning", (), lambda ins: [])
    with pytest.raises(ValueError, match="already registered"):
        register(clash)
