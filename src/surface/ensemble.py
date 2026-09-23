"""Fit all slice models and form a robust ensemble.

Default ensemble = median of available model IVs.
A large residual with *low* model dispersion is more interesting than a
large residual where models disagree.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.settings import ResearchConfig, DEFAULT
from src.sabr.sabr import fit_sabr, sabr_iv
from src.ssvi.ssvi import fit_ssvi, ssvi_total_variance
from src.svi.svi import fit_svi, svi_iv
from src.surface.polynomial import fit_polynomial, poly_total_variance
from src.surface.spline import fit_spline, spline_iv


MODEL_COLS = ("polynomial", "spline", "svi", "ssvi", "sabr")


@dataclass
class DayFits:
    poly: object
    spline: object
    svi: object
    ssvi: object
    sabr: object


def _weights(surface: pd.DataFrame, scheme: str) -> np.ndarray:
    if scheme == "equal":
        return np.ones(len(surface))
    if scheme == "vega":
        return np.clip(surface["vega"].to_numpy(dtype=float), 0, None)
    if scheme == "liquidity":
        return np.clip(surface["liquidity_score"].to_numpy(dtype=float), 0, None)
    if scheme == "hybrid":
        return np.clip(
            surface["vega"].to_numpy(dtype=float)
            * surface["liquidity_score"].to_numpy(dtype=float),
            0,
            None,
        )
    raise ValueError(f"unknown weighting {scheme}")


def fit_all_models(
    surface: pd.DataFrame,
    cfg: ResearchConfig | None = None,
    prev_svi: tuple[float, ...] | None = None,
    weighting: str = "vega",
) -> tuple[pd.DataFrame, DayFits, dict]:
    cfg = cfg or DEFAULT
    usable = surface.loc[surface["usable"]].copy()
    if len(usable) < cfg.min_valid_strikes:
        raise ValueError(f"too few usable strikes: {len(usable)}")

    k = usable["k"].to_numpy(dtype=float)
    w = usable["total_variance"].to_numpy(dtype=float)
    iv = usable["market_iv"].to_numpy(dtype=float)
    K = usable["strike"].to_numpy(dtype=float)
    T = float(usable["T"].iloc[0])
    F = float(usable["forward"].iloc[0])
    wt = _weights(usable, weighting)

    poly = fit_polynomial(k, w, iv, T, wt, weighting)
    spl = fit_spline(k, w, iv, T, wt)
    svi = fit_svi(k, w, iv, T, wt, prev_params=prev_svi)
    ssvi = fit_ssvi(k, w, iv, T, wt)
    sabr = fit_sabr(F, K, iv, T, beta=cfg.sabr_beta, weights=wt)

    k_all = surface["k"].to_numpy(dtype=float)
    K_all = surface["strike"].to_numpy(dtype=float)

    fair_poly = np.sqrt(
        np.maximum(poly_total_variance(k_all, poly.a, poly.b, poly.c), 1e-12) / max(T, 1e-12)
    )
    fair_spl = spline_iv(spl.spline, k_all, T)
    fair_svi = svi_iv(k_all, svi.params(), T) if svi.n_obs >= 5 else np.full_like(k_all, np.nan)
    w_ssvi = ssvi_total_variance(k_all, ssvi.theta, ssvi.rho, ssvi.phi)
    fair_ssvi = np.sqrt(np.maximum(w_ssvi, 1e-12) / max(T, 1e-12))
    fair_sabr = sabr_iv(F, K_all, T, sabr.alpha, sabr.beta, sabr.rho, sabr.nu)

    out = surface.copy()
    out["fair_iv_polynomial"] = fair_poly
    out["fair_iv_spline"] = fair_spl
    out["fair_iv_svi"] = fair_svi
    out["fair_iv_ssvi"] = fair_ssvi
    out["fair_iv_sabr"] = fair_sabr

    model_mat = out[[f"fair_iv_{m}" for m in MODEL_COLS]].to_numpy(dtype=float)
    out["fair_iv_ensemble"] = np.nanmedian(model_mat, axis=1)
    out["model_dispersion"] = np.nanstd(model_mat, axis=1, ddof=0)

    for m in (*MODEL_COLS, "ensemble"):
        out[f"residual_{m}"] = out["market_iv"] - out[f"fair_iv_{m}"]

    # Confidence: |residual| / dispersion.  High = residual large vs disagreement.
    disp = out["model_dispersion"].replace(0, np.nan)
    out["confidence_score"] = out["residual_ensemble"].abs() / disp

    metrics = {
        "poly": poly.to_record(),
        "spline": spl.to_record(),
        "svi": svi.to_record(),
        "ssvi": ssvi.to_record(),
        "sabr": sabr.to_record(),
        "weighting": weighting,
        "n_usable": int(usable.shape[0]),
    }
    return out, DayFits(poly, spl, svi, ssvi, sabr), metrics
