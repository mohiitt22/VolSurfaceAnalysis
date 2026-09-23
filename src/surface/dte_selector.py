"""Nearest-expiry 60-DTE selector.

Rule (per trade date, after snapshot filter):

1. Group by expiry (one consistent chain — never mix expiries).
2. Take that expiry's DTE (must be unique).
3. Prefer exact DTE == target.
4. Otherwise minimise |DTE - target|.
5. Ties: more valid strikes, then DTE >= target, then earlier expiry.

This is nearest-expiry-first, not nearest-DTE-per-strike.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class DTESelection:
    trade_date: date
    selected_expiry: pd.Timestamp
    actual_dte: int
    target_dte: int
    dte_error: int
    abs_dte_error: int
    n_candidate_expiries: int
    n_valid_strikes: int
    exact_match: bool
    tie_broken: bool
    contract: str | None
    snapshot_time: pd.Timestamp | None


def _expiry_stats(chain: pd.DataFrame) -> pd.DataFrame:
    required = {"expiry", "dte", "strike"}
    missing = required - set(chain.columns)
    if missing:
        raise ValueError(f"chain missing {missing}")

    rows = []
    for expiry, g in chain.groupby("expiry", sort=True):
        dtes = g["dte"].dropna().unique()
        if len(dtes) != 1:
            # Do not silently mix; take the modal DTE and flag.
            dte = int(g["dte"].mode().iloc[0])
        else:
            dte = int(dtes[0])
        n_strikes = int(g["strike"].nunique())
        contract = None
        if "contract" in g.columns:
            contract = str(g["contract"].mode().iloc[0])
        rows.append(
            {
                "expiry": pd.Timestamp(expiry),
                "dte": dte,
                "n_strikes": n_strikes,
                "contract": contract,
            }
        )
    return pd.DataFrame(rows)


def select_nearest_expiry(
    chain: pd.DataFrame,
    target_dte: int = 60,
    trade_date: date | None = None,
    snapshot_time: pd.Timestamp | None = None,
) -> tuple[DTESelection, pd.DataFrame]:
    """Return (selection metadata, rows belonging to the chosen expiry)."""
    if chain.empty:
        raise ValueError("empty chain")
    stats = _expiry_stats(chain)
    stats["abs_err"] = (stats["dte"] - target_dte).abs()
    min_err = int(stats["abs_err"].min())
    tied = stats.loc[stats["abs_err"] == min_err].copy()
    tie_broken = len(tied) > 1
    # Higher liquidity, then prefer DTE >= target, then earlier expiry.
    tied = tied.sort_values(
        by=["n_strikes", "dte", "expiry"],
        ascending=[False, False, True],
    )
    # Among same n_strikes, prefer dte >= target if any such exist.
    ge = tied.loc[tied["dte"] >= target_dte]
    if len(tied) > 1 and len(ge):
        # Re-sort ge the same way
        pick = ge.sort_values(
            by=["n_strikes", "dte", "expiry"],
            ascending=[False, False, True],
        ).iloc[0]
    else:
        pick = tied.iloc[0]

    selected_expiry = pd.Timestamp(pick["expiry"])
    actual = int(pick["dte"])
    slice_df = chain.loc[pd.to_datetime(chain["expiry"]) == selected_expiry].copy()
    # If two product codes share the expiry, keep one row per strike (higher vega).
    if "strike" in slice_df.columns and slice_df.duplicated(subset=["strike"]).any():
        vega_col = "call_vega" if "call_vega" in slice_df.columns else None
        if vega_col:
            slice_df = slice_df.sort_values(vega_col, ascending=False)
        slice_df = slice_df.drop_duplicates(subset=["strike"], keep="first")
    if trade_date is None:
        if "trade_date" in chain.columns:
            trade_date = chain["trade_date"].iloc[0]
        else:
            trade_date = pd.Timestamp(chain["time"].iloc[0]).date()

    meta = DTESelection(
        trade_date=trade_date,
        selected_expiry=selected_expiry,
        actual_dte=actual,
        target_dte=target_dte,
        dte_error=actual - target_dte,
        abs_dte_error=abs(actual - target_dte),
        n_candidate_expiries=int(stats.shape[0]),
        n_valid_strikes=int(pick["n_strikes"]),
        exact_match=actual == target_dte,
        tie_broken=tie_broken,
        contract=None if pd.isna(pick["contract"]) else str(pick["contract"]),
        snapshot_time=snapshot_time,
    )
    return meta, slice_df.reset_index(drop=True)


def select_from_dte_list(dtes: list[int], target: int = 60) -> int:
    """Pure helper used by unit tests (exact / nearest / documented ties)."""
    if not dtes:
        raise ValueError("empty dte list")
    if target in dtes:
        return target
    best = min(abs(d - target) for d in dtes)
    tied = [d for d in dtes if abs(d - target) == best]
    ge = [d for d in tied if d >= target]
    if ge:
        return max(ge) if len(ge) > 1 else ge[0]
    return min(tied)
