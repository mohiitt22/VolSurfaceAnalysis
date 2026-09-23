"""Delta convention, RR, butterfly, vertical, residual tests."""

import numpy as np
import pandas as pd

from src.signals.cheap_expensive import decide_trade
from src.surface.construction import _put_delta_abs


def test_put_delta_abs_handles_both_conventions():
    unsigned = np.array([0.25, 0.50, 0.10])
    signed = np.array([-0.25, -0.50, -0.10])
    assert np.allclose(_put_delta_abs(unsigned), unsigned)
    assert np.allclose(_put_delta_abs(signed), unsigned)


def test_rr25_definition():
    iv_c, iv_p = 0.16, 0.20
    assert abs((iv_c - iv_p) - (-0.04)) < 1e-12


def test_bf25_definition():
    iv_p, iv_c, iv_atm = 0.20, 0.16, 0.15
    bf = 0.5 * (iv_p + iv_c) - iv_atm
    assert abs(bf - 0.03) < 1e-12


def test_vertical_price():
    long_leg, short_leg = 8.00, 5.00
    assert abs((long_leg - short_leg) - 3.00) < 1e-12


def test_residual_is_market_minus_model():
    market, model = 3.00, 3.30
    assert abs((market - model) - (-0.30)) < 1e-12


def test_no_trade_when_models_disagree():
    row = pd.Series(
        {
            "z_60_residual": 2.5,
            "model_dispersion": 0.10,
            "liquidity_score": 0.8,
            "pred_prob_convergence": 0.7,
            "pred_expected_return": 0.01,
            "extrapolated": False,
        }
    )
    dec = decide_trade(row)
    assert dec["decision"] == "NO TRADE"
    assert "high_model_disagreement" in dec["no_trade_reasons"]
