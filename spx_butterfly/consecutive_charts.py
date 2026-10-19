"""Interactive Plotly charts for Consecutive Date Analysis.

Visualizes:
1. Individual Strike IVs and Fly IV (curvature) across consecutive dates.
2. 100-pt Butterfly Net Debit Premiums and daily changes across strikes.
3. Dual-panel side-by-side or overlay comparison modes.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from spx_butterfly.multidate_charts import (
    BASE_THEME,
    BASE_AXIS_STYLE,
    apply_theme_layout,
)


def create_consecutive_iv_and_fly_iv_chart(
    date1: str,
    date2: str,
    strike_df1: pd.DataFrame,
    strike_df2: pd.DataFrame,
    fly_df1: pd.DataFrame,
    fly_df2: pd.DataFrame,
    use_offset: bool = False,
    atm1: float = 0.0,
    atm2: float = 0.0,
    show_labels: bool = False,
) -> go.Figure:
    """Create Graph 1: Two-row synchronized chart of Strike IV (top) and Fly IV curvature (bottom).

    Parameters
    ----------
    date1, date2 : str
        The two consecutive dates.
    strike_df1, strike_df2 : pd.DataFrame
        DataFrames containing strike, atm_offset, iv_pct.
    fly_df1, fly_df2 : pd.DataFrame
        DataFrames containing centre_strike, atm_offset, initial_iv_fly_pct.
    use_offset : bool
        If True, x-axis is ATM offset (K - ATM). Otherwise absolute strike (K).
    atm1, atm2 : float
        ATM strike values for reference lines.
    show_labels : bool
        If True, displays value text annotations directly on points.
    """
    x_col_strike = "atm_offset" if use_offset else "strike"
    x_col_fly = "atm_offset" if use_offset else "centre_strike"
    x_axis_label = "Strike Distance to ATM: K − K_ATM (pts)" if use_offset else "Strike Price K (pts)"

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=(
            f"<b>1A. Individual Strike Implied Volatility ($IV$) Smile:</b> {date1} vs {date2}",
            f"<b>1B. Fly IV Curvature ($IV_{{low}} - 2IV_{{mid}} + IV_{{upp}}$):</b> Local Smile Convexity (vol pts)",
        ),
        row_heights=[0.60, 0.40],
    )

    # -------------------------------------------------------------
    # SUBPLOT 1: Strike IV Smiles
    # -------------------------------------------------------------
    # Sort data
    s1 = strike_df1.sort_values(x_col_strike)
    s2 = strike_df2.sort_values(x_col_strike)

    x1 = s1[x_col_strike].values
    y1 = s1["iv_pct"].values
    x2 = s2[x_col_strike].values
    y2 = s2["iv_pct"].values

    # Trace 1: Date 1 Strike IV
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=y1,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Strike IV ({date1})",
            line=dict(color="#38bdf8", width=3.2),
            marker=dict(size=7, color="#38bdf8", symbol="circle", line=dict(color="#ffffff", width=1.2)),
            text=[f"{v:.2f}%" for v in y1] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#38bdf8", size=9),
            hovertemplate=(
                f"<b>{date1} Strike IV</b><br>"
                + ("ATM Offset: %{x:+.0f} pts<br>" if use_offset else "Strike K: %{x:.0f}<br>")
                + "Implied Vol: <b>%{y:.3f}%</b><extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    # Trace 2: Date 2 Strike IV
    fig.add_trace(
        go.Scatter(
            x=x2,
            y=y2,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Strike IV ({date2}) ★",
            line=dict(color="#e3b341", width=3.6),
            marker=dict(size=8, color="#e3b341", symbol="diamond", line=dict(color="#ffffff", width=1.5)),
            text=[f"{v:.2f}%" for v in y2] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#e3b341", size=9),
            hovertemplate=(
                f"<b>{date2} Strike IV</b><br>"
                + ("ATM Offset: %{x:+.0f} pts<br>" if use_offset else "Strike K: %{x:.0f}<br>")
                + "Implied Vol: <b>%{y:.3f}%</b><extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    # Shaded Ribbon between Date 1 and Date 2 IV where common x exists
    common_x = sorted(list(set(x1).intersection(set(x2))))
    if len(common_x) > 1:
        y1_map = dict(zip(x1, y1))
        y2_map = dict(zip(x2, y2))
        c_y1 = [y1_map[kx] for kx in common_x]
        c_y2 = [y2_map[kx] for kx in common_x]

        fig.add_trace(
            go.Scatter(
                x=common_x + common_x[::-1],
                y=c_y1 + c_y2[::-1],
                fill="toself",
                fillcolor="rgba(56, 189, 248, 0.08)",
                line=dict(color="rgba(255,255,255,0)"),
                hoverinfo="skip",
                showlegend=True,
                name="IV Smile Shift Band",
            ),
            row=1,
            col=1,
        )

    # -------------------------------------------------------------
    # SUBPLOT 2: Fly IV Curvature
    # -------------------------------------------------------------
    f1 = fly_df1.sort_values(x_col_fly) if not fly_df1.empty else pd.DataFrame()
    f2 = fly_df2.sort_values(x_col_fly) if not fly_df2.empty else pd.DataFrame()

    if not f1.empty:
        fig.add_trace(
            go.Scatter(
                x=f1[x_col_fly],
                y=f1["initial_iv_fly_pct"],
                mode="lines+markers",
                name=f"Fly IV Curvature ({date1})",
                line=dict(color="#bc8cff", width=2.4),
                marker=dict(size=6, color="#bc8cff", symbol="square"),
                hovertemplate=(
                    f"<b>{date1} Fly IV</b><br>"
                    + ("ATM Offset: %{x:+.0f} pts<br>" if use_offset else "Centre Strike: %{x:.0f}<br>")
                    + "Fly IV: <b>%{y:+.4f} pts</b><extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

    if not f2.empty:
        fig.add_trace(
            go.Scatter(
                x=f2[x_col_fly],
                y=f2["initial_iv_fly_pct"],
                mode="lines+markers",
                name=f"Fly IV Curvature ({date2}) ★",
                line=dict(color="#3fb950", width=2.6),
                marker=dict(size=7, color="#3fb950", symbol="triangle-up"),
                hovertemplate=(
                    f"<b>{date2} Fly IV</b><br>"
                    + ("ATM Offset: %{x:+.0f} pts<br>" if use_offset else "Centre Strike: %{x:.0f}<br>")
                    + "Fly IV: <b>%{y:+.4f} pts</b><extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

    # Delta Fly IV Bars (Difference)
    if not f1.empty and not f2.empty:
        merged_f = pd.merge(
            f1[[x_col_fly, "initial_iv_fly_pct"]],
            f2[[x_col_fly, "initial_iv_fly_pct"]],
            on=x_col_fly,
            suffixes=("_1", "_2"),
        )
        if not merged_f.empty:
            merged_f["delta_fly_iv"] = (
                merged_f["initial_iv_fly_pct_2"] - merged_f["initial_iv_fly_pct_1"]
            )
            bar_colors = [
                "#3fb950" if d >= 0 else "#f85149" for d in merged_f["delta_fly_iv"]
            ]
            fig.add_trace(
                go.Bar(
                    x=merged_f[x_col_fly],
                    y=merged_f["delta_fly_iv"],
                    name="Δ Fly IV (T+1 − T)",
                    marker=dict(color=bar_colors, opacity=0.4),
                    hovertemplate=(
                        "<b>Δ Fly IV Curvature</b><br>"
                        + ("ATM Offset: %{x:+.0f} pts<br>" if use_offset else "Centre Strike: %{x:.0f}<br>")
                        + "Change: <b>%{y:+.4f} pts</b><extra></extra>"
                    ),
                ),
                row=2,
                col=1,
            )

    # Vertical reference lines
    if use_offset:
        fig.add_vline(x=0, line=dict(color="#38bdf8", width=1.5, dash="dash"), row=1, col=1)
        fig.add_vline(x=0, line=dict(color="#38bdf8", width=1.5, dash="dash"), row=2, col=1)
    else:
        if atm1 > 0:
            fig.add_vline(
                x=atm1,
                line=dict(color="#38bdf8", width=1.5, dash="dot"),
                annotation=dict(text=f"ATM ({date1}): {atm1:.0f}", font=dict(color="#38bdf8", size=10)),
                row=1,
                col=1,
            )
        if atm2 > 0 and atm2 != atm1:
            fig.add_vline(
                x=atm2,
                line=dict(color="#e3b341", width=1.5, dash="dot"),
                annotation=dict(text=f"ATM ({date2}): {atm2:.0f}", font=dict(color="#e3b341", size=10)),
                row=1,
                col=1,
            )

    # Horizontal zero line for Fly IV
    fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=2, col=1)

    # Layout styling
    fig = apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>Implied Volatility Smiles &amp; Fly IV Curvature:</b> {date1} &rarr; {date2}",
            font=dict(size=15, color="#f0f6fc"),
        ),
        height=660,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            y=1.06,
            x=0.01,
            bgcolor="rgba(19, 24, 35, 0.8)",
            bordercolor="#30363d",
            font=dict(size=11),
        ),
    )

    fig.update_xaxes(
        title_text=x_axis_label,
        row=2,
        col=1,
        dtick=100 if not use_offset else 100,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
        showspikes=True,
        spikemode="across",
        spikethickness=1.2,
        spikecolor="#38bdf8",
    )
    fig.update_xaxes(
        row=1,
        col=1,
        dtick=100 if not use_offset else 100,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
        showspikes=True,
        spikemode="across",
        spikethickness=1.2,
        spikecolor="#38bdf8",
    )
    fig.update_yaxes(
        title_text="Implied Volatility (%)",
        row=1,
        col=1,
        gridcolor="#21262d",
        zerolinecolor="#30363d",
    )
    fig.update_yaxes(
        title_text="Fly IV (vol pts)",
        row=2,
        col=1,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
    )

    return fig


def create_consecutive_fly_premium_chart(
    date1: str,
    date2: str,
    fly_df1: pd.DataFrame,
    fly_df2: pd.DataFrame,
    use_offset: bool = False,
    atm1: float = 0.0,
    atm2: float = 0.0,
    show_labels: bool = False,
) -> go.Figure:
    """Create Graph 2: Two-row synchronized chart of Butterfly Premium ($) (top) and Daily Change ($) (bottom).

    Parameters
    ----------
    date1, date2 : str
        The two consecutive dates.
    fly_df1, fly_df2 : pd.DataFrame
        DataFrames containing centre_strike, atm_offset, initial_fly_premium.
    use_offset : bool
        If True, x-axis is ATM offset (K - ATM). Otherwise absolute strike (K).
    atm1, atm2 : float
        ATM strike values.
    show_labels : bool
        If True, displays value annotations on points.
    """
    x_col = "atm_offset" if use_offset else "centre_strike"
    x_axis_label = "Strike Distance to ATM: K − K_ATM (pts)" if use_offset else "Butterfly Centre Strike K (pts)"

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=(
            f"<b>2A. 100-pt Butterfly Spread Net Debit Premium ($):</b> {date1} vs {date2}",
            f"<b>2B. Observed Consecutive Day Premium Change:</b> $\\Delta F = F_{{{date2}}} - F_{{{date1}}}$ ($/contract)",
        ),
        row_heights=[0.60, 0.40],
    )

    f1 = fly_df1.sort_values(x_col) if not fly_df1.empty else pd.DataFrame()
    f2 = fly_df2.sort_values(x_col) if not fly_df2.empty else pd.DataFrame()

    # Trace 1: Date 1 Premium
    if not f1.empty:
        x1 = f1[x_col].values
        y1 = f1["initial_fly_premium"].values
        fig.add_trace(
            go.Scatter(
                x=x1,
                y=y1,
                mode="lines+markers" if not show_labels else "lines+markers+text",
                name=f"Fly Premium ({date1})",
                line=dict(color="#d29922", width=3.2),
                marker=dict(size=7, color="#d29922", symbol="diamond", line=dict(color="#ffffff", width=1.2)),
                text=[f"${v:.2f}" for v in y1] if show_labels else None,
                textposition="top center",
                textfont=dict(color="#d29922", size=9),
                hovertemplate=(
                    f"<b>{date1} Fly Premium</b><br>"
                    + ("ATM Offset: %{x:+.0f} pts<br>" if use_offset else "Centre Strike: %{x:.0f}<br>")
                    + "Net Premium: <b>$%{y:.2f}</b><extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    # Trace 2: Date 2 Premium
    if not f2.empty:
        x2 = f2[x_col].values
        y2 = f2["initial_fly_premium"].values
        fig.add_trace(
            go.Scatter(
                x=x2,
                y=y2,
                mode="lines+markers" if not show_labels else "lines+markers+text",
                name=f"Fly Premium ({date2}) ★",
                line=dict(color="#3fb950", width=3.6),
                marker=dict(size=8, color="#3fb950", symbol="circle", line=dict(color="#ffffff", width=1.5)),
                text=[f"${v:.2f}" for v in y2] if show_labels else None,
                textposition="bottom center",
                textfont=dict(color="#3fb950", size=9),
                hovertemplate=(
                    f"<b>{date2} Fly Premium</b><br>"
                    + ("ATM Offset: %{x:+.0f} pts<br>" if use_offset else "Centre Strike: %{x:.0f}<br>")
                    + "Net Premium: <b>$%{y:.2f}</b><extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    # Shaded fill band between Date 1 and Date 2 Fly Premium
    if not f1.empty and not f2.empty:
        common_x = sorted(list(set(f1[x_col]).intersection(set(f2[x_col]))))
        if len(common_x) > 1:
            y1_map = dict(zip(f1[x_col], f1["initial_fly_premium"]))
            y2_map = dict(zip(f2[x_col], f2["initial_fly_premium"]))
            c_y1 = [y1_map[kx] for kx in common_x]
            c_y2 = [y2_map[kx] for kx in common_x]

            fig.add_trace(
                go.Scatter(
                    x=common_x + common_x[::-1],
                    y=c_y1 + c_y2[::-1],
                    fill="toself",
                    fillcolor="rgba(210, 153, 34, 0.08)",
                    line=dict(color="rgba(255,255,255,0)"),
                    hoverinfo="skip",
                    showlegend=True,
                    name="Premium Expansion/Contraction Band",
                ),
                row=1,
                col=1,
            )

    # SUBPLOT 2: Delta Fly Premium Bar Chart
    if not f1.empty and not f2.empty:
        merged_p = pd.merge(
            f1[[x_col, "initial_fly_premium"]],
            f2[[x_col, "initial_fly_premium"]],
            on=x_col,
            suffixes=("_1", "_2"),
        )
        if not merged_p.empty:
            merged_p["delta_premium"] = (
                merged_p["initial_fly_premium_2"] - merged_p["initial_fly_premium_1"]
            )
            bar_colors = [
                "#3fb950" if d >= 0 else "#f85149" for d in merged_p["delta_premium"]
            ]
            fig.add_trace(
                go.Bar(
                    x=merged_p[x_col],
                    y=merged_p["delta_premium"],
                    name="Δ Premium ($/fly)",
                    marker=dict(color=bar_colors),
                    text=[f"{v:+.2f}" for v in merged_p["delta_premium"]],
                    textposition="auto",
                    textfont=dict(color="#ffffff", size=9),
                    hovertemplate=(
                        "<b>Observed Fly Premium Change</b><br>"
                        + ("ATM Offset: %{x:+.0f} pts<br>" if use_offset else "Centre Strike: %{x:.0f}<br>")
                        + "Δ Premium: <b>$%{y:+.2f}</b><extra></extra>"
                    ),
                ),
                row=2,
                col=1,
            )

    # Vertical reference lines
    if use_offset:
        fig.add_vline(x=0, line=dict(color="#38bdf8", width=1.5, dash="dash"), row=1, col=1)
        fig.add_vline(x=0, line=dict(color="#38bdf8", width=1.5, dash="dash"), row=2, col=1)
    else:
        if atm1 > 0:
            fig.add_vline(
                x=atm1,
                line=dict(color="#38bdf8", width=1.5, dash="dot"),
                annotation=dict(text=f"ATM ({date1}): {atm1:.0f}", font=dict(color="#38bdf8", size=10)),
                row=1,
                col=1,
            )
        if atm2 > 0 and atm2 != atm1:
            fig.add_vline(
                x=atm2,
                line=dict(color="#e3b341", width=1.5, dash="dot"),
                annotation=dict(text=f"ATM ({date2}): {atm2:.0f}", font=dict(color="#e3b341", size=10)),
                row=1,
                col=1,
            )

    fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=2, col=1)

    fig = apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>100-pt Butterfly Premium Curves &amp; Daily Price Shifts:</b> {date1} &rarr; {date2}",
            font=dict(size=15, color="#f0f6fc"),
        ),
        height=660,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            y=1.06,
            x=0.01,
            bgcolor="rgba(19, 24, 35, 0.8)",
            bordercolor="#30363d",
            font=dict(size=11),
        ),
    )

    fig.update_xaxes(
        title_text=x_axis_label,
        row=2,
        col=1,
        dtick=100 if not use_offset else 100,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
        showspikes=True,
        spikemode="across",
        spikethickness=1.2,
        spikecolor="#38bdf8",
    )
    fig.update_xaxes(
        row=1,
        col=1,
        dtick=100 if not use_offset else 100,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
        showspikes=True,
        spikemode="across",
        spikethickness=1.2,
        spikecolor="#38bdf8",
    )
    fig.update_yaxes(
        title_text="Fly Premium ($)",
        row=1,
        col=1,
        gridcolor="#21262d",
        zerolinecolor="#30363d",
    )
    fig.update_yaxes(
        title_text="Δ Premium ($)",
        row=2,
        col=1,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
    )

    return fig


def create_single_date_panel_chart(
    date_val: str,
    strike_df: pd.DataFrame,
    fly_df: pd.DataFrame,
    use_offset: bool = False,
    atm_val: float = 0.0,
    accent_color: str = "#38bdf8",
) -> go.Figure:
    """Create a 3-trace unified panel for a single date: Strike IV, Fly IV, and Fly Premium.

    Used when the user selects the Side-by-Side Dual Charts view mode.
    """
    x_col_strike = "atm_offset" if use_offset else "strike"
    x_col_fly = "atm_offset" if use_offset else "centre_strike"
    x_axis_label = "Strike Distance to ATM (pts)" if use_offset else "Strike Price K (pts)"

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            f"<b>Strike IV (%)</b> — {date_val}",
            f"<b>Fly IV Curvature (vol pts)</b> — {date_val}",
            f"<b>Fly Premium ($)</b> — {date_val}",
        ),
        row_heights=[0.38, 0.31, 0.31],
    )

    s_sorted = strike_df.sort_values(x_col_strike)
    f_sorted = fly_df.sort_values(x_col_fly) if not fly_df.empty else pd.DataFrame()

    # 1. Strike IV
    fig.add_trace(
        go.Scatter(
            x=s_sorted[x_col_strike],
            y=s_sorted["iv_pct"],
            mode="lines+markers",
            name="Strike IV",
            line=dict(color=accent_color, width=2.8),
            marker=dict(size=6, color=accent_color),
            hovertemplate="Strike: %{x}<br>IV: %{y:.3f}%<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # 2. Fly IV
    if not f_sorted.empty:
        fig.add_trace(
            go.Scatter(
                x=f_sorted[x_col_fly],
                y=f_sorted["initial_iv_fly_pct"],
                mode="lines+markers",
                name="Fly IV",
                line=dict(color="#bc8cff", width=2.5),
                marker=dict(size=6, color="#bc8cff"),
                hovertemplate="Centre: %{x}<br>Fly IV: %{y:+.4f} pts<extra></extra>",
            ),
            row=2,
            col=1,
        )

    # 3. Fly Premium
    if not f_sorted.empty:
        fig.add_trace(
            go.Scatter(
                x=f_sorted[x_col_fly],
                y=f_sorted["initial_fly_premium"],
                mode="lines+markers",
                name="Fly Premium",
                line=dict(color="#d29922", width=2.8),
                marker=dict(size=6, color="#d29922"),
                hovertemplate="Centre: %{x}<br>Fly Premium: $%{y:.2f}<extra></extra>",
            ),
            row=3,
            col=1,
        )

    fig = apply_theme_layout(
        fig,
        title=dict(text=f"<b>Complete Structure Snapshot:</b> {date_val}", font=dict(size=14, color="#f0f6fc")),
        height=660,
        hovermode="x unified",
        showlegend=False,
    )

    fig.update_xaxes(title_text=x_axis_label, row=3, col=1, gridcolor="#21262d", dtick=100)
    fig.update_xaxes(row=1, col=1, gridcolor="#21262d", dtick=100)
    fig.update_xaxes(row=2, col=1, gridcolor="#21262d", dtick=100)
    fig.update_yaxes(title_text="IV (%)", row=1, col=1, gridcolor="#21262d")
    fig.update_yaxes(title_text="Fly IV (pts)", row=2, col=1, gridcolor="#21262d")
    fig.update_yaxes(title_text="Prem ($)", row=3, col=1, gridcolor="#21262d")

    return fig


def create_consecutive_skew_and_rr_chart(
    date1: str,
    date2: str,
    struct_metrics1: dict[str, Any],
    struct_metrics2: dict[str, Any],
    show_labels: bool = False,
) -> go.Figure:
    """Create two-row synchronized chart of Call/Put Skew (top) and Skew / Risk Reversal (bottom).

    Parameters
    ----------
    date1, date2 : str
        The two consecutive dates.
    struct_metrics1, struct_metrics2 : dict[str, Any]
        Dictionaries from compute_smile_structure_metrics containing table, atm_iv, etc.
    show_labels : bool
        If True, displays value annotations directly on markers.
    """
    t1 = struct_metrics1["table"].copy()
    t2 = struct_metrics2["table"].copy()

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=(
            f"<b>2A. Call Skew &amp; Put Skew Relative to ATM ($IV - IV_{{ATM}}$):</b> {date1} vs {date2} (vol pts)",
            f"<b>2B. Skew / Risk Reversal ($IV_{{Call}} - IV_{{Put}}$) &amp; Daily Skew Shift:</b> $\\Delta RR$ (vol pts)",
        ),
        row_heights=[0.56, 0.44],
    )

    x1 = t1["offset"].values
    x2 = t2["offset"].values

    # -------------------------------------------------------------
    # SUBPLOT 1: Call Skew and Put Skew
    # -------------------------------------------------------------
    # Date 1 Put Skew
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["put_skew"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Put Skew ({date1})",
            line=dict(color="#f85149", width=2.4, dash="dot"),
            marker=dict(size=7, color="#f85149", symbol="square"),
            text=[f"{v:+.2f}" if v is not None else "" for v in t1["put_skew"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#f85149", size=9),
            hovertemplate=(
                f"<b>{date1} Put Skew</b><br>"
                + "Offset: -%{x:.0f} pts<br>"
                + "Put Skew (IV - ATM): <b>%{y:+.3f} pts</b><extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    # Date 2 Put Skew
    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["put_skew"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Put Skew ({date2}) ★",
            line=dict(color="#ff7b72", width=3.4),
            marker=dict(size=8, color="#ff7b72", symbol="diamond", line=dict(color="#ffffff", width=1.2)),
            text=[f"{v:+.2f}" if v is not None else "" for v in t2["put_skew"].values] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#ff7b72", size=9),
            hovertemplate=(
                f"<b>{date2} Put Skew</b><br>"
                + "Offset: -%{x:.0f} pts<br>"
                + "Put Skew (IV - ATM): <b>%{y:+.3f} pts</b><extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    # Date 1 Call Skew
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["call_skew"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Call Skew ({date1})",
            line=dict(color="#38bdf8", width=2.4, dash="dot"),
            marker=dict(size=7, color="#38bdf8", symbol="circle"),
            text=[f"{v:+.2f}" if v is not None else "" for v in t1["call_skew"].values] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#38bdf8", size=9),
            hovertemplate=(
                f"<b>{date1} Call Skew</b><br>"
                + "Offset: +%{x:.0f} pts<br>"
                + "Call Skew (IV - ATM): <b>%{y:+.3f} pts</b><extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    # Date 2 Call Skew
    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["call_skew"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Call Skew ({date2}) ★",
            line=dict(color="#e3b341", width=3.4),
            marker=dict(size=8, color="#e3b341", symbol="diamond", line=dict(color="#ffffff", width=1.2)),
            text=[f"{v:+.2f}" if v is not None else "" for v in t2["call_skew"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#e3b341", size=9),
            hovertemplate=(
                f"<b>{date2} Call Skew</b><br>"
                + "Offset: +%{x:.0f} pts<br>"
                + "Call Skew (IV - ATM): <b>%{y:+.3f} pts</b><extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    # Horizontal zero line
    fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=1, col=1)

    # -------------------------------------------------------------
    # SUBPLOT 2: Skew / Risk Reversal (IV_Call - IV_Put)
    # -------------------------------------------------------------
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["risk_reversal"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Risk Reversal ({date1})",
            line=dict(color="#bc8cff", width=2.6, dash="dot"),
            marker=dict(size=7, color="#bc8cff", symbol="diamond"),
            text=[f"{v:+.2f}" if v is not None else "" for v in t1["risk_reversal"].values] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#bc8cff", size=9),
            hovertemplate=(
                f"<b>{date1} Risk Reversal</b><br>"
                + "Offset: %{x:.0f} pts<br>"
                + "RR (Call IV - Put IV): <b>%{y:+.3f} pts</b><extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["risk_reversal"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Risk Reversal ({date2}) ★",
            line=dict(color="#58a6ff", width=3.4),
            marker=dict(size=8, color="#58a6ff", symbol="circle", line=dict(color="#ffffff", width=1.4)),
            text=[f"{v:+.2f}" if v is not None else "" for v in t2["risk_reversal"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#58a6ff", size=9),
            hovertemplate=(
                f"<b>{date2} Risk Reversal</b><br>"
                + "Offset: %{x:.0f} pts<br>"
                + "RR (Call IV - Put IV): <b>%{y:+.3f} pts</b><extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    # Delta Risk Reversal Bars
    merged_rr = pd.merge(
        t1[["offset", "risk_reversal"]],
        t2[["offset", "risk_reversal"]],
        on="offset",
        suffixes=("_1", "_2"),
    )
    if not merged_rr.empty:
        merged_rr["delta_rr"] = merged_rr["risk_reversal_2"] - merged_rr["risk_reversal_1"]
        bar_colors = ["#3fb950" if d >= 0 else "#f85149" for d in merged_rr["delta_rr"]]
        fig.add_trace(
            go.Bar(
                x=merged_rr["offset"],
                y=merged_rr["delta_rr"],
                name="Δ Risk Reversal (T+1 − T)",
                marker=dict(color=bar_colors, opacity=0.45),
                hovertemplate=(
                    "<b>Δ Risk Reversal (Skew Shift)</b><br>"
                    + "Offset: %{x:.0f} pts<br>"
                    + "Change: <b>%{y:+.3f} pts</b><br>"
                    + "(+ = Skew Flattening / Call Rich, − = Skew Steepening)<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

    fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=2, col=1)

    # Layout styling
    fig = apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>Call/Put Skew &amp; Risk Reversal Dynamics:</b> {date1} &rarr; {date2}",
            font=dict(size=15, color="#f0f6fc"),
        ),
        height=660,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            y=1.06,
            x=0.01,
            bgcolor="rgba(19, 24, 35, 0.8)",
            bordercolor="#30363d",
            font=dict(size=11),
        ),
    )

    fig.update_xaxes(
        title_text="Moneyness Distance from ATM: ΔK (pts)",
        row=2,
        col=1,
        dtick=100,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
        showspikes=True,
        spikemode="across",
        spikethickness=1.2,
        spikecolor="#38bdf8",
    )
    fig.update_xaxes(
        row=1,
        col=1,
        dtick=100,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
        showspikes=True,
        spikemode="across",
        spikethickness=1.2,
        spikecolor="#38bdf8",
    )
    fig.update_yaxes(
        title_text="Skew to ATM (vol pts)",
        row=1,
        col=1,
        gridcolor="#21262d",
        zerolinecolor="#30363d",
    )
    fig.update_yaxes(
        title_text="Risk Reversal (vol pts)",
        row=2,
        col=1,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
    )

    return fig


def create_consecutive_curvature_and_kurtosis_chart(
    date1: str,
    date2: str,
    struct_metrics1: dict[str, Any],
    struct_metrics2: dict[str, Any],
    show_labels: bool = False,
) -> go.Figure:
    """Create two-row synchronized chart of Smile Curvature (top) and Smile Kurtosis Scaling Ratio (bottom).

    Parameters
    ----------
    date1, date2 : str
        The two consecutive dates.
    struct_metrics1, struct_metrics2 : dict[str, Any]
        Dictionaries from compute_smile_structure_metrics containing table, poly_coeffs, etc.
    show_labels : bool
        If True, displays value annotations directly on markers.
    """
    t1 = struct_metrics1["table"].copy()
    t2 = struct_metrics2["table"].copy()

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=(
            f"<b>2A. Symmetric Smile Curvature [$\\frac{{IV_{{Put}} + IV_{{Call}}}}{{2}} - IV_{{ATM}}$]:</b> {date1} vs {date2} (vol pts)",
            f"<b>2B. Smile Kurtosis Fat-Tail Scaling Ratio:</b> $\\frac{{Curvature(h)}}{{(h/100)^2 \\cdot Curvature(100)}}$ vs Quadratic Baseline (1.0)",
        ),
        row_heights=[0.56, 0.44],
    )

    x1 = t1["offset"].values
    x2 = t2["offset"].values

    # -------------------------------------------------------------
    # SUBPLOT 1: Curvature
    # -------------------------------------------------------------
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["curvature"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Curvature ({date1})",
            line=dict(color="#bc8cff", width=2.6, dash="dot"),
            marker=dict(size=7, color="#bc8cff", symbol="square"),
            text=[f"{v:+.2f}" if v is not None else "" for v in t1["curvature"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#bc8cff", size=9),
            hovertemplate=(
                f"<b>{date1} Curvature</b><br>"
                + "Offset: %{x:.0f} pts<br>"
                + "Curvature: <b>%{y:+.3f} pts</b><extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["curvature"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Curvature ({date2}) ★",
            line=dict(color="#3fb950", width=3.4),
            marker=dict(size=8, color="#3fb950", symbol="diamond", line=dict(color="#ffffff", width=1.4)),
            text=[f"{v:+.2f}" if v is not None else "" for v in t2["curvature"].values] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#3fb950", size=9),
            hovertemplate=(
                f"<b>{date2} Curvature</b><br>"
                + "Offset: %{x:.0f} pts<br>"
                + "Curvature: <b>%{y:+.3f} pts</b><extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    # Shaded band between curvatures
    common_x = sorted(list(set(x1).intersection(set(x2))))
    if len(common_x) > 1:
        y1_map = dict(zip(x1, t1["curvature"].values))
        y2_map = dict(zip(x2, t2["curvature"].values))
        c_y1 = [y1_map[kx] for kx in common_x]
        c_y2 = [y2_map[kx] for kx in common_x]
        fig.add_trace(
            go.Scatter(
                x=common_x + common_x[::-1],
                y=c_y1 + c_y2[::-1],
                fill="toself",
                fillcolor="rgba(63, 185, 80, 0.08)",
                line=dict(color="rgba(255,255,255,0)"),
                hoverinfo="skip",
                showlegend=True,
                name="Curvature Shift Band",
            ),
            row=1,
            col=1,
        )

    # Delta Curvature Bars
    merged_c = pd.merge(
        t1[["offset", "curvature"]],
        t2[["offset", "curvature"]],
        on="offset",
        suffixes=("_1", "_2"),
    )
    if not merged_c.empty:
        merged_c["delta_c"] = merged_c["curvature_2"] - merged_c["curvature_1"]
        bar_colors = ["#3fb950" if d >= 0 else "#f85149" for d in merged_c["delta_c"]]
        fig.add_trace(
            go.Bar(
                x=merged_c["offset"],
                y=merged_c["delta_c"],
                name="Δ Curvature (T+1 − T)",
                marker=dict(color=bar_colors, opacity=0.45),
                hovertemplate=(
                    "<b>Δ Smile Curvature</b><br>"
                    + "Offset: %{x:.0f} pts<br>"
                    + "Change: <b>%{y:+.4f} pts</b><extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=1, col=1)

    # -------------------------------------------------------------
    # SUBPLOT 2: Kurtosis Ratio
    # -------------------------------------------------------------
    # Baseline 1.0 (pure quadratic smile)
    fig.add_hline(
        y=1.0,
        line=dict(color="#8b949e", width=1.5, dash="dash"),
        annotation=dict(
            text="Pure Quadratic Smile Baseline (1.00)",
            font=dict(color="#8b949e", size=10),
            xref="paper",
            x=0.02,
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["kurtosis_ratio"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Kurtosis Ratio ({date1})",
            line=dict(color="#d29922", width=2.6, dash="dot"),
            marker=dict(size=7, color="#d29922", symbol="diamond"),
            text=[f"{v:.2f}" if v is not None else "" for v in t1["kurtosis_ratio"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#d29922", size=9),
            hovertemplate=(
                f"<b>{date1} Kurtosis Ratio</b><br>"
                + "Offset: %{x:.0f} pts<br>"
                + "Scaling Ratio: <b>%{y:.3f}x</b><extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["kurtosis_ratio"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Kurtosis Ratio ({date2}) ★",
            line=dict(color="#38bdf8", width=3.4),
            marker=dict(size=8, color="#38bdf8", symbol="circle", line=dict(color="#ffffff", width=1.4)),
            text=[f"{v:.2f}" if v is not None else "" for v in t2["kurtosis_ratio"].values] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#38bdf8", size=9),
            hovertemplate=(
                f"<b>{date2} Kurtosis Ratio</b><br>"
                + "Offset: %{x:.0f} pts<br>"
                + "Scaling Ratio: <b>%{y:.3f}x</b><extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    # Delta Kurtosis Ratio Bars
    merged_k = pd.merge(
        t1[["offset", "kurtosis_ratio"]],
        t2[["offset", "kurtosis_ratio"]],
        on="offset",
        suffixes=("_1", "_2"),
    )
    if not merged_k.empty:
        merged_k["delta_k"] = merged_k["kurtosis_ratio_2"] - merged_k["kurtosis_ratio_1"]
        bar_colors = ["#38bdf8" if d >= 0 else "#f85149" for d in merged_k["delta_k"]]
        fig.add_trace(
            go.Bar(
                x=merged_k["offset"],
                y=merged_k["delta_k"],
                name="Δ Kurtosis Ratio (T+1 − T)",
                marker=dict(color=bar_colors, opacity=0.45),
                hovertemplate=(
                    "<b>Δ Kurtosis Ratio</b><br>"
                    + "Offset: %{x:.0f} pts<br>"
                    + "Change: <b>%{y:+.3f}</b><br>"
                    + "(+ = Wings Got Fatter Relative to Base Curvature)<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

    # Layout styling
    fig = apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>Smile Curvature &amp; Kurtosis Fat-Tail Dynamics:</b> {date1} &rarr; {date2}",
            font=dict(size=15, color="#f0f6fc"),
        ),
        height=660,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            y=1.06,
            x=0.01,
            bgcolor="rgba(19, 24, 35, 0.8)",
            bordercolor="#30363d",
            font=dict(size=11),
        ),
    )

    fig.update_xaxes(
        title_text="Moneyness Distance from ATM: ΔK (pts)",
        row=2,
        col=1,
        dtick=100,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
        showspikes=True,
        spikemode="across",
        spikethickness=1.2,
        spikecolor="#38bdf8",
    )
    fig.update_xaxes(
        row=1,
        col=1,
        dtick=100,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
        showspikes=True,
        spikemode="across",
        spikethickness=1.2,
        spikecolor="#38bdf8",
    )
    fig.update_yaxes(
        title_text="Curvature (vol pts)",
        row=1,
        col=1,
        gridcolor="#21262d",
        zerolinecolor="#30363d",
    )
    fig.update_yaxes(
        title_text="Kurtosis Ratio",
        row=2,
        col=1,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
    )

    return fig


def create_consecutive_fly_skew_and_rr_chart(
    date1: str,
    date2: str,
    fly_struct1: dict[str, Any],
    fly_struct2: dict[str, Any],
    show_labels: bool = False,
) -> go.Figure:
    """Create two-row synchronized chart of Call/Put Butterfly Dollar Skew (top) and Fly Risk Reversal ($) (bottom).

    Parameters
    ----------
    date1, date2 : str
        The two consecutive dates.
    fly_struct1, fly_struct2 : dict[str, Any]
        Dictionaries from compute_fly_structure_metrics containing table, atm_fly, etc.
    show_labels : bool
        If True, displays value annotations directly on markers.
    """
    t1 = fly_struct1["table"].copy()
    t2 = fly_struct2["table"].copy()
    atm1 = fly_struct1.get("atm_fly", 0.0) or 0.0
    atm2 = fly_struct2.get("atm_fly", 0.0) or 0.0

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=(
            f"<b>2A. Butterfly Dollar Skew Relative to ATM ($F - F_{{ATM}}$):</b> {date1} vs {date2} ($/contract)",
            f"<b>2B. Fly Skew / Fly Risk Reversal ($F_{{Call}} - F_{{Put}}$) &amp; Daily Shift:</b> $\\Delta$ Fly RR ($/fly)",
        ),
        row_heights=[0.56, 0.44],
    )

    x1 = t1["offset"].values
    x2 = t2["offset"].values

    # -------------------------------------------------------------
    # SUBPLOT 1: Call Fly Skew & Put Fly Skew ($)
    # -------------------------------------------------------------
    # Zero baseline
    fig.add_hline(
        y=0.0,
        line=dict(color="#484f58", width=1.4, dash="dash"),
        annotation=dict(
            text=f"ATM Baseline ($0.00 | {date1}: ${atm1:.2f}, {date2}: ${atm2:.2f})",
            font=dict(color="#8b949e", size=10),
            xref="paper",
            x=0.02,
        ),
        row=1,
        col=1,
    )

    # Date 1 Put Fly Skew
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["put_skew"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Put Fly Skew ({date1})",
            line=dict(color="#f85149", width=2.4, dash="dot"),
            marker=dict(size=7, color="#f85149", symbol="square"),
            text=[f"${v:+.2f}" if v is not None else "" for v in t1["put_skew"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#f85149", size=9),
            hovertemplate=(
                f"<b>{date1} Put Fly Skew</b><br>"
                + "Offset: -%{x:.0f} pts<br>"
                + "Put Fly Skew (F - ATM): <b>$%{y:+.2f}</b><br>"
                + "Put Fly Prem: <b>$%{customdata:.2f}</b><extra></extra>"
            ),
            customdata=t1["fly_put"].values,
        ),
        row=1,
        col=1,
    )

    # Date 2 Put Fly Skew
    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["put_skew"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Put Fly Skew ({date2}) ★",
            line=dict(color="#ff7b72", width=3.4),
            marker=dict(size=8, color="#ff7b72", symbol="diamond", line=dict(color="#ffffff", width=1.2)),
            text=[f"${v:+.2f}" if v is not None else "" for v in t2["put_skew"].values] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#ff7b72", size=9),
            hovertemplate=(
                f"<b>{date2} Put Fly Skew</b><br>"
                + "Offset: -%{x:.0f} pts<br>"
                + "Put Fly Skew (F - ATM): <b>$%{y:+.2f}</b><br>"
                + "Put Fly Prem: <b>$%{customdata:.2f}</b><extra></extra>"
            ),
            customdata=t2["fly_put"].values,
        ),
        row=1,
        col=1,
    )

    # Date 1 Call Fly Skew
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["call_skew"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Call Fly Skew ({date1})",
            line=dict(color="#2ea043", width=2.4, dash="dot"),
            marker=dict(size=7, color="#2ea043", symbol="square"),
            text=[f"${v:+.2f}" if v is not None else "" for v in t1["call_skew"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#2ea043", size=9),
            hovertemplate=(
                f"<b>{date1} Call Fly Skew</b><br>"
                + "Offset: +%{x:.0f} pts<br>"
                + "Call Fly Skew (F - ATM): <b>$%{y:+.2f}</b><br>"
                + "Call Fly Prem: <b>$%{customdata:.2f}</b><extra></extra>"
            ),
            customdata=t1["fly_call"].values,
        ),
        row=1,
        col=1,
    )

    # Date 2 Call Fly Skew
    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["call_skew"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Call Fly Skew ({date2}) ★",
            line=dict(color="#3fb950", width=3.4),
            marker=dict(size=8, color="#3fb950", symbol="circle", line=dict(color="#ffffff", width=1.2)),
            text=[f"${v:+.2f}" if v is not None else "" for v in t2["call_skew"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#3fb950", size=9),
            hovertemplate=(
                f"<b>{date2} Call Fly Skew</b><br>"
                + "Offset: +%{x:.0f} pts<br>"
                + "Call Fly Skew (F - ATM): <b>$%{y:+.2f}</b><br>"
                + "Call Fly Prem: <b>$%{customdata:.2f}</b><extra></extra>"
            ),
            customdata=t2["fly_call"].values,
        ),
        row=1,
        col=1,
    )

    # -------------------------------------------------------------
    # SUBPLOT 2: Fly Skew / Fly Risk Reversal (F_Call - F_Put)
    # -------------------------------------------------------------
    fig.add_hline(
        y=0.0,
        line=dict(color="#484f58", width=1.4, dash="dash"),
        annotation=dict(
            text="Symmetric Fly Baseline ($0.00: Call Fly = Put Fly)",
            font=dict(color="#8b949e", size=10),
            xref="paper",
            x=0.02,
        ),
        row=2,
        col=1,
    )

    # Date 1 Fly Risk Reversal
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["risk_reversal"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Fly Risk Reversal ({date1})",
            line=dict(color="#58a6ff", width=2.6, dash="dot"),
            marker=dict(size=7, color="#58a6ff", symbol="diamond"),
            text=[f"${v:+.2f}" if v is not None else "" for v in t1["risk_reversal"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#58a6ff", size=9),
            hovertemplate=(
                f"<b>{date1} Fly Risk Reversal</b><br>"
                + "Offset: ±%{x:.0f} pts<br>"
                + "Fly RR (Call − Put): <b>$%{y:+.2f}</b><br>"
                + "(+ = Call Fly Richer than Put Fly)<extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    # Date 2 Fly Risk Reversal
    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["risk_reversal"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Fly Risk Reversal ({date2}) ★",
            line=dict(color="#38bdf8", width=3.4),
            marker=dict(size=8, color="#38bdf8", symbol="circle", line=dict(color="#ffffff", width=1.4)),
            text=[f"${v:+.2f}" if v is not None else "" for v in t2["risk_reversal"].values] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#38bdf8", size=9),
            hovertemplate=(
                f"<b>{date2} Fly Risk Reversal</b><br>"
                + "Offset: ±%{x:.0f} pts<br>"
                + "Fly RR (Call − Put): <b>$%{y:+.2f}</b><br>"
                + "(+ = Call Fly Richer than Put Fly)<extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    # Delta Fly Risk Reversal Bars
    merged_rr = pd.merge(
        t1[["offset", "risk_reversal"]],
        t2[["offset", "risk_reversal"]],
        on="offset",
        suffixes=("_1", "_2"),
    )
    if not merged_rr.empty:
        merged_rr["delta_rr"] = merged_rr["risk_reversal_2"] - merged_rr["risk_reversal_1"]
        bar_colors = ["#3fb950" if d >= 0 else "#f85149" for d in merged_rr["delta_rr"]]
        fig.add_trace(
            go.Bar(
                x=merged_rr["offset"],
                y=merged_rr["delta_rr"],
                name="Δ Fly RR (T+1 − T)",
                marker=dict(color=bar_colors, opacity=0.45),
                hovertemplate=(
                    "<b>Δ Fly Risk Reversal</b><br>"
                    + "Offset: ±%{x:.0f} pts<br>"
                    + "Shift: <b>$%{y:+.2f}</b><br>"
                    + "(+ = Call Fly gained relative to Put Fly)<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )

    # Layout styling
    fig = apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>Butterfly Dollar Skew &amp; Fly Risk Reversal Dynamics:</b> {date1} &rarr; {date2}",
            font=dict(size=15, color="#f0f6fc"),
        ),
        height=680,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            y=1.06,
            x=0.01,
            bgcolor="rgba(19, 24, 35, 0.8)",
            bordercolor="#30363d",
            font=dict(size=11),
        ),
    )

    fig.update_xaxes(
        title_text="Moneyness Distance from ATM: ΔK (pts)",
        row=2,
        col=1,
        dtick=100,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
        showspikes=True,
        spikemode="across",
        spikethickness=1.2,
        spikecolor="#38bdf8",
    )
    fig.update_xaxes(
        row=1,
        col=1,
        dtick=100,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
        showspikes=True,
        spikemode="across",
        spikethickness=1.2,
        spikecolor="#38bdf8",
    )
    fig.update_yaxes(
        title_text="Fly Skew ($/contract)",
        row=1,
        col=1,
        gridcolor="#21262d",
        zerolinecolor="#30363d",
    )
    fig.update_yaxes(
        title_text="Fly Risk Reversal ($)",
        row=2,
        col=1,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
    )

    return fig


def create_consecutive_fly_curvature_and_kurtosis_chart(
    date1: str,
    date2: str,
    fly_struct1: dict[str, Any],
    fly_struct2: dict[str, Any],
    show_labels: bool = False,
) -> go.Figure:
    """Create two-row synchronized chart of Fly Premium Curvature (top) and Kurtosis Butterfly Spread & Wing Retention (bottom).

    Parameters
    ----------
    date1, date2 : str
        The two consecutive dates.
    fly_struct1, fly_struct2 : dict[str, Any]
        Dictionaries from compute_fly_structure_metrics containing table, poly_coeffs, etc.
    show_labels : bool
        If True, displays value annotations directly on markers.
    """
    t1 = fly_struct1["table"].copy()
    t2 = fly_struct2["table"].copy()

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=(
            f"<b>2A. Butterfly Dollar Curvature [$\\frac{{F_{{Put}} + F_{{Call}}}}{{2}} - F_{{ATM}}$]:</b> {date1} vs {date2} ($/contract)",
            f"<b>2B. Kurtosis Butterfly Spread [Outer $2h$ vs Inner $h$ Fly] &amp; Wing Retention Ratio:</b> {date1} vs {date2}",
        ),
        row_heights=[0.56, 0.44],
    )

    x1 = t1["offset"].values
    x2 = t2["offset"].values

    # -------------------------------------------------------------
    # SUBPLOT 1: Fly Curvature ($)
    # -------------------------------------------------------------
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["curvature"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Fly Curvature ({date1})",
            line=dict(color="#bc8cff", width=2.6, dash="dot"),
            marker=dict(size=7, color="#bc8cff", symbol="square"),
            text=[f"${v:+.2f}" if v is not None else "" for v in t1["curvature"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#bc8cff", size=9),
            hovertemplate=(
                f"<b>{date1} Fly Curvature</b><br>"
                + "Offset: ±%{x:.0f} pts<br>"
                + "Curvature: <b>$%{y:+.2f}</b><extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["curvature"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Fly Curvature ({date2}) ★",
            line=dict(color="#d2a8ff", width=3.4),
            marker=dict(size=8, color="#d2a8ff", symbol="diamond", line=dict(color="#ffffff", width=1.4)),
            text=[f"${v:+.2f}" if v is not None else "" for v in t2["curvature"].values] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#d2a8ff", size=9),
            hovertemplate=(
                f"<b>{date2} Fly Curvature</b><br>"
                + "Offset: ±%{x:.0f} pts<br>"
                + "Curvature: <b>$%{y:+.2f}</b><extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )

    # Delta Fly Curvature Bars
    merged_c = pd.merge(
        t1[["offset", "curvature"]],
        t2[["offset", "curvature"]],
        on="offset",
        suffixes=("_1", "_2"),
    )
    if not merged_c.empty:
        merged_c["delta_c"] = merged_c["curvature_2"] - merged_c["curvature_1"]
        bar_colors = ["#38bdf8" if d >= 0 else "#f85149" for d in merged_c["delta_c"]]
        fig.add_trace(
            go.Bar(
                x=merged_c["offset"],
                y=merged_c["delta_c"],
                name="Δ Fly Curvature (T+1 − T)",
                marker=dict(color=bar_colors, opacity=0.45),
                hovertemplate=(
                    "<b>Δ Fly Curvature</b><br>"
                    + "Offset: ±%{x:.0f} pts<br>"
                    + "Shift: <b>$%{y:+.2f}</b><br>"
                    + "(+ = Wing Butterflies Expanded Relative to ATM)<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    # -------------------------------------------------------------
    # SUBPLOT 2: Kurtosis Butterfly Spread & Wing Retention Ratio
    # -------------------------------------------------------------
    # Kurtosis Butterfly Spread (Outer vs Inner Fly)
    t1_valid_spread = t1.dropna(subset=["kurtosis_spread"])
    t2_valid_spread = t2.dropna(subset=["kurtosis_spread"])

    if not t1_valid_spread.empty:
        fig.add_trace(
            go.Scatter(
                x=t1_valid_spread["offset"],
                y=t1_valid_spread["kurtosis_spread"],
                mode="lines+markers" if not show_labels else "lines+markers+text",
                name=f"Kurtosis Fly Spread ({date1})",
                line=dict(color="#f0883e", width=2.6, dash="dot"),
                marker=dict(size=7, color="#f0883e", symbol="square"),
                text=[f"${v:+.2f}" for v in t1_valid_spread["kurtosis_spread"]] if show_labels else None,
                textposition="top center",
                textfont=dict(color="#f0883e", size=9),
                hovertemplate=(
                    f"<b>{date1} Kurtosis Fly Spread</b><br>"
                    + "Inner Offset (h): ±%{x:.0f} pts (Outer: ±%{customdata:.0f} pts)<br>"
                    + "Spread (Outer − Inner): <b>$%{y:+.2f}</b><extra></extra>"
                ),
                customdata=t1_valid_spread["offset"] * 2.0,
            ),
            row=2,
            col=1,
        )

    if not t2_valid_spread.empty:
        fig.add_trace(
            go.Scatter(
                x=t2_valid_spread["offset"],
                y=t2_valid_spread["kurtosis_spread"],
                mode="lines+markers" if not show_labels else "lines+markers+text",
                name=f"Kurtosis Fly Spread ({date2}) ★",
                line=dict(color="#f97316", width=3.4),
                marker=dict(size=8, color="#f97316", symbol="circle", line=dict(color="#ffffff", width=1.4)),
                text=[f"${v:+.2f}" for v in t2_valid_spread["kurtosis_spread"]] if show_labels else None,
                textposition="bottom center",
                textfont=dict(color="#f97316", size=9),
                hovertemplate=(
                    f"<b>{date2} Kurtosis Fly Spread</b><br>"
                    + "Inner Offset (h): ±%{x:.0f} pts (Outer: ±%{customdata:.0f} pts)<br>"
                    + "Spread (Outer − Inner): <b>$%{y:+.2f}</b><extra></extra>"
                ),
                customdata=t2_valid_spread["offset"] * 2.0,
            ),
            row=2,
            col=1,
        )

    # Wing Retention Ratio (% of ATM fly price)
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["kurtosis_ratio"].values * 100.0,
            mode="lines+markers",
            name=f"Wing Retention % ({date1})",
            line=dict(color="#d29922", width=2.0, dash="dash"),
            marker=dict(size=6, color="#d29922", symbol="triangle-up"),
            hovertemplate=(
                f"<b>{date1} Wing Retention</b><br>"
                + "Offset: ±%{x:.0f} pts<br>"
                + "Retained ATM Value: <b>%{y:.1f}%</b><extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["kurtosis_ratio"].values * 100.0,
            mode="lines+markers",
            name=f"Wing Retention % ({date2})",
            line=dict(color="#38bdf8", width=2.2),
            marker=dict(size=6, color="#38bdf8", symbol="triangle-down"),
            hovertemplate=(
                f"<b>{date2} Wing Retention</b><br>"
                + "Offset: ±%{x:.0f} pts<br>"
                + "Retained ATM Value: <b>%{y:.1f}%</b><extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    # Layout styling
    fig = apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>Butterfly Curvature &amp; Kurtosis Butterfly Dynamics:</b> {date1} &rarr; {date2}",
            font=dict(size=15, color="#f0f6fc"),
        ),
        height=680,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            y=1.06,
            x=0.01,
            bgcolor="rgba(19, 24, 35, 0.8)",
            bordercolor="#30363d",
            font=dict(size=11),
        ),
    )

    fig.update_xaxes(
        title_text="Moneyness Distance from ATM: ΔK (pts)",
        row=2,
        col=1,
        dtick=100,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
        showspikes=True,
        spikemode="across",
        spikethickness=1.2,
        spikecolor="#38bdf8",
    )
    fig.update_xaxes(
        row=1,
        col=1,
        dtick=100,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
        showspikes=True,
        spikemode="across",
        spikethickness=1.2,
        spikecolor="#38bdf8",
    )
    fig.update_yaxes(
        title_text="Fly Curvature ($)",
        row=1,
        col=1,
        gridcolor="#21262d",
        zerolinecolor="#30363d",
    )
    fig.update_yaxes(
        title_text="Kurtosis Spread ($) / Retention (%)",
        row=2,
        col=1,
        gridcolor="#21262d",
        zerolinecolor="#484f58",
    )

    return fig


def create_consecutive_fly_call_put_skew_chart(
    date1: str,
    date2: str,
    fly_struct1: dict[str, Any],
    fly_struct2: dict[str, Any],
    show_labels: bool = False,
) -> go.Figure:
    """Create dedicated two-row chart of Call Fly Skew ($) on top and Put Fly Skew ($) on bottom."""
    t1 = fly_struct1["table"].copy()
    t2 = fly_struct2["table"].copy()
    atm1 = fly_struct1.get("atm_fly", 0.0) or 0.0
    atm2 = fly_struct2.get("atm_fly", 0.0) or 0.0

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=(
            f"<b>Call Fly Skew Relative to ATM [$F_{{Call}}(ATM+h) - F(ATM)$]:</b> {date1} vs {date2} ($/contract)",
            f"<b>Put Fly Skew Relative to ATM [$F_{{Put}}(ATM-h) - F(ATM)$]:</b> {date1} vs {date2} ($/contract)",
        ),
        row_heights=[0.5, 0.5],
    )

    x1 = t1["offset"].values
    x2 = t2["offset"].values

    # Row 1: Call Fly Skew
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["call_skew"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Call Fly Skew ({date1})",
            line=dict(color="#2ea043", width=2.4, dash="dot"),
            marker=dict(size=7, color="#2ea043", symbol="square"),
            text=[f"${v:+.2f}" if v is not None else "" for v in t1["call_skew"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#2ea043", size=9),
            hovertemplate=(
                f"<b>{date1} Call Fly Skew</b><br>"
                + "Offset: +%{x:.0f} pts<br>"
                + "Call Fly Skew (F - ATM): <b>$%{y:+.2f}</b><br>"
                + "Call Fly Prem: <b>$%{customdata:.2f}</b><extra></extra>"
            ),
            customdata=t1["fly_call"].values,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["call_skew"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Call Fly Skew ({date2}) ★",
            line=dict(color="#3fb950", width=3.4),
            marker=dict(size=8, color="#3fb950", symbol="circle", line=dict(color="#ffffff", width=1.2)),
            text=[f"${v:+.2f}" if v is not None else "" for v in t2["call_skew"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#3fb950", size=9),
            hovertemplate=(
                f"<b>{date2} Call Fly Skew</b><br>"
                + "Offset: +%{x:.0f} pts<br>"
                + "Call Fly Skew (F - ATM): <b>$%{y:+.2f}</b><br>"
                + "Call Fly Prem: <b>$%{customdata:.2f}</b><extra></extra>"
            ),
            customdata=t2["fly_call"].values,
        ),
        row=1,
        col=1,
    )

    # Row 2: Put Fly Skew
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["put_skew"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Put Fly Skew ({date1})",
            line=dict(color="#f85149", width=2.4, dash="dot"),
            marker=dict(size=7, color="#f85149", symbol="square"),
            text=[f"${v:+.2f}" if v is not None else "" for v in t1["put_skew"].values] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#f85149", size=9),
            hovertemplate=(
                f"<b>{date1} Put Fly Skew</b><br>"
                + "Offset: -%{x:.0f} pts<br>"
                + "Put Fly Skew (F - ATM): <b>$%{y:+.2f}</b><br>"
                + "Put Fly Prem: <b>$%{customdata:.2f}</b><extra></extra>"
            ),
            customdata=t1["fly_put"].values,
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["put_skew"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Put Fly Skew ({date2}) ★",
            line=dict(color="#ff7b72", width=3.4),
            marker=dict(size=8, color="#ff7b72", symbol="diamond", line=dict(color="#ffffff", width=1.2)),
            text=[f"${v:+.2f}" if v is not None else "" for v in t2["put_skew"].values] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#ff7b72", size=9),
            hovertemplate=(
                f"<b>{date2} Put Fly Skew</b><br>"
                + "Offset: -%{x:.0f} pts<br>"
                + "Put Fly Skew (F - ATM): <b>$%{y:+.2f}</b><br>"
                + "Put Fly Prem: <b>$%{customdata:.2f}</b><extra></extra>"
            ),
            customdata=t2["fly_put"].values,
        ),
        row=2,
        col=1,
    )

    fig.add_hline(y=0, line=dict(color="#484f58", width=1.2, dash="dash"), row=1, col=1)
    fig.add_hline(y=0, line=dict(color="#484f58", width=1.2, dash="dash"), row=2, col=1)

    fig = apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>Call Fly Skew &amp; Put Fly Skew Relative to ATM ($/contract):</b> {date1} &rarr; {date2}",
            font=dict(size=15, color="#f0f6fc"),
        ),
        height=680,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.06, x=0.01, bgcolor="rgba(19, 24, 35, 0.8)", bordercolor="#30363d", font=dict(size=11)),
    )
    fig.update_xaxes(title_text="Moneyness Distance from ATM: ΔK (pts)", row=2, col=1, dtick=100, gridcolor="#21262d")
    fig.update_xaxes(row=1, col=1, dtick=100, gridcolor="#21262d")
    fig.update_yaxes(title_text="Call Fly Skew ($)", row=1, col=1, gridcolor="#21262d")
    fig.update_yaxes(title_text="Put Fly Skew ($)", row=2, col=1, gridcolor="#21262d")
    return fig


def create_consecutive_fly_rr_chart(
    date1: str,
    date2: str,
    fly_struct1: dict[str, Any],
    fly_struct2: dict[str, Any],
    show_labels: bool = False,
) -> go.Figure:
    """Create dedicated chart for Fly Risk Reversal ($F_{Call} - F_{Put}$) and daily shifts."""
    t1 = fly_struct1["table"].copy()
    t2 = fly_struct2["table"].copy()

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=(
            f"<b>Fly Skew / Fly Risk Reversal ($F_{{Call}} - F_{{Put}}$):</b> {date1} vs {date2} ($/fly)",
            f"<b>Daily Shift in Fly Risk Reversal ($\\Delta$ Fly RR):</b> Shift from {date1} ($/fly)",
        ),
        row_heights=[0.56, 0.44],
    )

    x1 = t1["offset"].values
    x2 = t2["offset"].values

    fig.add_hline(y=0.0, line=dict(color="#484f58", width=1.4, dash="dash"), row=1, col=1)
    fig.add_hline(y=0.0, line=dict(color="#484f58", width=1.4, dash="dash"), row=2, col=1)

    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["risk_reversal"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Fly Risk Reversal ({date1})",
            line=dict(color="#58a6ff", width=2.6, dash="dot"),
            marker=dict(size=7, color="#58a6ff", symbol="diamond"),
            text=[f"${v:+.2f}" if v is not None else "" for v in t1["risk_reversal"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#58a6ff", size=9),
            hovertemplate=f"<b>{date1} Fly RR</b><br>Offset: ±%{{x:.0f}} pts<br>Fly RR: <b>$%{{y:+.2f}}</b><extra></extra>",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["risk_reversal"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Fly Risk Reversal ({date2}) ★",
            line=dict(color="#38bdf8", width=3.4),
            marker=dict(size=8, color="#38bdf8", symbol="circle", line=dict(color="#ffffff", width=1.4)),
            text=[f"${v:+.2f}" if v is not None else "" for v in t2["risk_reversal"].values] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#38bdf8", size=9),
            hovertemplate=f"<b>{date2} Fly RR</b><br>Offset: ±%{{x:.0f}} pts<br>Fly RR: <b>$%{{y:+.2f}}</b><extra></extra>",
        ),
        row=1,
        col=1,
    )

    merged_rr = pd.merge(
        t1[["offset", "risk_reversal"]],
        t2[["offset", "risk_reversal"]],
        on="offset",
        suffixes=("_1", "_2"),
    )
    if not merged_rr.empty:
        merged_rr["delta_rr"] = merged_rr["risk_reversal_2"] - merged_rr["risk_reversal_1"]
        bar_colors = ["#3fb950" if d >= 0 else "#f85149" for d in merged_rr["delta_rr"]]
        fig.add_trace(
            go.Bar(
                x=merged_rr["offset"],
                y=merged_rr["delta_rr"],
                name="Δ Fly RR (T+1 − T)",
                marker=dict(color=bar_colors, opacity=0.55),
                hovertemplate="<b>Δ Fly RR</b><br>Offset: ±%{x:.0f} pts<br>Shift: <b>$%{y:+.2f}</b><extra></extra>",
            ),
            row=2,
            col=1,
        )

    fig = apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>Fly Skew / Fly Risk Reversal ($F_{{Call}} - F_{{Put}}$):</b> {date1} &rarr; {date2}",
            font=dict(size=15, color="#f0f6fc"),
        ),
        height=680,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.06, x=0.01, bgcolor="rgba(19, 24, 35, 0.8)", bordercolor="#30363d", font=dict(size=11)),
    )
    fig.update_xaxes(title_text="Moneyness Distance from ATM: ΔK (pts)", row=2, col=1, dtick=100, gridcolor="#21262d")
    fig.update_xaxes(row=1, col=1, dtick=100, gridcolor="#21262d")
    fig.update_yaxes(title_text="Fly Risk Reversal ($/fly)", row=1, col=1, gridcolor="#21262d")
    fig.update_yaxes(title_text="Δ Fly RR ($/fly)", row=2, col=1, gridcolor="#21262d")
    return fig


def create_consecutive_fly_curvature_chart(
    date1: str,
    date2: str,
    fly_struct1: dict[str, Any],
    fly_struct2: dict[str, Any],
    show_labels: bool = False,
) -> go.Figure:
    """Create dedicated chart for Fly Premium Curvature [$(F_P + F_C)/2 - F_{ATM}$] and daily shifts."""
    t1 = fly_struct1["table"].copy()
    t2 = fly_struct2["table"].copy()

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=(
            f"<b>Fly Premium Curvature [$\\frac{{F_{{Put}} + F_{{Call}}}}{{2}} - F_{{ATM}}$]:</b> {date1} vs {date2} ($/contract)",
            f"<b>Daily Shift in Fly Curvature ($\\Delta$ Curvature):</b> Shift from {date1} ($/contract)",
        ),
        row_heights=[0.56, 0.44],
    )

    x1 = t1["offset"].values
    x2 = t2["offset"].values

    fig.add_hline(y=0.0, line=dict(color="#484f58", width=1.4, dash="dash"), row=1, col=1)
    fig.add_hline(y=0.0, line=dict(color="#484f58", width=1.4, dash="dash"), row=2, col=1)

    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["curvature"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Fly Curvature ({date1})",
            line=dict(color="#bc8cff", width=2.6, dash="dot"),
            marker=dict(size=7, color="#bc8cff", symbol="square"),
            text=[f"${v:+.2f}" if v is not None else "" for v in t1["curvature"].values] if show_labels else None,
            textposition="top center",
            textfont=dict(color="#bc8cff", size=9),
            hovertemplate=f"<b>{date1} Fly Curvature</b><br>Offset: ±%{{x:.0f}} pts<br>Curvature: <b>$%{{y:+.2f}}</b><extra></extra>",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["curvature"].values,
            mode="lines+markers" if not show_labels else "lines+markers+text",
            name=f"Fly Curvature ({date2}) ★",
            line=dict(color="#d2a8ff", width=3.4),
            marker=dict(size=8, color="#d2a8ff", symbol="diamond", line=dict(color="#ffffff", width=1.4)),
            text=[f"${v:+.2f}" if v is not None else "" for v in t2["curvature"].values] if show_labels else None,
            textposition="bottom center",
            textfont=dict(color="#d2a8ff", size=9),
            hovertemplate=f"<b>{date2} Fly Curvature</b><br>Offset: ±%{{x:.0f}} pts<br>Curvature: <b>$%{{y:+.2f}}</b><extra></extra>",
        ),
        row=1,
        col=1,
    )

    merged_c = pd.merge(
        t1[["offset", "curvature"]],
        t2[["offset", "curvature"]],
        on="offset",
        suffixes=("_1", "_2"),
    )
    if not merged_c.empty:
        merged_c["delta_c"] = merged_c["curvature_2"] - merged_c["curvature_1"]
        bar_colors = ["#38bdf8" if d >= 0 else "#f85149" for d in merged_c["delta_c"]]
        fig.add_trace(
            go.Bar(
                x=merged_c["offset"],
                y=merged_c["delta_c"],
                name="Δ Fly Curvature (T+1 − T)",
                marker=dict(color=bar_colors, opacity=0.55),
                hovertemplate="<b>Δ Fly Curvature</b><br>Offset: ±%{x:.0f} pts<br>Shift: <b>$%{y:+.2f}</b><extra></extra>",
            ),
            row=2,
            col=1,
        )

    fig = apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>Fly Premium Curvature [$\\frac{{F_{{Put}} + F_{{Call}}}}{{2}} - F_{{ATM}}$]:</b> {date1} &rarr; {date2}",
            font=dict(size=15, color="#f0f6fc"),
        ),
        height=680,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.06, x=0.01, bgcolor="rgba(19, 24, 35, 0.8)", bordercolor="#30363d", font=dict(size=11)),
    )
    fig.update_xaxes(title_text="Moneyness Distance from ATM: ΔK (pts)", row=2, col=1, dtick=100, gridcolor="#21262d")
    fig.update_xaxes(row=1, col=1, dtick=100, gridcolor="#21262d")
    fig.update_yaxes(title_text="Fly Curvature ($)", row=1, col=1, gridcolor="#21262d")
    fig.update_yaxes(title_text="Δ Fly Curvature ($)", row=2, col=1, gridcolor="#21262d")
    return fig


def create_consecutive_fly_kurtosis_chart(
    date1: str,
    date2: str,
    fly_struct1: dict[str, Any],
    fly_struct2: dict[str, Any],
    show_labels: bool = False,
) -> go.Figure:
    """Create dedicated chart for Kurtosis Butterfly Spread & Wing Retention Ratio."""
    t1 = fly_struct1["table"].copy()
    t2 = fly_struct2["table"].copy()

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=(
            f"<b>Kurtosis Butterfly Spread [Outer $2h$ vs Inner $h$ Fly]:</b> {date1} vs {date2} ($/contract)",
            f"<b>Wing Retention Ratio [$\\frac{{(F_P + F_C)/2}}{{F_{{ATM}}}}$]:</b> {date1} vs {date2} (% of ATM fly price)",
        ),
        row_heights=[0.52, 0.48],
    )

    t1_valid_spread = t1.dropna(subset=["kurtosis_spread"])
    t2_valid_spread = t2.dropna(subset=["kurtosis_spread"])

    if not t1_valid_spread.empty:
        fig.add_trace(
            go.Scatter(
                x=t1_valid_spread["offset"],
                y=t1_valid_spread["kurtosis_spread"],
                mode="lines+markers" if not show_labels else "lines+markers+text",
                name=f"Kurtosis Fly Spread ({date1})",
                line=dict(color="#f0883e", width=2.6, dash="dot"),
                marker=dict(size=7, color="#f0883e", symbol="square"),
                text=[f"${v:+.2f}" for v in t1_valid_spread["kurtosis_spread"]] if show_labels else None,
                textposition="top center",
                textfont=dict(color="#f0883e", size=9),
                hovertemplate=f"<b>{date1} Kurtosis Fly Spread</b><br>Inner: ±%{{x:.0f}} pts<br>Spread: <b>$%{{y:+.2f}}</b><extra></extra>",
            ),
            row=1,
            col=1,
        )

    if not t2_valid_spread.empty:
        fig.add_trace(
            go.Scatter(
                x=t2_valid_spread["offset"],
                y=t2_valid_spread["kurtosis_spread"],
                mode="lines+markers" if not show_labels else "lines+markers+text",
                name=f"Kurtosis Fly Spread ({date2}) ★",
                line=dict(color="#f97316", width=3.4),
                marker=dict(size=8, color="#f97316", symbol="circle", line=dict(color="#ffffff", width=1.4)),
                text=[f"${v:+.2f}" for v in t2_valid_spread["kurtosis_spread"]] if show_labels else None,
                textposition="bottom center",
                textfont=dict(color="#f97316", size=9),
                hovertemplate=f"<b>{date2} Kurtosis Fly Spread</b><br>Inner: ±%{{x:.0f}} pts<br>Spread: <b>$%{{y:+.2f}}</b><extra></extra>",
            ),
            row=1,
            col=1,
        )

    # Row 2: Wing Retention Ratio (%)
    x1 = t1["offset"].values
    x2 = t2["offset"].values
    fig.add_trace(
        go.Scatter(
            x=x1,
            y=t1["kurtosis_ratio"].values * 100.0,
            mode="lines+markers",
            name=f"Wing Retention % ({date1})",
            line=dict(color="#d29922", width=2.2, dash="dash"),
            marker=dict(size=7, color="#d29922", symbol="diamond"),
            hovertemplate=f"<b>{date1} Wing Retention</b><br>Offset: ±%{{x:.0f}} pts<br>Retention: <b>%{{y:.1f}}%</b><extra></extra>",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x2,
            y=t2["kurtosis_ratio"].values * 100.0,
            mode="lines+markers",
            name=f"Wing Retention % ({date2}) ★",
            line=dict(color="#38bdf8", width=3.2),
            marker=dict(size=8, color="#38bdf8", symbol="circle", line=dict(color="#ffffff", width=1.2)),
            hovertemplate=f"<b>{date2} Wing Retention</b><br>Offset: ±%{{x:.0f}} pts<br>Retention: <b>%{{y:.1f}}%</b><extra></extra>",
        ),
        row=2,
        col=1,
    )

    fig.add_hline(y=0, line=dict(color="#484f58", width=1.2, dash="dash"), row=1, col=1)

    fig = apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>Kurtosis Butterfly Spread &amp; Wing Retention Ratio:</b> {date1} &rarr; {date2}",
            font=dict(size=15, color="#f0f6fc"),
        ),
        height=680,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.06, x=0.01, bgcolor="rgba(19, 24, 35, 0.8)", bordercolor="#30363d", font=dict(size=11)),
    )
    fig.update_xaxes(title_text="Moneyness Distance from ATM: ΔK (pts)", row=2, col=1, dtick=100, gridcolor="#21262d")
    fig.update_xaxes(row=1, col=1, dtick=100, gridcolor="#21262d")
    fig.update_yaxes(title_text="Kurtosis Spread ($)", row=1, col=1, gridcolor="#21262d")
    fig.update_yaxes(title_text="Wing Retention (%)", row=2, col=1, gridcolor="#21262d")
    return fig


