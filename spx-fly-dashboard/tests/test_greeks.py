"""Unit tests for Black-Scholes analytical Greeks vs finite differences."""

from __future__ import annotations

import pytest
import numpy as np

from src.black_scholes import bs_price
from src.greeks import calc_greeks


def test_analytical_vega_and_volga_vs_finite_difference():
    """Test G: Greeks validation.

    Verify analytical vega and volga calculations against numerical finite differences.
    """
    s = 7631.25
    k = 7730.0
    t = 60.0 / 365.0
    sigma = 0.129442
    r = 0.0
    q = 0.0

    greeks = calc_greeks("call", s, k, t, sigma, r=r, q=q)
    analytical_vega_pt = greeks["vega"]
    analytical_volga_pt = greeks["volga"]

    # Finite difference step (0.0001 decimal = 0.01 vol point)
    h_dec = 1e-4
    h_pts = h_dec * 100.0  # 0.01 vol point

    p_plus = bs_price("call", s, k, t, sigma + h_dec, r=r, q=q)
    p_minus = bs_price("call", s, k, t, sigma - h_dec, r=r, q=q)
    p_center = bs_price("call", s, k, t, sigma, r=r, q=q)

    # First derivative w.r.t vol points: dPrice / d(vol_pts)
    fd_vega_pt = (p_plus - p_minus) / (2.0 * h_pts)

    # Second derivative w.r.t (vol points)^2: d2Price / d(vol_pts)^2
    fd_volga_pt = (p_plus - 2.0 * p_center + p_minus) / (h_pts ** 2)

    assert pytest.approx(analytical_vega_pt, rel=1e-4) == fd_vega_pt
    assert pytest.approx(analytical_volga_pt, rel=1e-3) == fd_volga_pt


def test_delta_and_gamma_vs_finite_difference():
    """Verify Delta and Gamma against finite differences in spot."""
    s = 7631.25
    k = 7730.0
    t = 60.0 / 365.0
    sigma = 0.129442
    r = 0.01
    q = 0.015

    g = calc_greeks("call", s, k, t, sigma, r=r, q=q)
    ds = 0.1

    p_up = bs_price("call", s + ds, k, t, sigma, r=r, q=q)
    p_dn = bs_price("call", s - ds, k, t, sigma, r=r, q=q)
    p_0 = bs_price("call", s, k, t, sigma, r=r, q=q)

    fd_delta = (p_up - p_dn) / (2.0 * ds)
    fd_gamma = (p_up - 2.0 * p_0 + p_dn) / (ds ** 2)

    assert pytest.approx(g["delta"], rel=1e-4) == fd_delta
    assert pytest.approx(g["gamma"], rel=1e-3) == fd_gamma
