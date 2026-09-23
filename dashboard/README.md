# 60DTE IV relative-value desk

Static dashboard over the expanded 60-DTE structure book.

Open `index.html` locally, or deploy this folder to Vercel.

Rebuild the panel (does not refit smiles or retune the gate):

```
python dashboard/build_expanded_panel.py
```

## Universe

- Risk reversals and butterflies at 5 / 10 / 15 / 20 / 25 / 30 / 35 / 40 / 45 delta
- Delta points (ATM + each put/call node)
- Slopes: ATM → each wing, and every far/near pair on each wing
- Listed strikes, with z-scores taken from a 0.02 log-moneyness bin (raw K is not a time series)
- k-bins themselves

## Decision rule (frozen, not retuned)

- **TRADE** — residual and 60-day residual z agree on sign, `|z60| ≥ gate`, and the point was not extrapolated
- **NO TRADE** — the reading is clean but `|z|` is below the gate
- **CANNOT DECIDE** — missing z, missing residual, sign conflict, or extrapolation

The frozen production gate is **3.0**. 11 September 2026 is the holdout and was not used to tune the engine.
