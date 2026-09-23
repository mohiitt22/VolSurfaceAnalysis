# 60-DTE implied-volatility relative-value framework

Research engine for detecting cheap / expensive points and structures on a
single ~60-DTE implied-volatility slice.  The objective is **predictive
relative value**, not minimum surface RMSE.

## Holdout

| Window | Dates | Use |
|---|---|---|
| Research / train / tune | 2025-06-05 … 2026-09-08 | Fitting, z-thresholds, ML, feature decisions |
| Gap | 2026-09-09, 2026-09-10 | Not used for training or tuning |
| Frozen test | **2026-09-11** | Signal generation only, after freeze |
| After test | 2026-09-14 … | Outcome scoring of the frozen decision only |

## Dashboard

`dashboard/` is a static desk for any structure × date:

- **CHEAP / EXPENSIVE / CANNOT DECIDE** using residual + historical z
- Separate definition cards (structural, z20/z60/z120, own-history level)
- Path chart, regime, historical hit rate, same-day cross-section
- Frozen holdout jump: 11 Sep 2026

```text
# local
start dashboard/index.html
```

- Dashboard: https://snp-60dte-iv-desk.vercel.app
- Private repo: https://github.com/Ayushkumarsingh09/snp-60dte-iv-relative-value

Vercel serves the `dashboard/` folder. Raw option chains are not in the repo.

## Run

```text
python run.py --phase 1      # data dictionary
python -m pytest tests -q
python run.py --phase all    # full pipeline
```

Outputs land in `outputs/` (`reports/`, `surfaces/`, `residuals/`,
`structures/`, `models/`, `backtests/`, `final_test/`, `plots/`).

## What the data actually is

See `outputs/reports/A_data_quality_report.md` after Phase 1.  Highlights:

- Column is `contract`, not `contact`.
- `rate` is always 0; forward comes from put-call parity.
- `put_delta` changes sign on 2026-07-16; the code always uses `abs`.
- IV is decimal.  No bid/ask / volume / OI.
- One expiry per date: nearest to 60 DTE.  Last snapshot of the day.

## Philosophy

Cheap ≠ low IV.  Cheap ≠ below SVI.  A trade requires residual + history +
model agreement + liquidity + predicted convergence + cost-aware edge.
**NO TRADE** is a valid output.
