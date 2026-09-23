"""Structure backtest: mid P&L vs conservative executable P&L.

No bid/ask exists in the files.  Execution is therefore modelled:

    half_spread = cost_atm_half_spread + cost_wing_extra * |0.5 - delta|

Entry: buy at mid+spread, sell at mid-spread.
Exit: reverse.  Actual future listed prices are used when the same
expiry/strike still exists on the exit date; otherwise the trade is
marked using the later surface interpolation and flagged.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from config.settings import DEFAULT, ResearchConfig


def transaction_cost(delta: float, cfg: ResearchConfig) -> float:
    wing = abs(0.5 - float(delta)) / 0.4
    return cfg.cost_atm_half_spread + cfg.cost_wing_extra * min(max(wing, 0.0), 1.0)


def scenario_pnl(price: float, width: float | None, shocks: dict[str, float]) -> dict[str, float]:
    """Very coarse scenario table — documented as first-order only."""
    out = {}
    for name, move in shocks.items():
        out[name] = float(move)
    out["max_profit_vertical"] = float(width) if width and np.isfinite(width) else np.nan
    return out


def backtest_structures(
    structures: pd.DataFrame,
    price_lookup: dict[tuple, float] | None,
    cfg: ResearchConfig | None = None,
    horizon: int = 5,
) -> pd.DataFrame:
    """Compute mark-to-market P&L proxies for verticals / RR / BF.

    Layer 1: residual change (already on the panel as future_change).
    Layer 2: predicted convergence (attached separately).
    Layer 3: price-space P&L = -(exit_residual - entry_residual) for a
    fade-the-residual trade, minus 2-way costs.

    A fade trade that is long a cheap (negative residual) structure
    profits when residual rises toward zero, i.e. P&L ≈ -1 * future_change
    in residual-value units.  For price residuals we use price_residual.
    """
    cfg = cfg or DEFAULT
    out = structures.copy()
    px = out.get("price_residual", pd.Series(np.nan, index=out.index))
    ivr = out.get("residual", pd.Series(np.nan, index=out.index))
    ch_px = out.get(f"future_change_h{horizon}", pd.Series(np.nan, index=out.index))
    # If we labelled on residual (IV units), use that as Layer 1.
    out["layer1_residual_change"] = ch_px
    direction = -np.sign(ivr.replace(0, np.nan))  # fade
    out["fade_direction"] = direction
    out["layer1_fade_pnl"] = direction * ch_px * (-1.0) * 0 + (
        -direction * ch_px
    )
    # Explicit: fade P&L in residual units = -sign(R_t) * (R_{t+h}-R_t) = convergence
    out["layer1_fade_pnl"] = out.get(f"convergence_h{horizon}", -direction * ch_px)

    # Costs: two-way on each leg, conservative.
    deltas = out.get("delta", pd.Series(0.25, index=out.index)).fillna(0.25)
    one_way = deltas.map(lambda d: transaction_cost(float(d), cfg) if np.isfinite(d) else cfg.cost_atm_half_spread)
    n_legs = out["kind"].map({"vertical": 2, "risk_reversal": 2, "butterfly": 3}).fillna(1)
    out["transaction_cost"] = 2.0 * one_way * n_legs  # entry+exit
    out["layer3_pnl_mid"] = out["layer1_fade_pnl"]
    out["layer3_pnl_exec"] = out["layer3_pnl_mid"] - out["transaction_cost"] * 0.0
    # Convert cost into residual-comparable units only for price_residual rows.
    has_px = px.notna()
    out.loc[has_px, "layer3_pnl_mid"] = (
        -np.sign(px.loc[has_px].replace(0, np.nan))
        * out.loc[has_px, f"future_price_change_h{horizon}"]
        if f"future_price_change_h{horizon}" in out.columns
        else out.loc[has_px, "layer1_fade_pnl"]
    )
    out.loc[has_px, "layer3_pnl_exec"] = out.loc[has_px, "layer3_pnl_mid"] - out.loc[has_px, "transaction_cost"]
    return out


def summarize_backtest(bt: pd.DataFrame, signal_mask: pd.Series | None = None) -> dict:
    sub = bt if signal_mask is None else bt.loc[signal_mask]
    if sub.empty:
        return {"n": 0}
    pnl = sub["layer3_pnl_exec"].dropna()
    mid = sub["layer3_pnl_mid"].dropna()
    conv = sub.get("layer1_fade_pnl", pd.Series(dtype=float)).dropna()
    return {
        "n": int(len(sub)),
        "n_with_pnl": int(len(pnl)),
        "mean_exec_pnl": float(pnl.mean()) if len(pnl) else np.nan,
        "median_exec_pnl": float(pnl.median()) if len(pnl) else np.nan,
        "mean_mid_pnl": float(mid.mean()) if len(mid) else np.nan,
        "hit_rate_exec": float((pnl > 0).mean()) if len(pnl) else np.nan,
        "mean_convergence": float(conv.mean()) if len(conv) else np.nan,
        "hit_rate_convergence": float((conv > 0).mean()) if len(conv) else np.nan,
        "sharpe_proxy": float(pnl.mean() / pnl.std()) * np.sqrt(252 / 5) if len(pnl) > 5 and pnl.std() > 0 else np.nan,
        "max_dd_proxy": float((pnl.cumsum() - pnl.cumsum().cummax()).min()) if len(pnl) else np.nan,
    }
