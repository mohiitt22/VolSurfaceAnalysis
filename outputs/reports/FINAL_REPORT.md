# 60-DTE IV Relative-Value Research Report

Training / research window: 2025-06-05 → 2026-09-08 (314 files).

Frozen holdout surface: 2026-09-11.  9–10 Sep 2026 excluded from training/tuning.

Snapshot rule: last timestamp of each day.  Expiry rule: single nearest expiry to 60 DTE (exact 60 on 36 days).

Forward: put-call parity (rate is identically 0; underlying is spot).

Cheap ≠ low IV.  Signals require residual + history + model agreement + liquidity + predicted convergence.  NO TRADE is a valid output.


## A. Data quality

Cleaning rows across snapshots: total=517395, valid=504690, removed=12705.

Vendor field `contact` in the brief is actually `contract` in the files. No bid/ask, volume or open-interest columns exist.  `rate` is always 0. `put_delta` is unsigned through 2026-07-15 and signed thereafter; the engine always uses abs(put_delta).  IV is decimal.

BS IV reconstruction MAE (call) median across audit days: 0.0046. Supplied IV is used because reconstruction error is small on liquid central strikes; wings can differ and are filtered.


## B. 60-DTE selection

```
 index trade_date            selected_expiry  actual_dte  target_dte  dte_error  abs_dte_error  n_candidate_expiries  n_valid_strikes exact_match tie_broken contract              snapshot_time             forward_source put_delta_convention
 count        317                        317  317.000000       317.0 317.000000     317.000000            317.000000       317.000000         317        317      317                        317                        317                  317
unique        317                        NaN         NaN         NaN        NaN            NaN                   NaN              NaN           2          2       61                        NaN                          1                    2
   top 2025-06-05                        NaN         NaN         NaN        NaN            NaN                   NaN              NaN       False      False OMSNPV25                        NaN put_call_parity_atm_median    unsigned_positive
  freq          1                        NaN         NaN         NaN        NaN            NaN                   NaN              NaN         281        297       11                        NaN                        317                  277
  mean        NaN 2026-03-22 11:44:06.056782   59.940063        60.0  -0.059937       2.854890             42.466877        44.088328         NaN        NaN      NaN 2026-01-22 11:02:50.347003                        NaN                  NaN
   min        NaN        2025-07-31 18:00:00   52.000000        60.0  -8.000000       0.000000             39.000000        17.000000         NaN        NaN      NaN        2025-06-05 16:00:00                        NaN                  NaN
   25%        NaN        2025-11-27 18:00:00   57.000000        60.0  -3.000000       2.000000             42.000000        30.000000         NaN        NaN      NaN        2025-09-29 16:00:00                        NaN                  NaN
   50%        NaN        2026-03-19 19:00:00   59.000000        60.0  -1.000000       3.000000             43.000000        31.000000         NaN        NaN      NaN        2026-01-22 16:00:00                        NaN                  NaN
   75%        NaN        2026-07-16 18:00:00   63.000000        60.0   3.000000       4.000000             43.000000        71.000000         NaN        NaN      NaN        2026-05-15 16:00:00                        NaN                  NaN
   max        NaN        2026-11-05 18:00:00   67.000000        60.0   7.000000       8.000000             44.000000        72.000000         NaN        NaN      NaN        2026-09-11 16:00:00                        NaN                  NaN
   std        NaN                        NaN    3.443882         0.0   3.443882       1.920348              0.876743        19.634438         NaN        NaN      NaN                        NaN                        NaN                  NaN
```

Exact DTE=60: 36 / 317 days.
Mean |DTE-60| = 2.85, max = 8.
Selection is nearest *expiry*, then all strikes of that expiry.


## C. Surface-fit comparison

In-sample IV RMSE by model (research+test surfaces).  Lowest RMSE is **not** the selection criterion.

```
         index  count     mean      std      min      25%      50%      75%      max
  poly_iv_rmse  317.0 0.002629 0.001542 0.000191 0.001680 0.002405 0.003339 0.009191
spline_iv_rmse  317.0 0.001288 0.000926 0.000097 0.000584 0.000983 0.001822 0.005090
   svi_iv_rmse  317.0 0.000469 0.000211 0.000061 0.000319 0.000447 0.000596 0.001123
  ssvi_iv_rmse  317.0 0.001498 0.000611 0.000296 0.001107 0.001522 0.001943 0.003514
  sabr_iv_rmse  317.0 0.001051 0.000519 0.000144 0.000684 0.000974 0.001387 0.003522
```

## D. Historical residual / structure analysis

- RR_25D: mean conv_h5 all=0.00021 (n=309), |z_60|>=1.5: 0.00076 (n=42), hit=0.952
- BF_25D: mean conv_h5 all=0.00015 (n=309), |z_60|>=1.5: 0.00030 (n=59), hit=0.661
- All verticals conv_h5 mean=0.00019 n=2930 hit=0.640
- corr(residual, future_change_h5) = -0.440 (negative ⇒ mean reversion)

## E. Walk-forward predictive models

```
 train_end  val_start    val_end  n_train  n_val        ic  sign_hit      mae
2025-11-10 2025-11-11 2025-12-09     1588    376 -0.076214  0.654255 0.000434
2025-12-09 2025-12-10 2026-01-08     1964    400 -0.136023  0.470000 0.000366
2026-01-08 2026-01-09 2026-02-06     2364    400 -0.165480  0.555000 0.000417
2026-02-06 2026-02-09 2026-03-09     2764    362  0.048001  0.500000 0.000399
2026-03-09 2026-03-10 2026-04-07     3126    292 -0.122272  0.527397 0.001018
2026-04-07 2026-04-08 2026-05-05     3418    400  0.105645  0.752500 0.000535
2026-05-05 2026-05-06 2026-06-03     3818    352 -0.072437  0.642045 0.000348
2026-06-03 2026-06-04 2026-07-06     4170    322  0.162204  0.673913 0.000356
2026-07-06 2026-07-07 2026-08-03     4492    384 -0.063943  0.635417 0.000434
2026-08-03 2026-08-04 2026-08-31     4876    380  0.112300  0.634211 0.000394
```

## F. Backtest (research period only)

{
  "all": {
    "n": 14444,
    "n_with_pnl": 9167,
    "mean_exec_pnl": -2.5477749224510333,
    "median_exec_pnl": -3.4197077184776674,
    "mean_mid_pnl": 1.7032614035007498,
    "hit_rate_exec": 0.3087160466892113,
    "mean_convergence": 0.00019193813977485532,
    "hit_rate_convergence": 0.6332497000109087,
    "sharpe_proxy": -2.8221885118276857,
    "max_dd_proxy": -23582.644627360925
  },
  "signalled": {
    "n": 92,
    "n_with_pnl": 80,
    "mean_exec_pnl": -1.7604804106854917,
    "median_exec_pnl": 0.0004531983434857556,
    "mean_mid_pnl": 1.750457089314508,
    "hit_rate_exec": 0.525,
    "mean_convergence": 0.0014253762032203445,
    "hit_rate_convergence": 0.9625,
    "sharpe_proxy": -2.317313002219675,
    "max_dd_proxy": -140.84189979455226
  },
  "verticals": {
    "n": 14,
    "n_with_pnl": 12,
    "mean_exec_pnl": -4.338069507485009,
    "median_exec_pnl": -4.502795164264711,
    "mean_mid_pnl": 0.7244304925149917,
    "hit_rate_exec": 0.0,
    "mean_convergence": 0.0012287369043978518,
    "hit_rate_convergence": 1.0,
    "sharpe_proxy": -21.86177864887304,
    "max_dd_proxy": -46.93792781556237
  },
  "rr": {
    "n": 1570,
    "n_with_pnl": 1465,
    "mean_exec_pnl": -6.004508065764548,
    "median_exec_pnl": -6.054515855701093,
    "mean_mid_pnl": 0.42791514242657774,
    "hit_rate_exec": 0.0006825938566552901,
    "mean_convergence": 0.0002087313017021332,
    "hit_rate_convergence": 0.6498293515358362,
    "sharpe_proxy": -30.039627548023105,
    "max_dd_proxy": -8788.67027563916
  },
  "bf": {
    "n": 1570,
    "n_with_pnl": 1465,
    "mean_exec_pnl": 0.15464165953367887,
    "median_exec_pnl": 0.43801442987762584,
    "mean_mid_pnl": 9.803276471820368,
    "hit_rate_exec": 0.5160409556313993,
    "mean_convergence": 0.00016913985080974073,
    "hit_rate_convergence": 0.6191126279863481,
    "sharpe_proxy": 0.07647716322521905,
    "max_dd_proxy": -974.2639494562466
  },
  "z_threshold": 3.0,
  "horizon": 5
}

## G. Frozen 11 September 2026 test

Structures scored on 2026-09-11: 46.  TRADE: 0.  NO TRADE is the default when z, liquidity, disagreement or predicted edge fail the frozen gates.

```
        structure              legs  actual_dte  market_value  fair_value  residual  z_60_residual  pred_prob_convergence  pred_expected_return decision  no_trade_reasons
           ATM_IV               ATM          56      0.134450    0.134552 -0.000102       0.205199                    NaN                   NaN NO TRADE z_below_threshold
           BF_10D 10DP / ATM / 10DC          56      0.030816    0.030195  0.000621       0.164707               0.629892              0.000083 NO TRADE z_below_threshold
           BF_15D 15DP / ATM / 15DC          56      0.019127    0.018906  0.000221      -0.371739               0.642937              0.000123 NO TRADE z_below_threshold
           BF_20D 20DP / ATM / 20DC          56      0.012012    0.011899  0.000113      -0.408099               0.640193              0.000124 NO TRADE z_below_threshold
           BF_25D 25DP / ATM / 25DC          56      0.007179    0.007160  0.000019      -0.600335               0.647072              0.000137 NO TRADE z_below_threshold
           BF_30D 30DP / ATM / 30DC          56      0.003859    0.003798  0.000061      -0.464925               0.644951              0.000130 NO TRADE z_below_threshold
    CALL_SKEW_10D       10DC vs ATM          56     -0.024547   -0.024841  0.000295       0.415037                    NaN                   NaN NO TRADE z_below_threshold
    CALL_SKEW_15D       15DC vs ATM          56     -0.022842   -0.023361  0.000519       0.183911                    NaN                   NaN NO TRADE z_below_threshold
    CALL_SKEW_20D       20DC vs ATM          56     -0.020798   -0.021365  0.000566       0.094774                    NaN                   NaN NO TRADE z_below_threshold
    CALL_SKEW_25D       25DC vs ATM          56     -0.018532   -0.018724  0.000192      -0.424403                    NaN                   NaN NO TRADE z_below_threshold
    CALL_SKEW_30D       30DC vs ATM          56     -0.015963   -0.015809 -0.000154      -0.907379                    NaN                   NaN NO TRADE z_below_threshold
   LEFT_WING_CURV     10P-2*25P+ATM          56      0.020400         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
     PUT_SKEW_10D       10DP vs ATM          56      0.086179    0.085232  0.000947       0.007280                    NaN                   NaN NO TRADE z_below_threshold
     PUT_SKEW_15D       15DP vs ATM          56      0.061095    0.061172 -0.000077      -1.021830                    NaN                   NaN NO TRADE z_below_threshold
     PUT_SKEW_20D       20DP vs ATM          56      0.044823    0.045163 -0.000340      -0.946974                    NaN                   NaN NO TRADE z_below_threshold
     PUT_SKEW_25D       25DP vs ATM          56      0.032889    0.033045 -0.000155      -0.743466                    NaN                   NaN NO TRADE z_below_threshold
     PUT_SKEW_30D       30DP vs ATM          56      0.023681    0.023405  0.000276       0.090165                    NaN                   NaN NO TRADE z_below_threshold
  RIGHT_WING_CURV     10C-2*25C+ATM          56      0.012517         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
           RR_10D     +10DC / -10DP          56     -0.110726   -0.110074 -0.000652       0.349817               0.558749              0.000113 NO TRADE z_below_threshold
           RR_15D     +15DC / -15DP          56     -0.083938   -0.084533  0.000596       0.822346               0.597197              0.000064 NO TRADE z_below_threshold
           RR_20D     +20DC / -20DP          56     -0.065621   -0.066527  0.000906       0.919038               0.599886              0.000043 NO TRADE z_below_threshold
           RR_25D     +25DC / -25DP          56     -0.051421   -0.051769  0.000348       0.182928               0.604661              0.000078 NO TRADE z_below_threshold
           RR_30D     +30DC / -30DP          56     -0.039644   -0.039214 -0.000430      -1.227794               0.629958              0.000150 NO TRADE z_below_threshold
 SLOPE_ATM_TO_10C       ATM -> 10DC          56     -0.061366         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
 SLOPE_ATM_TO_10P       ATM -> 10DP          56      0.215448         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
 SLOPE_ATM_TO_15C       ATM -> 15DC          56     -0.065264         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
 SLOPE_ATM_TO_15P       ATM -> 15DP          56      0.174558         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
 SLOPE_ATM_TO_20C       ATM -> 20DC          56     -0.069328         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
 SLOPE_ATM_TO_20P       ATM -> 20DP          56      0.149408         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
 SLOPE_ATM_TO_25C       ATM -> 25DC          56     -0.074128         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
 SLOPE_ATM_TO_25P       ATM -> 25DP          56      0.131557         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
 SLOPE_ATM_TO_30C       ATM -> 30DC          56     -0.079817         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
 SLOPE_ATM_TO_30P       ATM -> 30DP          56      0.118405         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
VERT_CALL_20D_10D     +20DC / -10DC          56      0.003748    0.003477  0.000271      -0.306126               0.633300              0.000138 NO TRADE z_below_threshold
VERT_CALL_25D_10D     +25DC / -10DC          56      0.006015    0.006117 -0.000102      -0.833806               0.635783              0.000166 NO TRADE z_below_threshold
VERT_CALL_25D_15D     +25DC / -15DC          56      0.004310    0.004637 -0.000326      -0.705927               0.621288              0.000155 NO TRADE z_below_threshold
VERT_CALL_30D_20D     +30DC / -20DC          56      0.004835    0.005555 -0.000720      -1.130630               0.623616              0.000175 NO TRADE z_below_threshold
VERT_CALL_40D_25D     +40DC / -25DC          56      0.008774    0.009153 -0.000379      -0.083447               0.618820              0.000139 NO TRADE z_below_threshold
 VERT_PUT_20D_10D     +20DP / -10DP          56     -0.041356   -0.040070 -0.001287      -0.556583               0.560277              0.000168 NO TRADE z_below_threshold
 VERT_PUT_25D_10D     +25DP / -10DP          56     -0.053290   -0.052188 -0.001102      -0.464337               0.563052              0.000158 NO TRADE z_below_threshold
 VERT_PUT_25D_15D     +25DP / -15DP          56     -0.028206   -0.028128 -0.000078       0.413633               0.579659              0.000092 NO TRADE z_below_threshold
 VERT_PUT_30D_20D     +30DP / -20DP          56     -0.021142   -0.021758  0.000616       1.219832               0.598310              0.000060 NO TRADE z_below_threshold
 VERT_PUT_40D_25D     +40DP / -25DP          56     -0.023235   -0.023903  0.000669       1.121176               0.611426              0.000062 NO TRADE z_below_threshold
  WING_10_VS_25_C           10C-25C          56     -0.006015         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
  WING_10_VS_25_P           10P-25P          56      0.053290         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
   WING_ASYMMETRY        left-right          56      0.007883         NaN       NaN            NaN                    NaN                   NaN NO TRADE z_below_threshold
```

## I. Conclusions

See `outputs/reports/M_conclusions.md` and
`outputs/final_test/L_11Sep2026_report.md`.

Short version: residuals mean-revert a little; the economic size is too
small to survive the cost model; the frozen 11 Sep 2026 book is
**NO TRADE**.

## H. What this does *not* claim

Many structures × horizons × thresholds create a multiple-testing problem. Walk-forward validation and a single frozen holdout are the safeguards used; they do not prove robustness out of this sample.  There is no bid/ask, so executable P&L is a model.  Event calendars are absent, so event premia are only proxied via the volatility regime.  SSVI is a *slice* model here because a single maturity cannot identify a calendar-consistent surface. Conclusions are only those supported by the research-period statistics.

