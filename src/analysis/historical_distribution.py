"""Historical Distribution Analysis for Options Structures (Causal, Zero-Lookahead).

Calculates where a given structure's value (e.g. 25-Delta Risk Reversal)
lies compared to its strictly prior historical distribution in terms of:
  1. Standard Deviations (Z-Score: (value_t - mean_{<t}) / std_{<t})
  2. Percentile Rank (0% to 100% within history strictly before date t)
  3. Quantiles, dispersion, and rolling lookbacks (expanding, 60D, 120D).
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from config.settings import DEFAULT, OUTPUT_DIR


def compute_causal_distribution_series(
    df: pd.DataFrame,
    structure: str = "RR_25D",
    value_col: str = "market_value",
    min_prior_obs: int = 10,
) -> pd.DataFrame:
    """Compute strictly causal historical distribution stats for every date.

    For date t, the reference distribution H_t consists strictly of {s < t}.
    No observation from date t or after is included in H_t.
    """
    sub = df[df["structure"] == structure].copy()
    if sub.empty:
        raise ValueError(f"Structure '{structure}' not found in dataset")

    sub["trade_date"] = pd.to_datetime(sub["trade_date"]).dt.strftime("%Y-%m-%d")
    sub = sub.sort_values("trade_date").reset_index(drop=True)

    records = []
    values_so_far: list[float] = []
    dates_so_far: list[str] = []

    for idx, row in sub.iterrows():
        t_date = row["trade_date"]
        val = row[value_col]

        if not np.isfinite(val):
            continue

        n_prior = len(values_so_far)
        rec = {
            "trade_date": t_date,
            "structure": structure,
            "value_col": value_col,
            "value": float(val),
            "value_vol_pts": float(val * 100),
            "actual_dte": int(row["actual_dte"]) if "actual_dte" in row and pd.notna(row["actual_dte"]) else None,
            "forward": float(row["forward"]) if "forward" in row and pd.notna(row["forward"]) else None,
            "spot": float(row["spot"]) if "spot" in row and pd.notna(row["spot"]) else None,
            "residual": float(row["residual"]) if "residual" in row and pd.notna(row["residual"]) else None,
            "fair_value": float(row["fair_value"]) if "fair_value" in row and pd.notna(row["fair_value"]) else None,
            "n_prior": n_prior,
            "prior_start": dates_so_far[0] if dates_so_far else None,
            "prior_end": dates_so_far[-1] if dates_so_far else None,
        }

        # Expanding history (all dates strictly before t_date)
        if n_prior >= min_prior_obs:
            arr = np.array(values_so_far, dtype=float)
            mean_exp = float(np.mean(arr))
            std_exp = float(np.std(arr, ddof=1))
            z_exp = (val - mean_exp) / std_exp if std_exp > 1e-12 else 0.0

            # Percentile rank: proportion of prior days <= val
            pct_exp = float((arr <= val).mean() * 100.0)

            rec.update({
                "mean_prior": mean_exp,
                "mean_prior_vol_pts": mean_exp * 100,
                "std_prior": std_exp,
                "std_prior_vol_pts": std_exp * 100,
                "z_score": float(z_exp),
                "percentile_rank": float(pct_exp),
                "min_prior": float(np.min(arr)),
                "p10_prior": float(np.percentile(arr, 10)),
                "q1_prior": float(np.percentile(arr, 25)),
                "median_prior": float(np.median(arr)),
                "q3_prior": float(np.percentile(arr, 75)),
                "p90_prior": float(np.percentile(arr, 90)),
                "max_prior": float(np.max(arr)),
            })

            # Rolling 60-day window strictly prior to t
            if n_prior >= 15:
                w60 = arr[-60:]
                m60 = float(np.mean(w60))
                s60 = float(np.std(w60, ddof=1)) if len(w60) > 1 else 0.0
                rec["rolling60_mean"] = m60
                rec["rolling60_std"] = s60
                rec["rolling60_z"] = (val - m60) / s60 if s60 > 1e-12 else 0.0
                rec["rolling60_pct"] = float((w60 <= val).mean() * 100.0)

            # Rolling 120-day window strictly prior to t
            if n_prior >= 30:
                w120 = arr[-120:]
                m120 = float(np.mean(w120))
                s120 = float(np.std(w120, ddof=1)) if len(w120) > 1 else 0.0
                rec["rolling120_mean"] = m120
                rec["rolling120_std"] = s120
                rec["rolling120_z"] = (val - m120) / s120 if s120 > 1e-12 else 0.0
                rec["rolling120_pct"] = float((w120 <= val).mean() * 100.0)

        else:
            rec.update({
                "mean_prior": None,
                "mean_prior_vol_pts": None,
                "std_prior": None,
                "std_prior_vol_pts": None,
                "z_score": None,
                "percentile_rank": None,
                "min_prior": None,
                "p10_prior": None,
                "q1_prior": None,
                "median_prior": None,
                "q3_prior": None,
                "p90_prior": None,
                "max_prior": None,
            })

        records.append(rec)

        # Update historical cache with date t's value for FUTURE dates
        values_so_far.append(float(val))
        dates_so_far.append(t_date)

    return pd.DataFrame(records)


def get_aug_sep_2026_analysis(structure: str = "RR_25D") -> pd.DataFrame:
    """Load structures and return the complete daily analysis for August and September 2026."""
    struct_path = OUTPUT_DIR / "structures" / "structures.csv"
    if not struct_path.exists():
        raise FileNotFoundError(f"Structures file {struct_path} does not exist.")
    df = pd.read_csv(struct_path)
    res = compute_causal_distribution_series(df, structure=structure, value_col="market_value")
    aug_sep = res[res["trade_date"].str.startswith("2026-08") | res["trade_date"].str.startswith("2026-09")].copy()
    return aug_sep


def export_distribution_payload() -> dict:
    """Precompute distribution statistics for primary key structures and export JSON for the dashboard."""
    struct_path = OUTPUT_DIR / "structures" / "structures.csv"
    df = pd.read_csv(struct_path)
    
    key_structures = [
        "RR_25D", "RR_10D", "RR_15D", "RR_20D", "RR_30D",
        "BF_25D", "BF_10D", "BF_20D", "ATM_IV"
    ]
    
    results = {}
    for st in key_structures:
        if st in df["structure"].values:
            dist_market = compute_causal_distribution_series(df, structure=st, value_col="market_value")
            dist_resid = compute_causal_distribution_series(df, structure=st, value_col="residual")
            results[st] = {
                "market_value": json.loads(dist_market.to_json(orient="records")),
                "residual": json.loads(dist_resid.to_json(orient="records")),
            }
            
    return results


if __name__ == "__main__":
    print("Testing 25D Risk Reversal causal analysis for August & September 2026...")
    df_aug_sep = get_aug_sep_2026_analysis("RR_25D")
    print(f"Total trading days in Aug + Sep 2026: {len(df_aug_sep)}")
    display_cols = [
        "trade_date", "actual_dte", "value_vol_pts", "n_prior",
        "mean_prior_vol_pts", "std_prior_vol_pts", "z_score", "percentile_rank"
    ]
    print(df_aug_sep[display_cols].to_string(index=False))
