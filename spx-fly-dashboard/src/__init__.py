"""SPX Fixed-Strike Butterfly Volatility Analysis Package."""

from src.black_scholes import bs_price, bs_d1_d2
from src.greeks import calc_greeks
from src.data_loader import (
    load_raw_dataset,
    transform_to_long_form,
    get_available_dates,
    get_snapshot,
    find_default_file,
)
from src.data_validation import validate_surface_data
from src.fly_builder import (
    ButterflySpread,
    build_all_butterflies,
    build_butterflies_for_side,
    butterflies_to_dataframe,
)
from src.iv_scenarios import (
    IVShiftScenario,
    apply_iv_shift,
    validate_iv_shift,
    check_static_arbitrage,
    compute_normalized_strike,
    compute_level_shock,
    compute_skew_shock,
    compute_curvature_shock,
    compute_total_iv_shock,
    compute_strike_iv_shock,
    apply_iv_scenario,
)
from src.repricing import (
    RepricedButterfly,
    reprice_butterfly,
    reprice_all_butterflies,
    repriced_butterflies_to_dataframe,
)

__all__ = [
    "bs_price",
    "bs_d1_d2",
    "calc_greeks",
    "load_raw_dataset",
    "transform_to_long_form",
    "get_available_dates",
    "get_snapshot",
    "find_default_file",
    "validate_surface_data",
    "ButterflySpread",
    "build_all_butterflies",
    "build_butterflies_for_side",
    "butterflies_to_dataframe",
    "IVShiftScenario",
    "apply_iv_shift",
    "validate_iv_shift",
    "check_static_arbitrage",
    "compute_normalized_strike",
    "compute_level_shock",
    "compute_skew_shock",
    "compute_curvature_shock",
    "compute_total_iv_shock",
    "compute_strike_iv_shock",
    "apply_iv_scenario",
    "RepricedButterfly",
    "reprice_butterfly",
    "reprice_all_butterflies",
    "repriced_butterflies_to_dataframe",
]

