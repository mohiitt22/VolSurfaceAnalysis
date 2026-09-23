"""Low-order polynomial benchmark on total variance: w(k) = a + b k + c k^2."""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np


@dataclass
class PolyFit:
    a: float
    b: float
    c: float
    success: bool
    n_obs: int
    iv_rmse: float
    iv_mae: float
    w_rmse: float
    weighting: str

    def to_record(self) -> dict:
        return asdict(self)


def poly_total_variance(k: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    k = np.asarray(k, dtype=float)
    return a + b * k + c * k * k


def fit_polynomial(
    k: np.ndarray,
    w: np.ndarray,
    iv: np.ndarray,
    T: float,
    weights: np.ndarray | None = None,
    weighting: str = "vega",
) -> PolyFit:
    k = np.asarray(k, dtype=float)
    w = np.asarray(w, dtype=float)
    iv = np.asarray(iv, dtype=float)
    mask = np.isfinite(k) & np.isfinite(w) & np.isfinite(iv)
    k, w, iv = k[mask], w[mask], iv[mask]
    if weights is None:
        wt = np.ones_like(w)
    else:
        wt = np.clip(np.asarray(weights, dtype=float)[mask], 0, None)
    n = len(k)
    if n < 4:
        return PolyFit(np.nan, 0, 0, False, n, np.nan, np.nan, np.nan, weighting)
    X = np.column_stack([np.ones(n), k, k * k])
    # Weighted least squares
    sw = np.sqrt(wt + 1e-12)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], w * sw, rcond=None)
    a, b, c = [float(v) for v in beta]
    w_hat = poly_total_variance(k, a, b, c)
    iv_hat = np.sqrt(np.maximum(w_hat, 1e-12) / max(T, 1e-12))
    return PolyFit(
        a=a,
        b=b,
        c=c,
        success=True,
        n_obs=n,
        iv_rmse=float(np.sqrt(np.mean((iv_hat - iv) ** 2))),
        iv_mae=float(np.mean(np.abs(iv_hat - iv))),
        w_rmse=float(np.sqrt(np.mean((w_hat - w) ** 2))),
        weighting=weighting,
    )
