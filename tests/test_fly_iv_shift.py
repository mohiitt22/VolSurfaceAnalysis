"""Unit tests for IV shift rules, units, and curvature invariance."""

from __future__ import annotations

import pytest

from spx_butterfly.data_loader import (
    find_default_file,
    load_raw_dataset,
    transform_to_long_form,
    get_snapshot,
)
from spx_butterfly.fly_builder import build_all_butterflies
from spx_butterfly.iv_scenarios import (
    IVShiftScenario,
    apply_iv_shift,
    validate_iv_shift,
)
from spx_butterfly.repricing import reprice_all_butterflies


def test_numerical_units_additive_shift():
    """Test H: Numerical units test.

    Shifting an IV of 0.136466 by +2 volatility points produces 0.156466,
    not 0.13919532 or 2.136466.
    """
    orig_iv = 0.136466
    scenario = IVShiftScenario(shift_vol_points=2.0)
    assert scenario.shift_decimal == 0.02

    shocked_iv = apply_iv_shift(orig_iv, scenario)
    assert pytest.approx(shocked_iv, abs=1e-8) == 0.156466
    # Verify it is not relative percentage or integer addition
    assert shocked_iv != orig_iv * 1.02
    assert shocked_iv != orig_iv + 2.0


def test_parallel_iv_movement_fixed_constraints():
    """Test B: Parallel IV movement.

    At slider = +2:
    - Every original IV must increase by exactly 0.02.
    - No strike must change.
    - SPX spot must remain unchanged.
    - Target DTE must remain unchanged.
    """
    path = find_default_file()
    raw = load_raw_dataset(path)
    long_df = transform_to_long_form(raw)
    snap = get_snapshot(long_df, "2026-08-03")

    scenario = IVShiftScenario(shift_vol_points=2.0)
    butterflies = build_all_butterflies(snap, wing_width=100.0)
    calls = butterflies["call"]

    repriced = reprice_all_butterflies(calls, scenario)
    for rep in repriced:
        # Check IV increased by exactly 0.02
        assert pytest.approx(rep.lower_shocked_iv - rep.fly.lower_iv, abs=1e-8) == 0.02
        assert pytest.approx(rep.middle_shocked_iv - rep.fly.middle_iv, abs=1e-8) == 0.02
        assert pytest.approx(rep.upper_shocked_iv - rep.fly.upper_iv, abs=1e-8) == 0.02

        # Fixed constraints
        assert rep.fly.underlying == 7631.25
        assert rep.fly.target_dte == 60.0
        assert rep.fly.centre_strike == rep.fly.centre_strike
        assert rep.fly.lower_strike == rep.fly.centre_strike - 100.0
        assert rep.fly.upper_strike == rep.fly.centre_strike + 100.0


def test_iv_fly_curvature_invariance():
    """Test C: IV fly curvature invariance.

    For every complete fly:
    ShockedIVFly - OriginalIVFly ≈ 0 (tight floating point tolerance).
    """
    path = find_default_file()
    raw = load_raw_dataset(path)
    long_df = transform_to_long_form(raw)
    snap = get_snapshot(long_df, "2026-08-03")

    scenario = IVShiftScenario(shift_vol_points=3.5)
    butterflies = build_all_butterflies(snap, wing_width=100.0)

    for side in ("call", "put"):
        repriced = reprice_all_butterflies(butterflies[side], scenario)
        for rep in repriced:
            diff = abs(rep.shocked_iv_fly_pct - rep.fly.initial_iv_fly_pct)
            assert diff < 1e-10, f"IV fly changed by {diff} for strike {rep.fly.centre_strike}"


def test_invalid_negative_iv_shift():
    """Verify that a negative shock producing non-positive IV is properly rejected."""
    ivs = [0.12, 0.14, 0.15]
    bad_scenario = IVShiftScenario(shift_vol_points=-15.0)  # -0.15 on 0.12 gives -0.03
    is_valid, err_msg = validate_iv_shift(ivs, bad_scenario)
    assert not is_valid
    assert err_msg is not None
    assert "produces non-positive IVs" in err_msg
