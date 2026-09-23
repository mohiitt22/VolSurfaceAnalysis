"""SABR implied volatility (Hagan 2002 lognormal approximation).

Default beta=1 (lognormal).  We fit (alpha, rho, nu) with beta fixed.
SABR is an alternative structural model, not assumed to beat SVI.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from scipy.optimize import least_squares


def sabr_iv(
    F: float,
    K: np.ndarray,
    T: float,
    alpha: float,
    beta: float,
    rho: float,
    nu: float,
) -> np.ndarray:
    K = np.asarray(K, dtype=float)
    out = np.empty_like(K, dtype=float)
    for i, k in enumerate(K):
        out[i] = _sabr_one(F, float(k), T, alpha, beta, rho, nu)
    return out


def _sabr_one(
    F: float,
    K: float,
    T: float,
    alpha: float,
    beta: float,
    rho: float,
    nu: float,
) -> float:
    if F <= 0 or K <= 0 or T <= 0 or alpha <= 0:
        return float("nan")
    if abs(F - K) < 1e-12:
        term = ((1 - beta) ** 2) * (alpha**2) / (24.0 * F ** (2 - 2 * beta))
        term += 0.25 * rho * beta * nu * alpha / (F ** (1 - beta))
        term += (2.0 - 3.0 * rho**2) * (nu**2) / 24.0
        return alpha / (F ** (1 - beta)) * (1.0 + term * T)

    logfk = np.log(F / K)
    fk = F * K
    z = (nu / alpha) * (fk ** ((1 - beta) / 2.0)) * logfk
    # x(z)
    if abs(z) < 1e-8:
        xz = 1.0
    else:
        xz = np.log((np.sqrt(1.0 - 2.0 * rho * z + z * z) + z - rho) / (1.0 - rho))
        if abs(xz) < 1e-12:
            xz = z
        else:
            xz = z / xz
    den = (fk ** ((1 - beta) / 2.0)) * (
        1.0
        + ((1 - beta) ** 2) / 24.0 * (logfk**2)
        + ((1 - beta) ** 4) / 1920.0 * (logfk**4)
    )
    A = 1.0 + (
        ((1 - beta) ** 2) * (alpha**2) / (24.0 * fk ** (1 - beta))
        + 0.25 * rho * beta * nu * alpha / (fk ** ((1 - beta) / 2.0))
        + (2.0 - 3.0 * rho**2) * (nu**2) / 24.0
    ) * T
    return (alpha / den) * xz * A


@dataclass
class SABRFit:
    alpha: float
    beta: float
    rho: float
    nu: float
    success: bool
    n_obs: int
    iv_rmse: float
    iv_mae: float
    message: str

    def to_record(self) -> dict:
        return asdict(self)


def fit_sabr(
    F: float,
    K: np.ndarray,
    iv: np.ndarray,
    T: float,
    beta: float = 1.0,
    weights: np.ndarray | None = None,
) -> SABRFit:
    K = np.asarray(K, dtype=float)
    iv = np.asarray(iv, dtype=float)
    mask = np.isfinite(K) & np.isfinite(iv) & (K > 0) & (iv > 0)
    K, iv = K[mask], iv[mask]
    wt = np.ones_like(iv) if weights is None else np.clip(np.asarray(weights, dtype=float)[mask], 0, None)
    n = len(K)
    if n < 5 or F <= 0:
        return SABRFit(np.nan, beta, 0, 0, False, n, np.nan, np.nan, "too_few_points")

    atm = int(np.argmin(np.abs(K - F)))
    alpha0 = float(max(iv[atm] * (F ** (1 - beta)), 1e-4))
    x0 = np.array([alpha0, -0.3, 0.8])  # alpha, rho, nu
    lo = np.array([1e-6, -0.999, 1e-4])
    hi = np.array([5.0, 0.999, 5.0])
    x0 = np.minimum(np.maximum(x0, lo + 1e-8), hi - 1e-8)

    def resid(x: np.ndarray) -> np.ndarray:
        alpha, rho, nu = x
        hat = sabr_iv(F, K, T, alpha, beta, rho, nu)
        hat = np.where(np.isfinite(hat), hat, 10.0)
        return np.sqrt(wt) * (hat - iv)

    res = least_squares(resid, x0, bounds=(lo, hi), max_nfev=250)
    alpha, rho, nu = [float(v) for v in res.x]
    hat = sabr_iv(F, K, T, alpha, beta, rho, nu)
    return SABRFit(
        alpha=alpha,
        beta=beta,
        rho=rho,
        nu=nu,
        success=bool(res.success) and np.isfinite(hat).all(),
        n_obs=n,
        iv_rmse=float(np.sqrt(np.nanmean((hat - iv) ** 2))),
        iv_mae=float(np.nanmean(np.abs(hat - iv))),
        message=str(res.message),
    )
