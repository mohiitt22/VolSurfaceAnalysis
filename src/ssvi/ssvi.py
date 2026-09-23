"""SSVI *slice* (Gatheral–Jacquier) as a constrained alternative to raw SVI.

Because the research surface is a single ~60-DTE expiry, a full
maturity-consistent SSVI surface is not identifiable.  This module fits
the SSVI *slice* formula

    w(k) = (theta/2) * (1 + rho * phi * k + sqrt((phi*k + rho)^2 + (1-rho^2)))

which is a restricted SVI.  It is useful as a more regular structural
benchmark, not as a calendar-arbitrage surface model.

Roger Lee wing condition (necessary):  theta * phi * (1+|rho|) < 4
is enforced as a soft/hard constraint.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from scipy.optimize import least_squares


def ssvi_total_variance(k: np.ndarray, theta: float, rho: float, phi: float) -> np.ndarray:
    k = np.asarray(k, dtype=float)
    inner = (phi * k + rho) ** 2 + (1.0 - rho * rho)
    return (theta / 2.0) * (1.0 + rho * phi * k + np.sqrt(np.maximum(inner, 0.0)))


@dataclass
class SSVIFit:
    theta: float
    rho: float
    phi: float
    success: bool
    n_obs: int
    iv_rmse: float
    iv_mae: float
    w_rmse: float
    lee_ok: bool
    message: str

    def to_record(self) -> dict:
        return asdict(self)


def fit_ssvi(
    k: np.ndarray,
    w: np.ndarray,
    iv: np.ndarray,
    T: float,
    weights: np.ndarray | None = None,
) -> SSVIFit:
    k = np.asarray(k, dtype=float)
    w = np.asarray(w, dtype=float)
    iv = np.asarray(iv, dtype=float)
    mask = np.isfinite(k) & np.isfinite(w) & np.isfinite(iv) & (w > 0)
    k, w, iv = k[mask], w[mask], iv[mask]
    wt = np.ones_like(w) if weights is None else np.clip(np.asarray(weights, dtype=float)[mask], 0, None)
    n = len(k)
    if n < 5:
        return SSVIFit(np.nan, 0, 0, False, n, np.nan, np.nan, np.nan, False, "too_few_points")

    atm = int(np.argmin(np.abs(k)))
    theta0 = float(max(w[atm], 1e-6))
    x0 = np.array([theta0, -0.3, 1.0 / max(np.std(k), 0.05)])
    lo = np.array([1e-6, -0.999, 1e-4])
    hi = np.array([2.0, 0.999, 50.0])
    x0 = np.minimum(np.maximum(x0, lo + 1e-8), hi - 1e-8)

    def resid(x: np.ndarray) -> np.ndarray:
        theta, rho, phi = x
        w_hat = ssvi_total_variance(k, theta, rho, phi)
        lee = theta * phi * (1.0 + abs(rho))
        pen = max(0.0, lee - 3.9) * 10.0
        return np.sqrt(wt) * (w_hat - w) + pen

    res = least_squares(resid, x0, bounds=(lo, hi), max_nfev=300)
    theta, rho, phi = [float(v) for v in res.x]
    w_hat = ssvi_total_variance(k, theta, rho, phi)
    iv_hat = np.sqrt(np.maximum(w_hat, 1e-12) / max(T, 1e-12))
    lee_ok = bool(theta * phi * (1.0 + abs(rho)) < 4.0)
    return SSVIFit(
        theta=theta,
        rho=rho,
        phi=phi,
        success=bool(res.success) and lee_ok,
        n_obs=n,
        iv_rmse=float(np.sqrt(np.mean((iv_hat - iv) ** 2))),
        iv_mae=float(np.mean(np.abs(iv_hat - iv))),
        w_rmse=float(np.sqrt(np.mean((w_hat - w) ** 2))),
        lee_ok=lee_ok,
        message=str(res.message),
    )
