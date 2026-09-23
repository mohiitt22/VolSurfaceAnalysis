"""Smoothing spline on total variance — local model for dislocations."""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from scipy.interpolate import UnivariateSpline


@dataclass
class SplineFit:
    success: bool
    n_obs: int
    iv_rmse: float
    iv_mae: float
    w_rmse: float
    smoothing: float
    spline: object

    def to_record(self) -> dict:
        rec = asdict(self)
        rec.pop("spline", None)
        return rec


def fit_spline(
    k: np.ndarray,
    w: np.ndarray,
    iv: np.ndarray,
    T: float,
    weights: np.ndarray | None = None,
    s_factor: float = 1e-6,
) -> SplineFit:
    k = np.asarray(k, dtype=float)
    w = np.asarray(w, dtype=float)
    iv = np.asarray(iv, dtype=float)
    mask = np.isfinite(k) & np.isfinite(w) & np.isfinite(iv)
    k, w, iv = k[mask], w[mask], iv[mask]
    order = np.argsort(k)
    k, w, iv = k[order], w[order], iv[order]
    # unique k
    _, idx = np.unique(k, return_index=True)
    k, w, iv = k[idx], w[idx], iv[idx]
    if weights is None:
        wt = np.ones_like(w)
    else:
        wt = np.clip(np.asarray(weights, dtype=float)[mask][order][idx], 1e-8, None)
    n = len(k)
    if n < 6:
        return SplineFit(False, n, np.nan, np.nan, np.nan, s_factor, None)
    s = float(s_factor * n)
    try:
        spl = UnivariateSpline(k, w, w=wt, k=3, s=s)
    except ValueError:
        return SplineFit(False, n, np.nan, np.nan, np.nan, s, None)
    w_hat = np.asarray(spl(k), dtype=float)
    iv_hat = np.sqrt(np.maximum(w_hat, 1e-12) / max(T, 1e-12))
    return SplineFit(
        success=True,
        n_obs=n,
        iv_rmse=float(np.sqrt(np.mean((iv_hat - iv) ** 2))),
        iv_mae=float(np.mean(np.abs(iv_hat - iv))),
        w_rmse=float(np.sqrt(np.mean((w_hat - w) ** 2))),
        smoothing=s,
        spline=spl,
    )


def spline_iv(spl: UnivariateSpline | None, k: np.ndarray, T: float) -> np.ndarray:
    if spl is None:
        return np.full(np.shape(k), np.nan)
    w = np.asarray(spl(k), dtype=float)
    return np.sqrt(np.maximum(w, 1e-12) / max(T, 1e-12))
