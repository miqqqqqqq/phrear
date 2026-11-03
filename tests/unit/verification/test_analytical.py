"""Analytical solutions of the verification cases."""

from __future__ import annotations

import math

import numpy as np
import pytest

from phrear.verification import analytical


def test_well_function_against_tabulated_values() -> None:
    # E1(u) from Abramowitz and Stegun, table 5.1; E1(1e-4) from its series
    # (minus the Euler constant, -ln u, +u, -u²/4)
    u = np.array([1e-4, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0])
    expected = [8.6332247046, 4.0379295765, 1.8229239584, 0.5597735948, 0.2193839344,
                0.0489005107, 0.0011482956, 4.156969e-6]  # fmt: skip
    assert analytical.exp1(u) == pytest.approx(expected, rel=1e-8)


def test_flow_1d_satisfies_its_equation() -> None:
    xi = np.linspace(0.0, 1000.0, 11)
    h = analytical.flow_1d(xi, 1000.0, 20.0, 15.0, 0.001, 100.0)
    assert h[0] == pytest.approx(20.0) and h[-1] == pytest.approx(15.0)
    # T h'' = -N, exact for the quadratic with the central difference
    curvature = (h[2:] - 2 * h[1:-1] + h[:-2]) / 100.0**2
    assert curvature == pytest.approx(np.full(9, -0.001 / 100.0))


def test_thiem_vanishes_at_the_boundary_and_follows_ln_r() -> None:
    r = np.array([10.0, 100.0, 900.0])
    s = analytical.thiem(r, 500.0, 100.0, 900.0)
    assert s[-1] == pytest.approx(0.0, abs=1e-12)
    assert s[0] - s[1] == pytest.approx(500.0 / (2 * math.pi * 100.0) * math.log(10.0))


def test_theis_approaches_cooper_jacob_for_small_u() -> None:
    r, t, q, transmissivity, storage = 30.0, 10.0, 500.0, 100.0, 1e-3
    u = r**2 * storage / (4 * transmissivity * t)
    jacob = q / (4 * math.pi * transmissivity) * (-analytical.EULER - math.log(u))
    s = analytical.theis(np.array([r]), np.array([t]), q, transmissivity, storage)
    assert u < 0.01
    assert s[0] == pytest.approx(jacob, rel=1e-3)


def test_dupuit_tends_to_thiem_when_drawdown_is_small() -> None:
    r = np.array([50.0, 300.0])
    s_dupuit = analytical.dupuit_thiem(r, 1.0, 10.0, 900.0, 20.0)
    s_thiem = analytical.thiem(r, 1.0, 10.0 * 20.0, 900.0)
    assert s_dupuit == pytest.approx(s_thiem, rel=1e-3)
