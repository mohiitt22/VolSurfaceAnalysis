"""Automated validation tests for the Multi-Date Surface Comparison Workspace.

Covers all 12 requirements specified in Part P:
1. Multi-date loading (Aug 3 & Aug 4)
2. Correct ATM-relative and absolute-strike alignment
3. Reference factor changes (ΔLevel = +0.6082, ΔSkew = +1.0832, ΔCurvature = -0.0202)
4. Exact factor reconstruction identity at all shared nodes
5. Anchor conditions (zero residuals at ATM and ATM±H)
6. Fly premiums on Aug 3 (~12.147) and Aug 4 (~10.8533)
7. Missing ATM put handling and omission of invalid flies
8. Focus date highlighting and state consistency
9. Reference date switching and self-comparison zero identity
10. Exact premium factor attribution identity (Total = L + S + C + Residual)
11. Historical data immutability under scenario calculations
12. Large date selections performance and cached stability
"""

from __future__ import annotations

import pytest
import numpy as np
import pandas as pd

from spx_butterfly.data_loader import (
    find_default_file,
    load_raw_dataset,
    transform_to_long_form,
    get_available_dates,
    get_snapshot,
)
from spx_butterfly.multidate_model import (
    calculate_daily_factors,
    compute_multidate_factors_table,
    fit_factors_between_dates,
    decompose_iv_smile,
    build_multidate_flies,
    compute_observed_fly_differences,
    compute_fixed_fly_attribution,
    extract_smile_points,
    get_iv_at_offset,
)


@pytest.fixture(scope="module")
def shared_long_df() -> pd.DataFrame:
    path = find_default_file()
    assert path is not None and path.exists(), "Default dataset must exist."
    raw = load_raw_dataset(path)
    return transform_to_long_form(raw)


def test_1_multidate_loading(shared_long_df: pd.DataFrame):
    """Test 1 — Multi-date loading.

    Select Aug 3 and Aug 4: both smiles exist and call/put fly curves exist.
    """
    dates = get_available_dates(shared_long_df)
    assert "2026-08-03" in dates
    assert "2026-08-04" in dates

    snap3 = get_snapshot(shared_long_df, "2026-08-03")
    snap4 = get_snapshot(shared_long_df, "2026-08-04")
    assert not snap3.empty
    assert not snap4.empty

    smile3 = extract_smile_points(snap3)
    smile4 = extract_smile_points(snap4)
    assert len(smile3) >= 19
    assert len(smile4) >= 19

    flies = build_multidate_flies(shared_long_df, ["2026-08-03", "2026-08-04"], strict_market_puts=True)
    assert "2026-08-03" in flies
    assert "2026-08-04" in flies

    calls_3 = [f for f in flies["2026-08-03"] if f.option_side == "call"]
    puts_3 = [f for f in flies["2026-08-03"] if f.option_side == "put"]
    assert len(calls_3) >= 8
    assert len(puts_3) >= 7


def test_2_correct_atm_relative_alignment(shared_long_df: pd.DataFrame):
    """Test 2 — Correct ATM-relative alignment.

    August 3 ATM = 7630, ATM+100 = 7730.
    August 4 ATM = 7775, ATM+100 = 7875.
    Both must appear at x = +100 in ATM-relative mode.
    In absolute-strike mode, they appear at 7730 and 7875.
    """
    snap3 = get_snapshot(shared_long_df, "2026-08-03")
    snap4 = get_snapshot(shared_long_df, "2026-08-04")

    smile3 = extract_smile_points(snap3)
    smile4 = extract_smile_points(snap4)

    row3_100 = smile3[smile3["atm_offset"] == 100.0]
    row4_100 = smile4[smile4["atm_offset"] == 100.0]

    assert len(row3_100) == 1
    assert len(row4_100) == 1

    # In ATM-relative mode, both are at offset +100
    assert row3_100["atm_offset"].iloc[0] == 100.0
    assert row4_100["atm_offset"].iloc[0] == 100.0

    # In absolute-strike mode, actual strikes differ
    assert row3_100["strike"].iloc[0] == 7730.0
    assert row4_100["strike"].iloc[0] == 7875.0


def test_3_reference_factors(shared_long_df: pd.DataFrame):
    """Test 3 — Reference factors.

    For Aug 3 vs Aug 4 with H = 500, verify approximately:
    DeltaLevel = +0.6082
    DeltaSkew = +1.0832
    DeltaCurvature = -0.0202
    """
    snap3 = get_snapshot(shared_long_df, "2026-08-03")
    snap4 = get_snapshot(shared_long_df, "2026-08-04")

    f3 = calculate_daily_factors(snap3, h_width=500.0)
    f4 = calculate_daily_factors(snap4, h_width=500.0)

    # August 3 factors
    assert pytest.approx(f3["level"], abs=1e-4) == 13.6466
    assert pytest.approx(f3["skew"], abs=1e-4) == -6.7855
    assert pytest.approx(f3["curvature"], abs=1e-4) == 1.54205

    # August 4 factors
    assert pytest.approx(f4["level"], abs=1e-4) == 14.2548
    assert pytest.approx(f4["skew"], abs=1e-4) == -5.7023
    assert pytest.approx(f4["curvature"], abs=1e-4) == 1.52185

    # Difference Aug 4 minus Aug 3
    d_level = f4["level"] - f3["level"]
    d_skew = f4["skew"] - f3["skew"]
    d_curv = f4["curvature"] - f3["curvature"]

    assert pytest.approx(d_level, abs=1e-4) == 0.6082
    assert pytest.approx(d_skew, abs=1e-4) == 1.0832
    assert pytest.approx(d_curv, abs=1e-4) == -0.0202


def test_4_exact_factor_reconstruction(shared_long_df: pd.DataFrame):
    """Test 4 — Exact factor reconstruction.

    At all shared offset nodes:
    ObservedIVChange = LevelContribution + SkewContribution + CurvatureContribution + Residual
    within numerical tolerance.
    """
    snap3 = get_snapshot(shared_long_df, "2026-08-03")
    snap4 = get_snapshot(shared_long_df, "2026-08-04")

    factors = fit_factors_between_dates(snap3, snap4, h_width=500.0, method="anchor")
    points = decompose_iv_smile(snap3, snap4, factors, h_width=500.0)

    assert len(points) >= 19
    for pt in points:
        reconstructed = pt.level_comp + pt.skew_comp + pt.curvature_comp + pt.residual
        assert pytest.approx(pt.observed_change, abs=1e-12) == reconstructed


def test_5_anchor_conditions(shared_long_df: pd.DataFrame):
    """Test 5 — Anchor conditions.

    For anchor-based factor estimation, residuals at ATM (offset 0) and
    ATM±H (offsets -500 and +500) must be approximately zero.
    """
    snap3 = get_snapshot(shared_long_df, "2026-08-03")
    snap4 = get_snapshot(shared_long_df, "2026-08-04")

    factors = fit_factors_between_dates(snap3, snap4, h_width=500.0, method="anchor")
    points = decompose_iv_smile(snap3, snap4, factors, h_width=500.0)

    pt_atm = next(p for p in points if p.atm_offset == 0.0)
    pt_left = next(p for p in points if p.atm_offset == -500.0)
    pt_right = next(p for p in points if p.atm_offset == 500.0)

    assert pytest.approx(pt_atm.residual, abs=1e-10) == 0.0
    assert pytest.approx(pt_left.residual, abs=1e-10) == 0.0
    assert pytest.approx(pt_right.residual, abs=1e-10) == 0.0


def test_6_fly_premiums(shared_long_df: pd.DataFrame):
    """Test 6 — Fly premiums.

    Aug 3 call fly centred at ATM+100 (7730):
    169.0354117 - 2*116.2152414 + 75.54206948 ~ 12.147.

    Aug 4 call fly centred at ATM+100 (7875):
    179.113787 - 2*128.423022 + 88.585515 ~ 10.8533.
    """
    flies = build_multidate_flies(shared_long_df, ["2026-08-03", "2026-08-04"])

    call3_100 = next(f for f in flies["2026-08-03"] if f.option_side == "call" and f.centre_strike == 7730.0)
    assert pytest.approx(call3_100.fly_premium, abs=1e-3) == 12.147

    call4_100 = next(f for f in flies["2026-08-04"] if f.option_side == "call" and f.centre_strike == 7875.0)
    assert pytest.approx(call4_100.fly_premium, abs=1e-3) == 10.8533


def test_7_missing_atm_put_handling(shared_long_df: pd.DataFrame):
    """Test 7 — Missing ATM put handling.

    When strict_market_puts is True, ATM-100 put fly is omitted because ATM put quote
    is unavailable in the market file (upper leg missing).
    Other complete put flies (ATM-200 to ATM-800) must still exist.
    """
    flies_strict = build_multidate_flies(shared_long_df, ["2026-08-03"], strict_market_puts=True)
    puts_strict = [f for f in flies_strict["2026-08-03"] if f.option_side == "put"]

    # ATM-100 is centre 7530; upper wing is 7630 (ATM)
    assert not any(f.centre_strike == 7530.0 for f in puts_strict), "ATM-100 put fly must be omitted in strict market mode"
    # ATM-200 to ATM-800 must all exist
    expected_centres = [7430.0, 7330.0, 7230.0, 7130.0, 7030.0, 6930.0, 6830.0]
    present_centres = [f.centre_strike for f in puts_strict]
    for exp_k in expected_centres:
        assert exp_k in present_centres

    # Non-strict mode should include it
    flies_synth = build_multidate_flies(shared_long_df, ["2026-08-03"], strict_market_puts=False)
    puts_synth = [f for f in flies_synth["2026-08-03"] if f.option_side == "put"]
    assert any(f.centre_strike == 7530.0 for f in puts_synth)


def test_8_date_highlighting(shared_long_df: pd.DataFrame):
    """Test 8 — Date highlighting and focus updates."""
    snap3 = get_snapshot(shared_long_df, "2026-08-03")
    snap4 = get_snapshot(shared_long_df, "2026-08-04")

    # Focus Aug 4 vs Ref Aug 3
    factors4 = fit_factors_between_dates(snap3, snap4, h_width=500.0)
    assert factors4.focus_date == "2026-08-04"
    assert pytest.approx(factors4.delta_level, abs=1e-4) == 0.6082

    # Switch focus to Aug 5 (if available) or check consistency
    dates = get_available_dates(shared_long_df)
    if "2026-08-05" in dates:
        snap5 = get_snapshot(shared_long_df, "2026-08-05")
        factors5 = fit_factors_between_dates(snap3, snap5, h_width=500.0)
        assert factors5.focus_date == "2026-08-05"
        assert factors5.reference_date == "2026-08-03"


def test_9_factor_decomposition_ref_switch(shared_long_df: pd.DataFrame):
    """Test 9 — Factor decomposition and self-comparison identity.

    Choosing the same date as reference and focus produces zero change everywhere.
    """
    snap3 = get_snapshot(shared_long_df, "2026-08-03")
    self_factors = fit_factors_between_dates(snap3, snap3, h_width=500.0)

    assert pytest.approx(self_factors.delta_level, abs=1e-12) == 0.0
    assert pytest.approx(self_factors.delta_skew, abs=1e-12) == 0.0
    assert pytest.approx(self_factors.delta_curvature, abs=1e-12) == 0.0

    points = decompose_iv_smile(snap3, snap3, self_factors, h_width=500.0)
    for p in points:
        assert pytest.approx(p.observed_change, abs=1e-12) == 0.0
        assert pytest.approx(p.level_comp, abs=1e-12) == 0.0
        assert pytest.approx(p.skew_comp, abs=1e-12) == 0.0
        assert pytest.approx(p.curvature_comp, abs=1e-12) == 0.0
        assert pytest.approx(p.residual, abs=1e-12) == 0.0


def test_10_premium_attribution_identity(shared_long_df: pd.DataFrame):
    """Test 10 — Premium factor attribution identity.

    For every valid fixed-reference fly:
    FullModelledIVChange = LevelEffect + SkewEffect + CurvatureEffect + ResidualEffect
    """
    snap3 = get_snapshot(shared_long_df, "2026-08-03")
    snap4 = get_snapshot(shared_long_df, "2026-08-04")
    factors = fit_factors_between_dates(snap3, snap4, h_width=500.0)

    attributions = compute_fixed_fly_attribution(snap3, snap4, factors, h_width=500.0)
    assert len(attributions) > 0

    for attr in attributions:
        sum_effects = (
            attr.level_effect + attr.skew_effect + attr.curvature_effect + attr.residual_effect
        )
        assert pytest.approx(attr.total_iv_change, abs=1e-12) == sum_effects


def test_11_historical_comparison_independence(shared_long_df: pd.DataFrame):
    """Test 11 — Historical comparison remains independent and immutable."""
    snap3 = get_snapshot(shared_long_df, "2026-08-03")
    orig_iv_atm = float(snap3[snap3["atm_offset"] == 0]["iv_decimal"].iloc[0])

    # Run calculations with various H and fits
    factors_wls = fit_factors_between_dates(snap3, snap3, h_width=400.0, method="wls")
    factors_rob = fit_factors_between_dates(snap3, snap3, h_width=600.0, method="robust")

    # Verify original snapshot remains unchanged
    snap3_after = get_snapshot(shared_long_df, "2026-08-03")
    assert snap3_after[snap3_after["atm_offset"] == 0]["iv_decimal"].iloc[0] == orig_iv_atm


def test_12_large_selections(shared_long_df: pd.DataFrame):
    """Test 12 — Large selections: select 10 and 20 dates without performance failure."""
    all_dates = get_available_dates(shared_long_df)
    assert len(all_dates) >= 20

    subset_20 = all_dates[:20]
    table_df = compute_multidate_factors_table(
        shared_long_df, subset_20, reference_date=subset_20[0], h_width=500.0
    )
    assert len(table_df) == 20
    assert not table_df.isna().all().any()

    flies = build_multidate_flies(shared_long_df, subset_20)
    assert len(flies) == 20
