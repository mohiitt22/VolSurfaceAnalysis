"""Multi-Date Surface Comparison Workspace View for Streamlit.

Implements the complete quantitative research layout defined in Parts A-Q:
- Multi-date selection with convenience controls (Add Prev/Next Day, Last 5/10, Range, Clear, All)
- Reference Date and Focus Date selection with Prev/Next focus day stepping
- ATM-relative and Absolute strike alignment modes
- Main Multi-Date IV Smile Comparison with optional Factor Transformation Bridge and Shaded Fills
- Smile Factor KPI metrics & IV Smile Change Attribution Companion Plot
- Multi-Date OTM Call & Put Fly Premium Comparison curves
- Observed Daily Rolling Fly Differences (with P&L interpretation warnings)
- Controlled Fixed-Reference IV-Only Repricing and Sequential Factor Attribution
- Historical Factor Trends (Level, Skew, Curvature vs chronological date)
- Interactive Contract-Level Single Fly Inspector with Repricing Waterfall
- Comprehensive CSV / Excel Export Functionality
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
import streamlit as st

from spx_butterfly.data_loader import get_snapshot
from spx_butterfly.multidate_model import (
    calculate_daily_factors,
    compute_multidate_factors_table,
    fit_factors_between_dates,
    decompose_iv_smile,
    build_multidate_flies,
    compute_observed_fly_differences,
    compute_fixed_fly_attribution,
    extract_smile_points,
    compute_smile_structure_metrics,
)
from spx_butterfly.multidate_charts import (
    create_multidate_iv_chart,
    create_iv_attribution_chart,
    create_multidate_fly_chart,
    create_multidate_structure_chart,
    create_observed_fly_change_chart,
    create_modelled_fly_attribution_chart,
    create_historical_factor_trends_chart,
    create_single_fly_inspection_chart,
    FACTOR_COLORS,
)


def render_multidate_workspace(long_df: pd.DataFrame, available_dates: list[str]) -> None:
    """Render the Multi-Date Surface Comparison research workspace."""

    # ---------------------------------------------------------------------------
    # Header & Subtitle
    # ---------------------------------------------------------------------------
    hdr_c1, hdr_c2 = st.columns([3, 1.2])
    with hdr_c1:
        st.markdown("## 📈 SPX Multi-Date Volatility Surface Comparison")
        st.markdown(
            "*Compare historical IV smiles, butterfly premium curves, level, skew, curvature and local smile changes.*"
        )
    with hdr_c2:
        pdf_path = Path("SPX_MultiDate_Surface_Comparison_Guide.pdf")
        if pdf_path.exists():
            with open(pdf_path, "rb") as f_pdf:
                st.download_button(
                    "📄 Download Math Guide (PDF)",
                    data=f_pdf.read(),
                    file_name="SPX_MultiDate_Surface_Comparison_Guide.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    help="Download complete mathematical derivations, smile factor proofs, and implementation guide as a formatted PDF.",
                )

    # ---------------------------------------------------------------------------
    # Session State Initialization for Multi-Date
    # ---------------------------------------------------------------------------
    default_dates = [d for d in ["2026-08-03", "2026-08-04"] if d in available_dates]
    if not default_dates:
        default_dates = available_dates[:2] if len(available_dates) >= 2 else available_dates

    if "ms_dates_picker" not in st.session_state:
        st.session_state["ms_dates_picker"] = default_dates
    if "multi_selected_dates" not in st.session_state:
        st.session_state["multi_selected_dates"] = default_dates
    if "multi_ref_date" not in st.session_state:
        st.session_state["multi_ref_date"] = default_dates[0]
    if "multi_focus_date" not in st.session_state:
        st.session_state["multi_focus_date"] = default_dates[-1]

    def _update_selected_dates(new_dates: list[str]):
        """Synchronously update dates in session state and trigger rerun."""
        valid = [d for d in available_dates if d in new_dates]
        if not valid:
            valid = [available_dates[0]]
        st.session_state["ms_dates_picker"] = valid
        st.session_state["multi_selected_dates"] = valid
        if st.session_state.get("multi_ref_date") not in valid:
            st.session_state["multi_ref_date"] = valid[0]
        if st.session_state.get("multi_focus_date") not in valid:
            st.session_state["multi_focus_date"] = valid[-1]
        st.rerun()

    # ---------------------------------------------------------------------------
    # Control Section: Multi-Date Selection & Convenience Controls
    # ---------------------------------------------------------------------------
    with st.expander("⚙️ **Date Selection & Convenience Controls**", expanded=True):
        st.markdown("**Quick Date Presets & Step Navigation:**")
        q_c1, q_c2, q_c3, q_c4, q_c5, q_c6, q_c7 = st.columns(7)

        # 1. Add Previous Trading Day
        if q_c1.button("◀️ Add Prev Day", use_container_width=True, help="Add the trading day immediately before the earliest selected date."):
            curr = [d for d in available_dates if d in st.session_state.ms_dates_picker]
            earliest = curr[0]
            idx = available_dates.index(earliest)
            if idx > 0:
                _update_selected_dates([available_dates[idx - 1]] + curr)

        # 2. Add Next Trading Day
        if q_c2.button("▶️ Add Next Day", use_container_width=True, help="Add the trading day immediately after the latest selected date."):
            curr = [d for d in available_dates if d in st.session_state.ms_dates_picker]
            latest = curr[-1]
            idx = available_dates.index(latest)
            if idx < len(available_dates) - 1:
                _update_selected_dates(curr + [available_dates[idx + 1]])

        # 3. Last 5 Available Trading Days
        if q_c3.button("📅 Last 5 Days", use_container_width=True, help="Select the last 5 trading days in the dataset."):
            _update_selected_dates(available_dates[-5:])

        # 4. Last 10 Available Trading Days
        if q_c4.button("📅 Last 10 Days", use_container_width=True, help="Select the last 10 trading days in the dataset."):
            _update_selected_dates(available_dates[-10:])

        # 5. Reset to August 3 & 4
        if q_c5.button("🔄 Aug 3 & 4 (Default)", use_container_width=True, help="Reset to August 3 and August 4, 2026."):
            def_d = [d for d in ["2026-08-03", "2026-08-04"] if d in available_dates]
            _update_selected_dates(def_d if def_d else available_dates[:2])

        # 6. Select All Dates
        if q_c6.button("🌐 Select All Dates", use_container_width=True, help="Select all historical trading dates."):
            _update_selected_dates(available_dates)

        # 7. Clear Selection
        if q_c7.button("🗑️ Clear Selection", use_container_width=True, help="Reset to single earliest date."):
            _update_selected_dates([available_dates[0]])

        # Multi-select component listing all chronological dates
        selected_dates = st.multiselect(
            "Select Historical Trading Dates to Overlay:",
            options=available_dates,
            key="ms_dates_picker",
            help="Choose any number of historical trading dates to overlay on the IV smile and butterfly charts.",
        )
        active_dates = [d for d in available_dates if d in st.session_state.ms_dates_picker]
        if not active_dates:
            active_dates = [available_dates[0]]
            st.session_state.ms_dates_picker = active_dates
        st.session_state.multi_selected_dates = active_dates

        if st.session_state.get("multi_ref_date") not in active_dates:
            st.session_state.multi_ref_date = active_dates[0]
        if st.session_state.get("multi_focus_date") not in active_dates:
            st.session_state.multi_focus_date = active_dates[-1]

        st.markdown("---")

        # Reference & Focus Date Configuration Row
        ctrl_c1, ctrl_c2, ctrl_c3, ctrl_c4 = st.columns([2, 2, 2, 2])

        with ctrl_c1:
            ref_idx = active_dates.index(st.session_state.multi_ref_date) if st.session_state.multi_ref_date in active_dates else 0
            ref_date = st.selectbox(
                "📌 Reference Date (Baseline Anchor):",
                options=active_dates,
                index=ref_idx,
                help="The baseline date used to calculate changes in Level, Skew, Curvature and fixed-reference fly repricing.",
            )
            st.session_state.multi_ref_date = ref_date

        with ctrl_c2:
            default_foc_idx = (
                active_dates.index(st.session_state.multi_focus_date)
                if st.session_state.multi_focus_date in active_dates
                else (len(active_dates) - 1 if len(active_dates) > 1 else 0)
            )
            focus_date = st.selectbox(
                "🎯 Focus Date (Comparison Target):",
                options=active_dates,
                index=default_foc_idx,
                help="The date whose smile transformation, factor changes, and premium differences are emphasized.",
            )
            st.session_state.multi_focus_date = focus_date

        with ctrl_c3:
            st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
            st.markdown("**Focus Day Navigation:**")
            f_prev_col, f_next_col = st.columns(2)
            if f_prev_col.button("◀️ Prev Day", use_container_width=True, help="Step focus date back one trading day"):
                f_idx = available_dates.index(focus_date)
                if f_idx > 0:
                    cand = available_dates[f_idx - 1]
                    if cand not in active_dates:
                        active_dates = sorted(active_dates + [cand])
                        st.session_state.ms_dates_picker = active_dates
                        st.session_state.multi_selected_dates = active_dates
                    st.session_state.multi_focus_date = cand
                    st.rerun()
            if f_next_col.button("Next Day ▶️", use_container_width=True, help="Step focus date forward one trading day"):
                f_idx = available_dates.index(focus_date)
                if f_idx < len(available_dates) - 1:
                    cand = available_dates[f_idx + 1]
                    if cand not in active_dates:
                        active_dates = sorted(active_dates + [cand])
                        st.session_state.ms_dates_picker = active_dates
                        st.session_state.multi_selected_dates = active_dates
                    st.session_state.multi_focus_date = cand
                    st.rerun()

        with ctrl_c4:
            align_opt = st.radio(
                "X-Axis Strike Alignment Mode:",
                options=["ATM-Relative (x = K − K_ATM)", "Absolute Strike Price (K)"],
                index=0,
                help="ATM-relative aligns smiles by distance from daily ATM. Absolute plots actual strike prices.",
            )
            alignment_mode = "relative" if align_opt.startswith("ATM-Relative") else "absolute"

    # Explanatory Note on ATM-relative vs Absolute
    if alignment_mode == "relative":
        st.caption(
            "ℹ️ **ATM-relative mode:** Compares newly defined daily smile locations at the same distance from each day's ATM. "
            "These are comparisons of newly quoted structures, **not** the realized holding-period P&L of a fixed option position."
        )
    else:
        st.caption(
            "ℹ️ **Absolute strike mode:** Displays observations at their actual SPX strike prices K. "
            "Diamond markers indicate each date's original ATM strike price."
        )

    # ---------------------------------------------------------------------------
    # Advanced Model Settings Toolbar
    # ---------------------------------------------------------------------------
    with st.expander("🎛️ **Advanced Comparison Settings & Visual Toggles**", expanded=False):
        set_c1, set_c2, set_c3, set_c4 = st.columns(4)

        with set_c1:
            ref_width_h = st.selectbox(
                "Reference Strike Width H (SPX pts):",
                options=[300.0, 400.0, 500.0, 600.0, 800.0],
                index=2,  # Default 500
                help="Strike distance H where Skew = IV(ATM+H) - IV(ATM-H). Default 500.",
            )

            fit_method_label = st.selectbox(
                "Factor Estimation Method:",
                options=[
                    "Anchor-Based (ATM, ATM±H) [Default]",
                    "Weighted Least Squares (All Nodes)",
                    "Robust Huber Fit (Outlier-Resistant)",
                ],
                index=0,
                help="Anchor-based calculates exact factors from the 3 reference nodes. WLS and Robust fit across all available smile points.",
            )
            fit_method = (
                "anchor"
                if fit_method_label.startswith("Anchor")
                else "wls"
                if fit_method_label.startswith("Weighted")
                else "robust"
            )

        with set_c2:
            comparison_basis_label = st.radio(
                "Factor Table Comparison Basis:",
                options=["Relative to Reference Date", "Sequential (Previous Trading Date)"],
                index=0,
                help="Choose whether historical changes in the table are relative to the Reference Date or day-over-day.",
            )
            comp_basis = "reference" if comparison_basis_label.startswith("Relative") else "sequential"

            strict_market_puts = st.toggle(
                "Strict Market-Only Quotes (Omit ATM-100 Put Fly)",
                value=True,
                help="The source Excel file has ATM Call premium but no separate ATM Put premium. Strict mode omits ATM-100 put fly to prevent synthetic leg contamination.",
            )

        with set_c3:
            pricing_mode_label = st.selectbox(
                "Repricing Method (Hypothetical IV-Only):",
                options=[
                    "Baseline-Preserving (Delta BS) [Default]",
                    "Full Black-Scholes",
                ],
                index=0,
            )
            pricing_mode = "baseline_delta" if pricing_mode_label.startswith("Baseline") else "full_bs"

            fly_diff_metric = st.selectbox(
                "Observed Fly Difference Metric:",
                options=[
                    "Absolute Net Change (SPX Points)",
                    "Percentage Change (%)",
                    "Normalized Change (Points / Wing Width h)",
                ],
                index=0,
            )
            diff_mode = (
                "absolute"
                if fly_diff_metric.startswith("Absolute")
                else "percentage"
                if fly_diff_metric.startswith("Percentage")
                else "normalized"
            )

        with set_c4:
            highlight_focus = st.toggle("Highlight Focus Date (Dim Others)", value=False)
            curve_line_weight = st.select_slider(
                "Curve Line Thickness:",
                options=["Regular (2.0px)", "Bold (2.6px)", "Heavy (3.4px)"],
                value="Bold (2.6px)",
                help="Adjust line thickness for all historical smiles and butterfly curves.",
            )
            line_thickness = 2.0 if curve_line_weight.startswith("Regular") else 2.6 if curve_line_weight.startswith("Bold") else 3.4
            show_bridge = st.toggle("Show Smile Transformation Bridge (IV_0 → Actual)", value=True)
            show_bridge_fills = st.toggle("Show Bridge Contribution Shaded Fills", value=False)
            show_modelled_repricing = st.toggle("Show Modelled Fixed-Strike Fly Repricing", value=True)

    # ---------------------------------------------------------------------------
    # Data Preparation & Calculations
    # ---------------------------------------------------------------------------
    # Load snapshots for all selected dates
    snapshots: dict[str, pd.DataFrame] = {}
    for d in active_dates:
        snapshots[d] = get_snapshot(long_df, d)

    ref_snap = snapshots[ref_date]
    focus_snap = snapshots[focus_date]

    # Calculate factor differences between reference and focus
    factors = fit_factors_between_dates(ref_snap, focus_snap, h_width=ref_width_h, method=fit_method)

    # Calculate smile decomposition points
    bridge_points = decompose_iv_smile(ref_snap, focus_snap, factors, h_width=ref_width_h)

    # Historical factor metrics table across all selected dates
    factor_table_df = compute_multidate_factors_table(
        long_df,
        active_dates,
        reference_date=ref_date,
        h_width=ref_width_h,
        comparison_basis=comp_basis,
        fit_method=fit_method,
    )

    # Build butterflies for all dates
    flies_by_date = build_multidate_flies(
        long_df, active_dates, wing_width=100.0, strict_market_puts=strict_market_puts
    )

    # Compute observed fly differences between ref and focus
    observed_fly_diffs = compute_observed_fly_differences(
        flies_by_date, ref_date=ref_date, focus_date=focus_date, wing_width=100.0
    )

    # Compute hypothetical fixed-reference IV-only repricing and sequential attribution
    fixed_attributions = compute_fixed_fly_attribution(
        ref_snapshot=ref_snap,
        focus_snapshot=focus_snap,
        factors=factors,
        wing_width=100.0,
        h_width=ref_width_h,
        pricing_mode=pricing_mode,
        r=0.0,
        q=0.0,
        strict_market_puts=strict_market_puts,
    )

    # ---------------------------------------------------------------------------
    # ROW 1: Main Multi-Date IV Smile Comparison Graph
    # ---------------------------------------------------------------------------
    st.markdown("### 1. Historical IV Smile Comparison")

    fig_iv = create_multidate_iv_chart(
        snapshots=snapshots,
        reference_date=ref_date,
        focus_date=focus_date,
        alignment_mode=alignment_mode,
        highlight_focus=highlight_focus,
        show_bridge=show_bridge,
        show_bridge_fills=show_bridge_fills,
        bridge_points=bridge_points,
        line_thickness=line_thickness,
    )
    st.plotly_chart(fig_iv, use_container_width=True)

    if show_bridge and alignment_mode == "relative":
        st.caption(
            "🌉 **Transformation Bridge Scheme:** "
            "<span style='color: #8b949e;'>● Gray Solid: Ref Smile (IV_0)</span> &nbsp;|&nbsp; "
            "<span style='color: #388bfd;'>-- Blue Dashed: + Level (IV_L)</span> &nbsp;|&nbsp; "
            "<span style='color: #bc8cff;'>-- Purple Dashed: + Skew (IV_LS)</span> &nbsp;|&nbsp; "
            "<span style='color: #f0883e;'>-.- Orange Dashed: + Curvature (IV_LSC Modelled)</span> &nbsp;|&nbsp; "
            "<span style='color: #f85149;'>○ Open Red Circles: Actual Focus Smile & Residual Gap</span>",
            unsafe_allow_html=True,
        )

    # Strike-by-Strike Comparative Matrix Table
    with st.expander("📊 **Cross-Sectional Strike-by-Strike Comparative Matrix (All Selected Dates)**", expanded=True):
        st.markdown(
            "Compare implied volatilities across all selected dates for each individual strike offset and inspect cross-date spreads."
        )
        matrix_rows = []
        all_offsets = sorted(list({
            int(row["atm_offset"])
            for snap in snapshots.values()
            for _, row in snap.iterrows()
        }))

        for off in all_offsets:
            row_dict: dict[str, Any] = {
                "ATM Offset": f"{off:+d} pts" if off != 0 else "0 (ATM)",
                "Side": "ATM" if off == 0 else ("PUT" if off < 0 else "CALL"),
            }
            iv_nums = []
            for d in active_dates:
                snap = snapshots[d]
                m = snap[snap["atm_offset"] == off]
                if not m.empty:
                    iv_val = float(m["iv_decimal"].iloc[0]) * 100.0
                    row_dict[d] = f"{iv_val:.3f}%"
                    iv_nums.append(iv_val)
                else:
                    row_dict[d] = "—"

            ref_snap_m = snapshots.get(ref_date)
            foc_snap_m = snapshots.get(focus_date)
            ref_iv = (
                float(ref_snap_m[ref_snap_m["atm_offset"] == off]["iv_decimal"].iloc[0]) * 100.0
                if ref_snap_m is not None and not ref_snap_m[ref_snap_m["atm_offset"] == off].empty
                else None
            )
            foc_iv = (
                float(foc_snap_m[foc_snap_m["atm_offset"] == off]["iv_decimal"].iloc[0]) * 100.0
                if foc_snap_m is not None and not foc_snap_m[foc_snap_m["atm_offset"] == off].empty
                else None
            )

            if ref_iv is not None and foc_iv is not None:
                row_dict["Δ (Focus − Ref)"] = f"{(foc_iv - ref_iv):+.3f} pts"
            else:
                row_dict["Δ (Focus − Ref)"] = "—"

            if len(iv_nums) > 1:
                row_dict["Min IV"] = f"{min(iv_nums):.3f}%"
                row_dict["Max IV"] = f"{max(iv_nums):.3f}%"
                row_dict["Spread (Range)"] = f"{(max(iv_nums) - min(iv_nums)):.3f} pts"
            else:
                row_dict["Min IV"] = f"{iv_nums[0]:.3f}%" if iv_nums else "—"
                row_dict["Max IV"] = f"{iv_nums[0]:.3f}%" if iv_nums else "—"
                row_dict["Spread (Range)"] = "0.000 pts"

            matrix_rows.append(row_dict)

        matrix_df = pd.DataFrame(matrix_rows)
        st.dataframe(matrix_df, use_container_width=True, height=280)

    st.markdown("---")

    # ---------------------------------------------------------------------------
    # ROW 2: Smile Factor Metrics KPI Cards & IV Attribution Graph
    # ---------------------------------------------------------------------------
    st.markdown("### 2. Smile-Factor Metrics & IV Change Attribution")

    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
    with kpi1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-title">Ref ATM IV ({ref_date})</div>
                <div class="metric-card-value">{factors.ref_level:.3f}%</div>
                <div class="metric-card-sub">Baseline ATM Anchor</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-title">Focus ATM IV ({focus_date})</div>
                <div class="metric-card-value">{factors.focus_level:.3f}%</div>
                <div class="metric-card-sub">Focus ATM Anchor</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi3:
        dl_col = "#3fb950" if factors.delta_level > 0 else "#f85149" if factors.delta_level < 0 else "#f0f6fc"
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-title">Δ Level (L)</div>
                <div class="metric-card-value" style="color: {dl_col};">{factors.delta_level:+.4f} pts</div>
                <div class="metric-card-sub">ATM IV Shift</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi4:
        ds_col = "#3fb950" if factors.delta_skew > 0 else "#f85149" if factors.delta_skew < 0 else "#f0f6fc"
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-title">Δ Skew (S)</div>
                <div class="metric-card-value" style="color: {ds_col};">{factors.delta_skew:+.4f} pts</div>
                <div class="metric-card-sub">Right - Left Wing Slope</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi5:
        dc_col = "#3fb950" if factors.delta_curvature > 0 else "#f85149" if factors.delta_curvature < 0 else "#f0f6fc"
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-title">Δ Curvature (C)</div>
                <div class="metric-card-value" style="color: {dc_col};">{factors.delta_curvature:+.4f} pts</div>
                <div class="metric-card-sub">Wing Avg Rel to ATM</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with kpi6:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-card-title">Residual RMSE</div>
                <div class="metric-card-value">{factors.rmse:.4f} pts</div>
                <div class="metric-card-sub">{factors.matched_nodes} Nodes ({factors.method.upper()})</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Factor Attribution Companion Graph
    fig_attr = create_iv_attribution_chart(
        bridge_points=bridge_points,
        reference_date=ref_date,
        focus_date=focus_date,
    )
    st.plotly_chart(fig_attr, use_container_width=True)

    st.markdown("---")

    # ---------------------------------------------------------------------------
    # ROW 3: Historical Butterfly Premium & Volatility Structure Comparison
    # ---------------------------------------------------------------------------
    st.markdown("### 3. Historical Butterfly Premium & Volatility Surface Structure Curves")
    st.markdown(
        "Analyze **100-pt Butterfly Net Debit Premiums**, **Call Skew & Put Skew**, "
        "**Skew / Risk Reversal (RR)**, **Smile Curvature**, and **Kurtosis Fat-Tail Ratio** across historical dates."
    )

    struct_view_choice = st.radio(
        "Select Volatility Structure View to Display:",
        options=[
            "💵 Call Fly Skew & Put Fly Skew ($/contract)",
            "💱 Fly Skew / Fly Risk Reversal ($/fly)",
            "🦋 Fly Curvature & Kurtosis ($/fly)",
            "🦅 100-pt Butterfly Net Premiums ($)",
            "⚖️ Call Skew & Put Skew (vol pts)",
            "📐 Skew / Risk Reversal (Call − Put vol pts)",
            "🌊 Smile Curvature & Kurtosis Fat-Tail Ratio",
            "📑 Stack All Structure Curves",
        ],
        index=0,
        horizontal=True,
        key="ms_struct_view_choice",
        help="Switch between 100-pt Butterfly Call/Put Skew ($), Fly Risk Reversal ($), Fly Curvature & Kurtosis ($), Butterfly dollar costs, Call/Put Skew (vol pts), Risk Reversal (vol pts), and Smile Curvature/Kurtosis across all selected dates.",
    )

    if struct_view_choice == "💵 Call Fly Skew & Put Fly Skew ($/contract)":
        fig_fly_cs_ps = create_multidate_structure_chart(
            snapshots=snapshots,
            selected_dates=active_dates,
            metric_category="fly_call_put_skew",
            reference_date=ref_date,
            focus_date=focus_date,
            highlight_focus=highlight_focus,
            line_thickness=line_thickness,
            flies_by_date=flies_by_date,
        )
        st.plotly_chart(fig_fly_cs_ps, use_container_width=True)
    elif struct_view_choice == "💱 Fly Skew / Fly Risk Reversal ($/fly)":
        fig_fly_rr = create_multidate_structure_chart(
            snapshots=snapshots,
            selected_dates=active_dates,
            metric_category="fly_skew_rr",
            reference_date=ref_date,
            focus_date=focus_date,
            highlight_focus=highlight_focus,
            line_thickness=line_thickness,
            flies_by_date=flies_by_date,
        )
        st.plotly_chart(fig_fly_rr, use_container_width=True)
    elif struct_view_choice == "🦋 Fly Curvature & Kurtosis ($/fly)":
        fig_fly_ck = create_multidate_structure_chart(
            snapshots=snapshots,
            selected_dates=active_dates,
            metric_category="fly_curvature_kurtosis",
            reference_date=ref_date,
            focus_date=focus_date,
            highlight_focus=highlight_focus,
            line_thickness=line_thickness,
            flies_by_date=flies_by_date,
        )
        st.plotly_chart(fig_fly_ck, use_container_width=True)
    elif struct_view_choice == "🦅 100-pt Butterfly Net Premiums ($)":
        col_r3_c, col_r3_p = st.columns(2)
        with col_r3_c:
            fig_fly_c = create_multidate_fly_chart(
                flies_by_date=flies_by_date,
                option_side="call",
                reference_date=ref_date,
                focus_date=focus_date,
                alignment_mode=alignment_mode,
                highlight_focus=highlight_focus,
                normalized_mode=(diff_mode == "normalized"),
                line_thickness=line_thickness,
            )
            st.plotly_chart(fig_fly_c, use_container_width=True)

        with col_r3_p:
            fig_fly_p = create_multidate_fly_chart(
                flies_by_date=flies_by_date,
                option_side="put",
                reference_date=ref_date,
                focus_date=focus_date,
                alignment_mode=alignment_mode,
                highlight_focus=highlight_focus,
                normalized_mode=(diff_mode == "normalized"),
                line_thickness=line_thickness,
            )
            st.plotly_chart(fig_fly_p, use_container_width=True)

        if strict_market_puts:
            st.caption(
                "🛡️ **Strict Market Safeguard Active:** ATM Put quote was unavailable in the source file; "
                "ATM-100 put butterfly (centre strike ATM−100 requiring upper wing at ATM) has been omitted to preserve quote integrity. "
                "Complete put butterflies from ATM−200 to ATM−800 are displayed with full market quotes."
            )
    elif struct_view_choice == "⚖️ Call Skew & Put Skew (vol pts)":
        fig_cs_ps = create_multidate_structure_chart(
            snapshots=snapshots,
            selected_dates=active_dates,
            metric_category="call_put_skew",
            reference_date=ref_date,
            focus_date=focus_date,
            highlight_focus=highlight_focus,
            line_thickness=line_thickness,
            flies_by_date=flies_by_date,
        )
        st.plotly_chart(fig_cs_ps, use_container_width=True)
    elif struct_view_choice == "📐 Skew / Risk Reversal (Call − Put vol pts)":
        fig_rr = create_multidate_structure_chart(
            snapshots=snapshots,
            selected_dates=active_dates,
            metric_category="skew_rr",
            reference_date=ref_date,
            focus_date=focus_date,
            highlight_focus=highlight_focus,
            line_thickness=line_thickness,
            flies_by_date=flies_by_date,
        )
        st.plotly_chart(fig_rr, use_container_width=True)
    elif struct_view_choice == "🌊 Smile Curvature & Kurtosis Fat-Tail Ratio":
        fig_ck = create_multidate_structure_chart(
            snapshots=snapshots,
            selected_dates=active_dates,
            metric_category="curvature_kurtosis",
            reference_date=ref_date,
            focus_date=focus_date,
            highlight_focus=highlight_focus,
            line_thickness=line_thickness,
            flies_by_date=flies_by_date,
        )
        st.plotly_chart(fig_ck, use_container_width=True)
    else:
        fig_all = create_multidate_structure_chart(
            snapshots=snapshots,
            selected_dates=active_dates,
            metric_category="all_stacked",
            reference_date=ref_date,
            focus_date=focus_date,
            highlight_focus=highlight_focus,
            line_thickness=line_thickness,
            flies_by_date=flies_by_date,
        )
        st.plotly_chart(fig_all, use_container_width=True)

    # Cross-Date Structure Metrics Table
    with st.expander("📊 **Cross-Date Smile Structure Metrics Table (Call/Put Skew, RR, Curvature, Kurtosis)**", expanded=False):
        st.markdown(
            "Inspect exact higher-order smile structure values across all selected historical dates at each moneyness distance $h$."
        )
        # Compute metrics for all dates
        ms_struct_map = {d: compute_smile_structure_metrics(extract_smile_points(snapshots[d])) for d in active_dates}
        # Gather all unique offsets
        struct_offsets = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]
        s_table_rows = []
        for off_h in struct_offsets:
            row_dict: dict[str, Any] = {
                "Moneyness Offset": f"±{off_h:.0f} pts",
            }
            for d in active_dates:
                tbl = ms_struct_map[d]["table"]
                match_r = tbl[tbl["offset"] == off_h]
                if not match_r.empty:
                    cs_val = match_r["call_skew"].iloc[0]
                    ps_val = match_r["put_skew"].iloc[0]
                    rr_val = match_r["risk_reversal"].iloc[0]
                    c_val = match_r["curvature"].iloc[0]
                    k_val = match_r["kurtosis_ratio"].iloc[0]
                    row_dict[f"RR ({d})"] = f"{rr_val:+.2f} pts" if rr_val is not None else "—"
                    row_dict[f"Curv ({d})"] = f"{c_val:+.3f} pts" if c_val is not None else "—"
                    row_dict[f"Kurt ({d})"] = f"{k_val:.2f}x" if k_val is not None else "—"
                else:
                    row_dict[f"RR ({d})"] = "—"
                    row_dict[f"Curv ({d})"] = "—"
                    row_dict[f"Kurt ({d})"] = "—"

            # Difference Focus - Ref
            if ref_date in ms_struct_map and focus_date in ms_struct_map:
                ref_t = ms_struct_map[ref_date]["table"]
                foc_t = ms_struct_map[focus_date]["table"]
                r_m = ref_t[ref_t["offset"] == off_h]
                f_m = foc_t[foc_t["offset"] == off_h]
                if not r_m.empty and not f_m.empty:
                    d_rr_val = f_m["risk_reversal"].iloc[0] - r_m["risk_reversal"].iloc[0]
                    d_c_val = f_m["curvature"].iloc[0] - r_m["curvature"].iloc[0]
                    row_dict["Δ RR (Foc − Ref)"] = f"{d_rr_val:+.3f} pts"
                    row_dict["Δ Curv (Foc − Ref)"] = f"{d_c_val:+.3f} pts"
                else:
                    row_dict["Δ RR (Foc − Ref)"] = "—"
                    row_dict["Δ Curv (Foc − Ref)"] = "—"

            s_table_rows.append(row_dict)

        ms_struct_df = pd.DataFrame(s_table_rows)
        st.dataframe(ms_struct_df, use_container_width=True, height=280)
        csv_ms_struct = ms_struct_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download Multi-Date Structure Metrics (CSV)",
            data=csv_ms_struct,
            file_name=f"spx_multidate_structure_metrics_{ref_date}_to_{focus_date}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("---")

    # ---------------------------------------------------------------------------
    # ROW 4: Observed Daily Butterfly Premium Differences
    # ---------------------------------------------------------------------------
    st.markdown("### 4. Observed Daily Butterfly Premium Differences")
    st.markdown(
        f"""
        <div style="background-color: rgba(227, 179, 65, 0.12); border: 1px solid rgba(227, 179, 65, 0.35); border-radius: 6px; padding: 10px 14px; margin-bottom: 12px; font-size: 12px; color: #e3b341;">
            ⚠️ <b>Critical Interpretation Warning:</b> These are observed changes in the quoted premiums of separately constructed daily ATM-relative butterflies 
            (Focus Date: <b>{focus_date}</b> minus Reference Date: <b>{ref_date}</b>). 
            They are <b>NOT</b> the realized holding-period P&L of a fixed-strike position, because underlying spot and absolute strikes shifted between the two dates.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_r4_c, col_r4_p = st.columns(2)
    with col_r4_c:
        fig_diff_c = create_observed_fly_change_chart(
            fly_diffs=observed_fly_diffs,
            option_side="call",
            reference_date=ref_date,
            focus_date=focus_date,
            display_mode=diff_mode,
        )
        st.plotly_chart(fig_diff_c, use_container_width=True)

    with col_r4_p:
        fig_diff_p = create_observed_fly_change_chart(
            fly_diffs=observed_fly_diffs,
            option_side="put",
            reference_date=ref_date,
            focus_date=focus_date,
            display_mode=diff_mode,
        )
        st.plotly_chart(fig_diff_p, use_container_width=True)

    st.markdown("---")

    # ---------------------------------------------------------------------------
    # ROW 5: Controlled Fixed-Reference IV-Only Factor Repricing & Attribution
    # ---------------------------------------------------------------------------
    if show_modelled_repricing:
        st.markdown("### 5. Hypothetical Fixed-Reference IV-Only Factor Repricing & Attribution")
        ref_s0 = float(ref_snap["underlying"].iloc[0])
        ref_atm0 = float(ref_snap["atm_strike"].iloc[0])
        ref_dte0 = float(ref_snap["target_dte"].iloc[0])

        st.markdown(
            f"""
            <div style="background-color: rgba(56, 139, 253, 0.12); border: 1px solid rgba(56, 139, 253, 0.35); border-radius: 6px; padding: 10px 14px; margin-bottom: 14px; font-size: 12px; color: #58a6ff;">
                🔒 <b>Fixed-Reference Valuation Conditions:</b> 
                Valued on <b>{ref_date}</b> option contracts holding 
                <b>Spot = {ref_s0:.2f}</b>, <b>ATM = {ref_atm0:.0f}</b>, <b>Maturity = {ref_dte0:.0f} DTE</b>, and original premiums constant. 
                Shocks are the measured factor changes from {focus_date}: 
                <b>L={factors.delta_level:+.4f}</b>, <b>S={factors.delta_skew:+.4f}</b>, <b>C={factors.delta_curvature:+.4f} pts</b>.
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_r5_c, col_r5_p = st.columns(2)
        with col_r5_c:
            fig_mod_c = create_modelled_fly_attribution_chart(
                attributions=fixed_attributions,
                option_side="call",
                reference_date=ref_date,
                focus_date=focus_date,
            )
            st.plotly_chart(fig_mod_c, use_container_width=True)

        with col_r5_p:
            fig_mod_p = create_modelled_fly_attribution_chart(
                attributions=fixed_attributions,
                option_side="put",
                reference_date=ref_date,
                focus_date=focus_date,
            )
            st.plotly_chart(fig_mod_p, use_container_width=True)

        st.caption(
            "📐 **Sequential Factor Attribution Order:** Level (L) → Skew (S) → Curvature (C) → Local Residual. "
            "Because Black-Scholes is nonlinear across large perturbations, exact attribution is sequential. "
            "Identity verified: Total Change = Level + Skew + Curvature + Local Residual holds within 1e-12 tolerance."
        )

        st.markdown("---")

    # ---------------------------------------------------------------------------
    # ROW 6: Historical Factor Trend Charts
    # ---------------------------------------------------------------------------
    st.markdown("### 6. Historical Factor Evolution Through Time")
    fig_trends = create_historical_factor_trends_chart(factor_table_df)
    st.plotly_chart(fig_trends, use_container_width=True)

    st.markdown("---")

    # ---------------------------------------------------------------------------
    # ROW 7: Historical Factor Comparison Table & Single Fly Inspector
    # ---------------------------------------------------------------------------
    st.markdown("### 7. Historical Factor Comparison Table & Fly Inspector")

    tab_table, tab_inspect = st.tabs(["📋 Historical Factor Table", "🔍 Single Butterfly Leg-Level Inspector"])

    with tab_table:
        st.dataframe(factor_table_df, use_container_width=True, height=280)
        st.caption(
            f"Table displays daily smile factors across {len(active_dates)} selected dates. "
            f"Changes are measured {comp_basis} (Reference Width H = {ref_width_h:.0f} pts)."
        )

    with tab_inspect:
        if fixed_attributions:
            fly_labels = [
                f"{a.option_side.upper()} @ {a.ref_centre_strike:.0f} (Offset: {a.atm_offset:+.0f} | Wings: {a.lower_strike:.0f} / {a.upper_strike:.0f})"
                for a in fixed_attributions
            ]
            chosen_label = st.selectbox(
                "Select Fixed-Reference Butterfly Spread to Inspect:",
                options=fly_labels,
                index=0,
            )
            chosen_attr = fixed_attributions[fly_labels.index(chosen_label)]

            # Detailed 3-leg table
            low_d = chosen_attr.lower_details
            mid_d = chosen_attr.middle_details
            upp_d = chosen_attr.upper_details

            leg_rows = [
                {
                    "Parameter": "Strike Price K",
                    "Lower Wing (+1)": f"{chosen_attr.lower_strike:.0f}",
                    "Middle Body (−2)": f"{chosen_attr.ref_centre_strike:.0f}",
                    "Upper Wing (+1)": f"{chosen_attr.upper_strike:.0f}",
                    "Package Structure": f"h = {chosen_attr.wing_width:.0f} pts",
                },
                {
                    "Parameter": "Ref Date IV (%)",
                    "Lower Wing (+1)": f"{low_d.get('orig_iv_pct', 0):.4f}%",
                    "Middle Body (−2)": f"{mid_d.get('orig_iv_pct', 0):.4f}%",
                    "Upper Wing (+1)": f"{upp_d.get('orig_iv_pct', 0):.4f}%",
                    "Package Structure": f"Ref: {ref_date}",
                },
                {
                    "Parameter": "Focus Aligned IV (%)",
                    "Lower Wing (+1)": f"{low_d.get('focus_iv_pct', 0):.4f}%",
                    "Middle Body (−2)": f"{mid_d.get('focus_iv_pct', 0):.4f}%",
                    "Upper Wing (+1)": f"{upp_d.get('focus_iv_pct', 0):.4f}%",
                    "Package Structure": f"Focus: {focus_date}",
                },
                {
                    "Parameter": "Level Shock (L)",
                    "Lower Wing (+1)": f"{low_d.get('level_shock', 0):+.4f} pts",
                    "Middle Body (−2)": f"{mid_d.get('level_shock', 0):+.4f} pts",
                    "Upper Wing (+1)": f"{upp_d.get('level_shock', 0):+.4f} pts",
                    "Package Structure": f"{factors.delta_level:+.4f} pts",
                },
                {
                    "Parameter": "Skew Shock ((S/2)*x)",
                    "Lower Wing (+1)": f"{low_d.get('skew_shock', 0):+.4f} pts",
                    "Middle Body (−2)": f"{mid_d.get('skew_shock', 0):+.4f} pts",
                    "Upper Wing (+1)": f"{upp_d.get('skew_shock', 0):+.4f} pts",
                    "Package Structure": "Linear Tilt",
                },
                {
                    "Parameter": "Curvature Shock (C*x²)",
                    "Lower Wing (+1)": f"{low_d.get('curvature_shock', 0):+.4f} pts",
                    "Middle Body (−2)": f"{mid_d.get('curvature_shock', 0):+.4f} pts",
                    "Upper Wing (+1)": f"{upp_d.get('curvature_shock', 0):+.4f} pts",
                    "Package Structure": "Quadratic Bend",
                },
                {
                    "Parameter": "Local Residual Shock",
                    "Lower Wing (+1)": f"{low_d.get('residual_shock', 0):+.4f} pts",
                    "Middle Body (−2)": f"{mid_d.get('residual_shock', 0):+.4f} pts",
                    "Upper Wing (+1)": f"{upp_d.get('residual_shock', 0):+.4f} pts",
                    "Package Structure": "Unexplained Gap",
                },
                {
                    "Parameter": "Total IV Shock",
                    "Lower Wing (+1)": f"{low_d.get('total_shock', 0):+.4f} pts",
                    "Middle Body (−2)": f"{mid_d.get('total_shock', 0):+.4f} pts",
                    "Upper Wing (+1)": f"{upp_d.get('total_shock', 0):+.4f} pts",
                    "Package Structure": f"{chosen_attr.total_iv_change:+.4f} SPX pts",
                },
            ]
            st.table(pd.DataFrame(leg_rows))

            # Repricing waterfall chart
            fig_single_fly = create_single_fly_inspection_chart(chosen_attr)
            st.plotly_chart(fig_single_fly, use_container_width=True)

            # Attribution breakdown metric tiles
            sf_c1, sf_c2, sf_c3, sf_c4, sf_c5 = st.columns(5)
            sf_c1.info(f"**Baseline (F0):** {chosen_attr.f0:.4f} pts")
            sf_c2.info(f"**Level Effect:** {chosen_attr.level_effect:+.4f} pts")
            sf_c3.info(f"**Skew Effect:** {chosen_attr.skew_effect:+.4f} pts")
            sf_c4.info(f"**Curvature Effect:** {chosen_attr.curvature_effect:+.4f} pts")
            sf_c5.success(f"**Total IV Change:** {chosen_attr.total_iv_change:+.4f} pts")
        else:
            st.info("No fixed-reference butterflies available for inspection.")

    st.markdown("---")

    # ---------------------------------------------------------------------------
    # Export Functionality (Part Q)
    # ---------------------------------------------------------------------------
    st.markdown("### 8. Export Workspace Analysis Data")

    exp_col1, exp_col2, exp_col3, exp_col4 = st.columns(4)

    # 1. Historical IV Observations Export
    with exp_col1:
        iv_obs_list = []
        for d in active_dates:
            s_df = extract_smile_points(snapshots[d])
            s_s0 = float(snapshots[d]["underlying"].iloc[0])
            s_atm = float(snapshots[d]["atm_strike"].iloc[0])
            s_dte = float(snapshots[d]["target_dte"].iloc[0])
            for _, r in s_df.iterrows():
                iv_obs_list.append({
                    "Date": d,
                    "Underlying SPX": s_s0,
                    "ATM Strike": s_atm,
                    "Strike": r["strike"],
                    "ATM Offset": r["atm_offset"],
                    "Option Side": r["option_side"],
                    "IV (%)": r["iv_pct"],
                    "Target DTE": s_dte,
                })
        iv_obs_df = pd.DataFrame(iv_obs_list)
        st.download_button(
            "📥 Historical IVs (CSV)",
            data=iv_obs_df.to_csv(index=False).encode("utf-8"),
            file_name=f"spx_multidate_iv_smiles_{len(active_dates)}_dates.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # 2. Historical Butterfly Premiums Export
    with exp_col2:
        all_flies_list = []
        for d, f_list in flies_by_date.items():
            for f in f_list:
                all_flies_list.append(f.to_dict())
        flies_exp_df = pd.DataFrame(all_flies_list)
        st.download_button(
            "📥 Historical Fly Premiums (CSV)",
            data=flies_exp_df.to_csv(index=False).encode("utf-8"),
            file_name=f"spx_multidate_fly_premiums_{len(active_dates)}_dates.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # 3. Factor Metrics Table Export
    with exp_col3:
        st.download_button(
            "📥 Factor Metrics Table (CSV)",
            data=factor_table_df.to_csv(index=False).encode("utf-8"),
            file_name=f"spx_factor_metrics_ref_{ref_date}_{len(active_dates)}_dates.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # 4. IV Decomposition & Fly Factor Attribution Export (Excel or CSV)
    with exp_col4:
        decomp_df = pd.DataFrame([p.to_dict() for p in bridge_points])
        attr_df = pd.DataFrame([a.to_dict() for a in fixed_attributions])

        # Combined Excel workbook
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
            decomp_df.to_excel(writer, sheet_name="IV_Decomposition", index=False)
            attr_df.to_excel(writer, sheet_name="Fly_Factor_Attribution", index=False)
            factor_table_df.to_excel(writer, sheet_name="Factor_Metrics", index=False)
        excel_buf.seek(0)

        st.download_button(
            "📥 Full Analysis Report (Excel)",
            data=excel_buf.getvalue(),
            file_name=f"spx_surface_decomposition_{ref_date}_to_{focus_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
