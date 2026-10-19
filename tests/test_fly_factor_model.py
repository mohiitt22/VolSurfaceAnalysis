"""Mathematical invariant and scenario validation tests for Level, Skew, and Curvature simulation."""

from __future__ import annotations

import pytest
import numpy as np

from spx_butterfly.data_loader import (
    find_default_file,
    load_raw_dataset,
    transform_to_long_form,
    get_available_dates,
    get_snapshot,
)
from spx_butterfly.fly_builder import build_all_butterflies
from spx_butterfly.iv_scenarios import (
    IVShiftScenario,
    compute_normalized_strike,
    compute_strike_iv_shock,
    apply_iv_scenario,
    apply_iv_shift,
)
from spx_butterfly.repricing import (
    reprice_butterfly,
    reprice_all_butterflies,
)


@pytest.fixture(scope="module")
def snapshot_aug3():
    """Load and return August 3, 2026 snapshot."""
    path = find_default_file()
    raw = load_raw_dataset(path)
    long_df = transform_to_long_form(raw)
    return get_snapshot(long_df, "2026-08-03"), long_df


def test_test1_all_sliders_zero(snapshot_aug3):
    """Test 1: All sliders zero (L = 0, S = 0, C = 0).

    Expected:
    - New IV equals original IV at every strike.
    - New option premium equals original Excel premium in baseline-adjusted mode.
    - New fly premium equals original fly premium.
    - Change in IV fly equals zero.
    - Change in fly premium equals zero.
    """
    snap, _ = snapshot_aug3
    atm0 = float(snap["atm_strike"].iloc[0])
    scenario = IVShiftScenario(level_vol_points=0.0, skew_vol_points=0.0, curvature_vol_points=0.0, atm_strike=atm0)

    butterflies = build_all_butterflies(snap, wing_width=100.0)
    for side in ("call", "put"):
        repriced = reprice_all_butterflies(butterflies[side], scenario, pricing_mode="baseline_delta")
        for rep in repriced:
            assert pytest.approx(rep.lower_shocked_iv, abs=1e-10) == rep.fly.lower_iv
            assert pytest.approx(rep.middle_shocked_iv, abs=1e-10) == rep.fly.middle_iv
            assert pytest.approx(rep.upper_shocked_iv, abs=1e-10) == rep.fly.upper_iv

            assert pytest.approx(rep.lower_shocked_premium, abs=1e-8) == rep.fly.lower_premium
            assert pytest.approx(rep.middle_shocked_premium, abs=1e-8) == rep.fly.middle_premium
            assert pytest.approx(rep.upper_shocked_premium, abs=1e-8) == rep.fly.upper_premium

            assert pytest.approx(rep.shocked_fly_premium, abs=1e-8) == rep.fly.initial_fly_premium
            assert pytest.approx(rep.fly_premium_change, abs=1e-8) == 0.0
            assert pytest.approx(rep.shocked_iv_fly_pct, abs=1e-10) == rep.fly.initial_iv_fly_pct


def test_test2_pure_level(snapshot_aug3):
    """Test 2: Pure level (L = +2, S = 0, C = 0).

    Expected:
    - Every IV increases by exactly 2 percentage points.
    - All IV fly second differences remain unchanged (ΔIVFly = 0).
    - All option premiums are fully repriced.
    - Fly premiums change nonuniformly.
    """
    snap, _ = snapshot_aug3
    atm0 = float(snap["atm_strike"].iloc[0])
    scenario = IVShiftScenario(level_vol_points=2.0, skew_vol_points=0.0, curvature_vol_points=0.0, atm_strike=atm0)

    butterflies = build_all_butterflies(snap, wing_width=100.0)
    for side in ("call", "put"):
        repriced = reprice_all_butterflies(butterflies[side], scenario)
        for rep in repriced:
            assert pytest.approx(rep.lower_shocked_iv - rep.fly.lower_iv, abs=1e-10) == 0.02
            assert pytest.approx(rep.middle_shocked_iv - rep.fly.middle_iv, abs=1e-10) == 0.02
            assert pytest.approx(rep.upper_shocked_iv - rep.fly.upper_iv, abs=1e-10) == 0.02

            diff_iv_fly = rep.shocked_iv_fly_pct - rep.fly.initial_iv_fly_pct
            assert pytest.approx(diff_iv_fly, abs=1e-10) == 0.0

    # Verify fly premiums change nonuniformly across strikes
    calls_rep = reprice_all_butterflies(butterflies["call"], scenario)
    changes = [r.fly_premium_change for r in calls_rep]
    assert len(set(round(c, 4) for c in changes)) > 1


def test_test3_pure_skew(snapshot_aug3):
    """Test 3: Pure skew (L = 0, S = -2, C = 0, H = 500).

    Expected:
    - ATM-500 shock = +1 vol point.
    - ATM shock = 0.
    - ATM+500 shock = -1 vol point.
    - Every complete 100-point-strike IV fly remains unchanged (ΔIVFly = 0).
    - The fly premium curves are recalculated rather than kept constant.
    """
    snap, _ = snapshot_aug3
    atm0 = float(snap["atm_strike"].iloc[0])
    scenario = IVShiftScenario(
        level_vol_points=0.0, skew_vol_points=-2.0, curvature_vol_points=0.0, reference_width=500.0, atm_strike=atm0
    )

    # Specific strike checks
    tot_atm, _ = compute_strike_iv_shock(atm0, scenario)
    tot_minus500, _ = compute_strike_iv_shock(atm0 - 500.0, scenario)
    tot_plus500, _ = compute_strike_iv_shock(atm0 + 500.0, scenario)

    assert pytest.approx(tot_atm, abs=1e-10) == 0.0
    assert pytest.approx(tot_minus500, abs=1e-10) == 1.0
    assert pytest.approx(tot_plus500, abs=1e-10) == -1.0

    # Curvature invariant under pure skew: ΔIVFly == 0 for all equal 100-pt strike flies
    butterflies = build_all_butterflies(snap, wing_width=100.0)
    for side in ("call", "put"):
        repriced = reprice_all_butterflies(butterflies[side], scenario)
        for rep in repriced:
            diff_iv_fly = rep.shocked_iv_fly_pct - rep.fly.initial_iv_fly_pct
            assert pytest.approx(diff_iv_fly, abs=1e-10) == 0.0


def test_test4_pure_curvature(snapshot_aug3):
    """Test 4: Pure curvature (L = 0, S = 0, C = +1, h = 100, H = 500).

    Expected:
    - Change in IV Fly = 2 * C * (h / H)^2 = 2 * 1 * (100 / 500)^2 = +0.08 vol points.
    - If C = -1, Change in IV Fly = -0.08 vol points.
    """
    snap, _ = snapshot_aug3
    atm0 = float(snap["atm_strike"].iloc[0])
    butterflies = build_all_butterflies(snap, wing_width=100.0)

    # Positive Curvature: C = +1.0
    scen_pos = IVShiftScenario(
        level_vol_points=0.0, skew_vol_points=0.0, curvature_vol_points=1.0, reference_width=500.0, atm_strike=atm0
    )
    for side in ("call", "put"):
        repriced = reprice_all_butterflies(butterflies[side], scen_pos)
        for rep in repriced:
            diff_iv_fly = rep.shocked_iv_fly_pct - rep.fly.initial_iv_fly_pct
            assert pytest.approx(diff_iv_fly, abs=1e-10) == 0.08

    # Negative Curvature: C = -1.0
    scen_neg = IVShiftScenario(
        level_vol_points=0.0, skew_vol_points=0.0, curvature_vol_points=-1.0, reference_width=500.0, atm_strike=atm0
    )
    for side in ("call", "put"):
        repriced = reprice_all_butterflies(butterflies[side], scen_neg)
        for rep in repriced:
            diff_iv_fly = rep.shocked_iv_fly_pct - rep.fly.initial_iv_fly_pct
            assert pytest.approx(diff_iv_fly, abs=1e-10) == -0.08


def test_test5_combined_scenario(snapshot_aug3):
    """Test 5: Combined scenario (L = +2, S = -2, C = +1, ATM = 7630, H = 500).

    Verify:
    - Strike 7630: +2.00 vol-point shock.
    - Strike 7730: +1.84 vol-point shock.
    - Strike 7830: +1.76 vol-point shock.
    - Strike 7530: +2.24 vol-point shock.
    - Strike 7430: +2.56 vol-point shock.
    - Every complete 100-pt fly's IV second difference increases by +0.08 vol points.
    - Sequential attribution sums exactly to total repriced change.
    - Shapley attribution sums exactly to total repriced change.
    """
    snap, _ = snapshot_aug3
    atm0 = 7630.0
    scenario = IVShiftScenario(
        level_vol_points=2.0, skew_vol_points=-2.0, curvature_vol_points=1.0, reference_width=500.0, atm_strike=atm0
    )

    expected_shocks = {
        7630.0: 2.00,
        7730.0: 1.84,
        7830.0: 1.76,
        7530.0: 2.24,
        7430.0: 2.56,
    }

    for strike, exp_shock in expected_shocks.items():
        tot, _ = compute_strike_iv_shock(strike, scenario)
        assert pytest.approx(tot, abs=1e-8) == exp_shock

    # Invariant: ΔIVFly = +0.08 vol pts for all flies
    butterflies = build_all_butterflies(snap, wing_width=100.0)
    for side in ("call", "put"):
        repriced = reprice_all_butterflies(butterflies[side], scenario)
        for rep in repriced:
            diff_iv_fly = rep.shocked_iv_fly_pct - rep.fly.initial_iv_fly_pct
            assert pytest.approx(diff_iv_fly, abs=1e-10) == 0.08

            # Sequential attribution sum
            seq_sum = rep.level_effect + rep.skew_effect + rep.curvature_effect
            assert pytest.approx(seq_sum, abs=1e-10) == rep.fly_premium_change

            # Shapley attribution sum
            shap_sum = rep.shapley_level + rep.shapley_skew + rep.shapley_curvature
            assert pytest.approx(shap_sum, abs=1e-10) == rep.fly_premium_change


def test_test6_reversibility(snapshot_aug3):
    """Test 6: Reversibility.

    Move sliders through multiple scenarios:
    (0, 0, 0) -> (+2, -1, +0.5) -> (-3, +2, -1) -> (0, 0, 0)
    Verify that original premiums and IVs return exactly to baseline.
    """
    snap, _ = snapshot_aug3
    atm0 = float(snap["atm_strike"].iloc[0])
    butterflies = build_all_butterflies(snap, wing_width=100.0)
    fly = butterflies["call"][0]

    scenarios = [
        IVShiftScenario(0.0, 0.0, 0.0, 500.0, atm0),
        IVShiftScenario(2.0, -1.0, 0.5, 500.0, atm0),
        IVShiftScenario(-3.0, 2.0, -1.0, 500.0, atm0),
        IVShiftScenario(0.0, 0.0, 0.0, 500.0, atm0),
    ]

    for sc in scenarios:
        rep = reprice_butterfly(fly, sc)

    # Final scenario is (0, 0, 0)
    assert pytest.approx(rep.shocked_fly_premium, abs=1e-10) == fly.initial_fly_premium
    assert pytest.approx(rep.fly_premium_change, abs=1e-10) == 0.0
    assert pytest.approx(rep.lower_shocked_iv, abs=1e-10) == fly.lower_iv
    assert pytest.approx(rep.middle_shocked_iv, abs=1e-10) == fly.middle_iv
    assert pytest.approx(rep.upper_shocked_iv, abs=1e-10) == fly.upper_iv


def test_test7_date_independence(snapshot_aug3):
    """Test 7: Date independence.

    Select August 3, then August 4 (or another available date).
    Rebuild reference ATM strike and all x coordinates for the new date.
    Ensure changing sliders does not cross-contaminate baseline across dates.
    """
    _, long_df = snapshot_aug3
    dates = get_available_dates(long_df)
    assert len(dates) >= 2

    d1, d2 = dates[0], dates[1]
    snap1 = get_snapshot(long_df, d1)
    snap2 = get_snapshot(long_df, d2)

    atm1 = float(snap1["atm_strike"].iloc[0])
    atm2 = float(snap2["atm_strike"].iloc[0])

    scen1 = IVShiftScenario(1.0, -1.0, 0.5, 500.0, atm1)
    scen2 = IVShiftScenario(1.0, -1.0, 0.5, 500.0, atm2)

    flies1 = build_all_butterflies(snap1, wing_width=100.0)["call"]
    flies2 = build_all_butterflies(snap2, wing_width=100.0)["call"]

    rep1 = reprice_all_butterflies(flies1, scen1)
    rep2 = reprice_all_butterflies(flies2, scen2)

    # Ensure baseline parameters are strictly preserved and date-specific
    for r1 in rep1:
        assert r1.fly.date == d1
        assert r1.fly.atm_strike == atm1
    for r2 in rep2:
        assert r2.fly.date == d2
        assert r2.fly.atm_strike == atm2


def test_test8_finite_difference_factor_sensitivities(snapshot_aug3):
    """Test 8: Finite-difference factor Greek verification.

    Numerically perturb Level, Skew, and Curvature by small epsilon = 1e-4
    and confirm that analytical factor sensitivities agree with finite-difference repricing.
    """
    snap, _ = snapshot_aug3
    atm0 = float(snap["atm_strike"].iloc[0])
    butterflies = build_all_butterflies(snap, wing_width=100.0)["call"]
    fly = butterflies[0]

    base_scen = IVShiftScenario(0.0, 0.0, 0.0, 500.0, atm0)
    rep_base = reprice_butterfly(fly, base_scen)

    eps = 1e-4

    # 1. Level sensitivity check: dPremium / dLevel
    scen_l_up = IVShiftScenario(eps, 0.0, 0.0, 500.0, atm0)
    scen_l_dn = IVShiftScenario(-eps, 0.0, 0.0, 500.0, atm0)
    fd_level = (reprice_butterfly(fly, scen_l_up).shocked_fly_premium - reprice_butterfly(fly, scen_l_dn).shocked_fly_premium) / (2.0 * eps)
    assert pytest.approx(rep_base.level_exposure, rel=1e-3, abs=1e-4) == fd_level

    # 2. Skew sensitivity check: dPremium / dSkew
    scen_s_up = IVShiftScenario(0.0, eps, 0.0, 500.0, atm0)
    scen_s_dn = IVShiftScenario(0.0, -eps, 0.0, 500.0, atm0)
    fd_skew = (reprice_butterfly(fly, scen_s_up).shocked_fly_premium - reprice_butterfly(fly, scen_s_dn).shocked_fly_premium) / (2.0 * eps)
    assert pytest.approx(rep_base.skew_exposure, rel=1e-3, abs=1e-4) == fd_skew

    # 3. Curvature sensitivity check: dPremium / dCurvature
    scen_c_up = IVShiftScenario(0.0, 0.0, eps, 500.0, atm0)
    scen_c_dn = IVShiftScenario(0.0, 0.0, -eps, 500.0, atm0)
    fd_curv = (reprice_butterfly(fly, scen_c_up).shocked_fly_premium - reprice_butterfly(fly, scen_c_dn).shocked_fly_premium) / (2.0 * eps)
    assert pytest.approx(rep_base.curvature_exposure, rel=1e-3, abs=1e-4) == fd_curv
