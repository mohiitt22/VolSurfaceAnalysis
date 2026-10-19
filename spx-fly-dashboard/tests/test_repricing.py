"""Unit tests for option repricing and slider reversibility."""

from __future__ import annotations

import pytest

from src.black_scholes import bs_price
from src.data_loader import (
    find_default_file,
    load_raw_dataset,
    transform_to_long_form,
    get_snapshot,
)
from src.fly_builder import build_all_butterflies
from src.iv_scenarios import IVShiftScenario
from src.repricing import reprice_all_butterflies


def test_premium_repricing_exact_formula():
    """Test D: Premium repricing consistency.

    For each leg:
    PremiumDifference = BS(OriginalIV + Shift) - BS(OriginalIV)
    Verify that the net fly premium change equals:
    Wing1PremiumDifference - 2*BodyPremiumDifference + Wing2PremiumDifference
    """
    path = find_default_file()
    raw = load_raw_dataset(path)
    long_df = transform_to_long_form(raw)
    snap = get_snapshot(long_df, "2026-08-03")

    shift_pts = 2.5
    scenario = IVShiftScenario(shift_vol_points=shift_pts)
    butterflies = build_all_butterflies(snap, wing_width=100.0)

    for fly in butterflies["call"]:
        s = fly.underlying
        t = fly.target_dte / 365.0
        side = fly.option_side

        p_low_orig = bs_price(side, s, fly.lower_strike, t, fly.lower_iv)
        p_low_shock = bs_price(side, s, fly.lower_strike, t, fly.lower_iv + scenario.shift_decimal)
        diff_low = p_low_shock - p_low_orig

        p_mid_orig = bs_price(side, s, fly.centre_strike, t, fly.middle_iv)
        p_mid_shock = bs_price(side, s, fly.centre_strike, t, fly.middle_iv + scenario.shift_decimal)
        diff_mid = p_mid_shock - p_mid_orig

        p_upp_orig = bs_price(side, s, fly.upper_strike, t, fly.upper_iv)
        p_upp_shock = bs_price(side, s, fly.upper_strike, t, fly.upper_iv + scenario.shift_decimal)
        diff_upp = p_upp_shock - p_upp_orig

        expected_fly_change = diff_low - 2.0 * diff_mid + diff_upp

        repriced = reprice_all_butterflies([fly], scenario)[0]
        assert pytest.approx(repriced.fly_premium_change, abs=1e-8) == expected_fly_change


def test_slider_reversibility():
    """Test E: Slider reversibility.

    Move slider: 0 → +3 → -2 → 0.
    The final curves must match the original baseline exactly.
    """
    path = find_default_file()
    raw = load_raw_dataset(path)
    long_df = transform_to_long_form(raw)
    snap = get_snapshot(long_df, "2026-08-03")

    butterflies = build_all_butterflies(snap, wing_width=100.0)
    calls = butterflies["call"]

    # Trajectory of scenarios
    shifts = [0.0, 3.0, -2.0, 0.0]
    last_rep = None
    for shift in shifts:
        scen = IVShiftScenario(shift_vol_points=shift)
        last_rep = reprice_all_butterflies(calls, scen)

    assert last_rep is not None
    for rep in last_rep:
        # At final 0.0, shocked premium must match original premium exactly
        assert pytest.approx(rep.shocked_fly_premium, abs=1e-10) == rep.fly.initial_fly_premium
        assert pytest.approx(rep.fly_premium_change, abs=1e-10) == 0.0
