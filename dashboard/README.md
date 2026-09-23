# 60DTE IV relative-value desk

Static dashboard over the research panel.

Open `index.html` locally, or deploy this folder to Vercel.

## Verdict rule

- **CHEAP** — residual &lt; 0 and 60-day residual z ≤ −gate
- **EXPENSIVE** — residual &gt; 0 and 60-day residual z ≥ +gate
- **CANNOT DECIDE** — otherwise (thin history, |z| below gate, or definitions disagree)

The frozen production gate is **3.0**. The dashboard default is **1.5** so you can inspect milder dislocations without pretending they are trades.

11 September 2026 is the holdout. It was not used to tune the engine.
