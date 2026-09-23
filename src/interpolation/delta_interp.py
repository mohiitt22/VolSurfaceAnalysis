"""Delta-space interpolation. Prefer local interpolation; flag extrapolation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d


@dataclass(frozen=True)
class DeltaPoint:
    delta_target: float
    side: str  # "put" | "call" | "atm"
    iv: float
    total_variance: float
    strike: float
    log_moneyness: float
    price: float
    vega: float
    gamma: float
    theta: float
    delta_actual: float
    interpolated: bool
    extrapolated: bool
    interp_distance: float


def _interp_xy(
    x: np.ndarray,
    y: np.ndarray,
    x0: float,
    max_extrap: float,
) -> tuple[float, bool, bool, float]:
    order = np.argsort(x)
    x = x[order]
    y = y[order]
    # unique x
    _, idx = np.unique(x, return_index=True)
    x = x[idx]
    y = y[idx]
    if len(x) < 2:
        return float("nan"), False, True, float("nan")
    dist_inside = 0.0
    extrapolated = bool(x0 < x[0] - 1e-12 or x0 > x[-1] + 1e-12)
    if extrapolated:
        edge = x[0] if x0 < x[0] else x[-1]
        dist = abs(x0 - edge)
        if dist > max_extrap:
            return float("nan"), False, True, dist
    f = interp1d(x, y, kind="linear", fill_value="extrapolate", assume_sorted=True)
    val = float(f(x0))
    if not extrapolated:
        # distance to nearest observed delta
        dist_inside = float(np.min(np.abs(x - x0)))
    interpolated = (not extrapolated) and dist_inside > 1e-6
    return val, interpolated, extrapolated, (abs(x0 - (x[0] if x0 < x[0] else x[-1])) if extrapolated else dist_inside)


def interpolate_delta_iv(
    surface: pd.DataFrame,
    delta_target: float,
    side: str,
    max_extrap: float = 0.03,
    iv_col: str = "market_iv",
) -> DeltaPoint:
    """Linear interpolation in delta space (later compared with TV interpolation).

    side='put'  uses put_delta_abs
    side='call' uses call_delta_abs
    side='atm'  uses the strike closest to forward / 50-delta blend
    """
    usable = surface.loc[surface.get("usable", True)].copy()
    if side == "atm":
        # Prefer |k| minimum; also record 50-delta call if present.
        if "k" in usable.columns:
            row = usable.iloc[(usable["k"].abs()).to_numpy().argmin()]
        else:
            row = usable.iloc[(usable["strike"] - usable["forward"]).abs().to_numpy().argmin()]
        return DeltaPoint(
            delta_target=0.50,
            side="atm",
            iv=float(row[iv_col]),
            total_variance=float(row["total_variance"]),
            strike=float(row["strike"]),
            log_moneyness=float(row["k"]),
            price=float(0.5 * (row["call_price"] + row["put_price"])),
            vega=float(row["vega"]),
            gamma=float(row["gamma"]),
            theta=float(row["theta"]),
            delta_actual=0.50,
            interpolated=False,
            extrapolated=False,
            interp_distance=0.0,
        )

    delta_col = "put_delta_abs" if side == "put" else "call_delta_abs"
    price_col = "put_price" if side == "put" else "call_price"
    x = usable[delta_col].to_numpy(dtype=float)
    mask = np.isfinite(x) & np.isfinite(usable[iv_col].to_numpy(dtype=float))
    x = x[mask]
    y_iv = usable[iv_col].to_numpy(dtype=float)[mask]
    y_w = usable["total_variance"].to_numpy(dtype=float)[mask]
    y_k = usable["strike"].to_numpy(dtype=float)[mask]
    y_m = usable["k"].to_numpy(dtype=float)[mask]
    y_p = usable[price_col].to_numpy(dtype=float)[mask]
    y_v = usable["vega"].to_numpy(dtype=float)[mask]
    y_g = usable["gamma"].to_numpy(dtype=float)[mask]
    y_t = usable["theta"].to_numpy(dtype=float)[mask]

    iv, interp, extrap, dist = _interp_xy(x, y_iv, delta_target, max_extrap)
    w, _, _, _ = _interp_xy(x, y_w, delta_target, max_extrap)
    strike, _, _, _ = _interp_xy(x, y_k, delta_target, max_extrap)
    moneyness, _, _, _ = _interp_xy(x, y_m, delta_target, max_extrap)
    price, _, _, _ = _interp_xy(x, y_p, delta_target, max_extrap)
    vega, _, _, _ = _interp_xy(x, y_v, delta_target, max_extrap)
    gamma, _, _, _ = _interp_xy(x, y_g, delta_target, max_extrap)
    theta, _, _, _ = _interp_xy(x, y_t, delta_target, max_extrap)

    return DeltaPoint(
        delta_target=delta_target,
        side=side,
        iv=iv,
        total_variance=w,
        strike=strike,
        log_moneyness=moneyness,
        price=price,
        vega=vega,
        gamma=gamma,
        theta=theta,
        delta_actual=delta_target,
        interpolated=interp,
        extrapolated=extrap,
        interp_distance=dist,
    )


def build_delta_grid(
    surface: pd.DataFrame,
    deltas: tuple[float, ...],
    max_extrap: float,
    iv_col: str = "market_iv",
) -> pd.DataFrame:
    rows = []
    atm = interpolate_delta_iv(surface, 0.50, "atm", max_extrap, iv_col)
    rows.append(atm.__dict__)
    for d in deltas:
        if abs(d - 0.50) < 1e-9:
            continue
        rows.append(interpolate_delta_iv(surface, d, "put", max_extrap, iv_col).__dict__)
        rows.append(interpolate_delta_iv(surface, d, "call", max_extrap, iv_col).__dict__)
    return pd.DataFrame(rows)
