/* 60DTE IV relative-value desk — expanded universe */
const $ = (id) => document.getElementById(id);
let DATA = null;
let BY_STRUCT = {};
let BY_DATE = {};
let BY_HID = {};

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
    ["Named structures", String(m.n_named || m.n_structures)],
    ["All names", String(m.n_structures)],
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
      return `<div class="count muted">${k}<b>${x.TRADE}</b> T · ${x["NO TRADE"]} N · ${x["CANNOT DECIDE"]} C</div>`;
    })
    .join("");
  $("countStrip").innerHTML = chips.join("") + byKind;
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
    ["Holdout date?", date === DATA.meta.test_date ? "YES — frozen, not used to tune" : date > DATA.meta.train_end ? "After research cut / gap" : "Research sample"],
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
  ctx.fillText(dates[0], pad.l, h - 8);
  ctx.fillText(dates[dates.length - 1], w - 90, h - 8);
  ctx.fillText(fmt(ymax, 3), 4, pad.t + 8);
  ctx.fillText(fmt(ymin, 3), 4, h - pad.b);
  const own = rowsFor(structure)[0];
  const hidNote = own && own.kind === "listed_strike" ? ` Chart is the ${own.history_id} k-bin path used for z.` : "";
  $("chartCaption").textContent = compare
    ? `${structure} market (white) vs ensemble fair (blue dashed) vs ${compare} market (gold)`
    : `${structure} market (white) vs ensemble fair (blue dashed). Purple line = selected date.${hidNote}`;
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

function inflate(payload) {
  const cols = payload.columns;
  if (!cols || !payload.rows?.length || typeof payload.rows[0] === "object" && !Array.isArray(payload.rows[0])) {
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

async function boot() {
  const res = await fetch("data/panel.json");
  DATA = inflate(await res.json());
  indexRows();
  fillSelects();
  renderMeta();
  renderWF();
  ["kind", "structure", "date", "zGate", "compare", "decisionFilter", "showListed"].forEach((id) => {
    $(id).addEventListener("change", () => {
      if (id === "kind" || id === "date") refreshStructures();
      render();
    });
  });
  $("crossSearch").addEventListener("input", () => {
    renderCross($("date").value, Number($("zGate").value), $("structure").value);
  });
  $("jumpTest").addEventListener("click", () => {
    $("date").value = DATA.meta.test_date;
    refreshStructures();
    render();
  });
  render();
}
boot();
