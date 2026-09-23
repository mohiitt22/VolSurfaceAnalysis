/* 60DTE IV relative-value desk */
const $ = (id) => document.getElementById(id);
let DATA = null;

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

function verdictOf(row, zGate) {
  const reasons = [];
  if (!row) {
    return { label: "CANNOT DECIDE", cls: "undecided", why: "No observation for this date / structure.", reasons: ["missing_row"], votes: {} };
  }
  const z = row.z_60_residual;
  const res = row.residual;
  const z20 = row.z_20_residual;
  const z120 = row.z_120_residual;
  const votes = {
    structural: !finite(res) ? "undecided" : res < 0 ? "cheap" : res > 0 ? "expensive" : "undecided",
    historical60: !finite(z) ? "undecided" : z <= -zGate ? "cheap" : z >= zGate ? "expensive" : "undecided",
    historical20: !finite(z20) ? "undecided" : z20 <= -zGate ? "cheap" : z20 >= zGate ? "expensive" : "undecided",
    historical120: !finite(z120) ? "undecided" : z120 <= -zGate ? "cheap" : z120 >= zGate ? "expensive" : "undecided",
    level: !finite(row.z_60_market_value) ? "undecided" : row.z_60_market_value <= -zGate ? "cheap" : row.z_60_market_value >= zGate ? "expensive" : "undecided",
  };

  if (row.extrapolated) reasons.push("Delta was extrapolated — treat as low confidence.");
  if (!finite(z)) reasons.push("Not enough history for a 60-day residual z-score.");
  else if (Math.abs(z) < zGate) reasons.push(`|z_60| = ${z.toFixed(2)} is below the ${zGate} gate.`);
  if (finite(res) && finite(z) && Math.sign(res) !== 0 && Math.sign(z) !== 0 && Math.sign(res) !== Math.sign(z)) {
    reasons.push("Structural residual and historical z disagree on direction.");
  }
  if (finite(row.actual_dte) && Math.abs(row.actual_dte - 60) >= 6) {
    reasons.push(`DTE is ${row.actual_dte}, far from the 60-day target.`);
  }

  const hist = votes.historical60;
  const struct = votes.structural;
  let label = "CANNOT DECIDE";
  let cls = "undecided";
  let why = "Definitions do not line up strongly enough to call cheap or expensive.";
  if (hist === "cheap" && struct === "cheap") {
    label = "CHEAP";
    cls = "cheap";
    why = "Market is below ensemble fair value and the residual is historically low.";
  } else if (hist === "expensive" && struct === "expensive") {
    label = "EXPENSIVE";
    cls = "expensive";
    why = "Market is above ensemble fair value and the residual is historically high.";
  } else if (hist === "undecided" && struct !== "undecided" && finite(z) && Math.abs(z) < zGate) {
    why = "There is a small structural residual, but it is not unusual versus this structure's own history.";
  }
  return { label, cls, why, reasons, votes };
}

function rowsFor(structure) {
  return DATA.rows.filter((r) => r.structure === structure);
}
function rowOn(structure, date) {
  return DATA.rows.find((r) => r.structure === structure && r.trade_date === date);
}
function catalogItem(structure) {
  return DATA.catalog.find((c) => c.structure === structure);
}
function dteOn(date) {
  return DATA.dte.find((d) => d.trade_date === date);
}
function statsOf(structure) {
  return DATA.stats.find((s) => s.structure === structure);
}

function fillSelects() {
  const kinds = ["all", ...new Set(DATA.catalog.map((c) => c.kind))];
  $("kind").innerHTML = kinds.map((k) => `<option value="${k}">${k}</option>`).join("");
  refreshStructures();
  $("date").min = DATA.dates[0];
  $("date").max = DATA.dates[DATA.dates.length - 1];
  $("date").value = DATA.meta.test_date;
  $("compare").innerHTML =
    `<option value="">— none —</option>` +
    DATA.catalog.map((c) => `<option value="${c.structure}">${c.structure}</option>`).join("");
}

function refreshStructures() {
  const kind = $("kind").value;
  const list = DATA.catalog.filter((c) => kind === "all" || c.kind === kind);
  const prev = $("structure").value;
  $("structure").innerHTML = list
    .map((c) => `<option value="${c.structure}">${c.structure} · ${c.legs || c.kind}</option>`)
    .join("");
  if (list.some((c) => c.structure === prev)) $("structure").value = prev;
}

function pill(v) {
  return `<span class="pill ${v.cls}">${v.label}</span>`;
}

function renderMeta() {
  const m = DATA.meta;
  $("metaBadges").innerHTML = [
    ["Research end", m.train_end],
    ["Holdout", m.test_date],
    ["Dates", String(m.n_dates)],
    ["Structures", String(m.n_structures)],
    ["Frozen z", String(m.frozen_z)],
  ]
    .map(([k, v]) => `<div class="badge">${k}<b>${v}</b></div>`)
    .join("");
}

function render() {
  const structure = $("structure").value;
  const date = $("date").value;
  const zGate = Number($("zGate").value);
  const row = rowOn(structure, date);
  const v = verdictOf(row, zGate);
  const cat = catalogItem(structure);
  const dte = dteOn(date);
  const hist = statsOf(structure);

  $("verdictLabel").textContent = v.label;
  $("verdictLabel").className = "verdict " + v.cls;
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
    ["Kind / legs", `${cat?.kind || ""} · ${cat?.legs || ""}`],
    ["Market value", finite(row?.market_value) ? `${fmt(row.market_value, 4)}  (${volPts(row.market_value)})` : "—"],
    ["Ensemble fair", fmt(row?.fair_value, 4)],
    ["IV residual", fmt(row?.residual, 5)],
    ["Price residual", fmt(row?.price_residual, 3)],
    ["z20 / z60 / z120 / z252", `${fmt(row?.z_20_residual, 2)} / ${fmt(row?.z_60_residual, 2)} / ${fmt(row?.z_120_residual, 2)} / ${fmt(row?.z_252_residual, 2)}`],
    ["60d percentile", fmt(row?.pct_60_residual, 2)],
    ["Holdout date?", date === DATA.meta.test_date ? "YES — frozen, not used to tune" : date > DATA.meta.train_end ? "After research cut / gap" : "Research sample"],
  ];
  $("snapTable").innerHTML = snap.map(([k, val]) => `<tr><th>${k}</th><td>${val}</td></tr>`).join("");

  const regime = [
    ["Selected expiry", dte?.selected_expiry || "—"],
    ["Contract", dte?.contract || "—"],
    ["Actual DTE", dte ? `${dte.actual_dte} (error ${dte.dte_error})` : "—"],
    ["Spot / forward", `${fmt(row?.spot_x, 2)} / ${fmt(row?.forward, 2)}`],
    ["ATM IV", volPts(row?.atm_iv)],
    ["RV 20 / 60", `${volPts(row?.rv_20)} / ${volPts(row?.rv_60)}`],
    ["IV − RV 20", volPts(row?.iv_rv_20)],
    ["Put-delta convention", dte?.put_delta_convention || "—"],
  ];
  $("regimeTable").innerHTML = regime.map(([k, val]) => `<tr><th>${k}</th><td>${val}</td></tr>`).join("");

  const hs = [
    ["Research obs / with 5d label", hist ? `${hist.n} / ${hist.n_conv}` : "—"],
    ["Mean 5d convergence", hist ? fmt(hist.mean_conv_h5, 5) : "—"],
    ["5d convergence hit rate", hist ? pct(hist.hit_conv_h5) : "—"],
    ["|z60|≥1.5 count", hist ? String(hist.n_extreme) : "—"],
    ["Extreme mean conv / hit", hist ? `${fmt(hist.mean_conv_extreme, 5)} / ${pct(hist.hit_extreme)}` : "—"],
    ["Mean |residual|", hist ? fmt(hist.mean_abs_residual, 5) : "—"],
    ["Interpretation", hist && hist.hit_conv_h5 > 0.6 && Math.abs(hist.mean_conv_h5 || 0) < 0.002
      ? "History mean-reverts a little; size is small vs costs."
      : "See numbers — do not assume tradability."],
  ];
  $("histTable").innerHTML = hs.map(([k, val]) => `<tr><th>${k}</th><td>${val}</td></tr>`).join("");

  drawChart(structure, date, $("compare").value);
  renderCross(date, zGate, structure);
}

function drawChart(structure, date, compare) {
  const canvas = $("chart");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  const series = rowsFor(structure).filter((r) => finite(r.market_value));
  if (!series.length) return;
  const dates = series.map((r) => r.trade_date);
  const y1 = series.map((r) => r.market_value);
  const y2 = series.map((r) => r.fair_value);
  const z = series.map((r) => r.z_60_residual);
  const allY = [...y1, ...y2.filter(finite)];
  const ymin = Math.min(...allY);
  const ymax = Math.max(...allY);
  const pad = { l: 48, r: 16, t: 16, b: 28 };
  const xAt = (i) => pad.l + (i / (series.length - 1)) * (w - pad.l - pad.r);
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
  $("chartCaption").textContent = compare
    ? `${structure} market (white) vs ensemble fair (blue dashed) vs ${compare} market (gold)`
    : `${structure} market (white) vs ensemble fair (blue dashed). Purple line = selected date. Source: 60DTE nearest-expiry panel.`;
}

function renderCross(date, zGate, active) {
  const rows = DATA.rows.filter((r) => r.trade_date === date);
  const head = ["Structure", "Kind", "Market", "Fair", "Residual", "z60", "Verdict"];
  $("crossTable").querySelector("thead").innerHTML =
    "<tr>" + head.map((h) => `<th>${h}</th>`).join("") + "</tr>";
  const body = rows
    .map((r) => {
      const v = verdictOf(r, zGate);
      return `<tr data-s="${r.structure}" class="${r.structure === active ? "active" : ""}">
        <td>${r.structure}</td>
        <td>${r.kind}</td>
        <td>${fmt(r.market_value, 4)}</td>
        <td>${fmt(r.fair_value, 4)}</td>
        <td>${fmt(r.residual, 5)}</td>
        <td>${fmt(r.z_60_residual, 2)}</td>
        <td>${pill(v)}</td>
      </tr>`;
    })
    .join("");
  $("crossTable").querySelector("tbody").innerHTML = body;
  $("crossTable").querySelectorAll("tbody tr").forEach((tr) => {
    tr.addEventListener("click", () => {
      const s = tr.getAttribute("data-s");
      const cat = catalogItem(s);
      if (cat) $("kind").value = cat.kind;
      refreshStructures();
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

async function boot() {
  const res = await fetch("data/panel.json");
  DATA = await res.json();
  fillSelects();
  renderMeta();
  renderWF();
  ["kind", "structure", "date", "zGate", "compare"].forEach((id) => {
    $(id).addEventListener("change", () => {
      if (id === "kind") refreshStructures();
      render();
    });
  });
  $("jumpTest").addEventListener("click", () => {
    $("date").value = DATA.meta.test_date;
    render();
  });
  render();
}
boot();
