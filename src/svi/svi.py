"""Raw SVI slice (Gatheral).

w(k) = a + b * ( rho*(k-m) + sqrt((k-m)^2 + sigma^2) )

Constraints enforced:
    b > 0
    |rho| < 1
    sigma > 0
    a + b * sigma * sqrt(1-rho^2) >= 0   (non-negative minimum variance)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from scipy.optimize import least_squares


def svi_total_variance(
    k: np.ndarray,
    a: float,
    b: float,
    rho: float,
    m: float,
    sigma: float,
) -> np.ndarray:
    k = np.asarray(k, dtype=float)
    return a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sigma**2))


def svi_iv(k: np.ndarray, params: tuple[float, ...], T: float) -> np.ndarray:
    w = svi_total_variance(k, *params)
    w = np.maximum(w, 1e-12)
    return np.sqrt(w / max(T, 1e-12))


@dataclass
class SVIFit:
    a: float
    b: float
    rho: float
    m: float
    sigma: float
    success: bool
    n_obs: int
    iv_rmse: float
    iv_mae: float
    w_rmse: float
    min_w: float
    calendar_ok: bool
    butterfly_density_ok: bool
    message: str

    def params(self) -> tuple[float, float, float, float, float]:
        return self.a, self.b, self.rho, self.m, self.sigma

    def to_record(self) -> dict:
        return asdict(self)


def _init_from_data(k: np.ndarray, w: np.ndarray) -> np.ndarray:
    atm = int(np.argmin(np.abs(k)))
    w_atm = float(max(w[atm], 1e-6))
    # Skew from a linear fit near ATM.
    near = np.abs(k) < 0.15
    if near.sum() >= 5:
        coef = np.polyfit(k[near], w[near], 1)
        slope = float(coef[0])
    else:
        slope = 0.0
    rho = float(np.clip(slope / (abs(slope) + 1e-6) * 0.3, -0.8, 0.8))
    a = max(0.5 * w_atm, 1e-6)
    b = max(0.1 * w_atm, 1e-4)
    m = float(np.clip(k[atm], -0.2, 0.2))
    sigma = 0.1
    return np.array([a, b, rho, m, sigma], dtype=float)


def _bounds() -> tuple[np.ndarray, np.ndarray]:
    # a, b, rho, m, sigma
    lo = np.array([1e-8, 1e-6, -0.999, -1.0, 1e-4])
    hi = np.array([2.0, 5.0, 0.999, 1.0, 2.0])
    return lo, hi


def _min_variance(a: float, b: float, rho: float, sigma: float) -> float:
    return a + b * sigma * np.sqrt(max(1.0 - rho * rho, 0.0))


def fit_svi(
    k: np.ndarray,
    w: np.ndarray,
    iv: np.ndarray,
    T: float,
    weights: np.ndarray | None = None,
    prev_params: tuple[float, ...] | None = None,
) -> SVIFit:
    k = np.asarray(k, dtype=float)
    w = np.asarray(w, dtype=float)
    iv = np.asarray(iv, dtype=float)
    mask = np.isfinite(k) & np.isfinite(w) & np.isfinite(iv) & (w > 0) & (iv > 0)
    k, w, iv = k[mask], w[mask], iv[mask]
    if weights is None:
        wt = np.ones_like(w)
    else:
        wt = np.asarray(weights, dtype=float)[mask]
        wt = np.clip(wt, 0, None)
        if wt.sum() <= 0:
            wt = np.ones_like(w)
    n = len(k)
    if n < 5:
        return SVIFit(0, 0, 0, 0, 0.1, False, n, np.nan, np.nan, np.nan, np.nan, False, False, "too_few_points")

    x0 = np.array(prev_params, dtype=float) if prev_params is not None else _init_from_data(k, w)
    lo, hi = _bounds()
    x0 = np.minimum(np.maximum(x0, lo + 1e-8), hi - 1e-8)

    def resid(x: np.ndarray) -> np.ndarray:
        a, b, rho, m, sig = x
        w_hat = svi_total_variance(k, a, b, rho, m, sig)
        # Soft penalty if min variance is negative.
        pen = min(0.0, _min_variance(a, b, rho, sig)) * 50.0
        return np.sqrt(wt) * (w_hat - w) + pen

    res = least_squares(resid, x0, bounds=(lo, hi), max_nfev=400, ftol=1e-10)
    a, b, rho, m, sig = [float(v) for v in res.x]
    w_hat = svi_total_variance(k, a, b, rho, m, sig)
    iv_hat = np.sqrt(np.maximum(w_hat, 1e-12) / max(T, 1e-12))
    iv_rmse = float(np.sqrt(np.mean((iv_hat - iv) ** 2)))
    iv_mae = float(np.mean(np.abs(iv_hat - iv)))
    w_rmse = float(np.sqrt(np.mean((w_hat - w) ** 2)))
    min_w = float(np.min(w_hat))
    dens_ok = bool(min_w >= -1e-8 and _min_variance(a, b, rho, sig) >= -1e-8)
    return SVIFit(
        a=a,
        b=b,
        rho=rho,
        m=m,
        sigma=sig,
        success=bool(res.success) and dens_ok,
        n_obs=n,
        iv_rmse=iv_rmse,
        iv_mae=iv_mae,
        w_rmse=w_rmse,
        min_w=min_w,
        calendar_ok=True,  # single-slice model; calendar N/A
        butterfly_density_ok=dens_ok,
        message=str(res.message),
    )
