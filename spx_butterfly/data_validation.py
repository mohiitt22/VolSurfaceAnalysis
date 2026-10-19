"""Data validation and data quality checks for option surface data."""

from __future__ import annotations

import pandas as pd


class DataValidationError(Exception):
    """Raised when critical data validation fails."""
    pass


def validate_surface_data(df: pd.DataFrame) -> dict[str, list[str]]:
    """Validate normalized long-form option surface DataFrame.

    Expected columns:
    date, underlying, atm_strike, target_dte, option_side, strike, atm_offset, iv_decimal, premium

    Returns
    -------
    dict[str, list[str]]
        Dictionary with 'errors' and 'warnings'.
    """
    errors: list[str] = []
    warnings: list[str] = []

    required_cols = [
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
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")
        return {"errors": errors, "warnings": warnings}

    if df.empty:
        errors.append("Dataset is empty.")
        return {"errors": errors, "warnings": warnings}

    # Check nulls
    null_counts = df[required_cols].isna().sum()
    for col, count in null_counts.items():
        if count > 0:
            errors.append(f"Column '{col}' contains {count} null/missing values.")

    # Check non-positive underlying or strikes
    if (df["underlying"] <= 0).any():
        errors.append("Non-positive underlying prices found.")
    if (df["strike"] <= 0).any():
        errors.append("Non-positive strike prices found.")

    # Check IV bounds and conventions
    if (df["iv_decimal"] <= 0).any():
        errors.append("Non-positive implied volatilities found (IV <= 0).")

    # Convention check: decimal vs percentage
    max_iv = df["iv_decimal"].max()
    if max_iv > 2.0:
        warnings.append(
            f"Maximum IV ({max_iv:.2f}) exceeds 2.0 (200%). Verify if IV is stored in percentages rather than decimals."
        )

    # Check for duplicate strikes for the same date and option side
    dup_mask = df.duplicated(subset=["date", "option_side", "strike"], keep=False)
    if dup_mask.any():
        dup_count = dup_mask.sum()
        errors.append(
            f"Found {dup_count} duplicate records for same date, option side, and strike."
        )

    # Check ATM strike consistency per date
    atm_check = df.groupby("date")["atm_strike"].nunique()
    if (atm_check > 1).any():
        inconsistent_dates = atm_check[atm_check > 1].index.tolist()
        errors.append(
            f"Inconsistent ATM strikes found within single snapshot date for: {inconsistent_dates[:5]}"
        )

    # Check spot price consistency per date
    spot_check = df.groupby("date")["underlying"].nunique()
    if (spot_check > 1).any():
        inconsistent_spot = spot_check[spot_check > 1].index.tolist()
        errors.append(
            f"Inconsistent spot prices found within single snapshot date for: {inconsistent_spot[:5]}"
        )

    return {"errors": errors, "warnings": warnings}
