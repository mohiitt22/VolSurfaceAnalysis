"""Black-Scholes-Merton option pricing model implementation.

Supports European calls and puts with continuous dividend yield.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm


def bs_d1_d2(
    s: float | np.ndarray,
    k: float | np.ndarray,
    t: float | np.ndarray,
    sigma: float | np.ndarray,
    r: float = 0.0,
    q: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Calculate Black-Scholes d1 and d2.

    Parameters
    ----------
    s : float or array-like
        Underlying spot price.
    k : float or array-like
        Option strike price.
    t : float or array-like
        Time to maturity in years.
    sigma : float or array-like
        Implied volatility in decimal form (e.g., 0.15 for 15%).
    r : float, optional
        Continuously compounded risk-free rate, by default 0.0.
    q : float, optional
        Continuous dividend yield, by default 0.0.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        (d1, d2) arrays.
    """
    s_arr = np.asarray(s, dtype=float)
    k_arr = np.asarray(k, dtype=float)
    t_arr = np.asarray(t, dtype=float)
    sigma_arr = np.asarray(sigma, dtype=float)

    if np.any(sigma_arr <= 0):
        raise ValueError("Implied volatility must be strictly positive.")
    if np.any(t_arr <= 0):
        raise ValueError("Time to maturity must be strictly positive.")
    if np.any(s_arr <= 0) or np.any(k_arr <= 0):
        raise ValueError("Spot and strike must be strictly positive.")

    vol_sqrt_t = sigma_arr * np.sqrt(t_arr)
    d1 = (np.log(s_arr / k_arr) + (r - q + 0.5 * sigma_arr**2) * t_arr) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return d1, d2


def bs_price(
    option_type: str,
    s: float | np.ndarray,
    k: float | np.ndarray,
    t: float | np.ndarray,
    sigma: float | np.ndarray,
    r: float = 0.0,
    q: float = 0.0,
) -> np.ndarray:
    """Calculate Black-Scholes European option price.

    Parameters
    ----------
    option_type : {'call', 'put'}
        Option type.
    s, k, t, sigma, r, q : parameters as in `bs_d1_d2`.

    Returns
    -------
    np.ndarray
        Option price(s).
    """
    d1, d2 = bs_d1_d2(s, k, t, sigma, r, q)
    s_arr = np.asarray(s, dtype=float)
    k_arr = np.asarray(k, dtype=float)
    t_arr = np.asarray(t, dtype=float)

    disc_r = np.exp(-r * t_arr)
    disc_q = np.exp(-q * t_arr)

    op_type = str(option_type).lower().strip()
    if op_type in ("c", "call"):
        price = s_arr * disc_q * norm.cdf(d1) - k_arr * disc_r * norm.cdf(d2)
    elif op_type in ("p", "put"):
        price = k_arr * disc_r * norm.cdf(-d2) - s_arr * disc_q * norm.cdf(-d1)
    else:
        raise ValueError(f"Unknown option type: {option_type}. Must be 'call' or 'put'.")

    return np.maximum(price, 0.0)
