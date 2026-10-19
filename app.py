"""SPX Volatility Surface & Fixed-Strike Butterfly Analysis Dashboard.

Workspaces:
1. Multi-Date Surface Comparison (Multi-Date IV Smile, Level/Skew/Curvature Decomposition, Butterfly Curves)
2. Single-Date Volatility Lab (Single-Date Scenario Simulation, Level/Skew/Curvature Sliders, Greeks & Repricing)
"""

from __future__ import annotations

import io
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

from spx_butterfly.data_loader import (
    find_default_file,
    load_raw_dataset,
    transform_to_long_form,
    get_available_dates,
)
from spx_butterfly.multidate_view import render_multidate_workspace
from spx_butterfly.single_date_view import render_single_date_workspace
from spx_butterfly.consecutive_view import render_consecutive_workspace

# ---------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="SPX Volatility Surface & Butterfly Lab",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling (Dark Quantitative Research Look)
st.markdown(
    """
    <style>
    /* Dark quantitative theme overrides */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    /* Ensure Streamlit buttons never truncate or overlap words */
    div[data-testid="stButton"] button {
        font-size: 13px !important;
        font-weight: 500 !important;
        line-height: 1.3 !important;
        white-space: normal !important;
        word-break: break-word !important;
        min-height: 38px !important;
        padding: 6px 12px !important;
    }
    /* Ensure selectbox and radio labels never overlap */
    div[data-testid="stSelectbox"] label,
    div[data-testid="stRadio"] label {
        font-size: 12px !important;
        font-weight: 600 !important;
        color: #c9d1d9 !important;
        line-height: 1.3 !important;
        word-break: break-word !important;
    }
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
        min-width: 0;
        box-sizing: border-box;
        overflow: hidden;
    }
    .metric-card-title {
        font-size: 10.5px;
        font-weight: 600;
        text-transform: uppercase;
        color: #8b949e;
        letter-spacing: 0.5px;
        line-height: 1.3;
        word-break: break-word;
        overflow-wrap: break-word;
    }
    .metric-card-value {
        font-size: 16px;
        font-weight: 700;
        color: #f0f6fc;
        margin-top: 3px;
        line-height: 1.3;
        word-break: break-word;
        overflow-wrap: break-word;
    }
    .metric-card-sub {
        font-size: 11px;
        color: #58a6ff;
        margin-top: 2px;
        line-height: 1.3;
        word-break: break-word;
        overflow-wrap: break-word;
    }
    .fixed-badge {
        display: inline-block;
        background-color: rgba(56, 139, 253, 0.15);
        color: #58a6ff;
        border: 1px solid rgba(56, 139, 253, 0.4);
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 500;
        margin-bottom: 4px;
    }
    .invariant-badge {
        display: inline-block;
        background-color: rgba(63, 185, 80, 0.15);
        color: #3fb950;
        border: 1px solid rgba(63, 185, 80, 0.4);
        padding: 6px 14px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 600;
        margin: 8px 0;
    }
    div[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Cached Data Ingestion
# ---------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_and_prepare_data(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """Read and transform Excel/CSV dataset into cached long-form table."""
    buf = io.BytesIO(file_bytes)
    raw = load_raw_dataset(buf)
    return transform_to_long_form(raw)


# ---------------------------------------------------------
# Sidebar File Loader & Workspace Navigation
# ---------------------------------------------------------
st.sidebar.markdown("### 🗂️ Workspace Navigation")

WORKSPACE_OPTIONS = [
    "Multi-Date Surface Comparison",
    "Single-Date Volatility Lab",
    "Consecutive Date Analysis",
]

def _on_radio_workspace_change():
    st.session_state.active_workspace = st.session_state.ws_radio_choice

def _set_workspace(target_ws: str):
    st.session_state.active_workspace = target_ws
    st.session_state.ws_radio_choice = target_ws

if "active_workspace" not in st.session_state or st.session_state.active_workspace not in WORKSPACE_OPTIONS:
    st.session_state.active_workspace = "Multi-Date Surface Comparison"

if "ws_radio_choice" not in st.session_state or st.session_state.ws_radio_choice not in WORKSPACE_OPTIONS:
    st.session_state.ws_radio_choice = st.session_state.active_workspace

active_workspace = st.sidebar.radio(
    "Active Workspace:",
    options=WORKSPACE_OPTIONS,
    index=WORKSPACE_OPTIONS.index(st.session_state.active_workspace),
    key="ws_radio_choice",
    on_change=_on_radio_workspace_change,
    help="Switch between Multi-Date Comparison, Single-Date Volatility Lab, and Consecutive Date Analysis.",
)
st.session_state.active_workspace = st.session_state.ws_radio_choice

st.sidebar.markdown("---")
st.sidebar.markdown("### 📁 Data Source")

default_path = find_default_file()
uploaded_file = st.sidebar.file_uploader(
    "Upload Option Chain (.xlsx, .xls, .csv)",
    type=["xlsx", "xls", "csv"],
    help="Defaults to sticky_delta_2026-10-12_2025-06-05.xlsx if not provided.",
)

file_bytes: bytes | None = None
file_name: str = ""

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    file_name = uploaded_file.name
    st.sidebar.success(f"Loaded: `{file_name}`")
elif default_path is not None and default_path.exists():
    file_bytes = default_path.read_bytes()
    file_name = default_path.name
    st.sidebar.info(f"Using default: `{file_name}`")
else:
    st.error("No historical Excel dataset found. Please upload an option chain file.")
    st.stop()

# Ingest and cache long-form table
try:
    with st.spinner("Preparing historical smile surface..."):
        long_df = load_and_prepare_data(file_bytes, file_name)
except Exception as e:
    st.error(f"Error parsing data file: {e}")
    st.stop()

# Available Snapshot Dates
available_dates = get_available_dates(long_df)
if not available_dates:
    st.error("No valid dates found in dataset.")
    st.stop()

# ---------------------------------------------------------
# Top Navigation Bar (Tabs)
# ---------------------------------------------------------
top_col1, top_col2, top_col3 = st.columns(3)
cur_ws = st.session_state.active_workspace

top_col1.button(
    "📈 Multi-Date Surface Comparison",
    type="primary" if cur_ws == "Multi-Date Surface Comparison" else "secondary",
    use_container_width=True,
    help="Compare IV smiles, butterfly curves, and Level/Skew/Curvature across multiple historical dates.",
    on_click=_set_workspace,
    args=("Multi-Date Surface Comparison",),
)

top_col2.button(
    "🦅 Single-Date Volatility Lab",
    type="primary" if cur_ws == "Single-Date Volatility Lab" else "secondary",
    use_container_width=True,
    help="Simulate Level, Skew, and Curvature perturbations on a single date with Black-Scholes repricing.",
    on_click=_set_workspace,
    args=("Single-Date Volatility Lab",),
)

top_col3.button(
    "📅 Consecutive Date Analysis",
    type="primary" if cur_ws == "Consecutive Date Analysis" else "secondary",
    use_container_width=True,
    help="Detailed two-date manual comparison of Individual Strike IVs, Fly IV Curvature, and Fly Net Premiums.",
    on_click=_set_workspace,
    args=("Consecutive Date Analysis",),
)

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# Render Active Workspace
# ---------------------------------------------------------
if st.session_state.active_workspace == "Multi-Date Surface Comparison":
    render_multidate_workspace(long_df, available_dates)
elif st.session_state.active_workspace == "Consecutive Date Analysis":
    render_consecutive_workspace(long_df, available_dates)
else:
    render_single_date_workspace(long_df, available_dates)
