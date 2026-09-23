"""Historical standardization, realized vol, and regime features.

All rolling statistics at date t use only observations with date <= t
(and, for residual z-scores, typically the past window ending at t).
No future IV or future RV is ever used as a feature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import DEFAULT, ResearchConfig


def compute_realized_vol(spot_daily: pd.Series, windows: tuple[int, ...] | None = None) -> pd.DataFrame:
    """Close-to-close realized vol from daily last-snapshot underlying.

    RV_n at date t uses log returns from t-n+1 through t (inclusive).
    Annualised with sqrt(252).
    """
    windows = windows or (5, 10, 20, 30, 60)
    px = spot_daily.sort_index()
    logret = np.log(px).diff()
    out = pd.DataFrame({"spot": px, "logret": logret})
    for w in windows:
        out[f"rv_{w}"] = logret.rolling(w, min_periods=max(3, w // 2)).std() * np.sqrt(252)
    # EWMA vol, lambda=0.94 (RiskMetrics)
    out["rv_ewma"] = logret.ewm(alpha=1 - 0.94, min_periods=10, adjust=False).std() * np.sqrt(252)
    out["spot_ret_1"] = logret
    out["spot_ret_5"] = np.log(px / px.shift(5))
    out["spot_ret_20"] = np.log(px / px.shift(20))
    roll_max = px.rolling(20, min_periods=5).max()
    out["drawdown_20"] = px / roll_max - 1.0
    return out


def add_rolling_stats(
    panel: pd.DataFrame,
    value_col: str,
    date_col: str = "trade_date",
    group_col: str = "structure",
    windows: tuple[int, ...] | None = None,
    prefix: str | None = None,
) -> pd.DataFrame:
    """Causal rolling mean / std / z / percentile by structure.

    Uses expanding-within-window observations up to and including t.
    z_w = (x_t - mean_{t-w+1..t}) / std_{t-w+1..t}
    Percentile is the empirical rank of x_t in the same window.
    """
    windows = windows or DEFAULT.rolling_windows
    prefix = prefix or value_col
    out = panel.sort_values([group_col, date_col]).copy()
    g = out.groupby(group_col, sort=False)[value_col]
    for w in windows:
        minp = max(1, min(w, max(8, w // 4)))
        mean = g.transform(lambda s, ww=w: s.rolling(ww, min_periods=minp).mean())
        std = g.transform(lambda s, ww=w: s.rolling(ww, min_periods=minp).std(ddof=1))
        out[f"z_{w}_{prefix}"] = (out[value_col] - mean) / std.replace(0, np.nan)
        out[f"pct_{w}_{prefix}"] = g.transform(
            lambda s, ww=w: s.rolling(ww, min_periods=minp).apply(_last_percentile, raw=False)
        )
        out[f"mean_{w}_{prefix}"] = mean
        out[f"std_{w}_{prefix}"] = std
    return out


def _last_percentile(s: pd.Series) -> float:
    if s.isna().all():
        return float("nan")
    return float(s.rank(pct=True).iloc[-1])


def attach_future_labels(
    panel: pd.DataFrame,
    value_col: str,
    date_col: str = "trade_date",
    group_col: str = "structure",
    horizons: tuple[int, ...] | None = None,
    label_horizon_cutoff: object | None = None,
) -> pd.DataFrame:
    """Future residual change and convergence labels.

    future_change_h = R_{t+h} - R_t
    convergence_h   = sign(-R_t) * (R_{t+h} - R_t)

    Positive convergence means the residual moved toward zero.
    Labels whose t+h date is after `label_horizon_cutoff` are set to NaN
    so they cannot enter training.
    """
    horizons = horizons or DEFAULT.horizons
    out = panel.sort_values([group_col, date_col]).copy()
    dates = pd.to_datetime(out[date_col])
    out["_dt"] = dates
    for h in horizons:
        fut = out.groupby(group_col)[value_col].shift(-h)
        fut_date = out.groupby(group_col)["_dt"].shift(-h)
        out[f"future_{value_col}_h{h}"] = fut
        out[f"future_change_h{h}"] = fut - out[value_col]
        out[f"convergence_h{h}"] = np.sign(-out[value_col]) * (fut - out[value_col])
        out[f"abs_residual_reduction_h{h}"] = out[value_col].abs() - fut.abs()
        out[f"converged_h{h}"] = (
            (np.sign(out[value_col]) != 0)
            & (fut * out[value_col] <= 0)
            | ((out[value_col].abs() > 0) & (fut.abs() < out[value_col].abs()))
        ).astype(float)
        if label_horizon_cutoff is not None:
            cutoff = pd.Timestamp(label_horizon_cutoff)
            invalid = fut_date > cutoff
            for c in (
                f"future_{value_col}_h{h}",
                f"future_change_h{h}",
                f"convergence_h{h}",
                f"abs_residual_reduction_h{h}",
                f"converged_h{h}",
            ):
                out.loc[invalid, c] = np.nan
    out = out.drop(columns=["_dt"])
    return out


def add_regime_features(panel: pd.DataFrame, rv: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.date
    rv2 = rv.copy()
    rv2.index = pd.to_datetime(rv2.index).date
    out = out.merge(rv2, left_on="trade_date", right_index=True, how="left", suffixes=("", "_rv"))
    if "ATM_IV" in set(out.get("structure", pd.Series(dtype=object))):
        pass
    return out
