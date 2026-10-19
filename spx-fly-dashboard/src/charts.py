"""Interactive Plotly charts for the SPX Fixed-Strike Butterfly Dashboard.

Professional dark quantitative research styling.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from spx_butterfly.iv_scenarios import (
    IVShiftScenario,
    compute_normalized_strike,
    compute_strike_iv_shock,
)
from spx_butterfly.repricing import RepricedButterfly, reprice_butterfly

THEME_LAYOUT = dict(
    paper_bgcolor="#0e1117",
    plot_bgcolor="#161b22",
    font=dict(color="#c9d1d9", family="Inter, -apple-system, sans-serif", size=12),
    margin=dict(l=50, r=30, t=50, b=40),
    hoverlabel=dict(bgcolor="#1f242c", font_color="#f0f6fc", font_size=12, bordercolor="#30363d"),
    legend=dict(
        bgcolor="rgba(22, 27, 34, 0.8)",
        bordercolor="#30363d",
        borderwidth=1,
        font=dict(size=11, color="#8b949e"),
    ),
    xaxis=dict(
        gridcolor="#21262d",
        zerolinecolor="#30363d",
        showline=True,
        linecolor="#30363d",
        tickfont=dict(color="#8b949e"),
        title_font=dict(size=12, color="#c9d1d9"),
    ),
    yaxis=dict(
        gridcolor="#21262d",
        zerolinecolor="#30363d",
        showline=True,
        linecolor="#30363d",
        tickfont=dict(color="#8b949e"),
        title_font=dict(size=12, color="#c9d1d9"),
    ),
)


def create_smile_chart(
    snapshot_df: pd.DataFrame,
    scenario: IVShiftScenario | None = None,
    shift_vol_points: float = 0.0,
) -> go.Figure:
    """Plot original and shocked IV smile across fixed strikes with factor overlays."""
    fig = go.Figure()

    if scenario is None:
        scenario = IVShiftScenario(shift_vol_points=shift_vol_points)

    if snapshot_df.empty:
        fig.update_layout(**THEME_LAYOUT, title="Implied Volatility Smile (Fixed Strikes)")
        return fig

    atm_strike = float(snapshot_df["atm_strike"].iloc[0])
    s0 = float(snapshot_df["underlying"].iloc[0])
    h_width = float(scenario.reference_width)

    # Ensure scenario has valid ATM anchor
    scen_active = IVShiftScenario(
        level_vol_points=scenario.level_vol_points,
        skew_vol_points=scenario.skew_vol_points,
        curvature_vol_points=scenario.curvature_vol_points,
        reference_width=h_width,
        atm_strike=atm_strike,
    )

    call_df = snapshot_df[snapshot_df["option_side"] == "call"].sort_values("strike")
    put_df = snapshot_df[snapshot_df["option_side"] == "put"].sort_values("strike")

    is_shock_active = (
        abs(scen_active.level_vol_points) > 1e-4
        or abs(scen_active.skew_vol_points) > 1e-4
        or abs(scen_active.curvature_vol_points) > 1e-4
    )

    # 1. Calls
    if not call_df.empty:
        c_k = call_df["strike"].to_numpy(dtype=float)
        c_iv_orig = (call_df["iv_decimal"] * 100.0).to_numpy(dtype=float)
        c_tot_shock, c_comp = compute_strike_iv_shock(c_k, scen_active)
        c_shocked_iv = c_iv_orig + c_tot_shock

        # Baseline Call trace
        fig.add_trace(
            go.Scatter(
                x=c_k,
                y=c_iv_orig,
                mode="lines+markers",
                name="Baseline Call IV",
                line=dict(color="#58a6ff", width=2.2),
                marker=dict(size=6, symbol="circle"),
                hovertemplate="<b>Call Strike:</b> %{x:.0f}<br><b>Baseline IV:</b> %{y:.2f}%<extra></extra>",
            )
        )

        if is_shock_active:
            # Full Shocked Call trace
            hover_call_shock = [
                (
                    f"<b>Call Strike:</b> {k:.0f}<br>"
                    f"<b>Baseline IV:</b> {orig:.2f}%<br>"
                    f"• Level Effect: {lvl:+.2f} pts<br>"
                    f"• Skew Effect: {skw:+.2f} pts<br>"
                    f"• Curvature Effect: {crv:+.2f} pts<br>"
                    f"<b>Total Shock:</b> {tot:+.2f} pts<br>"
                    f"<b>Shocked IV:</b> {shocked:.2f}%"
                )
                for k, orig, lvl, skw, crv, tot, shocked in zip(
                    c_k,
                    c_iv_orig,
                    c_comp["level"] if isinstance(c_comp["level"], np.ndarray) else np.full_like(c_k, c_comp["level"]),
                    c_comp["skew"],
                    c_comp["curvature"],
                    c_tot_shock,
                    c_shocked_iv,
                )
            ]

            fig.add_trace(
                go.Scatter(
                    x=c_k,
                    y=c_shocked_iv,
                    mode="lines+markers",
                    name="Shocked Call IV (L+S+C)",
                    line=dict(color="#ff9b54", width=2.5, dash="dash"),
                    marker=dict(size=6, symbol="circle-open"),
                    hoverinfo="text",
                    hovertext=hover_call_shock,
                )
            )

            # Optional overlays (Level-only, Level+Skew)
            if abs(scen_active.skew_vol_points) > 1e-4 or abs(scen_active.curvature_vol_points) > 1e-4:
                lvl_only_c = c_iv_orig + scen_active.level_vol_points
                lvl_skw_c = lvl_only_c + c_comp["skew"]

                fig.add_trace(
                    go.Scatter(
                        x=c_k,
                        y=lvl_only_c,
                        mode="lines",
                        name="Call Overlay: Level Only",
                        line=dict(color="#e3b341", width=1.5, dash="dot"),
                        visible="legendonly",
                        hovertemplate="<b>Call Strike:</b> %{x:.0f}<br><b>Level-Only IV:</b> %{y:.2f}%<extra></extra>",
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=c_k,
                        y=lvl_skw_c,
                        mode="lines",
                        name="Call Overlay: Level + Skew",
                        line=dict(color="#bc8cff", width=1.5, dash="dashdot"),
                        visible="legendonly",
                        hovertemplate="<b>Call Strike:</b> %{x:.0f}<br><b>Level+Skew IV:</b> %{y:.2f}%<extra></extra>",
                    )
                )

    # 2. Puts
    if not put_df.empty:
        p_k = put_df["strike"].to_numpy(dtype=float)
        p_iv_orig = (put_df["iv_decimal"] * 100.0).to_numpy(dtype=float)
        p_tot_shock, p_comp = compute_strike_iv_shock(p_k, scen_active)
        p_shocked_iv = p_iv_orig + p_tot_shock

        # Baseline Put trace
        fig.add_trace(
            go.Scatter(
                x=p_k,
                y=p_iv_orig,
                mode="lines+markers",
                name="Baseline Put IV",
                line=dict(color="#bc8cff", width=2.2),
                marker=dict(size=6, symbol="diamond"),
                hovertemplate="<b>Put Strike:</b> %{x:.0f}<br><b>Baseline IV:</b> %{y:.2f}%<extra></extra>",
            )
        )

        if is_shock_active:
            hover_put_shock = [
                (
                    f"<b>Put Strike:</b> {k:.0f}<br>"
                    f"<b>Baseline IV:</b> {orig:.2f}%<br>"
                    f"• Level Effect: {lvl:+.2f} pts<br>"
                    f"• Skew Effect: {skw:+.2f} pts<br>"
                    f"• Curvature Effect: {crv:+.2f} pts<br>"
                    f"<b>Total Shock:</b> {tot:+.2f} pts<br>"
                    f"<b>Shocked IV:</b> {shocked:.2f}%"
                )
                for k, orig, lvl, skw, crv, tot, shocked in zip(
                    p_k,
                    p_iv_orig,
                    p_comp["level"] if isinstance(p_comp["level"], np.ndarray) else np.full_like(p_k, p_comp["level"]),
                    p_comp["skew"],
                    p_comp["curvature"],
                    p_tot_shock,
                    p_shocked_iv,
                )
            ]

            fig.add_trace(
                go.Scatter(
                    x=p_k,
                    y=p_shocked_iv,
                    mode="lines+markers",
                    name="Shocked Put IV (L+S+C)",
                    line=dict(color="#f0883e", width=2.5, dash="dash"),
                    marker=dict(size=6, symbol="diamond-open"),
                    hoverinfo="text",
                    hovertext=hover_put_shock,
                )
            )

            if abs(scen_active.skew_vol_points) > 1e-4 or abs(scen_active.curvature_vol_points) > 1e-4:
                lvl_only_p = p_iv_orig + scen_active.level_vol_points
                lvl_skw_p = lvl_only_p + p_comp["skew"]

                fig.add_trace(
                    go.Scatter(
                        x=p_k,
                        y=lvl_only_p,
                        mode="lines",
                        name="Put Overlay: Level Only",
                        line=dict(color="#d29922", width=1.5, dash="dot"),
                        visible="legendonly",
                        hovertemplate="<b>Put Strike:</b> %{x:.0f}<br><b>Level-Only IV:</b> %{y:.2f}%<extra></extra>",
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=p_k,
                        y=lvl_skw_p,
                        mode="lines",
                        name="Put Overlay: Level + Skew",
                        line=dict(color="#a371f7", width=1.5, dash="dashdot"),
                        visible="legendonly",
                        hovertemplate="<b>Put Strike:</b> %{x:.0f}<br><b>Level+Skew IV:</b> %{y:.2f}%<extra></extra>",
                    )
                )

    # Reference lines: ATM Strike and Spot Price
    fig.add_vline(
        x=atm_strike,
        line=dict(color="#8b949e", width=1.2, dash="dash"),
        annotation_text=f"ATM: {atm_strike:.0f}",
        annotation_position="top left",
        annotation_font=dict(color="#8b949e", size=10),
    )
    fig.add_vline(
        x=s0,
        line=dict(color="#2ea043", width=1.0, dash="dot"),
        annotation_text=f"Spot: {s0:.2f}",
        annotation_position="bottom right",
        annotation_font=dict(color="#2ea043", size=10),
    )

    # Reference Width lines: K_ATM - H and K_ATM + H
    fig.add_vline(
        x=atm_strike - h_width,
        line=dict(color="#30363d", width=1.0, dash="dot"),
        annotation_text=f"ATM - H ({atm_strike - h_width:.0f})",
        annotation_position="bottom left",
        annotation_font=dict(color="#8b949e", size=9),
    )
    fig.add_vline(
        x=atm_strike + h_width,
        line=dict(color="#30363d", width=1.0, dash="dot"),
        annotation_text=f"ATM + H ({atm_strike + h_width:.0f})",
        annotation_position="bottom right",
        annotation_font=dict(color="#8b949e", size=9),
    )

    title_desc = "Implied Volatility Smile (Fixed Strikes)"
    if is_shock_active:
        title_desc += f" — Shock: L={scen_active.level_vol_points:+.2f}, S={scen_active.skew_vol_points:+.2f}, C={scen_active.curvature_vol_points:+.2f} (H={h_width:.0f})"

    fig.update_layout(
        **THEME_LAYOUT,
        title=dict(text=title_desc, font=dict(size=14, color="#f0f6fc")),
        xaxis_title="Option Strike Price (SPX Points)",
        yaxis_title="Implied Volatility (%)",
    )
    return fig


def create_shock_decomposition_chart(
    snapshot_df: pd.DataFrame,
    scenario: IVShiftScenario,
) -> go.Figure:
    """Plot the Level, Skew, and Curvature shock contributions versus strike."""
    fig = go.Figure()
    if snapshot_df.empty:
        fig.update_layout(**THEME_LAYOUT, title="IV Shock Factor Decomposition")
        return fig

    atm_strike = float(snapshot_df["atm_strike"].iloc[0])
    h_width = float(scenario.reference_width)
    strikes = np.sort(snapshot_df["strike"].unique())

    x = compute_normalized_strike(strikes, atm_strike, h_width)
    lvl = np.full_like(x, float(scenario.level_vol_points))
    skw = (float(scenario.skew_vol_points) / 2.0) * x
    crv = float(scenario.curvature_vol_points) * (x ** 2)
    tot = lvl + skw + crv

    fig.add_trace(
        go.Scatter(
            x=strikes,
            y=lvl,
            mode="lines",
            name=f"Level Component: {scenario.level_vol_points:+.2f} pts",
            line=dict(color="#e3b341", width=1.8, dash="dash"),
            hovertemplate="<b>Strike:</b> %{x:.0f}<br>Level Shock: %{y:+.2f} pts<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=strikes,
            y=skw,
            mode="lines",
            name=f"Skew Component: (S/2)*x (S={scenario.skew_vol_points:+.2f})",
            line=dict(color="#58a6ff", width=1.8, dash="dashdot"),
            hovertemplate="<b>Strike:</b> %{x:.0f}<br>Skew Shock: %{y:+.2f} pts<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=strikes,
            y=crv,
            mode="lines",
            name=f"Curvature Component: C*x² (C={scenario.curvature_vol_points:+.2f})",
            line=dict(color="#bc8cff", width=1.8, dash="dot"),
            hovertemplate="<b>Strike:</b> %{x:.0f}<br>Curvature Shock: %{y:+.2f} pts<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=strikes,
            y=tot,
            mode="lines+markers",
            name="Total Additive Shock: Shock(K)",
            line=dict(color="#ff7b72", width=2.5),
            marker=dict(size=4),
            hovertemplate="<b>Strike:</b> %{x:.0f}<br><b>Total Shock:</b> %{y:+.2f} pts<extra></extra>",
        )
    )

    fig.add_hline(y=0.0, line=dict(color="#30363d", width=1, dash="solid"))
    fig.add_vline(
        x=atm_strike,
        line=dict(color="#8b949e", width=1, dash="dot"),
        annotation_text="ATM",
        annotation_position="top left",
    )

    fig.update_layout(
        **THEME_LAYOUT,
        title=dict(text="Additive IV Shock Decomposition vs Strike", font=dict(size=14, color="#f0f6fc")),
        xaxis_title="Option Strike Price (SPX Points)",
        yaxis_title="IV Shock Component (Volatility Points)",
    )
    return fig


def create_premium_curve_chart(
    repriced_flies: list[RepricedButterfly],
    title: str = "Butterfly Premium Curve",
) -> go.Figure:
    """Create Butterfly Premium vs Centre Strike chart (Original vs Shocked)."""
    fig = go.Figure()
    if not repriced_flies:
        fig.update_layout(**THEME_LAYOUT, title=title)
        return fig

    flies_sorted = sorted(repriced_flies, key=lambda f: f.fly.centre_strike)

    centre_strikes = [f.fly.centre_strike for f in flies_sorted]
    init_premiums = [f.fly.initial_fly_premium for f in flies_sorted]
    shocked_premiums = [f.shocked_fly_premium for f in flies_sorted]

    hover_texts_orig = []
    hover_texts_shock = []
    for f in flies_sorted:
        ht_orig = (
            f"<b>{f.fly.option_side.upper()} Fly</b><br>"
            f"Centre: {f.fly.centre_strike:.0f} (Wings: {f.fly.lower_strike:.0f} / {f.fly.upper_strike:.0f})<br>"
            f"Initial Premium: <b>{f.fly.initial_fly_premium:.4f} pts</b><br>"
            f"Initial IVs: [{f.fly.lower_iv*100:.2f}%, {f.fly.middle_iv*100:.2f}%, {f.fly.upper_iv*100:.2f}%]<br>"
            f"Initial Net Vega: {f.fly.initial_net_vega:.4f}"
        )
        ht_shock = (
            f"<b>{f.fly.option_side.upper()} Fly</b><br>"
            f"Centre: {f.fly.centre_strike:.0f} (Wings: {f.fly.lower_strike:.0f} / {f.fly.upper_strike:.0f})<br>"
            f"Shocked Premium: <b>{f.shocked_fly_premium:.4f} pts</b><br>"
            f"Change: <b>{f.fly_premium_change:+.4f} pts</b><br>"
            f"• Level Effect: {f.level_effect:+.4f} pts<br>"
            f"• Skew Effect: {f.skew_effect:+.4f} pts<br>"
            f"• Curv Effect: {f.curvature_effect:+.4f} pts<br>"
            f"Shocked IVs: [{f.lower_shocked_iv*100:.2f}%, {f.middle_shocked_iv*100:.2f}%, {f.upper_shocked_iv*100:.2f}%]<br>"
            f"Shocked Net Vega: {f.shocked_net_vega:.4f}"
        )
        hover_texts_orig.append(ht_orig)
        hover_texts_shock.append(ht_shock)

    # 1. Original Premium Curve (Solid Blue)
    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=init_premiums,
            mode="lines+markers",
            name="Original Premium",
            line=dict(color="#388bfd", width=2.5),
            marker=dict(size=7, color="#388bfd", symbol="circle"),
            hoverinfo="text",
            hovertext=hover_texts_orig,
        )
    )

    # 2. Shocked Premium Curve (Orange)
    scen = repriced_flies[0].scenario
    is_shocked = (
        abs(scen.level_vol_points) > 1e-4
        or abs(scen.skew_vol_points) > 1e-4
        or abs(scen.curvature_vol_points) > 1e-4
    )
    shock_label = f"Shocked Premium (L={scen.level_vol_points:+.2f}, S={scen.skew_vol_points:+.2f}, C={scen.curvature_vol_points:+.2f})"

    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=shocked_premiums,
            mode="lines+markers",
            name=shock_label,
            line=dict(color="#f0883e", width=2.5, dash="solid" if not is_shocked else "dash"),
            marker=dict(size=7, color="#f0883e", symbol="circle-open"),
            hoverinfo="text",
            hovertext=hover_texts_shock,
        )
    )

    fig.add_hline(y=0.0, line=dict(color="#30363d", width=1, dash="dash"))

    fig.update_layout(
        **THEME_LAYOUT,
        title=dict(text=title, font=dict(size=14, color="#f0f6fc")),
        xaxis_title="Butterfly Centre Strike Price",
        yaxis_title="Net Butterfly Premium (SPX Points)",
    )
    return fig


def create_premium_change_chart(
    repriced_flies: list[RepricedButterfly],
    title: str = "Change in Fly Premium vs Centre Strike",
) -> go.Figure:
    """Create chart showing (NewFlyPremium - OriginalFlyPremium) vs Centre Strike."""
    fig = go.Figure()
    if not repriced_flies:
        fig.update_layout(**THEME_LAYOUT, title=title)
        return fig

    flies_sorted = sorted(repriced_flies, key=lambda f: f.fly.centre_strike)
    centre_strikes = [f.fly.centre_strike for f in flies_sorted]
    changes = [f.fly_premium_change for f in flies_sorted]

    colors = ["#2ea043" if c >= 0 else "#f85149" for c in changes]

    hover_texts = [
        (
            f"<b>Centre Strike:</b> {f.fly.centre_strike:.0f}<br>"
            f"<b>Premium Change:</b> {f.fly_premium_change:+.4f} pts<br>"
            f"<b>1st-Order Change:</b> {f.first_order_change:+.4f} pts<br>"
            f"• Level Effect: {f.level_effect:+.4f} pts<br>"
            f"• Skew Effect: {f.skew_effect:+.4f} pts<br>"
            f"• Curv Effect: {f.curvature_effect:+.4f} pts<br>"
            f"<b>Nonlinear Residual:</b> {f.nonlinear_residual:+.4f} pts"
        )
        for f in flies_sorted
    ]

    fig.add_trace(
        go.Bar(
            x=centre_strikes,
            y=changes,
            marker=dict(color=colors, line=dict(color="#30363d", width=1)),
            hoverinfo="text",
            hovertext=hover_texts,
            name="Premium Change",
        )
    )

    fig.add_hline(y=0.0, line=dict(color="#8b949e", width=1, dash="solid"))

    fig.update_layout(
        **THEME_LAYOUT,
        title=dict(text=title, font=dict(size=14, color="#f0f6fc")),
        xaxis_title="Butterfly Centre Strike Price",
        yaxis_title="Premium Change (SPX Points)",
    )
    return fig


def create_iv_fly_chart(
    repriced_flies: list[RepricedButterfly],
    title: str = "IV Butterfly Curvature vs Centre Strike",
) -> go.Figure:
    """Create chart of IV Fly curvature (Original vs Shocked vs Difference)."""
    fig = go.Figure()
    if not repriced_flies:
        fig.update_layout(**THEME_LAYOUT, title=title)
        return fig

    flies_sorted = sorted(repriced_flies, key=lambda f: f.fly.centre_strike)
    centre_strikes = [f.fly.centre_strike for f in flies_sorted]
    init_iv_flies = [f.fly.initial_iv_fly_pct for f in flies_sorted]
    shocked_iv_flies = [f.shocked_iv_fly_pct for f in flies_sorted]
    diff_iv_flies = [f.shocked_iv_fly_pct - f.fly.initial_iv_fly_pct for f in flies_sorted]

    # Theoretical invariant: ChangeInIVFly = 2 * C * (h / H)^2
    scen = repriced_flies[0].scenario
    c_val = scen.curvature_vol_points
    h_wing = repriced_flies[0].fly.wing_width
    h_ref = scen.reference_width
    theory_diff = 2.0 * c_val * ((h_wing / h_ref) ** 2)

    # 1. Original IV Fly
    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=init_iv_flies,
            mode="lines+markers",
            name="Original IV Fly",
            line=dict(color="#a371f7", width=2.5),
            marker=dict(size=7, color="#a371f7"),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br><b>Original IV Fly:</b> %{y:.4f} vol pts<extra></extra>",
        )
    )

    # 2. Shocked IV Fly
    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=shocked_iv_flies,
            mode="lines+markers",
            name="Shocked IV Fly",
            line=dict(color="#3fb950", width=2.5, dash="dash"),
            marker=dict(size=5, color="#3fb950", symbol="x"),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br><b>Shocked IV Fly:</b> %{y:.4f} vol pts<extra></extra>",
        )
    )

    # 3. Difference Curve
    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=diff_iv_flies,
            mode="lines+markers",
            name=f"Δ IV Fly (Theory: {theory_diff:+.4f} pts)",
            line=dict(color="#ff7b72", width=1.8, dash="dot"),
            marker=dict(size=6, symbol="triangle-up"),
            hovertemplate=(
                f"<b>Centre:</b> %{{x:.0f}}<br>"
                f"<b>Δ IV Fly:</b> %{{y:.4f}} vol pts<br>"
                f"<b>Theory [2*C*(h/H)²]:</b> {theory_diff:+.4f} vol pts<extra></extra>"
            ),
        )
    )

    fig.add_hline(y=0.0, line=dict(color="#30363d", width=1, dash="dot"))
    if abs(c_val) > 1e-4:
        fig.add_hline(
            y=theory_diff,
            line=dict(color="#d29922", width=1, dash="dash"),
            annotation_text=f"Invariant = 2*C*(h/H)² = {theory_diff:+.4f} pts",
            annotation_position="bottom right",
            annotation_font=dict(color="#d29922", size=10),
        )

    fig.update_layout(
        **THEME_LAYOUT,
        title=dict(text=title, font=dict(size=14, color="#f0f6fc")),
        xaxis_title="Butterfly Centre Strike Price",
        yaxis_title="IV Fly Second Difference (Volatility Points)",
    )
    return fig


def create_factor_exposures_chart(
    repriced_flies: list[RepricedButterfly],
    title: str = "Butterfly Factor Sensitivities vs Centre Strike",
) -> go.Figure:
    """Create chart displaying Level, Skew, and Curvature Factor Exposures."""
    fig = go.Figure()
    if not repriced_flies:
        fig.update_layout(**THEME_LAYOUT, title=title)
        return fig

    flies_sorted = sorted(repriced_flies, key=lambda f: f.fly.centre_strike)
    centre_strikes = [f.fly.centre_strike for f in flies_sorted]

    lvl_exps = [f.level_exposure for f in flies_sorted]
    skw_exps = [f.skew_exposure for f in flies_sorted]
    crv_exps = [f.curvature_exposure for f in flies_sorted]

    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=lvl_exps,
            mode="lines+markers",
            name="Level Sensitivity (Net Vega)",
            line=dict(color="#e3b341", width=2.2),
            marker=dict(size=6, symbol="circle"),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br><b>Level Exposure:</b> %{y:.4f} pts / +1 vol pt<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=skw_exps,
            mode="lines+markers",
            name="Skew Sensitivity (Σ q_i Vega_i x_i/2)",
            line=dict(color="#58a6ff", width=2.2, dash="dash"),
            marker=dict(size=6, symbol="square"),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br><b>Skew Exposure:</b> %{y:.4f} pts / +1 skew unit<extra></extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=crv_exps,
            mode="lines+markers",
            name="Curvature Sensitivity (Σ q_i Vega_i x_i²)",
            line=dict(color="#bc8cff", width=2.2, dash="dot"),
            marker=dict(size=6, symbol="diamond"),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br><b>Curvature Exposure:</b> %{y:.4f} pts / +1 curvature unit<extra></extra>",
        )
    )

    fig.add_hline(y=0.0, line=dict(color="#8b949e", width=1, dash="solid"))

    fig.update_layout(
        **THEME_LAYOUT,
        title=dict(text=title, font=dict(size=14, color="#f0f6fc")),
        xaxis_title="Butterfly Centre Strike Price",
        yaxis_title="Sensitivity (SPX Points / +1 Factor Unit)",
    )
    return fig


def create_scenario_attribution_chart(
    repriced_flies: list[RepricedButterfly],
    attribution_mode: str = "sequential",
    title: str = "Factor Premium Attribution vs Centre Strike",
) -> go.Figure:
    """Create stacked bar chart showing decomposition of premium change across factors."""
    fig = go.Figure()
    if not repriced_flies:
        fig.update_layout(**THEME_LAYOUT, title=title)
        return fig

    flies_sorted = sorted(repriced_flies, key=lambda f: f.fly.centre_strike)
    centre_strikes = [f.fly.centre_strike for f in flies_sorted]

    if attribution_mode == "shapley":
        lvl_vals = [f.shapley_level for f in flies_sorted]
        skw_vals = [f.shapley_skew for f in flies_sorted]
        crv_vals = [f.shapley_curvature for f in flies_sorted]
        sub_title = "Shapley Attribution (6-Permutation Average)"
    else:
        lvl_vals = [f.level_effect for f in flies_sorted]
        skw_vals = [f.skew_effect for f in flies_sorted]
        crv_vals = [f.curvature_effect for f in flies_sorted]
        sub_title = "Sequential Attribution (Level → Skew → Curvature)"

    exact_changes = [f.exact_change for f in flies_sorted]

    fig.add_trace(
        go.Bar(
            x=centre_strikes,
            y=lvl_vals,
            name="Level Effect",
            marker=dict(color="#e3b341"),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br>Level Effect: %{y:+.4f} pts<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=centre_strikes,
            y=skw_vals,
            name="Skew Effect",
            marker=dict(color="#58a6ff"),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br>Skew Effect: %{y:+.4f} pts<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=centre_strikes,
            y=crv_vals,
            name="Curvature Effect",
            marker=dict(color="#bc8cff"),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br>Curvature Effect: %{y:+.4f} pts<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=exact_changes,
            mode="lines+markers",
            name="Total Exact Change",
            line=dict(color="#f0f6fc", width=2.5),
            marker=dict(size=6, color="#f0f6fc"),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br><b>Total Change:</b> %{y:+.4f} pts<extra></extra>",
        )
    )

    fig.add_hline(y=0.0, line=dict(color="#8b949e", width=1, dash="solid"))

    fig.update_layout(
        **THEME_LAYOUT,
        barmode="relative",
        title=dict(text=f"{title} ({sub_title})", font=dict(size=14, color="#f0f6fc")),
        xaxis_title="Butterfly Centre Strike Price",
        yaxis_title="Premium Attribution (SPX Points)",
    )
    return fig


def create_selected_fly_sensitivity_chart(
    repriced_fly: RepricedButterfly,
    pricing_mode: str = "baseline_delta",
    r: float = 0.0,
    q: float = 0.0,
) -> go.Figure:
    """Create 3-panel 1D response curves for a selected fly: Premium vs Level, Skew, and Curvature."""
    fly = repriced_fly.fly
    base_scen = repriced_fly.scenario

    curr_L = base_scen.level_vol_points
    curr_S = base_scen.skew_vol_points
    curr_C = base_scen.curvature_vol_points
    h_ref = base_scen.reference_width
    atm_ref = base_scen.atm_strike if base_scen.atm_strike > 0 else fly.atm_strike

    # Grids
    l_grid = np.linspace(-5.0, 10.0, 31)
    s_grid = np.linspace(-5.0, 5.0, 41)
    c_grid = np.linspace(-3.0, 3.0, 31)

    # 1. Fly Premium vs Level (holding curr_S, curr_C constant)
    p_vs_l = []
    for l_val in l_grid:
        sc = IVShiftScenario(level_vol_points=l_val, skew_vol_points=curr_S, curvature_vol_points=curr_C, reference_width=h_ref, atm_strike=atm_ref)
        rep = reprice_butterfly(fly, sc, pricing_mode=pricing_mode, r=r, q=q)
        p_vs_l.append(rep.shocked_fly_premium)

    # 2. Fly Premium vs Skew (holding curr_L, curr_C constant)
    p_vs_s = []
    for s_val in s_grid:
        sc = IVShiftScenario(level_vol_points=curr_L, skew_vol_points=s_val, curvature_vol_points=curr_C, reference_width=h_ref, atm_strike=atm_ref)
        rep = reprice_butterfly(fly, sc, pricing_mode=pricing_mode, r=r, q=q)
        p_vs_s.append(rep.shocked_fly_premium)

    # 3. Fly Premium vs Curvature (holding curr_L, curr_S constant)
    p_vs_c = []
    for c_val in c_grid:
        sc = IVShiftScenario(level_vol_points=curr_L, skew_vol_points=curr_S, curvature_vol_points=c_val, reference_width=h_ref, atm_strike=atm_ref)
        rep = reprice_butterfly(fly, sc, pricing_mode=pricing_mode, r=r, q=q)
        p_vs_c.append(rep.shocked_fly_premium)

    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=[
            f"Premium vs Level (S={curr_S:+.2f}, C={curr_C:+.2f})",
            f"Premium vs Skew (L={curr_L:+.2f}, C={curr_C:+.2f})",
            f"Premium vs Curvature (L={curr_L:+.2f}, S={curr_S:+.2f})",
        ],
    )

    # Subplot 1: Level
    fig.add_trace(
        go.Scatter(
            x=l_grid,
            y=p_vs_l,
            mode="lines",
            name="vs Level",
            line=dict(color="#e3b341", width=2.5),
            hovertemplate="Level: %{x:+.2f} pts<br>Fly Premium: %{y:.4f} pts<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=[curr_L],
            y=[repriced_fly.shocked_fly_premium],
            mode="markers",
            name="Current Level",
            marker=dict(color="#ff7b72", size=9, symbol="diamond"),
            hovertemplate="Current L: %{x:+.2f} pts<br>Premium: %{y:.4f} pts<extra></extra>",
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    # Subplot 2: Skew
    fig.add_trace(
        go.Scatter(
            x=s_grid,
            y=p_vs_s,
            mode="lines",
            name="vs Skew",
            line=dict(color="#58a6ff", width=2.5),
            hovertemplate="Skew: %{x:+.2f} pts<br>Fly Premium: %{y:.4f} pts<extra></extra>",
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Scatter(
            x=[curr_S],
            y=[repriced_fly.shocked_fly_premium],
            mode="markers",
            name="Current Skew",
            marker=dict(color="#ff7b72", size=9, symbol="diamond"),
            hovertemplate="Current S: %{x:+.2f} pts<br>Premium: %{y:.4f} pts<extra></extra>",
            showlegend=False,
        ),
        row=1,
        col=2,
    )

    # Subplot 3: Curvature
    fig.add_trace(
        go.Scatter(
            x=c_grid,
            y=p_vs_c,
            mode="lines",
            name="vs Curvature",
            line=dict(color="#bc8cff", width=2.5),
            hovertemplate="Curvature: %{x:+.2f} pts<br>Fly Premium: %{y:.4f} pts<extra></extra>",
        ),
        row=1,
        col=3,
    )
    fig.add_trace(
        go.Scatter(
            x=[curr_C],
            y=[repriced_fly.shocked_fly_premium],
            mode="markers",
            name="Current Curvature",
            marker=dict(color="#ff7b72", size=9, symbol="diamond"),
            hovertemplate="Current C: %{x:+.2f} pts<br>Premium: %{y:.4f} pts<extra></extra>",
            showlegend=False,
        ),
        row=1,
        col=3,
    )

    # Baseline horizontal reference lines
    for col_idx in (1, 2, 3):
        fig.add_hline(
            y=fly.initial_fly_premium,
            line=dict(color="#30363d", width=1, dash="dot"),
            row=1,
            col=col_idx,
        )

    fly_name = f"{fly.option_side.upper()} @ {fly.centre_strike:.0f}"
    fig.update_layout(
        **THEME_LAYOUT,
        title=dict(
            text=f"Selected Fly 1D Response Curves — {fly_name} (Wings {fly.lower_strike:.0f}/{fly.upper_strike:.0f})",
            font=dict(size=14, color="#f0f6fc"),
        ),
        showlegend=False,
    )
    fig.update_xaxes(title_text="Level Shift (pts)", row=1, col=1)
    fig.update_xaxes(title_text="Skew Shift S (pts)", row=1, col=2)
    fig.update_xaxes(title_text="Curvature Shift C (pts)", row=1, col=3)
    fig.update_yaxes(title_text="Fly Premium (SPX pts)", row=1, col=1)

    return fig


def create_greeks_chart(
    repriced_flies: list[RepricedButterfly],
    title: str = "Net Vega & Volga vs Centre Strike",
) -> go.Figure:
    """Create chart displaying Net Vega (Initial & Shocked) and Net Volga."""
    fig = go.Figure()
    if not repriced_flies:
        fig.update_layout(**THEME_LAYOUT, title=title)
        return fig

    flies_sorted = sorted(repriced_flies, key=lambda f: f.fly.centre_strike)
    centre_strikes = [f.fly.centre_strike for f in flies_sorted]
    init_vegas = [f.fly.initial_net_vega for f in flies_sorted]
    shocked_vegas = [f.shocked_net_vega for f in flies_sorted]
    init_volgas = [f.fly.initial_net_volga for f in flies_sorted]

    # Initial Net Vega
    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=init_vegas,
            mode="lines+markers",
            name="Initial Net Vega",
            line=dict(color="#58a6ff", width=2),
            marker=dict(size=6),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br><b>Initial Net Vega:</b> %{y:.4f} pts / +1 vol pt<extra></extra>",
        )
    )

    # Shocked Net Vega
    scen = repriced_flies[0].scenario
    is_shocked = (
        abs(scen.level_vol_points) > 1e-4
        or abs(scen.skew_vol_points) > 1e-4
        or abs(scen.curvature_vol_points) > 1e-4
    )
    if is_shocked:
        fig.add_trace(
            go.Scatter(
                x=centre_strikes,
                y=shocked_vegas,
                mode="lines+markers",
                name=f"Shocked Net Vega (L={scen.level_vol_points:+.2f})",
                line=dict(color="#ff7b72", width=2, dash="dash"),
                marker=dict(size=6, symbol="circle-open"),
                hovertemplate="<b>Centre:</b> %{x:.0f}<br><b>Shocked Net Vega:</b> %{y:.4f} pts / +1 vol pt<extra></extra>",
            )
        )

    # Initial Net Volga
    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=init_volgas,
            mode="lines+markers",
            name="Initial Net Volga",
            line=dict(color="#d29922", width=1.5, dash="dot"),
            marker=dict(size=5, symbol="triangle-up"),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br><b>Initial Net Volga:</b> %{y:.5f}<extra></extra>",
        )
    )

    fig.add_hline(y=0.0, line=dict(color="#8b949e", width=1, dash="solid"))

    fig.update_layout(
        **THEME_LAYOUT,
        title=dict(text=title, font=dict(size=14, color="#f0f6fc")),
        xaxis_title="Butterfly Centre Strike Price",
        yaxis_title="Net Sensitivity",
    )
    return fig


def create_attribution_chart(
    repriced_flies: list[RepricedButterfly],
    title: str = "Nonlinear Repricing Attribution vs Centre Strike",
) -> go.Figure:
    """Compare Exact Change, 1st-order Factor Estimate, and Nonlinear Residual."""
    fig = go.Figure()
    if not repriced_flies:
        fig.update_layout(**THEME_LAYOUT, title=title)
        return fig

    flies_sorted = sorted(repriced_flies, key=lambda f: f.fly.centre_strike)
    centre_strikes = [f.fly.centre_strike for f in flies_sorted]
    exact_changes = [f.exact_change for f in flies_sorted]
    first_order = [f.first_order_change for f in flies_sorted]
    residuals = [f.nonlinear_residual for f in flies_sorted]

    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=exact_changes,
            mode="lines+markers",
            name="Exact Repricing Change",
            line=dict(color="#388bfd", width=2.5),
            marker=dict(size=7),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br><b>Exact Change:</b> %{y:.4f} pts<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=first_order,
            mode="lines+markers",
            name="1st-Order Factor Estimate",
            line=dict(color="#e3b341", width=2, dash="dash"),
            marker=dict(size=6, symbol="square"),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br><b>1st-Order Est:</b> %{y:.4f} pts<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=centre_strikes,
            y=residuals,
            mode="lines+markers",
            name="Nonlinear Residual",
            line=dict(color="#f85149", width=1.8, dash="dot"),
            marker=dict(size=5, symbol="diamond"),
            hovertemplate="<b>Centre:</b> %{x:.0f}<br><b>Nonlinear Residual:</b> %{y:.4f} pts<extra></extra>",
        )
    )

    fig.add_hline(y=0.0, line=dict(color="#30363d", width=1, dash="solid"))

    fig.update_layout(
        **THEME_LAYOUT,
        title=dict(text=title, font=dict(size=14, color="#f0f6fc")),
        xaxis_title="Butterfly Centre Strike Price",
        yaxis_title="Change in Premium (SPX Points)",
    )
    return fig
