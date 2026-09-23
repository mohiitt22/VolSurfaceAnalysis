"""Load and normalize daily option-chain parquet files."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from config.settings import DEFAULT, ResearchConfig

LOGGER = logging.getLogger(__name__)


def _default_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "SNP data"


def list_available_dates(data_dir: Path | None = None) -> list[date]:
    data_dir = data_dir or _default_data_dir()
    dates: list[date] = []
    for p in sorted(data_dir.glob("*.parquet")):
        dates.append(date.fromisoformat(p.stem))
    return dates


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map documented aliases and enforce a stable column order.

    The vendor schema uses `contract` (not the typo `contact` in the brief).
    Later files reorder columns; this function does not depend on order.
    """
    rename = {}
    if "contact" in df.columns and "contract" not in df.columns:
        rename["contact"] = "contract"
    out = df.rename(columns=rename).copy()
    missing = [c for c in DEFAULT.expected_columns if c not in out.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return out


def _parse_times(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["time"] = pd.to_datetime(out["time"])
    out["expiry"] = pd.to_datetime(out["expiry"])
    out["trade_date"] = out["time"].dt.date
    out["expiry_date"] = out["expiry"].dt.date
    return out


def select_snapshot(df: pd.DataFrame, rule: str = "last") -> pd.DataFrame:
    """Reduce multiple intraday snapshots to one chain per trade date.

    Default: last available timestamp that day (typically 16:00).
    Early-close days keep whatever last print exists.
    """
    if df.empty:
        return df
    if rule != "last":
        raise ValueError(f"Unsupported snapshot rule: {rule}")
    last_ts = df["time"].max()
    snap = df.loc[df["time"] == last_ts].copy()
    snap.attrs["snapshot_time"] = last_ts
    return snap


def load_day(
    d: date,
    cfg: ResearchConfig | None = None,
    data_dir: Path | None = None,
    snapshot: bool = True,
) -> pd.DataFrame:
    cfg = cfg or DEFAULT
    data_dir = data_dir or Path(__file__).resolve().parents[2] / "SNP data"
    path = data_dir / f"{d.isoformat()}.parquet"
    if not path.exists():
        raise FileNotFoundError(path)
    raw = pd.read_parquet(path)
    df = normalize_columns(raw)
    df = _parse_times(df)
    if snapshot:
        df = select_snapshot(df, rule=cfg.snapshot_rule)
    df["source_file"] = path.name
    return df.reset_index(drop=True)


def load_many(
    dates: list[date],
    cfg: ResearchConfig | None = None,
    snapshot: bool = True,
) -> pd.DataFrame:
    frames = [load_day(d, cfg=cfg, snapshot=snapshot) for d in dates]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
