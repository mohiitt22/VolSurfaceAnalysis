"""Turn a sticky-delta workbook into the payload for one dashboard tab.

The only choosable files are the 12 Oct 2026 and 16 Oct 2026 chains.
A tab is replaced only when that chain meets the tab's requirements.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
SOURCE_STEMS = (
    "sticky_delta_2026-10-12_2025-06-05",
    "sticky_delta_2026-10-16_2025-06-05",
)
RATE = 0.045
DELTAS = (10, 15, 20, 25, 30)


def source_catalog() -> list[dict]:
    skip = {".git", ".venv", ".pytest_cache", "__pycache__", "node_modules", ".vercel", ".cache", "SNP data"}
    found: dict[str, Path] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in skip for part in path.parts):
            continue
        if path.suffix.lower() not in {".xlsx", ".xls", ".csv"}:
            continue
        if path.stem not in SOURCE_STEMS:
            continue
        current = found.get(path.name)
        if current is None or len(path.relative_to(ROOT).parts) < len(current.relative_to(ROOT).parts):
            found[path.name] = path
    rows = []
    for name in sorted(found):
        path = found[name]
        end = "16 Oct 2026" if "2026-10-16" in name else "12 Oct 2026"
        rows.append({
            "path": path.relative_to(ROOT).as_posix(),
            "label": f"Through {end} ({path.suffix.lower().lstrip('.')})",
            "bytes": path.stat().st_size,
        })
    return rows


def load_chain(path: Path):
    from spx_butterfly.data_loader import load_raw_dataset, transform_to_long_form
    from spx_butterfly.data_validation import validate_surface_data

    raw = load_raw_dataset(path)
    long_df = transform_to_long_form(raw)
    report = validate_surface_data(long_df)
    if report["errors"]:
        raise ValueError("validate_surface_data: " + "; ".join(report["errors"]))
    if long_df.empty:
        raise ValueError("The file has no option rows after cleaning.")
    return long_df, report["warnings"], read_grids(raw)


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


def read_grids(raw: pd.DataFrame) -> tuple[dict, dict]:
    """Strike-wise nodes are Label 2. Delta-wise nodes are Label 1."""
    from spx_butterfly.data_loader import _normalize_col_names

    frame = _normalize_col_names(raw.copy())
    frame["date"] = pd.to_datetime(frame["Date"]).dt.strftime("%Y-%m-%d")
    strike: dict[str, list] = {}
    delta: dict[str, list] = {}
    for row in frame.to_dict("records"):
        day = row["date"]
        strike.setdefault(day, []).append({
            "label": str(row.get("Label 2") or "").strip(),
            "side": str(row.get("Side 2") or "").strip().lower(),
            "strike": _num(row.get("Strike 2")),
            "iv": None if _num(row.get("IV 2")) is None else _num(row.get("IV 2")) * 100.0,
            "prem": _num(row.get("Premium 2")),
            "delta": _num(row.get("Delta 2")),
            "vega": _num(row.get("Vega 2")),
        })
        delta.setdefault(day, []).append({
            "label": str(row.get("Label 1") or "").strip(),
            "side": str(row.get("Side 1") or "").strip().lower(),
            "strike": _num(row.get("Strike 1")),
            "iv": None if _num(row.get("IV 1")) is None else _num(row.get("IV 1")) * 100.0,
            "prem": _num(row.get("Premium 1")),
            "delta": _num(row.get("Delta 1")),
            "vega": _num(row.get("Vega 1")),
        })
    return strike, delta


def _summary(long_df: pd.DataFrame, warnings: list[str]) -> str:
    dates = sorted(long_df["date"].unique())
    dte = sorted({round(float(v), 1) for v in long_df["target_dte"].dropna().unique()})
    text = (
        f"{len(dates)} sessions, {dates[0]} through {dates[-1]}, "
        f"{len(long_df)} smile rows, target DTE {', '.join(str(v) for v in dte)}."
    )
    if warnings:
        text += " Warnings: " + "; ".join(warnings)
    return text


def _round(value, digits):
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return None
    return round(float(value), digits)


def build_surface(long_df: pd.DataFrame, strike_grid: dict | None = None, delta_grid: dict | None = None) -> dict:
    from spx_butterfly.data_loader import get_available_dates, get_snapshot
    from spx_butterfly.multidate_model import (
        build_multidate_flies,
        calculate_daily_factors,
        compute_smile_structure_metrics,
        extract_smile_points,
    )

    dates = get_available_dates(long_df)
    flies = build_multidate_flies(long_df, dates, wing_width=100.0)
    dates_data = {}
    history = []
    for day in dates:
        snap = get_snapshot(long_df, day)
        smile = extract_smile_points(snap)
        factors = calculate_daily_factors(snap, 500.0)
        spot = float(snap["underlying"].iloc[0])
        atm = float(snap["atm_strike"].iloc[0])
        dte = float(snap["target_dte"].iloc[0])
        level = factors.get("level")
        skew = factors.get("skew")
        curvature = factors.get("curvature")
        history.append({
            "date": day,
            "spot": spot,
            "atm_strike": atm,
            "target_dte": dte,
            "level": _round(level, 4),
            "skew": _round(skew, 4),
            "curvature": _round(curvature, 4),
        })
        struct = compute_smile_structure_metrics(smile)
        table = []
        for _, row in struct["table"].iterrows():
            table.append({
                "offset": float(row["offset"]),
                "call_skew": _round(row["call_skew"], 4),
                "put_skew": _round(row["put_skew"], 4),
                "risk_reversal": _round(row["risk_reversal"], 4),
                "curvature": _round(row["curvature"], 4),
                "kurtosis_ratio": _round(row["kurtosis_ratio"], 4),
            })
        day_flies = flies.get(day, [])
        extras = {}
        for node in (strike_grid or {}).get(day, []):
            if node["strike"] is None:
                continue
            extras[(str(node["side"])[:1], round(float(node["strike"]), 2))] = node
        smile_rows = []
        for _, row in smile.iterrows():
            extra = extras.get((str(row["option_side"])[:1], round(float(row["strike"]), 2)), {})
            smile_rows.append({
                "strike": float(row["strike"]),
                "offset": float(row["atm_offset"]),
                "side": str(row["option_side"]),
                "label": extra.get("label") or None,
                "iv": _round(row["iv_pct"], 4),
                "prem": _round(row["premium"], 4),
                "delta": _round(extra.get("delta"), 4),
                "vega": _round(extra.get("vega"), 4),
            })
        delta_nodes = []
        for node in (delta_grid or {}).get(day, []):
            if node["iv"] is None or node["delta"] is None or node["strike"] is None:
                continue
            delta_nodes.append({
                "label": node["label"],
                "side": node["side"],
                "strike": _round(node["strike"], 4),
                "iv": _round(node["iv"], 4),
                "prem": _round(node["prem"], 4),
                "delta": _round(node["delta"], 4),
                "vega": _round(node["vega"], 4),
            })
        dates_data[day] = {
            "spot": spot,
            "atm_strike": atm,
            "dte": dte,
            "level": _round(level, 4),
            "skew": _round(skew, 4),
            "curvature": _round(curvature, 4),
            "smile": smile_rows,
            "delta_nodes": delta_nodes,
            "call_flies": [_fly(fly) for fly in day_flies if fly.option_side == "call"],
            "put_flies": [_fly(fly) for fly in day_flies if fly.option_side == "put"],
            "structure": {
                "table": table,
                "benchmark_300": {k: _round(v, 4) if isinstance(v, float) else v for k, v in struct["benchmark_300"].items()},
                "poly_coeffs": {k: _round(v, 4) for k, v in struct["poly_coeffs"].items()},
            },
        }
    return {"all_dates": dates, "dates_data": dates_data, "factor_history": history}


def _fly(fly) -> dict:
    return {
        "centre": float(fly.centre_strike),
        "offset": float(fly.atm_offset),
        "lower": float(fly.lower_strike),
        "upper": float(fly.upper_strike),
        "prem": _round(fly.fly_premium, 4),
        "norm_prem": _round(fly.normalized_premium, 4),
    }


def _market_series(delta_grid: dict, long_df: pd.DataFrame) -> dict[str, list[dict]]:
    """Risk reversals and flies from the file's own delta nodes, not a fitted delta."""
    meta = {}
    for day, snap in long_df.groupby("date", sort=True):
        meta[str(day)] = (float(snap["underlying"].iloc[0]), float(snap["target_dte"].iloc[0]))
    series: dict[str, list[dict]] = {"ATM_IV": []}
    for delta in (10, 15, 20, 25, 30):
        series[f"RR_{delta}D"] = []
    for delta in (10, 20, 25):
        series[f"BF_{delta}D"] = []
    for day in sorted(delta_grid):
        nodes = {str(node["label"]).strip().lower(): node for node in delta_grid[day]}
        atm = nodes.get("atm")
        if not atm or atm["iv"] is None:
            continue
        spot, dte = meta.get(day, (None, None))
        base = {"trade_date": day, "actual_dte": dte, "spot": spot, "forward": None}
        series["ATM_IV"].append({**base, "value": atm["iv"] / 100.0})
        for delta in (10, 15, 20, 25, 30):
            call = nodes.get(f"{delta} delta call")
            put = nodes.get(f"{delta} delta put")
            if not call or not put or call["iv"] is None or put["iv"] is None:
                continue
            series[f"RR_{delta}D"].append({**base, "value": (call["iv"] - put["iv"]) / 100.0})
            if delta in (10, 20, 25):
                series[f"BF_{delta}D"].append({
                    **base,
                    "value": ((call["iv"] + put["iv"]) / 2.0 - atm["iv"]) / 100.0,
                })
    return series


def _causal(points: list[dict]) -> list[dict]:
    history: list[float] = []
    dates: list[str] = []
    out = []
    for point in points:
        value = float(point["value"])
        if not np.isfinite(value):
            continue
        record = _causal_record(point, value, history, dates)
        out.append(record)
        history.append(value)
        dates.append(point["trade_date"])
    return out


def _window_stats(history: list[float], value: float):
    if len(history) < 10:
        return None, None, None, None
    arr = np.asarray(history, dtype=float)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
    z = (value - mean) / std if std > 1e-12 else 0.0
    pct = float(np.mean(arr <= value) * 100)
    return mean, std, z, pct


def _causal_record(point, value, history, dates):
    mean, std, z, pct = _window_stats(history, value)
    roll60 = _window_stats(history[-60:], value) if len(history) >= 15 else (None, None, None, None)
    roll120 = _window_stats(history[-120:], value) if len(history) >= 30 else (None, None, None, None)
    ordered = sorted(history)
    return {
        "trade_date": point["trade_date"],
        "value": value,
        "value_vol_pts": value * 100,
        "actual_dte": point["actual_dte"],
        "spot": point["spot"],
        "forward": point["forward"],
        "residual": None,
        "fair_value": None,
        "n_prior": len(history),
        "prior_start": dates[0] if dates else None,
        "prior_end": dates[-1] if dates else None,
        "mean_prior": mean,
        "std_prior": std,
        "z_score": z,
        "percentile_rank": pct,
        "min_prior": ordered[0] if ordered else None,
        "median_prior": ordered[len(ordered) // 2] if ordered else None,
        "max_prior": ordered[-1] if ordered else None,
        "prior_values": list(history),
        "rolling60_mean": roll60[0],
        "rolling60_std": roll60[1],
        "rolling60_z": roll60[2],
        "rolling60_pct": roll60[3],
        "rolling120_mean": roll120[0],
        "rolling120_std": roll120[1],
        "rolling120_z": roll120[2],
        "rolling120_pct": roll120[3],
    }


def build_distribution(long_df: pd.DataFrame, delta_grid: dict) -> dict:
    dates = sorted(long_df["date"].unique())
    structures = {}
    for name, points in _market_series(delta_grid, long_df).items():
        market = _causal(points)
        if len(market) < 11:
            continue
        structures[name] = {"market_value": market}
    if "ATM_IV" not in structures and not structures:
        raise ValueError("The chain did not produce an ATM IV series, so the distribution lab has nothing to plot.")
    return {
        "meta": {
            "title": "Historical distribution from the selected smile chain",
            "description": "Market IV only. This workbook has no fair-smile residual.",
            "primary_structure": "RR_25D" if "RR_25D" in structures else "ATM_IV",
            "min_date": dates[0],
            "max_date": dates[-1],
            "focus_months": [],
        },
        "dte": [
            {"trade_date": day, "actual_dte": float(group["target_dte"].iloc[0]), "selected_expiry": None}
            for day, group in long_df.groupby("date", sort=True)
        ],
        "structures": structures,
    }


def cached_surface(path: Path, long_df: pd.DataFrame, warnings: list[str], strike_grid: dict, delta_grid: dict) -> str:
    CACHE.mkdir(exist_ok=True)
    stamp = f"{path.stat().st_mtime_ns}-{path.stat().st_size}"
    cache = CACHE / f"surface-v2-{path.stem}-{stamp}.json"
    if not cache.exists():
        payload = build_surface(long_df, strike_grid, delta_grid)
        payload["source"] = {
            "file": path.name,
            "summary": _summary(long_df, warnings),
        }
        cache.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return cache.relative_to(ROOT).as_posix()


def prepare(rel: str, tab: str) -> dict:
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    path = (ROOT / rel).resolve()
    if path.name not in {stem + suffix for stem in SOURCE_STEMS for suffix in (".xlsx", ".xls", ".csv")}:
        raise ValueError("Only the 12 Oct 2026 and 16 Oct 2026 workbooks can be selected.")
    if not path.is_file():
        raise ValueError(f"File not found: {rel}")
    long_df, warnings, grids = load_chain(path)
    strike_grid, delta_grid = grids
    summary = _summary(long_df, warnings)
    if tab == "strategy":
        raise ValueError(
            "The workbook itself loaded (" + summary + ") "
            "The strategy desk also requires fair value, residual, and z_60_residual for each structure. "
            "This file is a smile chain and does not have those columns, so the desk was not replaced."
        )
    if tab in {"surface", "spread"}:
        cache = cached_surface(path, long_df, warnings, strike_grid, delta_grid)
        return {"ok": True, "kind": "surface", "summary": summary, "cache": cache, "where": "tools/prepare_source.py"}
    if tab == "distribution":
        payload = build_distribution(long_df, delta_grid)
        if not payload["structures"]:
            raise ValueError("No structure had enough history to plot. " + summary)
        return {"ok": True, "kind": "distribution", "summary": summary, "payload": payload, "where": "tools/prepare_source.py"}
    raise ValueError(f"Unknown tab {tab}.")
