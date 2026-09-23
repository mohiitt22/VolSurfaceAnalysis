"""Research configuration. All research cutoffs and model knobs live here."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "SNP data"
OUTPUT_DIR = ROOT / "outputs"
LOG_DIR = ROOT / "logs"


@dataclass(frozen=True)
class ResearchConfig:
    """Frozen research calendar and modelling choices.

    TRAIN_END is the last date allowed for model development, parameter
    estimation, threshold selection, feature-engineering decisions and
    training.  The final holdout surface is TEST_DATE.  2026-09-09 and
    2026-09-10 are neither used for training/tuning nor as the holdout.
    """

    target_dte: int = 60
    train_start: date = date(2025, 6, 5)
    train_end: date = date(2026, 9, 8)
    test_date: date = date(2026, 9, 11)
    excluded_gap_dates: tuple[date, ...] = (date(2026, 9, 9), date(2026, 9, 10))

    # Snapshot rule: last available timestamp of the trading day.
    snapshot_rule: str = "last"

    # Day-count for total variance and discounting.
    day_count: int = 365

    # Surface / IV filters for the selected 60-DTE slice.
    iv_min: float = 0.02
    iv_max: float = 1.50
    min_valid_strikes: int = 8
    atm_neighborhood: int = 2  # |atm| <= this for PCP forward

    # Delta grid used for interpolation and structures.
    delta_levels: tuple[float, ...] = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
    max_delta_extrapolation: float = 0.03

    # Rolling windows (trading days) and forecast horizons.
    rolling_windows: tuple[int, ...] = (20, 60, 120, 252)
    horizons: tuple[int, ...] = (1, 3, 5, 10, 20)

    # Walk-forward
    min_train_days: int = 80
    validation_step_days: int = 20
    embargo_days: int = 5  # purge gap between train residuals and labels

    # Signal thresholds tested inside walk-forward (never on the holdout).
    z_thresholds: tuple[float, ...] = (1.0, 1.5, 2.0, 2.5, 3.0)
    default_z_threshold: float = 1.5
    max_model_dispersion: float = 0.03  # 3 vol points
    min_liquidity_score: float = 0.25
    min_predicted_edge: float = 0.0

    # Transaction-cost assumptions (no bid/ask in the files).
    # Conservative half-spread in price points, scaled by distance from ATM.
    cost_atm_half_spread: float = 0.50
    cost_wing_extra: float = 1.50
    cost_iv_half_spread: float = 0.002  # 0.2 vol points

    # SABR
    sabr_beta: float = 1.0

    # Plot subset (not every date).
    extra_plot_dates: tuple[date, ...] = (
        date(2025, 6, 5),
        date(2025, 12, 15),
        date(2026, 3, 16),
        date(2026, 6, 15),
        date(2026, 9, 8),
        date(2026, 9, 11),
    )

    random_seed: int = 7
    n_jobs: int = 1

    expected_columns: tuple[str, ...] = (
        "contract",
        "time",
        "expiry",
        "strike",
        "underlying",
        "rate",
        "call_price",
        "put_price",
        "call_iv",
        "put_iv",
        "call_delta",
        "put_delta",
        "straddle_delta",
        "call_gamma",
        "put_gamma",
        "call_vega",
        "put_vega",
        "call_theta",
        "put_theta",
        "atm",
        "dte",
    )

    structure_delta_pairs: tuple[tuple[float, float], ...] = (
        (0.25, 0.15),
        (0.30, 0.20),
        (0.20, 0.10),
        (0.25, 0.10),
        (0.40, 0.25),
    )
    butterfly_deltas: tuple[float, ...] = (0.10, 0.15, 0.20, 0.25, 0.30)
    rr_deltas: tuple[float, ...] = (0.10, 0.15, 0.20, 0.25, 0.30)

    def is_research_date(self, d: date) -> bool:
        return self.train_start <= d <= self.train_end

    def is_final_test(self, d: date) -> bool:
        return d == self.test_date

    def is_excluded_gap(self, d: date) -> bool:
        return d in self.excluded_gap_dates

    def allowed_for_training(self, d: date) -> bool:
        return self.is_research_date(d)

    def allowed_as_of(self, d: date) -> bool:
        """Information available for inference at date d (no future)."""
        return d <= self.test_date


DEFAULT = ResearchConfig()
