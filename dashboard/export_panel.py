"""Export a lean JSON panel for the strategy dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "data"
OUT.mkdir(parents=True, exist_ok=True)

COLS = [
    "trade_date",
    "structure",
    "kind",
    "legs",
    "side",
    "delta",
    "delta_2",
    "market_value",
    "fair_value",
    "residual",
    "price_residual",
    "market_price",
    "fair_price",
    "z_20_residual",
    "z_60_residual",
    "z_120_residual",
    "z_252_residual",
    "pct_60_residual",
    "z_60_market_value",
    "pct_60_market_value",
    "atm_iv",
    "rv_20",
    "rv_60",
    "iv_rv_20",
    "actual_dte",
    "spot_x",
    "forward",
    "extrapolated",
    "liquidity_score",
    "convergence_h5",
    "converged_h5",
]


def _num(x):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    if pd.isna(x):
        return None
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return round(float(x), 6)
    return x


def main() -> None:
    src = ROOT / "outputs" / "structures" / "structures_enriched.csv"
    dte = ROOT / "outputs" / "surfaces" / "dte_selection.csv"
    wf = ROOT / "outputs" / "models" / "walkforward_scores.csv"
    bt = ROOT / "outputs" / "backtests" / "summary.json"

    df = pd.read_csv(src, usecols=lambda c: c in COLS)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    for c in df.columns:
        if c not in ("trade_date", "structure", "kind", "legs", "side"):
            if df[c].dtype == bool or str(df[c].dtype) == "boolean":
                continue
            df[c] = pd.to_numeric(df[c], errors="coerce")

    catalog = (
        df[["structure", "kind", "legs", "side", "delta", "delta_2"]]
        .drop_duplicates("structure")
        .sort_values(["kind", "structure"])
    )
    catalog = catalog.replace({np.nan: None})

    # Historical performance by structure (research dates only, labels exist)
    research = df.loc[df["trade_date"] <= "2026-09-08"].copy()
    stats = []
    for name, g in research.groupby("structure"):
        c = g["convergence_h5"].dropna()
        z = g["z_60_residual"]
        ext = g.loc[z.abs() >= 1.5, "convergence_h5"].dropna()
        stats.append(
            {
                "structure": name,
                "kind": g["kind"].iloc[0],
                "n": int(len(g)),
                "n_conv": int(len(c)),
                "mean_conv_h5": _num(c.mean()) if len(c) else None,
                "hit_conv_h5": _num((c > 0).mean()) if len(c) else None,
                "n_extreme": int(len(ext)),
                "mean_conv_extreme": _num(ext.mean()) if len(ext) else None,
                "hit_extreme": _num((ext > 0).mean()) if len(ext) else None,
                "mean_abs_residual": _num(g["residual"].abs().mean()),
            }
        )

    dte_df = pd.read_csv(dte)
    dte_df["trade_date"] = pd.to_datetime(dte_df["trade_date"]).dt.strftime("%Y-%m-%d")
    dte_slim = dte_df[
        [
            "trade_date",
            "selected_expiry",
            "actual_dte",
            "dte_error",
            "exact_match",
            "contract",
            "put_delta_convention",
        ]
    ].to_dict(orient="records")
    for r in dte_slim:
        for k, v in list(r.items()):
            r[k] = _num(v) if not isinstance(v, str) else v

    wf_rows = []
    if wf.exists():
        wdf = pd.read_csv(wf)
        wf_rows = json.loads(wdf.to_json(orient="records"))

    summary = {}
    if bt.exists():
        summary = json.loads(bt.read_text(encoding="utf-8"))

    rows = []
    for rec in df.itertuples(index=False):
        item = {c: _num(getattr(rec, c)) if c not in ("trade_date", "structure", "kind", "legs", "side") else getattr(rec, c) for c in df.columns}
        # side may be nan
        if item.get("side") is not None and (item["side"] != item["side"] or item["side"] == "nan"):
            item["side"] = None
        rows.append(item)

    dates = sorted(df["trade_date"].unique().tolist())
    payload = {
        "meta": {
            "train_start": "2025-06-05",
            "train_end": "2026-09-08",
            "test_date": "2026-09-11",
            "target_dte": 60,
            "frozen_z": 3.0,
            "default_z": 1.5,
            "n_dates": len(dates),
            "n_structures": int(df["structure"].nunique()),
            "n_rows": len(rows),
            "notes": (
                "CHEAP / EXPENSIVE require residual and historical z to agree "
                "and |z| to clear the selected gate. Otherwise CANNOT DECIDE. "
                "Frozen production gate is 3.0. 11 Sep 2026 is the holdout."
            ),
        },
        "dates": dates,
        "catalog": catalog.to_dict(orient="records"),
        "stats": stats,
        "dte": dte_slim,
        "walkforward": wf_rows,
        "backtest": summary,
        "rows": rows,
    }
    path = OUT / "panel.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path} bytes={path.stat().st_size} rows={len(rows)}")


if __name__ == "__main__":
    main()
