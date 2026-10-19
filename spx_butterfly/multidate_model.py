"""Multi-date historical volatility surface and butterfly spread comparison engine.

Provides data structures, factor estimation (anchor-based, WLS, robust Huber),
smile alignment (ATM-relative and absolute strike), decomposition bridges,
and hypothetical fixed-reference IV-only butterfly repricing and attribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from sklearn.linear_model import HuberRegressor

from spx_butterfly.black_scholes import bs_price
from spx_butterfly.data_loader import get_snapshot
from spx_butterfly.fly_builder import ButterflySpread, build_butterflies_for_side
from spx_butterfly.greeks import calc_greeks


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class DailyFactorMetrics:
    """Historical Level, Skew, and Curvature measurements for a single date."""

    date: str
    underlying: float
    atm_strike: float
    target_dte: float
    level: float
    skew: float
    curvature: float
    h_width: float
    delta_level: float = 0.0
    delta_skew: float = 0.0
    delta_curvature: float = 0.0
    comparison_date: str = ""
    fit_method: str = "anchor"
    residual_rmse: float = 0.0
    nodes_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "Date": self.date,
            "SPX": self.underlying,
            "ATM Strike": self.atm_strike,
            "Target DTE": self.target_dte,
            "ATM IV (%)": self.level,
            "Skew (pts)": self.skew,
            "Curvature (pts)": self.curvature,
            "Δ Level": self.delta_level,
            "Δ Skew": self.delta_skew,
            "Δ Curvature": self.delta_curvature,
            "Basis": self.comparison_date,
            "Method": self.fit_method,
            "RMSE (pts)": self.residual_rmse,
        }


@dataclass
class FactorDifferences:
    """Estimated factor differences between a Reference Date and a Focus Date."""

    reference_date: str
    focus_date: str
    h_width: float
    delta_level: float  # L
    delta_skew: float   # S
    delta_curvature: float  # C
    method: str
    rmse: float = 0.0
    r_squared: float = 1.0
    matched_nodes: int = 0
    ref_level: float = 0.0
    ref_skew: float = 0.0
    ref_curvature: float = 0.0
    focus_level: float = 0.0
    focus_skew: float = 0.0
    focus_curvature: float = 0.0


@dataclass
class SmileDecompositionPoint:
    """Decomposition of IV smile change at an aligned ATM offset."""

    atm_offset: float
    x: float
    ref_strike: float
    focus_strike: float
    ref_iv_pct: float
    focus_iv_pct: float
    observed_change: float
    level_comp: float
    skew_comp: float
    curvature_comp: float
    modelled_change: float
    residual: float
    iv_0: float
    iv_l: float
    iv_ls: float
    iv_lsc: float
    iv_actual: float
    option_side: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ATM Offset": self.atm_offset,
            "x (Offset/H)": self.x,
            "Ref Strike": self.ref_strike,
            "Focus Strike": self.focus_strike,
            "Side": self.option_side,
            "Reference IV (%)": self.ref_iv_pct,
            "Focus IV (%)": self.focus_iv_pct,
            "Observed Change (pts)": self.observed_change,
            "Level Component (pts)": self.level_comp,
            "Skew Component (pts)": self.skew_comp,
            "Curvature Component (pts)": self.curvature_comp,
            "Modelled Change (pts)": self.modelled_change,
            "Residual (pts)": self.residual,
            "IV_0 (Ref)": self.iv_0,
            "IV_L (Level)": self.iv_l,
            "IV_LS (Level+Skew)": self.iv_ls,
            "IV_LSC (Modelled)": self.iv_lsc,
            "IV_Actual (Focus)": self.iv_actual,
        }


@dataclass
class DailyFlyObservation:
    """Observed historical butterfly spread for a single date."""

    date: str
    underlying: float
    atm_strike: float
    target_dte: float
    option_side: str
    centre_strike: float
    atm_offset: float
    lower_strike: float
    upper_strike: float
    wing_width: float
    lower_premium: float
    middle_premium: float
    upper_premium: float
    fly_premium: float
    normalized_premium: float
    is_valid_market: bool = True
    missing_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "Date": self.date,
            "SPX": self.underlying,
            "ATM Strike": self.atm_strike,
            "Target DTE": self.target_dte,
            "Side": self.option_side.upper(),
            "Centre Strike": self.centre_strike,
            "ATM Offset": self.atm_offset,
            "Lower Strike": self.lower_strike,
            "Upper Strike": self.upper_strike,
            "Wing Width": self.wing_width,
            "Lower Premium": self.lower_premium,
            "Middle Premium": self.middle_premium,
            "Upper Premium": self.upper_premium,
            "Net Fly Premium": self.fly_premium,
            "Normalized Premium (Fly/h)": self.normalized_premium,
            "Valid Market Quote": self.is_valid_market,
            "Notes": self.missing_reason,
        }


@dataclass
class ObservedFlyDifference:
    """Difference between rolling ATM-relative butterfly quotes across two dates."""

    option_side: str
    atm_offset: float
    ref_centre: float
    focus_centre: float
    ref_premium: float
    focus_premium: float
    abs_change: float
    pct_change: float | None
    normalized_ref: float
    normalized_focus: float
    normalized_change: float
    is_stable_ratio: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "Side": self.option_side.upper(),
            "ATM Offset": self.atm_offset,
            "Ref Centre Strike": self.ref_centre,
            "Focus Centre Strike": self.focus_centre,
            "Ref Premium": self.ref_premium,
            "Focus Premium": self.focus_premium,
            "Observed Change (SPX pts)": self.abs_change,
            "Percentage Change (%)": self.pct_change if self.pct_change is not None else np.nan,
            "Normalized Ref (pts/h)": self.normalized_ref,
            "Normalized Focus (pts/h)": self.normalized_focus,
            "Normalized Change (pts/h)": self.normalized_change,
            "Ratio Stable": self.is_stable_ratio,
        }


@dataclass
class FixedFlyAttribution:
    """Hypothetical fixed-reference IV-only repricing and sequential factor attribution."""

    option_side: str
    ref_centre_strike: float
    atm_offset: float
    lower_strike: float
    upper_strike: float
    wing_width: float
    # Premiums at stages
    f0: float
    f_l: float
    f_ls: float
    f_lsc: float
    f_full: float
    # Exact sequential effects
    level_effect: float
    skew_effect: float
    curvature_effect: float
    residual_effect: float
    total_iv_change: float
    # Leg-level details for inspection
    lower_details: dict[str, Any] = field(default_factory=dict)
    middle_details: dict[str, Any] = field(default_factory=dict)
    upper_details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "Side": self.option_side.upper(),
            "ATM Offset": self.atm_offset,
            "Centre Strike": self.ref_centre_strike,
            "Lower Strike": self.lower_strike,
            "Upper Strike": self.upper_strike,
            "Wing Width": self.wing_width,
            "Original Premium (F0)": self.f0,
            "After Level (FL)": self.f_l,
            "After Skew (FLS)": self.f_ls,
            "After Curvature (FLSC)": self.f_lsc,
            "Full Observed IV (FFull)": self.f_full,
            "Level Effect": self.level_effect,
            "Skew Effect": self.skew_effect,
            "Curvature Effect": self.curvature_effect,
            "Residual Effect": self.residual_effect,
            "Total IV-Only Change": self.total_iv_change,
        }


# ---------------------------------------------------------------------------
# Factor Estimation & Decomposition Functions
# ---------------------------------------------------------------------------

def extract_smile_points(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    """Extract ordered unique strike and IV observations from a snapshot.

    Sorts by ATM offset ascending: Puts (negative offsets), ATM (offset 0), Calls (positive offsets).
    Returns DataFrame with columns: option_side, strike, atm_offset, iv_pct, iv_decimal, premium.
    """
    df = snapshot_df.copy()
    df["iv_pct"] = df["iv_decimal"] * 100.0

    # Ensure ATM offset exists
    if "atm_offset" not in df.columns:
        df["atm_offset"] = df["strike"] - df["atm_strike"]

    # Filter out duplicate ATM contract if present (prefer call for offset 0 or first available)
    puts = df[(df["option_side"] == "put") & (df["atm_offset"] < 0)].copy()
    calls = df[(df["option_side"] == "call") & (df["atm_offset"] > 0)].copy()
    atm = df[df["atm_offset"] == 0].copy()
    if not atm.empty:
        # If both call and put ATM exist, take call or first
        atm_row = atm[atm["option_side"] == "call"]
        if atm_row.empty:
            atm_row = atm.iloc[[0]]
        else:
            atm_row = atm_row.iloc[[0]]
    else:
        atm_row = pd.DataFrame()

    combined = pd.concat([puts, atm_row, calls], ignore_index=True)
    combined = combined.sort_values("atm_offset").drop_duplicates(subset=["atm_offset"]).reset_index(drop=True)
    return combined


def get_iv_at_offset(
    smile_df: pd.DataFrame,
    target_offset: float,
    allow_interp: bool = True,
) -> float | None:
    """Get implied volatility in percentage points at a specific ATM offset.

    If exact match is found within 1e-4, returns it.
    If not found and allow_interp is True, interpolates within the min/max offset range.
    Never extrapolates outside the smile boundaries.
    """
    matches = smile_df[np.isclose(smile_df["atm_offset"], target_offset, atol=1e-3)]
    if not matches.empty:
        return float(matches["iv_pct"].iloc[0])

    if not allow_interp or len(smile_df) < 2:
        return None

    min_off = float(smile_df["atm_offset"].min())
    max_off = float(smile_df["atm_offset"].max())
    if target_offset < min_off or target_offset > max_off:
        return None

    # Linear interpolation inside smile
    f_interp = interp1d(
        smile_df["atm_offset"].values,
        smile_df["iv_pct"].values,
        kind="linear",
        bounds_error=False,
        fill_value=np.nan,
    )
    val = float(f_interp(target_offset))
    return val if np.isfinite(val) else None


def calculate_daily_factors(
    snapshot_df: pd.DataFrame,
    h_width: float = 500.0,
) -> dict[str, float | None]:
    """Calculate Level, Skew, and Curvature from a snapshot using reference width H.

    Level = IV(ATM)
    Skew = IV(ATM + H) - IV(ATM - H)
    Curvature = [IV(ATM - H) + IV(ATM + H)] / 2 - IV(ATM)

    All values in volatility percentage points.
    """
    smile = extract_smile_points(snapshot_df)
    iv_atm = get_iv_at_offset(smile, 0.0)
    iv_left = get_iv_at_offset(smile, -float(h_width))
    iv_right = get_iv_at_offset(smile, float(h_width))

    if iv_atm is None or iv_left is None or iv_right is None:
        return {
            "level": iv_atm,
            "skew": None,
            "curvature": None,
            "iv_atm": iv_atm,
            "iv_left": iv_left,
            "iv_right": iv_right,
        }

    level = iv_atm
    skew = iv_right - iv_left
    curvature = (iv_left + iv_right) / 2.0 - iv_atm

    return {
        "level": level,
        "skew": skew,
        "curvature": curvature,
        "iv_atm": iv_atm,
        "iv_left": iv_left,
        "iv_right": iv_right,
    }


def compute_multidate_factors_table(
    long_df: pd.DataFrame,
    selected_dates: list[str],
    reference_date: str,
    h_width: float = 500.0,
    comparison_basis: Literal["reference", "sequential"] = "reference",
    fit_method: str = "anchor",
) -> pd.DataFrame:
    """Generate the historical factor comparison table for all selected dates."""
    sorted_dates = sorted(selected_dates)
    rows: list[DailyFactorMetrics] = []

    daily_factors_cache: dict[str, dict[str, Any]] = {}
    for d in sorted_dates:
        snap = get_snapshot(long_df, d)
        f = calculate_daily_factors(snap, h_width=h_width)
        s0 = float(snap["underlying"].iloc[0])
        atm0 = float(snap["atm_strike"].iloc[0])
        dte0 = float(snap["target_dte"].iloc[0])
        daily_factors_cache[d] = {
            "factors": f,
            "spot": s0,
            "atm": atm0,
            "dte": dte0,
            "snapshot": snap,
        }

    ref_data = daily_factors_cache.get(reference_date)
    ref_factors = ref_data["factors"] if ref_data else None

    for i, d in enumerate(sorted_dates):
        d_info = daily_factors_cache[d]
        f = d_info["factors"]
        lvl = f["level"] or 0.0
        skw = f["skew"] or 0.0
        crv = f["curvature"] or 0.0

        if comparison_basis == "sequential":
            # Compare to immediately preceding selected date
            comp_date = sorted_dates[i - 1] if i > 0 else d
            base_factors = daily_factors_cache[comp_date]["factors"]
        else:
            comp_date = reference_date
            base_factors = ref_factors

        if base_factors and base_factors["level"] is not None:
            base_lvl = base_factors["level"]
            base_skw = base_factors["skew"] or 0.0
            base_crv = base_factors["curvature"] or 0.0

            if fit_method == "anchor":
                dl = lvl - base_lvl
                ds = skw - base_skw
                dc = crv - base_crv
                rmse = 0.0
            else:
                # Fitted factor difference between comp_date snapshot and d snapshot
                snap_base = daily_factors_cache[comp_date]["snapshot"]
                snap_curr = d_info["snapshot"]
                fitted = fit_factors_between_dates(snap_base, snap_curr, h_width=h_width, method=fit_method)
                dl = fitted.delta_level
                ds = fitted.delta_skew
                dc = fitted.delta_curvature
                rmse = fitted.rmse
        else:
            dl, ds, dc, rmse = 0.0, 0.0, 0.0, 0.0

        metric = DailyFactorMetrics(
            date=d,
            underlying=d_info["spot"],
            atm_strike=d_info["atm"],
            target_dte=d_info["dte"],
            level=lvl,
            skew=skw,
            curvature=crv,
            h_width=h_width,
            delta_level=dl,
            delta_skew=ds,
            delta_curvature=dc,
            comparison_date=comp_date,
            fit_method=fit_method,
            residual_rmse=rmse,
        )
        rows.append(metric)

    return pd.DataFrame([r.to_dict() for r in rows])


def fit_factors_between_dates(
    ref_snapshot: pd.DataFrame,
    focus_snapshot: pd.DataFrame,
    h_width: float = 500.0,
    method: Literal["anchor", "wls", "robust"] = "anchor",
) -> FactorDifferences:
    """Fit or calculate factor differences (L, S, C) between Reference and Focus snapshots."""
    ref_date = str(ref_snapshot["date"].iloc[0])
    focus_date = str(focus_snapshot["date"].iloc[0])

    ref_factors = calculate_daily_factors(ref_snapshot, h_width=h_width)
    focus_factors = calculate_daily_factors(focus_snapshot, h_width=h_width)

    ref_lvl = ref_factors["level"] or 0.0
    ref_skw = ref_factors["skew"] or 0.0
    ref_crv = ref_factors["curvature"] or 0.0

    foc_lvl = focus_factors["level"] or 0.0
    foc_skw = focus_factors["skew"] or 0.0
    foc_crv = focus_factors["curvature"] or 0.0

    # Align nodes on shared ATM offset
    ref_smile = extract_smile_points(ref_snapshot)
    foc_smile = extract_smile_points(focus_snapshot)

    merged = pd.merge(
        ref_smile[["atm_offset", "iv_pct"]],
        foc_smile[["atm_offset", "iv_pct"]],
        on="atm_offset",
        suffixes=("_ref", "_focus"),
    )

    if merged.empty:
        return FactorDifferences(
            reference_date=ref_date,
            focus_date=focus_date,
            h_width=h_width,
            delta_level=0.0,
            delta_skew=0.0,
            delta_curvature=0.0,
            method=method,
            rmse=0.0,
            matched_nodes=0,
            ref_level=ref_lvl,
            ref_skew=ref_skw,
            ref_curvature=ref_crv,
            focus_level=foc_lvl,
            focus_skew=foc_skw,
            focus_curvature=foc_crv,
        )

    offsets = merged["atm_offset"].to_numpy(dtype=float)
    x_coords = offsets / float(h_width)
    y_observed = (merged["iv_pct_focus"] - merged["iv_pct_ref"]).to_numpy(dtype=float)
    n_nodes = len(offsets)

    if method == "anchor":
        # Anchor-based factor changes
        if ref_factors["level"] is not None and focus_factors["level"] is not None:
            dl = foc_lvl - ref_lvl
            ds = foc_skw - ref_skw
            dc = foc_crv - ref_crv
        else:
            dl, ds, dc = 0.0, 0.0, 0.0

        modelled = dl + (ds / 2.0) * x_coords + dc * (x_coords ** 2)
        residuals = y_observed - modelled
        rmse = float(np.sqrt(np.mean(residuals ** 2)))

    elif method in ("wls", "ols"):
        # Unweighted OLS across all aligned nodes (method alias "wls" kept for
        # API compatibility; no diagonal weights are applied).
        # Model: y = dl + (ds/2)*x + dc*x^2
        X = np.column_stack([np.ones_like(x_coords), x_coords / 2.0, x_coords ** 2])
        coeffs, _, _, _ = np.linalg.lstsq(X, y_observed, rcond=None)
        dl, ds, dc = float(coeffs[0]), float(coeffs[1]), float(coeffs[2])
        modelled = X @ coeffs
        residuals = y_observed - modelled
        rmse = float(np.sqrt(np.mean(residuals ** 2)))

    elif method == "robust":
        # Robust Huber regression
        X = np.column_stack([np.ones_like(x_coords), x_coords / 2.0, x_coords ** 2])
        huber = HuberRegressor(fit_intercept=False, max_iter=200)
        huber.fit(X, y_observed)
        coeffs = huber.coef_
        dl, ds, dc = float(coeffs[0]), float(coeffs[1]), float(coeffs[2])
        modelled = X @ coeffs
        residuals = y_observed - modelled
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
    else:
        raise ValueError(f"Unknown fit method: {method}")

    # R-squared calculation
    tot_var = np.sum((y_observed - np.mean(y_observed)) ** 2)
    res_var = np.sum((y_observed - (dl + (ds / 2.0) * x_coords + dc * (x_coords ** 2))) ** 2)
    r2 = 1.0 - (res_var / tot_var) if tot_var > 1e-12 else 1.0

    return FactorDifferences(
        reference_date=ref_date,
        focus_date=focus_date,
        h_width=h_width,
        delta_level=dl,
        delta_skew=ds,
        delta_curvature=dc,
        method=method,
        rmse=rmse,
        r_squared=float(r2),
        matched_nodes=n_nodes,
        ref_level=ref_lvl,
        ref_skew=ref_skw,
        ref_curvature=ref_crv,
        focus_level=foc_lvl,
        focus_skew=foc_skw,
        focus_curvature=foc_crv,
    )


def decompose_iv_smile(
    ref_snapshot: pd.DataFrame,
    focus_snapshot: pd.DataFrame,
    factors: FactorDifferences,
    h_width: float = 500.0,
) -> list[SmileDecompositionPoint]:
    """Decompose smile change into Level, Skew, Curvature, and Local Residual components.

    For all aligned strike offsets:
        x = ATMOffset / H
        LevelComponent = L
        SkewComponent = (S/2) * x
        CurvatureComponent = C * x^2
        ModelledChange = LevelComponent + SkewComponent + CurvatureComponent
        PredictedFocusIV = ReferenceIV + ModelledChange
        Residual = FocusIV - PredictedFocusIV
    """
    ref_smile = extract_smile_points(ref_snapshot)
    foc_smile = extract_smile_points(focus_snapshot)

    merged = pd.merge(
        ref_smile,
        foc_smile,
        on="atm_offset",
        suffixes=("_ref", "_focus"),
    )

    if merged.empty:
        return []

    points: list[SmileDecompositionPoint] = []
    l_shock = float(factors.delta_level)
    s_shock = float(factors.delta_skew)
    c_shock = float(factors.delta_curvature)

    for _, row in merged.iterrows():
        off = float(row["atm_offset"])
        x = off / float(h_width)
        ref_k = float(row["strike_ref"])
        foc_k = float(row["strike_focus"])
        side = str(row["option_side_ref"])

        ref_iv = float(row["iv_pct_ref"])
        foc_iv = float(row["iv_pct_focus"])

        obs_chg = foc_iv - ref_iv

        lvl_comp = l_shock
        skw_comp = (s_shock / 2.0) * x
        crv_comp = c_shock * (x ** 2)

        mod_chg = lvl_comp + skw_comp + crv_comp
        pred_foc = ref_iv + mod_chg
        residual = foc_iv - pred_foc

        # Five Bridge Curves
        iv_0 = ref_iv
        iv_l = iv_0 + lvl_comp
        iv_ls = iv_l + skw_comp
        iv_lsc = iv_ls + crv_comp
        iv_actual = foc_iv

        pt = SmileDecompositionPoint(
            atm_offset=off,
            x=x,
            ref_strike=ref_k,
            focus_strike=foc_k,
            ref_iv_pct=ref_iv,
            focus_iv_pct=foc_iv,
            observed_change=obs_chg,
            level_comp=lvl_comp,
            skew_comp=skw_comp,
            curvature_comp=crv_comp,
            modelled_change=mod_chg,
            residual=residual,
            iv_0=iv_0,
            iv_l=iv_l,
            iv_ls=iv_ls,
            iv_lsc=iv_lsc,
            iv_actual=iv_actual,
            option_side=side,
        )
        points.append(pt)

    points.sort(key=lambda p: p.atm_offset)
    return points


# ---------------------------------------------------------------------------
# Butterfly Construction & Comparison Across Dates
# ---------------------------------------------------------------------------

def build_multidate_flies(
    long_df: pd.DataFrame,
    selected_dates: list[str],
    wing_width: float = 100.0,
    strict_market_puts: bool = True,
) -> dict[str, list[DailyFlyObservation]]:
    """Build all valid butterflies for each selected date.

    If strict_market_puts is True:
        Omits the ATM-100 put fly if the ATM put quote was synthesized (missing from source file).
    """
    results: dict[str, list[DailyFlyObservation]] = {}

    for d in selected_dates:
        snap = get_snapshot(long_df, d)
        s0 = float(snap["underlying"].iloc[0])
        atm0 = float(snap["atm_strike"].iloc[0])
        dte0 = float(snap["target_dte"].iloc[0])

        date_flies: list[DailyFlyObservation] = []

        # Calls: ATM+100 to ATM+800
        calls_df = snap[snap["option_side"] == "call"]
        call_strike_map = {row["strike"]: row for _, row in calls_df.iterrows()}

        for mid_k in sorted(call_strike_map.keys()):
            low_k = mid_k - wing_width
            upp_k = mid_k + wing_width
            if low_k in call_strike_map and upp_k in call_strike_map:
                p_low = float(call_strike_map[low_k]["premium"])
                p_mid = float(call_strike_map[mid_k]["premium"])
                p_upp = float(call_strike_map[upp_k]["premium"])
                fly_prem = p_low - 2.0 * p_mid + p_upp
                norm_prem = fly_prem / wing_width
                date_flies.append(
                    DailyFlyObservation(
                        date=d,
                        underlying=s0,
                        atm_strike=atm0,
                        target_dte=dte0,
                        option_side="call",
                        centre_strike=float(mid_k),
                        atm_offset=float(mid_k - atm0),
                        lower_strike=float(low_k),
                        upper_strike=float(upp_k),
                        wing_width=float(wing_width),
                        lower_premium=p_low,
                        middle_premium=p_mid,
                        upper_premium=p_upp,
                        fly_premium=fly_prem,
                        normalized_premium=norm_prem,
                        is_valid_market=True,
                    )
                )

        # Puts: ATM-800 to ATM-100
        puts_df = snap[snap["option_side"] == "put"]
        put_strike_map = {row["strike"]: row for _, row in puts_df.iterrows()}

        for mid_k in sorted(put_strike_map.keys()):
            low_k = mid_k - wing_width
            upp_k = mid_k + wing_width
            if low_k in put_strike_map and upp_k in put_strike_map:
                # Check if upper leg is ATM strike and whether strict market is enabled
                is_atm_leg = abs(upp_k - atm0) < 1e-4
                if is_atm_leg and strict_market_puts:
                    # In market Excel data, ATM strike was provided as Call only, Put ATM was synthesized.
                    # Record omission note
                    continue

                p_low = float(put_strike_map[low_k]["premium"])
                p_mid = float(put_strike_map[mid_k]["premium"])
                p_upp = float(put_strike_map[upp_k]["premium"])
                fly_prem = p_low - 2.0 * p_mid + p_upp
                norm_prem = fly_prem / wing_width
                date_flies.append(
                    DailyFlyObservation(
                        date=d,
                        underlying=s0,
                        atm_strike=atm0,
                        target_dte=dte0,
                        option_side="put",
                        centre_strike=float(mid_k),
                        atm_offset=float(mid_k - atm0),
                        lower_strike=float(low_k),
                        upper_strike=float(upp_k),
                        wing_width=float(wing_width),
                        lower_premium=p_low,
                        middle_premium=p_mid,
                        upper_premium=p_upp,
                        fly_premium=fly_prem,
                        normalized_premium=norm_prem,
                        is_valid_market=True,
                    )
                )

        results[d] = date_flies

    return results


def compute_observed_fly_differences(
    flies_by_date: dict[str, list[DailyFlyObservation]],
    ref_date: str,
    focus_date: str,
    wing_width: float = 100.0,
) -> list[ObservedFlyDifference]:
    """Compute observed premium differences between rolling ATM-relative butterflies across dates."""
    ref_flies = flies_by_date.get(ref_date, [])
    focus_flies = flies_by_date.get(focus_date, [])

    ref_map = {(f.option_side, round(f.atm_offset, 2)): f for f in ref_flies}
    focus_map = {(f.option_side, round(f.atm_offset, 2)): f for f in focus_flies}

    diffs: list[ObservedFlyDifference] = []
    all_keys = sorted(set(ref_map.keys()) & set(focus_map.keys()), key=lambda k: (0 if k[0] == "put" else 1, k[1]))

    for side, off in all_keys:
        f_ref = ref_map[(side, off)]
        f_foc = focus_map[(side, off)]

        p_ref = f_ref.fly_premium
        p_foc = f_foc.fly_premium
        abs_diff = p_foc - p_ref

        # Percentage change handling
        if abs(p_ref) > 0.05:
            pct_diff = 100.0 * (p_foc - p_ref) / abs(p_ref)
            stable = True
        else:
            pct_diff = None
            stable = False

        norm_ref = p_ref / wing_width
        norm_foc = p_foc / wing_width
        norm_diff = abs_diff / wing_width

        diffs.append(
            ObservedFlyDifference(
                option_side=side,
                atm_offset=off,
                ref_centre=f_ref.centre_strike,
                focus_centre=f_foc.centre_strike,
                ref_premium=p_ref,
                focus_premium=p_foc,
                abs_change=abs_diff,
                pct_change=pct_diff,
                normalized_ref=norm_ref,
                normalized_focus=norm_foc,
                normalized_change=norm_diff,
                is_stable_ratio=stable,
            )
        )

    return diffs


# ---------------------------------------------------------------------------
# Hypothetical Fixed-Reference IV-Only Repricing and Attribution
# ---------------------------------------------------------------------------

def compute_fixed_fly_attribution(
    ref_snapshot: pd.DataFrame,
    focus_snapshot: pd.DataFrame,
    factors: FactorDifferences,
    wing_width: float = 100.0,
    h_width: float = 500.0,
    pricing_mode: str = "baseline_delta",
    r: float = 0.0,
    q: float = 0.0,
    strict_market_puts: bool = True,
) -> list[FixedFlyAttribution]:
    """Reprice Reference Date's fixed strikes under factor changes and full observed smile change.

    Freezes:
        - Reference SPX Spot
        - Reference Strikes
        - Reference Target DTE
        - Reference Original Premiums
        - r, q

    Stages:
        F0: Original Reference Fly Premium
        FL: After Level Shock (L)
        FLS: After Level + Skew Shock (L + (S/2)*x)
        FLSC: After Level + Skew + Curvature Shock (L + (S/2)*x + C*x^2)
        FFull: Under Full Observed IV Shock (FocusIV(x) - ReferenceIV(x))

    Sequential Attribution:
        LevelEffect = FL - F0
        SkewEffect = FLS - FL
        CurvatureEffect = FLSC - FLS
        ResidualEffect = FFull - FLSC
        TotalIVOnlyChange = FFull - F0

    Identity:
        TotalIVOnlyChange = LevelEffect + SkewEffect + CurvatureEffect + ResidualEffect
    """
    s0 = float(ref_snapshot["underlying"].iloc[0])
    atm0 = float(ref_snapshot["atm_strike"].iloc[0])
    dte0 = float(ref_snapshot["target_dte"].iloc[0])
    t0 = dte0 / 365.0

    dl = float(factors.delta_level)
    ds = float(factors.delta_skew)
    dc = float(factors.delta_curvature)

    # Reference smile and focus smile mappings for offsets
    ref_smile = extract_smile_points(ref_snapshot)
    foc_smile = extract_smile_points(focus_snapshot)

    # Map ATM offset -> IV decimal
    ref_iv_map = {round(row["atm_offset"], 2): float(row["iv_decimal"]) for _, row in ref_smile.iterrows()}
    foc_iv_map = {round(row["atm_offset"], 2): float(row["iv_decimal"]) for _, row in foc_smile.iterrows()}

    # Reference strikes mapping for legs
    calls_df = ref_snapshot[ref_snapshot["option_side"] == "call"]
    puts_df = ref_snapshot[ref_snapshot["option_side"] == "put"]

    call_legs = {row["strike"]: row for _, row in calls_df.iterrows()}
    put_legs = {row["strike"]: row for _, row in puts_df.iterrows()}

    attributions: list[FixedFlyAttribution] = []

    # Helper function to reprice an individual option leg under baseline delta
    def reprice_leg(
        side: str,
        k: float,
        p_orig: float,
        iv_orig: float,
        iv_shocked: float,
    ) -> float:
        if pricing_mode == "full_bs":
            return float(bs_price(side, s0, k, t0, iv_shocked, r, q))
        # baseline delta preserving
        bs_orig = float(bs_price(side, s0, k, t0, iv_orig, r, q))
        bs_new = float(bs_price(side, s0, k, t0, iv_shocked, r, q))
        return float(p_orig + bs_new - bs_orig)

    # Process both Calls and Puts
    configs = [
        ("call", call_legs, [atm0 + off for off in range(100, 900, 100)]),
        ("put", put_legs, [atm0 - off for off in range(100, 900, 100)]),
    ]

    for side, leg_map, centre_candidates in configs:
        for mid_k in centre_candidates:
            low_k = mid_k - wing_width
            upp_k = mid_k + wing_width

            if low_k not in leg_map or mid_k not in leg_map or upp_k not in leg_map:
                continue

            # Check strict market put rule: if Put ATM is upper leg (i.e. mid_k = atm0 - wing_width)
            if side == "put" and abs(upp_k - atm0) < 1e-4 and strict_market_puts:
                continue

            row_low = leg_map[low_k]
            row_mid = leg_map[mid_k]
            row_upp = leg_map[upp_k]

            p_low = float(row_low["premium"])
            p_mid = float(row_mid["premium"])
            p_upp = float(row_upp["premium"])

            iv_low = float(row_low["iv_decimal"])
            iv_mid = float(row_mid["iv_decimal"])
            iv_upp = float(row_upp["iv_decimal"])

            # F0: Original Fly
            f0 = p_low - 2.0 * p_mid + p_upp

            # Offsets and x coordinates
            off_low = low_k - atm0
            off_mid = mid_k - atm0
            off_upp = upp_k - atm0

            x_low = off_low / h_width
            x_mid = off_mid / h_width
            x_upp = off_upp / h_width

            # Check if all 3 offsets exist in focus smile for Full IV repricing
            has_full_iv = (
                round(off_low, 2) in foc_iv_map
                and round(off_mid, 2) in foc_iv_map
                and round(off_upp, 2) in foc_iv_map
            )

            # Function to calculate shocked IV and repriced fly for any shock function
            def eval_fly_at_shock(shock_fn):
                shk_l = shock_fn(x_low, off_low) / 100.0
                shk_m = shock_fn(x_mid, off_mid) / 100.0
                shk_u = shock_fn(x_upp, off_upp) / 100.0

                p_l = reprice_leg(side, low_k, p_low, iv_low, max(1e-4, iv_low + shk_l))
                p_m = reprice_leg(side, mid_k, p_mid, iv_mid, max(1e-4, iv_mid + shk_m))
                p_u = reprice_leg(side, upp_k, p_upp, iv_upp, max(1e-4, iv_upp + shk_u))

                return p_l - 2.0 * p_m + p_u

            f_l = eval_fly_at_shock(lambda x, off: dl)
            f_ls = eval_fly_at_shock(lambda x, off: dl + (ds / 2.0) * x)
            f_lsc = eval_fly_at_shock(lambda x, off: dl + (ds / 2.0) * x + dc * (x ** 2))

            if has_full_iv:
                # Full observed IV shock
                def full_shock_fn(x, off):
                    ref_v = ref_iv_map[round(off, 2)] * 100.0
                    foc_v = foc_iv_map[round(off, 2)] * 100.0
                    return foc_v - ref_v

                f_full = eval_fly_at_shock(full_shock_fn)
            else:
                f_full = f_lsc  # Fallback if focus nodes missing

            # Sequential exact attribution
            lvl_eff = f_l - f0
            skw_eff = f_ls - f_l
            crv_eff = f_lsc - f_ls
            res_eff = f_full - f_lsc
            tot_change = f_full - f0

            # Detailed leg information dictionary
            def make_leg_detail(k_val, x_val, off_val, iv_orig, p_orig):
                obs_shock = (foc_iv_map[round(off_val, 2)] - ref_iv_map[round(off_val, 2)]) * 100.0 if has_full_iv else 0.0
                lvl_s = dl
                skw_s = (ds / 2.0) * x_val
                crv_s = dc * (x_val ** 2)
                res_s = obs_shock - (lvl_s + skw_s + crv_s)
                return {
                    "strike": k_val,
                    "offset": off_val,
                    "x": x_val,
                    "orig_iv_pct": iv_orig * 100.0,
                    "orig_premium": p_orig,
                    "focus_iv_pct": foc_iv_map.get(round(off_val, 2), np.nan) * 100.0,
                    "level_shock": lvl_s,
                    "skew_shock": skw_s,
                    "curvature_shock": crv_s,
                    "residual_shock": res_s,
                    "total_shock": obs_shock,
                }

            attributions.append(
                FixedFlyAttribution(
                    option_side=side,
                    ref_centre_strike=float(mid_k),
                    atm_offset=float(off_mid),
                    lower_strike=float(low_k),
                    upper_strike=float(upp_k),
                    wing_width=float(wing_width),
                    f0=f0,
                    f_l=f_l,
                    f_ls=f_ls,
                    f_lsc=f_lsc,
                    f_full=f_full,
                    level_effect=lvl_eff,
                    skew_effect=skw_eff,
                    curvature_effect=crv_eff,
                    residual_effect=res_eff,
                    total_iv_change=tot_change,
                    lower_details=make_leg_detail(low_k, x_low, off_low, iv_low, p_low),
                    middle_details=make_leg_detail(mid_k, x_mid, off_mid, iv_mid, p_mid),
                    upper_details=make_leg_detail(upp_k, x_upp, off_upp, iv_upp, p_upp),
                )
            )

    attributions.sort(key=lambda a: (0 if a.option_side == "put" else 1, a.atm_offset))
    return attributions


def compute_smile_structure_metrics(
    smile_df: pd.DataFrame,
    offsets: list[float] | None = None,
) -> dict[str, Any]:
    """Compute Call Skew, Put Skew, Risk Reversal, Curvature, and Kurtosis across moneyness offsets.

    Parameters
    ----------
    smile_df : pd.DataFrame
        DataFrame containing atm_offset, iv_pct, strike, etc.
    offsets : list[float], optional
        List of positive offsets to evaluate symmetric structures (default [100..800]).

    Returns
    -------
    dict[str, Any]
        Dictionary with atm_iv, structure DataFrame by offset, benchmark metrics, and polynomial coefficients.
    """
    atm_iv = get_iv_at_offset(smile_df, 0.0)

    if offsets is None:
        raw_offsets = [round(abs(x), 1) for x in smile_df["atm_offset"].dropna().tolist() if abs(x) > 1e-4]
        offsets = sorted(list(set(raw_offsets)))
        if not offsets:
            offsets = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]

    # Base curvature at 100 pts
    iv_c100 = get_iv_at_offset(smile_df, 100.0)
    iv_p100 = get_iv_at_offset(smile_df, -100.0)
    base_curv = ((iv_p100 + iv_c100) / 2.0 - atm_iv) if (iv_c100 is not None and iv_p100 is not None and atm_iv is not None) else None

    rows = []
    for h in offsets:
        h = float(h)
        iv_c = get_iv_at_offset(smile_df, h)
        iv_p = get_iv_at_offset(smile_df, -h)

        cs = (iv_c - atm_iv) if (iv_c is not None and atm_iv is not None) else None
        ps = (iv_p - atm_iv) if (iv_p is not None and atm_iv is not None) else None
        rr = (iv_c - iv_p) if (iv_c is not None and iv_p is not None) else None
        curv = ((iv_p + iv_c) / 2.0 - atm_iv) if (iv_p is not None and iv_c is not None and atm_iv is not None) else None

        # Kurtosis scaling ratio: Curvature(h) / [(h/100)^2 * base_curv]
        # Under a pure quadratic smile, this ratio is exactly 1.0. Values > 1 indicate leptokurtic / fat wings.
        # Undefined when wings/base curvature are missing — use NaN, not 1.0.
        if curv is not None and base_curv is not None and base_curv > 0 and h > 0:
            scale_factor = (h / 100.0) ** 2
            kurt_ratio = curv / (scale_factor * base_curv)
        else:
            kurt_ratio = float("nan")

        rows.append({
            "offset": h,
            "iv_call": iv_c,
            "iv_put": iv_p,
            "call_skew": cs,
            "put_skew": ps,
            "risk_reversal": rr,
            "curvature": curv,
            "kurtosis_ratio": kurt_ratio,
        })

    table_df = pd.DataFrame(rows)

    # 4th-degree polynomial fit: IV(x) = a0 + a1*x + a2*x^2 + a3*x^3 + a4*x^4 with x = offset / 500.0
    try:
        clean_df = smile_df.dropna(subset=["atm_offset", "iv_pct"]).drop_duplicates(subset=["atm_offset"])
        if len(clean_df) >= 5:
            x_norm = clean_df["atm_offset"].values / 500.0
            y_pts = clean_df["iv_pct"].values
            poly = np.polyfit(x_norm, y_pts, 4)
            a4 = float(poly[0])
            a3 = float(poly[1])
            a2 = float(poly[2])
            a1 = float(poly[3])
            a0 = float(poly[4])
        else:
            a0, a1, a2, a3, a4 = (atm_iv or 0.0), 0.0, 0.0, 0.0, 0.0
    except Exception:
        a0, a1, a2, a3, a4 = (atm_iv or 0.0), 0.0, 0.0, 0.0, 0.0

    # Benchmarks at 300 pts (standard 25-delta proxy) and 500 pts
    def _extract_benchmark(h_target: float) -> dict[str, float | None]:
        r = table_df[table_df["offset"] == h_target]
        if not r.empty:
            row0 = r.iloc[0]
            return {
                "offset": h_target,
                "call_skew": row0["call_skew"],
                "put_skew": row0["put_skew"],
                "risk_reversal": row0["risk_reversal"],
                "curvature": row0["curvature"],
                "kurtosis_ratio": row0["kurtosis_ratio"],
            }
        return {"offset": h_target, "call_skew": None, "put_skew": None, "risk_reversal": None, "curvature": None, "kurtosis_ratio": None}

    return {
        "atm_iv": atm_iv,
        "table": table_df,
        "benchmark_300": _extract_benchmark(300.0),
        "benchmark_500": _extract_benchmark(500.0),
        "poly_coeffs": {
            "a0_level": a0,
            "a1_skew": a1,
            "a2_curvature": a2,
            "a3_asymmetry": a3,
            "a4_kurtosis": a4,
        },
    }


def get_fly_premium_at_offset(
    fly_df: pd.DataFrame,
    target_offset: float,
    allow_interp: bool = True,
) -> float | None:
    """Get butterfly spread dollar premium ($ per contract) at a specific ATM offset.

    Supports both 'initial_fly_premium' and 'fly_premium' column names.
    Respects call side for positive offsets and put side for negative offsets.
    If offset is 0.0 (ATM), computes average of +100 Call fly and -100 Put fly if direct quote not found.
    """
    if fly_df.empty:
        return None

    col = "initial_fly_premium" if "initial_fly_premium" in fly_df.columns else "fly_premium" if "fly_premium" in fly_df.columns else None
    if col is None or "atm_offset" not in fly_df.columns:
        return None

    matches = fly_df[np.isclose(fly_df["atm_offset"], target_offset, atol=1.0)]
    if not matches.empty:
        if target_offset > 0 and "option_side" in matches.columns:
            c = matches[matches["option_side"] == "call"]
            if not c.empty:
                return float(c[col].iloc[0])
            return float(matches[col].iloc[0])
        elif target_offset < 0 and "option_side" in matches.columns:
            p = matches[matches["option_side"] == "put"]
            if not p.empty:
                return float(p[col].iloc[0])
            return float(matches[col].iloc[0])
        else:
            return float(matches[col].mean())

    if target_offset == 0.0:
        c100 = get_fly_premium_at_offset(fly_df, 100.0, allow_interp=False)
        p100 = get_fly_premium_at_offset(fly_df, -100.0, allow_interp=False)
        if c100 is not None and p100 is not None:
            return (c100 + p100) / 2.0

    if not allow_interp or len(fly_df) < 2:
        return None

    min_off = float(fly_df["atm_offset"].min())
    max_off = float(fly_df["atm_offset"].max())
    if target_offset < min_off or target_offset > max_off:
        return None

    sorted_df = fly_df.sort_values("atm_offset").drop_duplicates(subset=["atm_offset"])
    f_interp = interp1d(
        sorted_df["atm_offset"].values,
        sorted_df[col].values,
        kind="linear",
        bounds_error=False,
        fill_value=np.nan,
    )
    val = float(f_interp(target_offset))
    return val if np.isfinite(val) else None


def compute_fly_structure_metrics(
    fly_df: pd.DataFrame,
    offsets: list[float] | None = None,
) -> dict[str, Any]:
    """Compute Call Skew, Put Skew, Risk Reversal, Curvature, and Kurtosis Butterfly spread directly on Butterfly Premiums ($/contract).

    Parameters
    ----------
    fly_df : pd.DataFrame
        DataFrame containing atm_offset, initial_fly_premium (or fly_premium), option_side, etc.
    offsets : list[float], optional
        List of positive offsets to evaluate symmetric butterfly pairs (default [100..800]).

    Returns
    -------
    dict[str, Any]
        Dictionary with atm_fly ($), table DataFrame by offset, 300-pt & 500-pt benchmark metrics, and 4th-degree polynomial coefficients.
    """
    atm_fly = get_fly_premium_at_offset(fly_df, 0.0)

    if offsets is None:
        raw_offsets = [round(abs(x), 1) for x in fly_df["atm_offset"].dropna().tolist() if abs(x) > 1e-4]
        offsets = sorted(list(set(raw_offsets)))
        if not offsets:
            offsets = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]

    rows = []
    for h in offsets:
        h = float(h)
        fc = get_fly_premium_at_offset(fly_df, h)
        fp = get_fly_premium_at_offset(fly_df, -h)
        fc2 = get_fly_premium_at_offset(fly_df, 2.0 * h)
        fp2 = get_fly_premium_at_offset(fly_df, -2.0 * h)

        # Call Skew ($) and Put Skew ($) on Fly Premium
        cs = (fc - atm_fly) if (fc is not None and atm_fly is not None) else None
        ps = (fp - atm_fly) if (fp is not None and atm_fly is not None) else None

        # Fly Risk Reversal ($/fly): Dollar asymmetry between Call Fly and Put Fly
        rr = (fc - fp) if (fc is not None and fp is not None) else None

        # Fly Curvature ($/fly): Convexity of butterfly smile relative to ATM center
        curv = ((fp + fc) / 2.0 - atm_fly) if (fc is not None and fp is not None and atm_fly is not None) else None

        # Fly Kurtosis / Wing Retention Ratio (% of ATM butterfly price retained at offset h)
        kurt_ratio = (((fp + fc) / 2.0) / atm_fly) if (fc is not None and fp is not None and atm_fly and atm_fly > 0) else None

        # Kurtosis Butterfly Spread ($/contract): Outer wing fly vs inner wing fly spread [Fly(2h) - Fly(h)]
        kurt_spread = (((fc2 + fp2) / 2.0) - ((fc + fp) / 2.0)) if (fc2 is not None and fp2 is not None and fc is not None and fp is not None) else None

        # Discrete Butterfly-of-Butterflies (local 2nd difference if h-100 and h-200 exist)
        fc_prev1 = get_fly_premium_at_offset(fly_df, h - 100.0)
        fp_prev1 = get_fly_premium_at_offset(fly_df, -(h - 100.0))
        fc_prev2 = get_fly_premium_at_offset(fly_df, h - 200.0)
        fp_prev2 = get_fly_premium_at_offset(fly_df, -(h - 200.0))
        if fc is not None and fp is not None and fc_prev1 is not None and fp_prev1 is not None and fc_prev2 is not None and fp_prev2 is not None:
            sym_curr = (fc + fp) / 2.0
            sym_p1 = (fc_prev1 + fp_prev1) / 2.0
            sym_p2 = (fc_prev2 + fp_prev2) / 2.0
            kurt_discrete = sym_curr - 2.0 * sym_p1 + sym_p2
        else:
            kurt_discrete = None

        rows.append({
            "offset": h,
            "fly_call": fc,
            "fly_put": fp,
            "call_skew": cs,
            "put_skew": ps,
            "risk_reversal": rr,
            "curvature": curv,
            "kurtosis_ratio": kurt_ratio,
            "kurtosis_spread": kurt_spread,
            "kurtosis_discrete": kurt_discrete,
        })

    table_df = pd.DataFrame(rows)

    # 4th-degree polynomial fit on Fly Premium curve: F(x) = b0 + b1*x + b2*x^2 + b3*x^3 + b4*x^4 with x = offset / 500.0
    col_prem = "initial_fly_premium" if "initial_fly_premium" in fly_df.columns else "fly_premium" if "fly_premium" in fly_df.columns else None
    try:
        if col_prem and len(fly_df) >= 5:
            clean_df = fly_df.dropna(subset=["atm_offset", col_prem]).drop_duplicates(subset=["atm_offset"])
            x_norm = clean_df["atm_offset"].values / 500.0
            y_pts = clean_df[col_prem].values
            poly = np.polyfit(x_norm, y_pts, 4)
            b4 = float(poly[0])
            b3 = float(poly[1])
            b2 = float(poly[2])
            b1 = float(poly[3])
            b0 = float(poly[4])
        else:
            b0, b1, b2, b3, b4 = (atm_fly or 0.0), 0.0, 0.0, 0.0, 0.0
    except Exception:
        b0, b1, b2, b3, b4 = (atm_fly or 0.0), 0.0, 0.0, 0.0, 0.0

    # Benchmarks at 300 pts and 500 pts
    def _extract_fly_benchmark(h_target: float) -> dict[str, float | None]:
        r = table_df[table_df["offset"] == h_target]
        if not r.empty:
            row0 = r.iloc[0]
            return {
                "offset": h_target,
                "fly_call": row0["fly_call"],
                "fly_put": row0["fly_put"],
                "call_skew": row0["call_skew"],
                "put_skew": row0["put_skew"],
                "risk_reversal": row0["risk_reversal"],
                "curvature": row0["curvature"],
                "kurtosis_ratio": row0["kurtosis_ratio"],
                "kurtosis_spread": row0["kurtosis_spread"],
                "kurtosis_discrete": row0["kurtosis_discrete"],
            }
        return {
            "offset": h_target,
            "fly_call": None,
            "fly_put": None,
            "call_skew": None,
            "put_skew": None,
            "risk_reversal": None,
            "curvature": None,
            "kurtosis_ratio": None,
            "kurtosis_spread": None,
            "kurtosis_discrete": None,
        }

    return {
        "atm_fly": atm_fly,
        "table": table_df,
        "benchmark_300": _extract_fly_benchmark(300.0),
        "benchmark_500": _extract_fly_benchmark(500.0),
        "poly_coeffs": {
            "b0_level": b0,
            "b1_skew": b1,
            "b2_curvature": b2,
            "b3_asymmetry": b3,
            "b4_kurtosis": b4,
        },
    }


