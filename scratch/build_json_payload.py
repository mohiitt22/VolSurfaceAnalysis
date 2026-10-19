"""Generate standalone precalculated HTML dashboard for SPX Volatility Surface Analysis.

Extracts data from sticky_delta_2026-10-12_2025-06-05.xlsx, computes multi-date
factors, smile points, butterfly spreads, 5-stage decomposition bridge, and
outputs a completely self-contained, responsive, dark-mode quant web application.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Ensure workspace root in path
workspace_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(workspace_dir))
os.chdir(str(workspace_dir))

from spx_butterfly.data_loader import load_raw_dataset, transform_to_long_form, get_available_dates, get_snapshot
from spx_butterfly.multidate_model import (
    calculate_daily_factors,
    fit_factors_between_dates,
    decompose_iv_smile,
    build_multidate_flies,
    compute_observed_fly_differences,
    compute_fixed_fly_attribution,
    extract_smile_points,
    compute_smile_structure_metrics,
)

print("Loading raw dataset...")
raw = load_raw_dataset("sticky_delta_2026-10-12_2025-06-05.xlsx")
long_df = transform_to_long_form(raw)
all_dates = get_available_dates(long_df)
print(f"Loaded {len(all_dates)} historical dates.")

# Build flies for all dates
print("Building butterfly spreads for all dates...")
all_flies_dict = build_multidate_flies(long_df, all_dates, wing_width=100.0)

# Build date metadata and smile curves
print("Extracting smile points and factors...")
dates_data = {}
all_factor_history = []

for d in all_dates:
    snap = long_df[long_df["date"] == d]
    smile = extract_smile_points(snap)
    f = calculate_daily_factors(snap, 500.0)
    
    spot = float(snap["underlying"].iloc[0])
    atm_k = float(snap["atm_strike"].iloc[0])
    dte = float(snap["target_dte"].iloc[0])
    
    lvl = f.get("level")
    skw = f.get("skew")
    crv = f.get("curvature")
    
    all_factor_history.append({
        "date": d,
        "spot": spot,
        "atm_strike": atm_k,
        "target_dte": dte,
        "level": round(lvl, 4) if lvl is not None else None,
        "skew": round(skw, 4) if skw is not None else None,
        "curvature": round(crv, 4) if crv is not None else None,
    })
    
    d_flies = all_flies_dict.get(d, [])
    call_flies = [
        {
            "centre": float(fly.centre_strike),
            "offset": float(fly.atm_offset),
            "lower": float(fly.lower_strike),
            "upper": float(fly.upper_strike),
            "prem": round(float(fly.fly_premium), 4),
            "norm_prem": round(float(fly.normalized_premium), 4),
        }
        for fly in d_flies if fly.option_side == "call"
    ]
    put_flies = [
        {
            "centre": float(fly.centre_strike),
            "offset": float(fly.atm_offset),
            "lower": float(fly.lower_strike),
            "upper": float(fly.upper_strike),
            "prem": round(float(fly.fly_premium), 4),
            "norm_prem": round(float(fly.normalized_premium), 4),
        }
        for fly in d_flies if fly.option_side == "put"
    ]
    
    smile_records = []
    for _, r in smile.iterrows():
        smile_records.append({
            "strike": float(r["strike"]),
            "offset": float(r["atm_offset"]),
            "side": str(r["option_side"]),
            "iv": round(float(r["iv_pct"]), 4),
            "prem": round(float(r["premium"]), 4),
        })

    # Higher-order smile structure metrics (Call/Put Skew, RR, Curvature, Kurtosis)
    struct_res = compute_smile_structure_metrics(smile)
    table_records = []
    for _, row_s in struct_res["table"].iterrows():
        table_records.append({
            "offset": float(row_s["offset"]),
            "call_skew": round(float(row_s["call_skew"]), 4) if row_s["call_skew"] is not None else None,
            "put_skew": round(float(row_s["put_skew"]), 4) if row_s["put_skew"] is not None else None,
            "risk_reversal": round(float(row_s["risk_reversal"]), 4) if row_s["risk_reversal"] is not None else None,
            "curvature": round(float(row_s["curvature"]), 4) if row_s["curvature"] is not None else None,
            "kurtosis_ratio": round(float(row_s["kurtosis_ratio"]), 4) if row_s["kurtosis_ratio"] is not None else None,
        })
    b300 = struct_res["benchmark_300"]
    poly = struct_res["poly_coeffs"]

    dates_data[d] = {
        "spot": spot,
        "atm_strike": atm_k,
        "dte": dte,
        "level": round(lvl, 4) if lvl is not None else None,
        "skew": round(skw, 4) if skw is not None else None,
        "curvature": round(crv, 4) if crv is not None else None,
        "smile": smile_records,
        "call_flies": call_flies,
        "put_flies": put_flies,
        "structure": {
            "table": table_records,
            "benchmark_300": {k: (round(float(v), 4) if v is not None else None) for k, v in b300.items()},
            "poly_coeffs": {k: (round(float(v), 4) if v is not None else None) for k, v in poly.items()},
        },
    }

# Compute precalculated benchmark pair (2026-08-03 to 2026-08-04)
ref_snap = get_snapshot(long_df, "2026-08-03")
focus_snap = get_snapshot(long_df, "2026-08-04")
bench_factors = fit_factors_between_dates(ref_snap, focus_snap, 500.0, "anchor")
bench_bridge = decompose_iv_smile(ref_snap, focus_snap, bench_factors, 500.0)
bench_diffs = compute_observed_fly_differences(all_flies_dict, "2026-08-03", "2026-08-04", 100.0)
bench_attrs = compute_fixed_fly_attribution(ref_snap, focus_snap, bench_factors, 100.0, 500.0)

benchmark_precalc = {
    "ref_date": "2026-08-03",
    "focus_date": "2026-08-04",
    "delta_level": round(bench_factors.delta_level, 4),
    "delta_skew": round(bench_factors.delta_skew, 4),
    "delta_curvature": round(bench_factors.delta_curvature, 4),
    "rmse": round(bench_factors.rmse, 4),
    "ref_level": round(bench_factors.ref_level, 4),
    "focus_level": round(bench_factors.focus_level, 4),
    "bridge": [p.to_dict() for p in bench_bridge],
    "diffs": [d.to_dict() for d in bench_diffs],
    "attributions": [a.to_dict() for a in bench_attrs],
}

print("Benchmark precalc completed successfully.")
print(f"Exporting JSON structures...")

payload = {
    "all_dates": all_dates,
    "dates_data": dates_data,
    "factor_history": all_factor_history,
    "benchmark": benchmark_precalc,
}

json_str = json.dumps(payload, separators=(',', ':'))
print(f"Total compact JSON payload: {len(json_str) / 1024:.1f} KB")

output_json_path = workspace_dir / "spx_precalculated_data.json"
with open(output_json_path, "w", encoding="utf-8") as f:
    f.write(json_str)

print(f"Saved {output_json_path}")
