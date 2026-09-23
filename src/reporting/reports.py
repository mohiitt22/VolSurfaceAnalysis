"""Reports and plots.  Intermediate artefacts are written so the surface can be inspected."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config.settings import DEFAULT, OUTPUT_DIR, ResearchConfig


def write_data_quality_report(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def plot_surface_day(surface: pd.DataFrame, out_dir: Path, tag: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    usable = surface.loc[surface["usable"]]
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    ax = axes[0, 0]
    ax.scatter(usable["strike"], usable["market_iv"], s=18, label="market")
    if "fair_iv_svi" in usable:
        order = usable.sort_values("strike")
        ax.plot(order["strike"], order["fair_iv_svi"], label="SVI", lw=1.5)
        ax.plot(order["strike"], order["fair_iv_ensemble"], label="ensemble", lw=1.5)
        if "fair_iv_sabr" in order:
            ax.plot(order["strike"], order["fair_iv_sabr"], label="SABR", lw=1, ls="--")
    ax.set_title("IV vs strike")
    ax.set_xlabel("K")
    ax.set_ylabel("IV")
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    ax.scatter(usable["put_delta_abs"], usable["put_iv"], s=14, label="put IV")
    ax.scatter(usable["call_delta_abs"], usable["call_iv"], s=14, label="call IV")
    ax.set_title("IV vs |delta|")
    ax.legend(fontsize=8)

    ax = axes[1, 0]
    if "residual_ensemble" in usable:
        ax.axhline(0, color="k", lw=0.8)
        ax.scatter(usable["k"], usable["residual_ensemble"], c=usable["model_dispersion"], s=22)
        ax.set_title("Ensemble residual vs log-moneyness")
        ax.set_xlabel("k")
    ax = axes[1, 1]
    if "residual_svi" in usable:
        ax.axhline(0, color="k", lw=0.8)
        ax.scatter(usable["k"], usable["residual_svi"], s=18, label="SVI")
        ax.scatter(usable["k"], usable["residual_polynomial"], s=14, label="poly", alpha=0.7)
        ax.set_title("Model residuals")
        ax.legend(fontsize=8)
    fig.suptitle(tag)
    fig.tight_layout()
    fig.savefig(out_dir / f"{tag}_surface.png", dpi=120)
    plt.close(fig)


def plot_history(series: pd.Series, title: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(pd.to_datetime(series.index), series.values)
    ax.set_title(title)
    ax.axvline(pd.Timestamp(DEFAULT.train_end), color="C1", ls="--", label="train end")
    ax.axvline(pd.Timestamp(DEFAULT.test_date), color="C3", ls="--", label="test")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def write_markdown(path: Path, sections: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"# {sections[0][0]}\n\n{sections[0][1]}\n"]
    for title, body in sections[1:]:
        parts.append(f"## {title}\n\n{body}\n")
    path.write_text("\n".join(parts), encoding="utf-8")


def df_to_md(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_empty_"
    show = df.head(max_rows)
    try:
        return show.to_markdown(index=False)
    except Exception:
        return "```\n" + show.to_string(index=False) + "\n```"
