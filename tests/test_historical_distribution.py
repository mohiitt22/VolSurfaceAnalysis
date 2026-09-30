from datetime import date
import pandas as pd
import numpy as np
import pytest

from src.analysis.historical_distribution import compute_causal_distribution_series


def test_causal_distribution_zero_lookahead():
    # Synthetic dataset with 5 dates
    data = [
        {"trade_date": "2026-08-01", "structure": "RR_25D", "market_value": -0.060},
        {"trade_date": "2026-08-02", "structure": "RR_25D", "market_value": -0.050},
        {"trade_date": "2026-08-03", "structure": "RR_25D", "market_value": -0.040},
        {"trade_date": "2026-08-04", "structure": "RR_25D", "market_value": -0.030},
        {"trade_date": "2026-08-05", "structure": "RR_25D", "market_value": -0.020},
    ]
    df = pd.DataFrame(data)
    
    # Run with min_prior_obs=3
    res = compute_causal_distribution_series(df, structure="RR_25D", value_col="market_value", min_prior_obs=3)
    
    # Day 4 (2026-08-04) should strictly compare against Day 1, 2, 3: [-0.060, -0.050, -0.040]
    row4 = res[res["trade_date"] == "2026-08-04"].iloc[0]
    assert row4["n_prior"] == 3
    assert row4["prior_start"] == "2026-08-01"
    assert row4["prior_end"] == "2026-08-03"
    
    expected_mean = (-0.060 - 0.050 - 0.040) / 3  # -0.050
    expected_std = np.std([-0.060, -0.050, -0.040], ddof=1)  # 0.010
    expected_z = (-0.030 - expected_mean) / expected_std  # 2.0
    expected_pct = 100.0  # -0.030 > all prior
    
    assert pytest.approx(row4["mean_prior"], abs=1e-6) == expected_mean
    assert pytest.approx(row4["std_prior"], abs=1e-6) == expected_std
    assert pytest.approx(row4["z_score"], abs=1e-6) == expected_z
    assert pytest.approx(row4["percentile_rank"], abs=1e-6) == expected_pct
