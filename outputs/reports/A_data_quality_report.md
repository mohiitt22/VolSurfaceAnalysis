# Phase 1 data dictionary and quality report

Generated from the parquet files in `SNP data/`.  Nothing below is assumed
from the brief when the files contradict it.

## Inventory

- Files: 324
- Filename dates: 2025-06-05 → 2026-09-22
- Weekdays only (Mon–Fri).  Missing business days (15) match US
  market holidays: 2025-06-19, 2025-07-04, 2025-09-01, 2025-11-27, 2025-12-25, 2026-01-01, 2026-01-19, 2026-02-16, 2026-04-03, 2026-05-25, 2026-06-16, 2026-06-19, 2026-07-03, 2026-08-07, 2026-09-07.
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
| put_delta | float | **unsigned through 2026-07-15; signed negative from 2026-07-16** |
| straddle_delta | float | equals call_delta − abs(put_delta) in both regimes |
| call/put gamma, vega, theta | float | theta ≤ 0; vega ≥ 0 |
| atm | int | **strike offset from the ATM listed strike (0 = ATM), not a boolean** |
| dte | int | **calendar days** from trade date to expiry date (matches expiry−time date difference) |

No volume, open interest, bid, or ask columns exist in any file.

## Conventions used by the research engine

1. **Snapshot.** Last timestamp of the day (usually 16:00).  Early closes keep the last print.
2. **60-DTE surface.** One expiry per date: exact 60 if present, else nearest expiry to 60.  Never mix expiries across strikes.  Exact DTE=60 exists on only 37 / 324 days.  Typical |DTE−60| is 2–4 days.
3. **Forward.** `rate=0` would give F=S, but put-call parity is systematically off from S−K by tens of index points.  Underlying is treated as **spot**.  Forward = median ATM-neighborhood (K + C − P).
4. **IV units.** Decimal.  Vendor IV is retained after a BS reconstruction audit on a subset of days.
5. **OTM IV.** K<F → put_iv; K>F → call_iv; |k|<0.01 → 0.5*(call+put).
6. **Delta.** Always `put_delta_abs = abs(put_delta)`.  25D put / 50D ATM / 25D call.
7. **Holdout.** Train/tune: 2025-06-05 … 2026-09-08.  Gap (not used for training): 2026-09-09, 2026-09-10.  Frozen test surface: 2026-09-11.  Later dates are only for scoring that frozen decision.

## First-file sample (2025-06-05)

```
                 time    contract               expiry  strike  underlying  rate  call_price  put_price  atm  call_iv  put_iv  call_delta  call_gamma  call_vega  call_theta  put_delta  put_gamma  put_vega  put_theta  dte  straddle_delta
0 2025-06-05 09:00:00  ODSNP1AN25  2025-07-06 18:00:00  5500.0     5961.25   0.0      487.90  20.156250  -11   0.2202  0.2187      0.9001      0.0005     3.1876     -0.9858     0.0987     0.0005    3.1566    -1.0266   32          0.8014
1 2025-06-05 09:00:00  ODSNP1AN25  2025-07-06 18:00:00  5600.0     5961.25   0.0      395.30  26.127273  -10   0.2026  0.2003      0.8620      0.0006     3.9834     -1.1677     0.1356     0.0006    3.9349    -1.1841   32          0.7264
2 2025-06-05 09:00:00  ODSNP1AN25  2025-07-06 18:00:00  5700.0     5961.25   0.0      306.75  37.105882   -9   0.1883  0.1851      0.8032      0.0008     4.9723     -1.3913     0.1933     0.0008    4.9188    -1.3843   32          0.6099
```

## 11 September 2026 file

- Exists: yes
- Columns match (order differs: `contract` first)
- 8 timestamps, 44 expiries
- Nearest DTE to 60 is computed at runtime from the last snapshot (do not hard-code)

## Research split file counts

- ≤ 2026-09-08: 314
- 2026-09-09 / 10: 2 (present on disk, excluded from training)
- 2026-09-11: 1 (frozen test)
- > 2026-09-11: 7 (outcome scoring only)
