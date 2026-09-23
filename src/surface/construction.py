"""Build a single-expiry 60-DTE surface slice.

Assumptions documented from the data (not guessed):

* `rate` is identically 0.0 in every file.  Using F = S * exp(r T)
  would therefore yield F = S, but put-call parity shows a systematic
  carry: C - P ≈ F - K is *not* equal to S - K (gap ~30-40 index points
  at ~57 DTE on 2025-06-05).  Underlying is therefore treated as spot,
  and the forward is inferred from put-call parity near ATM:

      F = median_i ( K_i + (C_i - P_i) )     since r = 0 ⇒ DF = 1

* IV is a decimal (0.16 = 16%), never a percentage.
* `put_delta` is unsigned until 2026-07-15 inclusive and signed
  (negative) from 2026-07-16.  We always work with abs(put_delta).
* `atm` is an integer strike-offset (0 = closest listed strike), not a
  boolean ATM flag.
* No dividend field exists.  Event calendars are not in the files.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.settings import DEFAULT, ResearchConfig
from src.surface.black_scholes import implied_vol


@dataclass(frozen=True)
class SurfaceAssumptions:
    underlying_is_spot: bool
    forward_source: str
    rate_used: float
    put_delta_sign_convention: str
    iv_units: str
    t_year_fraction: float


def _put_delta_abs(put_delta: np.ndarray) -> np.ndarray:
    return np.abs(put_delta.astype(float))


def infer_forward(slice_df: pd.DataFrame, cfg: ResearchConfig) -> tuple[float, str]:
    """PCP-implied forward, falling back to spot only if PCP is unusable."""
    work = slice_df.copy()
    if "atm" in work.columns:
        near = work.loc[work["atm"].abs() <= cfg.atm_neighborhood]
        if len(near) < 3:
            near = work
    else:
        near = work
    implied = near["strike"] + near["call_price"] - near["put_price"]
    implied = implied[np.isfinite(implied) & (implied > 0)]
    spot = float(work["underlying"].median())
    if len(implied) >= 3:
        fwd = float(implied.median())
        # Guard against garbage PCP (e.g. crossed prices).
        if 0.8 * spot < fwd < 1.2 * spot:
            return fwd, "put_call_parity_atm_median"
    return spot, "spot_fallback_rate_zero"


def reconstruct_iv_subset(slice_df: pd.DataFrame, F: float, T: float) -> pd.DataFrame:
    """Independently invert BS IV for OTM legs; compare to vendor IV."""
    rec_call = []
    rec_put = []
    for row in slice_df.itertuples(index=False):
        rec_call.append(
            implied_vol(float(row.call_price), F, float(row.strike), T, "C", df=1.0)
        )
        rec_put.append(
            implied_vol(float(row.put_price), F, float(row.strike), T, "P", df=1.0)
        )
    out = slice_df.copy()
    out["recon_call_iv"] = rec_call
    out["recon_put_iv"] = rec_put
    out["call_iv_diff"] = out["call_iv"] - out["recon_call_iv"]
    out["put_iv_diff"] = out["put_iv"] - out["recon_put_iv"]
    return out


def build_surface_slice(
    slice_df: pd.DataFrame,
    actual_dte: int,
    cfg: ResearchConfig | None = None,
    reconstruct_iv: bool = False,
) -> tuple[pd.DataFrame, SurfaceAssumptions]:
    cfg = cfg or DEFAULT
    if slice_df.empty:
        raise ValueError("empty slice")

    T = actual_dte / float(cfg.day_count)
    F, fwd_src = infer_forward(slice_df, cfg)
    S = float(slice_df["underlying"].median())
    r = float(slice_df["rate"].median()) if "rate" in slice_df.columns else 0.0

    out = slice_df.copy()
    out["spot"] = S
    out["forward"] = F
    out["T"] = T
    out["actual_dte"] = actual_dte
    out["target_dte"] = cfg.target_dte
    out["dte_error"] = actual_dte - cfg.target_dte
    out["abs_dte_error"] = abs(actual_dte - cfg.target_dte)
    out["k"] = np.log(out["strike"] / F)
    out["log_moneyness"] = out["k"]
    out["K_over_S"] = out["strike"] / S
    out["K_over_F"] = out["strike"] / F

    out["put_delta_abs"] = _put_delta_abs(out["put_delta"].to_numpy())
    out["call_delta_abs"] = out["call_delta"].abs()
    # Standardized delta used for the surface: 0.5 ~ ATM, <0.5 OTM put side
    # uses put_delta_abs, OTM call side uses call_delta.
    out["delta_put_side"] = out["put_delta_abs"]
    out["delta_call_side"] = out["call_delta_abs"]

    # OTM IV rule: K < F use put, K > F use call, near ATM blend.
    otm = np.where(out["strike"] < F, out["put_iv"], out["call_iv"])
    near = np.abs(out["k"]) < 0.01
    blend = 0.5 * (out["call_iv"] + out["put_iv"])
    out["market_iv"] = np.where(near, blend, otm)
    # If chosen IV is invalid, fall back to the other side.
    bad = ~np.isfinite(out["market_iv"]) | (out["market_iv"] <= cfg.iv_min) | (
        out["market_iv"] > cfg.iv_max
    )
    alt = np.where(out["strike"] < F, out["call_iv"], out["put_iv"])
    out.loc[bad, "market_iv"] = alt[bad]
    out["total_variance"] = (out["market_iv"] ** 2) * T
    out["call_put_iv_abs_diff"] = (out["call_iv"] - out["put_iv"]).abs()
    out["vega"] = 0.5 * (out["call_vega"] + out["put_vega"])
    out["gamma"] = 0.5 * (out["call_gamma"] + out["put_gamma"])
    out["theta"] = 0.5 * (out["call_theta"] + out["put_theta"])

    # Liquidity proxy in the absence of volume / OI / bid-ask:
    # vega * (1 / (1 + |k|)) * indicator of reasonable call-put IV gap.
    gap = out["call_put_iv_abs_diff"].clip(lower=0)
    out["liquidity_score"] = (
        (out["vega"] / (out["vega"].max() + 1e-9))
        * (1.0 / (1.0 + out["k"].abs()))
        * (1.0 / (1.0 + 20.0 * gap))
    )
    out["liquidity_bucket"] = pd.cut(
        out["liquidity_score"],
        bins=[-np.inf, 0.15, 0.40, np.inf],
        labels=["low", "medium", "high"],
    )

    if reconstruct_iv:
        out = reconstruct_iv_subset(out, F, T)

    # Drop remaining unusable market_iv rows but keep them flagged.
    usable = (
        np.isfinite(out["market_iv"])
        & (out["market_iv"] >= cfg.iv_min)
        & (out["market_iv"] <= cfg.iv_max)
        & np.isfinite(out["k"])
        & np.isfinite(out["total_variance"])
        & (out["total_variance"] > 0)
    )
    out["usable"] = usable

    put_signed_frac = float((slice_df["put_delta"] < 0).mean())
    assumptions = SurfaceAssumptions(
        underlying_is_spot=True,
        forward_source=fwd_src,
        rate_used=r,
        put_delta_sign_convention=(
            "signed_negative" if put_signed_frac > 0.5 else "unsigned_positive"
        ),
        iv_units="decimal",
        t_year_fraction=T,
    )
    return out.sort_values("strike").reset_index(drop=True), assumptions
