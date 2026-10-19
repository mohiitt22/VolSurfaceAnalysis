"""Butterfly spread repricing under IV shift scenarios.

Supports:
1. Baseline-Preserving Repricing (Default):
   ShockedPremium = OriginalPremium + [BS(ShockedIV) - BS(OriginalIV)]
2. Full Black-Scholes Repricing:
   ShockedPremium = BS(ShockedIV)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from spx_butterfly.black_scholes import bs_price
from spx_butterfly.fly_builder import ButterflySpread
from spx_butterfly.greeks import calc_greeks
from spx_butterfly.iv_scenarios import (
    IVShiftScenario,
    apply_iv_shift,
    compute_strike_iv_shock,
)


@dataclass
class RepricedButterfly:
    """Stores repriced butterfly spread outputs under an IV scenario."""

    fly: ButterflySpread
    scenario: IVShiftScenario
    pricing_mode: str  # 'baseline_delta' or 'full_bs'

    # Shocked IVs
    lower_shocked_iv: float
    middle_shocked_iv: float
    upper_shocked_iv: float

    # Shocked option premiums
    lower_shocked_premium: float
    middle_shocked_premium: float
    upper_shocked_premium: float

    # Shocked fly metrics
    shocked_fly_premium: float
    fly_premium_change: float
    shocked_iv_fly_pct: float

    # Shocked Greeks
    shocked_net_vega: float
    shocked_net_volga: float
    shocked_net_delta: float
    shocked_net_gamma: float
    shocked_net_theta: float
    shocked_net_vanna: float
    shocked_net_rho: float

    # Factor-specific sensitivities (Part H)
    level_exposure: float = 0.0
    skew_exposure: float = 0.0
    curvature_exposure: float = 0.0
    first_order_change: float = 0.0

    # Sequential attribution: Level -> Skew -> Curvature (Part I)
    level_effect: float = 0.0
    skew_effect: float = 0.0
    curvature_effect: float = 0.0

    # Shapley attribution (averaged across all 6 permutations) (Part I)
    shapley_level: float = 0.0
    shapley_skew: float = 0.0
    shapley_curvature: float = 0.0

    # Classic vega attribution metrics (backward compatibility)
    vega_estimate: float = 0.0
    vega_volga_estimate: float = 0.0
    exact_change: float = 0.0
    nonlinear_residual: float = 0.0

    # Individual contract shocked Greeks
    lower_shocked_greeks: dict[str, float] | None = None
    middle_shocked_greeks: dict[str, float] | None = None
    upper_shocked_greeks: dict[str, float] | None = None

    # Leg-level factor shock details
    lower_shock_details: dict[str, Any] | None = None
    middle_shock_details: dict[str, Any] | None = None
    upper_shock_details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.fly.date,
            "underlying": self.fly.underlying,
            "atm_strike": self.fly.atm_strike,
            "target_dte": self.fly.target_dte,
            "option_side": self.fly.option_side,
            "centre_strike": self.fly.centre_strike,
            "lower_strike": self.fly.lower_strike,
            "upper_strike": self.fly.upper_strike,
            "wing_width": self.fly.wing_width,
            "shift_vol_points": self.scenario.shift_vol_points,
            "level_vol_points": self.scenario.level_vol_points,
            "skew_vol_points": self.scenario.skew_vol_points,
            "curvature_vol_points": self.scenario.curvature_vol_points,
            "reference_width": self.scenario.reference_width,
            "pricing_mode": self.pricing_mode,
            # Baseline & Shocked Premiums
            "initial_fly_premium": self.fly.initial_fly_premium,
            "shocked_fly_premium": self.shocked_fly_premium,
            "fly_premium_change": self.fly_premium_change,
            # IV Fly
            "initial_iv_fly_pct": self.fly.initial_iv_fly_pct,
            "shocked_iv_fly_pct": self.shocked_iv_fly_pct,
            "change_in_iv_fly_pct": self.shocked_iv_fly_pct - self.fly.initial_iv_fly_pct,
            # Factor Exposures
            "level_exposure": self.level_exposure,
            "skew_exposure": self.skew_exposure,
            "curvature_exposure": self.curvature_exposure,
            "first_order_change": self.first_order_change,
            # Sequential Attribution
            "level_effect": self.level_effect,
            "skew_effect": self.skew_effect,
            "curvature_effect": self.curvature_effect,
            # Shapley Attribution
            "shapley_level": self.shapley_level,
            "shapley_skew": self.shapley_skew,
            "shapley_curvature": self.shapley_curvature,
            # Net Greeks
            "initial_net_vega": self.fly.initial_net_vega,
            "shocked_net_vega": self.shocked_net_vega,
            "initial_net_volga": self.fly.initial_net_volga,
            "shocked_net_volga": self.shocked_net_volga,
            "initial_net_delta": self.fly.initial_net_delta,
            "shocked_net_delta": self.shocked_net_delta,
            "initial_net_gamma": self.fly.initial_net_gamma,
            "shocked_net_gamma": self.shocked_net_gamma,
            "initial_net_theta": self.fly.initial_net_theta,
            "shocked_net_theta": self.shocked_net_theta,
            "initial_net_vanna": self.fly.initial_net_vanna,
            "shocked_net_vanna": self.shocked_net_vanna,
            # Classic attribution
            "vega_estimate": self.vega_estimate,
            "vega_volga_estimate": self.vega_volga_estimate,
            "exact_change": self.exact_change,
            "nonlinear_residual": self.nonlinear_residual,
        }


def reprice_single_option(
    option_type: str,
    s: float,
    k: float,
    t: float,
    orig_iv: float,
    shocked_iv: float,
    orig_premium: float,
    pricing_mode: str = "baseline_delta",
    r: float = 0.0,
    q: float = 0.0,
) -> float:
    """Reprice a single option contract under an IV shift."""
    if pricing_mode == "full_bs":
        return float(bs_price(option_type, s, k, t, shocked_iv, r=r, q=q))

    # Baseline delta mode: P_shocked = P_orig + [BS(shocked) - BS(orig)]
    bs_orig = float(bs_price(option_type, s, k, t, orig_iv, r=r, q=q))
    bs_shocked = float(bs_price(option_type, s, k, t, shocked_iv, r=r, q=q))
    shocked_premium = orig_premium + (bs_shocked - bs_orig)
    return float(max(shocked_premium, 0.0))


def reprice_butterfly(
    fly: ButterflySpread,
    scenario: IVShiftScenario,
    pricing_mode: str = "baseline_delta",
    r: float = 0.0,
    q: float = 0.0,
) -> RepricedButterfly:
    """Reprice a butterfly spread under a Level, Skew, and Curvature IV scenario."""
    s = fly.underlying
    t = fly.target_dte / 365.0
    side = fly.option_side

    # Ensure ATM strike is anchored to selected date's baseline
    atm_ref = scenario.atm_strike if scenario.atm_strike > 0 else fly.atm_strike
    scen_atm = IVShiftScenario(
        level_vol_points=scenario.level_vol_points,
        skew_vol_points=scenario.skew_vol_points,
        curvature_vol_points=scenario.curvature_vol_points,
        reference_width=scenario.reference_width,
        atm_strike=atm_ref,
    )

    # 1. Calculate shocked IVs with leg-specific strike coordinates
    lower_shocked_iv = apply_iv_shift(fly.lower_iv, scen_atm, k=fly.lower_strike)
    mid_shocked_iv = apply_iv_shift(fly.middle_iv, scen_atm, k=fly.centre_strike)
    upper_shocked_iv = apply_iv_shift(fly.upper_iv, scen_atm, k=fly.upper_strike)

    # Leg-level factor shock details
    _, lower_shock_details = compute_strike_iv_shock(fly.lower_strike, scen_atm)
    _, mid_shock_details = compute_strike_iv_shock(fly.centre_strike, scen_atm)
    _, upper_shock_details = compute_strike_iv_shock(fly.upper_strike, scen_atm)

    # 2. Reprice individual legs
    p_lower_shocked = reprice_single_option(
        side, s, fly.lower_strike, t, fly.lower_iv, lower_shocked_iv, fly.lower_premium,
        pricing_mode=pricing_mode, r=r, q=q,
    )
    p_mid_shocked = reprice_single_option(
        side, s, fly.centre_strike, t, fly.middle_iv, mid_shocked_iv, fly.middle_premium,
        pricing_mode=pricing_mode, r=r, q=q,
    )
    p_upper_shocked = reprice_single_option(
        side, s, fly.upper_strike, t, fly.upper_iv, upper_shocked_iv, fly.upper_premium,
        pricing_mode=pricing_mode, r=r, q=q,
    )

    # 3. New Fly Premium & change
    shocked_fly_premium = p_lower_shocked - 2.0 * p_mid_shocked + p_upper_shocked
    fly_premium_change = shocked_fly_premium - fly.initial_fly_premium

    # 4. Shocked IV Fly Curvature
    shocked_iv_fly_dec = lower_shocked_iv - 2.0 * mid_shocked_iv + upper_shocked_iv
    shocked_iv_fly_pct = shocked_iv_fly_dec * 100.0

    # 5. Shocked Greeks
    g_lower_shocked = calc_greeks(side, s, fly.lower_strike, t, lower_shocked_iv, r=r, q=q)
    g_mid_shocked = calc_greeks(side, s, fly.centre_strike, t, mid_shocked_iv, r=r, q=q)
    g_upper_shocked = calc_greeks(side, s, fly.upper_strike, t, upper_shocked_iv, r=r, q=q)

    shocked_net_vega = g_lower_shocked["vega"] - 2.0 * g_mid_shocked["vega"] + g_upper_shocked["vega"]
    shocked_net_volga = g_lower_shocked["volga"] - 2.0 * g_mid_shocked["volga"] + g_upper_shocked["volga"]
    shocked_net_delta = g_lower_shocked["delta"] - 2.0 * g_mid_shocked["delta"] + g_upper_shocked["delta"]
    shocked_net_gamma = g_lower_shocked["gamma"] - 2.0 * g_mid_shocked["gamma"] + g_upper_shocked["gamma"]
    shocked_net_theta = g_lower_shocked["theta_daily"] - 2.0 * g_mid_shocked["theta_daily"] + g_upper_shocked["theta_daily"]
    shocked_net_vanna = g_lower_shocked["vanna"] - 2.0 * g_mid_shocked["vanna"] + g_upper_shocked["vanna"]
    shocked_net_rho = g_lower_shocked["rho"] - 2.0 * g_mid_shocked["rho"] + g_upper_shocked["rho"]

    # 6. Factor-Specific Sensitivities (Part H)
    x_low = float(lower_shock_details["x"])
    x_mid = float(mid_shock_details["x"])
    x_upp = float(upper_shock_details["x"])

    v_low = float(fly.lower_greeks["vega"])
    v_mid = float(fly.middle_greeks["vega"])
    v_upp = float(fly.upper_greeks["vega"])

    level_exposure = v_low - 2.0 * v_mid + v_upp
    skew_exposure = v_low * (x_low / 2.0) - 2.0 * v_mid * (x_mid / 2.0) + v_upp * (x_upp / 2.0)
    curvature_exposure = v_low * (x_low ** 2) - 2.0 * v_mid * (x_mid ** 2) + v_upp * (x_upp ** 2)

    L = scen_atm.level_vol_points
    S = scen_atm.skew_vol_points
    C = scen_atm.curvature_vol_points

    first_order_change = L * level_exposure + S * skew_exposure + C * curvature_exposure
    exact_change = fly_premium_change
    nonlinear_residual = exact_change - first_order_change

    # 7. Exact Sequential Factor Attribution: Level -> Skew -> Curvature (Part I)
    def eval_fly_shocks(d_low: float, d_mid: float, d_upp: float) -> float:
        iv_l = fly.lower_iv + d_low / 100.0
        iv_m = fly.middle_iv + d_mid / 100.0
        iv_u = fly.upper_iv + d_upp / 100.0
        pl = reprice_single_option(side, s, fly.lower_strike, t, fly.lower_iv, iv_l, fly.lower_premium, pricing_mode=pricing_mode, r=r, q=q)
        pm = reprice_single_option(side, s, fly.centre_strike, t, fly.middle_iv, iv_m, fly.middle_premium, pricing_mode=pricing_mode, r=r, q=q)
        pu = reprice_single_option(side, s, fly.upper_strike, t, fly.upper_iv, iv_u, fly.upper_premium, pricing_mode=pricing_mode, r=r, q=q)
        return pl - 2.0 * pm + pu

    f_0 = fly.initial_fly_premium
    # Level only
    f_l = eval_fly_shocks(L, L, L)
    # Level + Skew
    skw_l = (S / 2.0) * x_low
    skw_m = (S / 2.0) * x_mid
    skw_u = (S / 2.0) * x_upp
    f_ls = eval_fly_shocks(L + skw_l, L + skw_m, L + skw_u)
    # Level + Skew + Curvature
    f_lsc = shocked_fly_premium

    level_effect = f_l - f_0
    skew_effect = f_ls - f_l
    curvature_effect = f_lsc - f_ls

    # 8. Shapley Attribution (Averaged across 6 permutations) (Part I)
    crv_l = C * (x_low ** 2)
    crv_m = C * (x_mid ** 2)
    crv_u = C * (x_upp ** 2)

    v_0 = f_0
    v_L = f_l
    v_S = eval_fly_shocks(skw_l, skw_m, skw_u)
    v_C = eval_fly_shocks(crv_l, crv_m, crv_u)
    v_LS = f_ls
    v_LC = eval_fly_shocks(L + crv_l, L + crv_m, L + crv_u)
    v_SC = eval_fly_shocks(skw_l + crv_l, skw_m + crv_m, skw_u + crv_u)
    v_LSC = f_lsc

    # Permutations:
    # 1: L, S, C
    dL1 = v_L - v_0
    dS1 = v_LS - v_L
    dC1 = v_LSC - v_LS
    # 2: L, C, S
    dL2 = v_L - v_0
    dC2 = v_LC - v_L
    dS2 = v_LSC - v_LC
    # 3: S, L, C
    dS3 = v_S - v_0
    dL3 = v_LS - v_S
    dC3 = v_LSC - v_LS
    # 4: S, C, L
    dS4 = v_S - v_0
    dC4 = v_SC - v_S
    dL4 = v_LSC - v_SC
    # 5: C, L, S
    dC5 = v_C - v_0
    dL5 = v_LC - v_C
    dS5 = v_LSC - v_LC
    # 6: C, S, L
    dC6 = v_C - v_0
    dS6 = v_SC - v_C
    dL6 = v_LSC - v_SC

    shapley_level = (dL1 + dL2 + dL3 + dL4 + dL5 + dL6) / 6.0
    shapley_skew = (dS1 + dS2 + dS3 + dS4 + dS5 + dS6) / 6.0
    shapley_curvature = (dC1 + dC2 + dC3 + dC4 + dC5 + dC6) / 6.0

    # Legacy estimates for backward compatibility
    shift_pts = scen_atm.level_vol_points
    vega_estimate = fly.initial_net_vega * shift_pts
    vega_volga_estimate = (
        fly.initial_net_vega * shift_pts + 0.5 * fly.initial_net_volga * (shift_pts ** 2)
    )

    return RepricedButterfly(
        fly=fly,
        scenario=scenario,
        pricing_mode=pricing_mode,
        lower_shocked_iv=lower_shocked_iv,
        middle_shocked_iv=mid_shocked_iv,
        upper_shocked_iv=upper_shocked_iv,
        lower_shocked_premium=p_lower_shocked,
        middle_shocked_premium=p_mid_shocked,
        upper_shocked_premium=p_upper_shocked,
        shocked_fly_premium=shocked_fly_premium,
        fly_premium_change=fly_premium_change,
        shocked_iv_fly_pct=shocked_iv_fly_pct,
        shocked_net_vega=shocked_net_vega,
        shocked_net_volga=shocked_net_volga,
        shocked_net_delta=shocked_net_delta,
        shocked_net_gamma=shocked_net_gamma,
        shocked_net_theta=shocked_net_theta,
        shocked_net_vanna=shocked_net_vanna,
        shocked_net_rho=shocked_net_rho,
        level_exposure=level_exposure,
        skew_exposure=skew_exposure,
        curvature_exposure=curvature_exposure,
        first_order_change=first_order_change,
        level_effect=level_effect,
        skew_effect=skew_effect,
        curvature_effect=curvature_effect,
        shapley_level=shapley_level,
        shapley_skew=shapley_skew,
        shapley_curvature=shapley_curvature,
        vega_estimate=vega_estimate,
        vega_volga_estimate=vega_volga_estimate,
        exact_change=exact_change,
        nonlinear_residual=nonlinear_residual,
        lower_shocked_greeks=g_lower_shocked,
        middle_shocked_greeks=g_mid_shocked,
        upper_shocked_greeks=g_upper_shocked,
        lower_shock_details=lower_shock_details,
        middle_shock_details=mid_shock_details,
        upper_shock_details=upper_shock_details,
    )


def reprice_all_butterflies(
    flies: list[ButterflySpread],
    scenario: IVShiftScenario,
    pricing_mode: str = "baseline_delta",
    r: float = 0.0,
    q: float = 0.0,
) -> list[RepricedButterfly]:
    """Reprice a list of butterfly spreads under an IV scenario."""
    return [
        reprice_butterfly(f, scenario, pricing_mode=pricing_mode, r=r, q=q)
        for f in flies
    ]


def repriced_butterflies_to_dataframe(
    repriced_flies: list[RepricedButterfly],
) -> pd.DataFrame:
    """Convert repriced butterflies list to pandas DataFrame."""
    if not repriced_flies:
        return pd.DataFrame()
    return pd.DataFrame([rf.to_dict() for rf in repriced_flies])
