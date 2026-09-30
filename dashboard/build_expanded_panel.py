"""Build an expanded structure panel from saved 60-DTE surfaces.

Does not refit smiles or retune the z-gate.  Adds every RR / butterfly /
delta-point / slope pair plus listed strikes (z-scored via log-moneyness bins).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "data"
OUT.mkdir(parents=True, exist_ok=True)

DELTAS = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45)
MAX_EXTRAP = 0.03
KBIN = 0.02
FROZEN_Z = 3.0
TRAIN_END = "2026-09-08"
TEST_DATE = "2026-09-11"


def _n(x):
    if x is None or (isinstance(x, float) and not np.isfinite(x)) or pd.isna(x):
        return None
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return round(float(x), 6)
    return x


def _interp(x, y, x0):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 2:
        return np.nan, True
    order = np.argsort(x)
    x, y = x[order], y[order]
    _, idx = np.unique(x, return_index=True)
    x, y = x[idx], y[idx]
    if len(x) < 2:
        return np.nan, True
    extra = bool(x0 < x[0] - 1e-12 or x0 > x[-1] + 1e-12)
    if extra:
        edge = x[0] if x0 < x[0] else x[-1]
        if abs(x0 - edge) > MAX_EXTRAP:
            return np.nan, True
    f = interp1d(x, y, kind="linear", fill_value="extrapolate", assume_sorted=True)
    return float(f(x0)), extra


def _grid(g: pd.DataFrame) -> dict:
    out = {"atm_m": np.nan, "atm_f": np.nan, "atm_x": False}
    if g.empty:
        return out
    atm = g.iloc[g["k"].abs().to_numpy().argmin()]
    out["atm_m"] = float(atm["market_iv"])
    out["atm_f"] = float(atm["fair_iv_ensemble"])
    for side, xcol in (("P", "put_delta_abs"), ("C", "call_delta_abs")):
        x = g[xcol].to_numpy(dtype=float)
        ym = g["market_iv"].to_numpy(dtype=float)
        yf = g["fair_iv_ensemble"].to_numpy(dtype=float)
        for d in DELTAS:
            m, xe = _interp(x, ym, d)
            f, fe = _interp(x, yf, d)
            out[f"{side}{int(d*100)}_m"] = m
            out[f"{side}{int(d*100)}_f"] = f
            out[f"{side}{int(d*100)}_x"] = bool(xe or fe)
    return out


def _row(date, structure, kind, legs, market, fair, extra=None, history_id=None):
    rec = {
        "trade_date": date,
        "structure": structure,
        "history_id": history_id or structure,
        "kind": kind,
        "legs": legs,
        "market_value": market,
        "fair_value": fair,
        "residual": (market - fair) if np.isfinite(market) and np.isfinite(fair) else np.nan,
        "extrapolated": False,
    }
    if extra:
        rec.update(extra)
    return rec


def structures_for_day(g: pd.DataFrame) -> list[dict]:
    date = pd.Timestamp(g["trade_date"].iloc[0]).strftime("%Y-%m-%d")
    dte = int(g["actual_dte"].iloc[0])
    fwd = float(g["forward"].iloc[0])
    spot = float(g["spot"].iloc[0])
    grid = _grid(g)
    rows = []
    extra_base = {"actual_dte": dte, "forward": fwd, "spot_x": spot, "atm_iv": grid["atm_m"]}

    rows.append(
        _row(date, "POINT_ATM", "point", "ATM listed / min |k|", grid["atm_m"], grid["atm_f"], extra_base)
    )
    for d in DELTAS:
        di = int(d * 100)
        for side, lab in (("P", "put"), ("C", "call")):
            m, f, x = grid[f"{side}{di}_m"], grid[f"{side}{di}_f"], grid[f"{side}{di}_x"]
            rec = _row(
                date,
                f"POINT_{di}{side}",
                "point",
                f"{di}D {lab} IV",
                m,
                f,
                {**extra_base, "delta": d, "side": lab, "extrapolated": x},
            )
            rec["extrapolated"] = x
            rows.append(rec)

    for d in DELTAS:
        di = int(d * 100)
        cm, cf, cx = grid[f"C{di}_m"], grid[f"C{di}_f"], grid[f"C{di}_x"]
        pm, pf, px = grid[f"P{di}_m"], grid[f"P{di}_f"], grid[f"P{di}_x"]
        rec = _row(
            date,
            f"RR_{di}D",
            "risk_reversal",
            f"+{di}DC / -{di}DP",
            cm - pm if np.isfinite(cm) and np.isfinite(pm) else np.nan,
            cf - pf if np.isfinite(cf) and np.isfinite(pf) else np.nan,
            {**extra_base, "delta": d, "extrapolated": bool(cx or px)},
        )
        rec["extrapolated"] = bool(cx or px)
        rows.append(rec)
        rec = _row(
            date,
            f"BF_{di}D",
            "butterfly",
            f"{di}DP / ATM / {di}DC",
            0.5 * (pm + cm) - grid["atm_m"] if np.isfinite(pm) and np.isfinite(cm) else np.nan,
            0.5 * (pf + cf) - grid["atm_f"] if np.isfinite(pf) and np.isfinite(cf) else np.nan,
            {**extra_base, "delta": d, "extrapolated": bool(cx or px)},
        )
        rec["extrapolated"] = bool(cx or px)
        rows.append(rec)

    # Slopes: ATM -> wing, and every far/near pair on each wing.
    for d in DELTAS:
        di = int(d * 100)
        for side, lab in (("P", "put"), ("C", "call")):
            m, f, x = grid[f"{side}{di}_m"], grid[f"{side}{di}_f"], grid[f"{side}{di}_x"]
            rec = _row(
                date,
                f"SLOPE_ATM_{di}{side}",
                "slope",
                f"ATM → {di}D {lab}",
                m - grid["atm_m"] if np.isfinite(m) else np.nan,
                f - grid["atm_f"] if np.isfinite(f) else np.nan,
                {**extra_base, "delta": d, "side": lab, "extrapolated": x},
            )
            rec["extrapolated"] = x
            rows.append(rec)
    for i, d1 in enumerate(DELTAS):
        for d2 in DELTAS[i + 1 :]:
            a, b = int(d1 * 100), int(d2 * 100)  # a further OTM (smaller delta)
            for side, lab in (("P", "put"), ("C", "call")):
                m1, f1, x1 = grid[f"{side}{a}_m"], grid[f"{side}{a}_f"], grid[f"{side}{a}_x"]
                m2, f2, x2 = grid[f"{side}{b}_m"], grid[f"{side}{b}_f"], grid[f"{side}{b}_x"]
                rec = _row(
                    date,
                    f"SLOPE_{a}{side}_{b}{side}",
                    "slope",
                    f"{a}D {lab} − {b}D {lab}",
                    m1 - m2 if np.isfinite(m1) and np.isfinite(m2) else np.nan,
                    f1 - f2 if np.isfinite(f1) and np.isfinite(f2) else np.nan,
                    {**extra_base, "delta": d1, "delta_2": d2, "side": lab, "extrapolated": bool(x1 or x2)},
                )
                rec["extrapolated"] = bool(x1 or x2)
                rows.append(rec)

    # Listed strikes + k-bins. z-history lives on the bin, not on raw K.
    g2 = g.loc[g["usable"]].copy() if "usable" in g.columns else g
    bins_today = {}
    for r in g2.itertuples(index=False):
        k = float(r.k)
        if not np.isfinite(k):
            continue
        b = round(round(k / KBIN) * KBIN, 2)
        hid = f"KBIN_{b:+.2f}"
        bins_today.setdefault(hid, []).append(
            (float(r.market_iv), float(r.fair_iv_ensemble), float(r.strike), k)
        )
        rec = _row(
            date,
            f"STRIKE_{int(r.strike)}",
            "listed_strike",
            f"K={int(r.strike)}  k={k:.3f}",
            float(r.market_iv),
            float(r.fair_iv_ensemble),
            {**extra_base, "strike": float(r.strike), "k": k},
            history_id=hid,
        )
        rows.append(rec)
    for hid, pts in bins_today.items():
        m = float(np.mean([p[0] for p in pts]))
        f = float(np.mean([p[1] for p in pts]))
        rec = _row(
            date,
            hid,
            "kbin",
            f"log-moneyness bin {hid.replace('KBIN_', '')}",
            m,
            f,
            extra_base,
            history_id=hid,
        )
        rows.append(rec)
    return rows


def add_rolling(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["history_id", "trade_date"]).copy()
    g = df.groupby("history_id", sort=False)["residual"]
    gm = df.groupby("history_id", sort=False)["market_value"]

    def last_pct(s: pd.Series) -> float:
        return float(s.rank(pct=True).iloc[-1]) if s.notna().any() else np.nan

    for w, minp in ((20, 8), (60, 15), (120, 30), (252, 40)):
        minp = min(w, minp)
        mean = g.transform(lambda s, ww=w, mp=minp: s.rolling(ww, min_periods=mp).mean())
        std = g.transform(lambda s, ww=w, mp=minp: s.rolling(ww, min_periods=mp).std(ddof=1))
        df[f"z_{w}_residual"] = (df["residual"] - mean) / std.replace(0, np.nan)
        df[f"pct_{w}_residual"] = g.transform(
            lambda s, ww=w, mp=minp: s.rolling(ww, min_periods=mp).apply(last_pct, raw=False)
        )
        mmean = gm.transform(lambda s, ww=w, mp=minp: s.rolling(ww, min_periods=mp).mean())
        mstd = gm.transform(lambda s, ww=w, mp=minp: s.rolling(ww, min_periods=mp).std(ddof=1))
        df[f"z_{w}_market_value"] = (df["market_value"] - mmean) / mstd.replace(0, np.nan)
    return df


def main() -> None:
    src = ROOT / "outputs" / "residuals" / "surface_residuals.csv"
    use = [
        "trade_date",
        "strike",
        "k",
        "market_iv",
        "fair_iv_ensemble",
        "put_delta_abs",
        "call_delta_abs",
        "usable",
        "actual_dte",
        "forward",
        "spot",
    ]
    print("loading surfaces…")
    raw = pd.read_csv(src, usecols=use)
    raw["trade_date"] = pd.to_datetime(raw["trade_date"]).dt.strftime("%Y-%m-%d")
    print("dates", raw["trade_date"].nunique(), "rows", len(raw))

    rows = []
    for _, g in raw.groupby("trade_date", sort=True):
        g = g.loc[g["usable"]] if "usable" in g.columns else g
        if len(g) < 8:
            continue
        rows.extend(structures_for_day(g))
    panel = pd.DataFrame(rows)
    print("structures built", len(panel), "names", panel["structure"].nunique())
    panel = add_rolling(panel)

    dte = pd.read_csv(ROOT / "outputs" / "surfaces" / "dte_selection.csv")
    dte["trade_date"] = pd.to_datetime(dte["trade_date"]).dt.strftime("%Y-%m-%d")
    dte_slim = []
    for r in dte.itertuples(index=False):
        dte_slim.append(
            {
                "trade_date": r.trade_date,
                "selected_expiry": str(r.selected_expiry),
                "actual_dte": _n(r.actual_dte),
                "dte_error": _n(r.dte_error),
                "exact_match": bool(r.exact_match),
                "contract": r.contract,
                "put_delta_convention": r.put_delta_convention,
            }
        )

    # Historical stats on named (non-listed) structures, research dates only
    research = panel.loc[
        (panel["trade_date"] <= TRAIN_END) & (~panel["kind"].isin(["listed_strike"]))
    ]
    stats = []
    for name, g in research.groupby("structure"):
        stats.append(
            {
                "structure": name,
                "kind": g["kind"].iloc[0],
                "n": int(len(g)),
                "mean_abs_residual": _n(g["residual"].abs().mean()),
                "share_z60_ge_15": _n((g["z_60_residual"].abs() >= 1.5).mean()),
                "share_z60_ge_30": _n((g["z_60_residual"].abs() >= 3.0).mean()),
            }
        )

    wf_path = ROOT / "outputs" / "models" / "walkforward_scores.csv"
    wf_rows = []
    if wf_path.exists():
        wf_rows = json.loads(pd.read_csv(wf_path).to_json(orient="records"))

    catalog = (
        panel.loc[~panel["kind"].eq("listed_strike"), ["structure", "kind", "legs", "history_id"]]
        .drop_duplicates("structure")
        .sort_values(["kind", "structure"])
    )

    keep = [
        "trade_date",
        "structure",
        "history_id",
        "kind",
        "legs",
        "market_value",
        "fair_value",
        "residual",
        "extrapolated",
        "actual_dte",
        "forward",
        "spot_x",
        "atm_iv",
        "delta",
        "delta_2",
        "side",
        "strike",
        "k",
        "z_20_residual",
        "z_60_residual",
        "z_120_residual",
        "z_252_residual",
        "pct_60_residual",
        "z_60_market_value",
    ]
    slim = panel[keep].copy()
    payload_rows = []
    for rec in slim.itertuples(index=False):
        item = []
        for k in keep:
            v = getattr(rec, k)
            if k in ("trade_date", "structure", "history_id", "kind", "legs", "side"):
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    item.append(None)
                else:
                    item.append(v)
            else:
                item.append(_n(v))
        payload_rows.append(item)

    dates = sorted(slim["trade_date"].unique().tolist())
    payload = {
        "meta": {
            "train_start": "2025-06-05",
            "train_end": TRAIN_END,
            "test_date": TEST_DATE,
            "target_dte": 60,
            "frozen_z": FROZEN_Z,
            "default_z": FROZEN_Z,
            "n_dates": len(dates),
            "n_structures": int(slim["structure"].nunique()),
            "n_named": int(catalog.shape[0]),
            "n_rows": len(payload_rows),
            "universe": "All RR/BF at 5/10/15/20/25/30/35/40/45D, all wing slopes, delta points, listed strikes, k-bins. Gate not retuned.",
            "notes": (
                "TRADE if residual and z60 agree and |z60|>=gate and not extrapolated. "
                "NO TRADE if the reading is clean but |z| is below the gate. "
                "CANNOT DECIDE if z is missing, signs conflict, or the point was extrapolated."
            ),
        },
        "dates": dates,
        "catalog": json.loads(catalog.replace({np.nan: None}).to_json(orient="records")),
        "stats": stats,
        "dte": dte_slim,
        "walkforward": wf_rows,
        "columns": keep,
        "rows": payload_rows,
    }
    path = OUT / "panel.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path} MB={path.stat().st_size/1e6:.2f} rows={len(payload_rows)}")

    # Sanity: 11 Sep decisions at frozen 3.0
    test = slim.loc[slim["trade_date"] == TEST_DATE].copy()

    def dec(r, g=FROZEN_Z):
        z, res, ex = r.z_60_residual, r.residual, bool(r.extrapolated)
        if ex or not np.isfinite(z) or not np.isfinite(res):
            return "CANNOT DECIDE"
        if abs(z) < g:
            return "NO TRADE"
        if np.sign(z) != 0 and np.sign(res) != 0 and np.sign(z) != np.sign(res):
            return "CANNOT DECIDE"
        return "TRADE"

    test["dec"] = [dec(r) for r in test.itertuples()]
    print("\n11 Sep 2026 at frozen z=3.0")
    print(test.groupby(["kind", "dec"]).size().unstack(fill_value=0).to_string())
    trades = test.loc[test["dec"] == "TRADE", ["structure", "kind", "residual", "z_60_residual"]]
    print("TRADE count", len(trades))
    if len(trades):
        print(trades.sort_values("z_60_residual").to_string(index=False))


if __name__ == "__main__":
    main()
