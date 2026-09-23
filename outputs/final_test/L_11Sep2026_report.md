# Frozen test — 11 September 2026

Model, features, z-threshold (3.0) and structure definitions were frozen
on data through **8 September 2026**.  9–10 September were not used to
train or tune.  This page only *applies* the frozen engine.

## Surface

| item | value |
|---|---|
| Snapshot | 2026-09-11 16:00:00 |
| Selected expiry | 2026-11-05 18:00:00 (`OWSNP1EX26`) |
| actual_dte | 56 |
| dte_error | −4 |
| spot | 7661 |
| PCP forward | 7700 |
| ATM IV | 13.445% |
| 25D RR (IV) | −5.14 vol points |
| 25D BF (IV) | +0.72 vol points |
| Decision | **NO TRADE** on all 46 structures |

## Separate rankings (not collapsed)

Largest `|z_60|` (historical residual), still all below the frozen gate:

| rank | structure | residual | z_60 | p(conv) | decision |
|---|---|---|---|---|---|
| 1 | RR_30D | −0.00043 | −1.23 | 0.63 | NO TRADE |
| 2 | VERT_PUT_30D_20D | +0.00062 | +1.22 | 0.60 | NO TRADE |
| 3 | VERT_PUT_40D_25D | +0.00067 | +1.12 | 0.61 | NO TRADE |
| 4 | VERT_CALL_30D_20D | −0.00072 | −1.13 | 0.62 | NO TRADE |
| 5 | PUT_SKEW_15D | −0.00008 | −1.02 | n/a | NO TRADE |

Highest predicted convergence probability (ridge/logreg, frozen):

Butterflies ~0.63–0.65.  Expected residual change is ~0.0001 (one basis
point of vol).  None pass `|z| ≥ 3`.

## Why NO TRADE is the correct frozen output

The 11 Sep slice is **structurally ordinary**: SVI/SABR/spline residuals
are fractions of a vol point, and 60-day z-scores are inside ±1.3.
A forced ranking by raw residual would invent a “best” trade that the
historical rule rejected.

Subsequent dates (14 Sep onward) may be used only to *score* this
NO TRADE decision.  They must not be used to reopen threshold selection.
