"""Script to update generate_precalculated_html.py with the Consecutive Date Analysis tab and re-emit spx_surface_dashboard.html."""

from __future__ import annotations

import re
import sys
from pathlib import Path

file_path = Path("scratch/generate_precalculated_html.py")
content = file_path.read_text(encoding="utf-8")

# 1. Add tab button
old_nav = """      <!-- Tab Navigation Buttons -->
      <div class="tab-nav">
        <button class="tab-btn active" onclick="switchTab('tab-multidate')">
          <span>📈</span> Multi-Date Comparison
        </button>
        <button class="tab-btn" onclick="switchTab('tab-singledate')">
          <span>🔬</span> Single-Date Live Lab
        </button>
        <button class="tab-btn" onclick="switchTab('tab-math')">
          <span>📜</span> Mathematical Guide
        </button>
      </div>"""

new_nav = """      <!-- Tab Navigation Buttons -->
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
      </div>"""

assert old_nav in content, "Could not find old_nav in content"
content = content.replace(old_nav, new_nav, 1)

# 2. Add Consecutive Tab HTML before tab-singledate
tab_consec_html = """    <!-- TAB 4: CONSECUTIVE DAY ANALYSIS -->
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

"""

insert_marker = "    <!-- TAB 2: SINGLE-DATE VOLATILITY & LIVE BS PRICING LAB -->"
assert insert_marker in content, "Could not find insert_marker in content"
content = content.replace(insert_marker, tab_consec_html + insert_marker, 1)

# 3. Add JS functions for Consecutive Tab
js_consec = """
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

      // Render Table
      renderConsecTable();

      // Populate Drilldown select
      const selDrill = document.getElementById('sel-consec-drill-k');
      selDrill.innerHTML = '';
      const allCentres = Array.from(new Set([...f1Sorted.map(f => f.centre), ...f2Sorted.map(f => f.centre)])).sort((a,b) => a - b);
      allCentres.forEach(k => {
        selDrill.add(new Option(`Strike K = ${k}`, k));
      });
      if (allCentres.length > 0) {
        selDrill.value = allCentres[Math.floor(allCentres.length / 2)];
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
        <th>Strike K</th>
        <th>ATM Offset (T)</th>
        <th>Side</th>
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
        flies.forEach(f => m[f.centre] = f.prem);
        return m;
      };

      const getFlyIvMap = (smile) => {
        const m = {};
        for (let i = 1; i < smile.length - 1; i++) {
          const kL = smile[i-1].strike;
          const kM = smile[i].strike;
          const kU = smile[i+1].strike;
          if (Math.abs((kM - kL) - 100) < 1 && Math.abs((kU - kM) - 100) < 1) {
            m[kM] = smile[i-1].iv - 2 * smile[i].iv + smile[i+1].iv;
          }
        }
        return m;
      };

      const pMap1 = getFlyMap(o1);
      const pMap2 = getFlyMap(o2);
      const fIvMap1 = getFlyIvMap(o1.smile);
      const fIvMap2 = getFlyIvMap(o2.smile);

      const allStrikes = Array.from(new Set([...o1.smile.map(r => r.strike), ...o2.smile.map(r => r.strike)])).sort((a,b) => a - b);

      let bHtml = '';
      allStrikes.forEach(k => {
        const r1 = o1.smile.find(r => r.strike === k);
        const r2 = o2.smile.find(r => r.strike === k);

        const iv1 = r1 ? r1.iv : null;
        const iv2 = r2 ? r2.iv : null;
        const dIv = (iv1 !== null && iv2 !== null) ? iv2 - iv1 : null;

        const flyIv1 = fIvMap1[k] !== undefined ? fIvMap1[k] : null;
        const flyIv2 = fIvMap2[k] !== undefined ? fIvMap2[k] : null;
        const dFlyIv = (flyIv1 !== null && flyIv2 !== null) ? flyIv2 - flyIv1 : null;

        const prem1 = pMap1[k] !== undefined ? pMap1[k] : null;
        const prem2 = pMap2[k] !== undefined ? pMap2[k] : null;
        const dPrem = (prem1 !== null && prem2 !== null) ? prem2 - prem1 : null;

        const side = r1 ? r1.side.toUpperCase() : (r2 ? r2.side.toUpperCase() : '—');
        const badgeClass = side === 'CALL' ? 'badge-call' : side === 'PUT' ? 'badge-put' : 'badge-atm';
        const off = r1 ? r1.offset : (k - o1.atm_strike);

        bHtml += `<tr>
          <td><strong>${k}</strong></td>
          <td>${off >= 0 ? '+' : ''}${off} pts</td>
          <td><span class="tag-badge ${badgeClass}">${side}</span></td>
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
      const k = parseFloat(document.getElementById('sel-consec-drill-k').value);
      const o1 = DATA.dates_data[consecDate1];
      const o2 = DATA.dates_data[consecDate2];
      if (!o1 || !o2 || isNaN(k)) return;

      const kLow = k - 100;
      const kMid = k;
      const kUpp = k + 100;

      const r1Low = o1.smile.find(r => r.strike === kLow);
      const r1Mid = o1.smile.find(r => r.strike === kMid);
      const r1Upp = o1.smile.find(r => r.strike === kUpp);

      const r2Low = o2.smile.find(r => r.strike === kLow);
      const r2Mid = o2.smile.find(r => r.strike === kMid);
      const r2Upp = o2.smile.find(r => r.strike === kUpp);

      const div = document.getElementById('consec-drill-content');
      if (!r1Low || !r1Mid || !r1Upp || !r2Low || !r2Mid || !r2Upp) {
        div.innerHTML = '<p style="color: var(--text-muted); font-size: 13px;">Incomplete wing quotes at this strike.</p>';
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
            <div class="kpi-title">Lower Wing (+1): ${kLow}</div>
            <div class="kpi-value">$${r1Low.prem.toFixed(2)} &rarr; $${r2Low.prem.toFixed(2)}</div>
            <div class="kpi-sub">Δ Prem: ${(r2Low.prem - r1Low.prem >= 0 ? '+' : '')}${(r2Low.prem - r1Low.prem).toFixed(2)} | Δ IV: ${(r2Low.iv - r1Low.iv >= 0 ? '+' : '')}${(r2Low.iv - r1Low.iv).toFixed(3)} pts</div>
          </div>
          <div class="kpi-card cyan">
            <div class="kpi-title">Middle Body (−2): ${kMid}</div>
            <div class="kpi-value">$${r1Mid.prem.toFixed(2)} &rarr; $${r2Mid.prem.toFixed(2)}</div>
            <div class="kpi-sub">Δ Prem: ${(r2Mid.prem - r1Mid.prem >= 0 ? '+' : '')}${(r2Mid.prem - r1Mid.prem).toFixed(2)} | Δ IV: ${(r2Mid.iv - r1Mid.iv >= 0 ? '+' : '')}${(r2Mid.iv - r1Mid.iv).toFixed(3)} pts</div>
          </div>
          <div class="kpi-card cyan">
            <div class="kpi-title">Upper Wing (+1): ${kUpp}</div>
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
"""

# Insert js_consec before function initSimLab
init_sim_marker = "    function initSimLab() {"
assert init_sim_marker in content, "Could not find initSimLab in content"
content = content.replace(init_sim_marker, js_consec + "\n" + init_sim_marker, 1)

# In window DOMContentLoaded, add initConsecutiveWorkspace()
dom_marker = "        initSimLab();"
content = content.replace(dom_marker, "        initSimLab();\n        initConsecutiveWorkspace();", 1)

file_path.write_text(content, encoding="utf-8")
print("Updated scratch/generate_precalculated_html.py successfully!")
