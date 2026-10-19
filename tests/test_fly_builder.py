"""Unit tests for fixed-strike butterfly construction and baseline acceptance figures."""

from __future__ import annotations

import pytest

from spx_butterfly.data_loader import (
    find_default_file,
    load_raw_dataset,
    transform_to_long_form,
    get_snapshot,
)
from spx_butterfly.fly_builder import build_all_butterflies


def test_august_3_baseline_acceptance():
    """Test A: August 3 baseline validation.

    Call fly centred at 7730 must equal approximately 12.14707.
    Put fly centred at 7530 uses synthesized ATM put via PCP (P=C-S+K),
    so premium is ~8.0409 (legacy 9.2908 assumed put ATM = call ATM).
    """
    path = find_default_file()
    raw = load_raw_dataset(path)
    long_df = transform_to_long_form(raw)
    snap = get_snapshot(long_df, "2026-08-03")

    butterflies = build_all_butterflies(snap, wing_width=100.0)
    calls = butterflies["call"]
    puts = butterflies["put"]

    # Verify Call Fly at 7730
    c7730 = next((f for f in calls if f.centre_strike == 7730.0), None)
    assert c7730 is not None
    assert c7730.lower_strike == 7630.0
    assert c7730.upper_strike == 7830.0
    assert pytest.approx(c7730.initial_fly_premium, rel=1e-4) == 12.14707

    # Verify Put Fly at 7530 (upper leg = ATM put synthesized via PCP)
    p7530 = next((f for f in puts if f.centre_strike == 7530.0), None)
    assert p7530 is not None
    assert p7530.lower_strike == 7430.0
    assert p7530.upper_strike == 7630.0
    assert pytest.approx(p7530.initial_fly_premium, rel=1e-4) == 8.040886


def test_date_switching_august_3_to_4():
    """Test F: Switching dates reconstructs ATM reference and baseline strikes."""
    path = find_default_file()
    raw = load_raw_dataset(path)
    long_df = transform_to_long_form(raw)

    snap_aug3 = get_snapshot(long_df, "2026-08-03")
    snap_aug4 = get_snapshot(long_df, "2026-08-04")

    # August 3 baseline
    assert snap_aug3["underlying"].iloc[0] == 7631.25
    assert snap_aug3["atm_strike"].iloc[0] == 7630.0

    # August 4 baseline
    assert snap_aug4["underlying"].iloc[0] == 7774.75
    assert snap_aug4["atm_strike"].iloc[0] == 7775.0

    flies_aug4 = build_all_butterflies(snap_aug4, wing_width=100.0)
    call_centres_aug4 = [f.centre_strike for f in flies_aug4["call"]]

    # Aug 4 ATM+100 = 7875, ATM+200 = 7975
    assert 7875.0 in call_centres_aug4
    assert 7975.0 in call_centres_aug4
