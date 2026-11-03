"""Analytical solutions of the verification cases.

Symbols: Q pumping rate [m³/d], T transmissivity [m²/d], K hydraulic conductivity
[m/d], S storage coefficient [-], R radius of the fixed-head boundary [m], r
distance from the well [m], t time since pumping started [d].
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
EULER = 0.5772156649015329


def exp1(u: FloatArray) -> FloatArray:
    """Exponential integral E1(u) = ∫_u^∞ e^(-x)/x dx, the Theis well function W(u).

    Power series for u ≤ 1, continued fraction (modified Lentz) for u > 1;
    relative error below 1e-12.
    """
    u = np.asarray(u, dtype=np.float64)
    out = np.empty_like(u)
    small = u <= 1.0
    us = u[small]
    total = -EULER - np.log(us)
    term = np.ones_like(us)
    for k in range(1, 60):
        term = term * (-us) / k
        total = total - term / k
    out[small] = total
    ul = u[~small]
    b = ul + 1.0
    c = np.full_like(ul, 1e300)
    d = 1.0 / b
    h = d.copy()
    for i in range(1, 200):
        a = -float(i * i)
        b = b + 2.0
        d = 1.0 / (a * d + b)
        c = b + a / c
        h = h * c * d
    out[~small] = h * np.exp(-ul)
    return out


def flow_1d(xi: FloatArray, length: float, h1: float, h2: float, recharge: float,
            transmissivity: float) -> FloatArray:  # fmt: skip
    """Confined 1D flow between fixed heads h1 (ξ = 0) and h2 (ξ = L) with recharge N [m/d].

    T h'' = -N gives h = h1 + (h2 - h1) ξ/L + N ξ (L - ξ) / (2T).
    """
    return h1 + (h2 - h1) * xi / length + recharge * xi * (length - xi) / (2.0 * transmissivity)


def thiem(r: FloatArray, rate: float, transmissivity: float, radius: float) -> FloatArray:
    """Steady confined drawdown s = Q/(2πT) ln(R/r)."""
    return rate / (2.0 * math.pi * transmissivity) * np.log(radius / r)


def theis(r: FloatArray, t: FloatArray, rate: float, transmissivity: float,
          storage: float) -> FloatArray:  # fmt: skip
    """Transient confined drawdown s = Q/(4πT) W(u), u = r² S / (4 T t)."""
    u = r**2 * storage / (4.0 * transmissivity * t)
    return rate / (4.0 * math.pi * transmissivity) * exp1(u)


def dupuit_thiem(r: FloatArray, rate: float, conductivity: float, radius: float,
                 head: float) -> FloatArray:  # fmt: skip
    """Steady unconfined drawdown, from h_R² - h² = Q/(πK) ln(R/r), above a flat base at 0."""
    squared = head**2 - rate / (math.pi * conductivity) * np.log(radius / r)
    return head - np.sqrt(squared)
