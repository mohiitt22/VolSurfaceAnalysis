# Evidence-based conclusions

These statements use **only** the research window 2025-06-05 … 2026-09-08
(walk-forward / labels cut at that date).  The 11 September 2026 surface was
scored with the **frozen** rule and was not used to change any threshold.

## What is statistically supported

1. **Slice residuals mean-revert a little.**
   `corr(residual, future_change_h5) = −0.44` on the research sample.
   That is evidence of statistical convergence of *model residuals*, not of
   a tradable edge.

2. **The typical residual is tiny.**
   SVI in-sample IV RMSE ≈ 0.47 vol points (0.0047).  Ensemble residuals on
   a quiet day are often 1–10 *basis points* of vol.  “Below SVI” is therefore
   almost never an economically large dislocation on this 60-DTE slice.

3. **Extreme 25D risk reversals revert more often than butterflies.**
   RR_25D, `|z_60| ≥ 1.5`: mean 5-day convergence +0.00076, hit 95% (n=42).
   BF_25D, same gate: +0.00030, hit 66% (n=59).
   Verticals overall: hit 64%, mean convergence +0.00019.

4. **Walk-forward predictive IC is unstable.**
   Ridge IC on 5-day convergence flipped sign across folds
   (−0.17 … +0.16).  Sign-hit 47–75%.  There is **not** a stable
   out-of-sample mapping from the feature list to residual change.

5. **The frozen z-gate is 3.0.**
   It was chosen inside walk-forward as the threshold with the highest
   validation-mean convergence (0.0013).  That is a *small* number
   (~0.13 vol points).  At this gate, research-period signalled trades
   had 96% residual-convergence hit and **negative** cost-adjusted P&L.

6. **Statistical convergence ≠ P&L.**
   Mid-price fade P&L can look positive while the conservative
   executable P&L (no bid/ask in the files; modelled half-spreads) is
   negative.  Verticals and risk reversals in particular do not survive
   the cost model.  Butterflies were the least-bad package in-sample
   (exec hit ~52%, Sharpe proxy ~0.08) — not a claim of robustness.

## What is *not* supported

- Cheap ≠ low IV.  ATM IV on 11 Sep 2026 is 13.45%; that is a *level*,
  not a relative-value signal (`z_60` of ATM residual ≈ +0.21).
- Cheap ≠ below SVI.  Almost every strike is close to SVI/SABR/spline.
- A useful live book of trades.  After the frozen gates, **11 Sep 2026
  is NO TRADE on all 46 generated structures.**
- A claim that any one structure (e.g. 25D/15D put vertical) is the
  “best” after multiple-testing across deltas, horizons and thresholds.

## Answers to the research questions (research window only)

| # | Question | Evidence |
|---|---|---|
| 1 | Does an SVI/ensemble residual predict IV convergence? | Weakly yes (corr −0.44). Magnitude is small. |
| 2 | Is a large residual more useful when models agree? | Residuals are already small when models agree; not separately identified. |
| 3 | Are extreme RR mean-reverting? | Yes at 5d, high hit, tiny size. |
| 4 | Extreme BF? | Weaker than RR. |
| 5 | Extreme vertical prices? | Mild IV convergence; cost-adjusted P&L negative. |
| 6 | Skew vs ATM predictability | Skew/RR residuals revert; ATM is a regime variable, not a fade. |
| 7 | Curvature vs skew | BF weaker than RR in this sample. |
| 8 | Delta region | 25D RR more populated and better behaved than 10D wings. |
| 9 | 25P/15P vertical vs others | No outperformance after costs. |
| 10 | Residual + z vs either alone | z-gate improves hit rate; does not create exec P&L. |
| 11 | Residual + regime | Walk-forward IC includes RV/IV-RV and is still unstable. |
| 12 | Residual + liquidity → P&L | No bid/ask; liquidity is a vega proxy only. |
| 13 | Ensemble vs one model | SVI fits best in RMSE; ensemble used for residuals (median). RMSE is not the objective. |
| 14 | Disagreement predicts failure | Not tested as a stand-alone classifier; high disagreement is a hard NO TRADE. |
| 15 | Cheap vs expensive asymmetry | Not established (sample of |z|≥3 is 92 rows). |
| 16–17 | High/low IV or RV regimes | Insufficient stable fold-level evidence. |
| 18–19 | Survive costs / conservative execution? | **No**, under the documented cost model. |
| 20 | Economic P&L vs statistical convergence | They diverge. Convergence is real; tradable P&L is not shown. |

## Frozen 11 September 2026 (unseen)

- Last snapshot 16:00.  Selected expiry **2026-11-05**, actual DTE **56**
  (no exact 60).  Forward from put-call parity ≈ 7700 vs spot 7661.
- ATM IV 13.45%.  25D RR ≈ −5.14 vol points.  25D BF ≈ 0.72 vol points.
- Largest `|z_60|` among structures is about **1.23** (RR_30D, put
  verticals).  Frozen threshold is **3.0**.
- Decision: **NO TRADE** (46 / 46).  This is the intended output when
  nothing clears the historical gate.

Do not retune the threshold after reading this page.
