"""Walk-forward predictive models.  No random splits.  No test-date peeking.

Training sample restriction:
    trade_date <= TRAIN_END
    and t+h label date <= TRAIN_END

The frozen model is the last walk-forward fit.  Thresholds are chosen
by average validation hit-rate / cost-adjusted proxy, never on TEST_DATE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import ElasticNet, LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from config.settings import DEFAULT, ResearchConfig

LOGGER = logging.getLogger(__name__)

FEATURE_CANDIDATES = [
    "residual",
    "price_residual",
    "z_20_residual",
    "z_60_residual",
    "z_120_residual",
    "z_20_market_value",
    "z_60_market_value",
    "model_dispersion",
    "confidence_score",
    "liquidity_score",
    "actual_dte",
    "abs_dte_error",
    "atm_iv",
    "rv_20",
    "rv_60",
    "iv_rv_20",
    "spot_ret_5",
    "spot_ret_20",
    "drawdown_20",
]


@dataclass
class FrozenModel:
    name: str
    pipeline: object
    features: list[str]
    z_threshold: float
    horizon: int
    target: str
    validation_scores: pd.DataFrame


def _available_features(df: pd.DataFrame) -> list[str]:
    return [c for c in FEATURE_CANDIDATES if c in df.columns]


def _make_models(seed: int) -> dict[str, Pipeline]:
    return {
        "ridge": Pipeline(
            [("scaler", StandardScaler()), ("model", Ridge(alpha=1.0))]
        ),
        "elasticnet": Pipeline(
            [("scaler", StandardScaler()), ("model", ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=5000))]
        ),
        "logreg": Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(max_iter=500, C=0.5)),
            ]
        ),
        "rf": RandomForestClassifier(
            n_estimators=200, max_depth=4, min_samples_leaf=20, random_state=seed
        ),
        "gbm": GradientBoostingClassifier(
            n_estimators=150, max_depth=2, learning_rate=0.05, random_state=seed
        ),
    }


def walk_forward_predict(
    panel: pd.DataFrame,
    cfg: ResearchConfig | None = None,
    horizon: int = 5,
    target: str = "convergence",
) -> tuple[pd.DataFrame, FrozenModel, pd.DataFrame]:
    cfg = cfg or DEFAULT
    feats = _available_features(panel)
    if not feats:
        raise ValueError("no predictive features available")

    y_col = f"convergence_h{horizon}" if target == "convergence" else f"future_change_h{horizon}"
    cls_col = f"converged_h{horizon}"
    work = panel.copy()
    work["trade_date"] = pd.to_datetime(work["trade_date"]).dt.date
    work = work.loc[work["trade_date"].map(cfg.allowed_for_training)].copy()
    work = work.dropna(subset=feats + [y_col])
    dates = sorted(work["trade_date"].unique())
    if len(dates) < cfg.min_train_days + cfg.validation_step_days:
        raise ValueError("insufficient research dates for walk-forward")

    models = _make_models(cfg.random_seed)
    # Primary model: ridge on expected convergence (continuous).
    # Classification models used for probability of positive convergence.
    oos_rows = []
    val_scores = []
    last_pipe = None
    start_idx = cfg.min_train_days
    i = start_idx
    while i < len(dates):
        train_end = dates[i - 1]
        val_end_idx = min(i + cfg.validation_step_days, len(dates))
        val_dates = dates[i:val_end_idx]
        train = work.loc[work["trade_date"] <= train_end]
        val = work.loc[work["trade_date"].isin(val_dates)]
        if len(train) < 50 or len(val) < 10:
            i = val_end_idx
            continue
        Xtr, ytr = train[feats].to_numpy(), train[y_col].to_numpy()
        Xva, yva = val[feats].to_numpy(), val[y_col].to_numpy()
        pipe = _make_models(cfg.random_seed)["ridge"]
        pipe.fit(Xtr, ytr)
        pred = pipe.predict(Xva)
        # Classification
        ytr_c = (train[cls_col].fillna(0) > 0.5).astype(int).to_numpy()
        clf = _make_models(cfg.random_seed)["logreg"]
        if len(np.unique(ytr_c)) > 1:
            clf.fit(train[feats], ytr_c)
            proba = clf.predict_proba(Xva)[:, 1]
        else:
            proba = np.full(len(Xva), np.nan)
        last_pipe = pipe
        fold = val.copy()
        fold["pred_expected_convergence"] = pred
        fold["pred_prob_convergence"] = proba
        oos_rows.append(fold)
        ic = _safe_corr(pred, yva)
        hit = float(np.mean(np.sign(pred) == np.sign(yva))) if len(yva) else np.nan
        val_scores.append(
            {
                "train_end": train_end,
                "val_start": val_dates[0],
                "val_end": val_dates[-1],
                "n_train": len(train),
                "n_val": len(val),
                "ic": ic,
                "sign_hit": hit,
                "mae": float(np.mean(np.abs(pred - yva))),
            }
        )
        i = val_end_idx

    oos = pd.concat(oos_rows, ignore_index=True) if oos_rows else work.iloc[0:0]
    scores = pd.DataFrame(val_scores)
    # Threshold selection on validation folds only.
    best_z, best_score = _select_threshold(oos, cfg)
    LOGGER.info("Selected z-threshold %.2f with val score %.4f", best_z, best_score)

    # Refit frozen model on all research dates.
    frozen_pipe = _make_models(cfg.random_seed)["ridge"]
    frozen_pipe.fit(work[feats], work[y_col])
    clf = _make_models(cfg.random_seed)["logreg"]
    y_c = (work[cls_col].fillna(0) > 0.5).astype(int)
    if len(np.unique(y_c)) > 1:
        clf.fit(work[feats], y_c)
    else:
        clf = None

    frozen = FrozenModel(
        name="ridge+logreg",
        pipeline={"ridge": frozen_pipe, "logreg": clf},
        features=feats,
        z_threshold=best_z,
        horizon=horizon,
        target=target,
        validation_scores=scores,
    )
    return oos, frozen, scores


def apply_frozen(panel: pd.DataFrame, frozen: FrozenModel) -> pd.DataFrame:
    out = panel.copy()
    X = out[frozen.features]
    # Missing features → no prediction
    mask = X.notna().all(axis=1)
    out["pred_expected_convergence"] = np.nan
    out["pred_prob_convergence"] = np.nan
    out["pred_expected_return"] = np.nan
    if mask.any():
        out.loc[mask, "pred_expected_convergence"] = frozen.pipeline["ridge"].predict(X.loc[mask])
        clf = frozen.pipeline["logreg"]
        if clf is not None:
            out.loc[mask, "pred_prob_convergence"] = clf.predict_proba(X.loc[mask])[:, 1]
        out.loc[mask, "pred_expected_return"] = out.loc[mask, "pred_expected_convergence"]
    return out


def _select_threshold(oos: pd.DataFrame, cfg: ResearchConfig) -> tuple[float, float]:
    if oos.empty or "z_60_residual" not in oos.columns:
        return cfg.default_z_threshold, float("nan")
    best_z = cfg.default_z_threshold
    best = -np.inf
    for z in cfg.z_thresholds:
        sub = oos.loc[oos["z_60_residual"].abs() >= z]
        if len(sub) < 30:
            continue
        conv = sub.get("convergence_h5", sub.get("convergence_h1"))
        if conv is None:
            continue
        score = float(conv.mean())
        if score > best:
            best = score
            best_z = z
    return best_z, best


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 5 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])
