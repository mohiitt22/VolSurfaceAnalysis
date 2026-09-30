"""Export historical distribution analysis data for the dashboard.

Generates dashboard/data/distribution_analysis.json containing strictly causal
historical distribution statistics (Z-score in standard deviations and Percentile)
for 25-Delta Risk Reversal (RR_25D) and all major volatility structures across
every trading day in August 2026, September 2026 (through 2026-09-22), and all
historical dates in the dataset.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from src.analysis.historical_distribution import compute_causal_distribution_series

OUT = ROOT / "dashboard" / "data" / "distribution_analysis.json"


def generate_distribution_json() -> None:
    struct_path = ROOT / "outputs" / "structures" / "structures.csv"
    if not struct_path.exists():
        raise FileNotFoundError(f"Structures file {struct_path} not found.")

    df = pd.read_csv(struct_path)
    
    structures_to_analyze = [
        "RR_25D", "RR_10D", "RR_15D", "RR_20D", "RR_30D",
        "BF_25D", "BF_10D", "BF_20D", "ATM_IV"
    ]
    
    out_data = {
        "meta": {
            "title": "Historical Distribution Analysis (Zero-Lookahead Causal)",
            "description": "Calculates location of option structures vs historical distribution strictly prior to date t",
            "focus_months": ["2026-08", "2026-09"],
            "max_date": str(df["trade_date"].max())[:10],
            "min_date": str(df["trade_date"].min())[:10],
            "primary_structure": "RR_25D",
        },
        "structures": {},
    }

    for s in structures_to_analyze:
        if s not in df["structure"].values:
            continue
        print(f"Computing distribution for {s}...")
        mkt = compute_causal_distribution_series(df, structure=s, value_col="market_value")
        res = compute_causal_distribution_series(df, structure=s, value_col="residual")
        
        # Keep clean serializable records
        out_data["structures"][s] = {
            "market_value": json.loads(mkt.to_json(orient="records")),
            "residual": json.loads(res.to_json(orient="records")),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out_data, separators=(",", ":")), encoding="utf-8")
    print(f"Successfully generated {OUT} (size: {OUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    generate_distribution_json()
