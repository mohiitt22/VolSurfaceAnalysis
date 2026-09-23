"""DTE selection tests — exact match, nearest, documented ties."""

from src.surface.dte_selector import select_from_dte_list, select_nearest_expiry
import pandas as pd


def test_exact_60_selected():
    assert select_from_dte_list([30, 60, 90], 60) == 60


def test_nearest_58_from_55_58_63():
    assert select_from_dte_list([55, 58, 63], 60) == 58


def test_tie_57_63_prefers_longer():
    """Deterministic tie-break: equal |DTE-60|, prefer DTE >= 60."""
    assert select_from_dte_list([57, 63], 60) == 63


def test_selector_uses_one_expiry():
    df = pd.DataFrame(
        {
            "expiry": pd.to_datetime(["2026-01-01"] * 3 + ["2026-02-01"] * 5),
            "dte": [58, 58, 58, 63, 63, 63, 63, 63],
            "strike": [1, 2, 3, 1, 2, 3, 4, 5],
            "contract": ["A"] * 3 + ["B"] * 5,
            "time": pd.to_datetime(["2025-11-04"] * 8),
            "trade_date": [pd.Timestamp("2025-11-04").date()] * 8,
        }
    )
    meta, sl = select_nearest_expiry(df, target_dte=60)
    assert meta.actual_dte == 58
    assert sl["expiry"].nunique() == 1
    assert (sl["expiry"] == meta.selected_expiry).all()


def test_tie_broken_by_liquidity():
    df = pd.DataFrame(
        {
            "expiry": pd.to_datetime(["2026-01-01"] * 3 + ["2026-02-01"] * 8),
            "dte": [57] * 3 + [63] * 8,
            "strike": list(range(3)) + list(range(8)),
            "contract": ["A"] * 3 + ["B"] * 8,
            "time": pd.to_datetime(["2025-11-04"] * 11),
            "trade_date": [pd.Timestamp("2025-11-04").date()] * 11,
        }
    )
    meta, sl = select_nearest_expiry(df, target_dte=60)
    assert meta.actual_dte == 63
    assert meta.tie_broken is True
    assert sl["expiry"].nunique() == 1
