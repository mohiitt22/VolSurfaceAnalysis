"""Consecutive Date Analysis Workspace View for Streamlit.

Provides a dedicated environment for comparing two consecutive historical trading dates:
1. Quick Stepper & Benchmark Toolbar with reactive callbacks (Prev Pair, Next Pair, Aug 3->4, etc.).
2. High-readability KPI Summary Cards (2 rows of 3 spacious cards, zero overlapping text).
3. Dual-row Graph 1: Individual Strike IV smiles and Fly IV (local curvature) across strikes.
4. Dual-row Graph 2: 100-pt Butterfly Net Debit Premiums and daily changes ($) across strikes.
5. Cross-Strike Consecutive Inspection Grid:
   - ATM-Relative Offset Mode (default): Aligns both dates in a SINGLE ROW by moneyness (e.g. ATM - 900 to ATM + 900).
   - Absolute Strike Mode: Aligns by fixed index strike price K.
6. Single-Strike 3-Leg Butterfly Drilldown: Side-by-side leg-by-leg deconstruction (Lower, Body, Upper, Net).
7. Educational Mental Model Guide.
"""

from __future__ import annotations

import io
from typing import Any
import numpy as np
import pandas as pd
import streamlit as st

from spx_butterfly.data_loader import get_snapshot
from spx_butterfly.fly_builder import build_all_butterflies, ButterflySpread
from spx_butterfly.multidate_model import (
    calculate_daily_factors,
    fit_factors_between_dates,
    extract_smile_points,
    compute_smile_structure_metrics,
    compute_fly_structure_metrics,
    get_fly_premium_at_offset,
)
from spx_butterfly.consecutive_charts import (
    create_consecutive_iv_and_fly_iv_chart,
    create_consecutive_fly_premium_chart,
    create_consecutive_fly_call_put_skew_chart,
    create_consecutive_fly_rr_chart,
    create_consecutive_fly_curvature_chart,
    create_consecutive_fly_kurtosis_chart,
    create_consecutive_fly_skew_and_rr_chart,
    create_consecutive_fly_curvature_and_kurtosis_chart,
    create_consecutive_skew_and_rr_chart,
    create_consecutive_curvature_and_kurtosis_chart,
    create_single_date_panel_chart,
)


def _format_pct(val: float | None) -> str:
    if val is None or not np.isfinite(val):
        return "—"
    return f"{val:.3f}%"


def _format_pts(val: float | None) -> str:
    if val is None or not np.isfinite(val):
        return "—"
    return f"{val:+.3f} pts" if val != 0 else "0.000 pts"


def _format_currency(val: float | None) -> str:
    if val is None or not np.isfinite(val):
        return "—"
    return f"${val:.2f}"


def _format_delta_curr(val: float | None) -> str:
    if val is None or not np.isfinite(val):
        return "—"
    if val > 0:
        return f"+${val:.2f}"
    elif val < 0:
        return f"-${abs(val):.2f}"
    return "$0.00"


def render_consecutive_workspace(long_df: pd.DataFrame, available_dates: list[str]) -> None:
    """Render the Consecutive Date Analysis research workspace."""

    # ---------------------------------------------------------------------------
    # Custom CSS for crisp, non-overlapping typography & cards
    # ---------------------------------------------------------------------------
    st.markdown(
        """
        <style>
        .consec-header {
            margin-bottom: 4px;
        }
        .consec-card {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 10px 14px;
            margin-bottom: 8px;
            display: flex;
            flex-direction: column;
            gap: 4px;
            box-sizing: border-box;
            width: 100%;
            min-width: 0;
            overflow: hidden;
        }
        .consec-card-title {
            font-size: 11px;
            font-weight: 600;
            color: #8b949e;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 2px;
            line-height: 1.3;
            word-break: break-word;
            overflow-wrap: break-word;
        }
        .consec-card-value {
            font-size: 15px;
            font-weight: 700;
            color: #f0f6fc;
            line-height: 1.3;
            margin-bottom: 2px;
            word-break: break-word;
            overflow-wrap: break-word;
        }
        .consec-card-val-row {
            display: flex;
            flex-wrap: wrap;
            align-items: baseline;
            gap: 4px 8px;
            font-size: 15px;
            font-weight: 700;
            line-height: 1.3;
            word-break: break-word;
            overflow-wrap: break-word;
        }
        .consec-card-sub {
            font-size: 11.5px;
            color: #58a6ff;
            line-height: 1.35;
            word-break: break-word;
            overflow-wrap: break-word;
        }
        .consec-badge-row {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 4px 8px;
            font-size: 11px;
            color: #58a6ff;
            line-height: 1.35;
            word-break: break-word;
            overflow-wrap: break-word;
        }
        .section-badge {
            display: inline-block;
            background-color: rgba(56, 189, 248, 0.12);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.3);
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 6px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------------------------------
    # Header & Subtitle
    # ---------------------------------------------------------------------------
    st.markdown("## 📅 Consecutive Day Volatility & Butterfly Analysis")
    st.markdown(
        "*Dual-session deep dive comparing Individual Strike IVs, Fly IV Curvature, and Fly Net Premiums between trading day $T$ and $T+1$.*"
    )

    # ---------------------------------------------------------------------------
    # Session State Initialization
    # ---------------------------------------------------------------------------
    if "consec_date1" not in st.session_state or st.session_state.consec_date1 not in available_dates:
        st.session_state.consec_date1 = "2026-08-03" if "2026-08-03" in available_dates else available_dates[0]

    idx1_init = available_dates.index(st.session_state.consec_date1)
    default_date2 = available_dates[min(idx1_init + 1, len(available_dates) - 1)]

    if "consec_date2" not in st.session_state or st.session_state.consec_date2 not in available_dates:
        st.session_state.consec_date2 = default_date2

    # ---------------------------------------------------------------------------
    # Reactive Callbacks for Steppers and Presets
    # ---------------------------------------------------------------------------
    def _step_prev_pair():
        curr_d1 = st.session_state.consec_date1
        if curr_d1 in available_dates:
            i = available_dates.index(curr_d1)
            if i > 0:
                st.session_state.consec_date1 = available_dates[i - 1]
                st.session_state.consec_date2 = available_dates[i]

    def _step_next_pair():
        curr_d1 = st.session_state.consec_date1
        if curr_d1 in available_dates:
            i = available_dates.index(curr_d1)
            if i < len(available_dates) - 1:
                st.session_state.consec_date1 = available_dates[i + 1]
                st.session_state.consec_date2 = available_dates[min(i + 2, len(available_dates) - 1)]

    def _set_consec_pair(d1: str, d2: str):
        if d1 in available_dates and d2 in available_dates:
            st.session_state.consec_date1 = d1
            st.session_state.consec_date2 = d2

    def _on_change_date1():
        d1 = st.session_state.consec_date1
        if d1 in available_dates:
            i = available_dates.index(d1)
            st.session_state.consec_date2 = available_dates[min(i + 1, len(available_dates) - 1)]

    # ---------------------------------------------------------------------------
    # Controls Toolbar: Quick Presets & Steppers
    # ---------------------------------------------------------------------------
    btn_c1, btn_c2, btn_c3, btn_c4, btn_c5, btn_c6 = st.columns(6)

    btn_c1.button(
        "◀ Prev Pair",
        use_container_width=True,
        help="Step backward by 1 trading session (T-1, T)",
        on_click=_step_prev_pair,
    )
    btn_c2.button(
        "Next Pair ▶",
        use_container_width=True,
        help="Step forward by 1 trading session (T+1, T+2)",
        on_click=_step_next_pair,
    )
    btn_c3.button(
        "🎯 Aug 3 → 4",
        use_container_width=True,
        help="Primary benchmark pair: Aug 3 to Aug 4, 2026",
        on_click=_set_consec_pair,
        args=("2026-08-03", "2026-08-04"),
    )
    btn_c4.button(
        "Aug 4 → 5",
        use_container_width=True,
        help="Step to Aug 4 to Aug 5, 2026",
        on_click=_set_consec_pair,
        args=("2026-08-04", "2026-08-05"),
    )
    btn_c5.button(
        "Aug 5 → 6",
        use_container_width=True,
        help="Step to Aug 5 to Aug 6, 2026",
        on_click=_set_consec_pair,
        args=("2026-08-05", "2026-08-06"),
    )
    btn_c6.button(
        "⚡ Latest Pair",
        use_container_width=True,
        help="Jump to most recent consecutive pair in dataset",
        on_click=_set_consec_pair,
        args=(available_dates[-2], available_dates[-1]),
    )

    # ---------------------------------------------------------------------------
    # Date Pickers & Display Configuration
    # ---------------------------------------------------------------------------
    with st.container():
        st.markdown("<div style='background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; margin: 8px 0 14px 0;'>", unsafe_allow_html=True)
        col_d1, col_d2, col_side, col_align, col_mode = st.columns([1.3, 1.3, 1.4, 1.4, 1.6])

        with col_d1:
            st.selectbox(
                "Date 1 (Day T):",
                options=available_dates,
                key="consec_date1",
                on_change=_on_change_date1,
            )

        with col_d2:
            st.selectbox(
                "Date 2 (Day T+1):",
                options=available_dates,
                key="consec_date2",
            )

        with col_side:
            side_filter = st.selectbox(
                "Option Type:",
                options=["Calls & Puts (OTM Split)", "Calls Only", "Puts Only", "All Combined"],
                index=0,
                help="Choose which option contracts to visualize for butterflies and strike smiles.",
            )

        with col_align:
            align_mode = st.selectbox(
                "Chart Strike Alignment:",
                options=["ATM-Relative (K − ATM)", "Absolute Strike (K)"],
                index=0,
                help="Align chart x-axis relative to each day's ATM strike or by absolute index strike price.",
            )
            use_offset = (align_mode == "ATM-Relative (K − ATM)")

        with col_mode:
            view_mode = st.selectbox(
                "Chart View Layout:",
                options=["Synchronized Overlay Subplots", "Side-by-Side Daily Panels"],
                index=0,
                help="Compare both dates in shared dual subplots or inspect each day side-by-side in separate panels.",
            )

        st.markdown("</div>", unsafe_allow_html=True)

    date1 = st.session_state.consec_date1
    date2 = st.session_state.consec_date2

    # ---------------------------------------------------------------------------
    # Data Preparation & Factor Calculations
    # ---------------------------------------------------------------------------
    snap1 = get_snapshot(long_df, date1)
    snap2 = get_snapshot(long_df, date2)

    spot1 = float(snap1["underlying"].iloc[0])
    spot2 = float(snap2["underlying"].iloc[0])
    atm1 = float(snap1["atm_strike"].iloc[0])
    atm2 = float(snap2["atm_strike"].iloc[0])
    dte1 = float(snap1["target_dte"].iloc[0])
    dte2 = float(snap2["target_dte"].iloc[0])

    # Smile Points
    smile1 = extract_smile_points(snap1)
    smile2 = extract_smile_points(snap2)

    # Butterflies (100-pt wings)
    flies1_dict = build_all_butterflies(snap1, wing_width=100.0)
    flies2_dict = build_all_butterflies(snap2, wing_width=100.0)

    # Build complete unfiltered fly tables for symmetric structure analysis
    def _to_full_flies(f_dict: dict[str, list[ButterflySpread]]) -> pd.DataFrame:
        f_rows = []
        for side in ["call", "put"]:
            for f in f_dict.get(side, []):
                f_rows.append({
                    "centre_strike": f.centre_strike,
                    "atm_offset": round(f.centre_strike - f.atm_strike, 1),
                    "option_side": f.option_side,
                    "lower_strike": f.lower_strike,
                    "upper_strike": f.upper_strike,
                    "lower_premium": f.lower_premium,
                    "middle_premium": f.middle_premium,
                    "upper_premium": f.upper_premium,
                    "initial_iv_fly_pct": f.initial_iv_fly_pct,
                    "initial_fly_premium": f.initial_fly_premium,
                })
        return pd.DataFrame(f_rows)

    fly_df_full1 = _to_full_flies(flies1_dict)
    fly_df_full2 = _to_full_flies(flies2_dict)

    # Factor calculations
    factors1 = calculate_daily_factors(snap1, h_width=500.0)
    factors2 = calculate_daily_factors(snap2, h_width=500.0)
    diff_factors = fit_factors_between_dates(snap1, snap2, h_width=500.0, method="anchor")

    # 1. Higher-order IV smile structure metrics (Call/Put Skew, Risk Reversal, Curvature, Kurtosis in vol pts)
    struct_metrics1 = compute_smile_structure_metrics(smile1)
    struct_metrics2 = compute_smile_structure_metrics(smile2)

    b300_1 = struct_metrics1["benchmark_300"]
    b300_2 = struct_metrics2["benchmark_300"]
    p_poly1 = struct_metrics1["poly_coeffs"]
    p_poly2 = struct_metrics2["poly_coeffs"]

    cs1_300 = b300_1.get("call_skew")
    cs2_300 = b300_2.get("call_skew")
    d_cs_300 = (cs2_300 - cs1_300) if (cs1_300 is not None and cs2_300 is not None) else None

    ps1_300 = b300_1.get("put_skew")
    ps2_300 = b300_2.get("put_skew")
    d_ps_300 = (ps2_300 - ps1_300) if (ps1_300 is not None and ps2_300 is not None) else None

    rr1_300 = b300_1.get("risk_reversal")
    rr2_300 = b300_2.get("risk_reversal")
    d_rr_300 = (rr2_300 - rr1_300) if (rr1_300 is not None and rr2_300 is not None) else None
    rr_col = "#3fb950" if (d_rr_300 is not None and d_rr_300 >= 0) else "#f85149"

    curv1_300 = b300_1.get("curvature")
    curv2_300 = b300_2.get("curvature")
    d_curv_300 = (curv2_300 - curv1_300) if (curv1_300 is not None and curv2_300 is not None) else None
    curv_col = "#3fb950" if (d_curv_300 is not None and d_curv_300 >= 0) else "#f85149"

    kurt1_300 = b300_1.get("kurtosis_ratio")
    kurt2_300 = b300_2.get("kurtosis_ratio")
    d_kurt_300 = (kurt2_300 - kurt1_300) if (kurt1_300 is not None and kurt2_300 is not None) else None

    a4_1 = p_poly1.get("a4_kurtosis", 0.0)
    a4_2 = p_poly2.get("a4_kurtosis", 0.0)
    d_a4 = a4_2 - a4_1

    # 2. Butterfly Spread Structure Metrics ($/contract computed directly on Fly Premium curve)
    fly_struct1 = compute_fly_structure_metrics(fly_df_full1)
    fly_struct2 = compute_fly_structure_metrics(fly_df_full2)

    fb300_1 = fly_struct1["benchmark_300"]
    fb300_2 = fly_struct2["benchmark_300"]
    fly_rr1_300 = fb300_1.get("risk_reversal")
    fly_rr2_300 = fb300_2.get("risk_reversal")
    d_fly_rr_300 = (fly_rr2_300 - fly_rr1_300) if (fly_rr1_300 is not None and fly_rr2_300 is not None) else None

    fly_curv1_300 = fb300_1.get("curvature")
    fly_curv2_300 = fb300_2.get("curvature")
    d_fly_curv_300 = (fly_curv2_300 - fly_curv1_300) if (fly_curv1_300 is not None and fly_curv2_300 is not None) else None

    fly_kurt1_300 = fb300_1.get("kurtosis_spread")
    fly_kurt2_300 = fb300_2.get("kurtosis_spread")
    d_fly_kurt_300 = (fly_kurt2_300 - fly_kurt1_300) if (fly_kurt1_300 is not None and fly_kurt2_300 is not None) else None

    ret1_300 = fb300_1.get("kurtosis_ratio")
    ret2_300 = fb300_2.get("kurtosis_ratio")
    d_ret_300 = (ret2_300 - ret1_300) if (ret1_300 is not None and ret2_300 is not None) else None

    call_fly1_300 = fb300_1.get("fly_call")
    call_fly2_300 = fb300_2.get("fly_call")
    d_call_fly_300 = (call_fly2_300 - call_fly1_300) if (call_fly1_300 is not None and call_fly2_300 is not None) else None

    put_fly1_300 = fb300_1.get("fly_put")
    put_fly2_300 = fb300_2.get("fly_put")
    d_put_fly_300 = (put_fly2_300 - put_fly1_300) if (put_fly1_300 is not None and put_fly2_300 is not None) else None

    # ---------------------------------------------------------------------------
    # Market Summary KPI Cards (3 rows of 3 columns for spacious readability)
    # ---------------------------------------------------------------------------
    d_spot = spot2 - spot1
    d_spot_pct = (d_spot / spot1) * 100.0 if spot1 > 0 else 0.0
    sp_col = "#3fb950" if d_spot >= 0 else "#f85149"

    dl = diff_factors.delta_level
    dl_col = "#3fb950" if dl >= 0 else "#f85149"

    ds = diff_factors.delta_skew
    ds_col = "#3fb950" if ds >= 0 else "#f85149"

    dc = diff_factors.delta_curvature
    dc_col = "#3fb950" if dc >= 0 else "#f85149"

    # Row 1: Market State & Spot Movement
    r1_c1, r1_c2, r1_c3 = st.columns(3)
    with r1_c1:
        st.markdown(
            f"""
            <div class="consec-card">
                <div class="consec-card-title">Day T Snapshot: {date1}</div>
                <div class="consec-card-val-row">ATM Vol: {factors1['level']:.3f}%</div>
                <div class="consec-badge-row">
                    <span>SPX: {spot1:.1f}</span>
                    <span style="color: #484f58;">&bull;</span>
                    <span>ATM: {atm1:.0f}</span>
                    <span style="color: #484f58;">&bull;</span>
                    <span>{dte1:.0f} DTE</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r1_c2:
        st.markdown(
            f"""
            <div class="consec-card">
                <div class="consec-card-title">Day T+1 Snapshot: {date2}</div>
                <div class="consec-card-val-row">ATM Vol: {factors2['level']:.3f}%</div>
                <div class="consec-badge-row">
                    <span>SPX: {spot2:.1f}</span>
                    <span style="color: #484f58;">&bull;</span>
                    <span>ATM: {atm2:.0f}</span>
                    <span style="color: #484f58;">&bull;</span>
                    <span>{dte2:.0f} DTE</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r1_c3:
        st.markdown(
            f"""
            <div class="consec-card">
                <div class="consec-card-title">Underlying SPX Spot Movement</div>
                <div class="consec-card-val-row" style="color: {sp_col};">{d_spot:+.2f} pts ({d_spot_pct:+.2f}%)</div>
                <div class="consec-badge-row">
                    <span>ATM Shift: {atm2 - atm1:+.0f} pts</span>
                    <span style="color: #484f58;">&bull;</span>
                    <span>{'Rally' if d_spot >= 0 else 'Decline'}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Row 2: Smile Factor Shift Decomposition
    r2_c1, r2_c2, r2_c3 = st.columns(3)
    with r2_c1:
        st.markdown(
            f"""
            <div class="consec-card">
                <div class="consec-card-title">Δ Level Factor (L)</div>
                <div class="consec-card-val-row" style="color: {dl_col};">{dl:+.4f} pts</div>
                <div class="consec-badge-row">Parallel ATM Implied Volatility shift</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r2_c2:
        st.markdown(
            f"""
            <div class="consec-card">
                <div class="consec-card-title">Δ Skew Factor (S)</div>
                <div class="consec-card-val-row" style="color: {ds_col};">{ds:+.4f} pts</div>
                <div class="consec-badge-row">Smile slope twist (Call wing vs Put wing)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r2_c3:
        st.markdown(
            f"""
            <div class="consec-card">
                <div class="consec-card-title">Δ Curvature Factor (C)</div>
                <div class="consec-card-val-row" style="color: {dc_col};">{dc:+.4f} pts</div>
                <div class="consec-badge-row">Convexity bend (Fly IV expansion / squeeze)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Row 3: 100-pt Butterfly Spread Premium Structure Moments ($/contract) - FIRST
    st.markdown("<div style='font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.6px; margin: 12px 0 4px 2px;'>💵 1. 100-pt Butterfly Spread Dollar Moments ($ / contract) — Computed Directly on Fly Premium Curve</div>", unsafe_allow_html=True)
    r3_c1, r3_c2, r3_c3 = st.columns(3)
    call_fly_str = f"${call_fly2_300:.2f}" if call_fly2_300 is not None else "—"
    put_fly_str = f"${put_fly2_300:.2f}" if put_fly2_300 is not None else "—"
    cs_fly_str = f"${fb300_2.get('call_skew', 0.0):+.2f}" if fb300_2.get('call_skew') is not None else "—"
    ps_fly_str = f"${fb300_2.get('put_skew', 0.0):+.2f}" if fb300_2.get('put_skew') is not None else "—"
    with r3_c1:
        st.markdown(
            f"""
            <div class="consec-card">
                <div class="consec-card-title">300-pt Call &amp; Put Fly Skew ($)</div>
                <div class="consec-card-val-row">
                    <span style="color: #3fb950;">Call: {call_fly_str}</span>
                    <span style="color: #484f58;">&bull;</span>
                    <span style="color: #ff7b72;">Put: {put_fly_str}</span>
                </div>
                <div class="consec-badge-row">
                    <span>Call Skew: {cs_fly_str}</span>
                    <span style="color: #484f58;">&bull;</span>
                    <span>Put Skew: {ps_fly_str}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r3_c2:
        fly_rr_col = "#3fb950" if (d_fly_rr_300 is not None and d_fly_rr_300 >= 0) else "#f85149"
        fly_rr_str = f"${fly_rr2_300:+.2f} / fly" if fly_rr2_300 is not None else "—"
        d_fly_rr_str = f"${d_fly_rr_300:+.2f}" if d_fly_rr_300 is not None else "—"
        st.markdown(
            f"""
            <div class="consec-card">
                <div class="consec-card-title">300-pt Fly Skew / Fly Risk Reversal ($)</div>
                <div class="consec-card-val-row" style="color: {fly_rr_col};">
                    <span>{fly_rr_str}</span>
                    <span style="font-size: 11px; font-weight: normal; color: #8b949e;">({ 'Call Fly Gained' if (d_fly_rr_300 is not None and d_fly_rr_300 >= 0) else 'Put Fly Gained' })</span>
                </div>
                <div class="consec-badge-row">
                    <span>Shift: <b>{d_fly_rr_str}</b> from {date1}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r3_c3:
        curv_fly_str = f"${fly_curv2_300:+.2f}" if fly_curv2_300 is not None else "—"
        kurt_fly_str = f"${fly_kurt2_300:+.2f}" if fly_kurt2_300 is not None else "—"
        ret_val = (ret2_300 or 0.0) * 100.0
        d_ret_val = ((d_ret_300 or 0.0) * 100.0)
        st.markdown(
            f"""
            <div class="consec-card">
                <div class="consec-card-title">Fly Curvature &amp; Kurtosis Butterfly ($)</div>
                <div class="consec-card-val-row" style="color: #d2a8ff;">
                    <span>Curv: {curv_fly_str}</span>
                    <span style="color: #484f58;">&bull;</span>
                    <span style="color: #f97316;">Kurt: {kurt_fly_str}</span>
                </div>
                <div class="consec-badge-row">
                    <span>Wing Retention: <b>{ret_val:.1f}%</b> (Δ {d_ret_val:+.1f}%)</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Row 4: Higher-Order IV Smile Moments (vol pts) - SECOND
    st.markdown("<div style='font-size: 11px; font-weight: 700; color: #bc8cff; text-transform: uppercase; letter-spacing: 0.6px; margin: 12px 0 4px 2px;'>⚖️ 2. Implied Volatility Smile Moments (vol pts) — Computed on Implied Volatility Smile Curve</div>", unsafe_allow_html=True)
    r4_c1, r4_c2, r4_c3 = st.columns(3)
    with r4_c1:
        st.markdown(
            f"""
            <div class="consec-card">
                <div class="consec-card-title">25Δ Call &amp; Put Skew (300-pt)</div>
                <div class="consec-card-val-row">
                    <span style="color: #38bdf8;">Call: {cs2_300:+.2f}</span>
                    <span style="color: #484f58;">&bull;</span>
                    <span style="color: #ff7b72;">Put: {ps2_300:+.2f} pts</span>
                </div>
                <div class="consec-badge-row">
                    <span>Δ Call: {d_cs_300:+.2f} pts</span>
                    <span style="color: #484f58;">&bull;</span>
                    <span>Δ Put: {d_ps_300:+.2f} pts</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r4_c2:
        st.markdown(
            f"""
            <div class="consec-card">
                <div class="consec-card-title">25Δ Skew / Risk Reversal (Call − Put)</div>
                <div class="consec-card-val-row" style="color: {rr_col};">
                    <span>{rr2_300:+.2f} pts</span>
                    <span style="font-size: 11px; font-weight: normal; color: #8b949e;">({ 'Flattening' if (d_rr_300 is not None and d_rr_300 >= 0) else 'Steepening' })</span>
                </div>
                <div class="consec-badge-row">
                    <span>Shift: <b>{d_rr_300:+.3f} pts</b> from {date1}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with r4_c3:
        st.markdown(
            f"""
            <div class="consec-card">
                <div class="consec-card-title">Curvature &amp; Quartic Kurtosis (a₄)</div>
                <div class="consec-card-val-row" style="color: {curv_col};">
                    <span>Curv: {curv2_300:+.3f} pts</span>
                    <span style="color: #484f58;">&bull;</span>
                    <span style="color: #e3b341;">a₄: {a4_2:.3f}</span>
                </div>
                <div class="consec-badge-row">
                    <span>Δ Curv: {d_curv_300:+.3f} pts</span>
                    <span style="color: #484f58;">&bull;</span>
                    <span>Δ a₄: {d_a4:+.3f}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ---------------------------------------------------------------------------
    # Prepare Filtered Fly & Strike Data
    # ---------------------------------------------------------------------------
    def _filter_flies(flies_dict: dict[str, list[ButterflySpread]]) -> pd.DataFrame:
        call_flies = flies_dict.get("call", [])
        put_flies = flies_dict.get("put", [])
        rows = []
        if side_filter == "Calls Only":
            active_list = call_flies
        elif side_filter == "Puts Only":
            active_list = put_flies
        elif side_filter == "Calls & Puts (OTM Split)":
            active_list = [f for f in call_flies if f.centre_strike >= f.atm_strike] + [
                f for f in put_flies if f.centre_strike <= f.atm_strike
            ]
        else:
            active_list = call_flies + put_flies

        for f in active_list:
            rows.append({
                "centre_strike": f.centre_strike,
                "atm_offset": round(f.centre_strike - f.atm_strike, 1),
                "option_side": f.option_side,
                "lower_strike": f.lower_strike,
                "upper_strike": f.upper_strike,
                "lower_iv_pct": f.lower_iv * 100.0,
                "middle_iv_pct": f.middle_iv * 100.0,
                "upper_iv_pct": f.upper_iv * 100.0,
                "lower_premium": f.lower_premium,
                "middle_premium": f.middle_premium,
                "upper_premium": f.upper_premium,
                "initial_iv_fly_pct": f.initial_iv_fly_pct,
                "initial_fly_premium": f.initial_fly_premium,
                "vega": f.initial_net_vega,
                "volga": f.initial_net_volga,
            })
        df_res = pd.DataFrame(rows)
        if not df_res.empty:
            df_res = df_res.drop_duplicates(subset=["centre_strike", "option_side"]).reset_index(drop=True)
        return df_res

    fly_df1 = _filter_flies(flies1_dict)
    fly_df2 = _filter_flies(flies2_dict)

    # Filter strike dataframe
    def _filter_strikes(s_df: pd.DataFrame) -> pd.DataFrame:
        if side_filter == "Calls Only":
            return s_df[s_df["option_side"] == "call"].copy()
        elif side_filter == "Puts Only":
            return s_df[s_df["option_side"] == "put"].copy()
        return s_df.copy()

    strike_f1 = _filter_strikes(smile1)
    strike_f2 = _filter_strikes(smile2)

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    # ---------------------------------------------------------------------------
    # Main Visualizations: The Two Consecutive Graphs
    # ---------------------------------------------------------------------------
    show_labels = st.checkbox("Show exact numeric labels on chart data points", value=False)

    if view_mode == "Synchronized Overlay Subplots":
        # Graph 1: Strike IV & Fly IV
        fig_iv_fly = create_consecutive_iv_and_fly_iv_chart(
            date1=date1,
            date2=date2,
            strike_df1=strike_f1,
            strike_df2=strike_f2,
            fly_df1=fly_df1,
            fly_df2=fly_df2,
            use_offset=use_offset,
            atm1=atm1,
            atm2=atm2,
            show_labels=show_labels,
        )
        st.plotly_chart(fig_iv_fly, use_container_width=True)

        # Graph 2: Structure Curve Selector (Fly Premium, Skew & RR, Curvature & Kurtosis, Stacked)
        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        st.markdown("#### 🦅 2. Butterfly Premium & Volatility Surface Structure Curves")
        st.markdown(
            "Inspect **100-pt Butterfly Net Debit Premiums**, **Call/Put Skew**, **Skew (Risk Reversal)**, **Curvature**, and **Kurtosis** across moneyness points."
        )

        struct_choice = st.radio(
            "Select Structure View to Display:",
            options=[
                "💵 Call Fly Skew & Put Fly Skew ($/contract)",
                "💱 Fly Skew / Fly Risk Reversal ($/fly)",
                "🦋 Fly Curvature ($/fly)",
                "🦅 Kurtosis Butterfly Spread & Wing Retention ($)",
                "🦅 100-pt Butterfly Net Premium ($)",
                "⚖️ Volatility Call Skew & Put Skew (vol pts)",
                "📐 Volatility Risk Reversal (vol pts)",
                "🌊 Smile Vol Curvature & Kurtosis Fat-Tail Ratio",
                "📑 Stack All Fly Premium Moments ($)",
                "📑 Stack All Structure Curves (Both Fly $ and IV pts)",
            ],
            index=0,
            horizontal=True,
            key="consec_struct_choice",
            help="Switch between Call/Put Fly Skew ($), Fly Risk Reversal ($), Fly Curvature ($), Kurtosis Butterfly ($), 100-pt Butterfly dollar costs, IV Call/Put Skew (vol pts), Vol Risk Reversal (vol pts), Smile Curvature/Kurtosis, or stack them.",
        )

        fig_prem = create_consecutive_fly_premium_chart(
            date1=date1,
            date2=date2,
            fly_df1=fly_df1,
            fly_df2=fly_df2,
            use_offset=use_offset,
            atm1=atm1,
            atm2=atm2,
            show_labels=show_labels,
        )
        fig_fly_cs_ps = create_consecutive_fly_call_put_skew_chart(
            date1=date1,
            date2=date2,
            fly_struct1=fly_struct1,
            fly_struct2=fly_struct2,
            show_labels=show_labels,
        )
        fig_fly_rr = create_consecutive_fly_rr_chart(
            date1=date1,
            date2=date2,
            fly_struct1=fly_struct1,
            fly_struct2=fly_struct2,
            show_labels=show_labels,
        )
        fig_fly_curv = create_consecutive_fly_curvature_chart(
            date1=date1,
            date2=date2,
            fly_struct1=fly_struct1,
            fly_struct2=fly_struct2,
            show_labels=show_labels,
        )
        fig_fly_kurt = create_consecutive_fly_kurtosis_chart(
            date1=date1,
            date2=date2,
            fly_struct1=fly_struct1,
            fly_struct2=fly_struct2,
            show_labels=show_labels,
        )
        fig_skew_rr = create_consecutive_skew_and_rr_chart(
            date1=date1,
            date2=date2,
            struct_metrics1=struct_metrics1,
            struct_metrics2=struct_metrics2,
            show_labels=show_labels,
        )
        fig_curv_kurt = create_consecutive_curvature_and_kurtosis_chart(
            date1=date1,
            date2=date2,
            struct_metrics1=struct_metrics1,
            struct_metrics2=struct_metrics2,
            show_labels=show_labels,
        )

        if struct_choice == "💵 Call Fly Skew & Put Fly Skew ($/contract)":
            st.plotly_chart(fig_fly_cs_ps, use_container_width=True)
        elif struct_choice == "💱 Fly Skew / Fly Risk Reversal ($/fly)":
            st.plotly_chart(fig_fly_rr, use_container_width=True)
        elif struct_choice == "🦋 Fly Curvature ($/fly)":
            st.plotly_chart(fig_fly_curv, use_container_width=True)
        elif struct_choice == "🦅 Kurtosis Butterfly Spread & Wing Retention ($)":
            st.plotly_chart(fig_fly_kurt, use_container_width=True)
        elif struct_choice == "🦅 100-pt Butterfly Net Premium ($)":
            st.plotly_chart(fig_prem, use_container_width=True)
        elif struct_choice == "⚖️ Volatility Call Skew & Put Skew (vol pts)":
            st.plotly_chart(fig_skew_rr, use_container_width=True)
        elif struct_choice == "📐 Volatility Risk Reversal (vol pts)":
            st.plotly_chart(fig_skew_rr, use_container_width=True)
        elif struct_choice == "🌊 Smile Vol Curvature & Kurtosis Fat-Tail Ratio":
            st.plotly_chart(fig_curv_kurt, use_container_width=True)
        elif struct_choice == "📑 Stack All Fly Premium Moments ($)":
            st.plotly_chart(fig_prem, use_container_width=True)
            st.plotly_chart(fig_fly_cs_ps, use_container_width=True)
            st.plotly_chart(fig_fly_rr, use_container_width=True)
            st.plotly_chart(fig_fly_curv, use_container_width=True)
            st.plotly_chart(fig_fly_kurt, use_container_width=True)
        else:
            st.plotly_chart(fig_prem, use_container_width=True)
            st.plotly_chart(fig_fly_cs_ps, use_container_width=True)
            st.plotly_chart(fig_fly_rr, use_container_width=True)
            st.plotly_chart(fig_fly_curv, use_container_width=True)
            st.plotly_chart(fig_fly_kurt, use_container_width=True)
            st.plotly_chart(fig_skew_rr, use_container_width=True)
            st.plotly_chart(fig_curv_kurt, use_container_width=True)

    else:
        # Side-by-Side Daily Panels
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            fig_p1 = create_single_date_panel_chart(
                date=date1,
                strike_df=strike_f1,
                fly_df=fly_df1,
                use_offset=use_offset,
                atm_val=atm1,
                color_iv="#38bdf8",
                color_fly="#fbbf24",
                show_labels=show_labels,
            )
            st.plotly_chart(fig_p1, use_container_width=True)

        with col_p2:
            fig_p2 = create_single_date_panel_chart(
                date=date2,
                strike_df=strike_f2,
                fly_df=fly_df2,
                use_offset=use_offset,
                atm_val=atm2,
                color_iv="#f59e0b",
                color_fly="#34d399",
                show_labels=show_labels,
            )
            st.plotly_chart(fig_p2, use_container_width=True)

    st.markdown("---")

    # ---------------------------------------------------------------------------
    # Cross-Strike Consecutive Inspection Grid
    # ---------------------------------------------------------------------------
    st.markdown("### 📊 3. Cross-Strike Consecutive Inspection Grid")
    st.markdown(
        "Compare each strike level across Day $T$ and Day $T+1$. By default, strikes are matched by **ATM Moneyness Offset** "
        "(e.g. $\\text{ATM}-900$ on Day $T$ is compared directly with $\\text{ATM}-900$ on Day $T+1$ in a single row), "
        "allowing perfect like-for-like comparison despite the spot shift."
    )

    grid_alignment = st.radio(
        "Inspection Grid Alignment Mode:",
        options=[
            "ATM Moneyness Offset (Single Row: ATM − 900 to ATM + 900)",
            "Fixed Absolute Strike Price (K)",
        ],
        index=0,
        horizontal=True,
        help="Select ATM Moneyness Offset to compare constant delta / moneyness positions in a single row, or Fixed Absolute Strike Price to compare the exact same strike number.",
    )

    # Build Master Comparative Table based on chosen alignment
    matrix_rows = []

    if "ATM Moneyness Offset" in grid_alignment:
        # Aligns both dates in a single row by relative distance from ATM (K - ATM)
        # All unique offsets from both dates
        all_offsets = sorted(list(set(
            [round(x, 1) for x in strike_f1["atm_offset"].dropna().tolist()] +
            [round(x, 1) for x in strike_f2["atm_offset"].dropna().tolist()]
        )))

        # Build quick lookups for flies by offset
        fly_lookup1 = {round(row["atm_offset"], 1): row for _, row in fly_df1.iterrows()}
        fly_lookup2 = {round(row["atm_offset"], 1): row for _, row in fly_df2.iterrows()}

        for off in all_offsets:
            r1_s = strike_f1[strike_f1["atm_offset"].round(1) == off]
            r2_s = strike_f2[strike_f2["atm_offset"].round(1) == off]

            k1 = float(r1_s["strike"].iloc[0]) if not r1_s.empty else (atm1 + off)
            k2 = float(r2_s["strike"].iloc[0]) if not r2_s.empty else (atm2 + off)

            iv1 = float(r1_s["iv_pct"].iloc[0]) if not r1_s.empty else None
            iv2 = float(r2_s["iv_pct"].iloc[0]) if not r2_s.empty else None
            d_iv = (iv2 - iv1) if (iv1 is not None and iv2 is not None) else None

            # Fly match by offset
            f1_row = fly_lookup1.get(off)
            f2_row = fly_lookup2.get(off)

            fly_iv1 = float(f1_row["initial_iv_fly_pct"]) if f1_row is not None else None
            fly_iv2 = float(f2_row["initial_iv_fly_pct"]) if f2_row is not None else None

            # Fallback curvature calculation from smile points if wings exist (e.g. at ATM 0)
            if fly_iv1 is None and iv1 is not None:
                r_low = strike_f1[strike_f1["atm_offset"].round(1) == round(off - 100, 1)]
                r_upp = strike_f1[strike_f1["atm_offset"].round(1) == round(off + 100, 1)]
                if not r_low.empty and not r_upp.empty:
                    fly_iv1 = float(r_low["iv_pct"].iloc[0]) - 2.0 * iv1 + float(r_upp["iv_pct"].iloc[0])

            if fly_iv2 is None and iv2 is not None:
                r_low2 = strike_f2[strike_f2["atm_offset"].round(1) == round(off - 100, 1)]
                r_upp2 = strike_f2[strike_f2["atm_offset"].round(1) == round(off + 100, 1)]
                if not r_low2.empty and not r_upp2.empty:
                    fly_iv2 = float(r_low2["iv_pct"].iloc[0]) - 2.0 * iv2 + float(r_upp2["iv_pct"].iloc[0])

            d_fly_iv = (fly_iv2 - fly_iv1) if (fly_iv1 is not None and fly_iv2 is not None) else None

            prem1 = float(f1_row["initial_fly_premium"]) if f1_row is not None else None
            prem2 = float(f2_row["initial_fly_premium"]) if f2_row is not None else None
            d_prem = (prem2 - prem1) if (prem1 is not None and prem2 is not None) else None
            pct_prem = ((prem2 - prem1) / prem1 * 100.0) if (prem1 and prem2 and prem1 > 0) else None

            if off < 0:
                side_tag = "OTM Put"
            elif off == 0:
                side_tag = "ATM"
            else:
                side_tag = "OTM Call"

            matrix_rows.append({
                "Offset (pts)": f"{off:+.0f} pts",
                "Moneyness Level": f"ATM {off:+.0f}" if off != 0 else "ATM (0)",
                "Type": side_tag,
                f"K ({date1})": f"{k1:.0f}",
                f"K ({date2})": f"{k2:.0f}",
                f"IV {date1} (%)": _format_pct(iv1),
                f"IV {date2} (%)": _format_pct(iv2),
                "Δ IV (pts)": _format_pts(d_iv),
                f"Fly IV {date1} (pts)": _format_pts(fly_iv1),
                f"Fly IV {date2} (pts)": _format_pts(fly_iv2),
                "Δ Fly IV (pts)": _format_pts(d_fly_iv),
                f"Fly Prem {date1} ($)": _format_currency(prem1),
                f"Fly Prem {date2} ($)": _format_currency(prem2),
                "Δ Prem ($)": _format_delta_curr(d_prem),
                "% Δ Prem": f"{pct_prem:+.1f}%" if pct_prem is not None else "—",
            })

    else:
        # Aligns by absolute index strike price K
        all_strikes = sorted(list(set(strike_f1["strike"].tolist() + strike_f2["strike"].tolist())))
        fly_lookup1_k = {row["centre_strike"]: row for _, row in fly_df1.iterrows()}
        fly_lookup2_k = {row["centre_strike"]: row for _, row in fly_df2.iterrows()}

        for k in all_strikes:
            r1_s = strike_f1[strike_f1["strike"] == k]
            r2_s = strike_f2[strike_f2["strike"] == k]

            iv1 = float(r1_s["iv_pct"].iloc[0]) if not r1_s.empty else None
            iv2 = float(r2_s["iv_pct"].iloc[0]) if not r2_s.empty else None
            d_iv = (iv2 - iv1) if (iv1 is not None and iv2 is not None) else None

            off1 = k - atm1
            off2 = k - atm2

            f1_row = fly_lookup1_k.get(k)
            f2_row = fly_lookup2_k.get(k)

            fly_iv1 = float(f1_row["initial_iv_fly_pct"]) if f1_row is not None else None
            fly_iv2 = float(f2_row["initial_iv_fly_pct"]) if f2_row is not None else None
            d_fly_iv = (fly_iv2 - fly_iv1) if (fly_iv1 is not None and fly_iv2 is not None) else None

            prem1 = float(f1_row["initial_fly_premium"]) if f1_row is not None else None
            prem2 = float(f2_row["initial_fly_premium"]) if f2_row is not None else None
            d_prem = (prem2 - prem1) if (prem1 is not None and prem2 is not None) else None
            pct_prem = ((prem2 - prem1) / prem1 * 100.0) if (prem1 and prem2 and prem1 > 0) else None

            side_label = r1_s["option_side"].iloc[0].upper() if not r1_s.empty else (r2_s["option_side"].iloc[0].upper() if not r2_s.empty else "—")

            matrix_rows.append({
                "Strike K": f"{k:.0f}",
                f"Offset {date1}": f"{off1:+.0f} pts",
                f"Offset {date2}": f"{off2:+.0f} pts",
                "Side": side_label,
                f"IV {date1} (%)": _format_pct(iv1),
                f"IV {date2} (%)": _format_pct(iv2),
                "Δ IV (pts)": _format_pts(d_iv),
                f"Fly IV {date1} (pts)": _format_pts(fly_iv1),
                f"Fly IV {date2} (pts)": _format_pts(fly_iv2),
                "Δ Fly IV (pts)": _format_pts(d_fly_iv),
                f"Fly Prem {date1} ($)": _format_currency(prem1),
                f"Fly Prem {date2} ($)": _format_currency(prem2),
                "Δ Prem ($)": _format_delta_curr(d_prem),
                "% Δ Prem": f"{pct_prem:+.1f}%" if pct_prem is not None else "—",
            })

    grid_df = pd.DataFrame(matrix_rows)

    # Sub-tabs in Section 3: Fly Premiums & Structure Metrics Breakdown
    tab_fly_grid, tab_fly_struct_grid, tab_struct_grid = st.tabs([
        "🦅 100-pt Butterfly Premiums & Strike IVs",
        "💵 Fly Premium Skew, Fly RR, Curvature & Kurtosis Breakdown ($/fly)",
        "⚖️ Volatility Smile Skew, Risk Reversal, Curvature & Kurtosis Breakdown (vol pts)",
    ])

    with tab_fly_grid:
        tbl_c1, tbl_c2 = st.columns([3.2, 0.8])
        with tbl_c1:
            st.dataframe(grid_df, use_container_width=True, height=420)
        with tbl_c2:
            st.markdown(
                """
                **Column Reference:**
                - **Moneyness / Offset:** Relative strike distance from ATM ($K - ATM$).
                - **K(T) / K(T+1):** Exact strikes evaluated on each date.
                - **IV:** Implied Volatility ($IV$).
                - **Δ IV:** Observed daily IV smile shift.
                - **Fly IV:** Local curvature $= IV(K-h) - 2IV(K) + IV(K+h)$.
                - **Fly Prem:** 100-pt butterfly debit cost $= P(K-h) - 2P(K) + P(K+h)$.
                - **Δ Prem:** Daily mark-to-market P&L.
                """
            )
            csv_bytes = grid_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Table (CSV)",
                data=csv_bytes,
                file_name=f"spx_consecutive_strike_data_{date1}_to_{date2}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with tab_fly_struct_grid:
        # Build Dedicated Butterfly Premium Structure Table ($/fly)
        ft1 = fly_struct1["table"]
        ft2 = fly_struct2["table"]
        merged_ft = pd.merge(ft1, ft2, on="offset", suffixes=("_1", "_2"))

        f_rows = []
        for _, f_row in merged_ft.iterrows():
            h_off = float(f_row["offset"])
            fc1 = f_row["fly_call_1"]
            fc2 = f_row["fly_call_2"]
            d_fc = (fc2 - fc1) if (fc1 is not None and fc2 is not None) else None

            fp1 = f_row["fly_put_1"]
            fp2 = f_row["fly_put_2"]
            d_fp = (fp2 - fp1) if (fp1 is not None and fp2 is not None) else None

            cs1 = f_row["call_skew_1"]
            cs2 = f_row["call_skew_2"]
            d_cs = (cs2 - cs1) if (cs1 is not None and cs2 is not None) else None

            ps1 = f_row["put_skew_1"]
            ps2 = f_row["put_skew_2"]
            d_ps = (ps2 - ps1) if (ps1 is not None and ps2 is not None) else None

            rr1 = f_row["risk_reversal_1"]
            rr2 = f_row["risk_reversal_2"]
            d_rr = (rr2 - rr1) if (rr1 is not None and rr2 is not None) else None

            c1 = f_row["curvature_1"]
            c2 = f_row["curvature_2"]
            d_c = (c2 - c1) if (c1 is not None and c2 is not None) else None

            ks1 = f_row["kurtosis_spread_1"]
            ks2 = f_row["kurtosis_spread_2"]
            d_ks = (ks2 - ks1) if (ks1 is not None and ks2 is not None) else None

            ret1 = f_row["kurtosis_ratio_1"]
            ret2 = f_row["kurtosis_ratio_2"]
            d_ret = (ret2 - ret1) if (ret1 is not None and ret2 is not None) else None

            f_rows.append({
                "Offset (ΔK)": f"±{h_off:.0f} pts",
                f"Call Fly {date1}": _format_currency(fc1),
                f"Call Fly {date2}": _format_currency(fc2),
                "Δ Call Fly": _format_delta_curr(d_fc),
                f"Put Fly {date1}": _format_currency(fp1),
                f"Put Fly {date2}": _format_currency(fp2),
                "Δ Put Fly": _format_delta_curr(d_fp),
                f"Call Skew {date1}": _format_delta_curr(cs1),
                f"Call Skew {date2}": _format_delta_curr(cs2),
                f"Put Skew {date1}": _format_delta_curr(ps1),
                f"Put Skew {date2}": _format_delta_curr(ps2),
                f"Fly RR {date1}": _format_delta_curr(rr1),
                f"Fly RR {date2}": _format_delta_curr(rr2),
                "Δ Fly RR": _format_delta_curr(d_rr),
                f"Fly Curv {date1}": _format_delta_curr(c1),
                f"Fly Curv {date2}": _format_delta_curr(c2),
                "Δ Fly Curv": _format_delta_curr(d_c),
                f"Kurtosis Spread {date1}": _format_delta_curr(ks1),
                f"Kurtosis Spread {date2}": _format_delta_curr(ks2),
                "Δ Kurtosis": _format_delta_curr(d_ks),
                f"Retention {date1}": f"{ret1 * 100.0:.1f}%" if ret1 is not None else "—",
                f"Retention {date2}": f"{ret2 * 100.0:.1f}%" if ret2 is not None else "—",
                "Δ Retention": f"{(d_ret * 100.0):+.1f}%" if d_ret is not None else "—",
            })

        fly_struct_grid_df = pd.DataFrame(f_rows)
        f_tbl_c1, f_tbl_c2 = st.columns([3.2, 0.8])
        with f_tbl_c1:
            st.dataframe(fly_struct_grid_df, use_container_width=True, height=420)
        with f_tbl_c2:
            st.markdown(
                """
                **Fly Structure Reference ($/contract):**
                - **Call Fly Skew ($):** $F_{Call}(ATM + h) - F(ATM)$.
                - **Put Fly Skew ($):** $F_{Put}(ATM - h) - F(ATM)$.
                - **Fly Risk Reversal ($):** $F_{Call}(ATM + h) - F_{Put}(ATM - h)$ (dollar premium asymmetry).
                - **Fly Curvature ($):** $\\frac{F_{Put} + F_{Call}}{2} - F(ATM)$ (dollar smile convexity).
                - **Kurtosis Fly Spread ($):** $\\frac{F(+2h) + F(-2h)}{2} - \\frac{F(+h) + F(-h)}{2}$ (outer wing vs inner wing fly spread).
                - **Wing Retention Ratio (%):** $\\frac{(F_P + F_C) / 2}{F(ATM)}$ (% of ATM fly price retained).
                """
            )
            csv_fly_struct_bytes = fly_struct_grid_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Fly Structure (CSV)",
                data=csv_fly_struct_bytes,
                file_name=f"spx_fly_premium_structure_{date1}_to_{date2}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with tab_struct_grid:
        # Build Dedicated Higher-Order IV Smile Structure Table
        struct_table1 = struct_metrics1["table"]
        struct_table2 = struct_metrics2["table"]

        merged_struct = pd.merge(
            struct_table1,
            struct_table2,
            on="offset",
            suffixes=("_1", "_2"),
        )

        s_rows = []
        for _, s_row in merged_struct.iterrows():
            h_off = float(s_row["offset"])
            call_k1 = atm1 + h_off
            call_k2 = atm2 + h_off
            put_k1 = atm1 - h_off
            put_k2 = atm2 - h_off

            cs1 = s_row["call_skew_1"]
            cs2 = s_row["call_skew_2"]
            d_cs = (cs2 - cs1) if (cs1 is not None and cs2 is not None) else None

            ps1 = s_row["put_skew_1"]
            ps2 = s_row["put_skew_2"]
            d_ps = (ps2 - ps1) if (ps1 is not None and ps2 is not None) else None

            rr1 = s_row["risk_reversal_1"]
            rr2 = s_row["risk_reversal_2"]
            d_rr = (rr2 - rr1) if (rr1 is not None and rr2 is not None) else None

            c1 = s_row["curvature_1"]
            c2 = s_row["curvature_2"]
            d_c = (c2 - c1) if (c1 is not None and c2 is not None) else None

            k1 = s_row["kurtosis_ratio_1"]
            k2 = s_row["kurtosis_ratio_2"]
            d_k = (k2 - k1) if (k1 is not None and k2 is not None) else None

            s_rows.append({
                "Offset (ΔK)": f"±{h_off:.0f} pts",
                f"Call K ({date1})": f"{call_k1:.0f}",
                f"Call K ({date2})": f"{call_k2:.0f}",
                f"Put K ({date1})": f"{put_k1:.0f}",
                f"Put K ({date2})": f"{put_k2:.0f}",
                f"Call Skew {date1}": _format_pts(cs1),
                f"Call Skew {date2}": _format_pts(cs2),
                "Δ Call Skew": _format_pts(d_cs),
                f"Put Skew {date1}": _format_pts(ps1),
                f"Put Skew {date2}": _format_pts(ps2),
                "Δ Put Skew": _format_pts(d_ps),
                f"Risk Reversal {date1}": _format_pts(rr1),
                f"Risk Reversal {date2}": _format_pts(rr2),
                "Δ RR (Skew Shift)": _format_pts(d_rr),
                f"Curvature {date1}": _format_pts(c1),
                f"Curvature {date2}": _format_pts(c2),
                "Δ Curvature": _format_pts(d_c),
                f"Kurtosis Ratio {date1}": f"{k1:.3f}x" if k1 is not None else "—",
                f"Kurtosis Ratio {date2}": f"{k2:.3f}x" if k2 is not None else "—",
                "Δ Kurtosis": f"{d_k:+.3f}" if d_k is not None else "—",
            })

        struct_grid_df = pd.DataFrame(s_rows)
        s_tbl_c1, s_tbl_c2 = st.columns([3.2, 0.8])
        with s_tbl_c1:
            st.dataframe(struct_grid_df, use_container_width=True, height=420)
        with s_tbl_c2:
            st.markdown(
                """
                **Structure Formula Reference:**
                - **Call Skew:** $IV(ATM + h) - IV(ATM)$.
                - **Put Skew:** $IV(ATM - h) - IV(ATM)$.
                - **Risk Reversal (RR):** $IV_{Call} - IV_{Put} = \\text{Call Skew} - \\text{Put Skew}$.
                - **Curvature:** $\\frac{IV_{Put} + IV_{Call}}{2} - IV_{ATM}$.
                - **Kurtosis Ratio:** $\\frac{\\text{Curvature}(h)}{(h/100)^2 \\cdot \\text{Curvature}(100)}$ (baseline = 1.0 under pure quadratic smile).
                """
            )
            csv_struct_bytes = struct_grid_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Structure (CSV)",
                data=csv_struct_bytes,
                file_name=f"spx_smile_structure_{date1}_to_{date2}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    st.markdown("---")

    # ---------------------------------------------------------------------------
    # Single Strike 3-Leg Deconstruction Box
    # ---------------------------------------------------------------------------
    st.markdown("### 🔬 4. Single-Strike 3-Leg Butterfly Drilldown Inspector")
    st.markdown(
        "Select a moneyness offset or strike to deconstruct the exact 3 option legs (lower wing, body, upper wing) "
        "and verify how leg-by-leg premiums and IVs combine to determine the net butterfly P&L."
    )

    # Moneyness offset selection for drilldown ensures both dates exist and match
    fly_offsets = sorted(list(set(
        [round(x, 1) for x in fly_df1["atm_offset"].dropna().tolist()] +
        [round(x, 1) for x in fly_df2["atm_offset"].dropna().tolist()]
    )))

    if fly_offsets:
        default_off_idx = len(fly_offsets) // 2
        sel_off = st.selectbox(
            "Select Butterfly Moneyness Offset to Deconstruct:",
            options=fly_offsets,
            index=default_off_idx,
            format_func=lambda val: f"ATM {val:+.0f} pts (Day T Strike: {atm1 + val:.0f} | Day T+1 Strike: {atm2 + val:.0f})",
        )

        f1_row = fly_df1[fly_df1["atm_offset"].round(1) == sel_off]
        f2_row = fly_df2[fly_df2["atm_offset"].round(1) == sel_off]

        if not f1_row.empty and not f2_row.empty:
            f1 = f1_row.iloc[0]
            f2 = f2_row.iloc[0]

            col_leg1, col_leg2, col_leg3, col_leg_tot = st.columns(4)

            # Lower leg
            d_p_low = f2["lower_premium"] - f1["lower_premium"]
            d_iv_low = f2["lower_iv_pct"] - f1["lower_iv_pct"]
            with col_leg1:
                st.markdown(
                    f"""
                    <div class="consec-card">
                        <div class="consec-card-title">Lower Wing (+1): {f1['lower_strike']:.0f} &rarr; {f2['lower_strike']:.0f}</div>
                        <div class="consec-card-val-row">${f1['lower_premium']:.2f} &rarr; ${f2['lower_premium']:.2f}</div>
                        <div class="consec-badge-row">
                            <span>Δ Prem: {d_p_low:+.2f}</span>
                            <span style="color: #484f58;">&bull;</span>
                            <span>Δ IV: {d_iv_low:+.3f} pts</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Middle leg
            d_p_mid = f2["middle_premium"] - f1["middle_premium"]
            d_iv_mid = f2["middle_iv_pct"] - f1["middle_iv_pct"]
            with col_leg2:
                st.markdown(
                    f"""
                    <div class="consec-card">
                        <div class="consec-card-title">Middle Body (−2): {f1['centre_strike']:.0f} &rarr; {f2['centre_strike']:.0f}</div>
                        <div class="consec-card-val-row">${f1['middle_premium']:.2f} &rarr; ${f2['middle_premium']:.2f}</div>
                        <div class="consec-badge-row">
                            <span>Δ Prem: {d_p_mid:+.2f}</span>
                            <span style="color: #484f58;">&bull;</span>
                            <span>Δ IV: {d_iv_mid:+.3f} pts</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Upper leg
            d_p_upp = f2["upper_premium"] - f1["upper_premium"]
            d_iv_upp = f2["upper_iv_pct"] - f1["upper_iv_pct"]
            with col_leg3:
                st.markdown(
                    f"""
                    <div class="consec-card">
                        <div class="consec-card-title">Upper Wing (+1): {f1['upper_strike']:.0f} &rarr; {f2['upper_strike']:.0f}</div>
                        <div class="consec-card-val-row">${f1['upper_premium']:.2f} &rarr; ${f2['upper_premium']:.2f}</div>
                        <div class="consec-badge-row">
                            <span>Δ Prem: {d_p_upp:+.2f}</span>
                            <span style="color: #484f58;">&bull;</span>
                            <span>Δ IV: {d_iv_upp:+.3f} pts</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Package Net
            d_net_prem = f2["initial_fly_premium"] - f1["initial_fly_premium"]
            d_net_fly_iv = f2["initial_iv_fly_pct"] - f1["initial_iv_fly_pct"]
            tot_col = "#3fb950" if d_net_prem >= 0 else "#f85149"
            with col_leg_tot:
                st.markdown(
                    f"""
                    <div class="consec-card" style="border-left: 3px solid {tot_col};">
                        <div class="consec-card-title">Net 100-pt Fly Package</div>
                        <div class="consec-card-val-row" style="color: {tot_col};">${f1['initial_fly_premium']:.2f} &rarr; ${f2['initial_fly_premium']:.2f}</div>
                        <div class="consec-badge-row">
                            <span>Δ Prem: <b>{d_net_prem:+.2f}</b></span>
                            <span style="color: #484f58;">&bull;</span>
                            <span>Δ Fly IV: {d_net_fly_iv:+.4f} pts</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Arithmetic proof explanation
            st.info(
                f"**Arithmetic Verification at Moneyness Offset {sel_off:+.0f} pts:**  \n"
                f"- **Day T ({date1}) Strike {f1['centre_strike']:.0f}:**  \n"
                f"  `${f1['lower_premium']:.2f} - 2 \\times ${f1['middle_premium']:.2f} + ${f1['upper_premium']:.2f} = \\mathbf{{{f1['initial_fly_premium']:.2f}}}$`  \n"
                f"- **Day T+1 ({date2}) Strike {f2['centre_strike']:.0f}:**  \n"
                f"  `${f2['lower_premium']:.2f} - 2 \\times ${f2['middle_premium']:.2f} + ${f2['upper_premium']:.2f} = \\mathbf{{{f2['initial_fly_premium']:.2f}}}$`  \n"
                f"- **Observed Daily Net Dollar Difference:**  \n"
                f"  `{d_p_low:+.2f} (lower) - 2 \\times ({d_p_mid:+.2f}) (body) + {d_p_upp:+.2f} (upper) = \\mathbf{{{d_net_prem:+.2f}}}$`"
            )

    # ---------------------------------------------------------------------------
    # Educational Mental Model Reference Guide
    # ---------------------------------------------------------------------------
    with st.expander("🧠 **Mental Model: How to Fit IV Smile Shifts to Butterfly Price Moves in Your Mind**", expanded=False):
        st.markdown(
            f"""
            ### The Three Core Rules of Consecutive Smile Shifts:

            1. **Level Shift ($\\Delta L = {diff_factors.delta_level:+.4f}$ pts):**
               - A parallel rise in ATM IV lifts the baseline of all strikes.
               - Because a butterfly is **long 1 lower, short 2 body, long 1 upper**, the linear vega exposure roughly cancels at ATM ($\\text{{Vega}}_{{fly}} \\approx 0$).
               - Away from ATM, butterflies have non-zero vega because wings and bodies have different moneyness.

            2. **Skew Shift ($\\Delta S = {diff_factors.delta_skew:+.4f}$ pts):**
               - When skew twists, OTM calls and OTM puts move in opposite directions.
               - A flattening skew ($\\Delta S > 0$, as seen between Aug 3 and Aug 4) raises Call wing IVs relative to Put wing IVs.

            3. **Curvature Shift ($\\Delta C = {diff_factors.delta_curvature:+.4f}$ pts):**
               - Directly governs the **Fly IV value**!
               - $\\text{{Fly IV}}(K) = IV(K-h) - 2IV(K) + IV(K+h) \\approx 2 C \\left(\\frac{{h}}{{H}}\\right)^2$.
               - When curvature expands ($\\Delta C > 0$), outer wings gain more IV than the body, directly expanding the Fly IV and making the butterfly more expensive.
               - When curvature flattens ($\\Delta C < 0$), the butterfly compresses.

            4. **Underlying Spot Drift ($\\Delta S_0 = {spot2 - spot1:+.1f}$ pts):**
               - Because SPX drifted from ${spot1:.1f} \\to {spot2:.1f}$, fixed strikes changed moneyness.
               - By inspecting the **ATM Moneyness Offset** table above, you compare strikes at the exact same distance to spot on both days, isolating pure smile dynamics.

            5. **Call Skew & Put Skew Dynamics:**
               - **Call Skew:** $IV(ATM + h) - IV(ATM)$. Typically negative in equity index options as call wings are priced at a discount to ATM.
               - **Put Skew:** $IV(ATM - h) - IV(ATM)$. Typically positive and steep, reflecting high crash-protection premium demand.

            6. **Skew / Risk Reversal ($IV_{{Call}} - IV_{{Put}}$):**
               - Measures the asymmetry between upside and downside wings.
               - In SPX, Risk Reversal is negative (e.g. ${b300_1.get('risk_reversal', 0.0):.2f}$ pts on {date1}).
               - A positive shift ($\\Delta RR > 0$) indicates **skew flattening** (puts softening or calls being bid up).
               - A negative shift ($\\Delta RR < 0$) indicates **skew steepening** (crash protection bid escalating).

            7. **Curvature ($C$) vs Local Fly IV:**
               - **Curvature:** $\\frac{{IV(ATM-h) + IV(ATM+h)}}{{2}} - IV(ATM)$.
               - Measures how aggressively both wings curve upward relative to ATM.
               - At ATM, the Fly IV equals $2 \\times \\text{{Curvature}}(h)$.

            8. **Smile Kurtosis & Fat-Tail Heaviness (vol pts):**
               - In a pure quadratic smile, curvature scales strictly proportional to $(h/100)^2$, yielding a **Kurtosis Ratio of 1.0**.
               - When the ratio exceeds 1.0 or $a_4$ increases, deep OTM wings are being marked up beyond quadratic convexity, signifying heightened tail risk or jump expectation.

            9. **Butterfly Dollar Skew & Fly Risk Reversal ($/fly):**
               - $\\text{{Fly RR}}(h) = F_{{Call}}(ATM + h) - F_{{Put}}(ATM - h)$.
               - Measures the net dollar asymmetry between upside and downside 100-pt butterflies.
               - In SPX, Call Flies typically trade at a premium over equidistant Put Flies at intermediate moneyness (+300 pts: ${fb300_1.get('risk_reversal', 0.0):+.2f} on {date1} \\to {fb300_2.get('risk_reversal', 0.0):+.2f} on {date2}).

            10. **Fly Curvature & Kurtosis Butterfly Spread ($/contract):**
               - **Fly Curvature ($):** $\\frac{{F_{{Put}} + F_{{Call}}}}{{2}} - F(ATM)$ measures the dollar convex drop from ATM.
               - **Kurtosis Butterfly Spread ($):** Spread of trading outer wing butterflies ($2h$) against inner wing butterflies ($h$).
               - **Wing Retention Ratio (%):** Percentage of ATM butterfly price retained at moneyness $h$.
            """
        )
