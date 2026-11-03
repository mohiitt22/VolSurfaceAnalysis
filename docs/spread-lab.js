/* Spread Analysis tab. Reads the surface lab's DATA object and Plotly. */
(function () {
  const state = {
    dateA: null,
    dateB: null,
    mode: "strike",
    smileView: "strike",
    side: "call",
    width: null,
    method: "shapley",
    sortKey: "location",
    sortDir: 1,
    built: null,
  };

  function el(id) { return document.getElementById(id); }

  function dates() {
    return (window.DATA && window.DATA.all_dates) || [];
  }

  function day(iso) {
    return window.DATA && window.DATA.dates_data ? window.DATA.dates_data[iso] : null;
  }

  function fmt(n, d) {
    if (n === null || n === undefined || !Number.isFinite(n)) return "—";
    return n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  function pctShare(n) {
    return n === null || !Number.isFinite(n) ? "n/a" : fmt(n, 1) + "%";
  }

  function ensureDates() {
    const list = dates();
    if (!list.length) return;
    if (!state.dateA || !list.includes(state.dateA)) state.dateA = list[Math.max(0, list.length - 2)];
    if (!state.dateB || !list.includes(state.dateB)) state.dateB = list[list.length - 1];
  }

  function shiftIndex(iso, step) {
    const list = dates();
    const i = list.indexOf(iso);
    const j = i + step;
    return j >= 0 && j < list.length ? list[j] : null;
  }

  function layout(title, x, y) {
    return {
      title: { text: title, font: { size: 14, color: "#e6edf3" } },
      paper_bgcolor: "#0d1117",
      plot_bgcolor: "#0d1117",
      font: { color: "#c9d1d9", size: 11 },
      margin: { l: 64, r: 24, t: 48, b: 72 },
      legend: { orientation: "h", y: -0.28, yanchor: "top" },
      xaxis: { title: { text: x }, gridcolor: "#21262d", zerolinecolor: "#30363d" },
      yaxis: { title: { text: y }, gridcolor: "#21262d", zerolinecolor: "#30363d" },
      hovermode: "closest",
    };
  }

  function plot(id, traces, title, x, y) {
    const node = el(id);
    if (!node || !window.Plotly) return;
    Plotly.react(node, traces, layout(title, x, y), { responsive: true, displayModeBar: false });
  }

  function shell() {
    return `
      <section class="sa-block">
        <h2>Date selection</h2>
        <div class="sa-controls">
          <label>Reference date A <select id="saDateA"></select></label>
          <label>Comparison date B <select id="saDateB"></select></label>
          <label>Grid <select id="saMode">
            <option value="strike">Strike-wise (ATM, ATM±100, …)</option>
            <option value="delta">Delta-wise (file 5Δ–45Δ)</option>
          </select></label>
          <label>Side <select id="saSide"><option value="call">Calls</option><option value="put">Puts</option></select></label>
          <label>Step <select id="saWidth"></select></label>
          <label>Attribution view <select id="saMethod">
            <option value="shapley">Shapley</option>
            <option value="integrated">Integrated Greeks</option>
            <option value="both">Both methods</option>
          </select></label>
        </div>
        <div class="sa-nav">
          <button type="button" id="saPrevA">Previous A</button>
          <button type="button" id="saNextA">Next A</button>
          <button type="button" id="saPrevB">Previous B</button>
          <button type="button" id="saNextB">Next B</button>
          <button type="button" id="saPrevWin">Previous comparison window</button>
          <button type="button" id="saNextWin">Next comparison window</button>
          <button type="button" id="saBNext">B = next session after A</button>
          <button type="button" id="saBPrev">B = previous session before A</button>
          <button type="button" id="saSwap">Swap dates</button>
          <button type="button" id="saExport">Export CSV</button>
        </div>
        <div id="saSummary" class="sa-summary"></div>
        <p id="saWarn" class="sa-warn"></p>
      </section>
      <section class="sa-block">
        <h2>IV smile comparison</h2>
        <p class="sa-note" id="saSmileNote"></p>
        <div id="saSmile" class="sa-chart"></div>
        <div id="saSmileChg" class="sa-chart"></div>
        <div class="sa-scroll"><table id="saSmileTable"></table></div>
      </section>
      <section class="sa-block">
        <h2>Spread IV curves</h2>
        <div id="saLegIv" class="sa-chart"></div>
        <div id="saGap" class="sa-chart"></div>
      </section>
      <section class="sa-block">
        <h2>Spread premium curves</h2>
        <p class="sa-note">Premiums below are theoretical model-implied Black–Scholes values. Recorded source premiums, when the file has an exact strike, are kept in the table and are not treated as executable quotes. No bid or ask is in this file.</p>
        <div id="saPrem" class="sa-chart"></div>
        <div id="saPremChg" class="sa-chart"></div>
      </section>
      <section class="sa-block">
        <h2>Detailed spread values and Greeks</h2>
        <p class="sa-note">Net Greek = long near leg minus short far leg. Delta per underlying point. Gamma in delta per underlying point. Vega per 1 vol point. Volga per vol-point squared. Theta per calendar day. Vanna is dVega/dSpot per 1 vol point. Long near, short far. A positive premium change means that debit spread became more expensive.</p>
        <div class="sa-scroll"><table id="saTable"></table></div>
      </section>
      <section class="sa-block">
        <h2>Shapley attribution</h2>
        <p class="sa-note">IV-only. Spot, maturity, rate (4.5%), dividend yield (0), and the Date A strikes stay frozen. Only the two leg IVs move. Common leg-IV movement is the average of the two leg IV changes, not the ATM IV change. Local IV-gap change is near IV minus far IV.</p>
        <div id="saShapley" class="sa-chart"></div>
      </section>
      <section class="sa-block">
        <h2>Integrated-Greeks attribution</h2>
        <p class="sa-note">Vegas are recalculated on a straight line from the Date A IVs to the Date B IVs and integrated with 16-point Gauss–Legendre quadrature. An 8-point check is stored on each row. The two methods can split the nonlinear interaction differently. A total that misses the IV-only premium change is an error.</p>
        <div id="saIntegrated" class="sa-chart"></div>
      </section>
      <section class="sa-block">
        <h2>Method comparison</h2>
        <div id="saMethodStats" class="sa-summary"></div>
        <div id="saDiff" class="sa-chart"></div>
        <div id="saShare" class="sa-chart"></div>
        <div id="saSigned" class="sa-chart"></div>
        <div id="saReconcile" class="sa-chart"></div>
        <div id="saCards" class="sa-cards"></div>
      </section>
      <section class="sa-block">
        <h2>Global smile fit, kept separate</h2>
        <p class="sa-note">A quadratic in x = (K − ATM) / 500 is fit separately on each date for the selected side. Residuals stay residuals. This fit is not added into the two-factor Shapley or integrated-Greeks numbers. These surfaces are standardized around 60 calendar days, so the comparison is relative-value research, not the P&amp;L of one listed contract.</p>
        <div id="saFit"></div>
      </section>`;
  }

  function bind() {
    const map = {
      saDateA: (v) => { state.dateA = v; },
      saDateB: (v) => { state.dateB = v; },
      saMode: (v) => { state.mode = v; state.width = null; },
      saSide: (v) => { state.side = v; },
      saWidth: (v) => { state.width = Number(v); },
      saMethod: (v) => { state.method = v; },
    };
    Object.keys(map).forEach((id) => {
      el(id).addEventListener("change", () => { map[id](el(id).value); render(); });
    });
    el("saPrevA").onclick = () => moveOne("dateA", -1);
    el("saNextA").onclick = () => moveOne("dateA", 1);
    el("saPrevB").onclick = () => moveOne("dateB", -1);
    el("saNextB").onclick = () => moveOne("dateB", 1);
    el("saPrevWin").onclick = () => moveWindow(-1);
    el("saNextWin").onclick = () => moveWindow(1);
    el("saBNext").onclick = () => { const n = shiftIndex(state.dateA, 1); if (n) { state.dateB = n; render(); } };
    el("saBPrev").onclick = () => { const n = shiftIndex(state.dateA, -1); if (n) { state.dateB = n; render(); } };
    el("saSwap").onclick = () => { const t = state.dateA; state.dateA = state.dateB; state.dateB = t; render(); };
    el("saExport").onclick = exportCsv;
    el("saTable").addEventListener("click", (ev) => {
      const key = ev.target.getAttribute("data-sort");
      if (!key) return;
      state.sortDir = state.sortKey === key ? -state.sortDir : -1;
      state.sortKey = key;
      paintTable();
    });
  }

  function moveOne(key, step) {
    const next = shiftIndex(state[key], step);
    if (!next) return;
    state[key] = next;
    render();
  }

  function moveWindow(step) {
    const a = shiftIndex(state.dateA, step);
    const b = shiftIndex(state.dateB, step);
    if (!a || !b) return;
    state.dateA = a;
    state.dateB = b;
    render();
  }

  function fillDates() {
    const list = dates();
    ["saDateA", "saDateB"].forEach((id) => {
      const sel = el(id);
      const current = id === "saDateA" ? state.dateA : state.dateB;
      sel.innerHTML = list.map((d) => `<option value="${d}">${d}</option>`).join("");
      sel.value = current;
    });
    el("saMode").value = state.mode;
    el("saSide").value = state.side;
    el("saMethod").value = state.method;
    const listDates = dates();
    const iA = listDates.indexOf(state.dateA);
    const iB = listDates.indexOf(state.dateB);
    el("saPrevA").disabled = iA <= 0;
    el("saNextA").disabled = iA < 0 || iA >= listDates.length - 1;
    el("saPrevB").disabled = iB <= 0;
    el("saNextB").disabled = iB < 0 || iB >= listDates.length - 1;
    el("saPrevWin").disabled = iA <= 0 || iB <= 0;
    el("saNextWin").disabled = iA >= listDates.length - 1 || iB >= listDates.length - 1;
    el("saBNext").disabled = iA < 0 || iA >= listDates.length - 1;
    el("saBPrev").disabled = iA <= 0;
  }

  function xOf(row) {
    return row.loc || "—";
  }

  function validRows() {
    return (state.built && state.built.rows || []).filter((row) => row.available);
  }

  function render() {
    ensureDates();
    const a = day(state.dateA);
    const b = day(state.dateB);
    if (!a || !b) return;
    state.built = window.SpreadMath.buildRows(a, b, {
      side: state.side, mode: state.mode, width: state.width, rate: window.SpreadMath.RATE,
    });
    if (state.built.width) state.width = state.built.width;
    fillDates();
    const widthSel = el("saWidth");
    const unit = state.mode === "delta" ? "Δ" : " pts";
    widthSel.innerHTML = (state.built.widths || []).map((w) => `<option value="${w}">${w}${unit}</option>`).join("");
    widthSel.disabled = !(state.built.widths || []).length;
    if (state.built.width) widthSel.value = String(state.built.width);
    paintSummary(a, b);
    paintSmile(a, b);
    paintSpreads();
    paintTable();
    paintAttribution();
    paintFit(a, b);
  }

  function paintSummary(a, b) {
    const atmIv = (obj) => {
      const rows = window.SpreadMath.sideRows(obj, "call");
      const hit = window.SpreadMath.ivAtStrike(rows, Number(obj.atm_strike));
      return hit.iv;
    };
    el("saSummary").innerHTML = [
      ["Date A", state.dateA], ["Date B", state.dateB],
      ["Spot A", fmt(a.spot, 2)], ["Spot B", fmt(b.spot, 2)],
      ["ATM A", fmt(a.atm_strike, 2)], ["ATM B", fmt(b.atm_strike, 2)],
      ["DTE A", fmt(a.dte, 1)], ["DTE B", fmt(b.dte, 1)],
      ["ATM call IV A", atmIv(a) == null ? "—" : fmt(atmIv(a), 2) + "%"],
      ["ATM call IV B", atmIv(b) == null ? "—" : fmt(atmIv(b), 2) + "%"],
      ["Rate", "4.50% continuous"], ["Dividend yield", "0"],
    ].map(([k, v]) => `<span><em>${k}</em> ${v}</span>`).join("");
    const notes = [];
    if (Math.abs(Number(a.dte) - Number(b.dte)) > 0.5) notes.push("The two dates do not share the same DTE. IV-only attribution still freezes Date A's maturity.");
    if (state.built && state.built.missingGrid) notes.push(state.built.missingGrid);
    if (state.mode === "strike") notes.push("Strike-wise. The curve is the file's ATM, ATM+100, ATM−100 grid. The same offset is compared across days, so the absolute strikes change when ATM moves.");
    if (state.mode === "delta") notes.push("Delta-wise. The curve uses the file's own delta nodes (5Δ through 45Δ, plus ATM). The same delta is compared across days. Puts stay on the negative side and calls on the positive side.");
    const missing = (state.built.rows || []).filter((row) => !row.available).length;
    if (missing) notes.push(missing + " spread" + (missing === 1 ? "" : "s") + " unavailable because a strike or IV is outside the data.");
    el("saWarn").textContent = notes.join(" ");
  }

  function smileNodes(obj) {
    if (state.mode === "delta") {
      return (obj.delta_nodes || []).filter((row) => Number.isFinite(Number(row.iv)) && Number.isFinite(Number(row.delta)))
        .map((row) => ({
          x: Number(row.delta),
          label: row.label,
          side: row.side,
          strike: Number(row.strike),
          iv: Number(row.iv),
          delta: Number(row.delta),
        }))
        .sort((a, b) => a.x - b.x);
    }
    return (obj.smile || []).filter((row) => Number.isFinite(Number(row.iv)))
      .map((row) => ({
        x: Number(row.offset),
        label: row.label || ((Number(row.offset) > 0 ? "+" : "") + Math.round(Number(row.offset))),
        side: row.side,
        strike: Number(row.strike),
        iv: Number(row.iv),
        delta: Number(row.delta),
      }))
      .sort((a, b) => a.x - b.x);
  }

  function paintSmile(a, b) {
    const nodesA = smileNodes(a);
    const nodesB = smileNodes(b);
    const note = el("saSmileNote");
    if (state.mode === "delta" && !nodesA.length) {
      note.textContent = "Delta-wise nodes are the workbook columns labelled 5 delta call, 25 delta put, ATM, and so on. Choose the 12 Oct or 16 Oct workbook to plot them.";
      plot("saSmile", [], "Delta-wise IV smile", "File delta", "IV (%)");
      plot("saSmileChg", [], "IV change", "File delta", "Vol points");
      el("saSmileTable").innerHTML = "";
      return;
    }
    note.textContent = state.mode === "delta"
      ? "X-axis is the file's signed delta. Puts are negative, calls are positive, and ATM is its own node. Date A is solid and Date B is dashed. The two sides are not joined into one line."
      : "X-axis is the file's strike offset from that date's ATM: put wing, ATM, then call wing. Date A is solid and Date B is dashed.";
    const traces = [];
    const sides = state.mode === "delta" ? ["put", "call"] : ["all"];
    sides.forEach((side) => {
      const filter = (rows) => side === "all" ? rows : rows.filter((row) => String(row.side || "").toLowerCase().startsWith(side[0]) || (side === "call" && String(row.label).toLowerCase() === "atm"));
      const sa = filter(nodesA);
      const sb = filter(nodesB);
      const color = side === "put" ? "#f0883e" : "#58a6ff";
      const nameA = state.mode === "delta" ? state.dateA + " " + side : state.dateA;
      const nameB = state.mode === "delta" ? state.dateB + " " + side : state.dateB;
      traces.push({
        x: sa.map((row) => row.x), y: sa.map((row) => row.iv), name: nameA, mode: "lines+markers",
        line: { color, width: 2 },
        customdata: sa.map((row) => [row.label, row.strike, row.delta]),
        hovertemplate: "%{customdata[0]}<br>IV %{y:.2f}%<br>K %{customdata[1]:.2f}<br>file delta %{customdata[2]:.3f}<extra>" + nameA + "</extra>",
      });
      traces.push({
        x: sb.map((row) => row.x), y: sb.map((row) => row.iv), name: nameB, mode: "lines+markers",
        line: { color, width: 2, dash: "dash" },
        customdata: sb.map((row) => [row.label, row.strike, row.delta]),
        hovertemplate: "%{customdata[0]}<br>IV %{y:.2f}%<br>K %{customdata[1]:.2f}<br>file delta %{customdata[2]:.3f}<extra>" + nameB + "</extra>",
      });
    });
    const xTitle = state.mode === "delta" ? "File delta (puts negative)" : "ATM offset (points)";
    plot("saSmile", traces, state.mode === "delta" ? "Delta-wise IV smile" : "Strike-wise IV smile", xTitle, "IV (%)");
    const byX = new Map(nodesB.map((row) => [state.mode === "delta" ? row.label : row.x, row]));
    const changes = nodesA.map((row) => {
      const other = byX.get(state.mode === "delta" ? row.label : row.x);
      return other ? { x: row.x, d: other.iv - row.iv, label: row.label, other } : null;
    }).filter(Boolean);
    plot("saSmileChg", [{
      x: changes.map((row) => row.x), y: changes.map((row) => row.d),
      customdata: changes.map((row) => row.label),
      mode: "lines+markers", name: "IV change, vol points", line: { color: "#bc8cff", width: 2 },
      hovertemplate: "%{customdata}<br>%{y:.2f} vol pts<extra></extra>",
    }], "IV change at the same " + (state.mode === "delta" ? "delta node" : "ATM offset"), xTitle, "Vol points");
    const head = "<tr><th>Node</th><th>Strike A</th><th>File delta A</th><th>IV A %</th><th>Strike B</th><th>IV B %</th><th>Vol-pt change</th></tr>";
    const body = changes.map((row) => {
      const src = nodesA.find((item) => item.x === row.x && item.label === row.label);
      return `<tr><td>${row.label}</td><td>${fmt(src.strike, 2)}</td><td>${fmt(src.delta, 3)}</td><td>${fmt(src.iv, 2)}</td><td>${fmt(row.other.strike, 2)}</td><td>${fmt(row.other.iv, 2)}</td><td>${fmt(row.d, 2)}</td></tr>`;
    }).join("");
    el("saSmileTable").innerHTML = head + body;
  }

  function paintSpreads() {
    const rows = validRows();
    const labels = rows.map(xOf);
    plot("saLegIv", [
      { x: labels, y: rows.map((r) => r.ivnA), name: "Near A", mode: "lines+markers", line: { color: "#58a6ff" } },
      { x: labels, y: rows.map((r) => r.ivfA), name: "Far A", mode: "lines+markers", line: { color: "#58a6ff", dash: "dot" } },
      { x: labels, y: rows.map((r) => r.ivnB), name: "Near B", mode: "lines+markers", line: { color: "#3fb950" } },
      { x: labels, y: rows.map((r) => r.ivfB), name: "Far B", mode: "lines+markers", line: { color: "#3fb950", dash: "dot" } },
    ], "Near and far leg IV", "Spread", "IV (%)");
    plot("saGap", [
      { x: labels, y: rows.map((r) => r.gapA), name: "Gap A", mode: "lines+markers", line: { color: "#d29922" } },
      { x: labels, y: rows.map((r) => r.gapB), name: "Gap B", mode: "lines+markers", line: { color: "#db61a2" } },
      { x: labels, y: rows.map((r) => r.dGap), name: "Local IV-gap change", mode: "lines+markers", line: { color: "#bc8cff" } },
    ], "Local IV gap, near minus far", "Spread", "Vol points");
    const hover = rows.map((r) => `K ${r.kn.toFixed(0)}/${r.kf.toFixed(0)}<br>IV ${r.ivnA.toFixed(2)}/${r.ivfA.toFixed(2)} to ${r.ivnB.toFixed(2)}/${r.ivfB.toFixed(2)}<br>model spread ${r.spreadA.toFixed(2)} to ${r.spreadB.toFixed(2)}`);
    plot("saPrem", [
      { x: labels, y: rows.map((r) => r.spreadA), name: "Model spread A", mode: "lines+markers", text: hover, hoverinfo: "text+name", line: { color: "#58a6ff" } },
      { x: labels, y: rows.map((r) => r.spreadB), name: "Model spread B", mode: "lines+markers", text: hover, hoverinfo: "text+name", line: { color: "#3fb950", dash: "dash" } },
    ], state.side + " model-implied spread premium", "Spread", "Premium points");
    plot("saPremChg", [{
      x: labels, y: rows.map((r) => r.dSpread), name: "Full model change on each date's own spot and maturity",
      mode: "lines+markers", line: { color: "#f0883e" },
    }, {
      x: labels, y: rows.map((r) => r.attr ? r.attr.ivOnly : null), name: "IV-only change, Date A inputs frozen",
      mode: "lines+markers", line: { color: "#bc8cff" },
    }], "Spread premium change", "Spread", "Premium points");
  }

  function sortValue(row, key) {
    const attr = row.attr || {};
    const map = {
      location: row.kn,
      absPrem: Math.abs(row.dSpread || 0),
      absGap: Math.abs(row.dGap || 0),
      absVega: Math.abs(row.gA ? row.gA.vega : 0),
      shL: attr.shapleyL || 0,
      shA: attr.shapleyA || 0,
      igL: attr.igL || 0,
      igA: attr.igA || 0,
      methodDiff: attr.shapleyL != null ? Math.abs(attr.shapleyL - attr.igL) : 0,
    };
    return map[key];
  }

  function paintTable() {
    const rows = (state.built.rows || []).slice().sort((a, b) => {
      const av = a.available ? sortValue(a, state.sortKey) : -Infinity;
      const bv = b.available ? sortValue(b, state.sortKey) : -Infinity;
      return (av - bv) * state.sortDir;
    });
    const th = (key, label) => `<th data-sort="${key}">${label}</th>`;
    const head = `<tr>${th("location", "Location")}<th>Strikes</th><th>IV near/far A</th><th>Gap A</th><th>IV near/far B</th><th>Gap change</th><th>Model spread A</th><th>Model spread B</th><th>Full model change</th><th>Recorded spread A</th><th>Recorded spread B</th>${th("absVega", "Net vega A")}<th>Net delta A</th><th>Net gamma A</th><th>Net theta A</th><th>Net volga A</th><th>Net vanna A</th>${th("shL", "Shapley level")}${th("shA", "Shapley skew")}${th("igL", "IG level")}${th("igA", "IG skew")}${th("methodDiff", "|method diff|")}<th>Lookup</th></tr>`;
    const body = rows.map((r) => {
      if (!r.available) return `<tr><td>${xOf(r)}</td><td colspan="21">${r.reason}</td></tr>`;
      const g = r.gA;
      const attr = r.attr;
      return `<tr><td>${xOf(r)}</td><td>${fmt(r.kn, 2)} / ${fmt(r.kf, 2)}</td><td>${fmt(r.ivnA, 2)} / ${fmt(r.ivfA, 2)}</td><td>${fmt(r.gapA, 2)}</td><td>${fmt(r.ivnB, 2)} / ${fmt(r.ivfB, 2)}</td><td>${fmt(r.dGap, 2)}</td><td>${fmt(r.spreadA, 2)}</td><td>${fmt(r.spreadB, 2)}</td><td>${fmt(r.dSpread, 2)}</td><td>${fmt(r.recordedA, 2)}</td><td>${fmt(r.recordedB, 2)}</td><td>${fmt(g.vega, 4)}</td><td>${fmt(g.delta, 4)}</td><td>${fmt(g.gamma, 6)}</td><td>${fmt(g.theta, 4)}</td><td>${fmt(g.volga, 4)}</td><td>${fmt(g.vanna, 4)}</td><td>${attr ? fmt(attr.shapleyL, 4) : "—"}</td><td>${attr ? fmt(attr.shapleyA, 4) : "—"}</td><td>${attr ? fmt(attr.igL, 4) : "—"}</td><td>${attr ? fmt(attr.igA, 4) : "—"}</td><td>${attr ? fmt(Math.abs(attr.shapleyL - attr.igL), 4) : "—"}</td><td>${r.interpolated ? r.howB : "exact"}</td></tr>`;
    }).join("");
    el("saTable").innerHTML = head + body;
  }

  function attributed() {
    return validRows().filter((row) => row.attr);
  }

  function paintAttribution() {
    const rows = attributed();
    const labels = rows.map(xOf);
    const none = rows.length ? "" : "No fixed-strike attribution for this selection.";
    plot("saShapley", [
      { x: labels, y: rows.map((r) => r.attr.shapleyL), name: "Common leg-IV", mode: "lines+markers", line: { color: "#58a6ff" } },
      { x: labels, y: rows.map((r) => r.attr.shapleyA), name: "Local IV-gap", mode: "lines+markers", line: { color: "#f0883e" } },
      { x: labels, y: rows.map((r) => r.attr.ivOnly), name: "IV-only total", mode: "lines", line: { color: "#e6edf3", dash: "dot" } },
    ], "Shapley contributions" + (none ? " — " + none : ""), "Spread", "Premium points");
    plot("saIntegrated", [
      { x: labels, y: rows.map((r) => r.attr.igL), name: "Common leg-IV", mode: "lines+markers", line: { color: "#58a6ff" } },
      { x: labels, y: rows.map((r) => r.attr.igA), name: "Local IV-gap", mode: "lines+markers", line: { color: "#f0883e" } },
      { x: labels, y: rows.map((r) => r.attr.ivOnly), name: "IV-only total", mode: "lines", line: { color: "#e6edf3", dash: "dot" } },
    ], "Integrated-Greeks contributions", "Spread", "Premium points");
    plot("saDiff", [
      { x: labels, y: rows.map((r) => r.attr.shapleyL - r.attr.igL), name: "Level, Shapley minus integrated", mode: "lines+markers", line: { color: "#58a6ff" } },
      { x: labels, y: rows.map((r) => r.attr.shapleyA - r.attr.igA), name: "Skew, Shapley minus integrated", mode: "lines+markers", line: { color: "#f0883e" } },
    ], "Method difference", "Spread", "Premium points");
    const useSh = state.method !== "integrated";
    const levelShare = rows.map((r) => (useSh ? r.sharesSh : r.sharesIg).grossLevel);
    const skewShare = rows.map((r) => (useSh ? r.sharesSh : r.sharesIg).grossSkew);
    plot("saShare", [
      { x: labels, y: levelShare, name: "Gross level share", type: "bar", marker: { color: "#58a6ff" } },
      { x: labels, y: skewShare, name: "Gross skew share", type: "bar", marker: { color: "#f0883e" } },
    ], "Gross absolute contribution share (" + (useSh ? "Shapley" : "integrated") + ")", "Spread", "Percent");
    const signed = rows.map((r) => useSh ? r.sharesSh : r.sharesIg);
    plot("saSigned", [
      { x: labels, y: signed.map((s) => s.signedLevel), name: "Signed level % of IV-only change", mode: "lines+markers", line: { color: "#58a6ff" } },
      { x: labels, y: signed.map((s) => s.signedSkew), name: "Signed skew % of IV-only change", mode: "lines+markers", line: { color: "#f0883e" } },
    ], "Signed contribution versus the net IV-only change", "Spread", "Percent");
    plot("saReconcile", [
      { x: labels, y: rows.map((r) => r.attr.ivOnly), name: "IV-only premium change", mode: "lines", line: { color: "#e6edf3", width: 3 } },
      { x: labels, y: rows.map((r) => r.attr.shapleyTotal), name: "Shapley sum", mode: "markers", marker: { color: "#58a6ff", size: 8 } },
      { x: labels, y: rows.map((r) => r.attr.igTotal), name: "Integrated sum", mode: "markers", marker: { symbol: "diamond", color: "#3fb950", size: 7 } },
    ], "Observed IV-only change and the sum of each method", "Spread", "Premium points");
    const diffs = rows.map((r) => Math.abs(r.attr.shapleyL - r.attr.igL));
    const errs = rows.map((r) => Math.max(Math.abs(r.attr.shapleyError), Math.abs(r.attr.igError)));
    const conv = rows.map((r) => r.attr.igConvergence);
    const mean = diffs.length ? diffs.reduce((s, v) => s + v, 0) / diffs.length : null;
    const rms = diffs.length ? Math.sqrt(diffs.reduce((s, v) => s + v * v, 0) / diffs.length) : null;
    el("saMethodStats").innerHTML = [
      ["Spreads attributed", String(rows.length)],
      ["Max |level method difference|", fmt(diffs.length ? Math.max(...diffs) : null, 4)],
      ["Mean |level method difference|", fmt(mean, 4)],
      ["RMS level method difference", fmt(rms, 4)],
      ["Max |reconciliation error|", fmt(errs.length ? Math.max(...errs) : null, 6)],
      ["Max 8-pt vs 16-pt quadrature gap", fmt(conv.length ? Math.max(...conv) : null, 6)],
    ].map(([k, v]) => `<span><em>${k}</em> ${v}</span>`).join("");
    el("saCards").innerHTML = rows.map((r) => {
      const pack = state.method === "integrated" ? { L: r.attr.igL, A: r.attr.igA, sh: r.sharesIg } : { L: r.attr.shapleyL, A: r.attr.shapleyA, sh: r.sharesSh };
      const larger = Math.abs(pack.L) === Math.abs(pack.A) ? "the two factors match in magnitude" : (Math.abs(pack.L) > Math.abs(pack.A) ? "common leg-IV is larger in magnitude" : "local IV-gap is larger in magnitude");
      return `<article><b>${xOf(r)}</b><p>${larger}. Level ${fmt(pack.L, 2)} (${pctShare(pack.sh.grossLevel)} gross, ${pctShare(pack.sh.signedLevel)} of the net). Skew ${fmt(pack.A, 2)} (${pctShare(pack.sh.grossSkew)} gross, ${pctShare(pack.sh.signedSkew)} of the net). This is a decomposition of the last change, not a trade signal.</p></article>`;
    }).join("");
  }

  function paintFit(a, b) {
    const math = window.SpreadMath;
    const fa = math.fitQuadratic(math.sideRows(a, state.side), Number(a.atm_strike), 500);
    const fb = math.fitQuadratic(math.sideRows(b, state.side), Number(b.atm_strike), 500);
    if (!fa || !fb) {
      el("saFit").textContent = "Not enough smile points to fit a quadratic.";
      return;
    }
    el("saFit").innerHTML = `<p>Date A: level ${fmt(fa.a, 2)}%, skew slope ${fmt(fa.b, 2)}, curvature ${fmt(fa.c, 2)}, residual RMSE ${fmt(fa.rmse, 3)} vol points on ${fa.n} points.</p><p>Date B: level ${fmt(fb.a, 2)}%, skew slope ${fmt(fb.b, 2)}, curvature ${fmt(fb.c, 2)}, residual RMSE ${fmt(fb.rmse, 3)} vol points on ${fb.n} points.</p><p>Change in fitted coefficients: level ${fmt(fb.a - fa.a, 2)} vol points, slope ${fmt(fb.b - fa.b, 2)}, curvature ${fmt(fb.c - fa.c, 2)}. Wing residuals are not assigned to skew or curvature.</p>`;
  }

  function exportCsv() {
    const rows = state.built ? state.built.rows : [];
    const headers = ["dateA", "dateB", "side", "mode", "kn", "kf", "available", "ivnA", "ivfA", "ivnB", "ivfB", "gapA", "gapB", "spreadA", "spreadB", "fullModelChange", "ivOnly", "shapleyLevel", "shapleySkew", "igLevel", "igSkew", "shapleyError", "igError", "reason"];
    const lines = [headers.join(",")];
    rows.forEach((r) => {
      const attr = r.attr || {};
      const vals = [state.dateA, state.dateB, r.side, r.mode, r.kn, r.kf, r.available, r.ivnA, r.ivfA, r.ivnB, r.ivfB, r.gapA, r.gapB, r.spreadA, r.spreadB, r.dSpread, attr.ivOnly, attr.shapleyL, attr.shapleyA, attr.igL, attr.igA, attr.shapleyError, attr.igError, r.reason || ""];
      lines.push(vals.map((v) => v === undefined || v === null ? "" : String(v)).join(","));
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "spread-analysis-" + state.dateA + "-" + state.dateB + ".csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  function mount(data) {
    window.DATA = data || window.DATA;
    const root = el("spread-root");
    if (!root || !window.SpreadMath) return;
    if (!root.dataset.ready) {
      root.innerHTML = shell();
      if (!el("saStyle")) {
        const style = document.createElement("style");
        style.id = "saStyle";
        style.textContent = ".sa-block{margin:18px 0;padding:14px;border:1px solid #30363d;border-radius:10px;background:#0d1117}.sa-block h2{margin:0 0 10px;font-size:18px}.sa-controls,.sa-nav{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}.sa-controls label,.sa-block label{display:flex;flex-direction:column;gap:4px;font-size:12px;color:#8b949e}.sa-controls select,.sa-nav button,button{background:#161b22;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:6px 8px}.sa-nav button:disabled{opacity:.4}.sa-summary{display:flex;flex-wrap:wrap;gap:8px}.sa-summary span{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:4px 8px}.sa-summary em{color:#8b949e;font-style:normal;margin-right:4px}.sa-warn{color:#d29922}.sa-note{color:#8b949e;font-size:13px}.sa-chart{height:360px;margin:8px 0}.sa-scroll{overflow:auto;max-height:420px}.sa-scroll table{border-collapse:collapse;font-size:12px;min-width:1400px}.sa-scroll th,.sa-scroll td{border-bottom:1px solid #21262d;padding:4px 6px;text-align:right;white-space:nowrap}.sa-scroll th{cursor:pointer;position:sticky;top:0;background:#161b22}.sa-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}.sa-cards article{border:1px solid #30363d;border-radius:8px;padding:8px;background:#161b22}.sa-cards p{margin:6px 0 0;color:#c9d1d9;font-size:12px}";
        document.head.appendChild(style);
      }
      bind();
      root.dataset.ready = "1";
    }
    render();
  }

  window.SpreadLab = { mount, render };
})();
