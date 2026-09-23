"""Black-Scholes primitives used for IV reconstruction and model prices.

Rate in this dataset is identically 0.  We still take r as an argument so
the same functions work if a carry rate is later inferred from parity.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def _d1(F: float, K: float, T: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0 or F <= 0 or K <= 0:
        return float("nan")
    return (math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))


def bs_price(
    F: float,
    K: float,
    T: float,
    sigma: float,
    cp: str,
    df: float = 1.0,
) -> float:
    """Undiscounted Black price on the forward, then discounted by df."""
    if T <= 0:
        intrinsic = max(F - K, 0.0) if cp.upper() == "C" else max(K - F, 0.0)
        return df * intrinsic
    if sigma <= 0 or F <= 0 or K <= 0:
        return float("nan")
    d1 = _d1(F, K, T, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    if cp.upper() == "C":
        undisc = F * norm.cdf(d1) - K * norm.cdf(d2)
    elif cp.upper() == "P":
        undisc = K * norm.cdf(-d2) - F * norm.cdf(-d1)
    else:
        raise ValueError(f"cp must be C or P, got {cp}")
    return float(df * undisc)


def bs_vega(F: float, K: float, T: float, sigma: float, df: float = 1.0) -> float:
    if T <= 0 or sigma <= 0 or F <= 0 or K <= 0:
        return 0.0
    d1 = _d1(F, K, T, sigma)
    return float(df * F * norm.pdf(d1) * math.sqrt(T))


def implied_vol(
    price: float,
    F: float,
    K: float,
    T: float,
    cp: str,
    df: float = 1.0,
    lo: float = 1e-4,
    hi: float = 5.0,
) -> float:
    """Invert Black-Scholes. Returns NaN if the price is not bracketed."""
    if not np.isfinite(price) or price <= 0 or T <= 0 or F <= 0 or K <= 0:
        return float("nan")
    intrinsic = bs_price(F, K, T, 1e-8, cp, df)
    upper = bs_price(F, K, T, hi, cp, df)
    if price < intrinsic * 0.999 or price > upper * 1.001:
        return float("nan")

    def obj(sig: float) -> float:
        return bs_price(F, K, T, sig, cp, df) - price

    try:
        return float(brentq(obj, lo, hi, maxiter=100))
    except ValueError:
        return float("nan")


def implied_vol_vector(
    prices: np.ndarray,
    F: float,
    K: np.ndarray,
    T: float,
    cp: str,
    df: float = 1.0,
) -> np.ndarray:
    out = np.empty(len(prices), dtype=float)
    for i, (p, k) in enumerate(zip(prices, K)):
        out[i] = implied_vol(float(p), F, float(k), T, cp, df)
    return out
