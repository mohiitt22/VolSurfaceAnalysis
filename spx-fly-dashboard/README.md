# SPX Fixed-Strike Butterfly Volatility Lab — Level, Skew & Curvature Simulation

An interactive quantitative research dashboard analyzing how implied volatility smile **Level, Skew, and Curvature** adjustments affect fixed-strike SPX OTM call and put butterfly spreads at **constant spot, strikes, and maturity**.

---

## 1. Core Analytical Objective & Modeling Principles

The dashboard investigates:
> **How does the complete fixed-strike butterfly premium curve respond when the IV smile experiences controlled changes in its level, skew, and curvature, while spot, strikes, maturity, and other pricing inputs remain strictly fixed?**

### Key Principles: Fixed-Strike vs Fixed-Delta
- **SPX Spot is held constant ($S_0$)**
- **Option strikes are held constant ($K_{lower}, K_{mid}, K_{upper}$)**
- **Time to maturity is held constant ($T_0 = \text{Target DTE} / 365$)**
- **Interest rate and dividend yield assumptions are held constant ($r, q$)**
- **Strikes are NEVER reselected when sliders move.**

---

## 2. Volatility Surface Shock Model

The model applies an **additive quadratic strike-space perturbation** on top of the original historical smile:

$$\sigma_{\text{shocked}}(K) = \sigma_{\text{orig}}(K) + \frac{\text{Shock}(K)}{100}$$

where IVs are decimals and shocks are in volatility percentage points:

$$\text{Shock}(K) = L + \frac{S}{2}x + C x^2$$

with the normalized linear strike coordinate:

$$x = \frac{K - K_{\text{ATM}}}{H}$$

### Parameters:
- **Level ($L$)**: Uniform vertical smile shift in vol points ($\text{min}: -5, \text{max}: +10$).
- **Skew ($S$)**: Tilt / slope parameter ($\text{min}: -5, \text{max}: +5$).
  $$\text{Shock}(+H) - \text{Shock}(-H) = S$$
  - Negative skew ($S < 0$): steepens downside put wing relative to call wing.
  - Positive skew ($S > 0$): lifts upside call wing relative to put wing.
- **Curvature ($C$)**: Wing curvature / convexity parameter ($\text{min}: -3, \text{max}: +3$).
  $$\left[\frac{\text{Shock}(-H) + \text{Shock}(+H)}{2}\right] - \text{Shock}(K_{\text{ATM}}) = C$$
  - Bends both reference wings symmetrically upward ($C > 0$) or flatter ($C < 0$) relative to ATM.
- **Reference Strike Width ($H$)**: Configurable scale parameter (default: **500 SPX points**; selectable: 300, 400, 500, 600, 800). Fixed during slider movement.

---

## 3. Mathematical Invariants of the IV Fly

For any equally spaced 100-point butterfly ($h = 100$) centered at $K_{\text{mid}}$ with $K_{\text{lower}} = K_{\text{mid}} - h$ and $K_{\text{upper}} = K_{\text{mid}} + h$, the second-difference IV fly is:

$$\text{IVFly} = \sigma_{\text{lower}} - 2\sigma_{\text{mid}} + \sigma_{\text{upper}}$$

Under the additive quadratic model:
1. **Pure Level Shock ($L \neq 0, S = 0, C = 0$)**:
   $$\Delta\text{IVFly} = L - 2L + L = 0$$
2. **Pure Skew Shock ($L = 0, S \neq 0, C = 0$)**:
   $$\Delta\text{IVFly} = \frac{S}{2}\left[\frac{K_{\text{mid}} - h - K_{\text{ATM}}}{H} - 2\frac{K_{\text{mid}} - K_{\text{ATM}}}{H} + \frac{K_{\text{mid}} + h - K_{\text{ATM}}}{H}\right] = 0$$
   *Because $x$ is linear in strike, skew has zero second difference across equal strike spacing.*
3. **Pure Curvature Shock ($L = 0, S = 0, C \neq 0$)**:
   $$\Delta\text{IVFly} = C\left[(x_{\text{mid}} - \frac{h}{H})^2 - 2x_{\text{mid}}^2 + (x_{\text{mid}} + \frac{h}{H})^2\right] = 2C\left(\frac{h}{H}\right)^2$$
   For $h = 100$ and $H = 500$:
   $$\Delta\text{IVFly} = 2C\left(\frac{100}{500}\right)^2 = 0.08 \times C \quad \text{vol percentage points}$$
   *Every complete 100-point strike fly changes its IV second difference by exactly $0.08C$ points, invariant to center strike or smile shape.*

---

## 4. Option Repricing & Butterfly Spread Construction

### Butterfly Definition ($100$-point wings, $h = 100$):
$$\text{Fly}(K) = P(K - 100) - 2P(K) + P(K + 100)$$
- **OTM Call Butterflies**: Centres at ATM+100, ATM+200, ..., ATM+800.
- **OTM Put Butterflies**: Centres at ATM-100, ATM-200, ..., ATM-800.

### Baseline-Preserving Repricing Convention:
$$P_{\text{shocked}}(K) = P_{\text{orig}}(K) + \left[\text{BS}(S_0, K, T_0, \sigma_{\text{shocked}}(K), r, q) - \text{BS}(S_0, K, T_0, \sigma_{\text{orig}}(K), r, q)\right]$$
Guarantees that at $(L=0, S=0, C=0)$, shocked premiums reproduce Excel quotes exactly.

---

## 5. Factor Sensitivities & Scenario Attribution

### 5.1 First-Order Sensitivities
For fly weights $q = [1, -2, 1]$ and leg vegas expressed per 1 vol percentage point:
- **Level Sensitivity**: $\text{LevelExposure} = \sum_{i} q_i \text{Vega}_i$
- **Skew Sensitivity**: $\text{SkewExposure} = \sum_{i} q_i \text{Vega}_i \frac{x_i}{2}$
- **Curvature Sensitivity**: $\text{CurvatureExposure} = \sum_{i} q_i \text{Vega}_i x_i^2$
- **First-Order Predicted Change**:
  $$\text{FirstOrderChange} = L \cdot \text{LevelExposure} + S \cdot \text{SkewExposure} + C \cdot \text{CurvatureExposure}$$
- **Nonlinear Residual**:
  $$\text{NonlinearResidual} = \Delta\text{FlyPremium} - \text{FirstOrderChange}$$

### 5.2 Scenario Attribution
1. **Sequential Decomposition ($L \to S \to C$)**:
   - $\text{LevelEffect} = \text{FlyValue}(\sigma + \text{Shock}_L) - \text{FlyValue}(\sigma)$
   - $\text{SkewEffect} = \text{FlyValue}(\sigma + \text{Shock}_L + \text{Shock}_S) - \text{FlyValue}(\sigma + \text{Shock}_L)$
   - $\text{CurvatureEffect} = \text{FlyValue}(\sigma + \text{Shock}_{\text{Total}}) - \text{FlyValue}(\sigma + \text{Shock}_L + \text{Shock}_S)$
   - Sums exactly to total repriced change.
2. **Shapley Attribution (Order-Independent)**:
   - Averages marginal factor contributions across all $3! = 6$ valuation orderings:
     $$\{(L,S,C), (L,C,S), (S,L,C), (S,C,L), (C,L,S), (C,S,L)\}$$
   - Symmetrically allocates nonlinear cross-interaction effects.

---

## 6. Dashboard Structure & Layout

The dashboard consists of a 5-tier analytical layout:
- **Sidebar**:
  - Historical Date & Option Side selector.
  - Scenario Modes: `Combined`, `Level Only`, `Skew Only`, `Curvature Only`.
  - Reference strike width selector ($H \in \{300, 400, 500, 600, 800\}$).
  - One-click Presets:
    - *Reset to Baseline (0,0,0)*
    - *Downside Skew Steepening ($S = -2$)*
    - *Wing Curvature Steepening ($C = +1$)*
    - *Parallel Vol Rise ($L = +2$)*
    - *Combined Vol Stress ($L = +2, S = -2, C = +1$)*
  - 3 Independent Sliders for Level, Skew, and Curvature.
- **Top Metrics**: SPX Spot, Target DTE, ATM Strike, Risk-free rate, Baseline acceptance check, and Static Arbitrage diagnostics banner.
- **Row 1**: Original vs. Shocked IV Smile (with hover breakdown of $L, S, C$ contributions, ATM / Spot lines, and factor overlays) + Shock Decomposition curve.
- **Row 2**: OTM Put and OTM Call Butterfly Premium Curves (Baseline vs Shocked).
- **Row 3**: Mark-to-Market Fly Premium Change ($\Delta\text{Premium}$) & IV Fly Curvature ($\Delta\text{IVFly}$) with theoretical invariant badge.
- **Row 4**: Factor Exposures across strike (Level, Skew, Curvature sensitivities) & Factor Attribution Panel (Sequential vs. Shapley tabs).
- **Row 5**: Selected Contract Deep-Dive: 3-leg breakdown table, factor attribution summary, and 3-panel 1D response curves ($P$ vs $L$, $P$ vs $S$, $P$ vs $C$).

---

## 7. Static Arbitrage & Scenario Diagnostics

The engine includes built-in diagnostics to identify non-arbitrage-free scenarios:
- **Positive IV Check**: Rejects any shock resulting in non-positive IV ($\sigma \le 0$) across strikes and identifies offending strikes.
- **Monotonicity Check**: European call prices must not increase with strike; put prices must not decrease with strike.
- **Convexity Check**: Butterfly spreads must have non-negative prices ($\text{Fly}(K) \ge 0$) under pure Black-Scholes pricing.

---

## 8. Verification & Automated Unit Tests

The test suite validates all mathematical invariants and financial calculations across 37 comprehensive tests:
```bash
pytest -v
```

Key invariant tests in `tests/test_fly_factor_model.py`:
- **Test 1**: All sliders zero reproduces baseline IV and premiums exactly.
- **Test 2**: Pure level shift (+2 pts) gives $\Delta\text{IVFly} = 0$.
- **Test 3**: Pure skew shock ($S = -2$) confirms ATM $\pm 500$ exact shocks and $\Delta\text{IVFly} = 0$.
- **Test 4**: Pure curvature ($C = \pm 1$) confirms $\Delta\text{IVFly} \equiv \pm 0.08$ vol points across all 100-point flies.
- **Test 5**: Combined stress scenario ($L=+2, S=-2, C=+1$) verifies exact strike shocks ($7630 \to +2.00, 7730 \to +1.84, 7530 \to +2.24$) and sequential/Shapley attribution closure.
- **Test 6**: Slider reversibility.
- **Test 7**: Date independence (no cross-contamination across dates).
- **Test 8**: Finite-difference Greek validation ($\epsilon = 10^{-4}$ perturbation matches analytical factor exposures).

---

## 9. Running Locally

```bash
# Activate environment
.venv\Scripts\activate

# Launch Streamlit dashboard
streamlit run app.py --server.port 8501
```
Open `http://localhost:8501` in your browser.
