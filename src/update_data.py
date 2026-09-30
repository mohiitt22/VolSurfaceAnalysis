"""Process any unprocessed dates from 'SNP data' and append them to output datasets.

Ensures that dates after the frozen holdout (e.g. 2026-09-14 through 2026-09-22)
and any future parquet files added to 'SNP data' are automatically processed
and made available for analysis and the dashboard.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
import logging

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from config.settings import DEFAULT, OUTPUT_DIR, ResearchConfig
from src.data_loader.loader import list_available_dates
from src.pipeline import process_one_day, _save

LOGGER = logging.getLogger("update_data")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


def update_all_surfaces(cfg: ResearchConfig | None = None) -> list[date]:
    cfg = cfg or DEFAULT
    all_dates = list_available_dates()
    
    # Check existing processed dates
    struct_path = OUTPUT_DIR / "structures" / "structures.csv"
    existing_dates = set()
    if struct_path.exists():
        existing_df = pd.read_csv(struct_path, usecols=["trade_date"])
        existing_dates = set(pd.to_datetime(existing_df["trade_date"]).dt.date.unique())
    
    missing_dates = [d for d in all_dates if d not in existing_dates and d >= cfg.train_start]
    LOGGER.info("Total dates in SNP data: %d, already processed: %d, new to process: %d",
                len(all_dates), len(existing_dates), len(missing_dates))
    
    if not missing_dates:
        LOGGER.info("All dates already processed.")
        return []
    
    new_dte, new_clean, new_fit, new_surfaces, new_structures, new_grids = [], [], [], [], [], []
    prev_svi = None
    
    for i, d in enumerate(missing_dates):
        LOGGER.info("Processing %s (%d/%d)...", d, i + 1, len(missing_dates))
        day = process_one_day(d, cfg, prev_svi, reconstruct_iv=False)
        m = day["meta"]
        new_dte.append({
            "trade_date": d,
            "selected_expiry": m.selected_expiry,
            "actual_dte": m.actual_dte,
            "target_dte": m.target_dte,
            "dte_error": m.dte_error,
            "abs_dte_error": m.abs_dte_error,
            "n_candidate_expiries": m.n_candidate_expiries,
            "n_valid_strikes": m.n_valid_strikes,
            "exact_match": m.exact_match,
            "tie_broken": m.tie_broken,
            "contract": m.contract,
            "snapshot_time": day["snapshot_time"],
            "forward_source": day["assumptions"].forward_source,
            "put_delta_convention": day["assumptions"].put_delta_sign_convention,
        })
        new_clean.append(day["diag"].to_record())
        rec = {"trade_date": d, **{f"{k}_{kk}": vv for k, mtr in day["metrics"].items() if isinstance(mtr, dict) for kk, vv in mtr.items()}}
        rec.update({f"arb_{k}": v for k, v in day["arb"].items()})
        new_fit.append(rec)
        
        surf = day["surface"]
        surf["trade_date"] = d
        new_surfaces.append(surf)
        
        st = day["structures"]
        if not st.empty:
            new_structures.append(st)
            
        grid = day["delta_grid"]
        grid["trade_date"] = d
        new_grids.append(grid)
        
        if day["fits"].svi.success:
            prev_svi = day["fits"].svi.params()

    # Append to existing files
    def append_and_save(new_data, subdir, stem):
        csv_file = OUTPUT_DIR / subdir / f"{stem}.csv"
        parquet_file = OUTPUT_DIR / subdir / f"{stem}.parquet"
        new_df = pd.DataFrame(new_data) if isinstance(new_data, list) and not isinstance(new_data[0], pd.DataFrame) else pd.concat(new_data, ignore_index=True)
        if "trade_date" in new_df.columns:
            new_df["trade_date"] = pd.to_datetime(new_df["trade_date"]).dt.strftime("%Y-%m-%d")
        if csv_file.exists():
            old_df = pd.read_csv(csv_file)
            if "trade_date" in old_df.columns:
                old_df["trade_date"] = pd.to_datetime(old_df["trade_date"]).dt.strftime("%Y-%m-%d")
            combined = pd.concat([old_df, new_df], ignore_index=True)
        else:
            combined = new_df
        # Drop duplicates by trade_date + unique keys if applicable
        if "structure" in combined.columns:
            combined = combined.drop_duplicates(subset=["trade_date", "structure"])
        elif "strike" in combined.columns:
            combined = combined.drop_duplicates(subset=["trade_date", "strike"])
        else:
            combined = combined.drop_duplicates(subset=["trade_date"])
        
        combined.to_csv(csv_file, index=False)
        try:
            combined.to_parquet(parquet_file, index=False)
        except Exception:
            pass
        LOGGER.info("Saved %s with %d total rows", csv_file, len(combined))

    append_and_save(new_dte, "surfaces", "dte_selection")
    append_and_save(new_clean, "cleaned", "cleaning_diagnostics")
    append_and_save(new_fit, "models", "fit_metrics")
    append_and_save(new_surfaces, "residuals", "surface_residuals")
    append_and_save(new_structures, "structures", "structures")
    append_and_save(new_grids, "surfaces", "delta_grid")
    
    LOGGER.info("Successfully updated all datasets through %s", missing_dates[-1])
    return missing_dates


if __name__ == "__main__":
    update_all_surfaces()
