"""Fixed-strike butterfly spread construction and initial metrics calculation.

Every butterfly consists of:
- Long 1 lower-strike option (K - h)
- Short 2 middle-strike options (K)
- Long 1 upper-strike option (K + h)

Formula:
Fly(K) = P(K - h) - 2 * P(K) + P(K + h)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.greeks import calc_greeks


@dataclass
class ButterflySpread:
    """Represents a single fixed-strike butterfly spread."""

    date: str
    underlying: float
    atm_strike: float
    target_dte: float
    option_side: str  # 'call' or 'put'
    centre_strike: float
    lower_strike: float
    upper_strike: float
    wing_width: float

    # Contract level baseline values
    lower_iv: float
    middle_iv: float
    upper_iv: float

    lower_premium: float
    middle_premium: float
    upper_premium: float

    # Net butterfly metrics
    initial_fly_premium: float
    initial_iv_fly_dec: float
    initial_iv_fly_pct: float

    # Baseline Greeks
    initial_net_vega: float
    initial_net_volga: float
    initial_net_delta: float
    initial_net_gamma: float
    initial_net_theta: float
    initial_net_vanna: float
    initial_net_rho: float

    # Individual contract baseline Greeks dict
    lower_greeks: dict[str, float]
    middle_greeks: dict[str, float]
    upper_greeks: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "underlying": self.underlying,
            "atm_strike": self.atm_strike,
            "target_dte": self.target_dte,
            "option_side": self.option_side,
            "centre_strike": self.centre_strike,
            "lower_strike": self.lower_strike,
            "upper_strike": self.upper_strike,
            "wing_width": self.wing_width,
            "lower_iv": self.lower_iv,
            "middle_iv": self.middle_iv,
            "upper_iv": self.upper_iv,
            "lower_premium": self.lower_premium,
            "middle_premium": self.middle_premium,
            "upper_premium": self.upper_premium,
            "initial_fly_premium": self.initial_fly_premium,
            "initial_iv_fly_pct": self.initial_iv_fly_pct,
            "initial_net_vega": self.initial_net_vega,
            "initial_net_volga": self.initial_net_volga,
            "initial_net_delta": self.initial_net_delta,
            "initial_net_gamma": self.initial_net_gamma,
            "initial_net_theta": self.initial_net_theta,
            "initial_net_vanna": self.initial_net_vanna,
            "initial_net_rho": self.initial_net_rho,
        }


def build_butterflies_for_side(
    snapshot_df: pd.DataFrame,
    option_side: str,
    wing_width: float = 100.0,
    r: float = 0.0,
    q: float = 0.0,
) -> list[ButterflySpread]:
    """Construct butterfly spreads for a specific option side from a snapshot.

    Parameters
    ----------
    snapshot_df : pd.DataFrame
        Snapshot dataframe for a single date containing:
        date, underlying, atm_strike, target_dte, option_side, strike, iv_decimal, premium.
    option_side : {'call', 'put'}
        Option side to build flies for.
    wing_width : float, optional
        Wing spacing h, by default 100.0.
    r, q : float, optional
        Risk-free rate and dividend yield.

    Returns
    -------
    list[ButterflySpread]
        List of constructed butterfly spreads ordered by centre strike.
    """
    op_side = str(option_side).lower().strip()
    sub_df = snapshot_df[snapshot_df["option_side"] == op_side].copy()
    if sub_df.empty:
        return []

    # Map strike -> row
    strike_map = {row["strike"]: row for _, row in sub_df.iterrows()}
    available_strikes = sorted(strike_map.keys())

    date_val = str(sub_df["date"].iloc[0])
    s0 = float(sub_df["underlying"].iloc[0])
    atm0 = float(sub_df["atm_strike"].iloc[0])
    dte0 = float(sub_df["target_dte"].iloc[0])
    t0 = dte0 / 365.0

    flies: list[ButterflySpread] = []

    for k in available_strikes:
        k_lower = round(k - wing_width, 6)
        k_upper = round(k + wing_width, 6)

        # Check if all 3 strikes exist with floating tolerance
        lower_row = None
        upper_row = None
        for s_cand, row in strike_map.items():
            if abs(s_cand - k_lower) < 1e-4:
                lower_row = row
            if abs(s_cand - k_upper) < 1e-4:
                upper_row = row

        if lower_row is None or upper_row is None:
            continue

        mid_row = strike_map[k]

        p_lower = float(lower_row["premium"])
        p_mid = float(mid_row["premium"])
        p_upper = float(upper_row["premium"])

        iv_lower = float(lower_row["iv_decimal"])
        iv_mid = float(mid_row["iv_decimal"])
        iv_upper = float(upper_row["iv_decimal"])

        initial_fly_premium = p_lower - 2.0 * p_mid + p_upper
        initial_iv_fly_dec = iv_lower - 2.0 * iv_mid + iv_upper
        initial_iv_fly_pct = initial_iv_fly_dec * 100.0

        # Compute initial Greeks
        lower_greeks = calc_greeks(op_side, s0, k_lower, t0, iv_lower, r=r, q=q)
        mid_greeks = calc_greeks(op_side, s0, k, t0, iv_mid, r=r, q=q)
        upper_greeks = calc_greeks(op_side, s0, k_upper, t0, iv_upper, r=r, q=q)

        net_vega = lower_greeks["vega"] - 2.0 * mid_greeks["vega"] + upper_greeks["vega"]
        net_volga = lower_greeks["volga"] - 2.0 * mid_greeks["volga"] + upper_greeks["volga"]
        net_delta = lower_greeks["delta"] - 2.0 * mid_greeks["delta"] + upper_greeks["delta"]
        net_gamma = lower_greeks["gamma"] - 2.0 * mid_greeks["gamma"] + upper_greeks["gamma"]
        net_theta = lower_greeks["theta_daily"] - 2.0 * mid_greeks["theta_daily"] + upper_greeks["theta_daily"]
        net_vanna = lower_greeks["vanna"] - 2.0 * mid_greeks["vanna"] + upper_greeks["vanna"]
        net_rho = lower_greeks["rho"] - 2.0 * mid_greeks["rho"] + upper_greeks["rho"]

        fly = ButterflySpread(
            date=date_val,
            underlying=s0,
            atm_strike=atm0,
            target_dte=dte0,
            option_side=op_side,
            centre_strike=float(k),
            lower_strike=float(k_lower),
            upper_strike=float(k_upper),
            wing_width=float(wing_width),
            lower_iv=iv_lower,
            middle_iv=iv_mid,
            upper_iv=iv_upper,
            lower_premium=p_lower,
            middle_premium=p_mid,
            upper_premium=p_upper,
            initial_fly_premium=initial_fly_premium,
            initial_iv_fly_dec=initial_iv_fly_dec,
            initial_iv_fly_pct=initial_iv_fly_pct,
            initial_net_vega=net_vega,
            initial_net_volga=net_volga,
            initial_net_delta=net_delta,
            initial_net_gamma=net_gamma,
            initial_net_theta=net_theta,
            initial_net_vanna=net_vanna,
            initial_net_rho=net_rho,
            lower_greeks=lower_greeks,
            middle_greeks=mid_greeks,
            upper_greeks=upper_greeks,
        )
        flies.append(fly)

    return flies


def build_all_butterflies(
    snapshot_df: pd.DataFrame,
    wing_width: float = 100.0,
    r: float = 0.0,
    q: float = 0.0,
) -> dict[str, list[ButterflySpread]]:
    """Build all butterflies for both Call and Put sides."""
    return {
        "call": build_butterflies_for_side(snapshot_df, "call", wing_width, r=r, q=q),
        "put": build_butterflies_for_side(snapshot_df, "put", wing_width, r=r, q=q),
    }


def butterflies_to_dataframe(flies: list[ButterflySpread]) -> pd.DataFrame:
    """Convert a list of ButterflySpread objects to a pandas DataFrame."""
    if not flies:
        return pd.DataFrame()
    return pd.DataFrame([f.to_dict() for f in flies])
