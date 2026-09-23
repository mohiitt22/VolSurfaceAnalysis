"""Multiple cheap/expensive definitions.  None of them alone is a trade."""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import DEFAULT, ResearchConfig


def annotate_cheap_expensive(df: pd.DataFrame) -> pd.DataFrame:
    """Attach the 10 definition flags / scores as separate columns.

    Definition 1: structural (market vs ensemble fair)
    Definition 2: historical residual z
    Definition 3: relative-to-surface (neighbor residual)
    Definition 4: relative-to-delta (same structure historically — via z)
    Definition 5-7: skew / curvature / regime (structure kind + z)
    Definition 8: event-adjusted — no calendar in files; uses RV regime
    Definition 9: liquidity-adjusted residual
    Definition 10: executable (cost-adjusted residual)
    """
    out = df.copy()
    res = out.get("residual", out.get("residual_ensemble", pd.Series(np.nan, index=out.index)))
    out["cheap_structural"] = res < 0
    out["expensive_structural"] = res > 0

    z = out.get("z_60_residual", pd.Series(np.nan, index=out.index))
    out["residual_z"] = z
    out["cheap_historical"] = z < -1.0
    out["expensive_historical"] = z > 1.0

    if "price_residual" in out.columns:
        out["cheap_price"] = out["price_residual"] < 0
        out["expensive_price"] = out["price_residual"] > 0

    # Liquidity-adjusted: shrink residual when liquidity is poor.
    liq = out.get("liquidity_score", pd.Series(1.0, index=out.index)).fillna(0.0)
    out["residual_liq_adj"] = res * np.clip(liq, 0, 1)

    # Executable residual: residual after conservative cost (in value units).
    cost = out.get("transaction_cost", pd.Series(0.0, index=out.index)).fillna(0.0)
    out["residual_exec"] = res - np.sign(res) * cost
    out["cheap_executable"] = out["residual_exec"] < 0
    out["expensive_executable"] = out["residual_exec"] > 0

    # Regime split: high/low ATM IV if present as a column.
    if "atm_iv" in out.columns:
        med = out.groupby("trade_date")["atm_iv"].transform("median") if False else out["atm_iv"]
        out["high_iv_regime"] = out["atm_iv"] > out["atm_iv"].median()
    return out


def decide_trade(
    row: pd.Series,
    cfg: ResearchConfig | None = None,
    z_col: str = "z_60_residual",
    z_threshold: float | None = None,
) -> dict:
    """NO TRADE is a first-class output."""
    cfg = cfg or DEFAULT
    z_threshold = cfg.default_z_threshold if z_threshold is None else z_threshold
    z = row.get(z_col, np.nan)
    disp = row.get("model_dispersion", np.nan)
    liq = row.get("liquidity_score", np.nan)
    p_conv = row.get("pred_prob_convergence", np.nan)
    edge = row.get("pred_expected_return", np.nan)
    extrap = bool(row.get("extrapolated", False))

    reasons: list[str] = []
    if not np.isfinite(z) or abs(z) < z_threshold:
        reasons.append("z_below_threshold")
    if np.isfinite(disp) and disp > cfg.max_model_dispersion:
        reasons.append("high_model_disagreement")
    if np.isfinite(liq) and liq < cfg.min_liquidity_score:
        reasons.append("low_liquidity")
    if np.isfinite(p_conv) and p_conv < 0.5:
        reasons.append("weak_historical_convergence")
    if np.isfinite(edge) and edge < cfg.min_predicted_edge:
        reasons.append("edge_below_cost")
    if extrap:
        reasons.append("extrapolated_delta")

    trade = len(reasons) == 0 and np.isfinite(z) and abs(z) >= z_threshold
    direction = 0
    if trade:
        direction = -1 if z > 0 else 1  # fade the residual
    return {
        "decision": "TRADE" if trade else "NO TRADE",
        "trade_direction": direction,
        "no_trade_reasons": "|".join(reasons) if reasons else "",
        "signal_strength": float(abs(z)) if np.isfinite(z) else np.nan,
    }
