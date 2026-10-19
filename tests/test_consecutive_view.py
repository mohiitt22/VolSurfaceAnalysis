"""Unit tests for Consecutive Date Analysis charts, data filtering, and view functions."""

from __future__ import annotations

import pandas as pd
import pytest

from spx_butterfly.data_loader import (
    find_default_file,
    load_raw_dataset,
    transform_to_long_form,
    get_snapshot,
)
from spx_butterfly.fly_builder import build_all_butterflies
from spx_butterfly.multidate_model import extract_smile_points
from spx_butterfly.consecutive_charts import (
    create_consecutive_iv_and_fly_iv_chart,
    create_consecutive_fly_premium_chart,
    create_single_date_panel_chart,
)


@pytest.fixture(scope="module")
def sample_dataset():
    path = find_default_file()
    assert path is not None and path.exists()
    raw = load_raw_dataset(path)
    return transform_to_long_form(raw)


def test_consecutive_iv_and_fly_iv_chart_creation(sample_dataset):
    """Verify Graph 1 creates valid 2-row Plotly Figure with expected traces."""
    snap1 = get_snapshot(sample_dataset, "2026-08-03")
    snap2 = get_snapshot(sample_dataset, "2026-08-04")

    smile1 = extract_smile_points(snap1)
    smile2 = extract_smile_points(snap2)

    flies1 = build_all_butterflies(snap1, wing_width=100.0)
    flies2 = build_all_butterflies(snap2, wing_width=100.0)

    # Convert flies to DataFrame
    def to_df(f_list):
        return pd.DataFrame([
            {
                "centre_strike": f.centre_strike,
                "atm_offset": f.centre_strike - f.atm_strike,
                "initial_iv_fly_pct": f.initial_iv_fly_pct,
                "initial_fly_premium": f.initial_fly_premium,
            }
            for f in f_list
        ])

    fly_df1 = to_df(flies1["call"] + flies1["put"])
    fly_df2 = to_df(flies2["call"] + flies2["put"])

    # Test in ATM-offset mode
    fig_offset = create_consecutive_iv_and_fly_iv_chart(
        date1="2026-08-03",
        date2="2026-08-04",
        strike_df1=smile1,
        strike_df2=smile2,
        fly_df1=fly_df1,
        fly_df2=fly_df2,
        use_offset=True,
        atm1=7230.0,
        atm2=7375.0,
    )
    assert fig_offset is not None
    assert len(fig_offset.data) >= 4  # Strike IV 1, Strike IV 2, Fly IV 1, Fly IV 2 + delta/band

    # Test in Absolute Strike mode
    fig_abs = create_consecutive_iv_and_fly_iv_chart(
        date1="2026-08-03",
        date2="2026-08-04",
        strike_df1=smile1,
        strike_df2=smile2,
        fly_df1=fly_df1,
        fly_df2=fly_df2,
        use_offset=False,
        atm1=7230.0,
        atm2=7375.0,
    )
    assert fig_abs is not None
    assert len(fig_abs.data) >= 4


def test_consecutive_fly_premium_chart_creation(sample_dataset):
    """Verify Graph 2 creates valid 2-row Plotly Figure for butterfly premiums."""
    snap1 = get_snapshot(sample_dataset, "2026-08-03")
    snap2 = get_snapshot(sample_dataset, "2026-08-04")

    flies1 = build_all_butterflies(snap1, wing_width=100.0)
    flies2 = build_all_butterflies(snap2, wing_width=100.0)

    def to_df(f_list):
        return pd.DataFrame([
            {
                "centre_strike": f.centre_strike,
                "atm_offset": f.centre_strike - f.atm_strike,
                "initial_iv_fly_pct": f.initial_iv_fly_pct,
                "initial_fly_premium": f.initial_fly_premium,
            }
            for f in f_list
        ])

    fly_df1 = to_df(flies1["call"])
    fly_df2 = to_df(flies2["call"])

    fig_prem = create_consecutive_fly_premium_chart(
        date1="2026-08-03",
        date2="2026-08-04",
        fly_df1=fly_df1,
        fly_df2=fly_df2,
        use_offset=True,
        atm1=7230.0,
        atm2=7375.0,
    )
    assert fig_prem is not None
    assert len(fig_prem.data) >= 2  # Fly Prem 1, Fly Prem 2 + delta bars


def test_single_date_panel_chart_creation(sample_dataset):
    """Verify 3-row panel chart for single date creates valid figure."""
    snap1 = get_snapshot(sample_dataset, "2026-08-03")
    smile1 = extract_smile_points(snap1)
    flies1 = build_all_butterflies(snap1, wing_width=100.0)

    fly_df1 = pd.DataFrame([
        {
            "centre_strike": f.centre_strike,
            "atm_offset": f.centre_strike - f.atm_strike,
            "initial_iv_fly_pct": f.initial_iv_fly_pct,
            "initial_fly_premium": f.initial_fly_premium,
        }
        for f in flies1["call"]
    ])

    fig_panel = create_single_date_panel_chart(
        date_val="2026-08-03",
        strike_df=smile1,
        fly_df=fly_df1,
        use_offset=False,
        atm_val=7230.0,
    )
    assert fig_panel is not None
    assert len(fig_panel.data) == 3  # Strike IV, Fly IV, Fly Prem


def test_smile_structure_metrics_calculation(sample_dataset):
    """Verify compute_smile_structure_metrics produces exact Call Skew, Put Skew, RR, Curvature, Kurtosis."""
    from spx_butterfly.multidate_model import compute_smile_structure_metrics

    snap1 = get_snapshot(sample_dataset, "2026-08-03")
    smile1 = extract_smile_points(snap1)
    res = compute_smile_structure_metrics(smile1)

    assert "table" in res
    assert "benchmark_300" in res
    assert "poly_coeffs" in res

    table = res["table"]
    assert len(table) >= 8  # Offsets 100 to 800+
    assert set(["offset", "iv_call", "iv_put", "call_skew", "put_skew", "risk_reversal", "curvature", "kurtosis_ratio"]).issubset(table.columns)

    # Base at 100 pts has kurtosis_ratio = 1.0 by definition
    row100 = table[table["offset"] == 100.0].iloc[0]
    assert pytest.approx(row100["kurtosis_ratio"], abs=1e-4) == 1.0

    # Risk Reversal at 300 pts must be negative (SPX skew puts > calls)
    b300 = res["benchmark_300"]
    assert b300["risk_reversal"] < 0
    assert b300["call_skew"] < 0
    assert b300["put_skew"] > 0
    assert pytest.approx(b300["risk_reversal"], abs=1e-4) == (b300["call_skew"] - b300["put_skew"])


def test_consecutive_skew_and_rr_chart_creation(sample_dataset):
    """Verify create_consecutive_skew_and_rr_chart creates 2-row figure with 7 traces."""
    from spx_butterfly.multidate_model import compute_smile_structure_metrics
    from spx_butterfly.consecutive_charts import create_consecutive_skew_and_rr_chart

    snap1 = get_snapshot(sample_dataset, "2026-08-03")
    snap2 = get_snapshot(sample_dataset, "2026-08-04")
    m1 = compute_smile_structure_metrics(extract_smile_points(snap1))
    m2 = compute_smile_structure_metrics(extract_smile_points(snap2))

    fig = create_consecutive_skew_and_rr_chart("2026-08-03", "2026-08-04", m1, m2)
    assert fig is not None
    assert len(fig.data) == 7  # PS1, PS2, CS1, CS2, RR1, RR2, Delta RR bar


def test_consecutive_curvature_and_kurtosis_chart_creation(sample_dataset):
    """Verify create_consecutive_curvature_and_kurtosis_chart creates 2-row figure with 7 traces."""
    from spx_butterfly.multidate_model import compute_smile_structure_metrics
    from spx_butterfly.consecutive_charts import create_consecutive_curvature_and_kurtosis_chart

    snap1 = get_snapshot(sample_dataset, "2026-08-03")
    snap2 = get_snapshot(sample_dataset, "2026-08-04")
    m1 = compute_smile_structure_metrics(extract_smile_points(snap1))
    m2 = compute_smile_structure_metrics(extract_smile_points(snap2))

    fig = create_consecutive_curvature_and_kurtosis_chart("2026-08-03", "2026-08-04", m1, m2)
    assert fig is not None
    assert len(fig.data) == 7  # Curv1, Curv2, Curv Band, Delta Curv bar, Kurt1, Kurt2, Delta Kurt bar


def test_multidate_structure_chart_creation(sample_dataset):
    """Verify create_multidate_structure_chart creates valid figures for all 4 categories."""
    from spx_butterfly.multidate_charts import create_multidate_structure_chart

    dates = ["2026-08-03", "2026-08-04", "2026-08-05"]
    snaps = {d: get_snapshot(sample_dataset, d) for d in dates}

    fig_cs_ps = create_multidate_structure_chart(snaps, dates, "call_put_skew", "2026-08-03", "2026-08-04")
    assert fig_cs_ps is not None
    assert len(fig_cs_ps.data) == 6  # 3 Call Skew + 3 Put Skew

    fig_rr = create_multidate_structure_chart(snaps, dates, "skew_rr", "2026-08-03", "2026-08-04")
    assert fig_rr is not None
    assert len(fig_rr.data) >= 3

    fig_ck = create_multidate_structure_chart(snaps, dates, "curvature_kurtosis", "2026-08-03", "2026-08-04")
    assert fig_ck is not None
    assert len(fig_ck.data) == 6  # 3 Curvature + 3 Kurtosis

    fig_all = create_multidate_structure_chart(snaps, dates, "all_stacked", "2026-08-03", "2026-08-04")
    assert fig_all is not None
    assert len(fig_all.data) == 9  # 3 RR + 3 Curv + 3 Kurt


def test_fly_structure_metrics_computation(sample_dataset):
    """Verify compute_fly_structure_metrics produces complete dollar structure table and benchmarks."""
    from spx_butterfly.multidate_model import compute_fly_structure_metrics

    snap = get_snapshot(sample_dataset, "2026-08-03")
    flies = build_all_butterflies(snap, wing_width=100.0)
    rows = []
    for side in ["call", "put"]:
        for f in flies[side]:
            rows.append({
                "centre_strike": f.centre_strike,
                "atm_offset": round(f.centre_strike - f.atm_strike, 1),
                "option_side": f.option_side,
                "initial_fly_premium": f.initial_fly_premium,
            })
    f_df = pd.DataFrame(rows)
    metrics = compute_fly_structure_metrics(f_df)

    assert metrics["atm_fly"] is not None
    assert metrics["atm_fly"] > 0
    t = metrics["table"]
    assert len(t) == 8  # 100 to 800
    assert "fly_call" in t.columns
    assert "fly_put" in t.columns
    assert "risk_reversal" in t.columns
    assert "curvature" in t.columns
    assert "kurtosis_ratio" in t.columns

    b300 = metrics["benchmark_300"]
    assert b300["offset"] == 300.0
    assert b300["risk_reversal"] is not None
    assert b300["curvature"] is not None


def test_consecutive_fly_skew_and_rr_chart_creation(sample_dataset):
    """Verify create_consecutive_fly_skew_and_rr_chart produces valid 2-row figure."""
    from spx_butterfly.multidate_model import compute_fly_structure_metrics
    from spx_butterfly.consecutive_charts import create_consecutive_fly_skew_and_rr_chart

    def _get_fdf(d):
        snap = get_snapshot(sample_dataset, d)
        flies = build_all_butterflies(snap, wing_width=100.0)
        rows = []
        for side in ["call", "put"]:
            for f in flies[side]:
                rows.append({
                    "centre_strike": f.centre_strike,
                    "atm_offset": round(f.centre_strike - f.atm_strike, 1),
                    "option_side": f.option_side,
                    "initial_fly_premium": f.initial_fly_premium,
                })
        return pd.DataFrame(rows)

    f1 = compute_fly_structure_metrics(_get_fdf("2026-08-03"))
    f2 = compute_fly_structure_metrics(_get_fdf("2026-08-04"))

    fig = create_consecutive_fly_skew_and_rr_chart("2026-08-03", "2026-08-04", f1, f2)
    assert fig is not None
    assert len(fig.data) >= 5  # Put1, Put2, Call1, Call2, RR1, RR2, Delta RR bar


def test_consecutive_fly_curvature_and_kurtosis_chart_creation(sample_dataset):
    """Verify create_consecutive_fly_curvature_and_kurtosis_chart produces valid 2-row figure."""
    from spx_butterfly.multidate_model import compute_fly_structure_metrics
    from spx_butterfly.consecutive_charts import create_consecutive_fly_curvature_and_kurtosis_chart

    def _get_fdf(d):
        snap = get_snapshot(sample_dataset, d)
        flies = build_all_butterflies(snap, wing_width=100.0)
        rows = []
        for side in ["call", "put"]:
            for f in flies[side]:
                rows.append({
                    "centre_strike": f.centre_strike,
                    "atm_offset": round(f.centre_strike - f.atm_strike, 1),
                    "option_side": f.option_side,
                    "initial_fly_premium": f.initial_fly_premium,
                })
        return pd.DataFrame(rows)

    f1 = compute_fly_structure_metrics(_get_fdf("2026-08-03"))
    f2 = compute_fly_structure_metrics(_get_fdf("2026-08-04"))

    fig = create_consecutive_fly_curvature_and_kurtosis_chart("2026-08-03", "2026-08-04", f1, f2)
    assert fig is not None
    assert len(fig.data) >= 5  # Curv1, Curv2, Delta Curv bar, Kurt1, Kurt2, Ret1, Ret2


def test_dedicated_fly_structure_charts(sample_dataset):
    """Verify dedicated charts for Call/Put Fly Skew, Fly RR, Fly Curvature, and Fly Kurtosis."""
    from spx_butterfly.multidate_model import compute_fly_structure_metrics
    from spx_butterfly.consecutive_charts import (
        create_consecutive_fly_call_put_skew_chart,
        create_consecutive_fly_rr_chart,
        create_consecutive_fly_curvature_chart,
        create_consecutive_fly_kurtosis_chart,
    )

    def _get_fdf(d):
        snap = get_snapshot(sample_dataset, d)
        flies = build_all_butterflies(snap, wing_width=100.0)
        rows = []
        for side in ["call", "put"]:
            for f in flies[side]:
                rows.append({
                    "centre_strike": f.centre_strike,
                    "atm_offset": round(f.centre_strike - f.atm_strike, 1),
                    "option_side": f.option_side,
                    "initial_fly_premium": f.initial_fly_premium,
                })
        return pd.DataFrame(rows)

    f1 = compute_fly_structure_metrics(_get_fdf("2026-08-03"))
    f2 = compute_fly_structure_metrics(_get_fdf("2026-08-04"))

    fig_cs_ps = create_consecutive_fly_call_put_skew_chart("2026-08-03", "2026-08-04", f1, f2)
    assert fig_cs_ps is not None
    assert len(fig_cs_ps.data) >= 4  # Call1, Call2, Put1, Put2

    fig_rr = create_consecutive_fly_rr_chart("2026-08-03", "2026-08-04", f1, f2)
    assert fig_rr is not None
    assert len(fig_rr.data) >= 3  # RR1, RR2, Delta RR bar

    fig_curv = create_consecutive_fly_curvature_chart("2026-08-03", "2026-08-04", f1, f2)
    assert fig_curv is not None
    assert len(fig_curv.data) >= 3  # Curv1, Curv2, Delta Curv bar

    fig_kurt = create_consecutive_fly_kurtosis_chart("2026-08-03", "2026-08-04", f1, f2)
    assert fig_kurt is not None
    assert len(fig_kurt.data) >= 3  # Spread1, Spread2, Ret1, Ret2


