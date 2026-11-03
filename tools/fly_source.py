"""Hourly SNP parquet folder → Fly / Spread / Smile comparison payloads."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "fly_folders"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REQUIRED = (
    "contract",
    "time",
    "expiry",
    "strike",
    "underlying",
    "rate",
    "call_price",
    "put_price",
    "call_iv",
    "put_iv",
    "call_delta",
    "put_delta",
    "atm",
    "dte",
)
STATE_PATH = ROOT / ".cache" / "fly_folder.json"


def _round(value, digits=4):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return round(number, digits)


def resolve_folder(spec: str | None) -> Path:
    text = (spec or "").strip().strip('"')
    if not text:
        raise ValueError("No data folder selected.")
    path = Path(text)
    if not path.is_absolute():
        path = (ROOT / text).resolve()
    else:
        path = path.resolve()
    if not path.is_dir():
        raise FileNotFoundError(f"Folder not found: {path}")
    return path


def save_active_folder(path: Path) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        rel = path.resolve().relative_to(ROOT.resolve()).as_posix()
        payload = {"path": rel, "absolute": False}
    except ValueError:
        payload = {"path": str(path.resolve()), "absolute": True}
    STATE_PATH.write_text(json.dumps(payload), encoding="utf-8")


def load_active_folder() -> Path | None:
    if not STATE_PATH.exists():
        return None
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    try:
        return resolve_folder(payload.get("path"))
    except Exception:
        return None


def discover_folders() -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()

    def add(path: Path, label: str | None = None) -> None:
        try:
            path = path.resolve()
        except OSError:
            return
        if not path.is_dir():
            return
        dates = list_dates(path)
        if not dates:
            return
        try:
            key = path.relative_to(ROOT.resolve()).as_posix()
            absolute = False
        except ValueError:
            key = str(path)
            absolute = True
        if key in seen:
            return
        seen.add(key)
        found.append({
            "path": key,
            "label": label or f"{path.name} ({len(dates)} days)",
            "dates": len(dates),
            "absolute": absolute,
            "first": dates[0],
            "last": dates[-1],
        })

    add(ROOT / "SNP data", "SNP data (project)")
    sibling = ROOT.parent / "VolSurfaceAnalysis" / "SNP data"
    add(sibling, "VolSurfaceAnalysis/SNP data")
    if CACHE.exists():
        for child in sorted(CACHE.iterdir()):
            add(child, f"Uploaded: {child.name}")
    skip = {".git", ".venv", "venv", ".pytest_cache", "__pycache__", "node_modules", ".vercel", ".cache"}
    for path in ROOT.rglob("*.parquet"):
        if any(part in skip for part in path.parts):
            continue
        if DATE_RE.match(path.stem):
            add(path.parent)
    found.sort(key=lambda row: (
        0 if row["path"] == "SNP data" else 1 if "SNP data" in str(row["path"]) else 2,
        -row["dates"],
        str(row["path"]),
    ))
    return found


def list_dates(folder: Path) -> list[str]:
    dates = []
    for path in sorted(folder.glob("*.parquet")):
        if DATE_RE.match(path.stem):
            dates.append(path.stem)
    return dates


def _normalize(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    if "contact" in frame.columns and "contract" not in frame.columns:
        frame = frame.rename(columns={"contact": "contract"})
    missing = [name for name in REQUIRED if name not in frame.columns]
    if missing:
        raise ValueError("Missing columns: " + ", ".join(missing))
    frame["time"] = pd.to_datetime(frame["time"])
    frame["expiry"] = pd.to_datetime(frame["expiry"])
    frame["strike"] = pd.to_numeric(frame["strike"], errors="coerce")
    frame["underlying"] = pd.to_numeric(frame["underlying"], errors="coerce")
    frame["dte"] = pd.to_numeric(frame["dte"], errors="coerce")
    frame["atm"] = pd.to_numeric(frame["atm"], errors="coerce")
    for col in (
        "call_price",
        "put_price",
        "call_iv",
        "put_iv",
        "call_delta",
        "put_delta",
        "call_gamma",
        "put_gamma",
        "call_vega",
        "put_vega",
        "call_theta",
        "put_theta",
        "rate",
    ):
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame.dropna(subset=["strike", "underlying", "expiry", "time"])


def load_day(folder: Path, day: str) -> pd.DataFrame:
    path = folder / f"{day}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No parquet for {day} in {folder}")
    return _normalize(pd.read_parquet(path))


def hour_label(ts) -> str:
    stamp = pd.Timestamp(ts)
    return f"{stamp.hour:02d}:{stamp.minute:02d}"


def list_hours(frame: pd.DataFrame) -> list[str]:
    return sorted({hour_label(ts) for ts in frame["time"].unique()})


def filter_hour(frame: pd.DataFrame, hour: str) -> pd.DataFrame:
    wanted = str(hour).strip()
    mask = frame["time"].map(hour_label) == wanted
    out = frame.loc[mask].copy()
    if out.empty:
        raise ValueError(f"No rows for hour {wanted}.")
    return out


def list_expiries(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for expiry, group in frame.groupby(frame["expiry"].dt.strftime("%Y-%m-%d"), sort=True):
        dte = float(group["dte"].dropna().iloc[0]) if group["dte"].notna().any() else None
        rows.append({
            "expiry": expiry,
            "dte": _round(dte, 0),
            "strikes": int(group["strike"].nunique()),
        })
    rows.sort(key=lambda row: (abs((row["dte"] or 999) - 60), row["expiry"]))
    return rows


def pick_expiry(expiries: list[dict], target_dte: float = 60.0, chosen: str | None = None) -> dict:
    if not expiries:
        raise ValueError("No expiries in this hour slice.")
    if chosen:
        for row in expiries:
            if row["expiry"] == chosen:
                return row
        raise ValueError(f"Expiry {chosen} is not in this hour slice.")
    return min(expiries, key=lambda row: abs((row["dte"] if row["dte"] is not None else 1e9) - float(target_dte)))


def day_meta(folder: Path, day: str, target_dte: float = 60.0) -> dict:
    frame = load_day(folder, day)
    hours = list_hours(frame)
    by_hour = {}
    for hour in hours:
        slice_df = filter_hour(frame, hour)
        expiries = list_expiries(slice_df)
        default = pick_expiry(expiries, target_dte)
        by_hour[hour] = {
            "expiries": expiries,
            "default_expiry": default["expiry"],
            "default_dte": default["dte"],
            "spot": _round(float(slice_df["underlying"].iloc[0]), 2),
        }
    default_hour = hours[-1] if hours else None
    return {
        "date": day,
        "hours": hours,
        "default_hour": default_hour,
        "by_hour": by_hour,
        "rows": int(len(frame)),
    }


def _atm_strike(slice_df: pd.DataFrame) -> float:
    zero = slice_df.loc[slice_df["atm"].fillna(999).abs() < 1e-9]
    if not zero.empty:
        return float(zero["strike"].iloc[0])
    spot = float(slice_df["underlying"].iloc[0])
    strikes = slice_df["strike"].dropna().unique()
    return float(min(strikes, key=lambda k: abs(float(k) - spot)))


def to_long(slice_df: pd.DataFrame) -> pd.DataFrame:
    atm = _atm_strike(slice_df)
    spot = float(slice_df["underlying"].iloc[0])
    dte = float(slice_df["dte"].dropna().iloc[0])
    rate = float(slice_df["rate"].dropna().iloc[0]) if slice_df["rate"].notna().any() else 0.0
    trade_date = pd.Timestamp(slice_df["time"].iloc[0]).strftime("%Y-%m-%d")
    expiry = pd.Timestamp(slice_df["expiry"].iloc[0]).strftime("%Y-%m-%d")
    hour = hour_label(slice_df["time"].iloc[0])
    rows = []
    for _, row in slice_df.iterrows():
        strike = float(row["strike"])
        base = {
            "date": trade_date,
            "hour": hour,
            "expiry": expiry,
            "underlying": spot,
            "atm_strike": atm,
            "target_dte": dte,
            "rate": rate,
            "strike": strike,
            "atm_offset": strike - atm,
        }
        rows.append({
            **base,
            "option_side": "call",
            "iv_decimal": float(row["call_iv"]) if pd.notna(row["call_iv"]) else np.nan,
            "premium": float(row["call_price"]) if pd.notna(row["call_price"]) else np.nan,
            "delta": float(row["call_delta"]) if pd.notna(row.get("call_delta")) else np.nan,
            "gamma": float(row["call_gamma"]) if "call_gamma" in row and pd.notna(row["call_gamma"]) else np.nan,
            "vega": float(row["call_vega"]) if "call_vega" in row and pd.notna(row["call_vega"]) else np.nan,
            "theta": float(row["call_theta"]) if "call_theta" in row and pd.notna(row["call_theta"]) else np.nan,
        })
        put_delta = row.get("put_delta")
        if pd.notna(put_delta):
            put_delta = -abs(float(put_delta))
        rows.append({
            **base,
            "option_side": "put",
            "iv_decimal": float(row["put_iv"]) if pd.notna(row["put_iv"]) else np.nan,
            "premium": float(row["put_price"]) if pd.notna(row["put_price"]) else np.nan,
            "delta": put_delta if put_delta == put_delta else np.nan,
            "gamma": float(row["put_gamma"]) if "put_gamma" in row and pd.notna(row["put_gamma"]) else np.nan,
            "vega": float(row["put_vega"]) if "put_vega" in row and pd.notna(row["put_vega"]) else np.nan,
            "theta": float(row["put_theta"]) if "put_theta" in row and pd.notna(row["put_theta"]) else np.nan,
        })
    return pd.DataFrame(rows).dropna(subset=["iv_decimal", "premium"])


def build_smile(long_df: pd.DataFrame) -> list[dict]:
    puts = long_df[(long_df["option_side"] == "put") & (long_df["atm_offset"] < 0)]
    calls = long_df[(long_df["option_side"] == "call") & (long_df["atm_offset"] > 0)]
    atm = long_df[np.isclose(long_df["atm_offset"], 0.0, atol=1e-6)]
    if not atm.empty:
        atm_row = atm[atm["option_side"] == "call"]
        if atm_row.empty:
            atm_row = atm.iloc[[0]]
        else:
            atm_row = atm_row.iloc[[0]]
    else:
        atm_row = pd.DataFrame()
    smile = pd.concat([puts, atm_row, calls], ignore_index=True)
    smile = smile.sort_values("atm_offset").drop_duplicates(subset=["atm_offset"])
    out = []
    for _, row in smile.iterrows():
        out.append({
            "strike": _round(row["strike"], 2),
            "offset": _round(row["atm_offset"], 2),
            "side": str(row["option_side"]),
            "iv": _round(float(row["iv_decimal"]) * 100.0, 4),
            "prem": _round(row["premium"], 4),
            "delta": _round(row.get("delta"), 4),
            "vega": _round(row.get("vega"), 4),
        })
    return out


def _side_map(sub: pd.DataFrame) -> dict[float, dict]:
    out: dict[float, dict] = {}
    for _, row in sub.iterrows():
        out[round(float(row["strike"]), 4)] = {
            "strike": float(row["strike"]),
            "premium": float(row["premium"]),
            "iv_decimal": float(row["iv_decimal"]),
            "delta": float(row["delta"]) if pd.notna(row.get("delta")) else None,
            "vega": float(row["vega"]) if pd.notna(row.get("vega")) else None,
        }
    return out


def _lookup(side_map: dict[float, dict], strike: float) -> dict | None:
    key = round(float(strike), 4)
    if key in side_map:
        return side_map[key]
    for cand, row in side_map.items():
        if abs(cand - float(strike)) < 1e-6:
            return row
    return None


def build_flies(long_df: pd.DataFrame, wing: float = 100.0) -> tuple[list[dict], list[dict]]:
    atm = float(long_df["atm_strike"].iloc[0])
    calls: list[dict] = []
    puts: list[dict] = []
    for side, bucket in (("call", calls), ("put", puts)):
        side_map = _side_map(long_df[long_df["option_side"] == side])
        for centre in sorted(side_map):
            lower = _lookup(side_map, centre - wing)
            mid = _lookup(side_map, centre)
            upper = _lookup(side_map, centre + wing)
            if lower is None or mid is None or upper is None:
                continue
            offset = centre - atm
            if side == "call" and offset < -1e-6:
                continue
            if side == "put" and offset > 1e-6:
                continue
            prem = float(lower["premium"]) - 2.0 * float(mid["premium"]) + float(upper["premium"])
            iv_fly = (
                float(lower["iv_decimal"]) - 2.0 * float(mid["iv_decimal"]) + float(upper["iv_decimal"])
            ) * 100.0
            delta = (lower["delta"] or 0.0) - 2.0 * (mid["delta"] or 0.0) + (upper["delta"] or 0.0)
            vega = (lower["vega"] or 0.0) - 2.0 * (mid["vega"] or 0.0) + (upper["vega"] or 0.0)
            bucket.append({
                "centre": _round(centre, 2),
                "offset": _round(offset, 2),
                "lower": _round(centre - wing, 2),
                "upper": _round(centre + wing, 2),
                "prem": _round(prem, 4),
                "iv_fly": _round(iv_fly, 4),
                "delta": _round(delta, 4),
                "vega": _round(vega, 4),
                "lower_iv": _round(float(lower["iv_decimal"]) * 100.0, 4),
                "mid_iv": _round(float(mid["iv_decimal"]) * 100.0, 4),
                "upper_iv": _round(float(upper["iv_decimal"]) * 100.0, 4),
                "lower_prem": _round(lower["premium"], 4),
                "mid_prem": _round(mid["premium"], 4),
                "upper_prem": _round(upper["premium"], 4),
            })
    return calls, puts


def build_spreads(long_df: pd.DataFrame, width: float = 100.0) -> tuple[list[dict], list[dict]]:
    atm = float(long_df["atm_strike"].iloc[0])
    calls: list[dict] = []
    puts: list[dict] = []
    for side, bucket, direction in (
        ("call", calls, 1.0),
        ("put", puts, -1.0),
    ):
        side_map = _side_map(long_df[long_df["option_side"] == side])
        for near in sorted(side_map):
            far = near + direction * width
            near_row = _lookup(side_map, near)
            far_row = _lookup(side_map, far)
            if near_row is None or far_row is None:
                continue
            offset = near - atm
            if side == "call" and offset < -1e-6:
                continue
            if side == "put" and offset > 1e-6:
                continue
            prem = float(near_row["premium"]) - float(far_row["premium"])
            gap = (float(near_row["iv_decimal"]) - float(far_row["iv_decimal"])) * 100.0
            bucket.append({
                "near": _round(near, 2),
                "far": _round(far, 2),
                "offset": _round(offset, 2),
                "prem": _round(prem, 4),
                "iv_near": _round(float(near_row["iv_decimal"]) * 100.0, 4),
                "iv_far": _round(float(far_row["iv_decimal"]) * 100.0, 4),
                "iv_gap": _round(gap, 4),
                "delta": _round((near_row["delta"] or 0.0) - (far_row["delta"] or 0.0), 4),
                "vega": _round((near_row["vega"] or 0.0) - (far_row["vega"] or 0.0), 4),
            })
    return calls, puts


def factors_from_smile(smile: list[dict], h: float = 500.0) -> dict:
    by_off = {row["offset"]: row for row in smile if row.get("iv") is not None}
    def iv_at(offset):
        if offset in by_off:
            return by_off[offset]["iv"]
        offs = sorted(by_off)
        if not offs or offset < offs[0] or offset > offs[-1]:
            return None
        for i in range(len(offs) - 1):
            a, b = offs[i], offs[i + 1]
            if a <= offset <= b:
                wa = (b - offset) / (b - a) if b != a else 1.0
                return wa * by_off[a]["iv"] + (1 - wa) * by_off[b]["iv"]
        return None
    atm = iv_at(0.0)
    up = iv_at(h)
    down = iv_at(-h)
    level = atm
    skew = None if up is None or down is None else up - down
    curv = None if atm is None or up is None or down is None else 0.5 * (up + down) - atm
    return {
        "level": _round(level, 4),
        "skew": _round(skew, 4),
        "curvature": _round(curv, 4),
    }


def build_day(
    folder: Path,
    day: str,
    hour: str | None = None,
    expiry: str | None = None,
    target_dte: float = 60.0,
    wing: float = 100.0,
    spread_width: float | None = None,
) -> dict:
    frame = load_day(folder, day)
    hours = list_hours(frame)
    if not hours:
        raise ValueError(f"{day} has no timestamps.")
    chosen_hour = hour if hour in hours else (hour if hour else hours[-1])
    if chosen_hour not in hours:
        # nearest clock hour
        want = int(str(chosen_hour).split(":")[0])
        chosen_hour = min(hours, key=lambda h: abs(int(h.split(":")[0]) - want))
    slice_df = filter_hour(frame, chosen_hour)
    expiries = list_expiries(slice_df)
    picked = pick_expiry(expiries, target_dte, expiry)
    chain = slice_df[slice_df["expiry"].dt.strftime("%Y-%m-%d") == picked["expiry"]].copy()
    if chain.empty:
        raise ValueError(f"No chain for expiry {picked['expiry']} at {chosen_hour} on {day}.")
    long_df = to_long(chain)
    smile = build_smile(long_df)
    call_flies, put_flies = build_flies(long_df, wing=wing)
    width = float(spread_width if spread_width is not None else wing)
    call_spreads, put_spreads = build_spreads(long_df, width=width)
    facts = factors_from_smile(smile)
    return {
        "date": day,
        "hour": chosen_hour,
        "expiry": picked["expiry"],
        "dte": picked["dte"],
        "spot": _round(float(long_df["underlying"].iloc[0]), 2),
        "atm_strike": _round(float(long_df["atm_strike"].iloc[0]), 2),
        "rate": _round(float(long_df["rate"].iloc[0]), 6),
        "wing": wing,
        "spread_width": width,
        "level": facts["level"],
        "skew": facts["skew"],
        "curvature": facts["curvature"],
        "smile": smile,
        "call_flies": call_flies,
        "put_flies": put_flies,
        "call_spreads": call_spreads,
        "put_spreads": put_spreads,
        "hours": hours,
        "expiries": expiries,
        "n_strikes": int(chain["strike"].nunique()),
    }


def compare(
    folder: Path,
    date_a: str,
    date_b: str,
    hour: str | None = None,
    expiry_a: str | None = None,
    expiry_b: str | None = None,
    target_dte: float = 60.0,
    wing: float = 100.0,
    spread_width: float | None = None,
) -> dict:
    a = build_day(folder, date_a, hour=hour, expiry=expiry_a, target_dte=target_dte, wing=wing, spread_width=spread_width)
    # Prefer the same clock hour on B when available.
    hour_b = hour
    if hour_b and hour_b not in a["hours"]:
        hour_b = a["hour"]
    b = build_day(folder, date_b, hour=hour_b or a["hour"], expiry=expiry_b, target_dte=target_dte, wing=wing, spread_width=spread_width)
    spot_move = None if a["spot"] is None or b["spot"] is None else _round(b["spot"] - a["spot"], 2)
    spot_pct = None
    if a["spot"] and b["spot"] and a["spot"]:
        spot_pct = _round(100.0 * (b["spot"] - a["spot"]) / a["spot"], 4)
    return {
        "ok": True,
        "folder": str(folder),
        "target_dte": target_dte,
        "wing": wing,
        "spread_width": float(spread_width if spread_width is not None else wing),
        "date_a": a,
        "date_b": b,
        "spot_move": spot_move,
        "spot_move_pct": spot_pct,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def hold_path(
    folder: Path,
    start_date: str,
    hold_days: int = 10,
    hour: str | None = None,
    expiry: str | None = None,
    target_dte: float = 60.0,
    wing: float = 100.0,
    spread_width: float | None = None,
) -> dict:
    """Lock the start-day expiry and walk the next 1..10 trading sessions."""
    hold_days = max(1, min(10, int(hold_days)))
    dates = list_dates(folder)
    if start_date not in dates:
        raise ValueError(f"Start date {start_date} is not in the folder.")
    i0 = dates.index(start_date)
    path_dates = dates[i0 : i0 + hold_days + 1]
    if not path_dates:
        raise ValueError("No dates available for the hold path.")

    day0 = build_day(
        folder,
        path_dates[0],
        hour=hour,
        expiry=expiry,
        target_dte=target_dte,
        wing=wing,
        spread_width=spread_width,
    )
    locked = day0["expiry"]
    chosen_hour = hour or day0["hour"]
    days = [{"hold_day": 0, **day0}]
    warnings: list[str] = []
    for k, day in enumerate(path_dates[1:], start=1):
        try:
            built = build_day(
                folder,
                day,
                hour=chosen_hour,
                expiry=locked,
                target_dte=target_dte,
                wing=wing,
                spread_width=spread_width,
            )
            days.append({"hold_day": k, **built})
        except Exception as exc:
            warnings.append(f"{day}: {exc}")

    first = days[0]
    last = days[-1]
    spot_move = None if first.get("spot") is None or last.get("spot") is None else _round(last["spot"] - first["spot"], 2)
    spot_pct = None
    if first.get("spot"):
        spot_pct = _round(100.0 * (last["spot"] - first["spot"]) / first["spot"], 4)
    return {
        "ok": True,
        "mode": "hold",
        "folder": str(folder),
        "start_date": start_date,
        "locked_expiry": locked,
        "hold_days_requested": hold_days,
        "hold_days_available": len(days) - 1,
        "hour": chosen_hour,
        "wing": wing,
        "spread_width": float(spread_width if spread_width is not None else wing),
        "days": days,
        "spot_move": spot_move,
        "spot_move_pct": spot_pct,
        "dte_start": first.get("dte"),
        "dte_end": last.get("dte"),
        "warnings": warnings,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def receive_uploads(files: list[tuple[str, bytes]], label: str | None = None) -> dict:
    if not files:
        raise ValueError("No files uploaded.")
    name = (label or datetime.utcnow().strftime("upload_%Y%m%d_%H%M%S")).strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:80] or "upload"
    dest = CACHE / name
    dest.mkdir(parents=True, exist_ok=True)
    saved = 0
    for filename, payload in files:
        base = Path(filename.replace("\\", "/")).name
        if not base.lower().endswith(".parquet"):
            continue
        stem = Path(base).stem
        if not DATE_RE.match(stem):
            # keep anyway but only date-named files are catalogued
            pass
        (dest / base).write_bytes(payload)
        saved += 1
    if saved == 0:
        raise ValueError("Upload had no .parquet files.")
    dates = list_dates(dest)
    save_active_folder(dest)
    return {
        "ok": True,
        "path": dest.relative_to(ROOT).as_posix(),
        "saved": saved,
        "dates": len(dates),
        "first": dates[0] if dates else None,
        "last": dates[-1] if dates else None,
    }
