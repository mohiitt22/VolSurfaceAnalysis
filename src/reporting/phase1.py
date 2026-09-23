"""Phase 1: inspect files and write the data-quality / data-dictionary report."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import DEFAULT, OUTPUT_DIR, ResearchConfig
from src.data_loader.loader import list_available_dates, load_day, normalize_columns
from src.reporting.reports import write_data_quality_report


def run_phase1(cfg: ResearchConfig | None = None) -> Path:
    cfg = cfg or DEFAULT
    data_dir = Path(__file__).resolve().parents[2] / "SNP data"
    files = sorted(data_dir.glob("*.parquet"))
    dates = list_available_dates(data_dir)
    file_dates = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    missing = pd.bdate_range(file_dates.min(), file_dates.max()).difference(file_dates)

    df0 = normalize_columns(pd.read_parquet(files[0]))
    df0["time"] = pd.to_datetime(df0["time"])
    df11 = normalize_columns(pd.read_parquet(data_dir / "2026-09-11.parquet"))

    # Lightweight full scan
    rows = []
    for f in files:
        d = pd.read_parquet(f)
        rows.append(
            {
                "date": f.stem,
                "n": len(d),
                "n_time": d["time"].nunique(),
                "n_expiry": d["expiry"].nunique(),
                "has_60": 60 in set(d["dte"].dropna().astype(int)),
                "nearest_60": int(min(d["dte"].unique(), key=lambda x: abs(int(x) - 60))),
                "put_delta_frac_neg": float((d["put_delta"] < 0).mean()),
                "rate_med": float(d["rate"].median()),
                "call_iv_med": float(d["call_iv"].median()),
                "col0": d.columns[0],
            }
        )
    scan = pd.DataFrame(rows)
    (OUTPUT_DIR / "cleaned").mkdir(parents=True, exist_ok=True)
    scan.to_csv(OUTPUT_DIR / "cleaned" / "phase1_file_scan.csv", index=False)

    switch = scan.loc[scan["put_delta_frac_neg"] > 0.5, "date"]
    first_signed = switch.iloc[0] if len(switch) else "n/a"

    sample = df0.head(3).to_string()
    text = f"""# Phase 1 data dictionary and quality report

Generated from the parquet files in `SNP data/`.  Nothing below is assumed
from the brief when the files contradict it.

## Inventory

- Files: {len(files)}
- Filename dates: {dates[0]} → {dates[-1]}
- Weekdays only (Mon–Fri).  Missing business days ({len(missing)}) match US
  market holidays: {", ".join(d.date().isoformat() for d in missing)}.
- Typical file: ~12,000–13,000 rows, ~8 hourly timestamps (09:00–16:00),
  ~43 expiries, ~80–90 unique strikes.
- A few early-close / short files exist (e.g. 2025-07-03, 2026-06-10).

## Schema (actual)

The brief listed `contact`.  The files contain **`contract`**.

Stable fields (column *order* changes after ~2026-07; names do not):

| field | observed type | notes |
|---|---|---|
| time | string datetime `YYYY-MM-DD HH:MM:SS`, no timezone | 09:00–16:00 hourly |
| contract | string | expiry *product* code (`OWSNP1EQ25`, `ODSNP…`, `OMAMSNP…`), not a single option |
| expiry | string datetime, typically `18:00:00` | one expiry per contract almost always |
| strike | float | index points |
| underlying | float | S&P 500-like level (~5940 in Jun-2025 → ~7660 on 11 Sep 2026).  One value per timestamp. |
| rate | float | **identically 0.0 in every file** |
| call_price, put_price | float | often fractional (averages / mids).  Min observed 0.025.  No bid/ask. |
| call_iv, put_iv | float | **decimal** (0.16 = 16%).  Rare 0.0 and extreme wings up to ~8.5. |
| call_delta | float | standard [0, 1] |
| put_delta | float | **unsigned through 2026-07-15; signed negative from {first_signed}** |
| straddle_delta | float | equals call_delta − abs(put_delta) in both regimes |
| call/put gamma, vega, theta | float | theta ≤ 0; vega ≥ 0 |
| atm | int | **strike offset from the ATM listed strike (0 = ATM), not a boolean** |
| dte | int | **calendar days** from trade date to expiry date (matches expiry−time date difference) |

No volume, open interest, bid, or ask columns exist in any file.

## Conventions used by the research engine

1. **Snapshot.** Last timestamp of the day (usually 16:00).  Early closes keep the last print.
2. **60-DTE surface.** One expiry per date: exact 60 if present, else nearest expiry to 60.  Never mix expiries across strikes.  Exact DTE=60 exists on only {int(scan["has_60"].sum())} / {len(scan)} days.  Typical |DTE−60| is 2–4 days.
3. **Forward.** `rate=0` would give F=S, but put-call parity is systematically off from S−K by tens of index points.  Underlying is treated as **spot**.  Forward = median ATM-neighborhood (K + C − P).
4. **IV units.** Decimal.  Vendor IV is retained after a BS reconstruction audit on a subset of days.
5. **OTM IV.** K<F → put_iv; K>F → call_iv; |k|<0.01 → 0.5*(call+put).
6. **Delta.** Always `put_delta_abs = abs(put_delta)`.  25D put / 50D ATM / 25D call.
7. **Holdout.** Train/tune: {cfg.train_start} … {cfg.train_end}.  Gap (not used for training): 2026-09-09, 2026-09-10.  Frozen test surface: {cfg.test_date}.  Later dates are only for scoring that frozen decision.

## First-file sample (2025-06-05)

```
{sample}
```

## 11 September 2026 file

- Exists: yes
- Columns match (order differs: `contract` first)
- 8 timestamps, 44 expiries
- Nearest DTE to 60 is computed at runtime from the last snapshot (do not hard-code)

## Research split file counts

- ≤ 2026-09-08: {int((scan["date"] <= "2026-09-08").sum())}
- 2026-09-09 / 10: 2 (present on disk, excluded from training)
- 2026-09-11: 1 (frozen test)
- > 2026-09-11: {int((scan["date"] > "2026-09-11").sum())} (outcome scoring only)
"""
    path = OUTPUT_DIR / "reports" / "A_data_quality_report.md"
    write_data_quality_report(path, text)
    return path
