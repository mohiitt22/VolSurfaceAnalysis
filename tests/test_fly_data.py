"""Unit tests for option surface data loading, transformation, and validation."""

from __future__ import annotations

import pytest
import pandas as pd

from spx_butterfly.data_loader import (
    find_default_file,
    load_raw_dataset,
    transform_to_long_form,
    get_available_dates,
    get_snapshot,
)
from spx_butterfly.data_validation import validate_surface_data


def test_default_file_exists():
    path = find_default_file()
    assert path is not None
    assert path.exists()


def test_transform_and_validation():
    path = find_default_file()
    raw = load_raw_dataset(path)
    long_df = transform_to_long_form(raw)

    assert not long_df.empty
    expected_cols = [
        "date",
        "underlying",
        "atm_strike",
        "target_dte",
        "option_side",
        "strike",
        "atm_offset",
        "iv_decimal",
        "premium",
    ]
    for c in expected_cols:
        assert c in long_df.columns

    val_res = validate_surface_data(long_df)
    assert len(val_res["errors"]) == 0

    dates = get_available_dates(long_df)
    assert "2026-08-03" in dates
    assert "2026-08-04" in dates


def test_august_3_snapshot():
    path = find_default_file()
    raw = load_raw_dataset(path)
    long_df = transform_to_long_form(raw)
    snap = get_snapshot(long_df, "2026-08-03")

    assert snap["underlying"].iloc[0] == 7631.25
    assert snap["atm_strike"].iloc[0] == 7630.0
    assert snap["target_dte"].iloc[0] == 60.0

    # Check that both call and put sides contain the ATM contract at 7630
    call_atm = snap[(snap["option_side"] == "call") & (snap["strike"] == 7630.0)]
    put_atm = snap[(snap["option_side"] == "put") & (snap["strike"] == 7630.0)]

    assert len(call_atm) == 1
    assert len(put_atm) == 1
    assert pytest.approx(call_atm["premium"].iloc[0], rel=1e-4) == 169.0354
    # Put ATM is synthesized via PCP: P = C - S + K (r = q = 0)
    expected_put = 169.0354 - 7631.25 + 7630.0
    assert pytest.approx(put_atm["premium"].iloc[0], rel=1e-4) == expected_put
    assert bool(put_atm["synthesized"].iloc[0]) is True
    assert pytest.approx(call_atm["iv_decimal"].iloc[0], rel=1e-4) == 0.136466
    assert pytest.approx(put_atm["iv_decimal"].iloc[0], rel=1e-4) == 0.136466
