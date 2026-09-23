"""End-to-end research pipeline.

Phases are incremental.  The final holdout (2026-09-11) is processed for
signal generation only after all research-period decisions are frozen.
Dates after 2026-09-11 are used solely to score that frozen decision.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from pyarrow.lib import ArrowInvalid, ArrowTypeError

import numpy as np
import pandas as pd

from config.settings import DEFAULT, LOG_DIR, OUTPUT_DIR, ResearchConfig
from src.backtest.engine import backtest_structures, summarize_backtest, transaction_cost
from src.cleaning.clean import clean_chain
from src.data_loader.loader import list_available_dates, load_day
from src.features.library import add_rolling_stats, attach_future_labels, compute_realized_vol
from src.interpolation.delta_interp import build_delta_grid
from src.models.predictive import apply_frozen, walk_forward_predict
from src.reporting.reports import plot_history, plot_surface_day, write_markdown, df_to_md
from src.signals.cheap_expensive import annotate_cheap_expensive, decide_trade
from src.structures.engine import build_all_structures
from src.surface.construction import build_surface_slice
from src.surface.dte_selector import select_nearest_expiry
from src.surface.ensemble import fit_all_models
from src.surface.black_scholes import implied_vol

LOGGER = logging.getLogger("ivrv")


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def research_dates(cfg: ResearchConfig) -> list[date]:
    all_d = list_available_dates()
    return [d for d in all_d if cfg.train_start <= d <= cfg.train_end]


def processable_dates(cfg: ResearchConfig) -> list[date]:
    """Surfaces may be built through the test date (no later)."""
    all_d = list_available_dates()
    return [d for d in all_d if cfg.train_start <= d <= cfg.test_date]


def process_one_day(
    d: date,
    cfg: ResearchConfig,
    prev_svi: tuple[float, ...] | None,
    reconstruct_iv: bool = False,
) -> dict:
    raw = load_day(d, cfg=cfg, snapshot=True)
    snap_time = raw["time"].max()
    cleaned, diag = clean_chain(raw, cfg)
    if cleaned.empty:
        raise ValueError(f"{d}: no rows survived cleaning")
    meta, sl = select_nearest_expiry(
        cleaned, target_dte=cfg.target_dte, trade_date=d, snapshot_time=snap_time
    )
    sl_clean, sl_diag = clean_chain(sl, cfg)
    surface, assumptions = build_surface_slice(
        sl_clean, meta.actual_dte, cfg, reconstruct_iv=reconstruct_iv
    )
    usable_n = int(surface["usable"].sum())
    if usable_n < cfg.min_valid_strikes:
        raise ValueError(f"{d}: only {usable_n} usable strikes")
    fitted, fits, metrics = fit_all_models(surface, cfg, prev_svi=prev_svi)
    structures = build_all_structures(fitted, cfg)
    delta_grid = build_delta_grid(
        fitted, cfg.delta_levels, cfg.max_delta_extrapolation, "market_iv"
    )
    arb = _slice_arb_checks(fitted)
    return {
        "date": d,
        "meta": meta,
        "diag": diag,
        "slice_diag": sl_diag,
        "assumptions": assumptions,
        "surface": fitted,
        "structures": structures,
        "delta_grid": delta_grid,
        "metrics": metrics,
        "fits": fits,
        "arb": arb,
        "snapshot_time": snap_time,
    }


def _slice_arb_checks(surface: pd.DataFrame) -> dict:
    """Static checks on the selected 60-DTE call/put prices."""
    s = surface.loc[surface["usable"]].sort_values("strike")
    if len(s) < 4:
        return {"n": len(s)}
    calls = s["call_price"].to_numpy(dtype=float)
    puts = s["put_price"].to_numpy(dtype=float)
    K = s["strike"].to_numpy(dtype=float)
    # Calls should decrease in K; puts increase.
    call_mono = float((np.diff(calls) <= 1e-6).mean())
    put_mono = float((np.diff(puts) >= -1e-6).mean())
    # Butterfly / convexity: C(K-d) - 2C(K) + C(K+d) >= 0 on consecutive triples
    conv = []
    for i in range(1, len(calls) - 1):
        conv.append(calls[i - 1] - 2 * calls[i] + calls[i + 1])
    return {
        "n": int(len(s)),
        "call_monotonic_frac": call_mono,
        "put_monotonic_frac": put_mono,
        "min_call_butterfly": float(np.min(conv)) if conv else np.nan,
        "neg_butterfly_count": int(np.sum(np.array(conv) < -1e-6)) if conv else 0,
    }


def run_surface_panel(cfg: ResearchConfig | None = None, through: date | None = None) -> dict:
    cfg = cfg or DEFAULT
    dates = [d for d in processable_dates(cfg) if through is None or d <= through]
    LOGGER.info("Building surfaces for %d dates through %s", len(dates), dates[-1])
    dte_rows, clean_rows, fit_rows, arb_rows = [], [], [], []
    surfaces, structures, grids = [], [], []
    prev_svi = None
    iv_recon_rows = []
    for i, d in enumerate(dates):
        # Never initialise SVI from a non-research date when building research.
        if not cfg.allowed_for_training(d):
            prev_svi = None
        reconstruct = i == 0 or d in (cfg.train_start, cfg.train_end, cfg.test_date)
        day = process_one_day(d, cfg, prev_svi, reconstruct_iv=reconstruct)
        m = day["meta"]
        dte_rows.append(
            {
                "trade_date": d,
                "selected_expiry": m.selected_expiry,
                "actual_dte": m.actual_dte,
                "target_dte": m.target_dte,
                "dte_error": m.dte_error,
                "abs_dte_error": m.abs_dte_error,
                "n_candidate_expiries": m.n_candidate_expiries,
                "n_valid_strikes": m.n_valid_strikes,
                "exact_match": m.exact_match,
                "tie_broken": m.tie_broken,
                "contract": m.contract,
                "snapshot_time": day["snapshot_time"],
                "forward_source": day["assumptions"].forward_source,
                "put_delta_convention": day["assumptions"].put_delta_sign_convention,
            }
        )
        clean_rows.append(day["diag"].to_record())
        rec = {"trade_date": d, **{f"{k}_{kk}": vv for k, mtr in day["metrics"].items() if isinstance(mtr, dict) for kk, vv in mtr.items()}}
        rec.update({f"arb_{k}": v for k, v in day["arb"].items()})
        fit_rows.append(rec)
        arb_rows.append({"trade_date": d, **day["arb"]})
        surf = day["surface"]
        surf["trade_date"] = d
        surfaces.append(surf)
        st = day["structures"]
        if not st.empty:
            structures.append(st)
        grid = day["delta_grid"]
        grid["trade_date"] = d
        grids.append(grid)
        if day["fits"].svi.success:
            prev_svi = day["fits"].svi.params()
        if reconstruct and "recon_call_iv" in surf.columns:
            iv_recon_rows.append(
                {
                    "trade_date": d,
                    "call_iv_diff_med": float(surf["call_iv_diff"].median()),
                    "call_iv_diff_mae": float(surf["call_iv_diff"].abs().mean()),
                    "put_iv_diff_med": float(surf["put_iv_diff"].median()),
                    "put_iv_diff_mae": float(surf["put_iv_diff"].abs().mean()),
                    "n": int(surf["call_iv_diff"].notna().sum()),
                }
            )
        if d in cfg.extra_plot_dates:
            plot_surface_day(surf, OUTPUT_DIR / "plots", f"{d.isoformat()}")
        if (i + 1) % 20 == 0:
            LOGGER.info("  processed %d / %d (%s)", i + 1, len(dates), d)

    dte_df = pd.DataFrame(dte_rows)
    clean_df = pd.DataFrame(clean_rows)
    fit_df = pd.DataFrame(fit_rows)
    surface_df = pd.concat(surfaces, ignore_index=True)
    struct_df = pd.concat(structures, ignore_index=True) if structures else pd.DataFrame()
    grid_df = pd.concat(grids, ignore_index=True)
    recon_df = pd.DataFrame(iv_recon_rows)

    _save(dte_df, "surfaces", "dte_selection")
    _save(clean_df, "cleaned", "cleaning_diagnostics")
    _save(fit_df, "models", "fit_metrics")
    _save(surface_df, "residuals", "surface_residuals")
    _save(struct_df, "structures", "structures")
    _save(grid_df, "surfaces", "delta_grid")
    _save(recon_df, "cleaned", "iv_reconstruction")
    return {
        "dte": dte_df,
        "clean": clean_df,
        "fit": fit_df,
        "surface": surface_df,
        "structures": struct_df,
        "grid": grid_df,
        "recon": recon_df,
    }


def enrich_structures(struct_df: pd.DataFrame, dte_df: pd.DataFrame, cfg: ResearchConfig) -> pd.DataFrame:
    out = struct_df.copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.date
    # ATM IV per date from ATM_IV structure
    atm = out.loc[out["structure"] == "ATM_IV", ["trade_date", "market_value"]].rename(
        columns={"market_value": "atm_iv"}
    )
    out = out.merge(atm, on="trade_date", how="left")
    # Realized vol from unique daily spot
    daily_spot = out.drop_duplicates("trade_date").set_index("trade_date")["spot"].sort_index()
    daily_spot.index = pd.to_datetime(daily_spot.index)
    rv = compute_realized_vol(daily_spot)
    rv.index = pd.to_datetime(rv.index).date
    out = out.merge(rv, left_on="trade_date", right_index=True, how="left")
    out["iv_rv_20"] = out["atm_iv"] - out["rv_20"]
    out["iv_rv_60"] = out["atm_iv"] - out["rv_60"]
    out["transaction_cost"] = [
        transaction_cost(float(d), cfg) if np.isfinite(d) else cfg.cost_atm_half_spread
        for d in out.get("delta", pd.Series(np.nan, index=out.index)).fillna(0.25)
    ]
    out = annotate_cheap_expensive(out)
    # Rolling stats — causal, by structure.  Includes test date rows but
    # z-scores at t use only dates <= t.
    out = add_rolling_stats(out, "residual", windows=cfg.rolling_windows, prefix="residual")
    out = add_rolling_stats(out, "market_value", windows=cfg.rolling_windows, prefix="market_value")
    if "price_residual" in out.columns:
        out = add_rolling_stats(out, "price_residual", windows=cfg.rolling_windows, prefix="price_residual")
    # Labels for training may not use outcomes after TRAIN_END.
    out = attach_future_labels(
        out,
        "residual",
        horizons=cfg.horizons,
        label_horizon_cutoff=cfg.train_end,
    )
    if "price_residual" in out.columns:
        tmp = attach_future_labels(
            out[["trade_date", "structure", "price_residual"]].copy(),
            "price_residual",
            horizons=cfg.horizons,
            label_horizon_cutoff=cfg.train_end,
        )
        for h in cfg.horizons:
            out[f"future_price_change_h{h}"] = tmp[f"future_change_h{h}"]
    return out


def run_predictive(struct_en: pd.DataFrame, cfg: ResearchConfig) -> tuple[pd.DataFrame, object, pd.DataFrame]:
    research = struct_en.loc[struct_en["trade_date"].map(cfg.allowed_for_training)].copy()
    # Focus ML on relative-value structures, not raw level.
    kinds = {"risk_reversal", "butterfly", "vertical", "skew"}
    research = research.loc[research["kind"].isin(kinds)].copy()
    oos, frozen, scores = walk_forward_predict(research, cfg, horizon=5, target="convergence")
    _save(scores, "models", "walkforward_scores")
    _save(oos, "models", "walkforward_oos")
    return oos, frozen, scores


def run_backtests(struct_en: pd.DataFrame, frozen, cfg: ResearchConfig) -> tuple[pd.DataFrame, dict]:
    research = struct_en.loc[struct_en["trade_date"].map(cfg.allowed_for_training)].copy()
    research = apply_frozen(research, frozen)
    bt = backtest_structures(research, None, cfg, horizon=frozen.horizon)
    # Signal mask using the FROZEN threshold only.
    z = bt.get("z_60_residual")
    mask = z.notna() & (z.abs() >= frozen.z_threshold) & (~bt.get("extrapolated", False))
    if "pred_prob_convergence" in bt.columns:
        mask = mask & (bt["pred_prob_convergence"].fillna(0.5) >= 0.5)
    summary = {
        "all": summarize_backtest(bt),
        "signalled": summarize_backtest(bt, mask),
        "verticals": summarize_backtest(bt.loc[bt["kind"] == "vertical"], mask.loc[bt["kind"] == "vertical"] if len(bt) else None),
        "rr": summarize_backtest(bt.loc[bt["kind"] == "risk_reversal"]),
        "bf": summarize_backtest(bt.loc[bt["kind"] == "butterfly"]),
        "z_threshold": frozen.z_threshold,
        "horizon": frozen.horizon,
    }
    _save(bt, "backtests", "structure_backtest")
    (OUTPUT_DIR / "backtests" / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return bt, summary


def run_final_test(struct_en: pd.DataFrame, frozen, cfg: ResearchConfig, surface_df: pd.DataFrame) -> pd.DataFrame:
    test = struct_en.loc[struct_en["trade_date"] == cfg.test_date].copy()
    if test.empty:
        raise ValueError("no structures on final test date")
    test = apply_frozen(test, frozen)
    decisions = []
    for _, row in test.iterrows():
        dec = decide_trade(row, cfg, z_threshold=frozen.z_threshold)
        decisions.append(dec)
    dec_df = pd.DataFrame(decisions)
    test = pd.concat([test.reset_index(drop=True), dec_df], axis=1)
    _save(test, "final_test", "signals_2026-09-11")
    # Rankings — kept separate, never collapsed unless justified.
    def _rank(df: pd.DataFrame, col: str, name: str) -> pd.DataFrame:
        s = df.dropna(subset=[col]).copy()
        s[f"rank_{name}"] = s[col].abs().rank(ascending=False) if "residual" in col or col.endswith("z") else s[col].rank(ascending=False)
        return s.sort_values(f"rank_{name}")

    rankings = {
        "structural": _rank(test, "residual", "structural"),
        "confidence": _rank(test, "z_60_residual", "z") if "z_60_residual" in test else test,
        "convergence": _rank(test, "pred_prob_convergence", "pconv") if "pred_prob_convergence" in test else test,
        "expected": _rank(test, "pred_expected_return", "er") if "pred_expected_return" in test else test,
    }
    for name, df in rankings.items():
        _save(df, "final_test", f"rank_{name}")
    return test


def write_all_reports(bundle: dict, struct_en: pd.DataFrame, scores: pd.DataFrame, summary: dict, test: pd.DataFrame, cfg: ResearchConfig) -> None:
    dte = bundle["dte"]
    # History plots
    atm = struct_en.loc[struct_en["structure"] == "ATM_IV"].set_index("trade_date")["market_value"]
    rr = struct_en.loc[struct_en["structure"] == "RR_25D"].set_index("trade_date")["market_value"]
    bf = struct_en.loc[struct_en["structure"] == "BF_25D"].set_index("trade_date")["market_value"]
    plot_history(atm, "ATM IV (60-DTE nearest expiry)", OUTPUT_DIR / "plots" / "atm_iv.png")
    plot_history(rr, "25D risk reversal", OUTPUT_DIR / "plots" / "rr25.png")
    plot_history(bf, "25D butterfly", OUTPUT_DIR / "plots" / "bf25.png")

    research = struct_en.loc[struct_en["trade_date"].map(cfg.allowed_for_training)]
    # Research questions — computed only on the research sample.
    q = _research_questions(research)

    write_markdown(
        OUTPUT_DIR / "reports" / "FINAL_REPORT.md",
        [
            ("60-DTE IV Relative-Value Research Report", _exec_summary(dte, bundle, summary, q, cfg)),
            ("A. Data quality", _data_quality_md(bundle)),
            ("B. 60-DTE selection", df_to_md(dte.describe(include="all").reset_index()) + "\n\n" + _dte_md(dte)),
            ("C. Surface-fit comparison", _fit_md(bundle["fit"])),
            ("D. Historical residual / structure analysis", q),
            ("E. Walk-forward predictive models", df_to_md(scores) if scores is not None and len(scores) else "_no scores_"),
            ("F. Backtest (research period only)", json.dumps(summary, indent=2, default=str)),
            ("G. Frozen 11 September 2026 test", _test_md(test)),
            ("H. What this does *not* claim", _caveats()),
        ],
    )


def _exec_summary(dte, bundle, summary, q, cfg) -> str:
    return (
        f"Training / research window: {cfg.train_start} → {cfg.train_end} "
        f"({int((dte['trade_date']<=cfg.train_end).sum())} files).\n\n"
        f"Frozen holdout surface: {cfg.test_date}.  "
        f"9–10 Sep 2026 excluded from training/tuning.\n\n"
        f"Snapshot rule: last timestamp of each day.  "
        f"Expiry rule: single nearest expiry to {cfg.target_dte} DTE "
        f"(exact 60 on {int(dte['exact_match'].sum())} days).\n\n"
        f"Forward: put-call parity (rate is identically 0; underlying is spot).\n\n"
        "Cheap ≠ low IV.  Signals require residual + history + model agreement "
        "+ liquidity + predicted convergence.  NO TRADE is a valid output.\n"
    )


def _data_quality_md(bundle) -> str:
    c = bundle["clean"]
    r = bundle["recon"]
    txt = (
        f"Cleaning rows across snapshots: total={int(c['total_rows'].sum())}, "
        f"valid={int(c['valid_rows'].sum())}, removed={int(c['removed_rows'].sum())}.\n\n"
        "Vendor field `contact` in the brief is actually `contract` in the files. "
        "No bid/ask, volume or open-interest columns exist.  `rate` is always 0. "
        "`put_delta` is unsigned through 2026-07-15 and signed thereafter; "
        "the engine always uses abs(put_delta).  IV is decimal.\n"
    )
    if r is not None and len(r):
        txt += (
            f"\nBS IV reconstruction MAE (call) median across audit days: "
            f"{float(r['call_iv_diff_mae'].median()):.4f}. "
            "Supplied IV is used because reconstruction error is small on "
            "liquid central strikes; wings can differ and are filtered.\n"
        )
    return txt


def _dte_md(dte: pd.DataFrame) -> str:
    return (
        f"Exact DTE=60: {int(dte['exact_match'].sum())} / {len(dte)} days.\n"
        f"Mean |DTE-60| = {float(dte['abs_dte_error'].mean()):.2f}, "
        f"max = {int(dte['abs_dte_error'].max())}.\n"
        "Selection is nearest *expiry*, then all strikes of that expiry.\n"
    )


def _fit_md(fit: pd.DataFrame) -> str:
    cols = [c for c in fit.columns if c.endswith("_iv_rmse")]
    if not cols:
        return "_no fit rmse columns_"
    desc = fit[cols].describe().T
    return (
        "In-sample IV RMSE by model (research+test surfaces).  "
        "Lowest RMSE is **not** the selection criterion.\n\n" + df_to_md(desc.reset_index())
    )


def _research_questions(research: pd.DataFrame) -> str:
    lines = []
    for name, kind in [("RR_25D", "risk_reversal"), ("BF_25D", "butterfly")]:
        sub = research.loc[research["structure"] == name]
        if sub.empty or "convergence_h5" not in sub:
            continue
        z = sub["z_60_residual"]
        extreme = sub.loc[z.abs() >= 1.5, "convergence_h5"].dropna()
        allc = sub["convergence_h5"].dropna()
        lines.append(
            f"- {name}: mean conv_h5 all={allc.mean():.5f} (n={len(allc)}), "
            f"|z_60|>=1.5: {extreme.mean():.5f} (n={len(extreme)}), "
            f"hit={float((extreme>0).mean()) if len(extreme) else float('nan'):.3f}"
        )
    verts = research.loc[research["kind"] == "vertical"]
    if len(verts) and "convergence_h5" in verts:
        c = verts["convergence_h5"].dropna()
        lines.append(f"- All verticals conv_h5 mean={c.mean():.5f} n={len(c)} hit={float((c>0).mean()):.3f}")
    # Residual vs future change IC
    if "future_change_h5" in research:
        ic = research[["residual", "future_change_h5"]].dropna()
        if len(ic) > 20:
            corr = float(ic["residual"].corr(ic["future_change_h5"]))
            lines.append(f"- corr(residual, future_change_h5) = {corr:.3f} (negative ⇒ mean reversion)")
    return "\n".join(lines) if lines else "_insufficient overlapping labels_"


def _test_md(test: pd.DataFrame) -> str:
    trades = test.loc[test.get("decision", "") == "TRADE"] if "decision" in test else test.iloc[0:0]
    return (
        f"Structures scored on {DEFAULT.test_date}: {len(test)}.  "
        f"TRADE: {len(trades)}.  NO TRADE is the default when z, liquidity, "
        "disagreement or predicted edge fail the frozen gates.\n\n"
        + df_to_md(
            test[
                [
                    c
                    for c in [
                        "structure",
                        "legs",
                        "actual_dte",
                        "market_value",
                        "fair_value",
                        "residual",
                        "z_60_residual",
                        "pred_prob_convergence",
                        "pred_expected_return",
                        "decision",
                        "no_trade_reasons",
                    ]
                    if c in test.columns
                ]
            ].sort_values("structure"),
            max_rows=80,
        )
    )


def _caveats() -> str:
    return (
        "Many structures × horizons × thresholds create a multiple-testing problem. "
        "Walk-forward validation and a single frozen holdout are the safeguards used; "
        "they do not prove robustness out of this sample.  There is no bid/ask, so "
        "executable P&L is a model.  Event calendars are absent, so event premia "
        "are only proxied via the volatility regime.  SSVI is a *slice* model here "
        "because a single maturity cannot identify a calendar-consistent surface. "
        "Conclusions are only those supported by the research-period statistics.\n"
    )


def _save(df: pd.DataFrame, folder: str, name: str) -> None:
    if df is None or df.empty:
        return
    d = OUTPUT_DIR / folder
    d.mkdir(parents=True, exist_ok=True)
    parquet = d / f"{name}.parquet"
    csv = d / f"{name}.csv"
    try:
        df.to_parquet(parquet, index=False)
    except (ValueError, TypeError, ArrowInvalid, ArrowTypeError):
        # Mixed object columns (e.g. expiry timestamps + dates) — CSV still written.
        pass
    df.to_csv(csv, index=False)


def run_all(cfg: ResearchConfig | None = None) -> None:
    cfg = cfg or DEFAULT
    setup_logging()
    LOGGER.info("=== PHASE 2-7: surfaces, residuals, structures ===")
    bundle = run_surface_panel(cfg, through=cfg.test_date)
    LOGGER.info("=== PHASE 8: historical features / labels ===")
    struct_en = enrich_structures(bundle["structures"], bundle["dte"], cfg)
    _save(struct_en, "structures", "structures_enriched")
    LOGGER.info("=== PHASE 9: walk-forward predictive models (research dates only) ===")
    oos, frozen, scores = run_predictive(struct_en, cfg)
    LOGGER.info("Frozen z-threshold=%.2f horizon=%d features=%s", frozen.z_threshold, frozen.horizon, frozen.features)
    LOGGER.info("=== PHASE 10: research-period backtest ===")
    bt, summary = run_backtests(struct_en, frozen, cfg)
    LOGGER.info("Backtest summary: %s", summary.get("signalled"))
    LOGGER.info("=== PHASE 11: FROZEN test 2026-09-11 ===")
    test = run_final_test(struct_en, frozen, cfg, bundle["surface"])
    n_trade = int((test.get("decision") == "TRADE").sum()) if "decision" in test else 0
    LOGGER.info("Final test TRADE count = %d / %d", n_trade, len(test))
    write_all_reports(bundle, struct_en, scores, summary, test, cfg)
    LOGGER.info("Reports written to %s", OUTPUT_DIR / "reports")
