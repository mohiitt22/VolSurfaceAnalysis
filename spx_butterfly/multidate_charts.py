"""Interactive Plotly charts for the Multi-Date Surface Comparison Workspace.

Features:
- Harmonized date color palette across IV smile, Call fly, and Put fly charts.
- Fixed factor color convention (Level: Blue, Skew: Purple, Curvature: Orange, Residual: Magenta/Red).
- Factor bridge transformation overlays with optional transparent contribution fills.
- High-performance unified hover tooltips and focus-date highlighting.
"""

from __future__ import annotations

from typing import Any, Literal
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from spx_butterfly.multidate_model import (
    DailyFactorMetrics,
    DailyFlyObservation,
    FactorDifferences,
    FixedFlyAttribution,
    ObservedFlyDifference,
    SmileDecompositionPoint,
    extract_smile_points,
    compute_smile_structure_metrics,
    compute_fly_structure_metrics,
)

# Dark Quantitative Research Theme
BASE_THEME = dict(
    paper_bgcolor="#0d1117",
    plot_bgcolor="#161b22",
    font=dict(color="#c9d1d9", family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", size=12),
    margin=dict(l=55, r=35, t=50, b=45),
    hoverlabel=dict(bgcolor="#1f242c", font_color="#f0f6fc", font_size=12, bordercolor="#30363d"),
    legend=dict(
        bgcolor="rgba(22, 27, 34, 0.85)",
        bordercolor="#30363d",
        borderwidth=1,
        font=dict(size=11, color="#c9d1d9"),
    ),
)

BASE_AXIS_STYLE = dict(
    gridcolor="#282f3a",
    gridwidth=1,
    zerolinecolor="#484f58",
    zerolinewidth=1.5,
    showline=True,
    linecolor="#38414e",
    tickfont=dict(color="#adbac7", size=11),
    title_font=dict(size=12, color="#f0f6fc"),
    showspikes=True,
    spikethickness=1.5,
    spikecolor="#adbac7",
    spikemode="across",
    spikedash="solid",
)

THEME_LAYOUT = dict(**BASE_THEME, xaxis=BASE_AXIS_STYLE, yaxis=BASE_AXIS_STYLE)


def apply_theme_layout(fig: go.Figure, **overrides: Any) -> go.Figure:
    """Apply base dark theme with clean dictionary overrides to prevent keyword collisions."""
    layout_dict = dict(BASE_THEME)
    layout_dict.update(overrides)
    fig.update_layout(**layout_dict)
    return fig


# Extended High-Contrast Qualitative Palette for Selected Dates
DATE_PALETTE = [
    "#58a6ff",  # Soft Blue
    "#39c5bb",  # Cyan / Teal
    "#a371f7",  # Purple
    "#f0883e",  # Orange
    "#3fb950",  # Emerald Green
    "#e3b341",  # Gold / Amber
    "#f778ba",  # Pink
    "#79c0ff",  # Sky Blue
    "#56d364",  # Light Green
    "#d29922",  # Dark Gold
    "#bc8cff",  # Violet
    "#ff7b72",  # Coral
    "#2ea043",  # Deep Green
    "#1f6feb",  # Royal Blue
    "#db61a2",  # Magenta
    "#8957e5",  # Deep Violet
    "#bb8009",  # Brown Gold
    "#6e7681",  # Neutral Slate
]

# Fixed Factor Colors
FACTOR_COLORS = {
    "level": "#388bfd",      # Blue
    "skew": "#bc8cff",       # Purple
    "curvature": "#f0883e",  # Orange
    "residual": "#f85149",   # Magenta / Red
    "observed": "#f0f6fc",   # White
    "modelled": "#79c0ff",   # Light Cyan
}


def get_date_color_map(dates: list[str]) -> dict[str, str]:
    """Assign stable, consistent colors to dates in chronological order."""
    sorted_d = sorted(dates)
    color_map: dict[str, str] = {}
    n_pal = len(DATE_PALETTE)
    for i, d in enumerate(sorted_d):
        color_map[d] = DATE_PALETTE[i % n_pal]
    return color_map


# ---------------------------------------------------------------------------
# Chart 1: Multi-Date IV Smile Comparison
# ---------------------------------------------------------------------------

def create_multidate_iv_chart(
    snapshots: dict[str, pd.DataFrame],
    reference_date: str,
    focus_date: str,
    alignment_mode: Literal["relative", "absolute"] = "relative",
    highlight_focus: bool = True,
    show_bridge: bool = False,
    show_bridge_fills: bool = False,
    bridge_points: list[SmileDecompositionPoint] | None = None,
    visible_bridge_layers: dict[str, bool] | None = None,
    line_thickness: float = 2.6,
) -> go.Figure:
    """Plot multi-date IV smiles with optional factor bridge overlays."""
    fig = go.Figure()

    if not snapshots:
        return apply_theme_layout(fig, title=dict(text="Historical IV Smile Comparison (No Dates Selected)"))

    sorted_dates = sorted(snapshots.keys())
    color_map = get_date_color_map(sorted_dates)

    if visible_bridge_layers is None:
        visible_bridge_layers = {
            "ref": True,
            "level": True,
            "skew": True,
            "curvature": True,
            "actual": True,
        }

    # 1. Plot all selected dates' IV smiles
    for d in sorted_dates:
        snap = snapshots[d]
        smile = extract_smile_points(snap)
        if smile.empty:
            continue

        s0 = float(snap["underlying"].iloc[0])
        atm0 = float(snap["atm_strike"].iloc[0])
        dte0 = float(snap["target_dte"].iloc[0])

        is_focus = (d == focus_date)
        is_ref = (d == reference_date)

        # Style based on focus/ref with strong, easily visible lines
        base_color = color_map[d]
        if highlight_focus:
            if is_focus:
                line_width = max(4.0, line_thickness * 1.55)
                opacity = 1.0
                marker_size = 8.5
                marker_line = dict(color="#ffffff", width=2.0)
            elif is_ref:
                line_width = max(3.2, line_thickness * 1.25)
                opacity = 0.95
                marker_size = 7.5
                marker_line = dict(color="#ffffff", width=1.5)
            else:
                line_width = max(2.2, line_thickness * 0.9)
                opacity = 0.78  # High visibility even when focus is emphasized
                marker_size = 6.0
                marker_line = dict(color="#161b22", width=1.0)
        else:
            if is_focus:
                line_width = max(4.0, line_thickness * 1.5)
                opacity = 1.0
                marker_size = 8.5
                marker_line = dict(color="#ffffff", width=2.0)
            elif is_ref:
                line_width = max(3.4, line_thickness * 1.3)
                opacity = 0.95
                marker_size = 7.5
                marker_line = dict(color="#ffffff", width=1.5)
            else:
                line_width = line_thickness
                opacity = 0.88  # Vivid, saturated lines for all dates
                marker_size = 6.5
                marker_line = dict(color="#161b22", width=1.0)

        if alignment_mode == "relative":
            x_vals = smile["atm_offset"].to_numpy(dtype=float)
            x_title = "ATM Strike Offset (K − K_ATM, SPX Points)"
        else:
            x_vals = smile["strike"].to_numpy(dtype=float)
            x_title = "Absolute Strike Price K (SPX Index Points)"

        y_vals = smile["iv_pct"].to_numpy(dtype=float)

        # Build customdata for hover
        custom_arr = np.column_stack([
            np.full(len(smile), d),
            np.full(len(smile), s0),
            np.full(len(smile), atm0),
            smile["strike"].to_numpy(dtype=float),
            smile["atm_offset"].to_numpy(dtype=float),
            smile["option_side"].to_numpy(dtype=str),
            y_vals,
            np.full(len(smile), dte0),
        ])

        name_label = f"<b>{d}</b> (Focus)" if is_focus else f"{d} (Ref)" if is_ref else f"{d}"

        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="lines+markers",
                name=name_label,
                line=dict(color=base_color, width=line_width),
                marker=dict(size=marker_size, color=base_color, line=marker_line),
                opacity=opacity,
                customdata=custom_arr,
                hovertemplate=(
                    "<b>Date: %{customdata[0]}</b><br>"
                    "SPX Spot: %{customdata[1]:.2f}<br>"
                    "ATM Strike: %{customdata[2]:.0f}<br>"
                    "Strike: %{customdata[3]:.0f} (%{customdata[5]})<br>"
                    "ATM Offset: %{customdata[4]:+.0f} pts<br>"
                    "<b>Implied Vol: %{customdata[6]:.3f}%</b><br>"
                    "Target Maturity: %{customdata[7]:.0f} DTE<extra></extra>"
                ),
            )
        )

        # In absolute strike mode, add marker indicator at ATM strike
        if alignment_mode == "absolute":
            atm_iv = smile[smile["atm_offset"] == 0]["iv_pct"]
            if not atm_iv.empty:
                fig.add_trace(
                    go.Scatter(
                        x=[atm0],
                        y=[atm_iv.iloc[0]],
                        mode="markers",
                        marker=dict(symbol="diamond", size=9, color=base_color, line=dict(color="#ffffff", width=1.5)),
                        name=f"{d} ATM",
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )

    # 2. Factor Bridge Curves (only in relative alignment mode)
    if show_bridge and bridge_points and alignment_mode == "relative":
        x_pts = np.array([p.atm_offset for p in bridge_points])
        iv_0_pts = np.array([p.iv_0 for p in bridge_points])
        iv_l_pts = np.array([p.iv_l for p in bridge_points])
        iv_ls_pts = np.array([p.iv_ls for p in bridge_points])
        iv_lsc_pts = np.array([p.iv_lsc for p in bridge_points])
        iv_act_pts = np.array([p.iv_actual for p in bridge_points])

        # Optional Shaded Fills between consecutive curves
        if show_bridge_fills:
            fig.add_trace(
                go.Scatter(
                    x=np.concatenate([x_pts, x_pts[::-1]]),
                    y=np.concatenate([iv_0_pts, iv_l_pts[::-1]]),
                    fill="toself",
                    fillcolor="rgba(56, 139, 253, 0.12)",
                    line=dict(color="rgba(255,255,255,0)"),
                    hoverinfo="skip",
                    showlegend=True,
                    name="Area: Level Contribution",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=np.concatenate([x_pts, x_pts[::-1]]),
                    y=np.concatenate([iv_l_pts, iv_ls_pts[::-1]]),
                    fill="toself",
                    fillcolor="rgba(188, 140, 255, 0.12)",
                    line=dict(color="rgba(255,255,255,0)"),
                    hoverinfo="skip",
                    showlegend=True,
                    name="Area: Skew Contribution",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=np.concatenate([x_pts, x_pts[::-1]]),
                    y=np.concatenate([iv_ls_pts, iv_lsc_pts[::-1]]),
                    fill="toself",
                    fillcolor="rgba(240, 136, 62, 0.12)",
                    line=dict(color="rgba(255,255,255,0)"),
                    hoverinfo="skip",
                    showlegend=True,
                    name="Area: Curvature Contribution",
                )
            )

        # Bridge Curve 1: Reference Smile IV_0
        if visible_bridge_layers.get("ref", True):
            fig.add_trace(
                go.Scatter(
                    x=x_pts,
                    y=iv_0_pts,
                    mode="lines",
                    name=f"Bridge 1: Ref ({reference_date})",
                    line=dict(color="#8b949e", width=2.2, dash="solid"),
                    hovertemplate="Offset: %{x:+.0f} pts<br>IV_0 (Ref): %{y:.3f}%<extra></extra>",
                )
            )

        # Bridge Curve 2: Level-Adjusted IV_L
        if visible_bridge_layers.get("level", True):
            fig.add_trace(
                go.Scatter(
                    x=x_pts,
                    y=iv_l_pts,
                    mode="lines",
                    name="Bridge 2: + Level (IV_L)",
                    line=dict(color=FACTOR_COLORS["level"], width=2.0, dash="dash"),
                    hovertemplate="Offset: %{x:+.0f} pts<br>IV_L (Level Shift): %{y:.3f}%<extra></extra>",
                )
            )

        # Bridge Curve 3: Level + Skew Adjusted IV_LS
        if visible_bridge_layers.get("skew", True):
            fig.add_trace(
                go.Scatter(
                    x=x_pts,
                    y=iv_ls_pts,
                    mode="lines",
                    name="Bridge 3: + Skew (IV_LS)",
                    line=dict(color=FACTOR_COLORS["skew"], width=2.0, dash="dash"),
                    hovertemplate="Offset: %{x:+.0f} pts<br>IV_LS (Level + Skew): %{y:.3f}%<extra></extra>",
                )
            )

        # Bridge Curve 4: Level + Skew + Curvature Adjusted IV_LSC
        if visible_bridge_layers.get("curvature", True):
            fig.add_trace(
                go.Scatter(
                    x=x_pts,
                    y=iv_lsc_pts,
                    mode="lines",
                    name="Bridge 4: + Curvature (IV_LSC Modelled)",
                    line=dict(color=FACTOR_COLORS["curvature"], width=2.2, dash="dashdot"),
                    hovertemplate="Offset: %{x:+.0f} pts<br>IV_LSC (3-Factor Model): %{y:.3f}%<extra></extra>",
                )
            )

        # Residual markers showing unexplained local movement
        res_pts = np.array([p.residual for p in bridge_points])
        fig.add_trace(
            go.Scatter(
                x=x_pts,
                y=iv_act_pts,
                mode="markers",
                name="Bridge 5: Actual Focus (Residual Error)",
                marker=dict(
                    symbol="circle-open",
                    size=9,
                    color=FACTOR_COLORS["residual"],
                    line=dict(width=2, color=FACTOR_COLORS["residual"]),
                ),
                customdata=res_pts,
                hovertemplate=(
                    "Offset: %{x:+.0f} pts<br>"
                    "Actual IV: %{y:.3f}%<br>"
                    "<b>Residual Gap: %{customdata:+.3f} pts</b><extra></extra>"
                ),
            )
        )

    # Reference ATM Line at 0 in relative mode
    if alignment_mode == "relative":
        fig.add_vline(
            x=0,
            line_width=1.5,
            line_dash="dot",
            line_color="#484f58",
            annotation_text="ATM Reference (x = 0)",
            annotation_position="top left",
            annotation_font=dict(color="#8b949e", size=10),
        )

    title_text = (
        f"<b>Historical IV Smile Comparison</b> — {len(snapshots)} Dates Selected "
        f"(Ref: {reference_date} | Focus: {focus_date})"
    )

    return apply_theme_layout(
        fig,
        title=dict(text=title_text, font=dict(size=14, color="#f0f6fc")),
        xaxis=dict(
            **BASE_AXIS_STYLE,
            title=x_title,
            dtick=100 if alignment_mode == "relative" else None,
        ),
        yaxis=dict(**BASE_AXIS_STYLE, title="Implied Volatility (%)"),
        hovermode="x unified" if alignment_mode == "relative" else "closest",
        height=540,
    )


# ---------------------------------------------------------------------------
# Chart 2: IV Smile Change Attribution Graph
# ---------------------------------------------------------------------------

def create_iv_attribution_chart(
    bridge_points: list[SmileDecompositionPoint],
    reference_date: str,
    focus_date: str,
    visible_series: dict[str, bool] | None = None,
) -> go.Figure:
    """Plot IV Smile Change Attribution: Observed, Level, Skew, Curvature, Modelled, Residual."""
    fig = go.Figure()

    if not bridge_points:
        return apply_theme_layout(fig, title=dict(text="IV Smile Change Attribution (No Aligned Points)"))

    if visible_series is None:
        visible_series = {
            "observed": True,
            "level": True,
            "skew": True,
            "curvature": True,
            "modelled": True,
            "residual": True,
        }

    offsets = np.array([p.atm_offset for p in bridge_points])
    obs_chg = np.array([p.observed_change for p in bridge_points])
    lvl_comp = np.array([p.level_comp for p in bridge_points])
    skw_comp = np.array([p.skew_comp for p in bridge_points])
    crv_comp = np.array([p.curvature_comp for p in bridge_points])
    mod_chg = np.array([p.modelled_change for p in bridge_points])
    residuals = np.array([p.residual for p in bridge_points])

    ref_ivs = np.array([p.ref_iv_pct for p in bridge_points])
    foc_ivs = np.array([p.focus_iv_pct for p in bridge_points])

    # Table-like hover customdata
    custom_arr = np.column_stack([
        ref_ivs, foc_ivs, obs_chg, lvl_comp, skw_comp, crv_comp, mod_chg, residuals
    ])

    hover_fmt = (
        "<b>Offset: %{x:+.0f} pts</b><br>"
        "Reference IV: %{customdata[0]:.3f}%<br>"
        "Focus IV: %{customdata[1]:.3f}%<br>"
        "<b>Total IV Change: %{customdata[2]:+.3f} pts</b><br>"
        "├ Level Component: %{customdata[3]:+.3f} pts<br>"
        "├ Skew Component: %{customdata[4]:+.3f} pts<br>"
        "├ Curvature Component: %{customdata[5]:+.3f} pts<br>"
        "<b>Modelled 3-Factor Change: %{customdata[6]:+.3f} pts</b><br>"
        "<b>Residual Local Movement: %{customdata[7]:+.3f} pts</b><extra></extra>"
    )

    # 1. Observed Total IV Change
    if visible_series.get("observed", True):
        fig.add_trace(
            go.Scatter(
                x=offsets,
                y=obs_chg,
                mode="lines+markers",
                name="Observed Total IV Change",
                line=dict(color=FACTOR_COLORS["observed"], width=2.8),
                marker=dict(size=6, color=FACTOR_COLORS["observed"]),
                customdata=custom_arr,
                hovertemplate=hover_fmt,
            )
        )

    # 2. Level Component
    if visible_series.get("level", True):
        fig.add_trace(
            go.Scatter(
                x=offsets,
                y=lvl_comp,
                mode="lines",
                name="Level Component (L)",
                line=dict(color=FACTOR_COLORS["level"], width=2.0, dash="dash"),
                customdata=custom_arr,
                hovertemplate=hover_fmt,
            )
        )

    # 3. Skew Component
    if visible_series.get("skew", True):
        fig.add_trace(
            go.Scatter(
                x=offsets,
                y=skw_comp,
                mode="lines",
                name="Skew Component ((S/2)*x)",
                line=dict(color=FACTOR_COLORS["skew"], width=2.0, dash="dash"),
                customdata=custom_arr,
                hovertemplate=hover_fmt,
            )
        )

    # 4. Curvature Component
    if visible_series.get("curvature", True):
        fig.add_trace(
            go.Scatter(
                x=offsets,
                y=crv_comp,
                mode="lines",
                name="Curvature Component (C*x²)",
                line=dict(color=FACTOR_COLORS["curvature"], width=2.0, dash="dash"),
                customdata=custom_arr,
                hovertemplate=hover_fmt,
            )
        )

    # 5. Modelled Change
    if visible_series.get("modelled", True):
        fig.add_trace(
            go.Scatter(
                x=offsets,
                y=mod_chg,
                mode="lines",
                name="Total 3-Factor Modelled Change",
                line=dict(color=FACTOR_COLORS["modelled"], width=2.2, dash="dot"),
                customdata=custom_arr,
                hovertemplate=hover_fmt,
            )
        )

    # 6. Unexplained Residual
    if visible_series.get("residual", True):
        fig.add_trace(
            go.Scatter(
                x=offsets,
                y=residuals,
                mode="lines+markers",
                name="Unexplained Local Residual",
                line=dict(color=FACTOR_COLORS["residual"], width=1.8),
                marker=dict(symbol="x", size=6, color=FACTOR_COLORS["residual"]),
                customdata=custom_arr,
                hovertemplate=hover_fmt,
            )
        )

    # Baseline at zero
    fig.add_hline(y=0, line_width=1.0, line_color="#484f58", line_dash="solid")
    fig.add_vline(x=0, line_width=1.0, line_color="#484f58", line_dash="dot")

    return apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>IV Smile Change Attribution</b> (Focus: {focus_date} minus Ref: {reference_date})",
            font=dict(size=13, color="#f0f6fc"),
        ),
        xaxis=dict(**BASE_AXIS_STYLE, title="ATM Strike Offset (K − K_ATM, SPX Points)", dtick=100),
        yaxis=dict(**BASE_AXIS_STYLE, title="IV Change / Contribution (vol pts)"),
        hovermode="x unified",
        height=380,
    )


# ---------------------------------------------------------------------------
# Chart 3: Multi-Date Butterfly Premium Comparison (Call and Put)
# ---------------------------------------------------------------------------

def create_multidate_fly_chart(
    flies_by_date: dict[str, list[DailyFlyObservation]],
    option_side: Literal["call", "put"],
    reference_date: str,
    focus_date: str,
    alignment_mode: Literal["relative", "absolute"] = "relative",
    highlight_focus: bool = True,
    normalized_mode: bool = False,
    line_thickness: float = 2.6,
) -> go.Figure:
    """Plot multi-date butterfly premium curves with unified date colors."""
    fig = go.Figure()

    side_label = option_side.upper()
    title_suffix = "Call Butterfly (ATM+100 to ATM+800)" if option_side == "call" else "Put Butterfly (ATM-800 to ATM-100)"

    sorted_dates = sorted(flies_by_date.keys())
    color_map = get_date_color_map(sorted_dates)

    y_field = "normalized_premium" if normalized_mode else "fly_premium"
    y_title = "Normalized Fly Premium (pts/h)" if normalized_mode else "Net Fly Premium (SPX Points)"

    for d in sorted_dates:
        date_flies = [f for f in flies_by_date[d] if f.option_side == option_side]
        if not date_flies:
            continue

        date_flies.sort(key=lambda f: f.centre_strike)

        is_focus = (d == focus_date)
        is_ref = (d == reference_date)
        base_color = color_map[d]

        if highlight_focus:
            if is_focus:
                line_width = max(4.0, line_thickness * 1.55)
                opacity = 1.0
                marker_size = 8.5
                marker_line = dict(color="#ffffff", width=2.0)
            elif is_ref:
                line_width = max(3.2, line_thickness * 1.25)
                opacity = 0.95
                marker_size = 7.5
                marker_line = dict(color="#ffffff", width=1.5)
            else:
                line_width = max(2.2, line_thickness * 0.9)
                opacity = 0.78  # High visibility for non-focus dates
                marker_size = 6.0
                marker_line = dict(color="#161b22", width=1.0)
        else:
            if is_focus:
                line_width = max(4.0, line_thickness * 1.5)
                opacity = 1.0
                marker_size = 8.5
                marker_line = dict(color="#ffffff", width=2.0)
            elif is_ref:
                line_width = max(3.4, line_thickness * 1.3)
                opacity = 0.95
                marker_size = 7.5
                marker_line = dict(color="#ffffff", width=1.5)
            else:
                line_width = line_thickness
                opacity = 0.88  # Bright, solid line
                marker_size = 6.5
                marker_line = dict(color="#161b22", width=1.0)

        if alignment_mode == "relative":
            x_vals = [f.atm_offset for f in date_flies]
            x_title = f"{side_label} Fly Centre Offset from ATM (SPX Points)"
        else:
            x_vals = [f.centre_strike for f in date_flies]
            x_title = f"{side_label} Fly Centre Strike Price K (SPX Points)"

        y_vals = [getattr(f, y_field) for f in date_flies]

        custom_data = [
            [
                f.date,
                f.underlying,
                f.centre_strike,
                f.atm_offset,
                f.lower_strike,
                f.upper_strike,
                f.lower_premium,
                f.middle_premium,
                f.upper_premium,
                f.fly_premium,
                f.target_dte,
            ]
            for f in date_flies
        ]

        name_label = f"<b>{d}</b> (Focus)" if is_focus else f"{d} (Ref)" if is_ref else f"{d}"

        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_vals,
                mode="lines+markers",
                name=name_label,
                line=dict(color=base_color, width=line_width),
                marker=dict(size=marker_size, color=base_color, line=marker_line),
                opacity=opacity,
                customdata=custom_data,
                hovertemplate=(
                    "<b>Date: %{customdata[0]}</b><br>"
                    "SPX Spot: %{customdata[1]:.2f}<br>"
                    "Centre Strike: %{customdata[2]:.0f} (Offset: %{customdata[3]:+.0f})<br>"
                    "Wings: %{customdata[4]:.0f} / %{customdata[5]:.0f}<br>"
                    "Leg Premiums: %{customdata[6]:.2f} / %{customdata[7]:.2f} / %{customdata[8]:.2f}<br>"
                    "<b>Net Fly Premium: %{customdata[9]:.4f} SPX pts</b><br>"
                    "Target Maturity: %{customdata[10]:.0f} DTE<extra></extra>"
                ),
            )
        )

    return apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>OTM {side_label} Butterfly Premium — Historical Comparison</b> ({title_suffix})",
            font=dict(size=13, color="#f0f6fc"),
        ),
        xaxis=dict(
            **BASE_AXIS_STYLE,
            title=x_title,
            dtick=100 if alignment_mode == "relative" else None,
        ),
        yaxis=dict(**BASE_AXIS_STYLE, title=y_title),
        hovermode="closest",
        height=420,
    )


# ---------------------------------------------------------------------------
# Chart 4: Observed Historical Fly Premium Differences
# ---------------------------------------------------------------------------

def create_observed_fly_change_chart(
    fly_diffs: list[ObservedFlyDifference],
    option_side: Literal["call", "put"],
    reference_date: str,
    focus_date: str,
    display_mode: Literal["absolute", "percentage", "normalized"] = "absolute",
) -> go.Figure:
    """Plot observed changes in rolling ATM-relative butterfly premiums."""
    fig = go.Figure()

    side_label = option_side.upper()
    filtered = [d for d in fly_diffs if d.option_side == option_side]
    filtered.sort(key=lambda d: d.atm_offset)

    if not filtered:
        return apply_theme_layout(fig, title=dict(text=f"{side_label} Fly Premium Change vs ATM Offset (No Matched Offsets)"))

    offsets = [d.atm_offset for d in filtered]

    if display_mode == "percentage":
        y_vals = [d.pct_change if d.pct_change is not None else 0.0 for d in filtered]
        y_title = "Percentage Change in Quoted Fly (%)"
    elif display_mode == "normalized":
        y_vals = [d.normalized_change for d in filtered]
        y_title = "Normalized Change (pts / Wing Width h)"
    else:
        y_vals = [d.abs_change for d in filtered]
        y_title = "Observed Fly Change (SPX Points)"

    bar_colors = ["#3fb950" if y >= 0 else "#f85149" for y in y_vals]

    custom_data = [
        [d.atm_offset, d.ref_centre, d.focus_centre, d.ref_premium, d.focus_premium, d.abs_change, d.pct_change]
        for d in filtered
    ]

    fig.add_trace(
        go.Bar(
            x=offsets,
            y=y_vals,
            marker_color=bar_colors,
            customdata=custom_data,
            name=f"{side_label} Fly Change",
            hovertemplate=(
                "<b>ATM Offset: %{customdata[0]:+.0f} pts</b><br>"
                "Ref Centre: %{customdata[1]:.0f} (Prem: %{customdata[3]:.4f})<br>"
                "Focus Centre: %{customdata[2]:.0f} (Prem: %{customdata[4]:.4f})<br>"
                "<b>Observed Net Change: %{customdata[5]:+.4f} pts</b><extra></extra>"
            ),
        )
    )

    fig.add_hline(y=0, line_width=1.0, line_color="#8b949e")

    return apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>{side_label} Fly Premium Change vs ATM Offset</b> ({focus_date} minus {reference_date})",
            font=dict(size=13, color="#f0f6fc"),
        ),
        xaxis=dict(
            **BASE_AXIS_STYLE,
            title=f"{side_label} Fly Centre Offset from ATM (SPX Points)",
            dtick=100,
        ),
        yaxis=dict(**BASE_AXIS_STYLE, title=y_title),
        hovermode="closest",
        height=360,
    )


# ---------------------------------------------------------------------------
# Chart 5: Modelled Fixed-Reference Fly Factor Attribution
# ---------------------------------------------------------------------------

def create_modelled_fly_attribution_chart(
    attributions: list[FixedFlyAttribution],
    option_side: Literal["call", "put"],
    reference_date: str,
    focus_date: str,
) -> go.Figure:
    """Plot exact sequential IV factor attribution for fixed-reference butterflies."""
    fig = go.Figure()

    side_label = option_side.upper()
    filtered = [a for a in attributions if a.option_side == option_side]
    filtered.sort(key=lambda a: a.atm_offset)

    if not filtered:
        return apply_theme_layout(fig, title=dict(text=f"Fixed-Strike {side_label} Fly Factor Attribution (No Active Flies)"))

    offsets = [a.atm_offset for a in filtered]
    centres = [a.ref_centre_strike for a in filtered]

    lvl_effects = [a.level_effect for a in filtered]
    skw_effects = [a.skew_effect for a in filtered]
    crv_effects = [a.curvature_effect for a in filtered]
    res_effects = [a.residual_effect for a in filtered]
    tot_changes = [a.total_iv_change for a in filtered]
    f0_prems = [a.f0 for a in filtered]

    custom_arr = np.column_stack([
        offsets, centres, f0_prems, lvl_effects, skw_effects, crv_effects, res_effects, tot_changes
    ])

    hover_fmt = (
        "<b>Fly Centre: %{customdata[1]:.0f} (Offset: %{customdata[0]:+.0f})</b><br>"
        "Original Ref Premium (F0): %{customdata[2]:.4f} pts<br>"
        "<b>Total Modelled Change: %{customdata[7]:+.4f} pts</b><br>"
        "├ Level Effect: %{customdata[3]:+.4f} pts<br>"
        "├ Skew Effect: %{customdata[4]:+.4f} pts<br>"
        "├ Curvature Effect: %{customdata[5]:+.4f} pts<br>"
        "└ Local Residual Effect: %{customdata[6]:+.4f} pts<extra></extra>"
    )

    # 1. Level Effect (Blue)
    fig.add_trace(
        go.Bar(
            x=offsets,
            y=lvl_effects,
            name="Level Effect (FL − F0)",
            marker_color=FACTOR_COLORS["level"],
            customdata=custom_arr,
            hovertemplate=hover_fmt,
        )
    )

    # 2. Skew Effect (Purple)
    fig.add_trace(
        go.Bar(
            x=offsets,
            y=skw_effects,
            name="Skew Effect (FLS − FL)",
            marker_color=FACTOR_COLORS["skew"],
            customdata=custom_arr,
            hovertemplate=hover_fmt,
        )
    )

    # 3. Curvature Effect (Orange)
    fig.add_trace(
        go.Bar(
            x=offsets,
            y=crv_effects,
            name="Curvature Effect (FLSC − FLS)",
            marker_color=FACTOR_COLORS["curvature"],
            customdata=custom_arr,
            hovertemplate=hover_fmt,
        )
    )

    # 4. Local Residual Effect (Magenta/Red)
    fig.add_trace(
        go.Bar(
            x=offsets,
            y=res_effects,
            name="Local Residual Effect (FFull − FLSC)",
            marker_color=FACTOR_COLORS["residual"],
            customdata=custom_arr,
            hovertemplate=hover_fmt,
        )
    )

    # 5. Net Total Line (White/Yellow Line with Markers)
    fig.add_trace(
        go.Scatter(
            x=offsets,
            y=tot_changes,
            mode="lines+markers",
            name="Net Modelled IV Change (FFull − F0)",
            line=dict(color="#f0f6fc", width=2.4),
            marker=dict(size=7, color="#e3b341", line=dict(color="#0d1117", width=1.5)),
            customdata=custom_arr,
            hovertemplate=hover_fmt,
        )
    )

    fig.add_hline(y=0, line_width=1.0, line_color="#8b949e")

    return apply_theme_layout(
        fig,
        barmode="relative",  # Stacked supporting both positive and negative values
        title=dict(
            text=f"<b>Fixed-Strike {side_label} Fly Factor Attribution</b> (Freeze {reference_date} Conditions, Shocks to {focus_date})",
            font=dict(size=13, color="#f0f6fc"),
        ),
        xaxis=dict(**BASE_AXIS_STYLE, title=f"{side_label} Fly Centre Offset from ATM (SPX Points)"),
        yaxis=dict(**BASE_AXIS_STYLE, title="Sequential Factor Premium Contribution (SPX Points)"),
        hovermode="x unified",
        height=400,
    )


# ---------------------------------------------------------------------------
# Chart 6: Historical Factor Trends Through Time
# ---------------------------------------------------------------------------

def create_historical_factor_trends_chart(
    factor_table_df: pd.DataFrame,
) -> go.Figure:
    """Plot 3 subplots: ATM IV Level, Skew, and Curvature across chronological dates."""
    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=(
            "<b>1. ATM IV Level (%)</b>",
            "<b>2. Smile Skew (pts)</b>",
            "<b>3. Smile Curvature (pts)</b>",
        ),
        shared_xaxes=True,
    )

    if factor_table_df.empty:
        return apply_theme_layout(fig, title=dict(text="Historical Factor Trends (No Data)"))

    df = factor_table_df.sort_values("Date")
    dates = df["Date"].tolist()
    levels = df["ATM IV (%)"].tolist()
    skews = df["Skew (pts)"].tolist()
    curvs = df["Curvature (pts)"].tolist()

    # Subplot 1: Level
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=levels,
            mode="lines+markers",
            name="ATM IV Level",
            line=dict(color=FACTOR_COLORS["level"], width=2.2),
            marker=dict(size=6, color=FACTOR_COLORS["level"]),
            hovertemplate="Date: %{x}<br>ATM IV: %{y:.3f}%<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # Subplot 2: Skew
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=skews,
            mode="lines+markers",
            name="Skew",
            line=dict(color=FACTOR_COLORS["skew"], width=2.2),
            marker=dict(size=6, color=FACTOR_COLORS["skew"]),
            hovertemplate="Date: %{x}<br>Skew: %{y:+.3f} pts<extra></extra>",
        ),
        row=1,
        col=2,
    )

    # Subplot 3: Curvature
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=curvs,
            mode="lines+markers",
            name="Curvature",
            line=dict(color=FACTOR_COLORS["curvature"], width=2.2),
            marker=dict(size=6, color=FACTOR_COLORS["curvature"]),
            hovertemplate="Date: %{x}<br>Curvature: %{y:+.3f} pts<extra></extra>",
        ),
        row=1,
        col=3,
    )

    apply_theme_layout(
        fig,
        showlegend=False,
        height=300,
        margin=dict(l=45, r=25, t=55, b=40),
    )

    # Update axis styles across subplots
    for c in [1, 2, 3]:
        fig.update_xaxes(gridcolor="#21262d", linecolor="#30363d", tickangle=-35, row=1, col=c)
        fig.update_yaxes(gridcolor="#21262d", linecolor="#30363d", row=1, col=c)

    return fig


# ---------------------------------------------------------------------------
# Chart 7: Single Fly Contract Factor Inspection
# ---------------------------------------------------------------------------

def create_single_fly_inspection_chart(
    attribution: FixedFlyAttribution,
) -> go.Figure:
    """Plot a waterfall or step chart showing the repriced stages of a chosen butterfly spread."""
    fig = go.Figure()

    stages = [
        "F0: Baseline",
        "+ Level",
        "+ Skew",
        "+ Curvature",
        "FFull: Modelled",
    ]

    measures = ["absolute", "relative", "relative", "relative", "total"]

    y_vals = [
        attribution.f0,
        attribution.level_effect,
        attribution.skew_effect,
        attribution.curvature_effect,
        attribution.f_full,
    ]

    fig.add_trace(
        go.Waterfall(
            name="Repricing Stages",
            orientation="v",
            measure=measures,
            x=stages,
            textposition="outside",
            text=[f"{v:+.4f}" if m == "relative" else f"{v:.4f}" for m, v in zip(measures, y_vals)],
            y=y_vals,
            connector={"line": {"color": "#8b949e", "dash": "dot"}},
            decreasing={"marker": {"color": "#f85149"}},
            increasing={"marker": {"color": "#3fb950"}},
            totals={"marker": {"color": "#58a6ff"}},
        )
    )

    op = attribution.option_side.upper()
    centre = attribution.ref_centre_strike
    wings = f"{attribution.lower_strike:.0f} / {attribution.upper_strike:.0f}"

    return apply_theme_layout(
        fig,
        title=dict(
            text=f"<b>Sequential Repricing Waterfall: {op} @ {centre:.0f} (Wings: {wings})</b>",
            font=dict(size=12, color="#f0f6fc"),
        ),
        xaxis=dict(**BASE_AXIS_STYLE),
        yaxis=dict(**BASE_AXIS_STYLE, title="Fly Premium (SPX Points)"),
        height=320,
    )


# ---------------------------------------------------------------------------
# Chart 7: Multi-Date Higher-Order Structure Curves (Skew, RR, Curvature, Kurtosis)
# ---------------------------------------------------------------------------

def create_multidate_structure_chart(
    snapshots: dict[str, pd.DataFrame],
    selected_dates: list[str],
    metric_category: Literal["call_put_skew", "skew_rr", "curvature_kurtosis", "fly_call_put_skew", "fly_skew_rr", "fly_curvature_kurtosis", "all_stacked"],
    reference_date: str,
    focus_date: str,
    highlight_focus: bool = True,
    line_thickness: float = 2.6,
    flies_by_date: dict[str, dict[str, list[Any]]] | None = None,
) -> go.Figure:
    """Plot multi-date smile structure curves: Call/Put Skew, Risk Reversal, Curvature, and Kurtosis."""
    sorted_dates = sorted([d for d in selected_dates if d in snapshots])
    if not sorted_dates:
        fig = go.Figure()
        return apply_theme_layout(fig, title=dict(text="Structure Metrics (No Dates Available)"))

    color_map = get_date_color_map(sorted_dates)

    # Compute structure metrics for all selected dates
    metrics_by_date: dict[str, dict[str, Any]] = {}
    for d in sorted_dates:
        s_df = extract_smile_points(snapshots[d])
        metrics_by_date[d] = compute_smile_structure_metrics(s_df)

    # Compute fly structure metrics for dates if requested
    fly_metrics_by_date: dict[str, dict[str, Any]] = {}
    if flies_by_date:
        for d in sorted_dates:
            if d in flies_by_date:
                raw_flies = flies_by_date[d]
                f_list = []
                if isinstance(raw_flies, dict):
                    for side in ["call", "put"]:
                        for f in raw_flies.get(side, []):
                            prem = getattr(f, "fly_premium", None)
                            if prem is None:
                                prem = getattr(f, "initial_fly_premium", 0.0)
                            f_list.append({
                                "centre_strike": f.centre_strike,
                                "atm_offset": round(f.centre_strike - f.atm_strike, 1),
                                "option_side": f.option_side,
                                "initial_fly_premium": prem,
                            })
                elif isinstance(raw_flies, list):
                    for f in raw_flies:
                        prem = getattr(f, "fly_premium", None)
                        if prem is None:
                            prem = getattr(f, "initial_fly_premium", 0.0)
                        f_list.append({
                            "centre_strike": f.centre_strike,
                            "atm_offset": round(f.centre_strike - f.atm_strike, 1),
                            "option_side": f.option_side,
                            "initial_fly_premium": prem,
                        })
                if f_list:
                    f_df = pd.DataFrame(f_list)
                    fly_metrics_by_date[d] = compute_fly_structure_metrics(f_df)

    if metric_category == "fly_call_put_skew":
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.14,
            subplot_titles=(
                "<b>Call Fly Skew:</b> $F_{Call}(ATM + h) - F(ATM)$ Across Historical Dates ($/contract)",
                "<b>Put Fly Skew:</b> $F_{Put}(ATM - h) - F(ATM)$ Across Historical Dates ($/contract)",
            ),
            row_heights=[0.5, 0.5],
        )

        for d in sorted_dates:
            if d not in fly_metrics_by_date:
                continue
            m = fly_metrics_by_date[d]
            t = m["table"]
            is_focus = (d == focus_date)
            is_ref = (d == reference_date)
            col = color_map[d]
            w = max(3.8, line_thickness * 1.5) if is_focus else max(3.0, line_thickness * 1.2) if is_ref else line_thickness
            op = 1.0 if is_focus else 0.95 if is_ref else 0.82
            sym = "diamond" if is_focus else "square" if is_ref else "circle"
            sz = 8 if is_focus else 7 if is_ref else 5.5
            name_lbl = f"<b>{d}</b> (Focus)" if is_focus else f"{d} (Ref)" if is_ref else f"{d}"

            # Row 1: Call Fly Skew
            fig.add_trace(
                go.Scatter(
                    x=t["offset"],
                    y=t["call_skew"],
                    mode="lines+markers",
                    name=name_lbl,
                    line=dict(color=col, width=w),
                    marker=dict(size=sz, symbol=sym, color=col),
                    opacity=op,
                    hovertemplate=f"<b>{d} Call Fly Skew</b><br>Offset: +%{{x:.0f}} pts<br>Call Fly Skew: <b>$%{{y:+.2f}}</b><extra></extra>",
                ),
                row=1,
                col=1,
            )

            # Row 2: Put Fly Skew
            fig.add_trace(
                go.Scatter(
                    x=t["offset"],
                    y=t["put_skew"],
                    mode="lines+markers",
                    name=name_lbl,
                    showlegend=False,
                    line=dict(color=col, width=w),
                    marker=dict(size=sz, symbol=sym, color=col),
                    opacity=op,
                    hovertemplate=f"<b>{d} Put Fly Skew</b><br>Offset: -%{{x:.0f}} pts<br>Put Fly Skew: <b>$%{{y:+.2f}}</b><extra></extra>",
                ),
                row=2,
                col=1,
            )

        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=1, col=1)
        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=2, col=1)

        fig = apply_theme_layout(
            fig,
            title=dict(
                text=f"<b>Call Fly Skew &amp; Put Fly Skew Relative to ATM ($/contract):</b> {len(sorted_dates)} Dates (Ref: {reference_date} | Focus: {focus_date})",
                font=dict(size=14, color="#f0f6fc"),
            ),
            height=660,
            hovermode="x unified",
        )
        fig.update_xaxes(title_text="Moneyness Distance to ATM: h (SPX pts)", row=2, col=1, dtick=100)
        fig.update_xaxes(row=1, col=1, dtick=100)
        fig.update_yaxes(title_text="Call Fly Skew ($)", row=1, col=1)
        fig.update_yaxes(title_text="Put Fly Skew ($)", row=2, col=1)
        return fig

    elif metric_category == "call_put_skew":
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.14,
            subplot_titles=(
                "<b>Call Skew:</b> $IV(ATM + h) - IV(ATM)$ Across Historical Dates (vol pts)",
                "<b>Put Skew:</b> $IV(ATM - h) - IV(ATM)$ Across Historical Dates (vol pts)",
            ),
            row_heights=[0.5, 0.5],
        )

        for d in sorted_dates:
            m = metrics_by_date[d]
            t = m["table"]
            is_focus = (d == focus_date)
            is_ref = (d == reference_date)
            col = color_map[d]
            w = max(3.8, line_thickness * 1.5) if is_focus else max(3.0, line_thickness * 1.2) if is_ref else line_thickness
            op = 1.0 if is_focus else 0.95 if is_ref else 0.82
            sym = "diamond" if is_focus else "square" if is_ref else "circle"
            sz = 8 if is_focus else 7 if is_ref else 5.5
            name_lbl = f"<b>{d}</b> (Focus)" if is_focus else f"{d} (Ref)" if is_ref else f"{d}"

            # Row 1: Call Skew
            fig.add_trace(
                go.Scatter(
                    x=t["offset"],
                    y=t["call_skew"],
                    mode="lines+markers",
                    name=name_lbl,
                    line=dict(color=col, width=w),
                    marker=dict(size=sz, symbol=sym, color=col),
                    opacity=op,
                    hovertemplate=f"<b>{d} Call Skew</b><br>Offset: +%{{x:.0f}} pts<br>Call Skew: <b>%{{y:+.3f}} pts</b><extra></extra>",
                ),
                row=1,
                col=1,
            )

            # Row 2: Put Skew
            fig.add_trace(
                go.Scatter(
                    x=t["offset"],
                    y=t["put_skew"],
                    mode="lines+markers",
                    name=name_lbl,
                    showlegend=False,
                    line=dict(color=col, width=w),
                    marker=dict(size=sz, symbol=sym, color=col),
                    opacity=op,
                    hovertemplate=f"<b>{d} Put Skew</b><br>Offset: -%{{x:.0f}} pts<br>Put Skew: <b>%{{y:+.3f}} pts</b><extra></extra>",
                ),
                row=2,
                col=1,
            )

        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=1, col=1)
        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=2, col=1)

        fig = apply_theme_layout(
            fig,
            title=dict(
                text=f"<b>Call Skew &amp; Put Skew Relative to ATM:</b> {len(sorted_dates)} Dates (Ref: {reference_date} | Focus: {focus_date})",
                font=dict(size=14, color="#f0f6fc"),
            ),
            height=660,
            hovermode="x unified",
        )
        fig.update_xaxes(title_text="Moneyness Distance to ATM: h (SPX pts)", row=2, col=1, dtick=100)
        fig.update_xaxes(row=1, col=1, dtick=100)
        fig.update_yaxes(title_text="Call Skew (vol pts)", row=1, col=1)
        fig.update_yaxes(title_text="Put Skew (vol pts)", row=2, col=1)
        return fig

    elif metric_category == "skew_rr":
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.14,
            subplot_titles=(
                "<b>Skew / Risk Reversal ($IV_{Call} - IV_{Put}$):</b> Asymmetry Level (vol pts)",
                f"<b>Shift vs Reference ({reference_date}):</b> $\\Delta RR = RR_{{Date}} - RR_{{Ref}}$ (vol pts)",
            ),
            row_heights=[0.58, 0.42],
        )

        ref_rr_map = {}
        if reference_date in metrics_by_date:
            ref_t = metrics_by_date[reference_date]["table"]
            ref_rr_map = dict(zip(ref_t["offset"], ref_t["risk_reversal"]))

        for d in sorted_dates:
            m = metrics_by_date[d]
            t = m["table"]
            is_focus = (d == focus_date)
            is_ref = (d == reference_date)
            col = color_map[d]
            w = max(3.8, line_thickness * 1.5) if is_focus else max(3.0, line_thickness * 1.2) if is_ref else line_thickness
            op = 1.0 if is_focus else 0.95 if is_ref else 0.82
            sym = "diamond" if is_focus else "square" if is_ref else "circle"
            sz = 8 if is_focus else 7 if is_ref else 5.5
            name_lbl = f"<b>{d}</b> (Focus)" if is_focus else f"{d} (Ref)" if is_ref else f"{d}"

            # Row 1: Risk Reversal
            fig.add_trace(
                go.Scatter(
                    x=t["offset"],
                    y=t["risk_reversal"],
                    mode="lines+markers",
                    name=name_lbl,
                    line=dict(color=col, width=w),
                    marker=dict(size=sz, symbol=sym, color=col),
                    opacity=op,
                    hovertemplate=f"<b>{d} Risk Reversal</b><br>Offset: ±%{{x:.0f}} pts<br>RR: <b>%{{y:+.3f}} pts</b><extra></extra>",
                ),
                row=1,
                col=1,
            )

            # Row 2: Shift vs Reference
            if ref_rr_map and not is_ref:
                d_rr = [
                    (curr - ref_rr_map[off]) if (curr is not None and off in ref_rr_map and ref_rr_map[off] is not None) else None
                    for off, curr in zip(t["offset"], t["risk_reversal"])
                ]
                fig.add_trace(
                    go.Scatter(
                        x=t["offset"],
                        y=d_rr,
                        mode="lines+markers",
                        name=f"Δ RR vs Ref ({d})",
                        showlegend=False,
                        line=dict(color=col, width=w, dash="dash" if not is_focus else "solid"),
                        marker=dict(size=sz, symbol=sym, color=col),
                        opacity=op,
                        hovertemplate=f"<b>{d} Δ RR vs Ref</b><br>Offset: ±%{{x:.0f}} pts<br>Δ RR: <b>%{{y:+.3f}} pts</b><extra></extra>",
                    ),
                    row=2,
                    col=1,
                )

        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=1, col=1)
        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=2, col=1)

        fig = apply_theme_layout(
            fig,
            title=dict(
                text=f"<b>Historical Skew / Risk Reversal Dynamics:</b> {len(sorted_dates)} Dates (Ref: {reference_date} | Focus: {focus_date})",
                font=dict(size=14, color="#f0f6fc"),
            ),
            height=660,
            hovermode="x unified",
        )
        fig.update_xaxes(title_text="Moneyness Distance to ATM: h (SPX pts)", row=2, col=1, dtick=100)
        fig.update_xaxes(row=1, col=1, dtick=100)
        fig.update_yaxes(title_text="Risk Reversal (vol pts)", row=1, col=1)
        fig.update_yaxes(title_text="Δ RR vs Ref (vol pts)", row=2, col=1)
        return fig

    elif metric_category == "curvature_kurtosis":
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.14,
            subplot_titles=(
                "<b>Smile Curvature [$\\frac{IV_{Put} + IV_{Call}}{2} - IV_{ATM}$]:</b> Local Convexity (vol pts)",
                "<b>Kurtosis Fat-Tail Ratio:</b> $\\frac{Curvature(h)}{(h/100)^2 \\cdot Curvature(100)}$ vs Quadratic Baseline (1.0)",
            ),
            row_heights=[0.55, 0.45],
        )

        for d in sorted_dates:
            m = metrics_by_date[d]
            t = m["table"]
            is_focus = (d == focus_date)
            is_ref = (d == reference_date)
            col = color_map[d]
            w = max(3.8, line_thickness * 1.5) if is_focus else max(3.0, line_thickness * 1.2) if is_ref else line_thickness
            op = 1.0 if is_focus else 0.95 if is_ref else 0.82
            sym = "diamond" if is_focus else "square" if is_ref else "circle"
            sz = 8 if is_focus else 7 if is_ref else 5.5
            name_lbl = f"<b>{d}</b> (Focus)" if is_focus else f"{d} (Ref)" if is_ref else f"{d}"

            # Row 1: Curvature
            fig.add_trace(
                go.Scatter(
                    x=t["offset"],
                    y=t["curvature"],
                    mode="lines+markers",
                    name=name_lbl,
                    line=dict(color=col, width=w),
                    marker=dict(size=sz, symbol=sym, color=col),
                    opacity=op,
                    hovertemplate=f"<b>{d} Curvature</b><br>Offset: ±%{{x:.0f}} pts<br>Curvature: <b>%{{y:+.3f}} pts</b><extra></extra>",
                ),
                row=1,
                col=1,
            )

            # Row 2: Kurtosis Ratio
            fig.add_trace(
                go.Scatter(
                    x=t["offset"],
                    y=t["kurtosis_ratio"],
                    mode="lines+markers",
                    name=name_lbl,
                    showlegend=False,
                    line=dict(color=col, width=w),
                    marker=dict(size=sz, symbol=sym, color=col),
                    opacity=op,
                    hovertemplate=f"<b>{d} Kurtosis Ratio</b><br>Offset: ±%{{x:.0f}} pts<br>Ratio: <b>%{{y:.3f}}x</b><extra></extra>",
                ),
                row=2,
                col=1,
            )

        # Baseline 1.0 in Row 2
        fig.add_hline(
            y=1.0,
            line=dict(color="#8b949e", width=1.5, dash="dash"),
            annotation=dict(text="Pure Quadratic Baseline (1.00)", font=dict(color="#8b949e", size=10), xref="paper", x=0.02),
            row=2,
            col=1,
        )
        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=1, col=1)

        fig = apply_theme_layout(
            fig,
            title=dict(
                text=f"<b>Historical Smile Curvature &amp; Kurtosis Fat-Tail Dynamics:</b> {len(sorted_dates)} Dates",
                font=dict(size=14, color="#f0f6fc"),
            ),
            height=660,
            hovermode="x unified",
        )
        fig.update_xaxes(title_text="Moneyness Distance to ATM: h (SPX pts)", row=2, col=1, dtick=100)
        fig.update_xaxes(row=1, col=1, dtick=100)
        fig.update_yaxes(title_text="Curvature (vol pts)", row=1, col=1)
        fig.update_yaxes(title_text="Kurtosis Ratio", row=2, col=1)
        return fig

    elif metric_category == "fly_skew_rr":
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.14,
            subplot_titles=(
                "<b>Fly Risk Reversal ($F_{Call} - F_{Put}$):</b> Butterfly Premium Asymmetry ($/fly)",
                f"<b>Δ Fly RR Shift vs Reference ({reference_date}):</b> Daily Shift in Butterfly Skew ($/fly)",
            ),
            row_heights=[0.55, 0.45],
        )

        ref_fly_rr_map = {}
        if reference_date in fly_metrics_by_date:
            ref_t = fly_metrics_by_date[reference_date]["table"]
            ref_fly_rr_map = dict(zip(ref_t["offset"], ref_t["risk_reversal"]))

        for d in sorted_dates:
            if d not in fly_metrics_by_date:
                continue
            m = fly_metrics_by_date[d]
            t = m["table"]
            is_focus = (d == focus_date)
            is_ref = (d == reference_date)
            col = color_map[d]
            w = max(3.8, line_thickness * 1.5) if is_focus else max(3.0, line_thickness * 1.2) if is_ref else line_thickness
            op = 1.0 if is_focus else 0.95 if is_ref else 0.82
            sym = "diamond" if is_focus else "square" if is_ref else "circle"
            sz = 8 if is_focus else 7 if is_ref else 5.5
            name_lbl = f"<b>{d}</b> (Focus)" if is_focus else f"{d} (Ref)" if is_ref else f"{d}"

            # Row 1: Fly Risk Reversal
            fig.add_trace(
                go.Scatter(
                    x=t["offset"],
                    y=t["risk_reversal"],
                    mode="lines+markers",
                    name=name_lbl,
                    line=dict(color=col, width=w),
                    marker=dict(size=sz, symbol=sym, color=col),
                    opacity=op,
                    hovertemplate=f"<b>{d} Fly RR</b><br>Offset: ±%{{x:.0f}} pts<br>Fly RR: <b>$%{{y:+.2f}}</b><extra></extra>",
                ),
                row=1,
                col=1,
            )

            # Row 2: Shift vs Reference
            if ref_fly_rr_map and not is_ref:
                d_fly_rr = [
                    (curr - ref_fly_rr_map[off]) if (curr is not None and off in ref_fly_rr_map and ref_fly_rr_map[off] is not None) else None
                    for off, curr in zip(t["offset"], t["risk_reversal"])
                ]
                fig.add_trace(
                    go.Scatter(
                        x=t["offset"],
                        y=d_fly_rr,
                        mode="lines+markers",
                        name=f"Δ Fly RR vs Ref ({d})",
                        showlegend=False,
                        line=dict(color=col, width=w, dash="dash" if not is_focus else "solid"),
                        marker=dict(size=sz, symbol=sym, color=col),
                        opacity=op,
                        hovertemplate=f"<b>{d} Δ Fly RR vs Ref</b><br>Offset: ±%{{x:.0f}} pts<br>Δ Fly RR: <b>$%{{y:+.2f}}</b><extra></extra>",
                    ),
                    row=2,
                    col=1,
                )

        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=1, col=1)
        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=2, col=1)

        fig = apply_theme_layout(
            fig,
            title=dict(
                text=f"<b>Historical Butterfly Risk Reversal Dynamics ($/fly):</b> {len(sorted_dates)} Dates (Ref: {reference_date} | Focus: {focus_date})",
                font=dict(size=14, color="#f0f6fc"),
            ),
            height=660,
            hovermode="x unified",
        )
        fig.update_xaxes(title_text="Moneyness Distance to ATM: h (SPX pts)", row=2, col=1, dtick=100)
        fig.update_xaxes(row=1, col=1, dtick=100)
        fig.update_yaxes(title_text="Fly Risk Reversal ($)", row=1, col=1)
        fig.update_yaxes(title_text="Δ Fly RR vs Ref ($)", row=2, col=1)
        return fig

    elif metric_category == "fly_curvature_kurtosis":
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.14,
            subplot_titles=(
                "<b>Fly Premium Curvature [$\\frac{F_P + F_C}{2} - F_{ATM}$]:</b> Smile Convexity Drop ($/fly)",
                "<b>Kurtosis Butterfly Spread [Outer $2h$ vs Inner $h$ Fly]:</b> Fat-Tail Spread ($/contract)",
            ),
            row_heights=[0.55, 0.45],
        )

        for d in sorted_dates:
            if d not in fly_metrics_by_date:
                continue
            m = fly_metrics_by_date[d]
            t = m["table"]
            is_focus = (d == focus_date)
            is_ref = (d == reference_date)
            col = color_map[d]
            w = max(3.8, line_thickness * 1.5) if is_focus else max(3.0, line_thickness * 1.2) if is_ref else line_thickness
            op = 1.0 if is_focus else 0.95 if is_ref else 0.82
            sym = "diamond" if is_focus else "square" if is_ref else "circle"
            sz = 8 if is_focus else 7 if is_ref else 5.5
            name_lbl = f"<b>{d}</b> (Focus)" if is_focus else f"{d} (Ref)" if is_ref else f"{d}"

            # Row 1: Curvature
            fig.add_trace(
                go.Scatter(
                    x=t["offset"],
                    y=t["curvature"],
                    mode="lines+markers",
                    name=name_lbl,
                    line=dict(color=col, width=w),
                    marker=dict(size=sz, symbol=sym, color=col),
                    opacity=op,
                    hovertemplate=f"<b>{d} Fly Curvature</b><br>Offset: ±%{{x:.0f}} pts<br>Curv: <b>$%{{y:+.2f}}</b><extra></extra>",
                ),
                row=1,
                col=1,
            )

            # Row 2: Kurtosis Butterfly Spread
            t_valid = t.dropna(subset=["kurtosis_spread"])
            if not t_valid.empty:
                fig.add_trace(
                    go.Scatter(
                        x=t_valid["offset"],
                        y=t_valid["kurtosis_spread"],
                        mode="lines+markers",
                        name=f"Kurtosis Spread ({d})",
                        showlegend=False,
                        line=dict(color=col, width=w),
                        marker=dict(size=sz, symbol=sym, color=col),
                        opacity=op,
                        hovertemplate=f"<b>{d} Kurtosis Spread</b><br>Inner: ±%{{x:.0f}} pts<br>Spread: <b>$%{{y:+.2f}}</b><extra></extra>",
                    ),
                    row=2,
                    col=1,
                )

        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=1, col=1)
        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=2, col=1)

        fig = apply_theme_layout(
            fig,
            title=dict(
                text=f"<b>Historical Butterfly Curvature &amp; Kurtosis Spread:</b> {len(sorted_dates)} Dates",
                font=dict(size=14, color="#f0f6fc"),
            ),
            height=660,
            hovermode="x unified",
        )
        fig.update_xaxes(title_text="Moneyness Distance to ATM: h (SPX pts)", row=2, col=1, dtick=100)
        fig.update_xaxes(row=1, col=1, dtick=100)
        fig.update_yaxes(title_text="Fly Curvature ($)", row=1, col=1)
        fig.update_yaxes(title_text="Kurtosis Spread ($)", row=2, col=1)
        return fig

    else:
        # Stacked All (3 rows: Risk Reversal, Curvature, Kurtosis)
        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.10,
            subplot_titles=(
                "<b>1. Skew / Risk Reversal ($IV_{Call} - IV_{Put}$):</b> Wing Asymmetry (vol pts)",
                "<b>2. Smile Curvature:</b> Convexity Bend (vol pts)",
                "<b>3. Kurtosis Fat-Tail Ratio:</b> Scaling Relative to Quadratic Baseline (1.0)",
            ),
            row_heights=[0.34, 0.33, 0.33],
        )

        for d in sorted_dates:
            m = metrics_by_date[d]
            t = m["table"]
            is_focus = (d == focus_date)
            is_ref = (d == reference_date)
            col = color_map[d]
            w = max(3.8, line_thickness * 1.5) if is_focus else max(3.0, line_thickness * 1.2) if is_ref else line_thickness
            op = 1.0 if is_focus else 0.95 if is_ref else 0.82
            sym = "diamond" if is_focus else "square" if is_ref else "circle"
            sz = 8 if is_focus else 7 if is_ref else 5.5
            name_lbl = f"<b>{d}</b> (Focus)" if is_focus else f"{d} (Ref)" if is_ref else f"{d}"

            # Row 1: RR
            fig.add_trace(
                go.Scatter(
                    x=t["offset"],
                    y=t["risk_reversal"],
                    mode="lines+markers",
                    name=name_lbl,
                    line=dict(color=col, width=w),
                    marker=dict(size=sz, symbol=sym, color=col),
                    opacity=op,
                    hovertemplate=f"<b>{d} RR</b>: %{{y:+.3f}} pts<extra></extra>",
                ),
                row=1,
                col=1,
            )

            # Row 2: Curvature
            fig.add_trace(
                go.Scatter(
                    x=t["offset"],
                    y=t["curvature"],
                    mode="lines+markers",
                    name=name_lbl,
                    showlegend=False,
                    line=dict(color=col, width=w),
                    marker=dict(size=sz, symbol=sym, color=col),
                    opacity=op,
                    hovertemplate=f"<b>{d} Curv</b>: %{{y:+.3f}} pts<extra></extra>",
                ),
                row=2,
                col=1,
            )

            # Row 3: Kurtosis
            fig.add_trace(
                go.Scatter(
                    x=t["offset"],
                    y=t["kurtosis_ratio"],
                    mode="lines+markers",
                    name=name_lbl,
                    showlegend=False,
                    line=dict(color=col, width=w),
                    marker=dict(size=sz, symbol=sym, color=col),
                    opacity=op,
                    hovertemplate=f"<b>{d} Kurtosis</b>: %{{y:.3f}}x<extra></extra>",
                ),
                row=3,
                col=1,
            )

        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=1, col=1)
        fig.add_hline(y=0, line=dict(color="#484f58", width=1, dash="solid"), row=2, col=1)
        fig.add_hline(
            y=1.0,
            line=dict(color="#8b949e", width=1.5, dash="dash"),
            annotation=dict(text="Quadratic Baseline (1.00)", font=dict(color="#8b949e", size=9), xref="paper", x=0.02),
            row=3,
            col=1,
        )

        fig = apply_theme_layout(
            fig,
            title=dict(
                text=f"<b>Complete Higher-Order Volatility Structure Decomposition:</b> {len(sorted_dates)} Dates",
                font=dict(size=14, color="#f0f6fc"),
            ),
            height=780,
            hovermode="x unified",
        )
        fig.update_xaxes(title_text="Moneyness Distance to ATM: h (SPX pts)", row=3, col=1, dtick=100)
        fig.update_xaxes(row=1, col=1, dtick=100)
        fig.update_xaxes(row=2, col=1, dtick=100)
        fig.update_yaxes(title_text="Risk Reversal (vol pts)", row=1, col=1)
        fig.update_yaxes(title_text="Curvature (vol pts)", row=2, col=1)
        fig.update_yaxes(title_text="Kurtosis Ratio", row=3, col=1)
        return fig
