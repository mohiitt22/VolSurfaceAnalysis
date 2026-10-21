/* 60DTE IV Relative-Value Desk & Historical Distribution Lab */
const $ = (id) => document.getElementById(id);
let DATA = null;
let DIST_DATA = null;
let BY_STRUCT = {};
let BY_DATE = {};
let BY_HID = {};
let CURRENT_TAB = "strategy";

function finite(x) {
  return typeof x === "number" && Number.isFinite(x);
}
function fmt(x, d = 4) {
  if (!finite(x)) return "—";
  return x.toFixed(d);
}
function pct(x) {
  if (!finite(x)) return "—";
  return (100 * x).toFixed(1) + "%";
}
function volPts(x) {
  if (!finite(x)) return "—";
  return (100 * x).toFixed(2) + " vol pts";
}

function indexRows() {
  BY_STRUCT = {};
  BY_DATE = {};
  BY_HID = {};
  for (const r of DATA.rows) {
    (BY_STRUCT[r.structure] ||= []).push(r);
    (BY_DATE[r.trade_date] ||= []).push(r);
    const hid = r.history_id || r.structure;
    (BY_HID[hid] ||= []).push(r);
  }
}

/* ==================== STRATEGY DESK LOGIC (PRESERVED & EXTENDED) ==================== */
function decisionOf(row, zGate) {
  const reasons = [];
  const votes = {
    structural: "undecided",
    historical60: "undecided",
    historical20: "undecided",
    historical120: "undecided",
    level: "undecided",
  };
  if (!row) {
    return {
      label: "CANNOT DECIDE",
      cls: "undecided",
      direction: "",
      why: "No observation for this date / structure.",
      reasons: ["missing_row"],
      votes,
    };
  }
  const z = row.z_60_residual;
  const res = row.residual;
  const z20 = row.z_20_residual;
  const z120 = row.z_120_residual;
  votes.structural = !finite(res) ? "undecided" : res < 0 ? "cheap" : res > 0 ? "expensive" : "undecided";
  votes.historical60 = !finite(z) ? "undecided" : z <= -zGate ? "cheap" : z >= zGate ? "expensive" : "undecided";
  votes.historical20 = !finite(z20) ? "undecided" : z20 <= -zGate ? "cheap" : z20 >= zGate ? "expensive" : "undecided";
  votes.historical120 = !finite(z120) ? "undecided" : z120 <= -zGate ? "cheap" : z120 >= zGate ? "expensive" : "undecided";
  votes.level = !finite(row.z_60_market_value)
    ? "undecided"
    : row.z_60_market_value <= -zGate
      ? "cheap"
      : row.z_60_market_value >= zGate
        ? "expensive"
        : "undecided";

  if (row.extrapolated) reasons.push("Delta was extrapolated — cannot treat this as a clean reading.");
  if (!finite(res)) reasons.push("Market or fair value is missing, so there is no residual.");
  if (!finite(z)) reasons.push("Not enough history for a 60-day residual z-score.");
  else if (Math.abs(z) < zGate) reasons.push(`|z_60| = ${z.toFixed(2)} is below the ${zGate} gate.`);
  if (finite(res) && finite(z) && Math.sign(res) !== 0 && Math.sign(z) !== 0 && Math.sign(res) !== Math.sign(z)) {
    reasons.push("Structural residual and historical z disagree on direction.");
  }
  if (finite(row.actual_dte) && Math.abs(row.actual_dte - 60) >= 6) {
    reasons.push(`DTE is ${row.actual_dte}, far from the 60-day target (warning only).`);
  }
  if (row.kind === "listed_strike") {
    reasons.push(`Listed-strike z uses log-moneyness bin ${row.history_id || "—"}, not raw strike over time.`);
  }

  const signConflict =
    finite(res) && finite(z) && Math.sign(res) !== 0 && Math.sign(z) !== 0 && Math.sign(res) !== Math.sign(z);
  const direction = votes.structural === "cheap" ? "CHEAP" : votes.structural === "expensive" ? "EXPENSIVE" : "";

  if (row.extrapolated || !finite(z) || !finite(res) || signConflict) {
    return {
      label: "CANNOT DECIDE",
      cls: "undecided",
      direction,
      why: signConflict
        ? "Residual and z-score point in opposite directions, so the book will not take a side."
        : row.extrapolated
          ? "The smile point was extrapolated, so this is not a usable trade reading."
          : "History or the residual is missing, so the book cannot decide.",
      reasons,
      votes,
    };
  }
  if (Math.abs(z) < zGate) {
    return {
      label: "NO TRADE",
      cls: "notrade",
      direction,
      why: `The reading is clean, but |z_60| = ${z.toFixed(2)} is inside the ${zGate} gate, so this is not a trade.`,
      reasons,
      votes,
    };
  }
  return {
    label: "TRADE",
    cls: direction === "EXPENSIVE" ? "trade-exp" : "trade",
    direction,
    why:
      direction === "EXPENSIVE"
        ? "Market is above ensemble fair and the residual is historically high enough to clear the gate."
        : "Market is below ensemble fair and the residual is historically low enough to clear the gate.",
    reasons,
    votes,
  };
}

function rowsFor(structure) {
  return BY_STRUCT[structure] || [];
}
function chartSeries(structure) {
  const own = rowsFor(structure);
  const sample = own[0];
  if (sample && sample.kind === "listed_strike" && sample.history_id) {
    return (BY_HID[sample.history_id] || []).filter((r) => r.kind === "kbin" && finite(r.market_value));
  }
  return own.filter((r) => finite(r.market_value));
}
function rowOn(structure, date) {
  const list = BY_STRUCT[structure] || [];
  return list.find((r) => r.trade_date === date);
}
function catalogItem(structure) {
  return DATA.catalog.find((c) => c.structure === structure) || rowsFor(structure)[0] || null;
}
function dteOn(date) {
  return DATA.dte.find((d) => d.trade_date === date);
}
function statsOf(structure) {
  return DATA.stats.find((s) => s.structure === structure);
}

function kindOptions() {
  const fromCat = DATA.catalog.map((c) => c.kind);
  return ["all", ...new Set(["risk_reversal", "butterfly", "slope", "point", "kbin", "listed_strike", ...fromCat])];
}

function fillSelects() {
  $("kind").innerHTML = kindOptions()
    .map((k) => `<option value="${k}">${k}</option>`)
    .join("");
  $("date").min = DATA.dates[0];
  $("date").max = DATA.dates[DATA.dates.length - 1];
  $("date").value = DATA.meta.test_date;
  refreshStructures();
  $("compare").innerHTML =
    `<option value="">— none —</option>` +
    DATA.catalog.map((c) => `<option value="${c.structure}">${c.structure}</option>`).join("");
}

function structuresForKind(kind, date) {
  if (kind === "listed_strike") {
    const day = BY_DATE[date] || [];
    const seen = new Map();
    for (const r of day) {
      if (r.kind === "listed_strike") seen.set(r.structure, r);
    }
    return [...seen.values()].sort((a, b) => (a.strike || 0) - (b.strike || 0));
  }
  return DATA.catalog.filter((c) => kind === "all" || c.kind === kind);
}

function refreshStructures() {
  const kind = $("kind").value;
  const date = $("date").value || DATA.meta.test_date;
  const list = structuresForKind(kind, date);
  const prev = $("structure").value;
  $("structure").innerHTML = list
    .map((c) => `<option value="${c.structure}">${c.structure} · ${c.legs || c.kind}</option>`)
    .join("");
  if (list.some((c) => c.structure === prev)) $("structure").value = prev;
}

function pill(v) {
  const extra = v.direction && v.label === "TRADE" ? ` ${v.direction}` : "";
  return `<span class="pill ${v.cls}">${v.label}${extra}</span>`;
}

function renderMeta() {
  const m = DATA.meta;
  $("metaBadges").innerHTML = [
    ["Research end", m.train_end],
    ["Holdout", m.test_date],
    ["Dates", String(m.n_dates)],
    ["Latest Data", DATA.dates[DATA.dates.length - 1]],
    ["Named structures", String(m.n_named || m.n_structures)],
    ["Frozen z", String(m.frozen_z)],
  ]
    .map(([k, v]) => `<div class="badge">${k}<b>${v}</b></div>`)
    .join("");
}

function countDecisions(date, zGate) {
  const rows = BY_DATE[date] || [];
  const out = { TRADE: 0, "NO TRADE": 0, "CANNOT DECIDE": 0, byKind: {} };
  for (const r of rows) {
    const v = decisionOf(r, zGate);
    out[v.label] += 1;
    const k = r.kind || "other";
    out.byKind[k] ||= { TRADE: 0, "NO TRADE": 0, "CANNOT DECIDE": 0 };
    out.byKind[k][v.label] += 1;
  }
  return out;
}

function renderCounts(date, zGate) {
  const c = countDecisions(date, zGate);
  const kinds = Object.keys(c.byKind).sort();
  const chips = [
    `<div class="count trade"><b>${c.TRADE}</b>TRADE</div>`,
    `<div class="count notrade"><b>${c["NO TRADE"]}</b>NO TRADE</div>`,
    `<div class="count undecided"><b>${c["CANNOT DECIDE"]}</b>CANNOT DECIDE</div>`,
  ];
  const byKind = kinds
    .map((k) => {
      const x = c.byKind[k];
      return `<div class="count muted"><span class="count-name">${k}</span><b>${x.TRADE}</b><span>T · ${x["NO TRADE"]} N · ${x["CANNOT DECIDE"]} C</span></div>`;
    })
    .join("");
  $("countStrip").innerHTML = chips.join("") + byKind;
}

function renderPostHoldoutChips(activeDate) {
  const postDates = DATA.dates.filter((d) => d >= DATA.meta.test_date);
  $("postHoldoutChips").innerHTML = postDates
    .map((d) => {
      const isHoldout = d === DATA.meta.test_date;
      const isLatest = d === postDates[postDates.length - 1];
      const label = isHoldout ? `${d.slice(5)} (Holdout)` : isLatest ? `${d.slice(5)} (Latest)` : d.slice(5);
      const activeCls = d === activeDate ? "active" : "";
      const holdCls = isHoldout ? "holdout-chip" : "";
      return `<button type="button" class="date-chip ${holdCls} ${activeCls}" data-date="${d}">${label}</button>`;
    })
    .join("");

  $("postHoldoutChips").querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const d = btn.getAttribute("data-date");
      $("date").value = d;
      refreshStructures();
      render();
    });
  });
}

function render() {
  const structure = $("structure").value;
  const date = $("date").value;
  const zGate = Number($("zGate").value);
  const row = rowOn(structure, date);
  const v = decisionOf(row, zGate);
  const cat = catalogItem(structure);
  const dte = dteOn(date);
  const hist = statsOf(structure);

  const kicker = $("verdictKicker");
  if (kicker) {
    kicker.textContent =
      date === DATA.meta.test_date
        ? "Frozen holdout (11 Sep 2026)"
        : date > DATA.meta.test_date
          ? `Out-of-sample evaluation (${date})`
          : `Research period (${date})`;
  }

  $("verdictLabel").textContent = v.label;
  $("verdictLabel").className = "verdict " + v.cls;
  $("verdictDir").textContent = v.direction ? `Direction vs fair: ${v.direction}` : "";
  $("verdictWhy").textContent = v.why;
  $("verdictReasons").innerHTML = v.reasons.map((r) => `<li>${r}</li>`).join("");

  const defs = [
    ["Structural (vs ensemble)", v.votes.structural, row ? `residual ${fmt(row.residual, 5)}` : ""],
    ["Historical residual z60", v.votes.historical60, row ? `z=${fmt(row.z_60_residual, 2)}  pct=${fmt(row.pct_60_residual, 2)}` : ""],
    ["Short window z20", v.votes.historical20, row ? `z=${fmt(row.z_20_residual, 2)}` : ""],
    ["Long window z120", v.votes.historical120, row ? `z=${fmt(row.z_120_residual, 2)}` : ""],
    ["Level vs own history", v.votes.level, row ? `z_mkt=${fmt(row.z_60_market_value, 2)}` : ""],
  ];
  $("defCards").innerHTML = defs
    .map(([name, lab, detail]) => {
      const cls = lab || "undecided";
      const title = cls === "cheap" ? "CHEAP" : cls === "expensive" ? "EXPENSIVE" : "CANNOT DECIDE";
      return `<div class="def ${cls}"><div class="name">${name}</div><div class="val">${title}</div><div class="detail">${detail}</div></div>`;
    })
    .join("");

  const snap = [
    ["Structure", `${structure}`],
    ["Kind / legs", `${cat?.kind || ""} · ${cat?.legs || row?.legs || ""}`],
    ["History id", row?.history_id || structure],
    ["Market value", finite(row?.market_value) ? `${fmt(row.market_value, 4)}  (${volPts(row.market_value)})` : "—"],
    ["Ensemble fair", fmt(row?.fair_value, 4)],
    ["IV residual", fmt(row?.residual, 5)],
    ["z20 / z60 / z120 / z252", `${fmt(row?.z_20_residual, 2)} / ${fmt(row?.z_60_residual, 2)} / ${fmt(row?.z_120_residual, 2)} / ${fmt(row?.z_252_residual, 2)}`],
    ["60d percentile", fmt(row?.pct_60_residual, 2)],
    ["Extrapolated?", row?.extrapolated ? "YES" : "no"],
    ["Date Role", date === DATA.meta.test_date ? "Frozen holdout (signals only)" : date > DATA.meta.test_date ? "Post-holdout test evaluation" : "In-sample research"],
  ];
  $("snapTable").innerHTML = snap.map(([k, val]) => `<tr><th>${k}</th><td>${val}</td></tr>`).join("");

  const regime = [
    ["Selected expiry", dte?.selected_expiry || "—"],
    ["Contract", dte?.contract || "—"],
    ["Actual DTE", dte ? `${dte.actual_dte} (error ${dte.dte_error})` : "—"],
    ["Spot / forward", `${fmt(row?.spot_x, 2)} / ${fmt(row?.forward, 2)}`],
    ["ATM IV", volPts(row?.atm_iv)],
    ["Strike / k", row?.strike != null ? `${fmt(row.strike, 0)} / ${fmt(row.k, 3)}` : "—"],
    ["Put-delta convention", dte?.put_delta_convention || "—"],
  ];
  $("regimeTable").innerHTML = regime.map(([k, val]) => `<tr><th>${k}</th><td>${val}</td></tr>`).join("");

  const hs = [
    ["Research observations", hist ? String(hist.n) : "—"],
    ["Mean |residual|", hist ? fmt(hist.mean_abs_residual, 5) : "—"],
    ["Share |z60|≥1.5", hist ? pct(hist.share_z60_ge_15) : "—"],
    ["Share |z60|≥3.0", hist ? pct(hist.share_z60_ge_30) : "—"],
    ["Interpretation", hist && (hist.share_z60_ge_30 || 0) < 0.02
      ? "This name rarely clears the frozen 3.0 gate — most days will be NO TRADE."
      : "See the share of extreme days; do not assume tradability."],
  ];
  $("histTable").innerHTML = hs.map(([k, val]) => `<tr><th>${k}</th><td>${val}</td></tr>`).join("");

  renderCounts(date, zGate);
  drawChart(structure, date, $("compare").value);
  renderCross(date, zGate, structure);
  renderPostHoldoutChips(date);
  renderForwardTracker(structure, date, zGate);
  renderPostHoldoutScanner(zGate);
}

function drawChart(structure, date, compare) {
  const canvas = $("chart");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const series = chartSeries(structure);
  if (!series.length) return;
  const dates = series.map((r) => r.trade_date);
  const y1 = series.map((r) => r.market_value);
  const y2 = series.map((r) => r.fair_value);
  const allY = [...y1, ...y2.filter(finite)];
  const ymin = Math.min(...allY);
  const ymax = Math.max(...allY);
  const pad = { l: 48, r: 16, t: 16, b: 28 };
  const xAt = (i) => pad.l + (i / Math.max(series.length - 1, 1)) * (w - pad.l - pad.r);
  const yAt = (v) => pad.t + (1 - (v - ymin) / (ymax - ymin || 1)) * (h - pad.t - pad.b);

  ctx.strokeStyle = "#2a2f36";
  ctx.beginPath();
  ctx.moveTo(pad.l, pad.t);
  ctx.lineTo(pad.l, h - pad.b);
  ctx.lineTo(w - pad.r, h - pad.b);
  ctx.stroke();

  function line(vals, color, dash) {
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.setLineDash(dash || []);
    let started = false;
    vals.forEach((v, i) => {
      if (!finite(v)) return;
      const x = xAt(i);
      const y = yAt(v);
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.setLineDash([]);
  }
  line(y1, "#e8eaed");
  line(y2, "#7aa2f7", [4, 4]);
  if (compare) {
    const other = rowsFor(compare);
    const map = Object.fromEntries(other.map((r) => [r.trade_date, r.market_value]));
    line(dates.map((d) => map[d]), "#c9a227");
  }

  const idx = dates.indexOf(date);
  if (idx >= 0) {
    ctx.strokeStyle = "#8b7cf7";
    ctx.beginPath();
    ctx.moveTo(xAt(idx), pad.t);
    ctx.lineTo(xAt(idx), h - pad.b);
    ctx.stroke();
  }
  ctx.fillStyle = "#9aa3ad";
  ctx.font = "11px Segoe UI";
  ctx.textAlign = "left";
  ctx.fillText(dates[0], pad.l, h - 8);
  ctx.textAlign = "right";
  ctx.fillText(dates[dates.length - 1], w - pad.r, h - 8);
  ctx.textAlign = "right";
  ctx.fillText(fmt(ymax, 3), pad.l - 6, pad.t + 10);
  ctx.fillText(fmt(ymin, 3), pad.l - 6, h - pad.b);
  ctx.textAlign = "left";
  const own = rowsFor(structure)[0];
  const hidNote = own && own.kind === "listed_strike" ? ` Chart is the ${own.history_id} k-bin path used for z.` : "";
  $("chartCaption").textContent = compare
    ? `${structure} market (white) vs ensemble fair (blue dashed) vs ${compare} market (gold)`
    : `${structure} market (white) vs ensemble fair (blue dashed). Purple line = selected date.${hidNote}`;
}

/* ==================== FORWARD EVOLUTION & MARKET CORRECTION TRACKER ==================== */
function renderForwardTracker(structure, selectedDate, zGate) {
  const fwdLabel = $("fwdStructLabel");
  const fwdStart = $("fwdStartLabel");
  if (fwdLabel) fwdLabel.textContent = structure;
  if (fwdStart) fwdStart.textContent = selectedDate;

  // Filter all observations of this structure from selectedDate forward
  const allRows = rowsFor(structure);
  const fwdRows = allRows
    .filter((r) => r.trade_date >= selectedDate)
    .sort((a, b) => a.trade_date.localeCompare(b.trade_date));

  if (!fwdRows.length) {
    $("fwdKpis").innerHTML = `<div class="fwd-card" style="grid-column: 1/-1"><div class="fwd-card-sub">No observations found for ${structure} from ${selectedDate} onward.</div></div>`;
    $("fwdTableBody").innerHTML = `<tr><td colspan="10" style="text-align:center;padding:16px;color:var(--muted)">No forward observations available.</td></tr>`;
    return;
  }

  const baseRow = fwdRows[0];
  const baseResid = baseRow.residual;
  const baseResidBp = finite(baseResid) ? baseResid * 10000 : 0;
  const baseZ = baseRow.z_60_residual;
  const baseDec = decisionOf(baseRow, zGate);

  // Compute forward statistics
  let maxFadeBp = 0;
  let maxFadePct = 0;
  let latestRec = fwdRows[fwdRows.length - 1];

  const processedFwd = fwdRows.map((r, i) => {
    const curResid = r.residual;
    const curResidBp = finite(curResid) ? curResid * 10000 : 0;
    const deltaResidBp = curResidBp - baseResidBp;
    const z = r.z_60_residual;
    const dec = decisionOf(r, zGate);

    // Convergence = shrinkage of residual magnitude towards fair value (0)
    let convergenceBp = 0;
    let convergencePct = 0;
    if (Math.abs(baseResidBp) > 1e-4) {
      if (baseResidBp > 0) {
        convergenceBp = -deltaResidBp;
        convergencePct = (convergenceBp / baseResidBp) * 100;
      } else {
        convergenceBp = deltaResidBp;
        convergencePct = (convergenceBp / Math.abs(baseResidBp)) * 100;
      }
    }

    if (i > 0 && convergenceBp > maxFadeBp) {
      maxFadeBp = convergenceBp;
      maxFadePct = convergencePct;
    }

    // Status classification
    let statusText = "Observation Base (Day 0)";
    let statusCls = "neutral";
    if (i > 0) {
      if (Math.abs(curResidBp) <= 1.0 || (baseResidBp !== 0 && Math.sign(curResidBp) !== Math.sign(baseResidBp))) {
        statusText = "✅ Reverted to Fair / Converged";
        statusCls = "faded-full";
      } else if (convergencePct >= 50) {
        statusText = `⚡ Substantial Fade (${convergencePct.toFixed(0)}%)`;
        statusCls = "faded-full";
      } else if (convergencePct > 0) {
        statusText = `📈 Partial Fade (${convergencePct.toFixed(0)}%)`;
        statusCls = "faded-part";
      } else if (convergencePct <= -50) {
        statusText = `❌ Widened (${Math.abs(convergencePct).toFixed(0)}%)`;
        statusCls = "widened";
      } else {
        statusText = `⚠️ Persistent Dislocation`;
        statusCls = "persisted";
      }
    }

    return {
      r,
      i,
      date: r.trade_date,
      curResidBp,
      deltaResidBp,
      convergenceBp,
      convergencePct,
      z,
      dec,
      statusText,
      statusCls,
    };
  });

  // Overall verdict for the structure over the period
  const finalItem = processedFwd[processedFwd.length - 1];
  let overallVerdict = "Stable / Near Fair";
  let overallBadgeCls = "neutral";
  if (Math.abs(baseResidBp) > 1.5) {
    if (finalItem.convergencePct >= 60 || Math.abs(finalItem.curResidBp) <= 1.5) {
      overallVerdict = `Market Corrected (${maxFadeBp >= 0 ? "+" : ""}${maxFadeBp.toFixed(1)} bp Fade)`;
      overallBadgeCls = "faded";
    } else if (finalItem.convergencePct < 0) {
      overallVerdict = `Dislocation Persisted / Widened`;
      overallBadgeCls = "widened";
    } else {
      overallVerdict = `Partial Mean-Reversion (${finalItem.convergencePct.toFixed(0)}%)`;
      overallBadgeCls = "faded";
    }
  }

  $("fwdSummaryBadge").innerHTML = `<span class="fwd-badge ${overallBadgeCls}">${overallVerdict}</span>`;

  // Populate Forward KPI cards
  const baseZStr = finite(baseZ) ? (baseZ >= 0 ? "+" : "") + baseZ.toFixed(2) + " σ" : "—";
  $("fwdKpis").innerHTML = `
    <div class="fwd-card">
      <div class="fwd-card-title">Initial Dislocation (${selectedDate})</div>
      <div class="fwd-card-val">${baseResidBp >= 0 ? "+" : ""}${baseResidBp.toFixed(1)} bp</div>
      <div class="fwd-card-sub">z_60: <b>${baseZStr}</b> &middot; Gate ${zGate}: <b>${baseDec.label}</b></div>
    </div>
    <div class="fwd-card">
      <div class="fwd-card-title">Max Forward Fade / Correction</div>
      <div class="fwd-card-val" style="color:var(--cheap)">${maxFadeBp >= 0 ? "+" : ""}${maxFadeBp.toFixed(1)} bp</div>
      <div class="fwd-card-sub">Faded <b>${maxFadePct.toFixed(1)}%</b> of edge towards fair value</div>
    </div>
    <div class="fwd-card">
      <div class="fwd-card-title">Latest State (${latestRec.trade_date})</div>
      <div class="fwd-card-val">${(latestRec.residual * 10000 >= 0 ? "+" : "") + (latestRec.residual * 10000).toFixed(1)} bp</div>
      <div class="fwd-card-sub">Latest z_60: <b>${finite(latestRec.z_60_residual) ? latestRec.z_60_residual.toFixed(2) : "—"}</b> &middot; <b>${decisionOf(latestRec, zGate).label}</b></div>
    </div>
    <div class="fwd-card">
      <div class="fwd-card-title">Forward Path Horizons</div>
      <div class="fwd-card-val highlight-accent">${fwdRows.length - 1} <span style="font-size:13px;font-weight:400;color:var(--muted)">forward days</span></div>
      <div class="fwd-card-sub">${selectedDate} &rarr; ${latestRec.trade_date}</div>
    </div>
  `;

  // Draw Forward Chart
  drawForwardTrackerChart(structure, selectedDate, zGate, processedFwd);

  // Populate Forward Tracking Table
  $("fwdTableBody").innerHTML = processedFwd
    .map((item) => {
      const horizon = item.i === 0 ? "Day 0 (Start)" : `+${item.i} trading day${item.i > 1 ? "s" : ""}`;
      const changeStr = item.i === 0 ? "—" : (item.deltaResidBp >= 0 ? "+" : "") + item.deltaResidBp.toFixed(2) + " bp";
      const convStr = item.i === 0 ? "—" : (item.convergenceBp >= 0 ? "+" : "") + item.convergenceBp.toFixed(2) + " bp (" + item.convergencePct.toFixed(0) + "%)";
      const zStr = finite(item.z) ? item.z.toFixed(2) : "—";
      const isStart = item.i === 0;

      return `
        <tr data-date="${item.date}" class="${isStart ? "active" : ""}">
          <td><b>${horizon}</b></td>
          <td><b>${item.date}</b></td>
          <td>${fmt(item.r.market_value, 4)}</td>
          <td>${fmt(item.r.fair_value, 4)}</td>
          <td><b style="color:#fff">${(item.curResidBp >= 0 ? "+" : "") + item.curResidBp.toFixed(1)} bp</b></td>
          <td style="color:${item.deltaResidBp <= 0 ? "var(--cheap)" : "var(--exp)"}">${changeStr}</td>
          <td>${convStr}</td>
          <td>${zStr}</td>
          <td>${pill(item.dec)}</td>
          <td><span class="fwd-pill ${item.statusCls}">${item.statusText}</span></td>
        </tr>
      `;
    })
    .join("");

  $("fwdTableBody").querySelectorAll("tr").forEach((tr) => {
    tr.addEventListener("click", () => {
      const d = tr.getAttribute("data-date");
      $("date").value = d;
      refreshStructures();
      render();
    });
  });
}

function drawForwardTrackerChart(structure, selectedDate, zGate, processedFwd) {
  const canvas = $("fwdChart");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  if (processedFwd.length < 2) {
    ctx.fillStyle = "#8b949e";
    ctx.font = "13px sans-serif";
    ctx.fillText("Select an earlier date to view forward tracking (at least 2 days needed).", 60, h / 2);
    return;
  }

  const resids = processedFwd.map((x) => x.curResidBp);
  const zs = processedFwd.map((x) => x.z || 0);
  const dates = processedFwd.map((x) => x.date);

  const maxRes = Math.max(...resids, 2.0);
  const minRes = Math.min(...resids, -2.0);
  const boundRes = Math.max(Math.abs(maxRes), Math.abs(minRes)) * 1.25;

  const pad = { l: 56, r: 24, t: 26, b: 34 };
  const xAt = (i) => pad.l + (i / Math.max(processedFwd.length - 1, 1)) * (w - pad.l - pad.r);
  const yResAt = (v) => pad.t + (1 - (v - (-boundRes)) / (2 * boundRes || 1)) * (h - pad.t - pad.b);

  // Background Grid & Zero Fair Line
  const yZero = yResAt(0);
  ctx.strokeStyle = "rgba(48, 54, 61, 0.5)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad.l, pad.t);
  ctx.lineTo(w - pad.r, pad.t);
  ctx.moveTo(pad.l, h - pad.b);
  ctx.lineTo(w - pad.r, h - pad.b);
  ctx.stroke();

  // Zero Fair Value Line (Cyan dashed)
  ctx.strokeStyle = "#39c5cf";
  ctx.setLineDash([4, 4]);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(pad.l, yZero);
  ctx.lineTo(w - pad.r, yZero);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = "#39c5cf";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "right";
  ctx.fillText("Fair (0 bp)", pad.l - 6, yZero + 4);

  // Shaded positive/negative zones
  ctx.fillStyle = "rgba(248, 81, 73, 0.04)";
  ctx.fillRect(pad.l, pad.t, w - pad.l - pad.r, yZero - pad.t);
  ctx.fillStyle = "rgba(61, 186, 122, 0.04)";
  ctx.fillRect(pad.l, yZero, w - pad.l - pad.r, h - pad.b - yZero);

  // Residual Path Line
  ctx.strokeStyle = "#58a6ff";
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  processedFwd.forEach((item, i) => {
    const x = xAt(i);
    const y = yResAt(item.curResidBp);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Draw points with outcome color
  processedFwd.forEach((item, i) => {
    const x = xAt(i);
    const y = yResAt(item.curResidBp);

    ctx.fillStyle = item.dec.label === "TRADE"
      ? (item.dec.direction === "EXPENSIVE" ? "#f85149" : "#3dba7a")
      : (i === 0 ? "#bc8cff" : "#8b949e");

    ctx.beginPath();
    ctx.arc(x, y, i === 0 ? 6.5 : 4.5, 0, 2 * Math.PI);
    ctx.fill();

    if (i === 0) {
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.stroke();
    }

  });

  // Value labels only where they have room, so neighbouring prints do not stack.
  ctx.fillStyle = "#fff";
  ctx.font = "10.5px sans-serif";
  ctx.textAlign = "center";
  let lastLabelX = -1e9;
  processedFwd.forEach((item, i) => {
    const x = xAt(i);
    const end = i === 0 || i === processedFwd.length - 1;
    if (!end && x - lastLabelX < 42) return;
    const y = yResAt(item.curResidBp);
    const textY = item.curResidBp >= 0 ? y - 10 : y + 16;
    ctx.fillText(`${item.curResidBp >= 0 ? "+" : ""}${item.curResidBp.toFixed(1)}bp`, x, textY);
    lastLabelX = x;
  });

  // X axis: first, last, and dates that clear the previous label.
  ctx.fillStyle = "#8b949e";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "center";
  let lastDateX = -1e9;
  processedFwd.forEach((item, i) => {
    const x = xAt(i);
    const end = i === 0 || i === processedFwd.length - 1;
    if (!end && x - lastDateX < 48) return;
    ctx.fillText(item.date.slice(5), x, h - 12);
    lastDateX = x;
  });
}

/* ==================== POST-HOLDOUT TRADE SCANNER ==================== */
function renderPostHoldoutScanner(zGate) {
  const postDates = DATA.dates.filter((d) => d >= DATA.meta.test_date);
  const tbody = $("postHoldoutTableBody");
  if (!tbody) return;

  const rowsData = postDates.map((d) => {
    const dayRows = BY_DATE[d] || [];
    let trades = 0, notrades = 0, cannots = 0;
    let topCheap = null, topExp = null;
    let maxAbsZ = 0;

    for (const r of dayRows) {
      const v = decisionOf(r, zGate);
      if (v.label === "TRADE") trades++;
      else if (v.label === "NO TRADE") notrades++;
      else cannots++;

      if (finite(r.z_60_residual)) {
        const az = Math.abs(r.z_60_residual);
        if (az > maxAbsZ) maxAbsZ = az;
        if (topCheap === null || r.z_60_residual < topCheap.z_60_residual) topCheap = r;
        if (topExp === null || r.z_60_residual > topExp.z_60_residual) topExp = r;
      }
    }

    const isHoldout = d === DATA.meta.test_date;
    const roleText = isHoldout ? "Frozen Holdout" : "Out-of-sample Test";

    return {
      date: d,
      roleText,
      total: dayRows.length,
      trades,
      notrades,
      cannots,
      maxAbsZ,
      topCheap,
      topExp,
    };
  });

  tbody.innerHTML = rowsData
    .map((x) => {
      const cheapStr = x.topCheap ? `${x.topCheap.structure} (z=${x.topCheap.z_60_residual.toFixed(2)})` : "—";
      const expStr = x.topExp ? `${x.topExp.structure} (z=+${x.topExp.z_60_residual.toFixed(2)})` : "—";
      const tradeBadge = x.trades > 0
        ? `<span class="pill trade">${x.trades} TRADE${x.trades > 1 ? "S" : ""}</span>`
        : `<span class="pill notrade">0 TRADES</span>`;

      return `
        <tr data-date="${x.date}" class="${x.date === $("date").value ? "active" : ""}">
          <td><b>${x.date}</b></td>
          <td><span style="color:${x.date === DATA.meta.test_date ? "var(--hold)" : "var(--muted)"}">${x.roleText}</span></td>
          <td>${x.total}</td>
          <td>${tradeBadge}</td>
          <td style="color:var(--cheap)">${cheapStr}</td>
          <td style="color:var(--exp)">${expStr}</td>
          <td><b>${x.maxAbsZ.toFixed(2)} σ</b></td>
          <td><button type="button" class="btn-inspect" data-date="${x.date}">Inspect Date</button></td>
        </tr>
      `;
    })
    .join("");

  tbody.querySelectorAll("tr").forEach((tr) => {
    tr.addEventListener("click", () => {
      const d = tr.getAttribute("data-date");
      $("date").value = d;
      refreshStructures();
      render();
    });
  });
}

function renderCross(date, zGate, active) {
  const showListed = $("showListed").checked;
  const kind = $("kind").value;
  const want = $("decisionFilter").value;
  const q = ($("crossSearch").value || "").trim().toLowerCase();
  let rows = (BY_DATE[date] || []).filter((r) => {
    if (!showListed && r.kind === "listed_strike") return false;
    if (kind !== "all" && r.kind !== kind) return false;
    if (q && !(r.structure || "").toLowerCase().includes(q) && !(r.legs || "").toLowerCase().includes(q)) return false;
    return true;
  });
  const scored = rows.map((r) => {
    const v = decisionOf(r, zGate);
    return { r, v, az: finite(r.z_60_residual) ? Math.abs(r.z_60_residual) : -1 };
  });
  const rank = { TRADE: 0, "NO TRADE": 1, "CANNOT DECIDE": 2 };
  scored.sort((a, b) => (rank[a.v.label] - rank[b.v.label]) || (b.az - a.az));
  const filtered = want === "all" ? scored : scored.filter((x) => x.v.label === want);

  const head = ["Structure", "Kind", "Legs", "Market", "Fair", "Residual", "z60", "Decision"];
  $("crossTable").querySelector("thead").innerHTML =
    "<tr>" + head.map((h) => `<th>${h}</th>`).join("") + "</tr>";
  $("crossTable").querySelector("tbody").innerHTML = filtered
    .map(({ r, v }) => `<tr data-s="${r.structure}" data-k="${r.kind}" class="${r.structure === active ? "active" : ""}">
        <td>${r.structure}</td>
        <td>${r.kind}</td>
        <td>${r.legs || ""}</td>
        <td>${fmt(r.market_value, 4)}</td>
        <td>${fmt(r.fair_value, 4)}</td>
        <td>${fmt(r.residual, 5)}</td>
        <td>${fmt(r.z_60_residual, 2)}</td>
        <td>${pill(v)}</td>
      </tr>`)
    .join("");
  $("crossTable").querySelectorAll("tbody tr").forEach((tr) => {
    tr.addEventListener("click", () => {
      const s = tr.getAttribute("data-s");
      const k = tr.getAttribute("data-k");
      $("kind").value = k || "all";
      refreshStructures();
      if (![...$("structure").options].some((o) => o.value === s)) {
        const opt = document.createElement("option");
        opt.value = s;
        opt.textContent = s;
        $("structure").appendChild(opt);
      }
      $("structure").value = s;
      render();
    });
  });
}

function renderWF() {
  if (!DATA.walkforward?.length) return;
  const cols = Object.keys(DATA.walkforward[0]);
  $("wfTable").querySelector("thead").innerHTML =
    "<tr>" + cols.map((c) => `<th>${c}</th>`).join("") + "</tr>";
  $("wfTable").querySelector("tbody").innerHTML = DATA.walkforward
    .map((r) => "<tr>" + cols.map((c) => `<td>${typeof r[c] === "number" ? fmt(r[c], 3) : r[c]}</td>`).join("") + "</tr>")
    .join("");
}

/* ==================== VIEW 2: HISTORICAL DISTRIBUTION LAB ==================== */
function computeCausalSeries(structure, metric = "market_value", windowType = "expanding") {
  if (DIST_DATA?.structures?.[structure]?.[metric]) {
    const list = DIST_DATA.structures[structure][metric];
    if (windowType === "expanding") return list;
    return list.map((r) => ({
      ...r,
      mean_prior: windowType === "rolling60" ? r.rolling60_mean : r.rolling120_mean,
      std_prior: windowType === "rolling60" ? r.rolling60_std : r.rolling120_std,
      z_score: windowType === "rolling60" ? r.rolling60_z : r.rolling120_z,
      percentile_rank: windowType === "rolling60" ? r.rolling60_pct : r.rolling120_pct,
    }));
  }

  const rawRows = (BY_STRUCT[structure] || []).filter((r) => finite(r[metric])).sort((a, b) => a.trade_date.localeCompare(b.trade_date));
  const result = [];
  const history = [];

  for (const r of rawRows) {
    const val = r[metric];
    const n = history.length;
    let mean = null, std = null, z = null, pctRank = null;
    let minP = null, maxP = null, medP = null;

    if (n >= 10) {
      let ref = history;
      if (windowType === "rolling60" && n >= 15) ref = history.slice(-60);
      else if (windowType === "rolling120" && n >= 30) ref = history.slice(-120);

      const sum = ref.reduce((a, b) => a + b, 0);
      mean = sum / ref.length;
      const variance = ref.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / (ref.length - 1);
      std = Math.sqrt(variance);
      z = std > 1e-8 ? (val - mean) / std : 0;
      const countBelow = ref.filter((x) => x <= val).length;
      pctRank = (countBelow / ref.length) * 100;

      const sortedRef = [...ref].sort((a, b) => a - b);
      minP = sortedRef[0];
      maxP = sortedRef[sortedRef.length - 1];
      medP = sortedRef[Math.floor(sortedRef.length / 2)];
    }

    result.push({
      trade_date: r.trade_date,
      structure,
      value: val,
      value_vol_pts: val * 100,
      actual_dte: r.actual_dte,
      spot: r.spot_x,
      forward: r.forward,
      residual: r.residual,
      n_prior: n,
      prior_start: history.length ? rawRows[0].trade_date : null,
      prior_end: history.length ? rawRows[n - 1].trade_date : null,
      mean_prior: mean,
      std_prior: std,
      z_score: z,
      percentile_rank: pctRank,
      min_prior: minP,
      median_prior: medP,
      max_prior: maxP,
      prior_values: [...history],
    });

    history.push(val);
  }
  return result;
}

let DIST_ACTIVE_FILTER = "aug_sep"; // aug_sep | aug | sep | all

function getFilteredDistDates(series) {
  if (DIST_ACTIVE_FILTER === "aug") {
    return series.filter((r) => r.trade_date.startsWith("2026-08"));
  }
  if (DIST_ACTIVE_FILTER === "sep") {
    return series.filter((r) => r.trade_date.startsWith("2026-09"));
  }
  if (DIST_ACTIVE_FILTER === "aug_sep") {
    return series.filter((r) => r.trade_date.startsWith("2026-08") || r.trade_date.startsWith("2026-09"));
  }
  return series;
}

function zClassification(z) {
  if (!finite(z)) return { label: "No baseline", cls: "z-normal" };
  if (Math.abs(z) >= 2.0) return { label: `Extreme (${z > 0 ? "+" : ""}${z.toFixed(2)}σ)`, cls: "z-extreme" };
  if (z >= 1.0) return { label: `Flat Skew (+${z.toFixed(2)}σ)`, cls: "z-flat" };
  if (z <= -1.0) return { label: `Steep Skew (${z.toFixed(2)}σ)`, cls: "z-steep" };
  return { label: `Normal Range (${z >= 0 ? "+" : ""}${z.toFixed(2)}σ)`, cls: "z-normal" };
}

function renderDistributionLab() {
  const structure = $("distStructure").value;
  const metric = $("distMetric").value;
  const windowType = $("distWindow").value;
  let targetDate = $("distDate").value;

  const fullSeries = computeCausalSeries(structure, metric, windowType);
  if (!fullSeries.length) return;

  $("distDate").min = fullSeries[0].trade_date;
  $("distDate").max = fullSeries[fullSeries.length - 1].trade_date;

  if (!targetDate || !fullSeries.some((r) => r.trade_date === targetDate)) {
    const augDays = fullSeries.filter((r) => r.trade_date.startsWith("2026-08"));
    targetDate = augDays.length >= 2 ? augDays[1].trade_date : fullSeries[fullSeries.length - 1].trade_date;
    $("distDate").value = targetDate;
  }

  const currentRec = fullSeries.find((r) => r.trade_date === targetDate) || fullSeries[fullSeries.length - 1];
  const dteInfo = dteOn(targetDate);

  $("distMetaBadges").innerHTML = [
    ["Structure", structure],
    ["Metric", metric === "market_value" ? "Market IV" : "Residual"],
    ["Causal Rule", "History < Date (Zero-Lookahead)"],
    ["Coverage", `324 days (${fullSeries[0].trade_date} → ${fullSeries[fullSeries.length - 1].trade_date})`],
  ]
    .map(([k, v]) => `<div class="badge">${k}<b>${v}</b></div>`)
    .join("");

  const zClass = zClassification(currentRec.z_score);
  const pcts = finite(currentRec.percentile_rank) ? currentRec.percentile_rank.toFixed(1) + "%" : "—";
  const zStr = finite(currentRec.z_score) ? (currentRec.z_score >= 0 ? "+" : "") + currentRec.z_score.toFixed(2) + " σ" : "—";
  const valPts = finite(currentRec.value) ? (currentRec.value * 100).toFixed(2) + " vol pts" : "—";
  const meanPts = finite(currentRec.mean_prior) ? (currentRec.mean_prior * 100).toFixed(2) + " vol pts" : "—";
  const stdPts = finite(currentRec.std_prior) ? (currentRec.std_prior * 100).toFixed(2) + " vol pts" : "—";

  $("distKpiBanner").innerHTML = `
    <article class="kpi-card">
      <div class="kpi-title">Selected Observation</div>
      <div class="kpi-val highlight-accent">${targetDate}</div>
      <div class="kpi-sub">
        DTE: <b>${currentRec.actual_dte || dteInfo?.actual_dte || "—"}</b> · Expiry: <b>${dteInfo?.selected_expiry || "—"}</b><br/>
        Spot: <b>${fmt(currentRec.spot, 1)}</b> · Fwd: <b>${fmt(currentRec.forward, 1)}</b>
      </div>
    </article>

    <article class="kpi-card">
      <div class="kpi-title">${structure} Current Value</div>
      <div class="kpi-val">${valPts}</div>
      <div class="kpi-sub">
        Decimal: <b>${fmt(currentRec.value, 4)}</b><br/>
        Residual vs fair: <b>${fmt(currentRec.residual, 5)}</b>
      </div>
    </article>

    <article class="kpi-card">
      <div class="kpi-title">Prior Historical Baseline</div>
      <div class="kpi-val highlight-cyan">${currentRec.n_prior} <span style="font-size:14px;font-weight:400;color:var(--muted)">days (&lt; ${targetDate})</span></div>
      <div class="kpi-sub">
        Baseline: <b>${currentRec.prior_start || "—"}</b> &rarr; <b>${currentRec.prior_end || "—"}</b><br/>
        Prior Mean &mu;: <b>${meanPts}</b> · &sigma;: <b>${stdPts}</b>
      </div>
    </article>

    <article class="kpi-card">
      <div class="kpi-title">Standard Deviation Position (Z)</div>
      <div class="kpi-val"><span class="z-badge ${zClass.cls}">${zStr}</span></div>
      <div class="kpi-sub">
        Classification: <b>${zClass.label}</b><br/>
        Formula: <code>(Today - &mu;<sub>&lt;t</sub>) / &sigma;<sub>&lt;t</sub></code>
      </div>
    </article>

    <article class="kpi-card">
      <div class="kpi-title">Historical Percentile Rank</div>
      <div class="kpi-val highlight-cheap">${pcts}</div>
      <div class="kpi-sub">
        <div class="pct-bar-wrap" style="margin:4px 0 6px;">
          <div class="pct-bar-fill" style="width: ${Math.min(100, Math.max(0, currentRec.percentile_rank || 0))}%"></div>
        </div>
        Lies higher than <b>${pcts}</b> of historical trading days strictly prior to today.
      </div>
    </article>

    <article class="kpi-card">
      <div class="kpi-title">Prior Distribution Range</div>
      <div class="kpi-val" style="font-size:18px;margin-top:8px;">
        ${fmt(currentRec.min_prior != null ? currentRec.min_prior * 100 : null, 2)}% &rarr; ${fmt(currentRec.max_prior != null ? currentRec.max_prior * 100 : null, 2)}%
      </div>
      <div class="kpi-sub">
        Prior Median (P50): <b>${fmt(currentRec.median_prior != null ? currentRec.median_prior * 100 : null, 2)}%</b><br/>
        Spread: <b>${fmt((currentRec.max_prior - currentRec.min_prior) * 100, 2)} vol pts</b>
      </div>
    </article>
  `;

  drawHistoricalDensityChart(currentRec);
  drawTimeSeriesEnvelopesChart(fullSeries, targetDate);
  renderDailyInspectionTable(fullSeries, targetDate);
}

function drawHistoricalDensityChart(currentRec) {
  const canvas = $("distDensityCanvas");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const prior = currentRec.prior_values || [];
  if (!prior.length || !finite(currentRec.mean_prior) || !finite(currentRec.std_prior)) {
    ctx.fillStyle = "#8b949e";
    ctx.font = "14px sans-serif";
    ctx.fillText("Insufficient prior history (< 10 trading days) to construct distribution.", 60, h / 2);
    return;
  }

  const mean = currentRec.mean_prior;
  const std = currentRec.std_prior;
  const val = currentRec.value;

  const minX = Math.min(...prior, val, mean - 3.2 * std);
  const maxX = Math.max(...prior, val, mean + 3.2 * std);
  const pad = { l: 64, r: 28, t: 72, b: 40 };

  const xAt = (v) => pad.l + ((v - minX) / (maxX - minX || 1e-6)) * (w - pad.l - pad.r);

  const nBins = 28;
  const binWidth = (maxX - minX) / nBins;
  const bins = new Array(nBins).fill(0);
  for (const p of prior) {
    const b = Math.min(nBins - 1, Math.max(0, Math.floor((p - minX) / binWidth)));
    bins[b] += 1;
  }
  const maxBin = Math.max(...bins, 1);
  const yAt = (count) => (h - pad.b) - (count / maxBin) * (h - pad.t - pad.b);

  ctx.strokeStyle = "rgba(48, 54, 61, 0.4)";
  ctx.lineWidth = 1;
  for (let k = 0; k <= 4; k++) {
    const yVal = pad.t + (k / 4) * (h - pad.t - pad.b);
    ctx.beginPath();
    ctx.moveTo(pad.l, yVal);
    ctx.lineTo(w - pad.r, yVal);
    ctx.stroke();
  }

  ctx.fillStyle = "rgba(88, 166, 255, 0.22)";
  ctx.strokeStyle = "rgba(88, 166, 255, 0.6)";
  for (let i = 0; i < nBins; i++) {
    const bStart = minX + i * binWidth;
    const bEnd = bStart + binWidth;
    const bx1 = xAt(bStart);
    const bx2 = xAt(bEnd);
    const by = yAt(bins[i]);
    const bHeight = (h - pad.b) - by;
    ctx.fillRect(bx1 + 1, by, Math.max(1, bx2 - bx1 - 2), bHeight);
    ctx.strokeRect(bx1 + 1, by, Math.max(1, bx2 - bx1 - 2), bHeight);
  }

  ctx.beginPath();
  ctx.strokeStyle = "#39c5cf";
  ctx.lineWidth = 2;
  const normalPoints = 120;
  for (let i = 0; i <= normalPoints; i++) {
    const xv = minX + (i / normalPoints) * (maxX - minX);
    const normPdf = (1 / (std * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * Math.pow((xv - mean) / std, 2));
    const scaledCount = normPdf * binWidth * prior.length;
    const px = xAt(xv);
    const py = yAt(scaledCount);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  }
  ctx.stroke();

  const placedLabels = [];
  function drawRef(xVal, color, dash, label) {
    if (xVal < minX || xVal > maxX) return;
    const px = xAt(xVal);
    ctx.strokeStyle = color;
    ctx.setLineDash(dash);
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(px, pad.t);
    ctx.lineTo(px, h - pad.b);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = color;
    ctx.font = "11px sans-serif";
    ctx.textAlign = "center";
    const tw = ctx.measureText(label).width;
    let y = 16;
    let guard = 0;
    while (
      placedLabels.some((p) => Math.abs(p.x - px) < (p.w + tw) / 2 + 10 && Math.abs(p.y - y) < 14) &&
      guard < 4
    ) {
      y += 14;
      guard += 1;
    }
    const drawX = Math.min(w - pad.r - tw / 2, Math.max(pad.l + tw / 2, px));
    placedLabels.push({ x: drawX, y, w: tw });
    ctx.fillText(label, drawX, y);
  }

  drawRef(mean, "#f0f6fc", [4, 4], `Mean μ: ${(mean * 100).toFixed(2)}%`);
  drawRef(mean - std, "#8b949e", [2, 2], "-1σ");
  drawRef(mean + std, "#8b949e", [2, 2], "+1σ");
  drawRef(mean - 2 * std, "#f85149", [2, 2], "-2σ");
  drawRef(mean + 2 * std, "#3dba7a", [2, 2], "+2σ");

  const tx = xAt(val);
  ctx.strokeStyle = "#bc8cff";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(tx, pad.t + 10);
  ctx.lineTo(tx, h - pad.b);
  ctx.stroke();

  ctx.fillStyle = "#bc8cff";
  ctx.beginPath();
  ctx.arc(tx, h - pad.b, 6, 0, 2 * Math.PI);
  ctx.fill();

  const tagText = `Today ${currentRec.trade_date.slice(5)}  ${(val * 100).toFixed(2)}%`;
  ctx.font = "bold 11px sans-serif";
  const tagW = ctx.measureText(tagText).width + 12;
  let tagX = Math.min(w - pad.r - tagW / 2, Math.max(pad.l + tagW / 2, tx));
  let tagY = h - pad.b - 22;
  let tagGuard = 0;
  while (
    placedLabels.some((p) => Math.abs(p.x - tagX) < (p.w + tagW) / 2 + 8 && Math.abs(p.y - tagY) < 16) &&
    tagGuard < 3
  ) {
    tagY -= 16;
    tagGuard += 1;
  }
  placedLabels.push({ x: tagX, y: tagY, w: tagW });

  ctx.fillStyle = "#1e1730";
  ctx.strokeStyle = "#bc8cff";
  ctx.lineWidth = 1.5;
  ctx.fillRect(tagX - tagW / 2, tagY - 12, tagW, 18);
  ctx.strokeRect(tagX - tagW / 2, tagY - 12, tagW, 18);

  ctx.fillStyle = "#fff";
  ctx.textAlign = "center";
  ctx.fillText(tagText, tagX, tagY);

  ctx.fillStyle = "#8b949e";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(`Min: ${(minX * 100).toFixed(1)}%`, pad.l, h - 12);
  ctx.textAlign = "right";
  ctx.fillText(`Max: ${(maxX * 100).toFixed(1)}%`, w - pad.r, h - 12);

  $("distHistCaption").textContent = `Prior reference history N=${currentRec.n_prior} days (${currentRec.prior_start} → ${currentRec.prior_end}). Today's observation is marked in purple at ${(val * 100).toFixed(2)}%.`;
  $("distChartLegend").innerHTML = `
    <span class="legend-item"><span class="legend-dot" style="background:#58a6ff"></span> Prior History Bins</span>
    <span class="legend-item"><span class="legend-dot" style="background:#39c5cf"></span> Fitted Normal KDE</span>
    <span class="legend-item"><span class="legend-dot" style="background:#bc8cff"></span> Today's Observation</span>
  `;
}

function drawTimeSeriesEnvelopesChart(fullSeries, activeDate) {
  const canvas = $("distTrendCanvas");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const series = getFilteredDistDates(fullSeries);
  if (!series.length) return;

  const dates = series.map((r) => r.trade_date);
  const values = series.map((r) => r.value);
  const means = series.map((r) => r.mean_prior);
  const upper1 = series.map((r) => finite(r.mean_prior) && finite(r.std_prior) ? r.mean_prior + r.std_prior : null);
  const lower1 = series.map((r) => finite(r.mean_prior) && finite(r.std_prior) ? r.mean_prior - r.std_prior : null);
  const upper2 = series.map((r) => finite(r.mean_prior) && finite(r.std_prior) ? r.mean_prior + 2 * r.std_prior : null);
  const lower2 = series.map((r) => finite(r.mean_prior) && finite(r.std_prior) ? r.mean_prior - 2 * r.std_prior : null);

  const validAll = [...values, ...upper2.filter(finite), ...lower2.filter(finite)];
  const minY = Math.min(...validAll);
  const maxY = Math.max(...validAll);
  const pad = { l: 56, r: 24, t: 24, b: 36 };

  const xAt = (i) => pad.l + (i / Math.max(series.length - 1, 1)) * (w - pad.l - pad.r);
  const yAt = (v) => pad.t + (1 - (v - minY) / (maxY - minY || 1e-6)) * (h - pad.t - pad.b);

  ctx.strokeStyle = "rgba(48, 54, 61, 0.4)";
  ctx.lineWidth = 1;
  for (let k = 0; k <= 4; k++) {
    const yVal = pad.t + (k / 4) * (h - pad.t - pad.b);
    ctx.beginPath();
    ctx.moveTo(pad.l, yVal);
    ctx.lineTo(w - pad.r, yVal);
    ctx.stroke();
    const tickVal = maxY - (k / 4) * (maxY - minY);
    ctx.fillStyle = "#8b949e";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText((tickVal * 100).toFixed(1) + "%", pad.l - 6, yVal + 4);
  }

  // Draw ±2σ Band Shading
  ctx.fillStyle = "rgba(163, 113, 247, 0.08)";
  ctx.beginPath();
  let started = false;
  for (let i = 0; i < series.length; i++) {
    if (finite(upper2[i])) {
      const x = xAt(i), y = yAt(upper2[i]);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
  }
  for (let i = series.length - 1; i >= 0; i--) {
    if (finite(lower2[i])) {
      ctx.lineTo(xAt(i), yAt(lower2[i]));
    }
  }
  ctx.closePath();
  ctx.fill();

  // Draw ±1σ Band Shading
  ctx.fillStyle = "rgba(88, 166, 255, 0.12)";
  ctx.beginPath();
  started = false;
  for (let i = 0; i < series.length; i++) {
    if (finite(upper1[i])) {
      const x = xAt(i), y = yAt(upper1[i]);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
  }
  for (let i = series.length - 1; i >= 0; i--) {
    if (finite(lower1[i])) {
      ctx.lineTo(xAt(i), yAt(lower1[i]));
    }
  }
  ctx.closePath();
  ctx.fill();

  // Draw Mean Line (Dashed cyan)
  ctx.strokeStyle = "#39c5cf";
  ctx.setLineDash([4, 4]);
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  started = false;
  for (let i = 0; i < series.length; i++) {
    if (finite(means[i])) {
      const x = xAt(i), y = yAt(means[i]);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
  }
  ctx.stroke();
  ctx.setLineDash([]);

  // Draw Actual Values Line
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 2.2;
  ctx.beginPath();
  started = false;
  for (let i = 0; i < series.length; i++) {
    if (finite(values[i])) {
      const x = xAt(i), y = yAt(values[i]);
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
  }
  ctx.stroke();

  // Draw Data Points
  for (let i = 0; i < series.length; i++) {
    const x = xAt(i);
    const y = yAt(values[i]);
    ctx.fillStyle = dates[i] === activeDate ? "#bc8cff" : "#58a6ff";
    ctx.beginPath();
    ctx.arc(x, y, dates[i] === activeDate ? 6 : 3.5, 0, 2 * Math.PI);
    ctx.fill();
    if (dates[i] === activeDate) {
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }

  const activeIdx = dates.indexOf(activeDate);
  if (activeIdx >= 0) {
    ctx.strokeStyle = "#bc8cff";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(xAt(activeIdx), pad.t);
    ctx.lineTo(xAt(activeIdx), h - pad.b);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.fillStyle = "#8b949e";
  ctx.font = "11px sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(dates[0], pad.l, h - 12);
  ctx.textAlign = "right";
  ctx.fillText(dates[dates.length - 1], w - pad.r, h - 12);

  $("distTrendCaption").textContent = `Plotting ${series.length} trading days. Shaded bands represent causal strictly prior ±1σ (blue) and ±2σ (purple) bounds.`;
  $("distTrendLegend").innerHTML = `
    <span class="legend-item"><span class="legend-dot" style="background:#fff"></span> Actual RR</span>
    <span class="legend-item"><span class="legend-dot" style="background:#39c5cf"></span> Prior Mean μ</span>
    <span class="legend-item"><span class="legend-dot" style="background:rgba(88,166,255,0.6)"></span> ±1σ Band</span>
    <span class="legend-item"><span class="legend-dot" style="background:rgba(163,113,247,0.6)"></span> ±2σ Band</span>
  `;
}

function renderDailyInspectionTable(fullSeries, activeDate) {
  const q = ($("distTableSearch").value || "").trim().toLowerCase();
  const zFilter = $("distZFilter").value;
  const filtered = getFilteredDistDates(fullSeries).filter((r) => {
    if (q && !r.trade_date.includes(q)) return false;
    if (zFilter === "gt1" && (!finite(r.z_score) || Math.abs(r.z_score) < 1.0)) return false;
    if (zFilter === "gt15" && (!finite(r.z_score) || Math.abs(r.z_score) < 1.5)) return false;
    if (zFilter === "gt2" && (!finite(r.z_score) || Math.abs(r.z_score) < 2.0)) return false;
    return true;
  });

  const tbody = $("distTableBody");
  tbody.innerHTML = filtered
    .map((r) => {
      const zClass = zClassification(r.z_score);
      const zText = finite(r.z_score) ? (r.z_score >= 0 ? "+" : "") + r.z_score.toFixed(2) + " σ" : "—";
      const pctVal = finite(r.percentile_rank) ? r.percentile_rank.toFixed(1) : "—";
      const pctBar = finite(r.percentile_rank)
        ? `<div class="pct-cell"><div class="pct-bar-wrap"><div class="pct-bar-fill" style="width:${Math.min(100, Math.max(0, r.percentile_rank))}%"></div></div><span class="pct-num">${pctVal}%</span></div>`
        : "—";

      const rawRow = (BY_DATE[r.trade_date] || []).find((x) => x.structure === "POINT_25C");
      const rawPut = (BY_DATE[r.trade_date] || []).find((x) => x.structure === "POINT_25P");
      const cIv = rawRow ? (rawRow.market_value * 100).toFixed(2) + "%" : "—";
      const pIv = rawPut ? (rawPut.market_value * 100).toFixed(2) + "%" : "—";

      const rangeStr = r.min_prior != null ? `[${(r.min_prior * 100).toFixed(1)}%, ${(r.max_prior * 100).toFixed(1)}%]` : "—";

      return `
        <tr data-date="${r.trade_date}" class="${r.trade_date === activeDate ? "active" : ""}">
          <td><b>${r.trade_date}</b></td>
          <td>${r.actual_dte || "—"}</td>
          <td>${fmt(r.spot, 1)}</td>
          <td>${fmt(r.forward, 1)}</td>
          <td>${cIv}</td>
          <td>${pIv}</td>
          <td><b style="color:#fff">${(r.value * 100).toFixed(2)}%</b></td>
          <td>${r.n_prior}</td>
          <td>${finite(r.mean_prior) ? (r.mean_prior * 100).toFixed(2) + "%" : "—"}</td>
          <td>${finite(r.std_prior) ? (r.std_prior * 100).toFixed(2) + "%" : "—"}</td>
          <td><span class="z-badge ${zClass.cls}">${zText}</span></td>
          <td>${pctBar}</td>
          <td style="color:var(--muted);font-size:11.5px">${rangeStr}</td>
          <td><button type="button" class="btn-inspect" data-date="${r.trade_date}">Inspect</button></td>
        </tr>
      `;
    })
    .join("");

  tbody.querySelectorAll("tr").forEach((tr) => {
    tr.addEventListener("click", () => {
      const d = tr.getAttribute("data-date");
      $("distDate").value = d;
      renderDistributionLab();
    });
  });
}

function exportCsvTable(series) {
  const rows = getFilteredDistDates(series);
  const headers = [
    "trade_date", "structure", "actual_dte", "spot", "forward",
    "value_vol_pct", "prior_days_n", "prior_mean_pct", "prior_std_pct",
    "z_score", "percentile_rank", "prior_min_pct", "prior_median_pct", "prior_max_pct"
  ];
  const lines = [headers.join(",")];
  for (const r of rows) {
    lines.push([
      r.trade_date,
      r.structure,
      r.actual_dte || "",
      r.spot || "",
      r.forward || "",
      (r.value * 100).toFixed(4),
      r.n_prior,
      finite(r.mean_prior) ? (r.mean_prior * 100).toFixed(4) : "",
      finite(r.std_prior) ? (r.std_prior * 100).toFixed(4) : "",
      finite(r.z_score) ? r.z_score.toFixed(4) : "",
      finite(r.percentile_rank) ? r.percentile_rank.toFixed(2) : "",
      r.min_prior != null ? (r.min_prior * 100).toFixed(4) : "",
      r.median_prior != null ? (r.median_prior * 100).toFixed(4) : "",
      r.max_prior != null ? (r.max_prior * 100).toFixed(4) : "",
    ].join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `RR_25D_Historical_Distribution_Aug_Sep_2026.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ==================== BOOT & EVENT INITIALIZATION ==================== */
function inflate(payload) {
  const cols = payload.columns;
  if (!cols || !payload.rows?.length || (typeof payload.rows[0] === "object" && !Array.isArray(payload.rows[0]))) {
    return payload;
  }
  payload.rows = payload.rows.map((arr) => {
    const o = {};
    for (let i = 0; i < cols.length; i += 1) {
      const v = arr[i];
      if (v !== null && v !== undefined) o[cols[i]] = v;
    }
    return o;
  });
  return payload;
}

function switchTab(target) {
  CURRENT_TAB = target;
  const panes = [
    ["strategy", "tabStrategy", "viewStrategy"],
    ["distribution", "tabDistribution", "viewDistribution"],
    ["surface", "tabSurface", "viewSurface"],
  ];
  for (const [name, tabId, viewId] of panes) {
    const on = name === target;
    const tab = $(tabId);
    const view = $(viewId);
    if (tab) tab.classList.toggle("active", on);
    if (view) view.style.display = on ? "block" : "none";
  }
  document.body.classList.toggle("show-surface", target === "surface");
  const hash = target === "distribution" ? "#distribution" : target === "surface" ? "#surface" : "#strategy";
  if (window.location.hash !== hash) window.location.hash = hash;
  if (target === "strategy") render();
  else if (target === "distribution") renderDistributionLab();
  else {
    const frame = $("surfaceFrame");
    if (frame && frame.getAttribute("src") === "about:blank") frame.setAttribute("src", "surface/index.html");
  }
}

async function boot() {
  const res = await fetch("data/panel.json");
  DATA = inflate(await res.json());

  try {
    const dRes = await fetch("data/distribution_analysis.json");
    if (dRes.ok) DIST_DATA = await dRes.json();
  } catch (err) {
    console.warn("Precomputed distribution data not available, falling back to dynamic computation", err);
  }

  indexRows();
  fillSelects();
  renderMeta();
  renderWF();

  // Tab switching events
  $("tabStrategy").addEventListener("click", () => switchTab("strategy"));
  $("tabDistribution").addEventListener("click", () => switchTab("distribution"));
  $("tabSurface").addEventListener("click", () => switchTab("surface"));
  window.addEventListener("hashchange", () => {
    const next = window.location.hash === "#distribution"
      ? "distribution"
      : window.location.hash === "#surface"
        ? "surface"
        : "strategy";
    if (next !== CURRENT_TAB) switchTab(next);
  });

  if (window.location.hash === "#distribution") switchTab("distribution");
  else if (window.location.hash === "#surface") switchTab("surface");
  else switchTab("strategy");

  // Strategy Desk Events
  ["kind", "structure", "date", "zGate", "compare", "decisionFilter", "showListed"].forEach((id) => {
    $(id).addEventListener("change", () => {
      if (id === "kind" || id === "date") refreshStructures();
      render();
    });
  });
  $("crossSearch").addEventListener("input", () => {
    renderCross($("date").value, Number($("zGate").value), $("structure").value);
  });

  // Date Stepper & Quick Jump Buttons
  $("jumpTest").addEventListener("click", () => {
    $("date").value = DATA.meta.test_date;
    refreshStructures();
    render();
  });
  $("jumpLatest").addEventListener("click", () => {
    $("date").value = DATA.dates[DATA.dates.length - 1];
    refreshStructures();
    render();
  });
  $("btnPrevDate").addEventListener("click", () => {
    const curIdx = DATA.dates.indexOf($("date").value);
    if (curIdx > 0) {
      $("date").value = DATA.dates[curIdx - 1];
      refreshStructures();
      render();
    }
  });
  $("btnNextDate").addEventListener("click", () => {
    const curIdx = DATA.dates.indexOf($("date").value);
    if (curIdx >= 0 && curIdx < DATA.dates.length - 1) {
      $("date").value = DATA.dates[curIdx + 1];
      refreshStructures();
      render();
    }
  });

  // Distribution Lab Events
  ["distStructure", "distMetric", "distWindow", "distDate"].forEach((id) => {
    $(id).addEventListener("change", () => renderDistributionLab());
  });

  $("btnFilterAugSep").addEventListener("click", () => {
    DIST_ACTIVE_FILTER = "aug_sep";
    document.querySelectorAll(".btn-chip").forEach((b) => b.classList.remove("active"));
    $("btnFilterAugSep").classList.add("active");
    renderDistributionLab();
  });
  $("btnFilterAug").addEventListener("click", () => {
    DIST_ACTIVE_FILTER = "aug";
    document.querySelectorAll(".btn-chip").forEach((b) => b.classList.remove("active"));
    $("btnFilterAug").classList.add("active");
    renderDistributionLab();
  });
  $("btnFilterSep").addEventListener("click", () => {
    DIST_ACTIVE_FILTER = "sep";
    document.querySelectorAll(".btn-chip").forEach((b) => b.classList.remove("active"));
    $("btnFilterSep").classList.add("active");
    renderDistributionLab();
  });
  $("btnFilterAll").addEventListener("click", () => {
    DIST_ACTIVE_FILTER = "all";
    document.querySelectorAll(".btn-chip").forEach((b) => b.classList.remove("active"));
    $("btnFilterAll").classList.add("active");
    renderDistributionLab();
  });

  $("distTableSearch").addEventListener("input", () => {
    const fullSeries = computeCausalSeries($("distStructure").value, $("distMetric").value, $("distWindow").value);
    renderDailyInspectionTable(fullSeries, $("distDate").value);
  });
  $("distZFilter").addEventListener("change", () => {
    const fullSeries = computeCausalSeries($("distStructure").value, $("distMetric").value, $("distWindow").value);
    renderDailyInspectionTable(fullSeries, $("distDate").value);
  });
  $("btnExportCsv").addEventListener("click", () => {
    const fullSeries = computeCausalSeries($("distStructure").value, $("distMetric").value, $("distWindow").value);
    exportCsvTable(fullSeries);
  });
}

boot();
