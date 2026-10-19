"""Data loading and transformation for SPX option chains.

Loads Excel/CSV datasets, extracts columns P-T (ATM-offset smile) alongside
Date, Underlying, ATM Strike, Target DTE, and transforms them into clean long-form data.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd

from src.data_validation import validate_surface_data


DEFAULT_FILE_NAME = "sticky_delta_2026-10-12_2025-06-05.xlsx"


def find_default_file() -> Path | None:
    """Search common locations for the default historical Excel file."""
    search_paths = [
        Path(DEFAULT_FILE_NAME),
        Path("data") / DEFAULT_FILE_NAME,
        Path("data") / "uploaded_excel_files" / DEFAULT_FILE_NAME,
        Path("..") / DEFAULT_FILE_NAME,
    ]
    for p in search_paths:
        if p.exists() and p.is_file():
            return p.resolve()
    return None


def _normalize_col_names(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace and unify column name representations."""
    rename_map = {}
    for col in df.columns:
        c_str = str(col).strip()
        c_lower = c_str.lower().replace("_", " ")
        if c_lower in ("date", "snapshot date"):
            rename_map[col] = "Date"
        elif c_lower in ("underlying", "spot", "spx", "spx spot"):
            rename_map[col] = "Underlying"
        elif c_lower in ("atm strike", "atm"):
            rename_map[col] = "ATM Strike"
        elif c_lower in ("target dte", "dte", "target maturity"):
            rename_map[col] = "Target DTE"
        elif c_lower in ("label 2", "label2", "atm offset label"):
            rename_map[col] = "Label 2"
        elif c_lower in ("side 2", "side2", "option type 2"):
            rename_map[col] = "Side 2"
        elif c_lower in ("strike 2", "strike2", "atm offset strike"):
            rename_map[col] = "Strike 2"
        elif c_lower in ("iv 2", "iv2", "atm offset iv"):
            rename_map[col] = "IV 2"
        elif c_lower in ("premium 2", "premium2", "atm offset premium"):
            rename_map[col] = "Premium 2"
        else:
            rename_map[col] = c_str
    return df.rename(columns=rename_map)


def load_raw_dataset(file_source: str | Path | io.BytesIO | bytes) -> pd.DataFrame:
    """Load raw table from Excel or CSV file source."""
    if isinstance(file_source, (str, Path)):
        p = Path(file_source)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_source}")
        if p.suffix.lower() in (".xlsx", ".xls"):
            return pd.read_excel(p, sheet_name=0)
        elif p.suffix.lower() == ".csv":
            return pd.read_csv(p)
        else:
            # Fallback attempt
            try:
                return pd.read_excel(p)
            except Exception:
                return pd.read_csv(p)
    else:
        # File buffer / BytesIO
        try:
            return pd.read_excel(file_source)
        except Exception:
            if hasattr(file_source, "seek"):
                file_source.seek(0)
            return pd.read_csv(file_source)


def transform_to_long_form(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Transform raw dataframe into clean long-form table.

    Produces:
    `date, underlying, atm_strike, target_dte, option_side, strike, atm_offset, iv_decimal, premium`

    Ensures both Call and Put rows exist for the ATM contract.
    """
    df = _normalize_col_names(raw_df.copy())

    required_raw_cols = [
        "Date",
        "Underlying",
        "ATM Strike",
        "Target DTE",
        "Side 2",
        "Strike 2",
        "IV 2",
        "Premium 2",
    ]
    missing = [c for c in required_raw_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"Dataset missing required columns P-T: {missing}. Available columns: {list(df.columns)}"
        )

    # Standardize types
    df["date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    df["underlying"] = df["Underlying"].astype(float)
    df["atm_strike"] = df["ATM Strike"].astype(float)
    df["target_dte"] = df["Target DTE"].astype(float)
    df["option_side"] = df["Side 2"].astype(str).str.strip().str.lower()
    df["strike"] = df["Strike 2"].astype(float)
    df["iv_decimal"] = df["IV 2"].astype(float)
    df["premium"] = df["Premium 2"].astype(float)
    df["atm_offset"] = df["strike"] - df["atm_strike"]

    clean_cols = [
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
    long_df = df[clean_cols].copy()

    # Drop any row where essential numerical columns are NaN
    long_df = long_df.dropna(subset=["date", "strike", "iv_decimal", "premium"])

    # Ensure separate Put ATM contracts exist:
    # If a snapshot has a Call ATM (atm_offset == 0 and option_side == 'call')
    # but lacks a Put ATM (atm_offset == 0 and option_side == 'put'), synthesize the Put ATM.
    synthesized_put_rows = []
    grouped = long_df.groupby("date")
    for date_val, group in grouped:
        has_call_atm = (
            (group["atm_offset"] == 0) & (group["option_side"] == "call")
        ).any()
        has_put_atm = (
            (group["atm_offset"] == 0) & (group["option_side"] == "put")
        ).any()

        if has_call_atm and not has_put_atm:
            atm_call_row = group[
                (group["atm_offset"] == 0) & (group["option_side"] == "call")
            ].iloc[0]
            put_atm_row = atm_call_row.copy()
            put_atm_row["option_side"] = "put"
            synthesized_put_rows.append(put_atm_row)

    if synthesized_put_rows:
        synth_df = pd.DataFrame(synthesized_put_rows)
        long_df = pd.concat([long_df, synth_df], ignore_index=True)

    # Sort deterministically
    long_df = long_df.sort_values(
        by=["date", "option_side", "strike"], ascending=[True, True, True]
    ).reset_index(drop=True)

    # Validate
    val_res = validate_surface_data(long_df)
    if val_res["errors"]:
        raise ValueError(f"Surface data validation failed: {val_res['errors']}")

    return long_df


def get_available_dates(long_df: pd.DataFrame) -> list[str]:
    """Return chronological list of available dates."""
    dates = long_df["date"].unique().tolist()
    return sorted(dates)


def get_snapshot(long_df: pd.DataFrame, selected_date: str) -> pd.DataFrame:
    """Return snapshot slice for a given date."""
    snapshot = long_df[long_df["date"] == selected_date].copy()
    if snapshot.empty:
        raise ValueError(f"No data available for date: {selected_date}")
    return snapshot.reset_index(drop=True)
