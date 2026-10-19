"""Generate the standalone, fully interactive SPX Volatility Surface & Butterfly Lab HTML page.

Embeds precalculated JSON data, Plotly.js charts, interactive client-side vanilla JavaScript,
rich GitHub/Bloomberg terminal styling, live Black-Scholes pricing engine, and math guide.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

workspace_dir = Path(__file__).resolve().parent.parent
json_path = workspace_dir / "spx_precalculated_data.json"

if not json_path.exists():
    print("Error: spx_precalculated_data.json does not exist. Run build_json_payload.py first.")
    sys.exit(1)

print("Reading spx_precalculated_data.json...")
with open(json_path, "r", encoding="utf-8") as f:
    json_data = f.read()

print(f"Loaded JSON: {len(json_data) / 1024:.1f} KB")

html_template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SPX Volatility Surface & Butterfly Lab | Standalone Quant Workspace</title>
  
  <!-- Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  
  <!-- Plotly.js CDN with fallback -->
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>

  <style>
    :root {
      --bg-canvas: #090d16;
      --bg-card: #131823;
      --bg-card-hover: #182030;
      --bg-surface: #1a2234;
      --border-subtle: #232d42;
      --border-strong: #32415d;
      --text-main: #f0f6fc;
      --text-muted: #8b949e;
      --text-dim: #606b7d;
      
      --accent-cyan: #38bdf8;
      --accent-blue: #388bfd;
      --accent-orange: #d29922;
      --accent-green: #3fb950;
      --accent-red: #f85149;
      --accent-purple: #bc8cff;
      --accent-glow: rgba(56, 189, 248, 0.18);
      
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg-canvas);
      color: var(--text-main);
      font-family: var(--font-sans);
      line-height: 1.5;
      font-size: 14px;
      overflow-x: hidden;
    }

    /* Scrollbar */
    ::-webkit-scrollbar {
      width: 8px;
      height: 8px;
    }
    ::-webkit-scrollbar-track {
      background: var(--bg-canvas);
    }
    ::-webkit-scrollbar-thumb {
      background: var(--border-strong);
      border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: var(--accent-blue);
    }

    /* Header */
    header {
      background: linear-gradient(180deg, #101624 0%, var(--bg-canvas) 100%);
      border-bottom: 1px solid var(--border-subtle);
      padding: 18px 28px;
      position: sticky;
      top: 0;
      z-index: 100;
      backdrop-filter: blur(12px);
    }

    .header-content {
      max-width: 1720px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }

    .brand-title {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-logo {
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #388bfd 0%, #38bdf8 100%);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 0 16px rgba(56, 189, 248, 0.4);
      font-weight: 800;
      font-size: 18px;
      color: #0d1117;
    }

    .brand-text h1 {
      font-size: 19px;
      font-weight: 700;
      letter-spacing: -0.3px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .brand-text p {
      font-size: 12px;
      color: var(--text-muted);
    }

    .badge-pill {
      font-size: 11px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 12px;
      background: rgba(56, 189, 248, 0.12);
      color: var(--accent-cyan);
      border: 1px solid rgba(56, 189, 248, 0.3);
      letter-spacing: 0.3px;
    }

    /* Tabs */
    .tab-nav {
      display: flex;
      gap: 6px;
      background: var(--bg-card);
      padding: 4px;
      border-radius: 10px;
      border: 1px solid var(--border-subtle);
    }

    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s ease;
    }

    .tab-btn:hover {
      color: var(--text-main);
      background: rgba(255, 255, 255, 0.04);
    }

    .tab-btn.active {
      background: var(--accent-blue);
      color: #ffffff;
      box-shadow: 0 2px 8px rgba(56, 139, 253, 0.35);
    }

    /* Main Container */
    main {
      max-width: 1720px;
      margin: 0 auto;
      padding: 24px 28px 60px;
    }

    .tab-pane {
      display: none;
      animation: fadeIn 0.25s ease-in-out;
    }

    .tab-pane.active {
      display: block;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Control Panel Box */
    .controls-panel {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 20px 24px;
      margin-bottom: 24px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }

    .preset-toolbar {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 18px;
      flex-wrap: wrap;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--border-subtle);
    }

    .toolbar-label {
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      margin-right: 4px;
    }

    .btn-preset {
      background: var(--bg-surface);
      border: 1px solid var(--border-strong);
      color: var(--text-main);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }

    .btn-preset:hover {
      background: var(--bg-card-hover);
      border-color: var(--accent-cyan);
      color: var(--accent-cyan);
    }

    .btn-preset.active {
      background: rgba(56, 189, 248, 0.15);
      border-color: var(--accent-cyan);
      color: var(--accent-cyan);
      font-weight: 600;
    }

    .controls-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      align-items: flex-end;
    }

    .form-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .form-group label {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
    }

    .form-select, .form-input {
      background: var(--bg-canvas);
      border: 1px solid var(--border-strong);
      color: var(--text-main);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 13px;
      font-family: var(--font-sans);
      outline: none;
      transition: border-color 0.2s ease;
    }

    .form-select:focus, .form-input:focus {
      border-color: var(--accent-blue);
      box-shadow: 0 0 0 2px rgba(56, 139, 253, 0.25);
    }

    .toggle-group {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--border-subtle);
    }

    .toggle-item {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: var(--text-main);
      cursor: pointer;
      user-select: none;
    }

    .toggle-item input[type="checkbox"] {
      appearance: none;
      width: 16px;
      height: 16px;
      background: var(--bg-canvas);
      border: 1px solid var(--border-strong);
      border-radius: 4px;
      cursor: pointer;
      position: relative;
    }

    .toggle-item input[type="checkbox"]:checked {
      background: var(--accent-blue);
      border-color: var(--accent-blue);
    }

    .toggle-item input[type="checkbox"]:checked::after {
      content: "✓";
      position: absolute;
      color: #fff;
      font-size: 11px;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
    }

    /* KPI Cards */
    .kpi-row {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }

    .kpi-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 16px 20px;
      position: relative;
      overflow: hidden;
      transition: transform 0.2s ease, border-color 0.2s ease;
    }

    .kpi-card:hover {
      border-color: var(--border-strong);
      transform: translateY(-2px);
    }

    .kpi-card::before {
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: var(--card-accent, var(--border-subtle));
    }

    .kpi-card.cyan { --card-accent: var(--accent-cyan); }
    .kpi-card.orange { --card-accent: var(--accent-orange); }
    .kpi-card.green { --card-accent: var(--accent-green); }
    .kpi-card.purple { --card-accent: var(--accent-purple); }
    .kpi-card.red { --card-accent: var(--accent-red); }

    .kpi-title {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: var(--text-muted);
      margin-bottom: 6px;
    }

    .kpi-value {
      font-size: 24px;
      font-weight: 700;
      font-family: var(--font-mono);
      color: var(--text-main);
      letter-spacing: -0.5px;
    }

    .kpi-sub {
      font-size: 11px;
      color: var(--text-dim);
      margin-top: 4px;
    }

    /* Chart Containers */
    .chart-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }

    .chart-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      flex-wrap: wrap;
      gap: 10px;
    }

    .chart-title {
      font-size: 16px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .chart-desc {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 2px;
    }

    .chart-box {
      width: 100%;
      min-height: 480px;
    }

    .chart-box-compact {
      width: 100%;
      min-height: 380px;
    }

    .chart-grid-2 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(580px, 1fr));
      gap: 20px;
    }

    /* Table Styles */
    .table-container {
      overflow-x: auto;
      max-height: 420px;
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      background: var(--bg-canvas);
    }

    table.quant-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      font-family: var(--font-mono);
      text-align: right;
    }

    table.quant-table th, table.quant-table td {
      padding: 10px 14px;
      border-bottom: 1px solid var(--border-subtle);
      white-space: nowrap;
    }

    table.quant-table th {
      background: var(--bg-surface);
      color: var(--text-muted);
      font-weight: 600;
      position: sticky;
      top: 0;
      z-index: 10;
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
    }

    table.quant-table th:first-child, table.quant-table td:first-child {
      text-align: left;
    }

    table.quant-table tr:hover {
      background: rgba(255, 255, 255, 0.03);
    }

    .tag-pos {
      color: var(--accent-green);
      font-weight: 600;
    }

    .tag-neg {
      color: var(--accent-red);
      font-weight: 600;
    }

    .tag-badge {
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: 600;
    }
    .badge-atm { background: rgba(56, 189, 248, 0.15); color: var(--accent-cyan); }
    .badge-call { background: rgba(63, 185, 80, 0.15); color: var(--accent-green); }
    .badge-put { background: rgba(248, 81, 73, 0.15); color: var(--accent-red); }

    /* Single Date Slider Lab */
    .slider-box {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 14px 18px;
      margin-bottom: 12px;
    }

    .slider-header {
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 8px;
    }

    .slider-val {
      font-family: var(--font-mono);
      color: var(--accent-cyan);
    }

    input[type=range] {
      width: 100%;
      height: 6px;
      border-radius: 3px;
      background: var(--border-strong);
      outline: none;
      -webkit-appearance: none;
    }

    input[type=range]::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: var(--accent-blue);
      cursor: pointer;
      box-shadow: 0 0 8px rgba(56, 139, 253, 0.6);
      transition: transform 0.1s;
    }

    input[type=range]::-webkit-slider-thumb:hover {
      transform: scale(1.2);
    }

    /* Math Card */
    .math-card {
      background: var(--bg-card);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      padding: 28px;
      margin-bottom: 24px;
      line-height: 1.7;
    }

    .math-card h2 {
      font-size: 20px;
      margin-bottom: 16px;
      color: var(--accent-cyan);
    }

    .math-card h3 {
      font-size: 16px;
      margin: 24px 0 10px;
      color: var(--text-main);
      border-bottom: 1px solid var(--border-subtle);
      padding-bottom: 6px;
    }

    .formula-block {
      background: var(--bg-canvas);
      border-left: 3px solid var(--accent-cyan);
      padding: 14px 18px;
      margin: 14px 0;
      font-family: var(--font-mono);
      font-size: 13px;
      color: #e6edf3;
      overflow-x: auto;
      border-radius: 0 6px 6px 0;
    }

    /* Footer */
    footer {
      text-align: center;
      padding: 24px;
      color: var(--text-dim);
      font-size: 12px;
      border-top: 1px solid var(--border-subtle);
      margin-top: 40px;
    }
  </style>
</head>
<body>

  <!-- Top Header -->
  <header>
    <div class="header-content">
      <div class="brand-title">
        <div class="brand-logo">SPX</div>
        <div class="brand-text">
          <h1>SPX Volatility Surface & Butterfly Lab <span class="badge-pill">STANDALONE QUANT SUITE</span></h1>
          <p>Precalculated Multi-Date Volatility Surfaces, Factor Attributions & Black-Scholes Repricing Engine</p>
        </div>
      </div>
      
      <!-- Tab Navigation Buttons -->
      <div class="tab-nav">
        <button class="tab-btn active" onclick="switchTab('tab-multidate')">
          <span>📈</span> Multi-Date Comparison
        </button>
        <button class="tab-btn" onclick="switchTab('tab-consecutive')">
          <span>📅</span> Consecutive Day Analysis
        </button>
        <button class="tab-btn" onclick="switchTab('tab-singledate')">
          <span>🔬</span> Single-Date Live Lab
        </button>
        <button class="tab-btn" onclick="switchTab('tab-math')">
          <span>📜</span> Mathematical Guide
        </button>
      </div>
    </div>
  </header>

  <main>
    <!-- TAB 1: MULTI-DATE COMPARISON -->
    <div id="tab-multidate" class="tab-pane active">
      
      <!-- Controls Panel -->
      <div class="controls-panel">
        
        <!-- Preset Toolbar -->
        <div class="preset-toolbar">
          <span class="toolbar-label">Quick Presets:</span>
          <button class="btn-preset active" id="btn-p-bench" onclick="applyPreset('benchmark')">
            🎯 Aug 3 & Aug 4 (Benchmark Pair)
          </button>
          <button class="btn-preset" id="btn-p-week" onclick="applyPreset('aug_week')">
            📅 Aug 3 – Aug 7 (Benchmark Week)
          </button>
          <button class="btn-preset" id="btn-p-aug" onclick="applyPreset('aug_month')">
            📊 August 2026 (All 20 Days)
          </button>
          <button class="btn-preset" id="btn-p-recent" onclick="applyPreset('recent5')">
            ⚡ Latest 5 Days (Oct 2026)
          </button>
          <button class="btn-preset" onclick="stepFocusDay(-1)">
            ◀ Prev Focus Day
          </button>
          <button class="btn-preset" onclick="stepFocusDay(1)">
            Next Focus Day ▶
          </button>
        </div>

        <!-- Controls Grid -->
        <div class="controls-grid">
          
          <div class="form-group">
            <label for="sel-ref-date">Benchmark Reference Date (Basis):</label>
            <select id="sel-ref-date" class="form-select" onchange="onDateSelectionChanged()">
              <!-- Injected by JS -->
            </select>
          </div>

          <div class="form-group">
            <label for="sel-focus-date">Focus Target Date:</label>
            <select id="sel-focus-date" class="form-select" onchange="onDateSelectionChanged()">
              <!-- Injected by JS -->
            </select>
          </div>

          <div class="form-group">
            <label for="sel-align-mode">Strike Alignment Axis:</label>
            <select id="sel-align-mode" class="form-select" onchange="renderAllCharts()">
              <option value="offset" selected>ATM-Relative Offset (K − ATM)</option>
              <option value="absolute">Absolute Strike Price (K)</option>
            </select>
          </div>

          <div class="form-group">
            <label for="sel-ref-width">Reference Half-Width (H):</label>
            <select id="sel-ref-width" class="form-select" onchange="onDateSelectionChanged()">
              <option value="300">H = 300 pts (±0.04-0.05 Delta)</option>
              <option value="500" selected>H = 500 pts (±0.08 Delta)</option>
              <option value="700">H = 700 pts (±0.11 Delta)</option>
            </select>
          </div>

        </div>

        <!-- Toggles -->
        <div class="toggle-group">
          <label class="toggle-item">
            <input type="checkbox" id="chk-bridge" checked onchange="renderAllCharts()">
            <span>Show 5-Stage Smile Transformation Bridge (IV<sub>0</sub> → IV<sub>L</sub> → IV<sub>LS</sub> → IV<sub>LSC</sub> → Actual)</span>
          </label>
          <label class="toggle-item">
            <input type="checkbox" id="chk-spikes" checked onchange="renderAllCharts()">
            <span>Show Interactive Crosshair Hover Spikes</span>
          </label>
          <label class="toggle-item">
            <input type="checkbox" id="chk-grid100" checked onchange="renderAllCharts()">
            <span>100-pt Strike Gridlines</span>
          </label>
        </div>

      </div>

      <!-- KPI Summary Cards -->
      <div class="kpi-row">
        
        <div class="kpi-card cyan">
          <div class="kpi-title">Reference ATM IV</div>
          <div class="kpi-value" id="kpi-ref-iv">15.421%</div>
          <div class="kpi-sub" id="kpi-ref-sub">Basis: 2026-08-03 (SPX: 6380)</div>
        </div>

        <div class="kpi-card cyan">
          <div class="kpi-title">Focus ATM IV</div>
          <div class="kpi-value" id="kpi-focus-iv">16.029%</div>
          <div class="kpi-sub" id="kpi-focus-sub">Target: 2026-08-04 (SPX: 6420)</div>
        </div>

        <div class="kpi-card green" id="card-delta-level">
          <div class="kpi-title">Δ Level (L)</div>
          <div class="kpi-value" id="kpi-delta-level">+0.6082 pts</div>
          <div class="kpi-sub">Parallel ATM Volatility Shift</div>
        </div>

        <div class="kpi-card green" id="card-delta-skew">
          <div class="kpi-title">Δ Skew (S)</div>
          <div class="kpi-value" id="kpi-delta-skew">+1.0832 pts</div>
          <div class="kpi-sub">IV(ATM+H) − IV(ATM−H) Slope</div>
        </div>

        <div class="kpi-card red" id="card-delta-curv">
          <div class="kpi-title">Δ Curvature (C)</div>
          <div class="kpi-value" id="kpi-delta-curv">-0.0202 pts</div>
          <div class="kpi-sub">Wing Midpoint Rel to ATM Convexity</div>
        </div>

        <div class="kpi-card purple">
          <div class="kpi-title">Residual RMSE</div>
          <div class="kpi-value" id="kpi-rmse">0.0632 pts</div>
          <div class="kpi-sub" id="kpi-nodes-sub">19 Aligned Strike Nodes</div>
        </div>

      </div>

      <!-- Chart 1: Multi-Date IV Smile Comparison -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <div class="chart-title">📈 1. Historical Implied Volatility Smile Comparison & Factor Bridge</div>
            <div class="chart-desc">
              Visualizes cross-date IV smiles with prominent focus/reference highlights, 100-pt strike grid, and step-by-step transformation stages.
            </div>
          </div>
          <div style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">
            Focus: <span style="color: var(--accent-cyan); font-weight: 700;">Cyan 4.2px</span> | 
            Ref: <span style="color: var(--accent-orange); font-weight: 700;">Orange 3.2px</span> | 
            Grid: <span style="color: var(--text-muted);">dtick=100</span>
          </div>
        </div>
        <div id="chart-iv-smile" class="chart-box"></div>
      </div>

      <!-- Companion Chart: IV Attribution -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <div class="chart-title">📊 2. IV Smile Change Sequential Factor Decomposition</div>
            <div class="chart-desc">
              Strike-by-strike attribution of total observed IV change into Level (green), Skew (purple), Curvature (orange), and Local Residual (red).
            </div>
          </div>
        </div>
        <div id="chart-iv-attribution" class="chart-box-compact"></div>
      </div>

      <!-- Strike-by-Strike Comparative Matrix Table -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <div class="chart-title">📋 3. Cross-Sectional Strike-by-Strike Comparative Matrix</div>
            <div class="chart-desc">
              Detailed inspection of IV quotes across selected historical dates and cross-date spread (Focus − Reference).
            </div>
          </div>
          <div>
            <input type="text" id="tbl-search" class="form-input" placeholder="Filter strike or side..." oninput="filterMatrixTable()" style="width: 200px;">
          </div>
        </div>
        <div class="table-container">
          <table class="quant-table" id="matrix-table">
            <thead>
              <tr id="matrix-table-head">
                <!-- Injected by JS -->
              </tr>
            </thead>
            <tbody id="matrix-table-body">
              <!-- Injected by JS -->
            </tbody>
          </table>
        </div>
      </div>

      <!-- Dual Chart: Butterfly Premium Curves -->
      <div class="chart-grid-2">
        
        <div class="chart-card">
          <div class="chart-header">
            <div>
              <div class="chart-title">🦋 4A. OTM Call Butterfly Curves (100-pt Wings)</div>
              <div class="chart-desc">Net debit premium for Call Flies where K<sub>centre</sub> ≥ ATM Strike</div>
            </div>
          </div>
          <div id="chart-call-flies" class="chart-box-compact"></div>
        </div>

        <div class="chart-card">
          <div class="chart-header">
            <div>
              <div class="chart-title">🦋 4B. OTM Put Butterfly Curves (100-pt Wings)</div>
              <div class="chart-desc">Net debit premium for Put Flies where K<sub>centre</sub> ≤ ATM Strike</div>
            </div>
          </div>
          <div id="chart-put-flies" class="chart-box-compact"></div>
        </div>

      </div>

      <!-- Chart 5: Observed Fly Differences -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <div class="chart-title">⚖️ 5. Observed Butterfly Premium Differences (Focus − Reference)</div>
            <div class="chart-desc">
              Observed change in market fly quotes across strikes. (Note: reflect underlying SPX drift + skew shifts).
            </div>
          </div>
        </div>
        <div id="chart-fly-diffs" class="chart-box-compact"></div>
      </div>

      <!-- Chart 6: Fixed-Reference IV-Only Repricing Attribution -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <div class="chart-title">🔬 6. Fixed-Reference IV-Only Factor Attribution (Clean Volatility P&amp;L)</div>
            <div class="chart-desc">
              Isolates pure volatility dynamics on fixed reference strikes holding S<sub>0</sub>, DTE, and wings constant.
            </div>
          </div>
        </div>
        <div id="chart-fixed-attr" class="chart-box-compact"></div>
      </div>

      <!-- Chart 7: Historical Factor Trends -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <div class="chart-title">⏳ 7. Historical Smile Factor Evolution Across All 338 Trading Sessions</div>
            <div class="chart-desc">
              Time series evolution of ATM Level (IV), Skew (slope), and Curvature (convexity) from June 2025 to October 2026.
            </div>
          </div>
        </div>
        <div id="chart-factor-history" class="chart-box"></div>
      </div>

    </div>

    <!-- TAB 4: CONSECUTIVE DAY ANALYSIS -->
    <div id="tab-consecutive" class="tab-pane">
      
      <!-- Controls Panel -->
      <div class="controls-panel">
        <div class="preset-toolbar">
          <span class="toolbar-label">Consecutive Presets:</span>
          <button class="btn-preset active" id="btn-cp-bench" onclick="applyConsecPreset('2026-08-03', '2026-08-04')">
            🎯 Aug 3 → Aug 4 (Benchmark)
          </button>
          <button class="btn-preset" onclick="applyConsecPreset('2026-08-04', '2026-08-05')">
            Aug 4 → Aug 5
          </button>
          <button class="btn-preset" onclick="applyConsecPreset('2026-08-05', '2026-08-06')">
            Aug 5 → Aug 6
          </button>
          <button class="btn-preset" onclick="applyConsecPreset('2026-08-06', '2026-08-07')">
            Aug 6 → Aug 7
          </button>
          <button class="btn-preset" onclick="stepConsecPair(-1)">
            ◀ Prev Pair (T−1, T)
          </button>
          <button class="btn-preset" onclick="stepConsecPair(1)">
            Next Pair (T+1, T+2) ▶
          </button>
        </div>

        <div class="controls-grid">
          <div class="form-group">
            <label for="sel-consec-d1">Date 1 (Day T):</label>
            <select id="sel-consec-d1" class="form-select" onchange="onConsecDate1Changed()">
            </select>
          </div>

          <div class="form-group">
            <label for="sel-consec-d2">Date 2 (Day T+1):</label>
            <select id="sel-consec-d2" class="form-select" onchange="onConsecSelectionChanged()">
            </select>
          </div>

          <div class="form-group">
            <label for="sel-consec-align">Strike Alignment Axis:</label>
            <select id="sel-consec-align" class="form-select" onchange="renderConsecutiveWorkspace()">
              <option value="offset" selected>ATM-Relative Offset (K − ATM)</option>
              <option value="absolute">Absolute Strike Price (K)</option>
            </select>
          </div>
        </div>
      </div>

      <!-- KPI Row -->
      <div class="kpi-row">
        <div class="kpi-card cyan">
          <div class="kpi-title">Day T ATM IV</div>
          <div class="kpi-value" id="kpi-c-d1-iv">15.421%</div>
          <div class="kpi-sub" id="kpi-c-d1-sub">SPX: 6380 | ATM: 7230</div>
        </div>
        <div class="kpi-card cyan">
          <div class="kpi-title">Day T+1 ATM IV</div>
          <div class="kpi-value" id="kpi-c-d2-iv">16.029%</div>
          <div class="kpi-sub" id="kpi-c-d2-sub">SPX: 6420 | ATM: 7375</div>
        </div>
        <div class="kpi-card green" id="card-c-spot">
          <div class="kpi-title">Δ SPX Spot</div>
          <div class="kpi-value" id="kpi-c-spot">+40.0 pts</div>
          <div class="kpi-sub">+0.63% Market Drift</div>
        </div>
        <div class="kpi-card green" id="card-c-level">
          <div class="kpi-title">Δ Level (L)</div>
          <div class="kpi-value" id="kpi-c-level">+0.6082 pts</div>
          <div class="kpi-sub">ATM Shift</div>
        </div>
        <div class="kpi-card green" id="card-c-skew">
          <div class="kpi-title">Δ Skew (S)</div>
          <div class="kpi-value" id="kpi-c-skew">+1.0832 pts</div>
          <div class="kpi-sub">Slope Twist</div>
        </div>
        <div class="kpi-card purple" id="card-c-curv">
          <div class="kpi-title">Δ Curvature (C)</div>
          <div class="kpi-value" id="kpi-c-curv">-0.0202 pts</div>
          <div class="kpi-sub">Convexity Bend</div>
        </div>
        <div class="kpi-card cyan" id="card-c-callput-skew">
          <div class="kpi-title">25Δ Call &amp; Put Skew (300-pt)</div>
          <div class="kpi-value" id="kpi-c-callput-skew">Call: -1.12 | Put: +2.38</div>
          <div class="kpi-sub" id="kpi-c-callput-sub">Δ Call: +0.48 | Δ Put: -0.46</div>
        </div>
        <div class="kpi-card green" id="card-c-rr">
          <div class="kpi-title">25Δ Skew (Risk Reversal)</div>
          <div class="kpi-value" id="kpi-c-rr">-3.501 pts</div>
          <div class="kpi-sub" id="kpi-c-rr-sub">Shift: +0.935 pts (Flattening)</div>
        </div>
        <div class="kpi-card purple" id="card-c-kurt">
          <div class="kpi-title">Curvature &amp; Quartic Kurtosis (a₄)</div>
          <div class="kpi-value" id="kpi-c-kurt">+0.630 pts | a₄: -0.127</div>
          <div class="kpi-sub" id="kpi-c-kurt-sub">Δ Curv: +0.010 pts | Δ a₄: -0.035</div>
        </div>
      </div>

      <!-- Chart 1: Strike IV & Fly IV -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <div class="chart-title">📈 1. Implied Volatility Smiles &amp; Fly IV Curvature Across Strikes</div>
            <div class="chart-desc">
              Top: Individual Strike IV (%) for Day T vs Day T+1. Bottom: Fly IV Curvature ($IV_{low} - 2IV_{mid} + IV_{upp}$) in vol points.
            </div>
          </div>
        </div>
        <div id="chart-c-iv-fly" class="chart-box" style="min-height: 560px;"></div>
      </div>

      <!-- Chart 2: Fly Premium & Daily Shift -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <div class="chart-title">🦋 2. 100-pt Butterfly Premium Curves &amp; Daily Price Shifts</div>
            <div class="chart-desc">
              Top: Net debit premium ($) for 100-pt butterflies across strikes. Bottom: Observed daily price change ($\Delta F = F_{T+1} - F_T$) ($/fly).
            </div>
          </div>
        </div>
        <div id="chart-c-fly-prem" class="chart-box" style="min-height: 560px;"></div>
      </div>

      <!-- Chart 3: Call/Put Skew & Risk Reversal -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <div class="chart-title">⚖️ 3. Call Skew, Put Skew &amp; Risk Reversal Dynamics ($IV_{Call} - IV_{Put}$)</div>
            <div class="chart-desc">
              Call Skew, Put Skew relative to ATM ($IV - IV_{ATM}$) and Skew / Risk Reversal ($IV_{Call} - IV_{Put}$) with daily shift bars ($\Delta RR$).
            </div>
          </div>
        </div>
        <div id="chart-c-skew-rr" class="chart-box" style="min-height: 560px;"></div>
      </div>

      <!-- Chart 4: Curvature & Kurtosis -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <div class="chart-title">🌊 4. Smile Curvature &amp; Kurtosis Fat-Tail Scaling Ratio</div>
            <div class="chart-desc">
              Symmetric Smile Curvature [$(IV_{Put} + IV_{Call})/2 - IV_{ATM}$] and Kurtosis scaling ratio vs Pure Quadratic Baseline (1.00).
            </div>
          </div>
        </div>
        <div id="chart-c-curv-kurt" class="chart-box" style="min-height: 560px;"></div>
      </div>

      <!-- Cross-Sectional Table -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <div class="chart-title">📋 3. Comprehensive Cross-Strike Consecutive Inspection Grid</div>
            <div class="chart-desc">
              Direct inspection of every strike's Implied Volatility, Fly IV Curvature, and Fly Net Premium across both sessions.
            </div>
          </div>
          <div>
            <input type="text" id="tbl-c-search" class="form-input" placeholder="Search strike..." oninput="filterConsecTable()" style="width: 180px;">
          </div>
        </div>
        <div class="table-container">
          <table class="quant-table" id="consec-table">
            <thead>
              <tr id="consec-table-head">
              </tr>
            </thead>
            <tbody id="consec-table-body">
            </tbody>
          </table>
        </div>
      </div>

      <!-- Single Strike 3-Leg Deconstruction Box -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <div class="chart-title">🔬 4. Single-Strike 3-Leg Butterfly Drilldown Inspector</div>
            <div class="chart-desc">Select an individual centre strike K to deconstruct the exact 3 option legs on Day T and Day T+1.</div>
          </div>
          <div>
            <select id="sel-consec-drill-k" class="form-select" onchange="renderConsecDrilldown()">
            </select>
          </div>
        </div>
        <div id="consec-drill-content" style="margin-top: 10px;">
        </div>
      </div>

    </div>

    <!-- TAB 2: SINGLE-DATE VOLATILITY & LIVE BS PRICING LAB -->
    <div id="tab-singledate" class="tab-pane">
      
      <div class="controls-panel">
        <div class="chart-header" style="margin-bottom: 8px;">
          <div>
            <div class="chart-title">🔬 Real-Time Black-Scholes Scenario Simulation Engine</div>
            <div class="chart-desc">
              Drag the interactive sliders below to simulate hypothetical shifts in Level, Skew, and Curvature. 
              The embedded JavaScript Black-Scholes model instantly recalculates option prices, Greeks, and 100-point butterfly spreads in real-time.
            </div>
          </div>
          <button class="btn-preset" onclick="resetSimSliders()">↺ Reset Sliders</button>
        </div>

        <div class="controls-grid" style="margin-top: 14px;">
          <div class="form-group">
            <label for="sel-sim-date">Base Snapshot Date:</label>
            <select id="sel-sim-date" class="form-select" onchange="onSimDateChanged()">
              <!-- Injected by JS -->
            </select>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-top: 16px;">
          
          <div class="slider-box">
            <div class="slider-header">
              <span>Δ Level (Parallel ATM IV Shift):</span>
              <span id="lbl-sim-level" class="slider-val">+0.00%</span>
            </div>
            <input type="range" id="rng-sim-level" min="-5.0" max="5.0" step="0.1" value="0.0" oninput="runLiveSimulation()">
          </div>

          <div class="slider-box">
            <div class="slider-header">
              <span>Δ Skew (Slope Tilt):</span>
              <span id="lbl-sim-skew" class="slider-val">+0.00 pts</span>
            </div>
            <input type="range" id="rng-sim-skew" min="-10.0" max="10.0" step="0.2" value="0.0" oninput="runLiveSimulation()">
          </div>

          <div class="slider-box">
            <div class="slider-header">
              <span>Δ Curvature (Convexity Bend):</span>
              <span id="lbl-sim-curv" class="slider-val">+0.00 pts</span>
            </div>
            <input type="range" id="rng-sim-curv" min="-5.0" max="5.0" step="0.1" value="0.0" oninput="runLiveSimulation()">
          </div>

          <div class="slider-box">
            <div class="slider-header">
              <span>Underlying SPX Spot Bump:</span>
              <span id="lbl-sim-spot" class="slider-val">+0 pts</span>
            </div>
            <input type="range" id="rng-sim-spot" min="-200" max="200" step="10" value="0" oninput="runLiveSimulation()">
          </div>

        </div>
      </div>

      <!-- Live Simulation Charts -->
      <div class="chart-grid-2">
        <div class="chart-card">
          <div class="chart-title">Original vs Simulated IV Smile</div>
          <div id="chart-sim-smile" class="chart-box-compact"></div>
        </div>
        <div class="chart-card">
          <div class="chart-title">Original vs Simulated 100-pt Butterfly Premium Curves</div>
          <div id="chart-sim-fly" class="chart-box-compact"></div>
        </div>
      </div>

    </div>

    <!-- TAB 3: MATHEMATICAL GUIDE -->
    <div id="tab-math" class="tab-pane">
      <div class="math-card">
        <h2>📐 Quantitative Architecture & Mathematical Formulations</h2>
        <p>
          This dashboard extension enables cross-sectional and temporal analysis of SPX implied volatility smiles, 
          fixed-strike butterfly spreads, and factor-driven risk decomposition. Below is the complete mathematical specification.
        </p>

        <h3>1. Three-Factor Smile Decomposition Model</h3>
        <p>
          Using an anchor bandwidth \(H = 500\) index points (\(\approx 0.08\) delta), the volatility smile is decomposed into 
          orthogonal geometric components:
        </p>
        <div class="formula-block">
Level (L) = IV(ATM)
Skew (S) = IV(ATM + H) − IV(ATM − H)
Curvature (C) = [IV(ATM − H) + IV(ATM + H)] / 2 − IV(ATM)
        </div>
        <p>
          Between a Reference Date \(T_0\) and Focus Date \(T_1\), the factor differences are:
        </p>
        <div class="formula-block">
ΔL = L(T₁) − L(T₀)
ΔS = S(T₁) − S(T₀)
ΔC = C(T₁) − C(T₀)
        </div>

        <h3>2. Five-Stage Smile Transformation Bridge</h3>
        <p>
          For any aligned strike offset \(x = \frac{K − K_{\text{ATM}}}{H}\), the smile is reconstructed step-by-step:
        </p>
        <div class="formula-block">
Stage 0 (Baseline):       IV₀(x)   = IV_ref(x)
Stage 1 (Level Shock):    IV_L(x)  = IV₀(x) + ΔL
Stage 2 (Skew Shock):     IV_LS(x) = IV_L(x) + (ΔS / 2) · x
Stage 3 (Curvature Shock):IV_LSC(x)= IV_LS(x) + ΔC · x²
Stage 4 (Actual Focus):   IV_actual(x) = IV_focus(x)
Residual:                 ε(x) = IV_actual(x) − IV_LSC(x)
        </div>

        <h3>3. Fixed-Strike 100-pt Butterfly Construction</h3>
        <p>
          A long butterfly spread with body strike \(K\) and wing spacing \(h = 100\) index points is constructed as:
        </p>
        <div class="formula-block">
Fly(K, h) = Option(K − h) − 2 · Option(K) + Option(K + h)
        </div>
        <p>
          OTM Call butterflies are traded for \(K \ge S_0\) and OTM Put butterflies for \(K \le S_0\).
        </p>

        <h3>4. Why Fixed-Reference IV-Only Repricing Is Essential</h3>
        <p>
          Between two trading sessions, the observed butterfly premium change incorporates both volatility surface moves 
          and underlying spot drift (\(\Delta S_0\)). To isolate pure volatility risk (vega and volga), 
          we hold reference spot \(S_0\), time to expiry \(T\), and strikes fixed, repricing the structure through Black–Scholes 
          under \(IV_0 \to IV_L \to IV_{LS} \to IV_{LSC}\):
        </p>
        <div class="formula-block">
Level Effect:     ΔF_L = F(IV_L) − F(IV₀)
Skew Effect:      ΔF_S = F(IV_LS) − F(IV_L)
Curvature Effect: ΔF_C = F(IV_LSC) − F(IV_LS)
Residual Effect:  ΔF_ε = F(IV_actual) − F(IV_LSC)
Total Vol P&amp;L:    ΔF_total = ΔF_L + ΔF_S + ΔF_C + ΔF_ε
        </div>
      </div>
    </div>
  </main>

  <footer>
    SPX Volatility Surface &amp; Fixed-Strike Butterfly Quant Lab • Precalculated Standalone Application • Google DeepMind Antigravity
  </footer>

  <!-- Embedded Precalculated Data -->
  <script id="precalculated-data" type="application/json">
""" + json_data + """
  </script>

  <!-- Application Logic -->
  <script>
    // Global State
    let DATA = null;
    let selectedDates = ['2026-08-03', '2026-08-04'];
    let refDate = '2026-08-03';
    let focusDate = '2026-08-04';

    // Distinct High-Contrast Palette
    const COLOR_PALETTE = [
      '#58a6ff', '#d29922', '#3fb950', '#bc8cff', '#f0883e',
      '#79c0ff', '#56d364', '#e3b341', '#db61a2', '#7ee787'
    ];

    // Initialize Application
    window.addEventListener('DOMContentLoaded', () => {
      try {
        const rawEl = document.getElementById('precalculated-data');
        DATA = JSON.parse(rawEl.textContent);
        console.log("Loaded dataset successfully:", DATA.all_dates.length, "dates");
        
        populateDateDropdowns();
        onDateSelectionChanged();
        renderFactorHistoryChart();
        initSimLab();
        initConsecutiveWorkspace();
      } catch (err) {
        console.error("Initialization failed:", err);
        alert("Failed to load embedded quantitative dataset: " + err);
      }
    });

    // Tab Switching
    function switchTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      
      const targetPane = document.getElementById(tabId);
      if (targetPane) {
        targetPane.classList.add('active');
      }
      
      const btn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabId));
      if (btn) btn.classList.add('active');

      // Trigger Plotly relayout to fit sizes
      setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 50);
    }

    // Populate Dropdowns
    function populateDateDropdowns() {
      const selRef = document.getElementById('sel-ref-date');
      const selFoc = document.getElementById('sel-focus-date');
      const selSim = document.getElementById('sel-sim-date');
      
      selRef.innerHTML = '';
      selFoc.innerHTML = '';
      selSim.innerHTML = '';

      DATA.all_dates.forEach(d => {
        const opt1 = new Option(d, d);
        const opt2 = new Option(d, d);
        const opt3 = new Option(d, d);
        
        selRef.add(opt1);
        selFoc.add(opt2);
        selSim.add(opt3);
      });

      selRef.value = refDate;
      selFoc.value = focusDate;
      selSim.value = refDate;
    }

    // Quick Presets
    function applyPreset(presetType) {
      document.querySelectorAll('.btn-preset').forEach(b => b.classList.remove('active'));
      
      if (presetType === 'benchmark') {
        document.getElementById('btn-p-bench').classList.add('active');
        selectedDates = ['2026-08-03', '2026-08-04'];
        refDate = '2026-08-03';
        focusDate = '2026-08-04';
      } else if (presetType === 'aug_week') {
        document.getElementById('btn-p-week').classList.add('active');
        selectedDates = ['2026-08-03', '2026-08-04', '2026-08-05', '2026-08-06', '2026-08-07'].filter(d => DATA.all_dates.includes(d));
        refDate = '2026-08-03';
        focusDate = '2026-08-07';
      } else if (presetType === 'aug_month') {
        document.getElementById('btn-p-aug').classList.add('active');
        selectedDates = DATA.all_dates.filter(d => d.startsWith('2026-08'));
        refDate = selectedDates[0];
        focusDate = selectedDates[selectedDates.length - 1];
      } else if (presetType === 'recent5') {
        document.getElementById('btn-p-recent').classList.add('active');
        selectedDates = DATA.all_dates.slice(-5);
        refDate = selectedDates[0];
        focusDate = selectedDates[selectedDates.length - 1];
      }

      document.getElementById('sel-ref-date').value = refDate;
      document.getElementById('sel-focus-date').value = focusDate;
      onDateSelectionChanged();
    }

    function stepFocusDay(direction) {
      const idx = DATA.all_dates.indexOf(focusDate);
      const nextIdx = idx + direction;
      if (nextIdx >= 0 && nextIdx < DATA.all_dates.length) {
        focusDate = DATA.all_dates[nextIdx];
        if (!selectedDates.includes(focusDate)) {
          selectedDates.push(focusDate);
          selectedDates.sort();
        }
        document.getElementById('sel-focus-date').value = focusDate;
        onDateSelectionChanged();
      }
    }

    // Selection Changes
    function onDateSelectionChanged() {
      refDate = document.getElementById('sel-ref-date').value;
      focusDate = document.getElementById('sel-focus-date').value;

      if (!selectedDates.includes(refDate)) selectedDates.push(refDate);
      if (!selectedDates.includes(focusDate)) selectedDates.push(focusDate);
      selectedDates.sort();

      updateKpis();
      renderAllCharts();
      renderMatrixTable();
    }

    // Dynamic Factor Calculation (Client-Side)
    function computeDynamicFactors(rDate, fDate, hWidth = 500) {
      const rObj = DATA.dates_data[rDate];
      const fObj = DATA.dates_data[fDate];
      if (!rObj || !fObj) return null;

      // Extract smile IVs
      const getIvAtOffset = (smile, targetOffset) => {
        const match = smile.find(r => Math.abs(r.offset - targetOffset) < 1e-3);
        if (match) return match.iv;
        // linear interp
        const offsets = smile.map(r => r.offset);
        const minOff = Math.min(...offsets);
        const maxOff = Math.max(...offsets);
        if (targetOffset < minOff || targetOffset > maxOff) return null;
        for (let i = 0; i < smile.length - 1; i++) {
          if (smile[i].offset <= targetOffset && targetOffset <= smile[i+1].offset) {
            const frac = (targetOffset - smile[i].offset) / (smile[i+1].offset - smile[i].offset);
            return smile[i].iv + frac * (smile[i+1].iv - smile[i].iv);
          }
        }
        return null;
      };

      const rL = getIvAtOffset(rObj.smile, 0);
      const rLeft = getIvAtOffset(rObj.smile, -hWidth);
      const rRight = getIvAtOffset(rObj.smile, hWidth);
      const rS = (rRight !== null && rLeft !== null) ? rRight - rLeft : 0;
      const rC = (rRight !== null && rLeft !== null && rL !== null) ? (rLeft + rRight) / 2 - rL : 0;

      const fL = getIvAtOffset(fObj.smile, 0);
      const fLeft = getIvAtOffset(fObj.smile, -hWidth);
      const fRight = getIvAtOffset(fObj.smile, hWidth);
      const fS = (fRight !== null && fLeft !== null) ? fRight - fLeft : 0;
      const fC = (fRight !== null && fLeft !== null && fL !== null) ? (fLeft + fRight) / 2 - fL : 0;

      const dL = fL - rL;
      const dS = fS - rS;
      const dC = fC - rC;

      // Calculate bridge points
      const bridge = [];
      let sumSqRes = 0;
      let count = 0;

      rObj.smile.forEach(rRow => {
        const fMatch = fObj.smile.find(fRow => Math.abs(fRow.offset - rRow.offset) < 1e-3);
        if (fMatch) {
          const off = rRow.offset;
          const x = off / hWidth;
          const levelComp = dL;
          const skewComp = (dS / 2) * x;
          const curvComp = dC * x * x;
          const modelledChange = levelComp + skewComp + curvComp;
          const obsChange = fMatch.iv - rRow.iv;
          const residual = obsChange - modelledChange;

          sumSqRes += residual * residual;
          count++;

          bridge.push({
            offset: off,
            x: x,
            ref_strike: rRow.strike,
            focus_strike: fMatch.strike,
            ref_iv: rRow.iv,
            focus_iv: fMatch.iv,
            iv_0: rRow.iv,
            iv_l: rRow.iv + levelComp,
            iv_ls: rRow.iv + levelComp + skewComp,
            iv_lsc: rRow.iv + modelledChange,
            level_comp: levelComp,
            skew_comp: skewComp,
            curvature_comp: curvComp,
            residual: residual,
            obs_change: obsChange,
          });
        }
      });

      const rmse = count > 0 ? Math.sqrt(sumSqRes / count) : 0;

      return {
        rL, rS, rC, fL, fS, fC, dL, dS, dC, rmse, count, bridge
      };
    }

    // Update KPI UI
    function updateKpis() {
      const hWidth = parseFloat(document.getElementById('sel-ref-width').value) || 500;
      const f = computeDynamicFactors(refDate, focusDate, hWidth);
      if (!f) return;

      const rObj = DATA.dates_data[refDate];
      const fObj = DATA.dates_data[focusDate];

      document.getElementById('kpi-ref-iv').textContent = f.rL.toFixed(3) + '%';
      document.getElementById('kpi-ref-sub').textContent = `Basis: ${refDate} (SPX: ${rObj.spot.toFixed(0)})`;

      document.getElementById('kpi-focus-iv').textContent = f.fL.toFixed(3) + '%';
      document.getElementById('kpi-focus-sub').textContent = `Target: ${focusDate} (SPX: ${fObj.spot.toFixed(0)})`;

      const elL = document.getElementById('kpi-delta-level');
      elL.textContent = (f.dL >= 0 ? '+' : '') + f.dL.toFixed(4) + ' pts';
      document.getElementById('card-delta-level').className = 'kpi-card ' + (f.dL >= 0 ? 'green' : 'red');

      const elS = document.getElementById('kpi-delta-skew');
      elS.textContent = (f.dS >= 0 ? '+' : '') + f.dS.toFixed(4) + ' pts';
      document.getElementById('card-delta-skew').className = 'kpi-card ' + (f.dS >= 0 ? 'green' : 'red');

      const elC = document.getElementById('kpi-delta-curv');
      elC.textContent = (f.dC >= 0 ? '+' : '') + f.dC.toFixed(4) + ' pts';
      document.getElementById('card-delta-curv').className = 'kpi-card ' + (Math.abs(f.dC) < 0.1 ? 'purple' : f.dC >= 0 ? 'green' : 'red');

      document.getElementById('kpi-rmse').textContent = f.rmse.toFixed(4) + ' pts';
      document.getElementById('kpi-nodes-sub').textContent = `${f.count} Aligned Nodes (H = ${hWidth})`;
    }

    // Common Dark Theme Layout for Plotly
    function getDarkLayout(title, xTitle, yTitle) {
      const showSpikes = document.getElementById('chk-spikes').checked;
      const dtickVal = document.getElementById('chk-grid100').checked ? 100 : undefined;

      return {
        title: {
          text: title,
          font: { family: 'Inter', size: 14, color: '#f0f6fc', weight: 600 },
          x: 0.02,
          y: 0.96,
        },
        paper_bgcolor: 'transparent',
        plot_bgcolor: '#090d16',
        margin: { l: 55, r: 25, t: 45, b: 50 },
        font: { family: 'Inter', color: '#8b949e', size: 11 },
        hovermode: 'x unified',
        xaxis: {
          title: { text: xTitle, font: { size: 12, color: '#8b949e' } },
          gridcolor: '#1a2234',
          zerolinecolor: '#32415d',
          showgrid: true,
          dtick: dtickVal,
          showspikes: showSpikes,
          spikemode: 'across',
          spikesnap: 'cursor',
          spikethickness: 1,
          spikedash: 'dot',
          spikecolor: '#38bdf8',
        },
        yaxis: {
          title: { text: yTitle, font: { size: 12, color: '#8b949e' } },
          gridcolor: '#1a2234',
          zerolinecolor: '#32415d',
          showgrid: true,
          showspikes: showSpikes,
          spikemode: 'across',
          spikethickness: 1,
          spikedash: 'dot',
          spikecolor: '#38bdf8',
        },
        legend: {
          orientation: 'h',
          y: 1.12,
          x: 0.02,
          font: { size: 11, color: '#f0f6fc' },
          bgcolor: 'rgba(19, 24, 35, 0.7)',
        },
      };
    }

    // Render All Charts
    function renderAllCharts() {
      const isOffset = document.getElementById('sel-align-mode').value === 'offset';
      const showBridge = document.getElementById('chk-bridge').checked;
      const hWidth = parseFloat(document.getElementById('sel-ref-width').value) || 500;
      const dynFactors = computeDynamicFactors(refDate, focusDate, hWidth);

      // 1. IV Smile Comparison
      const ivTraces = [];

      selectedDates.forEach((d, idx) => {
        const dObj = DATA.dates_data[d];
        if (!dObj) return;

        const isFocus = (d === focusDate);
        const isRef = (d === refDate);

        let color = COLOR_PALETTE[idx % COLOR_PALETTE.length];
        let width = 2.4;
        let opacity = 0.75;

        if (isFocus) {
          color = '#58a6ff'; // Cyan
          width = 4.2;
          opacity = 1.0;
        } else if (isRef) {
          color = '#d29922'; // Orange
          width = 3.2;
          opacity = 0.95;
        }

        const xVals = dObj.smile.map(r => isOffset ? r.offset : r.strike);
        const yVals = dObj.smile.map(r => r.iv);

        ivTraces.push({
          x: xVals,
          y: yVals,
          mode: 'lines+markers',
          name: `${d}${isFocus ? ' (Focus ★)' : isRef ? ' (Ref Basis)' : ''}`,
          line: { color: color, width: width },
          marker: {
            size: isFocus ? 7 : isRef ? 6 : 5,
            symbol: isFocus ? 'circle' : isRef ? 'diamond' : 'circle',
            line: { color: '#ffffff', width: isFocus ? 1.5 : 1 }
          },
          opacity: opacity,
        });
      });

      // Add Bridge traces if enabled and in offset mode
      if (showBridge && isOffset && dynFactors && dynFactors.bridge.length > 0) {
        const b = dynFactors.bridge;
        const xB = b.map(p => p.offset);

        // Stage 1: Level
        ivTraces.push({
          x: xB,
          y: b.map(p => p.iv_l),
          mode: 'lines',
          name: 'Stage 1: + ΔLevel (IV_L)',
          line: { color: '#3fb950', width: 2, dash: 'dash' },
        });

        // Stage 2: Skew
        ivTraces.push({
          x: xB,
          y: b.map(p => p.iv_ls),
          mode: 'lines',
          name: 'Stage 2: + ΔSkew (IV_LS)',
          line: { color: '#bc8cff', width: 2, dash: 'dash' },
        });

        // Stage 3: Curvature
        ivTraces.push({
          x: xB,
          y: b.map(p => p.iv_lsc),
          mode: 'lines',
          name: 'Stage 3: + ΔCurv (IV_LSC Modelled)',
          line: { color: '#f0883e', width: 2.2, dash: 'dot' },
        });

        // Focus Actual Points (Circles)
        ivTraces.push({
          x: xB,
          y: b.map(p => p.focus_iv),
          mode: 'markers',
          name: 'Actual Focus Smile (Target)',
          marker: { size: 7, color: 'transparent', line: { color: '#f85149', width: 2 } },
        });
      }

      const layoutIv = getDarkLayout(
        `Implied Volatility Smile Comparison (${isOffset ? 'ATM-Relative' : 'Absolute Strikes'})`,
        isOffset ? 'Strike Distance to ATM: K − K_ATM (pts)' : 'Absolute Strike Price K (pts)',
        'Implied Volatility (%)'
      );
      Plotly.react('chart-iv-smile', ivTraces, layoutIv, { responsive: true, displayModeBar: false });

      // 2. IV Attribution Companion Chart
      if (dynFactors && dynFactors.bridge.length > 0) {
        const b = dynFactors.bridge;
        const xOffsets = b.map(p => `${p.offset >= 0 ? '+' : ''}${p.offset}`);

        const attrTraces = [
          {
            x: xOffsets,
            y: b.map(p => p.level_comp),
            name: 'Level Component (ΔL)',
            type: 'bar',
            marker: { color: '#3fb950' }
          },
          {
            x: xOffsets,
            y: b.map(p => p.skew_comp),
            name: 'Skew Component (ΔS·x/2)',
            type: 'bar',
            marker: { color: '#bc8cff' }
          },
          {
            x: xOffsets,
            y: b.map(p => p.curvature_comp),
            name: 'Curvature Component (ΔC·x²)',
            type: 'bar',
            marker: { color: '#f0883e' }
          },
          {
            x: xOffsets,
            y: b.map(p => p.residual),
            name: 'Residual Gap (ε)',
            type: 'bar',
            marker: { color: '#f85149' }
          },
          {
            x: xOffsets,
            y: b.map(p => p.obs_change),
            name: 'Total Observed IV Shift',
            type: 'scatter',
            mode: 'lines+markers',
            line: { color: '#58a6ff', width: 2.5 },
            marker: { size: 6 }
          }
        ];

        const layoutAttr = getDarkLayout(
          `Smile Change Attribution: ${refDate} → ${focusDate}`,
          'ATM Offset (pts)',
          'Change (vol points)'
        );
        layoutAttr.barmode = 'relative';
        Plotly.react('chart-iv-attribution', attrTraces, layoutAttr, { responsive: true, displayModeBar: false });
      }

      // 3A & 3B. Butterfly Curves (Calls & Puts)
      const callTraces = [];
      const putTraces = [];

      selectedDates.forEach((d, idx) => {
        const dObj = DATA.dates_data[d];
        if (!dObj) return;

        const isFocus = (d === focusDate);
        const isRef = (d === refDate);

        let color = COLOR_PALETTE[idx % COLOR_PALETTE.length];
        let width = 2.4;
        let opacity = 0.75;

        if (isFocus) { color = '#58a6ff'; width = 4.0; opacity = 1.0; }
        else if (isRef) { color = '#d29922'; width = 3.0; opacity = 0.95; }

        // Calls
        if (dObj.call_flies && dObj.call_flies.length > 0) {
          callTraces.push({
            x: dObj.call_flies.map(f => isOffset ? f.offset : f.centre),
            y: dObj.call_flies.map(f => f.prem),
            mode: 'lines+markers',
            name: d,
            line: { color: color, width: width },
            marker: { size: isFocus ? 6 : 4 },
            opacity: opacity,
          });
        }

        // Puts
        if (dObj.put_flies && dObj.put_flies.length > 0) {
          putTraces.push({
            x: dObj.put_flies.map(f => isOffset ? f.offset : f.centre),
            y: dObj.put_flies.map(f => f.prem),
            mode: 'lines+markers',
            name: d,
            line: { color: color, width: width },
            marker: { size: isFocus ? 6 : 4 },
            opacity: opacity,
          });
        }
      });

      const layoutCallFly = getDarkLayout(
        'OTM Call Butterfly Premiums (100-pt Wings)',
        isOffset ? 'ATM Offset (pts)' : 'Centre Strike K',
        'Net Debit Premium ($)'
      );
      Plotly.react('chart-call-flies', callTraces, layoutCallFly, { responsive: true, displayModeBar: false });

      const layoutPutFly = getDarkLayout(
        'OTM Put Butterfly Premiums (100-pt Wings)',
        isOffset ? 'ATM Offset (pts)' : 'Centre Strike K',
        'Net Debit Premium ($)'
      );
      Plotly.react('chart-put-flies', putTraces, layoutPutFly, { responsive: true, displayModeBar: false });

      // 4. Observed Fly Differences
      const rFlies = [...(DATA.dates_data[refDate]?.call_flies || []), ...(DATA.dates_data[refDate]?.put_flies || [])];
      const fFlies = [...(DATA.dates_data[focusDate]?.call_flies || []), ...(DATA.dates_data[focusDate]?.put_flies || [])];
      
      const flyDiffs = [];
      rFlies.forEach(rf => {
        const ff = fFlies.find(f => Math.abs(f.offset - rf.offset) < 1e-3);
        if (ff) {
          const diff = ff.prem - rf.prem;
          flyDiffs.push({
            offset: rf.offset,
            diff: diff,
            color: diff >= 0 ? '#3fb950' : '#f85149'
          });
        }
      });

      flyDiffs.sort((a,b) => a.offset - b.offset);

      const diffTraces = [{
        x: flyDiffs.map(d => `${d.offset >= 0 ? '+' : ''}${d.offset}`),
        y: flyDiffs.map(d => d.diff),
        type: 'bar',
        marker: { color: flyDiffs.map(d => d.color) },
        name: 'Observed Change (Focus − Ref)'
      }];

      const layoutDiff = getDarkLayout(
        `Observed Butterfly Premium Difference: ${focusDate} vs ${refDate}`,
        'ATM Offset (pts)',
        'Δ Premium ($)'
      );
      Plotly.react('chart-fly-diffs', diffTraces, layoutDiff, { responsive: true, displayModeBar: false });

      // 5. Fixed-Reference Repricing & Attribution
      if (DATA.benchmark && refDate === '2026-08-03' && focusDate === '2026-08-04') {
        const attrs = DATA.benchmark.attributions;
        const xAttr = attrs.map(a => `${a.Side} @ ${a['Centre Strike']}`);

        const fixedTraces = [
          {
            x: xAttr,
            y: attrs.map(a => a['Level Effect']),
            name: 'Level Effect',
            type: 'bar',
            marker: { color: '#3fb950' }
          },
          {
            x: xAttr,
            y: attrs.map(a => a['Skew Effect']),
            name: 'Skew Effect',
            type: 'bar',
            marker: { color: '#bc8cff' }
          },
          {
            x: xAttr,
            y: attrs.map(a => a['Curvature Effect']),
            name: 'Curvature Effect',
            type: 'bar',
            marker: { color: '#f0883e' }
          },
          {
            x: xAttr,
            y: attrs.map(a => a['Residual Effect']),
            name: 'Residual Effect',
            type: 'bar',
            marker: { color: '#f85149' }
          },
          {
            x: xAttr,
            y: attrs.map(a => a['Total IV-Only Change']),
            name: 'Net Repriced Change',
            type: 'scatter',
            mode: 'lines+markers',
            line: { color: '#58a6ff', width: 2.5 }
          }
        ];

        const layoutFixed = getDarkLayout(
          'Hypothetical Fixed-Reference IV-Only Repricing Attribution (100-pt Wings)',
          'Butterfly Structure',
          'Attributed Change ($)'
        );
        layoutFixed.barmode = 'relative';
        Plotly.react('chart-fixed-attr', fixedTraces, layoutFixed, { responsive: true, displayModeBar: false });
      }
    }

    // Render Matrix Table
    function renderMatrixTable() {
      const thead = document.getElementById('matrix-table-head');
      const tbody = document.getElementById('matrix-table-body');

      // Build Header
      let hHtml = '<th>Strike Offset</th><th>Option Side</th>';
      selectedDates.forEach(d => {
        hHtml += `<th>${d}</th>`;
      });
      hHtml += `<th>Δ (${focusDate} − ${refDate})</th>`;
      thead.innerHTML = hHtml;

      // Extract all unique offsets
      const offsetSet = new Set();
      selectedDates.forEach(d => {
        const dObj = DATA.dates_data[d];
        if (dObj) {
          dObj.smile.forEach(s => offsetSet.add(s.offset));
        }
      });
      const allOffsets = Array.from(offsetSet).sort((a,b) => a - b);

      // Build Rows
      let bHtml = '';
      allOffsets.forEach(off => {
        const side = off === 0 ? 'ATM' : off < 0 ? 'PUT' : 'CALL';
        const badgeClass = off === 0 ? 'badge-atm' : off < 0 ? 'badge-put' : 'badge-call';

        let rowHtml = `<tr>
          <td><strong>${off >= 0 ? '+' : ''}${off} pts</strong></td>
          <td><span class="tag-badge ${badgeClass}">${side}</span></td>`;

        let refIv = null;
        let focIv = null;

        selectedDates.forEach(d => {
          const dObj = DATA.dates_data[d];
          const m = dObj?.smile.find(s => Math.abs(s.offset - off) < 1e-3);
          if (m) {
            rowHtml += `<td>${m.iv.toFixed(3)}%</td>`;
            if (d === refDate) refIv = m.iv;
            if (d === focusDate) focIv = m.iv;
          } else {
            rowHtml += `<td>—</td>`;
          }
        });

        if (refIv !== null && focIv !== null) {
          const delta = focIv - refIv;
          const cls = delta > 0 ? 'tag-pos' : delta < 0 ? 'tag-neg' : '';
          rowHtml += `<td class="${cls}"><strong>${delta >= 0 ? '+' : ''}${delta.toFixed(3)} pts</strong></td>`;
        } else {
          rowHtml += `<td>—</td>`;
        }

        rowHtml += `</tr>`;
        bHtml += rowHtml;
      });

      tbody.innerHTML = bHtml;
    }

    function filterMatrixTable() {
      const query = document.getElementById('tbl-search').value.toLowerCase();
      const rows = document.querySelectorAll('#matrix-table-body tr');
      rows.forEach(r => {
        const text = r.textContent.toLowerCase();
        r.style.display = text.includes(query) ? '' : 'none';
      });
    }

    // Historical Factor Evolution Chart
    function renderFactorHistoryChart() {
      const hist = DATA.factor_history;
      const dates = hist.map(h => h.date);

      const traces = [
        {
          x: dates,
          y: hist.map(h => h.level),
          name: 'ATM Level IV (%)',
          type: 'scatter',
          mode: 'lines',
          line: { color: '#58a6ff', width: 2.2 }
        },
        {
          x: dates,
          y: hist.map(h => h.skew),
          name: 'Skew (pts)',
          yaxis: 'y2',
          type: 'scatter',
          mode: 'lines',
          line: { color: '#bc8cff', width: 2 }
        },
        {
          x: dates,
          y: hist.map(h => h.curvature),
          name: 'Curvature (pts)',
          yaxis: 'y2',
          type: 'scatter',
          mode: 'lines',
          line: { color: '#f0883e', width: 2 }
        }
      ];

      const layout = getDarkLayout(
        'Historical SPX Volatility Smile Factors (338 Sessions)',
        'Date',
        'Level IV (%)'
      );
      layout.yaxis2 = {
        title: { text: 'Skew & Curvature (pts)', font: { size: 12, color: '#bc8cff' } },
        overlaying: 'y',
        side: 'right',
        gridcolor: 'transparent',
      };

      Plotly.react('chart-factor-history', traces, layout, { responsive: true, displayModeBar: false });
    }

    // -------------------------------------------------------------
    // Single Date Live Black-Scholes Engine in Pure JavaScript
    // -------------------------------------------------------------
    function normCdf(x) {
      const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429;
      const p = 0.3275911;
      let sign = 1;
      if (x < 0) { sign = -1; x = -x; }
      const t = 1.0 / (1.0 + p * x);
      const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x / 2.0);
      return 0.5 * (1.0 + sign * y);
    }

    function bsPrice(side, S, K, T, r, sigma) {
      if (T <= 0 || sigma <= 0) {
        return side === 'call' ? Math.max(0, S - K) : Math.max(0, K - S);
      }
      const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * Math.sqrt(T));
      const d2 = d1 - sigma * Math.sqrt(T);
      if (side === 'call') {
        return S * normCdf(d1) - K * Math.exp(-r * T) * normCdf(d2);
      } else {
        return K * Math.exp(-r * T) * normCdf(-d2) - S * normCdf(-d1);
      }
    }


    // -------------------------------------------------------------
    // Consecutive Date Analysis Logic
    // -------------------------------------------------------------
    let consecDate1 = '2026-08-03';
    let consecDate2 = '2026-08-04';

    function initConsecutiveWorkspace() {
      const selD1 = document.getElementById('sel-consec-d1');
      const selD2 = document.getElementById('sel-consec-d2');
      if (!selD1 || !selD2) return;

      selD1.innerHTML = '';
      selD2.innerHTML = '';
      DATA.all_dates.forEach(d => {
        selD1.add(new Option(d, d));
        selD2.add(new Option(d, d));
      });

      selD1.value = consecDate1;
      selD2.value = consecDate2;

      renderConsecutiveWorkspace();
    }

    function applyConsecPreset(d1, d2) {
      consecDate1 = d1;
      consecDate2 = d2;
      document.getElementById('sel-consec-d1').value = d1;
      document.getElementById('sel-consec-d2').value = d2;
      renderConsecutiveWorkspace();
    }

    function stepConsecPair(dir) {
      const idx = DATA.all_dates.indexOf(consecDate1);
      const nextIdx = idx + dir;
      if (nextIdx >= 0 && nextIdx < DATA.all_dates.length - 1) {
        consecDate1 = DATA.all_dates[nextIdx];
        consecDate2 = DATA.all_dates[nextIdx + 1];
        document.getElementById('sel-consec-d1').value = consecDate1;
        document.getElementById('sel-consec-d2').value = consecDate2;
        renderConsecutiveWorkspace();
      }
    }

    function onConsecDate1Changed() {
      consecDate1 = document.getElementById('sel-consec-d1').value;
      const idx = DATA.all_dates.indexOf(consecDate1);
      const nextIdx = Math.min(idx + 1, DATA.all_dates.length - 1);
      consecDate2 = DATA.all_dates[nextIdx];
      document.getElementById('sel-consec-d2').value = consecDate2;
      renderConsecutiveWorkspace();
    }

    function onConsecSelectionChanged() {
      consecDate1 = document.getElementById('sel-consec-d1').value;
      consecDate2 = document.getElementById('sel-consec-d2').value;
      renderConsecutiveWorkspace();
    }

    function renderConsecutiveWorkspace() {
      const o1 = DATA.dates_data[consecDate1];
      const o2 = DATA.dates_data[consecDate2];
      if (!o1 || !o2) return;

      const isOffset = document.getElementById('sel-consec-align').value === 'offset';

      // Update KPIs
      document.getElementById('kpi-c-d1-iv').textContent = (o1.level !== null ? o1.level.toFixed(3) : '—') + '%';
      document.getElementById('kpi-c-d1-sub').textContent = `SPX: ${o1.spot.toFixed(0)} | ATM: ${o1.atm_strike.toFixed(0)}`;

      document.getElementById('kpi-c-d2-iv').textContent = (o2.level !== null ? o2.level.toFixed(3) : '—') + '%';
      document.getElementById('kpi-c-d2-sub').textContent = `SPX: ${o2.spot.toFixed(0)} | ATM: ${o2.atm_strike.toFixed(0)}`;

      const dSpot = o2.spot - o1.spot;
      const elSpot = document.getElementById('kpi-c-spot');
      elSpot.textContent = (dSpot >= 0 ? '+' : '') + dSpot.toFixed(1) + ' pts';
      document.getElementById('card-c-spot').className = 'kpi-card ' + (dSpot >= 0 ? 'green' : 'red');

      const dL = (o2.level !== null && o1.level !== null) ? o2.level - o1.level : 0;
      const elL = document.getElementById('kpi-c-level');
      elL.textContent = (dL >= 0 ? '+' : '') + dL.toFixed(4) + ' pts';
      document.getElementById('card-c-level').className = 'kpi-card ' + (dL >= 0 ? 'green' : 'red');

      const dS = (o2.skew !== null && o1.skew !== null) ? o2.skew - o1.skew : 0;
      const elS = document.getElementById('kpi-c-skew');
      elS.textContent = (dS >= 0 ? '+' : '') + dS.toFixed(4) + ' pts';
      document.getElementById('card-c-skew').className = 'kpi-card ' + (dS >= 0 ? 'green' : 'red');

      const dC = (o2.curvature !== null && o1.curvature !== null) ? o2.curvature - o1.curvature : 0;
      const elC = document.getElementById('kpi-c-curv');
      elC.textContent = (dC >= 0 ? '+' : '') + dC.toFixed(4) + ' pts';
      document.getElementById('card-c-curv').className = 'kpi-card ' + (Math.abs(dC) < 0.05 ? 'purple' : dC >= 0 ? 'green' : 'red');

      // Structure metrics
      const st1 = o1.structure || {};
      const st2 = o2.structure || {};
      const b300_1 = st1.benchmark_300 || {};
      const b300_2 = st2.benchmark_300 || {};
      const poly1 = st1.poly_coeffs || {};
      const poly2 = st2.poly_coeffs || {};

      const cs2 = b300_2.call_skew !== undefined ? b300_2.call_skew : null;
      const ps2 = b300_2.put_skew !== undefined ? b300_2.put_skew : null;
      const dCs = (cs2 !== null && b300_1.call_skew !== undefined) ? cs2 - b300_1.call_skew : 0;
      const dPs = (ps2 !== null && b300_1.put_skew !== undefined) ? ps2 - b300_1.put_skew : 0;

      const elCP = document.getElementById('kpi-c-callput-skew');
      if (elCP && cs2 !== null && ps2 !== null) {
        elCP.textContent = `Call: ${cs2.toFixed(2)} | Put: ${ps2 >= 0 ? '+' : ''}${ps2.toFixed(2)}`;
        document.getElementById('kpi-c-callput-sub').textContent = `Δ Call: ${dCs >= 0 ? '+' : ''}${dCs.toFixed(2)} | Δ Put: ${dPs >= 0 ? '+' : ''}${dPs.toFixed(2)}`;
      }

      const rr1 = b300_1.risk_reversal !== undefined ? b300_1.risk_reversal : null;
      const rr2 = b300_2.risk_reversal !== undefined ? b300_2.risk_reversal : null;
      const dRr = (rr1 !== null && rr2 !== null) ? rr2 - rr1 : 0;
      const elRr = document.getElementById('kpi-c-rr');
      if (elRr && rr2 !== null) {
        elRr.textContent = `${rr2.toFixed(3)} pts`;
        document.getElementById('kpi-c-rr-sub').textContent = `Shift: ${dRr >= 0 ? '+' : ''}${dRr.toFixed(3)} pts (${dRr >= 0 ? 'Flattening' : 'Steepening'})`;
        document.getElementById('card-c-rr').className = 'kpi-card ' + (dRr >= 0 ? 'green' : 'red');
      }

      const c2 = b300_2.curvature !== undefined ? b300_2.curvature : null;
      const c1 = b300_1.curvature !== undefined ? b300_1.curvature : null;
      const dCurv = (c2 !== null && c1 !== null) ? c2 - c1 : 0;
      const a4_2 = poly2.a4_kurtosis !== undefined ? poly2.a4_kurtosis : 0;
      const a4_1 = poly1.a4_kurtosis !== undefined ? poly1.a4_kurtosis : 0;
      const dKurt = a4_2 - a4_1;
      const elKurt = document.getElementById('kpi-c-kurt');
      if (elKurt && c2 !== null) {
        elKurt.textContent = `+${c2.toFixed(3)} pts | a₄: ${a4_2.toFixed(3)}`;
        document.getElementById('kpi-c-kurt-sub').textContent = `Δ Curv: ${dCurv >= 0 ? '+' : ''}${dCurv.toFixed(3)} | Δ a₄: ${dKurt >= 0 ? '+' : ''}${dKurt.toFixed(4)}`;
      }

      // Compute Fly IV for each date
      const getFlyIvMap = (smile) => {
        const map = {};
        for (let i = 1; i < smile.length - 1; i++) {
          const kL = smile[i-1].strike;
          const kM = smile[i].strike;
          const kU = smile[i+1].strike;
          if (Math.abs((kM - kL) - 100) < 1 && Math.abs((kU - kM) - 100) < 1) {
            const flyIv = smile[i-1].iv - 2 * smile[i].iv + smile[i+1].iv;
            map[kM] = flyIv;
          }
        }
        return map;
      };

      const flyIvMap1 = getFlyIvMap(o1.smile);
      const flyIvMap2 = getFlyIvMap(o2.smile);

      // Render Graph 1: Strike IV & Fly IV
      const xColStrike1 = o1.smile.map(r => isOffset ? r.offset : r.strike);
      const yColStrike1 = o1.smile.map(r => r.iv);
      const xColStrike2 = o2.smile.map(r => isOffset ? r.offset : r.strike);
      const yColStrike2 = o2.smile.map(r => r.iv);

      const fStrikes1 = Object.keys(flyIvMap1).map(Number).sort((a,b) => a - b);
      const fStrikes2 = Object.keys(flyIvMap2).map(Number).sort((a,b) => a - b);

      const tracesIvFly = [
        {
          x: xColStrike1,
          y: yColStrike1,
          name: `Strike IV (${consecDate1})`,
          mode: 'lines+markers',
          line: { color: '#38bdf8', width: 3.2 },
          marker: { size: 7, color: '#38bdf8' }
        },
        {
          x: xColStrike2,
          y: yColStrike2,
          name: `Strike IV (${consecDate2}) ★`,
          mode: 'lines+markers',
          line: { color: '#e3b341', width: 3.6 },
          marker: { size: 8, color: '#e3b341', symbol: 'diamond' }
        },
        {
          x: fStrikes1.map(k => isOffset ? k - o1.atm_strike : k),
          y: fStrikes1.map(k => flyIvMap1[k]),
          name: `Fly IV (${consecDate1})`,
          yaxis: 'y2',
          mode: 'lines+markers',
          line: { color: '#bc8cff', width: 2.4 },
          marker: { size: 6, color: '#bc8cff', symbol: 'square' }
        },
        {
          x: fStrikes2.map(k => isOffset ? k - o2.atm_strike : k),
          y: fStrikes2.map(k => flyIvMap2[k]),
          name: `Fly IV (${consecDate2}) ★`,
          yaxis: 'y2',
          mode: 'lines+markers',
          line: { color: '#3fb950', width: 2.6 },
          marker: { size: 7, color: '#3fb950', symbol: 'triangle-up' }
        }
      ];

      const layoutIvFly = getDarkLayout(
        `Implied Volatility Smiles & Fly IV Curvature (${consecDate1} → ${consecDate2})`,
        isOffset ? 'ATM Offset (pts)' : 'Strike Price K',
        'Strike IV (%)'
      );
      layoutIvFly.yaxis2 = {
        title: { text: 'Fly IV Curvature (vol pts)', font: { size: 12, color: '#bc8cff' } },
        overlaying: 'y',
        side: 'right',
        gridcolor: 'transparent',
      };
      Plotly.react('chart-c-iv-fly', tracesIvFly, layoutIvFly, { responsive: true, displayModeBar: false });

      // Render Graph 2: Fly Premium & Delta
      const flies1 = [...(o1.call_flies || []), ...(o1.put_flies || [])];
      const flies2 = [...(o2.call_flies || []), ...(o2.put_flies || [])];

      const f1Sorted = flies1.sort((a,b) => a.centre - b.centre);
      const f2Sorted = flies2.sort((a,b) => a.centre - b.centre);

      const tracesFlyPrem = [
        {
          x: f1Sorted.map(f => isOffset ? f.offset : f.centre),
          y: f1Sorted.map(f => f.prem),
          name: `Fly Premium (${consecDate1})`,
          mode: 'lines+markers',
          line: { color: '#d29922', width: 3.2 },
          marker: { size: 7, color: '#d29922', symbol: 'diamond' }
        },
        {
          x: f2Sorted.map(f => isOffset ? f.offset : f.centre),
          y: f2Sorted.map(f => f.prem),
          name: `Fly Premium (${consecDate2}) ★`,
          mode: 'lines+markers',
          line: { color: '#3fb950', width: 3.6 },
          marker: { size: 8, color: '#3fb950' }
        }
      ];

      // Delta bars
      const commonFlies = [];
      f1Sorted.forEach(fa => {
        const fb = f2Sorted.find(f => isOffset ? Math.abs(f.offset - fa.offset) < 1 : Math.abs(f.centre - fa.centre) < 1);
        if (fb) {
          const diff = fb.prem - fa.prem;
          commonFlies.push({
            x: isOffset ? fa.offset : fa.centre,
            diff: diff,
            color: diff >= 0 ? '#3fb950' : '#f85149'
          });
        }
      });

      if (commonFlies.length > 0) {
        tracesFlyPrem.push({
          x: commonFlies.map(c => c.x),
          y: commonFlies.map(c => c.diff),
          name: 'Δ Premium ($/fly)',
          type: 'bar',
          yaxis: 'y2',
          marker: { color: commonFlies.map(c => c.color), opacity: 0.55 }
        });
      }

      const layoutFlyPrem = getDarkLayout(
        `100-pt Butterfly Premium Curves & Daily Price Shifts (${consecDate1} → ${consecDate2})`,
        isOffset ? 'ATM Offset (pts)' : 'Centre Strike K',
        'Fly Premium ($)'
      );
      layoutFlyPrem.yaxis2 = {
        title: { text: 'Δ Premium ($)', font: { size: 12, color: '#3fb950' } },
        overlaying: 'y',
        side: 'right',
        gridcolor: 'transparent',
      };
      Plotly.react('chart-c-fly-prem', tracesFlyPrem, layoutFlyPrem, { responsive: true, displayModeBar: false });

      // Render Graph 3: Call/Put Skew & Risk Reversal
      const table1 = st1.table || [];
      const table2 = st2.table || [];
      const offsets = table1.map(t => t.offset);

      const tracesSkewRr = [
        {
          x: offsets,
          y: table1.map(t => t.put_skew),
          name: `Put Skew (${consecDate1})`,
          mode: 'lines+markers',
          line: { color: '#f85149', width: 2.4, dash: 'dot' },
          marker: { size: 6, color: '#f85149', symbol: 'square' },
        },
        {
          x: offsets,
          y: table2.map(t => t.put_skew),
          name: `Put Skew (${consecDate2}) ★`,
          mode: 'lines+markers',
          line: { color: '#ff7b72', width: 3.4 },
          marker: { size: 7, color: '#ff7b72', symbol: 'diamond' },
        },
        {
          x: offsets,
          y: table1.map(t => t.call_skew),
          name: `Call Skew (${consecDate1})`,
          mode: 'lines+markers',
          line: { color: '#38bdf8', width: 2.4, dash: 'dot' },
          marker: { size: 6, color: '#38bdf8', symbol: 'circle' },
        },
        {
          x: offsets,
          y: table2.map(t => t.call_skew),
          name: `Call Skew (${consecDate2}) ★`,
          mode: 'lines+markers',
          line: { color: '#e3b341', width: 3.4 },
          marker: { size: 7, color: '#e3b341', symbol: 'diamond' },
        },
        {
          x: offsets,
          y: table1.map(t => t.risk_reversal),
          name: `Risk Reversal (${consecDate1})`,
          yaxis: 'y2',
          mode: 'lines+markers',
          line: { color: '#bc8cff', width: 2.6, dash: 'dot' },
          marker: { size: 6, color: '#bc8cff', symbol: 'diamond' },
        },
        {
          x: offsets,
          y: table2.map(t => t.risk_reversal),
          name: `Risk Reversal (${consecDate2}) ★`,
          yaxis: 'y2',
          mode: 'lines+markers',
          line: { color: '#58a6ff', width: 3.4 },
          marker: { size: 7, color: '#58a6ff', symbol: 'circle' },
        },
      ];

      const deltaRr = [];
      table1.forEach(t1 => {
        const t2 = table2.find(x => Math.abs(x.offset - t1.offset) < 1);
        if (t2 && t1.risk_reversal !== null && t2.risk_reversal !== null) {
          const diff = t2.risk_reversal - t1.risk_reversal;
          deltaRr.push({
            x: t1.offset,
            diff: diff,
            color: diff >= 0 ? '#3fb950' : '#f85149',
          });
        }
      });
      if (deltaRr.length > 0) {
        tracesSkewRr.push({
          x: deltaRr.map(d => d.x),
          y: deltaRr.map(d => d.diff),
          name: 'Δ Risk Reversal (vol pts)',
          type: 'bar',
          yaxis: 'y2',
          marker: { color: deltaRr.map(d => d.color), opacity: 0.45 },
        });
      }

      const layoutSkewRr = getDarkLayout(
        `Call/Put Skew & Risk Reversal Dynamics (${consecDate1} → ${consecDate2})`,
        'Moneyness Distance to ATM: ΔK (pts)',
        'Skew to ATM (vol pts)'
      );
      layoutSkewRr.yaxis2 = {
        title: { text: 'Risk Reversal (vol pts)', font: { size: 12, color: '#58a6ff' } },
        overlaying: 'y',
        side: 'right',
        gridcolor: 'transparent',
      };
      Plotly.react('chart-c-skew-rr', tracesSkewRr, layoutSkewRr, { responsive: true, displayModeBar: false });

      // Render Graph 4: Smile Curvature & Kurtosis Scaling Ratio
      const tracesCurvKurt = [
        {
          x: offsets,
          y: table1.map(t => t.curvature),
          name: `Curvature (${consecDate1})`,
          mode: 'lines+markers',
          line: { color: '#bc8cff', width: 2.6, dash: 'dot' },
          marker: { size: 6, color: '#bc8cff', symbol: 'square' },
        },
        {
          x: offsets,
          y: table2.map(t => t.curvature),
          name: `Curvature (${consecDate2}) ★`,
          mode: 'lines+markers',
          line: { color: '#3fb950', width: 3.4 },
          marker: { size: 7, color: '#3fb950', symbol: 'diamond' },
        },
        {
          x: offsets,
          y: table1.map(t => t.kurtosis_ratio),
          name: `Kurtosis Ratio (${consecDate1})`,
          yaxis: 'y2',
          mode: 'lines+markers',
          line: { color: '#d29922', width: 2.6, dash: 'dot' },
          marker: { size: 6, color: '#d29922', symbol: 'diamond' },
        },
        {
          x: offsets,
          y: table2.map(t => t.kurtosis_ratio),
          name: `Kurtosis Ratio (${consecDate2}) ★`,
          yaxis: 'y2',
          mode: 'lines+markers',
          line: { color: '#38bdf8', width: 3.4 },
          marker: { size: 7, color: '#38bdf8', symbol: 'circle' },
        },
      ];

      const deltaCurv = [];
      table1.forEach(t1 => {
        const t2 = table2.find(x => Math.abs(x.offset - t1.offset) < 1);
        if (t2 && t1.curvature !== null && t2.curvature !== null) {
          const diff = t2.curvature - t1.curvature;
          deltaCurv.push({
            x: t1.offset,
            diff: diff,
            color: diff >= 0 ? '#3fb950' : '#f85149',
          });
        }
      });
      if (deltaCurv.length > 0) {
        tracesCurvKurt.push({
          x: deltaCurv.map(d => d.x),
          y: deltaCurv.map(d => d.diff),
          name: 'Δ Curvature (vol pts)',
          type: 'bar',
          marker: { color: deltaCurv.map(d => d.color), opacity: 0.45 },
        });
      }

      const layoutCurvKurt = getDarkLayout(
        `Smile Curvature & Kurtosis Fat-Tail Scaling Ratio (${consecDate1} → ${consecDate2})`,
        'Moneyness Distance to ATM: ΔK (pts)',
        'Curvature (vol pts)'
      );
      layoutCurvKurt.yaxis2 = {
        title: { text: 'Kurtosis Ratio (vs 1.0)', font: { size: 12, color: '#38bdf8' } },
        overlaying: 'y',
        side: 'right',
        gridcolor: 'transparent',
      };
      Plotly.react('chart-c-curv-kurt', tracesCurvKurt, layoutCurvKurt, { responsive: true, displayModeBar: false });

      // Render Table
      renderConsecTable();

      // Populate Drilldown select with offsets
      const selDrill = document.getElementById('sel-consec-drill-k');
      selDrill.innerHTML = '';
      const allDrillOffsets = [-800, -700, -600, -500, -400, -300, -200, -100, 100, 200, 300, 400, 500, 600, 700, 800];
      allDrillOffsets.forEach(off => {
        const k1 = o1.atm_strike + off;
        const k2 = o2.atm_strike + off;
        selDrill.add(new Option(`ATM ${off >= 0 ? '+' : ''}${off} pts (Day T: ${k1} | Day T+1: ${k2})`, off));
      });
      if (allDrillOffsets.length > 0) {
        selDrill.value = -800;
        renderConsecDrilldown();
      }
    }

    function renderConsecTable() {
      const o1 = DATA.dates_data[consecDate1];
      const o2 = DATA.dates_data[consecDate2];
      if (!o1 || !o2) return;

      const thead = document.getElementById('consec-table-head');
      const tbody = document.getElementById('consec-table-body');

      thead.innerHTML = `
        <th>Offset to ATM</th>
        <th>Type</th>
        <th>K (${consecDate1})</th>
        <th>K (${consecDate2})</th>
        <th>IV ${consecDate1}</th>
        <th>IV ${consecDate2}</th>
        <th>Δ IV</th>
        <th>Fly IV ${consecDate1}</th>
        <th>Fly IV ${consecDate2}</th>
        <th>Δ Fly IV</th>
        <th>Fly Prem ${consecDate1}</th>
        <th>Fly Prem ${consecDate2}</th>
        <th>Δ Premium</th>
      `;

      const getFlyMap = (o) => {
        const m = {};
        const flies = [...(o.call_flies || []), ...(o.put_flies || [])];
        flies.forEach(f => m[f.offset] = f.prem);
        return m;
      };

      const getFlyIvMap = (smile) => {
        const m = {};
        for (let i = 1; i < smile.length - 1; i++) {
          const kL = smile[i-1].strike;
          const kM = smile[i].strike;
          const kU = smile[i+1].strike;
          if (Math.abs((kM - kL) - 100) < 1 && Math.abs((kU - kM) - 100) < 1) {
            m[smile[i].offset] = smile[i-1].iv - 2 * smile[i].iv + smile[i+1].iv;
          }
        }
        return m;
      };

      const pMap1 = getFlyMap(o1);
      const pMap2 = getFlyMap(o2);
      const fIvMap1 = getFlyIvMap(o1.smile);
      const fIvMap2 = getFlyIvMap(o2.smile);

      const allOffsets = Array.from(new Set([...o1.smile.map(r => r.offset), ...o2.smile.map(r => r.offset)])).sort((a,b) => a - b);

      let bHtml = '';
      allOffsets.forEach(off => {
        const r1 = o1.smile.find(r => r.offset === off);
        const r2 = o2.smile.find(r => r.offset === off);

        const k1 = r1 ? r1.strike : (o1.atm_strike + off);
        const k2 = r2 ? r2.strike : (o2.atm_strike + off);

        const iv1 = r1 ? r1.iv : null;
        const iv2 = r2 ? r2.iv : null;
        const dIv = (iv1 !== null && iv2 !== null) ? iv2 - iv1 : null;

        const flyIv1 = fIvMap1[off] !== undefined ? fIvMap1[off] : null;
        const flyIv2 = fIvMap2[off] !== undefined ? fIvMap2[off] : null;
        const dFlyIv = (flyIv1 !== null && flyIv2 !== null) ? flyIv2 - flyIv1 : null;

        const prem1 = pMap1[off] !== undefined ? pMap1[off] : null;
        const prem2 = pMap2[off] !== undefined ? pMap2[off] : null;
        const dPrem = (prem1 !== null && prem2 !== null) ? prem2 - prem1 : null;

        const side = off < 0 ? 'PUT' : (off === 0 ? 'ATM' : 'CALL');
        const badgeClass = side === 'CALL' ? 'badge-call' : side === 'PUT' ? 'badge-put' : 'badge-atm';

        bHtml += `<tr>
          <td><strong>${off >= 0 ? '+' : ''}${off} pts</strong></td>
          <td><span class="tag-badge ${badgeClass}">${side}</span></td>
          <td>${k1}</td>
          <td>${k2}</td>
          <td>${iv1 !== null ? iv1.toFixed(3) + '%' : '—'}</td>
          <td>${iv2 !== null ? iv2.toFixed(3) + '%' : '—'}</td>
          <td class="${dIv > 0 ? 'tag-pos' : dIv < 0 ? 'tag-neg' : ''}"><strong>${dIv !== null ? (dIv >= 0 ? '+' : '') + dIv.toFixed(3) : '—'}</strong></td>
          <td>${flyIv1 !== null ? (flyIv1 >= 0 ? '+' : '') + flyIv1.toFixed(4) : '—'}</td>
          <td>${flyIv2 !== null ? (flyIv2 >= 0 ? '+' : '') + flyIv2.toFixed(4) : '—'}</td>
          <td class="${dFlyIv > 0 ? 'tag-pos' : dFlyIv < 0 ? 'tag-neg' : ''}">${dFlyIv !== null ? (dFlyIv >= 0 ? '+' : '') + dFlyIv.toFixed(4) : '—'}</td>
          <td>${prem1 !== null ? '$' + prem1.toFixed(2) : '—'}</td>
          <td>${prem2 !== null ? '$' + prem2.toFixed(2) : '—'}</td>
          <td class="${dPrem > 0 ? 'tag-pos' : dPrem < 0 ? 'tag-neg' : ''}"><strong>${dPrem !== null ? (dPrem >= 0 ? '+$' : '-$') + Math.abs(dPrem).toFixed(2) : '—'}</strong></td>
        </tr>`;
      });

      tbody.innerHTML = bHtml;
    }

    function filterConsecTable() {
      const q = document.getElementById('tbl-c-search').value.toLowerCase();
      const rows = document.querySelectorAll('#consec-table-body tr');
      rows.forEach(r => {
        r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    }

    function renderConsecDrilldown() {
      const off = parseFloat(document.getElementById('sel-consec-drill-k').value);
      const o1 = DATA.dates_data[consecDate1];
      const o2 = DATA.dates_data[consecDate2];
      if (!o1 || !o2 || isNaN(off)) return;

      const offLow = off - 100;
      const offMid = off;
      const offUpp = off + 100;

      const r1Low = o1.smile.find(r => r.offset === offLow);
      const r1Mid = o1.smile.find(r => r.offset === offMid);
      const r1Upp = o1.smile.find(r => r.offset === offUpp);

      const r2Low = o2.smile.find(r => r.offset === offLow);
      const r2Mid = o2.smile.find(r => r.offset === offMid);
      const r2Upp = o2.smile.find(r => r.offset === offUpp);

      const div = document.getElementById('consec-drill-content');
      if (!r1Low || !r1Mid || !r1Upp || !r2Low || !r2Mid || !r2Upp) {
        div.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">Incomplete wing quotes at this offset.</p>';
        return;
      }

      const f1Prem = r1Low.prem - 2 * r1Mid.prem + r1Upp.prem;
      const f2Prem = r2Low.prem - 2 * r2Mid.prem + r2Upp.prem;
      const dPrem = f2Prem - f1Prem;

      const f1Iv = r1Low.iv - 2 * r1Mid.iv + r1Upp.iv;
      const f2Iv = r2Low.iv - 2 * r2Mid.iv + r2Upp.iv;
      const dIv = f2Iv - f1Iv;

      div.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px;">
          <div class="kpi-card cyan">
            <div class="kpi-title">Lower Wing (+1): ${r1Low.strike} &rarr; ${r2Low.strike}</div>
            <div class="kpi-value">$${r1Low.prem.toFixed(2)} &rarr; $${r2Low.prem.toFixed(2)}</div>
            <div class="kpi-sub">Δ Prem: ${(r2Low.prem - r1Low.prem >= 0 ? '+' : '')}${(r2Low.prem - r1Low.prem).toFixed(2)} | Δ IV: ${(r2Low.iv - r1Low.iv >= 0 ? '+' : '')}${(r2Low.iv - r1Low.iv).toFixed(3)} pts</div>
          </div>
          <div class="kpi-card cyan">
            <div class="kpi-title">Middle Body (−2): ${r1Mid.strike} &rarr; ${r2Mid.strike}</div>
            <div class="kpi-value">$${r1Mid.prem.toFixed(2)} &rarr; $${r2Mid.prem.toFixed(2)}</div>
            <div class="kpi-sub">Δ Prem: ${(r2Mid.prem - r1Mid.prem >= 0 ? '+' : '')}${(r2Mid.prem - r1Mid.prem).toFixed(2)} | Δ IV: ${(r2Mid.iv - r1Mid.iv >= 0 ? '+' : '')}${(r2Mid.iv - r1Mid.iv).toFixed(3)} pts</div>
          </div>
          <div class="kpi-card cyan">
            <div class="kpi-title">Upper Wing (+1): ${r1Upp.strike} &rarr; ${r2Upp.strike}</div>
            <div class="kpi-value">$${r1Upp.prem.toFixed(2)} &rarr; $${r2Upp.prem.toFixed(2)}</div>
            <div class="kpi-sub">Δ Prem: ${(r2Upp.prem - r1Upp.prem >= 0 ? '+' : '')}${(r2Upp.prem - r1Upp.prem).toFixed(2)} | Δ IV: ${(r2Upp.iv - r1Upp.iv >= 0 ? '+' : '')}${(r2Upp.iv - r1Upp.iv).toFixed(3)} pts</div>
          </div>
          <div class="kpi-card ${dPrem >= 0 ? 'green' : 'red'}">
            <div class="kpi-title">Net 100-pt Fly Package</div>
            <div class="kpi-value">$${f1Prem.toFixed(2)} &rarr; $${f2Prem.toFixed(2)}</div>
            <div class="kpi-sub">Δ Premium: <b>${(dPrem >= 0 ? '+' : '')}$${dPrem.toFixed(2)}</b> | Δ Fly IV: ${(dIv >= 0 ? '+' : '')}${dIv.toFixed(4)} pts</div>
          </div>
        </div>
      `;
    }

    function initSimLab() {
      onSimDateChanged();
    }

    function onSimDateChanged() {
      runLiveSimulation();
    }

    function resetSimSliders() {
      document.getElementById('rng-sim-level').value = '0.0';
      document.getElementById('rng-sim-skew').value = '0.0';
      document.getElementById('rng-sim-curv').value = '0.0';
      document.getElementById('rng-sim-spot').value = '0';
      runLiveSimulation();
    }

    function runLiveSimulation() {
      const d = document.getElementById('sel-sim-date').value;
      const dObj = DATA.dates_data[d];
      if (!dObj) return;

      const dL = parseFloat(document.getElementById('rng-sim-level').value);
      const dS = parseFloat(document.getElementById('rng-sim-skew').value);
      const dC = parseFloat(document.getElementById('rng-sim-curv').value);
      const dSpot = parseFloat(document.getElementById('rng-sim-spot').value);

      document.getElementById('lbl-sim-level').textContent = (dL >= 0 ? '+' : '') + dL.toFixed(2) + '%';
      document.getElementById('lbl-sim-skew').textContent = (dS >= 0 ? '+' : '') + dS.toFixed(2) + ' pts';
      document.getElementById('lbl-sim-curv').textContent = (dC >= 0 ? '+' : '') + dC.toFixed(2) + ' pts';
      document.getElementById('lbl-sim-spot').textContent = (dSpot >= 0 ? '+' : '') + dSpot.toFixed(0) + ' pts';

      const H = 500;
      const origSmile = dObj.smile;
      const origStrikes = origSmile.map(s => s.strike);
      const origIvs = origSmile.map(s => s.iv);

      const simIvs = origSmile.map(s => {
        const x = s.offset / H;
        return Math.max(1.0, s.iv + dL + (dS / 2) * x + dC * x * x);
      });

      // Plot Smile
      const smileTraces = [
        {
          x: origStrikes,
          y: origIvs,
          mode: 'lines+markers',
          name: 'Original Baseline Smile',
          line: { color: '#8b949e', width: 2.5, dash: 'dot' }
        },
        {
          x: origStrikes,
          y: simIvs,
          mode: 'lines+markers',
          name: 'Repriced Simulated Smile',
          line: { color: '#38bdf8', width: 3.5 },
          marker: { size: 6 }
        }
      ];

      const layoutSmile = getDarkLayout('Original vs Simulated IV Smile', 'Strike Price K', 'Implied Volatility (%)');
      Plotly.react('chart-sim-smile', smileTraces, layoutSmile, { responsive: true, displayModeBar: false });

      // Reprice 100-pt Butterflies
      const S = dObj.spot + dSpot;
      const T = Math.max(1, dObj.dte) / 365.0;
      const r = 0.045;

      const origFlies = [];
      const simFlies = [];
      const flyStrikes = [];

      for (let i = 1; i < origSmile.length - 1; i++) {
        const kLow = origSmile[i-1].strike;
        const kMid = origSmile[i].strike;
        const kUpp = origSmile[i+1].strike;

        if (Math.abs((kMid - kLow) - 100) < 1 && Math.abs((kUpp - kMid) - 100) < 1) {
          const side = origSmile[i].side;
          
          // Orig price
          const pLow0 = bsPrice(side, dObj.spot, kLow, T, r, origIvs[i-1] / 100.0);
          const pMid0 = bsPrice(side, dObj.spot, kMid, T, r, origIvs[i] / 100.0);
          const pUpp0 = bsPrice(side, dObj.spot, kUpp, T, r, origIvs[i+1] / 100.0);
          const f0 = pLow0 - 2 * pMid0 + pUpp0;

          // Sim price
          const pLowSim = bsPrice(side, S, kLow, T, r, simIvs[i-1] / 100.0);
          const pMidSim = bsPrice(side, S, kMid, T, r, simIvs[i] / 100.0);
          const pUppSim = bsPrice(side, S, kUpp, T, r, simIvs[i+1] / 100.0);
          const fSim = pLowSim - 2 * pMidSim + pUppSim;

          flyStrikes.push(kMid);
          origFlies.push(f0);
          simFlies.push(fSim);
        }
      }

      const flyTraces = [
        {
          x: flyStrikes,
          y: origFlies,
          mode: 'lines+markers',
          name: 'Original Butterfly Curve',
          line: { color: '#8b949e', width: 2.5, dash: 'dot' }
        },
        {
          x: flyStrikes,
          y: simFlies,
          mode: 'lines+markers',
          name: 'Simulated Repriced Butterfly',
          line: { color: '#3fb950', width: 3.5 },
          marker: { size: 6 }
        }
      ];

      const layoutFly = getDarkLayout('Original vs Repriced 100-pt Butterfly Premium Curves', 'Centre Strike K', 'Net Premium ($)');
      Plotly.react('chart-sim-fly', flyTraces, layoutFly, { responsive: true, displayModeBar: false });
    }
  </script>
</body>
</html>
"""

output_path = workspace_dir / "spx_surface_dashboard.html"
print(f"Writing {output_path}...")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_template)

print(f"Standalone HTML generated successfully! File size: {output_path.stat().st_size / 1024:.1f} KB")
