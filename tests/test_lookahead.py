"""Look-ahead and holdout isolation tests."""

from datetime import date

import numpy as np
import pandas as pd

from config.settings import DEFAULT
from src.features.library import add_rolling_stats, attach_future_labels


def test_rolling_uses_only_past_and_present():
    df = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"]),
            "structure": ["RR_25D"] * 4,
            "residual": [0.01, 0.02, 0.03, 0.40],
        }
    )
    out = add_rolling_stats(df, "residual", windows=(3,), prefix="residual")
    # Last z-score must not depend on a fictional future row.
    assert out["mean_3_residual"].iloc[0] == out["residual"].iloc[0] or np.isnan(out["mean_3_residual"].iloc[0])
    # Window of 3 at row 2 uses rows 0..2 only.
    expected = np.mean([0.01, 0.02, 0.03])
    assert abs(out["mean_3_residual"].iloc[2] - expected) < 1e-12


def test_future_labels_cut_at_train_end():
    dates = pd.bdate_range("2026-09-01", "2026-09-08")
    df = pd.DataFrame(
        {
            "trade_date": dates,
            "structure": ["RR_25D"] * len(dates),
            "residual": np.linspace(-0.02, 0.02, len(dates)),
        }
    )
    out = attach_future_labels(df, "residual", horizons=(5,), label_horizon_cutoff=date(2026, 9, 8))
    # 2026-09-04 + 5 bdays is after 2026-09-08 → label must be NaN
    row = out.loc[out["trade_date"] == pd.Timestamp("2026-09-04")]
    assert row["convergence_h5"].isna().all()


def test_final_test_not_in_training_calendar():
    assert DEFAULT.allowed_for_training(date(2026, 9, 8))
    assert not DEFAULT.allowed_for_training(date(2026, 9, 9))
    assert not DEFAULT.allowed_for_training(date(2026, 9, 10))
    assert not DEFAULT.allowed_for_training(date(2026, 9, 11))
    assert DEFAULT.is_final_test(date(2026, 9, 11))
    assert DEFAULT.is_excluded_gap(date(2026, 9, 9))


def test_processable_stops_at_test_date():
    from src.pipeline import processable_dates

    dates = processable_dates(DEFAULT)
    assert date(2026, 9, 11) in dates
    assert all(d <= date(2026, 9, 11) for d in dates)
    assert date(2026, 9, 14) not in dates
