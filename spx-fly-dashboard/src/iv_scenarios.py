"""Implied volatility shock models: Level, Skew, and Curvature.

Additive quadratic strike-space shock model:
    x = (K - OriginalATMStrike) / ReferenceWidth
    Shock(K) = Level + (Skew / 2) * x + Curvature * x^2
    NewIV(K) = OriginalIV(K) + Shock(K) / 100

Where Level, Skew, and Curvature are all measured in volatility percentage points,
and IVs are stored internally as decimals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np
import pandas as pd


@dataclass
class IVShiftScenario:
    """Represents a combined Level, Skew, and Curvature IV perturbation scenario.

    Parameters
    ----------
    level_vol_points : float
        Uniform level shift L in volatility percentage points (e.g. +2.0 = +2 pts).
    skew_vol_points : float
        Linear skew slope S in volatility percentage points (Right minus Left over 2*H).
    curvature_vol_points : float
        Quadratic curvature C in volatility percentage points (Wings average minus ATM).
    reference_width : float
        Reference strike distance H in SPX index points (default 500.0).
    atm_strike : float
        Selected date's ATM strike reference.
    """

    level_vol_points: float = 0.0
    skew_vol_points: float = 0.0
    curvature_vol_points: float = 0.0
    reference_width: float = 500.0
    atm_strike: float = 0.0
    shift_vol_points: float | None = None

    def __post_init__(self) -> None:
        if self.shift_vol_points is not None:
            self.level_vol_points = float(self.shift_vol_points)
        else:
            self.shift_vol_points = float(self.level_vol_points)

    @property
    def shift_decimal(self) -> float:
        """Alias for level shift in decimal units."""
        return self.level_vol_points / 100.0


def compute_normalized_strike(
    k: float | np.ndarray,
    atm_strike: float,
    reference_width: float = 500.0,
) -> float | np.ndarray:
    """Calculate linear normalized strike coordinate x = (K - K_ATM) / H.

    Parameters
    ----------
    k : float or array-like
        Option strike price(s).
    atm_strike : float
        Reference ATM strike price.
    reference_width : float
        Strike normalization distance H (default 500.0).

    Returns
    -------
    float or np.ndarray
        Normalized strike coordinate x.
    """
    if reference_width <= 0:
        raise ValueError("Reference width H must be strictly positive.")
    return (np.asarray(k, dtype=float) - float(atm_strike)) / float(reference_width)


def compute_level_shock(
    level: float,
    n_strikes: int | None = None,
) -> float | np.ndarray:
    """Compute constant level shock component (in vol points)."""
    if n_strikes is None:
        return float(level)
    return np.full(n_strikes, float(level), dtype=float)


def compute_skew_shock(
    skew: float,
    x: float | np.ndarray,
) -> float | np.ndarray:
    """Compute linear skew shock component: (S / 2) * x (in vol points)."""
    return (float(skew) / 2.0) * np.asarray(x, dtype=float)


def compute_curvature_shock(
    curvature: float,
    x: float | np.ndarray,
) -> float | np.ndarray:
    """Compute quadratic curvature shock component: C * x^2 (in vol points)."""
    x_arr = np.asarray(x, dtype=float)
    return float(curvature) * (x_arr ** 2)


def compute_total_iv_shock(
    level: float,
    skew: float,
    curvature: float,
    x: float | np.ndarray,
) -> float | np.ndarray:
    """Compute total IV shock: Shock(x) = L + (S/2)*x + C*x^2 (in vol points)."""
    return (
        compute_level_shock(level)
        + compute_skew_shock(skew, x)
        + compute_curvature_shock(curvature, x)
    )


def compute_strike_iv_shock(
    k: float | np.ndarray,
    scenario: IVShiftScenario,
) -> tuple[float | np.ndarray, dict[str, float | np.ndarray]]:
    """Compute total shock and individual factor contributions for given strike(s).

    Returns
    -------
    tuple[total_shock_pts, dict_of_components]
        Components dict contains 'level', 'skew', 'curvature', 'total', 'x'.
    """
    x = compute_normalized_strike(k, scenario.atm_strike, scenario.reference_width)
    lvl = compute_level_shock(scenario.level_vol_points)
    skw = compute_skew_shock(scenario.skew_vol_points, x)
    crv = compute_curvature_shock(scenario.curvature_vol_points, x)
    tot = lvl + skw + crv
    components = {
        "x": x,
        "level": lvl,
        "skew": skw,
        "curvature": crv,
        "total": tot,
    }
    return tot, components


def apply_iv_scenario(
    original_iv: float | np.ndarray,
    k: float | np.ndarray,
    scenario: IVShiftScenario,
) -> float | np.ndarray:
    """Apply the combined additive quadratic IV shock to baseline IV(s).

    NewIV(K) = OriginalIV(K) + Shock(K) / 100.0
    """
    total_shock_pts, _ = compute_strike_iv_shock(k, scenario)
    shock_decimal = total_shock_pts / 100.0
    return np.asarray(original_iv, dtype=float) + shock_decimal


def apply_iv_shift(
    baseline_iv: float,
    shift_scenario: IVShiftScenario,
    k: float | None = None,
) -> float:
    """Calculate shocked IV from baseline IV and scenario.

    Maintains backward compatibility if strike k is omitted (assumes level-only if k is None).
    """
    if k is None:
        return float(baseline_iv + shift_scenario.shift_decimal)
    return float(apply_iv_scenario(baseline_iv, k, shift_scenario))


def validate_iv_shift(
    baseline_ivs: list[float] | pd.Series | np.ndarray,
    shift_scenario: IVShiftScenario,
    strikes: list[float] | pd.Series | np.ndarray | None = None,
) -> tuple[bool, str | None]:
    """Validate whether applying the shock scenario results in strictly positive IVs.

    Never silently clamps invalid IVs.

    Returns
    -------
    tuple[bool, str | None]
        (is_valid, error_message_or_none)
    """
    iv_arr = np.asarray(baseline_ivs, dtype=float)
    if len(iv_arr) == 0:
        return True, None

    if strikes is not None:
        k_arr = np.asarray(strikes, dtype=float)
        shocked_ivs = apply_iv_scenario(iv_arr, k_arr, shift_scenario)
        invalid_mask = shocked_ivs <= 0
        if np.any(invalid_mask):
            bad_strikes = k_arr[invalid_mask]
            bad_vols = shocked_ivs[invalid_mask] * 100.0
            msg = (
                f"Invalid scenario: shock produces non-positive IVs for strikes: "
                f"{[f'{k:.0f} ({v:.2f}%)' for k, v in zip(bad_strikes[:5], bad_vols[:5])]}. "
                f"Implied volatility must remain strictly positive across all strikes."
            )
            return False, msg
    else:
        # Fallback to level-only check
        shift_dec = shift_scenario.shift_decimal
        min_shocked_iv = np.min(iv_arr) + shift_dec
        if min_shocked_iv <= 0:
            msg = (
                f"Invalid IV shock: a level shift of {shift_scenario.level_vol_points:+.2f} vol points "
                f"produces non-positive IVs (min shocked IV = {min_shocked_iv * 100.0:.2f}%)."
            )
            return False, msg

    return True, None


def check_static_arbitrage(
    strikes: np.ndarray | list[float],
    call_prices: np.ndarray | list[float],
    put_prices: np.ndarray | list[float],
) -> dict[str, Any]:
    """Examine option prices across strikes for static arbitrage violations.

    Checks:
    1. Call price monotonicity: C(K1) >= C(K2) for K1 < K2
    2. Put price monotonicity: P(K1) <= P(K2) for K1 < K2
    3. Convexity (Butterfly arbitrage): discrete second difference >= 0
    """
    k = np.asarray(strikes, dtype=float)
    sort_idx = np.argsort(k)
    k_sorted = k[sort_idx]
    c_sorted = np.asarray(call_prices, dtype=float)[sort_idx]
    p_sorted = np.asarray(put_prices, dtype=float)[sort_idx]

    call_mono_violations = []
    put_mono_violations = []
    call_convex_violations = []
    put_convex_violations = []

    # 1. Monotonicity checks
    for i in range(len(k_sorted) - 1):
        if c_sorted[i] < c_sorted[i + 1] - 1e-6:
            call_mono_violations.append((k_sorted[i], k_sorted[i + 1]))
        if p_sorted[i] > p_sorted[i + 1] + 1e-6:
            put_mono_violations.append((k_sorted[i], k_sorted[i + 1]))

    # 2. Convexity checks (Butterfly spread >= 0)
    for i in range(1, len(k_sorted) - 1):
        k_prev, k_curr, k_next = k_sorted[i - 1], k_sorted[i], k_sorted[i + 1]
        h1 = k_curr - k_prev
        h2 = k_next - k_curr
        # Slope test
        c_slope1 = (c_sorted[i] - c_sorted[i - 1]) / h1
        c_slope2 = (c_sorted[i + 1] - c_sorted[i]) / h2
        if c_slope2 < c_slope1 - 1e-5:
            call_convex_violations.append(k_curr)

        p_slope1 = (p_sorted[i] - p_sorted[i - 1]) / h1
        p_slope2 = (p_sorted[i + 1] - p_sorted[i]) / h2
        if p_slope2 < p_slope1 - 1e-5:
            put_convex_violations.append(k_curr)

    is_arbitrage_free = (
        len(call_mono_violations) == 0
        and len(put_mono_violations) == 0
        and len(call_convex_violations) == 0
        and len(put_convex_violations) == 0
    )

    return {
        "is_arbitrage_free": is_arbitrage_free,
        "call_monotonicity_violations": call_mono_violations,
        "put_monotonicity_violations": put_mono_violations,
        "call_convexity_violations": call_convex_violations,
        "put_convexity_violations": put_convex_violations,
    }
