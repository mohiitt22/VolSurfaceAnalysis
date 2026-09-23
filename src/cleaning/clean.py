"""Option-chain cleaning with an explicit removal ledger.

Nothing is dropped silently.  Every removed row is counted by reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config.settings import DEFAULT, ResearchConfig


REASONS = (
    "missing_strike",
    "missing_underlying",
    "invalid_strike",
    "invalid_underlying",
    "missing_iv_both",
    "impossible_iv",
    "negative_price",
    "nan_inf",
    "zero_greeks_and_zero_iv",
    "broken_delta",
    "duplicate",
    "inconsistent_call_put",
)


@dataclass
class CleaningDiagnostics:
    trade_date: object
    expiry: object
    dte: int | None
    total_rows: int
    valid_rows: int
    removed_rows: int
    reason_counts: dict[str, int] = field(default_factory=dict)
    strike_min: float | None = None
    strike_max: float | None = None
    iv_min: float | None = None
    iv_max: float | None = None
    n_unique_strikes: int = 0

    def to_record(self) -> dict:
        rec = {
            "trade_date": self.trade_date,
            "expiry": self.expiry,
            "dte": self.dte,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "removed_rows": self.removed_rows,
            "strike_min": self.strike_min,
            "strike_max": self.strike_max,
            "iv_min": self.iv_min,
            "iv_max": self.iv_max,
            "n_unique_strikes": self.n_unique_strikes,
        }
        rec.update({f"removed_{k}": self.reason_counts.get(k, 0) for k in REASONS})
        return rec


def _first_true_reason(mask_dict: dict[str, np.ndarray]) -> np.ndarray:
    n = next(iter(mask_dict.values())).shape[0]
    out = np.full(n, "", dtype=object)
    assigned = np.zeros(n, dtype=bool)
    for name, m in mask_dict.items():
        take = m & ~assigned
        out[take] = name
        assigned |= take
    return out


def clean_chain(
    df: pd.DataFrame,
    cfg: ResearchConfig | None = None,
    iv_bounds: tuple[float, float] | None = None,
) -> tuple[pd.DataFrame, CleaningDiagnostics]:
    cfg = cfg or DEFAULT
    lo, hi = iv_bounds or (cfg.iv_min, cfg.iv_max)
    work = df.copy()
    n = len(work)
    if n == 0:
        diag = CleaningDiagnostics(
            trade_date=None, expiry=None, dte=None, total_rows=0, valid_rows=0, removed_rows=0
        )
        return work, diag

    strike = work["strike"].to_numpy(dtype=float)
    und = work["underlying"].to_numpy(dtype=float)
    civ = work["call_iv"].to_numpy(dtype=float)
    piv = work["put_iv"].to_numpy(dtype=float)
    cp = work["call_price"].to_numpy(dtype=float)
    pp = work["put_price"].to_numpy(dtype=float)
    cd = work["call_delta"].to_numpy(dtype=float)
    pdlt = work["put_delta"].to_numpy(dtype=float)

    num = work.select_dtypes(include=[np.number])
    nan_inf = ~np.isfinite(num.to_numpy()).all(axis=1)

    both_iv_bad = (~np.isfinite(civ) | (civ <= 0)) & (~np.isfinite(piv) | (piv <= 0))
    iv_impossible = (np.isfinite(civ) & ((civ < 0) | (civ > hi))) | (
        np.isfinite(piv) & ((piv < 0) | (piv > hi))
    )
    zero_greeks = (
        (work["call_vega"].to_numpy(dtype=float) <= 0)
        & (work["put_vega"].to_numpy(dtype=float) <= 0)
        & ((civ <= 0) | ~np.isfinite(civ))
        & ((piv <= 0) | ~np.isfinite(piv))
    )
    broken_delta = (
        (np.isfinite(cd) & ((cd < -0.05) | (cd > 1.05)))
        | (np.isfinite(pdlt) & (np.abs(pdlt) > 1.05))
    )
    # Call should be more expensive than put when K << S, opposite when K >> S.
    # Flag only gross violations of price positivity already handled; here
    # flag if both prices exist and call+put < |S-K| * 0 (impossible cheap package)
    # or call_iv and put_iv differ by more than 1.0 (100 vol points) at same strike.
    inconsistent = np.isfinite(civ) & np.isfinite(piv) & (np.abs(civ - piv) > 1.0)

    key = ["contract", "time", "expiry", "strike"]
    key = [c for c in key if c in work.columns]
    dup = work.duplicated(subset=key, keep="first").to_numpy() if key else np.zeros(n, dtype=bool)

    masks = {
        "missing_strike": ~np.isfinite(strike),
        "missing_underlying": ~np.isfinite(und),
        "invalid_strike": np.isfinite(strike) & (strike <= 0),
        "invalid_underlying": np.isfinite(und) & (und <= 0),
        "missing_iv_both": both_iv_bad,
        "impossible_iv": iv_impossible,
        "negative_price": (np.isfinite(cp) & (cp < 0)) | (np.isfinite(pp) & (pp < 0)),
        "nan_inf": nan_inf,
        "zero_greeks_and_zero_iv": zero_greeks,
        "broken_delta": broken_delta,
        "duplicate": dup,
        "inconsistent_call_put": inconsistent,
    }
    reason = _first_true_reason(masks)
    keep = reason == ""
    work["removal_reason"] = reason
    valid = work.loc[keep].drop(columns=["removal_reason"]).copy()
    removed = work.loc[~keep]

    counts = {k: int((reason == k).sum()) for k in REASONS}
    dte = int(work["dte"].mode().iloc[0]) if "dte" in work.columns and len(work) else None
    expiry = work["expiry"].iloc[0] if "expiry" in work.columns else None
    trade_date = work["trade_date"].iloc[0] if "trade_date" in work.columns else None
    if len(valid):
        ivs = np.concatenate(
            [
                valid["call_iv"].to_numpy(dtype=float),
                valid["put_iv"].to_numpy(dtype=float),
            ]
        )
        ivs = ivs[np.isfinite(ivs) & (ivs > 0)]
        iv_min = float(np.min(ivs)) if len(ivs) else None
        iv_max = float(np.max(ivs)) if len(ivs) else None
        strike_min = float(valid["strike"].min())
        strike_max = float(valid["strike"].max())
        n_u = int(valid["strike"].nunique())
    else:
        iv_min = iv_max = strike_min = strike_max = None
        n_u = 0

    diag = CleaningDiagnostics(
        trade_date=trade_date,
        expiry=expiry,
        dte=dte,
        total_rows=n,
        valid_rows=int(keep.sum()),
        removed_rows=int((~keep).sum()),
        reason_counts=counts,
        strike_min=strike_min,
        strike_max=strike_max,
        iv_min=iv_min,
        iv_max=iv_max,
        n_unique_strikes=n_u,
    )
    valid.attrs["removed_ledger"] = removed
    return valid.reset_index(drop=True), diag
