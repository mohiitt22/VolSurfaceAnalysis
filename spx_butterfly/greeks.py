"""Analytical Black-Scholes Greeks calculation and scaling.

Units:
- Vega: SPX premium points per +1 IV percentage point (i.e. Vega_dec * 0.01).
- Volga (Vomma): SPX premium points per (+1 IV percentage point)^2 (i.e. Volga_dec * 0.0001).
- Delta: Dimensionless (dPrice / dSpot).
- Gamma: Per SPX point (dDelta / dSpot).
- Theta: SPX premium points per 1 calendar day decay (Theta_annual / 365).
- Vanna: dVega / dSpot per +1 IV percentage point (Vanna_dec * 0.01).
- Rho: SPX premium points per +1% interest rate change (Rho_dec * 0.01).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

from spx_butterfly.black_scholes import bs_d1_d2


def calc_greeks(
    option_type: str,
    s: float | np.ndarray,
    k: float | np.ndarray,
    t: float | np.ndarray,
    sigma: float | np.ndarray,
    r: float = 0.0,
    q: float = 0.0,
) -> dict[str, np.ndarray]:
    """Compute analytical Greeks for European options.

    Returns dictionary with:
    - delta: dPrice / dSpot
    - gamma: dDelta / dSpot
    - vega: per +1 vol point (Vega_dec * 0.01)
    - vega_dec: unscaled vega w.r.t decimal vol
    - volga: per (1 vol point)^2 (Volga_dec * 0.0001)
    - volga_dec: unscaled volga w.r.t decimal vol^2
    - theta_daily: 1-day time decay (theta_annual / 365)
    - theta_annual: annual time decay
    - vanna: dVega / dSpot per +1 vol point
    - rho: per +1% interest rate change
    """
    d1, d2 = bs_d1_d2(s, k, t, sigma, r, q)
    s_arr = np.asarray(s, dtype=float)
    k_arr = np.asarray(k, dtype=float)
    t_arr = np.asarray(t, dtype=float)
    sigma_arr = np.asarray(sigma, dtype=float)

    disc_r = np.exp(-r * t_arr)
    disc_q = np.exp(-q * t_arr)
    sqrt_t = np.sqrt(t_arr)
    pdf_d1 = norm.pdf(d1)

    # Decimal Greeks
    vega_dec = s_arr * disc_q * sqrt_t * pdf_d1
    volga_dec = vega_dec * (d1 * d2) / sigma_arr
    gamma = (disc_q * pdf_d1) / (s_arr * sigma_arr * sqrt_t)
    vanna_dec = -disc_q * pdf_d1 * (d2 / sigma_arr)

    op_type = str(option_type).lower().strip()
    if op_type in ("c", "call"):
        delta = disc_q * norm.cdf(d1)
        theta_annual = (
            -(s_arr * disc_q * pdf_d1 * sigma_arr) / (2.0 * sqrt_t)
            - r * k_arr * disc_r * norm.cdf(d2)
            + q * s_arr * disc_q * norm.cdf(d1)
        )
        rho_annual = k_arr * t_arr * disc_r * norm.cdf(d2)
    elif op_type in ("p", "put"):
        delta = -disc_q * norm.cdf(-d1)
        theta_annual = (
            -(s_arr * disc_q * pdf_d1 * sigma_arr) / (2.0 * sqrt_t)
            + r * k_arr * disc_r * norm.cdf(-d2)
            - q * s_arr * disc_q * norm.cdf(-d1)
        )
        rho_annual = -k_arr * t_arr * disc_r * norm.cdf(-d2)
    else:
        raise ValueError(f"Unknown option type: {option_type}")

    # Scaled Greeks for presentation & scenarios
    vega_pt = vega_dec * 0.01
    volga_pt2 = volga_dec * 0.0001
    theta_daily = theta_annual / 365.0
    vanna_pt = vanna_dec * 0.01
    rho_pt = rho_annual * 0.01

    return {
        "delta": delta,
        "gamma": gamma,
        "vega": vega_pt,
        "vega_dec": vega_dec,
        "volga": volga_pt2,
        "volga_dec": volga_dec,
        "theta_daily": theta_daily,
        "theta_annual": theta_annual,
        "vanna": vanna_pt,
        "vanna_dec": vanna_dec,
        "rho": rho_pt,
    }
