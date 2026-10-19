"""Generic structure generator: RR, butterflies, skew, slope, curvature, verticals.

All structures are evaluated in both IV space and (where possible) price space.
Vertical residual = market_vertical_price - model_vertical_price.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config.settings import DEFAULT, ResearchConfig
from src.interpolation.delta_interp import interpolate_delta_iv, DeltaPoint
from src.surface.black_scholes import bs_price


def _point(surface: pd.DataFrame, delta: float, side: str, cfg: ResearchConfig, iv_col: str) -> DeltaPoint:
    return interpolate_delta_iv(surface, delta, side, cfg.max_delta_extrapolation, iv_col)


def _model_price(surface: pd.DataFrame, pt: DeltaPoint, cp: str, iv: float) -> float:
    if not np.isfinite(iv) or not np.isfinite(pt.strike):
        return float("nan")
    F = float(surface["forward"].iloc[0])
    T = float(surface["T"].iloc[0])
    return bs_price(F, pt.strike, T, iv, cp, df=1.0)


def build_all_structures(
    surface: pd.DataFrame,
    cfg: ResearchConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or DEFAULT
    rows: list[dict] = []
    rows.extend(_level_skew_slope(surface, cfg))
    rows.extend(_risk_reversals(surface, cfg))
    rows.extend(_butterflies(surface, cfg))
    rows.extend(_verticals(surface, cfg))
    rows.extend(_wings(surface, cfg))
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["trade_date"] = surface["trade_date"].iloc[0]
    out["expiry"] = surface["expiry"].iloc[0]
    out["actual_dte"] = int(surface["actual_dte"].iloc[0])
    out["forward"] = float(surface["forward"].iloc[0])
    out["spot"] = float(surface["spot"].iloc[0])
    return out


def _iv(surface: pd.DataFrame, d: float, side: str, cfg: ResearchConfig, col: str) -> DeltaPoint:
    return _point(surface, d, side, cfg, col)


def _level_skew_slope(surface: pd.DataFrame, cfg: ResearchConfig) -> list[dict]:
    mkt_atm = _point(surface, 0.5, "atm", cfg, "market_iv")
    ens_atm = _point(surface, 0.5, "atm", cfg, "fair_iv_ensemble") if "fair_iv_ensemble" in surface else mkt_atm
    rows = [
        _scalar_structure(
            "ATM_IV",
            "level",
            mkt_atm.iv,
            ens_atm.iv,
            legs="ATM",
            extra={"delta": 0.5, "market_price": mkt_atm.price, "fair_price": ens_atm.price},
        )
    ]
    for d in cfg.rr_deltas:
        p = _point(surface, d, "put", cfg, "market_iv")
        c = _point(surface, d, "call", cfg, "market_iv")
        atm = mkt_atm
        rows.append(
            _scalar_structure(
                f"PUT_SKEW_{int(d*100)}D",
                "skew",
                p.iv - atm.iv,
                _safe_sub(_fair(surface, d, "put", cfg), _fair(surface, 0.5, "atm", cfg)),
                legs=f"{int(d*100)}DP vs ATM",
                extra={"delta": d, "side": "put"},
            )
        )
        rows.append(
            _scalar_structure(
                f"CALL_SKEW_{int(d*100)}D",
                "skew",
                c.iv - atm.iv,
                _safe_sub(_fair(surface, d, "call", cfg), _fair(surface, 0.5, "atm", cfg)),
                legs=f"{int(d*100)}DC vs ATM",
                extra={"delta": d, "side": "call"},
            )
        )
        # Slope dIV/dDelta
        rows.append(
            _scalar_structure(
                f"SLOPE_ATM_TO_{int(d*100)}P",
                "slope",
                (p.iv - atm.iv) / max(0.5 - d, 1e-6),
                np.nan,
                legs=f"ATM -> {int(d*100)}DP",
                extra={"delta": d},
            )
        )
        rows.append(
            _scalar_structure(
                f"SLOPE_ATM_TO_{int(d*100)}C",
                "slope",
                (c.iv - atm.iv) / max(0.5 - d, 1e-6),
                np.nan,
                legs=f"ATM -> {int(d*100)}DC",
                extra={"delta": d},
            )
        )
    return rows


def _fair(surface: pd.DataFrame, d: float, side: str, cfg: ResearchConfig) -> float:
    if "fair_iv_ensemble" not in surface.columns:
        return float("nan")
    return _point(surface, d, side, cfg, "fair_iv_ensemble").iv


def _safe_sub(a: float, b: float) -> float:
    if not (np.isfinite(a) and np.isfinite(b)):
        return float("nan")
    return a - b


def _risk_reversals(surface: pd.DataFrame, cfg: ResearchConfig) -> list[dict]:
    rows = []
    for d in cfg.rr_deltas:
        c = _point(surface, d, "call", cfg, "market_iv")
        p = _point(surface, d, "put", cfg, "market_iv")
        mkt = c.iv - p.iv
        fair_c = _fair(surface, d, "call", cfg)
        fair_p = _fair(surface, d, "put", cfg)
        fair = _safe_sub(fair_c, fair_p)
        # Price-space RR: long call, short put at same |delta|
        mkt_px = c.price - p.price
        fair_px = _model_price(surface, c, "C", fair_c) - _model_price(surface, p, "P", fair_p)
        rows.append(
            _scalar_structure(
                f"RR_{int(d*100)}D",
                "risk_reversal",
                mkt,
                fair,
                legs=f"+{int(d*100)}DC / -{int(d*100)}DP",
                extra={
                    "delta": d,
                    "market_price": mkt_px,
                    "fair_price": fair_px,
                    "price_residual": mkt_px - fair_px if np.isfinite(mkt_px) and np.isfinite(fair_px) else np.nan,
                    "leg1_iv": c.iv,
                    "leg2_iv": p.iv,
                    "extrapolated": bool(c.extrapolated or p.extrapolated),
                    "liquidity_score": float(np.nanmean([c.vega, p.vega])) if np.isfinite(c.vega) or np.isfinite(p.vega) else float("nan"),
                },
            )
        )
    return rows


def _butterflies(surface: pd.DataFrame, cfg: ResearchConfig) -> list[dict]:
    rows = []
    atm = _point(surface, 0.5, "atm", cfg, "market_iv")
    for d in cfg.butterfly_deltas:
        p = _point(surface, d, "put", cfg, "market_iv")
        c = _point(surface, d, "call", cfg, "market_iv")
        mkt = 0.5 * (p.iv + c.iv) - atm.iv
        fair = 0.5 * (_fair(surface, d, "put", cfg) + _fair(surface, d, "call", cfg)) - _fair(
            surface, 0.5, "atm", cfg
        )
        # Price butterfly: +1 put +1 call - ATM straddle.
        # atm.price is already half-straddle (0.5*(call+put)), so 2*atm.price
        # is the full ATM straddle. Fair side must match: C_atm + P_atm, not 2*C.
        atm_fair_iv = _fair(surface, 0.5, "atm", cfg)
        mkt_px = p.price + c.price - 2.0 * atm.price
        fair_px = (
            _model_price(surface, p, "P", _fair(surface, d, "put", cfg))
            + _model_price(surface, c, "C", _fair(surface, d, "call", cfg))
            - (
                _model_price(surface, atm, "C", atm_fair_iv)
                + _model_price(surface, atm, "P", atm_fair_iv)
            )
        )
        rows.append(
            _scalar_structure(
                f"BF_{int(d*100)}D",
                "butterfly",
                mkt,
                fair,
                legs=f"{int(d*100)}DP / ATM / {int(d*100)}DC",
                extra={
                    "delta": d,
                    "market_price": mkt_px,
                    "fair_price": fair_px,
                    "price_residual": mkt_px - fair_px if np.isfinite(mkt_px) and np.isfinite(fair_px) else np.nan,
                    "extrapolated": bool(p.extrapolated or c.extrapolated),
                    "liquidity_score": float(np.nanmean([p.vega, c.vega, atm.vega])),
                },
            )
        )
    return rows


def _verticals(surface: pd.DataFrame, cfg: ResearchConfig) -> list[dict]:
    rows = []
    for d1, d2 in cfg.structure_delta_pairs:
        assert d1 > d2, "vertical pairs must be (closer_to_atm, further)"
        for side, cp in (("put", "P"), ("call", "C")):
            near = _point(surface, d1, side, cfg, "market_iv")
            far = _point(surface, d2, side, cfg, "market_iv")
            # Debit vertical: long nearer ATM, short further OTM.
            mkt_px = near.price - far.price
            fair_near = _fair(surface, d1, side, cfg)
            fair_far = _fair(surface, d2, side, cfg)
            fair_px = _model_price(surface, near, cp, fair_near) - _model_price(surface, far, cp, fair_far)
            iv_diff = near.iv - far.iv
            fair_iv_diff = _safe_sub(fair_near, fair_far)
            width = abs(near.strike - far.strike)
            rows.append(
                _scalar_structure(
                    f"VERT_{side.upper()}_{int(d1*100)}D_{int(d2*100)}D",
                    "vertical",
                    iv_diff,
                    fair_iv_diff,
                    legs=f"+{int(d1*100)}D{side[0].upper()} / -{int(d2*100)}D{side[0].upper()}",
                    extra={
                        "delta": d1,
                        "delta_2": d2,
                        "side": side,
                        "market_price": mkt_px,
                        "fair_price": fair_px,
                        "price_residual": mkt_px - fair_px if np.isfinite(mkt_px) and np.isfinite(fair_px) else np.nan,
                        "width": width,
                        "leg1_iv": near.iv,
                        "leg2_iv": far.iv,
                        "leg1_strike": near.strike,
                        "leg2_strike": far.strike,
                        "leg1_delta": d1,
                        "leg2_delta": d2,
                        "extrapolated": bool(near.extrapolated or far.extrapolated),
                        "liquidity_score": float(np.nanmin([near.vega, far.vega])) if np.isfinite(near.vega) or np.isfinite(far.vega) else float("nan"),
                    },
                )
            )
    return rows


def _wings(surface: pd.DataFrame, cfg: ResearchConfig) -> list[dict]:
    rows = []
    p10 = _point(surface, 0.10, "put", cfg, "market_iv")
    p25 = _point(surface, 0.25, "put", cfg, "market_iv")
    c10 = _point(surface, 0.10, "call", cfg, "market_iv")
    c25 = _point(surface, 0.25, "call", cfg, "market_iv")
    atm = _point(surface, 0.5, "atm", cfg, "market_iv")
    left = p10.iv - 2 * p25.iv + atm.iv
    right = c10.iv - 2 * c25.iv + atm.iv
    rows.append(_scalar_structure("LEFT_WING_CURV", "wing", left, np.nan, "10P-2*25P+ATM"))
    rows.append(_scalar_structure("RIGHT_WING_CURV", "wing", right, np.nan, "10C-2*25C+ATM"))
    rows.append(_scalar_structure("WING_ASYMMETRY", "wing", left - right, np.nan, "left-right"))
    rows.append(_scalar_structure("WING_10_VS_25_P", "wing", p10.iv - p25.iv, np.nan, "10P-25P"))
    rows.append(_scalar_structure("WING_10_VS_25_C", "wing", c10.iv - c25.iv, np.nan, "10C-25C"))
    return rows


def _scalar_structure(
    name: str,
    kind: str,
    market: float,
    fair: float,
    legs: str,
    extra: dict | None = None,
) -> dict:
    rec = {
        "structure": name,
        "kind": kind,
        "legs": legs,
        "market_value": market,
        "fair_value": fair,
        "residual": market - fair if np.isfinite(market) and np.isfinite(fair) else np.nan,
        "market_price": np.nan,
        "fair_price": np.nan,
        "price_residual": np.nan,
        "extrapolated": False,
        "liquidity_score": np.nan,
    }
    if extra:
        rec.update(extra)
    return rec
